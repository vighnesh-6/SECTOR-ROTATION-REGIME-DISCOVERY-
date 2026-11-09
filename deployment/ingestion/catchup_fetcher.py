"""
deployment/ingestion/catchup_fetcher.py
=======================================
Production Historical Catch-up and Daily Candle Ingestion Pipeline.

Uses Yahoo Finance (yfinance) as the primary data provider:
  - Fetches missing EOD candles for all 8 universe indices:
    NIFTY 50, NIFTY BANK, NIFTY AUTO, NIFTY FMCG, NIFTY IT,
    NIFTY METAL, NIFTY PHARMA, INDIA VIX.
  - Controlled retry mechanism with configurable delays (e.g. 7:00 PM, 7:30 PM, 8:00 PM, 8:30 PM IST).
  - Index-level error isolation and persistent recovery queue.
  - Validates and permanently inserts records into Neon PostgreSQL (`index_candles_daily`).
  - Strict duplicate detection and revision reconciliation via `CandleReconciler`.
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import get_db_client, NeonClient
from ingestion.yfinance_client import YahooFinanceClient, INDEX_TICKER_MAP
from ingestion.reconciler import CandleReconciler

logger = logging.getLogger("catchup_fetcher")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [catchup_fetcher]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

STATE_DIR = Path(__file__).resolve().parent.parent / "state"
RECOVERY_QUEUE_PATH = STATE_DIR / "recovery_queue.json"


class CatchupIngestionService:
    def __init__(
        self,
        db_client: Optional[NeonClient] = None,
        yf_client: Optional[YahooFinanceClient] = None,
        max_retries_per_index: int = 4,
        retry_delay_seconds: float = 2.0,
        append_only: bool = False,
        persist_recovery_queue: bool = True,
    ) -> None:
        self.db = db_client or get_db_client()
        self.yf_client = yf_client or YahooFinanceClient()
        self.reconciler = CandleReconciler(self.db, allow_revision_updates=not append_only)
        self.persist_recovery_queue = persist_recovery_queue
        self.max_retries = max_retries_per_index
        self.retry_delay = retry_delay_seconds
        if self.persist_recovery_queue:
            STATE_DIR.mkdir(parents=True, exist_ok=True)

    def load_recovery_queue(self) -> List[Dict[str, Any]]:
        """Load unresolved missing (date, symbol) items from persistent state."""
        if not self.persist_recovery_queue or not RECOVERY_QUEUE_PATH.exists():
            return []
        try:
            with open(RECOVERY_QUEUE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load recovery queue: {e}")
            return []

    def save_recovery_queue(self, queue: List[Dict[str, Any]]) -> None:
        """Persist unresolved missing items to state."""
        if not self.persist_recovery_queue:
            return
        try:
            with open(RECOVERY_QUEUE_PATH, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save recovery queue: {e}")

    def get_latest_completed_date(self) -> str:
        """
        Find the latest date in index_candles_daily where ALL 8 indices are present.
        """
        query = """
            SELECT date::text as dt, COUNT(DISTINCT symbol) as sym_count
            FROM index_candles_daily
            GROUP BY date
            HAVING COUNT(DISTINCT symbol) = 8
            ORDER BY date DESC
            LIMIT 1;
        """
        rows = self.db.query(query)
        if rows and rows[0].get("dt"):
            return str(rows[0]["dt"])[:10]
        return "2019-01-02"

    def check_incomplete_stored_sessions(self) -> List[Tuple[str, List[str]]]:
        """
        Find dates in index_candles_daily that have fewer than 8 indices stored.
        Returns list of (date_str, [missing_symbols]).
        """
        query = """
            SELECT date::text as dt, array_agg(symbol) as stored_symbols
            FROM index_candles_daily
            WHERE date > '2026-09-18'
            GROUP BY date
            HAVING COUNT(DISTINCT symbol) < 8
            ORDER BY date ASC;
        """
        rows = self.db.query(query)
        incomplete = []
        all_symbols = set(INDEX_TICKER_MAP.keys())
        for r in rows:
            d = str(r["dt"])[:10]
            stored = set(r.get("stored_symbols", []))
            missing = sorted(list(all_symbols - stored))
            if missing:
                incomplete.append((d, missing))
        return incomplete

    def process_recovery_queue(self) -> Dict[str, Any]:
        """
        Attempt recovery of any previously recorded incomplete sessions.
        """
        queue = self.load_recovery_queue()
        incomplete_db = self.check_incomplete_stored_sessions()
        
        # Merge DB incomplete with persistent queue
        pending_items: Dict[Tuple[str, str], int] = {}
        for item in queue:
            pending_items[(item["date"], item["symbol"])] = item.get("attempts", 0)
        for d, missing in incomplete_db:
            for s in missing:
                if (d, s) not in pending_items:
                    pending_items[(d, s)] = 0

        if not pending_items:
            return {"recovered": 0, "pending": 0}

        logger.info(f"Processing recovery queue: {len(pending_items)} pending items...")
        recovered_count = 0
        unresolved = []

        for (d_str, sym), attempts in pending_items.items():
            try:
                candles = self.yf_client.fetch_historical_candles(sym, d_str, d_str)
                matched = [c for c in candles if c["date"] == d_str]
                if matched:
                    res = self.reconciler.ingest_batch(matched)
                    if res["inserted"] > 0 or res["duplicate"] > 0 or res["reconciled"] > 0:
                        logger.info(f"Successfully recovered {sym} for {d_str}.")
                        recovered_count += 1
                        continue
                unresolved.append({"date": d_str, "symbol": sym, "attempts": attempts + 1})
            except Exception as e:
                logger.warning(f"Recovery failed for {sym} on {d_str}: {e}")
                unresolved.append({"date": d_str, "symbol": sym, "attempts": attempts + 1})

        self.save_recovery_queue(unresolved)
        return {"recovered": recovered_count, "pending": len(unresolved)}

    def run_catchup(
        self,
        target_date: Optional[str] = None,
        trigger_type: str = "daily_cron",
        expected_dates: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute historical catch-up ingestion from latest completed date + 1 to target_date.
        """
        start_time = time.time()
        if expected_dates is not None:
            return self.collect_expected_sessions(expected_dates)
        
        # 1. First recover any pending missing items
        recovery_summary = self.process_recovery_queue()

        latest_str = self.get_latest_completed_date()
        latest_dt = datetime.strptime(latest_str, "%Y-%m-%d").date()

        if target_date is None:
            today = datetime.now().date()
            target_dt = today
        else:
            target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()

        if latest_dt >= target_dt:
            logger.info(f"Data is already up to date (latest: {latest_str}, target: {target_dt}).")
            return {
                "status": "UP_TO_DATE",
                "latest_date": latest_str,
                "target_date": str(target_dt),
                "candles_processed": 0,
                "recovery": recovery_summary,
            }

        from_date_str = (latest_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        to_date_str = target_dt.strftime("%Y-%m-%d")

        logger.info(f"Executing historical catch-up: {from_date_str} -> {to_date_str}...")

        # Log pipeline start
        log_rows = self.db.query(
            """
            INSERT INTO pipeline_execution_logs (session_date, trigger_type, status, step_reached, records_processed)
            VALUES ($1, $2, 'RUNNING', 'FETCH_STARTED', 0)
            RETURNING log_id;
            """,
            params=[to_date_str, trigger_type],
        )
        if len(log_rows) != 1 or not isinstance(log_rows[0].get("log_id"), int):
            raise RuntimeError("Could not obtain the inserted ingestion log ID")
        log_id = log_rows[0]["log_id"]

        total_inserted = 0
        total_duplicates = 0
        total_reconciled = 0
        symbols_fetched = 0
        failed_symbols: List[str] = []

        try:
            for symbol in INDEX_TICKER_MAP.keys():
                fetched = False
                for attempt in range(1, self.max_retries + 1):
                    try:
                        candles = self.yf_client.fetch_historical_candles(
                            symbol_name=symbol,
                            from_date=from_date_str,
                            to_date=to_date_str,
                        )
                        summary = self.reconciler.ingest_batch(candles)
                        total_inserted += summary["inserted"]
                        total_duplicates += summary["duplicate"]
                        total_reconciled += summary["reconciled"]
                        symbols_fetched += 1
                        fetched = True
                        break
                    except Exception as e:
                        logger.warning(
                            f"Attempt {attempt}/{self.max_retries} failed for {symbol}: {e}"
                        )
                        if attempt < self.max_retries:
                            time.sleep(self.retry_delay * attempt)

                if not fetched:
                    logger.error(f"Failed to fetch {symbol} after {self.max_retries} attempts.")
                    failed_symbols.append(symbol)

            duration_ms = int((time.time() - start_time) * 1000)

            if failed_symbols:
                status = "PARTIAL_SUCCESS" if symbols_fetched > 0 else "FAILED"
                step_reached = "FETCH_PARTIAL"
                error_msg = f"Failed symbols: {failed_symbols}"
            else:
                status = "SUCCESS"
                step_reached = "COMPLETED"
                error_msg = None

            if log_id:
                self.db.execute(
                    """
                    UPDATE pipeline_execution_logs
                    SET status = $2, step_reached = $3, records_processed = $4, duration_ms = $5, error_message = $6
                    WHERE log_id = $1;
                    """,
                    params=[log_id, status, step_reached, total_inserted, duration_ms, error_msg],
                )

            return {
                "status": status,
                "from_date": from_date_str,
                "to_date": to_date_str,
                "symbols_processed": symbols_fetched,
                "inserted": total_inserted,
                "duplicates": total_duplicates,
                "reconciled": total_reconciled,
                "failed_symbols": failed_symbols,
                "duration_ms": duration_ms,
                "recovery": recovery_summary,
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            if log_id:
                self.db.execute(
                    """
                    UPDATE pipeline_execution_logs
                    SET status = 'FAILED', step_reached = 'FETCH_FAILED', error_message = $2, duration_ms = $3
                    WHERE log_id = $1;
                    """,
                    params=[log_id, str(e), duration_ms],
                )
            raise

    def collect_expected_sessions(self, expected_dates: List[str]) -> Dict[str, Any]:
        """EOD orchestrator path: recover explicit calendar sessions, not MAX(date).

        No local queue is needed: every retry reconstructs all expected dates
        after the last fully published session from the database and calendar.
        This method never declares the downstream portfolio pipeline successful.
        """
        if not expected_dates:
            return {"status": "UP_TO_DATE", "inserted": 0, "missing": []}
        days = sorted(set(expected_dates))
        if any(datetime.strptime(d, "%Y-%m-%d").strftime("%Y-%m-%d") != d for d in days):
            raise ValueError("Invalid expected session dates")
        if (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days > 90:
            raise ValueError("RECOVERY_REQUIRED: EOD recovery exceeds the 90-day bound")
        missing = []
        totals = {"inserted": 0, "duplicate": 0, "reconciled": 0}
        expected = set(days)
        for symbol in INDEX_TICKER_MAP:
            complete = False
            for attempt in range(self.max_retries):
                try:
                    candles = self.yf_client.fetch_historical_candles(symbol, days[0], days[-1])
                    found = {}
                    for candle in candles:
                        d = candle.get("date")
                        if d not in expected:
                            continue
                        if candle.get("symbol") != symbol or d in found:
                            raise ValueError("Invalid or duplicate source candle")
                        if not all(math.isfinite(float(candle[k])) and float(candle[k]) > 0
                                   for k in ("open", "high", "low", "close", "adj_close")):
                            raise ValueError("Invalid source candle prices")
                        if float(candle["high"]) < max(float(candle["open"]), float(candle["close"])) or float(candle["low"]) > min(float(candle["open"]), float(candle["close"])):
                            raise ValueError("Invalid source candle range")
                        found[d] = candle
                    # Identical existing candles are no-ops. Revisions fail closed.
                    summary = self.reconciler.ingest_batch([found[d] for d in sorted(found)])
                    for key in totals:
                        totals[key] += summary[key]
                    missing_days = sorted(expected - set(found))
                    if not missing_days:
                        complete = True
                        break
                except ValueError as error:
                    if str(error).startswith("RECOVERY_REQUIRED:"):
                        raise
                    logger.warning("Source validation failed for %s (%s)", symbol, type(error).__name__)
                except Exception as error:
                    logger.warning("EOD source attempt failed for %s (%s)", symbol, type(error).__name__)
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_delay * (attempt + 1))
            if not complete:
                missing.append(symbol)
        return {"status": "PARTIAL_SUCCESS" if missing else "FETCH_COMPLETE",
                **totals, "missing": missing, "expected_sessions": days}
