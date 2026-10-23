"""
tests/test_regime_discovery.py
==============================
Focused verification tests for Phase 6 Regime Discovery:
1. HMM per-observation log-likelihood normalization.
2. HMM seed-score standard deviation using normalized scores.
3. K-Means rejection of candidate K with incomplete valid-fold coverage.
4. Preservation of chronological split and holdout isolation.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List

from src.regime_discovery import (
    FOLDS,
    TRAIN_POOL_END,
    HOLDOUT_START,
    get_clean_splits,
    generate_folds,
    fit_scale_fold,
    fit_scale_full,
    select_kmeans_k,
    select_gmm_cov_type,
    select_gmm_covariance,
    run_gmm_cv,
    select_gmm_k,
    fit_final_gmm,
    GMM_COVARIANCE_TYPES,
    _fit_hmm_multi_seed,
    run_hmm_cv,
    fit_final_hmm,
    evaluate_holdout,
)


# ===========================================================================
# 1. HMM per-observation likelihood normalization
# ===========================================================================

def test_hmm_per_observation_normalization_multi_seed():
    """Verify that _fit_hmm_multi_seed records both total and per-observation LL,
    and that train_ll_per_obs == total_train_ll / T."""
    np.random.seed(42)
    T = 60
    D = 4
    X = np.random.randn(T, D)

    best_model, seed_recs = _fit_hmm_multi_seed(
        X, k=2, covariance_type="diag", n_iter=20, seeds=[0, 1]
    )

    assert len(seed_recs) == 2
    for rec in seed_recs:
        if rec["converged"]:
            total_ll = rec.get("total_train_ll") or rec.get("train_ll_total")
            per_obs_ll = rec["train_ll_per_obs"]
            assert total_ll is not None, "total_train_ll must be preserved for auditing"
            assert np.isclose(per_obs_ll, total_ll / T, rtol=1e-5), (
                f"Expected per_obs_ll {per_obs_ll} to equal total_ll/T {total_ll / T}"
            )


def test_hmm_cv_normalization():
    """Verify that run_hmm_cv calculates val_ll_per_obs as val_ll_total / n_val
    and best_train_ll_per_obs as best_train_ll_total / n_train."""
    np.random.seed(42)
    # Create 3 synthetic folds
    synthetic_folds = []
    dates_train = pd.date_range("2020-01-01", periods=80, freq="B")
    dates_val = pd.date_range("2020-05-01", periods=30, freq="B")
    for fid in ["F1", "F2", "F3"]:
        synthetic_folds.append({
            "fold_id": fid,
            "X_train": pd.DataFrame(np.random.randn(80, 3), index=dates_train),
            "X_val": pd.DataFrame(np.random.randn(30, 3), index=dates_val),
            "n_train": 80,
            "n_val": 30,
        })

    cv_df = run_hmm_cv(
        synthetic_folds,
        scaler_type="robust",
        candidate_k=[2],
        covariance_type="diag",
        n_iter=20,
        seeds=[0, 1],
    )

    assert not cv_df.empty
    row = cv_df.iloc[0]
    assert "val_ll_per_obs" in row
    assert "val_ll_total" in row, "val_ll_total should be preserved for auditing"
    assert np.isclose(row["val_ll_per_obs"], row["val_ll_total"] / row["n_val"], rtol=1e-5)

    assert "best_train_ll_per_obs" in row
    assert "best_train_ll_total" in row, "best_train_ll_total should be preserved for auditing"
    assert np.isclose(row["best_train_ll_per_obs"], row["best_train_ll_total"] / row["n_train"], rtol=1e-5)


def test_hmm_evaluate_holdout_normalization():
    """Verify that evaluate_holdout calculates HMM ll_per_obs as total_ll / n_holdout."""
    np.random.seed(42)
    T_tr, T_ho, D = 100, 40, 3
    X_tr = pd.DataFrame(np.random.randn(T_tr, D))
    X_ho = pd.DataFrame(
        np.random.randn(T_ho, D),
        index=pd.date_range("2025-01-01", periods=T_ho, freq="B"),
    )

    X_tr_sc, scaler = fit_scale_full(X_tr, scaler_type="robust")
    model, _ = fit_final_hmm(X_tr_sc, k=2, covariance_type="diag", n_iter=20, seeds=[0])

    ho_res = evaluate_holdout("hmm", model, scaler, X_ho, k=2, scaler_type="robust")

    assert "ll_per_obs" in ho_res
    assert "total_ll" in ho_res, "total_ll should be preserved in evaluate_holdout"
    assert np.isclose(ho_res["ll_per_obs"], ho_res["total_ll"] / T_ho, rtol=1e-5)


# ===========================================================================
# 2. HMM seed-score standard deviation using normalized scores
# ===========================================================================

def test_hmm_seed_std_uses_normalized_scores():
    """Verify that train_ll_std is computed from normalized per-observation scores,
    not raw total scores."""
    np.random.seed(42)
    T = 100
    D = 4
    X_train = np.random.randn(T, D)

    # Use fit_final_hmm with seeds [0, 1, 2]
    model, diag = fit_final_hmm(
        X_train, k=2, covariance_type="diag", n_iter=20, seeds=[0, 1, 2]
    )

    _, seed_recs = _fit_hmm_multi_seed(
        X_train, k=2, covariance_type="diag", n_iter=20, seeds=[0, 1, 2]
    )

    converged_per_obs = [
        r["train_ll_per_obs"] for r in seed_recs if r["converged"] and not np.isnan(r["train_ll_per_obs"])
    ]
    converged_total = [
        (r.get("total_train_ll") or r.get("train_ll_total"))
        for r in seed_recs if r["converged"] and not np.isnan(r.get("total_train_ll", np.nan))
    ]

    expected_norm_std = float(np.std(converged_per_obs))
    expected_total_std = float(np.std(converged_total))

    assert np.isclose(diag["train_ll_std"], expected_norm_std, rtol=1e-5), (
        f"diag['train_ll_std'] ({diag['train_ll_std']}) should match normalized std ({expected_norm_std})"
    )
    if expected_total_std > 1e-4:
        assert not np.isclose(diag["train_ll_std"], expected_total_std, rtol=1e-2), (
            f"diag['train_ll_std'] matches raw total std ({expected_total_std}) instead of normalized!"
        )


# ===========================================================================
# 3. K-Means rejection of candidates with incomplete valid-fold coverage
# ===========================================================================

def test_kmeans_rejects_incomplete_valid_fold_coverage():
    """Verify select_kmeans_k rejects candidate K with NaNs in any configured fold,
    even if its single-fold mean is higher than an eligible K."""
    # FOLDS has 3 folds (F1, F2, F3)
    # Construct synthetic metrics:
    # K=3 has NaN in F1 and F2, but 0.40 in F3 (mean=0.40 across 1 fold)
    # K=4 has 0.20 in F1, 0.25 in F2, 0.22 in F3 (mean=0.223 across 3 folds)
    # K=5 has 0.15 in F1, 0.16 in F2, 0.14 in F3 (mean=0.15 across 3 folds)
    data = [
        {"scaler": "robust", "fold": "F1", "k": 2, "val_silhouette": np.nan},
        {"scaler": "robust", "fold": "F2", "k": 2, "val_silhouette": np.nan},
        {"scaler": "robust", "fold": "F3", "k": 2, "val_silhouette": np.nan},
        {"scaler": "robust", "fold": "F1", "k": 3, "val_silhouette": np.nan},
        {"scaler": "robust", "fold": "F2", "k": 3, "val_silhouette": np.nan},
        {"scaler": "robust", "fold": "F3", "k": 3, "val_silhouette": 0.40},
        {"scaler": "robust", "fold": "F1", "k": 4, "val_silhouette": 0.20},
        {"scaler": "robust", "fold": "F2", "k": 4, "val_silhouette": 0.25},
        {"scaler": "robust", "fold": "F3", "k": 4, "val_silhouette": 0.22},
        {"scaler": "robust", "fold": "F1", "k": 5, "val_silhouette": 0.15},
        {"scaler": "robust", "fold": "F2", "k": 5, "val_silhouette": 0.16},
        {"scaler": "robust", "fold": "F3", "k": 5, "val_silhouette": 0.14},
    ]
    df = pd.DataFrame(data)

    selected = select_kmeans_k(df, scaler_type="robust", tol=0.02)
    assert selected == 4, f"Expected K=4 to be selected, got {selected}. K=3 must be rejected due to incomplete fold coverage."


def test_kmeans_raises_when_no_candidate_has_full_coverage():
    """Verify select_kmeans_k raises ValueError/RuntimeError if no candidate K
    has valid silhouette scores in all configured folds."""
    data = [
        {"scaler": "robust", "fold": "F1", "k": 2, "val_silhouette": np.nan},
        {"scaler": "robust", "fold": "F2", "k": 2, "val_silhouette": 0.30},
        {"scaler": "robust", "fold": "F3", "k": 2, "val_silhouette": 0.35},
        {"scaler": "robust", "fold": "F1", "k": 3, "val_silhouette": 0.25},
        {"scaler": "robust", "fold": "F2", "k": 3, "val_silhouette": np.nan},
        {"scaler": "robust", "fold": "F3", "k": 3, "val_silhouette": 0.28},
    ]
    df = pd.DataFrame(data)

    with pytest.raises((ValueError, RuntimeError), match="[Nn]o candidate K"):
        select_kmeans_k(df, scaler_type="robust")


def test_kmeans_respects_tolerance_and_tie_breaker():
    """Verify select_kmeans_k selects smaller K among eligible candidates within tolerance."""
    data = [
        {"scaler": "robust", "fold": "F1", "k": 4, "val_silhouette": 0.20},
        {"scaler": "robust", "fold": "F2", "k": 4, "val_silhouette": 0.20},
        {"scaler": "robust", "fold": "F3", "k": 4, "val_silhouette": 0.20},  # mean = 0.20
        {"scaler": "robust", "fold": "F1", "k": 5, "val_silhouette": 0.21},
        {"scaler": "robust", "fold": "F2", "k": 5, "val_silhouette": 0.21},
        {"scaler": "robust", "fold": "F3", "k": 5, "val_silhouette": 0.21},  # mean = 0.21
    ]
    df = pd.DataFrame(data)

    # tol=0.02: 0.20 is within [0.21 - 0.02, 0.21], so smaller K (4) must be selected
    selected = select_kmeans_k(df, scaler_type="robust", tol=0.02)
    assert selected == 4

    # tol=0.005: 0.20 is NOT within [0.21 - 0.005, 0.21], so K=5 should be selected
    selected_tight = select_kmeans_k(df, scaler_type="robust", tol=0.005)
    assert selected_tight == 5


# ===========================================================================
# 4. Preservation of chronological split and holdout isolation
# ===========================================================================

def test_chronological_split_and_holdout_boundaries():
    """Verify train_pool ends at TRAIN_POOL_END (2024-12-31) and holdout starts
    at HOLDOUT_START (2025-01-01)."""
    assert TRAIN_POOL_END == "2024-12-31"
    assert HOLDOUT_START == "2025-01-01"

    dates = pd.date_range("2019-10-01", "2026-09-01", freq="B")
    mock_master = pd.DataFrame(np.random.randn(len(dates), 2), index=dates)

    train_pool, holdout = get_clean_splits(mock_master)

    assert train_pool.index.max() <= pd.Timestamp(TRAIN_POOL_END)
    assert holdout.index.min() >= pd.Timestamp(HOLDOUT_START)
    # Check no overlap
    assert train_pool.index.max() < holdout.index.min()


def test_folds_do_not_leak_into_holdout():
    """Verify that all expanding-window CV folds strictly use data within train_pool."""
    dates = pd.date_range("2019-10-31", "2024-12-31", freq="B")
    mock_train = pd.DataFrame(np.random.randn(len(dates), 2), index=dates)

    folds = generate_folds(mock_train)
    assert len(folds) == len(FOLDS)

    for fold in folds:
        assert fold["X_train"].index.max() <= pd.Timestamp(TRAIN_POOL_END)
        assert fold["X_val"].index.max() <= pd.Timestamp(TRAIN_POOL_END)
        assert fold["X_train"].index.max() < fold["X_val"].index.min()


def test_actual_kmeans_selection_excludes_k3():
    """Verify that on the project's actual kmeans_cv_metrics.csv,
    K=3 is rejected (only 1 valid fold) and K=4 is selected for both scalers."""
    path = Path("results/phase6_model_selection/kmeans/kmeans_cv_metrics.csv")
    if not path.exists():
        path = Path("results/kmeans_cv_metrics.csv")
    df = pd.read_csv(path)
    k_rob = select_kmeans_k(df, scaler_type="robust")
    k_std = select_kmeans_k(df, scaler_type="standard")
    assert k_rob == 4, f"Expected K=4 for robust scaler, got {k_rob}"
    assert k_std == 4, f"Expected K=4 for standard scaler, got {k_std}"


def test_scalers_never_fit_on_holdout():
    """Verify that scalers are only fitted on training data, never holdout."""
    from src.regime_discovery import fit_scale_full, fit_scale_fold
    dates = pd.date_range("2019-10-31", "2026-09-18", freq="B")
    mock_df = pd.DataFrame(np.random.randn(len(dates), 2), index=dates)
    train_pool, holdout = get_clean_splits(mock_df)

    # Full fit
    X_sc, scaler = fit_scale_full(train_pool, scaler_type="robust")
    assert scaler.center_.shape[0] == 2
    # Verify scaler was fitted on len(train_pool) rows, not train_pool + holdout
    assert len(X_sc) == len(train_pool)
    assert len(X_sc) < len(mock_df)


# ===========================================================================
# 5. GMM temporal leakage and covariance selection verification
# ===========================================================================

def test_gmm_fold_covariance_selection_uses_only_training_data():
    """Verify that select_gmm_cov_type evaluates BIC strictly on the provided
    training slice and returns the covariance type with minimum BIC."""
    np.random.seed(42)
    T, D = 80, 4
    X_train = np.random.randn(T, D)

    cov_type, model, best_bic = select_gmm_cov_type(
        X_train, k=2, candidate_cov_types=["full", "diag"], random_state=42
    )

    assert cov_type in ["full", "diag"]
    assert model.converged_
    # Verify BIC calculated on X_train matches best_bic
    expected_bic = float(model.bic(X_train))
    assert np.isclose(best_bic, expected_bic, rtol=1e-5)


def test_gmm_f1_f2_does_not_depend_on_f3():
    """Verify that F1 and F2 covariance type and metrics are completely independent
    of F3 data, proving temporal leakage has been eliminated."""
    np.random.seed(42)
    dates_train1 = pd.date_range("2020-01-01", periods=60, freq="B")
    dates_val1 = pd.date_range("2020-04-01", periods=20, freq="B")
    dates_train2 = pd.date_range("2020-01-01", periods=80, freq="B")
    dates_val2 = pd.date_range("2020-05-01", periods=20, freq="B")
    dates_train3 = pd.date_range("2020-01-01", periods=100, freq="B")
    dates_val3 = pd.date_range("2020-06-01", periods=20, freq="B")

    folds_base = [
        {"fold_id": "F1", "X_train": pd.DataFrame(np.random.randn(60, 3), index=dates_train1),
         "X_val": pd.DataFrame(np.random.randn(20, 3), index=dates_val1), "n_train": 60, "n_val": 20},
        {"fold_id": "F2", "X_train": pd.DataFrame(np.random.randn(80, 3), index=dates_train2),
         "X_val": pd.DataFrame(np.random.randn(20, 3), index=dates_val2), "n_train": 80, "n_val": 20},
        {"fold_id": "F3", "X_train": pd.DataFrame(np.random.randn(100, 3), index=dates_train3),
         "X_val": pd.DataFrame(np.random.randn(20, 3), index=dates_val3), "n_train": 100, "n_val": 20},
    ]

    import copy
    folds_mod = copy.deepcopy(folds_base)
    # Modify F3 training data drastically
    folds_mod[2]["X_train"] = pd.DataFrame(np.random.randn(100, 3) * 100 + 50, index=dates_train3)

    metrics_base, _ = run_gmm_cv(
        folds_base, scaler_type="robust", candidate_k=[2], candidate_cov_types=["full", "diag"],
        n_init=2, max_iter=20, random_state=42
    )
    metrics_mod, _ = run_gmm_cv(
        folds_mod, scaler_type="robust", candidate_k=[2], candidate_cov_types=["full", "diag"],
        n_init=2, max_iter=20, random_state=42
    )

    # F1 and F2 records must be strictly equal across both runs
    f1_base = metrics_base[metrics_base["fold"] == "F1"].iloc[0]
    f1_mod = metrics_mod[metrics_mod["fold"] == "F1"].iloc[0]
    assert f1_base["covariance_type"] == f1_mod["covariance_type"]
    assert np.isclose(f1_base["train_bic"], f1_mod["train_bic"], rtol=1e-5)
    assert np.isclose(f1_base["val_ll_per_obs"], f1_mod["val_ll_per_obs"], rtol=1e-5)

    f2_base = metrics_base[metrics_base["fold"] == "F2"].iloc[0]
    f2_mod = metrics_mod[metrics_mod["fold"] == "F2"].iloc[0]
    assert f2_base["covariance_type"] == f2_mod["covariance_type"]
    assert np.isclose(f2_base["train_bic"], f2_mod["train_bic"], rtol=1e-5)
    assert np.isclose(f2_base["val_ll_per_obs"], f2_mod["val_ll_per_obs"], rtol=1e-5)


def test_gmm_validation_and_holdout_never_used_for_covariance():
    """Verify that changing validation data has zero effect on covariance type selection
    and training metrics for any fold."""
    np.random.seed(42)
    dates_train = pd.date_range("2020-01-01", periods=60, freq="B")
    dates_val = pd.date_range("2020-04-01", periods=20, freq="B")

    folds_v1 = [
        {"fold_id": "F1", "X_train": pd.DataFrame(np.random.randn(60, 3), index=dates_train),
         "X_val": pd.DataFrame(np.random.randn(20, 3), index=dates_val), "n_train": 60, "n_val": 20}
    ]
    import copy
    folds_v2 = copy.deepcopy(folds_v1)
    # Modify validation data dramatically
    folds_v2[0]["X_val"] = pd.DataFrame(np.random.randn(20, 3) * 50 - 100, index=dates_val)

    m1, _ = run_gmm_cv(
        folds_v1, scaler_type="robust", candidate_k=[2], candidate_cov_types=["full", "diag"],
        n_init=2, max_iter=20, random_state=42
    )
    m2, _ = run_gmm_cv(
        folds_v2, scaler_type="robust", candidate_k=[2], candidate_cov_types=["full", "diag"],
        n_init=2, max_iter=20, random_state=42
    )

    assert m1.iloc[0]["covariance_type"] == m2.iloc[0]["covariance_type"]
    assert np.isclose(m1.iloc[0]["train_bic"], m2.iloc[0]["train_bic"], rtol=1e-5)
    assert np.isclose(m1.iloc[0]["train_ll_per_obs"], m2.iloc[0]["train_ll_per_obs"], rtol=1e-5)
    # But val_ll should be different because validation data changed
    assert not np.isclose(m1.iloc[0]["val_ll_per_obs"], m2.iloc[0]["val_ll_per_obs"], rtol=1e-3)


def test_gmm_cv_records_covariance_and_criterion():
    """Verify that run_gmm_cv records covariance_type and selection_criterion in metrics DataFrame."""
    np.random.seed(42)
    dates_train = pd.date_range("2020-01-01", periods=60, freq="B")
    dates_val = pd.date_range("2020-04-01", periods=20, freq="B")
    folds = [
        {"fold_id": "F1", "X_train": pd.DataFrame(np.random.randn(60, 3), index=dates_train),
         "X_val": pd.DataFrame(np.random.randn(20, 3), index=dates_val), "n_train": 60, "n_val": 20}
    ]
    df, consensus_cov = run_gmm_cv(
        folds, scaler_type="robust", candidate_k=[2], candidate_cov_types=["full", "diag"],
        n_init=2, max_iter=20, random_state=42
    )

    assert "covariance_type" in df.columns
    assert "selection_criterion" in df.columns
    assert (df["selection_criterion"] == "min_train_bic").all()
    assert df["covariance_type"].iloc[0] in ["full", "diag"]
    assert consensus_cov in ["full", "diag"]


def test_gmm_consensus_covariance_selection():
    """Verify select_gmm_covariance performs majority vote among folds."""
    mock_metrics = pd.DataFrame([
        {"scaler": "robust", "fold": "F1", "k": 2, "covariance_type": "full"},
        {"scaler": "robust", "fold": "F2", "k": 2, "covariance_type": "full"},
        {"scaler": "robust", "fold": "F3", "k": 2, "covariance_type": "tied"},
    ])
    chosen = select_gmm_covariance(mock_metrics, selected_k=2, scaler_type="robust")
    assert chosen == "full"


