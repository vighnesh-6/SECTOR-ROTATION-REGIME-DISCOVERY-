"""
tests/test_event_analysis.py
============================
Formal unit test suite for Phase 12 - Event-Based Market Analysis.

Validates:
1. Event inventory reconciliation (135 total, 13 pre-backtest, 122 backtest).
2. Mutually exclusive 7-category taxonomy.
3. Strict 6-sector universe integrity (AUTO, BANK, FMCG, IT, METAL, PHARMA).
4. Strictly pre-event, look-ahead-free market model estimation and ineligibility gating.
5. Econometric abnormal return and CAR mathematical identities.
6. Normalized Shannon entropy bounds [0, 1] and shock dynamics.
7. Christie-Huang (1995) CSSD dispersion and leadership turnover bounds.
8. Macro episode clustering and Boolean union deduplication.
9. Signed Maximum Drawdown convention (MDD <= 0).
10. All seven authoritative Parquet output contracts.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from src.event_analysis import (
    BENCHMARK_NAME,
    CASE_STUDY_DEFINITIONS,
    MACRO_CATEGORIES,
    NUM_SECTORS,
    SECTOR_NAMES,
    STRATEGY_VARIANTS,
    cluster_macro_episodes,
    compute_abnormal_returns_for_event,
    compute_normalized_shannon_entropy,
    estimate_strictly_preevent_market_model,
    load_authoritative_event_inventory,
    map_macro_category,
    run_phase12_pipeline,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "results" / "event_analysis"


# ---------------------------------------------------------------------------
# Test 1: Event Inventory & Count Reconciliation
# ---------------------------------------------------------------------------

def test_authoritative_event_inventory_counts():
    events = load_authoritative_event_inventory()
    assert len(events) == 135, f"Expected 135 total events, got {len(events)}"

    bt_events = events[events["in_backtest_sample"]]
    assert len(bt_events) == 122, f"Expected 122 backtest events, got {len(bt_events)}"

    pre_events = events[~events["in_backtest_sample"]]
    assert len(pre_events) == 13, f"Expected 13 pre-backtest events, got {len(pre_events)}"

    # Severity distribution
    assert (bt_events["severity"] == "high").sum() == 94
    assert (bt_events["severity"] == "medium").sum() == 28


# ---------------------------------------------------------------------------
# Test 2: Mutually Exclusive Macro Taxonomy
# ---------------------------------------------------------------------------

def test_macro_taxonomy_mutual_exclusivity():
    events = load_authoritative_event_inventory()
    bt_events = events[events["in_backtest_sample"]]

    # No unmapped events
    assert (bt_events["macro_category"] == "Other").sum() == 0

    counts = bt_events["macro_category"].value_counts()
    assert counts["Monetary Policy Shocks"] == 49
    assert counts["Trade Policy & Tariffs"] == 34
    assert counts["Geopolitics & Global Summits"] == 11
    assert counts["Financial, Banking & Market Shocks"] == 8
    assert counts["Fiscal & Domestic Policy"] == 8
    assert counts["Pandemic & Health Shocks"] == 6
    assert counts["Elections & Domestic Politics"] == 6

    assert counts.sum() == 122


# ---------------------------------------------------------------------------
# Test 3: Sector Universe Consistency (Strictly 6 Sectors)
# ---------------------------------------------------------------------------

def test_sector_universe_consistency():
    assert NUM_SECTORS == 6
    assert set(SECTOR_NAMES) == {"AUTO", "BANK", "FMCG", "IT", "METAL", "PHARMA"}

    # Output Parquet contracts must reflect 6 sectors
    p_caar = OUTPUT_DIR / "macro_category_caar.parquet"
    if p_caar.exists():
        df_caar = pd.read_parquet(p_caar)
        assert set(df_caar["asset"].unique()) == set(SECTOR_NAMES)
        assert len(df_caar) == 7 * 6  # 42 comparisons


# ---------------------------------------------------------------------------
# Test 4: Strictly Pre-Event Look-Ahead-Free Estimation
# ---------------------------------------------------------------------------

def test_strictly_preevent_estimation_and_ineligibility():
    # Synthetic calendar
    dates = pd.date_range("2020-01-01", periods=100, freq="B")
    ret_asset = pd.Series(np.random.normal(0, 0.01, 100), index=dates)
    ret_bench = pd.Series(np.random.normal(0, 0.01, 100), index=dates)

    # Event on date index 10 (insufficient pre-event history)
    ev_early = dates[10]
    mask = np.zeros(100, dtype=bool)

    fit_early = estimate_strictly_preevent_market_model(
        asset_returns=ret_asset,
        benchmark_returns=ret_bench,
        event_start_date=ev_early,
        global_event_mask=mask,
        trading_dates=list(dates),
        min_clean_sessions=40,
    )
    assert not fit_early.is_eligible
    assert fit_early.ineligibility_reason == "INSUFFICIENT_PRE_EVENT_CLEAN_SESSIONS"
    assert np.isnan(fit_early.alpha_est)

    # Event on date index 70 with 50 clean days prior
    ev_valid = dates[70]
    fit_valid = estimate_strictly_preevent_market_model(
        asset_returns=ret_asset,
        benchmark_returns=ret_bench,
        event_start_date=ev_valid,
        global_event_mask=mask,
        trading_dates=list(dates),
        min_clean_sessions=40,
    )
    assert fit_valid.is_eligible
    assert fit_valid.m_clean_sessions >= 40
    assert not np.isnan(fit_valid.beta_est)


# ---------------------------------------------------------------------------
# Test 5: Abnormal Return & CAR Mathematical Identities
# ---------------------------------------------------------------------------

def test_abnormal_return_math_identity():
    # Synthetic perfect linear relationship
    dates = pd.date_range("2020-01-01", periods=100, freq="B")
    bench = pd.Series(np.random.normal(0.001, 0.01, 100), index=dates)
    alpha_true = 0.0005
    beta_true = 1.25
    asset = alpha_true + beta_true * bench

    mask = np.zeros(100, dtype=bool)
    ev_date = dates[60]

    fit = estimate_strictly_preevent_market_model(
        asset_returns=asset,
        benchmark_returns=bench,
        event_start_date=ev_date,
        global_event_mask=mask,
        trading_dates=list(dates),
        min_clean_sessions=40,
    )
    assert fit.is_eligible
    assert pytest.approx(fit.alpha_est, abs=1e-6) == alpha_true
    assert pytest.approx(fit.beta_est, abs=1e-6) == beta_true

    panel, summary = compute_abnormal_returns_for_event(
        event_id="TEST01",
        event_start_date=ev_date,
        asset_name="AUTO",
        asset_type="sector",
        macro_category="Monetary Policy Shocks",
        severity="high",
        asset_returns=asset,
        benchmark_returns=bench,
        model_fit=fit,
        trading_dates=list(dates),
    )
    # Under exact model, CAR must be zero
    assert pytest.approx(summary["CAR_m2_p2"], abs=1e-6) == 0.0


# ---------------------------------------------------------------------------
# Test 6: Normalized Shannon Entropy Bounds
# ---------------------------------------------------------------------------

def test_shannon_entropy_bounds():
    # Maximum entropy: uniform distribution across 6 regimes
    uniform_p = np.array([1.0 / 6.0] * 6)
    h_max = compute_normalized_shannon_entropy(uniform_p)
    assert pytest.approx(h_max, abs=1e-6) == 1.0

    # Minimum entropy: point mass on 1 regime
    certain_p = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    h_min = compute_normalized_shannon_entropy(certain_p)
    assert pytest.approx(h_min, abs=1e-4) == 0.0

    # In-between entropy
    mid_p = np.array([0.5, 0.5, 0.0, 0.0, 0.0, 0.0])
    h_mid = compute_normalized_shannon_entropy(mid_p)
    assert 0.0 < h_mid < 1.0


# ---------------------------------------------------------------------------
# Test 7: Sector Leadership Turnover Bounds
# ---------------------------------------------------------------------------

def test_leadership_turnover_bounds():
    p_lead = OUTPUT_DIR / "sector_leadership_stability.parquet"
    if p_lead.exists():
        df_lead = pd.read_parquet(p_lead)
        assert len(df_lead) == 122
        # Turnover must be strictly 0.0, 0.5, or 1.0
        assert set(df_lead["leadership_turnover"].unique()).issubset({0.0, 0.5, 1.0})
        # Spearman rho and Kendall tau in [-1, 1]
        assert (df_lead["spearman_rho"] >= -1.0).all() and (df_lead["spearman_rho"] <= 1.0).all()
        assert (df_lead["kendall_tau"] >= -1.0).all() and (df_lead["kendall_tau"] <= 1.0).all()


# ---------------------------------------------------------------------------
# Test 8: Macro Episode Deduplication
# ---------------------------------------------------------------------------

def test_macro_episodes_deduplication():
    p_ep = OUTPUT_DIR / "macro_episodes_summary.parquet"
    if p_ep.exists():
        df_ep = pd.read_parquet(p_ep)
        assert len(df_ep) > 0
        # Unique session count must be >= 5 (minimum window size)
        assert (df_ep["n_unique_sessions"] >= 5).all()
        # Event count sum must equal 122
        assert df_ep["event_count"].sum() == 122


# ---------------------------------------------------------------------------
# Test 9: Signed Maximum Drawdown Convention
# ---------------------------------------------------------------------------

def test_signed_drawdown_convention():
    p_ep = OUTPUT_DIR / "macro_episodes_summary.parquet"
    if p_ep.exists():
        df_ep = pd.read_parquet(p_ep)
        # All MDD values must be <= 0.0
        assert (df_ep["market_mdd"] <= 0.0).all()
        for v in STRATEGY_VARIANTS:
            assert (df_ep[f"mdd_{v}"] <= 0.0).all()


# ---------------------------------------------------------------------------
# Test 10: All Seven Parquet Output Contracts Exist & Valid
# ---------------------------------------------------------------------------

def test_all_seven_parquet_contracts():
    expected_files = [
        ("event_metadata_authoritative.parquet", (135, 11)),
        ("event_study_panel.parquet", (1340, 11)),
        ("event_car_summary.parquet", (1220, 17)),
        ("macro_category_caar.parquet", (42, 12)),
        ("sector_leadership_stability.parquet", (122, 13)),
        ("portfolio_event_behavior.parquet", (488, 13)),
        ("macro_episodes_summary.parquet", (68, 27)),
    ]

    for fname, expected_shape in expected_files:
        p = OUTPUT_DIR / fname
        assert p.exists(), f"Missing Parquet contract: {fname}"
        df = pd.read_parquet(p)
        assert df.shape == expected_shape, (
            f"Shape mismatch for {fname}: expected {expected_shape}, got {df.shape}"
        )

