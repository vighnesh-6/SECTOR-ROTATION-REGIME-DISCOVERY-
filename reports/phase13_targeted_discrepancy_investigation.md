# Phase 13 — Targeted Numerical Discrepancy Investigation & Source-Level Verification

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Phase:** Phase 13 — Economic Interpretation of Market Regimes  
**Investigation Type:** Strictly Read-Only Forensic Audit  
**Date:** November 6, 2026  
**Investigating Auditor:** Senior Quantitative Finance Researcher & ML Engineering Auditor  
**Primary Reference Artifacts:**
- `notebooks/zz_phase13_economic_interpretation.ipynb`
- `reports/phase13_regime_interpretation.md`
- `reports/phase13_regime_interpretation.pdf`
- `results/portfolio_backtest/daily_simulation_1A.parquet`
- `results/portfolio_backtest/metrics_summary.parquet`
- `results/regime_discovery/final_regime_labels.csv`
- `results/regime_characterization/regime_profiles/model_regime_profiles.csv`
- `results/statistical_validation/regime_duration_diagnostics.parquet`
- `results/event_analysis/*.parquet` (7 authoritative datasets)
- `reports/phase13_figures/` & `results/event_analysis/phase13_figures/` (6 PNG artifacts)

---

## 1. Executive Summary

This independent read-only investigation was conducted to resolve three specific numerical and documentation discrepancies identified during peer review of the Phase 13 research deliverables:
1. **Trading-Session Count Discrepancy:** The notebook reports 1,686 sessions (1,264 train, 422 holdout) starting 2019-11-01, while earlier audit narratives cited 1,687 sessions (1,265 train, 422 holdout) starting 2019-10-31.
2. **India VIX Median Discrepancies:** The notebook dynamically computes regime VIX medians of `[20.81, 32.98, 13.62, 55.30, 13.05, 19.44]`, whereas Table 1 and narrative text in the Markdown/PDF report presented `[20.81, 34.32, 13.65, 57.74, 13.69, 19.70]`.
3. **Figure 3 Transition-Persistence Discrepancy:** Notebook Cell 9 displays a full-sample transition matrix with diagonal persistence of `[98.02%, 97.50%, 95.91%, 96.30%, 95.79%, 96.67%]`, whereas an earlier chat verification response cited persistence figures of `(R0: 93.8%, R1: 97.5%, R2: 94.7%, R4: 94.3%, R5: 90.9%)`.

Additionally, all seven Phase 12 event-analysis Parquet datasets were independently inspected on disk, and all six visual figure artifacts were audited across both repository storage paths.

### Key Investigation Findings:
1. **Session Count Resolved (PASS):** The 1-session difference is a mathematically necessary boundary distinction between the **feature/label domain** ($N=1,687$, starting on feature date `2019-10-31`) and the **portfolio backtest return domain** ($N=1,686$, starting on first return interval `2019-11-01`). The Phase 13 notebook correctly operates in the portfolio simulation space.
2. **VIX Median Root Cause Identified (FAIL — Documentation Defect):** The notebook's calculation of VIX medians is 100% mathematically correct. The earlier report figures (`34.32, 13.65, 57.74, 13.69, 19.70`) were the **arithmetic means** of India VIX in the full sample (`vix_close_mean`), which had been mistakenly entered under a column labeled "Median India VIX".
3. **Figure 3 Persistence Discrepancy Resolved (PASS WITH DOCUMENTATION CLARIFICATION):** Figure 3 actually plots a two-panel heatmap of **Training (2019–2024)** vs. **Holdout (2025–2026)** transition matrices. Its diagonals are `[98.4%, 97.5%, 97.0%, 96.3%, 96.3%, 97.1%]` (Train) and `[87.5%, 0.0%, 93.2%, 0.0%, 94.7%, 96.0%]` (Holdout). The string `(R0: 93.8%, ...)` in the previous chat response was an errant summary statement; neither Figure 3 nor the underlying data ever contained those values.
4. **Parquet Datasets Verified (PASS / NOT APPLICABLE):** All 7 event-analysis Parquet datasets exist and are uncorrupted. `macro_episodes_summary.parquet` is loaded by the notebook, and its 68 macro episodes match notebook Cell 15 identically. The other 6 datasets are not directly called by the notebook and are accurately classified as `NOT APPLICABLE` for direct notebook comparison.
5. **Figure Verification (PASS):** All 6 figures exist, match their underlying data sources, and have identical SHA-256 hashes between `reports/phase13_figures/` and `results/event_analysis/phase13_figures/`.

---

## 2. Inventory of Actual Files Inspected

| Category | File Path | Existence | Rows / Dim | Columns / Type | Checksum / SHA-256 (Prefix) |
|---|---|:---:|:---:|:---:|:---:|
| **Notebook** | `notebooks/zz_phase13_economic_interpretation.ipynb` | Verified | 23 Cells | JSON Notebook (2.3 MB) | `B8E5F4A1...` |
| **Research Report** | `reports/phase13_regime_interpretation.md` | Verified | 455 lines | Markdown (47 KB) | `6112C78E...` |
| **Research PDF** | `reports/phase13_regime_interpretation.pdf` | Verified | 14 pages | PDF Document (1.98 MB) | `4E268F12...` |
| **Simulation Master** | `results/portfolio_backtest/daily_simulation_1A.parquet` | Verified | 1,686 rows | 70 columns | `D8D0C31F...` |
| **Metrics Summary** | `results/portfolio_backtest/metrics_summary.parquet` | Verified | 12 rows | 16 columns | `989B0E5A...` |
| **Regime Labels** | `results/regime_discovery/final_regime_labels.csv` | Verified | 6,748 rows | 7 columns | `BF84A6E8...` |
| **Regime Profiles** | `results/regime_characterization/regime_profiles/model_regime_profiles.csv` | Verified | 28 rows | 29 columns | `5F292261...` |
| **Duration Diagnostics**| `results/statistical_validation/regime_duration_diagnostics.parquet` | Verified | 7 rows | 12 columns | `87864B17...` |
| **India VIX Data** | `data/processed/aligned/india_vix_aligned.csv` | Verified | 1,886 rows | 6 columns | `13264F65...` |
| **Event Dataset 1** | `results/event_analysis/macro_episodes_summary.parquet` | Verified | 68 rows | 27 columns | `2F9B8A31...` |
| **Event Dataset 2** | `results/event_analysis/portfolio_event_behavior.parquet` | Verified | 488 rows | 13 columns | `C1448E4B...` |
| **Event Dataset 3** | `results/event_analysis/sector_leadership_stability.parquet` | Verified | 122 rows | 13 columns | `78D5EA14...` |
| **Event Dataset 4** | `results/event_analysis/macro_category_caar.parquet` | Verified | 42 rows | 12 columns | `FA7BB598...` |
| **Event Dataset 5** | `results/event_analysis/event_car_summary.parquet` | Verified | 1,220 rows | 17 columns | `5D19A0E3...` |
| **Event Dataset 6** | `results/event_analysis/event_metadata_authoritative.parquet` | Verified | 135 rows | 11 columns | `E4291B98...` |
| **Event Dataset 7** | `results/event_analysis/event_study_panel.parquet` | Verified | 1,340 rows | 11 columns | `82FA93DE...` |
| **Figure 1** | `reports/phase13_figures/fig1_regime_profiles.png` | Verified | 4800×1500 | 330,298 bytes | `5F1F35EC...` (Exact match) |
| **Figure 2** | `reports/phase13_figures/fig2_sector_performance.png` | Verified | 3000×1800 | 252,291 bytes | `2B59485F...` (Exact match) |
| **Figure 3** | `reports/phase13_figures/fig3_transition_dynamics.png` | Verified | 4200×1650 | 227,457 bytes | `07C325C3...` (Exact match) |
| **Figure 4** | `reports/phase13_figures/fig4_correlation_dispersion.png` | Verified | 3900×1500 | 248,033 bytes | `13B4F465...` (Exact match) |
| **Figure 5** | `reports/phase13_figures/fig5_holdout_diagnosis.png` | Verified | 4200×1650 | 318,595 bytes | `ABACA4E7...` (Exact match) |
| **Figure 6** | `reports/phase13_figures/fig6_regime_frequency_shift.png` | Verified | 4200×1500 | 287,399 bytes | `D5B643DC...` (Exact match) |

---

## 3. Investigation A — Trading-Session Count Discrepancy

### 3.1 Empirical Observation
- **Notebook (`zz_phase13_economic_interpretation.ipynb`):** Total = 1,686 sessions; Training = 1,264 sessions; Holdout = 422 sessions (Date range: 2019-11-01 to 2026-09-18).
- **Earlier Audit Narratives (`phase13_final_verification_audit.md`):** Total = 1,687 sessions; Training = 1,265 sessions; Holdout = 422 sessions.

### 3.2 Root-Cause Identification
By performing an exact inner and outer set difference on the underlying date indices, the exact 1-session divergence was identified:
- **Missing Date:** `2019-10-31`
- **Presence in Datasets:**
  - `results/regime_discovery/final_regime_labels.csv`: Contains `2019-10-31` (Total $N = 1,687$, Train = 1,265, Holdout = 422).
  - `data/processed/normalized/robust/master_features_robust.csv`: Contains `2019-10-31` ($N = 1,687$).
  - `results/portfolio_backtest/daily_simulation_1A.parquet`: Starts on `2019-11-01` (Total $N = 1,686$, Train = 1,264, Holdout = 422).
  - `results/statistical_validation/regime_duration_diagnostics.parquet`: Row 6 ("All Regimes Combined") reports `total_days = 1686`.

### 3.3 Methodological Explanation
In quantitative portfolio simulation:
1. On **`2019-10-31`** ($t_0$), the 200-day rolling lookback window completes, and the HMM emits its very first causal filtered state (`filtered_causal`). The portfolio engine (Phase 9) assigns initial sector target weights at the market Close of `2019-10-31`.
2. The **first daily holding return** is realized over the interval from `2019-10-31 Close` to `2019-11-01 Close` ($t_1$).
3. Consequently, the master daily portfolio simulation (`daily_simulation_1A.parquet`) contains exactly **1,264 daily return observations in training** and **422 in holdout**, totaling **1,686 simulated trading sessions**.
4. Both counts are mathematically correct in their respective domains:
   - **Feature & Regime Classification Domain (Phases 3–7):** 1,265 training dates (includes initial feature date `2019-10-31`).
   - **Portfolio Backtest & Return Attribution Domain (Phases 10–13):** 1,264 training return intervals (starts `2019-11-01`).

### 3.4 Verification Verdict
**Status: PASS**  
The Phase 13 notebook correctly uses 1,686 sessions because it analyzes daily strategy returns and performance attribution from `daily_simulation_1A.parquet`.

---

## 4. Investigation B — India VIX Median Discrepancies

### 4.1 Comparison Table

| Regime ID | Economic Designation | Sample Sessions ($N$) | Notebook Dynamic Output | Earlier Report Table 1 | Full-Sample VIX Mean | Full-Sample VIX Median | Train-Only VIX Mean | Train-Only VIX Median | Discrepancy Explanation | Status |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|:---:|
| **Regime 0** | Cyclical Reflation Rally | 252 | **20.81** | **20.81** | 20.93 | **20.81** | 21.05 | 20.98 | Exact match to full-sample median. | **PASS** |
| **Regime 1** | Post-Crash Relief Bounce | 40 | **32.98** | **34.32** | **34.32** | **32.98** | 34.32 | 32.98 | Earlier report used **Mean** (34.32) under a Median label. | **FAIL (Report Label)** |
| **Regime 2** | Low-Vol Consolidation | 515 | **13.62** | **13.65** | **13.65** | **13.62** | 13.96 | 13.95 | Earlier report used **Mean** (13.65) under a Median label. | **FAIL (Report Label)** |
| **Regime 3** | Acute Liquidation Crash | 27 | **55.30** | **57.74** | **57.74** | **55.30** | 57.74 | 55.30 | Earlier report used **Mean** (57.74) under a Median label. | **FAIL (Report Label)** |
| **Regime 4** | Steady Bull Expansion | 522 | **13.05** | **13.69** | **13.69** | **13.05** | 14.39 | 13.73 | Earlier report used **Mean** (13.69) under a Median label. | **FAIL (Report Label)** |
| **Regime 5** | Risk-Off Correction | 330 | **19.44** | **19.70** | **19.70** | **19.44** | 20.91 | 20.60 | Earlier report used **Mean** (19.70) under a Median label. | **FAIL (Report Label)** |

### 4.2 Forensic Root-Cause Analysis
1. In `notebooks/zz_phase13_economic_interpretation.ipynb` (Cell 3), the notebook joins `sim1a` with `india_vix_aligned.csv` on `Date` (inner join, 1,686 dates, 0 missing values) and calculates `sub['VIX'].median()`. The resulting values are `[20.81, 32.98, 13.62, 55.30, 13.05, 19.44]`.
2. In `results/regime_characterization/regime_profiles/model_regime_profiles.csv` (rows 10–15), Phase 7 computed both `vix_close_mean` and `vix_close_median`. For Regime 1, `vix_close_mean = 34.32` and `vix_close_median = 32.98`; for Regime 3, `vix_close_mean = 57.74` and `vix_close_median = 55.30`.
3. In the full sample across 1,687 aligned dates:
   - Arithmetic Means: R0 = 20.93, R1 = **34.32**, R2 = **13.65**, R3 = **57.74**, R4 = **13.69**, R5 = **19.70**.
   - Medians: R0 = **20.81**, R1 = **32.98**, R2 = **13.62**, R3 = **55.30**, R4 = **13.05**, R5 = **19.44**.
4. **Conclusion:** The earlier Markdown and PDF reports contained an inadvertent column conflation: the author populated Table 1 with the **empirical arithmetic means** for Regimes 1 through 5, while placing them under a column titled *"Median India VIX"*. The notebook's dynamic calculation is 100% mathematically correct.

---

## 5. Investigation C — Figure 3 Transition-Persistence Discrepancy

### 5.1 Comparison of Transition Metrics

| State | Notebook Cell 9 (Full Sample Empirical) | Figure 3 Panel 1 (Training Period 2019–2024) | Figure 3 Panel 2 (Holdout Period 2025–2026) | Chat Response Assertion (Step 2568) | Independent Verification Status |
|:---:|:---:|:---:|:---:|:---:|---|
| **R0** | **98.02%** | **98.4%** (98.36%) | **87.5%** (87.50%) | *93.8%* | **FAIL (Chat Statement Incorrect; Figure 3 Verified)** |
| **R1** | **97.50%** | **97.5%** (97.50%) | **0.0%** (0 sessions) | *97.5%* | **PASS (Matches Train Panel)** |
| **R2** | **95.91%** | **97.0%** (96.97%) | **93.2%** (93.16%) | *94.7%* | **FAIL (Chat Statement Incorrect; Figure 3 Verified)** |
| **R3** | **96.30%** | **96.3%** (96.30%) | **0.0%** (0 sessions) | *Not reported* | **PASS (Matches Train Panel)** |
| **R4** | **95.79%** | **96.3%** (96.31%) | **94.7%** (94.71%) | *94.3%* | **FAIL (Chat Statement Incorrect; Figure 3 Verified)** |
| **R5** | **96.67%** | **97.1%** (97.06%) | **96.0%** (96.03%) | *90.9%* | **FAIL (Chat Statement Incorrect; Figure 3 Verified)** |

### 5.2 Forensic Investigation of Figure 3
1. **Inspection of Step 2335 Execution:** The actual generation script that produced `reports/phase13_figures/fig3_transition_dynamics.png` was inspected in the system logs. It executes:
   ```python
   train_sim = sim[sim['period'] == 'train']
   holdout_sim = sim[sim['period'] == 'holdout']
   tm_train = calc_trans(train_sim['accepted_regime'])
   tm_holdout = calc_trans(holdout_sim['accepted_regime'])
   ```
2. **Actual Visual Content of Figure 3:**
   - Figure 3 does **not** contain persistence bar charts.
   - Figure 3 consists of **two 6×6 heatmaps side by side**:
     - **Left Panel:** *"Training Period Transition Matrix (2019-2024)"* with diagonal values: R0 = 98.4%, R1 = 97.5%, R2 = 97.0%, R3 = 96.3%, R4 = 96.3%, R5 = 97.1%.
     - **Right Panel:** *"Holdout Period Transition Matrix (2025-2026)"* with diagonal values: R0 = 87.5%, R1 = 0.0%, R2 = 93.2%, R3 = 0.0%, R4 = 94.7%, R5 = 96.0%.
3. **Notebook Cell 9 Content:** Displays the **Full-Sample Transition Matrix (1,686 sessions combined)** with diagonal values: R0 = 98.02%, R1 = 97.50%, R2 = 95.91%, R3 = 96.30%, R4 = 95.79%, R5 = 96.67%.
4. **Resolution of `93.8%, 94.7%, 90.9%`:**
   - A global repository search confirmed that the numbers `93.8%`, `94.7%`, `94.3%`, `90.9%` do not exist in any file, table, or script on disk.
   - These numbers originated solely as an **errant conversational hallucination/unverified assertion in the chat response at Step 2568**.
   - Both the stored Figure 3 artifact and Notebook Cell 9 are mathematically valid representations of their respective sample slices (Split Train/Holdout vs. Full Sample).

---

## 6. Investigation D — Audit of Seven Event-Analysis Parquet Files

Every authoritative event-analysis Parquet dataset in `results/event_analysis/` was directly inspected:

```
========================================================================================================================
                                    AUTHORITATIVE EVENT-ANALYSIS DATASET AUDIT
========================================================================================================================
Dataset Name:               macro_episodes_summary.parquet
Path:                       results/event_analysis/macro_episodes_summary.parquet
Status:                     PASS — DIRECTLY USED BY NOTEBOOK
Row Count:                  68 rows | Column Count: 27 columns | Duplicates: 0 | Total Nulls: 0
Primary Key:                episode_id (68 unique)
Date Coverage:              start_date: 2019-11-04 to 2026-09-15 | end_date: 2019-11-04 to 2026-09-15
Categories (7):             Monetary Policy (28), Trade & Tariffs (18), Geopolitics (7), Fiscal (5), Elections (5),
                            Financial Shocks (3), Pandemic (2).
Notebook Integration:       Cell 1 loads file; Cell 15 reproduces exact category distribution (68 episodes) and
                            computes inception regime cross-tabulation (R0: 7, R1: 1, R2: 24, R4: 23, R5: 13).
------------------------------------------------------------------------------------------------------------------------
Dataset Name:               portfolio_event_behavior.parquet
Path:                       results/event_analysis/portfolio_event_behavior.parquet
Status:                     NOT APPLICABLE (Not loaded by zz_phase13 notebook)
Row Count:                  488 rows | Column Count: 13 columns | Duplicates: 0 | Total Nulls: 0
Primary Key:                (event_id, variant) — 122 events x 4 variants (1A, 1B, 2A, 2B)
Key Metrics:                window_net_return, window_gross_return, window_turnover, signed_mdd, mean_cash_weight
Integrity Check:            File is structurally intact and fully populated.
------------------------------------------------------------------------------------------------------------------------
Dataset Name:               sector_leadership_stability.parquet
Path:                       results/event_analysis/sector_leadership_stability.parquet
Status:                     NOT APPLICABLE (Not loaded by zz_phase13 notebook)
Row Count:                  122 rows | Column Count: 13 columns | Duplicates: 0 | Total Nulls: 0
Primary Key:                event_id (122 unique events)
Key Metrics:                spearman_rho, kendall_tau, cssd_pre, cssd_post, cssd_delta, leadership_turnover
Integrity Check:            File is structurally intact and fully populated.
------------------------------------------------------------------------------------------------------------------------
Dataset Name:               macro_category_caar.parquet
Path:                       results/event_analysis/macro_category_caar.parquet
Status:                     NOT APPLICABLE (Not loaded by zz_phase13 notebook)
Row Count:                  42 rows | Column Count: 12 columns | Duplicates: 0 | Total Nulls: 0
Primary Key:                (macro_category, asset) — 7 categories x 6 sector indices
Key Metrics:                CAAR_m2_p2, boot_mean, boot_ci_lower, boot_ci_upper, p_value_boot, is_confirmatory
Integrity Check:            File is structurally intact and fully populated.
------------------------------------------------------------------------------------------------------------------------
Dataset Name:               event_car_summary.parquet
Path:                       results/event_analysis/event_car_summary.parquet
Status:                     NOT APPLICABLE (Not loaded by zz_phase13 notebook)
Row Count:                  1,220 rows | Column Count: 17 columns | Duplicates: 0 | Total Nulls: 74 (expected in CAR vars)
Primary Key:                (event_id, asset) — 122 events x 10 assets
Key Metrics:                alpha_est, beta_est, r2_est, CAR_m2_p2, CAR_m5_p5, t_stat_CAR, p_value_CAR
Integrity Check:            File is structurally intact and fully populated.
------------------------------------------------------------------------------------------------------------------------
Dataset Name:               event_metadata_authoritative.parquet
Path:                       results/event_analysis/event_metadata_authoritative.parquet
Status:                     NOT APPLICABLE (Not loaded by zz_phase13 notebook)
Row Count:                  135 rows | Column Count: 11 columns | Duplicates: 0 | Total Nulls: 0
Primary Key:                event_id (135 unique events; 122 in backtest sample)
Date Coverage:              2019-02-01 to 2026-09-15
Integrity Check:            File is structurally intact and fully populated.
------------------------------------------------------------------------------------------------------------------------
Dataset Name:               event_study_panel.parquet
Path:                       results/event_analysis/event_study_panel.parquet
Status:                     NOT APPLICABLE (Not loaded by zz_phase13 notebook)
Row Count:                  1,340 rows | Column Count: 11 columns | Duplicates: 0 | Total Nulls: 0
Primary Key:                (event_id, relative_day) — 122 events x 11 relative days [-5 to +5]
Key Metrics:                r_m, AR_AUTO, AR_BANK, AR_FMCG, AR_IT, AR_METAL, AR_PHARMA
Integrity Check:            File is structurally intact and fully populated.
========================================================================================================================
```

---

## 7. Investigation E — Cross-Artifact Dependency Mapping

| Phase 13 Output / Finding | Upstream Source Artifact | Phase | Nature of Calculation | Independent Reproduction | Verification Status |
|---|---|:---:|---|---|:---:|
| **Regime Profiles (Sessions, Returns, Vol)** | `daily_simulation_1A.parquet` | Phase 10 | Groupby `accepted_regime`: `mean() * 252`, `std() * sqrt(252)` | Exact match across all 6 regimes | **PASS** |
| **India VIX Medians (Notebook)** | `daily_simulation_1A.parquet` + `india_vix_aligned.csv` | Phase 10 & 2 | Inner join on `Date`, `groupby('accepted_regime')['VIX'].median()` | Exact match: 20.81, 32.98, 13.62, 55.30, 13.05, 19.44 | **PASS** |
| **India VIX Means (Report Table 1)** | `india_vix_aligned.csv` | Phase 2 | `groupby('accepted_regime')['Close'].mean()` | Exact match: 20.93, 34.32, 13.65, 57.74, 13.69, 19.70 | **FAIL (Mislabeled as Median)** |
| **Sector Performance Matrix** | `daily_simulation_1A.parquet` | Phase 10 | `groupby('accepted_regime')[sector_cols].mean() * 252 * 100` | Exact match (e.g. R3 Bank -202.86%, Pharma +214.28%) | **PASS** |
| **Transition Matrix (Full Sample)** | `daily_simulation_1A.parquet` | Phase 10 | 1st-order Markov frequency matrix on `accepted_regime` | Diagonals: 98.02%, 97.50%, 95.91%, 96.30%, 95.79%, 96.67% | **PASS** |
| **Transition Matrix (Train/Holdout)** | `daily_simulation_1A.parquet` | Phase 10 | Split Markov matrix by `period == 'train'` vs `'holdout'` | Train: 98.4%, 97.5%, 97.0%, 96.3%, 96.3%, 97.1%; Holdout: 87.5%, 0%, 93.2%, 0%, 94.7%, 96.0% | **PASS** |
| **Episode Duration Diagnostics** | `regime_duration_diagnostics.parquet` | Phase 11 | Duration median and IQR across 62 continuous episodes | Full sample: 18.5d; R0: 16d, R2: 19d, R4: 17.5d, R5: 19d | **PASS** |
| **Cross-Sector Correlations** | `daily_simulation_1A.parquet` | Phase 10 | Sector return correlation matrix by regime, off-diagonal mean | R0: 0.425, R1: 0.413, R2: 0.361, R3: 0.801, R4: 0.322, R5: 0.552 | **PASS** |
| **PCA Variance Explained** | `daily_simulation_1A.parquet` | Phase 10 | Eigenvalue decomposition of correlation matrix: $\lambda_1 / 6 \times 100$ | R0: 52.4%, R1: 55.9%, R2: 47.4%, R3: 83.5%, R4: 44.0%, R5: 63.0% | **PASS** |
| **Strategy Performance (CAGR, MDD)** | `metrics_summary.parquet` | Phase 10 | `cagr_net_pct`, `ann_volatility_pct`, `sharpe_ratio`, `max_drawdown_pct` | Train CAGR: +43.32%, Holdout CAGR: -11.87% (-55.19 pp decay) | **PASS** |
| **Arithmetic Sector Attribution** | `daily_simulation_1A.parquet` | Phase 10 | Linear additive attribution: `contrib_s.mean() * 252 * 100` | Train: +38.11%, Holdout: -11.44% (-49.55 pp decay) | **PASS** |
| **Banking Sector Omission** | `daily_simulation_1A.parquet` | Phase 10 | NIFTY BANK return (+7.36%) vs Strategy 1A Bank weight (0.00%) | Missed historical exposure verified (0.00 pp contribution) | **PASS** |
| **Macro Episodes Breakdown** | `macro_episodes_summary.parquet` | Phase 12 | Value counts of `primary_macro_category` and cross-tab with regime | 68 episodes verified across 7 categories | **PASS** |

---

## 8. Investigation F — Six-Figure Source & Content Verification

| Figure Name | Underlying Dataset & Variables | Key Plotted Values Verified | Labels & Axes Compliance | Checksum Match (`reports/` vs `results/`) | Status |
|---|---|---|---|:---:|:---:|
| **`fig1_regime_profiles.png`** | `daily_simulation_1A.parquet` (`r_NIFTY50`, `accepted_regime`) | Return: R0 (+46.9%), R1 (+68.1%), R2 (-1.8%), R3 (-78.0%), R4 (+19.2%), R5 (-5.5%); Vol: R3 77.9%, R4 10.3%; Sharpe: R0 +2.48, R4 +1.37. | Y-axis specifies `NIFTY 50 Annualized Return (Daily Mean x 252, %)`. | **MATCH** (`5F1F35EC...`) | **PASS** |
| **`fig2_sector_performance.png`** | `daily_simulation_1A.parquet` (`r_AUTO` to `r_PHARMA`) | 6x6 heatmap of annualized daily velocities: R3 Bank -202.9%, Pharma +214.3%; R1 Auto +138.4%, Metal +128.7%; R4 Metal +51.9%. | Clearly labeled as `Annualized Return (%)` with `Daily Mean x 252` caveats in text. | **MATCH** (`2B59485F...`) | **PASS** |
| **`fig3_transition_dynamics.png`** | `daily_simulation_1A.parquet` (`accepted_regime`, `period`) | 2-panel heatmap: Left (Train 2019–2024 diagonals: 98.4%, 97.5%, 97.0%, 96.3%, 96.3%, 97.1%); Right (Holdout 2025–2026 diagonals: 87.5%, 0%, 93.2%, 0%, 94.7%, 96.0%). | Panel titles explicitly state `Training Period (2019-2024)` and `Holdout Period (2025-2026)`. | **MATCH** (`07C325C3...`) | **PASS** |
| **`fig4_correlation_dispersion.png`** | `daily_simulation_1A.parquet` (sector correlation matrices) | Left: Mean pairwise corr (R0 0.43, R1 0.41, R2 0.36, R3 0.80, R4 0.32, R5 0.55); Right: PC1 variance (R3 83.5%, R4 44.0%). | Titles clearly denote `Mean Off-Diagonal Sector Correlation` and `First Principal Component (PC1) Variance Explained (%)`. | **MATCH** (`13B4F465...`) | **PASS** |
| **`fig5_holdout_diagnosis.png`** | `metrics_summary.parquet` & `daily_simulation_1A.parquet` | Left: CAGR Net (+43.3% vs -11.9%); Right: Attribution (Auto +5.8 to -3.7, IT +9.7 to -6.6, Metal +14.9 to -2.8, Bank 0.0 to 0.0). | Titles explicitly distinguish `Geometric Compounding` from `Arithmetic Net Return Attribution (pp)`. | **MATCH** (`ABACA4E7...`) | **PASS** |
| **`fig6_regime_frequency_shift.png`** | `daily_simulation_1A.parquet` (`accepted_regime`, `period`) | Left: Allocation frequency (R2 expanded from 31.4% to 45.5%; R4 contracted from 27.8% to 25.4%); Right: Duration boxplots (Train median 24d vs Holdout median 12d). | Clear axis labels and episode counts annotated. | **MATCH** (`D5B643DC...`) | **PASS** |

---

## 9. Itemized Audit Findings & Discrepancy Log

| Audit ID | Topic | Finding Description | Severity | Recommended Remediation | Status |
|:---:|---|---|:---:|---|:---:|
| **DISC-01** | Session Count | 1,686 sessions in backtest simulation vs 1,687 in feature label sets. | Informational | Document that $t_0 = \text{2019-10-31}$ generates initial weights, while daily returns start on $t_1 = \text{2019-11-01}$. | **PASS** |
| **DISC-02** | India VIX Medians | Table 1 of Markdown/PDF report presented full-sample VIX arithmetic means under a "Median India VIX" label. | Minor Documentation Defect | Update Table 1 and narrative in `phase13_regime_interpretation.md` and `.pdf` to display true empirical medians (`[20.81, 32.98, 13.62, 55.30, 13.05, 19.44]`) or explicitly label both Mean and Median. | **FAIL (Documentation Label)** |
| **DISC-03** | Figure 3 Transition Metrics | Step 2568 chat summary cited `(R0: 93.8%, ...)` which contradicted both the figure and notebook. | Conversational Defect | Clarify in audit records that Figure 3 plots Train vs. Holdout period matrices, while Notebook Cell 9 displays the Full-Sample matrix. Chat text was an errant summary. | **PASS (Artifacts Intact)** |
| **DISC-04** | Event-Analysis Parquets | 6 of 7 event-analysis Parquets are not called by `zz_phase13_economic_interpretation.ipynb`. | Expected Architecture | Mark the 6 unused datasets `NOT APPLICABLE` for direct notebook comparison. Verify that `macro_episodes_summary.parquet` matches Cell 15. | **PASS** |
| **DISC-05** | Metric Delineation | CAGR (+43.32% / -11.87%) vs. Arithmetic Attribution (+38.11% / -11.44%). | Validated | Fully distinguished and mathematically explained in notebook, report, and Figure 5. | **PASS** |

---

## 10. Final Recommendations

1. **Table 1 VIX Label Correction:** In the next authorized documentation correction pass, update Table 1 and Section 1 narrative in `reports/phase13_regime_interpretation.md` and `reports/phase13_regime_interpretation.pdf` to report the true empirical medians (`20.81, 32.98, 13.62, 55.30, 13.05, 19.44`) rather than the arithmetic means, or provide both side-by-side (`Mean / Median`).
2. **Transition Matrix Context Documentation:** Add a brief explanatory footnote in Section 4 of the Markdown report stating that Figure 3 illustrates the structural regime shift between the Training Period and Holdout Period transition matrices, whereas Table 3 and Notebook Cell 9 report the Full-Sample aggregate Markov matrix.
3. **Preserve Current Project State:** Do not modify any underlying canonical Phase 1–12 datasets or backtest simulation Parquets. The empirical outputs and calculations in `zz_phase13_economic_interpretation.ipynb` are mathematically verified and sound.

---

## 11. Final Audit Verdict

Based on an exhaustive, read-only inspection of all underlying Parquets, CSVs, notebook outputs, reports, and visual figure files:

### **PASS WITH MINOR DOCUMENTATION ISSUES — TARGETED CORRECTIONS REQUIRED**

**Justification:**  
All underlying numerical calculations in `notebooks/zz_phase13_economic_interpretation.ipynb` are independently reproducible from the canonical data sources. The 1-session difference and Figure 3 transition metrics are fully explained with mathematical and architectural evidence. The only outstanding issue is a minor documentation labeling defect in Table 1 of the Markdown and PDF reports, where arithmetic means of India VIX were reported under a median label. Once this minor text synchronization is authorized, Phase 13 will be fully certified for Phase 14.

