"""
Phase 10.6 Investigation 3 — Portfolio Concentration & Risk/Return Attribution.

Evaluates sectoral exposure concentration and mathematically decomposes total portfolio risk
and return:
  - Total Portfolio HHI & Effective N (cash inclusive)
  - Equity-Only Sector HHI & Effective N (normalized over equity allocation)
  - Additive sector return contributions (linear accounting)
  - Euler component-volatility risk contributions (MCR & absolute risk contribution)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.portfolio_backtest import (
    ALL_ASSETS,
    ANNUALIZATION_FACTOR,
    SECTOR_NAMES,
    VARIANTS,
)

logger = logging.getLogger(__name__)

PERIOD_RANGES: Dict[str, Tuple[str, str]] = {
    "train": ("2019-11-01", "2024-12-31"),
    "holdout": ("2025-01-02", "2026-09-18"),
    "full": ("2019-11-01", "2026-09-18"),
}


def compute_dual_hhi_metrics(
    daily_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute daily Total HHI (including cash) and Equity-Only HHI (rescaled over equity).
    """
    dates = daily_df.index
    records: List[Dict[str, Any]] = []

    for dt in dates:
        row = daily_df.loc[dt]
        w_sectors = np.array([float(row[f"w_hold_{s}"]) for s in SECTOR_NAMES])
        w_cash = float(row.get("w_hold_CASH", 0.0))
        w_nifty = float(row.get("w_hold_NIFTY50", 0.0))

        # Total portfolio HHI (cash, nifty, and sectors)
        all_w = np.append(w_sectors, [w_cash, w_nifty])
        hhi_total = float(np.sum(all_w ** 2))
        n_eff_total = float(1.0 / hhi_total) if hhi_total > 0 else 0.0

        # Equity-only sector HHI
        equity_sum = float(np.sum(w_sectors) + w_nifty)
        if equity_sum > 1e-6:
            w_equity_scaled = np.append(w_sectors, w_nifty) / equity_sum
            hhi_equity = float(np.sum(w_equity_scaled ** 2))
            n_eff_equity = float(1.0 / hhi_equity) if hhi_equity > 0 else 0.0
        else:
            hhi_equity = 0.0
            n_eff_equity = 0.0

        records.append({
            "date": dt,
            "hhi_total": hhi_total,
            "n_eff_total": n_eff_total,
            "hhi_equity": hhi_equity,
            "n_eff_equity": n_eff_equity,
            "w_cash": w_cash,
            "max_sector_weight": float(np.max(w_sectors)),
        })

    return pd.DataFrame(records).set_index("date")


def compute_euler_risk_attribution(
    daily_df: pd.DataFrame,
    ddof: int = 1,
) -> Dict[str, Dict[str, float]]:
    """
    Compute Euler component volatility risk contributions across portfolio assets over the provided window.
    Guarantees sum(Component_Volatility_i) == Portfolio_Volatility.

    Returns:
      Dict mapping asset name -> dict with keys:
        'weight_mean', 'component_vol', 'pct_risk_contrib', 'return_contrib_sum'
    """
    assets = [a for a in ALL_ASSETS if f"w_hold_{a}" in daily_df.columns and f"r_{a}" in daily_df.columns]

    # Asset returns matrix: N x K
    ret_matrix = daily_df[[f"r_{a}" for a in assets]].values
    cov_matrix = np.cov(ret_matrix, rowvar=False, ddof=ddof) * ANNUALIZATION_FACTOR

    # Average holding weights across the window
    weights_mean = daily_df[[f"w_hold_{a}" for a in assets]].mean().values

    # Portfolio variance and annualized volatility
    port_var = float(weights_mean @ cov_matrix @ weights_mean)
    port_vol = float(np.sqrt(np.maximum(port_var, 0.0)))

    results: Dict[str, Dict[str, float]] = {}

    if port_vol > 1e-9:
        # Marginal contribution to risk (MCR): Cov @ w / sigma_p
        mcr = (cov_matrix @ weights_mean) / port_vol
        # Absolute risk contribution (Component Volatility): w_i * MCR_i
        rc = weights_mean * mcr
        pct_rc = rc / port_vol
    else:
        mcr = np.zeros(len(assets))
        rc = np.zeros(len(assets))
        pct_rc = np.zeros(len(assets))

    for idx, a in enumerate(assets):
        contrib_sum = float(daily_df[f"contrib_{a}"].sum()) if f"contrib_{a}" in daily_df.columns else 0.0
        results[a] = {
            "weight_mean": float(weights_mean[idx]),
            "component_vol": float(rc[idx]),
            "pct_risk_contrib": float(pct_rc[idx]),
            "return_contrib_sum": contrib_sum,
        }

    return results


def run_concentration_analysis(
    simulations: Dict[str, pd.DataFrame],
    variants: Optional[List[str]] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run comprehensive concentration and risk-return attribution analysis across strategies and periods.

    Returns:
      Tuple of (concentration_summary_df, sector_attribution_df).
    """
    vars_to_run = variants if variants is not None else VARIANTS

    summary_records: List[Dict[str, Any]] = []
    attribution_records: List[Dict[str, Any]] = []

    for v in vars_to_run:
        daily_df = simulations[v]
        daily_hhi = compute_dual_hhi_metrics(daily_df)

        for period_name in ["train", "holdout", "full"]:
            s_dt, e_dt = PERIOD_RANGES[period_name]
            sub_daily = daily_df.loc[s_dt:e_dt]
            sub_hhi = daily_hhi.loc[s_dt:e_dt]

            # 1. Concentration metrics
            rec_sum = {
                "strategy": v,
                "period": period_name,
                "sample_count": len(sub_daily),
                "hhi_total_mean": float(sub_hhi["hhi_total"].mean()),
                "hhi_total_min": float(sub_hhi["hhi_total"].min()),
                "hhi_total_max": float(sub_hhi["hhi_total"].max()),
                "n_eff_total_mean": float(sub_hhi["n_eff_total"].mean()),
                "n_eff_total_min": float(sub_hhi["n_eff_total"].min()),
                "n_eff_total_max": float(sub_hhi["n_eff_total"].max()),
                "hhi_equity_mean": float(sub_hhi["hhi_equity"].mean()),
                "n_eff_equity_mean": float(sub_hhi["n_eff_equity"].mean()),
                "max_sector_weight_observed": float(sub_hhi["max_sector_weight"].max()),
                "cash_weight_mean": float(sub_hhi["w_cash"].mean()),
            }
            summary_records.append(rec_sum)

            # 2. Euler risk and return attribution
            risk_attr = compute_euler_risk_attribution(sub_daily)
            for asset_name, attr_dict in risk_attr.items():
                rec_attr = {
                    "strategy": v,
                    "period": period_name,
                    "asset": asset_name,
                    "average_weight": attr_dict["weight_mean"],
                    "component_volatility": attr_dict["component_vol"],
                    "pct_risk_contribution": attr_dict["pct_risk_contrib"],
                    "cumulative_return_contribution": attr_dict["return_contrib_sum"],
                }
                attribution_records.append(rec_attr)

    summary_df = pd.DataFrame(summary_records)
    attribution_df = pd.DataFrame(attribution_records)

    if output_dir is not None:
        out_p1 = Path(output_dir) / "concentration_metrics.parquet"
        out_p2 = Path(output_dir) / "sector_risk_return_attribution.parquet"
        out_p1.parent.mkdir(parents=True, exist_ok=True)
        summary_df.to_parquet(out_p1, index=False)
        attribution_df.to_parquet(out_p2, index=False)
        logger.info(f"Saved Investigation 3 Parquets to: {out_p1} and {out_p2}")

    return summary_df, attribution_df

