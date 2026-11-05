"""
Comparative Performance Evaluation Engine for ML-Based Sector Rotation Regime Discovery
in the Indian Equity Market (Phase 10.5).

Implements rigorous, multi-period comparative evaluation across six portfolios:
  - Strategy 1A: ML Equal-Weight (Top 2 Sectors, Cash OFF)
  - Strategy 1B: ML Inverse-Volatility (Top 2 Sectors, Cash OFF)
  - Strategy 2A: ML Equal-Weight + Cash (Top 2 Sectors + 33.3% Cash)
  - Strategy 2B: ML Inverse-Volatility + Cash (Top 2 Sectors + 33.3% Cash)
  - Benchmark A: NIFTY 50 Price Return Index Buy & Hold (0 bps)
  - Benchmark B: Equal-Weight Six-Sector Portfolio (Monthly rebalance, 15 bps)

Evaluation Windows:
  - Training Period: 2019-11-01 to 2024-12-31 (N = 1,264 daily return intervals)
  - Holdout Period:  2025-01-02 to 2026-09-18 (N = 422 daily return intervals)
  - Full Period:     2019-11-01 to 2026-09-18 (N = 1,686 daily return intervals)

All metrics, conventions, and regression identities adhere to the Phase 10.5 approved specification.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import scipy.stats as stats

logger = logging.getLogger(__name__)

# Canonical project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SIMULATION_DIR = PROJECT_ROOT / "results" / "portfolio_backtest"
DEFAULT_OUTPUT_DIR = DEFAULT_SIMULATION_DIR / "comparative_evaluation"

# Universal timeline constants
ANNUALIZATION_FACTOR: float = 252.0
EXPECTED_PRICE_SESSIONS: int = 1687
EXPECTED_TOTAL_RETURN_INTERVALS: int = 1686
EXPECTED_TRAIN_RETURN_INTERVALS: int = 1264
EXPECTED_HOLDOUT_RETURN_INTERVALS: int = 422

EXPECTED_TRAIN_START: str = "2019-11-01"
EXPECTED_TRAIN_END: str = "2024-12-31"
EXPECTED_HOLDOUT_START: str = "2025-01-02"
EXPECTED_HOLDOUT_END: str = "2026-09-18"

PERIOD_COUNTS: Dict[str, int] = {
    "train": EXPECTED_TRAIN_RETURN_INTERVALS,
    "holdout": EXPECTED_HOLDOUT_RETURN_INTERVALS,
    "full": EXPECTED_TOTAL_RETURN_INTERVALS,
}

PERIOD_RANGES: Dict[str, Tuple[str, str]] = {
    "train": (EXPECTED_TRAIN_START, EXPECTED_TRAIN_END),
    "holdout": (EXPECTED_HOLDOUT_START, EXPECTED_HOLDOUT_END),
    "full": (EXPECTED_TRAIN_START, EXPECTED_HOLDOUT_END),
}

# Portfolio metadata mapping
STRATEGY_KEYS: List[str] = ["1A", "1B", "2A", "2B"]
BENCHMARK_KEYS: List[str] = ["NIFTY50", "EQUAL_WEIGHT"]
ALL_PORTFOLIO_KEYS: List[str] = STRATEGY_KEYS + BENCHMARK_KEYS

PORTFOLIO_NAMES: Dict[str, str] = {
    "1A": "Strategy 1A (ML EW)",
    "1B": "Strategy 1B (ML Inv-Vol)",
    "2A": "Strategy 2A (ML EW + Cash)",
    "2B": "Strategy 2B (ML Inv-Vol + Cash)",
    "NIFTY50": "NIFTY 50 Buy & Hold",
    "EQUAL_WEIGHT": "Equal-Weight Six-Sector",
}

PORTFOLIO_FILENAMES: Dict[str, str] = {
    "1A": "daily_simulation_1A.parquet",
    "1B": "daily_simulation_1B.parquet",
    "2A": "daily_simulation_2A.parquet",
    "2B": "daily_simulation_2B.parquet",
    "NIFTY50": "daily_simulation_benchmark_nifty50.parquet",
    "EQUAL_WEIGHT": "daily_simulation_benchmark_equal_weight.parquet",
}


# =====================================================================
# 1. Mathematical Core: Drawdown & Regression Helpers
# =====================================================================

def compute_drawdown_metrics(
    cum_nav_series: Union[np.ndarray, pd.Series],
    tol: float = 1e-7,
) -> Tuple[float, int, str, int]:
    """
    Compute Maximum Drawdown (MDD), Maximum Underwater Duration, Terminal Status,
    and Count of Drawdown Episodes.

    Args:
      cum_nav_series: Array-like sequence of cumulative NAV values.
      tol: Numerical comparison tolerance for peak recovery.

    Returns:
      Tuple of (mdd, max_duration_sessions, terminal_status, episode_count):
        - mdd: float, minimum drawdown in [min_dd, 0.0].
        - max_duration_sessions: int, maximum consecutive sessions spent below running peak.
        - terminal_status: str, 'recovered' if ending NAV >= peak, else 'unrecovered'.
        - episode_count: int, count of distinct contiguous periods where NAV < peak.
    """
    nav = np.asarray(cum_nav_series, dtype=float)
    N = len(nav)
    if N == 0:
        return 0.0, 0, "recovered", 0

    peaks = np.maximum.accumulate(nav)
    # Relative drawdown: (NAV - Peak) / Peak
    dds = (nav - peaks) / peaks
    mdd = float(np.min(dds))

    # An underwater session occurs strictly when drawdown is below -tol
    is_underwater = dds < -tol

    episodes = 0
    max_duration = 0
    current_duration = 0

    for t in range(N):
        if is_underwater[t]:
            current_duration += 1
            if current_duration > max_duration:
                max_duration = current_duration
            if t == 0 or not is_underwater[t - 1]:
                episodes += 1
        else:
            current_duration = 0

    terminal_status = "unrecovered" if is_underwater[-1] else "recovered"
    return mdd, max_duration, terminal_status, episodes


def compute_regression_alpha_beta(
    r_strategy: np.ndarray,
    r_benchmark: np.ndarray,
    ann_factor: float = ANNUALIZATION_FACTOR,
) -> Dict[str, float]:
    """
    Perform single-factor OLS regression of net strategy returns on benchmark returns:
      R_strategy,t = alpha_daily + beta * R_benchmark,t + epsilon_t

    Computes Beta, Annualized Jensen's Alpha, Standard Errors, p-values, and R-squared.

    Args:
      r_strategy: Array of daily net strategy returns.
      r_benchmark: Array of daily net benchmark returns.
      ann_factor: Annualization factor (252.0).

    Returns:
      Dict[str, float] with keys:
        beta, beta_stderr, beta_pvalue,
        alpha_daily, alpha_annualized, alpha_annualized_pct,
        alpha_stderr, alpha_annualized_stderr, alpha_pvalue,
        r_squared
    """
    y = np.asarray(r_strategy, dtype=float)
    x = np.asarray(r_benchmark, dtype=float)
    N = len(y)

    if N != len(x):
        raise ValueError(f"Length mismatch: len(y)={len(y)}, len(x)={len(x)}.")

    if N < 3:
        raise ValueError(f"Regression requires at least 3 observations (got {N}).")

    var_x = float(np.var(x, ddof=1))
    var_y = float(np.var(y, ddof=1))

    # Guard against zero-variance benchmark (e.g. constant return)
    if np.isclose(var_x, 0.0, atol=1e-14):
        return {
            "beta": 0.0,
            "beta_stderr": 0.0,
            "beta_pvalue": 1.0,
            "alpha_daily": float(np.mean(y)),
            "alpha_annualized": float(np.mean(y) * ann_factor),
            "alpha_annualized_pct": float(np.mean(y) * ann_factor * 100.0),
            "alpha_stderr": 0.0,
            "alpha_annualized_stderr": 0.0,
            "alpha_pvalue": 1.0,
            "r_squared": 0.0,
        }

    # Use scipy.stats.linregress for exact OLS solution
    res = stats.linregress(x, y)
    beta = float(res.slope)
    alpha_daily = float(res.intercept)
    alpha_ann = float(alpha_daily * ann_factor)
    alpha_ann_pct = float(alpha_ann * 100.0)

    beta_stderr = float(res.stderr) if res.stderr is not None else 0.0
    beta_pvalue = float(res.pvalue) if res.pvalue is not None else 1.0

    alpha_stderr = float(res.intercept_stderr) if res.intercept_stderr is not None else 0.0
    alpha_ann_stderr = float(alpha_stderr * ann_factor)

    if alpha_stderr > 0.0:
        t_alpha = alpha_daily / alpha_stderr
        alpha_pvalue = float(2.0 * (1.0 - stats.t.cdf(abs(t_alpha), df=N - 2)))
    else:
        alpha_pvalue = 1.0

    r_squared = float(res.rvalue ** 2) if var_y > 1e-14 else 0.0

    return {
        "beta": beta,
        "beta_stderr": beta_stderr,
        "beta_pvalue": beta_pvalue,
        "alpha_daily": alpha_daily,
        "alpha_annualized": alpha_ann,
        "alpha_annualized_pct": alpha_ann_pct,
        "alpha_stderr": alpha_stderr,
        "alpha_annualized_stderr": alpha_ann_stderr,
        "alpha_pvalue": alpha_pvalue,
        "r_squared": r_squared,
    }


# =====================================================================
# 2. Input Loading & Verification
# =====================================================================

def load_all_simulations(
    sim_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Load all six canonical daily simulation Parquet artifacts and verify alignment.

    Args:
      sim_dir: Directory containing simulation Parquet files.

    Returns:
      Dict[str, pd.DataFrame]: Mapping of portfolio key ('1A', '1B', etc.) to daily simulation DataFrame.

    Raises:
      FileNotFoundError: If any simulation file is missing.
      ValueError: If date indices or period partitions do not match.
    """
    s_dir = Path(sim_dir) if sim_dir is not None else DEFAULT_SIMULATION_DIR

    simulations: Dict[str, pd.DataFrame] = {}
    base_idx: Optional[pd.DatetimeIndex] = None

    for key in ALL_PORTFOLIO_KEYS:
        fname = PORTFOLIO_FILENAMES[key]
        fpath = s_dir / fname
        if not fpath.exists():
            raise FileNotFoundError(f"Missing canonical simulation file: {fpath}")

        df = pd.read_parquet(fpath)

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(f"Simulation {key} index must be DatetimeIndex.")
        if not df.index.is_monotonic_increasing:
            raise ValueError(f"Simulation {key} index must be monotonically increasing.")
        if len(df) != EXPECTED_TOTAL_RETURN_INTERVALS:
            raise ValueError(
                f"Simulation {key} expected {EXPECTED_TOTAL_RETURN_INTERVALS} rows, got {len(df)}."
            )

        if base_idx is None:
            base_idx = df.index
        else:
            if not df.index.equals(base_idx):
                raise ValueError(f"Date index mismatch in simulation {key} against base index.")

        simulations[key] = df

    return simulations


# =====================================================================
# 3. Primary Comparative Metrics Table (18 Rows)
# =====================================================================

def compute_single_portfolio_metrics(
    daily_df: pd.DataFrame,
    period: str,
    portfolio_key: str,
    portfolio_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute full set of primary performance, risk, and trading efficiency metrics
    for a single portfolio over a designated period ('train', 'holdout', 'full').

    Args:
      daily_df: Daily simulation DataFrame.
      period: Evaluation window: 'train', 'holdout', or 'full'.
      portfolio_key: Short key ('1A', '1B', '2A', '2B', 'NIFTY50', 'EQUAL_WEIGHT').
      portfolio_name: Optional full display name.

    Returns:
      Dict[str, Any]: Comprehensive metrics dictionary.
    """
    if period not in PERIOD_COUNTS:
        raise ValueError(f"Invalid period '{period}'. Expected 'train', 'holdout', or 'full'.")

    expected_n = PERIOD_COUNTS[period]
    sub = daily_df if period == "full" else daily_df[daily_df["period"] == period]
    N = len(sub)

    if N != expected_n:
        raise ValueError(f"Period '{period}' expected {expected_n} intervals, got {N}.")

    p_name = portfolio_name if portfolio_name is not None else PORTFOLIO_NAMES.get(portfolio_key, portfolio_key)
    start_date = str(sub.index.min().date())
    end_date = str(sub.index.max().date())

    # NAV Endpoints
    if period == "train":
        nav_start_net = 1.0
        nav_end_net = float(sub["net_nav"].iloc[-1])
        nav_start_gross = 1.0
        nav_end_gross = float(sub["gross_nav"].iloc[-1])
    elif period == "holdout":
        train_sub = daily_df[daily_df["period"] == "train"]
        nav_start_net = float(train_sub["net_nav"].iloc[-1]) if len(train_sub) > 0 else 1.0
        nav_end_net = float(sub["net_nav"].iloc[-1])
        nav_start_gross = float(train_sub["gross_nav"].iloc[-1]) if len(train_sub) > 0 else 1.0
        nav_end_gross = float(sub["gross_nav"].iloc[-1])
    else:  # full
        nav_start_net = 1.0
        nav_end_net = float(sub["net_nav"].iloc[-1])
        nav_start_gross = 1.0
        nav_end_gross = float(sub["gross_nav"].iloc[-1])

    # 1. Performance
    tr_gross = float((nav_end_gross / nav_start_gross) - 1.0)
    tr_net = float((nav_end_net / nav_start_net) - 1.0)

    cagr_gross = float((nav_end_gross / nav_start_gross) ** (ANNUALIZATION_FACTOR / N) - 1.0)
    cagr_net = float((nav_end_net / nav_start_net) ** (ANNUALIZATION_FACTOR / N) - 1.0)
    cagr_cost_drag = float(cagr_gross - cagr_net)

    # 2. Risk Metrics
    r_net = sub["net_return"].values.astype(float)
    mean_daily_net = float(np.mean(r_net))
    ann_mean_return = float(mean_daily_net * ANNUALIZATION_FACTOR)

    ann_vol = float(np.std(r_net, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR))

    # Sharpe Ratio (Rf = 0%)
    sharpe = float(ann_mean_return / ann_vol) if ann_vol > 0.0 else 0.0

    # Downside Deviation & Sortino Ratio (MAR = 0%)
    downside_sq = np.minimum(0.0, r_net) ** 2
    downside_dev = float(np.sqrt(np.mean(downside_sq)) * np.sqrt(ANNUALIZATION_FACTOR))
    sortino = float(ann_mean_return / downside_dev) if downside_dev > 0.0 else 0.0

    # Drawdown metrics (holdout rebased to 1.0)
    if period == "holdout":
        cum_nav_series = np.cumprod(1.0 + r_net)
    else:
        cum_nav_series = sub["net_nav"].values / nav_start_net

    mdd, max_dur, term_status, episodes = compute_drawdown_metrics(cum_nav_series)

    # 3. Trading Activity and Costs
    cum_to = float(sub["actual_turnover"].sum())
    ann_to = float(cum_to * (ANNUALIZATION_FACTOR / N))
    rebal_count = int(sub["rebalance_executed"].sum())
    avg_to_rebal = float(cum_to / rebal_count) if rebal_count > 0 else np.nan
    avg_daily_to = float(cum_to / N)
    cum_tc = float(sub["transaction_cost"].sum())

    return {
        "portfolio_key": portfolio_key,
        "portfolio": p_name,
        "period": period,
        "sample_count": N,
        "start_date": start_date,
        "end_date": end_date,
        # Performance
        "total_return_gross_pct": tr_gross * 100.0,
        "total_return_net_pct": tr_net * 100.0,
        "cagr_gross_pct": cagr_gross * 100.0,
        "cagr_net_pct": cagr_net * 100.0,
        "cagr_cost_drag_pct": cagr_cost_drag * 100.0,
        # Risk
        "ann_volatility_pct": ann_vol * 100.0,
        "max_drawdown_pct": mdd * 100.0,
        "max_drawdown_duration": max_dur,
        "terminal_drawdown_status": term_status,
        "drawdown_episodes": episodes,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "downside_deviation_pct": downside_dev * 100.0,
        # Trading Activity & Costs
        "cum_actual_turnover": cum_to,
        "ann_actual_turnover": ann_to,
        "avg_turnover_per_rebalance": avg_to_rebal,
        "avg_daily_turnover": avg_daily_to,
        "cum_transaction_costs": cum_tc,
        "rebalances_executed": rebal_count,
    }


def compute_comparative_metrics_table(
    simulations: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Compile the canonical 18-row primary comparative metrics table:
      6 Portfolios x 3 Evaluation Periods = 18 Rows.

    Args:
      simulations: Dict of all six loaded simulation DataFrames.

    Returns:
      pd.DataFrame: 18-row comparative evaluation table.
    """
    rows: List[Dict[str, Any]] = []

    for p_key in ALL_PORTFOLIO_KEYS:
        df = simulations[p_key]
        for p in ["train", "holdout", "full"]:
            rec = compute_single_portfolio_metrics(
                daily_df=df,
                period=p,
                portfolio_key=p_key,
            )
            rows.append(rec)

    metrics_df = pd.DataFrame(rows)
    return metrics_df


# =====================================================================
# 4. Relative Performance & Benchmark-Risk Analysis (24 Rows)
# =====================================================================

def compute_single_relative_metrics(
    strat_df: pd.DataFrame,
    bench_df: pd.DataFrame,
    period: str,
    strat_key: str,
    bench_key: str,
) -> Dict[str, Any]:
    """
    Compute active, tracking, information, and regression metrics (Alpha, Beta, R^2)
    for a single strategy vs benchmark pair over a given evaluation period.

    Args:
      strat_df: Strategy daily simulation DataFrame.
      bench_df: Benchmark daily simulation DataFrame.
      period: 'train', 'holdout', or 'full'.
      strat_key: Strategy identifier ('1A', '1B', '2A', '2B').
      bench_key: Benchmark identifier ('NIFTY50', 'EQUAL_WEIGHT').

    Returns:
      Dict[str, Any]: Comprehensive relative performance dictionary.
    """
    expected_n = PERIOD_COUNTS[period]
    sub_s = strat_df if period == "full" else strat_df[strat_df["period"] == period]
    sub_b = bench_df if period == "full" else bench_df[bench_df["period"] == period]

    N = len(sub_s)
    if N != expected_n or len(sub_b) != expected_n:
        raise ValueError(f"Period '{period}' expected {expected_n} sessions, got s={N}, b={len(sub_b)}.")

    # Returns arrays
    r_s = sub_s["net_return"].values.astype(float)
    r_b = sub_b["net_return"].values.astype(float)

    # NAV endpoints for Total Return & CAGR
    if period == "train":
        nav_s_0, nav_s_T = 1.0, float(sub_s["net_nav"].iloc[-1])
        nav_b_0, nav_b_T = 1.0, float(sub_b["net_nav"].iloc[-1])
    elif period == "holdout":
        tr_s = strat_df[strat_df["period"] == "train"]
        tr_b = bench_df[bench_df["period"] == "train"]
        nav_s_0 = float(tr_s["net_nav"].iloc[-1]) if len(tr_s) > 0 else 1.0
        nav_s_T = float(sub_s["net_nav"].iloc[-1])
        nav_b_0 = float(tr_b["net_nav"].iloc[-1]) if len(tr_b) > 0 else 1.0
        nav_b_T = float(sub_b["net_nav"].iloc[-1])
    else:  # full
        nav_s_0, nav_s_T = 1.0, float(sub_s["net_nav"].iloc[-1])
        nav_b_0, nav_b_T = 1.0, float(sub_b["net_nav"].iloc[-1])

    tr_s_net = (nav_s_T / nav_s_0) - 1.0
    tr_b_net = (nav_b_T / nav_b_0) - 1.0

    cagr_s_net = (nav_s_T / nav_s_0) ** (ANNUALIZATION_FACTOR / N) - 1.0
    cagr_b_net = (nav_b_T / nav_b_0) ** (ANNUALIZATION_FACTOR / N) - 1.0

    # 1. Active Performance
    arith_excess_tr = tr_s_net - tr_b_net
    geom_rel_wealth = ((1.0 + tr_s_net) / (1.0 + tr_b_net)) - 1.0
    cagr_spread = cagr_s_net - cagr_b_net

    # Daily active returns: d_t = r_strat,t - r_bench,t
    d = r_s - r_b
    mean_d = float(np.mean(d))
    ann_arith_active_ret = float(mean_d * ANNUALIZATION_FACTOR)

    # Tracking Error
    te = float(np.std(d, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR))

    # Information Ratio (0.0 if TE == 0)
    ir = float(ann_arith_active_ret / te) if te > 0.0 else 0.0

    # 2. Alpha, Beta, R^2 Regression Analysis
    reg = compute_regression_alpha_beta(r_s, r_b, ann_factor=ANNUALIZATION_FACTOR)

    strat_name = PORTFOLIO_NAMES.get(strat_key, strat_key)
    bench_name = PORTFOLIO_NAMES.get(bench_key, bench_key)

    return {
        "strategy": strat_key,
        "strategy_name": strat_name,
        "benchmark": bench_key,
        "benchmark_name": bench_name,
        "period": period,
        "sample_count": N,
        # Active Performance
        "arithmetic_excess_total_return_pct": arith_excess_tr * 100.0,
        "geometric_relative_wealth_pct": geom_rel_wealth * 100.0,
        "annualized_arithmetic_active_return_pct": ann_arith_active_ret * 100.0,
        "cagr_spread_pct": cagr_spread * 100.0,
        "tracking_error_pct": te * 100.0,
        "information_ratio": ir,
        # Alpha, Beta, R^2
        "beta": reg["beta"],
        "beta_stderr": reg["beta_stderr"],
        "beta_pvalue": reg["beta_pvalue"],
        "alpha_daily": reg["alpha_daily"],
        "alpha_annualized": reg["alpha_annualized"],
        "alpha_annualized_pct": reg["alpha_annualized_pct"],
        "alpha_stderr": reg["alpha_stderr"],
        "alpha_annualized_stderr": reg["alpha_annualized_stderr"],
        "alpha_pvalue": reg["alpha_pvalue"],
        "r_squared": reg["r_squared"],
    }


def compute_relative_performance_matrix(
    simulations: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Compile the canonical 24-row relative performance and benchmark-risk matrix:
      4 Strategies x 2 Benchmarks x 3 Evaluation Periods = 24 Rows.

    Directly embeds Alpha, Beta, and R^2 as mandatory primary comparative metrics.

    Args:
      simulations: Dict of all six loaded simulation DataFrames.

    Returns:
      pd.DataFrame: 24-row relative performance matrix.
    """
    rows: List[Dict[str, Any]] = []

    for s_key in STRATEGY_KEYS:
        strat_df = simulations[s_key]
        for b_key in BENCHMARK_KEYS:
            bench_df = simulations[b_key]
            for p in ["train", "holdout", "full"]:
                rec = compute_single_relative_metrics(
                    strat_df=strat_df,
                    bench_df=bench_df,
                    period=p,
                    strat_key=s_key,
                    bench_key=b_key,
                )
                rows.append(rec)

    matrix_df = pd.DataFrame(rows)
    return matrix_df


# =====================================================================
# 5. Pipeline Orchestration & Output Generation
# =====================================================================

def run_comparative_evaluation(
    sim_dir: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Execute full Phase 10.5 comparative performance evaluation pipeline:
      1. Load and verify all six simulation artifacts.
      2. Compute 18-row primary comparative metrics table.
      3. Compute 24-row relative performance matrix (with Alpha, Beta, R^2).
      4. Export both tables to CSV and Parquet in results/portfolio_backtest/comparative_evaluation/.

    Returns:
      Tuple of (primary_metrics_df, relative_matrix_df).
    """
    out_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading canonical daily simulations...")
    simulations = load_all_simulations(sim_dir=sim_dir)

    logger.info("Computing 18-row primary comparative metrics table...")
    primary_df = compute_comparative_metrics_table(simulations)

    logger.info("Computing 24-row relative performance matrix...")
    relative_df = compute_relative_performance_matrix(simulations)

    # Export Primary Comparative Metrics
    primary_csv = out_dir / "comparative_metrics_table.csv"
    primary_parquet = out_dir / "comparative_metrics_table.parquet"
    primary_df.to_csv(primary_csv, index=False)
    primary_df.to_parquet(primary_parquet, index=False)
    logger.info(f"Saved primary metrics to {primary_csv} and {primary_parquet}")

    # Export Relative Performance Matrix
    relative_csv = out_dir / "relative_performance_matrix.csv"
    relative_parquet = out_dir / "relative_performance_matrix.parquet"
    relative_df.to_csv(relative_csv, index=False)
    relative_df.to_parquet(relative_parquet, index=False)
    logger.info(f"Saved relative performance matrix to {relative_csv} and {relative_parquet}")

    return primary_df, relative_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_comparative_evaluation()

