"""
deployment/events/sources/sebi_nse.py
=====================================
SEBI & NSE Regulatory and Market Structure Official Source Client.
Covers capital market reforms, index derivative frameworks, settlement cycles (T+1, T+0),
and major market-wide regulatory circulars.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List, Optional

from deployment.events.models import MacroEvent
from deployment.events.normalization import normalize_event
from .base import BaseEventSource

logger = logging.getLogger("sebi_nse_source")


class SebiNseSource(BaseEventSource):
    """
    Client for SEBI and NSE market regulation announcements.
    """

    # Official verified market-wide regulatory circulars and framework transitions
    HISTORICAL_CIRCULARS = [
        ("2020-03-20", "SEBI introduces enhanced market volatility margin framework and short-selling curbs amid COVID crash", "Domestic market shock", "high", "SEBI"),
        ("2020-09-01", "SEBI peak margin reporting framework phase 1 enters into force for equity derivatives", "Domestic market shock", "medium", "SEBI"),
        ("2021-09-01", "SEBI 100% upfront peak margin requirement implemented across cash and derivatives segments", "Domestic market shock", "high", "SEBI"),
        ("2023-01-27", "Indian capital markets complete phased transition to T+1 rolling settlement cycle across all equities", "Indian policy", "high", "SEBI / NSE"),
        ("2024-03-28", "SEBI launches optional T+0 settlement beta version for top 25 liquid equities", "Indian policy", "medium", "SEBI / NSE"),
        ("2026-10-01", "SEBI issues 6-point index derivative framework to curb speculative retail trading: upfront option premium and single weekly expiry", "Domestic market shock", "high", "SEBI"),
    ]

    @property
    def name(self) -> str:
        return "SEBI Market Regulation"

    @property
    def institution(self) -> str:
        return "SEBI / NSE"

    def fetch_incremental(self, start_date, end_date):
        # SEBI RSS includes circulars and enforcement items; retain market-wide policy only.
        events = self.parse_official_rss(
            "https://www.sebi.gov.in/sebirss.xml",
            ["derivative", "settlement", "margin", "market infrastructure", "short selling", "short-selling", "trading framework"],
            ["www.sebi.gov.in", "sebi.gov.in"], "India", "Domestic market shock")
        return [event for event in events if start_date <= event.date <= end_date]

    def recover_official_interval(self, start_date, end_date):
        from deployment.events.sources.archive import discover
        return discover(self, start_date, end_date, 'sebi', ['derivative', 'settlement', 'margin', 'market infrastructure', 'short selling', 'short-selling', 'trading framework'], 'Domestic market shock')

    def fetch_events(self, start_date: str, end_date: str) -> List[MacroEvent]:
        results: List[MacroEvent] = []

        for ev_date, title, cat, sev, inst in self.HISTORICAL_CIRCULARS:
            if start_date <= ev_date <= end_date:
                dt_str, clean_cat, clean_title, clean_sev, reg, end_d, src_id = normalize_event(
                    title=title,
                    raw_date=ev_date,
                    raw_category=cat,
                    raw_severity=sev,
                    region="India",
                    source_institution=inst,
                )
                results.append(
                    MacroEvent(
                        date=dt_str,
                        category=clean_cat,
                        title=clean_title,
                        severity=clean_sev,
                        region=reg,
                        end_date=end_d,
                        source_id=f"SEBI_{dt_str.replace('-', '')}",
                        source_institution=inst,
                        raw_source_url="https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&smid=0&ssid=7",
                    )
                )

        logger.info(f"SebiNseSource: Retrieved {len(results)} events for window [{start_date}, {end_date}].")
        return results

