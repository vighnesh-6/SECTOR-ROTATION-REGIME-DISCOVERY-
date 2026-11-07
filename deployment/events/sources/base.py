"""Verified HTTPS fetching and strict official RSS ingestion."""
from __future__ import annotations
import hashlib
import ssl
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from deployment.events.clock import now_ist
from deployment.events.models import MacroEvent
from deployment.events.normalization import normalize_event, normalize_datetime_to_date

class SourceError(RuntimeError):
    """Safe diagnostics without response bodies or credentials."""

class BaseEventSource(ABC):
    @property
    @abstractmethod
    def name(self): ...
    @property
    @abstractmethod
    def institution(self): ...
    @abstractmethod
    def fetch_events(self, start_date, end_date): ...

    def fetch_incremental(self, start_date, end_date):
        raise SourceError("Live adapter unavailable")

    def fetch_latest(self, days_back=14):
        from datetime import timedelta
        end = now_ist().date()
        return self.fetch_incremental((end-timedelta(days=days_back)).isoformat(), end.isoformat())

    @staticmethod
    def _http_get(url, headers=None, timeout=20, retries=3):
        if urlparse(url).scheme != "https":
            raise SourceError("HTTPS required")
        class OfficialRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, msg, hdrs, newurl):
                old, new = urlparse(request.full_url), urlparse(newurl)
                if new.scheme != "https" or (old.hostname or "").removeprefix("www.") != (new.hostname or "").removeprefix("www."):
                    raise SourceError("Unexpected source redirect")
                return super().redirect_request(request, fp, code, msg, hdrs, newurl)
        opener = urllib.request.build_opener(OfficialRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        request = urllib.request.Request(url, headers={"User-Agent": "SectorRotationEvents/1.0", "Accept": "application/rss+xml,application/xml,text/xml", **(headers or {})})
        for attempt in range(retries):
            try:
                with opener.open(request, timeout=timeout) as response:
                    data = response.read(5_000_001)
                    if not data or len(data) > 5_000_000:
                        raise SourceError("Empty or oversized source response")
                    return data
            except SourceError:
                raise
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt + 1 < retries:
                    time.sleep(2 ** attempt)
        raise SourceError("Source fetch failed after bounded retries")

    def parse_official_rss(self, url, keywords, hosts, region, category=None):
        data = self._http_get(url)
        if not data:
            raise SourceError("Empty source response")
        try:
            root = ET.fromstring(data)
        except (ET.ParseError, ValueError):
            raise SourceError("Invalid RSS XML") from None
        channel = root.find("channel")
        if root.tag != "rss" or channel is None:
            raise SourceError("Expected RSS channel")
        events = []
        publication_dates = []
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                raise SourceError("RSS item has no title")
            published_value = (item.findtext("pubDate") or "").strip()
            if not published_value:
                raise SourceError("RSS item has no publication date")
            try:
                publication_dates.append(normalize_datetime_to_date(published_value))
            except ValueError:
                raise SourceError("Invalid RSS publication date") from None
            if not any(k in title.lower() for k in keywords):
                continue
            published = (item.findtext("pubDate") or "").strip()
            link = (item.findtext("link") or "").strip()
            parsed = urlparse(link)
            if not published or parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password:
                raise SourceError("Relevant RSS item lacks valid date or official HTTPS reference")
            try:
                dt, cat, clean_title, sev, reg, end, _ = normalize_event(title, published, raw_category=category, region=region, source_institution=self.institution)
                if dt > now_ist().date().isoformat():
                    raise ValueError("Future publication")
                events.append(MacroEvent(date=dt, category=cat, title=clean_title, severity=sev, region=reg, end_date=end, source_institution=self.institution, raw_source_url=link, source_id="EVT:" + hashlib.sha256(link.encode()).hexdigest()[:40]))
            except ValueError:
                raise SourceError("Invalid relevant RSS event") from None
        self.oldest_publication = min(publication_dates) if publication_dates else None
        return events
