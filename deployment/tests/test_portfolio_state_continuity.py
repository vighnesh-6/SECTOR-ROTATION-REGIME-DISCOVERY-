"""
deployment/tests/test_portfolio_state_continuity.py
===================================================
Tests strategy allocations, holding lockups, crisis override, turnover, and NAV drift.
"""

import sys
from pathlib import Path
import pytest
import numpy as np

DEPLOYMENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEPLOYMENT_ROOT))

from engine.portfolio_state import (
    calculate_equal_weights,
    calculate_turnover,
    evaluate_rebalance_trigger,
    step_daily_nav,
    validate_weights,
    REGIME_SECTORS,
)


def test_equal_weights_allocations():
    # R0: 50% IT, 50% METAL
    w0 = calculate_equal_weights(0, template="A")
    assert w0["IT"] == 0.50
    assert w0["METAL"] == 0.50
    assert w0["CASH"] == 0.0

    # R1 Template B: 35% AUTO, 35% METAL, 30% Cash
    w1_b = calculate_equal_weights(1, template="B")
    assert w1_b["AUTO"] == 0.35
    assert w1_b["METAL"] == 0.35
    assert w1_b["CASH"] == 0.30

    # R3 Template B: 40% PHARMA, 20% FMCG, 40% Cash
    w3_b = calculate_equal_weights(3, template="B")
    assert w3_b["PHARMA"] == 0.40
    assert w3_b["FMCG"] == 0.20
    assert w3_b["CASH"] == 0.40


def test_turnover_calculation():
    # Complete rotation
    w_old = {"IT": 0.5, "METAL": 0.5, "AUTO": 0.0, "CASH": 0.0}
    w_new = {"AUTO": 0.5, "PHARMA": 0.5, "IT": 0.0, "METAL": 0.0}
    to = calculate_turnover(w_old, w_new)
    assert np.isclose(to, 1.0)

    # Identical portfolio
    assert np.isclose(calculate_turnover(w_old, w_old), 0.0)


def test_holding_lockup_and_crisis_override():
    curr_w = calculate_equal_weights(2, template="A")

    # Case 1: Target regime changed to R0, but holding_days = 2 (< 5). Should be blocked.
    trig1 = evaluate_rebalance_trigger(
        variant="1A",
        target_regime=0,
        incumbent_regime=2,
        holding_days=2,
        current_weights=curr_w,
        min_holding_days=5,
    )
    assert trig1["rebalance_triggered"] is False
    assert trig1["new_incumbent_regime"] == 2
    assert trig1["new_holding_days"] == 3

    # Case 2: Target regime changed to R0, holding_days = 5 (>= 5). Rebalance triggered!
    trig2 = evaluate_rebalance_trigger(
        variant="1A",
        target_regime=0,
        incumbent_regime=2,
        holding_days=5,
        current_weights=curr_w,
        min_holding_days=5,
    )
    assert trig2["rebalance_triggered"] is True
    assert trig2["new_incumbent_regime"] == 0
    assert trig2["new_holding_days"] == 0

    # Case 3: Target regime changed to R3 (Acute Liquidation), holding_days = 1 (< 5).
    # Crisis override exception MUST trigger immediate rebalance!
    trig3 = evaluate_rebalance_trigger(
        variant="1A",
        target_regime=3,
        incumbent_regime=2,
        holding_days=1,
        current_weights=curr_w,
        min_holding_days=5,
    )
    assert trig3["rebalance_triggered"] is True
    assert trig3["rebalance_bypassed_r3"] is True
    assert trig3["new_incumbent_regime"] == 3
    assert trig3["new_holding_days"] == 0


def test_step_daily_nav_compounding():
    holdings = {"IT": 0.50, "PHARMA": 0.50}
    returns = {"IT": 0.02, "PHARMA": -0.01}  # gross = 0.5*0.02 + 0.5*(-0.01) = +0.005
    step = step_daily_nav(
        current_holdings=holdings,
        asset_returns=returns,
        net_nav_prev=100.0,
        gross_nav_prev=100.0,
        rebalance_executing=False,
    )
    assert np.isclose(step["gross_return"], 0.005)
    assert np.isclose(step["net_return"], 0.005)
    assert np.isclose(step["net_nav"], 100.5)
    assert step["actual_turnover"] == 0.0
    assert step["transaction_cost"] == 0.0

