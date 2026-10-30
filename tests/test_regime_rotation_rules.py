"""
tests/test_regime_rotation_rules.py
===================================
Automated Unit and Integration Tests for Phase 8.3 Sector Rotation Rules Engine:

1. R0-R5 allocation mapping.
2. All four strategy variants (1A, 1B, 2A, 2B).
3. Exact agreed equal-weighted allocations, including R3 special handling.
4. Inverse-volatility weights using trailing 20-return lookback.
5. Volatility-floor behavior (1e-4 floor).
6. Confidence threshold acceptance (P >= 0.50) and rejection (P < 0.50).
7. Missing and invalid probabilities (NaNs, negative, bad sum).
8. Boundary ties and incumbent-regime persistence.
9. Retaining previous weights when confidence is insufficient.
10. NIFTY 50 initialization (Day 0 100% benchmark holding).
11. Turnover and transaction costs for the first allocation transition.
12. Next-day-close execution timing (Day t signal -> Day t+1 execution).
13. Five-day minimum holding period enforcement.
14. R3 holding-period bypass without same-day execution.
15. Nonnegative weights and sum equal to 1.0.
16. No future-return leakage or use of retrospective HMM labels.
17. Deterministic behavior for identical inputs.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from src.regime_rotation_rules import (
    SECTOR_NAMES,
    BENCHMARK_NAME,
    CASH_NAME,
    ALL_ASSETS,
    REGIME_SECTORS,
    TEMPLATE_A_CASH,
    TEMPLATE_B_CASH,
    StrategyVariant,
    create_zero_weights,
    create_nifty50_initial_weights,
    validate_portfolio_weights,
    calculate_equal_weights,
    calculate_trailing_volatilities,
    calculate_inverse_vol_weights,
    get_target_regime_weights,
    accept_regime_signal,
    calculate_turnover,
    calculate_transaction_cost,
    RegimeRotationRulesEngine,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MIN_HOLDING_DAYS,
    DEFAULT_TRANSACTION_COST_RATE,
    DEFAULT_VOLATILITY_LOOKBACK,
    DEFAULT_VOLATILITY_FLOOR,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_prices() -> pd.DataFrame:
    """Generate 60 trading days of deterministic synthetic prices for all assets."""
    np.random.seed(42)
    dates = pd.bdate_range("2024-01-01", periods=60)
    data = {}
    data[BENCHMARK_NAME] = 10000.0 * np.exp(np.cumsum(np.random.normal(0.0005, 0.01, size=60)))
    for s in SECTOR_NAMES:
        vol = 0.015 if s in ["IT", "FMCG", "PHARMA"] else 0.025
        data[s] = 5000.0 * np.exp(np.cumsum(np.random.normal(0.0004, vol, size=60)))
    return pd.DataFrame(data, index=dates)


# ---------------------------------------------------------------------------
# 1. R0-R5 Allocation Mapping & Nonnegativity / Sum to 1.0
# ---------------------------------------------------------------------------

def test_r0_r5_allocation_mapping():
    """Verify that every regime 0..5 maps to valid non-empty sector pairs and valid weights."""
    for r_id in range(6):
        assert r_id in REGIME_SECTORS
        s1, s2 = REGIME_SECTORS[r_id]
        assert s1 in SECTOR_NAMES
        assert s2 in SECTOR_NAMES
        assert s1 != s2

        # Template A check
        w_a = calculate_equal_weights(r_id, template="A")
        validate_portfolio_weights(w_a)
        assert w_a[s1] == 0.50
        assert w_a[s2] == 0.50
        assert w_a[CASH_NAME] == 0.0

        # Template B check
        w_b = calculate_equal_weights(r_id, template="B")
        validate_portfolio_weights(w_b)
        assert w_b[CASH_NAME] == TEMPLATE_B_CASH[r_id]


# ---------------------------------------------------------------------------
# 2. All Four Strategy Variants
# ---------------------------------------------------------------------------

def test_all_four_strategy_variants():
    """Verify parsing and behavior across 1A, 1B, 2A, 2B."""
    variants = ["1A", "1B", "2A", "2B"]
    dummy_vols = {s: 0.20 for s in SECTOR_NAMES}

    for v in variants:
        v_enum = StrategyVariant.from_str(v)
        assert isinstance(v_enum, StrategyVariant)
        w = get_target_regime_weights(regime_id=0, variant=v_enum, volatilities=dummy_vols)
        validate_portfolio_weights(w)

        if v_enum.template == "A":
            assert w[CASH_NAME] == 0.0
        else:
            assert w[CASH_NAME] == TEMPLATE_B_CASH[0]


# ---------------------------------------------------------------------------
# 3. Exact Agreed Equal-Weighted Allocations (Including R3 Special Case)
# ---------------------------------------------------------------------------

def test_exact_agreed_equal_weighted_allocations():
    """Verify exact numerical values for all regimes under Templates A and B."""
    # R0: 50% IT, 50% METAL
    w0_a = calculate_equal_weights(0, "A")
    assert w0_a["IT"] == 0.50 and w0_a["METAL"] == 0.50 and w0_a[CASH_NAME] == 0.0

    # R1: 50/50 in A, 35/35/30 in B
    w1_a = calculate_equal_weights(1, "A")
    assert w1_a["AUTO"] == 0.50 and w1_a["METAL"] == 0.50 and w1_a[CASH_NAME] == 0.0
    w1_b = calculate_equal_weights(1, "B")
    assert w1_b["AUTO"] == 0.35 and w1_b["METAL"] == 0.35 and w1_b[CASH_NAME] == 0.30

    # R2: 50% IT, 50% PHARMA
    w2_a = calculate_equal_weights(2, "A")
    assert w2_a["IT"] == 0.50 and w2_a["PHARMA"] == 0.50 and w2_a[CASH_NAME] == 0.0
    w2_b = calculate_equal_weights(2, "B")
    assert w2_b["IT"] == 0.50 and w2_b["PHARMA"] == 0.50 and w2_b[CASH_NAME] == 0.0

    # R3: 50/50 in A, 40% PHARMA / 20% FMCG / 40% Cash in B (agreed special case)
    w3_a = calculate_equal_weights(3, "A")
    assert w3_a["PHARMA"] == 0.50 and w3_a["FMCG"] == 0.50 and w3_a[CASH_NAME] == 0.0
    w3_b = calculate_equal_weights(3, "B")
    assert w3_b["PHARMA"] == 0.40 and w3_b["FMCG"] == 0.20 and w3_b[CASH_NAME] == 0.40

    # R4: 50% METAL, 50% AUTO
    w4_a = calculate_equal_weights(4, "A")
    assert w4_a["METAL"] == 0.50 and w4_a["AUTO"] == 0.50 and w4_a[CASH_NAME] == 0.0

    # R5: 50/50 in A, 40/40/20 in B
    w5_a = calculate_equal_weights(5, "A")
    assert w5_a["PHARMA"] == 0.50 and w5_a["FMCG"] == 0.50 and w5_a[CASH_NAME] == 0.0
    w5_b = calculate_equal_weights(5, "B")
    assert w5_b["PHARMA"] == 0.40 and w5_b["FMCG"] == 0.40 and w5_b[CASH_NAME] == 0.20


# ---------------------------------------------------------------------------
# 4. Inverse-Volatility Weights (Trailing 20-Day Lookback)
# ---------------------------------------------------------------------------

def test_inverse_volatility_weights_calculation(synthetic_prices):
    """Verify that inverse-volatility weighting shifts capital to the lower-volatility sector."""
    test_date = synthetic_prices.index[30]
    vols = calculate_trailing_volatilities(synthetic_prices, current_date=test_date, lookback=20)

    # In synthetic prices, IT is lower vol than METAL
    assert vols["IT"] < vols["METAL"]

    # In R0 (IT + METAL), IT should receive higher weight than METAL
    w_inv = calculate_inverse_vol_weights(regime_id=0, volatilities=vols, template="A")
    validate_portfolio_weights(w_inv)
    assert w_inv["IT"] > w_inv["METAL"]
    assert np.isclose(w_inv["IT"] + w_inv["METAL"], 1.0)

    # For R3 Template B, 60% equity split between PHARMA and FMCG + 40% Cash
    w_r3_inv = calculate_inverse_vol_weights(regime_id=3, volatilities=vols, template="B")
    validate_portfolio_weights(w_r3_inv)
    assert w_r3_inv[CASH_NAME] == 0.40
    assert np.isclose(w_r3_inv["PHARMA"] + w_r3_inv["FMCG"], 0.60)


# ---------------------------------------------------------------------------
# 5. Volatility-Floor Behavior
# ---------------------------------------------------------------------------

def test_volatility_floor_behavior():
    """Verify that 1e-4 floor prevents division by zero when volatility is 0 or tiny."""
    zero_vols = {s: 0.0 for s in SECTOR_NAMES}
    w = calculate_inverse_vol_weights(regime_id=0, volatilities=zero_vols, template="A", floor=1e-4)
    validate_portfolio_weights(w)
    # When both are floored at 1e-4, weights are equal
    assert np.isclose(w["IT"], 0.50)
    assert np.isclose(w["METAL"], 0.50)


# ---------------------------------------------------------------------------
# 6. Confidence Threshold Acceptance and Rejection
# ---------------------------------------------------------------------------

def test_confidence_threshold_acceptance_and_rejection():
    """Verify P >= 0.50 is accepted and P < 0.50 is rejected."""
    # Strong signal for R4 (P=0.80)
    p_high = [0.05, 0.05, 0.05, 0.02, 0.80, 0.03]
    res_high = accept_regime_signal(p_high, threshold=0.50, incumbent_regime=None)
    assert res_high.is_confident is True
    assert res_high.accepted_regime == 4

    # Borderline accepted signal (P=0.50)
    p_exact = [0.50, 0.10, 0.10, 0.10, 0.10, 0.10]
    res_exact = accept_regime_signal(p_exact, threshold=0.50, incumbent_regime=None)
    assert res_exact.is_confident is True
    assert res_exact.accepted_regime == 0

    # Diffuse signal (max P = 0.35 < 0.50)
    p_diffuse = [0.35, 0.20, 0.15, 0.10, 0.10, 0.10]
    res_diffuse = accept_regime_signal(p_diffuse, threshold=0.50, incumbent_regime=2)
    assert res_diffuse.is_confident is False
    assert res_diffuse.accepted_regime == 2  # persists incumbent


# ---------------------------------------------------------------------------
# 7. Missing and Invalid Probabilities
# ---------------------------------------------------------------------------

def test_missing_and_invalid_probabilities():
    """Verify that NaN, Inf, negative, bad length, or unnormalized inputs raise ValueError."""
    with pytest.raises(ValueError, match="Expected 6"):
        accept_regime_signal([0.5, 0.5])

    with pytest.raises(ValueError, match="NaN or Inf"):
        accept_regime_signal([0.5, np.nan, 0.2, 0.1, 0.1, 0.1])

    with pytest.raises(ValueError, match="Negative"):
        accept_regime_signal([-0.1, 0.6, 0.2, 0.1, 0.1, 0.1])

    with pytest.raises(ValueError, match="sum to ~1.0"):
        accept_regime_signal([0.1, 0.1, 0.1, 0.1, 0.1, 0.1])  # sums to 0.6


# ---------------------------------------------------------------------------
# 8. Boundary Ties and Incumbent-Regime Persistence
# ---------------------------------------------------------------------------

def test_boundary_ties_and_incumbent_persistence():
    """Verify that an exact tie at 0.50 favors incumbent regime if tied."""
    # R0 and R4 tied at 0.50
    p_tie = [0.50, 0.0, 0.0, 0.0, 0.50, 0.0]

    # If incumbent is 4, it should retain 4
    res_incumbent_4 = accept_regime_signal(p_tie, threshold=0.50, incumbent_regime=4)
    assert res_incumbent_4.accepted_regime == 4
    assert res_incumbent_4.was_tied is True

    # If incumbent is 0, it should retain 0
    res_incumbent_0 = accept_regime_signal(p_tie, threshold=0.50, incumbent_regime=0)
    assert res_incumbent_0.accepted_regime == 0

    # If incumbent is None or 2 (not in tied set), picks first candidate (0)
    res_other = accept_regime_signal(p_tie, threshold=0.50, incumbent_regime=2)
    assert res_other.accepted_regime == 0


# ---------------------------------------------------------------------------
# 9. Retaining Previous Weights When Confidence is Insufficient
# ---------------------------------------------------------------------------

def test_retaining_previous_weights_on_low_confidence():
    """Verify engine does not change weights when max probability < 0.50."""
    dates = pd.bdate_range("2024-01-01", periods=10)
    # Day 0-4 confident in R4 (P=0.9), Day 5-9 diffuse (P=0.25)
    probs = []
    for i in range(10):
        if i < 5:
            probs.append([0.02, 0.02, 0.02, 0.02, 0.90, 0.02])
        else:
            probs.append([0.20, 0.20, 0.20, 0.20, 0.10, 0.10])
    prob_df = pd.DataFrame(probs, index=dates)

    engine = RegimeRotationRulesEngine(variant="1A")
    sched = engine.generate_schedule(dates=dates, probabilities_df=prob_df)

    # After initial transition, weights should remain R4 (METAL=0.5, AUTO=0.5) throughout
    for i in range(1, 10):
        assert sched.iloc[i]["w_METAL"] == 0.50
        assert sched.iloc[i]["w_AUTO"] == 0.50
        if i >= 5:
            assert bool(sched.iloc[i]["is_confident"]) is False
            assert bool(sched.iloc[i]["rebalance_triggered"]) is False


# ---------------------------------------------------------------------------
# 10. NIFTY 50 Initialization (Day 0 Holding)
# ---------------------------------------------------------------------------

def test_nifty50_initialization():
    """Verify that Day 0 initial state is 100% NIFTY 50 and zero elsewhere."""
    init_w = create_nifty50_initial_weights()
    validate_portfolio_weights(init_w)
    assert init_w[BENCHMARK_NAME] == 1.0
    for s in SECTOR_NAMES:
        assert init_w[s] == 0.0
    assert init_w[CASH_NAME] == 0.0


# ---------------------------------------------------------------------------
# 11. Turnover and Costs for the First Allocation Transition
# ---------------------------------------------------------------------------

def test_first_transition_turnover_and_cost():
    """Verify that rotating from NIFTY 50 (100%) to a 50/50 sector portfolio costs 15 bps."""
    init_w = create_nifty50_initial_weights()
    target_w = calculate_equal_weights(0, "A")  # 50% IT, 50% METAL

    turnover = calculate_turnover(init_w, target_w)
    # 0.5 * (|0 - 1| + |0.5 - 0| + |0.5 - 0|) = 0.5 * (1 + 0.5 + 0.5) = 1.0
    assert np.isclose(turnover, 1.0)

    cost = calculate_transaction_cost(turnover, cost_rate=0.0015)
    assert np.isclose(cost, 0.0015)


# ---------------------------------------------------------------------------
# 12. Next-Day-Close Execution Timing (t+1 Close)
# ---------------------------------------------------------------------------

def test_next_day_close_execution_timing():
    """Verify that a signal on Day t schedules execution for Day t+1."""
    dates = pd.bdate_range("2024-01-01", periods=5)
    prob_df = pd.DataFrame(
        [[0.05, 0.05, 0.05, 0.05, 0.75, 0.05]] * 5,
        index=dates,
    )

    engine = RegimeRotationRulesEngine(variant="1A")
    sched = engine.generate_schedule(dates=dates, probabilities_df=prob_df)

    # Check signal_date vs exec_date
    for i in range(len(dates) - 1):
        row = sched.iloc[i]
        assert row.name == dates[i]
        assert row["exec_date"] == dates[i + 1]


# ---------------------------------------------------------------------------
# 13. Five-Day Minimum Holding Period Enforcement
# ---------------------------------------------------------------------------

def test_five_day_minimum_holding_period():
    """Verify that an elective regime change cannot execute before 5 days have elapsed."""
    dates = pd.bdate_range("2024-01-01", periods=10)
    # Day 0..2: R4 (P=0.9)
    # Day 3..5: R0 (P=0.9) -> attempt elective switch on day 3
    # Day 6..9: R0 (P=0.9) -> holding satisfied
    probs = []
    for i in range(10):
        if i < 3:
            probs.append([0.02, 0.02, 0.02, 0.02, 0.90, 0.02])  # R4
        else:
            probs.append([0.90, 0.02, 0.02, 0.02, 0.02, 0.02])  # R0

    prob_df = pd.DataFrame(probs, index=dates)
    engine = RegimeRotationRulesEngine(variant="1A", min_holding_days=5)
    sched = engine.generate_schedule(dates=dates, probabilities_df=prob_df)

    # Day 0: initial transition into R4
    assert bool(sched.iloc[0]["rebalance_triggered"]) is True

    # Days 1, 2: R4 holding
    assert bool(sched.iloc[1]["rebalance_triggered"]) is False
    assert bool(sched.iloc[2]["rebalance_triggered"]) is False

    # Day 3: R0 signals, but holding_days < 5 -> blocked!
    assert sched.iloc[3]["raw_regime_argmax"] == 0
    assert bool(sched.iloc[3]["rebalance_triggered"]) is False
    assert sched.iloc[3]["w_METAL"] == 0.50  # remains in R4

    # Day 4, 5: still blocked (holding_days < 5)
    assert bool(sched.iloc[4]["rebalance_triggered"]) is False
    assert sched.iloc[5]["holding_days_before"] == 4
    assert bool(sched.iloc[5]["rebalance_triggered"]) is False

    # Day 6: holding_days >= 5 -> elective rebalance allowed!
    assert sched.iloc[6]["holding_days_before"] >= 5
    assert bool(sched.iloc[6]["rebalance_triggered"]) is True
    assert sched.iloc[6]["w_IT"] == 0.50  # now rotated into R0


# ---------------------------------------------------------------------------
# 14. R3 Holding-Period Bypass Without Same-Day Execution
# ---------------------------------------------------------------------------

def test_r3_crisis_bypass_without_same_day_execution():
    """Verify that an accepted R3 signal bypasses lockup immediately, but still executes at t+1 Close."""
    dates = pd.bdate_range("2024-01-01", periods=6)
    # Day 0, 1: R4 (Expansion)
    # Day 2: R3 Panic Crash! (holding_days=1 < 5)
    probs = [
        [0.02, 0.02, 0.02, 0.02, 0.90, 0.02],  # Day 0: R4
        [0.02, 0.02, 0.02, 0.02, 0.90, 0.02],  # Day 1: R4
        [0.02, 0.02, 0.02, 0.90, 0.02, 0.02],  # Day 2: R3 (Crisis!)
        [0.02, 0.02, 0.02, 0.90, 0.02, 0.02],  # Day 3: R3
        [0.02, 0.02, 0.02, 0.90, 0.02, 0.02],  # Day 4: R3
        [0.02, 0.02, 0.02, 0.90, 0.02, 0.02],  # Day 5: R3
    ]
    prob_df = pd.DataFrame(probs, index=dates)

    engine = RegimeRotationRulesEngine(variant="2A", min_holding_days=5)
    sched = engine.generate_schedule(dates=dates, probabilities_df=prob_df)

    # Day 2: R3 triggered despite holding_days < 5 (holding_days_before == 1)
    assert sched.iloc[2]["holding_days_before"] < 5
    assert bool(sched.iloc[2]["rebalance_triggered"]) is True
    assert bool(sched.iloc[2]["rebalance_bypassed_r3"]) is True

    # Scheduled execution is t+1 (Day 3 close), NOT same day
    assert sched.iloc[2]["exec_date"] == dates[3]
    # Target weights for Template B R3: 40% PHARMA, 20% FMCG, 40% Cash
    assert sched.iloc[2]["w_PHARMA"] == 0.40
    assert sched.iloc[2]["w_FMCG"] == 0.20
    assert sched.iloc[2]["w_CASH"] == 0.40


# ---------------------------------------------------------------------------
# 15. Nonnegative Weights and Sum Equal to 1.0 (All Sessions)
# ---------------------------------------------------------------------------

def test_weights_simplex_constraint_across_entire_schedule(synthetic_prices):
    """Verify that all weights across every row of schedule are non-negative and sum to 1.0."""
    dates = synthetic_prices.index[:30]
    # Alternate through all 6 regimes
    probs = []
    for i in range(len(dates)):
        r = (i // 5) % 6
        p = [0.05] * 6
        p[r] = 0.75
        probs.append(p)
    prob_df = pd.DataFrame(probs, index=dates)

    for v in ["1A", "1B", "2A", "2B"]:
        engine = RegimeRotationRulesEngine(variant=v)
        sched = engine.generate_schedule(dates=dates, probabilities_df=prob_df, price_df=synthetic_prices)

        for _, row in sched.iterrows():
            w_dict = {asset: row[f"w_{asset}"] for asset in ALL_ASSETS}
            validate_portfolio_weights(w_dict)


# ---------------------------------------------------------------------------
# 16. No Future-Return Leakage or Use of Retrospective Labels
# ---------------------------------------------------------------------------

def test_no_future_return_leakage_in_volatility(synthetic_prices):
    """Verify that trailing volatility calculation on date t is invariant to future prices t+1..T."""
    date_t = synthetic_prices.index[25]
    vols_original = calculate_trailing_volatilities(synthetic_prices, current_date=date_t, lookback=20)

    # Corrupt future prices on date t+1 onwards
    corrupted_prices = synthetic_prices.copy()
    corrupted_prices.loc[synthetic_prices.index > date_t] = 999999.0

    vols_corrupted = calculate_trailing_volatilities(corrupted_prices, current_date=date_t, lookback=20)

    for s in SECTOR_NAMES:
        assert np.isclose(vols_original[s], vols_corrupted[s])


# ---------------------------------------------------------------------------
# 17. Deterministic Behavior for Identical Inputs
# ---------------------------------------------------------------------------

def test_deterministic_behavior(synthetic_prices):
    """Verify that running the engine twice on identical inputs produces bitwise identical results."""
    dates = synthetic_prices.index[:25]
    probs = [[0.1, 0.1, 0.1, 0.1, 0.5, 0.1] if i % 2 == 0 else [0.5, 0.1, 0.1, 0.1, 0.1, 0.1] for i in range(25)]
    prob_df = pd.DataFrame(probs, index=dates)

    engine1 = RegimeRotationRulesEngine(variant="1B")
    engine2 = RegimeRotationRulesEngine(variant="1B")

    sched1 = engine1.generate_schedule(dates=dates, probabilities_df=prob_df, price_df=synthetic_prices)
    sched2 = engine2.generate_schedule(dates=dates, probabilities_df=prob_df, price_df=synthetic_prices)

    pd.testing.assert_frame_equal(sched1, sched2)


# ---------------------------------------------------------------------------
# 18. Continuous Probability Precedence Over regime_id
# ---------------------------------------------------------------------------

def test_continuous_probability_precedence_over_regime_id():
    """
    Verify that when both continuous prob_0..prob_5 and regime_id are present,
    the engine prioritizes the genuine probability distribution over regime_id.
    """
    dates = pd.bdate_range("2024-01-01", periods=5)
    data = []
    for _ in range(5):
        # regime_id says 0, but genuine probability strongly indicates R4 (P=0.85)
        row = {f"prob_{j}": 0.03 for j in range(6)}
        row["prob_4"] = 0.85
        row["regime_id"] = 0
        data.append(row)
    prob_df = pd.DataFrame(data, index=dates)

    engine = RegimeRotationRulesEngine(variant="1A")
    sched = engine.generate_schedule(dates=dates, probabilities_df=prob_df)

    # Should allocate to R4 (METAL/AUTO), NOT R0 (IT/METAL)
    assert sched.iloc[0]["raw_regime_argmax"] == 4
    assert sched.iloc[0]["accepted_regime"] == 4
    assert sched.iloc[0]["max_probability"] == 0.85
    assert sched.iloc[0]["w_METAL"] == 0.50
    assert sched.iloc[0]["w_AUTO"] == 0.50
    assert sched.iloc[0]["w_IT"] == 0.0


# ---------------------------------------------------------------------------
# 19. Continuous Probability Confidence Threshold Filtering
# ---------------------------------------------------------------------------

def test_continuous_probability_confidence_threshold_filtering():
    """
    Verify that diffuse continuous probabilities (max P < 0.50) are rejected
    and the portfolio retains its incumbent allocation.
    """
    dates = pd.bdate_range("2024-01-01", periods=6)
    # Day 0: Confident in R2 (P=0.70)
    # Days 1..5: Diffuse transition with max P = 0.40 in R0, but no regime >= 0.50
    data = []
    # Day 0: confident in R2
    p0 = {f"prob_{j}": 0.06 for j in range(6)}
    p0["prob_2"] = 0.70
    data.append(p0)

    # Days 1..5: diffuse, R0 is leading candidate but only 0.40
    for _ in range(5):
        p_diff = {f"prob_{j}": 0.12 for j in range(6)}
        p_diff["prob_0"] = 0.40
        data.append(p_diff)

    prob_df = pd.DataFrame(data, index=dates)

    engine = RegimeRotationRulesEngine(variant="1A", min_holding_days=1)
    sched = engine.generate_schedule(dates=dates, probabilities_df=prob_df)

    # Day 0: enters R2 (IT + PHARMA)
    assert sched.iloc[0]["accepted_regime"] == 2
    assert bool(sched.iloc[0]["rebalance_triggered"]) is True
    assert sched.iloc[0]["w_IT"] == 0.50
    assert sched.iloc[0]["w_PHARMA"] == 0.50

    # Days 1..5: R0 has max probability (0.40), but 0.40 < 0.50 -> rejected!
    for i in range(1, 6):
        assert sched.iloc[i]["raw_regime_argmax"] == 0
        assert sched.iloc[i]["max_probability"] == 0.40
        assert bool(sched.iloc[i]["is_confident"]) is False
        assert sched.iloc[i]["accepted_regime"] == 2  # retains incumbent R2
        assert bool(sched.iloc[i]["rebalance_triggered"]) is False
        assert sched.iloc[i]["w_IT"] == 0.50
        assert sched.iloc[i]["w_PHARMA"] == 0.50


# ---------------------------------------------------------------------------
# 20. Malformed Continuous Probability Vectors Rejected
# ---------------------------------------------------------------------------

def test_malformed_continuous_probability_vectors_rejected():
    """Verify that continuous probabilities with NaNs, Infs, or bad sums raise ValueError."""
    dates = pd.bdate_range("2024-01-01", periods=3)

    # NaN in probabilities
    bad_nan = pd.DataFrame(
        [
            {"prob_0": np.nan, "prob_1": 0.2, "prob_2": 0.2, "prob_3": 0.2, "prob_4": 0.2, "prob_5": 0.2},
            {"prob_0": 0.2, "prob_1": 0.2, "prob_2": 0.2, "prob_3": 0.2, "prob_4": 0.2, "prob_5": 0.2},
            {"prob_0": 0.2, "prob_1": 0.2, "prob_2": 0.2, "prob_3": 0.2, "prob_4": 0.2, "prob_5": 0.2},
        ],
        index=dates,
    )
    engine = RegimeRotationRulesEngine(variant="1A")
    with pytest.raises(ValueError, match="NaN or Inf"):
        engine.generate_schedule(dates=dates, probabilities_df=bad_nan)

    # Row sum does not equal 1.0
    bad_sum = pd.DataFrame(
        [
            {"prob_0": 0.1, "prob_1": 0.1, "prob_2": 0.1, "prob_3": 0.1, "prob_4": 0.1, "prob_5": 0.1},
        ] * 3,
        index=dates,
    )
    with pytest.raises(ValueError, match="sum to ~1.0"):
        engine.generate_schedule(dates=dates, probabilities_df=bad_sum)


# ---------------------------------------------------------------------------
# 21. End-to-End Recovery File Ingestion on Actual hmm_causal_probabilities.csv
# ---------------------------------------------------------------------------

def test_recovered_hmm_causal_probabilities_file_ingestion(synthetic_prices):
    """
    Verify that results/regime_discovery/hmm_causal_probabilities.csv can be loaded
    directly into RegimeRotationRulesEngine across all 4 strategy variants.
    """
    prob_path = Path("results/regime_discovery/hmm_causal_probabilities.csv")
    if not prob_path.exists():
        pytest.skip("hmm_causal_probabilities.csv not present.")

    prob_df = pd.read_csv(prob_path, parse_dates=["Date"]).set_index("Date")
    # Intersect with synthetic prices date range (2024)
    common_dates = [d for d in synthetic_prices.index if d in prob_df.index][:25]
    assert len(common_dates) > 0, "No common dates between synthetic_prices and hmm_causal_probabilities."

    test_dates = pd.DatetimeIndex(common_dates)

    for v in ["1A", "1B", "2A", "2B"]:
        engine = RegimeRotationRulesEngine(variant=v)
        sched = engine.generate_schedule(
            dates=test_dates,
            probabilities_df=prob_df,
            price_df=synthetic_prices if "1B" in v or "2B" in v else None,
        )
        assert len(sched) == len(test_dates)
        assert "is_confident" in sched.columns
        for _, row in sched.iterrows():
            w_dict = {asset: row[f"w_{asset}"] for asset in ALL_ASSETS}
            validate_portfolio_weights(w_dict)

