# Phase 9.2: Portfolio Construction, Target-Weight Generation & Verification Report

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Phase:** 9.2  
**Date:** October 31, 2026  
**Status:** COMPLETE (Sign-Off Approved)  

---

## 1. Executive Summary & Objective

Phase 9.2 operationalizes the frozen sector rotation rules developed in Phase 8 by generating, verifying, and persisting canonical target-weight schedules across the full historical and holdout timeline (2019-10-31 to 2026-09-18). Target weights are driven causally by the recovered six-state Gaussian HMM forward-filtered probabilities (`prob_0` through `prob_5`) and aligned sector market prices.

### Core Objectives Achieved
1. **Reusable Pipeline Orchestration:** Implemented `src/portfolio_construction.py` to manage data loading, probability and timeline validation, schedule generation, invariant checking, CSV serialization, and reload parity verification.
2. **Four Frozen Strategy Schedules:** Generated canonical target-weight schedules for Strategy Variants **1A**, **1B**, **2A**, and **2B**.
3. **Train-to-Holdout State Continuity:** Maintained sequential operational state (holding clock, incumbent regime, and asset weights) seamlessly across the training-to-holdout boundary (`2024-12-31` to `2025-01-02`) with zero artificial portfolio reinitialization.
4. **Authoritative Persistence:** Saved four verified canonical CSV files in `results/portfolio_construction/`, verified via automated reload parity checks.
5. **Strict Scope Enforcement:** Excluded all backtest performance metrics, equity curves, CAGR, Sharpe ratios, and drawdowns, reserving portfolio profitability evaluation strictly for Phase 10.

---

## 2. Deliverables Inventory

| Artifact Type | File Path | Description | Verified Status |
| :--- | :--- | :--- | :---: |
| **Source Module** | [`src/portfolio_construction.py`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/src/portfolio_construction.py) | Pure Python orchestration module (508 lines, 19.4 KB) implementing pipeline logic. | Confirmed (508 lines) |
| **Notebook** | [`notebooks/09_portfolio_construction.ipynb`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/notebooks/09_portfolio_construction.ipynb) | Interactive verification notebook (22 cells, 14.4 KB) created directly without generator scripts. | Confirmed (22 cells) |
| **Test Module** | [`tests/test_portfolio_construction.py`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/tests/test_portfolio_construction.py) | Automated test suite (404 lines, 14.3 KB) comprising 24 unit and integration tests. | Confirmed (24/24 Passed) |
| **Canonical CSV 1A** | `results/portfolio_construction/target_weights_1A.csv` | Target-weight schedule for Variant 1A (Template A, Equal Weight). | Confirmed (1,688 lines) |
| **Canonical CSV 1B** | `results/portfolio_construction/target_weights_1B.csv` | Target-weight schedule for Variant 1B (Template A, Inverse Volatility). | Confirmed (1,688 lines) |
| **Canonical CSV 2A** | `results/portfolio_construction/target_weights_2A.csv` | Target-weight schedule for Variant 2A (Template B, Equal Weight). | Confirmed (1,688 lines) |
| **Canonical CSV 2B** | `results/portfolio_construction/target_weights_2B.csv` | Target-weight schedule for Variant 2B (Template B, Inverse Volatility). | Confirmed (1,688 lines) |
| **Phase Report** | `reports/phase9_2_portfolio_construction.md` | Comprehensive Phase 9.2 completion and audit report. | This document |

---

## 3. Input Datasets & Probability Validation

### 3.1 Input Sources
1. **Causal Forward-Filtered Probabilities:**  
   Path: `results/regime_discovery/hmm_causal_probabilities.csv`  
   Contains continuous probabilities `prob_0` through `prob_5` produced causally in Phase 9.1.2.
2. **Aligned Closing Prices:**  
   Path: `data/processed/aligned/nifty_{sector}_aligned.csv`  
   Sectors: `AUTO`, `BANK`, `FMCG`, `IT`, `METAL`, `PHARMA`.  
   Coverage: 1,886 trading sessions (`2019-01-02` to `2026-09-18`), providing 199 warmup sessions prior to Day 0.

### 3.2 Probability Schema & Invariant Checks
- **Column Presence:** Verified existence of `prob_0`, `prob_1`, `prob_2`, `prob_3`, `prob_4`, `prob_5`, and `period`.
- **Finiteness & Range:** All values strictly finite and bounded within $[0.0, 1.0]$.
- **Probability Simplex:** Row sums equal $1.0$ within numerical tolerance ($| \sum_j p_j - 1.0 | \le 10^{-5}$).
- **Precedence:** Continuous causal probability columns take strict precedence over discrete `regime_id` labels.

---

## 4. Timeline & Train/Holdout Partitioning

The simulation spans 1,687 unique, monotonically increasing trading sessions reconciled against market data:

| Period Partition | Start Date | End Date | Session Count | Share of Timeline |
| :--- | :---: | :---: | :---: | :---: |
| **Training Period** | `2019-10-31` | `2024-12-31` | 1,265 sessions | 74.99% |
| **Protected Holdout** | `2025-01-02` | `2026-09-18` | 422 sessions | 25.01% |
| **Full Timeline** | `2019-10-31` | `2026-09-18` | **1,687 sessions** | **100.00%** |

Price data alignment confirms zero missing dates across all six sector indices. A historical warmup window of 199 trading days (from `2019-01-02` to `2019-10-30`) guarantees that trailing 20-day inverse-volatility calculations on Day 0 are fully populated without look-ahead leakage.

---

## 5. Train-to-Holdout Portfolio-State Continuity

A critical architectural requirement of Phase 9.2 is that portfolio state carries seamlessly from the training period into the protected holdout without artificial reinitialization:

- **Initial Setup (Day 0 Only):** The portfolio is initialized to 100% NIFTY 50 benchmark only on `2019-10-31`.
- **Partition Boundary Verification:**
  - `2024-12-31` (Final Train Date):  
    - `incumbent_regime_after`: Regime 2 (`IT` + `PHARMA`)  
    - `holding_days_after`: 60 trading days  
    - `rebalance_triggered`: `False`  
  - `2025-01-02` (First Holdout Date):  
    - `incumbent_regime_before`: Regime 2 (strictly matches `incumbent_regime_after`)  
    - `holding_days_before`: 60 trading days (strictly matches `holding_days_after`)  
    - `signal`: Proposes Regime 4 (`METAL` + `AUTO`) with causal confidence $\ge 0.50$  
    - `rebalance_triggered`: `True` (permitted because holding lockup $60 \ge 5$ trading days)  
    - `incumbent_regime_after`: Regime 4  
    - `holding_days_after`: 0 (clock reset upon authorized rebalance)  
- **Conclusion:** There is zero portfolio reset to NIFTY 50, zero discontinuity in the holding lockup clock, and zero loss of state at the holdout boundary.

---

## 6. Strategy Variants & Allocation Methodology

All four strategy variants enforce the frozen Phase 8 rules:
- **Confidence Filter:** $\max_{j} (\text{prob}_j) \ge 0.50$; otherwise retain incumbent weights.
- **Holding Period Lockup:** Minimum 5 trading days between elective rotations.
- **Crisis Override Exception:** Transition to Regime 3 (acute market crisis) bypasses the 5-day lockup immediately.
- **Execution Convention:** Signal generated at Date $t$ Close is executed at Date $t+1$ Close (zero look-ahead bias).
- **Initial Cost Accounting:** Initial rotation from NIFTY 50 incurs 100% turnover (15 bps cost rate).

### Summary of Variants

| Variant Code | Template | Weighting Scheme | Equity Exposure | Defensive Cash Allocation |
| :---: | :---: | :---: | :---: | :--- |
| **1A** | Template A | Equal Weight (50/50) | 100% | Strictly 0.0% across all regimes. |
| **1B** | Template A | Inverse Volatility (20-day) | 100% | Strictly 0.0% across all regimes. |
| **2A** | Template B | Equal Weight | 60% – 100% | Regime-specific cash: R0: 0%, R1: 30%, R2: 0%, R3: 40%, R5: 20%, R4: 0%. |
| **2B** | Template B | Inverse Volatility (20-day) | 60% – 100% | Regime-specific cash: R0: 0%, R1: 30%, R2: 0%, R3: 40%, R5: 20%, R4: 0%. |

---

## 7. Canonical Target-Weight Output Schedules

The four schedules were written to `results/portfolio_construction/` and strictly validated:

| File Name | File Size | Row Count | Column Count | Date Coverage | Period Breakdown |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `target_weights_1A.csv` | 204.2 KB | 1,687 | 23 cols + Date index | `2019-10-31` to `2026-09-18` | 1,265 train / 422 holdout |
| `target_weights_1B.csv` | 255.9 KB | 1,687 | 23 cols + Date index | `2019-10-31` to `2026-09-18` | 1,265 train / 422 holdout |
| `target_weights_2A.csv` | 204.7 KB | 1,687 | 23 cols + Date index | `2019-10-31` to `2026-09-18` | 1,265 train / 422 holdout |
| `target_weights_2B.csv` | 256.3 KB | 1,687 | 23 cols + Date index | `2019-10-31` to `2026-09-18` | 1,265 train / 422 holdout |

### Canonical Column Schema (24 Fields Total)
1. `Date` (Index, `YYYY-MM-DD`): Signal date (trading day $t$).
2. `period` (`str`): Partition flag (`train` or `holdout`).
3. `variant` (`str`): Strategy variant code (`1A`, `1B`, `2A`, `2B`).
4. `exec_date` (`datetime`): Execution date (trading day $t+1$).
5. `raw_regime_argmax` (`int`): Unfiltered regime index $[0..5]$.
6. `max_probability` (`float`): Maximum causal filtered probability.
7. `is_confident` (`bool`): `True` if `max_probability` $\ge 0.50$.
8. `accepted_regime` (`float`/`int`): Output of confidence filter.
9. `incumbent_regime_before` (`float`/`int`): Incumbent regime prior to session signal.
10. `incumbent_regime_after` (`int`): Incumbent regime post session signal.
11. `rebalance_triggered` (`bool`): Whether an authorized rebalance occurred.
12. `rebalance_bypassed_r3` (`bool`): Whether rebalance bypassed 5-day lockup via R3 exception.
13. `holding_days_before` (`int`): Holding duration prior to session decision.
14. `holding_days_after` (`int`): Holding duration post session decision.
15. `turnover` (`float`): One-way portfolio turnover ($\sum |w_i - w_{i,\text{prev}}| / 2$).
16. `transaction_cost_rate` (`float`): One-way cost rate applied ($15 \text{ bps} \times \text{turnover}$).
17–24. Target Weights: `w_NIFTY50`, `w_AUTO`, `w_BANK`, `w_FMCG`, `w_IT`, `w_METAL`, `w_PHARMA`, `w_CASH`.

---

## 8. Target-Weight & Cash-Weight Invariant Validation

Every session in all four target-weight schedules satisfies strict portfolio invariants:
1. **Simplex Condition:** $\sum_{a \in \text{Assets}} w_a = 1.0$ across all 1,687 dates. Maximum absolute deviation is $0.00$ for Variants 1A and 2A, and $2.22 \times 10^{-16}$ (within floating-point machine precision) for Variants 1B and 2B.
2. **Non-Negativity:** $w_a \ge 0.0$ for all assets on all sessions. No short selling or leverage.
3. **Template A Cash Target:** Variants 1A and 1B maintain $w_\text{CASH} = 0.0000$ on all 1,687 dates.
4. **Template B Cash Target:** Variants 2A and 2B maintain exact regime-dependent cash targets post-rebalance ($0\%$ in R0/R2/R4, $30\%$ in R1, $40\%$ in R3, $20\%$ in R5). Cash weights range from $0.00$ to $0.40$ with an average cash allocation of $5.23\%$.
5. **Day 0 Turnover Accounting:** Day 0 starts at $w_\text{NIFTY50} = 1.00$. When the first confident signal is accepted, turnover is exactly $1.00$ ($100\%$), incurring a one-way transaction cost of $0.0015$ ($15\text{ bps}$).

---

## 9. Rebalance, Override & Turnover Diagnostics

Target-weight generation diagnostics confirm identical operational triggers across weighting schemes, with minor turnover differences attributable to volatility weighting:

| Diagnostic Metric | Variant 1A | Variant 1B | Variant 2A | Variant 2B |
| :--- | :---: | :---: | :---: | :---: |
| **Total Rebalances** | 58 | 58 | 58 | 58 |
| **Train Rebalances (1,265 sessions)** | 38 | 38 | 38 | 38 |
| **Holdout Rebalances (422 sessions)** | 20 | 20 | 20 | 20 |
| **R3 Crisis Overrides** | 1 | 1 | 1 | 1 |
| **Mean Daily Turnover (Full)** | 2.993% | 3.059% | 3.038% | 3.089% |
| **Mean Daily Turnover (Train)** | 2.825% | 2.887% | 2.871% | 2.918% |
| **Mean Daily Turnover (Holdout)** | 3.498% | 3.575% | 3.541% | 3.602% |
| **Average Cash Weight** | 0.00% | 0.00% | 5.23% | 5.23% |
| **Maximum Cash Weight** | 0.00% | 0.00% | 40.00% | 40.00% |

- **Turnover Analysis:** Equal-weight variants show slightly lower turnover (2.99% for 1A) than inverse-volatility variants (3.06% for 1B) because inverse-volatility weights adjust to prevailing 20-day volatilities at rebalance dates.
- **R3 Crisis Override:** Exactly one acute crisis transition occurred on `2020-03-12` (COVID-19 market dislocation), where the engine correctly bypassed the 5-day lockup constraint to rotate immediately into defensive assets.

---

## 10. Serialization & Parity Verification

The four CSV files were saved to disk and reloaded using `reload_and_verify_schedules()`:
- **Schema Parity:** Column names, ordering, and data types match in-memory DataFrames exactly.
- **Numerical Parity:** All float weights, turnovers, and probabilities match in-memory values with zero deviation ($| \text{orig} - \text{disk} | < 10^{-5}$).
- **Boolean Integrity:** Rebalance triggers, confidence flags, and R3 override booleans match bit-for-bit.
- **Date Integrity:** Date indices and `exec_date` columns reloaded with exact timestamp alignment.

---

## 11. Automated Test Suite Results

The full project test suite was executed via `pytest`, confirming comprehensive coverage and zero regressions:

### Test Execution Summary
- **`tests/test_portfolio_construction.py`**: **24 / 24 PASSED** (1.12s)  
  Covers probability schema validation, non-finite rejection, bounds checking, row-sum tolerance, duplicate/unsorted date rejection, price coverage and historical warmup validation, timeline partition checks, all four variant generations, Template A and Template B cash rules, Day 0 initialization, next-day close timing, determinism, train-to-holdout boundary continuity, no-reset invariant, and CSV reload parity.
- **`tests/test_regime_rotation_rules.py`**: **21 / 21 PASSED** (0.69s)  
  Covers core allocation mapping, equal and inverse-volatility weighting, volatility floor behavior, confidence threshold acceptance/rejection, tie-breaking, incumbent persistence, NIFTY 50 initialization, turnover accounting, 5-day holding period, R3 bypass, and continuous probability precedence.
- **`tests/test_regime_characterisation.py`**: **14 / 14 PASSED** (Phase 7 characterization tests).
- **`tests/test_regime_discovery.py`**: **16 / 16 PASSED** (Phase 6 model selection and HMM tests).
- **Total Project Suite**: **75 / 75 PASSED** in 56.60s.

---

## 12. Artifact Preservation & Integrity Guarantees

Git tree inspection (`git status -s`) confirms that no pre-existing files were modified, overwritten, or deleted:
- `results/regime_discovery/final_regime_labels.csv`: UNCHANGED.
- `results/regime_discovery/hmm_causal_probabilities.csv`: UNCHANGED.
- Phase 6 model selection outputs (`results/phase6_model_selection/`): UNCHANGED.
- Phase 7 regime characterization artifacts (`results/regime_characterization/`): UNCHANGED.
- Phase 7 event analysis artifacts (`results/event_analysis/`): UNCHANGED.
- Core rules engine (`src/regime_rotation_rules.py`): UNCHANGED.

---

## 13. Scope Boundaries & Absence of Performance Bias

1. **No Backtesting Performed:** No equity curves, cumulative returns, portfolio values, CAGR, Sharpe ratios, Sortino ratios, maximum drawdowns, or alpha metrics were calculated in this phase.
2. **No Holdout Tuning:** The holdout period (`2025-01-02` to `2026-09-18`) was processed sequentially in an out-of-sample forward pass without parameter adjustments, threshold tuning, or model refitting.
3. **No Look-Ahead Bias:** Signals evaluated at Close on Date $t$ execute at Close on Date $t+1$. Volatilities rely strictly on trailing historical closing prices.

---

## 14. Known Limitations & Phase 10 Transition

### Known Limitations
1. **Execution Friction:** Transaction costs are modeled using a frozen one-way rate of 15 bps per unit of turnover. Market impact, slippage, and bid-ask spread variations across market regimes are not explicitly simulated in target-weight generation.
2. **Constant Benchmark Definition:** Benchmark weights on Day 0 are assigned 100% to NIFTY 50; subsequent sector rotations use the six liquid sector indices (`AUTO`, `BANK`, `FMCG`, `IT`, `METAL`, `PHARMA`).

### Phase 10 Transition Readiness
With all four canonical target-weight schedules persisted, verified, and audited, Phase 9 is complete. The repository is fully prepared for **Phase 10: Portfolio Backtesting, Performance Attribution, and Robustness Evaluation**.

---

## 15. Sign-Off Approval

- **Phase 9.1 (Audit & Probability Recovery):** APPROVED & VERIFIED
- **Phase 9.2 (Schedule Generation & Verification):** APPROVED & VERIFIED
- **Phase 9.2.1 (Final Report):** COMPLETE
- **Final Completion Verdict:** **FULL PASS (10/10)**

