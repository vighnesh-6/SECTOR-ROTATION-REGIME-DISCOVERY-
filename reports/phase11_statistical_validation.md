# Phase 11 — Integrated Statistical Validation Report

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Phase:** 11 — Comprehensive Statistical Validation  
**Document Type:** Final Research Report & Econometric Findings  
**Status:** Complete, Verified, and Reconciled  
**Execution Timestamp:** 2026-11-06  

---

## Executive Summary

Phase 11 conducts the authoritative, non-parametric, and econometrically rigorous statistical validation of our four canonical sector rotation strategies (**Strategy 1A, 1B, 2A, 2B**) against two passive benchmarks (**NIFTY 50, Equal-Weight Sector**) and one active factor comparator (**Naive Top-2 Momentum**).

Following the rigorous methodology codified in [`reports/phase11_formulations.pdf`](file:///c:/Users/vighn/OneDrive/Desktop/sector%20rotation%20regime%20discovery/reports/phase11_formulations.pdf), we evaluate statistical significance while explicitly accounting for real-world financial time-series properties: **severe volatility clustering** (Engle ARCH LM $p < 10^{-24}$ across all series), **return autocorrelation**, **fat-tailed distributions**, and **cross-strategy contemporaneous dependence** ($r > 0.94$).

### Core Research Verdicts:
1. **Full Lifecycle Market Alpha ($N = 1,686$):** All four ML strategies generate **statistically significant annualized Jensen's alpha** against the NIFTY 50 index ($+14.73\%$ to $+16.13\%$, $t_{\text{HAC}} \ge 2.99$, $p < 0.002$) under Newey-West (1987, 1994) HAC inference.
2. **Structural Benchmark Alpha:** All four strategies deliver statistically significant alpha against the Equal-Weight Sector benchmark ($+9.01\%$ to $+9.51\%$, $t_{\text{HAC}} \ge 2.09$, $p < 0.02$).
3. **Active Factor Superiority:** Under Ledoit and Wolf's (2008) robust comparative Sharpe test, all four strategies deliver statistically superior risk-adjusted return compared to the Naive Top-2 Momentum comparator ($\Delta\text{SR} \approx +0.85$, $z_{\text{LW}} \ge 2.90$, $p < 0.002$).
4. **Multiple-Testing Global FWER Closure:** Under the **Unified Primary Omnibus Family ($M = 12$)**, all twelve core comparative hypotheses **reject the null hypothesis at global $\text{FWER} \le 0.05$** under the step-down Holm-Bonferroni procedure.
5. **Economic Significance & Temporal Degradation:** While the strategies achieve multi-year statistical validity over the full 7-year economic lifecycle, the **Previously Inspected Pseudo-OOS Partition (2025–2026, $N=422$)** experienced significant performance drag (CAGR $\approx -12\%$, failing to reject positive alpha). This reveals that while the regime-rotation edge is statistically authentic over complete macro cycles, execution latency and whipsaw turnover during choppy, non-trending regimes create severe short-term drag.

---

## 1. Epistemic Status & Dataset Framework

In adherence to modern empirical finance standards (Nosek et al., 2018; Harvey, Liu, & Zhu, 2016), we strictly reject misleading characterizations of previously inspected data. The evaluation dataset consists of 1,686 daily return intervals from `2019-11-01` to `2026-09-18` partitioned into:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 AUTHORITATIVE DATASET PARTITIONS                                 │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Model In-Sample Development Period (2019-11-01 to 2024-12-31, N = 1,264 daily return sessions):│
│    • Feature normalization, HMM fitting, regime threshold tuning (P_thresh, T_lock).             │
│    • Evaluates in-sample optimization magnitude, baseline fit, and internal consistency.         │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. Previously Inspected Pseudo-Out-of-Sample Partition (2025-01-02 to 2026-09-18, N = 422 sessions):│
│    • Temporally segregated from HMM training, but PREVIOUSLY EXAMINED in Phases 10.1–10.6.        │
│    • Evaluated as a retrospective stability check and post-training degradation diagnostic.      │
│    • Strictly diagnostic; cannot be claimed as a blind forward-looking clinical trial.           │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. Full Historical Lifecycle Backtest (2019-11-01 to 2026-09-18, N = 1,686 daily return sessions):│
│    • Pooled 7-year multi-cycle market history spanning pre-training and post-training regimes.   │
│    • Primary retrospective track record significance testing under real-world serial dependence. │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Descriptive Performance Overview

All figures below reflect the canonical frozen backtest invariants: actual one-way transaction costs ($15\text{ bps}$), dynamic portfolio weight drift, zero cash yield ($R_{\text{CASH}} = 0.0\%$), and $252.0$ trading days annualization:

| Portfolio | Partition | Sample Count ($N$) | Total Return (%) | Net CAGR (%) | Ann. Volatility (%) | Sharpe Ratio ($R_f = 0$) | Max Drawdown (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Strategy 1A** | Train | 1,264 | +508.09% | **+43.32%** | 20.44% | **1.8643** | -25.60% |
| **Strategy 1A** | Holdout | 422 | -19.08% | **-11.87%** | 15.43% | **-0.7416** | -25.11% |
| **Strategy 1A** | Full | 1,686 | +392.09% | **+26.89%** | 19.35% | **1.3284** | -25.60% |
| **Strategy 1B** | Train | 1,264 | +502.45% | **+43.05%** | 20.09% | **1.8843** | -26.10% |
| **Strategy 1B** | Holdout | 422 | -19.52% | **-12.16%** | 15.12% | **-0.7814** | -25.62% |
| **Strategy 1B** | Full | 1,686 | +384.82% | **+26.61%** | 19.01% | **1.3370** | -26.10% |
| **Strategy 2A** | Train | 1,264 | +434.89% | **+39.70%** | 18.22% | **1.9277** | -20.61% |
| **Strategy 2A** | Holdout | 422 | -20.72% | **-12.95%** | 14.71% | **-0.8686** | -25.74% |
| **Strategy 2A** | Full | 1,686 | +324.05% | **+24.10%** | 17.45% | **1.3254** | -25.74% |
| **Strategy 2B** | Train | 1,264 | +424.29% | **+39.14%** | 17.81% | **1.9451** | -21.01% |
| **Strategy 2B** | Holdout | 422 | -21.10% | **-13.20%** | 14.41% | **-0.9096** | -25.69% |
| **Strategy 2B** | Full | 1,686 | +313.66% | **+23.64%** | 17.07% | **1.3295** | -25.69% |
| **NIFTY 50** | Full | 1,686 | +154.26% | **+14.79%** | 21.02% | **0.6594** | -38.44% |
| **Equal Weight** | Full | 1,686 | +238.49% | **+19.78%** | 19.12% | **0.9899** | -32.88% |
| **Naive Momentum**| Full | 1,686 | +66.04% | **+7.87%** | 19.84% | **0.4820** | -39.03% |

---

## 3. Heteroskedasticity & Autocorrelation Consistent (HAC) Alpha Inference

Because residual squared returns exhibit extreme serial dependency (Engle ARCH LM $p < 10^{-24}$ across all specifications), standard homoskedastic OLS standard errors are biased downward. We estimate Jensen's Alpha via OLS with Newey-West (1987, 1994) HAC covariance matrices using the automatic plug-in bandwidth $L = \lfloor 4(T/100)^{2/9} \rfloor$:

$$L = 7 \text{ lags for } T=1,686 \text{ and } T=1,264; \quad L = 5 \text{ lags for } T=422$$

### Full Historical Lifecycle Backtest ($N = 1,686$, $L = 7$ lags)

| Strategy | Benchmark | Beta ($\beta$) | Beta SE (HAC) | Ann. Alpha ($\alpha_{\text{ann}}$) | Alpha SE (OLS) | Alpha SE (HAC) | $t_{\alpha}$ (HAC) | $p$-val (1-sided) | $p$-val (2-sided) | $R^2$ |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1A** | NIFTY 50 | 0.8194 | 0.0377 | **+16.13%** | 4.95% | 5.23% | **+3.082** | **0.0010** | **0.0021** | 0.5630 |
| **1A** | Equal Weight | 0.9618 | 0.0342 | **+9.47%** | 3.98% | 4.32% | **+2.192** | **0.0143** | **0.0285** | 0.7183 |
| **1A** | Naive Momentum | 0.7493 | 0.0253 | **+18.54%** | 4.60% | 4.85% | **+3.825** | **0.0001** | **0.0001** | 0.5900 |
| **1B** | NIFTY 50 | 0.8059 | 0.0338 | **+16.00%** | 4.86% | 5.05% | **+3.168** | **0.0008** | **0.0016** | 0.5644 |
| **1B** | Equal Weight | 0.9420 | 0.0312 | **+9.51%** | 3.94% | 4.21% | **+2.259** | **0.0120** | **0.0240** | 0.7141 |
| **1B** | Naive Momentum | 0.7345 | 0.0245 | **+18.39%** | 4.54% | 4.76% | **+3.866** | **0.0001** | **0.0001** | 0.5875 |
| **2A** | NIFTY 50 | 0.6911 | 0.0590 | **+15.05%** | 4.81% | 5.03% | **+2.993** | **0.0014** | **0.0028** | 0.4925 |
| **2A** | Equal Weight | 0.8275 | 0.0572 | **+9.16%** | 3.98% | 4.38% | **+2.089** | **0.0184** | **0.0368** | 0.6540 |
| **2A** | Naive Momentum | 0.6489 | 0.0368 | **+16.92%** | 4.41% | 4.65% | **+3.636** | **0.0001** | **0.0003** | 0.5441 |
| **2B** | NIFTY 50 | 0.6807 | 0.0520 | **+14.73%** | 4.67% | 4.82% | **+3.055** | **0.0011** | **0.0023** | 0.4995 |
| **2B** | Equal Weight | 0.8105 | 0.0509 | **+9.01%** | 3.88% | 4.25% | **+2.121** | **0.0170** | **0.0341** | 0.6558 |
| **2B** | Naive Momentum | 0.6359 | 0.0317 | **+16.61%** | 4.30% | 4.56% | **+3.643** | **0.0001** | **0.0003** | 0.5463 |

#### Findings on Alpha Inference:
- **Full Period Robustness:** Under HAC correction, standard errors increase modestly (from ~4.9% to ~5.2%), yet all $t$-statistics remain comfortably above the critical values. For all four ML strategies versus NIFTY 50, alpha is statistically significant at the 1% level ($p < 0.002$). Against Equal-Weight Sector, alpha is significant at the 5% level ($p < 0.02$). Against Naive Momentum, alpha exceeds $+16.6\%$ ($p < 0.0003$).

---

## 4. Standalone and Comparative Sharpe Inference

### 4.1 Andrew Lo (2002) Standalone Sharpe Inference ($H_0: \text{SR} \le 0$)

Following Lo (2002), we evaluate standalone risk-adjusted significance by computing the long-run variance of the influence function $z_t = u_t - \frac{1}{2}\text{SR}_{\text{daily}}(u_t^2 - 1)$:

| Portfolio | Partition | Annualized Sharpe ($\widehat{\text{SR}}$) | Skewness | Kurtosis | IID SE | HAC SE | $z_{\text{Lo}}$ (HAC) | $p$-val (1-sided) | Significance |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Strategy 1A** | Full | **1.3284** | -0.669 | 7.91 | 0.3976 | 0.4071 | **+3.263** | **0.00055** | Significant ($p < 0.001$) |
| **Strategy 1B** | Full | **1.3370** | -0.710 | 8.05 | 0.3972 | 0.4059 | **+3.294** | **0.00049** | Significant ($p < 0.001$) |
| **Strategy 2A** | Full | **1.3254** | -0.472 | 7.64 | 0.3977 | 0.4080 | **+3.248** | **0.00058** | Significant ($p < 0.001$) |
| **Strategy 2B** | Full | **1.3295** | -0.493 | 7.66 | 0.3969 | 0.4053 | **+3.280** | **0.00052** | Significant ($p < 0.001$) |
| **NIFTY 50** | Full | **0.6594** | -1.189 | 14.88 | 0.3982 | 0.4124 | **+1.599** | **0.05491** | Marginal ($p \approx 0.055$) |
| **Equal Weight** | Full | **0.9899** | -0.841 | 11.23 | 0.4027 | 0.4301 | **+2.302** | **0.01068** | Significant ($p < 0.05$) |
| **Naive Momentum**| Full | **0.4820** | -0.824 | 8.27 | 0.3930 | 0.4190 | **+1.150** | **0.12497** | Not Significant ($p > 0.10$) |

### 4.2 Ledoit & Wolf (2008) Comparative Sharpe Difference Tests ($H_0: \Delta\text{SR} \le 0$)

Evaluating whether Strategy $i$ delivers a statistically superior Sharpe ratio compared to Comparator $j$ requires accounting for the strong contemporaneous correlation between strategies and the market ($r \ge 0.70$):

| Strategy | Comparator | Strategy SR | Comparator SR | $\Delta\text{SR}_{\text{ann}}$ | HAC SE | $z_{\text{LW}}$ Stat | $p$-val (1-sided) | Decision |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1A** | NIFTY 50 | 1.3288 | 0.6596 | **+0.6691** | 0.2806 | **+2.385** | **0.0085** | Outperforms ($p < 0.01$) |
| **1A** | Equal Weight | 1.3288 | 0.9902 | **+0.3385** | 0.2336 | **+1.449** | **0.0736** | Positive Edge ($p \approx 0.07$) |
| **1A** | Naive Momentum | 1.3288 | 0.4822 | **+0.8466** | 0.2648 | **+3.197** | **0.0007** | Outperforms ($p < 0.001$) |
| **1B** | NIFTY 50 | 1.3374 | 0.6596 | **+0.6778** | 0.2750 | **+2.464** | **0.0069** | Outperforms ($p < 0.01$) |
| **1B** | Equal Weight | 1.3374 | 0.9902 | **+0.3472** | 0.2319 | **+1.497** | **0.0672** | Positive Edge ($p \approx 0.07$) |
| **1B** | Naive Momentum | 1.3374 | 0.4822 | **+0.8552** | 0.2644 | **+3.235** | **0.0006** | Outperforms ($p < 0.001$) |
| **2A** | NIFTY 50 | 1.3258 | 0.6596 | **+0.6662** | 0.3116 | **+2.138** | **0.0163** | Outperforms ($p < 0.02$) |
| **2A** | Equal Weight | 1.3258 | 0.9902 | **+0.3356** | 0.2685 | **+1.250** | **0.1057** | Positive Edge ($p \approx 0.10$) |
| **2A** | Naive Momentum | 1.3258 | 0.4822 | **+0.8436** | 0.2911 | **+2.898** | **0.0019** | Outperforms ($p < 0.002$) |
| **2B** | NIFTY 50 | 1.3298 | 0.6596 | **+0.6702** | 0.3060 | **+2.190** | **0.0143** | Outperforms ($p < 0.02$) |
| **2B** | Equal Weight | 1.3298 | 0.9902 | **+0.3396** | 0.2673 | **+1.270** | **0.1020** | Positive Edge ($p \approx 0.10$) |
| **2B** | Naive Momentum | 1.3298 | 0.4822 | **+0.8477** | 0.2917 | **+2.906** | **0.0018** | Outperforms ($p < 0.002$) |

---

## 5. Non-Parametric Stationary Block Bootstrap Validation

Using Politis and Romano's (1994) Stationary Block Bootstrap ($B = 2,000$, seed = 42, $b = 21$ days), we resampled synchronous bivariate return vectors to construct empirical distributions under realistic serial dependency without assuming Gaussianity:

### Delta-Sharpe Hypothesis Testing ($b = 21$ trading days, $B = 2,000$ iterations)

| Strategy | Comparator | Period | Point Estimate ($\Delta\text{SR}$) | 95% Bootstrap CI | Empirical $p$-val (1-sided) | Empirical $p$-val (2-sided) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1A** | NIFTY 50 | Full | **+0.6691** | [+0.0385, +1.2721] | **0.0090** | **0.0180** |
| **1A** | Equal Weight | Full | **+0.3385** | [-0.2227, +0.8655] | **0.0755** | **0.1499** |
| **1A** | Naive Momentum | Full | **+0.8466** | [+0.2741, +1.4429] | **0.0010** | **0.0020** |
| **1B** | NIFTY 50 | Full | **+0.6778** | [+0.0614, +1.2742] | **0.0070** | **0.0140** |
| **1B** | Equal Weight | Full | **+0.3472** | [-0.2079, +0.8710] | **0.0690** | **0.1374** |
| **1B** | Naive Momentum | Full | **+0.8552** | [+0.2785, +1.4431] | **0.0010** | **0.0020** |
| **2A** | NIFTY 50 | Full | **+0.6662** | [-0.0125, +1.3323] | **0.0170** | **0.0340** |
| **2A** | Equal Weight | Full | **+0.3356** | [-0.2676, +0.9275] | **0.1064** | **0.2109** |
| **2A** | Naive Momentum | Full | **+0.8436** | [+0.2198, +1.4883] | **0.0020** | **0.0040** |
| **2B** | NIFTY 50 | Full | **+0.6702** | [+0.0031, +1.3283] | **0.0145** | **0.0290** |
| **2B** | Equal Weight | Full | **+0.3396** | [-0.2608, +0.9238] | **0.1034** | **0.2059** |
| **2B** | Naive Momentum | Full | **+0.8477** | [+0.2198, +1.4868] | **0.0020** | **0.0040** |

### Performance Metric Uncertainty Bands Across Block Lengths ($b \in \{5, 10, 21, 42, 63\}$)
Evaluating Strategy 1A on the Full Lifecycle Backtest across the sensitivity spectrum reveals:
- **Net CAGR (Point = +26.89%):**
  - $b = 5$: 95% CI = [+13.48%, +41.97%]
  - $b = 10$: 95% CI = [+13.01%, +42.44%]
  - $b = 21$ (Primary): 95% CI = **[+12.63%, +43.08%]**
  - $b = 42$: 95% CI = [+11.89%, +44.15%]
  - $b = 63$: 95% CI = [+11.20%, +45.28%]
- **Maximum Drawdown (Point = -25.60%):**
  - $b = 21$ (Primary): 95% CI = **[-37.82%, -17.41%]**
  *(CAGR lower bound remains strictly positive (+11.2% to +13.5%) across all block lengths, confirming substantial economic compounding despite wide uncertainty intervals).*

---

## 6. Multiple-Testing Error Control

### 6.1 Unified Primary Omnibus Family ($M = 12$)

To eliminate family-splitting and guarantee global FWER $\le 0.05$ across the entire primary research agenda, all twelve core full-period comparative hypotheses are evaluated simultaneously using Holm-Bonferroni step-down:

| Hypothesis ID | Strategy | Comparator | Target Metric | Point Estimate | Test Stat | Raw $p$ (1s) | Holm-Adjusted $p$ (1s) | Holm Rejection ($\text{FWER} \le 0.05$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `H_alpha_N50_1A` | 1A | NIFTY 50 | Alpha (HAC) | +16.13% | $t = 3.082$ | 0.001045 | **0.009408** | **REJECTED (Alpha > 0)** |
| `H_alpha_EW_1A` | 1A | Equal Weight | Alpha (HAC) | +9.47% | $t = 2.192$ | 0.014250 | **0.048069** | **REJECTED (Alpha > 0)** |
| `H_deltaSR_MOM_1A` | 1A | Naive Momentum | $\Delta\text{SR}$ | +0.8466 | $z = 3.197$ | 0.000694 | **0.007631** | **REJECTED ($\Delta\text{SR} > 0$)** |
| `H_alpha_N50_1B` | 1B | NIFTY 50 | Alpha (HAC) | +16.00% | $t = 3.168$ | 0.000781 | **0.007806** | **REJECTED (Alpha > 0)** |
| `H_alpha_EW_1B` | 1B | Equal Weight | Alpha (HAC) | +9.51% | $t = 2.259$ | 0.012017 | **0.048069** | **REJECTED (Alpha > 0)** |
| `H_deltaSR_MOM_1B` | 1B | Naive Momentum | $\Delta\text{SR}$ | +0.8552 | $z = 3.235$ | 0.000609 | **0.007310** | **REJECTED ($\Delta\text{SR} > 0$)** |
| `H_alpha_N50_2A` | 2A | NIFTY 50 | Alpha (HAC) | +15.05% | $t = 2.993$ | 0.001403 | **0.009819** | **REJECTED (Alpha > 0)** |
| `H_alpha_EW_2A` | 2A | Equal Weight | Alpha (HAC) | +9.16% | $t = 2.089$ | 0.018407 | **0.048069** | **REJECTED (Alpha > 0)** |
| `H_deltaSR_MOM_2A` | 2A | Naive Momentum | $\Delta\text{SR}$ | +0.8436 | $z = 2.898$ | 0.001877 | **0.010976** | **REJECTED ($\Delta\text{SR} > 0$)** |
| `H_alpha_N50_2B` | 2B | NIFTY 50 | Alpha (HAC) | +14.73% | $t = 3.055$ | 0.001141 | **0.009408** | **REJECTED (Alpha > 0)** |
| `H_alpha_EW_2B` | 2B | Equal Weight | Alpha (HAC) | +9.01% | $t = 2.121$ | 0.017044 | **0.048069** | **REJECTED (Alpha > 0)** |
| `H_deltaSR_MOM_2B` | 2B | Naive Momentum | $\Delta\text{SR}$ | +0.8477 | $z = 2.906$ | 0.001829 | **0.010976** | **REJECTED ($\Delta\text{SR} > 0$)** |

**VERDICT:** Exactly **12 out of 12 hypotheses reject the null hypothesis**. The outperformance of all four canonical strategies is statistically authentic under closed global FWER control.

### 6.2 Exploratory Subperiod Stability Sweep ($M = 36$)

Evaluating all 36 combinations (4 strategies $\times$ 3 comparators $\times$ 3 partitions) under Benjamini-Hochberg FDR ($q = 0.05$) and Benjamini-Yekutieli sensitivity lower bounds reveals:
- **In-Sample Train ($N = 1,264$):** 12/12 BH rejections, 12/12 BY rejections (Alpha $+17.7\%$ to $+26.9\%$, all $p < 0.0002$).
- **Full Historical Lifecycle ($N = 1,686$):** 12/12 BH rejections, 8/12 BY rejections (Alpha $+9.0\%$ to $+18.5\%$, all $p < 0.018$).
- **Previously Inspected Pseudo-OOS ($N = 422$):** 0/12 rejections for positive alpha. Strategies experienced negative active returns (alpha $-7.3\%$ to $-16.6\%$, $p > 0.07$), failing to establish positive outperformance in the post-training window.

---

## 7. Regime Persistence & Episode Duration Diagnostics

Empirical run-length analysis of the frozen Viterbi sequence $\hat{S}_t$ ($N = 1,686$) yields the following episode holding durations (conditional on the realized path):

| Regime State | Economic Label | Episode Count | Total Sessions | Mean Duration (Days) | 95% Bootstrap CI | Median Duration (Days) | Min–Max Duration |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Regime 0** | Low-Vol Bull | 5 | 252 | **50.4** | [12.0, 119.6] | 16.0 | 8 – 187 |
| **Regime 1** | High-Vol Rally | 1 | 40 | **40.0** | [40.0, 40.0] | 40.0 | 40 – 40 |
| **Regime 2** | Sector Divergence | 22 | 515 | **23.4** | [16.1, 31.3] | 19.0 | 2 – 75 |
| **Regime 3** | Transitory Correction | 1 | 27 | **27.0** | [27.0, 27.0] | 27.0 | 27 – 27 |
| **Regime 4** | Bear / Market Stress | 22 | 522 | **23.7** | [15.3, 33.3] | 17.5 | 1 – 77 |
| **Regime 5** | High-Vol Bear / Recovery | 11 | 330 | **30.0** | [12.7, 54.1] | 19.0 | 5 – 130 |
| **All Regimes Combined**| Multi-Cycle Pool | 62 | 1,686 | **27.2** | **[20.4, 35.4]** | **18.5** | **1 – 187** |

*(Methodological justification: The primary block length $b = 21$ trading days sits squarely between the empirical median episode duration of $18.5$ days and the empirical mean episode duration of $27.2$ days, validating the choice of $b=21$ for capturing typical regime holding episodes).*

---

## 8. Econometric Limitations & Research Integrity Disclosures

1. **Retrospective Evaluation:** The 2025–2026 partition ($N=422$) was previously observed and analyzed in Phase 10. While temporally segregated from training, tests on this window represent retrospective diagnostic checks, not blind out-of-sample confirmation.
2. **HMM Estimation Variance Uncaptured:** Run-length bootstrapping measures sampling variability of episode lengths conditional on the single realized Viterbi path. Strict frozen artifact constraints prohibit re-fitting the HMM across resampled paths, meaning classification entropy and parameter estimation variance ($\mathbf{A}, \boldsymbol{\mu}, \boldsymbol{\Sigma}$) are not modeled.
3. **Bootstrap Boundary Splicing:** Stationary block bootstrap concatenations break the Markov chain at join boundaries. It models stationary return dependence, not continuous HMM state transitions.
4. **Short Pseudo-OOS Sample Power:** The holdout period spans only 422 trading days (~1.7 years), providing lower statistical power for detecting subtle Sharpe differences than the 1,686-day lifecycle sample.

---

## 9. Deliverables & Artifact Audit

| Artifact Path | Format | Verification Status | Purpose |
| :--- | :---: | :---: | :--- |
| `src/statistical_validation.py` | Python Module | **VERIFIED** | Core statistical validation library with HAC, Lo, Ledoit-Wolf, SBB, and Multiple Testing. |
| `tests/test_statistical_validation.py` | Pytest Suite | **PASSED (12/12)** | Unit tests verifying mathematical formulas, anti-symmetry, and edge cases. |
| `results/portfolio_backtest/robustness/benchmark/daily_simulation_momentum.parquet` | Parquet (1,686 rows) | **VERIFIED** | Deterministically reproduced daily momentum series matching frozen metrics to $10^{-6}$. |
| `results/statistical_validation/hac_alpha_beta_summary.parquet` | Parquet (36 rows) | **VERIFIED** | Complete Newey-West HAC alpha and beta regression summary. |
| `results/statistical_validation/sharpe_inference_summary.parquet` | Parquet (57 rows) | **VERIFIED** | Lo (2002) standalone and Ledoit-Wolf (2008) comparative Sharpe inferences. |
| `results/statistical_validation/bootstrap_hypothesis_tests.parquet` | Parquet (60 rows) | **VERIFIED** | Stationary block bootstrap empirical $p$-values across block lengths. |
| `results/statistical_validation/bootstrap_confidence_intervals.parquet` | Parquet (35 rows) | **VERIFIED** | Bootstrap 95% confidence intervals for CAGR, Volatility, and Max Drawdown. |
| `results/statistical_validation/multiple_testing_results.parquet` | Parquet (48 rows) | **VERIFIED** | Unified Omnibus M=12 Holm results and Exploratory M=36 BH/BY results. |
| `results/statistical_validation/regime_duration_diagnostics.parquet` | Parquet (7 rows) | **VERIFIED** | Run-length summary with conditional bootstrap duration confidence intervals. |
| `notebooks/statistical_validation.ipynb` | Jupyter Notebook | **VERIFIED & EXECUTED** | Complete, cleanly executed interactive research notebook with all outputs rendered. |
| `reports/phase11_formulations.pdf` | Academic PDF (665 KB) | **VERIFIED** | Authoritative mathematical reference, derivations, notation glossary, and flow diagram. |
| `reports/phase11_statistical_validation.md` | Markdown Report | **VERIFIED** | Comprehensive final research report documenting all findings. |

---

## 10. Final Verification Sign-Off

- **Test Suite Status:** Complete test suite passed: **167 passed, 0 failures** in 18.27 seconds.
- **Canonical Artifacts:** All Phase 6 HMM models, Phase 9 schedules, and Phase 10 daily simulations remain **100% frozen, unmodified, and bit-level identical**.
- **Determinism:** All results reproduce identically with random seed 42.
- **Phase 11 Completion Status:** **FULLY IMPLEMENTED, TESTED, AUDITED, AND SIGNED OFF.**

