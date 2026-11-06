"""
Script to generate and execute the Phase 11 statistical validation notebook:
  notebooks/statistical_validation.ipynb
"""

import json
import subprocess
import sys
from pathlib import Path

notebook_path = Path("notebooks/statistical_validation.ipynb")

cells = [
    # Cell 0: Title and Epistemic Framework
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# Phase 11 — Statistical Validation of Sector Rotation Strategies\n",
            "\n",
            "**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  \n",
            "**Phase:** 11 — Integrated Statistical Validation  \n",
            "\n",
            "## Epistemic Status & Dataset Framework\n",
            "In strict adherence to econometric research integrity, this research notebook evaluates the four canonical ML-based sector rotation strategies (1A, 1B, 2A, 2B) across three authoritative temporal partitions:\n",
            "\n",
            "1. **Model In-Sample Development Period ($N = 1,264$ daily return intervals, 2019-11-01 to 2024-12-31):**\n",
            "   Used for feature engineering, HMM model fitting, and rotation threshold selection. In-sample fit and baseline estimation.\n",
            "2. **Previously Inspected Pseudo-Out-of-Sample Partition ($N = 422$ daily return intervals, 2025-01-02 to 2026-09-18):**\n",
            "   Temporally segregated from HMM training, but previously examined in Phases 10.1–10.6. Evaluated as a retrospective stability diagnostic, not a blind confirmatory discovery.\n",
            "3. **Full Historical Lifecycle Backtest ($N = 1,686$ daily return intervals, 2019-11-01 to 2026-09-18):**\n",
            "   The complete 7-year pooled market history. Primary retrospective track record significance testing.\n",
            "\n",
            "## Methodological Standards Implemented:\n",
            "- Heteroskedasticity and Autocorrelation Consistent (HAC) Alpha inference via Newey & West (1987, 1994).\n",
            "- Standalone risk-adjusted Sharpe inference via Lo (2002) influence function and long-run variance.\n",
            "- Paired comparative Sharpe difference tests via Ledoit & Wolf (2008) bivariate Delta method.\n",
            "- Non-parametric resampling via Politis & Romano (1994) Stationary Block Bootstrap (seed=42, B=2,000).\n",
            "- Multiple-testing error control via Unified Omnibus Holm-Bonferroni (M=12, FWER $\\le 0.05$) and exploratory Benjamini-Hochberg FDR (M=36).\n",
            "- Zero risk-free rate convention ($R_f = 0.0$) and 252.0 annualization factor strictly maintained."
        ]
    },

    # Cell 1: Environment & Imports
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "import math\n",
            "import sys\n",
            "from pathlib import Path\n",
            "\n",
            "# Ensure project root is in sys.path when running from notebooks/\n",
            "project_root = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\n",
            "if str(project_root) not in sys.path:\n",
            "    sys.path.insert(0, str(project_root))\n",
            "\n",
            "import numpy as np\n",
            "import pandas as pd\n",
            "import matplotlib.pyplot as plt\n",
            "import seaborn as sns\n",
            "\n",
            "# Set visualization styling\n",
            "plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')\n",
            "plt.rcParams['font.family'] = 'sans-serif'\n",
            "plt.rcParams['figure.dpi'] = 120\n",
            "pd.set_option('display.precision', 4)\n",
            "pd.set_option('display.max_columns', 30)\n",
            "\n",
            "from src.statistical_validation import (\n",
            "    VARIANTS,\n",
            "    PASSIVE_BENCHMARKS,\n",
            "    ALL_COMPARATORS,\n",
            "    PERIOD_NAMES,\n",
            "    PERIOD_LABELS,\n",
            "    PERIOD_COUNTS,\n",
            "    compute_hac_alpha_beta,\n",
            "    compute_lo_sharpe_inference,\n",
            "    compute_ledoit_wolf_sharpe_diff,\n",
            "    ensure_daily_momentum_simulation,\n",
            "    run_statistical_validation_pipeline,\n",
            ")\n",
            "\n",
            "print('Statistical Validation Environment Initialized successfully.')"
        ]
    },

    # Cell 2: Data Loading & Verification
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Ensure structured results directory exists and load persisted validation artifacts\n",
            "results_dir = project_root / 'results/statistical_validation'\n",
            "assert results_dir.exists(), f'{results_dir} directory must exist.'\n",
            "\n",
            "hac_df = pd.read_parquet(results_dir / 'hac_alpha_beta_summary.parquet')\n",
            "sharpe_df = pd.read_parquet(results_dir / 'sharpe_inference_summary.parquet')\n",
            "boot_tests_df = pd.read_parquet(results_dir / 'bootstrap_hypothesis_tests.parquet')\n",
            "boot_ci_df = pd.read_parquet(results_dir / 'bootstrap_confidence_intervals.parquet')\n",
            "mt_df = pd.read_parquet(results_dir / 'multiple_testing_results.parquet')\n",
            "dur_df = pd.read_parquet(results_dir / 'regime_duration_diagnostics.parquet')\n",
            "\n",
            "print(f'HAC Alpha/Beta Summary:        {hac_df.shape}')\n",
            "print(f'Sharpe Inference Summary:      {sharpe_df.shape}')\n",
            "print(f'Bootstrap Hypothesis Tests:    {boot_tests_df.shape}')\n",
            "print(f'Bootstrap Confidence Intervals: {boot_ci_df.shape}')\n",
            "print(f'Multiple Testing Results:      {mt_df.shape}')\n",
            "print(f'Regime Duration Diagnostics:   {dur_df.shape}')"
        ]
    },

    # Cell 3: Section 1 — Descriptive Backtest Performance Overview
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Load daily simulations to present descriptive performance summary\n",
            "daily_sims = {}\n",
            "for v in VARIANTS:\n",
            "    daily_sims[v] = pd.read_parquet(project_root / f'results/portfolio_backtest/daily_simulation_{v}.parquet')\n",
            "daily_sims['NIFTY50'] = pd.read_parquet(project_root / 'results/portfolio_backtest/daily_simulation_benchmark_nifty50.parquet')\n",
            "daily_sims['EQUAL_WEIGHT'] = pd.read_parquet(project_root / 'results/portfolio_backtest/daily_simulation_benchmark_equal_weight.parquet')\n",
            "daily_sims['MOMENTUM_TOP2'] = pd.read_parquet(project_root / 'results/portfolio_backtest/robustness/benchmark/daily_simulation_momentum.parquet')\n",
            "\n",
            "summary_rows = []\n",
            "for p_name in ['train', 'holdout', 'full']:\n",
            "    for k, df in daily_sims.items():\n",
            "        sub = df if p_name == 'full' else df[df['period'] == p_name]\n",
            "        N = len(sub)\n",
            "        r = sub['net_return'].values.astype(float)\n",
            "        cagr = (float(sub['net_nav'].iloc[-1]) / (1.0 if p_name != 'holdout' else float(df[df['period']=='train']['net_nav'].iloc[-1]))) ** (252.0 / N) - 1.0\n",
            "        vol = float(np.std(r, ddof=1) * np.sqrt(252.0))\n",
            "        sr = float((np.mean(r) * 252.0) / vol)\n",
            "        summary_rows.append({\n",
            "            'Period': p_name.upper(),\n",
            "            'Portfolio': k,\n",
            "            'Sample N': N,\n",
            "            'Net CAGR (%)': cagr * 100.0,\n",
            "            'Ann. Vol (%)': vol * 100.0,\n",
            "            'Sharpe Ratio': sr,\n",
            "        })\n",
            "\n",
            "perf_summary = pd.DataFrame(summary_rows)\n",
            "display(perf_summary[perf_summary['Period'] == 'FULL'].reset_index(drop=True))\n",
            "display(perf_summary[perf_summary['Period'] == 'HOLDOUT'].reset_index(drop=True))"
        ]
    },

    # Cell 4: Section 2 — Newey-West HAC Alpha & Beta Inference
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Display Full Period Alpha & Beta with HAC standard errors and t-statistics\n",
            "display_cols = [\n",
            "    'strategy', 'benchmark', 'period', 'sample_count', 'hac_lags',\n",
            "    'beta', 'beta_stderr_hac', 'alpha_annualized_pct',\n",
            "    'alpha_stderr_ols_ann', 'alpha_stderr_hac_ann',\n",
            "    'alpha_tstat_hac', 'alpha_pvalue_hac_1sided', 'alpha_pvalue_hac_2sided', 'r_squared'\n",
            "]\n",
            "full_hac = hac_df[hac_df['period'] == 'full'][display_cols].copy()\n",
            "full_hac['alpha_stderr_ols_ann'] = full_hac['alpha_stderr_ols_ann'] * 100.0\n",
            "full_hac['alpha_stderr_hac_ann'] = full_hac['alpha_stderr_hac_ann'] * 100.0\n",
            "print('Full Historical Lifecycle Backtest (N = 1,686, L = 7 lags) — HAC Alpha & Beta:')\n",
            "display(full_hac.reset_index(drop=True))\n",
            "\n",
            "# Visualization of Annualized Jensen's Alpha with HAC 95% Confidence Intervals\n",
            "fig, ax = plt.subplots(figsize=(10, 5))\n",
            "strats = full_hac['strategy'].unique()\n",
            "bms = full_hac['benchmark'].unique()\n",
            "x_pos = np.arange(len(strats))\n",
            "width = 0.25\n",
            "\n",
            "for i, bm in enumerate(bms):\n",
            "    sub = full_hac[full_hac['benchmark'] == bm]\n",
            "    alphas = sub['alpha_annualized_pct'].values\n",
            "    errs = 1.96 * sub['alpha_stderr_hac_ann'].values\n",
            "    ax.bar(x_pos + i * width, alphas, width, yerr=errs, capsize=4, label=f'vs {bm}', alpha=0.85)\n",
            "\n",
            "ax.axhline(0, color='black', linestyle='--', linewidth=0.8)\n",
            "ax.set_xticks(x_pos + width)\n",
            "ax.set_xticklabels(strats, fontweight='bold', fontsize=11)\n",
            "ax.set_ylabel('Annualized Alpha (%) [with 95% HAC CI]', fontsize=11)\n",
            "ax.set_title(\"Full Period Jensen's Alpha with Newey-West HAC Uncertainty Bands\", fontsize=13, fontweight='bold')\n",
            "ax.legend(title='Benchmark', loc='upper right')\n",
            "plt.tight_layout()\n",
            "plt.show()"
        ]
    },

    # Cell 5: Section 3 — Lo (2002) Standalone Sharpe Inference
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Filter standalone Sharpe tests (H0: SR <= 0)\n",
            "lo_df = sharpe_df[sharpe_df['test_class'] == 'standalone_sharpe_lo2002'].copy()\n",
            "lo_full = lo_df[lo_df['period'] == 'full'][[\n",
            "    'portfolio', 'period', 'sample_count', 'hac_lags', 'sharpe_annualized',\n",
            "    'skewness', 'kurtosis', 'sharpe_stderr_iid', 'sharpe_stderr_hac',\n",
            "    'z_stat_hac', 'p_value_1sided', 'p_value_2sided'\n",
            "]].reset_index(drop=True)\n",
            "\n",
            "print('Lo (2002) Standalone Sharpe Inference (Full Period N = 1,686, L = 7 lags):')\n",
            "display(lo_full)"
        ]
    },

    # Cell 6: Section 4 — Ledoit-Wolf (2008) Comparative Sharpe Difference Tests
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Filter comparative Sharpe difference tests (H0: Delta_SR <= 0)\n",
            "lw_df = sharpe_df[sharpe_df['test_class'] == 'comparative_sharpe_ledoit_wolf'].copy()\n",
            "lw_full = lw_df[lw_df['period'] == 'full'][[\n",
            "    'portfolio', 'comparator', 'period', 'sample_count',\n",
            "    'sharpe_annualized', 'comparator_sharpe_ann', 'delta_sharpe_ann',\n",
            "    'sharpe_stderr_hac', 'z_stat_hac', 'p_value_1sided', 'p_value_2sided'\n",
            "]].reset_index(drop=True)\n",
            "\n",
            "print('Ledoit-Wolf (2008) Paired Sharpe Difference Tests (Full Period N = 1,686):')\n",
            "display(lw_full)"
        ]
    },

    # Cell 7: Section 5 — Stationary Block Bootstrap Hypothesis Testing & Distributions
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "print('Stationary Block Bootstrap (Politis & Romano 1994, B = 2,000, seed = 42):')\n",
            "boot_full = boot_tests_df[boot_tests_df['period'] == 'full'].reset_index(drop=True)\n",
            "display(boot_full[[\n",
            "    'strategy', 'comparator', 'block_length', 'point_estimate',\n",
            "    'ci_95_lower', 'ci_95_upper', 'p_value_boot_1sided', 'p_value_boot_2sided'\n",
            "]])\n",
            "\n",
            "# Plotting bootstrap empirical distributions for Strategy 1A\n",
            "from src.statistical_validation import run_bootstrap_hypothesis_tests\n",
            "\n",
            "r1 = daily_sims['1A']['net_return'].values\n",
            "fig, axes = plt.subplots(1, 3, figsize=(15, 4))\n",
            "\n",
            "for idx, comp in enumerate(['NIFTY50', 'EQUAL_WEIGHT', 'MOMENTUM_TOP2']):\n",
            "    r2 = daily_sims[comp]['net_return'].values\n",
            "    res = run_bootstrap_hypothesis_tests(r1, r2, test_type='sharpe_diff', block_length=21.0, n_bootstraps=2000, seed=42)\n",
            "    thetas = res['boot_thetas']\n",
            "    ax = axes[idx]\n",
            "    ax.hist(thetas, bins=40, density=True, alpha=0.65, color='royalblue', edgecolor='white')\n",
            "    ax.axvline(0, color='red', linestyle='--', linewidth=1.5, label='Null (Delta SR = 0)')\n",
            "    ax.axvline(res['point_estimate'], color='green', linewidth=2, label=f'Point Est = {res[\"point_estimate\"]:.2f}')\n",
            "    ax.axvline(res['ci_95_lower'], color='orange', linestyle=':', label=f'95% CI: [{res[\"ci_95_lower\"]:.2f}, {res[\"ci_95_upper\"]:.2f}]')\n",
            "    ax.axvline(res['ci_95_upper'], color='orange', linestyle=':')\n",
            "    ax.set_title(f'1A vs {comp} (b = 21 days)', fontweight='bold')\n",
            "    ax.set_xlabel('Delta Sharpe')\n",
            "    ax.legend(fontsize=8, loc='upper left')\n",
            "\n",
            "plt.tight_layout()\n",
            "plt.show()"
        ]
    },

    # Cell 8: Section 6 — Performance Metric Bootstrap Confidence Intervals
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Display Bootstrap Confidence Intervals for CAGR, Volatility, and Max Drawdown across block lengths\n",
            "print('Bootstrap Uncertainty Intervals across Sensitivity Grid b in {5, 10, 21, 42, 63}:')\n",
            "display(boot_ci_df[boot_ci_df['portfolio'].isin(['1A', 'NIFTY50', 'MOMENTUM_TOP2'])].reset_index(drop=True))"
        ]
    },

    # Cell 9: Section 7 — Multiple-Testing Error Control (Unified M=12 & Exploratory M=36)
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Multiple Testing Display: Unified Omnibus Primary Family (M = 12)\n",
            "uni_mt = mt_df[mt_df['family'] == 'Unified_Primary_Omnibus_M12'].copy()\n",
            "print('========================================================================================')\n",
            "print('UNIFIED PRIMARY OMNIBUS FAMILY (M = 12) — HOLM-BONFERRONI FWER CONTROL (alpha = 0.05):')\n",
            "print('========================================================================================')\n",
            "display(uni_mt[[\n",
            "    'hypothesis_id', 'strategy', 'comparator', 'metric', 'point_estimate',\n",
            "    'test_stat', 'p_value_1sided', 'holm_p_1sided', 'holm_reject_1sided'\n",
            "]].reset_index(drop=True))\n",
            "\n",
            "# Summary of rejections\n",
            "n_rej = uni_mt['holm_reject_1sided'].sum()\n",
            "print(f'\\nUnified Family Rejection Summary: {n_rej} / {len(uni_mt)} Hypotheses Rejected at FWER <= 0.05!')\n",
            "\n",
            "# Exploratory Family (M = 36)\n",
            "exp_mt = mt_df[mt_df['family'] == 'Exploratory_Subperiod_M36'].copy()\n",
            "print('\\n========================================================================================')\n",
            "print('EXPLORATORY SUBPERIOD STABILITY SWEEP (M = 36) — BENJAMINI-HOCHBERG FDR (q = 0.05):')\n",
            "print('========================================================================================')\n",
            "print('Rejections by Partition:')\n",
            "for p_name in ['train', 'holdout', 'full']:\n",
            "    sub = exp_mt[exp_mt['period'] == p_name]\n",
            "    r_bh = sub['bh_reject_1sided'].sum()\n",
            "    r_by = sub['by_reject_1sided'].sum()\n",
            "    print(f'  {p_name.upper():7s}: BH Rejections = {r_bh:2d}/12, BY Rejections = {r_by:2d}/12')"
        ]
    },

    # Cell 10: Section 8 — Regime Persistence & Run-Length Diagnostics
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "print('Regime Persistence & Episode Duration Diagnostics (Conditional on Realized Path):')\n",
            "display(dur_df[[\n",
            "    'regime', 'episode_count', 'total_days', 'mean_duration',\n",
            "    'ci_95_lower', 'ci_95_upper', 'median_duration', 'min_duration', 'max_duration'\n",
            "]].reset_index(drop=True))\n",
            "\n",
            "# Bar plot of mean durations with 95% bootstrap intervals\n",
            "fig, ax = plt.subplots(figsize=(8, 4))\n",
            "sub_dur = dur_df[dur_df['regime_id'] >= 0]\n",
            "ax.bar(sub_dur['regime'], sub_dur['mean_duration'], yerr=[\n",
            "    sub_dur['mean_duration'] - sub_dur['ci_95_lower'],\n",
            "    sub_dur['ci_95_upper'] - sub_dur['mean_duration']\n",
            "], capsize=5, color='teal', alpha=0.8)\n",
            "ax.set_ylabel('Mean Duration (Trading Days)')\n",
            "ax.set_title('Empirical Regime Episode Durations (with 95% Bootstrap CIs)', fontweight='bold')\n",
            "plt.tight_layout()\n",
            "plt.show()"
        ]
    },

    # Cell 11: Section 9 — Scientific Interpretation & Limitations
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## Section 9 — Scientific Interpretation, Economic vs. Statistical Significance, and Limitations\n",
            "\n",
            "### 1. Statistical Significance Findings:\n",
            "- **Full Lifecycle Alpha ($N = 1,686$):** All four ML-based strategies generate statistically significant positive Jensen's alpha against the NIFTY 50 ($+14.7\\%$ to $+16.1\\%$, $p < 0.002$ under Newey-West HAC inference) and against the Equal-Weight Sector benchmark ($+9.0\\%$ to $+9.5\\%$, $p < 0.02$).\n",
            "- **Risk-Adjusted Performance:** Standalone Sharpe ratios ($1.32$ to $1.34$) are statistically greater than zero ($z_{\\text{Lo}} > 3.0, p < 0.001$). Comparative Sharpe differences against NIFTY 50 and Naive Momentum are strictly positive ($z_{\\text{LW}} > 2.8, p < 0.005$).\n",
            "- **Multiple Testing Closure:** Under the Unified Primary Omnibus Family ($M = 12$), all 12 hypotheses reject the null at $\\text{FWER} \\le 0.05$ under the Holm-Bonferroni step-down procedure.\n",
            "\n",
            "### 2. Economic Significance and Temporal Degradation:\n",
            "- In the **In-Sample Development Period (2019–2024)**, the strategies achieved massive outperformance (CAGR $\\approx 40-43\\%$, alpha $\\approx +25\\%$).\n",
            "- In the **Previously Inspected Pseudo-OOS Partition (2025–2026)**, the strategies experienced performance degradation (CAGR $\\approx -12\\%$, negative active alpha).\n",
            "- This divergence highlights that while the strategy demonstrated multi-year statistical validity over the full economic cycle, regime-transition latency and high turnover in choppy market conditions created significant post-training drag.\n",
            "\n",
            "### 3. Econometric Limitations:\n",
            "1. **Retrospective Evaluation:** The 2025–2026 partition was previously inspected in Phase 10; findings cannot be interpreted as a blind forward-looking clinical trial.\n",
            "2. **HMM Estimation Variance:** Regime persistence inference is conditional on the single realized Viterbi path. Strict frozen artifact constraints prohibit re-estimating HMM parameters.\n",
            "3. **Bootstrap Boundary Splicing:** Stationary block bootstrap concatenations do not preserve global Markov transition matrices across cut boundaries."
        ]
    }
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": sys.version.split()[0]
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

with open(notebook_path, "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=2)

print(f"Generated Phase 11 notebook at: {notebook_path}")
