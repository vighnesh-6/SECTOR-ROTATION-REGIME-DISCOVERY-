"""
deployment/engine/inference_engine.py
=====================================
Production Causal Regime Inference Engine.

Uses frozen RobustScaler and 6-state Gaussian HMM parameters extracted from
the research baseline. Performs recursive forward-filtering inference step-by-step
with zero retraining, zero data leakage, and exact mathematical parity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


class RegimeInferenceEngine:
    """
    Online Causal Inference Engine for 6-State Market Regime Discovery.
    """

    def __init__(self, models_dir: Optional[Union[str, Path]] = None) -> None:
        if models_dir is None:
            models_dir = Path(__file__).resolve().parent / "models"
        else:
            models_dir = Path(models_dir)

        scaler_path = models_dir / "frozen_scaler.json"
        hmm_path = models_dir / "frozen_hmm.json"

        if not scaler_path.exists():
            raise FileNotFoundError(f"Missing frozen scaler parameters: {scaler_path}")
        if not hmm_path.exists():
            raise FileNotFoundError(f"Missing frozen HMM parameters: {hmm_path}")

        with open(scaler_path, "r", encoding="utf-8") as f:
            scaler_data = json.load(f)
        with open(hmm_path, "r", encoding="utf-8") as f:
            hmm_data = json.load(f)

        self.feature_names: List[str] = scaler_data["feature_names"]
        self.center: np.ndarray = np.array(scaler_data["center"], dtype=np.float64)
        self.scale: np.ndarray = np.array(scaler_data["scale"], dtype=np.float64)

        self.n_states: int = int(hmm_data["n_components"])
        self.startprob: np.ndarray = np.array(hmm_data["startprob"], dtype=np.float64)
        self.transmat: np.ndarray = np.array(hmm_data["transmat"], dtype=np.float64)
        self.means: np.ndarray = np.array(hmm_data["means"], dtype=np.float64)
        self.covars: np.ndarray = np.array(hmm_data["covars"], dtype=np.float64)

        # Precompute constants for log-likelihood
        self.d = len(self.feature_names)
        assert self.d == 42, f"Expected 42 features, got {self.d}"
        assert self.means.shape == (self.n_states, self.d)

        # Handle diagonal covariance matrices stored as (n_states, d, d) or (n_states, d)
        if self.covars.ndim == 3:
            self.variances = np.array([np.diag(self.covars[j]) for j in range(self.n_states)], dtype=np.float64)
        else:
            self.variances = self.covars.astype(np.float64)

        assert self.variances.shape == (self.n_states, self.d), f"Expected variances shape {(self.n_states, self.d)}, got {self.variances.shape}"

        # log_det per state: sum_d log(variance[j, d])
        self.log_dets = np.sum(np.log(self.variances), axis=1)  # shape (n_states,)
        self.const_term = self.d * np.log(2.0 * np.pi)

    def scale_features(self, features: Dict[str, float]) -> np.ndarray:
        """
        Scale incoming unscaled feature dictionary using frozen RobustScaler.
        Features must contain all 42 feature names.
        """
        x = np.empty(self.d, dtype=np.float64)
        for idx, feat in enumerate(self.feature_names):
            if feat not in features:
                raise KeyError(f"Missing required feature for inference: '{feat}'")
            val = float(features[feat])
            if np.isnan(val) or np.isinf(val):
                raise ValueError(f"Feature '{feat}' has non-finite value: {val}")
            x[idx] = val

        # Robust scaling: (x - center) / scale
        x_scaled = (x - self.center) / self.scale
        return x_scaled

    def compute_log_emissions(self, x_scaled: np.ndarray) -> np.ndarray:
        """
        Calculate emission log-likelihood for each of the 6 states given observation x_scaled.
        Uses diagonal covariance multivariate Gaussian formula in pure numpy.
        """
        log_emits = np.empty(self.n_states, dtype=np.float64)
        for j in range(self.n_states):
            diff = x_scaled - self.means[j]
            quad = np.sum((diff ** 2) / self.variances[j])
            log_emits[j] = -0.5 * (self.const_term + self.log_dets[j] + quad)
        return log_emits

    def forward_step(
        self,
        features: Dict[str, float],
        prev_probs: Optional[Union[List[float], np.ndarray]] = None,
        incumbent_regime: Optional[int] = None,
        threshold: float = 0.50,
    ) -> Dict[str, Any]:
        """
        Execute one causal forward filtering step.

        Args:
          features: Dict of 42 unscaled feature values for the current session.
          prev_probs: 6-element probability vector from session t-1. If None, uses startprob.
          incumbent_regime: Currently active regime ID [0..5] before this step.
          threshold: Acceptance confidence threshold (default 0.50).

        Returns:
          Dict containing updated probability distribution, argmax, max_prob,
          is_confident flag, and accepted regime.
        """
        x_scaled = self.scale_features(features)
        log_emits = self.compute_log_emissions(x_scaled)

        if prev_probs is None:
            # First session: prior is startprob
            prior = np.maximum(self.startprob, 1e-300)
            log_prior = np.log(prior)
        else:
            p_prev = np.asarray(prev_probs, dtype=np.float64)
            if len(p_prev) != self.n_states:
                raise ValueError(f"Expected {self.n_states} previous probabilities, got {len(p_prev)}")
            # Chapman-Kolmogorov predictive step: prior = p_prev @ transmat
            pred = p_prev @ self.transmat
            pred = np.maximum(pred, 1e-300)
            log_prior = np.log(pred)

        # Unnormalized log posterior
        log_unnorm = log_prior + log_emits

        # Log-sum-exp normalization
        max_log = np.max(log_unnorm)
        exp_vals = np.exp(log_unnorm - max_log)
        curr_probs = exp_vals / np.sum(exp_vals)

        # Clean tiny negatives or sum drift
        curr_probs = np.maximum(curr_probs, 0.0)
        curr_probs = curr_probs / np.sum(curr_probs)

        # Acceptance check
        max_p = float(np.max(curr_probs))
        candidates = np.where(np.isclose(curr_probs, max_p, atol=1e-6))[0].tolist()
        is_tied = len(candidates) > 1

        if max_p >= threshold - 1e-6:
            if is_tied and incumbent_regime in candidates:
                accepted = incumbent_regime
            else:
                accepted = int(candidates[0])
            is_confident = True
        else:
            accepted = incumbent_regime
            is_confident = False

        res = {
            "prob_0": float(curr_probs[0]),
            "prob_1": float(curr_probs[1]),
            "prob_2": float(curr_probs[2]),
            "prob_3": float(curr_probs[3]),
            "prob_4": float(curr_probs[4]),
            "prob_5": float(curr_probs[5]),
            "probs_array": curr_probs.tolist(),
            "raw_regime_argmax": int(np.argmax(curr_probs)),
            "max_probability": max_p,
            "is_confident": is_confident,
            "accepted_regime": accepted,
        }
        return res
