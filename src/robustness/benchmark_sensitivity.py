"""
Phase 10.6 Investigation 7 — Benchmark Sensitivity & Naive Momentum Comparator.

Evaluates directional asymmetry and market exposure against passive and active benchmarks:
  1. Primary Benchmark (NIFTY 50):
     - Linear Beta, Up-Market Beta, Down-Market Beta (Dual-Beta model).
     - Up-Market and Down-Market Capture Ratios.
     - Treynor-Mazuy quadratic market-timing curvature (gamma, stderr, p-value).
  2. Supplementary Active Factor Comparator (Naive Top-2 Momentum):
     - Monthly rebalanced Top-2 sectors by trailing 20-day simple return.
     - Strictly 50/50 equal-weighted, 15 bps fee, t+1 Close execution, zero HMM inputs.
     - Comparative performance vs ML strategies.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import scipy.stats as stats

from src.benchmark_backtest import get_month_end_signal_dates
from src.comparative_evaluation import compute_regression_alpha_beta, compute_single_portfolio_metrics
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

logger = logging.getLogger(__name__)

PERIOD_RANGES: Dict[str, Tuple[str, str]] = {
    "train": ("2019-11-01", "2024-12-31"),
    "holdout": ("2025-01-02", "2026-09-18"),
    "full": ("2019-11-01", "2026-09-18"),
}


def fit_treynor_mazuy_regression(
    r_strategy: np.ndarray,
    r_benchmark: np.ndarray,
) -> Tuple[float, float, float, float, float]:
    """
    Fit Treynor-Mazuy quadratic timing model:
      r_strat = alpha + beta_1 * r_mkt + gamma * (r_mkt^2) + epsilon

    Returns:
      Tuple of (alpha_daily, beta1, gamma, gamma_stderr, gamma_pvalue).
    """
    y = np.asarray(r_strategy, dtype=float)
    x = np.asarray(r_benchmark, dtype=float)
    N = len(y)

    if N < 4:
        return 0.0, 0.0, 0.0, 0.0, 1.0

    X = np.column_stack([np.ones(N), x, x ** 2])
    XtX = X.T @ X

    # Invert XtX safely
    try:
        inv_XtX = np.linalg.inv(XtX)
        beta_vec = inv_XtX @ (X.T @ y)
        residuals = y - (X @ beta_vec)
        dof = N - 3
        s2 = float(residuals @ residuals) / dof
        cov_beta = s2 * inv_XtX

        alpha_daily = float(beta_vec[0])
        beta1 = float(beta_vec[1])
        gamma = float(beta_vec[2])

        gamma_se = float(np.sqrt(np.maximum(cov_beta[2, 2], 0.0)))
        t_stat = gamma / gamma_se if gamma_se > 1e-12 else 0.0
        gamma_pval = float(2.0 * (1.0 - stats.t.cdf(np.abs(t_stat), df=dof)))
    except np.linalg.LinAlgError:
        alpha_daily = float(np.mean(y))
        beta1 = 0.0
        gamma = 0.0
        gamma_se = 0.0
        gamma_pval = 1.0

    return alpha_daily, beta1, gamma, gamma_se, gamma_pval


def compute_dual_beta_metrics(
    r_strategy: np.ndarray,
    r_benchmark: np.ndarray,
) -> Dict[str, float]:
    """
    Compute Linear Beta, Up-Market Beta, Down-Market Beta, and Capture Ratios.
    """
    y = np.asarray(r_strategy, dtype=float)
    x = np.asarray(r_benchmark, dtype=float)
    N = len(y)

    # 1. Overall Linear Beta
    res_lin = compute_regression_alpha_beta(y, x)
    beta_lin = res_lin["beta"]

    # 2. Up-Market Beta & Capture (r_mkt > 0)
    up_mask = x > 0.0
    if np.sum(up_mask) >= 3:
        y_up = y[up_mask]
        x_up = x[up_mask]
        res_up = stats.linregress(x_up, y_up)
        beta_up = float(res_up.slope)
        mean_y_up = float(np.mean(y_up))
        mean_x_up = float(np.mean(x_up))
        capture_up = float(mean_y_up / mean_x_up) if abs(mean_x_up) > 1e-9 else 0.0
    else:
        beta_up = beta_lin
        capture_up = 1.0

    # 3. Down-Market Beta & Capture (r_mkt < 0)
    down_mask = x < 0.0
    if np.sum(down_mask) >= 3:
        y_down = y[down_mask]
        x_down = x[down_mask]
        res_down = stats.linregress(x_down, y_down)
        beta_down = float(res_down.slope)
        mean_y_down = float(np.mean(y_down))
        mean_x_down = float(np.mean(x_down))
        capture_down = float(mean_y_down / mean_x_down) if abs(mean_x_down) > 1e-9 else 0.0
    else:
        beta_down = beta_lin
        capture_down = 1.0

    capture_ratio = float(capture_up / capture_down) if abs(capture_down) > 1e-9 else 0.0
    delta_beta = float(beta_up - beta_down)

    # 4. Treynor-Mazuy Timing
    _, _, gamma, gamma_se, gamma_pval = fit_treynor_mazuy_regression(y, x)

    return {
        "linear_beta": beta_lin,
        "beta_up": beta_up,
        "beta_down": beta_down,
        "delta_beta": delta_beta,
        "capture_up": capture_up,
        "capture_down": capture_down,
        "capture_ratio": capture_ratio,
        "treynor_mazuy_gamma": gamma,
        "gamma_stderr": gamma_se,
        "gamma_pvalue": gamma_pval,
    }


def construct_naive_momentum_schedule(
    price_df: pd.DataFrame,
    start_date: str = "2019-10-31",
    end_date: str = "2026-09-18",
    lookback: int = 20,
) -> pd.DataFrame:
    """
    Construct target-weight schedule for the Naive Top-2 Cross-Sectional Momentum Benchmark:
      - Trailing 20-trading-day simple price return across the 6 sectors.
      - Monthly calendar rebalance at month-end signal close.
      - Top 2 sectors allocated 50% each (equal-weighted). Zero cash toggle.
      - Rebalance executes at t+1 Close.
    """
    sub_prices = price_df.loc[start_date:end_date]
    dates = sub_prices.index
    month_end_signals = get_month_end_signal_dates(dates)

    n_assets = len(ALL_ASSETS)
    records: List[Dict[str, Any]] = []

    incumbent_top2: Tuple[str, str] = ("AUTO", "BANK")  # Arbitrary initial before first rebalance
    first_rebal_executed = False

    for dt in dates:
        # Check if dt is a month-end signal date
        is_signal_date = (dt in month_end_signals) or (not first_rebal_executed and dt == dates[0])

        if is_signal_date:
            # Trailing 20-day returns up to dt
            hist_dates = price_df.index[price_df.index <= dt]
            if len(hist_dates) >= lookback + 1:
                p_curr = price_df.loc[dt, SECTOR_NAMES]
                p_past = price_df.loc[hist_dates[-(lookback + 1)], SECTOR_NAMES]
                rets_20d = (p_curr / p_past) - 1.0
                sorted_sectors = rets_20d.sort_values(ascending=False).index.tolist()
                top2 = (sorted_sectors[0], sorted_sectors[1])
            else:
                top2 = ("AUTO", "BANK")

            rebal_triggered = True
            first_rebal_executed = True
            incumbent_top2 = top2
        else:
            rebal_triggered = False

        # Target weights: 50/50 between top2, zero cash, zero nifty
        rec: Dict[str, Any] = {
            "Date": dt,
            "period": "train" if dt <= pd.Timestamp("2024-12-31") else "holdout",
            "variant": "MOMENTUM_TOP2",
            "rebalance_triggered": rebal_triggered,
            "rebalance_bypassed_r3": False,
            "turnover": 1.0 if rebal_triggered else 0.0,
            "top1_sector": incumbent_top2[0],
            "top2_sector": incumbent_top2[1],
            "raw_regime_argmax": 0,
            "max_probability": 1.0,
            "is_confident": True,
            "accepted_regime": 0,
        }

        for a in ALL_ASSETS:
            if a in incumbent_top2:
                rec[f"w_{a}"] = 0.50
            else:
                rec[f"w_{a}"] = 0.00

        records.append(rec)

    sched_df = pd.DataFrame(records).set_index("Date")
    return sched_df


def run_benchmark_sensitivity_analysis(
    simulations: Dict[str, pd.DataFrame],
    nifty50_simulation: pd.DataFrame,
    price_df: pd.DataFrame,
    variants: Optional[List[str]] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run benchmark sensitivity analysis across strategies:
      1. Dual-Beta and Treynor-Mazuy analysis vs. NIFTY 50.
      2. Simulation and comparative evaluation against Naive Top-2 Momentum Benchmark.

    Returns:
      Tuple of (benchmark_sensitivity_df, momentum_comparison_df).
    """
    vars_to_run = variants if variants is not None else VARIANTS

    # 1. Dual-Beta and Treynor-Mazuy Analysis vs NIFTY 50
    records_dual: List[Dict[str, Any]] = []
    for v in vars_to_run:
        daily_v = simulations[v]
        daily_bm = nifty50_simulation

        for period_name in ["train", "holdout", "full"]:
            s_dt, e_dt = PERIOD_RANGES[period_name]
            y = daily_v.loc[s_dt:e_dt, "net_return"].values
            x = daily_bm.loc[s_dt:e_dt, "net_return"].values

            dual_m = compute_dual_beta_metrics(y, x)
            rec = {
                "strategy": v,
                "benchmark": "NIFTY50",
                "period": period_name,
                "sample_count": len(y),
                **dual_m,
            }
            records_dual.append(rec)

    dual_df = pd.DataFrame(records_dual)

    # 2. Naive Top-2 Momentum Benchmark Simulation
    logger.info("Simulating Naive Top-2 Momentum Comparator...")
    sched_mom = construct_naive_momentum_schedule(price_df)
    daily_mom = simulate_portfolio(
        schedule_df=sched_mom,
        price_df=price_df,
        cost_rate=DEFAULT_TRANSACTION_COST_RATE,
    )

    records_mom: List[Dict[str, Any]] = []

    # Compute Momentum baseline performance across periods
    for period_name in ["train", "holdout", "full"]:
        mom_m = compute_single_portfolio_metrics(
            daily_df=daily_mom,
            period=period_name,
            portfolio_key="MOMENTUM_TOP2",
            portfolio_name="Naive Top-2 Momentum",
        )
        records_mom.append({
            "portfolio": "Naive Top-2 Momentum Benchmark",
            "comparator_type": "benchmark_baseline",
            "period": period_name,
            "sample_count": int(mom_m["sample_count"]),
            "net_total_return": float(mom_m["total_return_net_pct"]) / 100.0,
            "net_cagr": float(mom_m["cagr_net_pct"]) / 100.0,
            "annualized_vol": float(mom_m["ann_volatility_pct"]) / 100.0,
            "sharpe_ratio": float(mom_m["sharpe_ratio"]),
            "max_drawdown": float(mom_m["max_drawdown_pct"]) / 100.0,
            "annualized_turnover": float(mom_m["ann_actual_turnover"]),
            "cash_costs_paid": float(mom_m["cum_transaction_costs"]),
            "alpha_vs_momentum": 0.0,
            "beta_vs_momentum": 1.0,
        })

    # Compare each ML strategy against Naive Momentum
    for v in vars_to_run:
        daily_v = simulations[v]
        for period_name in ["train", "holdout", "full"]:
            s_dt, e_dt = PERIOD_RANGES[period_name]
            y = daily_v.loc[s_dt:e_dt, "net_return"].values
            x = daily_mom.loc[s_dt:e_dt, "net_return"].values

            reg = compute_regression_alpha_beta(y, x)
            strat_m = compute_single_portfolio_metrics(
                daily_df=daily_v,
                period=period_name,
                portfolio_key=v,
            )

            records_mom.append({
                "portfolio": v,
                "comparator_type": "ml_strategy_vs_momentum",
                "period": period_name,
                "sample_count": len(y),
                "net_total_return": float(strat_m["total_return_net_pct"]) / 100.0,
                "net_cagr": float(strat_m["cagr_net_pct"]) / 100.0,
                "annualized_vol": float(strat_m["ann_volatility_pct"]) / 100.0,
                "sharpe_ratio": float(strat_m["sharpe_ratio"]),
                "max_drawdown": float(strat_m["max_drawdown_pct"]) / 100.0,
                "annualized_turnover": float(strat_m["ann_actual_turnover"]),
                "cash_costs_paid": float(strat_m["cum_transaction_costs"]),
                "alpha_vs_momentum": float(reg["alpha_annualized"]),
                "beta_vs_momentum": float(reg["beta"]),
            })

    mom_df = pd.DataFrame(records_mom)

    if output_dir is not None:
        out_p1 = Path(output_dir) / "benchmark_sensitivity.parquet"
        out_p2 = Path(output_dir) / "momentum_benchmark_comparison.parquet"
        out_p1.parent.mkdir(parents=True, exist_ok=True)
        dual_df.to_parquet(out_p1, index=False)
        mom_df.to_parquet(out_p2, index=False)
        logger.info(f"Saved Investigation 7 Parquets to: {out_p1} and {out_p2}")

    return dual_df, mom_df
