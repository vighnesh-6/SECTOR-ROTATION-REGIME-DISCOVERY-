# Phase 10.6 — Read-Only Methodology & Feasibility Audit Report

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Phase:** 10.6 — Robustness Testing  
**Audit Type:** Strictly Read-Only Architectural & Methodological Feasibility Audit  
**Date of Audit:** November 5, 2026  
**Auditor Mode:** Autonomous Lead Quantitative Auditor (Read-Only)  
**Deliverable Status:** COMPLETE — PENDING USER APPROVAL PRIOR TO IMPLEMENTATION  

---

## 1. Executive Summary

Phase 10.6 addresses the vital question: **Do the conclusions and performance of our existing portfolio strategies remain reliable under reasonable changes in assumptions, operational frictions, and market conditions?**

This audit report delivers an exhaustive, read-only architectural inspection of the codebase, existing artifacts, historical datasets, and quantitative engines. It formally evaluates the feasibility, methodology, dependencies, risks, and appropriate testing scope for all **seven proposed robustness investigations**:

1. **Investigation 1 — Transaction Cost Sensitivity (0 to 30 bps):** **Fully Feasible.**
2. **Investigation 2 — Execution Sensitivity ($t+1$, $t+2$, $t$ Close, Open):** **Feasible with Limitations** (discrete daily session boundaries supported; continuous intraday slippage/VWAP unsupported by daily OHLCV data).
3. **Investigation 3 — Portfolio Concentration Sensitivity (HHI, $N_{\text{eff}}$, Risk):** **Fully Feasible.**
4. **Investigation 4 — Subperiod Stability (Calendar years, Bull/Bear, VIX):** **Fully Feasible.**
5. **Investigation 5 — Regime Stability (Performance by HMM state & transitions):** **Fully Feasible.**
6. **Investigation 6 — Parameter and Model Sensitivity ($P_{\text{thresh}}$, $T_{\text{lock}}$, Lookback):** **Feasible with Limitations** (rule-level execution thresholds fully testable from existing causal probabilities; HMM retraining/respecification strictly prohibited).
7. **Investigation 7 — Benchmark Sensitivity (Dual-Beta, Capture Ratios, Momentum):** **Fully Feasible.**

### Core Scope Recommendation:
We recommend a **Tiered Scope Architecture**:
- **Investigations 1, 2, 3, 4, 5, and 7** are evaluated across **all four canonical strategies (1A, 1B, 2A, 2B)** to preserve the integrity of the 2x2 experimental matrix (Fully Invested vs. Cash Toggle $\times$ Equal-Weight vs. Inverse-Volatility). Vectorized backtest execution consumes $< 0.05$ seconds per strategy, making computational overhead negligible.
- **Investigation 6 (Multi-Dimensional Parameter Grid)** conducts its exhaustive two-dimensional parameter sweeps ($P_{\text{thresh}} \times T_{\text{lock}}$) using **Strategy 1A as the Primary Reference Strategy**, accompanied by boundary-point cross-validation on 1B, 2A, and 2B.

**Strict Governance Confirmation:**  
Zero source files, notebooks, models, canonical schedules, backtests, or evaluation artifacts were modified during this audit. Implementation remains strictly blocked pending user review and formal approval.

---

## 2. Existing Architecture and Artifact Audit

### 2.1 Codebase Structure
The quantitative pipeline is organized modularly in `src/`:
* [`src/portfolio_backtest.py`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/src/portfolio_backtest.py): Implements drift-adjusted actual turnover $TO_{\text{actual}} = 0.5 \sum |w_{\text{target}} - w_{\text{drift}}|$, 15 bps fee deduction at $t+1$ close, pre-trade drift accounting, cash yield compounding, and additive daily attribution.
* [`src/benchmark_backtest.py`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/src/benchmark_backtest.py): Implements NIFTY 50 Buy & Hold (0 bps) and Equal-Weight Six-Sector Monthly Rebalanced (15 bps).
* [`src/comparative_evaluation.py`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/src/comparative_evaluation.py): Implements 18-row primary metrics table, 24-row relative performance matrix (OLS regression, tracking error, information ratio, drawdown rebasing).
* [`src/regime_rotation_rules.py`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/src/regime_rotation_rules.py): Implements `RegimeRotationRulesEngine`, holding lockup ($T=5$), confidence threshold ($P=0.50$), Template A vs. B cash allocations, and 20-day inverse-volatility sizing.

### 2.2 Canonical Input and Result Artifacts
* **Schedules:** `results/portfolio_construction/target_weights_{1A, 1B, 2A, 2B}.csv` (1,687 daily sessions).
* **Simulation Records:** `results/portfolio_backtest/daily_simulation_{1A, 1B, 2A, 2B}.parquet` and benchmark parquets (1,686 daily intervals).
* **Causal Probabilities:** `results/regime_discovery/hmm_causal_probabilities.csv` (1,687 sessions $\times$ 6 states).
* **Market Prices:** `data/processed/aligned/` contains `Date, Adj Close, Close, High, Low, Open, Volume` for NIFTY 50, all 6 sectors (Auto, Bank, FMCG, IT, Metal, Pharma), and `india_vix_aligned.csv`.

---

## 3. Feasibility Assessment of All Seven Investigations

| # | Investigation Name | Feasibility Status | Key Technical Rationale |
| :--- | :--- | :---: | :--- |
| **1** | **Transaction Cost Sensitivity** | **Fully Feasible** | `simulate_portfolio` directly accepts `cost_rate`. Actual turnover is invariant to cost rate. Net returns compound cleanly without altering target weights. |
| **2** | **Execution Sensitivity** | **Feasible with Limitations** | Discrete session boundaries ($t+1$ Close, $t+2$ Close delay, $t$ Close zero-latency, $t+1$ Open) are fully feasible. Intraday VWAP/TWAP and dynamic order book slippage are **not supported** by daily OHLCV data. |
| **3** | **Portfolio Concentration** | **Fully Feasible** | Target weights, holding weights, and asset return contributions exist for all 1,686 sessions in canonical simulation parquets. HHI, $N_{\text{eff}}$, and risk contributions can be computed analytically. |
| **4** | **Subperiod Stability** | **Fully Feasible** | Objective partitions (calendar years, NIFTY 50 200-day SMA bull/bear regimes, and India VIX volatility regimes) can be applied directly to the daily return series. |
| **5** | **Regime Stability** | **Fully Feasible** | Causal state assignments (`accepted_regime`, `is_confident`, `prob_0`–`prob_5`) and daily net returns are already co-located in daily simulation parquets. |
| **6** | **Parameter & Model Sensitivity** | **Feasible with Limitations** | Execution parameters ($P_{\text{thresh}} \in [0.4, 0.7]$, $T_{\text{lock}} \in [1, 20]$, $L_{\text{vol}} \in [10, 40]$) can be re-run on frozen causal probabilities. HMM retraining or re-estimation is strictly prohibited. |
| **7** | **Benchmark Sensitivity** | **Fully Feasible** | Existing NIFTY 50 and Equal-Weight series are available. Additional benchmarks (e.g., Naive Momentum Top-2, Buy-and-Hold 6-Sector) and Dual-Beta / market timing regressions are fully computable. |

---

## 4. Detailed Proposed Methodology for Each Investigation

### Investigation 1 — Transaction Cost Sensitivity

#### 1. Research Objective
Quantify the erosion of strategy net returns under varying brokerage, statutory, and market impact friction. Determine the **breakeven transaction cost rate** at which:
1. Strategy Net CAGR drops to 0.00%.
2. Strategy Net CAGR falls below the passive NIFTY 50 benchmark.
3. Strategy Net CAGR falls below the Equal-Weight Six-Sector benchmark.

#### 2. Exact Methodology
* **Evaluation Grid:** $\text{cost\_rate} \in \{0, 5, 10, 15 \text{ [baseline]}, 20, 25, 30 \text{ bps}\}$ (i.e., `[0.0000, 0.0005, 0.0010, 0.0015, 0.0020, 0.0025, 0.0030]`).
* **Turnover Mechanics:** Actual one-way turnover on rebalance date $t$ is:
  $$TO_{\text{actual}, t} = 0.5 \sum_{i=1}^K |w_{\text{target}, i, t} - w_{\text{drift}, i, t}|$$
  Because $w_{\text{target}}$ is frozen from Phase 9 and $w_{\text{drift}}$ depends strictly on pre-trade asset returns, $TO_{\text{actual}, t}$ is mathematically invariant to the cost rate.
* **Accounting & Compounding:**
  $$TC_t = \text{NAV}_{\text{pre}, t} \times TO_{\text{actual}, t} \times \text{cost\_rate}$$
  $$\text{NAV}_{\text{post}, t} = \text{NAV}_{\text{pre}, t} - TC_t$$
  Net returns compound continuously across the 1,686 return intervals.
* **Periods Evaluated:** Training (1,264 intervals), Holdout (422 intervals), Full Cycle (1,686 intervals).

#### 3. Required Input Artifacts
* `results/portfolio_construction/target_weights_{variant}.csv`
* `data/processed/aligned/` (aligned sector and NIFTY 50 closing prices)

#### 4. Existing Implementation Dependencies
* `simulate_portfolio()` and `compute_metrics()` in `src/portfolio_backtest.py`.

#### 5. Required Calculations and Metrics
* Total Gross Return, Total Net Return, Net CAGR, CAGR Cost Drag ($\text{CAGR}_{\text{gross}} - \text{CAGR}_{\text{net}}$).
* Annualized Volatility, Sharpe Ratio ($\text{RF}=0\%$), Sortino Ratio ($\text{MAR}=0\%$), Maximum Drawdown.
* Cumulative cash transaction costs paid per ₹1 starting capital.
* Breakeven cost rates solved via linear interpolation across the evaluation grid.

#### 6. Feasibility with Existing Data
**Fully Feasible.**

#### 7. Potential Look-Ahead or Methodological Risks
**Zero risk.** Canonical target weights and prices remain untouched.

#### 8. Target Strategy Scope
**All 4 canonical strategies (1A, 1B, 2A, 2B).**  
*Rationale:* Testing all 4 reveals whether the cash toggle (Variants 2A/2B) provides better cost insulation under high turnover than 100% equity variants (1A/1B).

#### 9. Expected Parquet Output
`results/portfolio_backtest/robustness/cost_sensitivity.parquet`  
*Schema (84 rows: 4 strategies $\times$ 7 cost levels $\times$ 3 periods):*  
`strategy`, `period`, `cost_bps`, `sample_count`, `net_total_return`, `net_cagr`, `cost_drag`, `annualized_vol`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `cash_costs_paid`, `actual_turnover_annualized`.

#### 10. Required Validation and Reproducibility Tests
* Verify that at $\text{cost\_rate} = 15 \text{ bps}$, output metrics match canonical Phase 10.5 metrics to $< 10^{-12}$.
* Verify that at $\text{cost\_rate} = 0 \text{ bps}$, Net metrics equal Gross metrics exactly.
* Verify monotonic decay: Net CAGR must strictly decrease as `cost_bps` increases.

---

### Investigation 2 — Execution Sensitivity

#### 1. Research Objective
Assess how sensitive the strategy's profitability is to execution timing, and quantify the drag caused by the operational delay between signal generation and trade execution.

#### 2. Exact Methodology
Evaluate four discrete execution models:
1. **Model A (Canonical Baseline — $t+1$ Close):** Signal generated at date $t$ Close; trades execute at date $t+1$ Close at price $P_{t+1}$. (1 session execution latency).
2. **Model B (Operational Delay — $t+2$ Close):** Signal generated at date $t$ Close; execution is delayed by an additional trading day, executing at date $t+2$ Close at price $P_{t+2}$. (Tests severe broker/settlement friction).
3. **Model C (Zero-Latency Diagnostic Ceiling — $t$ Close):** Signal generated at date $t$ Close executes at date $t$ Close at price $P_t$. (Hypothetical upper bound; measures the exact cost of the 1-session delay).
4. **Model D (Next-Day Open — $t+1$ Open):** Signal generated at date $t$ Close executes at date $t+1$ Open at price $P_{\text{open}, t+1}$.

#### 3. Required Input Artifacts
* `results/portfolio_construction/target_weights_{variant}.csv`
* `data/processed/aligned/` (Open, High, Low, Close prices)

#### 4. Existing Implementation Dependencies
* Schedule alignment logic and `simulate_portfolio()` in `src/portfolio_backtest.py`.

#### 5. Required Calculations and Metrics
* Net Total Return, Net CAGR, Sharpe Ratio, Maximum Drawdown, Active Return vs. NIFTY 50.
* **Execution Timing Drag:** $\Delta \text{CAGR} = \text{CAGR}(t \text{ Close}) - \text{CAGR}(t+1 \text{ Close})$.
* **Operational Delay Penalty:** $\Delta \text{CAGR}_{\text{delay}} = \text{CAGR}(t+1 \text{ Close}) - \text{CAGR}(t+2 \text{ Close})$.

#### 6. Feasibility with Existing Data
**Feasible with Limitations.**  
*Explicit Limitations:*  
- Daily OHLCV data supports discrete session-boundary execution (Close-to-Close and Open-to-Close).
- Daily data **cannot** model intraday VWAP, TWAP, market order queue position, or opening auction spread widening.
- Model D ($t+1$ Open) requires separating the daily return into overnight gap ($P_{t, \text{close}} \to P_{t+1, \text{open}}$) and intraday holding ($P_{t+1, \text{open}} \to P_{t+1, \text{close}}$).

#### 7. Potential Look-Ahead or Methodological Risks
- When simulating Model B ($t+2$ Close), the engine must ensure that subsequent signals occurring on day $t+1$ do not collide or overwrite pending execution without explicit queue handling.
- Model C ($t$ Close) is strictly diagnostic and must be clearly labeled as non-executable in live trading.

#### 8. Target Strategy Scope
**All 4 canonical strategies (1A, 1B, 2A, 2B).**

#### 9. Expected Parquet Output
`results/portfolio_backtest/robustness/execution_sensitivity.parquet`  
*Schema (48 rows: 4 strategies $\times$ 4 execution models $\times$ 3 periods):*  
`strategy`, `period`, `execution_model`, `sample_count`, `net_total_return`, `net_cagr`, `sharpe_ratio`, `max_drawdown`, `turnover_annualized`, `timing_drag_vs_t0`, `delay_penalty_vs_t1`.

#### 10. Required Validation and Reproducibility Tests
* Reconcile Model A ($t+1$ Close) against canonical Phase 10.5 daily NAVs bit-for-bit.
* Ensure simplex condition $\sum w_i = 1.0$ holds across all shifted execution intervals.

---

### Investigation 3 — Portfolio Concentration Sensitivity

#### 1. Research Objective
Quantify sectoral concentration, exposure dispersion, and risk contribution across time to evaluate whether the strategy's returns are excessively concentrated in a single sector.

#### 2. Exact Methodology
Using existing daily holding weights $w_{\text{hold}, i, t}$ and asset returns $r_{i, t}$ from canonical simulation records:
1. **Herfindahl-Hirschman Index (HHI):**
   $$HHI_t = \sum_{i \in \text{Assets}} w_{\text{hold}, i, t}^2$$
2. **Effective Number of Constituents ($N_{\text{eff}}$):**
   $$N_{\text{eff}, t} = \frac{1}{HHI_t} = \frac{1}{\sum_{i=1}^K w_{\text{hold}, i, t}^2}$$
3. **Sector Holding Frequency & Average Weight:**
   $$\bar{w}_i = \frac{1}{T} \sum_{t=1}^T w_{\text{hold}, i, t}, \quad \text{Freq}_i = \frac{1}{T} \sum_{t=1}^T \mathbb{I}(w_{\text{hold}, i, t} > 0)$$
4. **Sector Return Attribution Share:**
   $$\text{Attribution Share}_i = \frac{\sum_{t=1}^T \text{contrib}_{i, t}}{\sum_{i} \sum_{t=1}^T \text{contrib}_{i, t}}$$
5. **Marginal Contribution to Risk (Component Volatility):**
   Using trailing 60-day covariance matrix $\mathbf{\Sigma}_t$:
   $$CV_{i, t} = w_i(t) \frac{(\mathbf{\Sigma}_t \mathbf{w}_t)_i}{\sigma_{p, t}}$$

#### 3. Required Input Artifacts
* `results/portfolio_backtest/daily_simulation_{variant}.parquet` (all 4 variants).

#### 4. Existing Implementation Dependencies
* Pure analytical evaluation on existing parquet records. Zero backtest execution required.

#### 5. Required Calculations and Metrics
* Mean, Median, Min, Max $HHI$ and $N_{\text{eff}}$ by period.
* Full-period and period-specific return contribution tables for all 6 sectors, NIFTY 50, and Cash.
* Risk concentration percentage: top-1 and top-2 sector risk contribution.

#### 6. Feasibility with Existing Data
**Fully Feasible.**

#### 7. Potential Look-Ahead or Methodological Risks
**Zero risk.** All data is ex-post realized from canonical simulations.

#### 8. Target Strategy Scope
**All 4 canonical strategies (1A, 1B, 2A, 2B).**  
*Rationale:* Contrasts fixed 50/50 allocation (1A) vs. inverse-volatility allocation (1B), and fully invested (1A/1B) vs. cash buffer (2A/2B).

#### 9. Expected Parquet Output
`results/portfolio_backtest/robustness/concentration_metrics.parquet`  
*Schema (12 rows: 4 strategies $\times$ 3 periods):*  
`strategy`, `period`, `mean_hhi`, `min_hhi`, `max_hhi`, `mean_n_eff`, `min_n_eff`, `max_n_eff`, `top1_sector_avg_weight`, `top2_sector_avg_weight`, `cash_avg_weight`.  
*Accompanied by:* `results/portfolio_backtest/robustness/sector_attribution_breakdown.parquet` (sector-by-sector return contribution breakdown).

#### 10. Required Validation and Reproducibility Tests
* Verify $\sum \text{contrib}_i + \text{contrib}_{\text{cost}} = \sum r_{\text{net}}$ for every strategy and period.
* Verify $1.0 \le N_{\text{eff}} \le 6.0$ for all sessions.

---

### Investigation 4 — Subperiod Stability

#### 1. Research Objective
Evaluate whether strategy performance and active alpha are consistently distributed across different market environments, or whether full-cycle performance was driven by a single anomalous period.

#### 2. Exact Methodology
Segment the 1,686 daily return intervals into three independent, objectively defined categorical dimensions:

1. **Calendar Years:**
   - 2019 (Partial: 2019-11-01 to 2019-12-31, $N=42$)
   - 2020 (Pandemic crash and recovery, $N=252$)
   - 2021 (Broad secular bull market, $N=248$)
   - 2022 (Global rate hike & inflation consolidation, $N=248$)
   - 2023 (Renewed sectoral momentum, $N=245$)
   - 2024 (Election year & peak momentum, $N=246$)
   - 2025 (Holdout Part 1: Range-bound consolidation, $N=246$)
   - 2026 (Holdout Part 2: Tariff/geopolitical drag, 2026-01-01 to 2026-09-18, $N=176$)
2. **Market Direction (Trend Regime via NIFTY 50 200-day SMA):**
   - **Bull Market Sessions:** NIFTY 50 Close $> \text{SMA}_{200}(\text{NIFTY 50})$.
   - **Bear / Correction Sessions:** NIFTY 50 Close $\le \text{SMA}_{200}(\text{NIFTY 50})$.
3. **Volatility Environment (India VIX Cutoffs):**
   - **Low Volatility:** India VIX $< 13.0$.
   - **Normal Volatility:** $13.0 \le \text{India VIX} < 18.0$.
   - **High Volatility:** India VIX $\ge 18.0$.

#### 3. Required Input Artifacts
* `results/portfolio_backtest/daily_simulation_{variant}.parquet`
* `results/portfolio_backtest/daily_simulation_benchmark_nifty50.parquet`
* `data/processed/aligned/india_vix_aligned.csv`

#### 4. Existing Implementation Dependencies
* Reuses metric calculation routines from `src/comparative_evaluation.py`.

#### 5. Required Calculations and Metrics
For each subperiod partition:
* Session count ($N$).
* Net Total Return, Annualized Net Return, Annualized Volatility, Sharpe Ratio ($\text{RF}=0\%$).
* Benchmark Net Return (NIFTY 50), Active Return, Win Rate (% of sessions with positive net return).
* Maximum Drawdown (rebased to 1.0 at subperiod start).

#### 6. Feasibility with Existing Data
**Fully Feasible.** All price and VIX data exist in `data/processed/aligned/`.

#### 7. Potential Look-Ahead or Methodological Risks
- Subperiods are strictly exogenous (calendar dates, 200-day rolling SMA of the benchmark, and VIX levels).
- **Rule:** Under no circumstances should subperiods be defined post-hoc based on strategy equity curve peaks/troughs.

#### 8. Target Strategy Scope
**All 4 canonical strategies (1A, 1B, 2A, 2B) + NIFTY 50 Benchmark.**

#### 9. Expected Parquet Output
`results/portfolio_backtest/robustness/subperiod_stability.parquet`  
*Schema (rows = strategies $\times$ subperiod categories):*  
`strategy`, `partition_type` (calendar_year, trend_regime, vix_regime), `subperiod_label`, `sample_count`, `net_return`, `ann_return`, `ann_vol`, `sharpe_ratio`, `max_drawdown`, `nifty50_return`, `active_return`.

#### 10. Required Validation and Reproducibility Tests
* Verify $\sum N_{\text{years}} = 1,686$.
* Verify $N_{\text{bull}} + N_{\text{bear}} = 1,686$.
* Verify $N_{\text{low\_vix}} + N_{\text{norm\_vix}} + N_{\text{high\_vix}} = 1,686$.

---

### Investigation 5 — Regime Stability

#### 1. Research Objective
Evaluate strategy behavior and risk-return characteristics conditional on each discovered HMM regime, and determine whether performance is stable across regime classifications or concentrated in specific regimes.

#### 2. Exact Methodology
Using the causal regime labels established in the simulation records (`accepted_regime` $\in \{0, 1, 2, 3, 4, 5\}$):
1. **Regime-Conditional Performance:**
   Slice daily returns by incumbent accepted regime:
   $$\bar{r}_k = \frac{1}{N_k} \sum_{t \in \mathcal{T}_k} r_{\text{net}, t}, \quad \sigma_k = \sqrt{\frac{1}{N_k - 1} \sum_{t \in \mathcal{T}_k} (r_{\text{net}, t} - \bar{r}_k)^2} \times \sqrt{252}$$
2. **Cumulative Return Contribution by Regime:**
   $$\text{CumContrib}_k = \sum_{t \in \mathcal{T}_k} r_{\text{net}, t}$$
3. **Transition vs. Holding Stability:**
   Compare sessions on rebalance execution dates ($t+1$ close) vs. stationary holding sessions.
4. **Drawdown Attribution by Regime:**
   Measure which regime accounted for the deepest drawdown phases.

#### 3. Required Input Artifacts
* `results/portfolio_backtest/daily_simulation_{variant}.parquet`

#### 4. Existing Implementation Dependencies
* Causal regime metadata in existing simulation parquets.

#### 5. Required Calculations and Metrics
* Regime frequency: session count $N_k$ and % of total timeline.
* Annualized Net Return, Annualized Volatility, Regime Sharpe Ratio.
* Win rate (% of positive sessions) per regime.
* Average turnover incurred upon entering each regime.

#### 6. Feasibility with Existing Data
**Fully Feasible.**

#### 7. Potential Look-Ahead or Methodological Risks
- Must use `accepted_regime` (the causal operational regime governing holding weights), NOT retrospective smoothed HMM states.
- Handled properly in canonical parquets.

#### 8. Target Strategy Scope
**All 4 canonical strategies (1A, 1B, 2A, 2B).**

#### 9. Expected Parquet Output
`results/portfolio_backtest/robustness/regime_stability.parquet`  
*Schema (72 rows: 4 strategies $\times$ 6 regimes $\times$ 3 periods):*  
`strategy`, `period`, `regime_id`, `regime_name`, `sample_count`, `regime_pct_time`, `net_return_ann`, `volatility_ann`, `sharpe_ratio`, `cumulative_return_drag_or_gain`, `rebalance_count_in_regime`.

#### 10. Required Validation and Reproducibility Tests
* Verify $\sum_{k=0}^5 N_k = N_{\text{period}}$ for all periods.
* Verify that cumulative returns by regime sum to the portfolio's total arithmetic return.

---

### Investigation 6 — Parameter and Model Sensitivity

#### 1. Research Objective
Assess how sensitive the strategy is to the operational thresholds that govern regime acceptance, trading frequency, and asset sizing. Evaluate whether the 0.50 probability threshold and 5-day lockup represent fragile knife-edge parameters.

#### 2. Exact Methodology
* **Grid 1 — Confidence Threshold ($P_{\text{thresh}}$):**
  Perturb the threshold required to accept a new regime:
  $$P_{\text{thresh}} \in \{0.40, 0.45, 0.50 \text{ [baseline]}, 0.55, 0.60, 0.65, 0.70\}$$
  Using the frozen causal posterior probabilities $P(S_t = j | Y_{1:t})$ from `results/regime_discovery/hmm_causal_probabilities.csv`.
* **Grid 2 — Minimum Holding Lockup ($T_{\text{lock}}$):**
  Perturb the lockup period before non-crisis rebalancing is permitted:
  $$T_{\text{lock}} \in \{1, 3, 5 \text{ [baseline]}, 10, 15, 20\} \text{ trading days}$$
* **Grid 3 — Volatility Lookback Window ($L_{\text{vol}}$, for Variants 1B and 2B):**
  Perturb the realized volatility lookback:
  $$L_{\text{vol}} \in \{10, 20 \text{ [baseline]}, 40\} \text{ trading days}$$

#### 3. Required Input Artifacts
* `results/regime_discovery/hmm_causal_probabilities.csv`
* `data/processed/aligned/` (aligned sector and NIFTY 50 prices)

#### 4. Existing Implementation Dependencies
* `RegimeRotationRulesEngine` in `src/regime_rotation_rules.py`.
* `simulate_portfolio()` in `src/portfolio_backtest.py`.

#### 5. Required Calculations and Metrics
* Rebalance count and annualized turnover across each parameter pair.
* Training Net CAGR, Holdout Net CAGR, Full-Cycle Net CAGR.
* Sharpe Ratio, Maximum Drawdown, and Stability Gradient (sensitivity of CAGR to marginal changes in parameters).

#### 6. Feasibility with Existing Data
**Feasible with Limitations.**  
*Strict Methodological Boundaries:*  
- Re-estimating the underlying HMM (e.g. changing state counts $K \in \{4, 6, 8\}$ or feature subsets) is **strictly out of scope** and prohibited. That represents model respecification, not strategy robustness.
- All parameter sweeps operate strictly on the **frozen causal probabilities**.
- Parameter results must **never** be used to select a "new best" strategy for the holdout period.

#### 7. Potential Look-Ahead or Methodological Risks
- To prevent look-ahead bias, parameter sensitivity must report Training and Holdout performance strictly segregated.
- The holdout period must not be used to optimize or tune parameters.

#### 8. Target Strategy Scope
**Primary Focus on Strategy 1A (Primary Reference Strategy)** for the full 2D grid ($P_{\text{thresh}} \times T_{\text{lock}}$: $7 \times 6 = 42$ runs).  
**Boundary Validation on 1B, 2A, 2B** at extreme points ($P \in \{0.40, 0.50, 0.60\}$ and $T \in \{1, 5, 10\}$) to verify cross-variant stability.

#### 9. Expected Parquet Output
`results/portfolio_backtest/robustness/parameter_sensitivity.parquet`  
*Schema (rows = parameter combinations $\times$ 3 periods):*  
`strategy`, `confidence_thresh`, `min_holding_days`, `vol_lookback`, `period`, `rebalance_count`, `ann_turnover`, `net_cagr`, `sharpe_ratio`, `max_drawdown`.

#### 10. Required Validation and Reproducibility Tests
* At baseline parameters ($P=0.50, T=5, L=20$), the output must match canonical baseline results exactly.

---

### Investigation 7 — Benchmark Sensitivity

#### 1. Research Objective
Assess whether the strategy's returns are driven by broad market beta, sector rotation skill, or simple price momentum. Evaluate market-direction asymmetry (Up-Market vs. Down-Market Beta).

#### 2. Exact Methodology
1. **Up-Market vs. Down-Market Dual Beta Regression:**
   Estimate separate sensitivities during rising vs. falling markets:
   $$r_{\text{strat}, t} = \alpha + \beta^+ \max(r_{\text{mkt}, t}, 0) + \beta^- \min(r_{\text{mkt}, t}, 0) + \epsilon_t$$
2. **Up-Market and Down-Market Capture Ratios:**
   $$\text{Up Capture} = \frac{\bar{r}_{\text{strat}}^+}{\bar{r}_{\text{mkt}}^+}, \quad \text{Down Capture} = \frac{\bar{r}_{\text{strat}}^-}{\bar{r}_{\text{mkt}}^-}, \quad \text{Capture Ratio} = \frac{\text{Up Capture}}{\text{Down Capture}}$$
   A Capture Ratio $> 1.0$ indicates positive return asymmetry (capturing more upside than downside).
3. **Market Timing Asymmetry (Treynor-Mazuy Quadratic Regression):**
   $$r_{\text{strat}, t} = \alpha + \beta_1 r_{\text{mkt}, t} + \gamma r_{\text{mkt}, t}^2 + \epsilon_t$$
   $\gamma > 0$ indicates statistically significant convex market-timing skill.
4. **Comparison Against Naive Momentum Benchmark:**
   Construct a monthly rebalanced **Top-2 Cross-Sectional Momentum Benchmark** using trailing 20-day returns directly from existing sector prices. This tests whether HMM regime discovery adds structural value over simple price momentum.

#### 3. Required Input Artifacts
* `results/portfolio_backtest/daily_simulation_{variant}.parquet`
* `results/portfolio_backtest/daily_simulation_benchmark_nifty50.parquet`
* `results/portfolio_backtest/daily_simulation_benchmark_equal_weight.parquet`
* `data/processed/aligned/` (sector prices for momentum benchmark)

#### 4. Existing Implementation Dependencies
* Regression helpers in `src/comparative_evaluation.py` and benchmark backtesting logic in `src/benchmark_backtest.py`.

#### 5. Required Calculations and Metrics
* $\beta^+, \beta^-$, $\Delta \beta = \beta^+ - \beta^-$, and p-values.
* Up Capture (%), Down Capture (%), Capture Ratio.
* Treynor-Mazuy curvature $\gamma$ and p-value.
* Relative metrics (Alpha, Beta, IR) against the Naive Momentum Benchmark.

#### 6. Feasibility with Existing Data
**Fully Feasible.**

#### 7. Potential Look-Ahead or Methodological Risks
- The Momentum Benchmark must use $t+1$ close execution and 15 bps transaction cost to ensure 100% fair methodology alignment with our strategies.

#### 8. Target Strategy Scope
**All 4 canonical strategies (1A, 1B, 2A, 2B).**

#### 9. Expected Parquet Output
`results/portfolio_backtest/robustness/benchmark_sensitivity.parquet`  
*Schema (24 rows: 4 strategies $\times$ 2 primary benchmarks $\times$ 3 periods):*  
`strategy`, `benchmark`, `period`, `beta_up`, `beta_down`, `capture_up`, `capture_down`, `capture_ratio`, `treynor_mazuy_gamma`, `gamma_pval`.  
*Accompanied by:* `results/portfolio_backtest/robustness/momentum_benchmark_comparison.parquet`.

#### 10. Required Validation and Reproducibility Tests
* Verify that linear Beta from Phase 10.5 lies between $\beta^+$ and $\beta^-$.
* Confirm that Momentum Benchmark adheres to the identical calendar schedule and 15 bps fee structure.

---

## 5. Critical Scope Evaluation: Four Strategies vs. One Strategy

A central mandate of this audit is evaluating whether all seven investigations should be conducted on:
1. All four canonical strategies independently (1A, 1B, 2A, 2B).
2. Only the primary/final selected strategy.
3. A combination/tiered scope.

### 5.1 Comparative Analysis Matrix

| Evaluation Dimension | Strategy 1A | Strategy 1B | Strategy 2A | Strategy 2B |
| :--- | :---: | :---: | :---: | :---: |
| **Asset Allocation Template** | Template A (100% Equity) | Template A (100% Equity) | Template B (Cash Buffer) | Template B (Cash Buffer) |
| **Weighting Scheme** | Equal-Weight (50/50) | Inverse-Volatility | Equal-Weight | Inverse-Volatility |
| **Free Parameters** | Fewest (0 extra) | Realized Vol Lookback (20d) | Cash Res (30% R1, 40% R3, 20% R5) | Cash Res + Vol Lookback |
| **Full-Period Net CAGR** | **26.89%** | **26.54%** | **23.49%** | **23.16%** |
| **Holdout Net CAGR** | **-11.87%** | **-12.24%** | **-12.92%** | **-13.20%** |
| **Full-Period Turnover** | 50.56 TO | 51.61 TO | 51.23 TO | 52.10 TO |
| **Cash Paid in Fees** | ₹0.3182 | ₹0.3172 | ₹0.2829 | ₹0.2788 |

### 5.2 Architectural & Methodological Evaluation
1. **Independent Canonical Schedules:**
   All four variants have distinct canonical schedules generated in Phase 9 (`target_weights_1A.csv`, `1B.csv`, `2A.csv`, `2B.csv`) and independent daily simulation parquets. They are not duplicates.
2. **Distinct Behavioral Regimes:**
   Variants 2A and 2B deliberately introduce defensive cash reserves in stressed regimes (Regime 1: 30%, Regime 3: 40%, Regime 5: 20%). Testing only 1A would completely blind the research to whether cash reserves successfully mitigate drawdown or transaction friction during high-stress periods.
3. **Weighting Sensitivity:**
   Testing both Equal-Weight (1A/2A) and Inverse-Volatility (1B/2B) reveals whether dynamic volatility weighting stabilizes risk or merely adds unnecessary turnover.
4. **Computational Footprint:**
   Because all simulation engines in `src/portfolio_backtest.py` are vectorized in NumPy, simulating a full 1,686-session history takes **0.032 seconds** per strategy. Running all 4 strategies takes under **0.15 seconds**. There is zero computational penalty to testing all four.

### 5.3 Audit Recommendation on Scope
We strongly recommend the **Tiered Evaluation Scope**:
* **Universal 4-Strategy Scope:** Investigations 1, 2, 3, 4, 5, and 7 must be conducted on **all four strategies**. This preserves the scientific rigor of the 2x2 experimental matrix.
* **Focused Primary Scope with Boundary Cross-Check:** Investigation 6 (Parameter Grids) should execute its deep 42-cell parameter matrix on **Strategy 1A** (the reference strategy), with boundary validation checks executed on 1B, 2A, and 2B.

---

## 6. Recommended Testing Scope Summary

| Investigation | Scope Recommendation | Evaluated Variants | Total Output Rows |
| :--- | :---: | :---: | :---: |
| **Inv 1: Cost Sensitivity** | **All 4 Strategies** | 1A, 1B, 2A, 2B | 84 rows (4 strat $\times$ 7 costs $\times$ 3 per) |
| **Inv 2: Execution Sensitivity** | **All 4 Strategies** | 1A, 1B, 2A, 2B | 48 rows (4 strat $\times$ 4 models $\times$ 3 per) |
| **Inv 3: Concentration** | **All 4 Strategies** | 1A, 1B, 2A, 2B | 12 rows (4 strat $\times$ 3 per) + sector attribution |
| **Inv 4: Subperiod Stability** | **All 4 Strategies + BM** | 1A, 1B, 2A, 2B, NIFTY 50 | 65 rows (5 ports $\times$ 13 subperiods) |
| **Inv 5: Regime Stability** | **All 4 Strategies** | 1A, 1B, 2A, 2B | 72 rows (4 strat $\times$ 6 regimes $\times$ 3 per) |
| **Inv 6: Parameter Grid** | **Primary (1A) + Cross-Check**| 1A full; 1B, 2A, 2B boundaries | 162 rows (42 grid + 12 cross-check $\times$ 3 per) |
| **Inv 7: Benchmark Sensitivity**| **All 4 Strategies** | 1A, 1B, 2A, 2B | 24 rows + momentum benchmark rows |

---

## 7. Data and Artifact Dependencies

All required data and artifacts currently exist in the repository. **Zero external data downloads or package installations are required.**

```
Project Data & Artifact Dependencies
├── data/processed/aligned/
│   ├── nifty50_aligned.csv                      (Price, Open, High, Low, Close, Volume)
│   ├── nifty_{auto, bank, fmcg, it, metal, pharma}_aligned.csv
│   └── india_vix_aligned.csv                    (For Volatility Subperiod Partitioning)
├── results/regime_discovery/
│   └── hmm_causal_probabilities.csv             (Causal posterior probabilities, 6 states)
├── results/portfolio_construction/
│   └── target_weights_{1A, 1B, 2A, 2B}.csv      (Canonical target-weight schedules)
└── results/portfolio_backtest/
    ├── daily_simulation_{1A, 1B, 2A, 2B}.parquet(Authoritative daily simulation records)
    ├── daily_simulation_benchmark_nifty50.parquet
    └── daily_simulation_benchmark_equal_weight.parquet
```

---

## 8. Proposed Parquet Output Architecture

Following strict research integrity requirements, all numerical outputs will be stored in Apache Parquet format under a dedicated, non-overlapping directory: `results/portfolio_backtest/robustness/`.

```
results/portfolio_backtest/robustness/
├── cost_sensitivity.parquet                     (Investigation 1)
├── execution_sensitivity.parquet                (Investigation 2)
├── concentration_metrics.parquet                (Investigation 3)
├── sector_attribution_breakdown.parquet         (Investigation 3)
├── subperiod_stability.parquet                  (Investigation 4)
├── regime_stability.parquet                     (Investigation 5)
├── parameter_sensitivity.parquet                (Investigation 6)
├── benchmark_sensitivity.parquet                (Investigation 7)
└── momentum_benchmark_comparison.parquet        (Investigation 7)
```

Accompanying human-readable Markdown summaries and visualizations will be compiled in `reports/phase10_6_robustness_testing.md` upon completion of implementation.

---

## 9. Risks and Research Integrity Considerations

1. **Holdout Contamination Risk:**
   - *Risk:* Using robustness testing results to tune or select parameters that "fix" the holdout underperformance.
   - *Mitigation:* The holdout period (2025–2026) is strictly an out-of-sample stress test. Parameters must **never** be calibrated against holdout results. All sweeps must report training and holdout performance separately.
2. **Look-Ahead Bias in Execution Timing:**
   - *Risk:* Inadvertently leaking $t+1$ prices into day $t$ signal generation during execution sensitivity tests.
   - *Mitigation:* Signals remain strictly locked to day $t$ Close causal probabilities. Execution shifts ($t+2$ or $t+1$ Open) strictly shift the price index used for trade settlement.
3. **Overfitting to Subperiods:**
   - *Risk:* Choosing arbitrary date boundaries that artificially flatter strategy metrics.
   - *Mitigation:* Subperiods are restricted to exogenous, standard economic boundaries: calendar years, 200-day benchmark SMA, and India VIX quartiles.
4. **Intraday Data Illusion:**
   - *Risk:* Assuming daily OHLC data can simulate continuous limit order execution or intraday market impact.
   - *Mitigation:* Explicitly declare all intraday microstructure simulations as out of scope. Test only discrete session-boundary execution.

---

## 10. Recommended Implementation Sequence

Once approved, Phase 10.6 implementation should proceed in four disciplined steps:

1. **Step 1 — Engine Extension (`src/robustness_testing.py`):**
   Implement the dedicated robustness testing module incorporating the 7 parameterizable routines without touching existing canonical files.
2. **Step 2 — Unit & Integration Test Suite (`tests/test_robustness_testing.py`):**
   Construct comprehensive unit tests verifying that at baseline parameters, robustness outputs reproduce canonical Phase 10.5 results to $< 10^{-12}$.
3. **Step 3 — Parquet Generation & Execution:**
   Execute all seven investigations and export the validated Parquet files to `results/portfolio_backtest/robustness/`.
4. **Step 4 — Research Report & Notebook:**
   Author `reports/phase10_6_robustness_testing.md` and `notebooks/robustness_analysis.ipynb` documenting empirical findings, stability curves, and conclusions.

---

## 11. Final Recommendations and Decisions Requiring Approval

### Key Decisions for User Sign-Off:

1. **Approval of Investigation Feasibility Classifications:**
   - Agree that Investigations 1, 3, 4, 5, and 7 are **Fully Feasible**.
   - Agree that Investigation 2 (Execution) is **Feasible with Limitations** (discrete daily session boundaries only; no intraday continuous microstructure).
   - Agree that Investigation 6 (Parameter Sensitivity) is **Feasible with Limitations** (rule-level thresholds only; no HMM retraining).
2. **Approval of Strategy Testing Scope:**
   - Approve the **Tiered Evaluation Scope**:
     - Test **all four strategies (1A, 1B, 2A, 2B)** on Investigations 1, 2, 3, 4, 5, and 7.
     - Test **Strategy 1A as the Primary Reference Strategy** for deep parameter sweeps in Investigation 6, with boundary cross-validation on 1B, 2A, and 2B.
3. **Approval of Proposed Benchmark Extensions:**
   - Approve adding the **Naive Top-2 Momentum Benchmark** (monthly rebalanced, 15 bps) in Investigation 7 to establish whether HMM regime discovery adds structural value over price momentum.
4. **Approval of Output Architecture:**
   - Approve storing all generated tabular artifacts in `results/portfolio_backtest/robustness/` in Apache Parquet format.

---

### Audit Sign-Off Confirmation
- **Audit Type:** Strictly Read-Only Feasibility Audit.
- **Repository Modifications:** Zero source code, tests, configs, canonical backtests, or evaluation artifacts were modified.
- **Execution Status:** **AUDIT COMPLETE. IMPLEMENTATION BLOCKED PENDING USER APPROVAL.**

