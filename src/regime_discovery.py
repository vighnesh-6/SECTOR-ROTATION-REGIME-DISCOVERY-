"""
src/regime_discovery.py
=======================
Phase 6 - Unsupervised Market Regime Discovery
Sector Rotation Regime Discovery Project

Implements:
  - Expanding-window walk-forward cross-validation folds
  - Per-fold, leakage-safe scaler fitting (RobustScaler / StandardScaler)
  - K-Means baseline regime discovery
  - Gaussian Mixture Model (GMM) probabilistic regime discovery
  - Gaussian HMM temporal regime discovery (hmmlearn)
  - Forward-filtered HMM state probabilities (real-time causal inference)
  - Viterbi retrospective state sequences (clearly distinguished from filtered)
  - Final model fitting, regime characterisation, and holdout evaluation
  - Scaler sensitivity comparison via ARI

Protocol source: phase6_final_protocol.md (approved 2026-10-11)
"""

from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import (
    silhouette_score,
    davies_bouldin_score,
    calinski_harabasz_score,
    adjusted_rand_score,
)
from sklearn.preprocessing import RobustScaler, StandardScaler
from scipy.stats import multivariate_normal
from hmmlearn.hmm import GaussianHMM

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANDIDATE_K: List[int] = [2, 3, 4, 5, 6]

FOLDS: List[Tuple[str, str, str, str, str]] = [
    ("F1", "2019-10-31", "2021-12-31", "2022-01-01", "2022-12-31"),
    ("F2", "2019-10-31", "2022-12-31", "2023-01-01", "2023-12-31"),
    ("F3", "2019-10-31", "2023-12-31", "2024-01-01", "2024-12-31"),
]

TRAIN_POOL_END: str = "2024-12-31"
HOLDOUT_START:  str = "2025-01-01"

GMM_COVARIANCE_TYPES: List[str] = ["full", "diag", "tied"]

SCALER_VARIANTS: Dict[str, Any] = {
    "robust":   RobustScaler,
    "standard": StandardScaler,
}

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_unscaled_master(data_dir: str) -> pd.DataFrame:
    """
    Load the 42-feature unscaled master DataFrame from Phase 3 outputs.
    Uses load_master_feature_dataset from src.normalization - the single
    authoritative assembly point for the 42 approved features.

    Source files (read-only):
      data/processed/feature_engineered/*.csv
      data/processed/aligned/india_vix_aligned.csv

    Returns a DataFrame indexed by Date with NaN rows preserved.
    """
    import sys
    sys.path.insert(0, str(Path(data_dir).parent))
    from src.normalization import load_master_feature_dataset
    return load_master_feature_dataset(data_dir)


def get_clean_splits(
    master_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Drop all NaN rows (rolling-window warmup), then split into:
      - train_pool : 2019-10-31 to 2024-12-31  (1265 rows)
      - holdout    : 2025-01-02 to 2026-09-18  (422 rows)

    The holdout DataFrame is returned but MUST NOT be used during
    model selection or hyperparameter tuning.
    """
    clean_df   = master_df.dropna()
    train_pool = clean_df.loc[:TRAIN_POOL_END].copy()
    holdout    = clean_df.loc[HOLDOUT_START:].copy()
    return train_pool, holdout


def generate_folds(
    train_pool: pd.DataFrame,
) -> List[Dict[str, Any]]:
    """
    Yield three expanding-window walk-forward fold dictionaries.
    Each dict contains:
      fold_id, X_train (unscaled), X_val (unscaled), train_dates, val_dates
    """
    result = []
    for fold_id, ts, te, vs, ve in FOLDS:
        X_train = train_pool.loc[ts:te].copy()
        X_val   = train_pool.loc[vs:ve].copy()
        result.append(
            {
                "fold_id":     fold_id,
                "X_train":     X_train,
                "X_val":       X_val,
                "train_dates": (X_train.index.min().date(), X_train.index.max().date()),
                "val_dates":   (X_val.index.min().date(),   X_val.index.max().date()),
                "n_train":     len(X_train),
                "n_val":       len(X_val),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Scaler helpers
# ---------------------------------------------------------------------------

def fit_scale_fold(
    X_train: pd.DataFrame,
    X_val:   pd.DataFrame,
    scaler_type: str = "robust",
) -> Tuple[np.ndarray, np.ndarray, Any]:
    """
    Fit a fresh scaler on X_train ONLY.
    Transform both X_train and X_val.
    Returns (X_train_scaled, X_val_scaled, fitted_scaler).

    No NaN rows should be present - callers must pass clean DataFrames.
    """
    ScalerClass = SCALER_VARIANTS[scaler_type]
    scaler = ScalerClass()
    X_tr_sc = scaler.fit_transform(X_train.values)
    X_va_sc = scaler.transform(X_val.values)
    return X_tr_sc, X_va_sc, scaler


def fit_scale_full(
    X_train: pd.DataFrame,
    scaler_type: str = "robust",
) -> Tuple[np.ndarray, Any]:
    """
    Fit a fresh scaler on the full training pool (final model step).
    Returns (X_train_scaled, fitted_scaler).
    """
    ScalerClass = SCALER_VARIANTS[scaler_type]
    scaler = ScalerClass()
    X_sc = scaler.fit_transform(X_train.values)
    return X_sc, scaler


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def median_regime_duration(labels: np.ndarray) -> float:
    """
    Compute median run-length (consecutive same-label days) in a label sequence.
    """
    if len(labels) == 0:
        return 0.0
    runs = []
    current_run = 1
    for i in range(1, len(labels)):
        if labels[i] == labels[i - 1]:
            current_run += 1
        else:
            runs.append(current_run)
            current_run = 1
    runs.append(current_run)
    return float(np.median(runs))


def posterior_entropy(proba: np.ndarray, eps: float = 1e-12) -> float:
    """
    Mean posterior entropy per observation from GMM predict_proba output.
    Low entropy -> confident regime assignments.
    """
    H = -np.sum(proba * np.log(proba + eps), axis=1)
    return float(np.mean(H))


# ---------------------------------------------------------------------------
# K-Means
# ---------------------------------------------------------------------------

def run_kmeans_cv(
    folds: List[Dict[str, Any]],
    scaler_type: str = "robust",
    candidate_k: List[int] = CANDIDATE_K,
    n_init: int = 20,
    max_iter: int = 500,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Run K-Means cross-validation across all folds and candidate K values.

    Primary selection metric: mean validation silhouette score.
    Supporting: Davies-Bouldin, Calinski-Harabasz, inertia, median regime duration.

    Returns a DataFrame of per-(fold, K) metrics.
    """
    records = []
    for fold in folds:
        X_tr_sc, X_va_sc, _ = fit_scale_fold(
            fold["X_train"], fold["X_val"], scaler_type
        )
        for k in candidate_k:
            km = KMeans(
                n_clusters=k,
                init="k-means++",
                n_init=n_init,
                max_iter=max_iter,
                random_state=random_state,
            )
            km.fit(X_tr_sc)
            val_labels = km.predict(X_va_sc)

            n_unique_val = len(np.unique(val_labels))
            sil = (
                silhouette_score(X_va_sc, val_labels)
                if n_unique_val > 1
                else np.nan
            )
            db  = davies_bouldin_score(X_va_sc, val_labels) if n_unique_val > 1 else np.nan
            ch  = calinski_harabasz_score(X_va_sc, val_labels) if n_unique_val > 1 else np.nan

            records.append(
                {
                    "scaler":                    scaler_type,
                    "fold":                      fold["fold_id"],
                    "n_train":                   fold["n_train"],
                    "n_val":                     fold["n_val"],
                    "k":                         k,
                    "inertia":                   float(km.inertia_),
                    "val_silhouette":            sil,
                    "val_davies_bouldin":        db,
                    "val_calinski_harabasz":     ch,
                    "val_median_regime_duration": median_regime_duration(val_labels),
                }
            )
    return pd.DataFrame(records)


def select_kmeans_k(
    metrics_df: pd.DataFrame,
    scaler_type: str = "robust",
    tol: float = 0.02,
) -> int:
    """
    Select optimal K for K-Means from CV metrics.
    Criterion: highest mean validation silhouette across folds.
    Ties within tol: prefer smaller K.
    """
    subset   = metrics_df[metrics_df["scaler"] == scaler_type]
    mean_sil = subset.groupby("k")["val_silhouette"].mean()
    best_sil = mean_sil.max()
    candidates = mean_sil[mean_sil >= best_sil - tol].index.tolist()
    return int(min(candidates))


# ---------------------------------------------------------------------------
# GMM
# ---------------------------------------------------------------------------

def _probe_covariance_type(
    X_tr_sc: np.ndarray,
    candidate_k: List[int],
    reg_covar: float = 1e-6,
    n_init: int = 10,
    max_iter: int = 500,
    random_state: int = 42,
) -> str:
    """
    Determine the covariance type to use for all GMM fits of this scaler variant.
    Tests 'full' -> 'diag' -> 'tied' in order on the largest training slice.
    Returns the first type that converges for all candidate K values.
    """
    from sklearn.exceptions import ConvergenceWarning
    for cov_type in GMM_COVARIANCE_TYPES:
        all_converged = True
        for k in candidate_k:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                try:
                    gm = GaussianMixture(
                        n_components=k,
                        covariance_type=cov_type,
                        reg_covar=reg_covar,
                        n_init=n_init,
                        max_iter=max_iter,
                        random_state=random_state,
                    ).fit(X_tr_sc)
                    if not gm.converged_:
                        all_converged = False
                        break
                    cov_warns = [
                        x for x in w
                        if issubclass(x.category, (ConvergenceWarning, RuntimeWarning))
                        and ("covariance" in str(x.message).lower()
                             or "not converge" in str(x.message).lower())
                    ]
                    if cov_warns:
                        all_converged = False
                        break
                except Exception:
                    all_converged = False
                    break
        if all_converged:
            return cov_type
    return "diag"


def run_gmm_cv(
    folds: List[Dict[str, Any]],
    scaler_type: str = "robust",
    candidate_k: List[int] = CANDIDATE_K,
    reg_covar: float = 1e-6,
    n_init: int = 10,
    max_iter: int = 500,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, str]:
    """
    Run GMM cross-validation across all folds and candidate K values.

    Covariance type is determined once from the largest fold (F3) training data,
    then fixed for all K and all folds so BIC comparisons remain valid.

    Primary K-selection metric: mean validation log-likelihood per observation.
    Supporting: training BIC, training AIC, posterior entropy, convergence, persistence.

    Returns (metrics_df, chosen_covariance_type).
    """
    fold3   = [f for f in folds if f["fold_id"] == "F3"][0]
    X_tr_f3, _, _ = fit_scale_fold(fold3["X_train"], fold3["X_val"], scaler_type)
    chosen_cov = _probe_covariance_type(
        X_tr_f3, candidate_k, reg_covar, n_init, max_iter, random_state
    )

    records = []
    for fold in folds:
        X_tr_sc, X_va_sc, _ = fit_scale_fold(
            fold["X_train"], fold["X_val"], scaler_type
        )
        for k in candidate_k:
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                gm = GaussianMixture(
                    n_components=k,
                    covariance_type=chosen_cov,
                    reg_covar=reg_covar,
                    n_init=n_init,
                    max_iter=max_iter,
                    random_state=random_state,
                ).fit(X_tr_sc)

            converged  = bool(gm.converged_)
            val_ll     = float(gm.score(X_va_sc))   if converged else np.nan
            train_bic  = float(gm.bic(X_tr_sc))     if converged else np.nan
            train_aic  = float(gm.aic(X_tr_sc))     if converged else np.nan
            train_ll   = float(gm.score(X_tr_sc))   if converged else np.nan

            val_labels = gm.predict(X_va_sc)
            val_proba  = gm.predict_proba(X_va_sc)
            n_unique   = len(np.unique(val_labels))
            ent        = posterior_entropy(val_proba) if converged else np.nan
            dur        = median_regime_duration(val_labels)

            records.append(
                {
                    "scaler":                     scaler_type,
                    "covariance_type":            chosen_cov,
                    "fold":                       fold["fold_id"],
                    "n_train":                    fold["n_train"],
                    "n_val":                      fold["n_val"],
                    "k":                          k,
                    "converged":                  converged,
                    "val_ll_per_obs":             val_ll,
                    "train_bic":                  train_bic,
                    "train_aic":                  train_aic,
                    "train_ll_per_obs":           train_ll,
                    "val_posterior_entropy":      ent,
                    "val_median_regime_duration": dur,
                    "val_n_unique_labels":        n_unique,
                }
            )
    return pd.DataFrame(records), chosen_cov


def select_gmm_k(
    metrics_df: pd.DataFrame,
    scaler_type: str = "robust",
    tol: float = 0.5,
) -> int:
    """
    Select optimal K for GMM.
    Criterion: highest mean validation log-likelihood per observation across folds.
    Ties within tol nats: prefer smaller K.
    Only considers K where all folds converged.
    """
    subset = metrics_df[
        (metrics_df["scaler"] == scaler_type) & (metrics_df["converged"] == True)
    ]
    counts  = subset.groupby("k")["converged"].count()
    valid_k = counts[counts == len(FOLDS)].index.tolist()
    if not valid_k:
        raise RuntimeError("No K converged in all folds for GMM.")
    mean_ll = (
        subset[subset["k"].isin(valid_k)]
        .groupby("k")["val_ll_per_obs"]
        .mean()
    )
    best_ll    = mean_ll.max()
    candidates = mean_ll[mean_ll >= best_ll - tol].index.tolist()
    return int(min(candidates))


# ---------------------------------------------------------------------------
# HMM - forward filter
# ---------------------------------------------------------------------------

def _hmm_forward_filter(model: GaussianHMM, X: np.ndarray) -> np.ndarray:
    """
    Compute causal (forward-filtered) state probabilities for each observation.
    P(s_t | o_1, ..., o_t, model) - no future observations used.

    This is the correct algorithm for real-time regime tracking.
    Viterbi (model.predict) is retrospective and uses the full sequence.

    Returned array shape: (T, n_states).
    """
    n_states  = model.n_components
    T         = len(X)
    log_trans = np.log(model.transmat_ + 1e-300)

    log_emit = np.zeros((T, n_states))
    for j in range(n_states):
        if model.covariance_type == "diag":
            cov = np.diag(model.covars_[j])
        elif model.covariance_type == "full":
            cov = model.covars_[j]
        elif model.covariance_type == "tied":
            cov = model.covars_
        else:  # spherical
            cov = np.eye(X.shape[1]) * model.covars_[j]
        log_emit[:, j] = multivariate_normal.logpdf(
            X, mean=model.means_[j], cov=cov
        )

    log_alpha = np.full((T, n_states), -np.inf)
    log_startprob     = np.log(model.startprob_ + 1e-300)
    log_alpha[0]      = log_startprob + log_emit[0]

    for t in range(1, T):
        for j in range(n_states):
            log_alpha[t, j] = (
                np.logaddexp.reduce(log_alpha[t - 1] + log_trans[:, j])
                + log_emit[t, j]
            )

    alpha    = np.exp(log_alpha - log_alpha.max(axis=1, keepdims=True))
    row_sums = alpha.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums == 0, 1.0, row_sums)
    return alpha / row_sums


# ---------------------------------------------------------------------------
# HMM - CV
# ---------------------------------------------------------------------------

def _fit_hmm_multi_seed(
    X_train: np.ndarray,
    k: int,
    covariance_type: str = "diag",
    n_iter: int = 200,
    tol: float = 1e-4,
    seeds: List[int] = list(range(10)),
) -> Tuple[Optional[GaussianHMM], List[Dict[str, Any]]]:
    """
    Fit GaussianHMM with multiple random seeds.
    Returns (best_converged_model, per_seed_records).
    best_model is None if no seed converged.
    """
    best_model    = None
    best_train_ll = -np.inf
    seed_records  = []

    for seed in seeds:
        converged = False
        train_ll  = np.nan
        try:
            model = GaussianHMM(
                n_components=k,
                covariance_type=covariance_type,
                n_iter=n_iter,
                tol=tol,
                random_state=seed,
            )
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                model.fit(X_train, lengths=[len(X_train)])
            converged = bool(model.monitor_.converged)
            if converged:
                train_ll = float(model.score(X_train, lengths=[len(X_train)]))
        except Exception:
            pass

        seed_records.append(
            {"k": k, "seed": seed, "converged": converged, "train_ll_per_obs": train_ll}
        )
        if converged and not np.isnan(train_ll) and train_ll > best_train_ll:
            best_train_ll = train_ll
            best_model    = model

    return best_model, seed_records


def run_hmm_cv(
    folds: List[Dict[str, Any]],
    scaler_type: str = "robust",
    candidate_k: List[int] = CANDIDATE_K,
    covariance_type: str = "diag",
    n_iter: int = 200,
    tol: float = 1e-4,
    seeds: List[int] = list(range(10)),
) -> pd.DataFrame:
    """
    Run GaussianHMM cross-validation across all folds and candidate K values.

    For each (fold, K):
      - Fit 10 independent HMMs with seeds 0-9 on the fold training sequence.
      - Select the best converged model (highest training LL).
      - Score the validation sequence with model.score (forward algorithm: no lookahead).
      - Record all stability diagnostics.

    HMM data requirements:
      - Observations remain in chronological order throughout (never shuffled).
      - Each fold training/validation segment is a single contiguous sequence.

    Primary K-selection metric: mean validation log-likelihood per observation.

    NOTE on Viterbi columns: prefixed with 'viterbi_' and labelled RETROSPECTIVE.
    They use the full sequence bidirectionally and are not real-time signals.
    """
    records = []
    for fold in folds:
        X_tr_sc, X_va_sc, _ = fit_scale_fold(
            fold["X_train"], fold["X_val"], scaler_type
        )

        for k in candidate_k:
            best_model, seed_recs = _fit_hmm_multi_seed(
                X_tr_sc, k, covariance_type, n_iter, tol, seeds
            )

            train_lls   = [
                r["train_ll_per_obs"]
                for r in seed_recs
                if r["converged"] and not np.isnan(r["train_ll_per_obs"])
            ]
            n_converged  = sum(r["converged"] for r in seed_recs)
            train_ll_std = float(np.std(train_lls)) if len(train_lls) > 1 else np.nan
            best_train_ll = float(np.max(train_lls)) if train_lls else np.nan

            if best_model is not None:
                # Validation log-likelihood: model.score uses forward algorithm
                val_ll = float(best_model.score(X_va_sc, lengths=[len(X_va_sc)]))

                # Retrospective Viterbi (uses full sequence; NOT a real-time signal)
                viterbi_train = best_model.predict(X_tr_sc, lengths=[len(X_tr_sc)])
                viterbi_val   = best_model.predict(X_va_sc, lengths=[len(X_va_sc)])

                trans_diag   = best_model.transmat_.diagonal()
                stationary   = best_model.get_stationary_distribution()
                train_dur    = median_regime_duration(viterbi_train)
                val_dur      = median_regime_duration(viterbi_val)
                min_stat     = float(stationary.min())
                trans_diag_mean = float(trans_diag.mean())
            else:
                val_ll = train_dur = val_dur = min_stat = trans_diag_mean = np.nan

            records.append(
                {
                    "scaler":                          scaler_type,
                    "covariance_type":                 covariance_type,
                    "fold":                            fold["fold_id"],
                    "n_train":                         fold["n_train"],
                    "n_val":                           fold["n_val"],
                    "k":                               k,
                    "n_seeds_converged":               n_converged,
                    "best_train_ll_per_obs":           best_train_ll,
                    "train_ll_std":                    train_ll_std,
                    # Primary K-selection metric (forward algorithm - causal):
                    "val_ll_per_obs":                  val_ll,
                    # Retrospective Viterbi diagnostics only:
                    "viterbi_train_median_duration_retrospective": train_dur,
                    "viterbi_val_median_duration_retrospective":   val_dur,
                    "transition_diag_mean":            trans_diag_mean,
                    "min_stationary_mass":             min_stat,
                }
            )
    return pd.DataFrame(records)


def select_hmm_k(
    metrics_df: pd.DataFrame,
    scaler_type: str = "robust",
    tol: float = 0.01,
) -> int:
    """
    Select optimal K for HMM.
    Criterion: highest mean validation log-likelihood per observation across folds.
    Ties within tol nats: prefer smaller K.
    Only considers K where valid val_ll exists in all 3 folds.
    """
    subset = metrics_df[metrics_df["scaler"] == scaler_type]
    valid_k = (
        subset[subset["val_ll_per_obs"].notna()]
        .groupby("k")["val_ll_per_obs"]
        .count()
    )
    valid_k = valid_k[valid_k == len(FOLDS)].index.tolist()
    if not valid_k:
        raise RuntimeError("No K produced valid validation LL in all folds for HMM.")
    mean_ll    = subset[subset["k"].isin(valid_k)].groupby("k")["val_ll_per_obs"].mean()
    best_ll    = mean_ll.max()
    candidates = mean_ll[mean_ll >= best_ll - tol].index.tolist()
    return int(min(candidates))


# ---------------------------------------------------------------------------
# Final model fitting
# ---------------------------------------------------------------------------

def fit_final_kmeans(
    X_train_sc: np.ndarray,
    k: int,
    n_init: int = 20,
    max_iter: int = 500,
    random_state: int = 42,
) -> KMeans:
    """Fit final K-Means model on the full training pool (scaled)."""
    km = KMeans(
        n_clusters=k,
        init="k-means++",
        n_init=n_init,
        max_iter=max_iter,
        random_state=random_state,
    )
    km.fit(X_train_sc)
    return km


def fit_final_gmm(
    X_train_sc: np.ndarray,
    k: int,
    covariance_type: str,
    reg_covar: float = 1e-6,
    n_init: int = 10,
    max_iter: int = 500,
    random_state: int = 42,
) -> GaussianMixture:
    """Fit final GMM model on the full training pool (scaled)."""
    gm = GaussianMixture(
        n_components=k,
        covariance_type=covariance_type,
        reg_covar=reg_covar,
        n_init=n_init,
        max_iter=max_iter,
        random_state=random_state,
    )
    gm.fit(X_train_sc)
    return gm


def fit_final_hmm(
    X_train_sc: np.ndarray,
    k: int,
    covariance_type: str = "diag",
    n_iter: int = 200,
    tol: float = 1e-4,
    seeds: List[int] = list(range(10)),
) -> Tuple[Optional[GaussianHMM], Dict[str, Any]]:
    """
    Fit final HMM on full training pool using multi-seed initialisation.
    Returns (best_model, diagnostics_dict).
    """
    best_model, seed_recs = _fit_hmm_multi_seed(
        X_train_sc, k, covariance_type, n_iter, tol, seeds
    )
    train_lls   = [
        r["train_ll_per_obs"]
        for r in seed_recs
        if r["converged"] and not np.isnan(r["train_ll_per_obs"])
    ]
    n_converged = sum(r["converged"] for r in seed_recs)
    diagnostics = {
        "n_seeds_converged": n_converged,
        "train_ll_std":      float(np.std(train_lls)) if len(train_lls) > 1 else np.nan,
        "best_train_ll":     float(np.max(train_lls)) if train_lls else np.nan,
    }
    if best_model is not None:
        diagnostics["transition_matrix"]  = best_model.transmat_.tolist()
        diagnostics["stationary_dist"]    = best_model.get_stationary_distribution().tolist()
        diagnostics["transmat_diag_mean"] = float(best_model.transmat_.diagonal().mean())
    return best_model, diagnostics


# ---------------------------------------------------------------------------
# Label assignment
# ---------------------------------------------------------------------------

def assign_labels_kmeans(model: KMeans, X_sc: np.ndarray) -> np.ndarray:
    """Hard cluster assignment from K-Means."""
    return model.predict(X_sc)


def assign_labels_gmm(model: GaussianMixture, X_sc: np.ndarray) -> np.ndarray:
    """Hard assignment from GMM (argmax of posterior)."""
    return model.predict(X_sc)


def assign_viterbi_labels_hmm(
    model: GaussianHMM, X_sc: np.ndarray
) -> np.ndarray:
    """
    Viterbi decoding - RETROSPECTIVE SMOOTHED state sequence.
    Uses the complete observation sequence; not causal.
    MUST be labelled retrospective in all outputs.
    """
    return model.predict(X_sc, lengths=[len(X_sc)])


def assign_filtered_proba_hmm(
    model: GaussianHMM, X_sc: np.ndarray
) -> np.ndarray:
    """
    Forward-filtered state probabilities - CAUSAL real-time estimate.
    P(s_t | o_1..o_t) - no future observations used.
    Shape: (T, n_states).
    """
    return _hmm_forward_filter(model, X_sc)


# ---------------------------------------------------------------------------
# Regime characterisation
# ---------------------------------------------------------------------------

def characterise_regimes(
    X_unscaled: pd.DataFrame,
    labels: np.ndarray,
    model_name: str,
    k: int,
    scaler_type: str,
    label_type: str = "hard",
) -> pd.DataFrame:
    """
    Compute per-regime statistics on the ORIGINAL UNSCALED features.

    label_type should be 'hard' for K-Means/GMM or
    'retrospective_viterbi' for HMM. Regime IDs are integers only;
    no economic names are pre-assigned.

    Returns a long-form DataFrame: one row per (regime_id, feature, statistic).
    """
    records = []
    feat_df = X_unscaled.copy()
    feat_df["_regime"] = labels

    for regime_id in range(k):
        subset = feat_df[feat_df["_regime"] == regime_id].drop(columns=["_regime"])
        n_obs  = len(subset)
        for col in subset.columns:
            records.append(
                {
                    "model":      model_name,
                    "scaler":     scaler_type,
                    "label_type": label_type,
                    "k":          k,
                    "regime_id":  regime_id,
                    "n_obs":      n_obs,
                    "feature":    col,
                    "mean":       float(subset[col].mean()),
                    "median":     float(subset[col].median()),
                    "std":        float(subset[col].std()),
                    "p25":        float(subset[col].quantile(0.25)),
                    "p75":        float(subset[col].quantile(0.75)),
                }
            )
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Holdout evaluation
# ---------------------------------------------------------------------------

def evaluate_holdout(
    model_name: str,
    model: Any,
    scaler: Any,
    X_holdout_unscaled: pd.DataFrame,
    k: int,
    scaler_type: str,
) -> Dict[str, Any]:
    """
    Evaluate the final fitted model on the 2025-2026 holdout.
    Called ONCE per model after K selection is finalised from CV.

    For HMM: returns both Viterbi (retrospective) and forward-filtered
    probabilities. These are clearly distinguished in the returned dict.

    No holdout result is used to modify K, covariance type, or any hyperparameter.
    """
    X_ho_sc = scaler.transform(X_holdout_unscaled.values)
    result  = {
        "model":     model_name,
        "scaler":    scaler_type,
        "k":         k,
        "n_holdout": len(X_holdout_unscaled),
        "dates":     (
            X_holdout_unscaled.index.min().date(),
            X_holdout_unscaled.index.max().date()
        ),
    }

    if model_name == "kmeans":
        labels = assign_labels_kmeans(model, X_ho_sc)
        result["labels"]       = labels
        n_uniq = len(np.unique(labels))
        result["val_silhouette"]    = float(silhouette_score(X_ho_sc, labels)) if n_uniq > 1 else np.nan
        result["median_duration"]   = median_regime_duration(labels)

    elif model_name == "gmm":
        labels = assign_labels_gmm(model, X_ho_sc)
        result["labels"]            = labels
        result["ll_per_obs"]        = float(model.score(X_ho_sc))
        result["posterior_entropy"] = posterior_entropy(model.predict_proba(X_ho_sc))
        result["median_duration"]   = median_regime_duration(labels)

    elif model_name == "hmm":
        # Retrospective Viterbi (full holdout sequence)
        viterbi_labels = assign_viterbi_labels_hmm(model, X_ho_sc)
        # Causal forward-filtered probabilities
        filtered_proba  = assign_filtered_proba_hmm(model, X_ho_sc)
        filtered_labels = np.argmax(filtered_proba, axis=1)

        result["viterbi_labels_retrospective"] = viterbi_labels
        result["filtered_proba_causal"]        = filtered_proba
        result["filtered_labels_causal"]       = filtered_labels
        result["ll_per_obs"]                   = float(
            model.score(X_ho_sc, lengths=[len(X_ho_sc)])
        )
        result["viterbi_median_duration_retrospective"] = median_regime_duration(viterbi_labels)
        result["filtered_median_duration_causal"]       = median_regime_duration(filtered_labels)

    return result


# ---------------------------------------------------------------------------
# Scaler sensitivity comparison
# ---------------------------------------------------------------------------

def compare_scaler_sensitivity(
    labels_robust: np.ndarray,
    labels_standard: np.ndarray,
    k_robust: int,
    k_standard: int,
    model_name: str,
) -> Dict[str, Any]:
    """
    Compare regime assignments between RobustScaler and StandardScaler variants.
    ARI is computed only when both scalers selected the same K.
    """
    result = {
        "model":      model_name,
        "k_robust":   k_robust,
        "k_standard": k_standard,
        "k_agree":    k_robust == k_standard,
    }
    if k_robust == k_standard and len(labels_robust) == len(labels_standard):
        ari = adjusted_rand_score(labels_robust, labels_standard)
        result["ari"] = float(ari)
        result["assessment"] = (
            "scaler_robust"          if ari >= 0.60 else
            "broadly_consistent"     if ari >= 0.40 else
            "materially_different"
        )
    else:
        result["ari"]        = np.nan
        result["assessment"] = "different_k_selected"
    return result
