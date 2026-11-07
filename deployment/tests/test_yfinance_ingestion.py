"""
deployment/tests/test_yfinance_ingestion.py
===========================================
Unit & Integration Test Suite for Yahoo Finance Ingestion, Reconciliation,
Historical Boundary Checks, and Pipeline Continuity.
"""

import json
import os
import sys
from datetime import datetime, date
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

DEPLOYMENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEPLOYMENT_ROOT))

from database.connection import get_db_client, NeonClient
from ingestion.yfinance_client import YahooFinanceClient, INDEX_TICKER_MAP, TICKER_TO_SYMBOL_MAP
from ingestion.catchup_fetcher import CatchupIngestionService, RECOVERY_QUEUE_PATH
from ingestion.reconciler import CandleReconciler
from engine.feature_adapter import MarketFeatureAdapter
from engine.inference_engine import RegimeInferenceEngine


def test_index_ticker_mappings():
    """Verify all 8 canonical indices are present and mapped to valid Yahoo tickers."""
    expected_symbols = [
        "NIFTY 50",
        "NIFTY BANK",
        "NIFTY AUTO",
        "NIFTY FMCG",
        "NIFTY IT",
        "NIFTY METAL",
        "NIFTY PHARMA",
        "INDIA VIX",
    ]
    assert len(INDEX_TICKER_MAP) == 8
    for sym in expected_symbols:
        assert sym in INDEX_TICKER_MAP
        assert INDEX_TICKER_MAP[sym].startswith("^")
    assert len(TICKER_TO_SYMBOL_MAP) == 8


def test_yfinance_client_live_download_nifty50():
    """Verify live Yahoo download for NIFTY 50 returns valid OHLC candles."""
    client = YahooFinanceClient()
    candles = client.fetch_historical_candles("NIFTY 50", "2026-11-02", "2026-11-06")
    assert len(candles) == 5  # Mon-Fri
    for c in candles:
        assert c["symbol"] == "NIFTY 50"
        assert c["open"] > 0
        assert c["high"] >= c["low"]
        assert c["close"] > 0
        assert c["source"] == "yahoo_finance"


def test_yfinance_client_live_download_vix():
    """Verify live Yahoo download for INDIA VIX."""
    client = YahooFinanceClient()
    candles = client.fetch_historical_candles("INDIA VIX", "2026-11-02", "2026-11-06")
    assert len(candles) == 5
    for c in candles:
        assert c["symbol"] == "INDIA VIX"
        assert 5.0 < c["close"] < 100.0  # reasonable VIX range
        assert c["source"] == "yahoo_finance"


def test_catchup_date_boundaries():
    """Verify that catch-up start date is strictly after 2026-09-18."""
    client = YahooFinanceClient()
    candles = client.fetch_historical_candles("NIFTY 50", "2026-09-19", "2026-09-25")
    dates = [c["date"] for c in candles]
    assert all(d > "2026-09-18" for d in dates)
    assert "2026-09-21" in dates  # First trading session after weekend


def test_reconciler_idempotency_and_duplicates():
    """Verify CandleReconciler duplicate detection on synthetic test candle."""
    db = get_db_client()
    reconciler = CandleReconciler(db)
    test_sym = "UNIT_TEST_SYM"
    test_d = "2099-12-31"

    # Clean
    db.execute("DELETE FROM index_candles_daily WHERE symbol = $1 AND date = $2;", params=[test_sym, test_d])

    try:
        # First insert
        r1 = reconciler.ingest_candle(test_sym, test_d, 100.0, 105.0, 95.0, 102.0, volume_val=500, source="yahoo_finance")
        assert r1["status"] == "INSERTED"

        # Duplicate insert
        r2 = reconciler.ingest_candle(test_sym, test_d, 100.0, 105.0, 95.0, 102.0, volume_val=500, source="yahoo_finance")
        assert r2["status"] == "DUPLICATE_IDENTICAL"

    finally:
        db.execute("DELETE FROM index_candles_daily WHERE symbol = $1 AND date = $2;", params=[test_sym, test_d])


def test_neon_historical_baseline_preservation():
    """Verify that historical records through 2026-09-18 remain strictly untouched."""
    db = get_db_client()
    res = db.query("""
        SELECT COUNT(*) as c, MIN(date)::text as min_d, MAX(date)::text as max_d
        FROM index_candles_daily
        WHERE data_source = 'historical_baseline_phase2';
    """)
    assert int(res[0]["c"]) == 15088
    assert res[0]["min_d"] == "2019-01-02"
    assert res[0]["max_d"] == "2026-09-18"


def test_neon_catchup_records_integrity():
    """Verify that the 264 catch-up candles in Neon are fully populated and valid."""
    db = get_db_client()
    res = db.query("""
        SELECT COUNT(*) as c, MIN(date)::text as min_d, MAX(date)::text as max_d, COUNT(DISTINCT symbol) as sym_cnt
        FROM index_candles_daily
        WHERE data_source = 'yahoo_finance';
    """)
    assert int(res[0]["c"]) == 264
    assert res[0]["min_d"] == "2026-09-21"
    assert res[0]["max_d"] == "2026-11-06"
    assert int(res[0]["sym_cnt"]) == 8


def test_recovery_queue_mechanism():
    """Test recovery queue serialization, deserialization, and recovery logic."""
    db = get_db_client()
    service = CatchupIngestionService(db_client=db)
    
    mock_queue = [{"date": "2099-01-01", "symbol": "NIFTY 50", "attempts": 1}]
    service.save_recovery_queue(mock_queue)
    loaded = service.load_recovery_queue()
    assert loaded == mock_queue

    # Clean up test queue
    if RECOVERY_QUEUE_PATH.exists():
        RECOVERY_QUEUE_PATH.unlink()


def test_feature_adapter_and_inference_continuity():
    """Verify that feature calculation and HMM inference run on catch-up date 2026-11-06."""
    db = get_db_client()
    adapter = MarketFeatureAdapter(db_client=db)
    engine = RegimeInferenceEngine()

    feats = adapter.compute_features_for_date("2026-11-06")
    assert len(feats) == 42
    assert all(not np.isnan(v) for v in feats.values())

    inf_res = engine.forward_step(features=feats, prev_probs=[0.0, 0.0, 1.0, 0.0, 0.0, 0.0], incumbent_regime=2)
    assert len(inf_res["probs_array"]) == 6
    assert abs(sum(inf_res["probs_array"]) - 1.0) < 1e-5
    assert inf_res["accepted_regime"] in range(6)

