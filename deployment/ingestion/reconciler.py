"""
deployment/ingestion/reconciler.py
==================================
Production Duplicate Detection and Conflicting-Record Reconciler.

Replaces blind ON CONFLICT DO NOTHING with systematic audit logging:
  - If a candle is identical within numerical tolerance (1e-4), it is safely deduplicated.
  - If an upstream settlement revision is detected, it is logged to `reconciliation_audit_logs`
    and reconciled in `index_candles_daily`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal


class CandleReconciler:
    def __init__(self, client: Any, tolerance: float = 1e-4) -> None:
        self.client = client
        self.tolerance = tolerance

    def ingest_candle(
        self,
        symbol: str,
        date_str: str,
        open_val: float,
        high_val: float,
        low_val: float,
        close_val: float,
        adj_close_val: Optional[float] = None,
        volume_val: int = 0,
        source: str = "yahoo_finance",
    ) -> Dict[str, Any]:
        """
        Ingest a single candle with duplicate detection and settlement revision reconciliation.
        """
        if adj_close_val is None:
            adj_close_val = close_val

        # 1. Check existing record
        query = """
            SELECT open, high, low, close, volume, data_source
            FROM index_candles_daily
            WHERE symbol = $1 AND date = $2;
        """
        rows = self.client.query(query, params=[symbol, date_str])

        if not rows:
            # New candle -> insert
            insert_sql = """
                INSERT INTO index_candles_daily (symbol, date, open, high, low, close, adj_close, volume, data_source)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
            """
            self.client.execute(
                insert_sql,
                params=[
                    symbol,
                    date_str,
                    open_val,
                    high_val,
                    low_val,
                    close_val,
                    adj_close_val,
                    volume_val,
                    source,
                ],
            )
            return {"status": "INSERTED", "symbol": symbol, "date": date_str}

        # Existing record found -> inspect differences
        existing = rows[0]
        fields = [
            ("open", float(existing["open"]), float(open_val)),
            ("high", float(existing["high"]), float(high_val)),
            ("low", float(existing["low"]), float(low_val)),
            ("close", float(existing["close"]), float(close_val)),
            ("volume", float(existing["volume"]) if existing.get("volume") is not None else 0.0, float(volume_val)),
        ]

        has_revision = False
        revisions = []

        for field_name, old_v, new_v in fields:
            abs_delta = abs(new_v - old_v)
            if abs_delta > self.tolerance:
                has_revision = True
                pct_delta = (abs_delta / old_v) if old_v != 0 else 0.0
                revisions.append((field_name, old_v, new_v, abs_delta, pct_delta))

        if not has_revision:
            return {"status": "DUPLICATE_IDENTICAL", "symbol": symbol, "date": date_str}

        # Log revisions to reconciliation_audit_logs
        for field_name, old_v, new_v, abs_delta, pct_delta in revisions:
            audit_sql = """
                INSERT INTO reconciliation_audit_logs (symbol, date, field_name, old_value, new_value, abs_delta, pct_delta, resolution)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'reconciled_update');
            """
            self.client.execute(
                audit_sql,
                params=[
                    symbol,
                    date_str,
                    field_name,
                    round(old_v, 4),
                    round(new_v, 4),
                    round(abs_delta, 4),
                    round(pct_delta, 4),
                ],
            )

        # Update index_candles_daily with corrected settlement prices
        update_sql = """
            UPDATE index_candles_daily
            SET open = $3, high = $4, low = $5, close = $6, adj_close = $7, volume = $8, data_source = $9, revision_count = revision_count + 1
            WHERE symbol = $1 AND date = $2;
        """
        self.client.execute(
            update_sql,
            params=[
                symbol,
                date_str,
                open_val,
                high_val,
                low_val,
                close_val,
                adj_close_val,
                volume_val,
                f"{source}_reconciled",
            ],
        )

        return {
            "status": "RECONCILED_REVISION",
            "symbol": symbol,
            "date": date_str,
            "revisions": len(revisions),
        }

    def ingest_batch(self, candles: List[Dict[str, Any]]) -> Dict[str, int]:
        summary = {"inserted": 0, "duplicate": 0, "reconciled": 0}
        for c in candles:
            res = self.ingest_candle(
                symbol=c["symbol"],
                date_str=c["date"],
                open_val=c["open"],
                high_val=c["high"],
                low_val=c["low"],
                close_val=c["close"],
                adj_close_val=c.get("adj_close", c["close"]),
                volume_val=c.get("volume", 0),
                source=c.get("source", "yahoo_finance"),
            )
            if res["status"] == "INSERTED":
                summary["inserted"] += 1
            elif res["status"] == "DUPLICATE_IDENTICAL":
                summary["duplicate"] += 1
            elif res["status"] == "RECONCILED_REVISION":
                summary["reconciled"] += 1
        return summary
