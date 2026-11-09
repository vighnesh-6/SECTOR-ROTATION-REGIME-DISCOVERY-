"""Offline EOD safety contracts. No network, files, database writes, or training."""
import io
import json
import os
import socket
from datetime import date, datetime
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from deployment.scripts import run_daily_eod as eod
from deployment.database.connection import NeonClient
from deployment.ingestion.trading_calendar import TradingCalendar, CalendarCoverageError, IST
from deployment.ingestion.reconciler import CandleReconciler
from deployment.ingestion.catchup_fetcher import CatchupIngestionService


HOST = eod.EXPECTED_ENDPOINT + ".ap-southeast-1.aws.neon.tech"
IDENTITY = {"database": "neondb", "branch_id": eod.EXPECTED_BRANCH, "endpoint_id": eod.EXPECTED_ENDPOINT}


@pytest.fixture(autouse=True)
def forbid_real_io(monkeypatch, request):
    """A test mistake must fail before opening any network/database connection."""
    def blocked(*args, **kwargs):
        raise AssertionError("Offline EOD suite forbids network and default database access")
    if (os.environ.get("EOD_OPS_INTEGRATION") == "1" and
            request.node.name == "test_disposable_neon_atomicity_idempotency_and_recovery"):
        # The opt-in integration test below validates its explicit disposable
        # target before SQL. Default-client access remains forbidden.
        monkeypatch.setattr(eod, "get_db_client", blocked)
        return
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(eod, "get_db_client", blocked)


def client():
    db = MagicMock()
    db.connection_string = "postgresql://user:offline@" + HOST + "/neondb?sslmode=require"
    db.execute.return_value = 1
    return db


def summary(day="2026-09-18"):
    return {"date": day, "symbols": list(eod.REQUIRED_INDEX_SYMBOLS), "features": 1,
            "regimes": 1, "simulations": list(eod.VARIANTS), "allocations": list(eod.VARIANTS),
            "benchmarks": list(eod.BENCHMARKS)}


def records(day="2026-09-21"):
    return {"market_features_daily": [{"date": day}], "regime_inference_daily": [{"date": day}],
            "portfolio_simulations_daily": [{"variant": v, "date": day} for v in eod.VARIANTS],
            "portfolio_allocations_daily": [{"variant": v, "date": day} for v in eod.VARIANTS],
            "benchmark_simulations_daily": [{"benchmark_name": v, "date": day} for v in sorted(eod.BENCHMARKS)]}


@pytest.mark.parametrize("url", [
    "postgresql://u:p@ep-calm-rain-a1emw9d9.ap-southeast-1.aws.neon.tech/neondb",
    "postgresql://u:p@other.neon.tech/neondb",
    "postgresql://u:p@" + HOST + "/main",
    "postgresql://u:p@" + HOST + "/neondb?options=endpoint%3Dep-calm-rain-a1emw9d9",
    "postgresql://u:p@" + HOST + ".evil.example/neondb",
    "not-a-connection",
])
def test_isolation_rejected_before_sql(url):
    db = client(); db.connection_string = url
    with pytest.raises(eod.EODSafetyError):
        eod.verify_eod_target(db)
    db.query.assert_not_called()
    db.execute.assert_not_called()


def test_server_identity_and_disposable_database_are_explicit():
    db = client(); db.query.return_value = [IDENTITY]
    assert eod.verify_eod_target(db) == IDENTITY
    db.query.return_value = [{**IDENTITY, "branch_id": "wrong"}]
    with pytest.raises(eod.EODSafetyError): eod.verify_eod_target(db)
    db.connection_string = "postgresql://u:p@" + HOST + "/eod_ops_test"
    db.query.reset_mock()
    with pytest.raises(eod.EODSafetyError): eod.verify_eod_target(db)
    db.query.assert_not_called()
    db.query.return_value = [{**IDENTITY, "database": "eod_ops_test"}]
    assert eod.verify_eod_target(db, "eod_ops_test")["database"] == "eod_ops_test"


@pytest.mark.parametrize("status,exit_code", [("SUCCESS",0),("UP_TO_DATE",0),("PARTIAL",1),("FAILED",1),("UNKNOWN",1)])
def test_cli_exit_status(status, exit_code, capsys):
    with patch.object(eod, "run_pipeline", return_value={"status": status}):
        assert eod.main([]) == exit_code
    assert status in capsys.readouterr().out


def test_actual_inserted_log_id_and_finalization():
    db = client(); db.query.return_value = [{"log_id": 712}]
    assert eod.start_eod_run(db, "2026-09-21", "test", IDENTITY) == 712
    assert "RETURNING log_id" in db.query.call_args.args[0]
    db.execute.assert_not_called()
    eod.finish_eod_run(db, 712, {"status": "UP_TO_DATE"}, eod.time.monotonic())
    assert db.execute.call_args.args[1][0:3] == [712, "SUCCESS", "UP_TO_DATE"]
    assert "status='RUNNING'" in db.execute.call_args.args[0]
    db.execute.return_value = 0
    with pytest.raises(eod.EODSafetyError):
        eod.finish_eod_run(db, 712, {"status":"FAILED"}, eod.time.monotonic())


@pytest.mark.parametrize("field", ["features", "regimes", "simulations", "allocations", "benchmarks", "symbols"])
def test_partial_existing_session_never_advances(field):
    db = client(); row = summary("2026-09-21")
    row[field] = 0 if field in ("features", "regimes") else []
    with patch.object(eod, "session_summary", return_value=[summary(), row]):
        with pytest.raises(eod.EODSafetyError, match="incomplete existing"):
            eod.last_complete_session(db, TradingCalendar())
    db.execute.assert_not_called(); db.execute_transaction.assert_not_called()


def test_missing_whole_session_is_not_skipped():
    with patch.object(eod, "session_summary", return_value=[summary(), summary("2026-09-22")]):
        with pytest.raises(eod.EODSafetyError, match="session gap"):
            eod.last_complete_session(client(), TradingCalendar())


def test_up_to_date_checks_completeness_and_writes_only_its_new_log():
    db = client(); db.query.side_effect = [[IDENTITY], [summary()], [{"log_id": 900}]]
    result = eod.run_pipeline(db=db, clock=lambda: datetime(2026,9,18,20,tzinfo=IST))
    assert result["status"] == "UP_TO_DATE"
    assert db.execute.call_count == 1
    assert db.execute.call_args.args[1][0] == 900
    db.execute_transaction.assert_not_called()


def test_partial_fetch_fails_without_derived_publication():
    db = client(); db.query.side_effect = [[IDENTITY], [summary()], [{"log_id": 901}]]
    with patch.object(eod, "CatchupIngestionService") as service, patch.object(eod, "_calculate_records") as calc:
        service.return_value.run_catchup.return_value = {"status":"PARTIAL_SUCCESS", "missing":["INDIA VIX"]}
        result = eod.run_pipeline(db=db, clock=lambda: datetime(2026,9,21,20,tzinfo=IST))
    assert result["status"] == "PARTIAL"
    calc.assert_not_called(); db.execute_transaction.assert_not_called()
    assert db.execute.call_args.args[1][1] == "FAILED"


@pytest.mark.parametrize("failure", [None, RuntimeError("injected rollback")])
def test_complete_session_atomic_publication_or_failed_run(failure):
    db = client()
    db.query.side_effect = [[IDENTITY], [{"log_id":902}], [{"date":"2026-09-21","symbols":list(eod.REQUIRED_INDEX_SYMBOLS)}]]
    db.execute_transaction.side_effect = failure
    with patch.object(eod, "last_complete_session", side_effect=[date(2026,9,18), date(2026,9,21)]), patch.object(eod,"CatchupIngestionService") as service, patch.object(eod,"_calculate_records",return_value=records()):
        service.return_value.run_catchup.return_value = {"status":"FETCH_COMPLETE", "missing":[]}
        result = eod.run_pipeline(db=db, clock=lambda: datetime(2026,9,21,20,tzinfo=IST))
    assert result["status"] == ("FAILED" if failure else "SUCCESS")
    assert db.execute_transaction.call_count == 1
    queries = db.execute_transaction.call_args.args[0]
    assert "pg_advisory_xact_lock" in queries[0]["query"]
    inserts = [q for q in queries if q["query"].startswith("INSERT")]
    assert len(inserts) == 12
    assert all("UPDATE" not in q["query"] and "CONFLICT" not in q["query"] for q in inserts)
    assert "continuity_guard" in queries[1]["query"]
    assert "publication_guard" in queries[-1]["query"]


def test_calendar_special_session_holiday_and_year_boundary():
    c = TradingCalendar()
    assert c.next_session(date(2026,11,6)) == date(2026,11,8)
    assert c.next_session(date(2026,11,9)) == date(2026,11,11)
    assert not c.is_session(date(2026,11,10))
    assert c.latest_completed_session(datetime(2026,11,9,6,tzinfo=IST)) == date(2026,11,8)
    with pytest.raises(CalendarCoverageError): c.next_session(date(2026,12,31))


def test_source_empty_feed_is_not_success_and_no_queue_file_is_created():
    db = client(); yf = MagicMock(); yf.fetch_historical_candles.return_value = []
    with patch("pathlib.Path.mkdir") as mkdir:
        service = CatchupIngestionService(db_client=db,yf_client=yf,max_retries_per_index=1,persist_recovery_queue=False,append_only=True)
        result = service.run_catchup(expected_dates=["2026-09-21"])
    mkdir.assert_not_called()
    assert result["status"] == "PARTIAL_SUCCESS" and len(result["missing"]) == 8
    db.execute.assert_not_called()


def test_append_only_reconciler_preserves_existing_conflicts():
    db = client(); db.query.return_value = [{"open":100,"high":105,"low":98,"close":103,"adj_close":103,"volume":1}]
    rec = CandleReconciler(db, allow_revision_updates=False)
    assert rec.ingest_candle("NIFTY 50","2026-09-21",100,105,98,103,volume_val=1)["status"] == "DUPLICATE_IDENTICAL"
    with pytest.raises(ValueError,match="preserved"):
        rec.ingest_candle("NIFTY 50","2026-09-21",100,105,98,104,volume_val=1)
    db.execute.assert_not_called()


def test_http_batch_is_serializable_and_retries_only_rolled_back_errors():
    db = NeonClient.__new__(NeonClient); db.endpoint="https://example.neon.tech/sql"; db.connection_string="offline-secret"
    response = MagicMock(); response.__enter__.return_value.read.return_value = b'{"results":[{"rows":[]}]}'
    serialization = urllib.error.HTTPError(db.endpoint,400,"bad",{},io.BytesIO(b'{"code":"40001"}'))
    with patch("urllib.request.urlopen",side_effect=[serialization,response]) as send, patch("time.sleep"):
        assert db.execute_transaction([{"query":"SELECT 1","params":[]}]) == [{"rows":[]}]
    assert send.call_count == 2
    request = send.call_args.args[0]
    assert request.get_header("Neon-batch-isolation-level") == "Serializable"
    assert json.loads(request.data)["queries"][0]["query"] == "SELECT 1"
    with patch("urllib.request.urlopen",side_effect=urllib.error.URLError("ambiguous")) as send:
        with pytest.raises(RuntimeError,match="outcome unconfirmed"):
            db.execute_transaction([{"query":"SELECT 1"}])
    assert send.call_count == 1


def test_diagnostics_redact_connection_and_password():
    text = eod._safe_error(RuntimeError("bad postgresql://u:npg_SENSITIVE@host/db password=npg_OTHER"))
    assert "SENSITIVE" not in text and "npg_" not in text and "postgresql://" not in text


@pytest.mark.skipif(os.environ.get("EOD_OPS_INTEGRATION") != "1", reason="Explicit disposable-database opt-in required")
def test_disposable_neon_atomicity_idempotency_and_recovery():
    """Writes only eod_ops_test; preserve every pre-existing row, even on failure."""
    from concurrent.futures import ThreadPoolExecutor
    connection = os.environ.get("EOD_TEST_DATABASE_URL", "")
    if not connection:
        pytest.fail("Explicit EOD_TEST_DATABASE_URL is required")
    # Inspect routing before constructing the client or sending any SQL.
    route = MagicMock(connection_string=connection)
    route.query.return_value = [{**IDENTITY, "database": "eod_ops_test"}]
    eod.verify_eod_target(route, "eod_ops_test")
    db = NeonClient(connection_string=connection)
    eod.verify_eod_target(db, "eod_ops_test")
    tables = list(eod.TABLE_KEYS) + ["index_candles_daily", "macro_events", "pipeline_execution_logs", "reconciliation_audit_logs"]
    def fingerprint(table, predicate="TRUE"):
        return db.query("SELECT count(*)::int AS n,md5(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'[]')) AS hash FROM " + table + " t WHERE " + predicate)[0]
    before = {t: fingerprint(t) for t in tables}
    # Do not clear or reuse an existing fixture database.
    assert all(r["n"] == 0 for r in before.values()), "Disposable database is not empty; existing records preserved"
    def bundle(day):
        return {
          "market_features_daily": [{"date": day, "features_raw": "{}", "features_robust_scaled": "{}"}],
          "regime_inference_daily": [{"date": day, **{"prob_"+str(i): 1.0 if i == 0 else 0.0 for i in range(6)}, "raw_argmax": 0, "max_probability": 1.0, "is_confident": True, "accepted_regime": 0}],
          "portfolio_simulations_daily": [{"date": day, "variant": v, "gross_return": 0.0, "net_return": 0.0, "gross_nav": 1.0, "net_nav": 1.0, "accepted_regime": 0} for v in eod.VARIANTS],
          "portfolio_allocations_daily": [{"date": day, "variant": v, "exec_date": TradingCalendar().next_session(date.fromisoformat(day)).isoformat(), "holding_days_before": 0, "holding_days_after": 1, "rebalance_triggered": False} for v in eod.VARIANTS],
          "benchmark_simulations_daily": [{"date": day, "benchmark_name": v, "net_return": 0.0, "net_nav": 1.0} for v in sorted(eod.BENCHMARKS)],
        }
    baseline = bundle("2026-09-18")
    seed = []
    for table, rows in baseline.items():
        for row in rows:
            seed.append({"query": "INSERT INTO " + table + " (" + ",".join(row) + ") VALUES (" + ",".join("$"+str(i+1) for i in range(len(row))) + ")", "params": list(row.values())})
    for symbol in eod.REQUIRED_INDEX_SYMBOLS:
        seed.append({"query": "INSERT INTO index_candles_daily(symbol,date,open,high,low,close,adj_close) VALUES($1,'2026-09-18',100,100,100,100,100)", "params": [symbol]})
    db.execute_transaction(seed)
    baseline_hash = {t: fingerprint(t) for t in tables}
    original_batch = db.execute_transaction
    def interrupted(queries):
        # Fault after real inserts: the entire batch must roll back.
        return original_batch(queries[:-1] + [{"query": "SELECT 1/0", "params": []}] + queries[-1:])
    with patch.object(db, "execute_transaction", side_effect=interrupted):
        with pytest.raises(RuntimeError):
            eod.publish_session(db, bundle("2026-09-21"), "2026-09-21", "2026-09-18")
    assert {t: fingerprint(t) for t in tables} == baseline_hash
    eod.publish_session(db, bundle("2026-09-21"), "2026-09-21", "2026-09-18")
    published = {t: fingerprint(t) for t in tables}
    with pytest.raises(RuntimeError):
        eod.publish_session(db, bundle("2026-09-21"), "2026-09-21", "2026-09-18")
    assert {t: fingerprint(t) for t in tables} == published
    def concurrent_writer(_):
        try:
            eod.publish_session(db, bundle("2026-09-22"), "2026-09-22", "2026-09-21")
            return "committed"
        except RuntimeError:
            return "rejected"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(concurrent_writer, range(2))) == ["committed", "rejected"]
    for table, count in (("market_features_daily",1),("regime_inference_daily",1),("portfolio_simulations_daily",4),("portfolio_allocations_daily",4),("benchmark_simulations_daily",2)):
        assert fingerprint(table, "date='2026-09-22'")["n"] == count
    for table in tables:
        if table in eod.TABLE_KEYS or table == "index_candles_daily":
            assert fingerprint(table, "date='2026-09-18'") == baseline_hash[table]
        else:
            assert fingerprint(table) == before[table]
    # No deletes: synthetic committed fixtures remain only in the disposable DB.
