# Phase 10.1: Read-Only Data and Schedule Readiness Audit Report

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Phase:** 10.1 (Read-Only Readiness Audit)  
**Date:** November 4, 2026  
**Auditor:** Automated Quantitative Audit Suite  
**Final Verdict:** **PASS WITH LIMITATIONS**  

---

## 1. Executive Summary

A comprehensive, strictly read-only audit of all datasets, probabilistic signals, portfolio schedules, and execution rules required for Phase 10 historical portfolio backtesting was conducted. 

### Key Findings
1. **Market Price Data (7 Files):** All seven aligned index CSV files exist, are chronologically sorted, contain zero nulls, zero negative/suspicious prices, and share a 100% identical trading calendar of 1,886 trading sessions from `2019-01-02` to `2026-09-18`.
2. **Close vs. Adj Close Investigation:** In 6 of 7 indices (`NIFTY50`, `AUTO`, `FMCG`, `IT`, `METAL`, `PHARMA`), `Close` and `Adj Close` are bit-for-bit identical (zero difference across all 1,886 sessions). In `BANK`, a minor scaling discrepancy of approximately 0.00116% (~1.16 bps) is present on 975 rows prior to `2022-12-15`. Crucially, both series represent **Price Return (PR)** indices without dividend reinvestment.
3. **Causal HMM Probabilities:** `results/regime_discovery/hmm_causal_probabilities.csv` contains exactly 1,687 observations across the frozen timeline (`2019-10-31` to `2026-09-18`). Probabilities are finite, bounded in $[0, 1]$, and sum to $1.0$. The argmax regime matches `final_regime_labels.csv` (`filtered_causal`) with **100.00% exact agreement (1,687 / 1,687)**, while diverging from retrospective Viterbi on 49 dates, confirming causal filtering.
4. **Phase 9 Portfolio Schedules:** All four canonical target-weight schedules (`1A`, `1B`, `2A`, `2B`) exist, have 1,687 rows, 23 columns (+ Date index), non-negative weights, simplex sum $= 1.0$, and verify seamless train-to-holdout state continuity (`incumbent_regime` and `holding_days` carry across `2024-12-31` to `2025-01-02` without reset).
5. **Phase 1–9 Integrity:** Git working tree confirms that all prior artifacts from Phases 1 through 9 remain untouched and committed.

---

## 2. Inventory of Inspected Files

| # | File Path | Category | File Size | Row Count | SHA-256 Checksum (Prefix) |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **1** | `data/processed/aligned/nifty_auto_aligned.csv` | Market Price | 117,498 B | 1,886 | `b7ce74...` |
| **2** | `data/processed/aligned/nifty_bank_aligned.csv` | Market Price | 161,923 B | 1,886 | `47f5cf...` |
| **3** | `data/processed/aligned/nifty_fmcg_aligned.csv` | Market Price | 119,800 B | 1,886 | `da96bb...` |
| **4** | `data/processed/aligned/nifty_it_aligned.csv` | Market Price | 163,757 B | 1,886 | `f9ba32...` |
| **5** | `data/processed/aligned/nifty_metal_aligned.csv` | Market Price | 113,031 B | 1,886 | `eb3dd5...` |
| **6** | `data/processed/aligned/nifty_pharma_aligned.csv` | Market Price | 176,076 B | 1,886 | `9a75d5...` |
| **7** | `data/processed/aligned/nifty50_aligned.csv` | Benchmark Price | 171,848 B | 1,886 | `a7be92...` |
| **8** | `results/regime_discovery/hmm_causal_probabilities.csv` | Causal Probabilities | 213,089 B | 1,687 | `8132a4...` |
| **9** | `results/regime_discovery/final_regime_labels.csv` | Reference Labels | 312,146 B | 6,748 | `814216...` |
| **10** | `results/portfolio_construction/target_weights_1A.csv` | Portfolio Schedule | 204,192 B | 1,687 | `2783ea...` |
| **11** | `results/portfolio_construction/target_weights_1B.csv` | Portfolio Schedule | 255,909 B | 1,687 | `7972ba...` |
| **12** | `results/portfolio_construction/target_weights_2A.csv` | Portfolio Schedule | 204,689 B | 1,687 | `693432...` |
| **13** | `results/portfolio_construction/target_weights_2B.csv` | Portfolio Schedule | 256,254 B | 1,687 | `435a9e...` |
| **14** | `reports/phase9_2_portfolio_construction.md` | Audit Reference | 16,808 B | 237 lines | `59a121...` |

---

## 3. Market Price Datasets Audit

### 3.1 Structural and Calendar Integrity
All seven files under `data/processed/aligned/` were parsed and inspected:

| Dataset File | Rows | Start Date | End Date | Sorted | Unique | Missing / Nulls | Zero / Neg Prices | Price Range (`Close`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `nifty_auto_aligned.csv` | 1,886 | `2019-01-02` | `2026-09-18` | Yes | Yes | 0 | 0 | 4,517.75 – 29,647.90 |
| `nifty_bank_aligned.csv` | 1,886 | `2019-01-02` | `2026-09-18` | Yes | Yes | 0 | 0 | 16,917.65 – 61,550.80 |
| `nifty_fmcg_aligned.csv` | 1,886 | `2019-01-02` | `2026-09-18` | Yes | Yes | 0 | 0 | 23,184.05 – 66,305.20 |
| `nifty_it_aligned.csv` | 1,886 | `2019-01-02` | `2026-09-18` | Yes | Yes | 0 | 0 | 11,179.60 – 45,995.80 |
| `nifty_metal_aligned.csv` | 1,886 | `2019-01-02` | `2026-09-18` | Yes | Yes | 0 | 0 | 1,496.45 – 13,718.30 |
| `nifty_pharma_aligned.csv` | 1,886 | `2019-01-02` | `2026-09-18` | Yes | Yes | 0 | 0 | 6,432.30 – 27,186.45 |
| `nifty50_aligned.csv` | 1,886 | `2019-01-02` | `2026-09-18` | Yes | Yes | 0 | 0 | 7,610.25 – 26,328.55 |

- **Calendar Synchronization:** Pairwise date index comparisons confirmed that all 7 series share a **100% identical trading calendar** of 1,886 sessions. There are zero calendar mismatches or missing sessions.
- **Historical Warmup Window:** The price history starts on `2019-01-02`, exactly 199 trading sessions prior to the strategy start date (`2019-10-31`). This provides ample history for any rolling volatility or momentum lookbacks.

### 3.2 Price Series Investigation: `Close` vs. `Adj Close`

A detailed numerical comparison between `Close` and `Adj Close` across all 1,886 sessions revealed:

| Index Dataset | Max Absolute Difference | Max Percentage Difference | Differing Rows | Assessment |
| :--- | :---: | :---: | :---: | :--- |
| `nifty_auto_aligned.csv` | 0.000000 | 0.0000% | 0 / 1,886 | Identical bit-for-bit |
| `nifty_bank_aligned.csv` | 0.511719 | 0.0012% (1.16 bps) | 975 / 1,886 | Minor historical scaling artifact |
| `nifty_fmcg_aligned.csv` | 0.000000 | 0.0000% | 0 / 1,886 | Identical bit-for-bit |
| `nifty_it_aligned.csv` | 0.000000 | 0.0000% | 0 / 1,886 | Identical bit-for-bit |
| `nifty_metal_aligned.csv` | 0.000000 | 0.0000% | 0 / 1,886 | Identical bit-for-bit |
| `nifty_pharma_aligned.csv` | 0.000000 | 0.0000% | 0 / 1,886 | Identical bit-for-bit |
| `nifty50_aligned.csv` | 0.000000 | 0.0000% | 0 / 1,886 | Identical bit-for-bit |

#### Diagnostic Findings on `Adj Close`
1. **Price Return (PR) vs. Total Return (TRI):**
   - In Yahoo Finance, index tickers (`^NSEI`, `^CNXAUTO`, `^NSEBANK`, etc.) are downloaded as **Price Return (PR)** series. Yahoo Finance does not adjust cash index levels for constituent dividend distributions.
   - Consequently, for 6 out of 7 indices, `Adj Close` is simply a direct duplicate of `Close`.
2. **NIFTY Bank Discrepancy:**
   - In `nifty_bank_aligned.csv`, `Adj Close` differs from `Close` by a constant factor of $0.99998836$ (~1.16 bps) between `2019-01-02` and `2022-12-14` (975 rows), after which `Adj Close == Close`.
   - This difference is an upstream Yahoo Finance artifact and does not reflect a dividend-adjusted Total Return series.
3. **Recommendation for Phase 10.2:**
   - Use `Close` as the authoritative price series for all return and performance calculations.
   - Formally document that historical backtest results represent Price Return (PR) performance, conservative with respect to dividend income (which would add ~1.2% to ~1.6% annualized to real-world equity performance).

---

## 4. Audit of Causal HMM Probabilities

### 4.1 File & Schema Verification
- **Path:** `results/regime_discovery/hmm_causal_probabilities.csv`
- **Observations:** Exactly 1,687 trading dates.
- **Columns:** `Date` (Index), `period`, `prob_0`, `prob_1`, `prob_2`, `prob_3`, `prob_4`, `prob_5`.
- **Finiteness & Missingness:** Zero nulls, zero NaNs, zero infinities.
- **Bounds:** All probabilities $\in [0.000000, 1.000000]$.
- **Row Sums:** Max deviation from $1.0$ is $4.44 \times 10^{-16}$, within double-precision machine epsilon.
- **Chronology:** Monotonically increasing from `2019-10-31` to `2026-09-18`. Unique dates confirmed.

### 4.2 Timeline Partition Reconciliations
- **Training Period:** 1,265 dates (`2019-10-31` to `2024-12-31`). Exactly matches frozen specifications.
- **Holdout Period:** 422 dates (`2025-01-02` to `2026-09-18`). Exactly matches frozen specifications.

### 4.3 Causal Filtering vs. Retrospective Viterbi Cross-Check
The argmax of the continuous probability vector $\text{argmax}_{j} (\text{prob}_j)$ was cross-checked against the discrete labels recorded in `results/regime_discovery/final_regime_labels.csv`:
- **Agreement with `filtered_causal` labels:** **1,687 / 1,687 (100.00% exact match)**.
- **Agreement with `retrospective_viterbi` labels:** **1,638 / 1,687 (97.10% match)**.
- **Divergence:** Exactly 49 trading sessions differ between causal filtering and Viterbi decoding. This confirms empirically that Phase 9 used causal forward-filtered probabilities with zero look-ahead leakage.

---

## 5. Audit of Four Phase 9 Portfolio Schedules

### 5.1 Schedule Integrity Matrix

| Parameter / Metric | Variant 1A | Variant 1B | Variant 2A | Variant 2B |
| :--- | :---: | :---: | :---: | :---: |
| **Output File** | `target_weights_1A.csv` | `target_weights_1B.csv` | `target_weights_2A.csv` | `target_weights_2B.csv` |
| **Row Count** | 1,687 | 1,687 | 1,687 | 1,687 |
| **Train / Holdout Rows**| 1,265 / 422 | 1,265 / 422 | 1,265 / 422 | 1,265 / 422 |
| **Date Coverage** | `2019-10-31` to `2026-09-18` | `2019-10-31` to `2026-09-18` | `2019-10-31` to `2026-09-18` | `2019-10-31` to `2026-09-18` |
| **Chronological / Unique**| Yes / Yes | Yes / Yes | Yes / Yes | Yes / Yes |
| **Next-Day Timing ($t+1$)**| Verified | Verified | Verified | Verified |
| **All 8 Assets Present**| Yes | Yes | Yes | Yes |
| **Weights Bounded $[0, 1]$**| $[0.00, 0.50]$ | $[0.00, 0.76]$ | $[0.00, 0.50]$ | $[0.00, 0.76]$ |
| **Weight Sum Max Dev** | $0.00$ | $2.22 \times 10^{-16}$ | $0.00$ | $2.22 \times 10^{-16}$ |
| **Cash Target Rule** | Strictly $0.0\%$ | Strictly $0.0\%$ | Regime Cash: $0\%-40\%$ | Regime Cash: $0\%-40\%$ |
| **Mean Cash Allocation** | $0.00\%$ | $0.00\%$ | $5.23\%$ | $5.23\%$ |
| **Total Rebalances** | 58 | 58 | 58 | 58 |
| **R3 Crisis Overrides** | 1 | 1 | 1 | 1 |
| **Mean Daily Turnover** | 2.993% | 3.059% | 3.038% | 3.089% |

### 5.2 Variant Definitions & Asset Schema
- **Eight Assets:** `w_NIFTY50`, `w_AUTO`, `w_BANK`, `w_FMCG`, `w_IT`, `w_METAL`, `w_PHARMA`, `w_CASH`.
- **Variant 1A:** Template A (100% equity) + Equal Weight (50% / 50% Top-2 sectors).
- **Variant 1B:** Template A (100% equity) + Trailing 20-day Inverse Volatility.
- **Variant 2A:** Template B (Defensive cash buffer) + Equal Weight.
- **Variant 2B:** Template B (Defensive cash buffer) + Trailing 20-day Inverse Volatility.

---

## 6. Phase 9 Execution Contract Verification

The operational mechanics recorded in the schedules and codebase conform to the frozen contract:

1. **Initial Portfolio (Day 0):** On `2019-10-31`, portfolio starts as 100% NIFTY 50 (`holding_days_before = 0`, `incumbent_regime_before = None`). Initial signal acceptance causes turnover $= 1.0$ into target sectors at 15 bps cost ($0.0015$).
2. **Next-Day Close Execution ($t+1$ Close):**
   - For every session $t < T$, `exec_date` is strictly the subsequent trading session index $t+1$.
   - A signal produced at session $t$ Close is scheduled for execution at session $t+1$ Close.
3. **Operational Controls:**
   - **Confidence Threshold:** Signals are accepted if and only if $\max_j (\text{prob}_j) \ge 0.50$.
   - **Minimum Holding Period:** Elective rebalances require $\ge 5$ trading days of incumbent tenure.
   - **Crisis Override:** A confirmed transition to Regime 3 (acute market liquidation) immediately bypasses the 5-day lockup (triggered exactly once on `2020-03-12`).
4. **Turnover Representation:**
   - In Phase 9 schedules, the `turnover` column records **nominal target-to-target turnover** ($\frac{1}{2}\sum |w_{i,\text{target}} - w_{i,\text{prev}}|$) without intra-period price drift.
5. **Cash Return Baseline:**
   - Cash allocations earn a baseline nominal return of $0.0\%$.

---

## 7. Phase 9 Integrity Verification

- **Git Working Tree:** Status is completely clean. Only temporary exploration scripts in `scratch/` exist as untracked files.
- **Immutability of Authoritative Artifacts:**
  - `results/regime_discovery/final_regime_labels.csv` (`SHA-256: 814216...`): UNCHANGED.
  - `results/regime_discovery/hmm_causal_probabilities.csv` (`SHA-256: 8132a4...`): UNCHANGED.
  - All four target-weight CSV files: UNCHANGED and committed under git commit `a951f67`.
  - Core rules engine `src/regime_rotation_rules.py`: UNCHANGED.
- **Phase 9 Test Baseline:** All 75 tests across the project test suite (`tests/`) passed cleanly prior to audit commencement.

---

## 8. Issues, Discrepancies & Unresolved Questions

1. **Price Return vs. Total Return Limitation:**
   - Yahoo Finance index series do not incorporate dividend reinvestment. Real-world performance of an ETF or basket replicating these sectors would capture an additional ~1.2% to ~1.6% in annual dividend yield.
2. **NIFTY Bank Minor Price Discrepancy:**
   - `Close` and `Adj Close` in `nifty_bank_aligned.csv` differ by ~1.16 bps across 975 pre-2023 rows due to an upstream data provider artifact.
3. **Turnover Modeling (Nominal vs. Drifted):**
   - Phase 9 recorded nominal turnover. Between rebalances, asset price movements alter relative weights. Phase 10 must decide whether transaction costs are billed on nominal turnover or dynamic market-drifted turnover.
4. **Terminal Session Execution ($T = \text{2026-09-18}$):**
   - The final row in the schedule (`2026-09-18`) generates target weights scheduled for execution at $T+1$, but no $T+1$ price exists. The effective return series terminates at Date $T$.

---

## 9. Phase 10.2 Architectural Prerequisites

Before implementing the backtesting engine in Phase 10.2, the following design decisions must be formally ratified:

1. **Price Series Selection:** Select `Close` as the uniform, canonical price series across all 7 indices.
2. **Return Accounting Equations:**
   - **Return Window:** Portfolio held across trading sessions $t \to t+1$ earns return:
     $$R_{t \to t+1} = \sum_{i} w_i^{(t)} \left( \frac{P_{i, t+1}}{P_{i, t}} - 1 \right)$$
   - **Rebalance Execution:** At Date $t+1$ Close, rebalancing occurs. New target weights $w^{(t+1)}$ apply to returns over $t+1 \to t+2$.
3. **Turnover & Cost Deductions:**
   - Formalize whether transaction costs (15 bps) apply to nominal target turnover or dynamic drifted turnover at $t+1$ Close.
   - Deduct transaction costs directly from portfolio equity value at execution close.
4. **Benchmark Implementation:**
   - NIFTY 50 Benchmark: Daily return $R_{\text{BM1}, t \to t+1} = \frac{P_{\text{NIFTY}, t+1}}{P_{\text{NIFTY}, t}} - 1$.
   - Equal-Weight 6-Sector Benchmark: Daily return $R_{\text{BM2}, t \to t+1} = \frac{1}{6} \sum_{s=1}^6 \left( \frac{P_{s, t+1}}{P_{s, t}} - 1 \right)$.
5. **Reporting Splits:**
   - Separate equity curves, CAGR, Sharpe ratios, Sortino ratios, and drawdowns strictly into Training (`2019-10-31` to `2024-12-31`) and Protected Holdout (`2025-01-02` to `2026-09-18`).

---

## 10. Final Audit Verdict

### **VERDICT: PASS WITH LIMITATIONS**

**Justification:**  
All inputs required for Phase 10 backtesting are present, mathematically sound, chronologically aligned, and strictly causal:
- 100% calendar and price alignment across 1,886 sessions.
- 100% label agreement between continuous probabilities and approved causal regime labels.
- Zero look-ahead bias across all four target-weight schedules.
- Seamless train-to-holdout state continuity.

The single limitation is the upstream Price Return nature of the data (dividends excluded) and the need to formalize the nominal vs. drifted turnover convention in Phase 10.2.

**Sign-Off:**  
Phase 10.1 is complete. No code was modified, no tests were altered, and no backtesting was conducted. Proceed to Phase 10.2 once authorized.

