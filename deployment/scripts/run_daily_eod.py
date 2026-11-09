"""
deployment/scripts/run_daily_eod.py
===================================
Master Daily EOD Pipeline Orchestrator.

Executed daily at 7:00 PM IST (13:30 UTC) with retries at 7:30 PM, 8:00 PM, 8:30 PM IST.
Provider: Yahoo Finance (yfinance) — 100% free, automated, no credentials required.

Flow:
  1. Missing Data Recovery: Process unresolved index items from previous runs via recovery queue.
  2. Ingestion: Fetch and validate daily EOD candles for all 8 indices into Neon PostgreSQL (`index_candles_daily`).
  3. Feature Calculation: Compute canonical 42 features via MarketFeatureAdapter.
  4. Causal Model Inference: Recursive forward filtering via frozen 6-state Gaussian HMM.
  5. Portfolio State & Compounding: Daily NAV compounding, drift, turnover, 15 bps friction, and event-driven rebalance rules for 1A, 1B, 2A, 2B.
  6. Benchmark Compounding: Daily NAV tracking for NIFTY 50 and Equal-Weight 6-Sector.
  7. Audit Logging: Detailed execution log recorded in `pipeline_execution_logs`.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from typing import Any, Dict, List, Optional

DEPLOYMENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEPLOYMENT_ROOT))

from database.connection import get_db_client, NeonClient
from engine.feature_adapter import (
    MarketFeatureAdapter,
    REQUIRED_INDEX_SYMBOLS,
    SECTOR_NAMES,
)
from engine.inference_engine import RegimeInferenceEngine
from engine.portfolio_state import (
    ALL_ASSETS,
    BENCHMARK_NAME,
    CASH_NAME,
    evaluate_rebalance_trigger,
    step_daily_nav,
)
from ingestion.catchup_fetcher import CatchupIngestionService
from ingestion.yfinance_client import YahooFinanceClient
from ingestion.trading_calendar import TradingCalendar, IST

logger = logging.getLogger("daily_eod")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [daily_eod]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

VARIANTS = ["1A", "1B", "2A", "2B"]


EXPECTED_BRANCH = "br-green-lab-a1ywzpjw"
EXPECTED_ENDPOINT = "ep-lively-voice-a13sw0d6"
FROZEN_RESEARCH_END = "2026-09-18"
BENCHMARKS = {"NIFTY50_BUY_HOLD", "EQUAL_WEIGHT_6SECTOR"}


class EODSafetyError(RuntimeError):
    pass


def _safe_error(error, connection=""):
    text = str(error)
    if connection:
        text = text.replace(connection, "[REDACTED]")
    text = re.sub(r"postgres(?:ql)?://[^\s]+", "[REDACTED]", text, flags=re.I)
    text = re.sub(r"npg_[A-Za-z0-9_-]+", "[REDACTED]", text)
    text = re.sub(r"(?i)(password|authorization|access_token)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", text)
    return text[:400]


def verify_eod_target(db, expected_database="neondb"):
    # Inspect routing BEFORE any query, including an identity SELECT.
    try:
        parsed = urlsplit(db.connection_string)
        if (parsed.scheme not in ("postgres", "postgresql") or
            parsed.hostname not in (EXPECTED_ENDPOINT + ".ap-southeast-1.aws.neon.tech",
                                    EXPECTED_ENDPOINT + "-pooler.ap-southeast-1.aws.neon.tech") or
            parsed.port not in (None, 5432) or not parsed.username or not parsed.password or
            parsed.path != "/" + expected_database or parsed.fragment or
            set(parse_qs(parsed.query)) - {"sslmode", "channel_binding"}):
            raise ValueError()
    except Exception:
        raise EODSafetyError("EOD target is not the approved isolated endpoint/database; no SQL issued") from None
    if expected_database not in ("neondb", "eod_ops_test"):
        raise EODSafetyError("Unapproved EOD database")
    rows = db.query("SELECT current_database() AS database, current_setting('neon.branch_id',true) AS branch_id, current_setting('neon.endpoint_id',true) AS endpoint_id")
    expected = {"database": expected_database, "branch_id": EXPECTED_BRANCH, "endpoint_id": EXPECTED_ENDPOINT}
    if len(rows) != 1 or any(rows[0].get(k) != v for k, v in expected.items()):
        raise EODSafetyError("Server-reported EOD isolation mismatch")
    return expected


def session_summary(db):
    # Do not advance solely from inference MAX(date). Include every derived table.
    return db.query("""
        WITH dates AS (
          SELECT date FROM regime_inference_daily UNION SELECT date FROM market_features_daily
          UNION SELECT date FROM portfolio_simulations_daily UNION SELECT date FROM portfolio_allocations_daily
          UNION SELECT date FROM benchmark_simulations_daily
        )
        SELECT d.date::text AS date,
          (SELECT array_agg(symbol ORDER BY symbol) FROM index_candles_daily WHERE date=d.date) AS symbols,
          (SELECT count(*)::int FROM market_features_daily WHERE date=d.date) AS features,
          (SELECT count(*)::int FROM regime_inference_daily WHERE date=d.date) AS regimes,
          (SELECT array_agg(variant ORDER BY variant) FROM portfolio_simulations_daily WHERE date=d.date) AS simulations,
          (SELECT array_agg(variant ORDER BY variant) FROM portfolio_allocations_daily WHERE date=d.date) AS allocations,
          (SELECT array_agg(benchmark_name ORDER BY benchmark_name) FROM benchmark_simulations_daily WHERE date=d.date) AS benchmarks
        FROM dates d WHERE d.date >= $1::date ORDER BY d.date
    """, [FROZEN_RESEARCH_END])


def last_complete_session(db, calendar):
    rows = session_summary(db)
    previous = None
    for row in rows:
        day = date.fromisoformat(row["date"][:10])
        if (set(row.get("symbols") or []) != set(REQUIRED_INDEX_SYMBOLS) or
            int(row.get("regimes", 0)) != 1 or
            (day.isoformat() > FROZEN_RESEARCH_END and int(row.get("features", 0)) != 1) or
            sorted(row.get("simulations") or []) != sorted(VARIANTS) or
            sorted(row.get("allocations") or []) != sorted(VARIANTS) or
            sorted(row.get("benchmarks") or []) != sorted(BENCHMARKS)):
            raise EODSafetyError("RECOVERY_REQUIRED: incomplete existing derived session " + day.isoformat() + "; records preserved")
        if not calendar.is_session(day):
            raise EODSafetyError("RECOVERY_REQUIRED: stored date is outside reviewed trading sessions")
        if previous is None:
            if day.isoformat() != FROZEN_RESEARCH_END:
                raise EODSafetyError("RECOVERY_REQUIRED: frozen continuity anchor is absent")
        elif calendar.next_session(previous) != day:
            raise EODSafetyError("RECOVERY_REQUIRED: historical session gap; no checkpoint skipping")
        previous = day
    if previous is None:
        raise EODSafetyError("RECOVERY_REQUIRED: no complete baseline session")
    return previous


def start_eod_run(db, session, trigger, identity):
    rows = db.query("""INSERT INTO pipeline_execution_logs
        (session_date,trigger_type,status,step_reached,records_processed,details)
        VALUES ($1::date,$2,'RUNNING','EOD_STARTED',0,$3::jsonb) RETURNING log_id""",
        [session, trigger, json.dumps({"component": "eod_pipeline", "identity": identity})])
    if len(rows) != 1 or type(rows[0].get("log_id")) is not int:
        raise EODSafetyError("Inserted EOD execution-log ID is unavailable")
    return rows[0]["log_id"]


def finish_eod_run(db, log_id, result, started):
    success = result["status"] in ("SUCCESS", "UP_TO_DATE")
    count = db.execute("""UPDATE pipeline_execution_logs
        SET status=$2,step_reached=$3,records_processed=$4,duration_ms=$5,details=$6::jsonb,error_message=$7
        WHERE log_id=$1 AND status='RUNNING'""",
        [log_id, "SUCCESS" if success else "FAILED", result["status"], result.get("dates_processed", 0),
         int((time.monotonic()-started)*1000), json.dumps(result, allow_nan=False),
         None if success else result.get("reason", "Incomplete EOD run")])
    if count != 1:
        raise EODSafetyError("EOD log finalization unconfirmed; no historical log was changed")


TABLE_KEYS = {
    "market_features_daily": ("date",), "regime_inference_daily": ("date",),
    "portfolio_simulations_daily": ("variant", "date"),
    "portfolio_allocations_daily": ("variant", "date"),
    "benchmark_simulations_daily": ("benchmark_name", "date"),
}


def _sql_value(value):
    # Preserve the existing engine's numerical calculations; just bind scalars.
    return value.item() if hasattr(value, "item") else value


def publish_session(db, records, day, previous):
    queries = [{"query": "SELECT pg_advisory_xact_lock(hashtext($1))", "params": ["eod:" + EXPECTED_BRANCH + ":" + day]}]
    # Inside the serializable transaction, fail rather than revise an existing
    # session or publish from an outdated predecessor after another writer wins.
    guard = " AND ".join("NOT EXISTS (SELECT 1 FROM " + t + " WHERE date=$1::date)" for t in TABLE_KEYS)
    predecessor = " AND ".join("(SELECT MAX(date) FROM " + t + ")=$2::date" for t in TABLE_KEYS)
    queries.append({"query": "SELECT 1 / CASE WHEN " + guard + " AND " + predecessor + " THEN 1 ELSE 0 END AS continuity_guard", "params": [day, previous]})
    expected_counts = {"market_features_daily": 1, "regime_inference_daily": 1,
                       "portfolio_simulations_daily": 4, "portfolio_allocations_daily": 4,
                       "benchmark_simulations_daily": 2}
    for table, count in expected_counts.items():
        rows = [r for r in records[table] if r["date"] == day]
        if len(rows) != count:
            raise EODSafetyError("Refusing incomplete EOD session bundle")
        for row in rows:
            columns = list(row)
            values = [_sql_value(row[c]) for c in columns]
            # Column names come only from the existing fixed record constructors.
            queries.append({"query": "INSERT INTO " + table + " (" + ",".join(columns) + ") VALUES (" +
                ",".join("$" + str(i+1) for i in range(len(columns))) + ")", "params": values})
    checks = " AND ".join("(SELECT count(*) FROM " + t + " WHERE date=$1::date)=" + str(n) for t, n in expected_counts.items())
    queries.append({"query": "SELECT 1 / CASE WHEN " + checks + " THEN 1 ELSE 0 END AS publication_guard", "params": [day]})
    db.execute_transaction(queries)


def _calculate_records(db, new_dates, latest_infer_str, calendar):
    # Load price history for feature adapter and returns
    prices_raw = db.query("""
        SELECT symbol, date::text as date, close
        FROM index_candles_daily
        ORDER BY date ASC, symbol ASC;
    """)
    import pandas as pd
    df_prices = pd.DataFrame(prices_raw)
    df_prices["close"] = df_prices["close"].astype(float)
    df_prices["date"] = pd.to_datetime(df_prices["date"])
    full_price_pivot = df_prices.pivot(index="date", columns="symbol", values="close").sort_index()

    feature_adapter = MarketFeatureAdapter(db_client=db)
    inference_engine = RegimeInferenceEngine()

    # Load previous baseline state
    last_inf = db.query("""
        SELECT prob_0, prob_1, prob_2, prob_3, prob_4, prob_5, accepted_regime
        FROM regime_inference_daily
        WHERE date = $1;
    """, params=[latest_infer_str])[0]
    curr_probs = [float(last_inf[f"prob_{i}"]) for i in range(6)]
    incumbent_regime = int(last_inf["accepted_regime"])

    last_allocs = db.query("""
        SELECT variant, incumbent_regime_after, holding_days_after, rebalance_triggered,
               w_nifty50, w_auto, w_bank, w_fmcg, w_it, w_metal, w_pharma, w_cash
        FROM portfolio_allocations_daily
        WHERE date = $1;
    """, params=[latest_infer_str])
    alloc_state: Dict[str, Dict[str, Any]] = {}
    for r in last_allocs:
        v = r["variant"]
        alloc_state[v] = {
            "incumbent_regime": int(r["incumbent_regime_after"]),
            "holding_days": int(r["holding_days_after"]),
            "rebalance_scheduled": bool(r["rebalance_triggered"]),
            "target_weights": {
                BENCHMARK_NAME: float(r["w_nifty50"]),
                "AUTO": float(r["w_auto"]),
                "BANK": float(r["w_bank"]),
                "FMCG": float(r["w_fmcg"]),
                "IT": float(r["w_it"]),
                "METAL": float(r["w_metal"]),
                "PHARMA": float(r["w_pharma"]),
                CASH_NAME: float(r["w_cash"]),
            },
        }

    last_sims = db.query("""
        SELECT variant, gross_nav, net_nav,
               w_post_auto, w_post_bank, w_post_fmcg, w_post_it, w_post_metal, w_post_pharma, w_post_cash
        FROM portfolio_simulations_daily
        WHERE date = $1;
    """, params=[latest_infer_str])
    sim_state: Dict[str, Dict[str, Any]] = {}
    for r in last_sims:
        v = r["variant"]
        sim_state[v] = {
            "gross_nav": float(r["gross_nav"]),
            "net_nav": float(r["net_nav"]),
            "current_holdings": {
                BENCHMARK_NAME: 0.0,
                "AUTO": float(r["w_post_auto"]),
                "BANK": float(r["w_post_bank"]),
                "FMCG": float(r["w_post_fmcg"]),
                "IT": float(r["w_post_it"]),
                "METAL": float(r["w_post_metal"]),
                "PHARMA": float(r["w_post_pharma"]),
                CASH_NAME: float(r["w_post_cash"]),
            },
        }

    last_bmarks = db.query("""
        SELECT benchmark_name, net_nav
        FROM benchmark_simulations_daily
        WHERE date = $1;
    """, params=[latest_infer_str])
    bmark_state: Dict[str, float] = {r["benchmark_name"]: float(r["net_nav"]) for r in last_bmarks}

    # Collectors
    rows_features = []
    rows_inference = []
    rows_simulations = []
    rows_allocations = []
    rows_benchmarks = []

    prev_date_str = latest_infer_str

    for idx, d_str in enumerate(new_dates):
        logger.info(f"Processing session {d_str} (prior: {prev_date_str})...")
        d_ts = pd.to_datetime(d_str)
        prev_d_ts = pd.to_datetime(prev_date_str)
        next_d_str = calendar.next_session(date.fromisoformat(d_str)).isoformat()

        sub_prices = full_price_pivot.loc[:d_ts]
        window_prices = sub_prices.iloc[-250:] if len(sub_prices) >= 250 else sub_prices

        # A. Features
        feats_df = feature_adapter.compute_features_from_prices(window_prices)
        raw_feats = {k: float(feats_df.loc[d_ts, k]) for k in feature_adapter.feature_names}
        scaled_feats_arr = inference_engine.scale_features(raw_feats)
        scaled_feats = {k: float(scaled_feats_arr[i]) for i, k in enumerate(feature_adapter.feature_names)}

        rows_features.append({
            "date": d_str,
            "period": "production",
            "features_raw": json.dumps(raw_feats),
            "features_robust_scaled": json.dumps(scaled_feats),
        })

        # B. Inference
        inf_res = inference_engine.forward_step(
            features=raw_feats,
            prev_probs=curr_probs,
            incumbent_regime=incumbent_regime,
        )
        curr_probs = inf_res["probs_array"]
        accepted_regime = inf_res["accepted_regime"]

        rows_inference.append({
            "date": d_str,
            "period": "production",
            "prob_0": inf_res["prob_0"],
            "prob_1": inf_res["prob_1"],
            "prob_2": inf_res["prob_2"],
            "prob_3": inf_res["prob_3"],
            "prob_4": inf_res["prob_4"],
            "prob_5": inf_res["prob_5"],
            "raw_argmax": inf_res["raw_regime_argmax"],
            "max_probability": inf_res["max_probability"],
            "is_confident": inf_res["is_confident"],
            "accepted_regime": accepted_regime,
        })

        # C. Asset Returns
        curr_p = full_price_pivot.loc[d_ts]
        prev_p = full_price_pivot.loc[prev_d_ts]

        asset_returns: Dict[str, float] = {}
        for s in SECTOR_NAMES:
            sym_key = f"NIFTY {s}"
            asset_returns[s] = (float(curr_p[sym_key]) / float(prev_p[sym_key])) - 1.0
        asset_returns[BENCHMARK_NAME] = (float(curr_p["NIFTY 50"]) / float(prev_p["NIFTY 50"])) - 1.0
        asset_returns[CASH_NAME] = 0.0

        # D. Simulations and Allocations
        for v in VARIANTS:
            v_alloc = alloc_state[v]
            v_sim = sim_state[v]

            rebal_executing = v_alloc["rebalance_scheduled"]
            target_w = v_alloc["target_weights"] if rebal_executing else None

            step_res = step_daily_nav(
                current_holdings=v_sim["current_holdings"],
                asset_returns=asset_returns,
                net_nav_prev=v_sim["net_nav"],
                gross_nav_prev=v_sim["gross_nav"],
                rebalance_executing=rebal_executing,
                target_weights=target_w,
            )

            v_sim["gross_nav"] = step_res["gross_nav"]
            v_sim["net_nav"] = step_res["net_nav"]
            v_sim["current_holdings"] = step_res["post_holdings"]

            post_h = step_res["post_holdings"]
            rows_simulations.append({
                "variant": v,
                "date": d_str,
                "period": "production",
                "rebalance_executed": rebal_executing,
                "rebalance_bypassed_r3": False,
                "actual_turnover": step_res["actual_turnover"],
                "nominal_turnover": step_res["actual_turnover"],
                "transaction_cost": step_res["transaction_cost"],
                "gross_return": step_res["gross_return"],
                "net_return": step_res["net_return"],
                "gross_nav": step_res["gross_nav"],
                "net_nav": step_res["net_nav"],
                "accepted_regime": accepted_regime,
                "w_post_auto": post_h.get("AUTO", 0.0),
                "w_post_bank": post_h.get("BANK", 0.0),
                "w_post_fmcg": post_h.get("FMCG", 0.0),
                "w_post_it": post_h.get("IT", 0.0),
                "w_post_metal": post_h.get("METAL", 0.0),
                "w_post_pharma": post_h.get("PHARMA", 0.0),
                "w_post_cash": post_h.get(CASH_NAME, 0.0),
            })

            trailing_sector_prices = sub_prices[[f"NIFTY {s}" for s in SECTOR_NAMES]].copy()
            trailing_sector_prices.columns = SECTOR_NAMES

            trig_res = evaluate_rebalance_trigger(
                variant=v,
                target_regime=accepted_regime,
                incumbent_regime=v_alloc["incumbent_regime"],
                holding_days=v_alloc["holding_days"],
                current_weights=post_h,
                price_df=trailing_sector_prices,
            )

            target_weights_next = trig_res["target_weights"]
            rebal_triggered = trig_res["rebalance_triggered"]

            rows_allocations.append({
                "variant": v,
                "date": d_str,
                "exec_date": next_d_str,
                "period": "production",
                "incumbent_regime_before": v_alloc["incumbent_regime"],
                "incumbent_regime_after": trig_res["new_incumbent_regime"],
                "holding_days_before": v_alloc["holding_days"],
                "holding_days_after": trig_res["new_holding_days"],
                "rebalance_triggered": rebal_triggered,
                "rebalance_bypassed_r3": trig_res["rebalance_bypassed_r3"],
                "turnover": trig_res["turnover"],
                "transaction_cost_rate": 0.0015,
                "w_nifty50": target_weights_next.get(BENCHMARK_NAME, 0.0),
                "w_auto": target_weights_next.get("AUTO", 0.0),
                "w_bank": target_weights_next.get("BANK", 0.0),
                "w_fmcg": target_weights_next.get("FMCG", 0.0),
                "w_it": target_weights_next.get("IT", 0.0),
                "w_metal": target_weights_next.get("METAL", 0.0),
                "w_pharma": target_weights_next.get("PHARMA", 0.0),
                "w_cash": target_weights_next.get(CASH_NAME, 0.0),
            })

            v_alloc["incumbent_regime"] = trig_res["new_incumbent_regime"]
            v_alloc["holding_days"] = trig_res["new_holding_days"]
            v_alloc["rebalance_scheduled"] = rebal_triggered
            v_alloc["target_weights"] = target_weights_next

        # E. Benchmarks
        r_n50 = asset_returns[BENCHMARK_NAME]
        bmark_state["NIFTY50_BUY_HOLD"] *= (1.0 + r_n50)
        rows_benchmarks.append({
            "benchmark_name": "NIFTY50_BUY_HOLD",
            "date": d_str,
            "period": "production",
            "net_return": r_n50,
            "net_nav": bmark_state["NIFTY50_BUY_HOLD"],
            "actual_turnover": 0.0,
            "transaction_cost": 0.0,
        })

        import numpy as np
        r_ew = float(np.mean([asset_returns[s] for s in SECTOR_NAMES]))
        bmark_state["EQUAL_WEIGHT_6SECTOR"] *= (1.0 + r_ew)
        rows_benchmarks.append({
            "benchmark_name": "EQUAL_WEIGHT_6SECTOR",
            "date": d_str,
            "period": "production",
            "net_return": r_ew,
            "net_nav": bmark_state["EQUAL_WEIGHT_6SECTOR"],
            "actual_turnover": 0.0,
            "transaction_cost": 0.0,
        })

        incumbent_regime = accepted_regime
        prev_date_str = d_str

    return {"market_features_daily": rows_features, "regime_inference_daily": rows_inference,
            "portfolio_simulations_daily": rows_simulations, "portfolio_allocations_daily": rows_allocations,
            "benchmark_simulations_daily": rows_benchmarks}


def run_pipeline(target_date=None, trigger_type="daily_cron", *, db=None, calendar=None,
                 clock=None, expected_database="neondb"):
    started = time.monotonic()
    log_id = None
    client = db
    try:
        client = client if client is not None else get_db_client()
        identity = verify_eod_target(client, expected_database)
        calendar = calendar or TradingCalendar()
        now = clock() if clock else datetime.now(IST)
        eligible = calendar.latest_completed_session(now)
        target = date.fromisoformat(target_date) if target_date else eligible
        if target > now.astimezone(IST).date():
            raise EODSafetyError("A future target date is not permitted")
        # A holiday manual request resolves to its latest actual completed session.
        while not calendar.is_session(target):
            target -= timedelta(days=1)
        if target > eligible:
            raise EODSafetyError("Requested session is not yet eligible for EOD collection")
        anchor = last_complete_session(client, calendar)
        if anchor > eligible:
            raise EODSafetyError("Stored session is beyond the completed-session boundary")
        if (target-anchor).days > 90:
            raise EODSafetyError("RECOVERY_REQUIRED: EOD recovery exceeds the 90-day bound")
        expected = [d.isoformat() for d in calendar.sessions(anchor+timedelta(days=1), target)]
        log_id = start_eod_run(client, target.isoformat(), trigger_type, identity)
        if not expected:
            result = {"status": "UP_TO_DATE", "latest_session": anchor.isoformat(), "dates_processed": 0}
        else:
            ingestion = CatchupIngestionService(db_client=client, append_only=True, persist_recovery_queue=False)
            fetched = ingestion.run_catchup(target_date=target.isoformat(), trigger_type=trigger_type, expected_dates=expected)
            if fetched.get("status") != "FETCH_COMPLETE" or fetched.get("missing"):
                result = {"status": "PARTIAL", "reason": "Expected trading-session candles are incomplete",
                          "fetch_res": fetched, "dates_processed": 0}
            else:
                # Confirm exact eight-index coverage before running the frozen engines.
                coverage = client.query("SELECT date::text AS date,array_agg(symbol ORDER BY symbol) AS symbols FROM index_candles_daily WHERE date=ANY($1::date[]) GROUP BY date ORDER BY date", [expected])
                if {r["date"][:10] for r in coverage} != set(expected) or any(set(r["symbols"]) != set(REQUIRED_INDEX_SYMBOLS) for r in coverage):
                    raise EODSafetyError("Eight-index session coverage is incomplete")
                records = _calculate_records(client, expected, anchor.isoformat(), calendar)
                previous = anchor.isoformat()
                for day in expected:
                    publish_session(client, records, day, previous)
                    previous = day
                if last_complete_session(client, calendar).isoformat() != target.isoformat():
                    raise EODSafetyError("Post-publication completeness check failed")
                result = {"status": "SUCCESS", "latest_session": target.isoformat(), "dates_processed": len(expected)}
        finish_eod_run(client, log_id, result, started)
        return result
    except Exception as error:
        result = {"status": "FAILED", "reason": _safe_error(error, getattr(client, "connection_string", "")),
                  "error_type": type(error).__name__}
        if log_id is not None:
            try:
                finish_eod_run(client, log_id, result, started)
            except Exception:
                result["log_finalization"] = "UNCONFIRMED"
        logger.error("EOD run failed (%s): %s", type(error).__name__, result["reason"])
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Daily EOD Pipeline Orchestrator")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--trigger", type=str, default="daily_cron")
    args = parser.parse_args(argv)
    result = run_pipeline(target_date=args.date, trigger_type=args.trigger)
    print(json.dumps(result, allow_nan=False, indent=2))
    return 0 if result.get("status") in ("SUCCESS", "UP_TO_DATE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
