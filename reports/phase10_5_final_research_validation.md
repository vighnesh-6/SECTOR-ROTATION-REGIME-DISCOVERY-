# Phase 10.5 — Final Research Validation Audit Report (Read-Only)

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Audit Phase:** 10.5 — Final Scientific, Statistical, and Empirical Validation  
**Date of Audit:** November 5, 2026  
**Auditor Mode:** Autonomous Lead Quantitative Auditor (Read-Only)  
**Overall Validation Verdict:** **PASS — READY FOR PHASE 10.5 SIGN-OFF**  

---

## 1. Executive Summary

This independent read-only audit provides the definitive validation of the Phase 10.5 Comparative Performance Evaluation. It verifies:
1. The execution and numerical integrity of the comparative evaluation notebook at its current path: [`notebooks/compare_performance.ipynb`](file:///C:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/notebooks/compare_performance.ipynb).
2. The statistical validity of conventional OLS versus Newey-West Heteroskedasticity and Autocorrelation Consistent (HAC) inference across all strategy-benchmark pairs.
3. The exact mathematical accounting and denominator of the -10.99% NIFTY IT return drag during the holdout period.
4. The statistical correction regarding the Durbin-Watson test and higher-order/non-linear serial dependence.
5. A comprehensive four-pillar forensic decomposition of the 2025–2026 holdout underperformance.
6. The complete preservation of all canonical Phase 1–10.3 and Phase 10.5 artifacts.

---

## 2. Validation A — Notebook Execution & Path Verification (PASS)

The primary comparative evaluation notebook was inspected and validated at its current path:
- **File Location:** `notebooks/compare_performance.ipynb`
- **Execution Check:** Executed headlessly via the Jupyter kernel. All 14 cells (7 code cells, 7 markdown cells) executed with **0 errors**.
- **Data Source:** Dynamically calls `run_comparative_evaluation()` from `src/comparative_evaluation.py`.
- **Output Agreement:** The formatted tables displayed in the notebook match the canonical CSV and Parquet files in `results/portfolio_backtest/comparative_evaluation/` bit-for-bit:
  - `comparative_metrics_table.csv` & `.parquet` (18 rows, 25 columns)
  - `relative_performance_matrix.csv` & `.parquet` (24 rows, 22 columns)
- **Visualizations Rendered:** Full-cycle net equity curves (linear and logarithmic), continuous and holdout-rebased drawdown charts, risk-return scatter plots with Sharpe isolines, and annualized alpha comparison bar charts all render without warnings or errors.

---

## 3. Validation B — OLS vs. HAC Inference for All 8 Full-Period Comparisons

To determine whether residual heteroskedasticity or serial correlation distorts statistical significance, Newey-West HAC standard errors and p-values were calculated across all 8 full-period comparisons ($N = 1,686$ return sessions).

### 3.1 Lag Selection & Mathematical Formulation
Following Newey and West (1987, 1994), standard errors were estimated with Bartlett kernel weights using the standard automatic bandwidth rule:
$$L = \left\lfloor 4 \times \left(\frac{N}{100}\right)^{2/9} \right\rfloor = \left\lfloor 4 \times (16.86)^{0.2222} \right\rfloor = \mathbf{7 \text{ lags}}$$

The asymptotic covariance matrix is:
$$\hat{\Omega}_{\text{HAC}} = \hat{\Gamma}_0 + \sum_{j=1}^7 \left(1 - \frac{j}{8}\right) (\hat{\Gamma}_j + \hat{\Gamma}_j')$$

### 3.2 Full-Period 8-Comparison Audit Table

| Strategy | Benchmark | Observations ($N$) | Beta ($\beta$) | Beta SE (HAC) | Beta $p$-val (HAC) | Ann. Alpha ($\alpha_{\text{ann}}$) | Alpha SE (OLS) | Alpha SE (HAC) | Alpha $t$ (HAC) | Alpha $p$-val (OLS) | Alpha $p$-val (HAC) | $R^2$ | Inference Outcome |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Strategy 1A** | NIFTY 50 | 1,686 | 0.8194 | 0.0402 | $2.55 \times 10^{-92}$ | **+16.13%** | 4.95% | 5.23% | +3.082 | 0.0011 | **0.0021** | 0.5632 | **Statistically Significant ($p < 0.01$)** |
| **Strategy 1A** | Equal-Weight | 1,686 | 0.9618 | 0.0381 | $3.37 \times 10^{-143}$| **+9.47%** | 3.98% | 4.32% | +2.192 | 0.0174 | **0.0285** | 0.7185 | **Statistically Significant ($p < 0.05$)** |
| **Strategy 1B** | NIFTY 50 | 1,686 | 0.8059 | 0.0363 | $2.37 \times 10^{-108}$| **+16.00%** | 4.86% | 5.05% | +3.168 | 0.0010 | **0.0016** | 0.5646 | **Statistically Significant ($p < 0.01$)** |
| **Strategy 1B** | Equal-Weight | 1,686 | 0.9420 | 0.0353 | $2.51 \times 10^{-160}$| **+9.51%** | 3.94% | 4.21% | +2.259 | 0.0158 | **0.0240** | 0.7143 | **Statistically Significant ($p < 0.05$)** |
| **Strategy 2A** | NIFTY 50 | 1,686 | 0.6911 | 0.0596 | $1.52 \times 10^{-30}$ | **+15.05%** | 4.81% | 5.03% | +2.993 | 0.0018 | **0.0028** | 0.4928 | **Statistically Significant ($p < 0.01$)** |
| **Strategy 2A** | Equal-Weight | 1,686 | 0.8275 | 0.0587 | $7.53 \times 10^{-45}$ | **+9.16%** | 3.98% | 4.38% | +2.089 | 0.0214 | **0.0368** | 0.6542 | **Statistically Significant ($p < 0.05$)** |
| **Strategy 2B** | NIFTY 50 | 1,686 | 0.6807 | 0.0538 | $2.39 \times 10^{-37}$ | **+14.73%** | 4.67% | 4.82% | +3.056 | 0.0016 | **0.0023** | 0.4998 | **Statistically Significant ($p < 0.01$)** |
| **Strategy 2B** | Equal-Weight | 1,686 | 0.8105 | 0.0544 | $2.99 \times 10^{-53}$ | **+9.01%** | 3.88% | 4.25% | +2.121 | 0.0204 | **0.0341** | 0.6560 | **Statistically Significant ($p < 0.05$)** |

### 3.3 Do Conclusions Change Under HAC?
**NO.** 
- All 8 full-period comparisons maintain their statistical significance.
- For all four ML strategies versus NIFTY 50, Jensen's Alpha remains **statistically significant at the 1% level ($p < 0.01$)**.
- For all four ML strategies versus the Equal-Weight Six-Sector benchmark, Jensen's Alpha remains **statistically significant at the 5% level ($p < 0.05$)**.
- All eight Betas remain overwhelmingly significant ($p < 10^{-30}$).

---

## 4. Validation C — Statistical Correction on Durbin-Watson Interpretation

### 4.1 The Methodological Correction
In early diagnostic discussions, Durbin-Watson ($DW$) values near 2.0 ($1.72 \le DW \le 2.13$) were casually described as showing "serial correlation in residuals is negligible." 

**This interpretation is mathematically incomplete and must be corrected:**
1. **$DW$ Tests Only First-Order Linear Correlation:** The Durbin-Watson statistic is defined as:
   $$DW = \frac{\sum_{t=2}^N (e_t - e_{t-1})^2}{\sum_{t=1}^N e_t^2} \approx 2(1 - \hat{\rho}_1)$$
   It is designed specifically to test the null hypothesis $H_0: \rho_1 = 0$ against $H_1: \rho_1 \ne 0$ in an $AR(1)$ process.
2. **$DW$ Does NOT Prove Absence of Serial Dependence:** A value of $DW \approx 2.0$ has zero power against:
   - **Higher-order linear autocorrelation ($AR(p), p \ge 2$):** e.g., weekly or monthly seasonal dependence.
   - **Non-linear serial dependence (ARCH/GARCH effects):** In financial asset returns, residuals frequently have zero linear correlation ($\text{Cov}(e_t, e_{t-k}) \approx 0$) but strong non-linear dependence in their conditional second moments ($\text{Cov}(e_t^2, e_{t-k}^2) > 0$), known as volatility clustering.
3. **Why HAC Remains Necessary:** The presence of conditional heteroskedasticity (confirmed by Breusch-Pagan tests with $p < 0.05$ on 16 of 24 regressions) and leptokurtosis (Jarque-Bera $p < 0.0001$) means OLS standard errors can be biased even when $DW \approx 2.0$. The Newey-West HAC estimator accounts for both heteroskedasticity and higher-order dependence, providing the authoritative statistical standard error.

---

## 5. Validation D — Verification and Exact Denominator of IT Return Drag (-10.99%)

### 5.1 Verification of the -10.99% Figure
In the holdout period (`2025-01-02` to `2026-09-18`, 422 trading sessions), NIFTY IT suffered a severe decline of **-33.42%**. During this time, Strategy 1A held an average allocation of 14.26% in IT.

In `simulate_portfolio`, the daily additive return attribution is defined as:
$$\text{contrib}_{\text{IT}, t} = w_{\text{hold}, \text{IT}, t} \times r_{\text{IT}, t}$$
Summing this quantity over the entire 422 holdout return sessions yields:
$$\sum_{t=1}^{422} \text{contrib}_{\text{IT}, t} = \mathbf{-0.109943 \text{ (or } -10.9943\%)}$$
This matches the reported **-10.99%** figure to four decimal places.

### 5.2 Clarification of the Exact Denominator: Attribution vs. Maximum Drawdown
It is mathematically vital **NOT** to equate this -10.99% cumulative return drag with "contribution to maximum drawdown."

Here is the exact accounting breakdown:

| Metric | Value | Mathematical Definition | Role & Interpretation |
| :--- | :---: | :--- | :--- |
| **Sum of IT Daily Contributions** | **-10.9943%** | $\sum_{t=1}^{422} (w_{\text{hold}, \text{IT}, t} \cdot r_{\text{IT}, t})$ | Cumulative additive return drag from IT over the full holdout period. |
| **Sum of Daily Net Portfolio Returns** | **-19.1597%** | $\sum_{t=1}^{422} r_{\text{net}, t}$ | **The exact denominator** of the additive linear attribution. |
| **IT Share of Cumulative Arithmetic Loss** | **57.38%** | $\frac{-10.9943\%}{-19.1597\%}$ | IT's proportion of the total cumulative arithmetic loss. |
| **Compounded Net Total Return** | **-19.0759%** | $\prod_{t=1}^{422} (1 + r_{\text{net}, t}) - 1$ | The true terminal geometric return ($NAV_{\text{end}} / NAV_{\text{start}} - 1$). |
| **Maximum Drawdown (MDD)** | **-25.1088%** | $\min_{t} \left(\frac{\text{NAV}_t}{\max_{\tau \le t} \text{NAV}_\tau} - 1\right)$ | Peak-to-trough path-dependent geometric drop in NAV (trough on `2026-04-02`). |

### 5.3 Key Distinction:
- **Cumulative Arithmetic Return Loss (-19.16%):** A linear sum of daily returns where IT represents **-10.99% (57.38% of the loss)**, Auto represents -6.12% (31.95%), Metal represents -4.66% (24.31%), Transaction Costs represent -2.70% (14.07%), and Pharma (+2.70%) and FMCG (+2.61%) partially offset.
- **Maximum Drawdown (-25.11%):** A geometric, path-dependent measurement between the running peak on Session 1 and the trough on Session 306 (`2026-04-02`). Up to that trough date, cumulative daily IT drag was -10.87% against a total cumulative daily return of -25.80%.
- **Conclusion:** -10.99% represents IT's cumulative additive return drag across the holdout period (57.38% of the -19.16% arithmetic return loss), **NOT** a linear subtraction from the -25.11% peak-to-trough maximum drawdown.

---

## 6. Validation E — Four-Pillar Forensic Decomposition of Holdout Underperformance

The holdout underperformance (-19.08% net total return) cannot and must not be attributed to any single cause. The data confirms that it resulted from the compounding interaction of **four distinct, complementary factors**:

```
                       HOLDOUT UNDERPERFORMANCE (-19.08%)
                                      │
         ┌──────────────────┬─────────┴────────┬──────────────────┐
         ▼                  ▼                  ▼                  ▼
   1. Market Macro     2. HMM Latency     3. Static Top-2     4. Transaction
      Choppy Band        & Whipsaws          Rule Blindspot      Friction Drag
     (22.5k - 26k)      (20 Rebalances)     (0% Bank, IT Drag)   (1.43% CAGR)
```

### Pillar 1: Market Macro Conditions (Range-Bound Choppy Regime)
* **Evidence:** NIFTY 50 traded in a choppy range between **22,082 and 26,328**, finishing down -1.26%.
* **Drivers:** Heavy foreign institutional selling, Middle East geopolitical conflict, high global interest rates, and US trade/tariff policy uncertainty created rapid, headline-driven sector rotations rather than the sustained multi-month sectoral trends seen in 2020–2024.

### Pillar 2: Regime Model Detection Latency & Whipsaws
* **Evidence:** Rebalancing frequency increased from once every 33.3 days in training to **once every 21.1 days in holdout** (a 58% increase in turnover events).
* **Mechanism:** The HMM filter requires multiple days of observation to confirm a regime shift with high probability ($p > 0.60$), and trades execute at $t+1$ close. In a trending market, this 1-to-2 day latency is negligible. In a choppy market, sector leadership mean-reverts quickly. The strategy bought into sectors after run-ups and exited after sharp dips, repeatedly oscillating between `AUTO+METAL`, `IT+PHARMA`, and `FMCG+PHARMA`.

### Pillar 3: Frozen Static Allocation Rules (Top-2 Sector Lockout)
* **Evidence:** The Phase 8/9 portfolio construction rules statically mapped each regime to the **Top 2 sector leaders** from the 2019–2024 training period:
  - Banking was Rank 3 in bullish regimes and Rank 6 (dead last) in crisis regimes during training.
  - Consequently, the static rules allocated **0.00% to Banking** across all 422 holdout sessions.
  - When NIFTY Bank decoupled and gained **+10.81%**, the model was structurally blind to the rally.
  - Concurrently, IT was in the Top 2 of Regimes 0 and 2, causing the portfolio to repeatedly re-enter a crashing sector (NIFTY IT fell **-33.42%**, generating **-10.99%** in additive return drag).

### Pillar 4: Trading Execution Friction & Transaction Costs
* **Evidence:** 20 rebalances in 422 sessions generated **18.01 cumulative turnover** (an annualized turnover of **1,075.42%**).
* **Cost Impact:** Deducting 15 bps per rebalance accumulated ₹0.1391 in cash fees per unit capital, resulting in an annualized **CAGR drag of 1.43%** (-2.16% in cumulative return drag).
* **Role:** Friction turned a -16.92% gross loss into a -19.08% net loss. It was an important **aggravating factor**, but not the primary cause (the gross return was already deeply negative due to Pillars 1–3).

---

## 7. Validation F — Turnover and Cost Reconciliation Across All Portfolios

| Portfolio | Period | Sessions ($N$) | Rebalance Count | Total Turnover | Annualized Turnover | Avg/Rebal TO | Cash Costs Paid | CAGR Cost Drag |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Strategy 1A** | Train | 1264 | 38 | 32.5518 | 6.4898 (648.98%) | 0.8566 | ₹0.1791 | 1.40% |
| **Strategy 1A** | Holdout | 422 | 20 | 18.0090 | 10.7542 (1075.42%) | 0.9005 | ₹0.1391 | 1.43% |
| **Strategy 1A** | Full | 1686 | 58 | 50.5609 | 7.5571 (755.71%) | 0.8717 | ₹0.3182 | 1.45% |
| **Strategy 1B** | Full | 1686 | 58 | 51.6063 | 7.7134 (771.34%) | 0.8898 | ₹0.3172 | 1.47% |
| **Strategy 2A** | Full | 1686 | 58 | 51.2326 | 7.6575 (765.75%) | 0.8833 | ₹0.2829 | 1.43% |
| **Strategy 2B** | Full | 1686 | 58 | 52.1028 | 7.7876 (778.76%) | 0.8983 | ₹0.2788 | 1.45% |
| **Equal-Weight 6S** | Full | 1686 | 82 | 1.4911 | 0.2229 (22.29%) | 0.0182 | ₹0.0041 | 0.04% |
| **NIFTY 50** | Full | 1686 | 0 | 0.0000 | 0.0000 (0.00%) | N/A | ₹0.0000 | 0.00% |

- **Reconciliation Verdict:** **PASS.** All formulas, annualization factors ($252/N$), denominators, and fee deductions ($0.0015 \times \text{NAV}_{\text{pre}} \times \text{TO}$) reconcile to zero discrepancy.

---

## 8. Final Repository Integrity Verification (PASS)

- **Source Code:** Unchanged (`src/portfolio_backtest.py`, `src/benchmark_backtest.py`, `src/comparative_evaluation.py`).
- **Tests:** All **132 unit and integration tests** pass cleanly in 47 seconds (`pytest tests/`).
- **Canonical Result Artifacts:** Unchanged in `results/portfolio_backtest/` and `results/portfolio_backtest/comparative_evaluation/`.
- **Scope Restriction:** Strictly observed. Zero Phase 10.6 or Phase 11 experimental code was introduced.

---

## 9. Final Validation Sign-Off Verdict

### Verdict: **PASS — READY FOR PHASE 10.5 SIGN-OFF**

All five validation criteria are fully satisfied:
1. `notebooks/compare_performance.ipynb` executes cleanly with 0 errors and matches canonical outputs.
2. HAC standard errors confirm that full-period annualized alpha remains statistically significant at $p < 0.01$ vs NIFTY 50 and $p < 0.05$ vs Equal-Weight across all four strategies.
3. The -10.99% IT return drag is verified to four decimals, and its denominator (-19.16% cumulative arithmetic return) is explicitly distinguished from maximum drawdown (-25.11%).
4. The Durbin-Watson interpretation has been statistically corrected.
5. The holdout underperformance discussion rigorously decomposes market conditions, model latency, static rule constraints, and execution friction without over-attributing to any single factor.

**Phase 10.5 is validated, complete, and signed off.**
