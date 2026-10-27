# Phase 8.2 — Sector Rotation Rules Specification (Consolidated Review Draft)

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Document Type:** Finalized Strategy & Rule Specification (Pre-Implementation Review Draft)  
**Primary ML Engine:** Gaussian Hidden Markov Model ($K=6$, Diagonal Covariance, Causal Forward-Filtered Stream `filtered_causal`)  
**Calibration / Evidence Window:** Training Pool **2019-10-31 to 2024-12-31** (1,265 trading sessions)  
**Protected Out-of-Sample Window:** Holdout Pool **2025-01-02 to 2026-09-18** (422 trading sessions — Quarantined / Unpeeked)  
**Status:** **Documentation & Specification Only — Implementation & Coding Paused Pending Final Approval**  
**Document Version:** 2.0.0 (Consolidated Authoritative Review Draft)

---

## 1. Purpose, Scope & Methodological Foundations

### 1.1 Purpose
This document establishes the single, consolidated, authoritative specification of sector-rotation rules for the Indian Equity Market. It translates unsupervised Gaussian Hidden Markov Model (HMM) regime discoveries into actionable, systematic portfolio allocations across the six major National Stock Exchange (NSE) sectoral indices:
1. **NIFTY AUTO** (Cyclical Consumer Discretionary)
2. **NIFTY BANK** (Cyclical Financials / Credit Intermediation)
3. **NIFTY FMCG** (Defensive Non-Cyclical Consumer Staples)
4. **NIFTY IT** (Global Defensive / Technology Exporters)
5. **NIFTY METAL** (High-Beta Commodities & Basic Materials)
6. **NIFTY PHARMA** (Defensive Healthcare / Non-Cyclical Pharmaceuticals)

### 1.2 Strict Scope Boundaries
* **Documentation Only:** This document defines the strategy rules, mathematical formulas, and operational controls. **No implementation code has been written under `src/`, no notebooks have been modified, and no backtests or portfolio simulations have been executed.**
* **Frozen Rules Principle:** All sector rankings, allocation weights, threshold parameters, and risk controls are derived **strictly and exclusively from the Training Pool (2019-10-31 to 2024-12-31)**.
* **Separation of Concerns:** This project is strictly separate from any intraday liquidity, market-making, or trading-risk engines. It operates as an end-of-day (EOD) regime-switching allocation strategy.

---

## 2. Primary Regime Model & Causal Probability Standards

### 2.1 Model Specification
The primary regime model selected from Phase 6 cross-validation and validated in Phase 7 is:
* **Model Class:** Gaussian Hidden Markov Model (`GaussianHMM`)
* **State Cardinality:** $K = 6$ regimes
* **Covariance Structure:** Diagonal covariance (`covariance_type="diag"`), regularized against singularity
* **Feature Input:** Unsupervised master feature matrix normalized via `RobustScaler` (calibrated strictly on training folds)

### 2.2 Causal Filtered Probabilities (`filtered_causal`)
* **Mandatory Operational Stream:** All live trading signals and simulated backtest allocations must rely **exclusively** on the causal forward-filtered regime probabilities:
  $$\alpha_t(k) = P(S_t = k \mid \mathcal{O}_{1}, \mathcal{O}_{2}, \dots, \mathcal{O}_{t})$$
  where $\mathcal{O}_{1:t}$ represents the market observation vector up to the market close of trading day $t$.
* **Prohibition of Look-Ahead / Smoothed Streams:** Retrospective smoothed probabilities (forward-backward algorithm) and full-sample Viterbi decoded paths (`retrospective_viterbi`) utilize future observations $\mathcal{O}_{t+1:T}$. **Viterbi and smoothed labels are strictly quarantined from signal generation and backtesting.** They are restricted solely to historical post-hoc diagnostic analysis.

### 2.3 Regime State Naming & Economic Identity
The six HMM regimes preserve their exact IDs and evidence-based economic designations established in Phase 6 and Phase 7:
* **Regime 0 (R0):** *Cyclical Reflation Rally* (Elevated VIX ~21, Bull Trend > 200 SMA, High Momentum)
* **Regime 1 (R1):** *High-Volatility Post-Crash Bounce* (High VIX ~34, Deep below 200 SMA, Sharp Mean-Reversion)
* **Regime 2 (R2):** *Low-Volatility Consolidation / Base* (Subdued VIX ~14, Near 200 SMA, Flat Momentum)
* **Regime 3 (R3):** *Acute Liquidation / Flight to Safety* (Extreme Panic VIX ~58, Crash below 200 SMA)
* **Regime 4 (R4):** *Steady Expansion / Low-Volatility Bull* (Calm VIX ~14, Sustained Bull Trend > 200 SMA)
* **Regime 5 (R5):** *Correction / Risk-Off Digestion* (Elevated VIX ~21, Hovering on 200 SMA, Negative Momentum)

---

## 3. Temporal Boundaries & Strict Holdout Protection Protocol

### 3.1 Partition Definitions
The dataset is partitioned chronologically into two non-overlapping windows:
1. **Training Pool:** `2019-10-31` to `2024-12-31` (1,265 active trading days)
   - Used for unsupervised model fitting, cross-validation, feature normalization calibration, sector performance characterization, and rule parameter specification.
2. **Protected Holdout Pool:** `2025-01-02` to `2026-09-18` (422 active trading days)
   - Quarantined as a blind forward-testing environment for Phase 10 backtesting.

### 3.2 Anti-Leakage Protocol
* **No Parameter Tuning on Holdout:** Sector allocation weights, probability thresholds, holding periods, volatility lookback windows, and cash buffers must **never** be tuned, adjusted, or selected using holdout performance.
* **Transparent Holdout Reporting:** Any operational failure, regime shift, or drawdown observed in the holdout period during Phase 10 will be reported as an empirical finding. The strategy will not be retroactively patched to improve holdout metrics while presenting that period as an out-of-sample test.

---

## 4. Correct Chronological Methodology for Forward 20-Day Returns

### 4.1 Role in Historical Analysis vs. Live Execution
Forward 20-day returns ($r_{t \to t+20}$) and their benchmark-relative excess returns ($r_{i, t \to t+20} - r_{\text{NIFTY}, t \to t+20}$) are retained in this project, but their methodological role is strictly defined:
* **Descriptive Regime Characterization (Historical Phase 7):** Forward 20-day returns evaluate whether being in a specific regime historically preceded sector outperformance over a typical multi-week holding horizon. They validate that discovered regimes capture persistent economic trends rather than transient 1-day noise.
* **Signal Generation (Phase 8 Onward):** **Forward returns are never used as a signal input.** At date $t$, future returns $r_{t \to t+20}$ do not exist. Trading decisions rely strictly on causal filtered probabilities $\alpha_t$ and historical model parameters.

### 4.2 Training Boundary Truncation & Statistical Independence
* **Boundary Enforcement:** To eliminate look-ahead leakage across the split boundary, forward 20-day return calculations for the training pool strictly exclude any date $t$ whose terminal horizon $t+20$ falls after `2024-12-31`. (Implemented and verified in `src/regime_characterisation.py:363-369` and unit test `test_training_fwd_boundary_enforcement`).
* **Serial Overlap Limitation:** Consecutive forward 20-day windows share 19 out of 20 daily price returns, creating autocorrelation. The effective number of independent observations is approximately $N / 20$. Therefore, forward return statistics serve as directional and ranking validation, not as uncorrelated statistical sample points.

---

## 5. Experimental Strategy Matrix & Benchmark Definitions

To avoid arbitrary selection of a single strategy configuration prior to backtesting, the project maintains a formal **$2 \times 2$ experimental matrix** combining two investment policies with two weighting methods.

### 5.1 The 4 Experimental Strategy Variants

```
                     STRATEGY VARIANT MATRIX (2 x 2)
    ┌───────────────────────────────┬───────────────────────────────┐
    │                               │                               │
    │          TEMPLATE A           │          TEMPLATE B           │
    │    (100% Fully Invested)      │    (Defensive Cash Floor)     │
    │                               │                               │
    ├───────────────────────────────┼───────────────────────────────┤
    │  VARIANT 1A (Baseline):       │  VARIANT 2A (Defensive EW):   │
    │  - Fully invested (100% eq)   │  - Cash buffer in R1/R3/R5    │
    │  - Equal-weighted Top-2       │  - Equal-weighted Top-2       │
    │    (50% / 50%)                │    within remaining equity    │
    ├───────────────────────────────┼───────────────────────────────┤
    │  VARIANT 1B (Risk-Weighted):  │  VARIANT 2B (Full Adaptive):  │
    │  - Fully invested (100% eq)   │  - Cash buffer in R1/R3/R5    │
    │  - Inverse-volatility Top-2   │  - Inverse-volatility Top-2   │
    │    weights                    │    within remaining equity    │
    └───────────────────────────────┴───────────────────────────────┘
```

1. **Variant 1A (Baseline — Template A + Equal-Weighted Top-2):**
   - 100% target equity exposure at all times.
   - Equal 50% / 50% allocation across the two selected sectors.
2. **Variant 1B (Experimental — Template A + Inverse-Volatility Top-2):**
   - 100% target equity exposure at all times.
   - Capital allocated inversely proportional to sector trailing volatility.
3. **Variant 2A (Experimental — Template B + Equal-Weighted Top-2):**
   - Permits an unallocated cash reserve during elevated risk regimes (R1: 30% cash, R3: 40% cash, R5: 20% cash).
   - Remaining equity capital distributed equally (50% / 50%) across the two selected sectors.
4. **Variant 2B (Experimental — Template B + Inverse-Volatility Top-2):**
   - Permits cash reserves in R1, R3, and R5.
   - Remaining equity capital distributed inversely proportional to trailing volatility.

### 5.2 Benchmark Definitions
Strategy performance in Phase 10 will be evaluated against two pre-specified benchmarks:
1. **Primary Benchmark: NIFTY 50 (Buy & Hold)**
   - Represents the broad market passive equity benchmark.
2. **Secondary Benchmark: Equal-Weighted 6-Sector Portfolio (Buy & Hold)**
   - Rebalanced daily or monthly with static 16.67% weight in each of the six sector indices. Isolates sector-selection alpha from broad sector-basket beta.

---

## 6. Regime-by-Regime Allocation Rules (Templates A & B)

All sector rankings and candidate allocations are verified against the training pool evidence (`results/regime_characterization/sector_performance/sector_performance_by_regime.csv` and `sector_leadership_summary.csv`).

### Master Candidate Allocation Table

| Regime ID | Economic Designation | Training Sample Size & Persistence | Sector Ranking (Training Evidence) | Template A Candidate (100% Invested) | Template B Candidate (Defensive Cash Floor) |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **R0** | Cyclical Reflation Rally | N = 244 days (4 ep)<br>Median: 22.5d (Reliable) | 1. **IT**<br>2. **METAL**<br>3. BANK<br>4. AUTO<br>5. PHARMA<br>6. FMCG | **50% IT**<br>**50% METAL** | **50% IT**<br>**50% METAL**<br>*(Fully invested)* |
| **R1** | High-Vol Post-Crash Bounce | N = 40 days (1 ep)<br>Median: 40.0d (Unstable) | 1. **AUTO**<br>2. **METAL**<br>3. IT<br>4. BANK<br>5. FMCG<br>6. PHARMA | **50% AUTO**<br>**50% METAL** | **35% AUTO**<br>**35% METAL**<br>**30% Cash** |
| **R2** | Low-Vol Consolidation / Base | N = 397 days (13 ep)<br>Median: 26.0d (Reliable) | 1. **IT**<br>2. **PHARMA**<br>3. BANK<br>4. FMCG<br>5. AUTO<br>6. METAL | **50% IT**<br>**50% PHARMA** | **50% IT**<br>**50% PHARMA**<br>*(Fully invested)* |
| **R3** | Acute Liquidation / Flight to Safety | N = 27 days (1 ep)<br>Median: 27.0d (Unstable) | 1. **PHARMA**<br>2. **FMCG**<br>3. IT<br>4. METAL<br>5. AUTO<br>6. BANK | **50% PHARMA**<br>**50% FMCG** | **40% PHARMA**<br>**20% FMCG**<br>**40% Cash** |
| **R4** | Steady Expansion / Low-Vol Bull | N = 353 days (13 ep)<br>Median: 19.0d (Reliable) | 1. **METAL**<br>2. **AUTO**<br>3. BANK<br>4. PHARMA<br>5. FMCG<br>6. IT | **50% METAL**<br>**50% AUTO** | **50% METAL**<br>**50% AUTO**<br>*(Fully invested)* |
| **R5** | Correction / Risk-Off Digestion | N = 204 days (6 ep)<br>Median: 18.0d (Reliable) | 1. **PHARMA**<br>2. **FMCG**<br>3. AUTO<br>4. METAL<br>5. IT<br>6. BANK | **50% PHARMA**<br>**50% FMCG** | **40% PHARMA**<br>**40% FMCG**<br>**20% Cash** |

*(Correction Note: The previous draft table contained an exploratory notation of 60% IT / 40% PHARMA for Template B in R2. In accordance with agreed decisions, R2 Template B is consolidated to "Same sector targets, fully invested" (50% IT / 50% PHARMA), maintaining exact parity with Template A).*

---

## 7. Mathematical Formulation of Allocation Weighting

### 7.1 Baseline Allocation: Equal-Weighted Top-2
For a regime with target equity exposure $E \in [0.0, 1.0]$ and cash allocation $C = 1.0 - E$:
$$w_{\text{sector}_1} = \frac{E}{2}, \quad w_{\text{sector}_2} = \frac{E}{2}, \quad w_{\text{cash}} = C$$
* In Template A: $E = 1.0 \implies w_1 = 0.50, w_2 = 0.50, w_{\text{cash}} = 0.00$.
* In Template B (e.g., R5): $C = 0.20 \implies E = 0.80 \implies w_1 = 0.40, w_2 = 0.40, w_{\text{cash}} = 0.20$.
* In Template B (R3): Explicitly specified as $w_{\text{PHARMA}} = 0.40, w_{\text{FMCG}} = 0.20, w_{\text{cash}} = 0.40$.

### 7.2 Experimental Allocation: Inverse-Volatility Top-2
Inverse-volatility weighting modifies the distribution of equity exposure between the two selected sectors based on their trailing realized volatility, penalizing high-risk sectors (e.g., METAL with ~35% vol) in favor of lower-volatility sectors (e.g., IT with ~22% vol).

#### Mathematical Formulation:
Let $\sigma_1$ and $\sigma_2$ be the estimated annualized realized volatilities for Sector 1 and Sector 2 calculated at day $t$.
1. **Raw Inverse Weights:**
   $$\text{raw}_1 = \frac{1}{\sigma_1}, \quad \text{raw}_2 = \frac{1}{\sigma_2}$$
2. **Normalized Equity Proportions:**
   $$p_1 = \frac{\text{raw}_1}{\text{raw}_1 + \text{raw}_2} = \frac{\sigma_2}{\sigma_1 + \sigma_2}, \quad p_2 = \frac{\text{raw}_2}{\text{raw}_1 + \text{raw}_2} = \frac{\sigma_1}{\sigma_1 + \sigma_2}$$
   where $p_1 + p_2 = 1.0$.
3. **Target Portfolio Weights:**
   $$w_{\text{sector}_1, t+1} = E \times p_1, \quad w_{\text{sector}_2, t+1} = E \times p_2, \quad w_{\text{cash}, t+1} = C$$

#### Parameters Requiring Training-Only Specification:
Before coding, the exact calculation of $\sigma_i$ must be frozen:
* **Lookback Window:** Trailing 20 trading days ($L=20$) or 60 trading days ($L=60$).
* **Return Frequency:** Daily log returns $r_{\tau} = \ln(P_{\tau}/P_{\tau-1})$.
* **Annualization Factor:** $\sqrt{252}$.
* **Volatility Floor Safeguard:** $\sigma_i = \max(\hat{\sigma}_i, 10^{-4})$ to prevent numerical instability or division by zero.
* **Status:** **Design parameter requiring pre-implementation confirmation using training data only.**

---

## 8. Special Handling & Safeguards for Rare Regimes (R1 & R3)

### 8.1 Regime 1 (High-Volatility Post-Crash Bounce)
* **Empirical Reality:** N = 40 trading days, occurring in a **single historical episode** (May–June 2020 post-COVID stimulus rebound). It never recurred in the holdout period.
* **Empirical Metrics:** AUTO (+70.3% daily excess, 80% 20D win rate) and METAL (+60.6% daily excess) achieved massive gains during this single episode.
* **Risk & Uncertainty:** Point estimates have wide standard errors due to $N=40$. An unconstrained 50/50 allocation in cyclical high-beta assets carries high model risk.
* **Agreed Candidates:**
  - *Template A:* 50% AUTO / 50% METAL (maintains symmetry across models).
  - *Template B:* 35% AUTO / 35% METAL / 30% Cash/Benchmark (prudent risk buffer).
* **Confidence Level:** **Low / Unstable.**

### 8.2 Regime 3 (Acute Liquidation / Flight to Safety)
* **Empirical Reality:** N = 27 trading days, occurring in a **single historical crisis episode** (March 2020 COVID shock).
* **Empirical Metrics:** PHARMA (+292.3% daily excess, 85.2% 20D win rate) and FMCG (+123.0% daily excess) decoupled strongly. BANK suffered catastrophic destruction (-124.8% excess, **0.0% forward 20D win rate**).
* **Market Turbulence:** Annualized volatility during R3 was 60% to 96% across sectors.
* **Agreed Candidates:**
  - *Template A:* 50% PHARMA / 50% FMCG.
  - *Template B:* 40% PHARMA / 20% FMCG / 40% Cash.
* **Crisis Bypass Rule:** Transition into R3 is permitted to bypass the normal 5-trading-day minimum holding period to prevent severe drawdown in crashing assets.
* **Execution Boundary:** Bypassing the holding lockup allows an immediate rebalance order, but execution must occur at the defined execution price/time ($t+1$ Open or $t+1$ Close). Same-bar execution at $C_t$ is strictly prohibited.
* **Confidence Level:** **Low / Unstable (Extreme Tail-Risk State).**

---

## 9. Three Agreed Operational Controls

### Control 1 — Regime-Confidence Acceptance Threshold ($P \ge 0.50$)
* **Threshold Value:** $P(S_t = k) \ge 0.50$ applied to causal filtered probabilities $\alpha_t$.
* **State Persistence Rule (Below Threshold):** If the maximum filtered probability satisfies $\max_k \alpha_t(k) < 0.50$, **no rebalancing is triggered**. The portfolio retains its existing sector allocation weights $w_t$.
* **Ambiguity Resolution:** Mathematically, at most one regime can have $\alpha_t(k) \ge 0.50$. If two regimes exactly tie at $\alpha_t(k_1) = \alpha_t(k_2) = 0.50$, the strategy retains the incumbent regime (hysteresis preference).
* **Initialization Convention (Day 0):** On the first day of strategy operation, before any regime history exists, if no regime achieves $\alpha_0(k) \ge 0.50$, the strategy initializes to the **Primary Benchmark (NIFTY 50)** or an equal-weighted sector basket until a confident regime signal emerges.

### Control 2 — Minimum Holding Period (5 Trading Days)
* **Rationale:** Prevents high-frequency whipsaws and transaction cost drag resulting from transient 1-day probability spikes.
* **Clock Mechanics:**
  - Execution occurs at date $t+1$. The holding clock begins on date $t+1$ (Day 0 of holding).
  - The portfolio must be held through Days 1, 2, 3, 4, and 5.
  - The earliest subsequent elective rebalance can be executed on date $t+6$.
* **Intervening Signals:** If a new regime achieves $P \ge 0.50$ on Days 1 through 4, the signal is ignored, and weights are held steady.
* **Crisis Exception:** An accepted transition into **Regime 3 (Acute Liquidation)** immediately overrides the holding lockup, allowing rebalance execution at the next executable bar.

### Control 3 — Transaction Cost Model (15 Basis Points One-Way)
* **Cost Factor:** 15 basis points ($c = 0.0015$) per unit of one-way portfolio turnover.
* **Turnover Calculation:**
  $$\text{Turnover}_t = \frac{1}{2} \sum_{i=1}^{M} \left| w_{i, t} - w_{i, t-1} \right|$$
  where $M = 7$ (6 sectoral indices + cash). Complete rotation from Sector A/B to Sector C/D yields $\text{Turnover}_t = 1.0$ (100% one-way turnover).
* **Cost Deduction:**
  $$\text{Transaction\_Cost}_t = 0.0015 \times \text{Turnover}_t \times \text{Portfolio\_Value}_t$$
  $$\text{Net\_Return}_t = \text{Gross\_Return}_t - (0.0015 \times \text{Turnover}_t)$$
* **Application Note:** 15 bps represents an institutional cost model covering Securities Transaction Tax (STT), NSE turnover charges, brokerage, GST, SEBI turnover fees, stamp duty, and bid-ask slippage. It will be deducted programmatically during Phase 10 backtesting.

---

## 10. Signal Generation, Temporal Integrity & Execution Timeline

To prevent look-ahead bias and guarantee execution realism, the strategy enforces a strict chronological execution timeline:

```
                            CHRONOLOGICAL EXECUTION TIMELINE
       Day t (Close)                                Day t+1 (Close)
─────────────┬─────────────────────────────────────────────┬──────────────────────>
             │                                             │
             ├─ 15:30 IST: Market Closes on Day t          ├─ 15:30 IST: Market Closes
             ├─ Data D_t finalized (Prices, VIX)           ├─ Target weights w* executed
             ├─ HMM Forward Filter computes alpha_t        ├─ Simulated at Close P_{i, t+1}
             ├─ Allocation Engine derives w*_{t+1}         ├─ Transaction costs deducted
             └─ Rebalance Order Queued                     └─ Post-execution return accrues
```

### Detailed Sequence of Events:
1. **$T_{\text{close}, t}$ (Day $t$, 15:30 IST):** Trading session $t$ closes on the NSE. Daily closing prices, volume, and India VIX are recorded in $\mathcal{O}_t$.
2. **$T_{\text{signal}, t}$ (Day $t$, Post-Close):**
   - The HMM forward filter processes $\mathcal{O}_t$ to produce causal filtered probabilities $\alpha_t$.
   - Operational controls (0.50 threshold and 5-day holding lockup) evaluate whether an accepted state change has occurred.
   - Target weights $w_{t+1}^*$ are generated.
3. **$T_{\text{exec}}$ (Execution Point):**
   - **Primary Convention (Standard Daily Close Model):** Target weights $w_{t+1}^*$ are executed at the **Market Close of Day $t+1$** ($P_{i, t+1}^{\text{close}}$). This provides a full trading day for trade preparation and execution.
   - **Alternative Convention (Next-Day Open Model):** If morning execution is selected, target weights execute at the **Market Open of Day $t+1$** ($P_{i, t+1}^{\text{open}}$).
4. **Performance Accrual:** Portfolio returns begin accruing immediately from $T_{\text{exec}}$.
5. **Strict Prohibition:** Executing trades at the same closing price $P_{i, t}^{\text{close}}$ that was used to generate the signal is strictly prohibited.

---

## 11. Status Summary: Agreed Decisions, Resolved Points & Implementation Checklist

### 11.1 Decisions Formally Agreed & Preserved
- [x] Primary ML Engine: Gaussian HMM ($K=6$, diagonal covariance).
- [x] Causal Probability Stream: `filtered_causal` only; zero retrospective Viterbi for execution.
- [x] Chronological Partitions: Training (2019-10-31 to 2024-12-31) and Protected Holdout (2025-01-02 to 2026-09-18).
- [x] Preservation of 2 Investment Policies: Template A (100% invested) and Template B (Defensive cash).
- [x] Preservation of 2 Weighting Methods: Equal-Weighted Top-2 and Inverse-Volatility Top-2.
- [x] Sector Selections for R0 through R5 preserved from training evidence.
- [x] Special status of R1 (rare bounce) and R3 (rare crisis) documented with low-sample warnings.
- [x] R3 crisis bypass of the 5-day holding period agreed.
- [x] Three operational controls agreed: 0.50 probability threshold, 5-day minimum holding period, 15 bps turnover cost.
- [x] Dual Benchmarks: NIFTY 50 and Equal-Weighted 6-Sector Portfolio.

### 11.2 Methodological Points Formally Clarified
- [x] Forward 20-day returns retained as descriptive regime validation; explicitly decoupled from real-time operational signals.
- [x] Training-period forward returns truncated at `2024-12-31` to eliminate holdout boundary leakage.
- [x] Serial correlation in overlapping forward windows acknowledged ($N_{\text{eff}} \approx N/20$).
- [x] R2 Template B consolidated to 50% IT / 50% PHARMA (identical to Template A), resolving earlier draft discrepancy.
- [x] Immediate R3 bypass clarified: permits immediate rebalance, but execution occurs at the designated subsequent execution time ($t+1$), not retroactively at $t$ close.

### 11.3 Specific Implementation Parameters Requiring Owner Sign-Off Before Coding
Before proceeding to write code in `src/regime_rotation_rules.py`, the following specific implementation choices require explicit confirmation:

| Decision Item | Candidate Options | Recommended Default | Rationale |
| :--- | :--- | :--- | :--- |
| **1. Primary Execution Price** | • Next-Day Close ($t+1$ Close)<br>• Next-Day Open ($t+1$ Open) | **Next-Day Close ($t+1$ Close)** | Standard for EOD index data; eliminates morning open auction noise. |
| **2. Volatility Lookback for Inverse-Vol** | • 20 trading days ($L=20$)<br>• 60 trading days ($L=60$) | **20 trading days ($L=20$)** | Matches the operational rotation horizon and responds faster to regime risk shifts. |
| **3. Portfolio Initialization (Day 0)** | • Hold Benchmark (NIFTY 50)<br>• Hold Cash (100%)<br>• Hold Equal-Weighted Basket | **Hold Benchmark (NIFTY 50)** | Avoids cash drag during warmup prior to the first confirmed regime signal. |

---

## 12. Explicit Non-Implementation Warranty

**Warranty Statement:**  
This document represents an authoritative specification and review draft only. **No code has been implemented under `src/`, no notebooks have been modified, no datasets have been changed, and no backtests have been executed.** All experimental backtesting, portfolio returns, transaction cost deductions, and holdout evaluations remain strictly paused until this specification receives explicit written approval from the project owner.
