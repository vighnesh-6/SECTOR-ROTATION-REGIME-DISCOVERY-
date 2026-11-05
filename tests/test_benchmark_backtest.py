"""
Unit and integration tests for src/benchmark_backtest.py (Phase 10).

Validates:
  1. NIFTY 50 daily return calculation (P_t / P_{t-1} - 1).
  2. NIFTY 50 NAV calculation (geometric compounding).
  3. NIFTY 50 gross/net equality (gross NAV == net NAV everywhere).
  4. Equal-weight initial allocation (exactly 1/6 per sector).
  5. Equal-weight portfolio daily return (sum(w_hold * r)).
  6. Correct portfolio weight drift under multi-asset return differentials.
  7. Correct month-end signal generation (final trading session of calendar month).
  8. Correct next-session execution (execution at t+1 Close).
  9. First rebalance date verification (2019-11-29 signal -> 2019-12-02 execution).
  10. Actual one-way turnover calculation (0.5 * sum(|1/6 - w_drift|)).
  11. Transaction-cost calculation at 15 bps (NAV_pre * TO_actual * 0.0015).
  12. Gross/net NAV separation for Equal-Weight Benchmark.
  13. No transaction costs on non-rebalance sessions (TO == 0, TC == 0).
  14. No transaction costs at inception (Day 0 entry cost == 0).
  15. Weight simplex conservation (sum(w) == 1.0, w >= 0).
  16. No look-ahead bias in signal generation or return realization.
  17. Identical date alignment with strategy simulation outputs.
  18. Correct train/holdout boundary treatment (boundary return in holdout).
  19. Missing-data and malformed-input handling.
  20. Deterministic reproducibility across multiple simulation runs.
"""

import sys
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark_backtest import (
    DEFAULT_TRANSACTION_COST_RATE,
    EXPECTED_HOLDOUT_RETURN_INTERVALS,
    EXPECTED_TOTAL_RETURN_INTERVALS,
    EXPECTED_TRAIN_RETURN_INTERVALS,
    SECTOR_NAMES,
    compute_benchmark_metrics,
    generate_benchmark_metrics_table,
    get_month_end_signal_dates,
    load_benchmark_prices,
    reload_and_verify_benchmark_parquet,
    run_all_benchmarks,
    run_benchmark_pipeline,
    save_benchmark_parquet,
    simulate_equal_weight_benchmark,
    simulate_nifty50_benchmark,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def synthetic_calendar():
    """
    Create a controlled synthetic trading calendar spanning 2 calendar months
    (January and February 2024) with 10 business dates.
    Jan dates: 2024-01-26, 2024-01-29, 2024-01-30, 2024-01-31 (Month-end)
    Feb dates: 2024-02-01 (Month-start), 2024-02-02, 2024-02-05, 2024-02-06, 2024-02-07, 2024-02-08
    """
    dates = pd.to_datetime([
        "2024-01-26", "2024-01-29", "2024-01-30", "2024-01-31",
        "2024-02-01", "2024-02-02", "2024-02-05", "2024-02-06",
        "2024-02-07", "2024-02-08"
    ])
    return dates


@pytest.fixture
def synthetic_prices(synthetic_calendar):
    """
    Create synthetic prices for NIFTY 50 and the 6 sectors.
    Prices follow known deterministic geometric paths for exact manual verification.
    """
    n = len(synthetic_calendar)
    data = {}
    # NIFTY 50: constant 1% daily gain
    data["NIFTY50"] = 100.0 * (1.01 ** np.arange(n))
    # AUTO: +2% daily
    data["AUTO"] = 100.0 * (1.02 ** np.arange(n))
    # BANK: flat (0%)
    data["BANK"] = np.full(n, 100.0)
    # FMCG: -1% daily
    data["FMCG"] = 100.0 * (0.99 ** np.arange(n))
    # IT: +3% daily
    data["IT"] = 100.0 * (1.03 ** np.arange(n))
    # METAL: -2% daily
    data["METAL"] = 100.0 * (0.98 ** np.arange(n))
    # PHARMA: flat (0%)
    data["PHARMA"] = np.full(n, 100.0)

    return pd.DataFrame(data, index=synthetic_calendar)


# =====================================================================
# Unit Tests (1-20)
# =====================================================================

def test_1_nifty50_daily_return_calculation(synthetic_prices):
    """Verify NIFTY 50 daily return matches simple percentage change (P_t / P_{t-1} - 1)."""
    df_sim = simulate_nifty50_benchmark(synthetic_prices)

    for i in range(1, len(synthetic_prices)):
        p_prev = synthetic_prices["NIFTY50"].iloc[i - 1]
        p_curr = synthetic_prices["NIFTY50"].iloc[i]
        expected_r = (p_curr / p_prev) - 1.0

        dt = synthetic_prices.index[i]
        actual_r = df_sim.loc[dt, "gross_return"]
        assert np.isclose(actual_r, expected_r, atol=1e-12)
        assert np.isclose(df_sim.loc[dt, "r_NIFTY50"], expected_r, atol=1e-12)


def test_2_nifty50_nav_calculation(synthetic_prices):
    """Verify NIFTY 50 NAV compounds geometrically and equals P_t / P_0."""
    df_sim = simulate_nifty50_benchmark(synthetic_prices)

    p0 = synthetic_prices["NIFTY50"].iloc[0]
    for i in range(1, len(synthetic_prices)):
        dt = synthetic_prices.index[i]
        p_t = synthetic_prices["NIFTY50"].iloc[i]
        expected_nav = p_t / p0
        actual_nav = df_sim.loc[dt, "gross_nav"]
        assert np.isclose(actual_nav, expected_nav, atol=1e-12)


def test_3_nifty50_gross_net_equality(synthetic_prices):
    """Verify NIFTY 50 buy-and-hold has gross NAV == net NAV and 0 transaction costs everywhere."""
    df_sim = simulate_nifty50_benchmark(synthetic_prices)

    assert (df_sim["gross_nav"] == df_sim["net_nav"]).all()
    assert (df_sim["gross_return"] == df_sim["net_return"]).all()
    assert (df_sim["transaction_cost"] == 0.0).all()
    assert (df_sim["actual_turnover"] == 0.0).all()
    assert (df_sim["contrib_cost"] == 0.0).all()


def test_4_equal_weight_initial_allocation(synthetic_prices):
    """Verify Equal-Weight Benchmark begins with exactly 1/6 (approx 16.6667%) per sector."""
    df_sim = simulate_equal_weight_benchmark(synthetic_prices)

    # First session holdings must be exactly 1/6 for all 6 sectors
    first_row = df_sim.iloc[0]
    for s in SECTOR_NAMES:
        assert np.isclose(first_row[f"w_hold_{s}"], 1.0 / 6.0, atol=1e-7)


def test_5_equal_weight_portfolio_daily_return(synthetic_prices):
    """Verify daily gross return equals dot product of holdings and sector returns."""
    df_sim = simulate_equal_weight_benchmark(synthetic_prices)

    for dt, row in df_sim.iterrows():
        expected_r = sum(row[f"w_hold_{s}"] * row[f"r_{s}"] for s in SECTOR_NAMES)
        assert np.isclose(row["gross_return"], expected_r, atol=1e-12)


def test_6_correct_portfolio_weight_drift(synthetic_prices):
    """Verify weight drift formula: w_drift = w_hold * (1 + r) / (1 + R_gross)."""
    df_sim = simulate_equal_weight_benchmark(synthetic_prices)

    for dt, row in df_sim.iterrows():
        r_gross = row["gross_return"]
        for s in SECTOR_NAMES:
            expected_drift = (row[f"w_hold_{s}"] * (1.0 + row[f"r_{s}"])) / (1.0 + r_gross)
            assert np.isclose(row[f"w_drift_{s}"], expected_drift, atol=1e-10)


def test_7_correct_month_end_signal_generation(synthetic_calendar):
    """Verify that get_month_end_signal_dates detects 2024-01-31 as the month-end signal."""
    signals = get_month_end_signal_dates(synthetic_calendar)

    # In synthetic calendar, 2024-01-31 is month-end (next date is 2024-02-01)
    assert pd.Timestamp("2024-01-31") in signals
    # Inception date (2024-01-26) must NOT be a signal date
    assert pd.Timestamp("2024-01-26") not in signals
    # Mid-month dates must NOT be signal dates
    assert pd.Timestamp("2024-02-01") not in signals


def test_8_correct_next_session_execution(synthetic_prices):
    """
    Verify t+1 execution: Signal on 2024-01-31 executes at 2024-02-01 Close.
    Returns on 2024-02-01 are earned by DRIFTED January holdings, NOT the reset target weights!
    """
    df_sim = simulate_equal_weight_benchmark(synthetic_prices)

    # 2024-01-31: Signal date
    row_jan31 = df_sim.loc[pd.Timestamp("2024-01-31")]
    assert bool(row_jan31["rebalance_signal"]) is True
    assert bool(row_jan31["rebalance_executed"]) is False

    # 2024-02-01: Execution date
    row_feb01 = df_sim.loc[pd.Timestamp("2024-02-01")]
    assert bool(row_feb01["rebalance_executed"]) is True

    # Holdings held during 2024-02-01 were drifted from Jan 31, NOT 1/6!
    # In synthetic data, IT gained +3% daily, Metal lost -2% daily, so drifted weights differ from 1/6
    assert not np.isclose(row_feb01["w_hold_IT"], 1.0 / 6.0)
    assert not np.isclose(row_feb01["w_hold_METAL"], 1.0 / 6.0)

    # At 2024-02-01 Close, post-trade weights reset to exactly 1/6
    for s in SECTOR_NAMES:
        assert np.isclose(row_feb01[f"w_post_{s}"], 1.0 / 6.0, atol=1e-7)


def test_9_first_rebalance_date_on_historical_calendar():
    """Verify on real aligned price calendar that first rebalance signal is 2019-11-29, executing 2019-12-02."""
    p_df = load_benchmark_prices()
    signals = get_month_end_signal_dates(p_df.index)

    # 2019-10-31 is inception, must NOT be a signal
    assert pd.Timestamp("2019-10-31") not in signals

    # First signal must be 2019-11-29
    sorted_signals = sorted(list(signals))
    assert sorted_signals[0] == pd.Timestamp("2019-11-29")

    # Simulation check
    df_sim = simulate_equal_weight_benchmark(p_df)
    assert bool(df_sim.loc[pd.Timestamp("2019-11-29"), "rebalance_signal"]) is True
    assert bool(df_sim.loc[pd.Timestamp("2019-11-29"), "rebalance_executed"]) is False
    assert bool(df_sim.loc[pd.Timestamp("2019-12-02"), "rebalance_executed"]) is True


def test_10_actual_turnover_calculation(synthetic_prices):
    """Verify actual turnover TO_actual = 0.5 * sum(|1/6 - w_drift|)."""
    df_sim = simulate_equal_weight_benchmark(synthetic_prices)

    # Rebalance executed on 2024-02-01
    row_exec = df_sim.loc[pd.Timestamp("2024-02-01")]
    drifted_vals = np.array([row_exec[f"w_drift_{s}"] for s in SECTOR_NAMES])
    expected_to = float(0.5 * np.sum(np.abs((1.0 / 6.0) - drifted_vals)))

    assert np.isclose(row_exec["actual_turnover"], expected_to, atol=1e-12)
    assert row_exec["actual_turnover"] > 0.0


def test_11_transaction_cost_calculation(synthetic_prices):
    """Verify transaction cost: TC = NAV_pre_net * TO_actual * 0.0015."""
    cost_rate = 0.0015
    df_sim = simulate_equal_weight_benchmark(synthetic_prices, cost_rate=cost_rate)

    row_exec = df_sim.loc[pd.Timestamp("2024-02-01")]
    expected_tc = row_exec["pre_trade_nav_net"] * row_exec["actual_turnover"] * cost_rate
    assert np.isclose(row_exec["transaction_cost"], expected_tc, atol=1e-12)


def test_12_gross_net_nav_separation(synthetic_prices):
    """Verify Gross NAV >= Net NAV due to transaction costs, and Net NAV < Gross NAV after rebalance."""
    df_sim = simulate_equal_weight_benchmark(synthetic_prices, cost_rate=0.0015)

    # Before first rebalance (Jan 26 to Jan 31), gross NAV == net NAV
    sub_before = df_sim.loc[:"2024-01-31"]
    assert np.allclose(sub_before["gross_nav"], sub_before["net_nav"], atol=1e-12)

    # After rebalance on 2024-02-01, Net NAV must be strictly less than Gross NAV
    sub_after = df_sim.loc["2024-02-01":]
    assert (sub_after["net_nav"] < sub_after["gross_nav"]).all()


def test_13_no_costs_on_non_rebalance_sessions(synthetic_prices):
    """Verify that sessions where rebalance_executed is False have TO == 0, TC == 0, and gross == net return."""
    df_sim = simulate_equal_weight_benchmark(synthetic_prices)

    non_rebal = df_sim[~df_sim["rebalance_executed"]]
    assert (non_rebal["actual_turnover"] == 0.0).all()
    assert (non_rebal["transaction_cost"] == 0.0).all()
    assert np.allclose(non_rebal["gross_return"], non_rebal["net_return"], atol=1e-12)
    assert np.allclose(non_rebal["contrib_cost"], 0.0, atol=1e-12)


def test_14_no_transaction_costs_at_inception(synthetic_prices):
    """Verify Day 1 Close incurs zero transaction costs (inception boundary condition)."""
    df_sim = simulate_equal_weight_benchmark(synthetic_prices)

    # Day 1 is index 0
    first_session = df_sim.iloc[0]
    assert first_session["transaction_cost"] == 0.0
    assert first_session["actual_turnover"] == 0.0
    assert bool(first_session["rebalance_executed"]) is False


def test_15_weight_simplex_conservation(synthetic_prices):
    """Verify that holding, drifted, and post-trade weights sum to 1.0 and are non-negative on every session."""
    df_sim = simulate_equal_weight_benchmark(synthetic_prices)

    for dt, row in df_sim.iterrows():
        sum_hold = sum(row[f"w_hold_{s}"] for s in SECTOR_NAMES)
        sum_drift = sum(row[f"w_drift_{s}"] for s in SECTOR_NAMES)
        sum_post = sum(row[f"w_post_{s}"] for s in SECTOR_NAMES)

        assert np.isclose(sum_hold, 1.0, atol=1e-7)
        assert np.isclose(sum_drift, 1.0, atol=1e-7)
        assert np.isclose(sum_post, 1.0, atol=1e-7)

        for s in SECTOR_NAMES:
            assert row[f"w_hold_{s}"] >= -1e-9
            assert row[f"w_drift_{s}"] >= -1e-9
            assert row[f"w_post_{s}"] >= -1e-9


def test_16_zero_lookahead_bias(synthetic_prices):
    """
    Verify zero look-ahead bias: Modifying prices after date t has zero impact
    on simulation outputs at date t.
    """
    df1 = simulate_equal_weight_benchmark(synthetic_prices)

    # Shock prices on the final 2 sessions
    shocked_prices = synthetic_prices.copy()
    shocked_prices.iloc[-2:, :] = shocked_prices.iloc[-2:, :] * 1.50
    df2 = simulate_equal_weight_benchmark(shocked_prices)

    # Slices up to 3rd to last session must be bit-level identical
    common_dates = df1.index[:-2]
    for col in df1.columns:
        if df1[col].dtype == object or df1[col].dtype == bool:
            assert (df1.loc[common_dates, col] == df2.loc[common_dates, col]).all()
        else:
            assert np.allclose(df1.loc[common_dates, col].values, df2.loc[common_dates, col].values, atol=1e-12)


def test_17_identical_date_alignment_with_strategy_outputs():
    """Verify benchmark dates match Phase 10 strategy simulation dates exactly (1,686 dates)."""
    strat_path = PROJECT_ROOT / "results" / "portfolio_backtest" / "daily_simulation_1A.parquet"
    if not strat_path.exists():
        pytest.skip("Strategy 1A parquet not found.")

    strat_df = pd.read_parquet(strat_path)
    price_df = load_benchmark_prices()
    bench_n50 = simulate_nifty50_benchmark(price_df)
    bench_ew = simulate_equal_weight_benchmark(price_df)

    assert len(bench_n50) == len(strat_df) == EXPECTED_TOTAL_RETURN_INTERVALS
    assert len(bench_ew) == len(strat_df) == EXPECTED_TOTAL_RETURN_INTERVALS
    assert (bench_n50.index == strat_df.index).all()
    assert (bench_ew.index == strat_df.index).all()


def test_18_train_holdout_boundary_treatment():
    """Verify train has exactly 1,264 intervals and holdout has exactly 422 intervals."""
    price_df = load_benchmark_prices()
    bench_ew = simulate_equal_weight_benchmark(price_df)

    train_mask = bench_ew["period"] == "train"
    holdout_mask = bench_ew["period"] == "holdout"

    assert train_mask.sum() == EXPECTED_TRAIN_RETURN_INTERVALS == 1264
    assert holdout_mask.sum() == EXPECTED_HOLDOUT_RETURN_INTERVALS == 422

    # Boundary return (2024-12-31 to 2025-01-02) is first holdout date
    assert bench_ew.loc[pd.Timestamp("2024-12-31"), "period"] == "train"
    assert bench_ew.loc[pd.Timestamp("2025-01-02"), "period"] == "holdout"

    # Compounding check
    m_train = compute_benchmark_metrics(bench_ew, period="train", validate_counts=True)
    m_holdout = compute_benchmark_metrics(bench_ew, period="holdout", validate_counts=True)
    m_full = compute_benchmark_metrics(bench_ew, period="full", validate_counts=True)

    tr_train = m_train["total_return_net_pct"] / 100.0
    tr_holdout = m_holdout["total_return_net_pct"] / 100.0
    tr_full = m_full["total_return_net_pct"] / 100.0

    compounded = (1.0 + tr_train) * (1.0 + tr_holdout) - 1.0
    assert np.isclose(tr_full, compounded, atol=1e-12)


def test_19_missing_data_and_malformed_inputs(synthetic_prices):
    """Verify that missing asset columns or fewer than 2 sessions raise KeyError / ValueError."""
    # Missing sector
    bad_prices = synthetic_prices.drop(columns=["METAL"])
    with pytest.raises(KeyError, match="missing sector column: 'METAL'"):
        simulate_equal_weight_benchmark(bad_prices)

    # Missing NIFTY 50
    bad_n50 = synthetic_prices.drop(columns=["NIFTY50"])
    with pytest.raises(KeyError, match="missing 'NIFTY50'"):
        simulate_nifty50_benchmark(bad_n50)

    # Too short series
    short_prices = synthetic_prices.iloc[:1]
    with pytest.raises(ValueError, match="at least 2 sessions"):
        simulate_nifty50_benchmark(short_prices)


def test_20_deterministic_reproducibility(synthetic_prices):
    """Verify that multiple simulation runs produce bit-level identical DataFrames."""
    run1 = simulate_equal_weight_benchmark(synthetic_prices)
    run2 = simulate_equal_weight_benchmark(synthetic_prices)

    pd.testing.assert_frame_equal(run1, run2)
