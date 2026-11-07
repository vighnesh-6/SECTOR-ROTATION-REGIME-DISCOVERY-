"""
deployment/events/sources/mospi_mof.py
======================================
MOSPI (Ministry of Statistics and Programme Implementation) &
Ministry of Finance (MoF) / PIB Official Source Client.
Covers CPI Inflation, IIP, GDP releases, Union Budgets, and Monthly Gross GST Collections.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional

from deployment.events.models import MacroEvent
from deployment.events.normalization import normalize_event
from .base import BaseEventSource

logger = logging.getLogger("mospi_mof_source")


class MospiMofSource(BaseEventSource):
    """
    Client for MOSPI economic indicators and Ministry of Finance fiscal releases.
    """

    PIB_RSS_URL = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1"

    # Official verified releases for key macro checkpoints (2019 - 2026)
    HISTORICAL_RELEASES = [
        # 2019 Inception Events
        ("2019-01-14", "MOSPI releases Consumer Price Index (CPI) for Dec 2018: inflation eases to 2.19%", "Indian policy", "medium", "2.19%", "MOSPI"),
        ("2019-02-01", "Interim Union Budget 2019 presented by Ministry of Finance", "Indian policy", "medium", None, "MoF"),
        ("2019-07-05", "Union Budget 2019 presented by Union Finance Minister", "Indian policy", "medium", None, "MoF"),
        ("2019-09-20", "Historic corporate tax rate reduction announcement (Taxation Laws Ordinance 2019)", "Fiscal / corporate policy", "high", None, "MoF"),
        
        # 2020 COVID / Fiscal
        ("2020-02-01", "Union Budget 2020 presented with simplified income tax regime", "Indian policy", "medium", None, "MoF"),
        ("2020-05-12", "Atmanirbhar Bharat Abhiyan special economic package of Rs 20 lakh crore announced", "Fiscal / corporate policy", "high", "Rs 20L Cr", "MoF"),
        ("2020-10-01", "Gross GST revenue for September 2020 marks first positive growth post-lockdown", "Fiscal / corporate policy", "medium", "Rs 95,480 Cr", "MoF"),
        
        # 2021 - 2025 Milestones
        ("2021-02-01", "Union Budget 2021: Capex outlay increased by 34.5% to boost post-pandemic revival", "Indian policy", "high", None, "MoF"),
        ("2022-02-01", "Union Budget 2022 introduces 30% tax on Virtual Digital Assets and 35.4% capex boost", "Indian policy", "high", None, "MoF"),
        ("2023-02-01", "Union Budget 2023 increases capital investment outlay to Rs 10 lakh crore (3.3% of GDP)", "Indian policy", "high", None, "MoF"),
        ("2024-02-01", "Interim Union Budget 2024: Fiscal deficit pegged at 5.1% of GDP for FY25", "Indian policy", "medium", None, "MoF"),
        ("2024-07-23", "Union Budget 2024: Long-Term Capital Gains (LTCG) tax increased to 12.5%, STCG to 20%", "Fiscal / corporate policy", "high", None, "MoF"),
        ("2025-02-01", "Union Budget 2025 presented with fiscal consolidation pathway to sub-4.5% deficit", "Indian policy", "medium", None, "MoF"),
        ("2026-02-01", "Union Budget 2026 presented by Ministry of Finance", "Indian policy", "medium", None, "MoF"),
        
        # Verified Recent & Post-2026-09-09 Releases
        ("2026-10-01", "Ministry of Finance reports Gross GST Revenue for September 2026 of Rs 1.73 lakh crore (6.5% YoY)", "Fiscal / corporate policy", "medium", "Rs 1.73L Cr", "MoF"),
        ("2026-10-14", "MOSPI All-India CPI Inflation for September 2026 rises to 5.49% on food and vegetable prices", "Indian policy", "medium", "5.49%", "MOSPI"),
        ("2026-10-14", "MOSPI Index of Industrial Production (IIP) for August 2026 contracts by -0.1%", "Indian policy", "medium", "-0.1%", "MOSPI"),
        ("2026-11-01", "Ministry of Finance reports Gross GST Revenue for October 2026 of Rs 1.87 lakh crore (8.9% YoY)", "Fiscal / corporate policy", "medium", "Rs 1.87L Cr", "MoF"),
    ]

    @property
    def name(self) -> str:
        return "MOSPI and Ministry of Finance"

    @property
    def institution(self) -> str:
        return "MOSPI / MoF"

    def fetch_live_pib_rss(self):
        return self.parse_official_rss(self.PIB_RSS_URL, ['gst revenue', 'cpi', 'inflation', 'industrial production', 'fiscal deficit', 'gdp'], ['pib.gov.in', 'www.pib.gov.in'], 'India', None)

    def fetch_incremental(self, start_date, end_date):
        return [event for event in self.fetch_live_pib_rss() if start_date <= event.date <= end_date]

    def recover_official_interval(self, start_date, end_date):
        from deployment.events.sources.archive import discover
        return discover(self, start_date, end_date, 'pib', ['gst revenue', 'cpi', 'inflation', 'industrial production', 'fiscal deficit', 'gdp'], None)

    def fetch_events(self, start_date: str, end_date: str) -> List[MacroEvent]:
        results: List[MacroEvent] = []

        # 1. Historical authoritative releases
        for ev_date, title, cat, sev, actual, inst in self.HISTORICAL_RELEASES:
            if start_date <= ev_date <= end_date:
                dt_str, clean_cat, clean_title, clean_sev, reg, end_d, src_id = normalize_event(
                    title=title,
                    raw_date=ev_date,
                    raw_category=cat,
                    raw_severity=sev,
                    region="India",
                    source_institution=inst,
                    actual_value=actual,
                )
                results.append(
                    MacroEvent(
                        date=dt_str,
                        category=clean_cat,
                        title=clean_title,
                        severity=clean_sev,
                        region=reg,
                        end_date=end_d,
                        source_id=f"{inst}_{dt_str.replace('-', '')}",
                        source_institution=inst,
                        actual_value=actual,
                        raw_source_url="https://pib.gov.in" if inst == "MoF" else "https://mospi.gov.in",
                    )
                )

        # 2. Augment with live PIB releases if window touches present
        if end_date >= datetime.now().strftime("%Y-%m-%d"):
            live = self.fetch_live_pib_rss()
            for ev in live:
                if start_date <= ev.date <= end_date:
                    results.append(ev)

        logger.info(f"MospiMofSource: Retrieved {len(results)} events for window [{start_date}, {end_date}].")
        return results

