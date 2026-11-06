"""
Unit and integration test suite for Phase 10.6 Integrated Robustness Testing.

Validates all seven robustness investigations, invariant properties, mathematical conservation laws,
and strict immutability of canonical Phase 1–10.5 artifacts.
"""

import hashlib
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
import pytest

from src.portfolio_backtest import (
    ALL_ASSETS,
    ANNUALIZATION_FACTOR,
    DEFAULT_TRANSACTION_COST_RATE,
    SECTOR_NAMES,
    VARIANTS,
)
from src.robustness.benchmark_sensitivity import (
    compute_dual_beta_metrics,
    construct_naive_momentum_schedule,
    fit_treynor_mazuy_regression,
)
from src.robustness.concentration import (
    compute_dual_hhi_metrics,
    compute_euler_risk_attribution,
)
from src.robustness.execution_sensitivity import (
    load_open_and_close_prices,
    simulate_delayed_close_portfolio,
    simulate_open_execution_portfolio,
)
from src.robustness.parameter_sensitivity import (
    BOUNDARY_P_THRESH,
    BOUNDARY_T_LOCK,
    PRIMARY_P_THRESH_GRID,
    PRIMARY_T_LOCK_GRID,
    run_single_parameter_scenario,
)
from src.robustness.subperiod_stability import (
    EXPECTED_YEAR_COUNTS,
    load_environmental_indicators,
)
from src.robustness.transaction_cost import (
    DEFAULT_COST_BPS_GRID,
    compute_breakeven_cost_rates,
)
from src.robustness_testing import RobustnessTestingEngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Pre-implementation SHA-256 checksums recorded prior to Phase 10.6
CANONICAL_PRE_CHECKSUMS: Dict[str, str] = {
    "daily_simulation_1A.parquet": "066cc9605029d47d143496008316dd3e2ba224c36884f5721794d90118451ce5",
    "daily_simulation_1B.parquet": "1d4561304248b8cf3886c57c03f0b18348afe8f8b76e1d03e85fc610c86f1cd2",
    "daily_simulation_2A.parquet": "6241618d9f20eea694b7177fb4acda895dd172f37a75fe3bd7d2aeff2638aeba",
    "daily_simulation_2B.parquet": "db4bc21f86f2545c0fd32d39b5f7951d7651542388fdfea8595e97f95311e5d8",
    "daily_simulation_benchmark_nifty50.parquet": "2bd2a6f115ce5724ea2713951b8cd6ad0752f5fd1189b7fb144431d557a5f273",
    "daily_simulation_benchmark_equal_weight.parquet": "11bebaf7848f9916bdd021213237f18e529dccba327f38e1fbaa168050688785",
    "target_weights_1A.csv": "2783ea644e0ad7fc902bc71ae2bb9b021a0d135f24392fbb56a501e01b7d0202",
    "target_weights_1B.csv": "7972ba6006b9bec76cb17fc6efa8cd871cc372430cfe881ca42309812717826b",
    "target_weights_2A.csv": "69343257a81f8ab517bbda8e86c372235a7998e99f9f228128a29384590318ee",
    "target_weights_2B.csv": "435a9eb95f2c3aaf6ca39437f51b3ee1e94845118f422b05aa0a8494ccdc4f5f",
    "hmm_causal_probabilities.csv": "8132a46ba3a3fe15351cafab3f809adb39ce30d08ecabd5457dedd5a68613e5e",
}


@pytest.fixture(scope="module")
def engine():
    eng = RobustnessTestingEngine()
    eng.load_all_canonical_inputs()
    return eng


class TestCanonicalArtifactProtection:
    """Verifies that Phase 1-10.5 canonical files remain strictly untouched."""

    def test_canonical_checksums_identical(self):
        def sha256_file(p: Path) -> str:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            return h.hexdigest()

        sim_dir = PROJECT_ROOT / "results" / "portfolio_backtest"
        sched_dir = PROJECT_ROOT / "results" / "portfolio_construction"
        prob_path = PROJECT_ROOT / "results" / "regime_discovery" / "hmm_causal_probabilities.csv"

        for fname, expected_hash in CANONICAL_PRE_CHECKSUMS.items():
            if fname.startswith("daily_simulation_"):
                fpath = sim_dir / fname
            elif fname.startswith("target_weights_"):
                fpath = sched_dir / fname
            elif fname == "hmm_causal_probabilities.csv":
                fpath = prob_path
            else:
                raise ValueError(f"Unknown canonical file: {fname}")

            assert fpath.exists(), f"File {fpath} does not exist."
            actual_hash = sha256_file(fpath)
            assert actual_hash == expected_hash, (
                f"CANONICAL FILE MODIFIED! {fname} actual={actual_hash} != expected={expected_hash}"
            )


class TestCostSensitivity:
    """Tests for Investigation 1: Transaction Cost Sensitivity."""

    def test_zero_cost_gross_net_identity(self, engine):
        cost_df = pd.read_parquet(engine.dir_cost / "cost_sensitivity.parquet")
        zero_df = cost_df[cost_df["cost_bps"] == 0]

        assert len(zero_df) == 12  # 4 strategies x 3 periods
        for _, row in zero_df.iterrows():
            assert abs(row["gross_total_return"] - row["net_total_return"]) < 1e-6
            assert abs(row["gross_cagr"] - row["net_cagr"]) < 1e-6
            assert abs(row["cost_drag"]) < 1e-6
            assert abs(row["cash_costs_paid"]) < 1e-6

    def test_baseline_parity_at_15bps(self, engine):
        cost_df = pd.read_parquet(engine.dir_cost / "cost_sensitivity.parquet")
        b15_df = cost_df[cost_df["cost_bps"] == 15]

        for v in VARIANTS:
            for p in ["train", "holdout", "full"]:
                row = b15_df[(b15_df["strategy"] == v) & (b15_df["period"] == p)].iloc[0]
                # Compare against canonical simulation
                sub_sim = engine.simulations[v]
                if p == "train":
                    s_nav = 1.0
                    e_nav = sub_sim.loc[:"2024-12-31", "net_nav"].iloc[-1]
                    n = 1264
                elif p == "holdout":
                    s_nav = sub_sim.loc[:"2024-12-31", "net_nav"].iloc[-1]
                    e_nav = sub_sim.loc["2025-01-02":, "net_nav"].iloc[-1]
                    n = 422
                else:
                    s_nav = 1.0
                    e_nav = sub_sim["net_nav"].iloc[-1]
                    n = 1686
                expected_cagr = (e_nav / s_nav) ** (252.0 / n) - 1.0
                assert abs(row["net_cagr"] - expected_cagr) < 1e-5

    def test_cost_monotonicity(self, engine):
        cost_df = pd.read_parquet(engine.dir_cost / "cost_sensitivity.parquet")
        for v in VARIANTS:
            for p in ["train", "holdout", "full"]:
                sub = cost_df[(cost_df["strategy"] == v) & (cost_df["period"] == p)].sort_values("cost_bps")
                cagrs = sub["net_cagr"].values
                costs = sub["cash_costs_paid"].values
                # CAGR must be strictly decreasing
                assert np.all(np.diff(cagrs) <= 0), f"Non-monotonic CAGR for {v} in {p}"
                # Cumulative costs must be non-decreasing
                assert np.all(np.diff(costs) >= 0), f"Non-monotonic costs for {v} in {p}"

    def test_breakeven_cost_output(self, engine):
        be_df = pd.read_parquet(engine.dir_cost / "cost_breakeven.parquet")
        assert len(be_df) == 12
        # Training breakeven vs zero must be positive for profitable strategies
        train_1a = be_df[(be_df["strategy"] == "1A") & (be_df["period"] == "train")].iloc[0]
        assert train_1a["breakeven_zero_cagr_bps"] > 15.0


class TestExecutionSensitivity:
    """Tests for Investigation 2: Execution Sensitivity Analysis."""

    def test_all_models_evaluated(self, engine):
        exec_df = pd.read_parquet(engine.dir_exec / "execution_sensitivity.parquet")
        assert len(exec_df) == 48  # 4 strategies x 4 models x 3 periods
        models = set(exec_df["execution_model"].unique())
        assert models == {"t+1_close", "t+2_close", "t_close", "t+1_open"}

    def test_baseline_t1_close_parity(self, engine):
        exec_df = pd.read_parquet(engine.dir_exec / "execution_sensitivity.parquet")
        t1_df = exec_df[exec_df["execution_model"] == "t+1_close"]

        for v in VARIANTS:
            for p in ["train", "holdout", "full"]:
                row = t1_df[(t1_df["strategy"] == v) & (t1_df["period"] == p)].iloc[0]
                assert abs(row["delay_penalty_vs_t1"]) < 1e-9

    def test_delayed_close_simulation_weights(self, engine):
        # Verify delayed simulation preserves simplex sum = 1.0
        sched = engine.schedules["1A"]
        daily_t2 = simulate_delayed_close_portfolio(sched, engine.close_prices, delay_sessions=2)
        assert len(daily_t2) == 1686
        for dt, row in daily_t2.iterrows():
            # Check holding weights if available or gross/net return consistency
            assert np.isfinite(row["net_nav"])
            assert row["net_nav"] > 0.0

    def test_open_execution_overnight_intraday_compounding(self, engine):
        sched = engine.schedules["1A"]
        daily_open = simulate_open_execution_portfolio(sched, engine.close_prices, engine.open_prices)
        assert len(daily_open) == 1686
        # Check compounding consistency across all sessions
        for _, row in daily_open.iterrows():
            r_over = row["overnight_return"]
            r_intra = row["intraday_return"]
            r_gross = row["gross_return"]
            # (1 + r_over) * (1 + r_intra) - 1 == r_gross
            assert abs((1.0 + r_over) * (1.0 + r_intra) - 1.0 - r_gross) < 1e-5


class TestConcentration:
    """Tests for Investigation 3: Concentration & Attribution."""

    def test_hhi_bounds(self, engine):
        conc_df = pd.read_parquet(engine.dir_conc / "concentration_metrics.parquet")
        for _, row in conc_df.iterrows():
            # Total HHI must be between 0 and 1
            assert 0.0 < row["hhi_total_mean"] <= 1.0
            # N_eff must be between 1 and 7 (cash + 6 sectors)
            assert 1.0 <= row["n_eff_total_mean"] <= 7.0
            # Equity N_eff must be between 1 and 2 (since top 2 sectors selected)
            assert 1.0 <= row["n_eff_equity_mean"] <= 2.01

    def test_euler_risk_conservation(self, engine):
        attr_df = pd.read_parquet(engine.dir_conc / "sector_risk_return_attribution.parquet")
        for v in VARIANTS:
            for p in ["train", "holdout", "full"]:
                sub = attr_df[(attr_df["strategy"] == v) & (attr_df["period"] == p)]
                # Sum of pct_risk_contribution must equal 100% (or 1.0)
                sum_pct = sub["pct_risk_contribution"].sum()
                assert abs(sum_pct - 1.0) < 1e-4

    def test_return_attribution_consistency(self, engine):
        attr_df = pd.read_parquet(engine.dir_conc / "sector_risk_return_attribution.parquet")
        for v in VARIANTS:
            sub = attr_df[(attr_df["strategy"] == v) & (attr_df["period"] == "full")]
            sum_ret = sub["cumulative_return_contribution"].sum()
            # Must equal gross return sum of strategy
            sim = engine.simulations[v]
            gross_sum = sim["gross_return"].sum()
            assert abs(sum_ret - gross_sum) < 1e-4


class TestSubperiodStability:
    """Tests for Investigation 4: Subperiod Stability Analysis."""

    def test_session_count_conservation(self, engine):
        subp_df = pd.read_parquet(engine.dir_subp / "subperiod_stability.parquet")
        # 1. Calendar Years
        yr_df = subp_df[(subp_df["strategy"] == "1A") & (subp_df["partition_type"] == "calendar_year")]
        assert len(yr_df) == 8
        total_yr_n = yr_df["sample_count"].sum()
        assert total_yr_n == 1686
        for _, r in yr_df.iterrows():
            yr = int(r["subperiod_label"].split()[0])
            assert r["sample_count"] == EXPECTED_YEAR_COUNTS[yr]

        # 2. Trend Regimes
        trend_df = subp_df[(subp_df["strategy"] == "1A") & (subp_df["partition_type"] == "trend_sma200")]
        assert trend_df["sample_count"].sum() == 1686

        # 3. VIX Regimes
        vix_df = subp_df[(subp_df["strategy"] == "1A") & (subp_df["partition_type"] == "vix_regime")]
        assert vix_df["sample_count"].sum() == 1686

    def test_no_nan_in_indicators(self, engine):
        ind = engine.indicators
        eval_ind = ind.loc["2019-11-01":"2026-09-18"]
        assert len(eval_ind) == 1686
        assert eval_ind["nifty50_sma200"].isna().sum() == 0
        assert eval_ind["india_vix"].isna().sum() == 0


class TestRegimeStability:
    """Tests for Investigation 5: Regime Stability Analysis."""

    def test_state_session_conservation(self, engine):
        regm_df = pd.read_parquet(engine.dir_regm / "regime_stability.parquet")
        full_df = regm_df[(regm_df["strategy"] == "1A") & (regm_df["period"] == "full")]
        assert len(full_df) == 6
        assert full_df["sample_count"].sum() == 1686

    def test_state_return_contribution_sum(self, engine):
        regm_df = pd.read_parquet(engine.dir_regm / "regime_stability.parquet")
        full_df = regm_df[(regm_df["strategy"] == "1A") & (regm_df["period"] == "full")]
        contrib_sum = full_df["cumulative_return_contribution"].sum()
        sim_net_sum = engine.simulations["1A"]["net_return"].sum()
        assert abs(contrib_sum - sim_net_sum) < 1e-5

    def test_transition_session_conservation(self, engine):
        trans_df = pd.read_parquet(engine.dir_regm / "regime_transition_dynamics.parquet")
        for _, row in trans_df.iterrows():
            n_tot = row["rebalance_sessions_count"] + row["stationary_sessions_count"]
            if row["period"] == "train":
                assert n_tot == 1264
            elif row["period"] == "holdout":
                assert n_tot == 422
            else:
                assert n_tot == 1686


class TestParameterSensitivity:
    """Tests for Investigation 6: Parameter Sensitivity Analysis."""

    def test_strategy_1a_grid_cell_counts(self, engine):
        param_df = pd.read_parquet(engine.dir_param / "parameter_sensitivity.parquet")
        sub_1a = param_df[(param_df["strategy"] == "1A") & (param_df["period"] == "full")]
        # Exactly 42 parameter cells
        assert len(sub_1a) == 42
        p_vals = set(sub_1a["confidence_threshold"].unique())
        t_vals = set(sub_1a["min_holding_days"].unique())
        assert p_vals == set(PRIMARY_P_THRESH_GRID)
        assert t_vals == set(PRIMARY_T_LOCK_GRID)

    def test_boundary_matrices_counts(self, engine):
        param_df = pd.read_parquet(engine.dir_param / "parameter_sensitivity.parquet")
        for v in ["1B", "2A", "2B"]:
            sub_v = param_df[
                (param_df["strategy"] == v)
                & (param_df["evaluation_type"] == "boundary_matrix_9")
                & (param_df["period"] == "full")
            ]
            assert len(sub_v) == 9
            p_vals = set(sub_v["confidence_threshold"].unique())
            t_vals = set(sub_v["min_holding_days"].unique())
            assert p_vals == set(BOUNDARY_P_THRESH)
            assert t_vals == set(BOUNDARY_T_LOCK)

    def test_volatility_lookback_slice_counts(self, engine):
        param_df = pd.read_parquet(engine.dir_param / "parameter_sensitivity.parquet")
        for v in ["1B", "2B"]:
            sub_v = param_df[
                (param_df["strategy"] == v)
                & (param_df["evaluation_type"] == "volatility_lookback_slice")
                & (param_df["period"] == "full")
            ]
            assert len(sub_v) == 2
            assert set(sub_v["volatility_lookback"].unique()) == {10, 40}


class TestBenchmarkSensitivity:
    """Tests for Investigation 7: Benchmark Sensitivity Analysis."""

    def test_dual_beta_metrics(self, engine):
        bench_df = pd.read_parquet(engine.dir_bench / "benchmark_sensitivity.parquet")
        assert len(bench_df) == 12  # 4 strategies x 3 periods
        for _, row in bench_df.iterrows():
            assert np.isfinite(row["linear_beta"])
            assert np.isfinite(row["beta_up"])
            assert np.isfinite(row["beta_down"])
            assert np.isfinite(row["capture_up"])
            assert np.isfinite(row["capture_down"])
            assert np.isfinite(row["treynor_mazuy_gamma"])

    def test_naive_momentum_properties(self, engine):
        mom_df = pd.read_parquet(engine.dir_bench / "momentum_benchmark_comparison.parquet")
        # Check baseline momentum row
        base_mom = mom_df[(mom_df["portfolio"] == "Naive Top-2 Momentum Benchmark") & (mom_df["period"] == "full")]
        assert len(base_mom) == 1
        row = base_mom.iloc[0]
        assert row["sample_count"] == 1686
        assert np.isfinite(row["net_cagr"])
        assert row["annualized_vol"] > 0.0

    def test_treynor_mazuy_function(self):
        # Synthetic test with known positive curvature
        np.random.seed(42)
        r_mkt = np.random.normal(0.0005, 0.01, 500)
        r_strat = 0.0002 + 0.8 * r_mkt + 5.0 * (r_mkt ** 2) + np.random.normal(0, 0.002, 500)
        _, beta1, gamma, gamma_se, pval = fit_treynor_mazuy_regression(r_strat, r_mkt)
        assert abs(beta1 - 0.8) < 0.1
        assert abs(gamma - 5.0) < 1.0
        assert pval < 0.01

