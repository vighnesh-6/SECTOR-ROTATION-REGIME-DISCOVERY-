"""
deployment/events/backfill.py
=============================
Historical Backfill Runner for Macroeconomic Events (2019-01-01 to Present).
Gathers verified events across RBI, MOSPI, MoF, Federal Reserve, ECB, BOJ, and SEBI,
deduplicates against existing Neon records, and safely persists new verified events.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

DEPLOYMENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEPLOYMENT_ROOT.parent))

from deployment.events.models import MacroEvent
from deployment.events.sources import (
    FedUsSource,
    MospiMofSource,
    RBISource,
    SebiNseSource,
)
from deployment.events.storage import EventStorage

logger = logging.getLogger("event_backfill")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [backfill]: %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)


def run_historical_backfill(
    start_date: str = "2019-01-01",
    end_date: Optional[str] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Executes historical event backfill across all registered official sources.
    Defaults to dry_run=True for validation safety.
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    logger.info("=" * 65)
    logger.info(f"STARTING MACROECONOMIC EVENT BACKFILL: {start_date} to {end_date}")
    logger.info(f"MODE: {'DRY RUN (Validation only)' if dry_run else 'PRODUCTION WRITE'}")
    logger.info("=" * 65)

    storage = EventStorage()
    db_status_before = storage.get_db_status()
    logger.info(f"Current Neon DB State: {db_status_before}")

    sources = [
        RBISource(),
        MospiMofSource(),
        FedUsSource(),
        SebiNseSource(),
    ]

    all_candidates: List[MacroEvent] = []
    source_stats: Dict[str, int] = {}

    for src in sources:
        try:
            logger.info(f"Querying {src.name} [{src.institution}]...")
            events = src.fetch_events(start_date=start_date, end_date=end_date)
            all_candidates.extend(events)
            source_stats[src.name] = len(events)
            logger.info(f"  -> {src.name}: Retrieved {len(events)} events.")
        except Exception as e:
            logger.error(f"  -> {src.name} FAILED: {e}")
            source_stats[src.name] = 0

    logger.info(f"Total raw candidates collected across sources: {len(all_candidates)}")

    # Sort candidates chronologically
    all_candidates.sort(key=lambda x: (x.date, x.title))

    # Persist via EventStorage (with deduplication)
    persist_res = storage.persist_events(candidates=all_candidates, dry_run=dry_run)

    summary = {
        "start_date": start_date,
        "end_date": end_date,
        "dry_run": dry_run,
        "db_status_before": db_status_before,
        "source_candidates": source_stats,
        "total_candidates": len(all_candidates),
        "unique_to_insert": persist_res.get("unique_to_insert") if dry_run else persist_res.get("inserted_count"),
        "duplicates_rejected": persist_res.get("duplicates_rejected", 0),
        "db_status_after": db_status_before if dry_run else persist_res.get("db_status_after"),
        "sample_rows": persist_res.get("sample_rows", []),
    }

    logger.info("=" * 65)
    logger.info(f"BACKFILL SUMMARY: Unique={summary['unique_to_insert']}, Duplicates={summary['duplicates_rejected']}")
    logger.info("=" * 65)

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Macroeconomic Event Backfill Runner")
    parser.add_argument("--start", type=str, default="2019-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--live", action="store_true", help="Execute live database writes (default: dry run)")
    args = parser.parse_args()

    res = run_historical_backfill(
        start_date=args.start,
        end_date=args.end,
        dry_run=not args.live,
    )
    print(json.dumps(res, indent=2, default=str))

