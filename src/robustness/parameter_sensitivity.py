"""
Phase 10.6 Investigation 6 — Parameter & Model Sensitivity Analysis.

Diagnostic evaluation of strategy sensitivity to operational threshold variations:
  - Strategy 1A Primary Grid: 42 parameter cells (7 confidence thresholds x 6 holding lockup periods).
  - Strategies 1B, 2A, 2B Boundary Matrices: 9 parameter cells each (True extrema: P in {0.40, 0.50, 0.70} x T in {1, 5, 20}).
  - Volatility Lookback Sensitivity Slice: L_vol in {10, 20, 40} days for applicable inverse-volatility variants (1B, 2B).

STRICT RULE: This evaluation is strictly diagnostic to map the stability surface.
No parameter combination will be retroactively selected or tuned against holdout performance.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.comparative_evaluation import compute_single_portfolio_metrics
from src.portfolio_backtest import VARIANTS, simulate_portfolio
from src.portfolio_construction import generate_portfolio_schedule
from src.regime_rotation_rules import StrategyVariant

logger = logging.getLogger(__name__)

# Primary 42-cell grid parameters for Strategy 1A
PRIMARY_P_THRESH_GRID: List[float] = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
PRIMARY_T_LOCK_GRID: List[int] = [1, 3, 5, 10, 15, 20]

# Extreme boundary matrix for Variants 1B, 2A, 2B
BOUNDARY_P_THRESH: List[float] = [0.40, 0.50, 0.70]
BOUNDARY_T_LOCK: List[int] = [1, 5, 20]

# Volatility lookback slice for 1B and 2B
VOL_LOOKBACK_GRID: List[int] = [10, 20, 40]

PERIOD_RANGES: Dict[str, Tuple[str, str]] = {
    "train": ("2019-11-01", "2024-12-31"),
    "holdout": ("2025-01-02", "2026-09-18"),
    "full": ("2019-11-01", "2026-09-18"),
}


def run_single_parameter_scenario(
    variant: str,
    prob_df: pd.DataFrame,
    price_df: pd.DataFrame,
    p_thresh: float,
    t_lock: int,
    vol_lookback: int = 20,
    cost_rate: float = 0.0015,
) -> Dict[str, Dict[str, Any]]:
    """
    Generate schedule and simulate portfolio for a specific parameter combination.
    Returns metrics dictionary keyed by period ('train', 'holdout', 'full').
    """
    engine_kwargs: Dict[str, Any] = {
        "confidence_threshold": p_thresh,
        "min_holding_days": t_lock,
    }
    if variant in ["1B", "2B"]:
        engine_kwargs["volatility_lookback"] = vol_lookback

    sched = generate_portfolio_schedule(
        variant=variant,
        prob_df=prob_df,
        price_df=price_df,
        engine_kwargs=engine_kwargs,
    )

    daily_df = simulate_portfolio(
        schedule_df=sched,
        price_df=price_df,
        cost_rate=cost_rate,
    )

    period_metrics: Dict[str, Dict[str, Any]] = {}
    for p_name in ["train", "holdout", "full"]:
        m = compute_single_portfolio_metrics(
            daily_df=daily_df,
            period=p_name,
            portfolio_key=variant,
        )
        period_metrics[p_name] = m

    return period_metrics


def run_parameter_sensitivity_analysis(
    prob_df: pd.DataFrame,
    price_df: pd.DataFrame,
    variants: Optional[List[str]] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """
    Execute full diagnostic parameter sensitivity suite:
      1. Strategy 1A: 42 cells (P_thresh x T_lock)
      2. Strategies 1B, 2A, 2B: 9 cells each (True extreme boundaries)
      3. Strategies 1B, 2B: Volatility lookback slice (L_vol in {10, 20, 40})
    """
    records: List[Dict[str, Any]] = []

    # 1. Strategy 1A Primary Grid (42 parameter cells)
    logger.info("Executing Strategy 1A primary 42-cell parameter grid...")
    for p_val in PRIMARY_P_THRESH_GRID:
        for t_val in PRIMARY_T_LOCK_GRID:
            p_metrics = run_single_parameter_scenario(
                variant="1A",
                prob_df=prob_df,
                price_df=price_df,
                p_thresh=p_val,
                t_lock=t_val,
            )
            for p_name, m in p_metrics.items():
                records.append({
                    "strategy": "1A",
                    "evaluation_type": "primary_grid_42",
                    "period": p_name,
                    "confidence_threshold": float(p_val),
                    "min_holding_days": int(t_val),
                    "volatility_lookback": 20,
                    "sample_count": int(m["sample_count"]),
                    "net_total_return": float(m["total_return_net_pct"]) / 100.0,
                    "net_cagr": float(m["cagr_net_pct"]) / 100.0,
                    "annualized_vol": float(m["ann_volatility_pct"]) / 100.0,
                    "sharpe_ratio": float(m["sharpe_ratio"]),
                    "sortino_ratio": float(m["sortino_ratio"]),
                    "max_drawdown": float(m["max_drawdown_pct"]) / 100.0,
                    "rebalances_count": int(m["rebalances_executed"]),
                    "actual_turnover_annualized": float(m["ann_actual_turnover"]),
                    "cash_costs_paid": float(m["cum_transaction_costs"]),
                })

    # 2. Boundary Matrices for 1B, 2A, 2B (9 parameter cells each)
    other_variants = ["1B", "2A", "2B"]
    for v in other_variants:
        logger.info(f"Executing {v} 9-cell boundary cross-check matrix...")
        for p_val in BOUNDARY_P_THRESH:
            for t_val in BOUNDARY_T_LOCK:
                p_metrics = run_single_parameter_scenario(
                    variant=v,
                    prob_df=prob_df,
                    price_df=price_df,
                    p_thresh=p_val,
                    t_lock=t_val,
                )
                for p_name, m in p_metrics.items():
                    records.append({
                        "strategy": v,
                        "evaluation_type": "boundary_matrix_9",
                        "period": p_name,
                        "confidence_threshold": float(p_val),
                        "min_holding_days": int(t_val),
                        "volatility_lookback": 20,
                        "sample_count": int(m["sample_count"]),
                        "net_total_return": float(m["total_return_net_pct"]) / 100.0,
                        "net_cagr": float(m["cagr_net_pct"]) / 100.0,
                        "annualized_vol": float(m["ann_volatility_pct"]) / 100.0,
                        "sharpe_ratio": float(m["sharpe_ratio"]),
                        "sortino_ratio": float(m["sortino_ratio"]),
                        "max_drawdown": float(m["max_drawdown_pct"]) / 100.0,
                        "rebalances_count": int(m["rebalances_executed"]),
                        "actual_turnover_annualized": float(m["ann_actual_turnover"]),
                        "cash_costs_paid": float(m["cum_transaction_costs"]),
                    })

    # 3. Volatility Lookback Slice for 1B and 2B (L in {10, 40}; L=20 already in baseline)
    for v in ["1B", "2B"]:
        for l_val in [10, 40]:  # 20 is already computed at baseline
            logger.info(f"Executing {v} volatility lookback slice L={l_val}...")
            p_metrics = run_single_parameter_scenario(
                variant=v,
                prob_df=prob_df,
                price_df=price_df,
                p_thresh=0.50,
                t_lock=5,
                vol_lookback=l_val,
            )
            for p_name, m in p_metrics.items():
                records.append({
                    "strategy": v,
                    "evaluation_type": "volatility_lookback_slice",
                    "period": p_name,
                    "confidence_threshold": 0.50,
                    "min_holding_days": 5,
                    "volatility_lookback": int(l_val),
                    "sample_count": int(m["sample_count"]),
                    "net_total_return": float(m["total_return_net_pct"]) / 100.0,
                    "net_cagr": float(m["cagr_net_pct"]) / 100.0,
                    "annualized_vol": float(m["ann_volatility_pct"]) / 100.0,
                    "sharpe_ratio": float(m["sharpe_ratio"]),
                    "sortino_ratio": float(m["sortino_ratio"]),
                    "max_drawdown": float(m["max_drawdown_pct"]) / 100.0,
                    "rebalances_count": int(m["rebalances_executed"]),
                    "actual_turnover_annualized": float(m["ann_actual_turnover"]),
                    "cash_costs_paid": float(m["cum_transaction_costs"]),
                })

    results_df = pd.DataFrame(records)

    if output_dir is not None:
        out_path = Path(output_dir) / "parameter_sensitivity.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        results_df.to_parquet(out_path, index=False)
        logger.info(f"Saved Investigation 6 Parquet to: {out_path}")

    return results_df
