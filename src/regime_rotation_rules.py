"""
src/regime_rotation_rules.py
============================
Phase 8 - Sector Rotation Rules Engine
Sector Rotation Regime Discovery - Indian Equity Market

This module implements the core strategy logic for translating causal Hidden Markov
Model (HMM) regime signals into systematic sector allocation weights across the six
major National Stock Exchange (NSE) sectoral indices:
  - NIFTY AUTO
  - NIFTY BANK
  - NIFTY FMCG
  - NIFTY IT
  - NIFTY METAL
  - NIFTY PHARMA
plus the NIFTY 50 benchmark (initialization asset) and cash.

Supported Features:
  1. Four Experimental Strategy Variants (2 x 2 matrix):
       - Variant 1A: Template A (100% Fully Invested) + Equal-Weighted Top-2
       - Variant 1B: Template A (100% Fully Invested) + Inverse-Volatility Top-2
       - Variant 2A: Template B (Defensive Cash Floor) + Equal-Weighted Top-2
       - Variant 2B: Template B (Defensive Cash Floor) + Inverse-Volatility Top-2
  2. Agreed Regime-Specific Candidate Allocations (R0 to R5)
  3. Trailing 20-day realized volatility estimation with volatility floor safeguard (1e-4)
  4. Causal regime confidence threshold acceptance (P >= 0.50) with incumbent persistence
  5. 5-trading-day minimum holding lockup with R3 crisis override exception
  6. Next-day-close (t+1 Close) execution scheduling to eliminate look-ahead bias
  7. NIFTY 50 initialization accounting for non-zero initial transition turnover
  8. Institutional transaction cost model (15 bps one-way turnover)

Strict Constraint:
  This module contains rules and weight generation only. Portfolio return backtesting
  and performance attribution are quarantined for subsequent phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants & Asset Universe
# ---------------------------------------------------------------------------

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

# Economic designations established in Phase 6 / Phase 7
REGIME_ECONOMIC_NAMES: Dict[int, str] = {
    0: "Cyclical Reflation Rally",
    1: "High-Volatility Post-Crash Bounce",
    2: "Low-Volatility Consolidation / Base",
    3: "Acute Liquidation / Flight to Safety",
    4: "Steady Expansion / Low-Volatility Bull",
    5: "Correction / Risk-Off Digestion",
}

# Agreed primary sector selections for each regime (Top-1, Top-2)
REGIME_SECTORS: Dict[int, Tuple[str, str]] = {
    0: ("IT", "METAL"),
    1: ("AUTO", "METAL"),
    2: ("IT", "PHARMA"),
    3: ("PHARMA", "FMCG"),
    4: ("METAL", "AUTO"),
    5: ("PHARMA", "FMCG"),
}

# Template A cash targets (always 0.0 - fully invested)
TEMPLATE_A_CASH: Dict[int, float] = {
    0: 0.0,
    1: 0.0,
    2: 0.0,
    3: 0.0,
    4: 0.0,
    5: 0.0,
}

# Template B cash targets (defensive reserves in stressed regimes)
TEMPLATE_B_CASH: Dict[int, float] = {
    0: 0.0,
    1: 0.30,  # 30% cash buffer in volatile post-crash bounce
    2: 0.0,
    3: 0.40,  # 40% cash reserve in acute liquidation panic
    4: 0.0,
    5: 0.20,  # 20% cash buffer in market correction/digestion
}

# Operational strategy control defaults
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.50
DEFAULT_MIN_HOLDING_DAYS: int = 5
DEFAULT_TRANSACTION_COST_RATE: float = 0.0015  # 15 basis points per unit of one-way turnover
DEFAULT_VOLATILITY_LOOKBACK: int = 20  # 20 trading days
DEFAULT_VOLATILITY_FLOOR: float = 1e-4  # Minimum volatility safeguard to avoid division by zero
ANNUALIZATION_FACTOR: float = np.sqrt(252.0)


# ---------------------------------------------------------------------------
# Strategy Variant Enumeration
# ---------------------------------------------------------------------------

class StrategyVariant(str, Enum):
    """The four canonical strategy variants forming the 2 x 2 experimental matrix."""
    VARIANT_1A = "1A_template_a_equal_weight"
    VARIANT_1B = "1B_template_a_inverse_vol"
    VARIANT_2A = "2A_template_b_equal_weight"
    VARIANT_2B = "2B_template_b_inverse_vol"

    @classmethod
    def from_str(cls, val: Union[StrategyVariant, str]) -> StrategyVariant:
        """Parse variant from instance, shorthand (e.g. '1A', '1B', '2A', '2B') or full string."""
        if isinstance(val, cls):
            return val
        if hasattr(val, "value"):
            val = val.value
        normalized = str(val).strip().lower()
        if normalized in ["1a", "variant_1a", "template_a_equal_weight", "1a_template_a_equal_weight"]:
            return cls.VARIANT_1A
        if normalized in ["1b", "variant_1b", "template_a_inverse_vol", "1b_template_a_inverse_vol"]:
            return cls.VARIANT_1B
        if normalized in ["2a", "variant_2a", "template_b_equal_weight", "2a_template_b_equal_weight"]:
            return cls.VARIANT_2A
        if normalized in ["2b", "variant_2b", "template_b_inverse_vol", "2b_template_b_inverse_vol"]:
            return cls.VARIANT_2B
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(
            f"Unknown strategy variant: '{val}'. Expected one of: "
            f"{[m.value for m in cls]} or shorthands ['1A', '1B', '2A', '2B']."
        )

    @property
    def template(self) -> str:
        """Return 'A' or 'B'."""
        return "A" if "template_a" in self.value else "B"

    @property
    def is_inverse_vol(self) -> bool:
        """Return True if weighting method is inverse-volatility."""
        return "inverse_vol" in self.value


# ---------------------------------------------------------------------------
# Weight Calculation Functions
# ---------------------------------------------------------------------------

def create_zero_weights() -> Dict[str, float]:
    """Create a weight dictionary with all assets initialized to 0.0."""
    return {asset: 0.0 for asset in ALL_ASSETS}


def create_nifty50_initial_weights() -> Dict[str, float]:
    """
    Create the Day 0 initial portfolio: 100% NIFTY 50 benchmark holding.
    All sectoral and cash allocations are 0.0.
    """
    w = create_zero_weights()
    w[BENCHMARK_NAME] = 1.0
    return w


def validate_portfolio_weights(
    weights: Dict[str, float],
    tol: float = 1e-6,
) -> None:
    """
    Validate that portfolio weights:
      1. Cover all known assets in ALL_ASSETS.
      2. Contain only non-negative weights (long-only constraint).
      3. Sum to 1.0 within numerical tolerance.
    Raises ValueError if validation fails.
    """
    total = sum(weights.values())
    if abs(total - 1.0) > tol:
        raise ValueError(f"Portfolio weights must sum to 1.0 (got {total:.8f}). Weights: {weights}")
    for asset, val in weights.items():
        if val < -tol:
            raise ValueError(f"Negative weight detected for {asset}: {val:.8f}")
        if np.isnan(val) or np.isinf(val):
            raise ValueError(f"Non-finite weight detected for {asset}: {val}")


def calculate_equal_weights(
    regime_id: int,
    template: str = "A",
) -> Dict[str, float]:
    """
    Calculate equal-weighted Top-2 candidate allocations for a given regime.
    Preserves exact agreed allocations from the Phase 8 specification:
      - R0: 50% IT, 50% METAL (Both templates)
      - R1: 50% AUTO, 50% METAL (Template A) | 35% AUTO, 35% METAL, 30% Cash (Template B)
      - R2: 50% IT, 50% PHARMA (Both templates)
      - R3: 50% PHARMA, 50% FMCG (Template A) | 40% PHARMA, 20% FMCG, 40% Cash (Template B)
      - R4: 50% METAL, 50% AUTO (Both templates)
      - R5: 50% PHARMA, 50% FMCG (Template A) | 40% PHARMA, 40% FMCG, 20% Cash (Template B)

    Args:
      regime_id: Integer regime ID [0..5]
      template: 'A' or 'B'

    Returns:
      Dict[str, float] with keys in ALL_ASSETS summing to 1.0.
    """
    if regime_id not in REGIME_SECTORS:
        raise ValueError(f"Invalid regime_id: {regime_id}. Expected integer in [0..5].")

    template_clean = template.strip().upper()
    if template_clean not in ["A", "B"]:
        raise ValueError(f"Invalid template: '{template}'. Expected 'A' or 'B'.")

    w = create_zero_weights()
    s1, s2 = REGIME_SECTORS[regime_id]

    if template_clean == "A":
        # Template A: 100% equity, 0% cash across all regimes
        w[s1] = 0.50
        w[s2] = 0.50
        w[CASH_NAME] = 0.0
    else:
        # Template B: Regime-specific cash allocations
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
            # Explicitly agreed special case: 40% PHARMA, 20% FMCG, 40% Cash
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

    validate_portfolio_weights(w)
    return w


def calculate_trailing_volatilities(
    price_df: pd.DataFrame,
    current_date: pd.Timestamp,
    lookback: int = DEFAULT_VOLATILITY_LOOKBACK,
    floor: float = DEFAULT_VOLATILITY_FLOOR,
) -> Dict[str, float]:
    """
    Calculate trailing realized annualized volatilities for all sectors using
    daily log returns up to and including current_date.
    Formula:
      r_tau = ln(P_tau / P_{tau-1})
      sigma_raw = std(r, ddof=1) * sqrt(252)
      sigma_floored = max(sigma_raw, floor)

    Strict Temporal Rule:
      Uses only price observations up to current_date. Zero future prices are accessed.

    Args:
      price_df: Close price DataFrame indexed by DatetimeIndex containing SECTOR_NAMES.
      current_date: The signal timestamp (Close of date t).
      lookback: Number of trailing return sessions (default 20).
      floor: Minimum volatility safeguard to avoid division by zero (default 1e-4).

    Returns:
      Dict[str, float]: Annualized volatility per sector.
    """
    # Truncate price history strictly up to current_date
    sub_prices = price_df.loc[:current_date]
    if len(sub_prices) < 2:
        # Zero returns can be computed; return floor safeguard for all sectors
        return {sector: float(floor) for sector in SECTOR_NAMES}

    # Use up to (lookback + 1) prices to compute trailing log returns
    window_prices = sub_prices.iloc[-(lookback + 1):] if len(sub_prices) >= lookback + 1 else sub_prices
    log_returns = np.log(window_prices / window_prices.shift(1)).dropna()

    volatilities: Dict[str, float] = {}
    for sector in SECTOR_NAMES:
        if sector not in log_returns.columns:
            raise KeyError(f"Sector '{sector}' not found in price_df columns.")
        sec_ret = log_returns[sector].values
        # Sample standard deviation (ddof=1)
        raw_std = float(np.std(sec_ret, ddof=1)) if len(sec_ret) > 1 else 0.0
        ann_vol = raw_std * ANNUALIZATION_FACTOR
        volatilities[sector] = float(max(ann_vol, floor))

    return volatilities


def calculate_inverse_vol_weights(
    regime_id: int,
    volatilities: Dict[str, float],
    template: str = "A",
    floor: float = DEFAULT_VOLATILITY_FLOOR,
) -> Dict[str, float]:
    """
    Calculate inverse-volatility Top-2 candidate allocations for a given regime.
    Maintains the exact same two selected sectors as equal-weighting and preserves
    the agreed cash allocation of the chosen template.

    Formula:
      raw_weight_i = 1 / max(vol_i, floor)
      p_i = raw_weight_i / sum(raw_weight_selected)
      w_i = Target_Equity_Exposure * p_i
      w_cash = Target_Cash_Allocation

    For Template B R3: Target equity exposure is 60% (1.0 - 0.40 cash), which is
    divided between PHARMA and FMCG inversely proportional to their volatilities.

    Args:
      regime_id: Integer regime ID [0..5]
      volatilities: Dict of annualized volatilities containing the eligible sectors.
      template: 'A' or 'B'
      floor: Volatility floor safeguard.

    Returns:
      Dict[str, float] with keys in ALL_ASSETS summing to 1.0.
    """
    if regime_id not in REGIME_SECTORS:
        raise ValueError(f"Invalid regime_id: {regime_id}. Expected integer in [0..5].")

    template_clean = template.strip().upper()
    if template_clean not in ["A", "B"]:
        raise ValueError(f"Invalid template: '{template}'. Expected 'A' or 'B'.")

    s1, s2 = REGIME_SECTORS[regime_id]
    vol1 = max(float(volatilities[s1]), floor)
    vol2 = max(float(volatilities[s2]), floor)

    inv1 = 1.0 / vol1
    inv2 = 1.0 / vol2
    prop1 = inv1 / (inv1 + inv2)
    prop2 = inv2 / (inv1 + inv2)

    # Determine cash and equity targets
    cash_target = TEMPLATE_A_CASH[regime_id] if template_clean == "A" else TEMPLATE_B_CASH[regime_id]
    equity_target = 1.0 - cash_target

    w = create_zero_weights()
    w[s1] = float(equity_target * prop1)
    w[s2] = float(equity_target * prop2)
    w[CASH_NAME] = float(cash_target)

    validate_portfolio_weights(w)
    return w


def get_target_regime_weights(
    regime_id: int,
    variant: Union[StrategyVariant, str],
    volatilities: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Dispatcher to compute target portfolio weights for any of the four variants.

    Args:
      regime_id: Integer regime ID [0..5]
      variant: StrategyVariant instance or shorthand string ('1A', '1B', '2A', '2B')
      volatilities: Required if variant is inverse-volatility (1B or 2B).

    Returns:
      Dict[str, float] with keys in ALL_ASSETS summing to 1.0.
    """
    var_enum = StrategyVariant.from_str(variant) if isinstance(variant, str) else variant

    if var_enum.is_inverse_vol:
        if volatilities is None:
            raise ValueError(f"Variant {var_enum.value} requires volatilities dictionary.")
        return calculate_inverse_vol_weights(
            regime_id=regime_id,
            volatilities=volatilities,
            template=var_enum.template,
        )
    else:
        return calculate_equal_weights(
            regime_id=regime_id,
            template=var_enum.template,
        )


# ---------------------------------------------------------------------------
# Causal Regime Acceptance & Operational Controls
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegimeAcceptanceResult:
    """Encapsulates the decision made by the confidence acceptance filter."""
    accepted_regime: Optional[int]
    max_probability: float
    is_confident: bool
    incumbent_regime: Optional[int]
    was_tied: bool


def accept_regime_signal(
    filtered_probs: Union[np.ndarray, pd.Series, List[float]],
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    incumbent_regime: Optional[int] = None,
) -> RegimeAcceptanceResult:
    """
    Apply the agreed confidence acceptance threshold (P >= 0.50) to causal
    forward-filtered regime probabilities.

    Rules:
      1. Validation: Probability vector must have length 6, non-negative elements,
         sum to ~1.0, and contain no non-finite values.
      2. Threshold: If max(probs) >= threshold (0.50):
         - Select candidate argmax.
         - Tie-Breaker: In the rare event that two states exactly tie at threshold
           (e.g. [0.50, 0.50, 0, 0, 0, 0]), retain incumbent_regime if incumbent is
           one of the tied states; otherwise select the lower regime ID.
         - Returns accepted candidate with is_confident=True.
      3. Persistence: If max(probs) < threshold:
         - Reject proposed state change.
         - Retain incumbent_regime with is_confident=False.

    Args:
      filtered_probs: 6-element probability vector for states [0..5]
      threshold: Confidence cutoff (default 0.50)
      incumbent_regime: The currently held regime ID (or None if uninitialized)

    Returns:
      RegimeAcceptanceResult
    """
    p_arr = np.asarray(filtered_probs, dtype=float)

    if len(p_arr) != 6:
        raise ValueError(f"Expected 6 regime probabilities, got {len(p_arr)}: {p_arr}")
    if np.any(np.isnan(p_arr)) or np.any(np.isinf(p_arr)):
        raise ValueError(f"Probabilities contain NaN or Inf values: {p_arr}")
    if np.any(p_arr < -1e-6):
        raise ValueError(f"Negative probabilities detected: {p_arr}")
    p_sum = float(np.sum(p_arr))
    if abs(p_sum - 1.0) > 1e-2:
        raise ValueError(f"Probabilities must sum to ~1.0 (got {p_sum:.6f}): {p_arr}")

    max_p = float(np.max(p_arr))
    best_candidates = np.where(np.isclose(p_arr, max_p, atol=1e-6))[0].tolist()
    is_tied = len(best_candidates) > 1

    if max_p >= threshold - 1e-6:
        # Confident signal
        if is_tied and incumbent_regime in best_candidates:
            chosen = incumbent_regime
        else:
            chosen = int(best_candidates[0])
        return RegimeAcceptanceResult(
            accepted_regime=chosen,
            max_probability=max_p,
            is_confident=True,
            incumbent_regime=incumbent_regime,
            was_tied=is_tied,
        )
    else:
        # Below confidence threshold -> persist incumbent regime
        return RegimeAcceptanceResult(
            accepted_regime=incumbent_regime,
            max_probability=max_p,
            is_confident=False,
            incumbent_regime=incumbent_regime,
            was_tied=is_tied,
        )


# ---------------------------------------------------------------------------
# Turnover & Transaction Cost Accounting
# ---------------------------------------------------------------------------

def calculate_turnover(
    old_weights: Dict[str, float],
    new_weights: Dict[str, float],
) -> float:
    """
    Calculate one-way portfolio turnover between two weight vectors.
    Formula:
      Turnover = 0.5 * sum_{asset in ALL_ASSETS} |new_weight_i - old_weight_i|

    Properties:
      - Unchanged portfolio: Turnover = 0.0
      - Complete rotation between disjoint fully-invested portfolios: Turnover = 1.0 (100%)
      - Day 0 NIFTY 50 (100%) -> Sector portfolio (50% A, 50% B): Turnover = 1.0
      - Rebalance to cash (e.g. 50% A + 50% B -> 100% Cash): Turnover = 1.0

    Returns:
      float in range [0.0, 1.0].
    """
    total_delta = 0.0
    for asset in ALL_ASSETS:
        w_old = old_weights.get(asset, 0.0)
        w_new = new_weights.get(asset, 0.0)
        total_delta += abs(w_new - w_old)
    return float(0.5 * total_delta)


def calculate_transaction_cost(
    turnover: float,
    portfolio_value: float = 1.0,
    cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
) -> float:
    """
    Calculate simulated transaction cost based on one-way turnover.
    Formula:
      Cost = cost_rate * turnover * portfolio_value
    where cost_rate = 0.0015 (15 basis points per unit of turnover).
    """
    return float(cost_rate * turnover * portfolio_value)


# ---------------------------------------------------------------------------
# Comprehensive Rules Engine Execution Simulation
# ---------------------------------------------------------------------------

@dataclass
class AllocationScheduleRecord:
    """Record of strategy state and target allocation for a single trading date."""
    date: pd.Timestamp
    exec_date: pd.Timestamp
    raw_regime_argmax: int
    max_probability: float
    is_confident: bool
    accepted_regime: Optional[int]
    incumbent_regime_before: Optional[int]
    incumbent_regime_after: Optional[int]
    rebalance_triggered: bool
    rebalance_bypassed_r3: bool
    holding_days_before: int
    holding_days_after: int
    turnover: float
    transaction_cost_rate: float
    weights: Dict[str, float]


class RegimeRotationRulesEngine:
    """
    Full operational rules engine that executes the Phase 8 strategy logic
    over a chronological sequence of trading dates.

    Guarantees:
      1. Zero look-ahead bias: Signal generated at Date t Close -> executed at Date t+1 Close.
      2. 5-trading-day minimum holding lockup enforced on trading calendar sequence.
      3. R3 crisis override exception immediately permits rebalance while still executing at t+1 Close.
      4. NIFTY 50 initialization on Day 0 with full turnover accounting upon first rebalance.
      5. Strict weight normalization and non-negativity across all sessions.
    """

    def __init__(
        self,
        variant: Union[StrategyVariant, str],
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        min_holding_days: int = DEFAULT_MIN_HOLDING_DAYS,
        transaction_cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
        volatility_lookback: int = DEFAULT_VOLATILITY_LOOKBACK,
        volatility_floor: float = DEFAULT_VOLATILITY_FLOOR,
    ) -> None:
        self.variant = StrategyVariant.from_str(variant) if isinstance(variant, str) else variant
        self.confidence_threshold = confidence_threshold
        self.min_holding_days = min_holding_days
        self.transaction_cost_rate = transaction_cost_rate
        self.volatility_lookback = volatility_lookback
        self.volatility_floor = volatility_floor

    def generate_schedule(
        self,
        dates: pd.DatetimeIndex,
        probabilities_df: pd.DataFrame,
        price_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Process chronological trading days and generate full allocation schedule.

        Args:
          dates: Monotonically increasing DatetimeIndex of trading sessions.
          probabilities_df: DataFrame indexed by dates containing either:
            - 6 probability columns [0, 1, 2, 3, 4, 5] or ['regime_0'..'regime_5'], OR
            - Column 'regime_id' (interpreted as 100% confident label).
          price_df: Close price DataFrame indexed by DatetimeIndex containing SECTOR_NAMES.
            Required if self.variant is an inverse-volatility variant.

        Returns:
          pd.DataFrame: Chronological allocation schedule containing asset weights,
          execution dates, turnover, and operational flags.
        """
        if not dates.is_monotonic_increasing:
            raise ValueError("Dates must be monotonically increasing.")
        if len(dates) == 0:
            raise ValueError("Dates sequence cannot be empty.")

        if self.variant.is_inverse_vol and price_df is None:
            raise ValueError(f"Variant '{self.variant.value}' requires price_df for volatility calculation.")

        # Determine probability column structure prior to the session loop.
        # Genuine continuous probability columns take strict precedence over discrete 'regime_id'.
        prob_cols: Optional[List[Any]] = None
        candidate_col_formats = [
            [f"prob_{j}" for j in range(6)],
            [f"regime_{j}" for j in range(6)],
            [0, 1, 2, 3, 4, 5],
            [str(j) for j in range(6)],
        ]
        for candidate in candidate_col_formats:
            if all(c in probabilities_df.columns for c in candidate):
                prob_cols = candidate
                break

        has_regime_id = "regime_id" in probabilities_df.columns
        if prob_cols is None and not has_regime_id:
            raise KeyError(
                "probabilities_df must contain continuous probability columns "
                "('prob_0'..'prob_5', 'regime_0'..'regime_5', 0..5) or 'regime_id'."
            )

        # State tracking
        current_weights = create_nifty50_initial_weights()
        incumbent_regime: Optional[int] = None
        holding_days: int = 0
        records: List[Dict[str, Any]] = []

        n_dates = len(dates)

        for i in range(n_dates):
            current_date = dates[i]
            # Scheduled execution is Next-Day Close (t+1). For final row, it is next trading bar.
            exec_date = dates[i + 1] if i + 1 < n_dates else current_date + pd.Timedelta(days=1)

            # 1. Extract regime probabilities
            if current_date not in probabilities_df.index:
                raise KeyError(f"Date {current_date} missing from probabilities_df.")

            row = probabilities_df.loc[current_date]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]

            if prob_cols is not None:
                # Genuine continuous probability columns take precedence
                p_vec = row[prob_cols].values.astype(float)
            else:
                # Discrete label fallback (one-hot vector)
                r_id = int(row["regime_id"])
                if r_id < 0 or r_id > 5:
                    raise ValueError(f"Invalid regime_id: {r_id}. Expected integer in [0..5].")
                p_vec = np.zeros(6, dtype=float)
                p_vec[r_id] = 1.0

            raw_argmax = int(np.argmax(p_vec))

            # 2. Evaluate confidence filter
            acceptance = accept_regime_signal(
                filtered_probs=p_vec,
                threshold=self.confidence_threshold,
                incumbent_regime=incumbent_regime,
            )

            target_regime = acceptance.accepted_regime
            is_confident = acceptance.is_confident

            # 3. Check rebalancing eligibility & operational controls
            rebalance_triggered = False
            rebalance_bypassed_r3 = False
            holding_before = holding_days
            incumbent_before = incumbent_regime

            if target_regime is not None:
                if incumbent_regime is None:
                    # Initial transition from NIFTY 50 into first confirmed regime
                    rebalance_triggered = True
                elif target_regime != incumbent_regime:
                    # Regime change proposed
                    if target_regime == 3:
                        # R3 Crisis Override Exception: bypasses 5-day lockup immediately
                        rebalance_triggered = True
                        rebalance_bypassed_r3 = True
                    elif holding_days >= self.min_holding_days:
                        # Elective rebalance after satisfying minimum holding period
                        rebalance_triggered = True
                    else:
                        # Blocked by holding lockup -> maintain incumbent weights
                        rebalance_triggered = False

            # 4. Generate target weights
            if rebalance_triggered and target_regime is not None:
                if self.variant.is_inverse_vol:
                    volatilities = calculate_trailing_volatilities(
                        price_df=price_df,
                        current_date=current_date,
                        lookback=self.volatility_lookback,
                        floor=self.volatility_floor,
                    )
                    new_weights = get_target_regime_weights(
                        regime_id=target_regime,
                        variant=self.variant,
                        volatilities=volatilities,
                    )
                else:
                    new_weights = get_target_regime_weights(
                        regime_id=target_regime,
                        variant=self.variant,
                    )

                turnover = calculate_turnover(current_weights, new_weights)
                cost = calculate_transaction_cost(turnover, cost_rate=self.transaction_cost_rate)
                current_weights = new_weights
                incumbent_regime = target_regime
                holding_days = 0  # reset lockup clock upon rebalancing
            else:
                turnover = 0.0
                cost = 0.0
                holding_days += 1  # increment lockup clock

            # Record state
            rec: Dict[str, Any] = {
                "signal_date": current_date,
                "exec_date": exec_date,
                "raw_regime_argmax": int(raw_argmax),
                "max_probability": float(acceptance.max_probability),
                "is_confident": bool(is_confident),
                "accepted_regime": int(target_regime) if target_regime is not None else None,
                "incumbent_regime_before": int(incumbent_before) if incumbent_before is not None else None,
                "incumbent_regime_after": int(incumbent_regime) if incumbent_regime is not None else None,
                "rebalance_triggered": bool(rebalance_triggered),
                "rebalance_bypassed_r3": bool(rebalance_bypassed_r3),
                "holding_days_before": int(holding_before),
                "holding_days_after": int(holding_days),
                "turnover": float(turnover),
                "transaction_cost_rate": float(cost),
            }
            for asset in ALL_ASSETS:
                rec[f"w_{asset}"] = current_weights[asset]

            records.append(rec)

        schedule_df = pd.DataFrame(records).set_index("signal_date")
        return schedule_df
