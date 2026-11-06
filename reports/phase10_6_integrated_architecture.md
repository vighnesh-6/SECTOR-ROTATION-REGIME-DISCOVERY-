# Phase 10.6 — Final Integrated Robustness Testing Architecture Specification

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Phase:** 10.6 — Integrated Robustness Testing  
**Document Type:** Final Architectural Specification & Implementation Blueprint  
**Status:** COMPLETE & FINALIZED — AWAITING USER APPROVAL TO BEGIN IMPLEMENTATION  
**Execution Mode:** STRICTLY READ-ONLY REVIEW (No Implementation Started)  

---

## 1. Executive Summary & Architectural Mandate

Phase 10.6 establishes the comprehensive robustness and sensitivity evaluation of the four canonical sector rotation strategies (1A, 1B, 2A, 2B) and their passive benchmarks across the 1,686 daily return sessions (`2019-11-01` to `2026-09-18`).

### The Core Architectural Mandate:
**Phase 10.6 will be implemented as ONE integrated, modular quantitative framework covering all seven investigations—not seven disconnected scripts or mini-projects.**

This architecture establishes:
1. **A Modular Sub-Package under `src/robustness/`:** Seven focused, highly cohesive modules handling domain-specific analytical primitives and simulation algorithms.
2. **A Central Orchestrator in `src/robustness_testing.py`:** A master orchestration class that coordinates input ingestion, dispatches investigation workflows, validates mathematical invariants, and persists structured Parquet datasets.
3. **An Integrated Research Notebook in `notebooks/10_robustness_testing.ipynb`:** Serving strictly as the presentation, visualization, and diagnostic dashboard layer without containing raw algorithmic business logic.
4. **A Comprehensive Pytest Suite in `tests/test_robustness_testing.py`:** Enforcing 100% baseline parity, mathematical identities, causal correctness, and canonical artifact immutability.
5. **A Partitioned Parquet Directory Structure:** Partitioning all numerical artifacts into dedicated investigation subdirectories under `results/portfolio_backtest/robustness/`.
6. **A Consolidated Markdown Report in `reports/phase10_6_robustness_testing.md`:** Delivering the definitive empirical findings, stress test topography, and research sign-off.

---

## 2. Mandatory Target Directory & File Structure

The implementation will strictly follow the specified repository hierarchy:

```text
src/
├── robustness_testing.py                       # Master orchestrator & public API
└── robustness/                                 # Dedicated investigation sub-package
    ├── __init__.py                             # Package exports and shared typing
    ├── transaction_cost.py                     # Investigation 1: 0–30 bps sensitivity & breakeven
    ├── execution_sensitivity.py                # Investigation 2: t+1, t+2, t Close, t+1 Open models
    ├── concentration.py                        # Investigation 3: Dual HHI, N_eff, Euler risk attribution
    ├── subperiod_stability.py                  # Investigation 4: Calendar years, SMA bull/bear, VIX terciles
    ├── regime_stability.py                     # Investigation 5: HMM state-conditional performance & transition drag
    ├── parameter_sensitivity.py                # Investigation 6: 42-cell 1A grid + boundary matrices
    └── benchmark_sensitivity.py                # Investigation 7: Dual Beta, TM curvature, Naive Momentum

notebooks/
└── 10_robustness_testing.ipynb                 # Integrated presentation & visual diagnostic dashboard

results/
└── portfolio_backtest/
    └── robustness/                             # Canonical robustness output directory
        ├── transaction_cost/                   # Investigation 1 Parquet outputs
        ├── execution/                          # Investigation 2 Parquet outputs
        ├── concentration/                      # Investigation 3 Parquet outputs
        ├── subperiod/                          # Investigation 4 Parquet outputs
        ├── regime/                             # Investigation 5 Parquet outputs
        ├── parameter_sensitivity/              # Investigation 6 Parquet outputs
        └── benchmark/                          # Investigation 7 Parquet outputs

reports/
└── phase10_6_robustness_testing.md             # Consolidated final analytical research report

tests/
└── test_robustness_testing.py                  # Centralized unit and integration test suite
```

---

## 3. Detailed Component Architecture & Responsibilities

### 3.1 Central Orchestrator: `src/robustness_testing.py`
The top-level orchestrator serves as the primary gateway for running the complete robustness test suite programmatically or from the command line/notebook.

```python
class RobustnessTestingEngine:
    """
    Central orchestration engine for Phase 10.6 Robustness Testing.
    Coordinates canonical input loading, validation, batch execution of all
    seven investigation modules, and structured Parquet persistence.
    """
    def __init__(
        self,
        base_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        ...

    def load_canonical_inputs(self) -> Dict[str, Any]:
        """Loads and verifies frozen schedules, simulation parquets, prices, and causal probabilities."""
        ...

    def run_all_investigations(self) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Executes Investigations 1 through 7 in topological sequence."""
        ...

    def export_all_parquet_catalogs(self) -> Dict[str, List[Path]]:
        """Persists all DataFrames to their respective subdirectories under results/.../robustness/."""
        ...
```

### 3.2 Modular Investigation Sub-Package: `src/robustness/`

#### 1. `src/robustness/transaction_cost.py` (Investigation 1)
* **Responsibility:** Evaluates cost drag, capital preservation breakeven, and benchmark hurdle breakeven across cost rates $\in \{0, 5, 10, 15, 20, 25, 30 \text{ bps}\}$.
* **Key Function:** `run_cost_sensitivity_analysis(schedules, price_df, cost_grid, variants) -> pd.DataFrame`.
* **Turnover Mechanics:** Drift-adjusted one-way turnover:
  $$TO_{\text{one-way}, t} = 0.5 \sum_{i=1}^K |w_{\text{target}, i, t} - w_{\text{drift}, i, t}|$$
* **Fee Formulation:** $TC_t = \text{NAV}_{\text{pre}, t} \times TO_{\text{one-way}, t} \times \text{cost\_rate}$. 15 bps on one-way turnover is mathematically equivalent to 7.5 bps on total two-way volume ($2 \times TO$).
* **Output Path:** `results/portfolio_backtest/robustness/transaction_cost/cost_sensitivity.parquet`.

#### 2. `src/robustness/execution_sensitivity.py` (Investigation 2)
* **Responsibility:** Implements the four discrete execution timing models with full state tracking, holdings drift, and actual turnover (no return shifting shortcuts).
* **Models Evaluated:**
  1. `Model A (Baseline)`: $t+1$ Close execution at price $P_{\text{close}, t+1}$.
  2. `Model B (Operational Delay)`: $t+2$ Close execution at price $P_{\text{close}, t+2}$.
  3. `Model C (Zero-Latency Bound)`: $t$ Close instantaneous execution at price $P_{\text{close}, t}$.
  4. `Model D (Next-Day Open)`: $t+1$ Open execution. Rebalances at 09:15 IST; compounds overnight gap return on drifted holdings and intraday return on target holdings:
     $$r_{\text{gap}, t+1} = \sum w_{\text{hold}, i, t} \left(\frac{P_{\text{open}, i, t+1}}{P_{\text{close}, i, t}} - 1\right), \quad r_{\text{day}, t+1} = \sum w_{\text{target}, i} \left(\frac{P_{\text{close}, i, t+1}}{P_{\text{open}, i, t+1}} - 1\right)$$
* **Microstructure Limitation:** Daily OHLCV data cannot support continuous intraday limit order queues or VWAP/TWAP schedules; continuous execution is explicitly declared out of scope.
* **Output Path:** `results/portfolio_backtest/robustness/execution/execution_sensitivity.parquet`.

#### 3. `src/robustness/concentration.py` (Investigation 3)
* **Responsibility:** Evaluates sectoral exposure concentration and separates arithmetic return attribution from Euler marginal risk attribution.
* **Key Metrics:**
  - **Total Portfolio HHI:** $HHI_{\text{total}} = \sum w_{\text{sector}, i}^2 + w_{\text{cash}}^2$ and $N_{\text{eff, total}} = 1 / HHI_{\text{total}}$ (balance sheet concentration).
  - **Equity-Only Sector HHI:** $HHI_{\text{equity}} = \sum \tilde{w}_i^2$ where $\tilde{w}_i = w_i / (1 - w_{\text{cash}})$ and $N_{\text{eff, equity}} = 1 / HHI_{\text{equity}}$ (pure sector diversification).
  - **Return Attribution:** $\text{contrib}_{i, t} = w_{\text{hold}, i, t} \times r_{i, t}$ (additive sum).
  - **Euler Risk Attribution (Component Volatility):** Using trailing 60-day covariance $\mathbf{\Sigma}_t$:
    $$\text{RC}_{i, t} = w_{i, t} \frac{(\mathbf{\Sigma}_t \mathbf{w}_t)_i}{\sigma_p}, \quad \sum_{i=1}^K \text{RC}_i = \sigma_p, \quad \% \text{RC}_i = \frac{\text{RC}_i}{\sigma_p}$$
* **Output Paths:**
  - `results/portfolio_backtest/robustness/concentration/concentration_metrics.parquet`
  - `results/portfolio_backtest/robustness/concentration/sector_risk_return_attribution.parquet`

#### 4. `src/robustness/subperiod_stability.py` (Investigation 4)
* **Responsibility:** Evaluates strategy stability across objective, exogenous market partitions without look-ahead bias.
* **Partitions Evaluated:**
  1. **Calendar Years (Reconciled Empirical Intervals):**
     - 2019: $N = 41$ (Partial, 2 Months: 2019-11-01 to 2019-12-31; 42 price sessions starting 2019-10-31 Date 0).
     - 2020: $N = 249$ (Full Year).
     - 2021: $N = 238$ (Full Year).
     - 2022: $N = 247$ (Full Year).
     - 2023: $N = 245$ (Full Year).
     - 2024: $N = 244$ (Full Year).
     - 2025: $N = 247$ (Previously Examined Holdout Part 1).
     - 2026: $N = 175$ (Previously Examined Holdout Part 2, through 2026-09-18).
     - *Total:* $41 + 249 + 238 + 247 + 245 + 244 + 247 + 175 = \mathbf{1,686 \text{ return intervals}}$.
  2. **Causal Trend Classification (NIFTY 50 200-day SMA):**
     - Historical prices start on `2019-01-02` (exactly 200 warm-up sessions before Date 0).
     - SMA is fully warmed up on Day 1; **zero evaluation sessions dropped**.
     - Bull if $P_t > \text{SMA}_{200}(t)$; Bear if $P_t \le \text{SMA}_{200}(t)$.
  3. **Volatility Regimes (Fixed Training VIX Cutoffs):**
     - Low VIX: $< 13.0$ (lower quartile of training period).
     - Normal VIX: $13.0 \le \text{VIX} < 18.0$ (interquartile training range).
     - High VIX: $\ge 18.0$ (upper quartile of training period).
     - Cutoffs are strictly fixed to training data and never updated using holdout data.
* **Output Path:** `results/portfolio_backtest/robustness/subperiod/subperiod_stability.parquet`.

#### 5. `src/robustness/regime_stability.py` (Investigation 5)
* **Responsibility:** Computes state-conditional return distributions, annualized Sharpe ratios, win rates, and rebalancing transition friction across the 6 discovered HMM regimes (`accepted_regime` $\in \{0, 1, 2, 3, 4, 5\}$).
* **Key Analysis:** Distinguishes rebalance execution sessions ($t+1$ Close) from stationary holding sessions to measure direct transition slippage.
* **Output Path:** `results/portfolio_backtest/robustness/regime/regime_stability.parquet`.

#### 6. `src/robustness/parameter_sensitivity.py` (Investigation 6)
* **Responsibility:** Evaluates rule-execution threshold sensitivity on frozen causal probabilities (`hmm_causal_probabilities.csv`) without retraining the HMM.
* **Scope:**
  - **Strategy 1A (Primary Reference Strategy):** Full $7 \times 6 = \mathbf{42\text{-cell primary grid}}$:
    - $P_{\text{thresh}} \in \{0.40, 0.45, 0.50 \text{ [baseline]}, 0.55, 0.60, 0.65, 0.70\}$
    - $T_{\text{lock}} \in \{1 \text{ [Min]}, 3, 5 \text{ [Baseline]}, 10, 15, 20 \text{ [Max]}\}$
  - **Strategies 1B, 2A, 2B:** Standardized $3 \times 3 = \mathbf{9\text{-cell True Extreme Boundary Matrix}}$ each:
    - $P_{\text{thresh}} \in \{0.40 \text{ [Min]}, 0.50 \text{ [Baseline]}, 0.70 \text{ [Max]}\} \times T_{\text{lock}} \in \{1 \text{ [Min]}, 5 \text{ [Baseline]}, 20 \text{ [Max]}\}$
  - **Volatility Lookback ($L_{\text{vol}}$):** Evaluated in a dedicated 1D slice ($L \in \{10, 20 \text{ [baseline]}, 40\}$) at baseline $P=0.50, T=5$ for applicable inverse-volatility strategies (1B and 2B).
* **Diagnostic Boundary:** Mapped as stability surfaces only; zero parameter optimization against holdout.
* **Output Path:** `results/portfolio_backtest/robustness/parameter_sensitivity/parameter_sensitivity.parquet`.

#### 7. `src/robustness/benchmark_sensitivity.py` (Investigation 7)
* **Responsibility:** Evaluates market-direction asymmetry and benchmarks against naive price momentum.
* **Key Metrics:**
  - **Dual-Beta Model:** $r_{\text{strat}, t} = \alpha + \beta^+ \max(r_{\text{mkt}, t}, 0) + \beta^- \min(r_{\text{mkt}, t}, 0) + \epsilon_t$.
  - **Capture Ratios:** $\text{Up Capture} = \bar{r}_{\text{strat}}^+ / \bar{r}_{\text{mkt}}^+$; $\text{Down Capture} = \bar{r}_{\text{strat}}^- / \bar{r}_{\text{mkt}}^-$; $\text{Capture Ratio} = \text{Up} / \text{Down}$.
  - **Treynor-Mazuy Timing Curvature:** $r_{\text{strat}, t} = \alpha + \beta_1 r_{\text{mkt}, t} + \gamma r_{\text{mkt}, t}^2 + \epsilon_t$.
  - **Naive Top-2 Momentum Comparator:** Trailing 20-day simple return ranking, strictly 50/50 equal-weighted between top-2 sectors, zero cash toggle, zero HMM inputs, monthly calendar rebalance at $t+1$ Close, 15 bps fee. NIFTY 50 remains primary statutory benchmark.
* **Output Paths:**
  - `results/portfolio_backtest/robustness/benchmark/benchmark_sensitivity.parquet`
  - `results/portfolio_backtest/robustness/benchmark/momentum_benchmark_comparison.parquet`

---

## 4. Reusable Function Map & Dependency Graph

```text
Existing Core Engines                 Robustness Sub-Modules (src/robustness/)        Orchestrator
────────────────────                 ─────────────────────────────────────────        ────────────
src/portfolio_backtest.py
  ├── calculate_drifted_weights() ───► transaction_cost.py
  ├── calculate_actual_turnover() ───► execution_sensitivity.py ───────────────────►  src/robustness_testing.py
  ├── simulate_portfolio() ──────────► benchmark_sensitivity.py (Momentum)             │
  └── compute_metrics() ─────────────► subperiod_stability.py                         │
                                                                                      │
src/comparative_evaluation.py                                                         ▼
  ├── compute_drawdown_metrics() ────► subperiod_stability.py                      Master Execution
  └── compute_regression_alpha_beta()► benchmark_sensitivity.py (Dual Beta)       Catalog Generation
                                                                                      │
src/regime_rotation_rules.py                                                          │
  └── RegimeRotationRulesEngine ─────► parameter_sensitivity.py                       ▼
                                                                             Parquet Results Catalog
src/benchmark_backtest.py                                                    (results/.../robustness/)
  └── get_month_end_signal_dates()───► benchmark_sensitivity.py (Momentum)
```

---

## 5. Integrated Notebook Architecture: `notebooks/10_robustness_testing.ipynb`

Following the mandatory filename `notebooks/10_robustness_testing.ipynb`, the notebook provides an end-to-end interactive dashboard structured into 9 logical sections:

* **Section 0: Executive Setup & Canonical Verification:**
  - Ingestion of frozen canonical simulation records and price series.
  - Verification of dataset checksums and interval counts ($N = 1,686$).
* **Section 1: Investigation 1 — Transaction Cost Sensitivity (0 to 30 bps):**
  - Interactive table of Net CAGR, Sharpe, and cost drag.
  - Multi-curve plot of Net CAGR vs. Transaction Cost Rate with NIFTY 50 and Equal-Weight hurdle lines.
* **Section 2: Investigation 2 — Execution Sensitivity & Timing Drag:**
  - Comparison of Models A ($t+1$ Close), B ($t+2$ Close), C ($t$ Close), and D ($t+1$ Open).
  - Bar charts of execution timing drag ($\Delta \text{CAGR}$ vs. $t$ Close) and delay penalties.
* **Section 3: Investigation 3 — Portfolio Concentration & Risk Attribution:**
  - Summary table of $HHI_{\text{total}}$, $HHI_{\text{equity}}$, and $N_{\text{eff}}$.
  - Stacked area chart of rolling HHI and dual bar chart comparing sector return attribution vs. Euler risk contribution.
* **Section 4: Investigation 4 — Subperiod Stability:**
  - Full breakdown of 8 calendar years (reconciling 2019 $N=41$ and 2026 $N=175$), NIFTY 50 200d SMA Bull/Bear states, and fixed training VIX terciles.
  - Grouped annual return bar charts comparing ML strategies vs. NIFTY 50.
* **Section 5: Investigation 5 — Regime Stability & Transition Dynamics:**
  - State-conditional return distributions, annualized Sharpe ratios, and win rates for Regimes 0 to 5.
  - Transition slippage chart comparing rebalance sessions to stationary holding sessions.
* **Section 6: Investigation 6 — Parameter & Model Sensitivity Surfaces:**
  - Interactive 2D Heatmap of Net CAGR and Sharpe across the 42-cell primary grid ($P_{\text{thresh}} \times T_{\text{lock}}$) on Strategy 1A.
  - Boundary matrix comparison charts for Variants 1B, 2A, and 2B.
* **Section 7: Investigation 7 — Benchmark Sensitivity & Active Momentum Comparator:**
  - Dual-Beta scatter plots ($\beta^+$ vs. $\beta^-$), Up/Down Capture quadrants, and Treynor-Mazuy timing curves.
  - Full-cycle performance comparison against the Naive Top-2 Momentum Benchmark.
* **Section 8: Parquet Catalog & Integrity Verification:**
  - Verification of exported Parquet files across all 7 subdirectories in `results/portfolio_backtest/robustness/`.

---

## 6. Testing Architecture: `tests/test_robustness_testing.py`

The test suite will be consolidated in `tests/test_robustness_testing.py` and organized into dedicated, modular test classes:

1. `TestTransactionCostSensitivity`:
   - Baseline parity: At 15 bps, outputs match Phase 10.5 canonical metrics to $< 10^{-12}$.
   - Zero-cost identity: At 0 bps, Net return series equals Gross return series bit-for-bit.
   - Monotonicity: Net CAGR strictly decreases as cost rate increases from 0 to 30 bps.
2. `TestExecutionSensitivity`:
   - Baseline parity: Model A ($t+1$ Close) reproduces canonical NAV bit-for-bit.
   - Simplex conservation: Sum of portfolio weights equals 1.0 on all sessions across all models.
   - Open execution compounding: Overnight gap + intraday returns compound cleanly without drift leakage.
3. `TestPortfolioConcentration`:
   - Invariant bounds: $1.0 \le N_{\text{eff, total}} \le 7.0$ and $1.0 \le N_{\text{eff, equity}} \le 6.0$.
   - Euler risk conservation: $\sum_{i=1}^K \text{Component\_Volatility}_i = \text{Portfolio\_Volatility}$ within $10^{-6}$.
   - Additive attribution identity: $\sum \text{contrib}_i + c_{\text{cost}} = r_{\text{net}}$ within $10^{-10}$.
4. `TestSubperiodStability`:
   - Session count conservation: $\sum N_{\text{years}} = 1,686$, $N_{\text{bull}} + N_{\text{bear}} = 1,686$, $\sum N_{\text{vix}} = 1,686$.
   - Warm-up integrity: Zero NaN values in 200d SMA across all 1,686 evaluation return intervals.
   - Fixed VIX threshold invariance: VIX cutoffs (<13, 13–18, >=18) match training parameters.
5. `TestRegimeStability`:
   - Session conservation: $\sum_{k=0}^5 N_k = 1,686$.
   - Arithmetic return reconciliation: Cumulative regime returns sum to total portfolio return.
6. `TestParameterSensitivity`:
   - Baseline reproduction: At $P=0.50, T=5$, Strategy 1A reproduces canonical schedule bit-for-bit.
   - Grid geometry: Exactly 42 rows for Strategy 1A grid; exactly 9 rows for 1B, 2A, 2B boundary checks.
7. `TestBenchmarkSensitivity`:
   - Beta bounding: Phase 10 linear beta lies between $\min(\beta^+, \beta^-)$ and $\max(\beta^+, \beta^-)$.
   - Momentum comparator parity: Exactly 50/50 weights, monthly rebalances, 15 bps fee, zero NaNs.
8. `TestCanonicalArtifactProtection`:
   - Confirms that all canonical files in `results/portfolio_backtest/` remain untampered.

---

## 7. Canonical Artifact Protection Protocol

To safeguard the scientific integrity of the research:
1. **Absolute Immutability:** Canonical files under `results/portfolio_backtest/` (`daily_simulation_*.parquet`, `metrics_summary.*`, `comparative_evaluation/*`), `results/portfolio_construction/`, `results/regime_discovery/`, and `data/` are strictly read-only.
2. **Dedicated Output Sandbox:** All Phase 10.6 outputs are written exclusively to `results/portfolio_backtest/robustness/` and its subdirectories.
3. **Audit Trail Preservation:** `reports/phase10_6_methodology_feasibility_audit.md` remains preserved as the approved historical methodology reference.
4. **Holdout Non-Optimization:** The holdout period (2025–2026) is strictly a diagnostic stress test; no parameter tuning or model selection will be performed against holdout results.

---

## 8. Five-Step Implementation Execution Sequence

Following user approval of this architecture, implementation will proceed incrementally:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: Core Engine Implementation                                         │
│ Create src/robustness/ sub-package (7 modules) and src/robustness_testing.py│
│ orchestrator. Reuses existing Phase 10 primitives.                          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: Test Suite Verification                                            │
│ Implement tests/test_robustness_testing.py. Run pytest and ensure 100% pass │
│ rate across baseline parity, mathematical identities, and invariants.       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: Integrated Execution & Parquet Generation                           │
│ Run orchestrator batch execution to populate all 7 Parquet subdirectories in│
│ results/portfolio_backtest/robustness/. Validate schema and row counts.     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: Interactive Notebook Construction                                  │
│ Construct notebooks/10_robustness_testing.ipynb; execute headlessly;        │
│ verify zero errors and render all diagnostic plots and tables.              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 5: Final Comprehensive Research Report                                │
│ Author reports/phase10_6_robustness_testing.md synthesizing all empirical   │
│ findings, sensitivity topography, and final sign-off.                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Final Verification & Architecture Sign-Off

### Verification Checklist:
- [x] All seven investigations are preserved and fully specified.
- [x] Target directory structure matches the exact mandatory layout (`src/robustness/`, `src/robustness_testing.py`, `notebooks/10_robustness_testing.ipynb`, `results/portfolio_backtest/robustness/*/`).
- [x] Strategy scope (universal 1A–2B for 1–5, 7; primary 42-cell + true extrema boundaries for 6) is preserved.
- [x] Reconciled session counts (2019 $N=41$, 2026 $N=175$, total $N=1,686$) are integrated.
- [x] Causal SMA 200d warm-up (zero dropped evaluation dates) and fixed VIX cutoffs (<13, 13–18, >=18) are preserved.
- [x] Naive Top-2 Momentum comparator (50/50 equal weighting, monthly rebalance, 15 bps fee) is specified.
- [x] Canonical artifact protection protocol is explicit.
- [x] Five-stage incremental implementation sequence is documented.
- [x] Implementation has NOT started; repository state remains 100% read-only.

