# Phase 10.6 — Read-Only Methodology & Feasibility Audit Report (Final Revision)

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Phase:** 10.6 — Robustness Testing  
**Audit Type:** Strictly Read-Only Architectural & Methodological Feasibility Audit (Final Approved Revision)  
**Date of Audit:** November 5, 2026  
**Auditor Mode:** Autonomous Lead Quantitative Auditor (Read-Only)  
**Deliverable Status:** COMPLETE & FINALIZED — AWAITING FINAL IMPLEMENTATION GO-AHEAD  

---

## 1. Executive Summary & Approved Scope

Phase 10.6 addresses the central question: **Do the conclusions and performance of our existing portfolio strategies remain reliable under reasonable changes in assumptions, operational frictions, execution delays, and market environments?**

Following two rounds of rigorous read-only methodology reviews, the overall framework has been approved in principle:
1. **Tiered Evaluation Scope:**
   - **Investigations 1–5 and 7:** Evaluated across **all four canonical strategies (1A, 1B, 2A, 2B)**.
   - **Investigation 6:** Evaluated using **Strategy 1A as the Primary Reference Strategy** across an exhaustive 42-cell parameter grid, supplemented by predefined extreme boundary cross-checks on Variants 1B, 2A, and 2B.
2. **Additional Active Comparator:** Approved the inclusion of a **Naive Top-2 Cross-Sectional Momentum Benchmark** (monthly rebalanced, 50/50 equal weighting, 15 bps fee) to isolate whether HMM regime discovery adds structural value over pure price momentum, while maintaining **NIFTY 50 as the primary benchmark**.
3. **Structured Outputs:** All tabular outputs will be exported in **Apache Parquet format** under `results/portfolio_backtest/robustness/`.
4. **Research Integrity:** Training and previously examined holdout results will be strictly segregated. The holdout is explicitly designated as a **previously examined out-of-sample stress test**, not a fresh untouched test set.

This final revision resolves all remaining empirical and methodological details regarding calendar-year session accounting, historical warm-up initialization, parameter grid boundaries, and naive momentum allocations.

---

## 2. Existing Architecture & Artifact Audit

### 2.1 Codebase Structure
The quantitative pipeline is organized modularly in `src/`:
* [`src/portfolio_backtest.py`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/src/portfolio_backtest.py): Implements multi-asset price drift, actual one-way turnover $TO_{\text{actual}} = 0.5 \sum |w_{\text{target}} - w_{\text{drift}}|$, 15 bps fee deduction at $t+1$ close, cash yield compounding, and additive daily return attribution.
* [`src/benchmark_backtest.py`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/src/benchmark_backtest.py): Implements NIFTY 50 Buy & Hold (0 bps) and Equal-Weight Six-Sector Monthly Rebalanced (15 bps).
* [`src/comparative_evaluation.py`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/src/comparative_evaluation.py): Implements 18-row primary metrics table, 24-row relative performance matrix (single-factor OLS regression, tracking error, information ratio, drawdown rebasing).
* [`src/regime_rotation_rules.py`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/src/regime_rotation_rules.py): Implements `RegimeRotationRulesEngine`, holding lockup ($T=5$), confidence threshold ($P=0.50$), Template A vs. B cash allocations, and 20-day inverse-volatility sizing.

### 2.2 Canonical Input and Result Artifacts
* **Schedules:** `results/portfolio_construction/target_weights_{1A, 1B, 2A, 2B}.csv` (1,687 daily sessions).
* **Simulation Records:** `results/portfolio_backtest/daily_simulation_{1A, 1B, 2A, 2B}.parquet` and benchmark parquets (1,686 daily return intervals).
* **Causal Probabilities:** `results/regime_discovery/hmm_causal_probabilities.csv` (1,687 sessions $\times$ 6 states).
* **Market Prices:** `data/processed/aligned/` contains `Date, Adj Close, Close, High, Low, Open, Volume` for NIFTY 50, all 6 sectors (Auto, Bank, FMCG, IT, Metal, Pharma), and `india_vix_aligned.csv`.

---

## 3. Feasibility Assessment of All Seven Investigations

| # | Investigation Name | Feasibility Status | Key Technical Rationale |
| :--- | :--- | :---: | :--- |
| **1** | **Transaction Cost Sensitivity** | **Fully Feasible** | `simulate_portfolio` directly accepts `cost_rate`. Actual turnover is invariant to cost rate. Net returns compound cleanly without altering target weights. |
| **2** | **Execution Sensitivity** | **Feasible with Limitations** | Discrete session boundaries ($t+1$ Close, $t+2$ Close delay, $t$ Close zero-latency, $t+1$ Open) are fully feasible. Intraday VWAP/TWAP and dynamic order book slippage are **not supported** by daily OHLCV data. |
| **3** | **Portfolio Concentration** | **Fully Feasible** | Target weights, holding weights, and asset return contributions exist for all 1,686 sessions in canonical simulation parquets. HHI, $N_{\text{eff}}$, and risk contributions can be computed analytically. |
| **4** | **Subperiod Stability** | **Fully Feasible** | Objective partitions (calendar years, causal NIFTY 50 200-day SMA bull/bear regimes, and pre-holdout India VIX volatility regimes) can be applied directly. |
| **5** | **Regime Stability** | **Fully Feasible** | Causal state assignments (`accepted_regime`, `is_confident`, `prob_0`–`prob_5`) and daily net returns are already co-located in daily simulation parquets. |
| **6** | **Parameter & Model Sensitivity** | **Feasible with Limitations** | Execution parameters ($P_{\text{thresh}} \in [0.4, 0.7]$, $T_{\text{lock}} \in [1, 20]$, $L_{\text{vol}} \in [10, 40]$) can be re-run on frozen causal probabilities. HMM retraining or re-estimation is strictly prohibited. |
| **7** | **Benchmark Sensitivity** | **Fully Feasible** | Existing NIFTY 50 and Equal-Weight series are available. Additional benchmarks (e.g., Naive Momentum Top-2, Buy-and-Hold 6-Sector) and Dual-Beta / market timing regressions are fully computable. |

---

## 4. Methodological Clarifications & Detailed Specifications

### Investigation 1 — Transaction Cost Sensitivity & Turnover Accounting

#### 1. Precise Turnover Formulation
Actual one-way portfolio turnover on rebalance session $t$ is calculated against pre-trade drifted weights:
$$TO_{\text{one-way}, t} = 0.5 \sum_{i=1}^K |w_{\text{target}, i, t} - w_{\text{drift}, i, t}|$$
where pre-trade drifted weights $w_{\text{drift}, i, t}$ reflect asset price movements since the prior session:
$$w_{\text{drift}, i, t} = \frac{w_{\text{hold}, i, t-1} (1 + r_{i, t})}{\sum_{j=1}^K w_{\text{hold}, j, t-1} (1 + r_{j, t})}$$

#### 2. Institutional Cost Definition (One-Way vs. Two-Way Notional)
* In institutional portfolio management, one-way turnover measures the fraction of portfolio equity bought (or sold). In any rebalance where starting and ending cash flows are zero, the total value of purchases equals the total value of sales:
  $$\sum_{i: \Delta w_i > 0} \Delta w_i = \sum_{i: \Delta w_i < 0} |\Delta w_i| = TO_{\text{one-way}}$$
* The total two-way traded volume (purchases + sales) is therefore:
  $$\text{Volume}_{\text{two-way}} = \sum_{i=1}^K |\Delta w_i| = 2 \times TO_{\text{one-way}}$$
* **Fee Application in Engine:**
  $$TC_t = \text{NAV}_{\text{pre}, t} \times TO_{\text{one-way}, t} \times \text{cost\_rate}$$
  With $\text{cost\_rate} = 0.0015$ (15 bps baseline), the portfolio pays **15 bps per unit of one-way turnover**.
* **Equivalence:** This is mathematically identical to charging **7.5 bps on total gross traded notional (both buys and sells)** ($0.00075 \times 2 \times TO_{\text{one-way}} = 0.0015 \times TO_{\text{one-way}}$), or 15 bps round-trip on every rupee shifted from an old sector into a new sector.
* **Verification of Non-Duplication and Non-Omission:**
  - Transaction costs are deducted *strictly once* per rebalance event, directly from pre-trade net NAV: $\text{NAV}_{\text{post}} = \text{NAV}_{\text{pre}} - TC$.
  - On non-rebalance sessions, $TO_{\text{actual}} = 0$ and $TC = 0$.
  - There is zero double-counting, and no transaction friction is omitted.

#### 3. Parameter Evaluation Grid
$$\text{cost\_rate} \in \{0, 5, 10, 15 \text{ [baseline]}, 20, 25, 30 \text{ bps}\} \equiv \{0.0000, 0.0005, 0.0010, 0.0015, 0.0020, 0.0025, 0.0030\}$$
Because $w_{\text{target}}$ and $w_{\text{drift}}$ are scale-invariant normalized weights, $TO_{\text{actual}, t}$ is mathematically invariant to the cost rate. Only cash costs and resulting compounding NAV series vary.

#### 4. Breakeven Analysis
Solve for the critical cost rate $\text{cost\_rate}^*$ where:
1. $\text{Net CAGR}(\text{cost\_rate}^*) = 0.00\%$ (Capital Preservation Breakeven).
2. $\text{Net CAGR}(\text{cost\_rate}^*) = \text{CAGR}(\text{NIFTY 50})$ (Alpha Breakeven vs. Primary Benchmark).
3. $\text{Net CAGR}(\text{cost\_rate}^*) = \text{CAGR}(\text{Equal-Weight 6S})$ (Alpha Breakeven vs. Sector Benchmark).

---

### Investigation 2 — Execution Sensitivity & Market Microstructure Boundaries

#### 1. Existing Phase 10 Baseline Execution Verification
In [`src/portfolio_backtest.py`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/src/portfolio_backtest.py), the baseline execution timing is strictly **$t+1$ Close**:
* **Signal Generation Timestamp:** Session $t$ Market Close (15:30 IST), using feature data and causal HMM filter probabilities up to session $t$.
* **Rebalance Execution Timestamp:** Session $t+1$ Market Close (15:30 IST), at closing price $P_{t+1}$.
* **Holding Mechanics:** Between session $t$ Close and session $t+1$ Close, the portfolio holds the incumbent drifted weights $w_{\text{drift}, t+1}$, earning the return of the incumbent portfolio. The new target weights take effect from session $t+1$ close onward. This represents a full 1-trading-day execution delay.

#### 2. Signal Timestamp and Realistically Executable Prices
* In live market conditions, signals calculated after market close on session $t$ (15:30 IST) can be executed at the earliest during the **next session's opening auction (Session $t+1$ Open, 09:15 IST)**, or via **Session $t+1$ Market-on-Close (15:30 IST)**.
* **Session $t$ Close is a Theoretical Zero-Latency Bound:** Executing at the same close as signal generation ($t$ Close) is physically impossible in live trading because closing prices must be finalized before the HMM filter can run. It is evaluated strictly as a diagnostic upper bound to isolate the exact cost of the 1-session delay.

#### 3. Execution Models with Full Drift and Turnover Tracking
**Do NOT simply shift return series.** Every model simulates state continuity, holdings drift, and actual turnover:

1. **Model A (Canonical Baseline — $t+1$ Close):**
   Signal at session $t$ Close. Holdings drift through session $t+1$. Trade executes at session $t+1$ Close at price $P_{\text{close}, t+1}$. Turnover $TO = 0.5 \sum |w_{\text{target}} - w_{\text{drift}, t+1}|$. Target weights hold over session $t+1 \to t+2$.
2. **Model B (Operational Delay — $t+2$ Close):**
   Signal at session $t$ Close. Due to operational or broker delays, execution is postponed by an additional session. Holdings drift through sessions $t+1$ and $t+2$. Trade executes at session $t+2$ Close at price $P_{\text{close}, t+2}$. Turnover $TO = 0.5 \sum |w_{\text{target}} - w_{\text{drift}, t+2}|$. Target weights hold over session $t+2 \to t+3$.
3. **Model C (Zero-Latency Diagnostic Bound — $t$ Close):**
   Signal at session $t$ Close. Hypothetical instantaneous rebalance at session $t$ Close from $w_{\text{drift}, t}$ to $w_{\text{target}}$. Target weights hold over session $t \to t+1$. Measures the "latency penalty" ($t$ Close return minus $t+1$ Close return).
4. **Model D (Next-Day Open — $t+1$ Open):**
   Signal at session $t$ Close. On session $t+1$, the portfolio earns the overnight gap return on drifted holdings:
   $$r_{\text{gap}, t+1} = \sum_{i=1}^K w_{\text{hold}, i, t} \times \left(\frac{P_{\text{open}, i, t+1}}{P_{\text{close}, i, t}} - 1\right)$$
   At session $t+1$ Open (09:15 IST), the portfolio rebalances to $w_{\text{target}}$, paying transaction fees on $TO_{\text{open}} = 0.5 \sum |w_{\text{target}} - w_{\text{drift, open}}|$. Over the intraday session ($t+1$ Open $\to t+1$ Close), target holdings earn:
   $$r_{\text{day}, t+1} = \sum_{i=1}^K w_{\text{target}, i} \times \left(\frac{P_{\text{close}, i, t+1}}{P_{\text{open}, i, t+1}} - 1\right)$$
   Total session net return compounds the overnight and intraday legs with transaction fee deduction.

#### 4. Explicit Microstructure Limitations of Daily OHLCV Data
Daily OHLCV bars cannot model:
- Continuous intraday trade matching or queue position in the limit order book.
- Intraday Volume-Weighted Average Price (VWAP) or Time-Weighted Average Price (TWAP) schedules.
- Bid-ask spread bounce or market impact curves (e.g. square-root law).
- Opening auction price dispersion or illiquidity.
*Conclusion:* Intraday continuous execution simulation is formally documented as outside the scope of Phase 10.6. Execution testing is strictly bounded to discrete session boundaries ($t+1$ Close, $t+2$ Close, $t$ Close, $t+1$ Open).

---

### Investigation 3 — Portfolio Concentration, Risk Attribution & Cash Treatment

#### 1. Return Contribution vs. Risk Contribution
* **Sector Return Contribution (Additive):**
  $$\text{contrib}_{i, t} = w_{\text{hold}, i, t} \times r_{i, t}$$
  Linear identity: $\sum_{i=1}^K \text{contrib}_{i, t} + c_{\text{cost}, t} = r_{\text{net}, t}$.
* **Sector Risk Contribution (Marginal Contribution to Risk / Component Volatility):**
  Let $\mathbf{w}_t$ be the portfolio weight vector and $\mathbf{\Sigma}_t$ be the trailing 60-day asset return covariance matrix.
  - Portfolio Volatility: $\sigma_p = \sqrt{\mathbf{w}_t^T \mathbf{\Sigma}_t \mathbf{w}_t}$.
  - Marginal Contribution to Risk (MCR): $\text{MCR}_i = \frac{(\mathbf{\Sigma}_t \mathbf{w}_t)_i}{\sigma_p}$.
  - Absolute Risk Contribution (Component Volatility): $\text{RC}_i = w_{i, t} \times \text{MCR}_i = w_{i, t} \frac{(\mathbf{\Sigma}_t \mathbf{w}_t)_i}{\sigma_p}$.
  - Euler's Theorem Decomposition: $\sum_{i=1}^K \text{RC}_i = \sigma_p$.
  - Percentage Risk Contribution: $\% \text{RC}_i = \frac{\text{RC}_i}{\sigma_p} = \frac{w_{i, t} (\mathbf{\Sigma}_t \mathbf{w}_t)_i}{\mathbf{w}_t^T \mathbf{\Sigma}_t \mathbf{w}_t}$, with $\sum_{i=1}^K \% \text{RC}_i = 100\%$.

#### 2. Herfindahl-Hirschman Index (HHI) and Effective Number of Assets ($N_{\text{eff}}$)
* Herfindahl-Hirschman Index: $HHI_t = \sum_i w_i(t)^2$.
* Effective Number of Constituents: $N_{\text{eff}, t} = \frac{1}{HHI_t} = \frac{1}{\sum_i w_i(t)^2}$.

#### 3. Treatment of Cash in Concentration Metrics
To avoid distorting concentration analysis in cash-toggle strategies (Variants 2A and 2B), two distinct HHI metrics will be computed and reported:
1. **Total Portfolio HHI ($HHI_{\text{total}}$):**
   Includes cash as a distinct asset:
   $$HHI_{\text{total}, t} = \sum_{i \in \text{Sectors}} w_{i, t}^2 + w_{\text{cash}, t}^2, \quad N_{\text{eff, total}, t} = \frac{1}{HHI_{\text{total}, t}}$$
   Reflects true balance-sheet concentration. When Strategy 2A holds 40% cash and 30% each in two sectors:
   $$HHI_{\text{total}} = 0.40^2 + 0.30^2 + 0.30^2 = 0.16 + 0.09 + 0.09 = 0.34 \implies N_{\text{eff, total}} = 2.94$$
2. **Equity-Only Sector HHI ($HHI_{\text{equity}}$):**
   Normalizes sector weights over the equity portion only:
   $$\tilde{w}_{i, t} = \frac{w_{i, t}}{1 - w_{\text{cash}, t}}, \quad HHI_{\text{equity}, t} = \sum_{i \in \text{Sectors}} \tilde{w}_{i, t}^2, \quad N_{\text{eff, equity}, t} = \frac{1}{HHI_{\text{equity}, t}}$$
   Isolates pure sector diversification independent of cash drag. In Strategy 2A, the two equity sectors are equal-weighted (50/50 of equity), yielding $HHI_{\text{equity}} = 0.50^2 + 0.50^2 = 0.50 \implies N_{\text{eff, equity}} = 2.0$.

---

### Investigation 4 — Subperiod Stability & Objective Environmental Partitions

#### 1. Empirical Calendar Year Partitioning & Reconciliation
The session counts across the 1,686 daily return intervals were independently audited and verified against `results/portfolio_backtest/daily_simulation_1A.parquet`:

| Calendar Year | Start Date | End Date | Daily Return Intervals ($N$) | Evaluation Classification | Notes |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **2019** | 2019-11-01 | 2019-12-31 | **41** | In-Sample (Training) | Partial Year (2 Months). Inception Date 0 is 2019-10-31 Close (42 price sessions, exactly 41 return intervals). |
| **2020** | 2020-01-02 | 2020-12-31 | **249** | In-Sample (Training) | Full Year. Pandemic crash (March) and liquidity recovery. |
| **2021** | 2021-01-04 | 2021-12-31 | **238** | In-Sample (Training) | Full Year. Broad secular bull market across sectors. |
| **2022** | 2022-01-03 | 2022-12-30 | **247** | In-Sample (Training) | Full Year. Global rate hikes and inflation consolidation. |
| **2023** | 2023-01-02 | 2023-12-29 | **245** | In-Sample (Training) | Full Year. Midcap and sectoral momentum expansion. |
| **2024** | 2024-01-02 | 2024-12-31 | **244** | In-Sample (Training) | Full Year. General election year and peak momentum. |
| **2025** | 2025-01-02 | 2025-12-31 | **247** | Previously Examined Holdout | Full Year. Out-of-Sample Part 1: Range-bound consolidation, FII outflows. |
| **2026** | 2026-01-02 | 2026-09-18 | **175** | Previously Examined Holdout | Partial Year (8.5 Months). Out-of-Sample Part 2: Tariff/geopolitical drag through terminal date. |
| **Total Full Cycle** | **2019-11-01** | **2026-09-18** | **1,686** | **Full History** | **Sum of all 8 calendar years: 41 + 249 + 238 + 247 + 245 + 244 + 247 + 175 = 1,686.** |

* **Reconciliation with 2026-10-23:**  
  The canonical historical market dataset downloaded in Phase 1 and frozen through Phase 10 terminates at **2026-09-18** (1,886 price dates from 2019-01-02 to 2026-09-18). The date `2026-10-23` appears in the repository as the execution timestamp of Phase 6/7 notebooks, NOT the historical market price cutoff. Strict research integrity rules prohibit downloading new historical data. Thus, 2026 coverage correctly terminates on `2026-09-18` with exactly **$N = 175$ return intervals**.
* Annualized metrics for partial years must use exact session counts: $\text{CAGR} = (\text{NAV}_{\text{end}} / \text{NAV}_{\text{start}})^{252 / N} - 1$.

#### 2. Causal 200-day SMA Warm-Up & Zero Dropped Evaluation Dates
* In `data/processed/aligned/nifty50_aligned.csv`, historical price records begin on **2019-01-02**.
* Exactly **200 trading sessions exist between 2019-01-02 and 2019-10-31** (Date 0).
* Therefore, the 200-day rolling simple moving average is already fully warmed up and populated on Date 0:
  $$\text{SMA}_{200}(\text{2019-10-31}) = 11,313.61, \quad \text{SMA}_{200}(\text{2019-11-01}) = 11,319.11$$
* **Zero evaluation sessions are dropped.** All 1,686 evaluation intervals possess a valid, non-null, causal 200-day SMA.
* **Causal Definition:** On session $t$, state is Bull if $P_{\text{NIFTY}, t} > \text{SMA}_{200}(t)$; Bear if $P_{\text{NIFTY}, t} \le \text{SMA}_{200}(t)$.

#### 3. Volatility Environment Partitions (Fixed India VIX Thresholds)
To prevent look-ahead contamination, VIX thresholds are derived strictly from the **Training-Period-Only (2019–2024) Distribution** and standard institutional benchmarks:
* **Low Volatility Environment:** India VIX $< 13.0$ (corresponds to lower quartile of training period; 20.6% of training sessions).
* **Normal Volatility Environment:** $13.0 \le \text{India VIX} < 18.0$ (interquartile training range; 40.1% of training sessions).
* **High Volatility / Stress Environment:** $\text{India VIX} \ge 18.0$ (upper quartile of training period; 39.3% of training sessions).
* **Fixed Invariance Rule:** These thresholds remain 100% fixed throughout the evaluation and are **never** re-estimated using holdout observations.

---

### Investigation 5 — Regime Stability & Transition Dynamics

#### 1. Regime-Conditional Metrics
Using causal state assignments (`accepted_regime` $\in \{0, 1, 2, 3, 4, 5\}$):
* Session count $N_k$ and time percentage $N_k / N_{\text{total}}$.
* Mean daily return and annualized net return: $\bar{r}_k \times 252$.
* Annualized sample volatility: $s_k \times \sqrt{252}$.
* Regime Sharpe ratio: $(\bar{r}_k \times 252) / (s_k \times \sqrt{252})$.
* Cumulative arithmetic return contribution: $\text{CumContrib}_k = \sum_{t \in \mathcal{T}_k} r_{\text{net}, t}$.

#### 2. Transition vs. Steady-State Holding Analysis
* **Transition Sessions:** Rebalance execution sessions ($t+1$ Close) where target weights change.
* **Steady-State Sessions:** Sessions where portfolio drifts without rebalancing.
* Compare return distributions, transaction costs paid, and slippage between transition days and stationary holding days.

---

### Investigation 6 — Parameter and Model Sensitivity Grid

#### 1. Geometry of the 42-Cell Primary Parameter Grid (Strategy 1A)
The primary sensitivity exploration evaluates a complete 2D parameter grid on **Strategy 1A** (the reference strategy):
* **Confidence Threshold ($P_{\text{thresh}}$) — 7 Values:**
  $$P_{\text{thresh}} \in \{0.40, 0.45, 0.50 \text{ [baseline]}, 0.55, 0.60, 0.65, 0.70\}$$
  (Minimum: 0.40, Baseline: 0.50, Maximum: 0.70; uniform step: 0.05).
* **Minimum Holding Lockup ($T_{\text{lock}}$) — 6 Values:**
  $$T_{\text{lock}} \in \{1 \text{ [Min]}, 3, 5 \text{ [Baseline]}, 10, 15, 20 \text{ [Max]}\} \text{ trading sessions}$$
* **Total Primary Grid Combinations:** $7 \times 6 = \mathbf{42 \text{ parameter cells}}$.

#### 2. Parameter Range Justifications
* $P_{\text{thresh}} < 0.40$ approaches noise (since with 6 states, uniform prior is $1/6 \approx 0.167$, and dominant states rarely fall below 0.35).
* $P_{\text{thresh}} > 0.70$ causes extreme model paralysis where new regimes are almost never accepted, locking the incumbent regime indefinitely.
* $T_{\text{lock}} = 1$ tests instantaneous rebalancing (zero lockup, maximum whipsaw exposure).
* $T_{\text{lock}} = 20$ represents monthly rebalance lockup (20 trading sessions $\approx 1$ calendar month).

#### 3. Treatment of Volatility Lookback ($L_{\text{vol}}$)
* For Strategy 1A and 2A (Equal-Weight), $L_{\text{vol}}$ is **not applicable** because equity sectors are allocated 50/50. $L_{\text{vol}}$ is omitted from the primary grid.
* For Inverse-Volatility variants (1B and 2B), $L_{\text{vol}}$ is **frozen at the 20-day baseline** during boundary cross-checks, and evaluated in a dedicated **1D Sensitivity Slice**:
  $$L_{\text{vol}} \in \{10, 20 \text{ [baseline]}, 40\} \text{ trading sessions}$$
  at baseline $P=0.50, T=5$. This keeps reporting structured and prevents a 3D combinatorial explosion.

#### 4. Diagnostic Topography vs. Optimization Safeguard
* **Explicit Research Boundary:** The 42-cell grid is strictly a diagnostic tool to map the **stability surface** (verifying that CAGR and Sharpe degrade smoothly rather than falling off a cliff).
* **No Optimization Rule:** Under no circumstances will any parameter pair from this grid be selected or retroactively substituted as a "new best" strategy for the holdout period.

#### 5. True Extreme Boundary Cross-Checks for Variants 1B, 2A, and 2B
To rigorously test whether sensitivity patterns hold across asset allocation templates and weighting schemes at the true parameter bounds, a standardized **$3 \times 3 = 9$ cell Extreme Boundary Matrix** will be evaluated on Variants 1B, 2A, and 2B:
$$P_{\text{thresh}} \in \{0.40 \text{ [Min]}, 0.50 \text{ [Baseline]}, 0.70 \text{ [Max]}\} \times T_{\text{lock}} \in \{1 \text{ [Min]}, 5 \text{ [Baseline]}, 20 \text{ [Max]}\}$$
($9 \times 3 = 27$ runs total).  
*Clarification on Boundary Selection:* Incorporating the true extrema ($P=0.70$ and $T=20$) rather than intermediate points ($P=0.60, T=10$) ensures that the cross-check tests genuine outer boundaries (paralysis vs. churn) across all strategy variants.

---

### Investigation 7 — Benchmark Sensitivity & Naive Momentum Comparator

#### 1. Dual-Beta Regression (Up-Market vs. Down-Market Beta)
Estimate separate market sensitivities conditional on benchmark direction:
$$r_{\text{strat}, t} = \alpha + \beta^+ \max(r_{\text{mkt}, t}, 0) + \beta^- \min(r_{\text{mkt}, t}, 0) + \epsilon_t$$
* $\Delta \beta = \beta^+ - \beta^-$ measures directional asymmetry. A positive $\Delta \beta$ indicates higher upside participation than downside exposure.

#### 2. Up-Market and Down-Market Capture Ratios
$$\text{Up Capture} = \frac{\bar{r}_{\text{strat}}^+}{\bar{r}_{\text{mkt}}^+}, \quad \text{Down Capture} = \frac{\bar{r}_{\text{strat}}^-}{\bar{r}_{\text{mkt}}^-}, \quad \text{Capture Ratio} = \frac{\text{Up Capture}}{\text{Down Capture}}$$
A Capture Ratio $> 1.0$ indicates favorable asymmetric return capture.

#### 3. Market Timing Curvature (Treynor-Mazuy Model)
$$r_{\text{strat}, t} = \alpha + \beta_1 r_{\text{mkt}, t} + \gamma r_{\text{mkt}, t}^2 + \epsilon_t$$
$\gamma > 0$ indicates statistically significant convex market timing skill.

#### 4. Naive Top-2 Cross-Sectional Momentum Comparator
To establish whether the HMM regime discovery adds structural predictive value over naive price momentum, an active momentum benchmark will be constructed adhering to strict fair-methodology principles:
1. **Investable Universe:** Identical 6 sector indices (AUTO, BANK, FMCG, IT, METAL, PHARMA).
2. **Causal Signal Formulation:** On month-end signal session $t$, compute trailing 20-trading-day simple price return for each sector:
   $$R_{i, 20d}(t) = \frac{P_{i, t}}{P_{i, t-20}} - 1$$
   Strictly causal, using only closing prices available at session $t$ close.
3. **Portfolio Allocation:** Top 2 sectors with the highest trailing 20-day return, allocated strictly **50% / 50% Equal-Weight**.
   - Zero cash toggle (100% equity invested at all times).
   - Zero inverse-volatility weighting (strictly fixed 0.50 / 0.50).
   - Zero HMM probabilities, confidence thresholds, or hidden state inputs.
4. **Rebalance Schedule:** Calendar month-end signal at date $t$ Close, executing at date $t+1$ Close (identical to Benchmark B).
5. **Execution & Cost Accounting:** Evaluated through the identical `simulate_portfolio` engine, with intra-month price drift, actual one-way turnover tracking, and 15 bps fee deduction.
6. **Benchmark Hierarchy:** **NIFTY 50 remains the primary statutory benchmark.** The Naive Momentum Benchmark serves as a supplementary active factor comparator.

---

## 5. Summary of Recommended Testing Scope

| Investigation | Scope Recommendation | Evaluated Variants | Total Output Rows |
| :--- | :---: | :---: | :---: |
| **Inv 1: Cost Sensitivity** | **All 4 Strategies** | 1A, 1B, 2A, 2B | 84 rows (4 strat $\times$ 7 costs $\times$ 3 per) |
| **Inv 2: Execution Sensitivity** | **All 4 Strategies** | 1A, 1B, 2A, 2B | 48 rows (4 strat $\times$ 4 models $\times$ 3 per) |
| **Inv 3: Concentration** | **All 4 Strategies** | 1A, 1B, 2A, 2B | 12 rows (4 strat $\times$ 3 per) + sector risk/return breakdown |
| **Inv 4: Subperiod Stability** | **All 4 Strategies + BM** | 1A, 1B, 2A, 2B, NIFTY 50 | 65 rows (5 ports $\times$ 13 subperiods) |
| **Inv 5: Regime Stability** | **All 4 Strategies** | 1A, 1B, 2A, 2B | 72 rows (4 strat $\times$ 6 regimes $\times$ 3 per) |
| **Inv 6: Parameter Grid** | **Primary (1A) + True Boundary Checks**| 1A full (42); 1B, 2A, 2B extrema (9 each) | 213 rows ((42 + 27 + 2 vol) $\times$ 3 per) |
| **Inv 7: Benchmark Sensitivity**| **All 4 Strategies** | 1A, 1B, 2A, 2B | 24 rows + momentum benchmark rows |

---

## 6. Proposed Parquet Output Architecture

All numerical records will be persisted in Apache Parquet format in `results/portfolio_backtest/robustness/`:

```
results/portfolio_backtest/robustness/
├── cost_sensitivity.parquet                     (Investigation 1: 0–30 bps grid)
├── execution_sensitivity.parquet                (Investigation 2: t+1, t+2, t Close, t+1 Open)
├── concentration_metrics.parquet                (Investigation 3: HHI_total, HHI_equity, N_eff)
├── sector_risk_return_attribution.parquet       (Investigation 3: Return contrib & Component Vol)
├── subperiod_stability.parquet                  (Investigation 4: Calendar years, SMA bull/bear, VIX)
├── regime_stability.parquet                     (Investigation 5: HMM regime-conditional performance)
├── parameter_sensitivity.parquet                (Investigation 6: 42-cell 1A grid + boundary checks)
├── benchmark_sensitivity.parquet                (Investigation 7: Dual Beta, Capture Ratios, TM Gamma)
└── momentum_benchmark_comparison.parquet        (Investigation 7: Naive Top-2 Momentum comparator)
```

Human-readable Markdown documentation and analytical commentary will be authored in `reports/phase10_6_robustness_testing.md` upon completion of implementation.

---

## 7. Reporting & Research Integrity Standards

1. **Segregation of Periods:** Every table and visualization must explicitly segregate Training (1,264 sessions), Previously Examined Holdout (422 sessions), and Full Cycle (1,686 sessions).
2. **Terminology Protocol:** The 2025–2026 holdout period must **never** be described as an "untouched", "unseen", or "fresh" test set. It is formally designated as the **"Previously Examined Out-of-Sample Holdout"**.
3. **No Retuning or Re-Optimization:** Robustness testing is purely diagnostic. Discovered parameter sensitivities must not be used to retroactively optimize or replace canonical strategy definitions.
4. **Frozen Baselines:** Phase 1–10.3 and Phase 10.5 canonical schedules, HMM models, transition matrices, prices, and backtest results remain 100% frozen.

---

## 8. Final Approval Checklist

| # | Item | Status | Final Verification Details |
| :-: | :--- | :---: | :--- |
| **1** | **Parameter Grid Extrema** | **READY** | $7 \times 6 = 42$ cell primary grid on Strategy 1A ($P \in [0.40, 0.70]$, $T \in [1, 20]$). $3 \times 3 = 9$ cell True Extreme Boundary Matrix ($P \in \{0.40, 0.50, 0.70\} \times T \in \{1, 5, 20\}$) for 1B, 2A, 2B. Diagnostic-only principle strictly enforced. |
| **2** | **Session Counts & Alignment** | **VERIFIED** | 2019 $N = 41$ return intervals (42 price sessions starting 2019-10-31); 2026 $N = 175$ return intervals. Sum of all 8 years = 1,686. Historical price dataset terminates on 2026-09-18 (2026-10-23 is notebook execution timestamp). |
| **3** | **Naive Top-2 Momentum Comparator** | **READY** | Strictly 50/50 equal-weight across top-2 trailing 20-day return sectors. Zero cash toggle, zero inverse-vol, zero HMM inputs. Monthly rebalance at $t+1$ Close, 15 bps fee. NIFTY 50 primary. |
| **4** | **Causal Initialization (SMA & VIX)** | **VERIFIED** | Exactly 200 warm-up sessions exist between 2019-01-02 and 2019-10-31. 200-day rolling SMA is valid on Day 1 (zero evaluation dates dropped). VIX cutoffs ($<13, 13-18, \ge 18$) fixed on training period. |
| **5** | **Output Architecture** | **READY** | Parquet format under `results/portfolio_backtest/robustness/`. Summary report in Markdown under `reports/`. |

---

### Audit Sign-Off Confirmation
- **Audit Mode:** Strictly Read-Only Feasibility Audit.
- **Repository Modifications:** Zero source code files, tests, notebooks, datasets, models, or canonical backtest artifacts were modified.
- **Execution Status:** **AUDIT FINALIZED. READY FOR PHASE 10.6 IMPLEMENTATION UPON FINAL APPROVAL.**
