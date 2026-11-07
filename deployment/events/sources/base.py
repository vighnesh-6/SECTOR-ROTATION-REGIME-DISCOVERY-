"""Verified HTTPS fetching and strict official RSS ingestion."""
from __future__ import annotations
import hashlib
import ssl
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from deployment.events.clock import now_ist
from deployment.events.models import MacroEvent
from deployment.events.normalization import normalize_event, normalize_datetime_to_date

class SourceError(RuntimeError):
    """Safe diagnostics without response bodies or credentials."""

class FeedValidationError(SourceError):
    """Valid items survive malformed siblings, but the source remains incomplete."""
    def __init__(self, events, diagnostics):
        super().__init__(f"RSS feed rejected {diagnostics['rejected_items']} of {diagnostics['total_items']} items")
        self.events = events
        self.diagnostics = diagnostics

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
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(2 ** attempt)
        raise SourceError("Source fetch failed after bounded retries") from last_error

    def parse_official_rss(self, url, keywords, hosts, region, category=None):
        # Reset metadata even when a reused adapter fails before parsing.
        self.oldest_publication = None
        self.newest_publication = None
        self.feed_diagnostics = {'total_items':0,'valid_items':0,'accepted_events':0,
                                 'ignored_items':0,'rejected_items':0,'rejection_reasons':{},
                                 'rejected_item_details':[], 'oldest_publication':None,
                                 'newest_publication':None,'complete':False}
        data = self._http_get(url)
        if not data:
            raise SourceError("Empty source response")
        try:
            root = ET.fromstring(data)
        except (ET.ParseError, ValueError) as exc:
            raise SourceError("Invalid RSS XML") from exc
        channel = root.find("channel")
        if root.tag != "rss" or channel is None:
            raise SourceError("Expected RSS channel")
        events, publication_dates = [], []
        reasons = Counter()
        items = channel.findall("item")
        self.feed_diagnostics['total_items'] = len(items)
        today = now_ist().date().isoformat()
        def reject(index, reason):
            reasons[reason] += 1
            if len(self.feed_diagnostics['rejected_item_details']) < 20:
                self.feed_diagnostics['rejected_item_details'].append({'item_index':index,'reason':reason})
        for index, item in enumerate(items, start=1):
            title = (item.findtext("title") or "").strip()
            if not title:
                reject(index, 'missing_title')
                continue
            published = (item.findtext("pubDate") or "").strip()
            if not published:
                reject(index, 'missing_publication_date')
                continue
            try:
                dt = normalize_datetime_to_date(published)
            except (ValueError, TypeError, OverflowError):
                reject(index, 'malformed_publication_date')
                continue
            if not '2019-01-01' <= dt <= today:
                reject(index, 'publication_date_out_of_bounds')
                continue
            # All trustworthy dated items contribute to retention diagnostics,
            # including non-policy announcements; never only the matching events.
            publication_dates.append(dt)
            if not any(k in title.lower() for k in keywords):
                self.feed_diagnostics['ignored_items'] += 1
                self.feed_diagnostics['valid_items'] += 1
                continue
            link = (item.findtext("link") or "").strip()
            try:
                parsed = urlparse(link)
                official = parsed.scheme == 'https' and parsed.hostname in hosts and not parsed.username and not parsed.password
            except ValueError:
                official = False
            if not official:
                reject(index, 'invalid_official_reference')
                continue
            try:
                dt, cat, clean_title, sev, reg, end, _ = normalize_event(title, published, raw_category=category, region=region, source_institution=self.institution)
                events.append(MacroEvent(date=dt, category=cat, title=clean_title, severity=sev, region=reg, end_date=end, source_institution=self.institution, raw_source_url=link, source_id="EVT:" + hashlib.sha256(link.encode()).hexdigest()[:40]))
                self.feed_diagnostics['valid_items'] += 1
            except (ValueError, TypeError, OverflowError):
                reject(index, 'invalid_event')
        self.oldest_publication = min(publication_dates) if publication_dates else None
        self.newest_publication = max(publication_dates) if publication_dates else None
        self.feed_diagnostics.update(
            oldest_publication=self.oldest_publication, newest_publication=self.newest_publication,
            accepted_events=len(events), rejected_items=sum(reasons.values()),
            rejection_reasons=dict(reasons), complete=not reasons)
        if reasons:
            raise FeedValidationError(events, dict(self.feed_diagnostics))
        return events
