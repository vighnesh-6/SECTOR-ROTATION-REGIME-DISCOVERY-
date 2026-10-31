"""
Portfolio Construction Module for ML-Based Sector Rotation Regime Discovery
in the Indian Equity Market (Phase 9.2).

Orchestrates the generation, validation, state continuity verification, and
canonical persistence of four target-weight schedules (Variants 1A, 1B, 2A, 2B)
over the full timeline (2019-10-31 to 2026-09-18).

Reuses the authoritative rules engine from src/regime_rotation_rules.py without
duplication, preserving frozen Phase 8 allocation rules, confidence threshold (0.50),
five-day minimum holding lockup, and R3 crisis override exception.

Guarantees:
  1. Continuous portfolio state across the train-to-holdout boundary (2024-12-31 to 2025-01-02).
  2. Pure target-weight and operational turnover tracking with zero look-ahead bias.
  3. No performance metrics, backtesting, or equity curves (deferred to Phase 10).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.regime_rotation_rules import (
    ALL_ASSETS,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MIN_HOLDING_DAYS,
    DEFAULT_TRANSACTION_COST_RATE,
    DEFAULT_VOLATILITY_FLOOR,
    DEFAULT_VOLATILITY_LOOKBACK,
    REGIME_SECTORS,
    SECTOR_NAMES,
    TEMPLATE_A_CASH,
    TEMPLATE_B_CASH,
    RegimeRotationRulesEngine,
    StrategyVariant,
    validate_portfolio_weights,
)

logger = logging.getLogger(__name__)

# Canonical paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROB_PATH = PROJECT_ROOT / "results" / "regime_discovery" / "hmm_causal_probabilities.csv"
DEFAULT_ALIGNED_PRICE_DIR = PROJECT_ROOT / "data" / "processed" / "aligned"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "portfolio_construction"

# Canonical target-weight file mapping
TARGET_WEIGHT_FILENAMES: Dict[str, str] = {
    "1A": "target_weights_1A.csv",
    "1B": "target_weights_1B.csv",
    "2A": "target_weights_2A.csv",
    "2B": "target_weights_2B.csv",
}

# Timeline specifications
EXPECTED_TOTAL_SESSIONS: int = 1687
EXPECTED_TRAIN_SESSIONS: int = 1265
EXPECTED_HOLDOUT_SESSIONS: int = 422
EXPECTED_TRAIN_START: str = "2019-10-31"
EXPECTED_TRAIN_END: str = "2024-12-31"
EXPECTED_HOLDOUT_START: str = "2025-01-02"
EXPECTED_HOLDOUT_END: str = "2026-09-18"

PROB_COLS: List[str] = [f"prob_{j}" for j in range(6)]
WEIGHT_COLS: List[str] = [f"w_{a}" for a in ALL_ASSETS]

SCHEDULE_COLUMNS: List[str] = [
    "period",
    "variant",
    "exec_date",
    "raw_regime_argmax",
    "max_probability",
    "is_confident",
    "accepted_regime",
    "incumbent_regime_before",
    "incumbent_regime_after",
    "rebalance_triggered",
    "rebalance_bypassed_r3",
    "holding_days_before",
    "holding_days_after",
    "turnover",
    "transaction_cost_rate",
    "w_NIFTY50",
    "w_AUTO",
    "w_BANK",
    "w_FMCG",
    "w_IT",
    "w_METAL",
    "w_PHARMA",
    "w_CASH",
]


# =====================================================================
# 1. Input Loading and Validation
# =====================================================================

def load_causal_probabilities(path: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """
    Load and index the recovered causal forward-filtered probabilities CSV.

    Args:
      path: Path to hmm_causal_probabilities.csv. Defaults to canonical location.

    Returns:
      pd.DataFrame: Datetime-indexed DataFrame with columns Date, period, prob_0..prob_5.
    """
    p = Path(path) if path is not None else DEFAULT_PROB_PATH
    if not p.exists():
        raise FileNotFoundError(f"Causal probabilities file not found at {p}")

    df = pd.read_csv(p, parse_dates=["Date"]).set_index("Date")
    validate_probabilities_df(df)
    return df


def load_aligned_prices(
    price_dir: Optional[Union[str, Path]] = None,
    sectors: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Load aligned closing prices for all sector indices.

    Args:
      price_dir: Directory containing nifty_{sector}_aligned.csv. Defaults to canonical path.
      sectors: List of sector names. Defaults to SECTOR_NAMES.

    Returns:
      pd.DataFrame: Datetime-indexed DataFrame with closing prices for each sector.
    """
    pdir = Path(price_dir) if price_dir is not None else DEFAULT_ALIGNED_PRICE_DIR
    if not pdir.exists():
        raise FileNotFoundError(f"Aligned price directory not found at {pdir}")

    sec_list = sectors if sectors is not None else SECTOR_NAMES
    prices: Dict[str, pd.Series] = {}

    for s in sec_list:
        fpath = pdir / f"nifty_{s.lower()}_aligned.csv"
        if not fpath.exists():
            raise FileNotFoundError(f"Missing sector price file: {fpath}")
        pdf = pd.read_csv(fpath, index_col=0, parse_dates=True)
        if "Close" not in pdf.columns:
            raise KeyError(f"Expected 'Close' column in {fpath}")
        prices[s] = pdf["Close"]

    price_df = pd.DataFrame(prices).sort_index()
    return price_df


def validate_probabilities_df(df: pd.DataFrame, tol: float = 1e-5) -> None:
    """
    Validate schema, bounds, finiteness, and partition labels of the probabilities DataFrame.

    Raises:
      KeyError: If required columns or period column are missing.
      ValueError: If values are non-finite, out of [0, 1], row sums != 1.0, or dates invalid.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Probabilities DataFrame must have a pd.DatetimeIndex.")
    if not df.index.is_monotonic_increasing:
        raise ValueError("Probabilities DataFrame dates must be monotonically increasing.")
    if not df.index.is_unique:
        raise ValueError("Probabilities DataFrame contains duplicate dates.")

    if "period" not in df.columns:
        raise KeyError("Probabilities DataFrame missing required 'period' column.")

    valid_periods = {"train", "holdout"}
    periods_present = set(df["period"].unique())
    if not periods_present.issubset(valid_periods):
        raise ValueError(f"Invalid period values found: {periods_present - valid_periods}")

    missing_cols = [c for c in PROB_COLS if c not in df.columns]
    if missing_cols:
        raise KeyError(f"Probabilities DataFrame missing required columns: {missing_cols}")

    p_arr = df[PROB_COLS].values
    if not np.isfinite(p_arr).all():
        raise ValueError("Non-finite values detected in probability columns.")

    if (p_arr < -tol).any() or (p_arr > 1.0 + tol).any():
        raise ValueError("Probability values out of bounds [0, 1].")

    row_sums = p_arr.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=tol):
        max_dev = np.max(np.abs(row_sums - 1.0))
        raise ValueError(f"Probability row sums deviate from 1.0 (max deviation: {max_dev:.2e}).")


def validate_price_coverage(
    price_df: pd.DataFrame,
    required_dates: pd.DatetimeIndex,
    lookback: int = DEFAULT_VOLATILITY_LOOKBACK,
) -> None:
    """
    Verify that aligned price data covers all required timeline dates and provides
    sufficient historical warmup sessions for trailing inverse-volatility computation.

    Raises:
      KeyError: If sectors or required dates are missing.
      ValueError: If price values contain non-finite numbers or insufficient history.
    """
    for s in SECTOR_NAMES:
        if s not in price_df.columns:
            raise KeyError(f"Price DataFrame missing required sector: {s}")

    missing_dates = required_dates.difference(price_df.index)
    if len(missing_dates) > 0:
        raise KeyError(f"Price DataFrame is missing {len(missing_dates)} required simulation dates.")

    first_req_date = required_dates[0]
    historical_sessions = price_df.index[price_df.index <= first_req_date]
    if len(historical_sessions) < lookback + 1:
        raise ValueError(
            f"Insufficient historical price sessions for volatility lookback ({lookback} required, "
            f"got {len(historical_sessions)})."
        )

    # Check for NaN / non-positive prices across the required date range
    sub_prices = price_df.loc[historical_sessions[-(lookback + 1):].union(required_dates)]
    if sub_prices.isna().any().any():
        raise ValueError("Price DataFrame contains NaN values in the required date range.")
    if (sub_prices <= 0).any().any():
        raise ValueError("Price DataFrame contains zero or negative prices.")


def validate_timeline_partition(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Reconcile date ranges and period session counts against frozen specifications.

    Returns:
      Dict[str, Any]: Summary dictionary with verified timeline metadata.
    """
    total_count = len(df)
    train_mask = df["period"] == "train"
    holdout_mask = df["period"] == "holdout"

    train_count = int(train_mask.sum())
    holdout_count = int(holdout_mask.sum())

    train_dates = df.index[train_mask]
    holdout_dates = df.index[holdout_mask]

    if total_count != EXPECTED_TOTAL_SESSIONS:
        raise ValueError(f"Expected {EXPECTED_TOTAL_SESSIONS} total sessions, got {total_count}.")
    if train_count != EXPECTED_TRAIN_SESSIONS:
        raise ValueError(f"Expected {EXPECTED_TRAIN_SESSIONS} train sessions, got {train_count}.")
    if holdout_count != EXPECTED_HOLDOUT_SESSIONS:
        raise ValueError(f"Expected {EXPECTED_HOLDOUT_SESSIONS} holdout sessions, got {holdout_count}.")

    actual_train_start = str(train_dates.min().date())
    actual_train_end = str(train_dates.max().date())
    actual_holdout_start = str(holdout_dates.min().date())
    actual_holdout_end = str(holdout_dates.max().date())

    if actual_train_start != EXPECTED_TRAIN_START or actual_train_end != EXPECTED_TRAIN_END:
        raise ValueError(
            f"Train date mismatch: expected {EXPECTED_TRAIN_START} to {EXPECTED_TRAIN_END}, "
            f"got {actual_train_start} to {actual_train_end}."
        )

    if actual_holdout_start != EXPECTED_HOLDOUT_START or actual_holdout_end != EXPECTED_HOLDOUT_END:
        raise ValueError(
            f"Holdout date mismatch: expected {EXPECTED_HOLDOUT_START} to {EXPECTED_HOLDOUT_END}, "
            f"got {actual_holdout_start} to {actual_holdout_end}."
        )

    return {
        "total_sessions": total_count,
        "train_sessions": train_count,
        "holdout_sessions": holdout_count,
        "train_start": actual_train_start,
        "train_end": actual_train_end,
        "holdout_start": actual_holdout_start,
        "holdout_end": actual_holdout_end,
    }


# =====================================================================
# 2. Schedule Validation and Invariant Checks
# =====================================================================

def validate_schedule(
    schedule_df: pd.DataFrame,
    variant: Union[StrategyVariant, str],
    tol: float = 1e-5,
    expected_len: Optional[int] = None,
) -> None:
    """
    Validate target-weight invariants, operational flags, cash targets, and state continuity.

    Args:
      schedule_df: Allocation schedule DataFrame indexed by Date.
      variant: Strategy variant ('1A', '1B', '2A', '2B').
      tol: Numerical comparison tolerance.
      expected_len: Optional expected length (e.g., 1687 for full timeline).

    Raises:
      KeyError / ValueError: If schema, invariants, or state continuity checks fail.
    """
    v_obj = StrategyVariant.from_str(variant) if isinstance(variant, str) else variant
    v_str = v_obj.value

    # Index and length checks
    if not isinstance(schedule_df.index, pd.DatetimeIndex):
        raise ValueError("Schedule index must be pd.DatetimeIndex.")
    if not schedule_df.index.is_monotonic_increasing:
        raise ValueError("Schedule dates must be monotonically increasing.")
    if not schedule_df.index.is_unique:
        raise ValueError("Schedule contains duplicate dates.")
    if expected_len is not None and len(schedule_df) != expected_len:
        raise ValueError(f"Schedule length {len(schedule_df)} != expected {expected_len}.")

    # Required column presence
    missing_cols = [c for c in SCHEDULE_COLUMNS if c not in schedule_df.columns]
    if missing_cols:
        raise KeyError(f"Schedule missing required columns: {missing_cols}")

    # Variant column consistency
    short_code = v_str[:2]  # '1A', '1B', '2A', '2B'
    valid_variant_labels = {short_code, v_str}
    actual_variants = set(schedule_df["variant"].unique())
    if not actual_variants.issubset(valid_variant_labels):
        raise ValueError(f"Schedule 'variant' column values {actual_variants} do not match expected {valid_variant_labels}.")

    # Weight invariants: non-negative and row sum == 1.0
    w_mat = schedule_df[WEIGHT_COLS].values
    if (w_mat < -tol).any():
        raise ValueError(f"Variant {short_code}: Negative weights detected.")
    row_sums = w_mat.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=tol):
        max_dev = np.max(np.abs(row_sums - 1.0))
        raise ValueError(f"Variant {short_code}: Target weights do not sum to 1.0 (max dev: {max_dev:.2e}).")

    # Day 0 initialization invariant:
    # Before the first rebalance, portfolio is 100% NIFTY 50.
    # On Day 0, holding_days_before must be 0 and incumbent_regime_before must be null/None.
    first_row = schedule_df.iloc[0]
    if first_row["holding_days_before"] != 0:
        raise ValueError(f"Variant {short_code}: Day 0 holding_days_before must be 0.")
    if pd.notna(first_row["incumbent_regime_before"]):
        raise ValueError(f"Variant {short_code}: Day 0 incumbent_regime_before must be None/NaN.")

    if first_row["rebalance_triggered"]:
        # Transition from initial 100% NIFTY 50 into target regime
        if not np.isclose(first_row["turnover"], 1.0, atol=tol):
            raise ValueError(f"Variant {short_code}: Day 0 initial rebalance turnover must be 1.0.")
    else:
        # Unconfident signal on Day 0: portfolio remains 100% NIFTY 50
        if not np.isclose(first_row["w_NIFTY50"], 1.0, atol=tol):
            raise ValueError(f"Variant {short_code}: Day 0 portfolio must be 100% NIFTY 50 when no rebalance occurs.")

    # Cash target rules
    expected_cash_targets = TEMPLATE_A_CASH if v_obj.template == "A" else TEMPLATE_B_CASH

    rebal_dates = schedule_df[schedule_df["rebalance_triggered"]].index
    if len(rebal_dates) > 0:
        first_rebal = rebal_dates[0]
        post_rebal = schedule_df.loc[first_rebal:]
        for dt, row in post_rebal.iterrows():
            inc = int(row["incumbent_regime_after"])
            expected_cash = expected_cash_targets[inc]
            actual_cash = row["w_CASH"]
            if not np.isclose(actual_cash, expected_cash, atol=tol):
                raise ValueError(
                    f"Variant {short_code} Date {dt.date()}: Expected {expected_cash:.2f} cash for R{inc}, "
                    f"got {actual_cash:.4f}"
                )

    # Train-to-holdout state continuity check
    train_idx = schedule_df.index[schedule_df["period"] == "train"]
    holdout_idx = schedule_df.index[schedule_df["period"] == "holdout"]

    if len(train_idx) > 0 and len(holdout_idx) > 0:
        last_train_dt = train_idx[-1]
        first_holdout_dt = holdout_idx[0]

        train_end_row = schedule_df.loc[last_train_dt]
        holdout_start_row = schedule_df.loc[first_holdout_dt]

        # Incumbent regime before holdout must match incumbent regime after train end
        inc_train_after = train_end_row["incumbent_regime_after"]
        inc_holdout_before = holdout_start_row["incumbent_regime_before"]
        if inc_train_after != inc_holdout_before:
            raise ValueError(
                f"Variant {short_code}: State discontinuity! Incumbent after train ({inc_train_after}) "
                f"!= incumbent before holdout ({inc_holdout_before})."
            )

        # Holding days before holdout must match holding days after train end
        hold_train_after = train_end_row["holding_days_after"]
        hold_holdout_before = holdout_start_row["holding_days_before"]
        if hold_train_after != hold_holdout_before:
            raise ValueError(
                f"Variant {short_code}: Holding clock discontinuity! Holding after train ({hold_train_after}) "
                f"!= holding before holdout ({hold_holdout_before})."
            )


# =====================================================================
# 3. Schedule Generation and Pipeline Orchestration
# =====================================================================

def generate_portfolio_schedule(
    variant: Union[StrategyVariant, str],
    prob_df: pd.DataFrame,
    price_df: Optional[pd.DataFrame] = None,
    engine_kwargs: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Generate target-weight allocation schedule for a single strategy variant across the full timeline.

    Args:
      variant: Strategy variant ('1A', '1B', '2A', '2B').
      prob_df: Datetime-indexed causal probabilities DataFrame (must contain 'period' and prob_0..prob_5).
      price_df: Close price DataFrame (required for inverse-volatility variants 1B and 2B).
      engine_kwargs: Optional overrides for RegimeRotationRulesEngine parameters.

    Returns:
      pd.DataFrame: Validated schedule DataFrame indexed by Date with SCHEDULE_COLUMNS.
    """
    v_obj = StrategyVariant.from_str(variant) if isinstance(variant, str) else variant
    v_str = v_obj.value

    kwargs = engine_kwargs or {}
    engine = RegimeRotationRulesEngine(variant=v_obj, **kwargs)

    # Execute continuous sequence over full timeline
    raw_schedule = engine.generate_schedule(
        dates=prob_df.index,
        probabilities_df=prob_df,
        price_df=price_df,
    )

    # Attach period partition and variant identifier
    variant_code = variant if isinstance(variant, str) and len(variant) == 2 else v_str[:2]
    raw_schedule["period"] = prob_df.loc[raw_schedule.index, "period"]
    raw_schedule["variant"] = variant_code
    raw_schedule.index.name = "Date"

    # Reorder columns to canonical schema
    ordered_schedule = raw_schedule[SCHEDULE_COLUMNS].copy()

    # Invariant validation
    validate_schedule(ordered_schedule, variant=v_obj)

    return ordered_schedule


def generate_all_schedules(
    prob_df: pd.DataFrame,
    price_df: pd.DataFrame,
    engine_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Generate all four canonical target-weight schedules (1A, 1B, 2A, 2B).

    Returns:
      Dict[str, pd.DataFrame]: Mapping of variant name ('1A', '1B', '2A', '2B') to its schedule.
    """
    schedules: Dict[str, pd.DataFrame] = {}
    for v in ["1A", "1B", "2A", "2B"]:
        logger.info(f"Generating schedule for Strategy Variant {v}...")
        schedules[v] = generate_portfolio_schedule(
            variant=v,
            prob_df=prob_df,
            price_df=price_df,
            engine_kwargs=engine_kwargs,
        )
    return schedules


def save_target_weight_schedules(
    schedules: Dict[str, pd.DataFrame],
    output_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Path]:
    """
    Persist validated schedules to their canonical CSV paths under results/portfolio_construction/.

    Args:
      schedules: Dictionary mapping variant names ('1A', '1B', '2A', '2B') to schedule DataFrames.
      output_dir: Directory path. Defaults to results/portfolio_construction/.

    Returns:
      Dict[str, Path]: Mapping of variant name to saved file path.
    """
    out_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: Dict[str, Path] = {}
    for variant, sched in schedules.items():
        fname = TARGET_WEIGHT_FILENAMES.get(variant, f"target_weights_{variant}.csv")
        target_path = out_dir / fname

        # Validate before writing
        validate_schedule(sched, variant=variant)

        # Write to CSV with Date index
        sched.to_csv(target_path, index=True, index_label="Date")
        saved_paths[variant] = target_path
        logger.info(f"Saved {variant} schedule to {target_path} ({len(sched)} rows)")

    return saved_paths


def reload_and_verify_schedules(
    saved_paths: Dict[str, Path],
    original_schedules: Optional[Dict[str, pd.DataFrame]] = None,
    tol: float = 1e-5,
) -> Dict[str, Dict[str, Any]]:
    """
    Reload persisted CSV schedules from disk and strictly verify their schema,
    row counts, date ranges, period partitions, and exact numerical parity.

    Returns:
      Dict[str, Dict[str, Any]]: Per-variant audit verification summary.
    """
    audit_results: Dict[str, Dict[str, Any]] = {}

    for variant, fpath in saved_paths.items():
        if not fpath.exists():
            raise FileNotFoundError(f"Persisted schedule not found at {fpath}")

        # Reload CSV
        reloaded = pd.read_csv(fpath, parse_dates=["Date", "exec_date"]).set_index("Date")

        # Invariant checks on reloaded data
        validate_schedule(reloaded, variant=variant, tol=tol)

        # Period reconciliation
        train_rows = (reloaded["period"] == "train").sum()
        holdout_rows = (reloaded["period"] == "holdout").sum()

        # Rebalance metrics
        rebal_total = int(reloaded["rebalance_triggered"].sum())
        rebal_train = int(reloaded[reloaded["period"] == "train"]["rebalance_triggered"].sum())
        rebal_holdout = int(reloaded[reloaded["period"] == "holdout"]["rebalance_triggered"].sum())
        mean_turnover = float(reloaded["turnover"].mean())

        # Exact parity comparison against in-memory original
        parity_confirmed = False
        if original_schedules is not None and variant in original_schedules:
            orig = original_schedules[variant]
            # Verify shapes and column match
            if orig.shape != reloaded.shape or list(orig.columns) != list(reloaded.columns):
                raise ValueError(f"Reloaded {variant} shape/columns do not match original.")

            # Check float/int/bool parity
            for col in orig.columns:
                if col in ["period", "variant"]:
                    assert (orig[col].values == reloaded[col].values).all(), f"Mismatch in {col}"
                elif col in ["exec_date"]:
                    assert (orig[col].values == reloaded[col].values).all(), f"Mismatch in {col}"
                elif orig[col].dtype == bool:
                    assert (orig[col].values == reloaded[col].values).all(), f"Mismatch in {col}"
                else:
                    o_vals = orig[col].fillna(-999).values.astype(float)
                    r_vals = reloaded[col].fillna(-999).values.astype(float)
                    assert np.allclose(o_vals, r_vals, atol=tol), f"Mismatch in {col}"
            parity_confirmed = True

        audit_results[variant] = {
            "path": str(fpath),
            "rows": len(reloaded),
            "columns": len(reloaded.columns),
            "train_rows": int(train_rows),
            "holdout_rows": int(holdout_rows),
            "start_date": str(reloaded.index.min().date()),
            "end_date": str(reloaded.index.max().date()),
            "rebalances_total": rebal_total,
            "rebalances_train": rebal_train,
            "rebalances_holdout": rebal_holdout,
            "mean_turnover_pct": round(mean_turnover * 100.0, 3),
            "parity_verified": parity_confirmed,
        }

    return audit_results


def run_portfolio_construction_pipeline(
    prob_path: Optional[Union[str, Path]] = None,
    price_dir: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Path], Dict[str, Any]]:
    """
    Execute the end-to-end Phase 9.2 portfolio construction pipeline:
      1. Load and validate causal probabilities and sector closing prices.
      2. Verify timeline partitions (1,265 train + 422 holdout = 1,687 total sessions).
      3. Generate all four canonical target-weight schedules (1A, 1B, 2A, 2B).
      4. Validate target weights, cash targets, and state continuity across train/holdout.
      5. Persist canonical CSV files to results/portfolio_construction/.
      6. Reload and strictly audit saved files for numerical and schema integrity.

    Returns:
      Tuple of (schedules_dict, saved_paths_dict, audit_metadata_dict).
    """
    # 1. Load inputs
    prob_df = load_causal_probabilities(prob_path)
    price_df = load_aligned_prices(price_dir)

    # 2. Validate timeline and price coverage
    partition_meta = validate_timeline_partition(prob_df)
    validate_price_coverage(price_df, prob_df.index)

    # 3. Generate schedules
    schedules = generate_all_schedules(prob_df, price_df)

    # 4. Persist to canonical CSVs
    saved_paths = save_target_weight_schedules(schedules, output_dir=output_dir)

    # 5. Reload and verify
    audit_meta = reload_and_verify_schedules(saved_paths, original_schedules=schedules)

    combined_metadata = {
        "partition": partition_meta,
        "variants": audit_meta,
    }

    return schedules, saved_paths, combined_metadata
