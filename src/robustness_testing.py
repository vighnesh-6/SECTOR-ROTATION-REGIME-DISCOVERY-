"""
Phase 10.6 Central Orchestration Engine — Integrated Robustness Testing.

Coordinates, executes, and persists all seven approved robustness investigations:
  1. Transaction Cost Sensitivity (0 to 30 bps)
  2. Execution Sensitivity (t+1 Close, t+2 Close, t Close, t+1 Open)
  3. Portfolio Concentration (Dual HHI, N_eff, Euler risk & return attribution)
  4. Subperiod Stability (Calendar years, NIFTY 50 200d SMA, fixed training VIX terciles)
  5. Regime Stability (State-conditional distributions & transition drag)
  6. Parameter & Model Sensitivity (Strategy 1A 42-cell grid + boundary matrices)
  7. Benchmark Sensitivity (Dual-Beta, Capture Ratios, TM Timing, Naive Momentum)

Strict Constraint: All outputs are persisted to results/portfolio_backtest/robustness/*/
with zero modification to canonical Phase 1–10.5 artifacts.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from src.portfolio_backtest import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PRICE_DIR,
    DEFAULT_PROB_PATH,
    DEFAULT_SCHEDULE_DIR,
    SECTOR_NAMES,
    VARIANTS,
    load_backtest_inputs,
)
from src.robustness.benchmark_sensitivity import run_benchmark_sensitivity_analysis
from src.robustness.concentration import run_concentration_analysis
from src.robustness.execution_sensitivity import (
    load_open_and_close_prices,
    run_execution_sensitivity_analysis,
)
from src.robustness.parameter_sensitivity import run_parameter_sensitivity_analysis
from src.robustness.regime_stability import run_regime_stability_analysis
from src.robustness.subperiod_stability import (
    load_environmental_indicators,
    run_subperiod_stability_analysis,
)
from src.robustness.transaction_cost import (
    compute_breakeven_cost_rates,
    run_cost_sensitivity_analysis,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("RobustnessTestingEngine")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROBUSTNESS_DIR = PROJECT_ROOT / "results" / "portfolio_backtest" / "robustness"


class RobustnessTestingEngine:
    """
    Central orchestration engine managing input loading, invariant verification,
    cross-investigation execution, and structured Parquet catalog persistence.
    """

    def __init__(
        self,
        base_dir: Optional[Union[str, Path]] = None,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else PROJECT_ROOT
        self.output_dir = Path(output_dir) if output_dir is not None else DEFAULT_ROBUSTNESS_DIR

        # Subdirectory layout
        self.dir_cost = self.output_dir / "transaction_cost"
        self.dir_exec = self.output_dir / "execution"
        self.dir_conc = self.output_dir / "concentration"
        self.dir_subp = self.output_dir / "subperiod"
        self.dir_regm = self.output_dir / "regime"
        self.dir_param = self.output_dir / "parameter_sensitivity"
        self.dir_bench = self.output_dir / "benchmark"

        for d in [
            self.dir_cost,
            self.dir_exec,
            self.dir_conc,
            self.dir_subp,
            self.dir_regm,
            self.dir_param,
            self.dir_bench,
        ]:
            d.mkdir(parents=True, exist_ok=True)

        self.schedules: Dict[str, pd.DataFrame] = {}
        self.simulations: Dict[str, pd.DataFrame] = {}
        self.nifty50_simulation: Optional[pd.DataFrame] = None
        self.equal_weight_simulation: Optional[pd.DataFrame] = None
        self.close_prices: Optional[pd.DataFrame] = None
        self.open_prices: Optional[pd.DataFrame] = None
        self.causal_probs: Optional[pd.DataFrame] = None
        self.indicators: Optional[pd.DataFrame] = None

    def load_all_canonical_inputs(self) -> None:
        """
        Load all required canonical inputs without modifying source files.
        Verifies expected session counts and schema integrity.
        """
        logger.info("Loading canonical simulation parquets, schedules, and price data...")

        # 1. Canonical daily simulations
        sim_dir = self.base_dir / "results" / "portfolio_backtest"
        for v in VARIANTS:
            fpath = sim_dir / f"daily_simulation_{v}.parquet"
            if not fpath.exists():
                raise FileNotFoundError(f"Missing canonical simulation parquet: {fpath}")
            self.simulations[v] = pd.read_parquet(fpath)

        p50_fpath = sim_dir / "daily_simulation_benchmark_nifty50.parquet"
        ew_fpath = sim_dir / "daily_simulation_benchmark_equal_weight.parquet"
        self.nifty50_simulation = pd.read_parquet(p50_fpath)
        self.equal_weight_simulation = pd.read_parquet(ew_fpath)

        # 2. Canonical target weight schedules
        sched_dir = self.base_dir / "results" / "portfolio_construction"
        for v in VARIANTS:
            fpath = sched_dir / f"target_weights_{v}.csv"
            if not fpath.exists():
                raise FileNotFoundError(f"Missing canonical schedule file: {fpath}")
            self.schedules[v] = pd.read_csv(fpath, parse_dates=["Date"]).set_index("Date")

        # 3. Prices (Close and Open)
        price_dir = self.base_dir / "data" / "processed" / "aligned"
        self.close_prices, self.open_prices = load_open_and_close_prices(price_dir)

        # 4. Causal probabilities
        prob_path = self.base_dir / "results" / "regime_discovery" / "hmm_causal_probabilities.csv"
        self.causal_probs = pd.read_csv(prob_path, parse_dates=["Date"]).set_index("Date")

        # 5. Environmental indicators (Causal SMA200 and VIX regimes)
        self.indicators = load_environmental_indicators(price_dir)

        # Validate interval count (1,686)
        for v, df in self.simulations.items():
            if len(df) != 1686:
                raise ValueError(f"Simulation {v} has {len(df)} intervals (expected 1,686).")

        logger.info("All canonical inputs loaded and verified successfully.")

    def run_all_investigations(
        self,
        export_parquet: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute all seven investigations in sequence and return catalog of DataFrames.
        """
        if not self.simulations:
            self.load_all_canonical_inputs()

        results: Dict[str, Any] = {}

        # -------------------------------------------------------------
        # Investigation 1: Transaction Cost Sensitivity
        # -------------------------------------------------------------
        logger.info("Running Investigation 1: Transaction Cost Sensitivity...")
        cost_df = run_cost_sensitivity_analysis(
            schedules=self.schedules,
            price_df=self.close_prices,
            output_dir=self.dir_cost if export_parquet else None,
        )
        results["transaction_cost"] = cost_df

        # Benchmark CAGR dict for breakeven calculation
        bm_cagrs = {
            "NIFTY50": {
                "train": float((self.nifty50_simulation.loc[:"2024-12-31", "net_nav"].iloc[-1]) ** (252.0 / 1264) - 1.0),
                "holdout": float(
                    (self.nifty50_simulation.loc["2025-01-02":, "net_nav"].iloc[-1] /
                     self.nifty50_simulation.loc[:"2024-12-31", "net_nav"].iloc[-1]) ** (252.0 / 422) - 1.0
                ),
                "full": float((self.nifty50_simulation["net_nav"].iloc[-1]) ** (252.0 / 1686) - 1.0),
            },
            "EQUAL_WEIGHT": {
                "train": float((self.equal_weight_simulation.loc[:"2024-12-31", "net_nav"].iloc[-1]) ** (252.0 / 1264) - 1.0),
                "holdout": float(
                    (self.equal_weight_simulation.loc["2025-01-02":, "net_nav"].iloc[-1] /
                     self.equal_weight_simulation.loc[:"2024-12-31", "net_nav"].iloc[-1]) ** (252.0 / 422) - 1.0
                ),
                "full": float((self.equal_weight_simulation["net_nav"].iloc[-1]) ** (252.0 / 1686) - 1.0),
            },
        }
        breakeven_df = compute_breakeven_cost_rates(cost_df, benchmark_cagrs=bm_cagrs)
        results["cost_breakeven"] = breakeven_df
        if export_parquet:
            breakeven_df.to_parquet(self.dir_cost / "cost_breakeven.parquet", index=False)

        # -------------------------------------------------------------
        # Investigation 2: Execution Sensitivity
        # -------------------------------------------------------------
        logger.info("Running Investigation 2: Execution Sensitivity...")
        exec_df = run_execution_sensitivity_analysis(
            schedules=self.schedules,
            close_df=self.close_prices,
            open_df=self.open_prices,
            output_dir=self.dir_exec if export_parquet else None,
        )
        results["execution"] = exec_df

        # -------------------------------------------------------------
        # Investigation 3: Portfolio Concentration
        # -------------------------------------------------------------
        logger.info("Running Investigation 3: Portfolio Concentration & Risk Attribution...")
        conc_summary_df, conc_attr_df = run_concentration_analysis(
            simulations=self.simulations,
            output_dir=self.dir_conc if export_parquet else None,
        )
        results["concentration_summary"] = conc_summary_df
        results["concentration_attribution"] = conc_attr_df

        # -------------------------------------------------------------
        # Investigation 4: Subperiod Stability
        # -------------------------------------------------------------
        logger.info("Running Investigation 4: Subperiod Stability...")
        subp_df = run_subperiod_stability_analysis(
            simulations=self.simulations,
            nifty50_simulation=self.nifty50_simulation,
            indicators_df=self.indicators,
            output_dir=self.dir_subp if export_parquet else None,
        )
        results["subperiod"] = subp_df

        # -------------------------------------------------------------
        # Investigation 5: Regime Stability
        # -------------------------------------------------------------
        logger.info("Running Investigation 5: Regime Stability & Transition Dynamics...")
        regm_df, trans_df = run_regime_stability_analysis(
            simulations=self.simulations,
            output_dir=self.dir_regm if export_parquet else None,
        )
        results["regime_stability"] = regm_df
        results["regime_transitions"] = trans_df

        # -------------------------------------------------------------
        # Investigation 6: Parameter & Model Sensitivity
        # -------------------------------------------------------------
        logger.info("Running Investigation 6: Parameter & Model Sensitivity Grid...")
        param_df = run_parameter_sensitivity_analysis(
            prob_df=self.causal_probs,
            price_df=self.close_prices,
            output_dir=self.dir_param if export_parquet else None,
        )
        results["parameter_sensitivity"] = param_df

        # -------------------------------------------------------------
        # Investigation 7: Benchmark Sensitivity
        # -------------------------------------------------------------
        logger.info("Running Investigation 7: Benchmark Sensitivity & Naive Momentum Comparator...")
        dual_df, mom_df = run_benchmark_sensitivity_analysis(
            simulations=self.simulations,
            nifty50_simulation=self.nifty50_simulation,
            price_df=self.close_prices,
            output_dir=self.dir_bench if export_parquet else None,
        )
        results["benchmark_sensitivity"] = dual_df
        results["momentum_comparison"] = mom_df

        logger.info("All seven investigations completed successfully.")
        return results


def run_pipeline() -> None:
    """Entrypoint to execute the full Phase 10.6 robustness testing pipeline."""
    engine = RobustnessTestingEngine()
    engine.load_all_canonical_inputs()
    engine.run_all_investigations(export_parquet=True)
    logger.info(f"Phase 10.6 robustness outputs saved to: {engine.output_dir}")


if __name__ == "__main__":
    run_pipeline()
