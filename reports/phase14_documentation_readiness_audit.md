# Phase 14 — Final Documentation Readiness Audit & Technical Architecture Baseline

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Phase:** Phase 14 — Final Research Documentation & Project Architecture  
**Audit Type:** Repository-Wide Evidence Collection, Data Ingestion Mapping & Documentation Readiness Assessment  
**Audit Mode:** Strictly Read-Only  
**Date:** November 6, 2026  
**Lead Auditor:** Senior Quantitative Finance Researcher & ML Systems Architect  
**Permitted New File:** `reports/phase14_documentation_readiness_audit.md` (Single Authorized Output)

---

## 1. Executive Summary

This readiness audit conducts an exhaustive, read-only forensic examination of the complete quantitative research codebase spanning **Phases 1 through 13** of the project *Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market*.

The primary objective is to evaluate whether all theoretical formulations, empirical datasets, backtest results, statistical validation outputs, event-study panels, and economic interpretations are available, mathematically sound, and sufficiently documented to author the two final deliverables authorized for Phase 14:
1. **Complete Research Report (PDF):** A publication-grade, academic monograph synthesizing the full research lifecycle from data acquisition to the forensic holdout decay diagnosis.
2. **Complete Project Architecture Document (PDF):** A formal quantitative systems engineering specification documenting the end-to-end data pipeline, model inference mechanics, modular execution graph, and conceptual future production deployment boundary.

### Audit Summary Statistics
```
========================================================================================
                          PHASE 14 READINESS AUDIT SCORECARD
========================================================================================

  Total Phases Reconstructed:                 13 Phases (Phases 1–13 + 4 Subphases in P10)
  Total Repository Files Audited:             233 Files across 7 Primary Subdirectories
  Python Source Modules (`src/`):             17 Active Modules (1.00 MB source code)
  Jupyter Execution Notebooks (`notebooks/`): 16 Sequential Notebooks (15.63 MB)
  Authoritative Datasets (`data/` & `results/`): 113 CSV / Parquet Datasets (17.43 MB)
  Visual Figures & Diagrams:                  31 Visual Artifacts (PNG / PDF / SVG)
  Automated Regression Test Suite:            177/177 Tests Passing (100% Pass Rate)
  Research Findings Traced to Source:         100% Traceability across all Core Claims
  Readiness Verdict — Research Report PDF:    READY — ALL SECTIONS SUPPORTED BY DATA
  Readiness Verdict — Architecture PDF:       READY — FULL TECHNICAL PIPELINE MAPPED

========================================================================================
```

---

## 2. Repository-Wide Inventory

The repository is organized into a clean, modular structure conforming to standard quantitative engineering and reproducible research practices.

### 2.1 Directory Structure & File Counts

```
sector-rotation-regime-discovery/
├── data/                                 # 35 files (8.98 MB)
│   ├── raw/                              # Market, sector indices, and macro-event raw CSVs
│   └── processed/                        # Cleaned, calendar-aligned, engineered, normalized
│       ├── cleaned/                      # 9 cleaned asset CSVs + major events
│       ├── aligned/                      # 8 NSE calendar-aligned CSVs (1,886 sessions)
│       ├── feature_engineered/           # 7 sector/market feature sets (20D, 60D, 200D)
│       └── normalized/                   # Robust & Standard master feature matrices
├── docs/                                 # Empty directory reserved for static documentation
├── notebooks/                            # 19 files (15.63 MB) — 16 executed phase notebooks
│   ├── 01_data_collection.ipynb to 10_portfolio_backtest.ipynb
│   ├── benchmark_engine.ipynb, compare_performance.ipynb, robustness_testing.ipynb
│   ├── statistical_validation.ipynb, event_analysis.ipynb
│   └── zz_phase13_economic_interpretation.ipynb (Final sequential notebook)
├── reports/                              # 27 files (5.47 MB)
│   ├── Phase reports (Phases 9, 10, 11, 12, 13)
│   ├── Audit & Verification logs (Phases 10, 13)
│   ├── Publication PDFs (Phase 10.3, Phase 11 formulations, Phase 12, Phase 13)
│   └── phase13_figures/                  # 6 canonical publication-grade 300-DPI PNGs
├── results/                              # 78 files (8.45 MB) — Canonical empirical outputs
│   ├── regime_discovery/                 # HMM models, labels, transition matrices, timelines
│   ├── phase6_model_selection/           # CV metrics for K-Means, GMM, HMM
│   ├── regime_characterization/          # Profiles, sector leadership, correlation matrices
│   ├── portfolio_construction/           # Target weight schedules (1A, 1B, 2A, 2B)
│   ├── portfolio_backtest/               # Master daily simulation Parquets & metrics summaries
│   │   ├── comparative_evaluation/       # Cross-model comparisons & rankings
│   │   └── robustness/                   # 6 sub-dimensions of stress testing
│   ├── statistical_validation/           # Bootstrap, HAC alpha/beta, duration diagnostics
│   └── event_analysis/                   # 7 authoritative event parquets & figure mirrors
├── src/                                  # 48 files (1.00 MB) — Production source code
│   ├── data_loader.py, data_cleaning.py, feature_engineering.py, eda.py, normalization.py
│   ├── regime_discovery.py, regime_characterisation.py, regime_rotation_rules.py
│   ├── portfolio_construction.py, portfolio_backtest.py, benchmark_backtest.py
│   ├── comparative_evaluation.py, robustness_testing.py, statistical_validation.py, event_analysis.py
│   └── robustness/                       # 7 sub-modules for stress and sensitivity testing
└── tests/                                # 22 files (0.78 MB) — 10 unit/integration test modules
```

### 2.2 Source Modules Responsibility Inventory

| Module Path | Primary Class / Functions | Phase | Core Responsibility |
|---|---|:---:|---|
| `src/data_loader.py` | `fetch_ticker_data()`, `validate_raw_data()` | Phase 1 | Ingests OHLCV data from Yahoo Finance for NIFTY 50, India VIX, and 6 sectoral indices. |
| `src/data_cleaning.py` | `clean_ohlcv_data()`, `align_trading_calendar()` | Phase 2 | Handles missing values, weekend drops, holiday reconciliation, and zero-volume filtering. |
| `src/feature_engineering.py` | `compute_momentum()`, `compute_relative_strength()` | Phase 3 | Generates 20D/60D/200D market trend ratios, sector relative strength, and rolling volatilities. |
| `src/eda.py` | `plot_correlation_matrix()`, `run_stationarity_tests()` | Phase 4 | Statistical profiling, ADF stationarity testing, skewness, kurtosis, and correlation heatmaps. |
| `src/normalization.py` | `fit_scale_train()`, `transform_holdout()` | Phase 5 | Strict training-pool fitting (RobustScaler & StandardScaler) with frozen transformation on holdout. |
| `src/regime_discovery.py` | `fit_hmm()`, `forward_filter()`, `viterbi_decode()` | Phase 6 | 3-fold expanding CV, Baum-Welch HMM training ($K=6$, diagonal), causal forward filtering. |
| `src/regime_characterisation.py`| `compute_model_regime_profiles()`, `radar_chart()` | Phase 7 | Multi-dimensional empirical profiling, duration stats, occupancy, and forward-return matrices. |
| `src/regime_rotation_rules.py` | `select_top_sectors()`, `map_regime_to_sectors()` | Phase 8 | Decision logic mapping active HMM states to Top-2 sector selections based on historical RS. |
| `src/portfolio_construction.py`| `generate_target_weights()`, `apply_cash_floor()` | Phase 9 | Constructs Target Weight Schedules for 4 strategy variants (1A, 1B, 2A, 2B). |
| `src/portfolio_backtest.py` | `simulate_portfolio()`, `compute_performance_metrics()`| Phase 10.1| Vectorized daily portfolio backtest engine with 15 bps turnover transaction cost modeling. |
| `src/benchmark_backtest.py` | `simulate_nifty50()`, `simulate_equal_weight()` | Phase 10.2| Simulates buy-and-hold benchmarks (NIFTY 50 and Equal-Weight 6-Sector). |
| `src/comparative_evaluation.py`| `compute_comparative_table()`, `rank_strategies()` | Phase 10.3| Compiles master comparative evaluation matrix and institutional risk-adjusted rankings. |
| `src/robustness_testing.py` | `run_robustness_battery()` | Phase 10.4| Orchestrates 6-dimensional robustness stress tests (costs, execution, parameters, etc.). |
| `src/statistical_validation.py` | `run_stationary_bootstrap()`, `hac_regressions()` | Phase 11 | Politis-Romano stationary bootstrap, Ledoit-Wolf Sharpe inference, Newey-West HAC alpha. |
| `src/event_analysis.py` | `run_event_study()`, `compute_caar()`, `bootstrap_p()` | Phase 12 | Market model abnormal returns (CAR $[-2, +2]$), CAAR by macro category, portfolio drawdown. |

---

## 3. Phase 1–13 Workflow & Technical Reconstruction

```
+-------------------------------------------------------------------------------------------------------------------------+
|                                           END-TO-END QUANTITATIVE RESEARCH PIPELINE                                     |
+-------------------------------------------------------------------------------------------------------------------------+
| [Phase 1: Ingestion]   --> 8 NSE Asset Indices + India VIX + 135 Macro Events (2018–2026)                               |
|          |                                                                                                              |
| [Phase 2: Cleaning]    --> Missing-value handling, calendar alignment (1,886 synchronized sessions)                     |
|          |                                                                                                              |
| [Phase 3: Features]    --> 20D/60D/200D Market Ratios, Sector Relative Strength, Realized Volatility                    |
|          |                                                                                                              |
| [Phase 4: EDA]         --> Stationarity tests (ADF), distributional properties, correlation structures                  |
|          |                                                                                                              |
| [Phase 5: Scaling]     --> RobustScaler fit strictly on Train (2019-10-31 to 2024-12-31, 1,265d); Holdout transformed  |
|          |                                                                                                              |
| [Phase 6: Regimes]     --> Expanding-window CV (150 fits); Gaussian HMM (K=6, Diag Cov); Causal Filtering               |
|          |                                                                                                              |
| [Phase 7: Profiles]    --> Multi-dimensional characterization: duration medians, sector RS, VIX distributions           |
|          |                                                                                                              |
| [Phase 8: Rules]       --> Regime-conditioned Top-2 selection logic (Cyclical vs. Defensive asymmetry)                  |
|          |                                                                                                              |
| [Phase 9: Portfolios]  --> 4 Variants: 1A (EW Full), 1B (Inv-Vol Full), 2A (EW Cash Floor), 2B (Inv-Vol Cash Floor)     |
|          |                                                                                                              |
| [Phase 10: Backtests]  --> Daily simulation (1,686 sessions), 15 bps slippage/costs, comparative ranking, robustness     |
|          |                                                                                                              |
| [Phase 11: Validation] --> Stationary bootstrap (B=2,000), Ledoit-Wolf Sharpe test, Newey-West HAC alpha, FDR bounds  |
|          |                                                                                                              |
| [Phase 12: Events]     --> 122 backtest events, 68 macro episodes, market model CAR [-2, +2], CAAR bootstrap inference |
|          |                                                                                                              |
| [Phase 13: Synthesis]  --> Capstone economic profiling, transition dynamics, forensic holdout decay diagnosis           |
+-------------------------------------------------------------------------------------------------------------------------+
```

### Phase-by-Phase Technical Audit

#### Phase 1: Data Acquisition & Universe Ingestion
- **Objective:** Establish an automated, repeatable ingestion pipeline for the Indian equity sector universe and macroeconomic risk proxies over a minimum 7-year history (2018–2026).
- **Necessity:** High-quality daily price history for Indian sectoral indices was required to capture diverse macroeconomic business cycles (2019 pre-COVID, 2020 crash, 2021–2024 bull run, 2025–2026 consolidation).
- **Implementation & Source:** `src/data_loader.py` and `notebooks/01_data_collection.ipynb`. Ingests OHLCV data from Yahoo Finance for 8 symbols: NIFTY 50 (`^NSEI`), India VIX (`^INDIAVIX`), NIFTY AUTO (`^CNXAUTO`), NIFTY BANK (`^NSEBANK`), NIFTY FMCG (`^CNXFMCG`), NIFTY IT (`^CNXIT`), NIFTY METAL (`^CNXMETAL`), and NIFTY PHARMA (`^CNXPHARMA`).
- **Outputs:** `data/raw/market/` and `data/raw/sector_indices/` CSV files.
- **Verification Result:** PASS. Complete raw CSVs verified on disk.

#### Phase 2: Data Cleaning & Calendar Alignment
- **Objective:** Reconcile asynchronous holiday schedules, resolve zero-volume sessions, verify corporate action adjustments, and create a single unified trading calendar.
- **Necessity:** Missing values or mismatched dates across sector indices would introduce spurious cross-sectional dispersion or break matrix algebra in HMM training.
- **Implementation & Source:** `src/data_cleaning.py` and `notebooks/02_data_cleaning_alignment.ipynb`. Applied forward-fill for single-day gaps, validated non-negative volumes and prices, and aligned all assets to the official NSE trading calendar.
- **Outputs:** `data/processed/cleaned/*.csv` and `data/processed/aligned/*.csv` ($N = 1,886$ sessions from 2019-01-02 to 2026-09-18).
- **Verification Result:** PASS. Cleaned and aligned files exist with zero null values across all columns.

#### Phase 3: Feature Engineering
- **Objective:** Transform raw prices into economically stationary, predictive feature representations capturing broad market momentum, long-term trend, market volatility, and sector relative strength.
- **Necessity:** Raw asset prices are non-stationary ($I(1)$); machine learning clustering requires stationary ($I(0)$), normalized indicators of economic conditions.
- **Implementation & Source:** `src/feature_engineering.py` and `notebooks/03_feature_engineering.ipynb`. Generated:
  - Broad Market Momentum: $\text{Ratio}_{20D} = P_t / P_{t-20}$ and $\text{Ratio}_{60D} = P_t / P_{t-60}$.
  - Broad Market Trend: $\text{Trend}_{200D} = P_t / \text{SMA}_{200}(P_t)$.
  - Implied Volatility: Raw India VIX Close ($VIX_t$).
  - Sector Relative Strength: $RS_{s, 20D} = r_{s, 20D} - r_{m, 20D}$ and $RS_{s, 60D} = r_{s, 60D} - r_{m, 60D}$.
  - Sector Realized Volatility: $\sigma_{s, 20D} \times \sqrt{252}$ and $\sigma_{s, 60D} \times \sqrt{252}$.
- **Outputs:** `data/processed/feature_engineered/*.csv`.
- **Verification Result:** PASS. Feature definitions verified; 200-day warm-up window properly handled.

#### Phase 4: Exploratory Data Analysis (EDA)
- **Objective:** Evaluate feature distributions, check collinearity, detect structural breaks, and verify stationarity via Augmented Dickey-Fuller (ADF) tests.
- **Necessity:** Confirm that engineered features do not violate statistical assumptions of mixture models and HMMs.
- **Implementation & Source:** `src/eda.py` and `notebooks/04_eda.ipynb`. ADF tests confirmed stationarity ($p < 0.01$) for all return and relative strength features. Pairwise correlations identified multi-collinearity boundaries.
- **Outputs:** Embedded EDA plots in `04_eda.ipynb` (8.1 MB notebook).
- **Verification Result:** PASS. Verified in notebook outputs.

#### Phase 5: Normalization & Preprocessing
- **Objective:** Scale multi-dimensional features while strictly preserving the temporal train/holdout boundary to prevent lookahead bias and data leakage.
- **Necessity:** Neural networks and Gaussian mixture models are sensitive to disparate feature scales (e.g. VIX ranging from 9 to 83 vs. relative strength ranging from -0.15 to +0.15).
- **Implementation & Source:** `src/normalization.py` and `notebooks/05_normalization.ipynb`. Scalers fit strictly on the **Training Pool** (`2019-10-31` to `2024-12-31`, 1,265 sessions). Holdout Pool (`2025-01-02` to `2026-09-18`, 422 sessions) transformed using the frozen training scalers. Applied both `RobustScaler` (median & IQR) and `StandardScaler` (z-score).
- **Outputs:** `data/processed/normalized/robust/master_features_robust.csv` and `data/processed/normalized/standard/master_features_standard.csv`.
- **Verification Result:** PASS. Verified zero leakage; scalers fit exclusively on training data.

#### Phase 6: Unsupervised Regime Discovery
- **Objective:** Train and select the optimal unsupervised clustering architecture to discover distinct market states in the Indian equity market.
- **Necessity:** Supervised regime classification imposes arbitrary human labels (e.g. "bull" or "bear") that fail to capture subtle multi-asset volatility and liquidity shifts.
- **Implementation & Source:** `src/regime_discovery.py` and `notebooks/06_regime_discovery.ipynb`. Conducted a 3-fold expanding-window cross-validation battery (150 HMM fits across 10 random seeds $\times$ 5 $K$ values $\times$ 3 folds) comparing K-Means ($K=2..6$), Gaussian Mixture Models ($K=2..6$, multiple covariance types), and Gaussian Hidden Markov Models ($K=2..6$).
- **Selection Decision:** **Gaussian HMM with $K=6$, diagonal covariance, RobustScaler** was selected based on validation log-likelihood per observation ($-36.11$), convergence rate ($10/10$ seeds), and state persistence (mean diagonal $0.9707$).
- **Dual Inference Engine:**
  1. *Retrospective Viterbi Decoding:* Global sequence optimization using future information (research benchmark).
  2. *Causal Forward-Filtered Probabilities:* Real-time filtering $\alpha_t(i) = P(S_t = i \mid x_{1:t})$ with zero future lookahead (backtest engine driver).
- **Outputs:** `results/regime_discovery/final_regime_labels.csv`, `hmm_causal_probabilities.csv`, `hmm_transition_matrix.png`, `regime_timelines.png`.
- **Verification Result:** PASS. All model selection metrics and label files verified on disk.

#### Phase 7: Regime Characterization & Profiling
- **Objective:** Quantify the empirical properties of each discovered HMM state across duration, market returns, volatility, VIX distributions, and sector leadership.
- **Necessity:** Unsupervised clusters lack inherent labels; empirical profiling is necessary to ground each state in financial reality before constructing investment rules.
- **Implementation & Source:** `src/regime_characterisation.py` and `notebooks/07_regime_characterisation.ipynb`.
- **Outputs:** `results/regime_characterization/regime_profiles/model_regime_profiles.csv`, correlation heatmaps, sector leadership stability tables.
- **Verification Result:** PASS. Verified complete profile matrix across all candidate models.

#### Phase 8: Systematic Sector Rotation Rules
- **Objective:** Formulate systematic, objective mapping rules that translate active HMM regime probabilities into target sector allocations.
- **Necessity:** Eliminate subjective human discretion by programmatically tying historical sector alpha to detected macro regimes.
- **Implementation & Source:** `src/regime_rotation_rules.py`, `notebooks/08_sector_rotation_rules.ipynb`, and proposal document `phase_8_2_sector_rotation_rules_proposal.md`.
- **Selection Logic:** Dynamically selects the **Top-2 sector indices** exhibiting the strongest historical risk-adjusted relative strength within each detected regime.
- **Outputs:** Documented rule schedules embedded in `src/portfolio_construction.py`.
- **Verification Result:** PASS. Rule architecture validated against Phase 7 empirical rankings.

#### Phase 9: Portfolio Construction & Allocation Architecture
- **Objective:** Translate sector selection signals into actionable daily target weight schedules under varying weighting schemes and risk management overlays.
- **Necessity:** Test whether risk parity (inverse volatility) or dynamic cash preservation enhances regime-driven sector rotation.
- **Implementation & Source:** `src/portfolio_construction.py`, `notebooks/09_portfolio_construction.ipynb`, and report `reports/phase9_2_portfolio_construction.md`.
- **Four Standardized Variants:**
  - **Variant 1A:** Equal-Weight (50% / 50%) Top-2 Sectors, Fully Invested (0% Cash).
  - **Variant 1B:** Inverse-Volatility Weighted Top-2 Sectors, Fully Invested (0% Cash).
  - **Variant 2A:** Equal-Weight Top-2 Sectors with Dynamic Cash Floor (Template B: 50% Cash in R3/R5, 20% in R2).
  - **Variant 2B:** Inverse-Volatility Top-2 Sectors with Dynamic Cash Floor.
- **Outputs:** `results/portfolio_construction/target_weights_1A.csv` through `2B.csv` (1,687 daily weight vectors).
- **Verification Result:** PASS. Weight schedules verified; sum of weights strictly equals 1.0 (with cash).

#### Phase 10: Frozen-Baseline Backtesting, Benchmark Comparison & Robustness
- **Objective:** Execute an institutional-grade, daily portfolio backtest over the full sample (2019–2026), compare against benchmarks, and test robustness across 6 risk dimensions.
- **Necessity:** Verify whether regime-based sector rotation generates authentic risk-adjusted alpha after transaction friction, and isolate points of failure.
- **Implementation & Source:**
  - *10.1 Strategy Simulation:* `src/portfolio_backtest.py`, `notebooks/10_portfolio_backtest.ipynb`, reports `phase10_1_readiness_audit.md`, `phase10_3_backtest_engine.md`. Models 15 bps one-way transaction costs.
  - *10.2 Benchmark Engine:* `src/benchmark_backtest.py`, `notebooks/benchmark_engine.ipynb`. Simulates NIFTY 50 Buy-and-Hold and Equal-Weight 6-Sector.
  - *10.3 Comparative Evaluation:* `src/comparative_evaluation.py`, `notebooks/compare_performance.ipynb`, report `reports/phase10_5_comparative_evaluation.md`.
  - *10.4 Robustness Testing:* `src/robustness_testing.py`, `src/robustness/*.py`, `notebooks/robustness_testing.ipynb`, report `reports/phase10_6_robustness_testing.md`. Stress tests: transaction costs (10–50 bps), execution timing (Close-to-Close vs Next-Open), parameter sensitivity, concentration, subperiod stability, and momentum benchmark comparison.
- **Outputs:** Master Parquets: `daily_simulation_1A.parquet` through `2B.parquet`, `metrics_summary.parquet`, `benchmark_metrics_summary.parquet`, and 10 robustness summary files.
- **Verification Result:** PASS. 100% frozen backtest records intact.

#### Phase 11: Training-Period Statistical Validation
- **Objective:** Subject the training-period outperformance to rigorous econometric hypothesis testing and multiple testing corrections.
- **Necessity:** Rule out data snooping, p-hacking, and sample-selection bias as drivers of the observed strategy performance.
- **Implementation & Source:** `src/statistical_validation.py`, `notebooks/statistical_validation.ipynb`, reports `reports/phase11_statistical_validation.md`, `reports/phase11_formulations.pdf`.
- **Econometric Methods:**
  - Politis & Romano (1994) Stationary Bootstrap ($B = 2,000$ iterations, optimal block length).
  - Newey-West Heteroskedasticity and Autocorrelation Consistent (HAC) robust standard errors.
  - Ledoit-Wolf (2008) / Jobson-Korkie-Memmel hypothesis test for Sharpe ratio equality.
  - Holm-Bonferroni (FWER) and Benjamini-Hochberg (FDR) multiple testing adjustments.
  - Nonparametric empirical duration analysis and bootstrap survival diagnostics.
- **Outputs:** `results/statistical_validation/*.parquet` (7 authoritative tables).
- **Verification Result:** PASS. Verified: Strategy 1A training alpha is statistically significant ($p < 0.001$), but Sharpe difference over NIFTY 50 was borderline after HAC adjustment ($p = 0.052$).

#### Phase 12: Event-Based Market Analysis
- **Objective:** Evaluate how macroeconomic shocks interact with regime transitions, sector abnormal returns, and portfolio resilience.
- **Necessity:** Quantify strategy behavior during extreme historical tail events (e.g. COVID crash, Russia-Ukraine war, Union Budgets, RBI monetary policy shocks).
- **Implementation & Source:** `src/event_analysis.py`, `notebooks/event_analysis.ipynb`, reports `reports/phase12_event_analysis.md`, `reports/phase12_event_analysis.pdf`.
- **Event Methodology:** Market Model Cumulative Abnormal Returns (CAR $[-2, +2]$ and $[-5, +5]$) across 122 events (68 multi-session episodes) categorized into 7 macro classes. Bootstrapped CAAR inference.
- **Outputs:** `results/event_analysis/*.parquet` (7 authoritative tables).
- **Verification Result:** PASS. Authoritative event catalog and CAR summary panel verified.

#### Phase 13: Economic Interpretation of Market Regimes
- **Objective:** Synthesize all empirical findings from Phases 6–12 into an economically meaningful, mathematically rigorous research narrative.
- **Necessity:** Bridge the gap between machine learning clustering and macroeconomic theory, while providing an unsparing forensic diagnosis of the holdout performance collapse.
- **Implementation & Source:** `notebooks/zz_phase13_economic_interpretation.ipynb`, reports `reports/phase13_regime_interpretation.md`, `reports/phase13_regime_interpretation.pdf`, and audits `reports/phase13_targeted_discrepancy_investigation.md`, `reports/phase13_vix_documentation_correction_completion.md`.
- **Outputs:** 6 publication figures in `reports/phase13_figures/` and `results/event_analysis/phase13_figures/`, synchronized 14-page PDF document.
- **Verification Result:** PASS. 100% synchronized across all audit areas.

---

## 4. Complete Research Methodology Reconstruction

### 4.1 Research Universe & Temporal Boundaries
- **Market Universe:** National Stock Exchange of India (NSE).
- **Asset Universe:**
  - Broad Market Benchmark: NIFTY 50 Index (`^NSEI`).
  - Volatility Index: India VIX (`^INDIAVIX`).
  - Sectoral Universe (6 Canonical Indices): NIFTY AUTO, NIFTY BANK, NIFTY FMCG, NIFTY IT, NIFTY METAL, NIFTY PHARMA.
- **Temporal Sample Structure:**
  - Full Backtest Window: **November 1, 2019 to September 18, 2026** ($T = 1,686$ simulated daily return intervals).
  - Feature & Label Window: **October 31, 2019 to September 18, 2026** ($N = 1,687$ trading sessions, including $t_0$).
  - Training Period (In-Sample): **October 31, 2019 to December 31, 2024** ($1,265$ label days / $1,264$ simulated return intervals).
  - Holdout Period (Out-of-Sample Lockbox): **January 2, 2025 to September 18, 2026** ($422$ trading sessions / return intervals).

### 4.2 Mathematical Formulations

#### Feature Calculations
1. **Broad Market Trend Ratios:**
   $$\text{Ratio}_{20D, t} = \frac{P_{m, t}}{P_{m, t-20}}, \quad \text{Ratio}_{60D, t} = \frac{P_{m, t}}{P_{m, t-60}}, \quad \text{Trend}_{200D, t} = \frac{P_{m, t}}{\frac{1}{200}\sum_{i=0}^{199} P_{m, t-i}}$$
2. **Sector Relative Strength:**
   $$RS_{s, k, t} = \left(\frac{P_{s, t}}{P_{s, t-k}} - 1\right) - \left(\frac{P_{m, t}}{P_{m, t-k}} - 1\right), \quad k \in \{20, 60\}$$
3. **Sector Realized Volatility:**
   $$\sigma_{s, k, t} = \sqrt{\frac{252}{k-1} \sum_{i=0}^{k-1} \left(r_{s, t-i} - \bar{r}_{s}\right)^2}, \quad k \in \{20, 60\}$$

#### Hidden Markov Model Mechanics
The system assumes an unobserved discrete Markov chain $S_t \in \{0, 1, \dots, 5\}$ with state transition probability matrix $A = [a_{ij}]$ where $a_{ij} = P(S_{t+1} = j \mid S_t = i)$. The emission probability density for observation vector $x_t \in \mathbb{R}^D$ is Gaussian:
$$b_j(x_t) = \mathcal{N}(x_t; \mu_j, \Sigma_j) = \frac{1}{(2\pi)^{D/2} |\Sigma_j|^{1/2}} \exp\left(-\frac{1}{2}(x_t - \mu_j)^T \Sigma_j^{-1} (x_t - \mu_j)\right)$$
Where $\Sigma_j$ is a diagonal covariance matrix. Causal forward filtering computes:
$$\alpha_t(j) = P(x_1, \dots, x_t, S_t = j) = b_j(x_t) \sum_{i=0}^{K-1} \alpha_{t-1}(i) a_{ij}$$
Filtered state probability:
$$\gamma_t(j) = P(S_t = j \mid x_{1:t}) = \frac{\alpha_t(j)}{\sum_{k=0}^{K-1} \alpha_t(k)}$$

#### Portfolio Simulation & Friction Accounting
For target weights $w_{t}$ decided at $t-1$ Close, gross return is:
$$R_{\text{gross}, t} = \sum_{s=1}^{6} w_{s, t} \cdot r_{s, t} + w_{\text{cash}, t} \cdot r_{\text{cash}}$$
Where $r_{\text{cash}} = \frac{0.05}{252}$ ($5.0\%$ risk-free rate). Turnover transaction cost:
$$\text{Turnover}_t = \sum_{s=1}^{6} |w_{s, t} - w_{s, t-1}^+|$$
$$\text{Cost Drag}_t = \text{Turnover}_t \times 0.0015 \quad (15\text{ bps})$$
$$R_{\text{net}, t} = R_{\text{gross}, t} - \text{Cost Drag}_t$$

---

## 5. Canonical Datasets & Artifact Dependency Inventory

| Artifact Path | Generating Phase | Format | Shape / Coverage | Description & Purpose | Downstream Dependency |
|---|:---:|:---:|:---:|---|---|
| `data/processed/aligned/nifty50_aligned.csv` | Phase 2 | CSV | 1,886 × 6 | Master trading calendar & NIFTY 50 reference prices. | Phases 3, 4, 10, 12 |
| `data/processed/aligned/india_vix_aligned.csv` | Phase 2 | CSV | 1,886 × 6 | Historical India VIX index levels. | Phases 3, 6, 7, 13 |
| `data/processed/normalized/robust/master_features_robust.csv`| Phase 5 | CSV | 1,687 × 28 | Scaled feature matrix fit strictly on training pool. | Phase 6 (HMM Training) |
| `results/regime_discovery/final_regime_labels.csv` | Phase 6 | CSV | 6,748 × 7 | Causal filtered and retrospective regime labels. | Phases 7, 8, 9, 10 |
| `results/regime_discovery/hmm_causal_probabilities.csv` | Phase 6 | CSV | 1,687 × 7 | Real-time filtered probabilities $\gamma_t(j)$ for all states. | Phase 8, 9 |
| `results/regime_characterization/regime_profiles/model_regime_profiles.csv`| Phase 7 | CSV | 28 × 29 | Empirical profiles across candidate model streams. | Phase 8, 13 |
| `results/portfolio_construction/target_weights_1A.csv` | Phase 9 | CSV | 1,687 × 7 | Daily target weights for Strategy 1A (Top-2 EW). | Phase 10 (Backtest) |
| `results/portfolio_backtest/daily_simulation_1A.parquet` | Phase 10 | Parquet | 1,686 × 70 | Primary daily simulation panel (NAV, turnover, returns). | Phases 10.3, 11, 12, 13 |
| `results/portfolio_backtest/metrics_summary.parquet` | Phase 10 | Parquet | 12 × 16 | Master performance summary table for all 4 variants. | Phases 10.3, 11, 13 |
| `results/portfolio_backtest/benchmark_metrics_summary.parquet`| Phase 10 | Parquet | 6 × 16 | Performance summary for NIFTY 50 and Equal-Weight. | Phases 10.3, 13 |
| `results/statistical_validation/regime_duration_diagnostics.parquet`| Phase 11 | Parquet | 7 × 12 | Nonparametric duration medians, means, IQRs (62 eps).| Phase 13 |
| `results/statistical_validation/hac_alpha_beta_summary.parquet`| Phase 11 | Parquet | 4 × 12 | Newey-West HAC CAPM regressions and p-values. | Phase 11 Report, 13 |
| `results/event_analysis/macro_episodes_summary.parquet` | Phase 12 | Parquet | 68 × 27 | Multi-session macro episodes and strategy drawdowns. | Phase 13 |
| `results/event_analysis/event_study_panel.parquet` | Phase 12 | Parquet | 1,340 × 11 | Daily abnormal returns panel for 122 events $[-5, +5]$. | Phase 12 Report |
| `results/event_analysis/macro_category_caar.parquet` | Phase 12 | Parquet | 42 × 12 | Bootstrapped CAAR significance by macro category. | Phase 12 Report |

---

## 6. Authoritative Research Findings Inventory

All numerical figures below have been independently verified against the canonical underlying Parquets and CSVs:

### 6.1 The Six Discovered Regimes (HMM Ground Truth)

| Regime ID | Economic Designation | Total Sessions | Allocation Share (%) | NIFTY Ann. Velocity (Mean $\times$ 252) | Raw Cumulative Episode Return | Realized Volatility (%) | Sharpe Ratio (Rf=5%) | Median India VIX | Mean India VIX | Median Duration |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Regime 0** | Cyclical Reflation Rally | 252 | 14.95% | **+46.91%** | +46.85% (across 5 eps) | 16.87% | **+2.48** | **20.81** | 20.93 | 16.0 days |
| **Regime 1** | High-Vol Relief Bounce | 40 | 2.37% | **+68.11%** | **+10.71% (40 days)** | 28.29% | **+2.23** | **32.98** | 34.32 | 40.0 days |
| **Regime 2** | Low-Vol Consolidation | 515 | 30.55% | **-1.78%** | -3.61% (across 22 eps)| 11.52% | -0.59 | **13.62** | 13.65 | 19.0 days |
| **Regime 3** | Acute Liquidation Crash | 27 | 1.60% | **-78.04%** | **-10.94% (27 days)** | 77.92% | **-1.07** | **55.30** | 57.74 | 27.0 days |
| **Regime 4** | Steady Bull Expansion | 522 | 30.96% | **+19.17%** | +39.73% (across 22 eps)| 10.32% | **+1.37** | **13.05** | 13.69 | 17.5 days |
| **Regime 5** | Risk-Off Correction | 330 | 19.57% | **-5.53%** | -7.21% (across 11 eps)| 20.76% | -0.51 | **19.44** | 19.70 | 19.0 days |
| **Overall** | Full Combined Sample | 1,686 | 100.0% | +10.89% | +95.14% | 19.35% | +0.30 | 14.85 | 16.65 | 18.5 days |

### 6.2 Sector Leadership & Asymmetry Matrix (Annualized Velocity $\bar{r} \times 252$, %)

| Regime | NIFTY AUTO | NIFTY BANK | NIFTY FMCG | NIFTY IT | NIFTY METAL | NIFTY PHARMA | NIFTY 50 | Selected Top-2 Sectors |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **R0: Reflation** | +51.39% | +58.94% | +18.40% | **+82.12%** | **+80.75%** | +22.10% | +46.91% | **IT & METAL** |
| **R1: Bounce** | **+138.39%** | +54.62% | +3.56% | +64.70% | **+128.66%** | +55.54% | +68.11% | **AUTO & METAL** |
| **R2: Consolidation** | -3.34% | -5.80% | -4.63% | **+12.78%** | -9.06% | **+2.98%** | -1.78% | **IT & PHARMA** |
| **R3: Liquidation** | -136.88% | **-202.86%** | **+44.93%** | -77.70% | -118.97% | **+214.28%** | -78.04% | **PHARMA & FMCG** |
| **R4: Expansion** | **+35.03%** | +26.82% | +9.93% | -2.37% | **+51.88%** | +25.01% | +19.17% | **METAL & AUTO** |
| **R5: Correction** | +7.61% | -6.16% | **+6.21%** | -18.68% | +12.83% | **+16.84%** | -5.53% | **PHARMA & FMCG** |

### 6.3 Frozen Portfolio Performance: Training vs. Holdout

| Strategy / Benchmark | Training CAGR (Net %) | Training Volatility (%) | Training Sharpe | Holdout CAGR (Net %) | Holdout Volatility (%) | Holdout Sharpe | Full Sample CAGR (Net %) | Full Sample Sharpe | Max Drawdown (%) | Annualized Turnover (x) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Strategy 1A (Primary)** | **+43.32%** | 20.44% | **1.86** | **-11.87%** | 15.43% | **-0.74** | **+26.89%** | **1.33** | -25.60% | 7.56x |
| **Strategy 1B (Inv-Vol)** | +43.05% | 20.09% | 1.88 | -12.16% | 15.12% | -0.78 | +26.61% | 1.34 | -24.89% | 7.64x |
| **Strategy 2A (Cash Floor)** | +39.70% | 18.22% | 1.93 | -12.95% | 14.71% | -0.87 | +24.10% | 1.33 | -21.68% | 8.89x |
| **Strategy 2B (Cash+InvVol)**| +39.14% | 17.81% | 1.95 | -13.20% | 14.41% | -0.91 | +23.64% | 1.33 | -21.43% | 8.94x |
| **NIFTY 50 Benchmark** | +14.71% | 18.99% | 0.82 | -0.76% | 13.23% | +0.01 | +10.63% | 0.66 | -38.44% | 0.00x |
| **Equal-Weight 6-Sector** | +21.51% | 18.07% | 1.17 | +3.27% | 13.58% | +0.31 | +16.67% | 0.99 | -34.82% | 0.20x |

### 6.4 Arithmetic Sector Attribution & Holdout Decay Root Causes

Portfolio return attribution follows the additive linear identity: $r_{\text{net}, t} \equiv \sum_{s=1}^6 c_{s, t} + c_{\text{cost}, t}$.

| Component | Training Arithmetic (pp/yr) | Holdout Arithmetic (pp/yr) | Shift / Decay (pp) | Forensic Economic Diagnosis |
|---|---:|---:|---:|---|
| **NIFTY AUTO** | +5.84 pp | -3.66 pp | -9.50 pp | Cyclical demand peak; financing rate headwinds. |
| **NIFTY BANK** | **0.00 pp** | **0.00 pp** | **0.00 pp** | **Opportunity Cost:** NIFTY BANK returned +7.36% in holdout; strategy had 0% allocation. |
| **NIFTY FMCG** | +1.65 pp | +1.56 pp | -0.09 pp | Resilient defensive cushion; preserved capital. |
| **NIFTY IT** | **+9.73 pp** | **-6.57 pp** | **-16.30 pp** | **Severe Drag:** US tech capex deceleration, tariff uncertainty. |
| **NIFTY METAL** | **+14.87 pp** | **-2.78 pp** | **-17.65 pp** | **Commodity Reversal:** Global manufacturing slowdown, tariff headwinds. |
| **NIFTY PHARMA** | +6.96 pp | +1.61 pp | -5.35 pp | Positive absolute contribution; generic pricing drag. |
| **Cost Drag** | -0.97 pp | -1.61 pp | -0.64 pp | **Turnover Surge:** Annualized turnover jumped from 6.49x to 10.75x (+65.6%). |
| **Arithmetic Net Total**| **+38.11 pp** | **-11.44 pp** | **-49.55 pp** | Reconciled against **Geometric CAGR Decay of -55.19 pp** (+43.32% to -11.87%). |

---

## 7. Technical Architecture Reconstruction

```
+-------------------------------------------------------------------------------------------------------------------------+
|                                    IMPLEMENTED RESEARCH SYSTEM ARCHITECTURE                                             |
+-------------------------------------------------------------------------------------------------------------------------+
|                                                                                                                         |
|  [RAW DATA LAYER]                                                                                                       |
|    - Yahoo Finance Ingestion (`src/data_loader.py`)                                                                     |
|    - Storage: `data/raw/market/` (NIFTY 50, India VIX), `data/raw/sector_indices/` (6 Sectors)                          |
|                                                                                                                         |
|  [PREPROCESSING & FEATURE PIPELINE]                                                                                     |
|    - Calendar Alignment & Cleaning (`src/data_cleaning.py` -> `data/processed/aligned/`, 1,886 sessions)               |
|    - Feature Generation (`src/feature_engineering.py` -> 20D/60D Momentum, 200D Trend, Sector RS, Sector Vol)          |
|    - Leakage-Proof Normalization (`src/normalization.py` -> RobustScaler fit strictly on Train Pool)                    |
|                                                                                                                         |
|  [MACHINE LEARNING INFERENCE ENGINE]                                                                                    |
|    - Model Selection (`src/regime_discovery.py` -> 150 CV Fits, Gaussian HMM K=6 selected)                             |
|    - Real-Time Forward Filtering -> `results/regime_discovery/hmm_causal_probabilities.csv`                            |
|    - Characterization & Profiling (`src/regime_characterisation.py` -> Duration diagnostics, Radar profiles)            |
|                                                                                                                         |
|  [PORTFOLIO DECISION & SIMULATION ENGINE]                                                                               |
|    - Systematic Rotation Rules (`src/regime_rotation_rules.py` -> Top-2 Sector Selector)                                |
|    - Target Weight Generation (`src/portfolio_construction.py` -> Schedules 1A, 1B, 2A, 2B)                            |
|    - Daily Vectorized Backtest (`src/portfolio_backtest.py` -> 15 bps slippage, turnover drag, cash rebalancing)        |
|                                                                                                                         |
|  [VALIDATION & VERIFICATION SUITE]                                                                                      |
|    - Econometric Inference (`src/statistical_validation.py` -> Politis-Romano Bootstrap, Ledoit-Wolf Sharpe, HAC)      |
|    - Event Study Engine (`src/event_analysis.py` -> Market Model CAR [-2, +2], CAAR Bootstrap, Drawdown Tracking)      |
|    - Automated Regression Suite (`tests/` -> 10 test modules, 177 unit & integration tests)                             |
|                                                                                                                         |
+-------------------------------------------------------------------------------------------------------------------------+
```

---

## 8. Future Production Deployment Boundary (Conceptual Architecture)

To maintain absolute scientific integrity, the historical research system implemented in Phases 1–13 is strictly separated from future production deployment:

```
+-------------------------------------------------------------------------------------------------------------------------+
|                                         FUTURE PRODUCTION DEPLOYMENT BOUNDARY                                           |
|                                         (Conceptual Architecture — Not in Scope for P14)                                |
+-------------------------------------------------------------------------------------------------------------------------+
|                                                                                                                         |
|   +---------------------------+        +---------------------------+        +----------------------------+              |
|   | External Market Data API  |        | Daily Scheduled Cron /    |        | Neon Serverless PostgreSQL |              |
|   | (NSE Bhavcopy / TrueData) | -----> | Serverless Ingestion Job  | -----> | - Aligned EOD Price Tables |              |
|   | - EOD OHLCV + India VIX   |        | (Vercel / Cloud Functions)|        | - Rolling Feature Vectors  |              |
|   +---------------------------+        +---------------------------+        +----------------------------+              |
|                                                      |                                     |                            |
|                                                      v                                     v                            |
|                                        +---------------------------+        +----------------------------+              |
|                                        | HMM Forward-Filter Worker |        | Web Application / UI       |              |
|                                        | - Loads frozen model      | -----> | (Next.js on Vercel)        |              |
|                                        | - Emits daily gamma_t     |        | - Interactive Dashboard    |              |
|                                        | - Outputs Top-2 weights   |        | - Strategy Allocation View |              |
|                                        +---------------------------+        +----------------------------+              |
|                                                                                                                         |
+-------------------------------------------------------------------------------------------------------------------------+
```

- **Boundary Enforcement:** Phase 14 will produce **only research documentation** (`final_project_research_report.pdf` and `final_project_architecture.pdf`). No web dashboard, database migrations, live API connectors, or serverless functions will be created in this phase.

---

## 9. Research Report Readiness Assessment (`final_project_research_report.pdf`)

| Report Section | Planned Content | Supporting Repository Artifacts | Readiness Status |
|---|---|---|:---:|
| 1. Abstract | Executive summary of regime discovery, 43.3% training CAGR, and holdout decay. | `metrics_summary.parquet`, Phase 13 report | **PASS** |
| 2. Introduction | Sector rotation theory, regime persistence, Indian market context. | Phase 13 Section 1, project proposals | **PASS** |
| 3. Problem Statement | Pitfalls of static allocation, lookahead bias in regime models. | `src/regime_discovery.py`, Phase 6 report | **PASS** |
| 4. Research Motivation | Systematic macro adaptation, unconstrained vs cash-protected variants. | `phase_8_2_sector_rotation_rules_proposal.md`| **PASS** |
| 5. Literature & Background | Hamilton (1989) HMMs, Ang & Bekaert (2002), Politis-Romano (1994). | Phase 11 & 13 formulation notes | **PASS** |
| 6. Data & Market Universe | 8 NSE indices, 1,886 sessions, data provenance, Yahoo Finance. | `data/processed/aligned/*.csv` | **PASS** |
| 7. Preprocessing & Alignment | Forward-fill, holiday reconciliation, zero-volume verification. | `src/data_cleaning.py`, `02_data_cleaning.ipynb`| **PASS** |
| 8. Feature Engineering | 20D/60D Momentum, 200D Trend, Sector Relative Strength, Volatility. | `data/processed/feature_engineered/*.csv` | **PASS** |
| 9. Normalization & Anti-Leakage| RobustScaler vs StandardScaler fit strictly on Training Pool. | `src/normalization.py`, `05_normalization.ipynb`| **PASS** |
| 10. Regime Discovery Architecture| Expanding-window CV, 150 HMM fits, $K=6$, diagonal covariance. | `results/phase6_model_selection/hmm/*.csv` | **PASS** |
| 11. Regime Characterization | Empirical profiles of 6 states, duration medians, occupancy. | `results/regime_characterization/*.csv` | **PASS** |
| 12. Sector Rotation Methodology| Top-2 selection logic, cyclical vs defensive state mapping. | `src/regime_rotation_rules.py` | **PASS** |
| 13. Portfolio Construction | Variants 1A, 1B, 2A, 2B, Target Weight Schedules, cash rules. | `results/portfolio_construction/*.csv` | **PASS** |
| 14. Backtesting Engine | Vectorized simulation, 1,686 sessions, 15 bps slippage modeling. | `results/portfolio_backtest/*.parquet` | **PASS** |
| 15. Statistical Validation | Stationary bootstrap ($B=2,000$), Ledoit-Wolf Sharpe, HAC alpha. | `results/statistical_validation/*.parquet` | **PASS** |
| 16. Event-Based Market Analysis| 122 events, 68 episodes, CAR $[-2, +2]$, bootstrapped CAAR. | `results/event_analysis/*.parquet` | **PASS** |
| 17. Economic Interpretation | Economic business cycle mapping, crisis progression (COVID-19). | `reports/phase13_regime_interpretation.md` | **PASS** |
| 18. Holdout Forensic Diagnosis | CAGR decay (-55.19 pp), arithmetic decay (-49.55 pp), Bank omission. | `results/portfolio_backtest/daily_simulation_1A.parquet`| **PASS** |
| 19. Limitations & Failure Modes| Single-episode regimes (R1/R3), turnover friction, correlation shifts.| Phase 13 Section 8, Phase 10.6 audit | **PASS** |
| 20. Conclusion & Future Work | Summary of findings, dynamic rebalancing heuristics, next steps. | Phase 13 Section 9 | **PASS** |

---

## 10. Architecture Document Readiness Assessment (`final_project_architecture.pdf`)

| Architectural Component | Planned Content | Supporting Repository Evidence | Readiness Status |
|---|---|---|:---:|
| 1. High-Level System Architecture | Complete layered diagram (Data -> Features -> Model -> Allocation -> Sim).| Implemented modules in `src/` | **PASS** |
| 2. End-to-End Pipeline Workflow | Sequential phase progression from Phase 1 to Phase 13. | 16 sequential notebooks | **PASS** |
| 3. Data Ingestion & Storage Graph | Raw, cleaned, aligned, engineered, normalized dataset schemas. | 35 Parquet/CSV files in `data/` | **PASS** |
| 4. Feature & Scaling Architecture | Window formulas, rolling lookbacks, RobustScaler parameter storage. | `src/feature_engineering.py`, `normalization.py`| **PASS** |
| 5. Machine Learning Inference Graph | Baum-Welch training, forward-filter recurrence equation, Viterbi. | `src/regime_discovery.py` | **PASS** |
| 6. Decision & Portfolio Allocation | Signal generation, Top-2 ranker, cash floor rule overlay. | `src/regime_rotation_rules.py`, `portfolio_construction.py`| **PASS** |
| 7. Execution & Simulation Engine | Daily rebalancing mechanics, turnover computation, friction modeling. | `src/portfolio_backtest.py` | **PASS** |
| 8. Validation & Econometric Engine | Stationary bootstrap pipeline, Newey-West HAC regression engine. | `src/statistical_validation.py` | **PASS** |
| 9. Event-Study Analytical Engine | Event window alignment, market model estimation, CAAR inference. | `src/event_analysis.py` | **PASS** |
| 10. Module & Class Responsibility Map| Detailed interface documentation for all 17 Python modules. | Code inspection of all `src/` files | **PASS** |
| 11. Dataset Dependency DAG | Directed Acyclic Graph mapping file inputs and outputs across phases. | Traced in Section 5 of this audit | **PASS** |
| 12. Production Boundary Specification| Conceptual architecture for Next.js, Vercel, Neon DB, and live cron. | Formulated in Section 8 of this audit | **PASS** |

---

## 11. Audit Discrepancies, Ambiguities & Resolutions

1. **Session Count Reconciliation (RESOLVED):**
   - Feature/label space ($N=1,687$, starting on feature date `2019-10-31`) vs. Portfolio simulation space ($N=1,686$, starting on first return date `2019-11-01`). Both documents will explicitly disclose this distinction to eliminate reader confusion.
2. **India VIX Median vs. Mean Synchronization (RESOLVED):**
   - The minor labeling defect in Phase 13 Table 1 was corrected on disk. The authoritative median values (`R0: 20.81, R1: 32.98, R2: 13.62, R3: 55.30, R4: 13.05, R5: 19.44`) and arithmetic means (`R0: 20.93, R1: 34.32, R2: 13.65, R3: 57.74, R4: 13.69, R5: 19.70`) are fully synchronized across `reports/phase13_regime_interpretation.md` and `.pdf`.
3. **Metric Terminology Delineation (RESOLVED):**
   - All final reports will strictly distinguish:
     - Geometric CAGR Net (+43.32% Train vs. -11.87% Holdout; -55.19 pp decay).
     - Arithmetic Net Return Attribution (+38.11% Train vs. -11.44% Holdout; -49.55 pp decay).
     - Daily Annualized Return Velocity ($\bar{r} \times 252$, e.g. R3 Bank -202.86%, Pharma +214.28%).
     - Raw Cumulative Episode Returns (e.g. R3 Bank -23.48%, Pharma +23.16%, NIFTY 50 -10.94% over 27 sessions).

---

## 12. Final Readiness Verdict

Based on an exhaustive, read-only inspection of all 233 repository files, 17 Python source modules, 16 notebooks, 113 datasets, 31 visual artifacts, and the 177-test automated regression suite:

### **1. Complete Research Report PDF: READY — PROCEED TO IMPLEMENTATION**
All 20 planned sections are backed by verified empirical datasets, mathematical formulations, and completed research findings. No missing data or unverified claims exist.

### **2. Complete Project Architecture PDF: READY — PROCEED TO IMPLEMENTATION**
The complete software execution graph, data pipeline, module interfaces, dataset DAG, and conceptual production boundary are mapped from empirical code.

### **OVERALL VERDICT: READY — BOTH DOCUMENTS CAN BE CREATED**

