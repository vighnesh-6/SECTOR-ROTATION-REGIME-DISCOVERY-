"""
Unit and integration tests for src/portfolio_construction.py (Phase 9.2).

Validates:
  1. Input schema and probability vector integrity (finiteness, [0, 1] bounds, sum to 1.0).
  2. Date ordering, uniqueness, and price coverage checks.
  3. Timeline partition reconciliation (train vs holdout).
  4. Generation of all four strategy variants (1A, 1B, 2A, 2B).
  5. Continuous state across the train-to-holdout boundary (no reset at holdout start).
  6. Asset-weight simplex and cash-target invariants (Template A vs Template B).
  7. Day 0 initialization and execution timing.
  8. Determinism and zero look-ahead bias.
  9. CSV serialization, reload, and numerical parity verification.
  10. Strict alignment with existing RegimeRotationRulesEngine behavior.
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

from src.regime_rotation_rules import (
    ALL_ASSETS,
    SECTOR_NAMES,
    TEMPLATE_A_CASH,
    TEMPLATE_B_CASH,
    RegimeRotationRulesEngine,
    StrategyVariant,
)
from src.portfolio_construction import (
    EXPECTED_HOLDOUT_END,
    EXPECTED_HOLDOUT_SESSIONS,
    EXPECTED_HOLDOUT_START,
    EXPECTED_TOTAL_SESSIONS,
    EXPECTED_TRAIN_END,
    EXPECTED_TRAIN_SESSIONS,
    EXPECTED_TRAIN_START,
    PROB_COLS,
    SCHEDULE_COLUMNS,
    WEIGHT_COLS,
    generate_all_schedules,
    generate_portfolio_schedule,
    load_aligned_prices,
    load_causal_probabilities,
    reload_and_verify_schedules,
    save_target_weight_schedules,
    validate_price_coverage,
    validate_probabilities_df,
    validate_schedule,
    validate_timeline_partition,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def synthetic_dates():
    """Create 30 business dates for lightweight unit testing."""
    return pd.bdate_range("2024-01-01", periods=30)


@pytest.fixture
def synthetic_prob_df(synthetic_dates):
    """
    Create a valid synthetic probabilities DataFrame split into train and holdout.
    First 20 dates are 'train', remaining 10 are 'holdout'.
    """
    n = len(synthetic_dates)
    # Default: strong Regime 0 signal
    probs = np.zeros((n, 6))
    probs[:, 0] = 0.80
    probs[:, 1:] = 0.04

    # Mid-sequence regime switch to Regime 4 at date index 10
    probs[10:18, :] = 0.04
    probs[10:18, 4] = 0.80

    # Switch to Regime 3 (crisis) at date index 18
    probs[18:25, :] = 0.04
    probs[18:25, 3] = 0.80

    # Normalize rows to sum to 1.0 exactly
    probs = probs / probs.sum(axis=1, keepdims=True)

    df = pd.DataFrame(probs, index=synthetic_dates, columns=PROB_COLS)
    df["period"] = ["train"] * 20 + ["holdout"] * 10
    return df


@pytest.fixture
def synthetic_prices(synthetic_dates):
    """
    Create synthetic prices covering synthetic_dates plus 30 warmup dates.
    """
    warmup_dates = pd.bdate_range(end=synthetic_dates[0] - pd.Timedelta(days=1), periods=30)
    all_dates = warmup_dates.append(synthetic_dates)
    np.random.seed(42)
    data = {}
    for s in SECTOR_NAMES:
        # Geometric random walk
        rets = np.random.normal(0.0005, 0.015, size=len(all_dates))
        data[s] = 1000.0 * np.exp(np.cumsum(rets))
    return pd.DataFrame(data, index=all_dates)


# =====================================================================
# 1. Probability Schema and Boundary Validation Tests
# =====================================================================

def test_probability_schema_validation_success(synthetic_prob_df):
    """Verify that a compliant probability DataFrame passes validation without error."""
    validate_probabilities_df(synthetic_prob_df)


def test_probability_missing_columns(synthetic_prob_df):
    """Verify that missing probability columns or period column raise KeyError."""
    df_missing_prob = synthetic_prob_df.drop(columns=["prob_5"])
    with pytest.raises(KeyError, match="missing required columns"):
        validate_probabilities_df(df_missing_prob)

    df_missing_period = synthetic_prob_df.drop(columns=["period"])
    with pytest.raises(KeyError, match="missing required 'period' column"):
        validate_probabilities_df(df_missing_period)


def test_probability_non_finite_values(synthetic_prob_df):
    """Verify that NaN or Inf values in probabilities raise ValueError."""
    df_nan = synthetic_prob_df.copy()
    df_nan.iloc[2, 0] = np.nan
    with pytest.raises(ValueError, match="Non-finite"):
        validate_probabilities_df(df_nan)

    df_inf = synthetic_prob_df.copy()
    df_inf.iloc[3, 1] = np.inf
    with pytest.raises(ValueError, match="Non-finite"):
        validate_probabilities_df(df_inf)


def test_probability_out_of_bounds(synthetic_prob_df):
    """Verify that probability values outside [0, 1] raise ValueError."""
    df_neg = synthetic_prob_df.copy()
    df_neg.iloc[0, 0] = -0.05
    with pytest.raises(ValueError, match="out of bounds"):
        validate_probabilities_df(df_neg)

    df_excess = synthetic_prob_df.copy()
    df_excess.iloc[1, 0] = 1.05
    with pytest.raises(ValueError, match="out of bounds"):
        validate_probabilities_df(df_excess)


def test_probability_row_sums_not_one(synthetic_prob_df):
    """Verify that rows not summing to 1.0 (within tolerance) raise ValueError."""
    df_bad_sum = synthetic_prob_df.copy()
    df_bad_sum.iloc[4, 0] += 0.10
    with pytest.raises(ValueError, match="row sums deviate"):
        validate_probabilities_df(df_bad_sum)


def test_probability_invalid_period_labels(synthetic_prob_df):
    """Verify that period values other than 'train' and 'holdout' raise ValueError."""
    df_bad_period = synthetic_prob_df.copy()
    df_bad_period.iloc[0, df_bad_period.columns.get_loc("period")] = "test"
    with pytest.raises(ValueError, match="Invalid period"):
        validate_probabilities_df(df_bad_period)


# =====================================================================
# 2. Date and Price Coverage Validation Tests
# =====================================================================

def test_date_validation_duplicate_dates(synthetic_prob_df):
    """Verify that duplicate dates in probabilities DataFrame raise ValueError."""
    dup_index = list(synthetic_prob_df.index)
    dup_index[1] = dup_index[0]
    df_dup = synthetic_prob_df.copy()
    df_dup.index = pd.DatetimeIndex(dup_index)
    with pytest.raises(ValueError, match="duplicate dates"):
        validate_probabilities_df(df_dup)


def test_date_validation_unsorted_dates(synthetic_prob_df):
    """Verify that unsorted dates raise ValueError."""
    df_unsorted = synthetic_prob_df.iloc[::-1].copy()
    with pytest.raises(ValueError, match="monotonically increasing"):
        validate_probabilities_df(df_unsorted)


def test_price_coverage_validation_success(synthetic_prices, synthetic_dates):
    """Verify that complete price coverage passes validation."""
    validate_price_coverage(synthetic_prices, synthetic_dates, lookback=20)


def test_price_coverage_missing_sector(synthetic_prices, synthetic_dates):
    """Verify that missing sector in price DataFrame raises KeyError."""
    bad_prices = synthetic_prices.drop(columns=["AUTO"])
    with pytest.raises(KeyError, match="missing required sector"):
        validate_price_coverage(bad_prices, synthetic_dates)


def test_price_coverage_missing_dates(synthetic_prices, synthetic_dates):
    """Verify that missing dates in price DataFrame raise KeyError."""
    bad_prices = synthetic_prices.iloc[:-5]
    with pytest.raises(KeyError, match="missing .* required simulation dates"):
        validate_price_coverage(bad_prices, synthetic_dates)


def test_price_coverage_insufficient_warmup(synthetic_prices, synthetic_dates):
    """Verify that insufficient warmup history for volatility calculation raises ValueError."""
    # Slice prices starting right at the simulation date (0 warmup sessions)
    bad_prices = synthetic_prices.loc[synthetic_dates]
    with pytest.raises(ValueError, match="Insufficient historical price sessions"):
        validate_price_coverage(bad_prices, synthetic_dates, lookback=20)


# =====================================================================
# 3. Timeline Partition Verification Tests
# =====================================================================

def test_timeline_partition_verification(synthetic_prob_df):
    """Verify that timeline partition correctly flags counts deviating from canonical targets."""
    # Test on synthetic data should raise ValueError because counts are not 1265/422
    with pytest.raises(ValueError, match=f"Expected {EXPECTED_TOTAL_SESSIONS} total sessions"):
        validate_timeline_partition(synthetic_prob_df)


# =====================================================================
# 4. Schedule Generation and Variant Tests
# =====================================================================

def test_generate_portfolio_schedule_all_four_variants(synthetic_prob_df, synthetic_prices):
    """Verify that all four variants (1A, 1B, 2A, 2B) generate valid schedules."""
    for v in ["1A", "1B", "2A", "2B"]:
        sched = generate_portfolio_schedule(v, synthetic_prob_df, price_df=synthetic_prices)
        assert len(sched) == len(synthetic_prob_df)
        assert list(sched.columns) == SCHEDULE_COLUMNS
        assert (sched["variant"] == v).all()
        # Invariants: sum of weights = 1.0, non-negative
        w_sums = sched[WEIGHT_COLS].sum(axis=1)
        assert np.allclose(w_sums, 1.0, atol=1e-5)
        assert (sched[WEIGHT_COLS].values >= -1e-8).all()


def test_target_weights_and_cash_invariants_template_a(synthetic_prob_df, synthetic_prices):
    """Verify that Template A variants (1A, 1B) have strictly 0.0 cash across all sessions."""
    for v in ["1A", "1B"]:
        sched = generate_portfolio_schedule(v, synthetic_prob_df, price_df=synthetic_prices)
        assert np.allclose(sched["w_CASH"].values, 0.0, atol=1e-5)


def test_target_weights_and_cash_invariants_template_b(synthetic_prob_df, synthetic_prices):
    """Verify that Template B variants (2A, 2B) enforce regime-specific cash targets post-rebalance."""
    for v in ["2A", "2B"]:
        sched = generate_portfolio_schedule(v, synthetic_prob_df, price_df=synthetic_prices)
        rebal_dates = sched[sched["rebalance_triggered"]].index
        assert len(rebal_dates) > 0
        post_rebal = sched.loc[rebal_dates[0]:]
        for _, row in post_rebal.iterrows():
            inc = int(row["incumbent_regime_after"])
            expected_cash = TEMPLATE_B_CASH[inc]
            assert np.isclose(row["w_CASH"], expected_cash, atol=1e-5)


def test_day0_initialization_invariant(synthetic_prob_df, synthetic_prices):
    """Verify that Day 0 initial state has holding_days_before = 0 and incumbent_before = None."""
    for v in ["1A", "1B", "2A", "2B"]:
        sched = generate_portfolio_schedule(v, synthetic_prob_df, price_df=synthetic_prices)
        day0 = sched.iloc[0]
        assert day0["holding_days_before"] == 0
        assert pd.isna(day0["incumbent_regime_before"])
        # Because synthetic_prob_df Day 0 has a confident signal (0.80), initial rebalance triggers
        assert bool(day0["rebalance_triggered"]) is True
        assert np.isclose(day0["turnover"], 1.0, atol=1e-5)


def test_next_day_close_execution_timing(synthetic_prob_df, synthetic_prices):
    """Verify that exec_date is strictly next trading session (t+1) for all bars except last."""
    sched = generate_portfolio_schedule("1A", synthetic_prob_df, price_df=synthetic_prices)
    for i in range(len(sched) - 1):
        assert sched["exec_date"].iloc[i] == sched.index[i + 1]


def test_deterministic_schedule_generation(synthetic_prob_df, synthetic_prices):
    """Verify that repeated runs on identical inputs yield bit-for-bit identical outputs."""
    sched1 = generate_portfolio_schedule("1B", synthetic_prob_df, price_df=synthetic_prices)
    sched2 = generate_portfolio_schedule("1B", synthetic_prob_df, price_df=synthetic_prices)
    pd.testing.assert_frame_equal(sched1, sched2)


# =====================================================================
# 5. Train-to-Holdout State Continuity Tests
# =====================================================================

def test_continuous_state_across_train_holdout_boundary(synthetic_prob_df, synthetic_prices):
    """
    Verify continuous state across train/holdout boundary:
    incumbent_regime and holding_days carry seamlessly from train end to holdout start.
    """
    sched = generate_portfolio_schedule("1A", synthetic_prob_df, price_df=synthetic_prices)
    train_end_idx = 19
    holdout_start_idx = 20

    train_end_row = sched.iloc[train_end_idx]
    holdout_start_row = sched.iloc[holdout_start_idx]

    assert train_end_row["period"] == "train"
    assert holdout_start_row["period"] == "holdout"

    # Continuity assertions
    assert train_end_row["incumbent_regime_after"] == holdout_start_row["incumbent_regime_before"]
    assert train_end_row["holding_days_after"] == holdout_start_row["holding_days_before"]


def test_no_unintended_portfolio_reset_at_holdout_start(synthetic_prob_df, synthetic_prices):
    """
    Verify that portfolio holdings are NOT reset to NIFTY 50 at the start of holdout.
    """
    sched = generate_portfolio_schedule("1A", synthetic_prob_df, price_df=synthetic_prices)
    holdout_start_row = sched.iloc[20]
    # At index 20, incumbent was R3 (PHARMA + FMCG). w_NIFTY50 must remain 0.0
    assert np.isclose(holdout_start_row["w_NIFTY50"], 0.0, atol=1e-5)


# =====================================================================
# 6. Serialization and Verification Tests
# =====================================================================

def test_csv_serialization_reload_parity(synthetic_prob_df, synthetic_prices, tmp_path):
    """
    Verify that schedules serialized to disk can be reloaded with complete schema
    and numerical parity.
    """
    schedules = {}
    for v in ["1A", "2A"]:
        schedules[v] = generate_portfolio_schedule(v, synthetic_prob_df, price_df=synthetic_prices)

    saved_paths = save_target_weight_schedules(schedules, output_dir=tmp_path)
    assert len(saved_paths) == 2

    for v, p in saved_paths.items():
        assert p.exists()
        reloaded = pd.read_csv(p, parse_dates=["Date", "exec_date"]).set_index("Date")
        assert len(reloaded) == len(synthetic_prob_df)
        assert list(reloaded.columns) == SCHEDULE_COLUMNS
        # Test exact parity
        orig = schedules[v]
        for col in orig.columns:
            if col in ["period", "variant", "exec_date"]:
                assert (orig[col].values == reloaded[col].values).all()
            elif orig[col].dtype == bool:
                assert (orig[col].values == reloaded[col].values).all()
            else:
                o_vals = orig[col].fillna(-999).values.astype(float)
                r_vals = reloaded[col].fillna(-999).values.astype(float)
                assert np.allclose(o_vals, r_vals, atol=1e-5)


def test_preservation_of_rules_engine_behavior(synthetic_prob_df, synthetic_prices):
    """
    Verify that generate_portfolio_schedule produces identical rebalance decisions
    and turnover as direct RegimeRotationRulesEngine execution.
    """
    for v in ["1A", "1B", "2A", "2B"]:
        sched_module = generate_portfolio_schedule(v, synthetic_prob_df, price_df=synthetic_prices)
        engine_direct = RegimeRotationRulesEngine(variant=v)
        sched_direct = engine_direct.generate_schedule(
            synthetic_prob_df.index, synthetic_prob_df, price_df=synthetic_prices
        )

        assert (sched_module["rebalance_triggered"].values == sched_direct["rebalance_triggered"].values).all()
        assert np.allclose(sched_module["turnover"].values, sched_direct["turnover"].values, atol=1e-5)
        assert np.allclose(sched_module["w_CASH"].values, sched_direct["w_CASH"].values, atol=1e-5)


# =====================================================================
# 7. Real Canonical Artifact Integration Test
# =====================================================================

def test_canonical_artifacts_loading_and_partition():
    """
    Integration test verifying that the canonical probability and price artifacts
    load and validate against frozen timeline specifications.
    """
    prob_df = load_causal_probabilities()
    price_df = load_aligned_prices()

    partition_meta = validate_timeline_partition(prob_df)
    assert partition_meta["total_sessions"] == EXPECTED_TOTAL_SESSIONS
    assert partition_meta["train_sessions"] == EXPECTED_TRAIN_SESSIONS
    assert partition_meta["holdout_sessions"] == EXPECTED_HOLDOUT_SESSIONS
    assert partition_meta["train_start"] == EXPECTED_TRAIN_START
    assert partition_meta["train_end"] == EXPECTED_TRAIN_END
    assert partition_meta["holdout_start"] == EXPECTED_HOLDOUT_START
    assert partition_meta["holdout_end"] == EXPECTED_HOLDOUT_END

    validate_price_coverage(price_df, prob_df.index)
