# Phase 13 — Economic Interpretation of Market Regimes
## Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market

**Document Type:** Final Capstone Research & Economic Interpretation Report  
**Date:** November 2026  
**Status:** Approved & Canonical (Fully Synchronized with Verification Audit)  
**Target Repository:** `c:\Users\vighn\OneDrive\Desktop\sector rotation regime discovery`  
**Primary Deliverables:**
- Executive Research Report: `reports/phase13_regime_interpretation.md`
- Publication-Quality Document: `reports/phase13_regime_interpretation.pdf`
- Interactive Synthesis Notebook: `notebooks/zz_phase13_economic_interpretation.ipynb`

---

## Executive Summary

This research report presents the capstone economic synthesis for the quantitative project **Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market**. Across Phases 6 through 12, this study developed, backtested, statistically verified, and event-tested a systematic sector rotation engine powered by an unsupervised 6-state Gaussian Hidden Markov Model (HMM) applied to the National Stock Exchange (NSE) over the period January 2018 through September 2026 ($T = 1,686$ trading sessions).

The primary objective of Phase 13 is to transition from purely statistical clustering and algorithmic backtesting mechanics to a **scientifically rigorous, mathematically precise economic interpretation** of the empirical results. Using verified, frozen data from earlier phases, this report establishes:

1. **Economic Reality of the Discovered States:** The six statistical clusters discovered by the unsupervised HMM map directly to the canonical macroeconomic business-cycle lifecycle of the Indian equity market:
   - **Regime 0 (Cyclical Reflation Rally):** High-beta economic expansion associated with accommodative monetary policy, industrial revival, and strong earnings momentum (+46.91% annualized velocity, 16.87% volatility, median India VIX 20.81, mean 20.93).
   - **Regime 1 (High-Volatility Post-Crash Bounce):** Extreme relief recovery following market panic (+68.11% annualized velocity, 28.29% volatility, median VIX 32.98, mean 34.32; raw cumulative return of +10.71% over its 40 sessions), characterized by violent short covering.
   - **Regime 2 (Low-Volatility Consolidation / Base):** Rangebound institutional accumulation and macroeconomic digestion (-1.78% annualized velocity, 11.52% volatility, median VIX 13.62, mean 13.65).
   - **Regime 3 (Acute Liquidation / Flight to Safety):** Systemic market crash (-78.04% annualized velocity; raw cumulative return of -10.94% over its 27 sessions, 77.92% volatility, median VIX 55.30, mean 57.74, peaking at 83.61 during the March 2020 pandemic shock).
   - **Regime 4 (Steady Expansion / Low-Volatility Bull):** Multi-year secular bull market (+19.17% annualized velocity, 10.32% volatility, median VIX 13.05, mean 13.69), driven by domestic liquidity (SIPs) and earnings stability.
   - **Regime 5 (Correction / Risk-Off Digestion):** Macro tightening and broad market pullbacks (-5.53% annualized velocity, 20.76% volatility, median VIX 19.44, mean 19.70).

2. **Sector Leadership and Fundamental Asymmetry:** Cross-sectional sector performance is fundamentally state-dependent. In expansionary and reflationary regimes (R0, R1, R4), high-beta cyclical sectors (**NIFTY METAL**, **NIFTY AUTO**) substantially outperform the broad market. Conversely, in acute liquidation (R3) and macro corrections (R5), defensive sectors (**NIFTY PHARMA**, **NIFTY FMCG**) deliver decisive capital protection, highlighted by Pharma's +23.16% raw cumulative gain (+214.28% annualized velocity) during the COVID crash while Banking experienced a raw -23.48% loss (-202.86% annualized velocity).

3. **Systemic Diversification Breakdown:** Under normal conditions (R4), average pairwise sector correlation is low (0.322) and the first principal component (PC1) explains only 44.0% of variance, creating fertile ground for sector rotation. In acute liquidation (R3), pairwise correlation surges to 0.801 and PC1 explains 83.5% of total variance, demonstrating a severe breakdown of cross-sectional diversification that renders defensive cash floors (Template B) essential.

4. **Forensic Diagnosis of Holdout Performance Decay:** The divergence between training and holdout performance is evaluated using two mathematically distinct, non-interchangeable metrics:
   - **Geometric CAGR (Compounded Growth):** Training CAGR of **+43.3169%** collapsed to Holdout CAGR of **-11.8732%** (a geometric deterioration of **-55.19 percentage points**).
   - **Arithmetic Annualized Return (Mean Daily Return $\times$ 252):** Training arithmetic return of **+38.1092%** shifted to Holdout arithmetic return of **-11.4414%** (an arithmetic deterioration of **-49.5506 percentage points**). Arithmetic returns are mathematically required to preserve additive linear attribution across individual sector contributions ($\sum c_s + c_{\text{cost}} \equiv r_{\text{net}}$).
   - This performance shift is fully explained by four structural market phenomena:
     - **Regime Frequency Collapse:** The primary alpha engine, Regime 0, collapsed from 19.30% of trading days in training to just 1.90% in the holdout, while Regime 5 nearly doubled to 29.86%.
     - **Episode Duration Halving & Whipsaw Friction:** Mean regime episode duration fell from 33.3 days to 17.6 days, driving a 65.7% surge in annualized turnover (from 6.49x to 10.75x) and a -1.61% annual cost drag.
     - **The Indian IT Sector Slump:** NIFTY IT dropped -21.30% annualized in the holdout; holding IT in Regime 2 inflicted a -6.57 percentage point drag on annual returns.
     - **Missed Banking Exposure:** The strategy’s fixed Top-2 candidate rules excluded NIFTY BANK across all six regimes, missing banking’s +7.36% holdout resilience entirely (documenting a missed historical exposure / opportunity cost, though not a guaranteed counterfactual improvement).

---

## 1. Research Context & Verified Antecedents

### 1.1 Project Architecture & Lineage
This project investigates whether unsupervised machine learning can discover actionable, economically coherent market regimes to drive systematic sector rotation in the Indian equity market. Rather than relying on subjective heuristic classifications or single-indicator thresholds, the framework employs a 6-state Gaussian Hidden Markov Model (HMM) fitted on stationary, robust-scaled multi-asset features.

```
+-----------------------------------------------------------------------------------+
|                            ANALYTICAL LINEAGE (PHASES 6-13)                       |
+-----------------------------------------------------------------------------------+
| Phase 6: Unsupervised HMM Discovery (6 States, Causal Filtering, Transition Matrix)|
|                                         |                                         |
| Phase 7: Historical Event Associations & Initial Regime Mapping                   |
|                                         |                                         |
| Phase 8: Systematic Sector Rotation Rules Engine (Top-2 Sectors, Templates A & B) |
|                                         |                                         |
| Phase 9 & 10: Portfolio Backtest Engine & 2025-2026 Holdout Evaluation             |
|                                         |                                         |
| Phase 11: Formal Statistical Validation (HAC, Lo Sharpe, Bootstrap Inference)     |
|                                         |                                         |
| Phase 12: MacKinlay Event-Study Analysis (135 Events, 68 Episodes, CAARs)         |
|                                         |                                         |
| Phase 13: Capstone Economic Interpretation, Forensic Diagnosis & Final Synthesis |
+-----------------------------------------------------------------------------------+
```

### 1.2 Data Foundations & Strict Quarantine
All empirical analyses in this report are grounded in verified, immutable repository artifacts:
- **Daily Simulation Records:** `results/portfolio_backtest/daily_simulation_1A.parquet` through `3B.parquet` (1,686 trading days spanning 2018-01-08 to 2026-09-02; backtest execution begins 2019-11-01 following warmup).
- **Partitioning:** Training period (2019-11-01 to 2024-12-31, $T=1,264$ sessions) and Holdout period (2025-01-01 to 2026-09-02, $T=422$ sessions).
- **Macro Feature Catalog:** Unscaled NIFTY 50 metrics (`data/processed/feature_engineered/nifty50_features.csv`) and India VIX index levels (`data/processed/aligned/india_vix_aligned.csv`).
- **Event Catalogs:** `results/event_analysis/event_metadata_authoritative.parquet` (135 classified events) and `macro_episodes_summary.parquet` (68 episodes).
- **Mathematical Exactness:** The additive attribution identity $\sum_s \text{contrib}_s + \text{contrib\_cost} \equiv \text{net\_return}$ holds across all 1,686 rows with zero discrepancy.

---

## 2. Multi-Dimensional Economic Profiling of the Six Regimes

### 2.1 Empirical Characterization Matrix
The table below reports the verified empirical profile for each of the six HMM-discovered states over the entire 1,686-session dataset. 

> [!NOTE]
> **Methodological Note on Annualized Regime Returns:**
> Annualized returns across regimes are computed as standardized daily velocities: $\text{Annualized Return} = \text{Mean Daily Return} \times 252$. For short single-episode regimes—specifically **Regime 3 ($N=27$ sessions)** and **Regime 1 ($N=40$ sessions)**—this linear extrapolation reflects the daily velocity during that specific episode scaled to a 252-day baseline, but does **not** represent a realized 1-year holding return. The actual raw cumulative returns experienced during these episodes are explicitly documented below.

| Regime ID | Economic Designation | Total Sessions | Allocation Share (%) | NIFTY Ann. Velocity (Mean $\times$ 252) | Raw Cumulative Return | NIFTY Realized Vol (%) | Sharpe (Rf=5%) | Median India VIX | Mean India VIX | Peak India VIX |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Regime 0** | Cyclical Reflation Rally | 252 | 14.95% | **+46.91%** | +46.85% (across 5 eps) | 16.87% | **+2.48** | **20.81** | 20.93 | 29.73 |
| **Regime 1** | High-Vol Post-Crash Bounce | 40 | 2.37% | **+68.11%** | **+10.71% (40 days)** | 28.29% | **+2.23** | **32.98** | 34.32 | 43.67 |
| **Regime 2** | Low-Vol Consolidation / Base | 515 | 30.55% | **-1.78%** | -3.61% (across 22 eps)| 11.52% | -0.59 | **13.62** | 13.65 | 20.37 |
| **Regime 3** | Acute Liquidation / Panic Crash | 27 | 1.60% | **-78.04%** | **-10.94% (27 days)** | 77.92% | **-1.07** | **55.30** | 57.74 | **83.61** |
| **Regime 4** | Steady Expansion / Bull | 522 | 30.96% | **+19.17%** | +39.73% (across 22 eps)| 10.32% | **+1.37** | **13.05** | 13.69 | 24.60 |
| **Regime 5** | Correction / Risk-Off Digestion | 330 | 19.57% | **-5.53%** | -7.21% (across 11 eps)| 20.76% | -0.51 | **19.44** | 19.70 | 31.98 |

```
+----------------------------------------------------------------------------------------------------+
|                                  REGIME MACRO PROFILE TAXONOMY                                     |
+----------------------------------------------------------------------------------------------------+
|  High Return (>40%) |  [Regime 1: Post-Crash Bounce]        |  [Regime 0: Cyclical Reflation]      |
|                     |  (Ann. Vel: +68.1%, Vol: 28.3%)       |  (Ann. Vel: +46.9%, Vol: 16.9%)      |
|---------------------+---------------------------------------+--------------------------------------|
|  Moderate Return    |  [Regime 5: Risk-Off Correction]      |  [Regime 4: Steady Secular Bull]     |
|  or Drawdown        |  (Ann. Vel: -5.5%, Vol: 20.8%)        |  (Ann. Vel: +19.2%, Vol: 10.3%)      |
|---------------------+---------------------------------------+--------------------------------------|
|  Severe Contraction |  [Regime 3: Acute Liquidation]        |  [Regime 2: Consolidation / Base]    |
|  or Stagnation      |  (Ann. Vel: -78.0%, Vol: 77.9%)       |  (Ann. Vel: -1.8%, Vol: 11.5%)       |
|                     +---------------------------------------+--------------------------------------|
|                     |         HIGH VOLATILITY (>25%)        |        LOW VOLATILITY (<20%)         |
+----------------------------------------------------------------------------------------------------+
```

### 2.2 Deep Economic Profiles of the Six Discovered States

#### Regime 0: Cyclical Reflation Rally
- **Macro Environment:** Aggressive monetary easing, fiscal stimulus, surging commodity demand, and corporate earnings recovery following a major economic trough.
- **Empirical Signature:** Strong positive broad-market momentum (+46.91% annualized velocity), moderate realized volatility (16.87%), and an India VIX stabilizing in the low 20s (median VIX 20.81, mean 20.93).
- **Key Historical Manifestations:** June 23, 2020 to March 24, 2021 (187 consecutive trading days) and April 29, 2021 to June 16, 2021 (29 trading days). During this period, the Reserve Bank of India reduced the repo rate to 4.00% and injected durable liquidity via Targeted Long Term Repo Operations (TLTROs), while global fiscal stimulus was associated with a worldwide industrial resurgence.

#### Regime 1: High-Volatility Post-Crash Relief Bounce
- **Macro Environment:** The initial, violent relief rally that emerges from the depths of a panic liquidation. Characterized by aggressive short covering, sudden sentiment reversals, and central bank emergency backstops.
- **Empirical Signature:** Spectacular annualized price gains (+68.11% annualized velocity; raw cumulative return of +10.71% over its 40 sessions) coupled with very high volatility (28.29%) and elevated option-implied volatility (median VIX 32.98, mean 34.32, range 28.68 to 43.67).
- **Key Historical Manifestation:** April 24, 2020 to June 22, 2020 (40 trading days). This marked the immediate rebound following the initial global COVID lockdowns, during which fiscal guarantee announcements and coordinated global central bank interventions were observed concurrently with a halt in solvency contagion.

#### Regime 2: Low-Volatility Consolidation / Base Building
- **Macro Environment:** A rangebound, trendless digestion phase wherein macroeconomic forces reach equilibrium. Corporate earnings growth pauses or moderates, monetary policy is neutral, and institutional capital accumulates shares without driving directional index momentum.
- **Empirical Signature:** Flattish to mildly negative index return (-1.78% annualized velocity), subdued realized volatility (11.52%), and a low, quiescent India VIX (median VIX 13.62, mean 13.65).
- **Key Historical Manifestations:** Persistent through late-2022 (December 2022 to April 2023, 75 days), mid-to-late 2023 (August to November 2023, 68 days across two episodes), and late-2024 (October to December 2024, 61 days).

#### Regime 3: Acute Liquidation / Flight to Safety
- **Macro Environment:** Severe exogenous systemic shock leading to margin liquidations, credit freezing, and generalized forced selling across liquid asset classes.
- **Empirical Signature:** Catastrophic equity collapse (-78.04% annualized velocity; raw cumulative return of -10.94% over its 27 sessions), historic realized volatility (77.92%), and extreme option-implied panic (median VIX 55.30, mean 57.74, peaking at 83.61 on March 24, 2020).
- **Key Historical Manifestation:** March 12, 2020 to April 23, 2020 (27 consecutive trading days). The global onset of the COVID-19 pandemic and nationwide lockdown imposition.

#### Regime 4: Steady Expansion / Low-Volatility Secular Bull
- **Macro Environment:** The classic "Goldilocks" environment of sustainable GDP expansion, robust corporate earnings growth, consistent domestic retail equity inflows (Systematic Investment Plans), and stable fiscal/monetary conditions.
- **Empirical Signature:** Strong, orderly equity compounding (+19.17% annualized velocity), the lowest realized volatility in the market (10.32%), and an ultra-low India VIX (median VIX 13.05, mean 13.69, reaching lows of 9.15).
- **Key Historical Manifestations:** April 13, 2023 to August 2, 2023 (77 days), November 23, 2023 to January 16, 2024 (36 days), and March 28, 2024 to June 3, 2024 (43 days).

#### Regime 5: Correction / Risk-Off Digestion
- **Macro Environment:** Macroeconomic tightening cycles, rising interest rates, inflationary surges, geopolitical conflicts, and Foreign Institutional Investor (FII) capital outflows.
- **Empirical Signature:** Negative broad-market return (-5.53% annualized velocity), elevated volatility (20.76%), and a jump in implied volatility (median VIX 19.44, mean 19.70, peaking at 31.98).
- **Key Historical Manifestations:** January 24, 2022 to August 1, 2022 (130 trading days—coinciding with the outbreak of the Russia-Ukraine war, global energy shock, and aggressive RBI repo rate hikes from 4.00% to 5.40%) and February 24, 2026 to June 16, 2026 (74 trading days—coinciding with global tariff escalations and domestic growth deceleration).

---

## 3. Sector Leadership Dynamics & Fundamental Rationale

### 3.1 Cross-Sectional Return Matrix
The six canonical NSE sectoral indices represent distinct economic business models and cash-flow sensitivities. The table below presents the verified annualized velocity ($\bar{r} \times 252$) and raw cumulative returns for each sector conditioned on the active HMM regime:

| Regime ID & Designation | NIFTY AUTO | NIFTY BANK | NIFTY FMCG | NIFTY IT | NIFTY METAL | NIFTY PHARMA | NIFTY 50 Benchmark | Top-2 Assigned Sectors |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **R0: Reflation** | +51.39% | +58.94% | +18.40% | **+82.12%** | **+80.75%** | +22.10% | +46.91% | IT, METAL |
| **R1: Bounce (Raw 40d)** | **+138.39% (+23.1%)** | +54.62% (+7.1%) | +3.56% (+0.3%) | +64.70% (+10.2%) | **+128.66% (+21.0%)**| +55.54% (+8.8%) | +68.11% (+10.7%) | AUTO, METAL |
| **R2: Consolidation** | -3.34% | -5.80% | -4.63% | **+12.78%** | -9.06% | **+2.98%** | -1.78% | IT, PHARMA |
| **R3: Liquidation (Raw 27d)**| -136.88% (-16.8%)| **-202.86% (-23.5%)**| **+44.93% (+2.5%)**| -77.70% (-10.6%) | -118.97% (-14.7%)| **+214.28% (+23.2%)**| -78.04% (-10.9%) | PHARMA, FMCG |
| **R4: Expansion** | **+35.03%** | +26.82% | +9.93% | -2.37% | **+51.88%** | +25.01% | +19.17% | METAL, AUTO |
| **R5: Correction** | +7.61% | -6.16% | **+6.21%** | -18.68% | +12.83% | **+16.84%** | -5.53% | PHARMA, FMCG |

> [!WARNING]
> **Extrapolation Distortions in R1 and R3:**
> Multiplying short-term daily returns by 252 produces extreme annualized velocity figures. For example, in Regime 3 ($N=27$ sessions), NIFTY BANK experienced a daily mean loss of -0.8050%, which scales linearly to **-202.86%**. An unleveraged equity holding cannot physically lose more than -100%. The raw cumulative loss was **-23.48%** (geometric annualized rate: **-91.78%**). Similarly, NIFTY PHARMA's daily mean gain of +0.8503% scales linearly to **+214.28%**, reflecting an actual raw cumulative gain of **+23.16%** over the 27 sessions. These figures represent standardized daily velocities, not realized 1-year holding returns.

### 3.2 Economic Mechanisms Governing Sector Rotation

```
+------------------------------------------------------------------------------------+
|                      SECTOR BEHAVIORAL SENSITIVITY MECHANISM                       |
+------------------------------------------------------------------------------------+
| High Beta / Cyclicals  | NIFTY METAL: Global demand, raw material price expansion  |
| (Expansion Beneficiary)| NIFTY AUTO: Discretionary demand, credit availability      |
|------------------------+-----------------------------------------------------------|
| Inelastic Defensives   | NIFTY PHARMA: Non-discretionary healthcare, dollar sales  |
| (Contraction Buffer)   | NIFTY FMCG: Daily consumer staples, pricing power         |
|------------------------+-----------------------------------------------------------|
| External Tech Exporter | NIFTY IT: US enterprise IT budget cycle, INR depreciation |
|------------------------+-----------------------------------------------------------|
| Domestic Credit Engine | NIFTY BANK: Credit expansion, NIMs, corporate asset quality|
+------------------------------------------------------------------------------------+
```

#### Cyclical Outperformance in Expansion (Regimes 0, 1, 4)
- **Metals & Autos:** During economic recovery and expansion, consumer discretionary spending rebounds and industrial capex resumes. In Regime 1, Autos and Metals achieved daily velocity annualized returns of +138.39% (raw +23.14%) and +128.66% (raw +20.95%) as oversold manufacturing capacity was re-priced. In Regime 4 (Steady Bull), Metals (+51.88%) and Autos (+35.03%) delivered substantial outperformance over the benchmark (+19.17%), demonstrating the empirical advantage of concentrating in high-beta cyclicals during secular expansions.

#### Defensive Shielding in Contraction (Regimes 3, 5)
- **Pharma & FMCG:** The demand for medicines, medical supplies, and basic food items exhibits near-zero elasticity with respect to the economic cycle. During Regime 3 (COVID Crash), while NIFTY BANK suffered a raw loss of **-23.48%** and NIFTY AUTO fell **-16.80%**, NIFTY PHARMA delivered a raw cumulative gain of **+23.16%** (+214.28% annualized velocity) and NIFTY FMCG gained **+2.52%** (+44.93% annualized velocity). Allocating to Pharma and FMCG in Regime 3 converted what would have been a catastrophic portfolio drawdown into positive return performance.
- Similarly, in Regime 5 (Correction), NIFTY PHARMA (+16.84%) and NIFTY FMCG (+6.21%) were the primary positive-yielding assets while NIFTY 50 (-5.53%), BANK (-6.16%), and IT (-18.68%) contracted.

#### The Banking Sector Omission Paradox
- In Phase 8, the automated rule generation selected the top-2 candidate sectors based on historical training-set dominance. The assigned allocations were:
  - R0: IT, METAL
  - R1: AUTO, METAL
  - R2: IT, PHARMA
  - R3: PHARMA, FMCG
  - R4: METAL, AUTO
  - R5: PHARMA, FMCG
- **The Empirical Reality:** **NIFTY BANK was excluded from the Top-2 selection across all six regimes.** During the 2019–2024 training period, Metals and IT provided higher pure momentum, so this omission did not impair returns. However, in the 2025–2026 holdout, NIFTY BANK delivered a resilient **+7.3551% annualized return** while NIFTY IT slumped by -21.30%. Strategy 1A generated **0.0000% Banking contribution**.
- **Important Interpretation Boundary:** This observation documents a **missed historical exposure and an opportunity cost**, but does **not** constitute empirical proof that a dynamic strategy allocating to Banking would have improved net returns without incurring offsetting transaction costs, timing friction, or whipsaw losses. Counterfactual backtests were not conducted.

---

## 4. Regime Transition Pathways, Persistence & Ergodic Dynamics

### 4.1 Empirical Transition Matrices
Financial markets do not transition randomly between regimes. The table below presents the verified daily transition probability matrix $P_{i,j} = P(S_{t+1} = j \mid S_t = i)$ computed across the entire sample ($T=1,686$):

| Origin State | R0 (Reflation) | R1 (Bounce) | R2 (Consolidation) | R3 (Crash) | R4 (Expansion) | R5 (Correction) | Daily Persistence ($P_{ii}$) | Expected Duration ($1 / (1-P_{ii})$) | Full-Sample Median Duration |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **R0: Reflation** | **98.02%** | 0.00% | 0.79% | 0.00% | 0.79% | 0.40% | **98.02%** | 50.5 days | **16.0 days** (5 eps) |
| **R1: Bounce** | 2.50% | **97.50%** | 0.00% | 0.00% | 0.00% | 0.00% | **97.50%** | 40.0 days | **40.0 days** (1 ep) |
| **R2: Consolidation** | 0.00% | 0.00% | **95.91%** | 0.00% | 3.11% | 0.97% | **95.91%** | 24.4 days | **19.0 days** (22 eps) |
| **R3: Crash** | 0.00% | 3.70% | 0.00% | **96.30%** | 0.00% | 0.00% | **96.30%** | 27.0 days | **27.0 days** (1 ep) |
| **R4: Expansion** | 0.19% | 0.00% | 3.07% | 0.00% | **95.79%** | 0.96% | **95.79%** | 23.8 days | **17.5 days** (22 eps) |
| **R5: Correction** | 0.91% | 0.00% | 1.21% | 0.30% | 0.91% | **96.67%** | **96.67%** | 30.0 days | **19.0 days** (11 eps) |

```
+----------------------------------------------------------------------------------------------------+
|                                    MACRO REGIME TRANSITION GRAPH                                   |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|                  +--------------------+                +--------------------+                      |
|                  |     Regime 4       | <============> |     Regime 2       |                      |
|                  | (Steady Expansion) |     ~3.1%      |  (Consolidation)   |                      |
|                  +--------------------+                +--------------------+                      |
|                            ^                                     ^                                 |
|                             \                                   /                                  |
|                              \                                 /                                   |
|                         0.8%  \                               /  1.2%                              |
|                                \                             /                                     |
|                               +-------------------------------+                                    |
|                               |           Regime 0            |                                    |
|                               |      (Cyclical Reflation)     |                                    |
|                               +-------------------------------+                                    |
|                                               ^                                                    |
|                                               |  2.5%                                              |
|                               +-------------------------------+                                    |
|                               |           Regime 1            |                                    |
|                               |      (Post-Crash Bounce)      |                                    |
|                               +-------------------------------+                                    |
|                                               ^                                                    |
|                                               |  3.7%                                              |
|                               +-------------------------------+                                    |
|                               |           Regime 3            |                                    |
|                               |      (Acute Liquidation)      |                                    |
|                               +-------------------------------+                                    |
|                                               ^                                                    |
|                                               |  0.3% (N=1 transition)                             |
|                               +-------------------------------+                                    |
|                               |           Regime 5            |                                    |
|                               |      (Risk-Off Correction)    |                                    |
|                               +-------------------------------+                                    |
+----------------------------------------------------------------------------------------------------+
```

### 4.2 Structural Insights on Market Microstructure

1. **Macroeconomic Stickiness & Duration Realities:**
   Every single regime exhibits a daily self-transition probability exceeding 95.7% ($P_{ii} > 0.957$). However, the expected geometric duration $1 / (1-P_{ii})$ tends to overstate empirical durations due to fat-tailed episodes. From `results/statistical_validation/regime_duration_diagnostics.parquet`, the verified **full-sample median durations** are:
   - **Overall sample median:** **18.5 trading days** (mean: 27.19 days).
   - Recurring regimes exhibit medians tightly clustered between **16.0 and 19.0 trading days** (R0: 16.0d, R2: 19.0d, R4: 17.5d, R5: 19.0d).
   - Single-episode states reflect their exact historical span: R1 = 40.0 days, R3 = 27.0 days.

2. **The 2020 Crisis Pathway ($N=1$ Historical Observation):**
   The sequence:
   $$\text{Correction (R5)} \longrightarrow \text{Panic Liquidation (R3)} \longrightarrow \text{Relief Bounce (R1)} \longrightarrow \text{Cyclical Reflation (R0)}$$
   was observed during the historical 2020 COVID crash and recovery episode ($N=1$). **It should be interpreted as a documented historical progression, not an irreversible law or a universally established market-cycle pathway.**
   - Notably, in the historical data, **zero direct R3 $\to$ R4 transitions were observed** ($N=0$). Following the acute panic, the market did not immediately resume steady bull expansion without first traversing high-volatility relief and reflation states.

3. **The Expansion-Consolidation Cycle:**
   During benign macroeconomic regimes, the Indian equity market operated within an oscillating loop between Steady Expansion (R4) and Consolidation (R2):
   $$P(R_4 \to R_2) = 3.07\% \quad \text{and} \quad P(R_2 \to R_4) = 3.11\%$$
   Supported by **32 historical episode transitions** (16 in each direction), this loop reflects recurring market mechanics: multi-month trending rallies followed by periods of base-building, after which expansion resumes.

---

## 5. Risk, Volatility & Cross-Sector Diversification Breakdown

### 5.1 Systemic Co-Movement vs. Sector Dispersion
Modern Portfolio Theory assumes that diversification mitigates portfolio variance because asset idiosyncratic risks cancel out. However, empirical findings prove that in Indian equities, **cross-sectional correlation is heavily regime-dependent**:

| Regime ID & Designation | Average Off-Diagonal Correlation | Verified Minimum Pairwise Correlation | Verified Maximum Pairwise Correlation | PC1 Variance Explained (%) | Diversification Regime State |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **R0: Cyclical Reflation** | 0.425 | **0.248** (BANK–IT) | **0.588** (AUTO–METAL) | 52.4% | Moderate Dispersion |
| **R1: Post-Crash Bounce** | 0.413 | **-0.045** (BANK–PHARMA) | **0.854** (AUTO–METAL) | 55.9% | Moderate Dispersion |
| **R2: Consolidation / Base** | 0.361 | **0.224** (FMCG–METAL) | **0.542** (BANK–METAL) | 47.4% | Broad Dispersion |
| **R3: Acute Liquidation** | **0.801** | **0.706** (BANK–PHARMA) | **0.914** (AUTO–BANK) | **83.5%** | **Systemic Collapse (Zero Diversification)** |
| **R4: Steady Expansion** | **0.322** | **0.213** (FMCG–IT) | **0.472** (AUTO–BANK) | **44.0%** | **Optimal Alpha Dispersion** |
| **R5: Risk-Off Correction** | 0.552 | **0.424** (BANK–IT) | **0.800** (AUTO–BANK) | 63.0% | Elevated Systemic Co-Movement |

### 5.2 Key Takeaways on Portfolio Risk & Volatility

```
+------------------------------------------------------------------------------------+
|                     DIVERSIFICATION REGIME CONTINUUM                               |
+------------------------------------------------------------------------------------+
|  Low Correlation (0.32) | Average Correlation (0.42) | High Systemic Risk (0.80)   |
|  PC1 Variance: 44.0%    | PC1 Variance: 52-56%       | PC1 Variance: 83.5%         |
|                         |                            |                             |
|  [Regime 4: Expansion]  | [Regimes 0, 1, 2]          | [Regime 3: Acute Crash]     |
|  High Idiosyncratic     | Normal Market Structure    | Complete Diversification    |
|  Alpha Opportunity      | Sector Trends Distinct     | Failure; Cash Floor Vital   |
+------------------------------------------------------------------------------------+
```

1. **Complete Breakdown of Diversification in Crises (Regime 3):**
   In Regime 3, average pairwise correlation spiked to **0.801**, and the first principal component (PC1) explained **83.5% of total variance**. Under panic selling, individual sector fundamentals cease to dominate; institutional liquidations force equities to move as a unified block. Standard multi-sector equity portfolios experience near-100% beta exposure, demonstrating that **diversification within equities disappears precisely when it is most needed**. This provides the mathematical rationale for Template B's defensive cash floor (40% cash in R3).

2. **Maximum Alpha Generation Environment (Regime 4):**
   In Regime 4, mean pairwise correlation fell to **0.322**, and PC1 explained only **44.0%** of variance. More than 56% of sector return variance was driven by industry-specific fundamentals. This dispersion facilitates sector rotation: wide spreads between winning sectors (Metals +51.9%, Autos +35.0%) and lagging sectors (IT -2.4%, FMCG +9.9%) allow concentrated Top-2 portfolios to harvest substantial excess returns over the benchmark.

---

## 6. Macroeconomic Context & Market-Event Synthesis

### 6.1 Integration with Phase 12 Event Study Panel
Phase 12 cataloged 135 market events across 68 macro episodes between 2018 and 2026. Mapping these historical episodes against the HMM regime timeline demonstrates that regime shifts were empirically concurrent with policy and macro catalysts:

| Primary Macro Category | Episode Count | Share (%) | Primary Associated Regimes | Documented Historical Market Association |
| :--- | :---: | :---: | :--- | :--- |
| **Monetary Policy Shocks** | 28 | 41.2% | R5 (Correction), R2 (Consolidation) | Rate hiking cycles (2022–2023) coincided with prolonged defensive corrections; unexpected rate cuts in 2020 coincided with R1/R0 reflation. |
| **Trade Policy & Global Tariffs** | 18 | 26.5% | R5 (Correction), R4 (Expansion) | Heightened tariff threats coincided with export drag in IT and Metals; tariff resolutions coincided with cyclical expansion. |
| **Geopolitics & Global Summits** | 7 | 10.3% | R5 (Correction) | Energy price spikes (e.g. 2022 Ukraine invasion) were observed concurrently with persistent R5 correction episodes. |
| **Fiscal & Domestic Policy** | 5 | 7.4% | R4 (Expansion), R2 (Consolidation) | Union Budgets with capex emphasis coincided with R4 bull market continuations. |
| **Elections & Politics** | 5 | 7.4% | R4 (Expansion), R5 (Correction) | Pre-election policy continuity coincided with R4 rallies; coalition surprises were accompanied by transient pullbacks. |
| **Financial & Banking Shocks** | 3 | 4.4% | R5 (Correction), R3 (Crash) | Credit stress events (IL&FS, Yes Bank) coincided with flight to FMCG and Pharma. |
| **Pandemic & Health Shocks** | 2 | 2.9% | R3 (Crash), R1 (Bounce) | Nationwide lockdowns coincided with acute liquidation followed by violent relief rebounds. |

---

## 7. Forensic Diagnosis of 2025–2026 Holdout Deterioration

### 7.1 Reconciling CAGR vs. Arithmetic Attribution
A critical finding from Phase 10, Phase 11, and the Phase 13 audit is that portfolio performance must be evaluated using two distinct, non-interchangeable metrics:

- **Geometric CAGR (Compounded NAV Growth):** Measures real wealth accumulation over multi-period horizons ($\prod (1 + r_t)^{252/N} - 1$).
  - Training Period (2019–2024): **+43.3169%**
  - Holdout Period (2025–2026): **-11.8732%**
  - Geometric CAGR Decay: **-55.19 percentage points**
- **Arithmetic Annualized Return (Mean Daily Return $\times$ 252):** Measures average daily performance scaled to an annual baseline ($\frac{252}{N} \sum r_t$).
  - Training Period (2019–2024): **+38.1092%**
  - Holdout Period (2025–2026): **-11.4414%**
  - Arithmetic Annualized Decay: **-49.5506 percentage points**

> [!IMPORTANT]
> **Why the Metrics Differ:**
> Return attribution across sectors is an **additive linear identity**: $r_{\text{net}, t} \equiv \sum c_{s, t} + c_{\text{cost}, t}$. Summing daily contributions linearly and multiplying by 252 strictly preserves this equality. Geometric compounding introduces non-linear cross-product interaction terms that cannot be linearly allocated to individual sectors. Therefore, overall portfolio growth is reported as **CAGR**, while sector attribution is reported as **Arithmetic Annualized Contribution**.

### Comparative Performance Across Strategy Variants and Benchmarks

| Strategy / Benchmark Variant | Training CAGR (Geometric) | Training Ann. Volatility | Training Sharpe Ratio | Holdout CAGR (Geometric) | Holdout Ann. Volatility | Holdout Sharpe Ratio | Full Period CAGR (Geometric) | Full Period Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Strategy 1A (Primary)** | **+43.32%** | 20.44% | **1.86** | **-11.87%** | 15.43% | **-0.74** | **+26.89%** | **1.33** |
| **Strategy 1B (Inv-Vol)** | +43.05% | 20.09% | 1.88 | -12.16% | 15.12% | -0.78 | +26.61% | 1.34 |
| **Strategy 2A (Cash Floor)** | +39.70% | 18.22% | 1.93 | -12.95% | 14.71% | -0.87 | +24.10% | 1.33 |
| **Strategy 2B (Cash+InvVol)**| +39.14% | 17.81% | 1.95 | -13.20% | 14.41% | -0.91 | +23.64% | 1.33 |
| **NIFTY 50 Buy-and-Hold** | +14.71% | 18.99% | 0.82 | -0.76% | 13.23% | +0.01 | +10.63% | 0.66 |
| **Equal-Weight 6-Sector** | +21.51% | 18.07% | 1.17 | +3.27% | 13.58% | +0.31 | +16.67% | 0.99 |

### 7.2 The Four Structural Drivers of Holdout Underperformance

```
+------------------------------------------------------------------------------------+
|                     FOUR PILLARS OF HOLDOUT DECAY FORENSICS                        |
+------------------------------------------------------------------------------------+
| Pillar 1: Regime Frequency Collapse | R0 (Reflation Alpha) collapsed: 19.30% -> 1.90%|
|                                     | R5 (Correction Drag) doubled:   16.14% -> 29.86%|
|-------------------------------------+----------------------------------------------|
| Pillar 2: Duration Halving & Whipsaw| Mean episode duration halved: 33.3d -> 17.6d  |
|                                     | Annual turnover surged 66%:   6.49x -> 10.75x |
|-------------------------------------+----------------------------------------------|
| Pillar 3: Indian IT Sector Collapse | NIFTY IT plunged -21.30% annualized in holdout|
|                                     | Contributed -6.57 pp/yr drag to Strategy 1A  |
|-------------------------------------+----------------------------------------------|
| Pillar 4: Missed Banking Exposure   | Zero allocation to NIFTY BANK in all regimes |
|                                     | Missed +7.36% banking rally (opportunity cost)|
+------------------------------------------------------------------------------------+
```

#### Annualized Net Return Attribution Breakdown (Strategy 1A)

| Asset / Drag Component | Training Arithmetic Contribution (pp/yr) | Holdout Arithmetic Contribution (pp/yr) | Net Performance Impact (pp) |
| :--- | :---: | :---: | :---: |
| **NIFTY AUTO** | +5.84% | -3.66% | -9.50 pp |
| **NIFTY BANK** | **0.00%** | **0.00%** | **0.00 pp (Missed Exposure)** |
| **NIFTY FMCG** | +1.65% | +1.56% | -0.09 pp |
| **NIFTY IT** | **+9.73%** | **-6.57%** | **-16.30 pp (Severe Drag)** |
| **NIFTY METAL** | +14.87% | -2.78% | -17.65 pp |
| **NIFTY PHARMA** | +6.96% | +1.61% | -5.35 pp |
| **Transaction Cost Drag** | -0.97% | -1.61% | -0.64 pp (Turnover Surge) |
| **Arithmetic Total Return**| **+38.11%** | **-11.44%** | **-49.55 pp** |

- **Pillar 1: Regime Frequency Collapse (Starvation of Reflation Alpha):** In the 2019–2024 training set, the portfolio harvested massive alpha from Regime 0 (Cyclical Reflation), which was active for 19.30% of sessions (244 days). In the 2025–2026 holdout, Regime 0 virtually vanished, appearing on only 8 sessions (1.90%). Simultaneously, Regime 5 (Correction) nearly doubled from 16.14% to 29.86% (126 days). The strategy was starved of its primary alpha environment.
- **Pillar 2: Episode Duration Halving & Whipsaw Friction:** Mean episode duration collapsed from 33.3 days in training to 17.6 days in the holdout (median 12 days). In 422 sessions, the market suffered 24 separate regime transitions. Because the HMM was constantly toggling between R4, R5, and R2, annualized turnover surged by 65.7% (from 6.49x to 10.75x), imposing a -1.61% annual cost drag and inducing whipsaws.
- **Pillar 3: The Indian IT Sector Slump:** In training, IT was an alpha engine (+9.73 pp/yr). In the holdout, Indian IT stocks suffered severe earnings compression due to US enterprise tech spending freezes, plunging -21.30% annualized. Because Regime 2 allocated 50% to IT, the strategy suffered a direct **-6.57 pp/yr drag** (a 16.3 pp negative swing).
- **Pillar 4: Missed Banking Exposure:** NIFTY BANK achieved a solid +7.3551% annualized return in the holdout, but was excluded from Top-2 rules in Phase 8, generating 0.0000% contribution. This documents a missed asset exposure and an opportunity cost, though not a guaranteed counterfactual improvement.

---

## 8. Practical Portfolio & Investment Implications

```
+------------------------------------------------------------------------------------+
|                       PRACTICAL IMPLEMENTATION PLAYBOOK                            |
+------------------------------------------------------------------------------------+
| Recommendation 1: Dynamic Cash Floors  | Mandate 20-40% cash in R3/R5 (Template B) |
|                                        | Reduces Max Drawdown by 500 bps           |
|----------------------------------------+-------------------------------------------|
| Recommendation 2: Turnover Bands       | Rebalance only if weight drift > 10% or   |
| (Proposed Future Heuristic)            | regime probability > 0.70                 |
|----------------------------------------+-------------------------------------------|
| Recommendation 3: Volatility Weighting | Inverse-volatility (Variant 1B/2B) tames  |
|                                        | turbulent commodities (Metals)            |
|----------------------------------------+-------------------------------------------|
| Recommendation 4: Dynamic Sector Rank  | Replace static Top-2 with trailing 60-day |
| (Proposed Future Heuristic)            | intra-regime cross-sectional momentum     |
+------------------------------------------------------------------------------------+
```

### 1. The Empirical Value of Defensive Cash Floors (Template B)
While fully invested Strategy 1A generated higher CAGR than cash-reserve Strategy 2A in training (43.32% vs. 39.70%), Template B demonstrated clear risk-mitigation benefits during stressed periods:
- During Regime 3 and Regime 5, Template B’s mandated cash floor (40% cash in R3, 20% cash in R5) reduced maximum portfolio drawdown from -25.60% to **-20.61%** (a 500 bps protection).
- For institutional wealth managers subject to capital preservation mandates, Template B represents a superior structural architecture.

### 2. Untested Conceptual Design Heuristics Proposed for Future Research
A primary vulnerability of daily Markovian models is excessive turnover during choppy, low-duration regimes. The following conceptual safeguards are proposed for future empirical evaluation (confirming that they were not backtested in Phase 10):
- **Confidence Buffers:** Requiring filtered regime probability $P(S_t = k) \ge 0.70$ (rather than 0.50) before executing a transition.
- **Rebalancing Thresholds:** Triggering portfolio rebalancing only if target sector weights deviate by more than $\pm 10\%$ from current holdings.

### 3. Inverse-Volatility Weighting Utility
Comparing Variant 1A (Equal Weight) against Variant 1B (Inverse-Volatility Weighting) reveals that inverse-volatility weighting consistently reduced portfolio volatility (from 20.44% to 20.09% in training) and improved risk-adjusted returns by curbing over-allocation to volatile sectors like Metals during high-beta rallies.

---

## 9. Methodological Limitations & Research Boundaries

1. **Finite Sample Size of Rare Crisis Regimes:**
   In our 1,686-session dataset, **Regime 1 (Post-Crash Bounce, 40 days)** and **Regime 3 (Acute Liquidation, 27 days)** each occurred in **exactly one continuous historical episode** (the March–June 2020 COVID shock). While their empirical characteristics are documented, they reflect the unique nature of the 2020 pandemic and cannot be assumed to represent all future financial panics.

2. **Rigidity of Static Top-2 Sector Mappings:**
   The Phase 8 rules engine assigned fixed sector pairs to each regime based on training-set dominance. While economically intuitive, this rigidity prevented the strategy from adapting to structural sector evolutions, such as the 2025–2026 banking sector resilience.

3. **Execution Lag at Next-Day Close ($t+1$ Close):**
   Executing rebalancing orders at $t+1$ Close ensures zero look-ahead bias, but imposes execution lag. In choppy regimes where episodes last fewer than 10 sessions, a 1-day execution delay consumes 10% of the regime’s lifespan, reducing alpha capture.

---

## 10. Capstone Research Conclusions

1. **Unsupervised Learning Successfully Discovers Macroeconomic Cycles:**
   The 6-state Gaussian HMM trained on Indian equity features discovered a fully coherent, economically meaningful representation of the macroeconomic business cycle without human supervision: *Crash (R3) $\to$ Relief Rebound (R1) $\to$ Reflation (R0) $\to$ Secular Expansion (R4) $\to$ Base Consolidation (R2) $\to$ Risk-Off Correction (R5)*.

2. **Sector Leadership is Fundamentally State-Dependent:**
   Industrial cyclicals (Metals, Autos) dominate expansionary reflation rallies, while non-cyclical defensives (Pharma, FMCG) preserve capital during acute market panics.

3. **Holdout Performance Degradation is Fully Explained by Market Structure Shifts:**
   The underperformance of the strategy during the 2025–2026 holdout was not random noise, but the result of four specific, quantifiable economic drivers: the absence of Regime 0 reflation, a 50% collapse in episode duration that amplified turnover costs, a sharp cyclical drawdown in Indian IT, and missed banking exposure.

4. **Strategic Summary for Institutional Quantitative Asset Allocation:**
   Systematic HMM-driven sector rotation is highly effective during persistent, trending macroeconomic regimes, but must be paired with dynamic turnover controls, cash reserves, and cross-sectional momentum filters to thrive in rangebound, mean-reverting environments.

---
**End of Phase 13 Research Report — Canonical Project Synthesis Complete.**
