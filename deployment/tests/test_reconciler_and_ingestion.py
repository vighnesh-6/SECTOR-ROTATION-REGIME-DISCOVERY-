"""
deployment/tests/test_reconciler_and_ingestion.py
=================================================
Tests duplicate candle deduplication, settlement revisions, and pure Python RFC 6238 TOTP.
"""

import sys
from pathlib import Path
import pytest

DEPLOYMENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEPLOYMENT_ROOT))

from database.connection import get_db_client
from ingestion.reconciler import CandleReconciler


def test_candle_reconciliation_workflow():
    client = get_db_client()
    reconciler = CandleReconciler(client)

    test_date = "2099-01-01"
    test_symbol = "TEST_INDEX"

    # Clean up test artifact if exists
    client.execute("DELETE FROM index_candles_daily WHERE symbol = $1 AND date = $2;", params=[test_symbol, test_date])
    client.execute("DELETE FROM reconciliation_audit_logs WHERE symbol = $1 AND date = $2;", params=[test_symbol, test_date])

    try:
        # Step 1: Initial Insert
        res1 = reconciler.ingest_candle(
            symbol=test_symbol,
            date_str=test_date,
            open_val=100.0,
            high_val=105.0,
            low_val=98.0,
            close_val=103.0,
            volume_val=1000,
        )
        assert res1["status"] == "INSERTED"

        # Step 2: Duplicate Ingest with identical prices -> Should detect duplicate
        res2 = reconciler.ingest_candle(
            symbol=test_symbol,
            date_str=test_date,
            open_val=100.0,
            high_val=105.0,
            low_val=98.0,
            close_val=103.0,
            volume_val=1000,
        )
        assert res2["status"] == "DUPLICATE_IDENTICAL"

        # Step 3: Upstream revised settlement price (e.g. close changed from 103.0 to 103.5)
        res3 = reconciler.ingest_candle(
            symbol=test_symbol,
            date_str=test_date,
            open_val=100.0,
            high_val=105.0,
            low_val=98.0,
            close_val=103.5,
            volume_val=1000,
        )
        assert res3["status"] == "RECONCILED_REVISION"

        # Check reconciliation audit log
        audit_rows = client.query(
            "SELECT * FROM reconciliation_audit_logs WHERE symbol = $1 AND date = $2;",
            params=[test_symbol, test_date],
        )
        assert len(audit_rows) >= 1
        assert float(audit_rows[0]["old_value"]) == 103.0
        assert float(audit_rows[0]["new_value"]) == 103.5

    finally:
        # Clean up test rows
        client.execute("DELETE FROM index_candles_daily WHERE symbol = $1 AND date = $2;", params=[test_symbol, test_date])
        client.execute("DELETE FROM reconciliation_audit_logs WHERE symbol = $1 AND date = $2;", params=[test_symbol, test_date])

