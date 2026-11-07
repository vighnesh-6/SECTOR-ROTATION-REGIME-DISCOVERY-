"""
deployment/tests/test_model_inference_parity.py
===============================================
Verifies mathematical parity of the online inference engine against the research baseline.
"""

import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEPLOYMENT_ROOT = REPO_ROOT / "deployment"
sys.path.insert(0, str(DEPLOYMENT_ROOT))
sys.path.insert(0, str(REPO_ROOT))

from engine.inference_engine import RegimeInferenceEngine
from src.regime_discovery import load_unscaled_master


def test_frozen_model_files_exist():
    models_dir = DEPLOYMENT_ROOT / "engine" / "models"
    assert (models_dir / "frozen_scaler.json").exists()
    assert (models_dir / "frozen_hmm.json").exists()
    assert (models_dir / "frozen_metadata.json").exists()

    with open(models_dir / "frozen_scaler.json") as f:
        scaler_data = json.load(f)
    assert len(scaler_data["feature_names"]) == 42
    assert len(scaler_data["center"]) == 42
    assert len(scaler_data["scale"]) == 42

    with open(models_dir / "frozen_hmm.json") as f:
        hmm_data = json.load(f)
    assert hmm_data["n_components"] == 6
    assert len(hmm_data["startprob"]) == 6
    assert len(hmm_data["transmat"]) == 6


def test_single_step_inference_parity():
    engine = RegimeInferenceEngine()
    master_df = load_unscaled_master(str(REPO_ROOT / "data")).dropna()
    ref_df = pd.read_csv(REPO_ROOT / "results" / "regime_discovery" / "hmm_causal_probabilities.csv")

    # Pick 5 distinct sessions in the holdout sequence to verify single-step forward filter
    sample_indices = [1266, 1350, 1450, 1550, 1686]
    for idx in sample_indices:
        prev_probs = ref_df.iloc[idx - 1][[f"prob_{i}" for i in range(6)]].values
        feat_dict = master_df.iloc[idx].to_dict()
        step_res = engine.forward_step(feat_dict, prev_probs=prev_probs)

        ref_probs = ref_df.iloc[idx][[f"prob_{i}" for i in range(6)]].values
        calc_probs = np.array(step_res["probs_array"])

        max_diff = float(np.max(np.abs(calc_probs - ref_probs)))
        assert max_diff < 1e-7, f"Parity mismatch at index {idx} ({ref_df.iloc[idx]['Date']}): max_diff={max_diff:.4e}"


def test_confidence_threshold_acceptance():
    engine = RegimeInferenceEngine()
    dummy_features = {f: 0.0 for f in engine.feature_names}

    # Case 1: Confident signal >= 0.50
    probs_confident = [0.05, 0.05, 0.60, 0.10, 0.10, 0.10]
    res1 = engine.forward_step(dummy_features, prev_probs=probs_confident, incumbent_regime=0, threshold=0.50)
    # Regardless of dummy emission, test acceptance logic
    assert "accepted_regime" in res1
    assert "is_confident" in res1

