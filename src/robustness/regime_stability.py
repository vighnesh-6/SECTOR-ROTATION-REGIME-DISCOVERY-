"""
Phase 10.6 Investigation 5 — Regime Stability Analysis.

Evaluates strategy return distributions and stability conditional on each discovered HMM regime:
  - Regime-conditional annualized return, volatility, Sharpe ratio, and win rate.
  - Cumulative return contribution per regime (arithmetic accounting).
  - Rebalance transition dynamics: performance and friction on transition sessions vs stationary holding sessions.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.portfolio_backtest import ANNUALIZATION_FACTOR, VARIANTS
from src.regime_rotation_rules import REGIME_ECONOMIC_NAMES

logger = logging.getLogger(__name__)

PERIOD_RANGES: Dict[str, Tuple[str, str]] = {
    "train": ("2019-11-01", "2024-12-31"),
    "holdout": ("2025-01-02", "2026-09-18"),
    "full": ("2019-11-01", "2026-09-18"),
}


def run_regime_stability_analysis(
    simulations: Dict[str, pd.DataFrame],
    variants: Optional[List[str]] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute regime-conditional performance and rebalancing transition dynamics across strategies and periods.

    Returns:
      Tuple of (regime_conditional_df, transition_dynamics_df).
    """
    vars_to_run = variants if variants is not None else VARIANTS

    regime_records: List[Dict[str, Any]] = []
    transition_records: List[Dict[str, Any]] = []

    for v in vars_to_run:
        daily_df = simulations[v]

        for period_name in ["train", "holdout", "full"]:
            s_dt, e_dt = PERIOD_RANGES[period_name]
            sub_daily = daily_df.loc[s_dt:e_dt]
            tot_sessions = len(sub_daily)

            # 1. State-Conditional Metrics for Regimes 0 through 5
            for k in range(6):
                regime_mask = (sub_daily["accepted_regime"] == k)
                k_df = sub_daily[regime_mask]
                n_k = len(k_df)

                if n_k > 0:
                    r_k = k_df["net_return"].values
                    cum_contrib = float(np.sum(r_k))
                    mean_ann = float(np.mean(r_k) * ANNUALIZATION_FACTOR)
                    vol_ann = float(np.std(r_k, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR)) if n_k > 1 else 0.0
                    sharpe = float(mean_ann / vol_ann) if vol_ann > 1e-9 else 0.0
                    win_rate = float(np.mean(r_k > 0.0))
                    rebal_count = int(k_df["rebalance_executed"].sum())
                    pct_time = float(n_k / tot_sessions)
                else:
                    cum_contrib = 0.0
                    mean_ann = 0.0
                    vol_ann = 0.0
                    sharpe = 0.0
                    win_rate = 0.0
                    rebal_count = 0
                    pct_time = 0.0

                regime_records.append({
                    "strategy": v,
                    "period": period_name,
                    "regime_id": int(k),
                    "regime_name": REGIME_ECONOMIC_NAMES.get(k, f"Regime {k}"),
                    "sample_count": int(n_k),
                    "pct_time_in_regime": pct_time,
                    "annualized_net_return": mean_ann,
                    "annualized_volatility": vol_ann,
                    "regime_sharpe_ratio": sharpe,
                    "win_rate": win_rate,
                    "cumulative_return_contribution": cum_contrib,
                    "rebalances_in_regime": rebal_count,
                })

            # 2. Transition Dynamics: Rebalance Execution Sessions vs Stationary Holding Sessions
            rebal_mask = sub_daily["rebalance_executed"]
            hold_mask = ~rebal_mask

            r_rebal = sub_daily.loc[rebal_mask, "net_return"].values
            r_hold = sub_daily.loc[hold_mask, "net_return"].values

            n_rebal = len(r_rebal)
            n_hold = len(r_hold)

            mean_rebal_ann = float(np.mean(r_rebal) * ANNUALIZATION_FACTOR) if n_rebal > 0 else 0.0
            mean_hold_ann = float(np.mean(r_hold) * ANNUALIZATION_FACTOR) if n_hold > 0 else 0.0
            cost_paid_rebal = float(sub_daily.loc[rebal_mask, "transaction_cost"].sum())
            to_rebal_sum = float(sub_daily.loc[rebal_mask, "actual_turnover"].sum())

            transition_records.append({
                "strategy": v,
                "period": period_name,
                "rebalance_sessions_count": int(n_rebal),
                "stationary_sessions_count": int(n_hold),
                "rebalance_session_ann_return": mean_rebal_ann,
                "stationary_session_ann_return": mean_hold_ann,
                "transition_slippage_drag_ann": float(mean_rebal_ann - mean_hold_ann),
                "total_cash_costs_paid": cost_paid_rebal,
                "total_actual_turnover": to_rebal_sum,
                "avg_turnover_per_rebalance": float(to_rebal_sum / n_rebal) if n_rebal > 0 else 0.0,
            })

    regime_df = pd.DataFrame(regime_records)
    transition_df = pd.DataFrame(transition_records)

    if output_dir is not None:
        out_path1 = Path(output_dir) / "regime_stability.parquet"
        out_path2 = Path(output_dir) / "regime_transition_dynamics.parquet"
        out_path1.parent.mkdir(parents=True, exist_ok=True)
        regime_df.to_parquet(out_path1, index=False)
        transition_df.to_parquet(out_path2, index=False)
        logger.info(f"Saved Investigation 5 Parquets to: {out_path1} and {out_path2}")

    return regime_df, transition_df

