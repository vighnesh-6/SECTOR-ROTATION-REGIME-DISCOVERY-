"""
Comprehensive Unit and Integration Test Suite for Phase 11 Statistical Validation.

Validates:
  1. Deterministic Naive Top-2 Momentum comparator reproduction against frozen baseline.
  2. Heteroskedasticity and Autocorrelation Consistent (HAC) Alpha and Beta inference.
  3. Andrew Lo (2002) HAC asymptotic Sharpe inference.
  4. Ledoit and Wolf (2008) paired Sharpe difference test, analytical gradients, and exact symmetry.
  5. Politis and Romano (1994) Stationary Block Bootstrap generator, block lengths, and empirical p-values.
  6. Multiple-testing error control procedures (Holm-Bonferroni, Benjamini-Hochberg, Benjamini-Yekutieli).
  7. Regime episode run-length extraction and conditional duration bootstrap.
  8. Edge cases, zero variance, short samples, and input validation guards.
"""

import math
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
import pytest

from src.statistical_validation import (
    ANNUALIZATION_FACTOR,
    PERIOD_COUNTS,
    apply_multiple_testing_adjustments,
    bartlett_weights,
    benjamini_hochberg_correction,
    benjamini_yekutieli_correction,
    compute_automatic_hac_bandwidth,
    compute_hac_alpha_beta,
    compute_ledoit_wolf_sharpe_diff,
    compute_lo_sharpe_inference,
    compute_regime_duration_diagnostics,
    ensure_daily_momentum_simulation,
    generate_stationary_bootstrap_indices,
    holm_bonferroni_correction,
    run_bootstrap_hypothesis_tests,
)


# =====================================================================
# 1. Momentum Comparator Reproduction Tests
# =====================================================================

def test_ensure_daily_momentum_simulation_reproduction():
    """Verify deterministic reproduction of Naive Momentum daily simulation."""
    daily_mom = ensure_daily_momentum_simulation()

    # Shape and period validation
    assert len(daily_mom) == PERIOD_COUNTS["full"]
    assert int((daily_mom["period"] == "train").sum()) == PERIOD_COUNTS["train"]
    assert int((daily_mom["period"] == "holdout").sum()) == PERIOD_COUNTS["holdout"]
    assert "net_return" in daily_mom.columns
    assert "net_nav" in daily_mom.columns

    # Verify against frozen Phase 10.6 baseline table
    frozen_path = Path("results/portfolio_backtest/robustness/benchmark/momentum_benchmark_comparison.parquet")
    assert frozen_path.exists(), "Frozen momentum comparison parquet missing."

    frozen_df = pd.read_parquet(frozen_path)
    base_rows = frozen_df[frozen_df["comparator_type"] == "benchmark_baseline"]

    for _, row in base_rows.iterrows():
        p_name = row["period"]
        sub = daily_mom if p_name == "full" else daily_mom[daily_mom["period"] == p_name]
        N = len(sub)

        # CAGR
        nav_end = float(sub["net_nav"].iloc[-1])
        if p_name == "train":
            nav_start = 1.0
        elif p_name == "holdout":
            tr_sub = daily_mom[daily_mom["period"] == "train"]
            nav_start = float(tr_sub["net_nav"].iloc[-1])
        else:
            nav_start = 1.0

        cagr = (nav_end / nav_start) ** (ANNUALIZATION_FACTOR / float(N)) - 1.0
        r_arr = sub["net_return"].values.astype(float)
        vol = float(np.std(r_arr, ddof=1) * np.sqrt(ANNUALIZATION_FACTOR))
        sharpe = float((np.mean(r_arr) * ANNUALIZATION_FACTOR) / vol)

        assert abs(cagr - row["net_cagr"]) < 1e-4, f"CAGR mismatch in {p_name}"
        assert abs(vol - row["annualized_vol"]) < 1e-4, f"Vol mismatch in {p_name}"
        assert abs(sharpe - row["sharpe_ratio"]) < 1e-4, f"Sharpe mismatch in {p_name}"


# =====================================================================
# 2. HAC Bandwidth and Alpha-Beta Regression Tests
# =====================================================================

def test_automatic_hac_bandwidth():
    """Verify automatic Bartlett bandwidth for Phase 11 sample counts."""
    assert compute_automatic_hac_bandwidth(1686) == 7
    assert compute_automatic_hac_bandwidth(1264) == 7
    assert compute_automatic_hac_bandwidth(422) == 5
    assert compute_automatic_hac_bandwidth(100) == 4
    assert compute_automatic_hac_bandwidth(2) == 0


def test_bartlett_weights_properties():
    """Verify mathematical properties of Bartlett kernel weights."""
    L = 7
    w = bartlett_weights(L)
    assert len(w) == 7
    # Strictly decreasing
    assert np.all(np.diff(w) < 0)
    # First weight: 1 - 1/8 = 7/8 = 0.875
    assert math.isclose(w[0], 7.0 / 8.0, rel_tol=1e-9)
    # Last weight: 1 - 7/8 = 1/8 = 0.125 > 0
    assert math.isclose(w[-1], 1.0 / 8.0, rel_tol=1e-9)
    assert np.all(w > 0.0)


def test_hac_alpha_beta_reference_values():
    """Verify HAC Alpha & Beta against Phase 10.5 analytical validation table."""
    sim_1a = pd.read_parquet("results/portfolio_backtest/daily_simulation_1A.parquet")
    sim_n50 = pd.read_parquet("results/portfolio_backtest/daily_simulation_benchmark_nifty50.parquet")

    y = sim_1a["net_return"].values
    x = sim_n50["net_return"].values

    res = compute_hac_alpha_beta(y, x)

    # Reference values from Phase 10.5 Section 3.2:
    # 1A vs NIFTY 50: Beta = 0.8194, Ann. Alpha = +16.13%, Alpha SE (HAC) = 5.23%, Alpha t = +3.082, Alpha p = 0.0021
    assert abs(res["beta"] - 0.8194) < 0.01
    assert abs(res["alpha_annualized_pct"] - 16.13) < 0.20
    assert abs(res["alpha_stderr_hac_ann"] * 100.0 - 5.23) < 0.20
    assert abs(res["alpha_tstat_hac"] - 3.082) < 0.15
    assert res["alpha_pvalue_hac_2sided"] < 0.01
    assert res["alpha_pvalue_hac_1sided"] < 0.005
    assert res["r_squared"] > 0.50


# =====================================================================
# 3. Lo (2002) Sharpe Inference Tests
# =====================================================================

def test_lo_sharpe_inference_properties():
    """Verify Lo (2002) Sharpe inference on simulated and canonical data."""
    # 1. Pure IID Gaussian returns
    rng = np.random.default_rng(123)
    r_iid = rng.normal(0.001, 0.01, size=1000)
    res_iid = compute_lo_sharpe_inference(r_iid)

    assert res_iid["sample_count"] == 1000
    assert res_iid["sharpe_annualized"] > 0
    assert res_iid["sharpe_stderr_hac"] > 0
    assert res_iid["p_value_1sided"] < res_iid["p_value_2sided"]
    assert math.isclose(res_iid["p_value_2sided"], 2.0 * res_iid["p_value_1sided"], rel_tol=1e-5)

    # 2. Canonical Strategy 1A full period
    sim_1a = pd.read_parquet("results/portfolio_backtest/daily_simulation_1A.parquet")
    res_1a = compute_lo_sharpe_inference(sim_1a["net_return"].values)

    # Sharpe ~ 1.328, z_stat ~ 3.26, p < 0.001
    assert abs(res_1a["sharpe_annualized"] - 1.328) < 0.05
    assert res_1a["z_stat_hac"] > 3.0
    assert res_1a["p_value_1sided"] < 0.001


# =====================================================================
# 4. Ledoit-Wolf (2008) Sharpe Difference Tests
# =====================================================================

def test_ledoit_wolf_sharpe_diff_symmetry_and_stability():
    """Verify exact anti-symmetry and numerical properties of Ledoit-Wolf test."""
    sim_1a = pd.read_parquet("results/portfolio_backtest/daily_simulation_1A.parquet")
    sim_n50 = pd.read_parquet("results/portfolio_backtest/daily_simulation_benchmark_nifty50.parquet")

    y1 = sim_1a["net_return"].values
    y2 = sim_n50["net_return"].values

    res_12 = compute_ledoit_wolf_sharpe_diff(y1, y2)
    res_21 = compute_ledoit_wolf_sharpe_diff(y2, y1)

    # Exact anti-symmetry
    assert math.isclose(res_12["delta_sharpe_ann"], -res_21["delta_sharpe_ann"], abs_tol=1e-12)
    assert math.isclose(res_12["stderr_delta_ann"], res_21["stderr_delta_ann"], abs_tol=1e-12)
    assert math.isclose(res_12["z_stat"], -res_21["z_stat"], abs_tol=1e-10)

    # Strategy 1A beats NIFTY 50 by ~0.67 Sharpe (statistically significant)
    assert res_12["delta_sharpe_ann"] > 0.50
    assert res_12["z_stat"] > 2.0
    assert res_12["p_value_1sided"] < 0.01

    # Identity test (y1 vs y1)
    res_ident = compute_ledoit_wolf_sharpe_diff(y1, y1)
    assert math.isclose(res_ident["delta_sharpe_ann"], 0.0, abs_tol=1e-12)
    assert math.isclose(res_ident["z_stat"], 0.0, abs_tol=1e-10)


# =====================================================================
# 5. Stationary Block Bootstrap Tests
# =====================================================================

def test_stationary_bootstrap_index_generator():
    """Verify index validity, bounds, and geometric distribution of block bootstrap."""
    N = 500
    B = 200
    b_len = 10.0
    indices = generate_stationary_bootstrap_indices(n_obs=N, block_length=b_len, n_bootstraps=B, seed=42)

    assert indices.shape == (B, N)
    assert np.all(indices >= 0)
    assert np.all(indices < N)

    # Determinism with same seed
    indices_clone = generate_stationary_bootstrap_indices(n_obs=N, block_length=b_len, n_bootstraps=B, seed=42)
    np.testing.assert_array_equal(indices, indices_clone)

    # Empirical mean block length verification
    # Count transitions where index[t] != (index[t-1] + 1) % N
    is_break = indices[:, 1:] != (indices[:, :-1] + 1) % N
    p_hat = np.mean(is_break)
    expected_p = 1.0 / b_len
    # p_hat should be within 10% of expected_p for B=200, N=500
    assert abs(p_hat - expected_p) < 0.03


def test_run_bootstrap_hypothesis_tests():
    """Verify bootstrap hypothesis testing and empirical p-values."""
    rng = np.random.default_rng(99)
    r1 = rng.normal(0.001, 0.01, size=300)
    r2 = rng.normal(0.000, 0.01, size=300)

    res = run_bootstrap_hypothesis_tests(
        r1=r1,
        r2=r2,
        test_type="sharpe_diff",
        block_length=10.0,
        n_bootstraps=500,
        seed=42,
    )

    assert 0.0 <= res["p_value_boot_1sided"] <= 1.0
    assert 0.0 <= res["p_value_boot_2sided"] <= 1.0
    assert res["ci_95_lower"] < res["ci_95_upper"]
    assert res["ci_95_lower"] <= res["point_estimate"] <= res["ci_95_upper"]


# =====================================================================
# 6. Multiple-Testing Corrections Tests
# =====================================================================

def test_multiple_testing_corrections():
    """Verify Holm, BH, and BY adjustments on known test vectors."""
    p_vals = [0.001, 0.010, 0.040, 0.120]

    # Holm-Bonferroni
    holm_p, holm_rej = holm_bonferroni_correction(p_vals, alpha=0.05)
    # p1: 0.001 * 4 = 0.004 <= 0.05 (Reject)
    # p2: 0.010 * 3 = 0.030 <= 0.05 (Reject)
    # p3: 0.040 * 2 = 0.080 > 0.05 (Fail to reject)
    # p4: 0.120 * 1 = 0.120 > 0.05 (Fail to reject)
    assert math.isclose(holm_p[0], 0.004, abs_tol=1e-6)
    assert math.isclose(holm_p[1], 0.030, abs_tol=1e-6)
    assert math.isclose(holm_p[2], 0.080, abs_tol=1e-6)
    assert math.isclose(holm_p[3], 0.120, abs_tol=1e-6)
    assert list(holm_rej) == [True, True, False, False]

    # Benjamini-Hochberg (BH)
    bh_p, bh_rej = benjamini_hochberg_correction(p_vals, q=0.05)
    # All adjusted p-values <= raw / (rank / M)
    assert np.all(bh_p >= p_vals)
    assert np.all(bh_p <= 1.0)
    # Monotonicity check
    assert np.all(np.diff(bh_p) >= -1e-12)

    # Benjamini-Yekutieli (BY)
    by_p, by_rej = benjamini_yekutieli_correction(p_vals, q=0.05)
    c_M = 1.0 + 1.0/2.0 + 1.0/3.0 + 1.0/4.0  # 2.08333
    assert math.isclose(by_p[0], min(1.0, bh_p[0] * c_M), rel_tol=1e-5)
    # BY is always at least as conservative as BH
    assert np.all(by_p >= bh_p)


def test_multiple_testing_record_applicator():
    """Verify application of corrections to tabular hypothesis records."""
    records = [
        {"hypothesis_id": "H1", "p_value_1sided": 0.002, "p_value_2sided": 0.004},
        {"hypothesis_id": "H2", "p_value_1sided": 0.015, "p_value_2sided": 0.030},
        {"hypothesis_id": "H3", "p_value_1sided": 0.045, "p_value_2sided": 0.090},
    ]

    df = apply_multiple_testing_adjustments(records, alpha=0.05)
    assert len(df) == 3
    assert "holm_p_1sided" in df.columns
    assert "bh_p_1sided" in df.columns
    assert "by_p_1sided" in df.columns
    assert "holm_reject_1sided" in df.columns


# =====================================================================
# 7. Regime Duration Diagnostics Tests
# =====================================================================

def test_regime_duration_diagnostics():
    """Verify run-length calculation on synthetic and canonical regimes."""
    # Synthetic: 3 days of 0, 2 days of 1, 4 days of 0 -> episodes: 0(3), 1(2), 0(4)
    s = pd.Series([0, 0, 0, 1, 1, 0, 0, 0, 0])
    df_dur = compute_regime_duration_diagnostics(s, n_bootstraps=100, seed=42)

    assert len(df_dur) == 3  # Regime 0, Regime 1, All Regimes Combined
    r0 = df_dur[df_dur["regime_id"] == 0].iloc[0]
    assert r0["episode_count"] == 2
    assert r0["total_days"] == 7
    assert math.isclose(r0["mean_duration"], 3.5)
    assert r0["min_duration"] == 3
    assert r0["max_duration"] == 4

    r_all = df_dur[df_dur["regime_id"] == -1].iloc[0]
    assert r_all["episode_count"] == 3
    assert r_all["total_days"] == 9


# =====================================================================
# 8. Edge Cases and Input Validation Guards
# =====================================================================

def test_input_validation_and_edge_cases():
    """Verify robust error handling for mismatched lengths, zero variance, and short samples."""
    # 1. Length mismatch
    with pytest.raises(ValueError, match="Length mismatch"):
        compute_hac_alpha_beta(np.array([1, 2, 3]), np.array([1, 2]))

    with pytest.raises(ValueError, match="Length mismatch"):
        compute_ledoit_wolf_sharpe_diff(np.array([1, 2, 3]), np.array([1, 2]))

    # 2. Too short sample
    with pytest.raises(ValueError, match="at least 4 observations"):
        compute_hac_alpha_beta(np.array([1, 2]), np.array([1, 2]))

    with pytest.raises(ValueError, match="at least 4 observations"):
        compute_lo_sharpe_inference(np.array([1, 2, 3]))

    # 3. Constant return (zero variance)
    r_const = np.ones(50) * 0.01
    res_lo = compute_lo_sharpe_inference(r_const)
    assert res_lo["sharpe_annualized"] == 0.0
    assert res_lo["p_value_1sided"] == 1.0

    # 4. Empty multiple-testing input
    empty_df = apply_multiple_testing_adjustments([])
    assert len(empty_df) == 0

