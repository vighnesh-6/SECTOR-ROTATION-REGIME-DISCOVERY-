"""
Phase 10.6 Investigation 2 — Execution Sensitivity Analysis.

Evaluates portfolio profitability and operational fragility across four discrete execution models:
  - Model A (Canonical Baseline): t+1 Close execution (1 session latency).
  - Model B (Operational Delay): t+2 Close execution (2 sessions latency).
  - Model C (Theoretical Zero-Latency Bound): t Close instantaneous execution (upper diagnostic bound).
  - Model D (Next-Day Open): t+1 Open execution (09:15 IST opening proxy, with overnight/intraday split).

All models preserve complete holdings drift, actual turnover, fee accounting, and state continuity.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.portfolio_backtest import (
    ALL_ASSETS,
    ANNUALIZATION_FACTOR,
    DEFAULT_TRANSACTION_COST_RATE,
    SECTOR_NAMES,
    VARIANTS,
    calculate_actual_turnover,
    calculate_drifted_weights,
    simulate_portfolio,
)
from src.comparative_evaluation import compute_single_portfolio_metrics

logger = logging.getLogger(__name__)

EXECUTION_MODELS: List[str] = ["t+1_close", "t+2_close", "t_close", "t+1_open"]

PERIOD_RANGES: Dict[str, Tuple[str, str]] = {
    "train": ("2019-11-01", "2024-12-31"),
    "holdout": ("2025-01-02", "2026-09-18"),
    "full": ("2019-11-01", "2026-09-18"),
}


def load_open_and_close_prices(
    price_dir: Optional[Union[str, Path]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load aligned Open and Close price DataFrames for all universe assets.
    """
    p_dir = Path(price_dir) if price_dir is not None else Path("data/processed/aligned")

    close_dict: Dict[str, pd.Series] = {}
    open_dict: Dict[str, pd.Series] = {}

    for s in SECTOR_NAMES:
        fpath = p_dir / f"nifty_{s.lower()}_aligned.csv"
        pdf = pd.read_csv(fpath, index_col=0, parse_dates=True)
        close_dict[s] = pdf["Close"]
        open_dict[s] = pdf["Open"]

    p50_path = p_dir / "nifty50_aligned.csv"
    p50_df = pd.read_csv(p50_path, index_col=0, parse_dates=True)
    close_dict["NIFTY50"] = p50_df["Close"]
    open_dict["NIFTY50"] = p50_df["Open"]

    close_df = pd.DataFrame(close_dict).sort_index()
    open_df = pd.DataFrame(open_dict).sort_index()

    return close_df, open_df


def simulate_delayed_close_portfolio(
    schedule_df: pd.DataFrame,
    price_df: pd.DataFrame,
    delay_sessions: int = 2,
    cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
    tol: float = 1e-7,
) -> pd.DataFrame:
    """
    Simulate portfolio with a discrete execution delay of N sessions at market Close.
    When delay_sessions = 1: standard t+1 Close.
    When delay_sessions = 2: operational delay t+2 Close.
    When delay_sessions = 0: theoretical zero-latency t Close.
    """
    dates = schedule_df.index
    n_dates = len(dates)
    n_assets = len(ALL_ASSETS)
    w_cols = [f"w_{a}" for a in ALL_ASSETS]
    variant_name = str(schedule_df["variant"].iloc[0])

    # Initial state at Date 0 Close (2019-10-31)
    w_post = np.zeros(n_assets, dtype=float)
    w_post[ALL_ASSETS.index("NIFTY50")] = 1.0

    nav_gross = 1.0
    nav_net = 1.0

    # Queue for pending orders: map of execution session index -> target weights
    # Session k index: 1 to n_dates - 1
    # For delay_sessions=1, signal on k-1 executes on session k
    # For delay_sessions=2, signal on k-1 executes on session k+1
    # For delay_sessions=0, signal on k-1 executes on session k-1 (or signal on k executes on k)
    pending_executions: Dict[int, np.ndarray] = {}

    records: List[Dict[str, Any]] = []

    for k in range(1, n_dates):
        dt_prev = dates[k - 1]
        dt_curr = dates[k]

        # 1. Asset returns over interval dt_prev -> dt_curr
        rets = np.zeros(n_assets, dtype=float)
        for idx, a in enumerate(ALL_ASSETS):
            if a == "CASH":
                rets[idx] = 0.0
            else:
                p_prev = float(price_df.loc[dt_prev, a])
                p_curr = float(price_df.loc[dt_curr, a])
                rets[idx] = (p_curr / p_prev) - 1.0

        w_hold = w_post.copy()
        r_gross = float(np.sum(w_hold * rets))

        nav_pre_gross = nav_gross * (1.0 + r_gross)
        nav_pre_net = nav_net * (1.0 + r_gross)
        w_drift = calculate_drifted_weights(w_hold, rets, tol=tol)

        # 2. Check if rebalance was authorized on dt_prev
        row_prev = schedule_df.loc[dt_prev]
        if bool(row_prev["rebalance_triggered"]):
            target_w = row_prev[w_cols].values.astype(float)
            target_w = np.maximum(target_w, 0.0)
            target_w = target_w / np.sum(target_w)

            if delay_sessions == 0:
                # Theoretical: signal on dt_curr was somehow executed on dt_prev
                # Handled below
                pass
            elif delay_sessions == 1:
                pending_executions[k] = target_w
            elif delay_sessions == 2:
                pending_executions[k + 1] = target_w

        # Check execution for this session k
        if delay_sessions == 0:
            # Model C: signal generated on session k-1 was executed on session k-1 close,
            # meaning at session k, portfolio starts ALREADY holding target_w
            row_curr_signal = schedule_df.loc[dt_curr]
            rebal_executing = bool(row_curr_signal["rebalance_triggered"])
            if rebal_executing:
                w_target = row_curr_signal[w_cols].values.astype(float)
                w_target = np.maximum(w_target, 0.0)
                w_target = w_target / np.sum(w_target)
                to_actual = calculate_actual_turnover(w_target, w_drift, tol=tol)
                tc = float(nav_pre_net * to_actual * cost_rate)
                nav_post_net = nav_pre_net - tc
                nav_post_gross = nav_pre_gross
                w_post = w_target.copy()
            else:
                to_actual = 0.0
                tc = 0.0
                nav_post_net = nav_pre_net
                nav_post_gross = nav_pre_gross
                w_post = w_drift.copy()
        else:
            if k in pending_executions:
                w_target = pending_executions[k]
                rebal_executing = True
                to_actual = calculate_actual_turnover(w_target, w_drift, tol=tol)
                tc = float(nav_pre_net * to_actual * cost_rate)
                nav_post_net = nav_pre_net - tc
                nav_post_gross = nav_pre_gross
                w_post = w_target.copy()
            else:
                rebal_executing = False
                to_actual = 0.0
                tc = 0.0
                nav_post_net = nav_pre_net
                nav_post_gross = nav_pre_gross
                w_post = w_drift.copy()

        r_net = float((nav_post_net / nav_net) - 1.0)
        nav_gross = nav_post_gross
        nav_net = nav_post_net
        c_cost = float(r_net - r_gross)

        rec = {
            "date": dt_curr,
            "period": str(schedule_df.loc[dt_curr, "period"]),
            "variant": variant_name,
            "rebalance_executed": rebal_executing,
            "actual_turnover": to_actual,
            "transaction_cost": tc,
            "gross_return": r_gross,
            "net_return": r_net,
            "gross_nav": nav_gross,
            "net_nav": nav_net,
            "contrib_cost": c_cost,
        }
        records.append(rec)

    return pd.DataFrame(records).set_index("date")


def simulate_open_execution_portfolio(
    schedule_df: pd.DataFrame,
    close_df: pd.DataFrame,
    open_df: pd.DataFrame,
    cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
    tol: float = 1e-7,
) -> pd.DataFrame:
    """
    Simulate Model D: t+1 Open execution.
    - Signal on session t Close (15:30 IST).
    - Session t+1 Open (09:15 IST):
      1. Portfolio earns overnight gap return on drifted holdings.
      2. Rebalance executes from drifted open holdings to target weights, paying transaction costs.
      3. Portfolio earns intraday return (Open to Close) on target holdings.
    - Non-rebalance sessions:
      Portfolio drifts continuously from close to close.
    """
    dates = schedule_df.index
    n_dates = len(dates)
    n_assets = len(ALL_ASSETS)
    w_cols = [f"w_{a}" for a in ALL_ASSETS]
    variant_name = str(schedule_df["variant"].iloc[0])

    w_post = np.zeros(n_assets, dtype=float)
    w_post[ALL_ASSETS.index("NIFTY50")] = 1.0

    nav_gross = 1.0
    nav_net = 1.0

    records: List[Dict[str, Any]] = []

    for k in range(1, n_dates):
        dt_prev = dates[k - 1]
        dt_curr = dates[k]

        # Check if rebalance was authorized on dt_prev
        row_prev = schedule_df.loc[dt_prev]
        rebal_executing = bool(row_prev["rebalance_triggered"])

        if rebal_executing:
            # 1. Overnight gap returns: Close(dt_prev) -> Open(dt_curr)
            rets_gap = np.zeros(n_assets, dtype=float)
            for idx, a in enumerate(ALL_ASSETS):
                if a == "CASH":
                    rets_gap[idx] = 0.0
                else:
                    p_close_prev = float(close_df.loc[dt_prev, a])
                    p_open_curr = float(open_df.loc[dt_curr, a])
                    rets_gap[idx] = (p_open_curr / p_close_prev) - 1.0

            w_hold = w_post.copy()
            r_gap_gross = float(np.sum(w_hold * rets_gap))
            nav_open_pre_net = nav_net * (1.0 + r_gap_gross)
            nav_open_pre_gross = nav_gross * (1.0 + r_gap_gross)

            w_drift_open = calculate_drifted_weights(w_hold, rets_gap, tol=tol)

            # 2. Rebalance at Open to target weights
            target_w = row_prev[w_cols].values.astype(float)
            target_w = np.maximum(target_w, 0.0)
            target_w = target_w / np.sum(target_w)

            to_actual = calculate_actual_turnover(target_w, w_drift_open, tol=tol)
            tc = float(nav_open_pre_net * to_actual * cost_rate)
            nav_open_post_net = nav_open_pre_net - tc
            nav_open_post_gross = nav_open_pre_gross

            # 3. Intraday returns: Open(dt_curr) -> Close(dt_curr) on target_w
            rets_day = np.zeros(n_assets, dtype=float)
            for idx, a in enumerate(ALL_ASSETS):
                if a == "CASH":
                    rets_day[idx] = 0.0
                else:
                    p_open_curr = float(open_df.loc[dt_curr, a])
                    p_close_curr = float(close_df.loc[dt_curr, a])
                    rets_day[idx] = (p_close_curr / p_open_curr) - 1.0

            r_day_gross = float(np.sum(target_w * rets_day))
            nav_close_net = nav_open_post_net * (1.0 + r_day_gross)
            nav_close_gross = nav_open_post_gross * (1.0 + r_day_gross)

            # Net and Gross session returns
            r_net = float((nav_close_net / nav_net) - 1.0)
            r_gross = float((nav_close_gross / nav_gross) - 1.0)
            c_cost = float(r_net - r_gross)
            r_overnight = r_gap_gross
            r_intraday = r_day_gross

            # Update running NAV and drifted post holdings at close
            nav_gross = nav_close_gross
            nav_net = nav_close_net
            w_post = calculate_drifted_weights(target_w, rets_day, tol=tol)

        else:
            # Stationary day: full close-to-close drift
            rets_close = np.zeros(n_assets, dtype=float)
            rets_gap = np.zeros(n_assets, dtype=float)
            for idx, a in enumerate(ALL_ASSETS):
                if a == "CASH":
                    rets_close[idx] = 0.0
                    rets_gap[idx] = 0.0
                else:
                    p_close_prev = float(close_df.loc[dt_prev, a])
                    p_close_curr = float(close_df.loc[dt_curr, a])
                    p_open_curr = float(open_df.loc[dt_curr, a])
                    rets_close[idx] = (p_close_curr / p_close_prev) - 1.0
                    rets_gap[idx] = (p_open_curr / p_close_prev) - 1.0

            w_hold = w_post.copy()
            r_gross = float(np.sum(w_hold * rets_close))
            r_overnight = float(np.sum(w_hold * rets_gap))
            r_intraday = float((1.0 + r_gross) / (1.0 + r_overnight) - 1.0) if abs(1.0 + r_overnight) > 1e-9 else 0.0

            nav_post_gross = nav_gross * (1.0 + r_gross)
            nav_post_net = nav_net * (1.0 + r_gross)

            r_net = r_gross
            tc = 0.0
            to_actual = 0.0
            c_cost = 0.0

            nav_gross = nav_post_gross
            nav_net = nav_post_net
            w_post = calculate_drifted_weights(w_hold, rets_close, tol=tol)

        rec = {
            "date": dt_curr,
            "period": str(schedule_df.loc[dt_curr, "period"]),
            "variant": variant_name,
            "rebalance_executed": rebal_executing,
            "actual_turnover": to_actual,
            "transaction_cost": tc,
            "overnight_return": r_overnight,
            "intraday_return": r_intraday,
            "gross_return": r_gross,
            "net_return": r_net,
            "gross_nav": nav_gross,
            "net_nav": nav_net,
            "contrib_cost": c_cost,
        }
        records.append(rec)

    return pd.DataFrame(records).set_index("date")


def run_execution_sensitivity_analysis(
    schedules: Dict[str, pd.DataFrame],
    close_df: pd.DataFrame,
    open_df: Optional[pd.DataFrame] = None,
    variants: Optional[List[str]] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """
    Run execution sensitivity analysis across all four strategies and four execution models.
    """
    vars_to_run = variants if variants is not None else VARIANTS
    if open_df is None:
        _, open_df = load_open_and_close_prices()

    records: List[Dict[str, Any]] = []

    for v in vars_to_run:
        sched = schedules[v]

        # Model A: t+1 Close (canonical baseline)
        daily_t1_close = simulate_portfolio(schedule_df=sched, price_df=close_df)

        # Model B: t+2 Close (operational delay)
        daily_t2_close = simulate_delayed_close_portfolio(schedule_df=sched, price_df=close_df, delay_sessions=2)

        # Model C: t Close (theoretical zero-latency bound)
        daily_t0_close = simulate_delayed_close_portfolio(schedule_df=sched, price_df=close_df, delay_sessions=0)

        # Model D: t+1 Open (earliest realistically executable proxy)
        daily_t1_open = simulate_open_execution_portfolio(schedule_df=sched, close_df=close_df, open_df=open_df)

        sim_map = {
            "t+1_close": daily_t1_close,
            "t+2_close": daily_t2_close,
            "t_close": daily_t0_close,
            "t+1_open": daily_t1_open,
        }

        # Cache baseline CAGR for timing drag calculations
        cagr_by_model: Dict[Tuple[str, str], float] = {}
        for m_name, d_df in sim_map.items():
            for p_name in ["train", "holdout", "full"]:
                m = compute_single_portfolio_metrics(daily_df=d_df, period=p_name, portfolio_key=v)
                cagr_by_model[(m_name, p_name)] = float(m["cagr_net_pct"]) / 100.0

        for m_name, d_df in sim_map.items():
            for p_name in ["train", "holdout", "full"]:
                m = compute_single_portfolio_metrics(daily_df=d_df, period=p_name, portfolio_key=v)

                cagr_m = float(m["cagr_net_pct"]) / 100.0
                cagr_t0 = cagr_by_model[("t_close", p_name)]
                cagr_t1 = cagr_by_model[("t+1_close", p_name)]

                timing_drag = cagr_t0 - cagr_m  # Drag vs zero-latency ceiling
                delay_penalty = cagr_t1 - cagr_m  # Penalty vs canonical baseline

                rec = {
                    "strategy": v,
                    "period": p_name,
                    "execution_model": m_name,
                    "sample_count": int(m["sample_count"]),
                    "net_total_return": float(m["total_return_net_pct"]) / 100.0,
                    "net_cagr": cagr_m,
                    "annualized_vol": float(m["ann_volatility_pct"]) / 100.0,
                    "sharpe_ratio": float(m["sharpe_ratio"]),
                    "sortino_ratio": float(m["sortino_ratio"]),
                    "max_drawdown": float(m["max_drawdown_pct"]) / 100.0,
                    "actual_turnover_annualized": float(m["ann_actual_turnover"]),
                    "timing_drag_vs_t0": float(timing_drag),
                    "delay_penalty_vs_t1": float(delay_penalty),
                }
                records.append(rec)

    results_df = pd.DataFrame(records)

    if output_dir is not None:
        out_path = Path(output_dir) / "execution_sensitivity.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        results_df.to_parquet(out_path, index=False)
        logger.info(f"Saved Investigation 2 Parquet to: {out_path}")

    return results_df
