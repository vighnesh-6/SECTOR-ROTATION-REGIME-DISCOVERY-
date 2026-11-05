"""
Portfolio Backtesting Engine for ML-Based Sector Rotation Regime Discovery
in the Indian Equity Market (Phase 10.3).

Executes the formal historical backtesting methodology approved in Phase 10.2:
  1. Next-session close (t+1 Close) execution timing with zero look-ahead bias.
  2. Multi-asset price drift formulation between rebalances.
  3. Dynamic drift-adjusted actual one-way turnover: TO = 0.5 * sum(|w_target - w_drift|).
  4. Separate gross (0 bps) and net (15 bps) portfolio accounting.
  5. Continuous state across the training-to-holdout boundary (2024-12-31 to 2025-01-02).
  6. Exact additive return attribution: R_net = sum(C_i) + C_cost without approximation.
  7. Apache Parquet storage for authoritative daily simulation records.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Canonical project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PRICE_DIR = PROJECT_ROOT / "data" / "processed" / "aligned"
DEFAULT_PROB_PATH = PROJECT_ROOT / "results" / "regime_discovery" / "hmm_causal_probabilities.csv"
DEFAULT_SCHEDULE_DIR = PROJECT_ROOT / "results" / "portfolio_construction"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "portfolio_backtest"

# Universe definitions
SECTOR_NAMES: List[str] = ["AUTO", "BANK", "FMCG", "IT", "METAL", "PHARMA"]
ALL_ASSETS: List[str] = ["NIFTY50", "AUTO", "BANK", "FMCG", "IT", "METAL", "PHARMA", "CASH"]

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

VARIANTS: List[str] = ["1A", "1B", "2A", "2B"]


# =====================================================================
# 1. Mathematical Core: Drift and Turnover Calculations
# =====================================================================

def calculate_drifted_weights(
    weights_prev: np.ndarray,
    returns: np.ndarray,
    tol: float = 1e-7,
) -> np.ndarray:
    """
    Calculate pre-trade drifted portfolio weights after asset price returns have occurred.

    Formula:
      w_tilde_i = (w_prev_i * (1 + r_i)) / sum_j (w_prev_j * (1 + r_j))

    Args:
      weights_prev: Array of starting portfolio weights summing to 1.0.
      returns: Array of simple asset returns over the holding interval.
      tol: Numerical comparison tolerance.

    Returns:
      np.ndarray: Drifted portfolio weights summing strictly to 1.0.

    Raises:
      ValueError: If weights do not sum to 1.0 or gross return factor <= 0.
    """
    w_sum = float(np.sum(weights_prev))
    if not np.isclose(w_sum, 1.0, atol=tol):
        raise ValueError(f"Starting weights must sum to 1.0 (got {w_sum:.6f}).")

    if (weights_prev < -tol).any():
        raise ValueError("Starting weights cannot be negative.")

    gross_factor = float(np.sum(weights_prev * (1.0 + returns)))
    if gross_factor <= 0.0:
        raise ValueError(f"Gross portfolio factor is non-positive ({gross_factor:.6f}).")

    drifted = (weights_prev * (1.0 + returns)) / gross_factor

    # Clean small floating point negatives within tolerance
    drifted = np.maximum(drifted, 0.0)
    drifted = drifted / np.sum(drifted)
    return drifted


def calculate_actual_turnover(
    weights_target: np.ndarray,
    weights_drifted: np.ndarray,
    tol: float = 1e-7,
) -> float:
    """
    Calculate actual one-way portfolio turnover between target weights and pre-trade drifted weights.

    Formula:
      TO_actual = 0.5 * sum_i |w_target_i - w_drifted_i|

    Args:
      weights_target: Authorized target portfolio weights summing to 1.0.
      weights_drifted: Pre-trade drifted portfolio weights summing to 1.0.
      tol: Numerical comparison tolerance.

    Returns:
      float: Actual one-way turnover in [0.0, 1.0].
    """
    sum_target = float(np.sum(weights_target))
    sum_drifted = float(np.sum(weights_drifted))

    if not np.isclose(sum_target, 1.0, atol=tol):
        raise ValueError(f"Target weights must sum to 1.0 (got {sum_target:.6f}).")
    if not np.isclose(sum_drifted, 1.0, atol=tol):
        raise ValueError(f"Drifted weights must sum to 1.0 (got {sum_drifted:.6f}).")

    to = float(0.5 * np.sum(np.abs(weights_target - weights_drifted)))
    return to


# =====================================================================
# 2. Input Loading and Return Preparation
# =====================================================================

def load_backtest_inputs(
    schedule_dir: Optional[Union[str, Path]] = None,
    price_dir: Optional[Union[str, Path]] = None,
    prob_path: Optional[Union[str, Path]] = None,
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    """
    Load and validate Phase 9 schedules, aligned closing prices, and causal probabilities.

    Returns:
      Tuple of (schedules_dict, price_df, prob_df).
    """
    s_dir = Path(schedule_dir) if schedule_dir is not None else DEFAULT_SCHEDULE_DIR
    p_dir = Path(price_dir) if price_dir is not None else DEFAULT_PRICE_DIR
    pr_path = Path(prob_path) if prob_path is not None else DEFAULT_PROB_PATH

    # 1. Load prices
    prices: Dict[str, pd.Series] = {}
    for s in SECTOR_NAMES:
        fpath = p_dir / f"nifty_{s.lower()}_aligned.csv"
        if not fpath.exists():
            raise FileNotFoundError(f"Missing price file: {fpath}")
        pdf = pd.read_csv(fpath, index_col=0, parse_dates=True)
        prices[s] = pdf["Close"]

    p50_path = p_dir / "nifty50_aligned.csv"
    if not p50_path.exists():
        raise FileNotFoundError(f"Missing NIFTY 50 price file: {p50_path}")
    p50_df = pd.read_csv(p50_path, index_col=0, parse_dates=True)
    prices["NIFTY50"] = p50_df["Close"]

    price_df = pd.DataFrame(prices).sort_index()

    # 2. Load causal probabilities
    if not pr_path.exists():
        raise FileNotFoundError(f"Missing causal probabilities file: {pr_path}")
    prob_df = pd.read_csv(pr_path, parse_dates=["Date"]).set_index("Date")

    # 3. Load schedules
    schedules: Dict[str, pd.DataFrame] = {}
    for v in VARIANTS:
        fpath = s_dir / f"target_weights_{v}.csv"
        if not fpath.exists():
            raise FileNotFoundError(f"Missing schedule file: {fpath}")
        sdf = pd.read_csv(fpath, parse_dates=["Date", "exec_date"]).set_index("Date")
        schedules[v] = sdf

    return schedules, price_df, prob_df


# =====================================================================
# 3. Portfolio Simulation Core Engine
# =====================================================================

def simulate_portfolio(
    schedule_df: pd.DataFrame,
    price_df: pd.DataFrame,
    prob_df: Optional[pd.DataFrame] = None,
    cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
    cash_yield_daily: float = 0.0,
    tol: float = 1e-7,
) -> pd.DataFrame:
    """
    Execute full historical portfolio backtest across the complete timeline.

    Chronology and Execution Contract:
      - Initial State (Date 0, 2019-10-31): Portfolio starts with 100% NIFTY 50 (NAV = 1.0).
      - Interval 1 (2019-10-31 -> 2019-11-01): Portfolio earns 100% NIFTY 50 return.
      - Session 1 Close (2019-11-01): First rebalance executes into target sectors (100% turnover fee).
      - Subsequent Sessions: If rebalance authorized on t-1, executes at session t Close.
      - Terminal Date (2026-09-18): Final price realization; any signal on Date T is untraded.

    Args:
      schedule_df: Target-weight schedule DataFrame from Phase 9 (1,687 dates).
      price_df: Aligned closing prices covering schedule dates (and NIFTY 50).
      prob_df: Optional causal probabilities DataFrame for metadata attachment.
      cost_rate: One-way transaction cost rate (e.g., 0.0015 for 15 bps).
      cash_yield_daily: Daily return on cash balances (baseline = 0.0).
      tol: Numerical tolerance for simplex and attribution checks.

    Returns:
      pd.DataFrame: Daily simulation record covering 1,686 return intervals with full attribution.
    """
    dates = schedule_df.index
    n_dates = len(dates)

    if n_dates < 2:
        raise ValueError(f"Schedule must contain at least 2 sessions (got {n_dates}).")

    # Verify price coverage
    for a in ALL_ASSETS:
        if a != "CASH" and a not in price_df.columns:
            raise KeyError(f"Price DataFrame missing asset: {a}")

    missing_dates = dates.difference(price_df.index)
    if len(missing_dates) > 0:
        raise KeyError(f"Price DataFrame missing {len(missing_dates)} simulation dates.")

    # Asset ordering
    n_assets = len(ALL_ASSETS)
    w_cols = [f"w_{a}" for a in ALL_ASSETS]
    variant_name = str(schedule_df["variant"].iloc[0])

    # Initial state at Date 0 Close (2019-10-31)
    # 100% NIFTY 50, zero cash, zero sectors
    w_post = np.zeros(n_assets, dtype=float)
    w_post[ALL_ASSETS.index("NIFTY50")] = 1.0

    nav_gross = 1.0
    nav_net = 1.0

    records: List[Dict[str, Any]] = []

    # Simulation loop across return sessions: k = 1 to n_dates - 1
    # Day k=1 corresponds to 2019-11-01 Close
    for k in range(1, n_dates):
        dt_prev = dates[k - 1]
        dt_curr = dates[k]

        # 1. Asset simple returns over dt_prev -> dt_curr
        rets = np.zeros(n_assets, dtype=float)
        for idx, a in enumerate(ALL_ASSETS):
            if a == "CASH":
                rets[idx] = cash_yield_daily
            else:
                p_prev = float(price_df.loc[dt_prev, a])
                p_curr = float(price_df.loc[dt_curr, a])
                rets[idx] = (p_curr / p_prev) - 1.0

        # 2. Holdings held before return
        w_hold = w_post.copy()

        # 3. Gross portfolio return
        r_gross = float(np.sum(w_hold * rets))

        # 4. Pre-trade NAV
        nav_pre_gross = nav_gross * (1.0 + r_gross)
        nav_pre_net = nav_net * (1.0 + r_gross)

        # 5. Pre-trade drifted weights
        w_drift = calculate_drifted_weights(w_hold, rets, tol=tol)

        # 6. Rebalance authorization check from previous session signal
        row_prev = schedule_df.loc[dt_prev]
        rebal_executing = bool(row_prev["rebalance_triggered"])
        r3_bypass = bool(row_prev["rebalance_bypassed_r3"])
        nom_turnover = float(row_prev["turnover"])

        if rebal_executing:
            w_target = row_prev[w_cols].values.astype(float)
            w_target = np.maximum(w_target, 0.0)
            w_target = w_target / np.sum(w_target)

            to_actual = calculate_actual_turnover(w_target, w_drift, tol=tol)
            tc = float(nav_pre_net * to_actual * cost_rate)
            nav_post_net = nav_pre_net - tc
            nav_post_gross = nav_pre_gross  # Gross simulation incurs zero cost
            w_post = w_target.copy()
        else:
            to_actual = 0.0
            tc = 0.0
            nav_post_net = nav_pre_net
            nav_post_gross = nav_pre_gross
            w_post = w_drift.copy()

        # 7. Net daily return
        r_net = float((nav_post_net / nav_net) - 1.0)

        # Update running NAV
        nav_gross = nav_post_gross
        nav_net = nav_post_net

        # 8. Exact additive attribution
        # Asset contribution = w_hold_i * r_i
        # Cost drag contribution = R_net - R_gross
        contrib_assets = w_hold * rets
        c_cost = float(r_net - r_gross)

        # Attribution identity check
        recon_r_net = float(np.sum(contrib_assets) + c_cost)
        if not np.isclose(r_net, recon_r_net, atol=1e-10):
            raise ValueError(f"Date {dt_curr.date()}: Attribution reconciliation failed (diff: {abs(r_net - recon_r_net):.2e}).")

        # 9. Record session row
        row_curr = schedule_df.loc[dt_curr]
        rec: Dict[str, Any] = {
            "date": dt_curr,
            "period": str(row_curr["period"]),
            "variant": variant_name,
            "rebalance_executed": rebal_executing,
            "rebalance_bypassed_r3": r3_bypass,
            "actual_turnover": to_actual,
            "nominal_turnover": nom_turnover,
            "transaction_cost": tc,
            "gross_return": r_gross,
            "net_return": r_net,
            "gross_nav": nav_gross,
            "net_nav": nav_net,
            "contrib_cost": c_cost,
            "raw_regime_argmax": int(row_curr["raw_regime_argmax"]),
            "max_probability": float(row_curr["max_probability"]),
            "is_confident": bool(row_curr["is_confident"]),
            "accepted_regime": int(row_curr["accepted_regime"]) if pd.notna(row_curr["accepted_regime"]) else -1,
        }

        # Asset-specific fields
        for idx, a in enumerate(ALL_ASSETS):
            rec[f"r_{a}"] = float(rets[idx])
            rec[f"w_hold_{a}"] = float(w_hold[idx])
            rec[f"w_drift_{a}"] = float(w_drift[idx])
            rec[f"w_post_{a}"] = float(w_post[idx])
            rec[f"contrib_{a}"] = float(contrib_assets[idx])
            # Target weights established on dt_curr
            rec[f"w_target_{a}"] = float(row_curr[f"w_{a}"])

        # Attach causal probabilities if provided
        if prob_df is not None and dt_curr in prob_df.index:
            p_row = prob_df.loc[dt_curr]
            for j in range(6):
                rec[f"prob_{j}"] = float(p_row[f"prob_{j}"])

        records.append(rec)

    daily_df = pd.DataFrame(records).set_index("date")
    return daily_df


def run_all_simulations(
    schedules: Dict[str, pd.DataFrame],
    price_df: pd.DataFrame,
    prob_df: Optional[pd.DataFrame] = None,
    cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
    cash_yield_daily: float = 0.0,
) -> Dict[str, pd.DataFrame]:
    """
    Execute simulation across all four frozen strategy variants.

    Returns:
      Dict[str, pd.DataFrame]: Mapping of variant name ('1A', '1B', '2A', '2B') to daily simulation DataFrame.
    """
    simulations: Dict[str, pd.DataFrame] = {}
    for v in VARIANTS:
        logger.info(f"Running simulation for Strategy Variant {v}...")
        simulations[v] = simulate_portfolio(
            schedule_df=schedules[v],
            price_df=price_df,
            prob_df=prob_df,
            cost_rate=cost_rate,
            cash_yield_daily=cash_yield_daily,
        )
    return simulations


# =====================================================================
# 4. Performance Metrics and Attribution Analysis
# =====================================================================

def compute_metrics(
    daily_df: pd.DataFrame,
    period: str = "full",
    validate_counts: bool = False,
) -> Dict[str, Any]:
    """
    Compute quantitative performance, risk, and execution metrics strictly following
    the Phase 10.2 approved definitions.

    Args:
      daily_df: Daily simulation DataFrame for a single variant.
      period: Evaluation window: 'full', 'train', or 'holdout'.
      validate_counts: If True, strictly enforce expected interval counts (1264, 422, 1686).

    Returns:
      Dict[str, Any]: Comprehensive performance and risk metrics dictionary.
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

    # Compounded Annual Growth Rate (CAGR) with N daily return intervals
    cagr_net = float((nav_end_net / nav_start_net) ** (ANNUALIZATION_FACTOR / N) - 1.0)
    cagr_gross = float((nav_end_gross / nav_start_gross) ** (ANNUALIZATION_FACTOR / N) - 1.0)
    cagr_drag = float(cagr_gross - cagr_net)

    # Net returns array
    r_net_series = sub["net_return"].values.astype(float)
    mean_daily = float(np.mean(r_net_series))
    ann_mean_return = float(mean_daily * ANNUALIZATION_FACTOR)

    # Annualized Volatility (ddof=1)
    ann_vol = float(np.std(r_net_series, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR))

    # Annualized Sharpe Ratio (zero risk-free baseline)
    sharpe = float(ann_mean_return / ann_vol) if ann_vol > 0.0 else 0.0

    # Annualized Downside Deviation (minimum acceptable return = 0)
    downside_sq = np.minimum(0.0, r_net_series) ** 2
    downside_dev = float(np.sqrt(np.mean(downside_sq)) * np.sqrt(ANNUALIZATION_FACTOR))

    # Corrected Annualized Sortino Ratio (arithmetic numerator)
    sortino = float(ann_mean_return / downside_dev) if downside_dev > 0.0 else 0.0

    # Maximum Drawdown (MDD)
    if period == "holdout":
        # Cumulative NAV indexed to 1.0 for holdout
        cum_nav = np.cumprod(1.0 + r_net_series)
    else:
        cum_nav = sub["net_nav"].values / nav_start_net

    peaks = np.maximum.accumulate(cum_nav)
    dds = (cum_nav - peaks) / peaks
    mdd = float(np.min(dds))

    # Execution and cost statistics
    rebal_count = int(sub["rebalance_executed"].sum())
    cum_to = float(sub["actual_turnover"].sum())
    ann_to = float(cum_to * (ANNUALIZATION_FACTOR / N))
    cum_tc = float(sub["transaction_cost"].sum())
    worst_day = float(np.min(r_net_series))
    r3_count = int(sub["rebalance_bypassed_r3"].sum())

    # Average exposure
    avg_cash = float(sub["w_post_CASH"].mean())
    avg_equity = float(1.0 - avg_cash)

    return {
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
        "r3_crisis_overrides": r3_count,
        "cum_actual_turnover": cum_to,
        "ann_actual_turnover": ann_to,
        "cum_transaction_costs": cum_tc,
        "avg_cash_weight_pct": avg_cash * 100.0,
        "avg_equity_weight_pct": avg_equity * 100.0,
    }


def compute_attribution(daily_df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize asset-level and cost contributions across evaluation periods.

    Returns:
      pd.DataFrame: Summary table of cumulative percentage returns contributed by each asset and costs.
    """
    records = []
    for p in ["train", "holdout", "full"]:
        sub = daily_df if p == "full" else daily_df[daily_df["period"] == p]
        rec: Dict[str, Any] = {"period": p, "return_intervals": len(sub)}

        for a in ALL_ASSETS:
            rec[f"contrib_{a}_pct"] = float(sub[f"contrib_{a}"].sum() * 100.0)

        rec["contrib_cost_pct"] = float(sub["contrib_cost"].sum() * 100.0)
        rec["gross_sum_pct"] = float(sum(sub[f"contrib_{a}"].sum() for a in ALL_ASSETS) * 100.0)
        rec["reconciled_net_pct"] = float(rec["gross_sum_pct"] + rec["contrib_cost_pct"])
        rec["actual_net_sum_pct"] = float(sub["net_return"].sum() * 100.0)
        records.append(rec)

    return pd.DataFrame(records)


def generate_metrics_table(
    simulations: Dict[str, pd.DataFrame],
    validate_counts: bool = False,
) -> pd.DataFrame:
    """
    Compile performance metrics for all variants across train, holdout, and full periods.
    """
    rows = []
    for v, df in simulations.items():
        for p in ["train", "holdout", "full"]:
            m = compute_metrics(df, period=p, validate_counts=validate_counts)
            m["variant"] = v
            rows.append(m)

    cols = ["variant", "period", "return_intervals", "total_return_net_pct", "cagr_net_pct",
            "cagr_gross_pct", "cagr_drag_pct", "ann_volatility_pct", "sharpe_ratio",
            "sortino_ratio", "max_drawdown_pct", "rebalances_executed", "cum_actual_turnover",
            "ann_actual_turnover", "cum_transaction_costs", "avg_cash_weight_pct"]
    metrics_df = pd.DataFrame(rows)[cols]
    return metrics_df


# =====================================================================
# 5. Parquet Serialization and Parity Verification
# =====================================================================

def save_simulation_parquet(
    simulations: Dict[str, pd.DataFrame],
    output_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Path]:
    """
    Persist authoritative daily simulation records in Apache Parquet format.

    Args:
      simulations: Dictionary mapping variant names to daily simulation DataFrames.
      output_dir: Directory path. Defaults to results/portfolio_backtest/.

    Returns:
      Dict[str, Path]: Mapping of variant name to saved .parquet file path.
    """
    out_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: Dict[str, Path] = {}
    for v, df in simulations.items():
        fname = f"daily_simulation_{v}.parquet"
        target_path = out_dir / fname

        # Write to Parquet using PyArrow engine
        df.to_parquet(target_path, engine="pyarrow", compression="snappy", index=True)
        saved_paths[v] = target_path
        logger.info(f"Saved {v} simulation to {target_path} ({len(df)} rows)")

    # Also save summary tables
    metrics_table = generate_metrics_table(simulations)
    metrics_table.to_parquet(out_dir / "metrics_summary.parquet", engine="pyarrow", index=False)
    metrics_table.to_csv(out_dir / "metrics_summary.csv", index=False)

    return saved_paths


def reload_and_verify_parquet(
    parquet_paths: Dict[str, Path],
    original_simulations: Optional[Dict[str, pd.DataFrame]] = None,
    expected_intervals: Optional[int] = EXPECTED_TOTAL_RETURN_INTERVALS,
    tol: float = 1e-7,
) -> Dict[str, Dict[str, Any]]:
    """
    Reload persisted Parquet files and strictly verify schema, row counts, data types,
    null counts, and exact numerical parity against in-memory records.

    Returns:
      Dict[str, Dict[str, Any]]: Verification audit summary dictionary.
    """
    audit_results: Dict[str, Dict[str, Any]] = {}

    for v, p in parquet_paths.items():
        if not p.exists():
            raise FileNotFoundError(f"Parquet file not found at {p}")

        # Reload
        reloaded = pd.read_parquet(p, engine="pyarrow")

        # Row count and date index verification
        if expected_intervals is not None and len(reloaded) != expected_intervals:
            raise ValueError(f"Variant {v}: Expected {expected_intervals} rows, got {len(reloaded)}.")

        if not isinstance(reloaded.index, pd.DatetimeIndex):
            raise ValueError(f"Variant {v}: Reloaded index must be pd.DatetimeIndex.")

        if not reloaded.index.is_monotonic_increasing:
            raise ValueError(f"Variant {v}: Dates are not monotonically increasing.")

        # Check for unexpected nulls
        null_counts = reloaded.isnull().sum()
        cols_with_nulls = null_counts[null_counts > 0].to_dict()
        if cols_with_nulls:
            raise ValueError(f"Variant {v}: Null values detected in columns: {cols_with_nulls}")

        # Parity comparison if in-memory DataFrame provided
        parity_confirmed = False
        if original_simulations is not None and v in original_simulations:
            orig = original_simulations[v]
            if orig.shape != reloaded.shape:
                raise ValueError(f"Variant {v}: Shape mismatch: {orig.shape} vs {reloaded.shape}")

            for col in orig.columns:
                if col in ["period", "variant"]:
                    assert (orig[col].values == reloaded[col].values).all(), f"Mismatch in {col}"
                elif orig[col].dtype == bool:
                    assert (orig[col].values == reloaded[col].values).all(), f"Mismatch in {col}"
                else:
                    o_vals = orig[col].values.astype(float)
                    r_vals = reloaded[col].values.astype(float)
                    assert np.allclose(o_vals, r_vals, atol=tol), f"Mismatch in {col}"
            parity_confirmed = True

        audit_results[v] = {
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
# 6. Master End-to-End Pipeline Function
# =====================================================================

def run_portfolio_backtest_pipeline(
    schedule_dir: Optional[Union[str, Path]] = None,
    price_dir: Optional[Union[str, Path]] = None,
    prob_path: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Path], Dict[str, Any]]:
    """
    Execute full Phase 10.3 portfolio backtest pipeline:
      1. Load schedules, aligned prices, and probabilities.
      2. Simulate all four variants (1A, 1B, 2A, 2B).
      3. Verify exact attribution and interval counts.
      4. Persist daily simulations to Apache Parquet format.
      5. Reload and verify Parquet file integrity and parity.

    Returns:
      Tuple of (simulations_dict, saved_paths_dict, audit_metadata_dict).
    """
    schedules, price_df, prob_df = load_backtest_inputs(
        schedule_dir=schedule_dir,
        price_dir=price_dir,
        prob_path=prob_path,
    )

    simulations = run_all_simulations(
        schedules=schedules,
        price_df=price_df,
        prob_df=prob_df,
        cost_rate=cost_rate,
    )

    saved_paths = save_simulation_parquet(simulations, output_dir=output_dir)
    audit_meta = reload_and_verify_parquet(saved_paths, original_simulations=simulations)

    metrics_table = generate_metrics_table(simulations)

    pipeline_metadata = {
        "parquet_audit": audit_meta,
        "metrics_summary": metrics_table.to_dict(orient="records"),
    }

    return simulations, saved_paths, pipeline_metadata
