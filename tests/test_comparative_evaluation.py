"""
Unit and Integration Test Suite for Comparative Performance Evaluation (Phase 10.5).

Verifies the mathematical rigor, row counts, boundary isolation, and statistical
correctness of `src/comparative_evaluation.py` and its generated artifacts.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import scipy.stats as stats

from src.comparative_evaluation import (
    ANNUALIZATION_FACTOR,
    BENCHMARK_KEYS,
    DEFAULT_OUTPUT_DIR,
    EXPECTED_HOLDOUT_RETURN_INTERVALS,
    EXPECTED_TOTAL_RETURN_INTERVALS,
    EXPECTED_TRAIN_RETURN_INTERVALS,
    STRATEGY_KEYS,
    compute_comparative_metrics_table,
    compute_drawdown_metrics,
    compute_regression_alpha_beta,
    compute_relative_performance_matrix,
    compute_single_portfolio_metrics,
    compute_single_relative_metrics,
    load_all_simulations,
    run_comparative_evaluation,
)


@pytest.fixture(scope="module")
def simulations():
    """Load canonical simulations once for the test module."""
    return load_all_simulations()


@pytest.fixture(scope="module")
def primary_table(simulations):
    """Compute primary comparative metrics table."""
    return compute_comparative_metrics_table(simulations)


@pytest.fixture(scope="module")
def relative_matrix(simulations):
    """Compute relative performance matrix."""
    return compute_relative_performance_matrix(simulations)


# =====================================================================
# 1. Structural Invariants & Alignment Tests
# =====================================================================

def test_01_portfolio_and_period_counts(primary_table, relative_matrix):
    """Test exact row counts: exactly 18 for primary table and 24 for relative matrix."""
    assert len(primary_table) == 18, f"Primary table must have 18 rows, got {len(primary_table)}"
    assert len(relative_matrix) == 24, f"Relative matrix must have 24 rows, got {len(relative_matrix)}"

    # 6 portfolios x 3 periods = 18
    p_keys = set(primary_table["portfolio_key"].unique())
    assert p_keys == set(STRATEGY_KEYS + BENCHMARK_KEYS)
    assert set(primary_table["period"].unique()) == {"train", "holdout", "full"}

    # 4 strategies x 2 benchmarks x 3 periods = 24
    assert set(relative_matrix["strategy"].unique()) == set(STRATEGY_KEYS)
    assert set(relative_matrix["benchmark"].unique()) == set(BENCHMARK_KEYS)
    assert set(relative_matrix["period"].unique()) == {"train", "holdout", "full"}


def test_02_timeline_and_sample_counts(simulations):
    """Verify that all six portfolios share identical sample counts and monotonic DatetimeIndex."""
    base_idx = simulations["1A"].index
    assert len(base_idx) == EXPECTED_TOTAL_RETURN_INTERVALS == 1686
    assert base_idx.is_monotonic_increasing

    for key, df in simulations.items():
        assert df.index.equals(base_idx), f"Date index mismatch for {key}."
        assert len(df[df["period"] == "train"]) == EXPECTED_TRAIN_RETURN_INTERVALS == 1264
        assert len(df[df["period"] == "holdout"]) == EXPECTED_HOLDOUT_RETURN_INTERVALS == 422


def test_03_boundary_isolation(simulations):
    """Confirm that the 2024-12-31 to 2025-01-02 return belongs exclusively to holdout."""
    for key, df in simulations.items():
        assert df.loc["2024-12-31", "period"] == "train"
        assert df.loc["2025-01-02", "period"] == "holdout"

        train_end_nav = df.loc["2024-12-31", "net_nav"]
        holdout_start_ret = df.loc["2025-01-02", "net_return"]
        holdout_start_nav = df.loc["2025-01-02", "net_nav"]

        # Exact compounding across the boundary
        expected_holdout_start_nav = train_end_nav * (1.0 + holdout_start_ret)
        assert np.isclose(holdout_start_nav, expected_holdout_start_nav, atol=1e-12)


# =====================================================================
# 2. Return & Compounding Mathematical Identities
# =====================================================================

def test_04_nav_compounding_reconciliation(simulations):
    """Verify that cumulative net returns compound to the reported net NAV for all 6 portfolios."""
    for key, df in simulations.items():
        cum_from_rets = np.cumprod(1.0 + df["net_return"].values)
        reported_nav = df["net_nav"].values
        max_diff = np.max(np.abs(cum_from_rets - reported_nav))
        assert max_diff < 1e-12, f"NAV compounding mismatch on {key}: {max_diff}"


def test_05_cagr_mathematical_identity(primary_table):
    """Verify CAGR identity: CAGR = (1 + Total Return)^(252 / N) - 1."""
    for _, row in primary_table.iterrows():
        tr_net = row["total_return_net_pct"] / 100.0
        n = row["sample_count"]
        expected_cagr = (1.0 + tr_net) ** (ANNUALIZATION_FACTOR / n) - 1.0
        actual_cagr = row["cagr_net_pct"] / 100.0
        assert np.isclose(actual_cagr, expected_cagr, atol=1e-10)

        # CAGR drag identity
        expected_drag = row["cagr_gross_pct"] - row["cagr_net_pct"]
        assert np.isclose(row["cagr_cost_drag_pct"], expected_drag, atol=1e-10)


# =====================================================================
# 3. Risk & Drawdown Metric Tests
# =====================================================================

def test_06_drawdown_metrics_unit():
    """Unit test compute_drawdown_metrics with deterministic synthetic NAV series."""
    # NAV sequence: 1.0, 1.2, 0.9 (DD = -25%), 1.1, 1.25 (new peak), 1.0 (DD = -20%), 1.05
    nav = np.array([1.0, 1.2, 0.9, 1.1, 1.25, 1.0, 1.05])
    mdd, max_dur, term_status, episodes = compute_drawdown_metrics(nav)

    # First drawdown: 0.9 / 1.2 - 1 = -0.25 (-25%)
    # Second drawdown: 1.0 / 1.25 - 1 = -0.20 (-20%)
    assert np.isclose(mdd, -0.25)
    # Episode 1: indices 2 and 3 (duration = 2)
    # Episode 2: indices 5 and 6 (duration = 2)
    assert max_dur == 2
    assert term_status == "unrecovered"
    assert episodes == 2


def test_07_drawdown_rebasing_isolation(simulations, primary_table):
    """Confirm holdout drawdown uses NAV rebased to 1.0 and does not mix training history."""
    for key in STRATEGY_KEYS + BENCHMARK_KEYS:
        df = simulations[key]
        holdout_sub = df[df["period"] == "holdout"]
        holdout_rets = holdout_sub["net_return"].values
        rebased_nav = np.cumprod(1.0 + holdout_rets)

        mdd, max_dur, term_status, episodes = compute_drawdown_metrics(rebased_nav)

        row = primary_table[(primary_table["portfolio_key"] == key) & (primary_table["period"] == "holdout")].iloc[0]
        assert np.isclose(row["max_drawdown_pct"], mdd * 100.0, atol=1e-6)
        assert row["max_drawdown_duration"] == max_dur
        assert row["terminal_drawdown_status"] == term_status
        assert row["drawdown_episodes"] == episodes


def test_08_sharpe_and_sortino_formulas(primary_table, simulations):
    """Verify that Sharpe and Sortino ratios match their exact definitions."""
    for _, row in primary_table.iterrows():
        key = row["portfolio_key"]
        p = row["period"]
        df = simulations[key]
        sub = df if p == "full" else df[df["period"] == p]
        r = sub["net_return"].values

        # Annualized Volatility
        vol = float(np.std(r, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR))
        assert np.isclose(row["ann_volatility_pct"], vol * 100.0, atol=1e-8)

        # Sharpe
        ann_mean = float(np.mean(r) * ANNUALIZATION_FACTOR)
        expected_sharpe = ann_mean / vol if vol > 0 else 0.0
        assert np.isclose(row["sharpe_ratio"], expected_sharpe, atol=1e-8)

        # Sortino
        downside_sq = np.minimum(0.0, r) ** 2
        down_dev = float(np.sqrt(np.mean(downside_sq)) * np.sqrt(ANNUALIZATION_FACTOR))
        assert np.isclose(row["downside_deviation_pct"], down_dev * 100.0, atol=1e-8)
        expected_sortino = ann_mean / down_dev if down_dev > 0 else 0.0
        assert np.isclose(row["sortino_ratio"], expected_sortino, atol=1e-8)


# =====================================================================
# 4. Trading Activity & Turnover Invariants
# =====================================================================

def test_09_turnover_metrics_invariants(primary_table):
    """Verify turnover definitions and buy-and-hold invariants."""
    # NIFTY 50 Buy and Hold must have zero turnover and zero transaction costs
    n50_rows = primary_table[primary_table["portfolio_key"] == "NIFTY50"]
    for _, row in n50_rows.iterrows():
        assert row["cum_actual_turnover"] == 0.0
        assert row["ann_actual_turnover"] == 0.0
        assert np.isnan(row["avg_turnover_per_rebalance"])
        assert row["avg_daily_turnover"] == 0.0
        assert row["cum_transaction_costs"] == 0.0
        assert row["rebalances_executed"] == 0

    # Strategy 1A full period turnover check
    s1a_full = primary_table[(primary_table["portfolio_key"] == "1A") & (primary_table["period"] == "full")].iloc[0]
    assert s1a_full["cum_actual_turnover"] > 50.0
    assert np.isclose(
        s1a_full["ann_actual_turnover"],
        s1a_full["cum_actual_turnover"] * (ANNUALIZATION_FACTOR / 1686),
    )
    assert np.isclose(
        s1a_full["avg_turnover_per_rebalance"],
        s1a_full["cum_actual_turnover"] / s1a_full["rebalances_executed"],
    )


# =====================================================================
# 5. Relative Performance & Active Metrics
# =====================================================================

def test_10_active_performance_identities(relative_matrix, primary_table):
    """Verify active return, tracking error, and information ratio identities."""
    for _, row in relative_matrix.iterrows():
        strat = row["strategy"]
        bench = row["benchmark"]
        p = row["period"]

        p_s = primary_table[(primary_table["portfolio_key"] == strat) & (primary_table["period"] == p)].iloc[0]
        p_b = primary_table[(primary_table["portfolio_key"] == bench) & (primary_table["period"] == p)].iloc[0]

        # Arithmetic Excess Total Return
        expected_arith_tr = p_s["total_return_net_pct"] - p_b["total_return_net_pct"]
        assert np.isclose(row["arithmetic_excess_total_return_pct"], expected_arith_tr, atol=1e-8)

        # Geometric Relative Wealth
        tr_s = p_s["total_return_net_pct"] / 100.0
        tr_b = p_b["total_return_net_pct"] / 100.0
        expected_geom = ((1.0 + tr_s) / (1.0 + tr_b) - 1.0) * 100.0
        assert np.isclose(row["geometric_relative_wealth_pct"], expected_geom, atol=1e-8)

        # CAGR spread
        expected_cagr_spread = p_s["cagr_net_pct"] - p_b["cagr_net_pct"]
        assert np.isclose(row["cagr_spread_pct"], expected_cagr_spread, atol=1e-8)

        # Information Ratio = Active Return / Tracking Error
        te = row["tracking_error_pct"]
        act_ret = row["annualized_arithmetic_active_return_pct"]
        expected_ir = act_ret / te if te > 0 else 0.0
        assert np.isclose(row["information_ratio"], expected_ir, atol=1e-8)


# =====================================================================
# 6. Alpha, Beta, and R² Regression Correctness
# =====================================================================

def test_11_regression_alpha_beta_math():
    """Unit test compute_regression_alpha_beta against independent analytical formulas."""
    np.random.seed(42)
    x = np.random.normal(0.0005, 0.01, 500)
    # y has true beta=1.2, true daily alpha=0.0003
    noise = np.random.normal(0, 0.005, 500)
    y = 0.0003 + 1.2 * x + noise

    res = compute_regression_alpha_beta(y, x)

    # Independent calculations
    cov_xy = np.cov(x, y, ddof=1)[0, 1]
    var_x = np.var(x, ddof=1)
    indep_beta = cov_xy / var_x
    indep_alpha_daily = np.mean(y) - indep_beta * np.mean(x)
    indep_r2 = (np.corrcoef(x, y)[0, 1]) ** 2

    assert np.isclose(res["beta"], indep_beta, atol=1e-12)
    assert np.isclose(res["alpha_daily"], indep_alpha_daily, atol=1e-12)
    assert np.isclose(res["alpha_annualized"], indep_alpha_daily * 252.0, atol=1e-12)
    assert np.isclose(res["r_squared"], indep_r2, atol=1e-12)


def test_12_alpha_beta_all_24_combinations(relative_matrix, simulations):
    """Independently verify Alpha, Beta, and R² across all 24 combinations in relative_matrix."""
    for _, row in relative_matrix.iterrows():
        s_key = row["strategy"]
        b_key = row["benchmark"]
        p = row["period"]

        df_s = simulations[s_key]
        df_b = simulations[b_key]

        sub_s = df_s if p == "full" else df_s[df_s["period"] == p]
        sub_b = df_b if p == "full" else df_b[df_b["period"] == p]

        y = sub_s["net_return"].values
        x = sub_b["net_return"].values

        lin = stats.linregress(x, y)
        assert np.isclose(row["beta"], lin.slope, atol=1e-10)
        assert np.isclose(row["alpha_daily"], lin.intercept, atol=1e-10)
        assert np.isclose(row["alpha_annualized"], lin.intercept * 252.0, atol=1e-10)
        assert np.isclose(row["r_squared"], lin.rvalue ** 2, atol=1e-10)
        assert np.isclose(row["beta_stderr"], lin.stderr, atol=1e-10)
        assert np.isclose(row["alpha_stderr"], lin.intercept_stderr, atol=1e-10)


def test_13_zero_variance_guard():
    """Verify safe zero-denominator handling when benchmark variance is zero."""
    x_const = np.zeros(100)
    y = np.random.normal(0.001, 0.01, 100)
    res = compute_regression_alpha_beta(y, x_const)

    assert res["beta"] == 0.0
    assert np.isclose(res["alpha_daily"], np.mean(y))
    assert res["r_squared"] == 0.0


# =====================================================================
# 7. Output Files & Schema Verification
# =====================================================================

def test_14_generated_artifacts_integrity():
    """Verify that all generated CSV and Parquet files exist, load cleanly, and have valid types."""
    out_dir = DEFAULT_OUTPUT_DIR
    p_csv = out_dir / "comparative_metrics_table.csv"
    p_parquet = out_dir / "comparative_metrics_table.parquet"
    r_csv = out_dir / "relative_performance_matrix.csv"
    r_parquet = out_dir / "relative_performance_matrix.parquet"

    assert p_csv.exists(), f"Missing {p_csv}"
    assert p_parquet.exists(), f"Missing {p_parquet}"
    assert r_csv.exists(), f"Missing {r_csv}"
    assert r_parquet.exists(), f"Missing {r_parquet}"

    df_p_csv = pd.read_csv(p_csv)
    df_p_pq = pd.read_parquet(p_parquet)
    df_r_csv = pd.read_csv(r_csv)
    df_r_pq = pd.read_parquet(r_parquet)

    assert len(df_p_csv) == len(df_p_pq) == 18
    assert len(df_r_csv) == len(df_r_pq) == 24

    # Verify no unexpected nulls (except avg_turnover_per_rebalance for Buy & Hold)
    assert df_p_csv.drop(columns=["avg_turnover_per_rebalance"]).isna().sum().sum() == 0
    assert df_r_csv.isna().sum().sum() == 0


def test_15_no_unintended_changes_to_canonical_artifacts():
    """Verify that original Phase 10.3 and benchmark simulation files were not altered."""
    sim_dir = Path("results/portfolio_backtest")
    canonical_files = [
        "daily_simulation_1A.parquet",
        "daily_simulation_1B.parquet",
        "daily_simulation_2A.parquet",
        "daily_simulation_2B.parquet",
        "daily_simulation_benchmark_nifty50.parquet",
        "daily_simulation_benchmark_equal_weight.parquet",
        "metrics_summary.csv",
        "metrics_summary.parquet",
        "benchmark_metrics_summary.csv",
        "benchmark_metrics_summary.parquet",
    ]
    for fname in canonical_files:
        fpath = sim_dir / fname
        assert fpath.exists(), f"Canonical file missing: {fpath}"
        # Ensure it has non-zero size
        assert fpath.stat().st_size > 0

