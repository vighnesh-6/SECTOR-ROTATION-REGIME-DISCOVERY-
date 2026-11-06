"""
Phase 10.6 Integrated Robustness Testing Sub-Package.

Exposes domain-specific quantitative engines for all seven robustness investigations:
  1. transaction_cost: Transaction cost sensitivity (0–30 bps) & breakeven analysis.
  2. execution_sensitivity: Discrete execution timing (t+1 Close, t+2 Close, t Close, t+1 Open).
  3. concentration: Dual HHI, N_eff, and Euler component volatility risk attribution.
  4. subperiod_stability: Calendar years, causal NIFTY 50 200d SMA, and training VIX terciles.
  5. regime_stability: HMM state-conditional distributions and rebalance transition drag.
  6. parameter_sensitivity: 42-cell primary grid (Strategy 1A) and boundary matrices (1B, 2A, 2B).
  7. benchmark_sensitivity: Dual-Beta, Up/Down Capture, Treynor-Mazuy, and Naive Momentum.
"""

from src.robustness.transaction_cost import run_cost_sensitivity_analysis
from src.robustness.execution_sensitivity import run_execution_sensitivity_analysis
from src.robustness.concentration import run_concentration_analysis
from src.robustness.subperiod_stability import run_subperiod_stability_analysis
from src.robustness.regime_stability import run_regime_stability_analysis
from src.robustness.parameter_sensitivity import run_parameter_sensitivity_analysis
from src.robustness.benchmark_sensitivity import run_benchmark_sensitivity_analysis

__all__ = [
    "run_cost_sensitivity_analysis",
    "run_execution_sensitivity_analysis",
    "run_concentration_analysis",
    "run_subperiod_stability_analysis",
    "run_regime_stability_analysis",
    "run_parameter_sensitivity_analysis",
    "run_benchmark_sensitivity_analysis",
]

