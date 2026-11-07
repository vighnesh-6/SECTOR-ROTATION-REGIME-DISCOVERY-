"""
deployment/tests/test_feature_adapter.py
========================================
Unit and integration tests for MarketFeatureAdapter:
  - Exact 42-feature calculation and canonical ordering
  - Numerical parity against research ground truth
  - RobustScaler compatibility and scaling invariance
  - Missing data, missing symbols, and date alignment error handling
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

from engine.feature_adapter import (
    MarketFeatureAdapter,
    SECTOR_NAMES,
    REQUIRED_INDEX_SYMBOLS,
    MIN_LOOKBACK_SESSIONS,
)
from src.normalization import load_master_feature_dataset


@pytest.fixture(scope="module")
def adapter():
    return MarketFeatureAdapter()


@pytest.fixture(scope="module")
def ground_truth_df():
    return load_master_feature_dataset(str(REPO_ROOT / "data")).dropna()


def test_feature_names_and_ordering(adapter):
    """Verify that adapter produces exactly the approved 42 features in identical order."""
    assert len(adapter.feature_names) == 42

    # First 5: NIFTY 50
    assert adapter.feature_names[:5] == [
        "Return_20D",
        "Return_60D",
        "NIFTY50_Momentum_20D",
        "NIFTY50_Momentum_60D",
        "NIFTY50_Market_Trend_200D",
    ]

    # 6th: VIX
    assert adapter.feature_names[5] == "VIX_Close"

    # Remaining 36: 6 sectors * 6 features
    expected_sector_feats = [
        "Return_20D",
        "Return_60D",
        "Relative_Strength_20D",
        "Relative_Strength_60D",
        "Volatility_20D",
        "Volatility_60D",
    ]
    idx = 6
    for sector in ["AUTO", "BANK", "FMCG", "IT", "METAL", "PHARMA"]:
        for f in expected_sector_feats:
            assert adapter.feature_names[idx] == f"{sector}_{f}"
            idx += 1


def test_feature_parity_across_historical_dates(adapter, ground_truth_df):
    """Verify numerical parity against research ground truth across distinct test dates."""
    sample_dates = [
        "2020-03-23",  # COVID crash trough
        "2021-10-19",  # Bull market peak
        "2023-03-20",  # Mid-sample consolidation
        "2025-01-02",  # Holdout boundary start
        "2026-09-18",  # Holdout boundary end
    ]

    for test_date in sample_dates:
        assert test_date in ground_truth_df.index, f"Test date {test_date} not in ground truth."
        gt_row = ground_truth_df.loc[test_date]

        calc_dict = adapter.compute_features_for_date(test_date)
        assert len(calc_dict) == 42

        # Check every feature individually
        for feat in adapter.feature_names:
            gt_val = float(gt_row[feat])
            calc_val = calc_dict[feat]
            # Max tolerated unscaled diff is 1e-4 (primarily VIX float precision)
            abs_diff = abs(calc_val - gt_val)
            assert abs_diff < 1e-4, (
                f"Feature '{feat}' parity failed on {test_date}: "
                f"calc={calc_val:.6f}, gt={gt_val:.6f}, diff={abs_diff:.4e}"
            )

        # Check scaled feature parity under frozen RobustScaler
        scaled_calc = adapter.scale_feature_dict(calc_dict)
        gt_scaled = (gt_row[adapter.feature_names].values - adapter.center) / adapter.scale
        max_scaled_diff = float(np.max(np.abs(scaled_calc - gt_scaled)))
        assert max_scaled_diff < 1e-6, (
            f"Scaled parity failed on {test_date}: max_diff={max_scaled_diff:.4e}"
        )


def test_missing_symbol_handling(adapter):
    """Verify KeyError is raised when an index symbol is missing from prices."""
    dates = pd.date_range("2026-01-01", periods=250, freq="B")
    dummy_prices = pd.DataFrame(index=dates)
    # Populate only 7 symbols, omitting 'INDIA VIX'
    for s in REQUIRED_INDEX_SYMBOLS:
        if s != "INDIA VIX":
            dummy_prices[s] = 100.0

    with pytest.raises(KeyError, match="Missing required price column: INDIA VIX"):
        adapter.compute_features_from_prices(dummy_prices)


def test_insufficient_lookback_handling(adapter):
    """Verify ValueError is raised if price history is less than 201 sessions."""
    dates = pd.date_range("2026-01-01", periods=150, freq="B")
    dummy_prices = pd.DataFrame(index=dates)
    for s in REQUIRED_INDEX_SYMBOLS:
        dummy_prices[s] = 100.0

    # 150 sessions is insufficient for 200D trend
    with pytest.raises(ValueError):
        adapter.compute_features_for_date("2019-01-10")


def test_nonexistent_date_handling(adapter):
    """Verify KeyError is raised if the target date is not in price history."""
    with pytest.raises(KeyError, match="Target date 2099-01-01 not found"):
        adapter.fetch_trailing_prices("2099-01-01")


def test_robust_scaler_vector_transformation(adapter):
    """Verify that scale_feature_dict matches exact (x - center) / scale math."""
    dummy_feats = {feat: float(i + 1) for i, feat in enumerate(adapter.feature_names)}
    scaled = adapter.scale_feature_dict(dummy_feats)
    assert scaled.shape == (42,)

    raw_vec = np.array([dummy_feats[f] for f in adapter.feature_names], dtype=np.float64)
    expected_scaled = (raw_vec - adapter.center) / adapter.scale
    assert np.allclose(scaled, expected_scaled, atol=1e-12)

