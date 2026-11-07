"""
deployment/tests/test_event_ingestion.py
========================================
Offline fixture-based unit and integration tests for the macroeconomic event pipeline.
Zero live external network dependencies during execution.
"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from deployment.events.deduplication import EventDeduplicator
from deployment.events.models import MacroEvent
from deployment.events.normalization import (
    infer_region,
    infer_severity,
    normalize_category,
    normalize_datetime_to_date,
    normalize_event,
)
from deployment.events.sources.fed_us import FedUsSource
from deployment.events.sources.mospi_mof import MospiMofSource
from deployment.events.sources.rbi import RBISource
from deployment.events.storage import EventStorage


SAMPLE_FED_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Federal Reserve Press Releases</title>
    <link>https://www.federalreserve.gov</link>
    <item>
      <title>Federal Reserve issues FOMC statement</title>
      <pubDate>Wed, 16 Sep 2026 18:00:00 GMT</pubDate>
      <link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm</link>
    </item>
    <item>
      <title>Minutes of the Federal Open Market Committee, July 28-29, 2026</title>
      <pubDate>Wed, 19 Aug 2026 18:00:00 GMT</pubDate>
      <link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20260819a.htm</link>
    </item>
  </channel>
</rss>
"""

SAMPLE_RBI_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Reserve Bank of India Press Releases</title>
    <link>https://www.rbi.org.in</link>
    <item>
      <title>Monetary Policy Statement, 2026-27 Resolution of the Monetary Policy Committee (MPC)</title>
      <pubDate>Fri, 09 Oct 2026 10:00:00 GMT</pubDate>
      <link>https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=62100</link>
    </item>
    <item>
      <title>Auction of Treasury Bills</title>
      <pubDate>Fri, 09 Oct 2026 14:00:00 GMT</pubDate>
      <link>https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=62101</link>
    </item>
  </channel>
</rss>
"""


class TestEventModelAndValidation(unittest.TestCase):
    def test_valid_macro_event_creation(self):
        ev = MacroEvent(
            date="2026-10-09",
            category="Monetary policy",
            title="RBI shifts policy stance to NEUTRAL",
            severity="high",
            region="India",
        )
        self.assertEqual(ev.date, "2026-10-09")
        self.assertEqual(ev.end_date, "2026-10-09")
        self.assertEqual(ev.severity, "high")
        self.assertTrue(len(ev.fingerprint()) > 0)

    def test_reject_pre_2019_date(self):
        with self.assertRaises(ValueError):
            MacroEvent(
                date="2018-12-31",
                category="Indian policy",
                title="Pre-project event",
            )

    def test_title_truncation_to_200_chars(self):
        long_title = "A" * 250
        ev = MacroEvent(
            date="2026-10-09",
            category="Monetary policy",
            title=long_title,
        )
        self.assertLessEqual(len(ev.title), 200)
        self.assertTrue(ev.title.endswith("..."))

    def test_to_db_row_format(self):
        ev = MacroEvent(
            date="2026-10-09",
            category="Monetary policy",
            title="RBI MPC Decision",
            severity="high",
            region="India",
            end_date="2026-10-09",
            source_id="ID: E136",
        )
        row = ev.to_db_row()
        self.assertIn("date", row)
        self.assertIn("category", row)
        self.assertIn("title", row)
        self.assertEqual(row["actual"], "Severity: high")
        self.assertEqual(row["forecast"], "Region: India")
        self.assertEqual(row["previous"], "End: 2026-10-09")
        self.assertEqual(row["source"], "ID: E136")


class TestEventNormalization(unittest.TestCase):
    def test_normalize_datetime_rfc2822(self):
        dt = normalize_datetime_to_date("Wed, 16 Sep 2026 18:00:00 GMT")
        self.assertEqual(dt, "2026-09-16")

    def test_normalize_datetime_iso(self):
        dt = normalize_datetime_to_date("2026-10-09T10:00:00Z")
        self.assertEqual(dt, "2026-10-09")

    def test_category_inference(self):
        cat1 = normalize_category("Federal Reserve FOMC rate decision")
        self.assertEqual(cat1, "US monetary policy")

        cat2 = normalize_category("RBI Monetary Policy Committee resolution")
        self.assertEqual(cat2, "Monetary policy")

        cat3 = normalize_category("SEBI index derivatives circular")
        self.assertEqual(cat3, "Domestic market shock")

        cat4 = normalize_category("Gross GST Revenue collection release")
        self.assertEqual(cat4, "Fiscal / corporate policy")

    def test_severity_inference(self):
        self.assertEqual(infer_severity("Emergency rate cut of 50 bps"), "high")
        self.assertEqual(infer_severity("Federal Reserve holds interest rate"), "medium")
        self.assertEqual(infer_severity("Weekly statistical extract bulletin"), "low")

    def test_region_inference(self):
        self.assertEqual(infer_region("FOMC meeting statement", "Federal Reserve"), "US")
        self.assertEqual(infer_region("RBI MPC meeting resolution", "RBI"), "India")
        self.assertEqual(infer_region("India-US interim trade agreement", "Trade"), "India / US")


class TestEventDeduplication(unittest.TestCase):
    def setUp(self):
        self.existing = [
            MacroEvent(
                date="2026-09-12",
                category="International summit",
                title="18th BRICS Summit, New Delhi",
                severity="high",
                region="Global",
            )
        ]
        self.dedup = EventDeduplicator(existing_events=self.existing)

    def test_exact_duplicate_rejected(self):
        cand = MacroEvent(
            date="2026-09-12",
            category="International summit",
            title="18th BRICS Summit, New Delhi",
        )
        is_dup, reason = self.dedup.is_duplicate(cand)
        self.assertTrue(is_dup)
        self.assertIn("fingerprint match", reason)

    def test_fuzzy_duplicate_rejected(self):
        cand = MacroEvent(
            date="2026-09-12",
            category="International summit",
            title="BRICS Summit held in New Delhi, 18th edition",
        )
        is_dup, reason = self.dedup.is_duplicate(cand)
        self.assertTrue(is_dup)

    def test_unique_event_accepted(self):
        cand = MacroEvent(
            date="2026-09-18",
            category="US monetary policy",
            title="Federal Reserve cuts federal funds rate by 50 bps",
        )
        is_dup, reason = self.dedup.is_duplicate(cand)
        self.assertFalse(is_dup)
        self.assertIsNone(reason)

    def test_idempotency_double_run(self):
        candidates = [
            MacroEvent(
                date="2026-09-18",
                category="US monetary policy",
                title="Federal Reserve cuts rate by 50 bps",
            ),
            MacroEvent(
                date="2026-10-09",
                category="Monetary policy",
                title="RBI MPC shifts stance to NEUTRAL",
            ),
        ]
        # Pass 1: both accepted
        unique_1, rej_1 = self.dedup.filter_unique(candidates)
        self.assertEqual(len(unique_1), 2)
        self.assertEqual(len(rej_1), 0)

        # Pass 2: both rejected as duplicates
        unique_2, rej_2 = self.dedup.filter_unique(candidates)
        self.assertEqual(len(unique_2), 0)
        self.assertEqual(len(rej_2), 2)


class TestSourceParsingOffline(unittest.TestCase):
    @patch.object(FedUsSource, "_http_get", return_value=SAMPLE_FED_RSS.encode("utf-8"))
    def test_fed_rss_parsing(self, mock_http):
        src = FedUsSource()
        events = src.fetch_live_fomc_rss()
        self.assertGreaterEqual(len(events), 1)
        self.assertEqual(events[0].date, "2026-09-16")
        self.assertEqual(events[0].category, "US monetary policy")

    @patch.object(RBISource, "_http_get", return_value=SAMPLE_RBI_RSS.encode("utf-8"))
    def test_rbi_rss_parsing_filters_routine(self, mock_http):
        src = RBISource()
        events = src.fetch_live_rss()
        # Should retain Monetary Policy Statement and filter out Treasury Bills auction
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].date, "2026-10-09")
        self.assertIn("Resolution of the Monetary Policy Committee", events[0].title)


class TestStorageMockIntegration(unittest.TestCase):
    def test_dry_run_does_not_execute_sql(self):
        mock_db = MagicMock()
        mock_db.query.side_effect = [
            # query 1: load existing events
            [
                {
                    "event_id": 1,
                    "date": "2019-02-01",
                    "category": "Indian policy",
                    "title": "Interim Union Budget 2019",
                    "actual": "Severity: medium",
                    "forecast": "Region: India",
                    "previous": "End: 2019-02-01",
                    "source": "ID: E001",
                }
            ]
        ]
        storage = EventStorage(db_client=mock_db)
        candidates = [
            MacroEvent(
                date="2026-10-09",
                category="Monetary policy",
                title="RBI MPC shifts stance to NEUTRAL",
            )
        ]
        res = storage.persist_events(candidates, dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["unique_to_insert"], 1)
        # Verify no INSERT queries were made
        insert_calls = [c for c in mock_db.query.call_args_list if "INSERT INTO" in str(c)]
        self.assertEqual(len(insert_calls), 0)

