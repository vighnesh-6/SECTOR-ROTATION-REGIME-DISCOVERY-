"""
Phase 10.6 Investigation 4 — Subperiod Stability Analysis.

Evaluates performance consistency and downside resilience across objective, exogenous partitions:
  1. Calendar Years: Reconciled empirical session counts (2019 N=41 through 2026 N=175; total N=1,686).
  2. Causal Trend Regimes: NIFTY 50 200-day SMA with 200 warm-up sessions (zero dropped evaluation dates).
  3. Volatility Environments: Fixed training-period India VIX thresholds (<13, 13–18, >=18).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.comparative_evaluation import compute_drawdown_metrics
from src.portfolio_backtest import ANNUALIZATION_FACTOR, VARIANTS

logger = logging.getLogger(__name__)

# Expected calendar counts
EXPECTED_YEAR_COUNTS: Dict[int, int] = {
    2019: 41,
    2020: 249,
    2021: 238,
    2022: 247,
    2023: 245,
    2024: 244,
    2025: 247,
    2026: 175,
}

VIX_THRESHOLDS: Tuple[float, float] = (13.0, 18.0)


def load_environmental_indicators(
    price_dir: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """
    Load aligned NIFTY 50 and India VIX price series, and construct causal SMA 200 and VIX regimes.
    Uses the 200 historical warm-up sessions (2019-01-02 to 2019-10-31) so that SMA 200 is valid
    from Day 1 of the evaluation timeline (2019-11-01) with zero dropped dates.
    """
    p_dir = Path(price_dir) if price_dir is not None else Path("data/processed/aligned")

    p50_path = p_dir / "nifty50_aligned.csv"
    vix_path = p_dir / "india_vix_aligned.csv"

    p50_df = pd.read_csv(p50_path, index_col=0, parse_dates=True)
    vix_df = pd.read_csv(vix_path, index_col=0, parse_dates=True)

    df = pd.DataFrame(index=p50_df.index)
    df["nifty50_close"] = p50_df["Close"]
    df["india_vix"] = vix_df["Close"]

    # Causal 200-day rolling simple moving average
    df["nifty50_sma200"] = df["nifty50_close"].rolling(window=200).mean()

    # Causal trend label: Bull if Close > SMA200 else Bear
    df["trend_label"] = np.where(df["nifty50_close"] > df["nifty50_sma200"], "Bull (Close > SMA200)", "Bear (Close <= SMA200)")

    # Fixed training VIX regime
    vix_low, vix_high = VIX_THRESHOLDS
    conditions = [
        df["india_vix"] < vix_low,
        (df["india_vix"] >= vix_low) & (df["india_vix"] < vix_high),
        df["india_vix"] >= vix_high,
    ]
    choices = ["Low Vol (< 13.0)", "Normal Vol (13.0 - 18.0)", "High Vol (>= 18.0)"]
    df["vix_regime"] = np.select(conditions, choices, default="Normal Vol (13.0 - 18.0)")

    return df


def compute_slice_metrics(
    daily_returns: pd.Series,
    nifty_returns: pd.Series,
    slice_label: str,
    partition_type: str,
    strategy_name: str,
) -> Dict[str, Any]:
    """
    Compute annualized performance and risk metrics over an isolated partition slice.
    """
    n = len(daily_returns)
    if n == 0:
        return {}

    r = daily_returns.values
    r_bm = nifty_returns.values

    # Net total return & CAGR (annualized using 252/N)
    cum_nav = np.cumprod(1.0 + r)
    tot_ret = float(cum_nav[-1] - 1.0)
    ann_ret = float((1.0 + tot_ret) ** (ANNUALIZATION_FACTOR / n) - 1.0) if tot_ret > -1.0 else -1.0

    # Annualized volatility (ddof=1)
    vol = float(np.std(r, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR)) if n > 1 else 0.0

    # Sharpe ratio (RF = 0.0)
    mean_ann = float(np.mean(r) * ANNUALIZATION_FACTOR)
    sharpe = float(mean_ann / vol) if vol > 1e-9 else 0.0

    # Sortino ratio (MAR = 0.0)
    downside_dev = float(np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(ANNUALIZATION_FACTOR))
    sortino = float(mean_ann / downside_dev) if downside_dev > 1e-9 else 0.0

    # Drawdown rebased to 1.0 at start of partition
    mdd, _, _, _ = compute_drawdown_metrics(cum_nav)

    # Benchmark metrics
    cum_bm = np.cumprod(1.0 + r_bm)
    tot_ret_bm = float(cum_bm[-1] - 1.0)
    ann_ret_bm = float((1.0 + tot_ret_bm) ** (ANNUALIZATION_FACTOR / n) - 1.0) if tot_ret_bm > -1.0 else -1.0
    active_ret = float(ann_ret - ann_ret_bm)

    win_rate = float(np.mean(r > 0.0))

    return {
        "strategy": strategy_name,
        "partition_type": partition_type,
        "subperiod_label": slice_label,
        "sample_count": int(n),
        "net_total_return": tot_ret,
        "annualized_return": ann_ret,
        "annualized_volatility": vol,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": mdd,
        "nifty50_return": tot_ret_bm,
        "nifty50_annualized": ann_ret_bm,
        "active_return": active_ret,
        "win_rate": win_rate,
    }


def run_subperiod_stability_analysis(
    simulations: Dict[str, pd.DataFrame],
    nifty50_simulation: pd.DataFrame,
    indicators_df: Optional[pd.DataFrame] = None,
    variants: Optional[List[str]] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """
    Run subperiod stability analysis across calendar years, SMA200 trend regimes, and VIX terciles.
    """
    vars_to_run = variants if variants is not None else VARIANTS
    ind_df = indicators_df if indicators_df is not None else load_environmental_indicators()

    # Align dates covering evaluation timeline
    eval_dates = nifty50_simulation.index
    sub_ind = ind_df.loc[eval_dates]

    all_portfolios = vars_to_run + ["NIFTY50"]
    records: List[Dict[str, Any]] = []

    for port in all_portfolios:
        if port == "NIFTY50":
            daily_r = nifty50_simulation["net_return"]
        else:
            daily_r = simulations[port]["net_return"]

        bm_r = nifty50_simulation["net_return"]

        # 1. Calendar Years
        for yr, expected_n in EXPECTED_YEAR_COUNTS.items():
            yr_mask = (daily_r.index.year == yr)
            r_slice = daily_r[yr_mask]
            r_bm_slice = bm_r[yr_mask]
            label = f"{yr} (Partial)" if yr in [2019, 2026] else str(yr)
            rec = compute_slice_metrics(
                r_slice, r_bm_slice, label, "calendar_year", port
            )
            records.append(rec)

        # 2. Bull vs Bear Market (SMA 200)
        for trend in ["Bull (Close > SMA200)", "Bear (Close <= SMA200)"]:
            trend_mask = (sub_ind["trend_label"] == trend)
            r_slice = daily_r[trend_mask]
            r_bm_slice = bm_r[trend_mask]
            rec = compute_slice_metrics(
                r_slice, r_bm_slice, trend, "trend_sma200", port
            )
            records.append(rec)

        # 3. Volatility Regimes (India VIX)
        for vix_cat in ["Low Vol (< 13.0)", "Normal Vol (13.0 - 18.0)", "High Vol (>= 18.0)"]:
            vix_mask = (sub_ind["vix_regime"] == vix_cat)
            r_slice = daily_r[vix_mask]
            r_bm_slice = bm_r[vix_mask]
            rec = compute_slice_metrics(
                r_slice, r_bm_slice, vix_cat, "vix_regime", port
            )
            records.append(rec)

    results_df = pd.DataFrame(records)

    if output_dir is not None:
        out_path = Path(output_dir) / "subperiod_stability.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        results_df.to_parquet(out_path, index=False)
        logger.info(f"Saved Investigation 4 Parquet to: {out_path}")

    return results_df

