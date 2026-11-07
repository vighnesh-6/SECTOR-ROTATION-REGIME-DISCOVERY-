"""
deployment/scripts/serialize_frozen_models.py
=============================================
Extracts and serializes the exact frozen parameters for:
  1. RobustScaler (center_, scale_, feature_names)
  2. Gaussian HMM (startprob_, transmat_, means_, covars_)

Source of truth:
  - Full clean training pool: 2019-10-31 to 2024-12-31 (1,265 rows)
  - Evaluated against causal reference: results/regime_discovery/hmm_causal_probabilities.csv
  - Parity requirement: max prob diff < 1e-9, 0 label mismatches across all 1,687 sessions.

Strict Rule: READ-ONLY access to src/ and data/. All outputs saved to deployment/engine/models/.
"""

import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd

# Safe read-only import of research modules
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.regime_discovery import (
    load_unscaled_master,
    get_clean_splits,
    fit_scale_full,
    fit_final_hmm,
    assign_filtered_proba_hmm,
    evaluate_holdout,
)

MODELS_DIR = REPO_ROOT / "deployment" / "engine" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def serialize():
    print("=" * 60)
    print("Serializing Frozen RobustScaler & Gaussian HMM Models")
    print("=" * 60)

    # 1. Load data
    print("Loading 42-feature master dataset...")
    master_df = load_unscaled_master(str(REPO_ROOT / "data"))
    clean_df = master_df.dropna()
    feature_names = list(clean_df.columns)
    assert len(feature_names) == 42, f"Expected 42 features, got {len(feature_names)}"

    train_pool, holdout = get_clean_splits(master_df)
    print(f"Train pool: {train_pool.index.min().date()} to {train_pool.index.max().date()} ({len(train_pool)} rows)")
    print(f"Holdout:    {holdout.index.min().date()} to {holdout.index.max().date()} ({len(holdout)} rows)")

    # 2. Fit Scaler
    print("\nFitting frozen RobustScaler...")
    X_tr_sc, scaler = fit_scale_full(train_pool, "robust")
    scaler_params = {
        "scaler_type": "RobustScaler",
        "feature_names": feature_names,
        "center": scaler.center_.tolist(),
        "scale": scaler.scale_.tolist(),
    }
    scaler_path = MODELS_DIR / "frozen_scaler.json"
    with open(scaler_path, "w") as f:
        json.dump(scaler_params, f, indent=2)
    print(f"Saved: {scaler_path}")

    # 3. Fit HMM
    print("\nFitting frozen 6-state Gaussian HMM (multi-seed 0-9)...")
    hmm_model, hmm_diag = fit_final_hmm(X_tr_sc, k=6, covariance_type="diag", n_iter=200, tol=1e-4, seeds=list(range(10)))
    assert hmm_model is not None, "HMM fit failed"

    hmm_params = {
        "model_type": "GaussianHMM",
        "n_components": 6,
        "covariance_type": "diag",
        "startprob": hmm_model.startprob_.tolist(),
        "transmat": hmm_model.transmat_.tolist(),
        "means": hmm_model.means_.tolist(),
        "covars": hmm_model.covars_.tolist(),
        "n_features": len(feature_names),
    }
    hmm_path = MODELS_DIR / "frozen_hmm.json"
    with open(hmm_path, "w") as f:
        json.dump(hmm_params, f, indent=2)
    print(f"Saved: {hmm_path}")

    # 4. Parity verification against reference CSV
    print("\nRunning parity verification across all 1,687 historical sessions...")
    hmm_filtered_train = assign_filtered_proba_hmm(hmm_model, X_tr_sc)
    ho_hmm = evaluate_holdout("hmm", hmm_model, scaler, holdout, 6, "robust")
    combined_proba = np.vstack([hmm_filtered_train, ho_hmm["filtered_proba_causal"]])

    ref_path = REPO_ROOT / "results" / "regime_discovery" / "hmm_causal_probabilities.csv"
    ref_df = pd.read_csv(ref_path)
    ref_proba = ref_df[[f"prob_{i}" for i in range(6)]].values

    max_prob_diff = float(np.max(np.abs(combined_proba - ref_proba)))
    label_mismatches = int(np.sum(np.argmax(combined_proba, axis=1) != np.argmax(ref_proba, axis=1)))

    print(f"  Maximum Probability Difference: {max_prob_diff:.6e}")
    print(f"  Label Mismatches: {label_mismatches} / {len(ref_df)}")

    assert max_prob_diff < 1e-9, f"Parity failed: max_diff={max_prob_diff} >= 1e-9"
    assert label_mismatches == 0, f"Parity failed: mismatches={label_mismatches} != 0"

    metadata = {
        "status": "VERIFIED_PARITY",
        "verified_at_date": "2026-09-18",
        "total_historical_rows": len(ref_df),
        "max_prob_diff": max_prob_diff,
        "label_mismatches": label_mismatches,
        "hmm_diagnostics": {
            "best_train_ll_per_obs": hmm_diag.get("best_train_ll_per_obs"),
            "transmat_diag_mean": hmm_diag.get("transmat_diag_mean"),
            "stationary_dist": hmm_diag.get("stationary_dist"),
        },
    }
    meta_path = MODELS_DIR / "frozen_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata: {meta_path}")
    print("\nAll models serialized and mathematically verified!")


if __name__ == "__main__":
    serialize()

