"""
deployment/events/normalization.py
==================================
Taxonomy, date, timezone, severity, and region normalization for macroeconomic events.
Ensures uniform naming standards across all official sources.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Tuple


CANONICAL_CATEGORIES = {
    "Monetary policy",
    "US monetary policy",
    "European monetary policy",
    "Japan monetary policy",
    "Indian policy",
    "Fiscal / corporate policy",
    "Trade / FTA",
    "Trade policy",
    "Global trade policy",
    "Global trade policy / geopolitics",
    "Geopolitical",
    "Elections",
    "International summit",
    "Banking crisis",
    "Domestic market shock",
    "Global market shock",
    "Pandemic",
    "Pandemic / market shock",
}


def normalize_datetime_to_date(dt_input: str | datetime) -> str:
    """Date-only values stay dates; timestamped releases are converted to IST."""
    from datetime import date
    from deployment.events.clock import IST
    if isinstance(dt_input, datetime):
        dt = dt_input
    else:
        value = str(dt_input).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value).isoformat()
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = parsedate_to_datetime(value)
            except (ValueError, TypeError):
                try:
                    dt = datetime.strptime(value, "%d %b, %Y %z")
                    return dt.astimezone(IST).date().isoformat()
                except ValueError:
                    pass
                for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%B %d, %Y"):
                    try:
                        return datetime.strptime(value, fmt).date().isoformat()
                    except ValueError:
                        continue
                raise ValueError("Invalid event publication date") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(IST).date().isoformat()


def normalize_category(
    title: str,
    raw_category: Optional[str] = None,
    source_institution: Optional[str] = None,
) -> str:
    """
    Maps raw categories and headlines to canonical research categories.
    """
    if raw_category and raw_category in CANONICAL_CATEGORIES:
        return raw_category

    t_lower = title.lower()
    src = (source_institution or "").lower()

    if "federal reserve" in t_lower or "fomc" in t_lower or "fed" in t_lower or "us_fed" in src:
        return "US monetary policy"
    if "bank of japan" in t_lower or "boj" in t_lower:
        return "Japan monetary policy"
    if "european central bank" in t_lower or "ecb" in t_lower:
        return "European monetary policy"
    if "rbi" in t_lower or "mpc" in t_lower or "repo" in t_lower or "rbi" in src:
        return "Monetary policy"
    if "sebi" in t_lower or "derivative" in t_lower or "f&o" in t_lower or "circular" in t_lower:
        return "Domestic market shock"
    if "gst" in t_lower or "budget" in t_lower or "tax" in t_lower or "fiscal" in t_lower:
        return "Fiscal / corporate policy"
    if "cpi" in t_lower or "inflation" in t_lower or "iip" in t_lower or "gdp" in t_lower or "mospi" in src:
        return "Indian policy"
    if "fta" in t_lower or "cepa" in t_lower or "tariff" in t_lower or "trade" in t_lower:
        return "Trade / FTA"
    if "election" in t_lower or "lok sabha" in t_lower or "poll" in t_lower:
        return "Elections"
    if "summit" in t_lower or "brics" in t_lower or "g20" in t_lower:
        return "International summit"
    if "war" in t_lower or "military" in t_lower or "geopolit" in t_lower:
        return "Geopolitical"

    return "Indian policy" if "india" in src else "Fiscal / corporate policy"


def infer_severity(title: str, raw_severity: Optional[str] = None) -> str:
    """
    Standardizes impact severity to ('low', 'medium', 'high').
    """
    if raw_severity and raw_severity.lower() in ("low", "medium", "high"):
        return raw_severity.lower()

    t = title.lower()
    high_keywords = [
        "rate cut", "emergency", "crisis", "framework", "election", "budget",
        "fta enters into force", "pandemic", "lockdown", "50 bps", "strike",
        "interim trade agreement", "neutral", "unwind", "tariff takes effect"
    ]
    for hk in high_keywords:
        if hk in t:
            return "high"

    low_keywords = ["treasury bills", "extract", "bulletin", "weekly statistical", "routine"]
    for lk in low_keywords:
        if lk in t:
            return "low"

    return "medium"


def infer_region(title: str, source_institution: str) -> str:
    """
    Infers the primary geographic region for the event.
    """
    t = title.lower()
    src = source_institution.lower()

    if "us" in src or "federal reserve" in t or "fomc" in t:
        return "US"
    if "japan" in src or "bank of japan" in t or "boj" in t:
        return "Japan"
    if "ecb" in src or "european" in t:
        return "Europe"
    if "brics" in t or "global" in t or "who" in t:
        return "Global"
    if "trade agreement" in t or "fta" in t:
        if "india-us" in t or "india - us" in t:
            return "India / US"
        if "india-uk" in t:
            return "India / UK"
        if "india-eu" in t:
            return "India / European Union"
        if "oman" in t:
            return "India / Oman"
        return "India / Global"

    return "India"


def normalize_event(
    title: str,
    raw_date: str | datetime,
    raw_category: Optional[str] = None,
    raw_severity: Optional[str] = None,
    region: Optional[str] = None,
    end_date: Optional[str] = None,
    source_institution: str = "Official",
    source_id: Optional[str] = None,
    raw_source_url: Optional[str] = None,
    actual_value: Optional[str] = None,
    forecast_value: Optional[str] = None,
    previous_value: Optional[str] = None,
) -> Tuple[str, str, str, str, str, str, str]:
    """
    Helper function returning normalized values:
    (date, category, title, severity, region, end_date, source_id)
    """
    clean_date = normalize_datetime_to_date(raw_date)
    clean_cat = normalize_category(title, raw_category, source_institution)
    clean_sev = infer_severity(title, raw_severity)
    clean_reg = region or infer_region(title, source_institution)
    clean_end = normalize_datetime_to_date(end_date) if end_date else clean_date
    clean_src = source_id or f"{source_institution}_{clean_date.replace('-', '')}"

    clean_title = re.sub(r"\s+", " ", title).strip()
    if len(clean_title) > 200:
        clean_title = clean_title[:197] + "..."

    return clean_date, clean_cat, clean_title, clean_sev, clean_reg, clean_end, clean_src

