"""
tests/test_regime_characterisation.py
=====================================
Unit and integration tests for Phase 7 Regime Characterisation & Sector Performance:
1. Aligned price and returns loading (daily and forward 20D, excess returns).
2. Episode segmentation and run-length calculations.
3. Regime profiling and economic naming.
4. Sector performance by regime (look-ahead separation, sample size flags).
5. Sector leadership and defensive candidate identification.
6. Event calendar parsing, alignment, and deduplicated window masks.
7. Event regime association logic and relative frequency ratios.
8. Cross-model comparison and holdout state collapse detection.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from src.regime_characterisation import (
    SECTOR_NAMES,
    BENCHMARK_NAME,
    REGIME_INTERPRETATIONS,
    load_regime_labels,
    load_clean_prices_and_returns,
    calculate_regime_episodes,
    compute_model_regime_profiles,
    compute_sector_performance_by_regime,
    identify_sector_leadership,
    load_and_align_events,
    build_event_windows,
    analyze_event_regime_associations,
    generate_cross_model_comparison,
    compute_hmm_holdout_sector_correlations,
    plot_hmm_holdout_sector_correlations,
    run_phase7_pipeline,
)


# ---------------------------------------------------------------------------
# 1. Price and Return Alignment Tests
# ---------------------------------------------------------------------------

def test_load_clean_prices_and_returns():
    """Verify price data and returns are aligned with exactly 6 sectors + NIFTY50."""
    price_df, daily_ret, fwd_20d = load_clean_prices_and_returns("data")

    # Dimensions and column coverage
    assert price_df.shape[1] == 7
    assert BENCHMARK_NAME in price_df.columns
    for s in SECTOR_NAMES:
        assert s in price_df.columns
        assert f"{s}_Excess" in daily_ret.columns
        assert f"{s}_Excess" in fwd_20d.columns

    # Index properties
    assert isinstance(price_df.index, pd.DatetimeIndex)
    assert price_df.index.is_monotonic_increasing
    assert len(price_df) == 1886

    # Verify excess return math
    test_date = daily_ret.index[50]
    for s in SECTOR_NAMES:
        expected_excess = daily_ret.loc[test_date, s] - daily_ret.loc[test_date, BENCHMARK_NAME]
        actual_excess = daily_ret.loc[test_date, f"{s}_Excess"]
        assert np.isclose(expected_excess, actual_excess, atol=1e-7)

    # Forward returns should have NaNs ONLY at the final 20 rows
    assert fwd_20d.iloc[:-20][BENCHMARK_NAME].isna().sum() == 0
    assert fwd_20d.iloc[-20:][BENCHMARK_NAME].isna().sum() == 20


# ---------------------------------------------------------------------------
# 2. Episode Segmentation Tests
# ---------------------------------------------------------------------------

def test_calculate_regime_episodes():
    """Verify run-length episode segmentation with synthetic sequence."""
    dates = pd.date_range("2021-01-01", periods=10, freq="B")
    labels = pd.Series([0, 0, 0, 1, 1, 0, 2, 2, 2, 2], index=dates)

    ep_df = calculate_regime_episodes(labels)
    assert len(ep_df) == 4
    assert ep_df["regime_id"].tolist() == [0, 1, 0, 2]
    assert ep_df["duration_days"].tolist() == [3, 2, 1, 4]
    assert ep_df["start_date"].iloc[0] == dates[0]
    assert ep_df["end_date"].iloc[0] == dates[2]
    assert ep_df["start_date"].iloc[1] == dates[3]
    assert ep_df["end_date"].iloc[1] == dates[4]


# ---------------------------------------------------------------------------
# 3. Model Regime Profiles Tests
# ---------------------------------------------------------------------------

def test_compute_model_regime_profiles():
    """Verify regime profile calculations on actual Phase 6 labels and features."""
    labels_df = load_regime_labels("results")
    from src.normalization import load_master_feature_dataset
    master_df = load_master_feature_dataset("data")

    profiles = compute_model_regime_profiles(labels_df, master_df)
    assert not profiles.empty
    assert "economic_name" in profiles.columns
    assert "caveats" in profiles.columns

    # Verify HMM training occupancy sums to ~100%
    hmm_train = profiles[(profiles["model"] == "hmm") & (profiles["label_type"] == "filtered_causal") & (profiles["period"] == "train")]
    assert len(hmm_train) == 6
    assert np.isclose(hmm_train["pct_trading_days"].sum(), 100.0, atol=0.1)

    # Verify holdout absence for HMM R1 and R3
    hmm_holdout = profiles[(profiles["model"] == "hmm") & (profiles["label_type"] == "filtered_causal") & (profiles["period"] == "holdout")]
    r1_days = hmm_holdout[hmm_holdout["regime_id"] == 1]["n_trading_days"].values[0]
    r3_days = hmm_holdout[hmm_holdout["regime_id"] == 3]["n_trading_days"].values[0]
    assert r1_days == 0
    assert r3_days == 0


# ---------------------------------------------------------------------------
# 4. Sector Performance Tests
# ---------------------------------------------------------------------------

def test_compute_sector_performance_by_regime():
    """Verify sector performance calculations with strict look-ahead separation."""
    labels_df = load_regime_labels("results")
    price_df, daily_ret, fwd_20d = load_clean_prices_and_returns("data")

    perf = compute_sector_performance_by_regime(labels_df, daily_ret, fwd_20d, price_df=price_df)
    assert not perf.empty
    assert set(perf["return_horizon"].unique()) == {"contemporaneous_daily", "forward_20D"}

    # Verify sample size flags
    assert "reliable" in perf["sample_size_flag"].unique()
    assert "low_sample_unstable" in perf["sample_size_flag"].unique()

    # Verify absent regimes have 0 observations and zero_sample_absent flag
    gmm_holdout_r1 = perf[(perf["model"] == "gmm") & (perf["period"] == "holdout") & (perf["regime_id"] == 1)]
    assert (gmm_holdout_r1["n_observations"] == 0).all()
    assert (gmm_holdout_r1["sample_size_flag"] == "zero_sample_absent").all()


# ---------------------------------------------------------------------------
# 5. Sector Leadership Tests
# ---------------------------------------------------------------------------

def test_identify_sector_leadership():
    """Verify top leaders and bottom laggards are identified per regime."""
    labels_df = load_regime_labels("results")
    price_df, daily_ret, fwd_20d = load_clean_prices_and_returns("data")
    perf = compute_sector_performance_by_regime(labels_df, daily_ret, fwd_20d, price_df=price_df)
    lead = identify_sector_leadership(perf)

    assert not lead.empty
    assert "top_leader_1" in lead.columns
    assert "bottom_laggard_1" in lead.columns
    assert "defensive_candidate" in lead.columns

    # In HMM R4 (Steady Expansion), Metal should be in top leaders
    hmm_train_r4 = lead[(lead["model"] == "hmm") & (lead["label_type"] == "filtered_causal") & (lead["period"] == "train") & (lead["regime_id"] == 4)]
    assert not hmm_train_r4.empty
    leaders = [hmm_train_r4["top_leader_1"].values[0], hmm_train_r4["top_leader_2"].values[0]]
    assert "METAL" in leaders


# ---------------------------------------------------------------------------
# 6. Event Calendar Alignment & Deduplication Tests
# ---------------------------------------------------------------------------

def test_event_calendar_alignment_and_deduplication():
    """Verify event calendar date parsing, alignment to trading calendar, and deduplication."""
    _, daily_ret, _ = load_clean_prices_and_returns("data")
    events = load_and_align_events("data/raw/Events/major_events_2019_2026.csv", daily_ret.index)

    assert len(events) == 135
    assert (events["aligned_start_date"].isin(daily_ret.index)).all()
    assert (events["aligned_end_date"].isin(daily_ret.index)).all()

    # Build windows and verify boolean mask deduplication
    is_event_day, windows_df = build_event_windows(events, daily_ret.index, pre_days=2, post_days=2)
    assert len(is_event_day) == len(daily_ret)
    assert is_event_day.dtype == bool

    # Total event days should be strictly less than sum of individual window lengths due to overlaps
    total_window_days_sum = windows_df["window_trading_days"].sum()
    unique_event_days = is_event_day.sum()
    assert unique_event_days < total_window_days_sum, "Deduplication must reduce total days from overlapping windows"


# ---------------------------------------------------------------------------
# 7. Cross-Model Comparison & Pipeline End-to-End
# ---------------------------------------------------------------------------

def test_cross_model_comparison():
    """Verify cross-model comparison detects GMM holdout collapse and HMM superiority."""
    labels_df = load_regime_labels("results")
    from src.normalization import load_master_feature_dataset
    master_df = load_master_feature_dataset("data")
    _, daily_ret, fwd_20d = load_clean_prices_and_returns("data")

    profiles = compute_model_regime_profiles(labels_df, master_df)
    perf = compute_sector_performance_by_regime(labels_df, daily_ret, fwd_20d)
    lead = identify_sector_leadership(perf)
    cm = generate_cross_model_comparison(profiles, lead)

    assert len(cm) == 3
    gmm_row = cm[cm["model_id"] == "gmm"].iloc[0]
    assert gmm_row["holdout_state_collapse"] == True

    hmm_row = cm[cm["model_id"] == "hmm"].iloc[0]
    assert hmm_row["holdout_state_collapse"] == False
    assert hmm_row["holdout_active_states"] == 4
    assert hmm_row["holdout_absent_states"] == 2


def test_pipeline_artifact_generation():
    """Verify end-to-end pipeline generates all required CSV artifacts and figures."""
    outputs = run_phase7_pipeline("data", "results")
    assert "model_regime_profiles" in outputs
    assert "sector_performance_by_regime" in outputs
    assert "sector_leadership_summary" in outputs
    assert "event_regime_association" in outputs
    assert "cross_model_comparison_summary" in outputs
    assert "hmm_holdout_sector_correlation_matrices" in outputs
    assert "hmm_holdout_sector_correlation_summary" in outputs

    for name, path in [
        ("model_regime_profiles", "results/regime_characterization/regime_profiles/model_regime_profiles.csv"),
        ("sector_performance_by_regime", "results/regime_characterization/sector_performance/sector_performance_by_regime.csv"),
        ("sector_leadership_summary", "results/regime_characterization/sector_leadership/sector_leadership_summary.csv"),
        ("event_regime_association", "results/event_analysis/event_regime_association.csv"),
        ("sector_performance_during_events", "results/event_analysis/sector_performance_during_events.csv"),
        ("cross_model_comparison_summary", "results/reports/cross_model_comparison_summary.csv"),
        ("hmm_holdout_sector_correlation_matrices", "results/regime_characterization/correlations/hmm_holdout_sector_correlation_matrices.csv"),
        ("hmm_holdout_sector_correlation_summary", "results/regime_characterization/correlations/hmm_holdout_sector_correlation_summary.csv"),
        ("hmm_holdout_sector_corr_regime_0", "results/regime_characterization/correlations/hmm_holdout_sector_corr_regime_0.png"),
        ("hmm_holdout_sector_corr_regime_2", "results/regime_characterization/correlations/hmm_holdout_sector_corr_regime_2.png"),
        ("hmm_holdout_sector_corr_regime_4", "results/regime_characterization/correlations/hmm_holdout_sector_corr_regime_4.png"),
        ("hmm_holdout_sector_corr_regime_5", "results/regime_characterization/correlations/hmm_holdout_sector_corr_regime_5.png"),
        ("hmm_holdout_sector_corr_comparison", "results/regime_characterization/correlations/hmm_holdout_sector_corr_comparison.png"),
    ]:
        p = Path(path)
        assert p.exists(), f"Expected artifact {path} does not exist"
        assert p.stat().st_size > 0, f"Artifact {path} is empty"


# ---------------------------------------------------------------------------
# 8. Forward-Return Boundary Regression Tests
# ---------------------------------------------------------------------------

def test_training_fwd_boundary_enforcement():
    """
    Verify that training-period forward_20D returns do NOT use prices from the
    holdout period (2025-01-01 onwards).  After the fix, for every training date
    with a non-NaN forward_20D observation, the t+20 price endpoint must be <=
    TRAIN_END_DATE (2024-12-31).
    """
    price_df, daily_ret, fwd_20d = load_clean_prices_and_returns("data")
    labels_df = load_regime_labels("results")

    TRAIN_END_TS = pd.Timestamp("2024-12-31")
    all_td = price_df.index

    perf = compute_sector_performance_by_regime(
        labels_df, daily_ret, fwd_20d, price_df=price_df
    )

    train_fwd = perf[
        (perf["period"] == "train") & (perf["return_horizon"] == "forward_20D")
    ]
    # n_observations is the count of valid fwd rows used; fetch a reference from labels
    train_labels = labels_df[(labels_df["period"] == "train")]
    train_dates = pd.DatetimeIndex(train_labels["Date"].unique())

    # Derive which training dates have a t+20 endpoint in holdout
    leakage_dates = {
        d for d in train_dates
        if d in all_td and all_td[min(all_td.get_loc(d) + 20, len(all_td) - 1)] > TRAIN_END_TS
    }
    assert len(leakage_dates) == 20, "Expected exactly 20 boundary-leakage dates in training period"

    # All 20 Dec 2024 boundary dates fall in HMM R2 (Low-Volatility Consolidation).
    # Pre-fix n_observations for R2 was 397; post-fix must be 377 (exactly 20 fewer).
    hmm_r2 = train_fwd[
        (train_fwd["model"] == "hmm")
        & (train_fwd["label_type"] == "filtered_causal")
        & (train_fwd["regime_id"] == 2)
        & (train_fwd["sector"] == "BANK")
    ]
    assert not hmm_r2.empty, "HMM R2 causal training forward_20D rows must exist"
    n_obs = hmm_r2["n_observations"].iloc[0]
    assert n_obs == 377, (
        f"HMM R2 forward_20D n_observations ({n_obs}) should be 377 after removing "
        f"20 boundary dates (pre-fix was 397)"
    )


def test_training_fwd_excluded_observation_count():
    """
    Confirm the exact number of excluded training observations matches the 20
    boundary-crossing dates identified by the audit.  All 20 dates are in
    Dec 2024 and their t+20 endpoints fall in Jan 2025 (holdout).
    """
    price_df, daily_ret, fwd_20d = load_clean_prices_and_returns("data")

    TRAIN_END_TS = pd.Timestamp("2024-12-31")
    all_td = price_df.index
    train_dates = all_td[all_td <= TRAIN_END_TS]

    leakage_dates = [
        d for d in train_dates
        if all_td[min(all_td.get_loc(d) + 20, len(all_td) - 1)] > TRAIN_END_TS
    ]
    assert len(leakage_dates) == 20, f"Expected 20 leakage dates, found {len(leakage_dates)}"

    # All leakage dates must fall in December 2024
    for d in leakage_dates:
        assert d.year == 2024 and d.month == 12, (
            f"Unexpected leakage date outside Dec 2024: {d.date()}"
        )

    # The earliest leakage date: t+20 must be in holdout
    first_leak = leakage_dates[0]
    t20 = all_td[all_td.get_loc(first_leak) + 20]
    assert t20 > TRAIN_END_TS, f"t+20 for {first_leak.date()} = {t20.date()} should be in holdout"


def test_holdout_and_contemporaneous_unaffected_by_boundary_fix():
    """
    Boundary enforcement must not alter:
    1. Holdout-period forward_20D return counts (holdout forward returns are untouched).
    2. Contemporaneous daily return counts for any period/model/regime.
    """
    price_df, daily_ret, fwd_20d = load_clean_prices_and_returns("data")
    labels_df = load_regime_labels("results")

    # Run with and without boundary enforcement for comparison
    perf_with_fix = compute_sector_performance_by_regime(
        labels_df, daily_ret, fwd_20d, price_df=price_df
    )
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        perf_no_fix = compute_sector_performance_by_regime(
            labels_df, daily_ret, fwd_20d, price_df=None
        )

    # Contemporaneous rows must be identical
    cont_fix = perf_with_fix[perf_with_fix["return_horizon"] == "contemporaneous_daily"][
        ["model", "label_type", "period", "regime_id", "sector", "n_observations"]
    ].sort_values(["model", "label_type", "period", "regime_id", "sector"]).reset_index(drop=True)
    cont_nofix = perf_no_fix[perf_no_fix["return_horizon"] == "contemporaneous_daily"][
        ["model", "label_type", "period", "regime_id", "sector", "n_observations"]
    ].sort_values(["model", "label_type", "period", "regime_id", "sector"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(cont_fix, cont_nofix, check_like=False)

    # Holdout forward rows must be identical
    hold_fwd_fix = perf_with_fix[
        (perf_with_fix["return_horizon"] == "forward_20D")
        & (perf_with_fix["period"] == "holdout")
    ][["model", "label_type", "regime_id", "sector", "n_observations"]].sort_values(
        ["model", "label_type", "regime_id", "sector"]
    ).reset_index(drop=True)
    hold_fwd_nofix = perf_no_fix[
        (perf_no_fix["return_horizon"] == "forward_20D")
        & (perf_no_fix["period"] == "holdout")
    ][["model", "label_type", "regime_id", "sector", "n_observations"]].sort_values(
        ["model", "label_type", "regime_id", "sector"]
    ).reset_index(drop=True)
    pd.testing.assert_frame_equal(hold_fwd_fix, hold_fwd_nofix, check_like=False)


def test_terminal_nan_rows_excluded_from_forward_returns():
    """
    The last 20 rows of fwd_20d are NaN (no t+20 price available).
    Verify these are never counted as valid observations in any forward_20D row.
    For the holdout period's last regime, n_observations for forward_20D must be
    less than the holdout period's total length by at least 20.
    """
    price_df, daily_ret, fwd_20d = load_clean_prices_and_returns("data")
    labels_df = load_regime_labels("results")

    # Last 20 rows of the full fwd_20d are NaN
    assert fwd_20d.iloc[-20:][BENCHMARK_NAME].isna().all(), (
        "Expected last 20 rows of fwd_20d to be NaN"
    )
    assert not pd.isna(fwd_20d.iloc[-21][BENCHMARK_NAME]), (
        "Row -21 should NOT be NaN (only last 20 are terminal)"
    )

    perf = compute_sector_performance_by_regime(
        labels_df, daily_ret, fwd_20d, price_df=price_df
    )

    # Total holdout trading days
    holdout_labels = labels_df[labels_df["period"] == "holdout"]
    total_holdout_days = holdout_labels["Date"].nunique()  # 422

    # Sum of n_observations over all sectors for one label stream in holdout forward_20D
    hmm_hold_fwd = perf[
        (perf["period"] == "holdout")
        & (perf["return_horizon"] == "forward_20D")
        & (perf["model"] == "hmm")
        & (perf["label_type"] == "filtered_causal")
    ]
    # Any present (non-absent) regime in holdout should have n_obs < total_holdout_days
    # because the last 20 holdout dates have no t+20 price
    present_regimes = hmm_hold_fwd[hmm_hold_fwd["n_observations"] > 0]
    for _, row in present_regimes.iterrows():
        assert row["n_observations"] < total_holdout_days, (
            f"HMM holdout R{row['regime_id']} fwd n_obs ({row['n_observations']}) "
            f">= total_holdout_days ({total_holdout_days}); terminal NaN rows not dropped"
        )


# ---------------------------------------------------------------------------
# 9. HMM Holdout Sector Performance Correlation Tests
# ---------------------------------------------------------------------------

def test_compute_hmm_holdout_sector_correlations():
    """
    Verify calculation of Pearson correlation matrices for HMM causal holdout regimes:
    1. Regime observation counts match holdout ground truth:
       R0: 8 (low_sample_unstable), R1: 0 (absent), R2: 118 (sufficient),
       R3: 0 (absent), R4: 170 (sufficient), R5: 126 (sufficient).
       Total holdout days = 422.
    2. Proper sample size flags assigned.
    3. Pearson correlation matrix mathematical properties:
       - Diagonals are 1.0.
       - Matrices are symmetric (C_ij == C_ji).
       - Values bounded in [-1.0, 1.0].
    4. Financial/empirical properties:
       - R5 (Correction) has higher mean pairwise correlation (~0.496) than R4 (~0.325) and R2 (~0.319).
       - AUTO-BANK correlation in R5 is >= 0.80 (elevated cyclical coupling during selloffs).
    5. Comparison DataFrame contains exactly 15 unique sector pairs.
    """
    price_df, daily_ret, fwd_20d = load_clean_prices_and_returns("data")
    labels_df = load_regime_labels("results")

    res = compute_hmm_holdout_sector_correlations(labels_df, daily_ret, min_obs_threshold=30)

    summary = res["regime_summary_df"]
    matrices_df = res["matrices_df"]
    comp_df = res["comparison_df"]
    regime_mats = res["regime_matrices"]

    # 1. Total holdout days and per-regime counts
    assert summary["n_observations"].sum() == 422, "Total holdout days across all HMM regimes must be 422"

    counts = summary.set_index("regime_id")["n_observations"].to_dict()
    assert counts == {0: 8, 1: 0, 2: 118, 3: 0, 4: 170, 5: 126}

    # 2. Sample size flags
    flags = summary.set_index("regime_id")["sample_size_flag"].to_dict()
    assert flags[0] == "low_sample_unstable"
    assert flags[1] == "absent_in_holdout"
    assert flags[2] == "sufficient"
    assert flags[3] == "absent_in_holdout"
    assert flags[4] == "sufficient"
    assert flags[5] == "sufficient"

    # 3. Mathematical properties of matrices for active regimes
    for k in [0, 2, 4, 5]:
        mat = regime_mats[k]
        assert mat.shape == (6, 6)
        # Check diagonal
        for sec in SECTOR_NAMES:
            assert np.isclose(mat.loc[sec, sec], 1.0), f"R{k} diagonal for {sec} must be 1.0"
        # Check symmetry
        for s1 in SECTOR_NAMES:
            for s2 in SECTOR_NAMES:
                assert np.isclose(mat.loc[s1, s2], mat.loc[s2, s1]), f"R{k} matrix must be symmetric"
                assert -1.0 <= mat.loc[s1, s2] <= 1.0, f"R{k} corr {s1}-{s2} out of bounds"

    # For absent regimes, matrix should be all NaN
    for k in [1, 3]:
        assert regime_mats[k].isna().all().all(), f"Absent regime R{k} matrix must be all NaN"

    # 4. Financial properties: R5 correction correlation surge
    r2_mean = summary.loc[summary["regime_id"] == 2, "mean_pairwise_correlation"].iloc[0]
    r4_mean = summary.loc[summary["regime_id"] == 4, "mean_pairwise_correlation"].iloc[0]
    r5_mean = summary.loc[summary["regime_id"] == 5, "mean_pairwise_correlation"].iloc[0]

    assert r5_mean > r4_mean, f"R5 mean correlation ({r5_mean}) should exceed R4 ({r4_mean})"
    assert r5_mean > r2_mean, f"R5 mean correlation ({r5_mean}) should exceed R2 ({r2_mean})"
    assert np.isclose(r5_mean, 0.4957, atol=0.01)

    # AUTO-BANK correlation in R5 is >= 0.80
    auto_bank_r5 = regime_mats[5].loc["AUTO", "BANK"]
    assert auto_bank_r5 >= 0.80, f"R5 AUTO-BANK correlation ({auto_bank_r5}) should be >= 0.80"

    # 5. Exactly 15 unique pairs in comparison table (6 * 5 / 2 = 15)
    assert len(comp_df) == 15, f"Expected 15 sector pairs, got {len(comp_df)}"
    assert "sector_pair" in comp_df.columns
    assert "R5_minus_R4_shift" in comp_df.columns
    assert "max_regime_sufficient" in comp_df.columns


def test_plot_hmm_holdout_sector_correlations():
    """Verify that individual and comparison heatmap PNG files are created on disk."""
    price_df, daily_ret, fwd_20d = load_clean_prices_and_returns("data")
    labels_df = load_regime_labels("results")

    res = compute_hmm_holdout_sector_correlations(labels_df, daily_ret)
    saved_plots = plot_hmm_holdout_sector_correlations(res, "results")

    for key, path in saved_plots.items():
        assert path.exists(), f"Plot {path} was not created"
        assert path.stat().st_size > 0, f"Plot {path} is 0 bytes"


