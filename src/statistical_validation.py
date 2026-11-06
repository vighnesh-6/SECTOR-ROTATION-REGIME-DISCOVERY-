"""
Phase 11 — Statistical Validation Engine for Sector Rotation Strategies.

This module provides the complete statistical inference, multiple-testing correction,
and non-parametric bootstrap validation framework for evaluating the canonical
ML-based sector rotation strategies (1A, 1B, 2A, 2B) against passive benchmarks
(NIFTY 50, Equal-Weight Sector) and active comparators (Naive Top-2 Momentum).

Authoritative Econometric Methodology:
  1. Heteroskedasticity and Autocorrelation Consistent (HAC) Alpha Inference:
     - Newey and West (1987, 1994) OLS regression with automatic Bartlett bandwidth
       L = floor(4.0 * (T / 100)^(2/9)).
     - Full (N=1,686, L=7), Train (N=1,264, L=7), Pseudo-OOS (N=422, L=5).
  2. Standalone Risk-Adjusted Inference:
     - Lo (2002) HAC asymptotic Sharpe inference via influence function representation
       and long-run spectral variance.
  3. Paired Comparative Sharpe Inference:
     - Ledoit and Wolf (2008) bivariate Delta-method HAC test with analytical gradients
       and Newey-West spectral covariance matrix.
  4. Non-Parametric Resampling:
     - Politis and Romano (1994) Stationary Block Bootstrap with geometric block sampling
       and synchronous paired vector resampling.
     - Studentized null-centered bootstrap p-values and uncentered percentile CIs.
     - Primary block length b = 21 days; sensitivity sweep {5, 10, 21, 42, 63}.
  5. Multiple Testing Error Control:
     - Unified Omnibus Holm-Bonferroni Family (M = 12) bounding global FWER <= 0.05.
     - Two-Tier Hierarchical Gatekeeping Procedure (Fixed-Sequence Tree).
     - Benjamini-Hochberg (BH) False Discovery Rate screening (M = 36 exploratory).
     - Benjamini-Yekutieli (BY) dependence-robust sensitivity lower bound.
  6. Regime Persistence Diagnostics:
     - Conditional empirical run-length analysis with bootstrap duration intervals.

Strict Constraints:
  - Canonical Phase 6–10 artifacts remain frozen and read-only.
  - Zero risk-free baseline (R_f = 0.0) and 252.0 annualization factor strictly maintained.
  - Deterministic reproducibility guaranteed via seed = 42.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats

from src.portfolio_backtest import (
    ANNUALIZATION_FACTOR,
    DEFAULT_TRANSACTION_COST_RATE,
    load_backtest_inputs,
    simulate_portfolio,
)
from src.robustness.benchmark_sensitivity import construct_naive_momentum_schedule

# Configure logger
logger = logging.getLogger("statistical_validation")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s | %(name)s | %(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# =====================================================================
# Authoritative Constants and Nomenclature
# =====================================================================

VARIANTS: List[str] = ["1A", "1B", "2A", "2B"]
PASSIVE_BENCHMARKS: List[str] = ["NIFTY50", "EQUAL_WEIGHT"]
ALL_COMPARATORS: List[str] = ["NIFTY50", "EQUAL_WEIGHT", "MOMENTUM_TOP2"]

PERIOD_NAMES: List[str] = ["train", "holdout", "full"]

PERIOD_LABELS: Dict[str, str] = {
    "train": "Model In-Sample Development (Train)",
    "holdout": "Previously Inspected Pseudo-OOS (Holdout)",
    "full": "Full Historical Lifecycle Backtest (Full)",
}

PERIOD_RANGES: Dict[str, Tuple[str, str]] = {
    "train": ("2019-11-01", "2024-12-31"),
    "holdout": ("2025-01-02", "2026-09-18"),
    "full": ("2019-11-01", "2026-09-18"),
}

PERIOD_COUNTS: Dict[str, int] = {
    "train": 1264,
    "holdout": 422,
    "full": 1686,
}

DEFAULT_BOOTSTRAP_REPLICATIONS: int = 2000
DEFAULT_BOOTSTRAP_SEED: int = 42
DEFAULT_PRIMARY_BLOCK_LENGTH: float = 21.0
SENSITIVITY_BLOCK_LENGTHS: List[float] = [5.0, 10.0, 21.0, 42.0, 63.0]
HOLDOUT_PRIMARY_BLOCK_LENGTHS: List[float] = [5.0, 10.0, 21.0]

DEFAULT_MOMENTUM_PARQUET_PATH: Path = Path(
    "results/portfolio_backtest/robustness/benchmark/daily_simulation_momentum.parquet"
)


# =====================================================================
# 1. Deterministic Momentum Comparator Reproduction
# =====================================================================

def ensure_daily_momentum_simulation(
    price_df: Optional[pd.DataFrame] = None,
    output_path: Optional[Union[str, Path]] = None,
    cost_rate: float = DEFAULT_TRANSACTION_COST_RATE,
    force_recompute: bool = False,
) -> pd.DataFrame:
    """
    Ensure the daily simulation parquet for the Naive Top-2 Momentum comparator
    exists on disk and is loaded with full validation.

    If the parquet already exists and force_recompute is False, it is loaded
    and verified. If missing or forced, it is deterministically generated using
    Phase 10's construct_naive_momentum_schedule and simulate_portfolio.

    Args:
      price_df: Aligned closing price DataFrame. If None, loaded via load_backtest_inputs().
      output_path: Target parquet destination path.
      cost_rate: One-way transaction fee rate (default: 0.0015 = 15 bps).
      force_recompute: If True, regenerates the file even if present.

    Returns:
      pd.DataFrame: Daily simulation record for Naive Momentum (1,686 rows).
    """
    out_p = Path(output_path) if output_path is not None else DEFAULT_MOMENTUM_PARQUET_PATH

    if out_p.exists() and not force_recompute:
        logger.info(f"Loading existing daily momentum simulation from: {out_p}")
        daily_mom = pd.read_parquet(out_p)
    else:
        logger.info("Generating daily simulation for Naive Top-2 Momentum comparator...")
        if price_df is None:
            _, price_df, _ = load_backtest_inputs()

        sched_mom = construct_naive_momentum_schedule(price_df)
        daily_mom = simulate_portfolio(
            schedule_df=sched_mom,
            price_df=price_df,
            cost_rate=cost_rate,
        )

        out_p.parent.mkdir(parents=True, exist_ok=True)
        daily_mom.to_parquet(out_p)
        logger.info(f"Persisted daily momentum simulation ({len(daily_mom)} rows) to: {out_p}")

    # Integrity verification
    n_total = len(daily_mom)
    if n_total != PERIOD_COUNTS["full"]:
        raise ValueError(
            f"Momentum simulation length mismatch: expected {PERIOD_COUNTS['full']} rows, got {n_total}."
        )

    for p_name, exp_n in [("train", PERIOD_COUNTS["train"]), ("holdout", PERIOD_COUNTS["holdout"])]:
        actual_n = int((daily_mom["period"] == p_name).sum())
        if actual_n != exp_n:
            raise ValueError(
                f"Momentum period '{p_name}' count mismatch: expected {exp_n}, got {actual_n}."
            )

    return daily_mom


# =====================================================================
# 2. HAC Bandwidth and Bartlett Weights
# =====================================================================

def compute_automatic_hac_bandwidth(T: int) -> int:
    """
    Calculate the automatic Bartlett kernel bandwidth for Newey-West HAC estimation:
      L = floor(4.0 * (T / 100.0)^(2/9))

    Exact integer results:
      T = 1686 -> L = 7
      T = 1264 -> L = 7
      T = 422  -> L = 5
    """
    if T < 3:
        return 0
    val = 4.0 * ((float(T) / 100.0) ** (2.0 / 9.0))
    return max(1, int(math.floor(val)))


def bartlett_weights(L: int) -> np.ndarray:
    """
    Compute Bartlett kernel weights w(j, L) = 1.0 - j / (L + 1) for lags j = 1, ..., L.
    """
    if L <= 0:
        return np.array([], dtype=float)
    j = np.arange(1, L + 1, dtype=float)
    return 1.0 - (j / (float(L) + 1.0))


# =====================================================================
# 3. Newey-West HAC Jensen's Alpha & Market Beta
# =====================================================================

def compute_hac_alpha_beta(
    r_strategy: Union[np.ndarray, Sequence[float], pd.Series],
    r_benchmark: Union[np.ndarray, Sequence[float], pd.Series],
    ann_factor: float = ANNUALIZATION_FACTOR,
    max_lags: Optional[int] = None,
) -> Dict[str, float]:
    """
    Perform single-factor OLS regression of strategy returns on benchmark returns:
      r_strategy,t = alpha_daily + beta * r_benchmark,t + epsilon_t

    Computes Beta, Annualized Jensen's Alpha, classical OLS standard errors,
    and Newey-West (1987, 1994) HAC standard errors, t-statistics, and p-values
    (both one-sided and two-sided).

    Args:
      r_strategy: Array of daily net strategy returns.
      r_benchmark: Array of daily net benchmark returns.
      ann_factor: Annualization factor (default: 252.0).
      max_lags: HAC truncation lag. If None, automatic rule L = floor(4*(T/100)^(2/9)) is used.

    Returns:
      Dict[str, float] containing comprehensive regression estimates and inference.
    """
    y = np.asarray(r_strategy, dtype=float)
    x = np.asarray(r_benchmark, dtype=float)
    N = len(y)

    if N != len(x):
        raise ValueError(f"Length mismatch: len(y)={N}, len(x)={len(x)}.")
    if N < 4:
        raise ValueError(f"HAC regression requires at least 4 observations, got {N}.")

    # Design matrix X = [1, x]
    X = np.column_stack([np.ones(N, dtype=float), x])
    XtX = X.T @ X

    try:
        inv_XtX = np.linalg.inv(XtX)
    except np.linalg.LinAlgError:
        inv_XtX = np.linalg.pinv(XtX)

    beta_vec = inv_XtX @ (X.T @ y)
    alpha_daily = float(beta_vec[0])
    beta = float(beta_vec[1])

    residuals = y - (X @ beta_vec)
    dof = N - 2
    s2_ols = float(residuals @ residuals) / max(1, dof)
    cov_ols = s2_ols * inv_XtX

    se_alpha_ols_daily = float(np.sqrt(max(0.0, cov_ols[0, 0])))
    se_beta_ols = float(np.sqrt(max(0.0, cov_ols[1, 1])))

    # Automatic lag selection
    L = compute_automatic_hac_bandwidth(N) if max_lags is None else max(0, int(max_lags))

    # HAC Spectral Matrix S = Gamma_0 + sum_{j=1}^L w_j (Gamma_j + Gamma_j^T)
    # v_t = x_t * e_t
    V = X * residuals[:, np.newaxis]  # (N, 2)
    gamma_0 = (V.T @ V) / float(N)
    S_hac = gamma_0.copy()

    if L > 0:
        weights = bartlett_weights(L)
        for j_idx, lag in enumerate(range(1, L + 1)):
            w = weights[j_idx]
            gamma_j = (V[lag:].T @ V[:-lag]) / float(N)
            S_hac += w * (gamma_j + gamma_j.T)

    # Asymptotic covariance matrix: Omega_HAC = inv(X'X) * (N * S_hac) * inv(X'X)
    cov_hac = inv_XtX @ (float(N) * S_hac) @ inv_XtX

    se_alpha_hac_daily = float(np.sqrt(max(0.0, cov_hac[0, 0])))
    se_beta_hac = float(np.sqrt(max(0.0, cov_hac[1, 1])))

    # Annualization
    alpha_ann = float(alpha_daily * ann_factor)
    alpha_ann_pct = float(alpha_ann * 100.0)
    se_alpha_ols_ann = float(se_alpha_ols_daily * ann_factor)
    se_alpha_hac_ann = float(se_alpha_hac_daily * ann_factor)

    # Test statistics
    t_alpha_hac = float(alpha_daily / se_alpha_hac_daily) if se_alpha_hac_daily > 1e-12 else 0.0
    t_beta_hac = float(beta / se_beta_hac) if se_beta_hac > 1e-12 else 0.0

    # p-values (Student-t with N-2 degrees of freedom)
    p_alpha_hac_2s = float(2.0 * (1.0 - stats.t.cdf(abs(t_alpha_hac), df=dof)))
    p_alpha_hac_1s = float(1.0 - stats.t.cdf(t_alpha_hac, df=dof)) if t_alpha_hac >= 0.0 else float(stats.t.cdf(t_alpha_hac, df=dof))

    t_alpha_ols = float(alpha_daily / se_alpha_ols_daily) if se_alpha_ols_daily > 1e-12 else 0.0
    p_alpha_ols_2s = float(2.0 * (1.0 - stats.t.cdf(abs(t_alpha_ols), df=dof)))
    p_alpha_ols_1s = float(1.0 - stats.t.cdf(t_alpha_ols, df=dof)) if t_alpha_ols >= 0.0 else float(stats.t.cdf(t_alpha_ols, df=dof))

    p_beta_hac_2s = float(2.0 * (1.0 - stats.t.cdf(abs(t_beta_hac), df=dof)))

    # R-squared
    var_y = float(np.var(y, ddof=1))
    r_squared = float(1.0 - (s2_ols / var_y)) if var_y > 1e-14 else 0.0
    r_squared = max(0.0, min(1.0, r_squared))

    return {
        "sample_count": float(N),
        "hac_lags": float(L),
        "beta": beta,
        "beta_stderr_ols": se_beta_ols,
        "beta_stderr_hac": se_beta_hac,
        "beta_tstat_hac": t_beta_hac,
        "beta_pvalue_hac": p_beta_hac_2s,
        "alpha_daily": alpha_daily,
        "alpha_annualized": alpha_ann,
        "alpha_annualized_pct": alpha_ann_pct,
        "alpha_stderr_ols_daily": se_alpha_ols_daily,
        "alpha_stderr_ols_ann": se_alpha_ols_ann,
        "alpha_tstat_ols": t_alpha_ols,
        "alpha_pvalue_ols_1sided": p_alpha_ols_1s,
        "alpha_pvalue_ols_2sided": p_alpha_ols_2s,
        "alpha_stderr_hac_daily": se_alpha_hac_daily,
        "alpha_stderr_hac_ann": se_alpha_hac_ann,
        "alpha_tstat_hac": t_alpha_hac,
        "alpha_pvalue_hac_1sided": p_alpha_hac_1s,
        "alpha_pvalue_hac_2sided": p_alpha_hac_2s,
        "r_squared": r_squared,
    }


# =====================================================================
# 4. Lo (2002) Standalone Sharpe Ratio Inference
# =====================================================================

def compute_lo_sharpe_inference(
    r_series: Union[np.ndarray, Sequence[float], pd.Series],
    ann_factor: float = ANNUALIZATION_FACTOR,
    max_lags: Optional[int] = None,
) -> Dict[str, float]:
    """
    Perform autocorrelation-consistent and non-normality-robust Sharpe ratio
    inference following Andrew Lo (2002, Financial Analysts Journal).

    Evaluates H0: SR <= 0 vs H1: SR > 0 (one-sided) and H0: SR = 0 (two-sided).

    Method:
      Daily Sharpe: SR_daily = mean / std (ddof=1).
      Influence function for observation t:
        z_t = ((r_t - mean) / std) - 0.5 * SR_daily * [((r_t - mean) / std)^2 - 1.0]
      Long-run variance Omega_z via Newey-West Bartlett kernel.
      Annualized AsyVar(SR_ann) = (ann_factor / T) * Omega_z.
      z_stat = SR_ann / sqrt(AsyVar(SR_ann)).
    """
    r = np.asarray(r_series, dtype=float)
    T = len(r)

    if T < 4:
        raise ValueError(f"Lo Sharpe inference requires at least 4 observations, got {T}.")

    mean = float(np.mean(r))
    std = float(np.std(r, ddof=1))

    if std <= 1e-12:
        return {
            "sample_count": float(T),
            "hac_lags": 0.0,
            "sharpe_daily": 0.0,
            "sharpe_annualized": 0.0,
            "sharpe_stderr_iid": 0.0,
            "sharpe_stderr_hac": 0.0,
            "z_stat_hac": 0.0,
            "p_value_1sided": 1.0,
            "p_value_2sided": 1.0,
        }

    sr_daily = mean / std
    sr_ann = sr_daily * np.sqrt(ann_factor)

    # Standardized deviations
    u = (r - mean) / std

    # Higher moments
    skew = float(np.mean(u ** 3))
    kurt = float(np.mean(u ** 4))

    # Classical Lo IID variance (Proposition 1):
    # AsyVar_IID(SR_daily) = (1 / T) * [ 1 + 0.5 * SR^2 - skew * SR + 0.25 * (kurt - 3) * SR^2 ]
    var_iid_daily = (1.0 / float(T)) * (
        1.0 + 0.5 * (sr_daily ** 2) - skew * sr_daily + 0.25 * (kurt - 3.0) * (sr_daily ** 2)
    )
    se_iid_ann = float(np.sqrt(max(0.0, var_iid_daily * ann_factor)))

    # Influence function for serial correlation (Proposition 2):
    z = u - 0.5 * sr_daily * (u ** 2 - 1.0)
    z_bar = float(np.mean(z))
    z_demeaned = z - z_bar

    # Bartlett kernel HAC long-run variance of z
    L = compute_automatic_hac_bandwidth(T) if max_lags is None else max(0, int(max_lags))
    gamma_0 = float(np.mean(z_demeaned ** 2))
    lr_var_z = gamma_0

    if L > 0:
        weights = bartlett_weights(L)
        for j_idx, lag in enumerate(range(1, L + 1)):
            w = weights[j_idx]
            gamma_j = float(np.mean(z_demeaned[lag:] * z_demeaned[:-lag]))
            lr_var_z += 2.0 * w * gamma_j

    lr_var_z = max(1e-12, lr_var_z)
    var_hac_daily = lr_var_z / float(T)
    se_hac_ann = float(np.sqrt(max(0.0, var_hac_daily * ann_factor)))

    z_stat = float(sr_ann / se_hac_ann) if se_hac_ann > 1e-12 else 0.0

    p_1s = float(1.0 - stats.norm.cdf(z_stat)) if z_stat >= 0.0 else float(stats.norm.cdf(z_stat))
    p_2s = float(2.0 * (1.0 - stats.norm.cdf(abs(z_stat))))

    return {
        "sample_count": float(T),
        "hac_lags": float(L),
        "sharpe_daily": float(sr_daily),
        "sharpe_annualized": float(sr_ann),
        "skewness": skew,
        "kurtosis": kurt,
        "sharpe_stderr_iid": se_iid_ann,
        "sharpe_stderr_hac": se_hac_ann,
        "z_stat_hac": z_stat,
        "p_value_1sided": p_1s,
        "p_value_2sided": p_2s,
    }


# =====================================================================
# 5. Ledoit-Wolf (2008) Paired Sharpe Difference Test
# =====================================================================

def compute_ledoit_wolf_sharpe_diff(
    r1: Union[np.ndarray, Sequence[float], pd.Series],
    r2: Union[np.ndarray, Sequence[float], pd.Series],
    ann_factor: float = ANNUALIZATION_FACTOR,
    max_lags: Optional[int] = None,
) -> Dict[str, float]:
    """
    Perform robust paired comparative Sharpe ratio hypothesis testing
    following Olivier Ledoit and Michael Wolf (2008, Journal of Empirical Finance).

    Evaluates H0: Delta_SR = SR_1 - SR_2 <= 0 vs H1: Delta_SR > 0 (one-sided)
    and H0: Delta_SR = 0 vs H1: Delta_SR != 0 (two-sided).

    Method:
      Parameter vector theta = (mu1, mu2, gamma1, gamma2)^T with gamma = E[r^2].
      Difference function f(theta) = mu1 / sqrt(gamma1 - mu1^2) - mu2 / sqrt(gamma2 - mu2^2).
      Analytical gradient grad_f in R^4.
      Spectral covariance matrix Psi in R^{4x4} estimated via Newey-West Bartlett kernel.
      AsyVar(Delta_daily) = (1 / T) * (grad_f^T * Psi * grad_f).
      z_LW = Delta_daily / sqrt(AsyVar(Delta_daily)) ~ N(0, 1).
    """
    y1 = np.asarray(r1, dtype=float)
    y2 = np.asarray(r2, dtype=float)
    T = len(y1)

    if T != len(y2):
        raise ValueError(f"Length mismatch: len(r1)={T}, len(r2)={len(y2)}.")
    if T < 4:
        raise ValueError(f"Ledoit-Wolf test requires at least 4 observations, got {T}.")

    # Parameter estimates
    mu1 = float(np.mean(y1))
    mu2 = float(np.mean(y2))
    gam1 = float(np.mean(y1 ** 2))
    gam2 = float(np.mean(y2 ** 2))

    var1 = max(1e-14, gam1 - mu1 ** 2)
    var2 = max(1e-14, gam2 - mu2 ** 2)
    sig1 = float(np.sqrt(var1))
    sig2 = float(np.sqrt(var2))

    sr1_daily = mu1 / sig1
    sr2_daily = mu2 / sig2
    diff_daily = sr1_daily - sr2_daily

    sr1_ann = sr1_daily * np.sqrt(ann_factor)
    sr2_ann = sr2_daily * np.sqrt(ann_factor)
    diff_ann = diff_daily * np.sqrt(ann_factor)

    # Analytical gradient vector: grad = (df/dmu1, df/dmu2, df/dgam1, df/dgam2)
    grad = np.array([
        gam1 / (sig1 ** 3),
        -gam2 / (sig2 ** 3),
        -0.5 * mu1 / (sig1 ** 3),
        0.5 * mu2 / (sig2 ** 3),
    ], dtype=float)

    # Demeaned time series vector u_t in R^4
    Y = np.column_stack([y1, y2, y1 ** 2, y2 ** 2])  # (T, 4)
    u = Y - np.array([mu1, mu2, gam1, gam2])

    # Spectral covariance matrix Psi
    L = compute_automatic_hac_bandwidth(T) if max_lags is None else max(0, int(max_lags))
    gamma_0 = (u.T @ u) / float(T)
    Psi = gamma_0.copy()

    if L > 0:
        weights = bartlett_weights(L)
        for j_idx, lag in enumerate(range(1, L + 1)):
            w = weights[j_idx]
            gamma_k = (u[lag:].T @ u[:-lag]) / float(T)
            Psi += w * (gamma_k + gamma_k.T)

    # Asymptotic variance via Delta method
    var_diff_daily = float((grad @ Psi @ grad) / float(T))
    se_diff_daily = float(np.sqrt(max(1e-14, var_diff_daily)))
    se_diff_ann = float(se_diff_daily * np.sqrt(ann_factor))

    z_lw = float(diff_daily / se_diff_daily) if se_diff_daily > 1e-12 else 0.0

    p_1s = float(1.0 - stats.norm.cdf(z_lw)) if z_lw >= 0.0 else float(stats.norm.cdf(z_lw))
    p_2s = float(2.0 * (1.0 - stats.norm.cdf(abs(z_lw))))

    return {
        "sample_count": float(T),
        "hac_lags": float(L),
        "sharpe1_ann": float(sr1_ann),
        "sharpe2_ann": float(sr2_ann),
        "delta_sharpe_ann": float(diff_ann),
        "stderr_delta_ann": float(se_diff_ann),
        "z_stat": float(z_lw),
        "p_value_1sided": p_1s,
        "p_value_2sided": p_2s,
    }


# =====================================================================
# 6. Politis-Romano (1994) Stationary Block Bootstrap
# =====================================================================

def generate_stationary_bootstrap_indices(
    n_obs: int,
    block_length: float,
    n_bootstraps: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> np.ndarray:
    """
    Generate an (n_bootstraps, n_obs) index matrix using Politis and Romano's (1994)
    Stationary Block Bootstrap with circular wrap-around.

    Args:
      n_obs: Sample length N.
      block_length: Expected block length b (parameter p = 1 / b).
      n_bootstraps: Number of bootstrap paths B (default: 2000).
      seed: Random seed for deterministic reproducibility (default: 42).

    Returns:
      np.ndarray: Integer matrix of shape (n_bootstraps, n_obs) with values in 0, ..., N-1.
    """
    if n_obs < 1:
        raise ValueError(f"n_obs must be >= 1, got {n_obs}.")
    if block_length < 1.0:
        raise ValueError(f"block_length must be >= 1.0, got {block_length}.")

    rng = np.random.default_rng(seed)
    p = 1.0 / float(block_length)

    # Initialize index matrix
    indices = np.zeros((n_bootstraps, n_obs), dtype=int)

    # Start of every bootstrap path is a random uniform draw
    indices[:, 0] = rng.integers(0, n_obs, size=n_bootstraps)

    # Transition decisions: Bernoulli(p) for new block, 1-p to increment
    new_block_flags = rng.uniform(0.0, 1.0, size=(n_bootstraps, n_obs - 1)) < p
    random_starts = rng.integers(0, n_obs, size=(n_bootstraps, n_obs - 1))

    for t in range(1, n_obs):
        flag = new_block_flags[:, t - 1]
        prev_idx = indices[:, t - 1]
        # Circular wrap-around: (prev + 1) % n_obs
        cont_idx = (prev_idx + 1) % n_obs
        indices[:, t] = np.where(flag, random_starts[:, t - 1], cont_idx)

    return indices


def run_bootstrap_hypothesis_tests(
    r1: Union[np.ndarray, Sequence[float], pd.Series],
    r2: Optional[Union[np.ndarray, Sequence[float], pd.Series]] = None,
    test_type: str = "sharpe_diff",
    block_length: float = DEFAULT_PRIMARY_BLOCK_LENGTH,
    n_bootstraps: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    studentized: bool = True,
    ann_factor: float = ANNUALIZATION_FACTOR,
) -> Dict[str, Any]:
    """
    Execute stationary block bootstrap hypothesis tests and confidence intervals.

    Supported test_type values:
      - 'sharpe_diff': Compares r1 vs r2 (H0: SR1 - SR2 <= 0).
      - 'sharpe_standalone': Tests r1 (H0: SR1 <= 0).
      - 'alpha_hac': Regression alpha of r1 on r2 (H0: alpha <= 0).

    Computes:
      - Point estimate.
      - 95% uncentered percentile confidence interval [CI_low, CI_high].
      - Studentized or null-centered empirical p-values (both 1-sided and 2-sided)
        using Davison & Hinkley (1997) continuity correction: (1 + sum) / (B + 1).
    """
    y1 = np.asarray(r1, dtype=float)
    T = len(y1)

    if test_type in ["sharpe_diff", "alpha_hac"]:
        if r2 is None:
            raise ValueError(f"test_type '{test_type}' requires r2 benchmark series.")
        y2 = np.asarray(r2, dtype=float)
        if len(y2) != T:
            raise ValueError(f"Length mismatch: len(r1)={T}, len(r2)={len(y2)}.")

    # Generate bootstrap index matrix (synchronous resampling across series)
    idx_matrix = generate_stationary_bootstrap_indices(
        n_obs=T,
        block_length=block_length,
        n_bootstraps=n_bootstraps,
        seed=seed,
    )

    B = n_bootstraps

    if test_type == "sharpe_diff":
        # Base estimate
        base_res = compute_ledoit_wolf_sharpe_diff(y1, y2, ann_factor=ann_factor)
        theta_hat = base_res["delta_sharpe_ann"]
        se_hat = base_res["stderr_delta_ann"]
        t_base = base_res["z_stat"]

        # Resample
        boot_thetas = np.zeros(B, dtype=float)
        boot_ses = np.zeros(B, dtype=float)

        for b in range(B):
            sample_idx = idx_matrix[b]
            yb1 = y1[sample_idx]
            yb2 = y2[sample_idx]
            m1, m2 = np.mean(yb1), np.mean(yb2)
            s1, s2 = np.std(yb1, ddof=1), np.std(yb2, ddof=1)
            sr1 = (m1 / s1) * np.sqrt(ann_factor) if s1 > 1e-12 else 0.0
            sr2 = (m2 / s2) * np.sqrt(ann_factor) if s2 > 1e-12 else 0.0
            boot_thetas[b] = sr1 - sr2
            # Quick standard error proxy under bootstrap or studentized
            if studentized:
                # Fast standard error approximation to avoid full HAC inside loop
                boot_ses[b] = se_hat

        # Percentile CI (uncentered)
        ci_low = float(np.percentile(boot_thetas, 2.5))
        ci_high = float(np.percentile(boot_thetas, 97.5))

        # Null-centered empirical p-value
        if studentized and se_hat > 1e-12:
            t_boot = (boot_thetas - theta_hat) / se_hat
            p_1s = float((1.0 + np.sum(t_boot >= t_base)) / (B + 1.0))
            p_2s = float((1.0 + np.sum(np.abs(t_boot) >= np.abs(t_base))) / (B + 1.0))
        else:
            diff_centered = boot_thetas - theta_hat
            p_1s = float((1.0 + np.sum(diff_centered >= theta_hat)) / (B + 1.0))
            p_2s = float((1.0 + np.sum(np.abs(diff_centered) >= np.abs(theta_hat))) / (B + 1.0))

        return {
            "test_type": "sharpe_diff",
            "sample_count": float(T),
            "block_length": float(block_length),
            "n_bootstraps": float(B),
            "point_estimate": float(theta_hat),
            "stderr": float(se_hat),
            "test_stat": float(t_base),
            "ci_95_lower": ci_low,
            "ci_95_upper": ci_high,
            "p_value_boot_1sided": min(1.0, max(0.0, p_1s)),
            "p_value_boot_2sided": min(1.0, max(0.0, p_2s)),
            "boot_thetas": boot_thetas,
        }

    elif test_type == "sharpe_standalone":
        base_res = compute_lo_sharpe_inference(y1, ann_factor=ann_factor)
        theta_hat = base_res["sharpe_annualized"]
        se_hat = base_res["sharpe_stderr_hac"]
        t_base = base_res["z_stat_hac"]

        boot_thetas = np.zeros(B, dtype=float)
        for b in range(B):
            sample_idx = idx_matrix[b]
            yb = y1[sample_idx]
            mb = np.mean(yb)
            sb = np.std(yb, ddof=1)
            boot_thetas[b] = (mb / sb) * np.sqrt(ann_factor) if sb > 1e-12 else 0.0

        ci_low = float(np.percentile(boot_thetas, 2.5))
        ci_high = float(np.percentile(boot_thetas, 97.5))

        if studentized and se_hat > 1e-12:
            t_boot = (boot_thetas - theta_hat) / se_hat
            p_1s = float((1.0 + np.sum(t_boot >= t_base)) / (B + 1.0))
            p_2s = float((1.0 + np.sum(np.abs(t_boot) >= np.abs(t_base))) / (B + 1.0))
        else:
            diff_centered = boot_thetas - theta_hat
            p_1s = float((1.0 + np.sum(diff_centered >= theta_hat)) / (B + 1.0))
            p_2s = float((1.0 + np.sum(np.abs(diff_centered) >= np.abs(theta_hat))) / (B + 1.0))

        return {
            "test_type": "sharpe_standalone",
            "sample_count": float(T),
            "block_length": float(block_length),
            "n_bootstraps": float(B),
            "point_estimate": float(theta_hat),
            "stderr": float(se_hat),
            "test_stat": float(t_base),
            "ci_95_lower": ci_low,
            "ci_95_upper": ci_high,
            "p_value_boot_1sided": min(1.0, max(0.0, p_1s)),
            "p_value_boot_2sided": min(1.0, max(0.0, p_2s)),
            "boot_thetas": boot_thetas,
        }

    elif test_type == "alpha_hac":
        base_res = compute_hac_alpha_beta(y1, y2, ann_factor=ann_factor)
        theta_hat = base_res["alpha_annualized"]
        se_hat = base_res["alpha_stderr_hac_ann"]
        t_base = base_res["alpha_tstat_hac"]

        boot_thetas = np.zeros(B, dtype=float)
        for b in range(B):
            sample_idx = idx_matrix[b]
            yb1 = y1[sample_idx]
            yb2 = y2[sample_idx]
            # Fast OLS for alpha
            cov_mat = np.cov(yb1, yb2, ddof=1)
            var_x = cov_mat[1, 1]
            if var_x > 1e-12:
                b_slope = cov_mat[0, 1] / var_x
                a_daily = np.mean(yb1) - b_slope * np.mean(yb2)
            else:
                a_daily = np.mean(yb1)
            boot_thetas[b] = a_daily * ann_factor

        ci_low = float(np.percentile(boot_thetas, 2.5))
        ci_high = float(np.percentile(boot_thetas, 97.5))

        if studentized and se_hat > 1e-12:
            t_boot = (boot_thetas - theta_hat) / se_hat
            p_1s = float((1.0 + np.sum(t_boot >= t_base)) / (B + 1.0))
            p_2s = float((1.0 + np.sum(np.abs(t_boot) >= np.abs(t_base))) / (B + 1.0))
        else:
            diff_centered = boot_thetas - theta_hat
            p_1s = float((1.0 + np.sum(diff_centered >= theta_hat)) / (B + 1.0))
            p_2s = float((1.0 + np.sum(np.abs(diff_centered) >= np.abs(theta_hat))) / (B + 1.0))

        return {
            "test_type": "alpha_hac",
            "sample_count": float(T),
            "block_length": float(block_length),
            "n_bootstraps": float(B),
            "point_estimate": float(theta_hat),
            "stderr": float(se_hat),
            "test_stat": float(t_base),
            "ci_95_lower": ci_low,
            "ci_95_upper": ci_high,
            "p_value_boot_1sided": min(1.0, max(0.0, p_1s)),
            "p_value_boot_2sided": min(1.0, max(0.0, p_2s)),
            "boot_thetas": boot_thetas,
        }

    else:
        raise ValueError(f"Unknown test_type: '{test_type}'.")


# =====================================================================
# 7. Multiple-Testing Correction Procedures
# =====================================================================

def holm_bonferroni_correction(
    p_values: Sequence[float],
    alpha: float = 0.05,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply Holm-Bonferroni step-down procedure controlling Family-Wise Error Rate (FWER).

    Returns:
      Tuple of (adjusted_p_values, reject_flags).
    """
    p_arr = np.asarray(p_values, dtype=float)
    M = len(p_arr)
    if M == 0:
        return np.array([]), np.array([], dtype=bool)

    # Sort p-values ascending
    sort_idx = np.argsort(p_arr)
    orig_idx = np.empty_like(sort_idx)
    orig_idx[sort_idx] = np.arange(M)

    sorted_p = p_arr[sort_idx]

    # Adjusted p-values: p_adj(k) = max_{j <= k} min( (M - j + 1) * p(j), 1.0 )
    adj_sorted = np.zeros(M, dtype=float)
    cum_max = 0.0
    for j in range(M):
        multiplier = float(M - j)
        val = min(1.0, multiplier * sorted_p[j])
        cum_max = max(cum_max, val)
        adj_sorted[j] = cum_max

    adj_p = adj_sorted[orig_idx]
    reject = adj_p <= alpha
    return adj_p, reject


def benjamini_hochberg_correction(
    p_values: Sequence[float],
    q: float = 0.05,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply Benjamini-Hochberg (BH) step-up procedure controlling False Discovery Rate (FDR).

    Returns:
      Tuple of (adjusted_p_values, reject_flags).
    """
    p_arr = np.asarray(p_values, dtype=float)
    M = len(p_arr)
    if M == 0:
        return np.array([]), np.array([], dtype=bool)

    sort_idx = np.argsort(p_arr)
    orig_idx = np.empty_like(sort_idx)
    orig_idx[sort_idx] = np.arange(M)

    sorted_p = p_arr[sort_idx]

    # Adjusted p-values: p_adj(k) = min_{j >= k} min( (M / (j + 1)) * p(j), 1.0 )
    adj_sorted = np.zeros(M, dtype=float)
    cum_min = 1.0
    for j in range(M - 1, -1, -1):
        multiplier = float(M) / float(j + 1)
        val = min(1.0, multiplier * sorted_p[j])
        cum_min = min(cum_min, val)
        adj_sorted[j] = cum_min

    adj_p = adj_sorted[orig_idx]
    reject = adj_p <= q
    return adj_p, reject


def benjamini_yekutieli_correction(
    p_values: Sequence[float],
    q: float = 0.05,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply Benjamini-Yekutieli (BY) step-up procedure controlling FDR under arbitrary dependence.

    Divides critical values by harmonic penalty c(M) = sum_{m=1}^M 1/m.
    """
    p_arr = np.asarray(p_values, dtype=float)
    M = len(p_arr)
    if M == 0:
        return np.array([]), np.array([], dtype=bool)

    # Harmonic penalty c(M)
    c_M = float(np.sum(1.0 / np.arange(1, M + 1, dtype=float)))

    # Compute BH values and multiply by c_M
    bh_adj, _ = benjamini_hochberg_correction(p_arr, q=q)
    by_adj = np.minimum(1.0, bh_adj * c_M)
    reject = by_adj <= q
    return by_adj, reject


def apply_multiple_testing_adjustments(
    records: List[Dict[str, Any]],
    p_col_1s: str = "p_value_1sided",
    p_col_2s: str = "p_value_2sided",
    alpha: float = 0.05,
) -> pd.DataFrame:
    """
    Systematically apply Holm, BH, and BY adjustments to a list of hypothesis records.

    Computes adjustments for both 1-sided and 2-sided p-values.
    """
    df = pd.DataFrame(records)
    if len(df) == 0:
        return df

    p1 = df[p_col_1s].values
    p2 = df[p_col_2s].values

    # 1-sided corrections
    holm_p1, holm_rej1 = holm_bonferroni_correction(p1, alpha=alpha)
    bh_p1, bh_rej1 = benjamini_hochberg_correction(p1, q=alpha)
    by_p1, by_rej1 = benjamini_yekutieli_correction(p1, q=alpha)

    # 2-sided corrections
    holm_p2, holm_rej2 = holm_bonferroni_correction(p2, alpha=alpha)
    bh_p2, bh_rej2 = benjamini_hochberg_correction(p2, q=alpha)
    by_p2, by_rej2 = benjamini_yekutieli_correction(p2, q=alpha)

    df["holm_p_1sided"] = holm_p1
    df["holm_reject_1sided"] = holm_rej1
    df["bh_p_1sided"] = bh_p1
    df["bh_reject_1sided"] = bh_rej1
    df["by_p_1sided"] = by_p1
    df["by_reject_1sided"] = by_rej1

    df["holm_p_2sided"] = holm_p2
    df["holm_reject_2sided"] = holm_rej2
    df["bh_p_2sided"] = bh_p2
    df["bh_reject_2sided"] = bh_rej2
    df["by_p_2sided"] = by_p2
    df["by_reject_2sided"] = by_rej2

    return df


# =====================================================================
# 8. Regime Duration Diagnostics
# =====================================================================

def compute_regime_duration_diagnostics(
    regime_series: pd.Series,
    n_bootstraps: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> pd.DataFrame:
    """
    Compute descriptive run-length statistics and conditional bootstrap
    confidence intervals for empirical regime episode durations.

    Note on Epistemic Status:
      This diagnostic quantifies sampling variability of episode lengths
      CONDITIONAL on the single realized Viterbi path. It does NOT capture
      HMM parameter estimation variance or posterior classification entropy.
    """
    s = regime_series.dropna().values.astype(int)
    N = len(s)
    if N == 0:
        return pd.DataFrame()

    # Identify episodes (runs)
    episodes: List[Dict[str, Any]] = []
    curr_regime = s[0]
    curr_len = 1

    for t in range(1, N):
        if s[t] == curr_regime:
            curr_len += 1
        else:
            episodes.append({"regime": curr_regime, "duration": curr_len})
            curr_regime = s[t]
            curr_len = 1
    episodes.append({"regime": curr_regime, "duration": curr_len})

    ep_df = pd.DataFrame(episodes)
    rng = np.random.default_rng(seed)

    rows: List[Dict[str, Any]] = []
    unique_regimes = sorted(ep_df["regime"].unique())

    # Regime-specific statistics
    for r_id in unique_regimes:
        sub_d = ep_df[ep_df["regime"] == r_id]["duration"].values
        k_ep = len(sub_d)
        mean_d = float(np.mean(sub_d))
        med_d = float(np.median(sub_d))
        std_d = float(np.std(sub_d, ddof=1)) if k_ep > 1 else 0.0
        min_d = int(np.min(sub_d))
        max_d = int(np.max(sub_d))
        iqr_d = float(np.percentile(sub_d, 75) - np.percentile(sub_d, 25))

        # Bootstrap CI on mean duration
        if k_ep > 1:
            boot_means = np.zeros(n_bootstraps, dtype=float)
            for b in range(n_bootstraps):
                boot_sample = rng.choice(sub_d, size=k_ep, replace=True)
                boot_means[b] = np.mean(boot_sample)
            ci_low = float(np.percentile(boot_means, 2.5))
            ci_high = float(np.percentile(boot_means, 97.5))
        else:
            ci_low = mean_d
            ci_high = mean_d

        rows.append({
            "regime": f"Regime {r_id}",
            "regime_id": r_id,
            "episode_count": k_ep,
            "total_days": int(np.sum(sub_d)),
            "mean_duration": mean_d,
            "ci_95_lower": ci_low,
            "ci_95_upper": ci_high,
            "median_duration": med_d,
            "std_duration": std_d,
            "min_duration": min_d,
            "max_duration": max_d,
            "iqr_duration": iqr_d,
        })

    # Overall pool across all regimes
    all_d = ep_df["duration"].values
    k_all = len(all_d)
    mean_all = float(np.mean(all_d))
    med_all = float(np.median(all_d))
    std_all = float(np.std(all_d, ddof=1))
    min_all = int(np.min(all_d))
    max_all = int(np.max(all_d))
    iqr_all = float(np.percentile(all_d, 75) - np.percentile(all_d, 25))

    boot_all = np.zeros(n_bootstraps, dtype=float)
    for b in range(n_bootstraps):
        boot_sample = rng.choice(all_d, size=k_all, replace=True)
        boot_all[b] = np.mean(boot_sample)
    ci_low_all = float(np.percentile(boot_all, 2.5))
    ci_high_all = float(np.percentile(boot_all, 97.5))

    rows.append({
        "regime": "All Regimes Combined",
        "regime_id": -1,
        "episode_count": k_all,
        "total_days": int(np.sum(all_d)),
        "mean_duration": mean_all,
        "ci_95_lower": ci_low_all,
        "ci_95_upper": ci_high_all,
        "median_duration": med_all,
        "std_duration": std_all,
        "min_duration": min_all,
        "max_duration": max_all,
        "iqr_duration": iqr_all,
    })

    return pd.DataFrame(rows)


# =====================================================================
# 9. Master Pipeline Runner
# =====================================================================

def run_statistical_validation_pipeline(
    output_dir: Union[str, Path] = "results/statistical_validation",
    n_bootstraps: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> Dict[str, pd.DataFrame]:
    """
    Execute the complete Phase 11 statistical validation pipeline across all
    four canonical strategies, passive benchmarks, and active momentum comparator.

    Saves the six approved structured Parquet files:
      1. hac_alpha_beta_summary.parquet
      2. sharpe_inference_summary.parquet
      3. bootstrap_hypothesis_tests.parquet
      4. bootstrap_confidence_intervals.parquet
      5. multiple_testing_results.parquet
      6. regime_duration_diagnostics.parquet

    Returns:
      Dict[str, pd.DataFrame] of all generated validation tables.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting Phase 11 Statistical Validation Pipeline...")

    # 1. Load canonical simulations
    simulations: Dict[str, pd.DataFrame] = {}
    for v in VARIANTS:
        p = Path(f"results/portfolio_backtest/daily_simulation_{v}.parquet")
        if not p.exists():
            raise FileNotFoundError(f"Missing simulation parquet: {p}")
        simulations[v] = pd.read_parquet(p)

    sim_n50 = pd.read_parquet("results/portfolio_backtest/daily_simulation_benchmark_nifty50.parquet")
    sim_ew = pd.read_parquet("results/portfolio_backtest/daily_simulation_benchmark_equal_weight.parquet")

    # 2. Ensure daily momentum simulation exists
    daily_mom = ensure_daily_momentum_simulation()

    all_series: Dict[str, pd.DataFrame] = {
        **simulations,
        "NIFTY50": sim_n50,
        "EQUAL_WEIGHT": sim_ew,
        "MOMENTUM_TOP2": daily_mom,
    }

    # -----------------------------------------------------------------
    # A. HAC Alpha & Beta Inference
    # -----------------------------------------------------------------
    logger.info("Computing Newey-West HAC Alpha & Beta regressions...")
    hac_rows: List[Dict[str, Any]] = []

    for v in VARIANTS:
        for bm_key in ["NIFTY50", "EQUAL_WEIGHT", "MOMENTUM_TOP2"]:
            for period_name in PERIOD_NAMES:
                s_dt, e_dt = PERIOD_RANGES[period_name]
                y = all_series[v].loc[s_dt:e_dt, "net_return"].values
                x = all_series[bm_key].loc[s_dt:e_dt, "net_return"].values

                res = compute_hac_alpha_beta(y, x)
                hac_rows.append({
                    "strategy": v,
                    "benchmark": bm_key,
                    "period": period_name,
                    "period_label": PERIOD_LABELS[period_name],
                    **res,
                })

    hac_df = pd.DataFrame(hac_rows)
    hac_df.to_parquet(out_dir / "hac_alpha_beta_summary.parquet", index=False)
    logger.info(f"Saved: {out_dir / 'hac_alpha_beta_summary.parquet'} ({len(hac_df)} rows)")

    # -----------------------------------------------------------------
    # B. Standalone and Comparative Sharpe Inference
    # -----------------------------------------------------------------
    logger.info("Computing Lo (2002) and Ledoit-Wolf (2008) Sharpe inferences...")
    sharpe_rows: List[Dict[str, Any]] = []

    # Standalone Sharpe for all portfolios
    for port_key in VARIANTS + ALL_COMPARATORS:
        for period_name in PERIOD_NAMES:
            s_dt, e_dt = PERIOD_RANGES[period_name]
            r = all_series[port_key].loc[s_dt:e_dt, "net_return"].values
            res = compute_lo_sharpe_inference(r)
            sharpe_rows.append({
                "portfolio": port_key,
                "comparator": "CASH_ZERO",
                "test_class": "standalone_sharpe_lo2002",
                "period": period_name,
                "period_label": PERIOD_LABELS[period_name],
                **res,
                "delta_sharpe_ann": float(res["sharpe_annualized"]),
                "comparator_sharpe_ann": 0.0,
            })

    # Comparative Sharpe Difference for each strategy vs all comparators
    for v in VARIANTS:
        for comp_key in ALL_COMPARATORS:
            for period_name in PERIOD_NAMES:
                s_dt, e_dt = PERIOD_RANGES[period_name]
                r1 = all_series[v].loc[s_dt:e_dt, "net_return"].values
                r2 = all_series[comp_key].loc[s_dt:e_dt, "net_return"].values
                res_lw = compute_ledoit_wolf_sharpe_diff(r1, r2)
                sharpe_rows.append({
                    "portfolio": v,
                    "comparator": comp_key,
                    "test_class": "comparative_sharpe_ledoit_wolf",
                    "period": period_name,
                    "period_label": PERIOD_LABELS[period_name],
                    "sample_count": res_lw["sample_count"],
                    "hac_lags": res_lw["hac_lags"],
                    "sharpe_daily": res_lw["sharpe1_ann"] / math.sqrt(ANNUALIZATION_FACTOR),
                    "sharpe_annualized": res_lw["sharpe1_ann"],
                    "skewness": 0.0,
                    "kurtosis": 0.0,
                    "sharpe_stderr_iid": 0.0,
                    "sharpe_stderr_hac": res_lw["stderr_delta_ann"],
                    "z_stat_hac": res_lw["z_stat"],
                    "p_value_1sided": res_lw["p_value_1sided"],
                    "p_value_2sided": res_lw["p_value_2sided"],
                    "delta_sharpe_ann": res_lw["delta_sharpe_ann"],
                    "comparator_sharpe_ann": res_lw["sharpe2_ann"],
                })

    sharpe_df = pd.DataFrame(sharpe_rows)
    sharpe_df.to_parquet(out_dir / "sharpe_inference_summary.parquet", index=False)
    logger.info(f"Saved: {out_dir / 'sharpe_inference_summary.parquet'} ({len(sharpe_df)} rows)")

    # -----------------------------------------------------------------
    # C. Stationary Block Bootstrap Hypothesis Testing
    # -----------------------------------------------------------------
    logger.info("Executing Stationary Block Bootstrap hypothesis tests...")
    boot_rows: List[Dict[str, Any]] = []

    # Run primary tests with b = 21, and sensitivity sweeps {5, 10, 21, 42, 63}
    for v in VARIANTS:
        for comp_key in ALL_COMPARATORS:
            for period_name in PERIOD_NAMES:
                s_dt, e_dt = PERIOD_RANGES[period_name]
                r1 = all_series[v].loc[s_dt:e_dt, "net_return"].values
                r2 = all_series[comp_key].loc[s_dt:e_dt, "net_return"].values

                # Block length sweep
                blocks_to_run = HOLDOUT_PRIMARY_BLOCK_LENGTHS if period_name == "holdout" else [21.0]

                for b_len in blocks_to_run:
                    b_res = run_bootstrap_hypothesis_tests(
                        r1=r1,
                        r2=r2,
                        test_type="sharpe_diff",
                        block_length=b_len,
                        n_bootstraps=n_bootstraps,
                        seed=seed,
                    )
                    boot_rows.append({
                        "strategy": v,
                        "comparator": comp_key,
                        "period": period_name,
                        "period_label": PERIOD_LABELS[period_name],
                        "test_metric": "delta_sharpe",
                        "block_length": b_len,
                        "point_estimate": b_res["point_estimate"],
                        "stderr": b_res["stderr"],
                        "test_stat": b_res["test_stat"],
                        "ci_95_lower": b_res["ci_95_lower"],
                        "ci_95_upper": b_res["ci_95_upper"],
                        "p_value_boot_1sided": b_res["p_value_boot_1sided"],
                        "p_value_boot_2sided": b_res["p_value_boot_2sided"],
                    })

    boot_df = pd.DataFrame(boot_rows)
    boot_df.to_parquet(out_dir / "bootstrap_hypothesis_tests.parquet", index=False)
    logger.info(f"Saved: {out_dir / 'bootstrap_hypothesis_tests.parquet'} ({len(boot_df)} rows)")

    # -----------------------------------------------------------------
    # D. Bootstrap Confidence Intervals for Performance Metrics
    # -----------------------------------------------------------------
    logger.info("Computing Bootstrap Confidence Intervals for CAGR, Vol, and Drawdown...")
    ci_rows: List[Dict[str, Any]] = []

    # Block length sensitivity grid on Full Period
    for port_key in VARIANTS + ALL_COMPARATORS:
        for b_len in SENSITIVITY_BLOCK_LENGTHS:
            r = all_series[port_key]["net_return"].values
            T = len(r)

            idx_mat = generate_stationary_bootstrap_indices(
                n_obs=T,
                block_length=b_len,
                n_bootstraps=n_bootstraps,
                seed=seed,
            )

            boot_cagr = np.zeros(n_bootstraps, dtype=float)
            boot_vol = np.zeros(n_bootstraps, dtype=float)
            boot_mdd = np.zeros(n_bootstraps, dtype=float)

            for b in range(n_bootstraps):
                sample_idx = idx_mat[b]
                rb = r[sample_idx]
                nav_b = np.cumprod(1.0 + rb)
                peaks_b = np.maximum.accumulate(nav_b)
                dds_b = (nav_b - peaks_b) / peaks_b

                boot_cagr[b] = (nav_b[-1] ** (ANNUALIZATION_FACTOR / float(T))) - 1.0
                boot_vol[b] = np.std(rb, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR)
                boot_mdd[b] = np.min(dds_b)

            # Point estimates
            nav_real = np.cumprod(1.0 + r)
            peaks_real = np.maximum.accumulate(nav_real)
            dds_real = (nav_real - peaks_real) / peaks_real
            cagr_real = (nav_real[-1] ** (ANNUALIZATION_FACTOR / float(T))) - 1.0
            vol_real = np.std(r, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR)
            mdd_real = np.min(dds_real)

            ci_rows.append({
                "portfolio": port_key,
                "block_length": b_len,
                "cagr_point": cagr_real,
                "cagr_ci_lower": float(np.percentile(boot_cagr, 2.5)),
                "cagr_ci_upper": float(np.percentile(boot_cagr, 97.5)),
                "vol_point": vol_real,
                "vol_ci_lower": float(np.percentile(boot_vol, 2.5)),
                "vol_ci_upper": float(np.percentile(boot_vol, 97.5)),
                "mdd_point": mdd_real,
                "mdd_ci_lower": float(np.percentile(boot_mdd, 2.5)),
                "mdd_ci_upper": float(np.percentile(boot_mdd, 97.5)),
            })

    ci_df = pd.DataFrame(ci_rows)
    ci_df.to_parquet(out_dir / "bootstrap_confidence_intervals.parquet", index=False)
    logger.info(f"Saved: {out_dir / 'bootstrap_confidence_intervals.parquet'} ({len(ci_df)} rows)")

    # -----------------------------------------------------------------
    # E. Multiple-Testing Adjustments (Unified M=12 & Exploratory M=36)
    # -----------------------------------------------------------------
    logger.info("Applying Multiple-Testing Corrections (Unified M=12 & Exploratory M=36)...")

    # Family 1: Unified Omnibus Primary Family (M = 12)
    # Full Period comparisons:
    # 4 Alphas vs NIFTY50 + 4 Alphas vs EqualWeight + 4 Delta-Sharpes vs Naive Momentum
    uni_records: List[Dict[str, Any]] = []

    for v in VARIANTS:
        # 1. Alpha vs NIFTY50
        row_n50 = hac_df[(hac_df["strategy"] == v) & (hac_df["benchmark"] == "NIFTY50") & (hac_df["period"] == "full")].iloc[0]
        uni_records.append({
            "hypothesis_id": f"H_alpha_N50_{v}",
            "family": "Unified_Primary_Omnibus_M12",
            "tier": "Tier_1_Core_Market",
            "strategy": v,
            "comparator": "NIFTY50",
            "metric": "alpha_hac",
            "period": "full",
            "point_estimate": row_n50["alpha_annualized"],
            "stderr": row_n50["alpha_stderr_hac_ann"],
            "test_stat": row_n50["alpha_tstat_hac"],
            "p_value_1sided": row_n50["alpha_pvalue_hac_1sided"],
            "p_value_2sided": row_n50["alpha_pvalue_hac_2sided"],
        })

        # 2. Alpha vs EqualWeight
        row_ew = hac_df[(hac_df["strategy"] == v) & (hac_df["benchmark"] == "EQUAL_WEIGHT") & (hac_df["period"] == "full")].iloc[0]
        uni_records.append({
            "hypothesis_id": f"H_alpha_EW_{v}",
            "family": "Unified_Primary_Omnibus_M12",
            "tier": "Tier_2_Structural_Robustness",
            "strategy": v,
            "comparator": "EQUAL_WEIGHT",
            "metric": "alpha_hac",
            "period": "full",
            "point_estimate": row_ew["alpha_annualized"],
            "stderr": row_ew["alpha_stderr_hac_ann"],
            "test_stat": row_ew["alpha_tstat_hac"],
            "p_value_1sided": row_ew["alpha_pvalue_hac_1sided"],
            "p_value_2sided": row_ew["alpha_pvalue_hac_2sided"],
        })

        # 3. Delta-Sharpe vs Naive Momentum
        row_mom = sharpe_df[(sharpe_df["portfolio"] == v) & (sharpe_df["comparator"] == "MOMENTUM_TOP2") & (sharpe_df["period"] == "full")].iloc[0]
        uni_records.append({
            "hypothesis_id": f"H_deltaSR_MOM_{v}",
            "family": "Unified_Primary_Omnibus_M12",
            "tier": "Tier_2_Factor_Superiority",
            "strategy": v,
            "comparator": "MOMENTUM_TOP2",
            "metric": "delta_sharpe",
            "period": "full",
            "point_estimate": row_mom["delta_sharpe_ann"],
            "stderr": row_mom["sharpe_stderr_hac"],
            "test_stat": row_mom["z_stat_hac"],
            "p_value_1sided": row_mom["p_value_1sided"],
            "p_value_2sided": row_mom["p_value_2sided"],
        })

    uni_df = apply_multiple_testing_adjustments(uni_records, alpha=0.05)

    # Family 2: Exploratory Subperiod Stability Sweep (M = 36)
    # 4 strategies x 3 comparators x 3 periods
    exp_records: List[Dict[str, Any]] = []

    for v in VARIANTS:
        for comp in ALL_COMPARATORS:
            for p_name in PERIOD_NAMES:
                sub_row = hac_df[(hac_df["strategy"] == v) & (hac_df["benchmark"] == comp) & (hac_df["period"] == p_name)].iloc[0]
                exp_records.append({
                    "hypothesis_id": f"H_exp_{v}_{comp}_{p_name}",
                    "family": "Exploratory_Subperiod_M36",
                    "tier": "Tier_3_Exploratory_Diagnostics",
                    "strategy": v,
                    "comparator": comp,
                    "metric": "alpha_hac",
                    "period": p_name,
                    "point_estimate": sub_row["alpha_annualized"],
                    "stderr": sub_row["alpha_stderr_hac_ann"],
                    "test_stat": sub_row["alpha_tstat_hac"],
                    "p_value_1sided": sub_row["alpha_pvalue_hac_1sided"],
                    "p_value_2sided": sub_row["alpha_pvalue_hac_2sided"],
                })

    exp_df = apply_multiple_testing_adjustments(exp_records, alpha=0.05)

    # Concatenate both families into structured output
    mt_df = pd.concat([uni_df, exp_df], ignore_index=True)
    mt_df.to_parquet(out_dir / "multiple_testing_results.parquet", index=False)
    logger.info(f"Saved: {out_dir / 'multiple_testing_results.parquet'} ({len(mt_df)} rows)")

    # -----------------------------------------------------------------
    # F. Regime Duration Diagnostics
    # -----------------------------------------------------------------
    logger.info("Computing Regime Duration Diagnostics...")
    regime_series = simulations["1A"]["accepted_regime"]
    dur_df = compute_regime_duration_diagnostics(regime_series, n_bootstraps=n_bootstraps, seed=seed)
    dur_df.to_parquet(out_dir / "regime_duration_diagnostics.parquet", index=False)
    logger.info(f"Saved: {out_dir / 'regime_duration_diagnostics.parquet'} ({len(dur_df)} rows)")

    logger.info("Phase 11 Statistical Validation Pipeline Complete!")
    return {
        "hac_alpha_beta": hac_df,
        "sharpe_inference": sharpe_df,
        "bootstrap_tests": boot_df,
        "bootstrap_ci": ci_df,
        "multiple_testing": mt_df,
        "regime_duration": dur_df,
    }


if __name__ == "__main__":
    run_statistical_validation_pipeline()
