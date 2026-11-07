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
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path
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

logger = logging.getLogger("daily_eod")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [daily_eod]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

VARIANTS = ["1A", "1B", "2A", "2B"]


def run_pipeline(target_date: Optional[str] = None, trigger_type: str = "daily_cron") -> Dict[str, Any]:
    start_time = time.time()
    db = get_db_client()

    logger.info("=" * 65)
    logger.info("STARTING DAILY EOD SECTOR ROTATION PIPELINE EXECUTION")
    logger.info("=" * 65)

    # 1. Ingestion: Fetch missing candles from Yahoo Finance and persist to Neon
    logger.info("Step 1: Ingesting daily EOD candles from Yahoo Finance...")
    ingestion_service = CatchupIngestionService(db_client=db)
    fetch_res = ingestion_service.run_catchup(target_date=target_date, trigger_type=trigger_type)
    logger.info(f"Ingestion result: {fetch_res}")

    if fetch_res.get("status") == "FAILED":
        logger.error("Ingestion failed. Aborting downstream inference and portfolio updates.")
        return {"status": "FAILED", "reason": "Ingestion failed", "fetch_res": fetch_res}

    # 2. Check pending completed trading sessions
    latest_inf_row = db.query("SELECT MAX(date)::text as max_date FROM regime_inference_daily;")
    latest_infer_str = str(latest_inf_row[0]["max_date"])[:10] if latest_inf_row and latest_inf_row[0].get("max_date") else "2026-09-18"

    # Find complete sessions where all 8 indices are present in index_candles_daily
    pending_dates_query = """
        SELECT date::text as dt
        FROM index_candles_daily
        WHERE date > $1
        GROUP BY date
        HAVING COUNT(DISTINCT symbol) = 8
        ORDER BY date ASC;
    """
    new_dates = [r["dt"][:10] for r in db.query(pending_dates_query, params=[latest_infer_str])]

    if not new_dates:
        logger.info(f"Pipeline is up-to-date. Latest completed session in DB is {latest_infer_str}.")
        return {
            "status": "UP_TO_DATE",
            "latest_session": latest_infer_str,
            "duration_ms": int((time.time() - start_time) * 1000),
        }

    logger.info(f"Step 2: Processing {len(new_dates)} new completed session(s): {new_dates}")

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
        next_d_str = new_dates[idx + 1] if idx + 1 < len(new_dates) else (datetime.strptime(d_str, "%Y-%m-%d").date() + timedelta(days=3)).strftime("%Y-%m-%d")

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

    # Persist all records atomically per table
    logger.info("Persisting calculated records to Neon PostgreSQL...")

    # A. market_features_daily
    feat_vals = [
        f"('{r['date']}', '{r['period']}', '{r['features_raw']}'::jsonb, '{r['features_robust_scaled']}'::jsonb)"
        for r in rows_features
    ]
    db.execute(
        f"INSERT INTO market_features_daily (date, period, features_raw, features_robust_scaled) "
        f"VALUES {', '.join(feat_vals)} "
        f"ON CONFLICT (date) DO UPDATE SET features_raw = EXCLUDED.features_raw, features_robust_scaled = EXCLUDED.features_robust_scaled;"
    )

    # B. regime_inference_daily
    inf_vals = [
        f"('{r['date']}', '{r['period']}', {r['prob_0']:.8f}, {r['prob_1']:.8f}, {r['prob_2']:.8f}, {r['prob_3']:.8f}, {r['prob_4']:.8f}, {r['prob_5']:.8f}, {r['raw_argmax']}, {r['max_probability']:.8f}, {r['is_confident']}, {r['accepted_regime']})"
        for r in rows_inference
    ]
    db.execute(
        f"INSERT INTO regime_inference_daily (date, period, prob_0, prob_1, prob_2, prob_3, prob_4, prob_5, raw_argmax, max_probability, is_confident, accepted_regime) "
        f"VALUES {', '.join(inf_vals)} "
        f"ON CONFLICT (date) DO UPDATE SET prob_0 = EXCLUDED.prob_0, accepted_regime = EXCLUDED.accepted_regime;"
    )

    # C. portfolio_simulations_daily
    sim_vals = [
        f"('{r['variant']}', '{r['date']}', '{r['period']}', {r['rebalance_executed']}, {r['rebalance_bypassed_r3']}, {r['actual_turnover']:.6f}, {r['nominal_turnover']:.6f}, {r['transaction_cost']:.6f}, {r['gross_return']:.8f}, {r['net_return']:.8f}, {r['gross_nav']:.6f}, {r['net_nav']:.6f}, {r['accepted_regime']}, {r['w_post_auto']:.6f}, {r['w_post_bank']:.6f}, {r['w_post_fmcg']:.6f}, {r['w_post_it']:.6f}, {r['w_post_metal']:.6f}, {r['w_post_pharma']:.6f}, {r['w_post_cash']:.6f})"
        for r in rows_simulations
    ]
    db.execute(
        f"INSERT INTO portfolio_simulations_daily (variant, date, period, rebalance_executed, rebalance_bypassed_r3, actual_turnover, nominal_turnover, transaction_cost, gross_return, net_return, gross_nav, net_nav, accepted_regime, w_post_auto, w_post_bank, w_post_fmcg, w_post_it, w_post_metal, w_post_pharma, w_post_cash) "
        f"VALUES {', '.join(sim_vals)} "
        f"ON CONFLICT (variant, date) DO UPDATE SET net_nav = EXCLUDED.net_nav;"
    )

    # D. portfolio_allocations_daily
    alloc_vals = [
        f"('{r['variant']}', '{r['date']}', '{r['exec_date']}', '{r['period']}', {r['incumbent_regime_before']}, {r['incumbent_regime_after']}, {r['holding_days_before']}, {r['holding_days_after']}, {r['rebalance_triggered']}, {r['rebalance_bypassed_r3']}, {r['turnover']:.6f}, {r['transaction_cost_rate']:.6f}, {r['w_nifty50']:.6f}, {r['w_auto']:.6f}, {r['w_bank']:.6f}, {r['w_fmcg']:.6f}, {r['w_it']:.6f}, {r['w_metal']:.6f}, {r['w_pharma']:.6f}, {r['w_cash']:.6f})"
        for r in rows_allocations
    ]
    db.execute(
        f"INSERT INTO portfolio_allocations_daily (variant, date, exec_date, period, incumbent_regime_before, incumbent_regime_after, holding_days_before, holding_days_after, rebalance_triggered, rebalance_bypassed_r3, turnover, transaction_cost_rate, w_nifty50, w_auto, w_bank, w_fmcg, w_it, w_metal, w_pharma, w_cash) "
        f"VALUES {', '.join(alloc_vals)} "
        f"ON CONFLICT (variant, date) DO UPDATE SET holding_days_after = EXCLUDED.holding_days_after;"
    )

    # E. benchmark_simulations_daily
    bmark_vals = [
        f"('{r['benchmark_name']}', '{r['date']}', '{r['period']}', {r['net_return']:.8f}, {r['net_nav']:.6f}, {r['actual_turnover']:.6f}, {r['transaction_cost']:.6f})"
        for r in rows_benchmarks
    ]
    db.execute(
        f"INSERT INTO benchmark_simulations_daily (benchmark_name, date, period, net_return, net_nav, actual_turnover, transaction_cost) "
        f"VALUES {', '.join(bmark_vals)} "
        f"ON CONFLICT (benchmark_name, date) DO UPDATE SET net_nav = EXCLUDED.net_nav;"
    )

    duration_ms = int((time.time() - start_time) * 1000)
    logger.info("=" * 65)
    logger.info(f"DAILY EOD PIPELINE EXECUTION COMPLETED IN {duration_ms} ms.")
    logger.info("=" * 65)

    return {
        "status": "SUCCESS",
        "dates_processed": len(new_dates),
        "latest_session": new_dates[-1],
        "duration_ms": duration_ms,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily EOD Pipeline Orchestrator")
    parser.add_argument("--date", type=str, default=None, help="Target session date (YYYY-MM-DD)")
    parser.add_argument("--trigger", type=str, default="daily_cron", help="Trigger type")
    args = parser.parse_args()

    res = run_pipeline(target_date=args.date, trigger_type=args.trigger)
    print(json.dumps(res, indent=2))
