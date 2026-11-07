"""
deployment/tests/test_database_connection.py
============================================
Tests Neon PostgreSQL database connection, schema tables, and migration counts.
"""

import sys
from pathlib import Path
import pytest

DEPLOYMENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEPLOYMENT_ROOT))

from database.connection import get_db_client


def test_neon_connection():
    client = get_db_client()
    rows = client.query("SELECT 1 as connected, NOW() as current_time;")
    assert len(rows) == 1
    assert rows[0]["connected"] == 1


def test_schema_tables_exist():
    client = get_db_client()
    expected_tables = [
        "index_candles_daily",
        "market_features_daily",
        "regime_inference_daily",
        "portfolio_allocations_daily",
        "portfolio_simulations_daily",
        "benchmark_simulations_daily",
        "macro_events",
        "pipeline_execution_logs",
        "reconciliation_audit_logs",
        "schema_migrations",
    ]
    query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
    """
    rows = client.query(query)
    existing_tables = {r["table_name"] for r in rows}
    for t in expected_tables:
        assert t in existing_tables, f"Missing table: {t}"


def test_historical_migration_row_counts():
    client = get_db_client()
    expected_baseline_counts = {
        "index_candles_daily": 15088,
        "regime_inference_daily": 1687,
        "portfolio_allocations_daily": 6748,
        "portfolio_simulations_daily": 6744,
        "benchmark_simulations_daily": 3372,
        "macro_events": 135,
    }
    for table_name, expected_count in expected_baseline_counts.items():
        if table_name == "macro_events":
            res = client.query(f"SELECT COUNT(*) as count FROM {table_name};")
        else:
            res = client.query(f"SELECT COUNT(*) as count FROM {table_name} WHERE date <= '2026-09-18';")
        actual_count = int(res[0]["count"])
        assert actual_count == expected_count, (
            f"Historical baseline in table {table_name} mismatch: expected {expected_count}, got {actual_count}"
        )

