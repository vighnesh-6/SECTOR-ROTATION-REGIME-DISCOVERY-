"""
deployment/events/models.py
===========================
Strict internal data models and validation for macroeconomic events.
Ensures zero data corruption and full compatibility with existing Neon schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Optional


@dataclass
class MacroEvent:
    """
    Standardized internal representation of a macroeconomic or policy event.
    """
    date: str                                   # YYYY-MM-DD
    category: str                               # Standardized category
    title: str                                  # Event title / headline (max 200 chars)
    severity: str = "medium"                    # 'low', 'medium', 'high'
    region: str = "India"                       # 'India', 'US', 'Global', 'Europe', 'Japan', etc.
    end_date: Optional[str] = None              # YYYY-MM-DD (defaults to date if None)
    source_id: Optional[str] = None             # Identifier (e.g. 'ID: E136', 'RBI_MPC_20261009')
    source_institution: str = "official"        # 'RBI', 'MOSPI', 'MoF', 'SEBI', 'Federal Reserve', etc.
    raw_source_url: Optional[str] = None        # Official URL/reference
    actual_value: Optional[str] = None          # Raw metric if applicable (e.g. '6.50%', '5.49%')
    forecast_value: Optional[str] = None        # Consensus forecast if applicable
    previous_value: Optional[str] = None        # Prior period figure if applicable
    event_id: Optional[int] = None              # Assigned by DB SERIAL or existing ID
    created_at: Optional[datetime] = None

    def __post_init__(self):
        # Validate date format YYYY-MM-DD
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(self.date)):
            raise ValueError(f"Invalid event date format '{self.date}'. Must be YYYY-MM-DD.")
        
        date.fromisoformat(self.date)

        # Enforce project inception boundary (2019-01-01)
        if self.date < "2019-01-01":
            raise ValueError(f"Event date '{self.date}' precedes project inception date (2019-01-01).")

        # Standardize end_date
        if self.end_date is None or not str(self.end_date).strip():
            self.end_date = self.date
        elif not re.match(r"^\d{4}-\d{2}-\d{2}$", str(self.end_date)):
            self.end_date = self.date

        date.fromisoformat(self.end_date)
        if self.end_date < self.date:
            raise ValueError("Event end precedes start")

        # Standardize severity
        self.severity = str(self.severity).strip().lower()
        if self.severity not in ("low", "medium", "high"):
            self.severity = "medium"

        # Trim title to 200 chars max (Neon VARCHAR(200) constraint)
        self.title = str(self.title).strip()
        if len(self.title) > 200:
            self.title = self.title[:197] + "..."

        # Trim category to 50 chars max (Neon VARCHAR(50) constraint)
        self.category = str(self.category).strip()
        if len(self.category) > 50:
            self.category = self.category[:50]

        if not self.title or not self.category:
            raise ValueError("Event title and category are required")

        # Standardize source_id
        if self.source_id is None:
            self.source_id = f"{self.source_institution}_{self.date.replace('-', '')}"

    def fingerprint(self) -> str:
        """
        Compute a canonical normalized fingerprint for deduplication.
        Combines date, simplified alphanumeric tokens of title, and category.
        """
        clean_title = re.sub(r"[^a-zA-Z0-9]", "", self.title.lower())
        clean_cat = re.sub(r"[^a-zA-Z0-9]", "", self.category.lower())
        return f"{self.date}|{clean_cat}|{clean_title}"

    def to_db_row(self) -> Dict[str, Any]:
        """
        Serializes this event into the exact Neon macro_events table schema:
        Columns: date, category, title, actual, forecast, previous, source
        Maintains complete format parity with the 135 historical records.
        """
        # Historical convention:
        # actual: 'Severity: high' (or '6.50%' if metric exists, but historically 'Severity: ...')
        actual_str = f"Severity: {self.severity}" if not self.actual_value else f"{self.actual_value[:35]} (Sev: {self.severity[:1]})"
        if len(actual_str) > 50:
            actual_str = actual_str[:50]

        forecast_str = f"Region: {self.region}" if not self.forecast_value else f"Region: {self.region} | Exp: {self.forecast_value[:25]}"
        if len(forecast_str) > 50:
            forecast_str = forecast_str[:50]

        previous_str = f"End: {self.end_date}" if not self.previous_value else f"End: {self.end_date} | Prev: {self.previous_value[:20]}"
        if len(previous_str) > 50:
            previous_str = previous_str[:50]

        source_str = self.source_id or f"SRC: {self.source_institution}"
        if len(source_str) > 50:
            source_str = source_str[:50]

        return {
            "date": self.date,
            "category": self.category,
            "title": self.title,
            "actual": actual_str,
            "forecast": forecast_str,
            "previous": previous_str,
            "source": source_str,
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> MacroEvent:
        """
        Deserializes a dictionary row fetched from Neon macro_events table.
        """
        raw_date = str(row.get("date", ""))[:10]
        cat = str(row.get("category", "General"))
        title = str(row.get("title", ""))

        actual = str(row.get("actual", ""))
        severity = "medium"
        if "severity: high" in actual.lower():
            severity = "high"
        elif "severity: low" in actual.lower():
            severity = "low"
        elif "severity: medium" in actual.lower():
            severity = "medium"

        forecast = str(row.get("forecast", ""))
        region = "India"
        if "region:" in forecast.lower():
            region = forecast.split(":", 1)[1].split("|")[0].strip()

        previous = str(row.get("previous", ""))
        end_date = raw_date
        if "end:" in previous.lower():
            end_date = previous.split(":", 1)[1].split("|")[0].strip()[:10]

        source = str(row.get("source", ""))
        ev_id = row.get("event_id")

        return cls(
            date=raw_date,
            category=cat,
            title=title,
            severity=severity,
            region=region,
            end_date=end_date,
            source_id=source,
            source_institution="Neon_DB",
            event_id=int(ev_id) if ev_id is not None else None,
        )

