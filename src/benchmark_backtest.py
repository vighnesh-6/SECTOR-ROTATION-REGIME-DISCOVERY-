"""
Benchmark Backtesting Engine for ML-Based Sector Rotation Regime Discovery
in the Indian Equity Market (Phase 10).

Implements independent, mathematically rigorous backtesting for the two approved benchmarks:
  1. Benchmark A: NIFTY 50 Price Index Buy & Hold (0 bps transaction costs, gross == net).
  2. Benchmark B: Equal-Weight Six-Sector Portfolio (monthly calendar rebalancing at t+1 Close,
     dynamic intra-month weight drift, actual one-way turnover, and 15 bps transaction fee).

All accounting, return compounding, timeline partitions, and numerical tolerances are 100%
compatible with the existing Phase 10 strategy backtesting engine.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Canonical project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PRICE_DIR = PROJECT_ROOT / "data" / "processed" / "aligned"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "portfolio_backtest"

# Universe definitions
SECTOR_NAMES: List[str] = ["AUTO", "BANK", "FMCG", "IT", "METAL", "PHARMA"]
ALL_BENCHMARK_ASSETS: List[str] = ["NIFTY50", "AUTO", "BANK", "FMCG", "IT", "METAL", "PHARMA"]

# Operational defaults
DEFAULT_TRANSACTION_COST_RATE: float = 0.0015  # 15 basis points one-way
ANNUALIZATION_FACTOR: float = 252.0

# Expected observation and interval counts
EXPECTED_PRICE_SESSIONS: int = 1687
EXPECTED_TOTAL_RETURN_INTERVALS: int = 1686
EXPECTED_TRAIN_RETURN_INTERVALS: int = 1264
EXPECTED_HOLDOUT_RETURN_INTERVALS: int = 422
EXPECTED_TRAIN_START: str = "2019-10-31"
EXPECTED_TRAIN_END: str = "2024-12-31"
EXPECTED_HOLDOUT_START: str = "2025-01-02"
EXPECTED_HOLDOUT_END: str = "2026-09-18"


# =====================================================================
# 1. Price Loading and Calendar Synchronization
# =====================================================================

def load_benchmark_prices(
    price_dir: Optional[Union[str, Path]] = None,
    start_date: str = EXPECTED_TRAIN_START,
    end_date: str = EXPECTED_HOLDOUT_END,
) -> pd.DataFrame:
    """
    Load aligned closing price series for NIFTY 50 and the six sector indices.

    Args:
      price_dir: Path to aligned price CSV directory.
      start_date: Inception date ('2019-10-31').
      end_date: Terminal evaluation date ('2026-09-18').

    Returns:
      pd.DataFrame: Sliced closing prices covering exactly the evaluation sessions.
    """
    p_dir = Path(price_dir) if price_dir is not None else DEFAULT_PRICE_DIR

    prices: Dict[str, pd.Series] = {}
    for s in SECTOR_NAMES:
        fpath = p_dir / f"nifty_{s.lower()}_aligned.csv"
        if not fpath.exists():
            raise FileNotFoundError(f"Missing sector price file: {fpath}")
        pdf = pd.read_csv(fpath, index_col=0, parse_dates=True)
        prices[s] = pdf["Close"]

    p50_path = p_dir / "nifty50_aligned.csv"
    if not p50_path.exists():
        raise FileNotFoundError(f"Missing NIFTY 50 price file: {p50_path}")
    p50_df = pd.read_csv(p50_path, index_col=0, parse_dates=True)
    prices["NIFTY50"] = p50_df["Close"]

    price_df = pd.DataFrame(prices).sort_index()

    # Slice to exact evaluation timeline
    sub_df = price_df.loc[start_date:end_date]
    if len(sub_df) == 0:
        raise ValueError(f"No price observations found between {start_date} and {end_date}.")

    return sub_df


def get_month_end_signal_dates(dates: pd.DatetimeIndex) -> Set[pd.Timestamp]:
    """
    Identify month-end signal dates across the trading calendar.
    A session is a month-end signal date if the subsequent session is in a new month/year.
    Inception date (dates[0]) is explicitly excluded because portfolio is initialized at that close.

    Args:
      dates: Monotonically increasing DatetimeIndex of trading sessions.

    Returns:
      Set[pd.Timestamp]: Set of session dates where a month-end rebalance is signaled.
    """
    if len(dates) < 2:
        return set()

    signals: Set[pd.Timestamp] = set()
    # Start loop from index 1 so inception date (index 0) is never a rebalance signal
    for i in range(1, len(dates) - 1):
        curr_d = dates[i]
        next_d = dates[i + 1]
        if (curr_d.month != next_d.month) or (curr_d.year != next_d.year):
            signals.add(curr_d)

    return signals


# =====================================================================
# 2. Benchmark A: NIFTY 50 Price Index Buy & Hold Simulation
# =====================================================================

def simulate_nifty50_benchmark(
    price_df: pd.DataFrame,
    start_date: str = EXPECTED_TRAIN_START,
    end_date: str = EXPECTED_HOLDOUT_END,
) -> pd.DataFrame:
    """
    Execute simulation for Benchmark A: NIFTY 50 Price Index Buy & Hold.

    Rules & Accounting:
      - Initial NAV = 1.0 on inception date (2019-10-31).
      - Initial allocation = 100% NIFTY 50.
      - Zero rebalancing, zero turnover, zero transaction costs.
      - Gross NAV == Net NAV everywhere.
      - Daily simple return: r_t = (P_t / P_{t-1}) - 1.

    Returns:
      pd.DataFrame: Daily simulation record covering 1,686 return intervals.
    """
    if "NIFTY50" not in price_df.columns:
        raise KeyError("Price DataFrame missing 'NIFTY50' column.")

    dates = price_df.index
    n_dates = len(dates)
    if n_dates < 2:
        raise ValueError(f"Price series must contain at least 2 sessions (got {n_dates}).")

    records: List[Dict[str, Any]] = []
    nav = 1.0

    for k in range(1, n_dates):
        dt_prev = dates[k - 1]
        dt_curr = dates[k]

        p_prev = float(price_df.loc[dt_prev, "NIFTY50"])
        p_curr = float(price_df.loc[dt_curr, "NIFTY50"])
        r_t = (p_curr / p_prev) - 1.0

        pre_trade_nav = nav * (1.0 + r_t)
        nav = pre_trade_nav  # No transaction costs

        period_label = "train" if dt_curr <= pd.Timestamp(EXPECTED_TRAIN_END) else "holdout"

        rec: Dict[str, Any] = {
            "date": dt_curr,
            "period": period_label,
            "benchmark_name": "NIFTY50_BUY_HOLD",
            "rebalance_signal": False,
            "rebalance_executed": False,
            "actual_turnover": 0.0,
            "nominal_turnover": 0.0,
            "transaction_cost": 0.0,
            "gross_return": r_t,
            "net_return": r_t,
            "pre_trade_nav_gross": pre_trade_nav,
            "pre_trade_nav_net": pre_trade_nav,
            "gross_nav": nav,
            "net_nav": nav,
            "contrib_cost": 0.0,
            "r_NIFTY50": r_t,
            "w_hold_NIFTY50": 1.0,
            "w_drift_NIFTY50": 1.0,
            "w_post_NIFTY50": 1.0,
            "w_target_NIFTY50": 1.0,
            "contrib_NIFTY50": r_t,
        }
        records.append(rec)

    daily_df = pd.DataFrame(records).set_index("date")
    return daily_df


# =====================================================================
# 3. Benchmark B: Equal-Weight Six-Sector Portfolio Simulation
# =====================================================================

def simulate_equal_weight_benchmark(
    price_df: pd.DataFrame,
    start_date: str = EXPECTED_TRAIN_START,
    end_date: str = EXPECTED_HOLDOUT_END,
    cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
    tol: float = 1e-7,
) -> pd.DataFrame:
    """
    Execute simulation for Benchmark B: Equal-Weight Six-Sector Portfolio.

    Rules & Accounting:
      - Universe: AUTO, BANK, FMCG, IT, METAL, PHARMA.
      - Initial NAV = 1.0 on inception date (2019-10-31), initialized to 1/6 per sector.
      - No entry transaction fee on Day 0.
      - Daily holding returns: R_gross,t = sum(w_hold,i * r_i,t).
      - Weight drift: w_drifted,i,t = w_hold,i * (1 + r_i,t) / (1 + R_gross,t).
      - Monthly rebalance signal: final available trading session of each calendar month.
      - Execution timing: next available trading session close (t+1 Close).
      - Actual one-way turnover: TO_actual,t = 0.5 * sum(|1/6 - w_drifted,i,t|).
      - Transaction costs: TC_t = NAV_pre,net,t * TO_actual,t * cost_rate.
      - Independent Gross NAV (0 bps) and Net NAV (15 bps) compounding.

    Returns:
      pd.DataFrame: Daily simulation record covering 1,686 return intervals.
    """
    for s in SECTOR_NAMES:
        if s not in price_df.columns:
            raise KeyError(f"Price DataFrame missing sector column: '{s}'")

    dates = price_df.index
    n_dates = len(dates)
    if n_dates < 2:
        raise ValueError(f"Price series must contain at least 2 sessions (got {n_dates}).")

    signal_dates = get_month_end_signal_dates(dates)

    n_sectors = len(SECTOR_NAMES)
    w_target = np.full(n_sectors, 1.0 / n_sectors, dtype=float)

    # Inception state on Date 0 Close (2019-10-31)
    w_post = w_target.copy()
    nav_gross = 1.0
    nav_net = 1.0

    records: List[Dict[str, Any]] = []

    for k in range(1, n_dates):
        dt_prev = dates[k - 1]
        dt_curr = dates[k]

        # 1. Simple sector returns over dt_prev -> dt_curr
        rets = np.zeros(n_sectors, dtype=float)
        for idx, s in enumerate(SECTOR_NAMES):
            p_prev = float(price_df.loc[dt_prev, s])
            p_curr = float(price_df.loc[dt_curr, s])
            rets[idx] = (p_curr / p_prev) - 1.0

        # 2. Holdings held before return
        w_hold = w_post.copy()

        # 3. Gross portfolio return
        r_gross = float(np.sum(w_hold * rets))

        # 4. Pre-trade NAV
        nav_pre_gross = nav_gross * (1.0 + r_gross)
        nav_pre_net = nav_net * (1.0 + r_gross)

        # 5. Drifted weights
        gross_factor = float(1.0 + r_gross)
        if gross_factor <= 0.0:
            raise ValueError(f"Date {dt_curr.date()}: Gross portfolio factor is non-positive ({gross_factor:.6f}).")

        w_drift = (w_hold * (1.0 + rets)) / gross_factor
        w_drift = np.maximum(w_drift, 0.0)
        w_drift = w_drift / np.sum(w_drift)

        # 6. Rebalance authorization check from dt_prev
        rebal_executing = (dt_prev in signal_dates)
        is_signal_today = (dt_curr in signal_dates)

        if rebal_executing:
            to_actual = float(0.5 * np.sum(np.abs(w_target - w_drift)))
            tc = float(nav_pre_net * to_actual * cost_rate)
            nav_post_net = nav_pre_net - tc
            nav_post_gross = nav_pre_gross
            w_post = w_target.copy()
            nom_turnover = 0.0  # Target-to-target turnover is 0 (1/6 to 1/6)
        else:
            to_actual = 0.0
            tc = 0.0
            nav_post_net = nav_pre_net
            nav_post_gross = nav_pre_gross
            w_post = w_drift.copy()
            nom_turnover = 0.0

        # 7. Net daily return
        r_net = float((nav_post_net / nav_net) - 1.0)

        # Update running NAV
        nav_gross = nav_post_gross
        nav_net = nav_post_net

        # 8. Exact additive attribution
        contrib_sectors = w_hold * rets
        c_cost = float(r_net - r_gross)

        # Attribution identity check
        recon_r_net = float(np.sum(contrib_sectors) + c_cost)
        if not np.isclose(r_net, recon_r_net, atol=1e-10):
            raise ValueError(f"Date {dt_curr.date()}: Attribution reconciliation failed (diff: {abs(r_net - recon_r_net):.2e}).")

        period_label = "train" if dt_curr <= pd.Timestamp(EXPECTED_TRAIN_END) else "holdout"

        rec = {
            "date": dt_curr,
            "period": period_label,
            "benchmark_name": "EQUAL_WEIGHT_6SECTOR",
            "rebalance_signal": is_signal_today,
            "rebalance_executed": rebal_executing,
            "actual_turnover": to_actual,
            "nominal_turnover": nom_turnover,
            "transaction_cost": tc,
            "gross_return": r_gross,
            "net_return": r_net,
            "pre_trade_nav_gross": nav_pre_gross,
            "pre_trade_nav_net": nav_pre_net,
            "gross_nav": nav_gross,
            "net_nav": nav_net,
            "contrib_cost": c_cost,
        }

        # Attach sector-specific return, weights, and contributions
        for idx, s in enumerate(SECTOR_NAMES):
            rec[f"r_{s}"] = float(rets[idx])
            rec[f"w_hold_{s}"] = float(w_hold[idx])
            rec[f"w_drift_{s}"] = float(w_drift[idx])
            rec[f"w_post_{s}"] = float(w_post[idx])
            rec[f"contrib_{s}"] = float(contrib_sectors[idx])
            rec[f"w_target_{s}"] = float(w_target[idx])

        records.append(rec)

    daily_df = pd.DataFrame(records).set_index("date")
    return daily_df


def run_all_benchmarks(
    price_df: Optional[pd.DataFrame] = None,
    cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
) -> Dict[str, pd.DataFrame]:
    """
    Run simulations for both Benchmark A (NIFTY 50) and Benchmark B (Equal-Weight 6-Sector).

    Returns:
      Dict[str, pd.DataFrame]: Mapping of 'NIFTY50' and 'EQUAL_WEIGHT' to daily simulation DataFrames.
    """
    pdf = price_df if price_df is not None else load_benchmark_prices()
    logger.info("Simulating Benchmark A: NIFTY 50 Buy & Hold...")
    df_n50 = simulate_nifty50_benchmark(pdf)

    logger.info("Simulating Benchmark B: Equal-Weight 6-Sector Portfolio...")
    df_ew = simulate_equal_weight_benchmark(pdf, cost_rate=cost_rate)

    return {
        "NIFTY50": df_n50,
        "EQUAL_WEIGHT": df_ew,
    }


# =====================================================================
# 4. Performance Metrics and Table Compilation
# =====================================================================

def compute_benchmark_metrics(
    daily_df: pd.DataFrame,
    period: str = "full",
    validate_counts: bool = False,
) -> Dict[str, Any]:
    """
    Compute quantitative performance, risk, and execution metrics strictly following
    the Phase 10 approved definitions.
    """
    if period == "train":
        sub = daily_df[daily_df["period"] == "train"]
        nav_start_net = 1.0
        nav_end_net = float(sub["net_nav"].iloc[-1])
        nav_start_gross = 1.0
        nav_end_gross = float(sub["gross_nav"].iloc[-1])
        expected_n = EXPECTED_TRAIN_RETURN_INTERVALS
    elif period == "holdout":
        sub = daily_df[daily_df["period"] == "holdout"]
        train_sub = daily_df[daily_df["period"] == "train"]
        nav_start_net = float(train_sub["net_nav"].iloc[-1]) if len(train_sub) > 0 else 1.0
        nav_end_net = float(sub["net_nav"].iloc[-1])
        nav_start_gross = float(train_sub["gross_nav"].iloc[-1]) if len(train_sub) > 0 else 1.0
        nav_end_gross = float(sub["gross_nav"].iloc[-1])
        expected_n = EXPECTED_HOLDOUT_RETURN_INTERVALS
    elif period == "full":
        sub = daily_df
        nav_start_net = 1.0
        nav_end_net = float(sub["net_nav"].iloc[-1])
        nav_start_gross = 1.0
        nav_end_gross = float(sub["gross_nav"].iloc[-1])
        expected_n = EXPECTED_TOTAL_RETURN_INTERVALS
    else:
        raise ValueError(f"Unknown period: '{period}'. Expected 'full', 'train', or 'holdout'.")

    N = len(sub)
    if N == 0:
        raise ValueError(f"Period '{period}' has 0 return intervals.")

    if validate_counts and N != expected_n:
        raise ValueError(f"Period '{period}' expected {expected_n} return intervals, got {N}.")

    # Cumulative total return
    tr_net = float((nav_end_net / nav_start_net) - 1.0)
    tr_gross = float((nav_end_gross / nav_start_gross) - 1.0)

    # CAGR with N daily return intervals
    cagr_net = float((nav_end_net / nav_start_net) ** (ANNUALIZATION_FACTOR / N) - 1.0)
    cagr_gross = float((nav_end_gross / nav_start_gross) ** (ANNUALIZATION_FACTOR / N) - 1.0)
    cagr_drag = float(cagr_gross - cagr_net)

    # Returns array
    r_net_series = sub["net_return"].values.astype(float)
    mean_daily = float(np.mean(r_net_series))
    ann_mean_return = float(mean_daily * ANNUALIZATION_FACTOR)

    # Annualized Volatility (ddof=1)
    ann_vol = float(np.std(r_net_series, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR))

    # Annualized Sharpe Ratio (zero risk-free baseline)
    sharpe = float(ann_mean_return / ann_vol) if ann_vol > 0.0 else 0.0

    # Downside Deviation (MAR = 0%)
    downside_sq = np.minimum(0.0, r_net_series) ** 2
    downside_dev = float(np.sqrt(np.mean(downside_sq)) * np.sqrt(ANNUALIZATION_FACTOR))

    # Annualized Sortino Ratio (arithmetic numerator)
    sortino = float(ann_mean_return / downside_dev) if downside_dev > 0.0 else 0.0

    # Maximum Drawdown (MDD)
    if period == "holdout":
        cum_nav = np.cumprod(1.0 + r_net_series)
    else:
        cum_nav = sub["net_nav"].values / nav_start_net

    peaks = np.maximum.accumulate(cum_nav)
    dds = (cum_nav - peaks) / peaks
    mdd = float(np.min(dds))

    # Execution statistics
    rebal_count = int(sub["rebalance_executed"].sum())
    cum_to = float(sub["actual_turnover"].sum())
    ann_to = float(cum_to * (ANNUALIZATION_FACTOR / N))
    cum_tc = float(sub["transaction_cost"].sum())
    worst_day = float(np.min(r_net_series))

    b_name = str(sub["benchmark_name"].iloc[0])

    return {
        "benchmark_name": b_name,
        "period": period,
        "return_intervals": N,
        "start_date": str(sub.index.min().date()),
        "end_date": str(sub.index.max().date()),
        "total_return_gross_pct": tr_gross * 100.0,
        "total_return_net_pct": tr_net * 100.0,
        "cagr_gross_pct": cagr_gross * 100.0,
        "cagr_net_pct": cagr_net * 100.0,
        "cagr_drag_pct": cagr_drag * 100.0,
        "ann_mean_return_pct": ann_mean_return * 100.0,
        "ann_volatility_pct": ann_vol * 100.0,
        "sharpe_ratio": sharpe,
        "downside_deviation_pct": downside_dev * 100.0,
        "sortino_ratio": sortino,
        "max_drawdown_pct": mdd * 100.0,
        "worst_daily_return_pct": worst_day * 100.0,
        "rebalances_executed": rebal_count,
        "cum_actual_turnover": cum_to,
        "ann_actual_turnover": ann_to,
        "cum_transaction_costs": cum_tc,
    }


def generate_benchmark_metrics_table(
    simulations: Dict[str, pd.DataFrame],
    validate_counts: bool = False,
) -> pd.DataFrame:
    """
    Compile performance metrics for both benchmarks across train, holdout, and full periods.
    """
    rows = []
    for b_key, df in simulations.items():
        for p in ["train", "holdout", "full"]:
            m = compute_benchmark_metrics(df, period=p, validate_counts=validate_counts)
            rows.append(m)

    cols = ["benchmark_name", "period", "return_intervals", "total_return_net_pct", "cagr_net_pct",
            "cagr_gross_pct", "cagr_drag_pct", "ann_volatility_pct", "sharpe_ratio",
            "sortino_ratio", "max_drawdown_pct", "rebalances_executed", "cum_actual_turnover",
            "ann_actual_turnover", "cum_transaction_costs"]
    metrics_df = pd.DataFrame(rows)[cols]
    return metrics_df


# =====================================================================
# 5. Parquet Serialization and Parity Verification
# =====================================================================

def save_benchmark_parquet(
    simulations: Dict[str, pd.DataFrame],
    output_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Path]:
    """
    Persist benchmark simulation records in Apache Parquet format.

    Persists:
      - results/portfolio_backtest/daily_simulation_benchmark_nifty50.parquet
      - results/portfolio_backtest/daily_simulation_benchmark_equal_weight.parquet
      - results/portfolio_backtest/benchmark_metrics_summary.parquet
      - results/portfolio_backtest/benchmark_metrics_summary.csv

    Returns:
      Dict[str, Path]: Mapping of benchmark key to saved .parquet file path.
    """
    out_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: Dict[str, Path] = {}

    file_mapping = {
        "NIFTY50": "daily_simulation_benchmark_nifty50.parquet",
        "EQUAL_WEIGHT": "daily_simulation_benchmark_equal_weight.parquet",
    }

    for b_key, fname in file_mapping.items():
        if b_key in simulations:
            df = simulations[b_key]
            target_path = out_dir / fname
            df.to_parquet(target_path, engine="pyarrow", compression="snappy", index=True)
            saved_paths[b_key] = target_path
            logger.info(f"Saved {b_key} benchmark simulation to {target_path} ({len(df)} rows)")

    # Save summary tables
    metrics_table = generate_benchmark_metrics_table(simulations)
    metrics_table.to_parquet(out_dir / "benchmark_metrics_summary.parquet", engine="pyarrow", index=False)
    metrics_table.to_csv(out_dir / "benchmark_metrics_summary.csv", index=False)

    return saved_paths


def reload_and_verify_benchmark_parquet(
    parquet_paths: Dict[str, Path],
    original_simulations: Optional[Dict[str, pd.DataFrame]] = None,
    expected_intervals: Optional[int] = EXPECTED_TOTAL_RETURN_INTERVALS,
    tol: float = 1e-7,
) -> Dict[str, Dict[str, Any]]:
    """
    Reload persisted benchmark Parquet files and verify schema, row counts, and numerical parity.
    """
    audit_results: Dict[str, Dict[str, Any]] = {}

    for b_key, p in parquet_paths.items():
        if not p.exists():
            raise FileNotFoundError(f"Parquet file not found at {p}")

        reloaded = pd.read_parquet(p, engine="pyarrow")

        if expected_intervals is not None and len(reloaded) != expected_intervals:
            raise ValueError(f"Benchmark {b_key}: Expected {expected_intervals} rows, got {len(reloaded)}.")

        if not isinstance(reloaded.index, pd.DatetimeIndex):
            raise ValueError(f"Benchmark {b_key}: Reloaded index must be pd.DatetimeIndex.")

        if not reloaded.index.is_monotonic_increasing:
            raise ValueError(f"Benchmark {b_key}: Dates are not monotonically increasing.")

        null_counts = reloaded.isnull().sum()
        cols_with_nulls = null_counts[null_counts > 0].to_dict()
        if cols_with_nulls:
            raise ValueError(f"Benchmark {b_key}: Null values detected in columns: {cols_with_nulls}")

        parity_confirmed = False
        if original_simulations is not None and b_key in original_simulations:
            orig = original_simulations[b_key]
            if orig.shape != reloaded.shape:
                raise ValueError(f"Benchmark {b_key}: Shape mismatch: {orig.shape} vs {reloaded.shape}")

            for col in orig.columns:
                if col in ["period", "benchmark_name"]:
                    assert (orig[col].values == reloaded[col].values).all(), f"Mismatch in {col}"
                elif orig[col].dtype == bool:
                    assert (orig[col].values == reloaded[col].values).all(), f"Mismatch in {col}"
                else:
                    o_vals = orig[col].values.astype(float)
                    r_vals = reloaded[col].values.astype(float)
                    assert np.allclose(o_vals, r_vals, atol=tol), f"Mismatch in {col}"
            parity_confirmed = True

        audit_results[b_key] = {
            "path": str(p),
            "size_bytes": p.stat().st_size,
            "rows": len(reloaded),
            "columns": len(reloaded.columns),
            "start_date": str(reloaded.index.min().date()),
            "end_date": str(reloaded.index.max().date()),
            "train_intervals": int((reloaded["period"] == "train").sum()),
            "holdout_intervals": int((reloaded["period"] == "holdout").sum()),
            "rebalances_executed": int(reloaded["rebalance_executed"].sum()),
            "ending_net_nav": float(reloaded["net_nav"].iloc[-1]),
            "parity_verified": parity_confirmed,
        }

    return audit_results


# =====================================================================
# 6. Master End-to-End Benchmark Pipeline
# =====================================================================

def run_benchmark_pipeline(
    price_dir: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Path], Dict[str, Any]]:
    """
    Execute full Phase 10 benchmark backtesting pipeline:
      1. Load aligned prices for NIFTY 50 and 6 sectors.
      2. Simulate Benchmark A (NIFTY 50 Buy & Hold) and Benchmark B (Equal-Weight 6-Sector).
      3. Verify interval counts, compounding, and attribution exactness.
      4. Persist simulation records and metrics to Apache Parquet format.
      5. Reload and verify Parquet file integrity and parity.

    Returns:
      Tuple of (simulations_dict, saved_paths_dict, pipeline_metadata_dict).
    """
    price_df = load_benchmark_prices(price_dir=price_dir)
    simulations = run_all_benchmarks(price_df=price_df, cost_rate=cost_rate)
    saved_paths = save_benchmark_parquet(simulations, output_dir=output_dir)
    audit_meta = reload_and_verify_benchmark_parquet(saved_paths, original_simulations=simulations)
    metrics_table = generate_benchmark_metrics_table(simulations, validate_counts=True)

    metadata = {
        "parquet_audit": audit_meta,
        "metrics_summary": metrics_table.to_dict(orient="records"),
    }
    return simulations, saved_paths, metadata

