"""
deployment/engine/portfolio_state.py
====================================
Production Portfolio State, Allocation Rules, and NAV Compounding Engine.

Implements exact logic from Phase 8 (regime_rotation_rules) and Phase 10 (portfolio_backtest):
  - 4 canonical strategy variants: 1A, 1B, 2A, 2B
  - 50% causal probability acceptance threshold
  - 5-trading-day minimum holding lockup
  - Regime 3 (Acute Liquidation) crisis override exception
  - Next-trading-day execution scheduling
  - Trailing 20-day realized volatility with 1e-4 floor
  - Pre-trade asset drift, actual turnover, and 15 bps slippage/friction accounting
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

# Asset universe
SECTOR_NAMES: List[str] = ["AUTO", "BANK", "FMCG", "IT", "METAL", "PHARMA"]
BENCHMARK_NAME: str = "NIFTY50"
CASH_NAME: str = "CASH"
ALL_ASSETS: List[str] = [
    BENCHMARK_NAME,
    "AUTO",
    "BANK",
    "FMCG",
    "IT",
    "METAL",
    "PHARMA",
    CASH_NAME,
]

REGIME_SECTORS: Dict[int, Tuple[str, str]] = {
    0: ("IT", "METAL"),
    1: ("AUTO", "METAL"),
    2: ("IT", "PHARMA"),
    3: ("PHARMA", "FMCG"),
    4: ("METAL", "AUTO"),
    5: ("PHARMA", "FMCG"),
}

DEFAULT_CONFIDENCE_THRESHOLD: float = 0.50
DEFAULT_MIN_HOLDING_DAYS: int = 5
DEFAULT_TRANSACTION_COST_RATE: float = 0.0015  # 15 bps
DEFAULT_VOLATILITY_LOOKBACK: int = 20
DEFAULT_VOLATILITY_FLOOR: float = 1e-4
ANNUALIZATION_FACTOR: float = np.sqrt(252.0)


def create_zero_weights() -> Dict[str, float]:
    return {asset: 0.0 for asset in ALL_ASSETS}


def validate_weights(weights: Dict[str, float], tol: float = 1e-6) -> None:
    tot = sum(weights.values())
    if abs(tot - 1.0) > tol:
        raise ValueError(f"Weights must sum to 1.0 (got {tot:.6f})")
    for k, v in weights.items():
        if v < -tol:
            raise ValueError(f"Negative weight for {k}: {v}")


def calculate_equal_weights(regime_id: int, template: str = "A") -> Dict[str, float]:
    """
    Agreed allocations:
      - R0: 50% IT, 50% METAL (Templates A and B)
      - R1: 50% AUTO, 50% METAL (Template A) | 35% AUTO, 35% METAL, 30% Cash (Template B)
      - R2: 50% IT, 50% PHARMA (Templates A and B)
      - R3: 50% PHARMA, 50% FMCG (Template A) | 40% PHARMA, 20% FMCG, 40% Cash (Template B)
      - R4: 50% METAL, 50% AUTO (Templates A and B)
      - R5: 50% PHARMA, 50% FMCG (Template A) | 40% PHARMA, 40% FMCG, 20% Cash (Template B)
    """
    w = create_zero_weights()
    s1, s2 = REGIME_SECTORS[regime_id]
    tpl = template.upper()

    if tpl == "A":
        w[s1] = 0.50
        w[s2] = 0.50
        w[CASH_NAME] = 0.0
    elif tpl == "B":
        if regime_id == 0:
            w[s1] = 0.50
            w[s2] = 0.50
            w[CASH_NAME] = 0.0
        elif regime_id == 1:
            w[s1] = 0.35
            w[s2] = 0.35
            w[CASH_NAME] = 0.30
        elif regime_id == 2:
            w[s1] = 0.50
            w[s2] = 0.50
            w[CASH_NAME] = 0.0
        elif regime_id == 3:
            w["PHARMA"] = 0.40
            w["FMCG"] = 0.20
            w[CASH_NAME] = 0.40
        elif regime_id == 4:
            w[s1] = 0.50
            w[s2] = 0.50
            w[CASH_NAME] = 0.0
        elif regime_id == 5:
            w[s1] = 0.40
            w[s2] = 0.40
            w[CASH_NAME] = 0.20
    else:
        raise ValueError(f"Unknown template: {template}")

    validate_weights(w)
    return w


def calculate_trailing_volatilities(
    price_df: pd.DataFrame,
    lookback: int = DEFAULT_VOLATILITY_LOOKBACK,
    floor: float = DEFAULT_VOLATILITY_FLOOR,
) -> Dict[str, float]:
    """
    Trailing realized annualized volatilities for all 6 sectors using up to lookback+1 prices.
    ddof=1 sample standard deviation * sqrt(252).
    """
    if len(price_df) < 2:
        return {s: float(floor) for s in SECTOR_NAMES}

    window = price_df.iloc[-(lookback + 1):] if len(price_df) >= lookback + 1 else price_df
    log_rets = np.log(window / window.shift(1)).dropna()

    vols: Dict[str, float] = {}
    for s in SECTOR_NAMES:
        col = s if s in log_rets.columns else s.lower()
        if col not in log_rets.columns:
            vols[s] = float(floor)
            continue
        series = log_rets[col].values
        std = float(np.std(series, ddof=1)) if len(series) > 1 else 0.0
        ann_vol = std * ANNUALIZATION_FACTOR
        vols[s] = float(max(ann_vol, floor))
    return vols


def calculate_inverse_vol_weights(
    regime_id: int,
    volatilities: Dict[str, float],
    template: str = "A",
    floor: float = DEFAULT_VOLATILITY_FLOOR,
) -> Dict[str, float]:
    """
    Inverse-volatility weighting across top-2 sectors:
      raw_w_i = 1.0 / max(vol_i, floor)
      p_i = raw_w_i / sum(raw_w)
      w_i = target_equity_exposure * p_i
    """
    w = create_zero_weights()
    s1, s2 = REGIME_SECTORS[regime_id]
    tpl = template.upper()

    if tpl == "A":
        target_cash = 0.0
    elif tpl == "B":
        if regime_id in (0, 2, 4):
            target_cash = 0.0
        elif regime_id == 1:
            target_cash = 0.30
        elif regime_id == 3:
            target_cash = 0.40
        elif regime_id == 5:
            target_cash = 0.20
        else:
            target_cash = 0.0
    else:
        raise ValueError(f"Unknown template: {template}")

    target_equity = 1.0 - target_cash
    v1 = max(float(volatilities.get(s1, floor)), floor)
    v2 = max(float(volatilities.get(s2, floor)), floor)

    inv1 = 1.0 / v1
    inv2 = 1.0 / v2
    tot_inv = inv1 + inv2

    w[s1] = target_equity * (inv1 / tot_inv)
    w[s2] = target_equity * (inv2 / tot_inv)
    w[CASH_NAME] = target_cash

    validate_weights(w)
    return w


def get_target_regime_weights(
    regime_id: int,
    variant: str,
    volatilities: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    v = variant.upper()
    if v in ("1A", "VARIANT_1A"):
        return calculate_equal_weights(regime_id, template="A")
    elif v in ("1B", "VARIANT_1B"):
        if volatilities is None:
            raise ValueError("Inverse-vol variant 1B requires volatilities")
        return calculate_inverse_vol_weights(regime_id, volatilities, template="A")
    elif v in ("2A", "VARIANT_2A"):
        return calculate_equal_weights(regime_id, template="B")
    elif v in ("2B", "VARIANT_2B"):
        if volatilities is None:
            raise ValueError("Inverse-vol variant 2B requires volatilities")
        return calculate_inverse_vol_weights(regime_id, volatilities, template="B")
    else:
        raise ValueError(f"Unknown variant: {variant}")


def calculate_turnover(old_weights: Dict[str, float], new_weights: Dict[str, float]) -> float:
    """One-way portfolio turnover: 0.5 * sum |new - old|."""
    diff = 0.0
    for a in ALL_ASSETS:
        diff += abs(new_weights.get(a, 0.0) - old_weights.get(a, 0.0))
    return float(0.5 * diff)


def evaluate_rebalance_trigger(
    variant: str,
    target_regime: Optional[int],
    incumbent_regime: Optional[int],
    holding_days: int,
    current_weights: Dict[str, float],
    price_df: Optional[pd.DataFrame] = None,
    min_holding_days: int = DEFAULT_MIN_HOLDING_DAYS,
) -> Dict[str, Any]:
    """
    Evaluates whether an accepted signal triggers a target portfolio rebalance.
    Enforces 5-day lockup and Regime 3 Crisis Override exception.
    """
    rebalance_triggered = False
    rebalance_bypassed_r3 = False

    if target_regime is not None:
        if incumbent_regime is None:
            rebalance_triggered = True
        elif target_regime != incumbent_regime:
            if target_regime == 3:
                # Crisis override immediately bypasses 5-day lockup
                rebalance_triggered = True
                rebalance_bypassed_r3 = True
            elif holding_days >= min_holding_days:
                rebalance_triggered = True
            else:
                rebalance_triggered = False

    if rebalance_triggered and target_regime is not None:
        volatilities = None
        if variant.upper() in ("1B", "VARIANT_1B", "2B", "VARIANT_2B"):
            if price_df is None:
                raise ValueError("Inverse-vol requires price_df")
            volatilities = calculate_trailing_volatilities(price_df)

        target_weights = get_target_regime_weights(target_regime, variant, volatilities)
        turnover = calculate_turnover(current_weights, target_weights)
        new_incumbent = target_regime
        new_holding_days = 0
    else:
        target_weights = current_weights.copy()
        turnover = 0.0
        new_incumbent = incumbent_regime
        new_holding_days = holding_days + 1

    return {
        "rebalance_triggered": rebalance_triggered,
        "rebalance_bypassed_r3": rebalance_bypassed_r3,
        "target_weights": target_weights,
        "turnover": turnover,
        "new_incumbent_regime": new_incumbent,
        "new_holding_days": new_holding_days,
    }


def step_daily_nav(
    current_holdings: Dict[str, float],
    asset_returns: Dict[str, float],
    net_nav_prev: float,
    gross_nav_prev: float,
    rebalance_executing: bool,
    target_weights: Optional[Dict[str, float]] = None,
    cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
) -> Dict[str, Any]:
    """
    Executes one trading session NAV compounding step.
    Computes pre-trade gross return, asset drift, actual turnover, and 15 bps friction.
    """
    # 1. Gross portfolio return
    r_gross = 0.0
    for a in ALL_ASSETS:
        w_i = current_holdings.get(a, 0.0)
        r_i = asset_returns.get(a, 0.0) if a != CASH_NAME else 0.0
        r_gross += w_i * r_i

    # 2. Pre-trade drifted NAV
    gross_factor = 1.0 + r_gross
    nav_pre_net = net_nav_prev * gross_factor
    nav_pre_gross = gross_nav_prev * gross_factor

    # 3. Drifted weights
    drifted_weights = {}
    for a in ALL_ASSETS:
        w_i = current_holdings.get(a, 0.0)
        r_i = asset_returns.get(a, 0.0) if a != CASH_NAME else 0.0
        drifted_weights[a] = (w_i * (1.0 + r_i)) / gross_factor
    drifted_weights = {k: max(v, 0.0) for k, v in drifted_weights.items()}
    drift_sum = sum(drifted_weights.values())
    drifted_weights = {k: v / drift_sum for k, v in drifted_weights.items()}

    # 4. Rebalance execution
    if rebalance_executing and target_weights is not None:
        actual_turnover = calculate_turnover(drifted_weights, target_weights)
        tc = nav_pre_net * actual_turnover * cost_rate
        nav_post_net = nav_pre_net - tc
        nav_post_gross = nav_pre_gross
        post_holdings = target_weights.copy()
    else:
        actual_turnover = 0.0
        tc = 0.0
        nav_post_net = nav_pre_net
        nav_post_gross = nav_pre_gross
        post_holdings = drifted_weights.copy()

    # 5. Net daily return
    r_net = (nav_post_net / net_nav_prev) - 1.0

    return {
        "gross_return": float(r_gross),
        "net_return": float(r_net),
        "gross_nav": float(nav_post_gross),
        "net_nav": float(nav_post_net),
        "actual_turnover": float(actual_turnover),
        "transaction_cost": float(tc),
        "post_holdings": post_holdings,
    }

