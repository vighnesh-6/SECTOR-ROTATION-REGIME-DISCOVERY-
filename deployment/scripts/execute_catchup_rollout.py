"""
deployment/scripts/execute_catchup_rollout.py
============================================
Sequential Chronological Rollout of Causal Inference & Portfolio Compounding
for the 33 Catch-up Trading Sessions (2026-09-21 to 2026-11-06).

Maintains strict project isolation and numerical continuity from the 2026-09-18 baseline.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import get_db_client, NeonClient
from engine.feature_adapter import (
    MarketFeatureAdapter,
    REQUIRED_INDEX_SYMBOLS,
    SECTOR_NAMES,
    MIN_LOOKBACK_SESSIONS,
)
from engine.inference_engine import RegimeInferenceEngine
from engine.portfolio_state import (
    ALL_ASSETS,
    BENCHMARK_NAME,
    CASH_NAME,
    calculate_trailing_volatilities,
    evaluate_rebalance_trigger,
    step_daily_nav,
)

logger = logging.getLogger("catchup_rollout")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

VARIANTS = ["1A", "1B", "2A", "2B"]
BENCHMARKS = ["NIFTY50_BUY_HOLD", "EQUAL_WEIGHT_6SECTOR"]


def execute_rollout(dry_run: bool = False) -> Dict[str, Any]:
    db = get_db_client()
    logger.info("Starting Catch-up Rollout for Sessions: 2026-09-21 -> 2026-11-06...")

    # 1. Identify catch-up dates
    dates_query = """
        SELECT DISTINCT date
        FROM index_candles_daily
        WHERE date > '2026-09-18'
        ORDER BY date ASC;
    """
    catchup_dates = [str(r["date"])[:10] for r in db.query(dates_query)]
    logger.info(f"Found {len(catchup_dates)} catch-up dates to process: {catchup_dates[0]} to {catchup_dates[-1]}")
    assert len(catchup_dates) == 33, f"Expected exactly 33 dates, got {len(catchup_dates)}"

    # 2. Check baseline state as of 2026-09-18
    # Baseline regime inference
    last_inf = db.query("""
        SELECT prob_0, prob_1, prob_2, prob_3, prob_4, prob_5, accepted_regime
        FROM regime_inference_daily
        WHERE date = '2026-09-18';
    """)[0]
    curr_probs = [float(last_inf[f"prob_{i}"]) for i in range(6)]
    incumbent_regime = int(last_inf["accepted_regime"])
    logger.info(f"Baseline (2026-09-18) Regime: {incumbent_regime}, Probs: {curr_probs}")

    # Baseline allocations
    last_allocs = db.query("""
        SELECT variant, incumbent_regime_after, holding_days_after, rebalance_triggered,
               w_nifty50, w_auto, w_bank, w_fmcg, w_it, w_metal, w_pharma, w_cash
        FROM portfolio_allocations_daily
        WHERE date = '2026-09-18';
    """)
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

    # Baseline simulations
    last_sims = db.query("""
        SELECT variant, gross_nav, net_nav,
               w_post_auto, w_post_bank, w_post_fmcg, w_post_it, w_post_metal, w_post_pharma, w_post_cash
        FROM portfolio_simulations_daily
        WHERE date = '2026-09-18';
    """)
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

    # Baseline benchmarks
    last_bmarks = db.query("""
        SELECT benchmark_name, net_nav
        FROM benchmark_simulations_daily
        WHERE date = '2026-09-18';
    """)
    bmark_state: Dict[str, float] = {r["benchmark_name"]: float(r["net_nav"]) for r in last_bmarks}

    # 3. Load wide closing price history for trailing calculations
    logger.info("Fetching price history for feature adapter...")
    prices_raw = db.query("""
        SELECT symbol, date::text as date, close
        FROM index_candles_daily
        ORDER BY date ASC, symbol ASC;
    """)
    df_prices_raw = pd.DataFrame(prices_raw)
    df_prices_raw["close"] = df_prices_raw["close"].astype(float)
    df_prices_raw["date"] = pd.to_datetime(df_prices_raw["date"])
    full_price_pivot = df_prices_raw.pivot(index="date", columns="symbol", values="close").sort_index()

    feature_adapter = MarketFeatureAdapter(db_client=db)
    inference_engine = RegimeInferenceEngine()

    # Collectors for batch insertion
    rows_features: List[Dict[str, Any]] = []
    rows_inference: List[Dict[str, Any]] = []
    rows_allocations: List[Dict[str, Any]] = []
    rows_simulations: List[Dict[str, Any]] = []
    rows_benchmarks: List[Dict[str, Any]] = []

    # 4. Chronological Step-by-Step Execution
    prev_date_str = "2026-09-18"

    for idx, d_str in enumerate(catchup_dates):
        d_ts = pd.to_datetime(d_str)
        prev_d_ts = pd.to_datetime(prev_date_str)
        next_d_str = catchup_dates[idx + 1] if idx + 1 < len(catchup_dates) else (datetime.strptime(d_str, "%Y-%m-%d").date() + timedelta(days=3)).strftime("%Y-%m-%d")

        # Slice trailing price history up to d_ts (250 sessions)
        sub_prices = full_price_pivot.loc[:d_ts]
        window_prices = sub_prices.iloc[-250:] if len(sub_prices) >= 250 else sub_prices

        # A. Feature Calculation
        feats_df = feature_adapter.compute_features_from_prices(window_prices)
        raw_feats = {k: float(feats_df.loc[d_ts, k]) for k in feature_adapter.feature_names}
        scaled_feats_arr = inference_engine.scale_features(raw_feats)
        scaled_feats = {k: float(scaled_feats_arr[i]) for i, k in enumerate(feature_adapter.feature_names)}

        rows_features.append({
            "date": d_str,
            "period": "catchup",
            "features_raw": json.dumps(raw_feats),
            "features_robust_scaled": json.dumps(scaled_feats),
        })

        # B. Causal Forward HMM Inference
        inf_res = inference_engine.forward_step(
            features=raw_feats,
            prev_probs=curr_probs,
            incumbent_regime=incumbent_regime,
        )
        curr_probs = inf_res["probs_array"]
        accepted_regime = inf_res["accepted_regime"]

        rows_inference.append({
            "date": d_str,
            "period": "catchup",
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

        # C. Asset Returns for session d_str (from prev_d_ts to d_ts)
        curr_p = full_price_pivot.loc[d_ts]
        prev_p = full_price_pivot.loc[prev_d_ts]

        asset_returns: Dict[str, float] = {}
        for s in SECTOR_NAMES:
            sym_key = f"NIFTY {s}"
            asset_returns[s] = (float(curr_p[sym_key]) / float(prev_p[sym_key])) - 1.0
        asset_returns[BENCHMARK_NAME] = (float(curr_p["NIFTY 50"]) / float(prev_p["NIFTY 50"])) - 1.0
        asset_returns[CASH_NAME] = 0.0

        # D. Portfolio Simulations & Allocations for each variant
        for v in VARIANTS:
            v_alloc = alloc_state[v]
            v_sim = sim_state[v]

            rebal_executing = v_alloc["rebalance_scheduled"]
            target_w = v_alloc["target_weights"] if rebal_executing else None

            # 1. Simulation compounding
            step_res = step_daily_nav(
                current_holdings=v_sim["current_holdings"],
                asset_returns=asset_returns,
                net_nav_prev=v_sim["net_nav"],
                gross_nav_prev=v_sim["gross_nav"],
                rebalance_executing=rebal_executing,
                target_weights=target_w,
            )

            # Update simulation state
            v_sim["gross_nav"] = step_res["gross_nav"]
            v_sim["net_nav"] = step_res["net_nav"]
            v_sim["current_holdings"] = step_res["post_holdings"]

            post_h = step_res["post_holdings"]
            rows_simulations.append({
                "variant": v,
                "date": d_str,
                "period": "catchup",
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

            # 2. Allocation Decision for next trading day
            # Needs trailing sector prices if variant is 1B or 2B
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
                "period": "catchup",
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

            # Update allocation state for next date
            v_alloc["incumbent_regime"] = trig_res["new_incumbent_regime"]
            v_alloc["holding_days"] = trig_res["new_holding_days"]
            v_alloc["rebalance_scheduled"] = rebal_triggered
            v_alloc["target_weights"] = target_weights_next

        # E. Benchmarks Compounding
        r_n50 = asset_returns[BENCHMARK_NAME]
        bmark_state["NIFTY50_BUY_HOLD"] *= (1.0 + r_n50)
        rows_benchmarks.append({
            "benchmark_name": "NIFTY50_BUY_HOLD",
            "date": d_str,
            "period": "catchup",
            "net_return": r_n50,
            "net_nav": bmark_state["NIFTY50_BUY_HOLD"],
            "actual_turnover": 0.0,
            "transaction_cost": 0.0,
        })

        r_ew = float(np.mean([asset_returns[s] for s in SECTOR_NAMES]))
        bmark_state["EQUAL_WEIGHT_6SECTOR"] *= (1.0 + r_ew)
        rows_benchmarks.append({
            "benchmark_name": "EQUAL_WEIGHT_6SECTOR",
            "date": d_str,
            "period": "catchup",
            "net_return": r_ew,
            "net_nav": bmark_state["EQUAL_WEIGHT_6SECTOR"],
            "actual_turnover": 0.0,
            "transaction_cost": 0.0,
        })

        # Advance incumbent regime for next session inference
        incumbent_regime = accepted_regime
        prev_date_str = d_str

    logger.info(f"Generated {len(rows_inference)} inference, {len(rows_allocations)} alloc, {len(rows_simulations)} sim, {len(rows_benchmarks)} bmark records.")

    if dry_run:
        logger.info("Dry-run complete. No database writes executed.")
        return {"dry_run": True, "dates_processed": len(catchup_dates)}

    # 5. Batch Persist into Neon PostgreSQL
    logger.info("Persisting catch-up records to Neon PostgreSQL...")

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
    logger.info("Persisted market_features_daily.")

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
    logger.info("Persisted regime_inference_daily.")

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
    logger.info("Persisted portfolio_simulations_daily.")

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
    logger.info("Persisted portfolio_allocations_daily.")

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
    logger.info("Persisted benchmark_simulations_daily.")

    return {
        "status": "SUCCESS",
        "dates_processed": len(catchup_dates),
        "from_date": catchup_dates[0],
        "to_date": catchup_dates[-1],
        "features_inserted": len(rows_features),
        "inference_inserted": len(rows_inference),
        "allocations_inserted": len(rows_allocations),
        "simulations_inserted": len(rows_simulations),
        "benchmarks_inserted": len(rows_benchmarks),
    }


if __name__ == "__main__":
    res = execute_rollout()
    print("\nRollout Final Summary:")
    print(json.dumps(res, indent=2))
