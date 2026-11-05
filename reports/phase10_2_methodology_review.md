# Phase 10.2: Independent Methodology Review and Validation Report

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Phase:** 10.2 (Methodology Review & Architectural Validation — Updated Revision)  
**Date:** November 4, 2026  
**Auditor:** Quantitative Strategy Review & Validation Framework  
**Verdict:** **APPROVED**  

---

## 1. Executive Summary

This independent methodology review conducts a comprehensive mathematical, temporal, and operational validation of the complete Phase 10 historical backtesting framework.

Phase 10 evaluates four frozen sector rotation strategies (Variants **1A**, **1B**, **2A**, and **2B**) constructed across 1,687 trading sessions from `2019-10-31` to `2026-09-18` (1,265 training sessions and 422 protected holdout sessions). The strategies utilize causal, forward-filtered six-state Gaussian HMM probabilities and trade across six sectoral indices (`AUTO`, `BANK`, `FMCG`, `IT`, `METAL`, `PHARMA`), the `NIFTY50` benchmark, and cash reserves.

### Review Summary & Final Status
Following an independent peer audit of the initial Phase 10.2 review, all identified mathematical, operational, and benchmarking refinements have been fully formalized and reconciled:
1. **Dynamic Drift-Adjusted Actual Turnover:** Transaction costs are billed on dynamic pre-trade drifted weights rather than static Phase 9 nominal schedule turnover.
2. **Observation-Count & Boundary Convention for CAGR:** The compounding parameter $N$ is strictly defined as the number of **daily return intervals** ($N = 1,686$ full; $N = 1,264$ training; $N = 422$ holdout). The boundary-spanning return (`2024-12-31` Close $\to$ `2025-01-02` Close) is unambiguously assigned to the holdout period, preserving continuous capital without duplication or loss.
3. **Annualized Arithmetic Sortino Ratio:** The Sortino ratio formula has been corrected to use the standard annualized arithmetic mean net return in the numerator rather than compounded CAGR, eliminating formulaic distortion.
4. **Day 0 Strategy Funding & Benchmark Initialization:** Initial portfolio allocation sequences and monthly benchmark rebalancing mechanics are synchronized under the identical next-session-close ($t+1$ Close) execution delay.
5. **Attribution Exactness:** Daily asset and cost contributions reconcile additively to net portfolio returns with zero approximation error.
6. **Hypothetical 6% Cash Sensitivity:** Formally decoupled from empirical historical assertions and defined with an exact daily geometric compounding rate.
7. **Price Return (PR) Methodology:** Clarified as a strict Price Return framework without unverified quantitative dividend yield estimates.

All issues are resolved, and the methodology is **APPROVED** for Phase 10.3 implementation.

---

## 2. Overall Methodology Assessment

| Methodology Dimension | Evaluation | Final Assessment & Resolution |
| :--- | :---: | :--- |
| **Price Return Series** | **APPROVED** | `Close` prices across all 7 indices provide synchronized, clean data. Validated as Price Return (PR) without constituent dividend reinvestment. |
| **Execution Timing** | **APPROVED** | Next-session close ($t+1$ Close) execution completely eliminates look-ahead bias across both strategies and the monthly benchmark. |
| **Portfolio Drift Formulation** | **APPROVED** | Dynamic weights drift naturally with asset returns between rebalances; denominator correctly accounts for equity returns and zero-return cash. |
| **Turnover Accounting** | **APPROVED** | Actual one-way turnover computed dynamically from pre-trade drifted weights and new target weights; billed only when `rebalance_triggered == True`. |
| **Transaction-Cost Deduction** | **APPROVED** | 15 bps one-way fee deducted from pre-trade NAV at execution close. Cumulative costs reported separately from CAGR drag. |
| **Benchmark Design** | **APPROVED** | NIFTY 50 Buy-and-Hold (gross/net identical at 0 bps) and Equal-Weight 6-Sector Benchmark (rebalanced monthly at $t+1$ Close; reported gross and net). |
| **Train/Holdout Boundary** | **APPROVED** | Continuous portfolio state; boundary return assigned to holdout; training has 1,264 return intervals, holdout has 422 ($1,264 + 422 = 1,686$). |
| **Performance Metrics** | **APPROVED** | CAGR defined with exact return interval counts; Sortino ratio corrected to standard annualized arithmetic form. |
| **Attribution Framework** | **APPROVED** | Beginning-of-period asset contributions plus exact cost drag sum to net return without approximation. |

---

## 3. Section-by-Section Review & Operational Conventions

### 3.1 Price-Series Methodology & Dividend Limitation
- **Approved Price Series:** `Close` prices from `data/processed/aligned/` for all seven indices (`nifty_auto`, `nifty_bank`, `nifty_fmcg`, `nifty_it`, `nifty_metal`, `nifty_pharma`, `nifty50`).
- **Daily Asset Simple Return:**
  $$r_{i, t} = \frac{P_{i, t}}{P_{i, t-1}} - 1, \quad \forall i \in \{\text{AUTO}, \text{BANK}, \text{FMCG}, \text{IT}, \text{METAL}, \text{PHARMA}, \text{NIFTY50}\}$$
- **Cash Return Baseline:** $r_{\text{cash}, t} = 0.0000$ (0% nominal return). Cash preserves nominal capital without interest or depreciation.
- **Price Return (PR) Disclosure:**  
  All seven index series represent Price Return indices. Upstream data providers (Yahoo Finance) do not incorporate or reinvest constituent cash dividends for Indian cash index tickers.  
  - Consequently, the backtest evaluates **pure capital appreciation** of the sector rotation strategy and its benchmarks.
  - The methodology does not assume or introduce unverified dividend yield adjustments.
  - In real-world institutional implementation, an investor holding physical constituent equity baskets or Total Return Index (TRI) ETFs would capture incremental cash dividends. The Price Return evaluation is therefore strictly conservative.

### 3.2 Signal and Execution Timing
- **Signal Generation ($t$ Close):** At session $t$ Close ($15:30$ IST), continuous causal filtered probabilities $p_j(t)$ are evaluated. If $\max_j p_j(t) \ge 0.50$ and holding duration $\ge 5$ trading days (or if an R3 crisis override occurs), target weights $w_{i, t}^{\text{target}}$ are generated.
- **Interim Holding Window ($t \to t+1$):** During the interval between Date $t$ Close and Date $t+1$ Close, incumbent portfolio holdings remain entirely in effect and earn the market return over $t \to t+1$.
- **Execution Event ($t+1$ Close):** Rebalancing executes at Date $t+1$ Close ($15:30$ IST) using the closing prices of session $t+1$. Transaction costs are calculated and deducted at this point.
- **New Target Holding Window ($t+1 \to t+2$):** Post-trade target weights earn market returns beginning from session $t+1$ Close to session $t+2$ Close.
- **Terminal Session Exclusion ($T = \text{2026-09-18}$):** The final signal generated at Date $T$ Close cannot be executed because no subsequent session ($T+1$) exists in the verified dataset. Therefore, the backtest return sequence spans exactly $N = 1,686$ return intervals across 1,687 daily price observations. No synthetic prices or extrapolated returns are generated.

### 3.3 Strategy Day 0 Initialization & Funding Contract
Inspection of the first row of `results/portfolio_construction/target_weights_1A.csv` establishes the exact initial sequence:
- **Date 0 (`2019-10-31` Close):**  
  Strategy portfolio is initialized with initial wealth $\text{NAV}_0 = 1.0000$ invested 100% in the NIFTY 50 benchmark ($w_{\text{NIFTY50}, 0} = 1.0$, all other assets $= 0.0$).  
  At Date 0 Close, the rules engine receives the first confident signal (Regime 4) and schedules a rebalance for execution at Date 1 Close (`2019-11-01`).
- **Date 1 (`2019-11-01` Close):**  
  Between Date 0 Close and Date 1 Close, the portfolio holds 100% NIFTY 50, earning:
  $$R_{\text{gross}, 1} = r_{\text{NIFTY50}, 1}$$
  $$\text{NAV}_{\text{pre}, 1} = \text{NAV}_0 \times (1 + r_{\text{NIFTY50}, 1})$$
  Pre-trade drifted weights at Date 1 Close are $\tilde{w}_{\text{NIFTY50}, 1} = 1.0$ (all other assets $= 0.0$).  
  At Date 1 Close, the first rebalance executes into target sector weights (e.g., 50% AUTO + 50% METAL for Variant 1A):
  $$\text{TO}_{\text{actual}, 1} = \frac{1}{2} (|0.0 - 1.0| + |0.5 - 0.0| + |0.5 - 0.0|) = 1.0000 \quad (100\% \text{ turnover})$$
  $$\text{TC}_1 = \text{NAV}_{\text{pre}, 1} \times 1.0000 \times 0.0015$$
  $$\text{NAV}_1 = \text{NAV}_{\text{pre}, 1} - \text{TC}_1$$
  Post-trade weights at Date 1 Close become $w_{\text{AUTO}, 1} = 0.50$, $w_{\text{METAL}, 1} = 0.50$, $w_{\text{NIFTY50}, 1} = 0.00$.
- **Date 2 (`2019-11-04` Close):**  
  Target sector weights earn market returns over Date 1 Close $\to$ Date 2 Close.

### 3.4 Portfolio Drift Formulation
Between authorized rebalances, individual asset values fluctuate with market price movements, altering relative weights.

Let $w_{i, t-1}$ denote the post-trade portfolio weight of asset $i$ at session $t-1$ Close ($\sum_i w_{i, t-1} = 1.0$).  
Over session $t-1 \to t$, asset prices change by simple return $r_{i, t}$ (with $r_{\text{cash}, t} = 0.0$).

The pre-trade drifted weight of asset $i$ at session $t$ Close is:
$$\tilde{w}_{i, t} = \frac{w_{i, t-1} (1 + r_{i, t})}{\sum_{j \in \text{Assets}} w_{j, t-1} (1 + r_{j, t})}$$

Where the denominator represents the gross portfolio return factor:
$$1 + R_{\text{gross}, t} = \sum_{j \in \text{Assets}} w_{j, t-1} (1 + r_{j, t}) = \sum_{s \in \text{Sectors}} w_{s, t-1} (1 + r_{s, t}) + w_{\text{cash}, t-1} \cdot 1.0 + w_{\text{NIFTY50}, t-1} (1 + r_{\text{NIFTY50}, t})$$

- **Simplex Invariant:** Sum of pre-trade drifted weights strictly equals 1:
  $$\sum_{i} \tilde{w}_{i, t} = \frac{\sum_{i} w_{i, t-1} (1 + r_{i, t})}{1 + R_{\text{gross}, t}} = 1.0$$
- **Non-Rebalance Sessions:** If `rebalance_triggered == False` on session $t$, post-trade weights equal pre-trade drifted weights:
  $$w_{i, t} = \tilde{w}_{i, t}$$
  Daily schedule rows in the target weights CSV must NOT reset portfolio weights to target weights on non-rebalance days.

### 3.5 Actual Turnover Formulation
Phase 9 target-weight schedules recorded nominal target-to-target turnover ($\text{TO}_{\text{nominal}} = \frac{1}{2}\sum |w_{i, t}^{\text{target}} - w_{i, t-1}^{\text{target}}|$). In Phase 10 backtesting, realized trading turnover must be calculated from pre-trade drifted weights:

When an authorized rebalance executes at session $t$ Close (`rebalance_triggered == True`):
$$\text{TO}_{\text{actual}, t} = \frac{1}{2} \sum_{i \in \text{Assets}} |w_{i, t}^{\text{target}} - \tilde{w}_{i, t}|$$

- **One-Way Turnover Definition:** In an all-long portfolio with cash where $\sum w_i^{\text{target}} = \sum \tilde{w}_i = 1.0$, total purchases equal total sales:
  $$\sum_{i: w_i^{\text{target}} > \tilde{w}_i} (w_i^{\text{target}} - \tilde{w}_i) = \sum_{i: w_i^{\text{target}} < \tilde{w}_i} (\tilde{w}_i - w_i^{\text{target}}) = \frac{1}{2} \sum_{i} |w_i^{\text{target}} - \tilde{w}_i|$$
  This measures the fraction of portfolio equity traded one-way. Gross two-way volume is $2 \times \text{TO}_{\text{actual}, t}$.
- **Non-Rebalance Sessions:** When `rebalance_triggered == False`, $\text{TO}_{\text{actual}, t} = 0.0000$.

### 3.6 Transaction-Cost Accounting & Separate Reporting
- **Frozen Parameter:** One-way transaction cost rate $c = 15\text{ bps} = 0.0015$.
- **Deduction Timing:** Deducted at the execution close (session $t$ Close) from pre-trade NAV:
  $$\text{NAV}_{\text{pre}, t} = \text{NAV}_{t-1} \times (1 + R_{\text{gross}, t})$$
  $$\text{TC}_t = \begin{cases} \text{NAV}_{\text{pre}, t} \times \text{TO}_{\text{actual}, t} \times c, & \text{if } \text{rebalance\_triggered} == \text{True} \\ 0.0, & \text{if } \text{rebalance\_triggered} == \text{False} \end{cases}$$
  $$\text{NAV}_t = \text{NAV}_{\text{pre}, t} - \text{TC}_t = \text{NAV}_{\text{pre}, t} \times (1 - \text{TO}_{\text{actual}, t} \times c)$$
- **Strict Distinction in Reporting:**
  Transaction costs must be reported as separate, unambiguous metrics:
  1. **Cumulative Transaction Costs Paid ($\text{TC}_{\text{cum}}$):** The arithmetic sum of all realized cost deductions expressed relative to unit initial capital:
     $$\text{TC}_{\text{cum}} = \sum_{t=1}^N \text{TC}_t$$
  2. **Gross Compounded Annual Growth Rate ($\text{CAGR}_{\text{gross}}$):** Computed on the gross return sequence with $c = 0$.
  3. **Net Compounded Annual Growth Rate ($\text{CAGR}_{\text{net}}$):** Computed on the net return sequence after 15 bps deductions.
  4. **CAGR Drag ($\Delta_{\text{CAGR}}$):**
     $$\Delta_{\text{CAGR}} = \text{CAGR}_{\text{gross}} - \text{CAGR}_{\text{net}}$$
  > **Explicit Requirement:** The CAGR difference ($\Delta_{\text{CAGR}}$) represents an annualized compounding drag and must NEVER be labeled as the cumulative transaction costs paid.

---

## 4. Benchmark Methodology & Synchronization

Two passive benchmark portfolios provide dual performance reference:

### 4.1 Benchmark 1: NIFTY 50 Buy-and-Hold
- **Initialization:** Funded at `2019-10-31` Close with wealth $1.0000$ in 100% NIFTY 50.
- **Return Attribution:** Earns $r_{\text{NIFTY50}, t}$ on each session $t \ge 1$.
- **Transaction Costs:** 0 bps. Because buy-and-hold involves zero trading after initial funding, gross and net returns are identical.
- **Fairness:** Provides an untraded passive benchmark subject to the identical Price Return data convention.

### 4.2 Benchmark 2: Equal-Weight 6-Sector Benchmark
- **Asset Universe:** Six equal sectors (`AUTO`, `BANK`, `FMCG`, `IT`, `METAL`, `PHARMA`).
- **Initial Condition:** Initialized at `2019-10-31` Close with $w_{s, 0} = 1/6 \approx 16.6667\%$ for each sector. This is the benchmark's starting boundary condition, not a trade charged within the evaluation timeline.
- **Rebalance Signal & Execution Calendar:**
  - **Rebalance Signal:** Signaled at the final trading session of each calendar month Close.
  - **Rebalance Execution:** Executes at the Close of the **first trading session of the next calendar month** ($t+1$ Close).
  - **Drift Between Month-Ends:** Holdings drift naturally with individual sector returns between month-ends.
  - **Turnover & Cost:** Actual turnover $\text{TO}_{\text{actual}, t} = \frac{1}{2}\sum_s |1/6 - \tilde{w}_{s, t}|$ is calculated at each executed monthly rebalance.
- **Dual Reporting:** The Equal-Weight Benchmark is reported both:
  1. **Gross Benchmark Return:** 0 bps transaction cost.
  2. **Net Benchmark Return:** After deducting 15 bps one-way cost on actual monthly turnover.
- **Disclosure of Starting Allocation Asymmetry:**  
  The strategy begins on Day 0 in 100% NIFTY 50 (rebalancing on Day 1 into target sectors), whereas Benchmark 2 begins on Day 0 in 1/6 equal sectors. This distinction is preserved as a frozen project specification and disclosed in all comparison tables.

---

## 5. Training, Holdout, and CAGR Observation-Count Conventions

### 5.1 Timeline Partitioning & Return Interval Counts
The dataset contains 1,687 daily price sessions and exactly **1,686 single-period return intervals**:

| Evaluation Period | Price Date Range | Price Observations | Daily Return Intervals ($N$) | Boundary Assignment Rationale |
| :--- | :---: | :---: | :---: | :--- |
| **Training Period** | `2019-10-31` to `2024-12-31` | 1,265 | **1,264** | Spans intervals $t=1$ (`2019-11-01`) through $t=1,264$ (`2024-12-31`). |
| **Protected Holdout** | `2025-01-02` to `2026-09-18` | 422 | **422** | Spans intervals $t=1,265$ (`2025-01-02`) through $t=1,686$ (`2026-09-18`). |
| **Full Timeline** | `2019-10-31` to `2026-09-18` | 1,687 | **1,686** | Exactly equals $1,264 + 422 = 1,686$ return intervals. |

### 5.2 Boundary-Spanning Return Assignment
The return interval between `2024-12-31` Close and `2025-01-02` Close spans the New Year holiday boundary.
- **Segment Assignment:** Assigned strictly to the **Holdout Period** ($t = 1,265$).
- **Methodological Rationale:**  
  1. In out-of-sample portfolio evaluation, training ends at the close of the final in-sample session (`2024-12-31` Close). The portfolio value at that point ($\text{NAV}_{\text{train\_end}}$) serves as the baseline initial capital for the holdout period.
  2. The price that realizes the return across the boundary is observed at `2025-01-02` Close, which is the first calendar day of the holdout period.
  3. This assignment yields exactly 422 return intervals for the 422 holdout dates, preserving continuous capital without duplicating or omitting any trading session.
- **Exact Compounding Identity:**
  $$\frac{\text{NAV}_{1686}}{\text{NAV}_0} = \frac{\text{NAV}_{1264}}{\text{NAV}_0} \times \frac{\text{NAV}_{1686}}{\text{NAV}_{1264}}$$
  $$(1 + \text{TR}_{\text{full}}) = (1 + \text{TR}_{\text{train}}) \times (1 + \text{TR}_{\text{holdout}})$$

### 5.3 Correct CAGR Formula
CAGR must use the number of **daily return intervals** ($N$), NOT price observations:
$$\text{CAGR} = \left(\frac{\text{NAV}_{\text{end}}}{\text{NAV}_{\text{start}}}\right)^{\frac{252}{N}} - 1$$
- **Full Period:** $N = 1,686$, exponent $= \frac{252}{1686}$.
- **Training Period:** $N = 1,264$, exponent $= \frac{252}{1264}$.
- **Holdout Period:** $N = 422$, exponent $= \frac{252}{422}$.

---

## 6. Corrected Performance Metric Definitions

All Phase 10 metrics will adhere to standard quantitative finance formulations:

### 6.1 Return Metrics
- **Cumulative Total Return (TR):**
  $$\text{TR} = \frac{\text{NAV}_T}{\text{NAV}_0} - 1$$
- **Compound Annual Growth Rate (CAGR):**
  $$\text{CAGR} = \left(\frac{\text{NAV}_T}{\text{NAV}_0}\right)^{\frac{252}{N}} - 1$$
- **Calendar-Year Returns:** Compounded return within calendar years ($2020 \dots 2025$, and partials $2019, 2026$).

### 6.2 Risk Metrics
- **Annualized Volatility ($\sigma_{\text{ann}}$):**
  $$\sigma_{\text{ann}} = \sqrt{252} \times \sqrt{\frac{1}{N-1} \sum_{t=1}^N (R_{\text{net}, t} - \bar{R}_{\text{net}})^2}$$
- **Maximum Drawdown (MDD):**
  $$\text{Peak}_t = \max_{0 \le \tau \le t} \text{NAV}_\tau, \quad \text{DD}_t = \frac{\text{NAV}_t - \text{Peak}_t}{\text{Peak}_t}, \quad \text{MDD} = \min_{1 \le t \le T} \text{DD}_t$$
- **Annualized Downside Deviation ($\sigma_{\text{down}}$):**
  $$\sigma_{\text{down}} = \sqrt{252} \times \sqrt{\frac{1}{N} \sum_{t=1}^N \min(0, R_{\text{net}, t})^2}$$
  (Evaluated against a minimum acceptable return target of 0%).

### 6.3 Risk-Adjusted Return Metrics
- **Annualized Sharpe Ratio (Zero Risk-Free Baseline):**
  $$\text{Sharpe} = \frac{\bar{R}_{\text{net}}}{\text{std}(R_{\text{net}})} \times \sqrt{252}$$
- **Corrected Annualized Sortino Ratio:**
  Standard annualized arithmetic-return formulation:
  $$\text{Sortino} = \frac{\bar{R}_{\text{net}} \times 252}{\sigma_{\text{down}}}$$
  > **Correction Implemented:** Eliminates formulaic distortion by ensuring the numerator is the annualized arithmetic mean return ($\bar{R}_{\text{net}} \times 252$) rather than compounded CAGR. CAGR remains a separate compounded-return metric.
- **Information Ratio (vs. Benchmarks):**
  $$\text{IR} = \frac{\text{mean}(R_{\text{net}} - R_{\text{BM}}) \times 252}{\text{std}(R_{\text{net}} - R_{\text{BM}}) \times \sqrt{252}}$$

---

## 7. Performance Attribution Reconciliation

Attribution must decompose daily and cumulative returns without approximation error:

1. **Asset-Level Gross Contribution:**
   $$C_{i, t} = w_{i, t-1} \times r_{i, t}$$
   Where $w_{i, t-1}$ is the beginning-of-period weight.
2. **Gross Return Identity:**
   $$R_{\text{gross}, t} = \sum_{i \in \text{Assets}} C_{i, t}$$
3. **Exact Transaction Cost Contribution:**
   $$C_{\text{cost}, t} = R_{\text{net}, t} - R_{\text{gross}, t} = -\text{TO}_{\text{actual}, t} \times c \times (1 + R_{\text{gross}, t})$$
4. **Exact Net Return Identity:**
   $$R_{\text{net}, t} = \sum_{i \in \text{Assets}} C_{i, t} + C_{\text{cost}, t}$$
   > **Implementation Rule:** Cumulative asset contributions and cost drag must reconcile to total portfolio return without using the linear approximation $-\text{TO}_{\text{actual}} \times c$.

---

## 8. Robustness & Hypothetical 6% Cash Sensitivity

### 8.1 Transaction Cost Sensitivity Grid
- $0\text{ bps}$ (frictionless reference)
- $10\text{ bps}$ (institutional direct execution)
- $15\text{ bps}$ (**Frozen Baseline**)
- $25\text{ bps}$ (elevated friction/retail slippage)
- $30\text{ bps}$ (stress test)

### 8.2 Hypothetical 6% Cash-Yield Sensitivity
- **Baseline:** $r_{\text{cash}, t} = 0.0000$ (0% nominal return).
- **Sensitivity Scenario Formulation:**
  A hypothetical scenario evaluating cash balances earning an annualized yield of 6.0%:
  $$r_{\text{cash}, \text{daily}} = (1.06)^{\frac{1}{252}} - 1 \approx 0.0002313 \quad (2.313\text{ bps/day})$$
  Applied solely to cash allocations ($w_{\text{CASH}}$) during sensitivity reporting.
  > **Explicit Requirement:** This scenario is strictly labeled as a **"Hypothetical 6% Cash-Yield Scenario"**. It is not presented as empirical Indian Treasury Bill or MIBOR data. Baseline results remain unadjusted at 0% cash yield.

---

## 9. Comprehensive Corrections & Resolution Matrix

| # | Methodology Item | Initial Review Status | Approved Resolution & Operational Rule |
| :---: | :--- | :---: | :--- |
| **1** | **Turnover Modeling** | Major Correction | Billed on actual one-way turnover: $\text{TO}_{\text{actual}} = \frac{1}{2}\sum \|w_i^{\text{target}} - \tilde{w}_i\|$. Nominal turnover discarded for cost calculation. |
| **2** | **Terminal Session Boundary** | Major Correction | Terminal session (`2026-09-18`) signal is untraded. Timeline spans 1,686 daily return intervals. |
| **3** | **Day 0 $\to$ Day 1 Funding** | Major Correction | Initialized in 100% NIFTY 50 on Day 0. Earns NIFTY 50 return on Day 1. First rebalance executes at Day 1 Close (100% turnover fee). Sector returns start Day 2. |
| **4** | **Benchmark Rebalancing Delay** | Major Correction | Equal-Weight Benchmark initialized at 1/6 on `2019-10-31`. Monthly rebalances signal at month-end Close and execute at next session Close ($t+1$). |
| **5** | **CAGR Interval Count ($N$)** | Refinement Added | Exponent uses return intervals ($N=1,686$ full; $N=1,264$ train; $N=422$ holdout). Boundary return assigned to holdout. |
| **6** | **Sortino Ratio Formulation** | Refinement Added | Standardized to arithmetic form: $\bar{R}_{\text{net}} \times 252 / \sigma_{\text{down}}$. CAGR not mixed with downside deviation. |
| **7** | **Transaction Cost Reporting** | Refinement Added | Cumulative costs paid ($\sum \text{TC}_t$) reported separately from CAGR compounding drag ($\text{CAGR}_{\text{gross}} - \text{CAGR}_{\text{net}}$). |
| **8** | **Attribution Exactness** | Refinement Added | Exact cost drag $C_{\text{cost}, t} = R_{\text{net}, t} - R_{\text{gross}, t}$ used. Linear approximation prohibited. |
| **9** | **Hypothetical 6% Cash Yield** | Refinement Added | Compounded daily rate $(1.06)^{1/252}-1$ defined; labeled strictly as hypothetical sensitivity, not empirical cash rate. |
| **10** | **Dividend Limitation** | Refinement Added | Speculative "1.2%–1.6%" removed. Price Return limitation disclosed qualitatively. |

---

## 10. Implementation Requirements for Phase 10.3

Phase 10.3 implementation will execute under the following modular architecture:
1. **Source Module (`src/portfolio_backtest.py`):**
   - Pure functions: `calculate_drifted_weights()`, `calculate_actual_turnover()`, `simulate_portfolio()`, `generate_equal_weight_benchmark()`, `compute_metrics()`, and `compute_attribution()`.
   - Strictly consuming Phase 9 target-weight CSVs and `Close` price series.
2. **Automated Unit & Integration Tests (`tests/test_portfolio_backtest.py`):**
   - Validating single-asset pass-through, zero-turnover drift, 100% rebalancing, cash drag, exact cost deduction, simplex conservation, and train/holdout boundary continuity.
3. **Execution Notebook (`notebooks/10_portfolio_backtest.ipynb`):**
   - Authored directly as clean, reproducible Jupyter notebook displaying equity curves, drawdown charts, monthly return heatmaps, and performance tables.

---

## 11. Report Revision Change Log

- **Revision Date:** November 4, 2026
- **Changes Implemented:**
  1. Updated CAGR definition to use daily return intervals ($N=1,686, 1,264, 422$) rather than price observation counts.
  2. Formalized boundary-spanning return (`2024-12-31` $\to$ `2025-01-02`) assignment to the holdout period ($t=1,265$), proving the exact compounding identity.
  3. Corrected the Sortino ratio to the standard annualized arithmetic return formulation ($\bar{R}_{\text{net}} \times 252 / \sigma_{\text{down}}$).
  4. Defined exact daily compounding rate for the hypothetical 6% cash yield scenario ($(1.06)^{1/252} - 1$) and disclaimed historical empirical claims.
  5. Established separate reporting for cumulative cash fees paid ($\text{TC}_{\text{cum}}$) versus annualized CAGR drag ($\Delta_{\text{CAGR}}$).
  6. Enforced exact additive attribution identity ($R_{\text{net}} = \sum C_i + C_{\text{cost}}$) without linear approximations.
  7. Removed speculative "1.2%–1.6%" dividend estimate, retaining qualitative Price Return disclosure.
  8. Synchronized monthly Equal-Weight Benchmark execution timing to next-session close ($t+1$ Close) and established its initial boundary condition at 1/6 on `2019-10-31`.
  9. Elevated verdict from `APPROVED WITH CORRECTIONS` to **`APPROVED`**.

---

## 12. Final Sign-Off & Verdict

### **FINAL VERDICT: APPROVED**

**Justification:**  
All mathematical formulas, temporal conventions, drift dynamics, benchmark mechanics, metric definitions, and boundary conditions are rigorously specified, mutually consistent, and free of look-ahead bias. The methodology is 100% implementation-ready.

**Sign-Off:**  
Phase 10.2 is complete. Proceed to Phase 10.3 (Engine Implementation & Automated Testing) upon owner authorization.
