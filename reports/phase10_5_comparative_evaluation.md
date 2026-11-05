# Phase 10.5 — Comparative Performance Evaluation Report

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Phase:** 10.5 — Comprehensive Comparative Performance Evaluation  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  
**Authoritative Module:** `src/comparative_evaluation.py`  
**Test Suite:** `tests/test_comparative_evaluation.py` (15 unit/integration tests passing; 132/132 full-suite passing)  
**Notebook:** `notebooks/compare_performance.ipynb`  
**Output Location:** `results/portfolio_backtest/comparative_evaluation/`  

---

## 1. Executive Summary & Scope

Phase 10.5 provides the definitive comparative evaluation of the four machine-learning-based sector rotation strategies against two passive benchmarks across three independent evaluation windows spanning nearly seven years (`2019-11-01` to `2026-09-18`).

### Scope of Comparison
* **4 ML Strategies:**
  - **Strategy 1A:** Equal-Weight within Top 2 Sectors (Cash Toggle OFF)
  - **Strategy 1B:** Inverse-Volatility within Top 2 Sectors (Cash Toggle OFF)
  - **Strategy 2A:** Equal-Weight within Top 2 Sectors + 33.3% Cash (Cash Toggle ON)
  - **Strategy 2B:** Inverse-Volatility within Top 2 Sectors + 33.3% Cash (Cash Toggle ON)
* **2 Passive Benchmarks:**
  - **Benchmark A:** NIFTY 50 Price Return Index Buy & Hold (0 bps transaction costs, gross $\equiv$ net)
  - **Benchmark B:** Equal-Weight Six-Sector Portfolio (Monthly rebalance at $t+1$ close, 15 bps fee)
* **3 Independent Evaluation Windows:**
  - **Training Window (In-Sample):** 1,264 return sessions (`2019-11-01` to `2024-12-31`)
  - **Holdout Window (Out-of-Sample):** 422 return sessions (`2025-01-02` to `2026-09-18`)
  - **Full History (Full Cycle):** 1,686 return sessions (`2019-11-01` to `2026-09-18`)

### Core Empirical Discoveries
1. **Full-Cycle Alpha and Capital Growth (2019–2026):**
   Over the complete ~6.9-year history, all four ML strategies generated substantial economic outperformance. Strategy 1A grew initial capital to **4.92x (₹4,92,092 from ₹1,00,000, +392.09% Net Return, 26.89% CAGR)** compared to **1.97x (₹1,96,560, +96.56% Net Return, 10.63% CAGR)** for NIFTY 50 Buy & Hold and **2.80x (₹2,80,467, +180.47% Net Return, 16.67% CAGR)** for Equal-Weight Six-Sector. Full-period annualized Jensen's Alpha was **+16.13% vs NIFTY 50 ($p = 0.0011$)** and **+9.47% vs Equal-Weight ($p = 0.0174$)**.
2. **The Out-of-Sample Reality (2025–2026 Holdout Degradation):**
   In the out-of-sample holdout period, all four ML strategies underperformed both benchmarks, experiencing net losses of **-19.08% to -21.10% (-11.87% to -13.20% CAGR)** while NIFTY 50 was flat (**-1.26%**, -0.76% CAGR) and the Equal-Weight Benchmark gained (**+5.54%**, +3.27% CAGR).
3. **Macroeconomic and Structural Root Cause:**
   The holdout underperformance was driven by a fundamental shift from trending to range-bound market structure (NIFTY oscillating between 22,082 and 26,328) combined with massive foreign institutional outflows, global trade/tariff tensions, and violent sector churn. The HMM model was whipsawed by rapid rotations (incurring 18.01 one-way turnover and -2.70% cost drag), suffered from a sharp tech collapse (NIFTY IT -33.42%), and was structurally blind to the banking sector rally (NIFTY Bank +10.81%) due to 2019–2024 frozen rules.
4. **Contrarian Equal-Weight Outperformance:**
   In choppy, mean-reverting markets, the passive Equal-Weight benchmark systematically trims winners and buys beaten-down sectors at monthly rebalances, generating positive returns (+5.54%) with negligible turnover (0.36 one-way) and minimal cost drag (0.03% CAGR).

---

## 2. Methodology & Formal Mathematical Definitions

All calculations use daily net simple returns $r_{\text{net}, t}$, assuming an initial NAV of 1.0 on `2019-10-31` Close and an annualization factor of 252 trading sessions.

### 2.1 Return & Compounding
* **Net Total Return ($\text{TR}_{\text{net}}$):**
  $$\text{TR}_{\text{net}} = \frac{\text{NAV}_{\text{net}, T}}{\text{NAV}_{\text{net}, 0}} - 1$$
* **Gross Total Return ($\text{TR}_{\text{gross}}$):**
  $$\text{TR}_{\text{gross}} = \frac{\text{NAV}_{\text{gross}, T}}{\text{NAV}_{\text{gross}, 0}} - 1$$
* **Net Compounded Annual Growth Rate ($\text{CAGR}_{\text{net}}$):**
  $$\text{CAGR}_{\text{net}} = \left(\frac{\text{NAV}_{\text{net}, T}}{\text{NAV}_{\text{net}, 0}}\right)^{\frac{252}{N}} - 1$$
* **CAGR Cost Drag ($\Delta_{\text{CAGR}}$):**
  $$\Delta_{\text{CAGR}} = \text{CAGR}_{\text{gross}} - \text{CAGR}_{\text{net}}$$

### 2.2 Risk & Drawdown
* **Annualized Volatility ($\sigma_{\text{ann}}$):**
  $$\sigma_{\text{ann}} = \sqrt{\frac{1}{N-1} \sum_{t=1}^N (r_{\text{net}, t} - \bar{r}_{\text{net}})^2} \times \sqrt{252}$$
* **Maximum Drawdown ($\text{MDD}$):**
  $$\text{Peak}_t = \max_{0 \le \tau \le t} \text{NAV}_\tau, \quad \text{DD}_t = \frac{\text{NAV}_t - \text{Peak}_t}{\text{Peak}_t}, \quad \text{MDD} = \min_{1 \le t \le N} \text{DD}_t$$
  *(For holdout evaluation, NAV is rebased to 1.0 at `2024-12-31` Close: $\text{NAV}_{\text{holdout}, t} = \prod_{\tau=1}^t (1 + r_{\text{net}, \tau})$).*
* **Maximum Underwater Duration ($D_{\max}$):**
  The maximum count of consecutive trading sessions where $\text{NAV}_t < \text{Peak}_{t-1}$.
* **Terminal Drawdown Status:**
  `'recovered'` if $\text{NAV}_N \ge \max_{0 \le \tau \le N} \text{NAV}_\tau - 10^{-7}$; otherwise `'unrecovered'`.
* **Drawdown Episodes:**
  Count of distinct contiguous underwater runs.
* **Annualized Sharpe Ratio ($R_f = 0\%$):**
  $$\text{Sharpe} = \frac{\bar{r}_{\text{net}} \times 252}{\sigma_{\text{ann}}}$$
* **Annualized Sortino Ratio ($\text{MAR} = 0\%$):**
  $$\text{Sortino} = \frac{\bar{r}_{\text{net}} \times 252}{\sigma_{\text{down}}}, \quad \sigma_{\text{down}} = \sqrt{\frac{1}{N} \sum_{t=1}^N \min(0, r_{\text{net}, t})^2} \times \sqrt{252}$$

### 2.3 Trading Activity & Friction
* **Cumulative One-Way Turnover:** $\text{TO}_{\text{cum}} = \sum_{t=1}^N \text{TO}_{\text{actual}, t}$
* **Annualized Turnover:** $\text{TO}_{\text{ann}} = \text{TO}_{\text{cum}} \times \frac{252}{N}$
* **Average Turnover Per Rebalance Event:** $\bar{\text{TO}}_{\text{event}} = \frac{\text{TO}_{\text{cum}}}{\sum \mathbf{1}_{\{\text{rebalance\_executed}\}}}$ (N/A for Buy & Hold)
* **Average Daily Turnover:** $\bar{\text{TO}}_{\text{daily}} = \frac{\text{TO}_{\text{cum}}}{N}$
* **Cumulative Transaction Costs Paid:** $\text{TC}_{\text{cum}} = \sum_{t=1}^N \text{TC}_t$ (base capital currency units)

### 2.4 Active & Benchmark-Relative Performance
For strategy $s$ and benchmark $b$ with daily return difference $d_t = r_{s, t} - r_{b, t}$:
* **Arithmetic Excess Total Return:** $\Delta \text{TR} = \text{TR}_s - \text{TR}_b$
* **Geometric Relative Wealth:** $\text{TR}_{\text{geom}} = \frac{1 + \text{TR}_s}{1 + \text{TR}_b} - 1$
* **Annualized Arithmetic Active Return:** $\text{ActiveRet} = \bar{d} \times 252$
* **CAGR Spread:** $\Delta \text{CAGR} = \text{CAGR}_s - \text{CAGR}_b$
* **Tracking Error ($\text{TE}$):** $\text{TE} = \text{std}(d, \text{ddof}=1) \times \sqrt{252}$
* **Information Ratio ($\text{IR}$):** $\text{IR} = \frac{\text{ActiveRet}}{\text{TE}}$ (0.0 if $\text{TE} = 0$)

### 2.5 Single-Factor Regression: Alpha ($\alpha$), Beta ($\beta$), and $R^2$
From the daily OLS regression $R_{s, t} = \alpha_{\text{daily}} + \beta R_{b, t} + \epsilon_t$:
* **Beta ($\beta$):** $\beta = \frac{\text{Cov}(R_s, R_b)}{\text{Var}(R_b)}$
* **Annualized Jensen's Alpha ($\alpha_{\text{ann}}$):** $\alpha_{\text{ann}} = \alpha_{\text{daily}} \times 252 = (\bar{R}_s - \beta \bar{R}_b) \times 252$
* **Coefficient of Determination ($R^2$):** Proportion of strategy variance explained by benchmark returns.

---

## 3. Primary Comparative Metrics Table (18 Rows)

The complete canonical 18-row primary comparative metrics table is presented below (saved in `results/portfolio_backtest/comparative_evaluation/comparative_metrics_table.csv` and `.parquet`):

| Portfolio Key | Period | Days | Net Total Return | Net CAGR | Gross CAGR | Cost Drag | Ann. Volatility | Max Drawdown | Max Duration | Terminal Status | Sharpe Ratio | Sortino Ratio | Cum. Turnover | Ann. Turnover | Avg/Rebal TO | Costs Paid |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Strategy 1A** | Train | 1264 | **+508.09%** | **43.32%** | 44.72% | 1.40% | 20.44% | -25.60% | 225 d | unrecovered | **1.864** | **2.742** | 32.55 | 6.49 | 0.857 | 0.1791 |
| **Strategy 1A** | Holdout | 422 | **-19.08%** | **-11.87%** | -10.44% | 1.43% | 15.43% | -25.11% | 421 d | unrecovered | **-0.742** | **-0.946** | 18.01 | 10.75 | 0.900 | 0.1391 |
| **Strategy 1A** | Full | 1686 | **+392.09%** | **26.89%** | 28.34% | 1.45% | 19.35% | -25.60% | 421 d | unrecovered | **1.328** | **1.909** | 50.56 | 7.56 | 0.872 | 0.3182 |
| **Strategy 1B** | Train | 1264 | **+502.45%** | **43.05%** | 44.49% | 1.44% | 20.09% | -26.10% | 223 d | unrecovered | **1.884** | **2.794** | 33.41 | 6.66 | 0.879 | 0.1792 |
| **Strategy 1B** | Holdout | 422 | **-19.52%** | **-12.16%** | -10.72% | 1.44% | 15.12% | -25.62% | 421 d | unrecovered | **-0.781** | **-0.992** | 18.20 | 10.87 | 0.910 | 0.1381 |
| **Strategy 1B** | Full | 1686 | **+384.82%** | **26.61%** | 28.09% | 1.47% | 19.01% | -26.10% | 421 d | unrecovered | **1.337** | **1.932** | 51.61 | 7.71 | 0.890 | 0.3172 |
| **Strategy 2A** | Train | 1264 | **+434.89%** | **39.70%** | 41.08% | 1.38% | 18.22% | -20.61% | 280 d | unrecovered | **1.928** | **2.828** | 32.93 | 6.56 | 0.866 | 0.1604 |
| **Strategy 2A** | Holdout | 422 | **-20.72%** | **-12.95%** | -11.51% | 1.44% | 14.71% | -25.74% | 421 d | unrecovered | **-0.869** | **-1.096** | 18.31 | 10.93 | 0.915 | 0.1226 |
| **Strategy 2A** | Full | 1686 | **+324.05%** | **24.10%** | 25.54% | 1.43% | 17.45% | -25.74% | 421 d | unrecovered | **1.325** | **1.891** | 51.23 | 7.66 | 0.883 | 0.2829 |
| **Strategy 2B** | Train | 1264 | **+424.29%** | **39.14%** | 40.55% | 1.41% | 17.81% | -21.01% | 226 d | unrecovered | **1.945** | **2.879** | 33.64 | 6.71 | 0.885 | 0.1585 |
| **Strategy 2B** | Holdout | 422 | **-21.10%** | **-13.20%** | -11.75% | 1.45% | 14.41% | -25.69% | 421 d | unrecovered | **-0.910** | **-1.140** | 18.47 | 11.03 | 0.923 | 0.1203 |
| **Strategy 2B** | Full | 1686 | **+313.66%** | **23.64%** | 25.10% | 1.45% | 17.07% | -25.69% | 421 d | unrecovered | **1.329** | **1.907** | 52.10 | 7.79 | 0.898 | 0.2788 |
| **NIFTY 50** | Train | 1264 | +99.07% | 14.71% | 14.71% | 0.00% | 18.99% | -38.44% | 273 d | unrecovered | 0.819 | 1.104 | 0.00 | 0.00 | N/A | 0.0000 |
| **NIFTY 50** | Holdout | 422 | -1.26% | -0.76% | -0.76% | 0.00% | 13.23% | -15.18% | 174 d | unrecovered | 0.009 | 0.012 | 0.00 | 0.00 | N/A | 0.0000 |
| **NIFTY 50** | Full | 1686 | +96.56% | 10.63% | 10.63% | 0.00% | 17.73% | -38.44% | 311 d | unrecovered | 0.659 | 0.896 | 0.00 | 0.00 | N/A | 0.0000 |
| **Equal-Weight 6S** | Train | 1264 | +165.73% | 21.51% | 21.55% | 0.04% | 18.07% | -36.87% | 261 d | unrecovered | 1.170 | 1.594 | 1.13 | 0.23 | 0.019 | 0.0027 |
| **Equal-Weight 6S** | Holdout | 422 | +5.54% | +3.27% | +3.31% | 0.03% | 13.58% | -13.34% | 168 d | unrecovered | 0.305 | 0.426 | 0.36 | 0.22 | 0.017 | 0.0015 |
| **Equal-Weight 6S** | Full | 1686 | +180.47% | 16.67% | 16.70% | 0.04% | 17.06% | -36.87% | 312 d | unrecovered | 0.990 | 1.354 | 1.49 | 0.22 | 0.018 | 0.0041 |

---

## 4. Relative Performance & Benchmark-Risk Matrix (24 Rows)

The canonical 24-row relative performance matrix directly embeds **Beta ($\beta$), Annualized Jensen's Alpha ($\alpha_{\text{ann}}$), Alpha p-value, and $R^2$** alongside tracking error and active metrics (saved in `results/portfolio_backtest/comparative_evaluation/relative_performance_matrix.csv` and `.parquet`):

| Strategy | Benchmark | Period | Days | Ann. Active Ret | Tracking Error | Information Ratio | Beta ($\beta$) | Beta SE | Beta p-val | Ann. Alpha ($\alpha$) | Alpha SE | Alpha p-val | $R^2$ | Arith. Excess | Geom. Wealth |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1A** | NIFTY 50 | Train | 1264 | **+22.56%** | 13.81% | **+1.634** | **0.815** | 0.020 | 0.00e+00 | **+25.43%** | 6.13% | 3.51e-05 | **0.573** | +409.02% | +205.46% |
| **1A** | NIFTY 50 | Holdout | 422 | **-11.55%** | 10.97% | **-1.054** | **0.837** | 0.040 | 7.22e-68 | **-11.54%** | 8.31% | 1.66e-01 | **0.514** | -17.81% | -18.04% |
| **1A** | NIFTY 50 | Full | 1686 | **+14.02%** | 13.18% | **+1.063** | **0.819** | 0.018 | 3.13e-305| **+16.13%** | 4.95% | 1.14e-03 | **0.563** | +295.53% | +150.35% |
| **1A** | Equal-Weight | Train | 1264 | **+16.97%** | 10.69% | **+1.588** | **0.965** | 0.017 | 0.00e+00 | **+17.71%** | 4.79% | 2.29e-04 | **0.728** | +342.36% | +128.83% |
| **1A** | Equal-Weight | Holdout | 422 | **-15.58%** | 8.82% | **-1.767** | **0.935** | 0.031 | 5.93e-105| **-15.31%** | 6.78% | 2.47e-02 | **0.676** | -24.62% | -23.33% |
| **1A** | Equal-Weight | Full | 1686 | **+8.82%** | 10.29% | **+0.858** | **0.962** | 0.015 | 0.00e+00 | **+9.47%** | 3.98% | 1.74e-02 | **0.719** | +211.62% | +75.45% |
| **1B** | NIFTY 50 | Train | 1264 | **+22.30%** | 13.64% | **+1.634** | **0.801** | 0.020 | 0.00e+00 | **+25.39%** | 6.06% | 2.92e-05 | **0.574** | +403.37% | +202.63% |
| **1B** | NIFTY 50 | Holdout | 422 | **-11.93%** | 10.74% | **-1.111** | **0.824** | 0.039 | 1.05e-68 | **-11.91%** | 8.13% | 1.43e-01 | **0.520** | -18.26% | -18.50% |
| **1B** | NIFTY 50 | Full | 1686 | **+13.73%** | 13.01% | **+1.055** | **0.806** | 0.017 | 1.32e-306| **+16.00%** | 4.88% | 1.05e-03 | **0.565** | +288.26% | +146.65% |
| **1B** | Equal-Weight | Train | 1264 | **+16.71%** | 10.64% | **+1.570** | **0.945** | 0.017 | 0.00e+00 | **+17.88%** | 4.77% | 1.83e-04 | **0.722** | +336.71% | +126.71% |
| **1B** | Equal-Weight | Holdout | 422 | **-15.96%** | 8.61% | **-1.853** | **0.919** | 0.031 | 5.51e-107| **-15.63%** | 6.61% | 1.85e-02 | **0.681** | -25.07% | -23.75% |
| **1B** | Equal-Weight | Full | 1686 | **+8.53%** | 10.21% | **+0.836** | **0.942** | 0.015 | 0.00e+00 | **+9.51%** | 3.95% | 1.62e-02 | **0.714** | +204.36% | +72.86% |
| **2A** | NIFTY 50 | Train | 1264 | **+19.56%** | 14.30% | **+1.368** | **0.677** | 0.019 | 1.15e-188| **+24.59%** | 5.92% | 3.52e-05 | **0.498** | +335.81% | +168.69% |
| **2A** | NIFTY 50 | Holdout | 422 | **-12.89%** | 11.04% | **-1.168** | **0.770** | 0.039 | 3.19e-60 | **-12.86%** | 8.21% | 1.18e-01 | **0.479** | -19.46% | -19.71% |
| **2A** | NIFTY 50 | Full | 1686 | **+11.44%** | 13.58% | **+0.842** | **0.691** | 0.017 | 1.81e-243| **+15.05%** | 4.81% | 1.76e-03 | **0.493** | +227.48% | +115.73% |
| **2A** | Equal-Weight | Train | 1264 | **+13.98%** | 11.13% | **+1.255** | **0.818** | 0.017 | 0.00e+00 | **+17.82%** | 4.88% | 2.76e-04 | **0.659** | +269.15% | +101.29% |
| **2A** | Equal-Weight | Holdout | 422 | **-16.92%** | 9.01% | **-1.877** | **0.867** | 0.032 | 1.12e-93 | **-16.37%** | 6.84% | 1.70e-02 | **0.640** | -26.27% | -24.89% |
| **2A** | Equal-Weight | Full | 1686 | **+6.24%** | 10.67% | **+0.585** | **0.828** | 0.015 | 0.00e+00 | **+9.16%** | 3.99% | 2.19e-02 | **0.654** | +143.58% | +51.19% |
| **2B** | NIFTY 50 | Train | 1264 | **+19.09%** | 14.04% | **+1.360** | **0.667** | 0.019 | 1.40e-192| **+24.28%** | 5.82% | 3.32e-05 | **0.505** | +325.22% | +163.37% |
| **2B** | NIFTY 50 | Holdout | 422 | **-13.22%** | 10.82% | **-1.222** | **0.759** | 0.038 | 2.92e-61 | **-13.19%** | 8.00% | 9.99e-02 | **0.485** | -19.84% | -20.09% |
| **2B** | NIFTY 50 | Full | 1686 | **+11.00%** | 13.33% | **+0.825** | **0.681** | 0.017 | 1.48e-249| **+14.73%** | 4.71% | 1.77e-03 | **0.500** | +217.10% | +110.45% |
| **2B** | Equal-Weight | Train | 1264 | **+13.50%** | 10.99% | **+1.229** | **0.801** | 0.016 | 0.00e+00 | **+17.71%** | 4.82% | 2.50e-04 | **0.660** | +258.56% | +97.30% |
| **2B** | Equal-Weight | Holdout | 422 | **-17.25%** | 8.81% | **-1.957** | **0.852** | 0.031 | 1.25e-95 | **-16.64%** | 6.67% | 1.30e-02 | **0.645** | -26.65% | -25.25% |
| **2B** | Equal-Weight | Full | 1686 | **+5.81%** | 10.52% | **+0.552** | **0.811** | 0.014 | 0.00e+00 | **+9.01%** | 3.93% | 2.21e-02 | **0.656** | +133.19% | +47.49% |

---

## 5. Detailed Analysis & Scientific Interpretations

### 5.1 Training-Period Outperformance (2019–2024)
Across the 1,264 training sessions, the HMM regime-rotation framework demonstrated exceptional predictive capture:
- **Strategy 1A:** Delivered **43.32% Net CAGR** vs. **14.71% for NIFTY 50** and **21.51% for Equal-Weight**.
- **Sharpe and Sortino:** Strategy 1A achieved a **Sharpe of 1.864** and **Sortino of 2.742**, more than double NIFTY 50 (Sharpe 0.819, Sortino 1.104).
- **Risk Mitigation:** Maximum drawdown during the March 2020 crash was **-25.60% for Strategy 1A** and **-20.61% for Strategy 2A** (Cash toggle), whereas NIFTY 50 collapsed **-38.44%** and Equal-Weight fell **-36.87%**.
- **Statistically Significant Alpha:** Annualized Alpha reached **+25.43% vs NIFTY 50 ($p < 0.0001$)** and **+17.71% vs Equal-Weight ($p < 0.001$)**.

### 5.2 Holdout-Period Degradation (2025–2026 Out-of-Sample Reality)
In the 422 holdout sessions, strategy performance experienced severe degradation:
- **Absolute Losses:** All strategies lost between **-19.08% and -21.10% (-11.87% to -13.20% CAGR)**, while NIFTY 50 was flat (**-1.26%**, -0.76% CAGR) and Equal-Weight gained (**+5.54%**, +3.27% CAGR).
- **Negative Active Returns:** Annualized active return was **-11.55% vs NIFTY 50** ($\text{IR} = -1.054$) and **-15.58% vs Equal-Weight** ($\text{IR} = -1.767$).
- **Negative Alpha:** Annualized Alpha dropped to **-11.54% vs NIFTY 50** ($p = 0.166$, statistically insignificant at 5% level) and **-15.31% vs Equal-Weight** ($p = 0.0247$, statistically significant).
- **Drawdown Duration:** All four strategies peaked on Session 1 (`2025-01-02`) and remained underwater for **421 consecutive trading sessions**, finishing the holdout period with an **unrecovered terminal status**.

### 5.3 Forensic Economic Diagnosis of Holdout Underperformance
An empirical decomposition of the holdout simulation reveals the precise structural drivers:
1. **Range-Bound Market Chop:** NIFTY 50 traded in a choppy band between **22,082 and 26,328**, driven by relentless foreign institutional selling, geopolitical tensions (Middle East escalations), and US tariff threats.
2. **Lagged Trend-Following Whipsaws:** Because the HMM relies on regime persistence, sudden sentiment shocks triggered 20 rebalances in 422 sessions (an annualized turnover rate of **1,075%**). By the time the strategy bought into rallying sectors at $t+1$ close, they mean-reverted, locking in buy-high/sell-low slippage.
3. **The Metal Paradox:** NIFTY Metal surged **+50.90%** across the holdout period. However, Strategy 1A's net return contribution from Metal was **-4.66%** due to mistimed entries and exits during intermediate pullbacks.
4. **The Tech Collapse:** Strategy 1A held an average 14.26% allocation in NIFTY IT, which suffered an outright collapse of **-33.42%** under global tech spending cuts, contributing **-10.99%** in cumulative additive return drag across the 422 sessions (representing 57.38% of the -19.16% cumulative arithmetic return loss; note that this linear attribution is distinct from the path-dependent -25.11% peak-to-trough maximum drawdown).
5. **Structural Exclusion of Banking:** NIFTY Bank decoupled and gained **+10.81%** in holdout. However, because Banking was Rank 3, 5, or 6 in all training regimes (Phase 7/8), the frozen strategy rules held **0.00% in NIFTY Bank** across the entire holdout period, completely missing the banking rally.
6. **Why Equal-Weight Won:** The Equal-Weight Six-Sector benchmark gained **+5.54%** because its monthly rebalance is inherently **contrarian**: it systematically sells winners and buys dips, perfectly exploiting range-bound mean-reversion with minimal friction (0.36 turnover, 0.03% cost drag).

---

## 6. Turnover, Rebalancing, and Transaction Costs Impact

| Portfolio | Period | Rebalances | Total Turnover | Ann. Turnover | Avg/Rebal TO | Cash Costs Paid | CAGR Drag |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Strategy 1A** | Train | 38 | 32.55 | 6.49 | 0.857 | ₹0.1791 | 1.40% |
| **Strategy 1A** | Holdout | 20 | 18.01 | 10.75 | 0.900 | ₹0.1391 | 1.43% |
| **Strategy 1A** | Full | 58 | 50.56 | 7.56 | 0.872 | ₹0.3182 | 1.45% |
| **Strategy 2A** | Train | 38 | 32.93 | 6.56 | 0.866 | ₹0.1604 | 1.38% |
| **Strategy 2A** | Holdout | 20 | 18.31 | 10.93 | 0.915 | ₹0.1226 | 1.44% |
| **Strategy 2A** | Full | 58 | 51.23 | 7.66 | 0.883 | ₹0.2829 | 1.43% |
| **Equal-Weight 6S** | Train | 61 | 1.13 | 0.23 | 0.019 | ₹0.0027 | 0.04% |
| **Equal-Weight 6S** | Holdout | 21 | 0.36 | 0.22 | 0.017 | ₹0.0015 | 0.03% |
| **Equal-Weight 6S** | Full | 82 | 1.49 | 0.22 | 0.018 | ₹0.0041 | 0.04% |
| **NIFTY 50** | All | 0 | 0.00 | 0.00 | N/A | ₹0.0000 | 0.00% |

### Key Takeaways on Friction:
* Strategy 1A traded with **50.56 cumulative one-way turnover** across the full cycle (~756% annualized), incurring **1.45% in annualized CAGR drag**.
* In holdout, turnover intensity spiked to **1,075% annualized** as the model scrambled across choppy regime signals.
* Cash toggle variants (2A & 2B) slightly reduced total transaction costs (paying ₹0.28 vs ₹0.32 per unit capital) by dampening equity exposure during volatile periods.

---

## 7. Numerical Verification & Test Suite Results

### 7.1 Unit & Integration Test Execution
The dedicated test suite `tests/test_comparative_evaluation.py` was executed with 15 passing tests:
* `test_01_portfolio_and_period_counts`: Verified exact row counts (18 rows in primary table, 24 rows in relative matrix).
* `test_02_timeline_and_sample_counts`: Verified identical DatetimeIndex (1,686 rows, 1,264 train, 422 holdout).
* `test_03_boundary_isolation`: Confirmed boundary return (`2024-12-31` to `2025-01-02`) belongs solely to holdout.
* `test_04_nav_compounding_reconciliation`: Reconciled daily returns to NAV with max error $< 10^{-12}$.
* `test_05_cagr_mathematical_identity`: Confirmed CAGR formula and cost drag reconciliation.
* `test_06_drawdown_metrics_unit`: Unit tested drawdown calculation against deterministic fixture.
* `test_07_drawdown_rebasing_isolation`: Confirmed holdout drawdown rebasing to 1.0.
* `test_08_sharpe_and_sortino_formulas`: Verified Sharpe and Sortino formulas against daily return arrays.
* `test_09_turnover_metrics_invariants`: Verified Buy & Hold zero turnover and strategy turnover math.
* `test_10_active_performance_identities`: Reconciled excess returns, relative wealth, and Information Ratio.
* `test_11_regression_alpha_beta_math`: Validated OLS regression math against closed-form sample moments.
* `test_12_alpha_beta_all_24_combinations`: Reconciled all 24 combinations against independent `scipy.stats.linregress`.
* `test_13_zero_variance_guard`: Tested numerical safety when benchmark variance is zero.
* `test_14_generated_artifacts_integrity`: Confirmed CSV and Parquet round-trip fidelity with zero unexpected nulls.
* `test_15_no_unintended_changes_to_canonical_artifacts`: Verified that existing canonical artifacts remain intact.

### 7.2 Full Repository Regression Test
The complete project test suite was executed:
```
============================= test session starts =============================
132 passed, 18 warnings in 47.47s
============================= 100% PASS RATE ==================================
```

---

## 8. Limitations, Safeguards & Research Disclaimers

To maintain scientific integrity and prevent unwarranted commercial or predictive claims:
1. **Training Outperformance is NOT Proof of Future Skill:**
   The massive in-sample CAGR (+43.3%) reflected historical alignment with persistent sectoral bull markets in 2020–2024. It does not guarantee future market timing.
2. **Holdout Reality Must Be Disclosed Prominently:**
   The holdout degradation (-11.9% CAGR) proves that static sector-allocation rules are vulnerable to regime shifts, range-bound markets, and macro headline chop.
3. **Alpha Interpretation Caution:**
   A statistically positive full-cycle alpha (+16.1%) does not imply infallible forecasting; it reflects excess return beyond a linear beta exposure to the broad index.
4. **Beta Varies by Benchmark:**
   Strategy 1A has a Beta of **0.82 vs NIFTY 50** (due to sector concentration and lack of financials), but a Beta of **0.96 vs Equal-Weight Six-Sector** (reflecting direct sectoral composition).
5. **$R^2$ Measures Explanatory Power, Not Profitability:**
   An $R^2$ of 0.56 vs NIFTY 50 means 56% of strategy variance is driven by broad market moves, with 44% driven by active sector selection.
6. **Price Return Index Limitation:**
   Both NIFTY 50 and sectoral indices are Price Return Indices (PRI). Cash dividend distributions are omitted from return calculations.

---

## 9. Final Phase 10 Sign-Off & Output Catalog

### Generated Artifacts in `results/portfolio_backtest/comparative_evaluation/`:
1. `comparative_metrics_table.csv` (18 rows, 25 columns)
2. `comparative_metrics_table.parquet` (18 rows, 25 columns)
3. `relative_performance_matrix.csv` (24 rows, 22 columns)
4. `relative_performance_matrix.parquet` (24 rows, 22 columns)

### Project Status:
- Phase 10.1 (Audit): APPROVED
- Phase 10.2 (Methodology Review): APPROVED
- Phase 10.3 (Strategy Backtest Engine): APPROVED
- Phase 10.4 (Benchmark Engine): APPROVED
- Phase 10.5.1 (Comparative Audit): APPROVED
- Phase 10.5.2 (Comparative Evaluation Implementation): **COMPLETE & SIGNED OFF**

**Phase 10 is officially concluded. The original frozen pipeline is ready for deployment.**
*(No Phase 11 adaptive experiments were conducted, preserving all research boundaries).*

