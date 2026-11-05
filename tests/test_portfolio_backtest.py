"""
Unit and integration tests for src/portfolio_backtest.py (Phase 10.3).

Validates:
  1. Simple daily return calculation (P_t / P_{t-1} - 1).
  2. Portfolio weight drift calculation under multi-asset price movements.
  3. Weight normalization and simplex conservation (sum(w) == 1.0, w >= 0).
  4. Actual one-way turnover: TO_actual = 0.5 * sum(|w_target - w_drift|).
  5. Zero turnover and zero transaction cost on non-rebalance days.
  6. Transaction-cost calculation: TC = NAV_pre * TO_actual * cost_rate.
  7. Gross vs net accounting consistency (gross incurs zero cost, net NAV <= gross NAV).
  8. Initial 100% NIFTY 50 funding on Day 0 (2019-10-31).
  9. Initial transition to first target at Day 1 Close with 100% turnover fee.
  10. Correct signal/execution timing (Day t signal executed at Day t+1 Close).
  11. Zero look-ahead leakage in return realization and execution.
  12. Cash return baseline of zero (r_cash == 0.0).
  13. Continuous portfolio state across the train-to-holdout boundary.
  14. Interval counts and timeline partition: 1,264 train, 422 holdout, 1,686 full.
  15. Exclusion of terminal untraded signal on final session.
  16. Exact additive attribution reconciliation: R_net = sum(C_i) + C_cost.
  17. Weight non-negativity and simplex constraints maintained every session.
  18. Invalid, missing, or mismatched data rejection.
  19. Performance metrics calculation (CAGR, Annualized Volatility, Sharpe, Sortino, MDD).
  20. Apache Parquet serialization, round-trip reload, and bit-level parity verification.
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

from src.portfolio_backtest import (
    ALL_ASSETS,
    ANNUALIZATION_FACTOR,
    DEFAULT_TRANSACTION_COST_RATE,
    EXPECTED_HOLDOUT_RETURN_INTERVALS,
    EXPECTED_TOTAL_RETURN_INTERVALS,
    EXPECTED_TRAIN_RETURN_INTERVALS,
    SECTOR_NAMES,
    VARIANTS,
    calculate_actual_turnover,
    calculate_drifted_weights,
    compute_attribution,
    compute_metrics,
    generate_metrics_table,
    load_backtest_inputs,
    reload_and_verify_parquet,
    run_all_simulations,
    run_portfolio_backtest_pipeline,
    save_simulation_parquet,
    simulate_portfolio,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def synthetic_dates():
    """Create 10 business dates for controlled simulation unit tests."""
    return pd.bdate_range("2024-01-01", periods=10)


@pytest.fixture
def synthetic_prices(synthetic_dates):
    """
    Create synthetic prices for all 7 equity assets across synthetic_dates.
    Asset prices follow known deterministic paths for exact arithmetic checks.
    """
    n = len(synthetic_dates)
    data = {}
    # NIFTY50: constant 1% daily gain
    data["NIFTY50"] = 100.0 * (1.01 ** np.arange(n))
    # AUTO: 2% daily gain
    data["AUTO"] = 100.0 * (1.02 ** np.arange(n))
    # BANK: 0% daily gain (flat)
    data["BANK"] = np.full(n, 100.0)
    # FMCG: -1% daily loss
    data["FMCG"] = 100.0 * (0.99 ** np.arange(n))
    # IT: 1.5% daily gain
    data["IT"] = 100.0 * (1.015 ** np.arange(n))
    # METAL: 0.5% daily gain
    data["METAL"] = 100.0 * (1.005 ** np.arange(n))
    # PHARMA: flat
    data["PHARMA"] = np.full(n, 100.0)

    return pd.DataFrame(data, index=synthetic_dates)


@pytest.fixture
def synthetic_schedule(synthetic_dates):
    """
    Create a valid synthetic target-weight schedule across synthetic_dates.
    Day 0: Rebalance triggered (sets target for Day 1 Close: 50% AUTO, 50% BANK).
    Day 1-3: No rebalance triggered.
    Day 4: Rebalance triggered (sets target for Day 5 Close: 100% IT).
    Day 5-9: No rebalance triggered.
    First 6 sessions are 'train', next 4 are 'holdout' (so train ends at date index 5, holdout starts at 6).
    """
    n = len(synthetic_dates)
    rows = []
    for i in range(n):
        dt = synthetic_dates[i]
        exec_dt = synthetic_dates[i + 1] if i + 1 < n else dt
        is_train = i < 6
        period = "train" if is_train else "holdout"

        # Baseline weights (Day 0-3 target: 50% AUTO, 50% BANK; Day 4+ target: 100% IT)
        w_dict = {f"w_{a}": 0.0 for a in ALL_ASSETS}
        if i < 4:
            w_dict["w_AUTO"] = 0.50
            w_dict["w_BANK"] = 0.50
        else:
            w_dict["w_IT"] = 1.00

        rebal_trig = (i == 0 or i == 4)

        row = {
            "Date": dt,
            "exec_date": exec_dt,
            "period": period,
            "variant": "1A",
            "raw_regime_argmax": 0 if i < 4 else 1,
            "max_probability": 0.85,
            "is_confident": True,
            "accepted_regime": 0 if i < 4 else 1,
            "rebalance_triggered": rebal_trig,
            "rebalance_bypassed_r3": False,
            "turnover": 1.0 if i == 0 else (0.5 if i == 4 else 0.0),
            **w_dict,
        }
        rows.append(row)

    df = pd.DataFrame(rows).set_index("Date")
    return df


@pytest.fixture
def synthetic_prob_df(synthetic_dates):
    """Synthetic causal probabilities for metadata attachment."""
    n = len(synthetic_dates)
    probs = np.full((n, 6), 1.0 / 6.0)
    df = pd.DataFrame(probs, index=synthetic_dates, columns=[f"prob_{j}" for j in range(6)])
    return df


# =====================================================================
# 1. Math Core Tests: Drift, Normalization & Simplex
# =====================================================================

def test_drifted_weights_formula():
    """Verify that calculate_drifted_weights matches exact analytical formula."""
    # 2 assets: 50% in Asset A, 50% in Asset B.
    # Asset A returns +10%, Asset B returns -10%.
    # Value factor: 0.5 * 1.1 + 0.5 * 0.9 = 0.55 + 0.45 = 1.0.
    # Drifted weight A = 0.55 / 1.0 = 0.55.
    # Drifted weight B = 0.45 / 1.0 = 0.45.
    weights_prev = np.array([0.5, 0.5])
    returns = np.array([0.10, -0.10])
    w_drift = calculate_drifted_weights(weights_prev, returns)

    assert np.isclose(w_drift[0], 0.55)
    assert np.isclose(w_drift[1], 0.45)
    assert np.isclose(np.sum(w_drift), 1.0)


def test_drifted_weights_simplex_conservation():
    """Verify that drifted weights strictly preserve the probability simplex (sum to 1.0, >= 0)."""
    np.random.seed(123)
    for _ in range(50):
        raw_w = np.random.uniform(0.01, 1.0, size=len(ALL_ASSETS))
        w_prev = raw_w / np.sum(raw_w)
        rets = np.random.normal(0.0, 0.05, size=len(ALL_ASSETS))
        # Cash returns zero
        rets[-1] = 0.0

        w_drift = calculate_drifted_weights(w_prev, rets)
        assert np.isclose(np.sum(w_drift), 1.0, atol=1e-7)
        assert (w_drift >= -1e-9).all()


def test_drifted_weights_invalid_inputs():
    """Verify that non-normalized starting weights or negative weights raise ValueError."""
    with pytest.raises(ValueError, match="must sum to 1.0"):
        calculate_drifted_weights(np.array([0.4, 0.4]), np.array([0.01, 0.01]))

    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_drifted_weights(np.array([-0.2, 1.2]), np.array([0.01, 0.01]))


# =====================================================================
# 2. Math Core Tests: Actual One-Way Turnover
# =====================================================================

def test_actual_turnover_formula():
    """
    Verify actual one-way turnover: TO = 0.5 * sum(|w_target - w_drift|).
    Example: Drifted = [0.6, 0.4], Target = [0.5, 0.5].
    |0.5 - 0.6| + |0.5 - 0.4| = 0.1 + 0.1 = 0.2 -> TO = 0.1 (10%).
    """
    w_drift = np.array([0.6, 0.4])
    w_target = np.array([0.5, 0.5])
    to = calculate_actual_turnover(w_target, w_drift)
    assert np.isclose(to, 0.10)


def test_actual_turnover_bounds():
    """Verify turnover is bounded between 0.0 (identical) and 1.0 (complete rotation)."""
    w1 = np.array([1.0, 0.0, 0.0])
    w2 = np.array([1.0, 0.0, 0.0])
    assert np.isclose(calculate_actual_turnover(w1, w2), 0.0)

    w3 = np.array([0.0, 1.0, 0.0])
    assert np.isclose(calculate_actual_turnover(w1, w3), 1.0)


def test_actual_turnover_invalid_inputs():
    """Verify turnover raises ValueError when inputs do not sum to 1.0."""
    with pytest.raises(ValueError, match="Target weights must sum to 1.0"):
        calculate_actual_turnover(np.array([0.5, 0.4]), np.array([0.5, 0.5]))

    with pytest.raises(ValueError, match="Drifted weights must sum to 1.0"):
        calculate_actual_turnover(np.array([0.5, 0.5]), np.array([0.5, 0.6]))


# =====================================================================
# 3. Simulation Execution & Funding Contract Tests
# =====================================================================

def test_day_0_funding_and_day_1_first_return(synthetic_schedule, synthetic_prices):
    """
    Verify Initial State and Day 1 Execution Contract:
      - Day 0 (2024-01-01): Portfolio initialized with 100% NIFTY 50 (NAV = 1.0).
      - Interval 1 (Day 0 Close -> Day 1 Close): Portfolio earns 100% NIFTY 50 return.
      - At Day 1 Close: Rebalance authorized on Day 0 executes into target (100% turnover fee deducted).
    """
    sim_df = simulate_portfolio(synthetic_schedule, synthetic_prices)

    # First simulation row corresponds to Day 1
    row_day1 = sim_df.iloc[0]

    # Holding weight during Day 1 was 100% NIFTY50
    assert np.isclose(row_day1["w_hold_NIFTY50"], 1.0)
    for a in SECTOR_NAMES + ["CASH"]:
        assert np.isclose(row_day1[f"w_hold_{a}"], 0.0)

    # Gross return over Interval 1 must match NIFTY50 simple return exactly
    p0 = synthetic_prices.loc[synthetic_prices.index[0], "NIFTY50"]
    p1 = synthetic_prices.loc[synthetic_prices.index[1], "NIFTY50"]
    expected_r_gross = (p1 / p0) - 1.0
    assert np.isclose(row_day1["gross_return"], expected_r_gross)

    # At Day 1 Close, first rebalance executes
    assert bool(row_day1["rebalance_executed"]) is True
    # Day 0 had target: 50% AUTO, 50% BANK, 0% NIFTY50.
    # Drifted weight was 100% NIFTY50.
    # Actual turnover from 100% NIFTY50 to 50% AUTO + 50% BANK is 100% (1.0).
    assert np.isclose(row_day1["actual_turnover"], 1.0)

    # Transaction cost = NAV_pre * 1.0 * 0.0015
    nav_pre = 1.0 * (1.0 + expected_r_gross)
    expected_tc = nav_pre * 1.0 * DEFAULT_TRANSACTION_COST_RATE
    assert np.isclose(row_day1["transaction_cost"], expected_tc)

    # Post-rebalance holdings at Day 1 Close match Day 0 target
    assert np.isclose(row_day1["w_post_AUTO"], 0.5)
    assert np.isclose(row_day1["w_post_BANK"], 0.5)
    assert np.isclose(row_day1["w_post_NIFTY50"], 0.0)


def test_zero_turnover_on_non_rebalance_days(synthetic_schedule, synthetic_prices):
    """Verify that sessions where rebalance_executed is False have zero turnover and zero cost."""
    sim_df = simulate_portfolio(synthetic_schedule, synthetic_prices)

    # Day 2 (index 1) has no rebalance
    row_day2 = sim_df.iloc[1]
    assert bool(row_day2["rebalance_executed"]) is False
    assert np.isclose(row_day2["actual_turnover"], 0.0)
    assert np.isclose(row_day2["transaction_cost"], 0.0)
    assert np.isclose(row_day2["gross_return"], row_day2["net_return"])
    assert np.isclose(row_day2["contrib_cost"], 0.0)

    # Post-trade weights on non-rebalance day equal drifted weights
    for a in ALL_ASSETS:
        assert np.isclose(row_day2[f"w_post_{a}"], row_day2[f"w_drift_{a}"])


def test_timing_and_zero_lookahead_leakage(synthetic_schedule, synthetic_prices):
    """
    Verify t+1 execution timing:
      Signal generated at Day t Close executes at Day t+1 Close.
      Returns on Day t+1 are earned by holdings held from Day t Close to Day t+1 Close,
      NOT by the new target weights established at Day t+1 Close.
    """
    sim_df = simulate_portfolio(synthetic_schedule, synthetic_prices)

    # Rebalance triggered on Day 4 (row index 4 in schedule, date index 4).
    # Day 4 is Date 2024-01-05.
    # Simulation row for Day 5 (Date 2024-01-08) must execute this rebalance at Close.
    row_day5 = sim_df.loc[synthetic_prices.index[5]]
    assert bool(row_day5["rebalance_executed"]) is True

    # During Day 5 holding period, the portfolio held drifted AUTO and BANK weights, NOT IT!
    assert row_day5["w_hold_IT"] == 0.0
    assert row_day5["w_hold_AUTO"] > 0.0
    assert row_day5["w_hold_BANK"] > 0.0

    # IT return on Day 5 did NOT contribute to Day 5 return
    assert np.isclose(row_day5["contrib_IT"], 0.0)

    # Post-trade weight at Day 5 Close becomes 100% IT
    assert np.isclose(row_day5["w_post_IT"], 1.0)

    # Day 6 holding weight is now 100% IT
    row_day6 = sim_df.loc[synthetic_prices.index[6]]
    assert np.isclose(row_day6["w_hold_IT"], 1.0)
    assert row_day6["contrib_IT"] > 0.0


def test_terminal_untraded_signal_exclusion(synthetic_schedule, synthetic_prices):
    """
    Verify that the final date in schedule (terminal session) realized returns,
    and any signal evaluated on that day is excluded (there is no t+1 session).
    Total simulation rows == n_dates - 1.
    """
    sim_df = simulate_portfolio(synthetic_schedule, synthetic_prices)
    n_schedule_dates = len(synthetic_schedule)
    assert len(sim_df) == n_schedule_dates - 1
    assert sim_df.index[-1] == synthetic_schedule.index[-1]


# =====================================================================
# 4. Gross vs Net Accounting & Attribution Invariants
# =====================================================================

def test_gross_vs_net_accounting_consistency(synthetic_schedule, synthetic_prices):
    """
    Verify that gross NAV is always >= net NAV due to transaction costs,
    and net NAV equals gross NAV when cost_rate == 0.
    """
    sim_net = simulate_portfolio(synthetic_schedule, synthetic_prices, cost_rate=0.0015)
    sim_zero = simulate_portfolio(synthetic_schedule, synthetic_prices, cost_rate=0.0)

    # Zero cost simulation: gross NAV == net NAV everywhere
    assert np.allclose(sim_zero["gross_nav"], sim_zero["net_nav"])

    # Net NAV under 15 bps must be strictly less than gross NAV after first rebalance
    assert (sim_net["gross_nav"] >= sim_net["net_nav"]).all()
    assert sim_net["net_nav"].iloc[-1] < sim_net["gross_nav"].iloc[-1]


def test_exact_additive_attribution_identity(synthetic_schedule, synthetic_prices):
    """
    Verify that for every session:
      R_net = sum_{i} (w_hold_i * r_i) + C_cost
    where C_cost = R_net - R_gross.
    Attribution discrepancy must be identically zero (within machine precision).
    """
    sim_df = simulate_portfolio(synthetic_schedule, synthetic_prices)

    for dt, row in sim_df.iterrows():
        r_net = row["net_return"]
        contrib_sum = sum(row[f"contrib_{a}"] for a in ALL_ASSETS)
        c_cost = row["contrib_cost"]
        reconciled = contrib_sum + c_cost
        assert np.isclose(r_net, reconciled, atol=1e-12), f"Failed on {dt}"


def test_cash_zero_return_baseline(synthetic_schedule, synthetic_prices):
    """Verify that cash earns exactly 0.0 return in baseline simulation."""
    # Modify schedule to hold 100% CASH from Day 0
    sched_cash = synthetic_schedule.copy()
    for a in ALL_ASSETS:
        sched_cash[f"w_{a}"] = 0.0
    sched_cash["w_CASH"] = 1.0

    sim_df = simulate_portfolio(sched_cash, synthetic_prices, cash_yield_daily=0.0)

    # After Day 1 rebalance into CASH, cash return is 0
    # Day 2 holdings: 100% CASH
    row_day2 = sim_df.iloc[1]
    assert np.isclose(row_day2["w_hold_CASH"], 1.0)
    assert np.isclose(row_day2["r_CASH"], 0.0)
    assert np.isclose(row_day2["contrib_CASH"], 0.0)
    assert np.isclose(row_day2["gross_return"], 0.0)


# =====================================================================
# 5. Continuous Train-to-Holdout Boundary Tests
# =====================================================================

def test_continuous_portfolio_state_across_boundary(synthetic_schedule, synthetic_prices):
    """
    Verify that portfolio holdings, NAV, and drift continue seamlessly across
    the training-to-holdout boundary without any reset or artificial liquidation.
    """
    sim_df = simulate_portfolio(synthetic_schedule, synthetic_prices)

    # Find boundary: last train session and first holdout session
    train_mask = sim_df["period"] == "train"
    holdout_mask = sim_df["period"] == "holdout"

    last_train = sim_df[train_mask].iloc[-1]
    first_holdout = sim_df[holdout_mask].iloc[0]

    # Post-trade weights at end of train must exactly equal holdings at start of holdout
    for a in ALL_ASSETS:
        assert np.isclose(last_train[f"w_post_{a}"], first_holdout[f"w_hold_{a}"])

    # Ending net NAV of train must match start base of holdout
    # Holdout day 1 pre-NAV = last_train_post_NAV * (1 + r_gross_holdout_1)
    expected_pre_nav = last_train["net_nav"] * (1.0 + first_holdout["gross_return"])
    # If no rebalance on first holdout day, net_nav == pre_nav
    if not first_holdout["rebalance_executed"]:
        assert np.isclose(first_holdout["net_nav"], expected_pre_nav)


# =====================================================================
# 6. Performance Metrics Calculation Tests
# =====================================================================

def test_compute_metrics_arithmetic_sortino():
    """
    Verify Sortino ratio formula:
      Sortino = Ann_Mean_Return / Ann_Downside_Deviation
    where numerator is arithmetic mean * 252 (not CAGR).
    """
    dates = pd.bdate_range("2024-01-01", periods=10)
    # Synthetic daily simulation dataframe
    df = pd.DataFrame({
        "period": ["full"] * 10,
        "gross_return": [0.01, -0.01, 0.02, -0.005, 0.01, 0.0, 0.015, -0.01, 0.005, 0.005],
        "net_return": [0.009, -0.01, 0.019, -0.005, 0.009, 0.0, 0.014, -0.01, 0.004, 0.004],
        "gross_nav": np.cumprod(1.0 + np.array([0.01, -0.01, 0.02, -0.005, 0.01, 0.0, 0.015, -0.01, 0.005, 0.005])),
        "net_nav": np.cumprod(1.0 + np.array([0.009, -0.01, 0.019, -0.005, 0.009, 0.0, 0.014, -0.01, 0.004, 0.004])),
        "rebalance_executed": [True, False, False, True, False, False, False, False, False, False],
        "rebalance_bypassed_r3": [False] * 10,
        "actual_turnover": [1.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "transaction_cost": [0.0015, 0.0, 0.0, 0.00075, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "w_post_CASH": [0.0] * 10,
    }, index=dates)

    # Monkey patch expected count for synthetic test
    from unittest.mock import patch
    with patch("src.portfolio_backtest.EXPECTED_TOTAL_RETURN_INTERVALS", 10):
        metrics = compute_metrics(df, period="full")

    r_net = df["net_return"].values
    mean_daily = np.mean(r_net)
    ann_mean = mean_daily * 252.0
    downside_sq = np.minimum(0.0, r_net) ** 2
    downside_dev = np.sqrt(np.mean(downside_sq)) * np.sqrt(252.0)
    expected_sortino = ann_mean / downside_dev

    assert np.isclose(metrics["sortino_ratio"], expected_sortino)
    assert np.isclose(metrics["ann_mean_return_pct"], ann_mean * 100.0)
    assert np.isclose(metrics["downside_deviation_pct"], downside_dev * 100.0)


def test_compute_metrics_cagr_and_mdd():
    """Verify CAGR formula ((NAV_end / NAV_start) ** (252 / N) - 1) and MDD."""
    dates = pd.bdate_range("2024-01-01", periods=4)
    # NAV drops from 1.0 -> 0.90 (-10%) then recovers to 0.99
    net_rets = np.array([0.0, -0.10, 0.10, 0.0])
    net_navs = np.array([1.0, 0.90, 0.99, 0.99])
    df = pd.DataFrame({
        "period": ["full"] * 4,
        "gross_return": net_rets,
        "net_return": net_rets,
        "gross_nav": net_navs,
        "net_nav": net_navs,
        "rebalance_executed": [False] * 4,
        "rebalance_bypassed_r3": [False] * 4,
        "actual_turnover": [0.0] * 4,
        "transaction_cost": [0.0] * 4,
        "w_post_CASH": [0.0] * 4,
    }, index=dates)

    from unittest.mock import patch
    with patch("src.portfolio_backtest.EXPECTED_TOTAL_RETURN_INTERVALS", 4):
        metrics = compute_metrics(df, period="full")

    # MDD must be -10.0%
    assert np.isclose(metrics["max_drawdown_pct"], -10.0)
    expected_cagr = (0.99 / 1.0) ** (252.0 / 4) - 1.0
    assert np.isclose(metrics["cagr_net_pct"], expected_cagr * 100.0)


def test_interval_counts_validation_enforcement():
    """
    Verify that compute_metrics strictly enforces expected interval counts
    (1,264 train, 422 holdout, 1,686 full) when validate_counts=True.
    """
    # Create DataFrame with 1,265 rows (1 row too many for train)
    dates_bad = pd.bdate_range("2020-01-01", periods=1265)
    df_bad = pd.DataFrame({
        "period": ["train"] * 1265,
        "gross_return": [0.001] * 1265,
        "net_return": [0.001] * 1265,
        "gross_nav": np.cumprod(1.0 + np.full(1265, 0.001)),
        "net_nav": np.cumprod(1.0 + np.full(1265, 0.001)),
        "rebalance_executed": [False] * 1265,
        "rebalance_bypassed_r3": [False] * 1265,
        "actual_turnover": [0.0] * 1265,
        "transaction_cost": [0.0] * 1265,
        "w_post_CASH": [0.0] * 1265,
    }, index=dates_bad)

    with pytest.raises(ValueError, match="Period 'train' expected 1264 return intervals, got 1265"):
        compute_metrics(df_bad, period="train", validate_counts=True)

    # Valid train DataFrame with exactly 1,264 rows
    df_valid_train = df_bad.iloc[:1264]
    m_train = compute_metrics(df_valid_train, period="train", validate_counts=True)
    assert m_train["return_intervals"] == 1264

    # Valid holdout DataFrame with exactly 422 rows
    dates_holdout = pd.bdate_range("2025-01-02", periods=422)
    df_valid_holdout = pd.DataFrame({
        "period": ["holdout"] * 422,
        "gross_return": [0.0005] * 422,
        "net_return": [0.0005] * 422,
        "gross_nav": np.cumprod(1.0 + np.full(422, 0.0005)),
        "net_nav": np.cumprod(1.0 + np.full(422, 0.0005)),
        "rebalance_executed": [False] * 422,
        "rebalance_bypassed_r3": [False] * 422,
        "actual_turnover": [0.0] * 422,
        "transaction_cost": [0.0] * 422,
        "w_post_CASH": [0.0] * 422,
    }, index=dates_holdout)
    m_holdout = compute_metrics(df_valid_holdout, period="holdout", validate_counts=True)
    assert m_holdout["return_intervals"] == 422


# =====================================================================
# 7. Error Handling and Input Validation Tests
# =====================================================================

def test_missing_price_column_raises_keyerror(synthetic_schedule, synthetic_prices):
    """Verify that missing asset prices raise KeyError."""
    bad_prices = synthetic_prices.drop(columns=["AUTO"])
    with pytest.raises(KeyError, match="missing asset: AUTO"):
        simulate_portfolio(synthetic_schedule, bad_prices)


def test_missing_simulation_dates_raises_keyerror(synthetic_schedule, synthetic_prices):
    """Verify that prices missing schedule dates raise KeyError."""
    bad_prices = synthetic_prices.iloc[:-2]
    with pytest.raises(KeyError, match="missing 2 simulation dates"):
        simulate_portfolio(synthetic_schedule, bad_prices)


def test_schedule_too_short_raises_valueerror(synthetic_prices):
    """Verify that schedule with fewer than 2 dates raises ValueError."""
    short_sched = pd.DataFrame({"variant": ["1A"]}, index=[synthetic_prices.index[0]])
    with pytest.raises(ValueError, match="at least 2 sessions"):
        simulate_portfolio(short_sched, synthetic_prices)


# =====================================================================
# 8. Parquet Serialization and Parity Tests
# =====================================================================

def test_parquet_serialization_and_verification(synthetic_schedule, synthetic_prices, tmp_path):
    """
    Verify that save_simulation_parquet and reload_and_verify_parquet
    write, read, and verify round-trip fidelity with zero data corruption.
    """
    sim_df = simulate_portfolio(synthetic_schedule, synthetic_prices)
    simulations = {"1A": sim_df}

    # Save to tmp directory
    saved_paths = save_simulation_parquet(simulations, output_dir=tmp_path)
    assert "1A" in saved_paths
    assert saved_paths["1A"].exists()
    assert (tmp_path / "metrics_summary.parquet").exists()
    assert (tmp_path / "metrics_summary.csv").exists()

    audit = reload_and_verify_parquet(saved_paths, original_simulations=simulations, expected_intervals=len(sim_df))
    assert audit["1A"]["parity_verified"] is True
    assert audit["1A"]["rows"] == len(sim_df)


# =====================================================================
# 9. Attribution Summary Table Test
# =====================================================================

def test_compute_attribution_summary(synthetic_schedule, synthetic_prices):
    """Verify compute_attribution aggregates asset contributions and costs properly."""
    sim_df = simulate_portfolio(synthetic_schedule, synthetic_prices)
    attr_df = compute_attribution(sim_df)

    assert set(attr_df["period"]) == {"train", "holdout", "full"}
    for _, row in attr_df.iterrows():
        assert np.isclose(row["reconciled_net_pct"], row["actual_net_sum_pct"], atol=1e-10)
