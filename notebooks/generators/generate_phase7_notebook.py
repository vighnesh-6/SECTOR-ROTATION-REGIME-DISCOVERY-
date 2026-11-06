"""
generate_phase7_notebook.py
===========================
Generates and executes notebooks/07_regime_characterisation.ipynb cleanly.
"""

from pathlib import Path
import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

def create_and_run_notebook():
    project_root = Path.cwd().resolve()
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {"display_name": "base", "language": "python", "name": "python3"},
        "language_info": {
            "name": "python",
            "version": "3.13.5",
            "mimetype": "text/x-python",
            "codemirror_mode": {"name": "ipython", "version": 3},
            "pygments_lexer": "ipython3",
        },
    }

    cells = []

    # Cell 0: Header
    cells.append(nbf.v4.new_markdown_cell(
"""# Phase 7 — Regime Characterisation & Sector Performance Analysis
**Project:** Sector Rotation Regime Discovery — Indian Equity Market  
**Target:** Explain discovered regimes economically, measure conditional sector performance, evaluate major event associations, and synthesize cross-model findings without look-ahead bias.

### Core Objectives:
1. **Regime Characterisation:** Quantify occupancy, persistence, episode run-lengths, switching frequency, market trend, volatility (India VIX), and trailing sector context for K-Means ($K=4$), GMM ($K=2$), and HMM ($K=6$). Assign concise, evidence-based economic names with documented caveats. Separate training (2019–2024) and protected holdout (2025–2026).
2. **HMM Label Separation:** Explicitly distinguish real-time causal (`filtered_causal`) labels from smoothed retrospective (`retrospective_viterbi`) labels. Enforce causal labels for all decision-relevant insights.
3. **Sector Performance & Leadership:** Measure contemporaneous daily returns and forward 20-day returns against NIFTY 50 across all six sectors (`AUTO`, `BANK`, `FMCG`, `IT`, `METAL`, `PHARMA`). Identify historical leaders, laggards, and defensive candidates with sample size and episode counts.
4. **Major-Event Analysis:** Align major events (2019–2026) to trading days, construct deduplicated event windows, and compare regime frequencies and sector excess returns against a non-event baseline.
5. **Cross-Model Comparison:** Synthesize robust commonalities, model-specific divergences, and carry forward Phase 6 stability evidence."""
    ))

    # Cell 1: Environment Setup Markdown
    cells.append(nbf.v4.new_markdown_cell("## 0. Environment Setup & Imports"))

    # Cell 2: Imports Code
    cells.append(nbf.v4.new_code_cell(
"""import sys
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Ensure project root is in sys.path
notebook_dir = Path.cwd()
project_root = notebook_dir.parent if notebook_dir.name == "notebooks" else notebook_dir
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.regime_characterisation import (
    SECTOR_NAMES,
    BENCHMARK_NAME,
    REGIME_INTERPRETATIONS,
    load_regime_labels,
    load_clean_prices_and_returns,
    calculate_regime_episodes,
    compute_model_regime_profiles,
    compute_sector_performance_by_regime,
    identify_sector_leadership,
    load_and_align_events,
    build_event_windows,
    analyze_event_regime_associations,
    analyze_sector_performance_during_events,
    generate_cross_model_comparison,
    compute_hmm_holdout_sector_correlations,
    plot_hmm_holdout_sector_correlations,
    run_phase7_pipeline,
)

# Styling configuration
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["figure.titlesize"] = 14
plt.rcParams["axes.titlesize"] = 12

print("Environment setup complete. Matplotlib & Seaborn configured.")"""
    ))

    # Cell 3: Data Verification Markdown
    cells.append(nbf.v4.new_markdown_cell(
"""## 1. Data Setup & Split Verification
Loads Phase 6 final regime labels, unscaled master features, and aligned sector/NIFTY 50 prices.  
Verifies strict temporal split boundaries:
- **Training Pool:** 1,265 observations (2019-10-31 to 2024-12-31)
- **Protected Holdout:** 422 observations (2025-01-02 to 2026-09-18)"""
    ))

    # Cell 4: Data Verification Code
    cells.append(nbf.v4.new_code_cell(
"""data_dir = project_root / "data"
results_dir = project_root / "results"

# Ensure organized subdirectories exist
for subdir in [
    "regime_characterization/regime_profiles",
    "regime_characterization/sector_performance",
    "regime_characterization/sector_leadership",
    "regime_characterization/correlations",
    "event_analysis",
    "reports",
]:
    (results_dir / subdir).mkdir(parents=True, exist_ok=True)

# 1. Load Labels
labels_df = load_regime_labels(str(results_dir))
print(f"Total regime label rows : {len(labels_df)} (4 streams x 1,687 dates)")

# 2. Load Prices & Returns
price_df, daily_returns, fwd_20d_returns = load_clean_prices_and_returns(str(data_dir))
print(f"Price dataset shape     : {price_df.shape} (NIFTY50 + 6 sectors)")
print(f"Daily returns shape     : {daily_returns.shape}")
print(f"Forward 20D returns     : {fwd_20d_returns.shape}")

# 3. Load Master Features (Phase 3 unscaled 42 features)
from src.normalization import load_master_feature_dataset
master_features = load_master_feature_dataset(str(data_dir))
print(f"Master features shape   : {master_features.shape} (42 approved features)")

# Verify split boundary integrity
train_labels = labels_df[labels_df["period"] == "train"]
holdout_labels = labels_df[labels_df["period"] == "holdout"]
print(f"Training dates          : {train_labels['Date'].min().date()} to {train_labels['Date'].max().date()} ({train_labels['Date'].nunique()} days)")
print(f"Holdout dates           : {holdout_labels['Date'].min().date()} to {holdout_labels['Date'].max().date()} ({holdout_labels['Date'].nunique()} days)")
assert train_labels["Date"].nunique() == 1265, "Expected exactly 1265 training days"
assert holdout_labels["Date"].nunique() == 422, "Expected exactly 422 holdout days"
print("Split boundaries verified clean.")"""
    ))

    # Cell 5: Regime Characterisation Markdown
    cells.append(nbf.v4.new_markdown_cell(
r"""## 2. Model Regime Profiling & Evidence-Based Economic Naming

Every regime for each candidate model is analyzed independently.
- **K-Means ($K=4$, RobustScaler):** Baseline geometric clusterer.
- **GMM ($K=2$, Full Covariance):** Probabilistic density model.
- **Gaussian HMM ($K=6$, Diagonal Covariance):** Temporal Markov regime model.

### Key Audit Findings & Ground Truths:
1. **HMM Primary Standard:** Causal forward-filtered probabilities $P(s_t \mid o_1, \dots, o_t)$ are strictly separated from retrospective Viterbi sequences to eliminate look-ahead bias.
2. **GMM Holdout State Collapse:** GMM assigned 100% (422/422 days) of holdout data to Regime 0. Its second state was a one-time COVID shock detector (64 days in 2020) that never recurred.
3. **HMM Rare/Absent Crisis States:** HMM R1 (post-crash bounce, 40 days) and R3 (acute crash, 27 days) occurred only during March–June 2020 and have 0 observations in the 2025–2026 holdout. They are documented as historically verified but untested out-of-sample."""
    ))

    # Cell 6: Regime Profiles Code
    cells.append(nbf.v4.new_code_cell(
"""regime_profiles = compute_model_regime_profiles(labels_df, master_features)
regime_profiles.to_csv(results_dir / "regime_characterization" / "regime_profiles" / "model_regime_profiles.csv", index=False)

print("=== HMM CAUSAL FILTERED REGIME PROFILES (TRAINING POOL) ===")
hmm_causal_train = regime_profiles[
    (regime_profiles["model"] == "hmm") & 
    (regime_profiles["label_type"] == "filtered_causal") & 
    (regime_profiles["period"] == "train")
]
display_cols = [
    "regime_id", "economic_name", "n_trading_days", "pct_trading_days", 
    "n_episodes", "median_duration_days", "nifty50_return_20d_mean", 
    "vix_close_mean", "metal_rs_20d_mean", "fmcg_rs_20d_mean", "pharma_rs_20d_mean"
]
print(hmm_causal_train[display_cols].to_string(index=False))

print("\\n=== HMM CAUSAL FILTERED REGIME PROFILES (HOLDOUT PERIOD) ===")
hmm_causal_holdout = regime_profiles[
    (regime_profiles["model"] == "hmm") & 
    (regime_profiles["label_type"] == "filtered_causal") & 
    (regime_profiles["period"] == "holdout")
]
print(hmm_causal_holdout[display_cols].to_string(index=False))"""
    ))

    # Cell 7: Regime Plot Code
    cells.append(nbf.v4.new_code_cell(
"""# Plot Occupancy and Median Duration across models
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Subplot 1: HMM Causal Training vs Holdout Occupancy
x = np.arange(6)
width = 0.35
train_pcts = hmm_causal_train["pct_trading_days"].values
holdout_pcts = hmm_causal_holdout["pct_trading_days"].values

axes[0].bar(x - width/2, train_pcts, width, label="Training Pool (2019-2024)", color="#2b5c8f")
axes[0].bar(x + width/2, holdout_pcts, width, label="Holdout (2025-2026)", color="#d95f02")
axes[0].set_title("HMM Causal: Regime Occupancy (% Trading Days)", fontweight="bold")
axes[0].set_xlabel("HMM Regime ID")
axes[0].set_ylabel("% of Period Days")
axes[0].set_xticks(x)
axes[0].set_xticklabels([f"R{i}\\n{hmm_causal_train['economic_name'].iloc[i][:15]}..." for i in range(6)], fontsize=9)
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Subplot 2: Cross-Model Median Episode Duration (Persistence)
models = ["K-Means (K=4)", "GMM (K=2)", "HMM (K=6)"]
train_durs = [
    regime_profiles[(regime_profiles["model"]=="kmeans") & (regime_profiles["period"]=="train")]["median_duration_days"].median(),
    regime_profiles[(regime_profiles["model"]=="gmm") & (regime_profiles["period"]=="train")]["median_duration_days"].median(),
    regime_profiles[(regime_profiles["model"]=="hmm") & (regime_profiles["label_type"]=="filtered_causal") & (regime_profiles["period"]=="train")]["median_duration_days"].median(),
]
hold_durs = [
    regime_profiles[(regime_profiles["model"]=="kmeans") & (regime_profiles["period"]=="holdout")]["median_duration_days"].median(),
    regime_profiles[(regime_profiles["model"]=="gmm") & (regime_profiles["period"]=="holdout")]["median_duration_days"].median(),
    regime_profiles[(regime_profiles["model"]=="hmm") & (regime_profiles["label_type"]=="filtered_causal") & (regime_profiles["period"]=="holdout")]["median_duration_days"].median(),
]

x_m = np.arange(len(models))
axes[1].bar(x_m - width/2, train_durs, width, label="Train Median Duration", color="#1b9e77")
axes[1].bar(x_m + width/2, hold_durs, width, label="Holdout Median Duration", color="#7570b3")
axes[1].set_title("Cross-Model Median Episode Duration (Days)", fontweight="bold")
axes[1].set_xticks(x_m)
axes[1].set_xticklabels(models, fontsize=11)
axes[1].set_ylabel("Trading Days")
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(results_dir / "regime_characterization" / "regime_profiles" / "regime_occupancy_persistence.png", dpi=150)
plt.show()
print("Saved: results/regime_characterization/regime_profiles/regime_occupancy_persistence.png")"""
    ))

    # Cell 8: Sector Performance Markdown
    cells.append(nbf.v4.new_markdown_cell(
r"""## 3. Sector Performance Analysis within Discovered Regimes

For all six sectors (`AUTO`, `BANK`, `FMCG`, `IT`, `METAL`, `PHARMA`), we compute:
1. **Contemporaneous Daily Performance:** Daily returns ($r_{i,t}$) and daily excess returns relative to NIFTY 50 ($r_{i,t} - r_{\text{NIFTY50},t}$) while holding the sector during regime days.
2. **Forward 20-Day Performance:** Forward returns ($r_{i,t \to t+20}$) and forward excess returns conditional on regime presence at date $t$. Strictly segregated to prevent look-ahead bias.
3. **Statistical Dispersion & Quality:** Standard deviation, IQR, win rate vs benchmark, sample size (days and episodes), and episode-weighted returns.

### Boundary Enforcement
For the **training period**, forward 20-day returns whose $t{+}20$ price endpoint falls beyond `TRAIN_END_DATE` (2024-12-31) are excluded. This prevents the last 20 training dates (Dec 2024) from drawing on 2025 holdout prices. Boundary lookup uses **trading-day index positions**, not calendar offsets, so Indian market holidays are handled correctly. Contemporaneous returns and holdout-period forward returns are unaffected.

### Limitation: Overlapping Windows & Serial Correlation
20-day forward returns on consecutive dates share 19/20 price observations, creating serial correlation. Mean estimates are unbiased, but **standard errors are understated** (effective $n \approx n_{\text{obs}} / 20$). `sample_size_flag = low_sample_unstable` provides a partial safeguard for small regimes."""
    ))

    # Cell 9: Sector Performance Code
    cells.append(nbf.v4.new_code_cell(
"""# Pass price_df so the function can enforce the training-period forward-return
# boundary: dates whose t+20 price endpoint exceeds TRAIN_END_DATE are excluded.
sector_perf = compute_sector_performance_by_regime(
    labels_df, daily_returns, fwd_20d_returns, price_df=price_df
)
sector_perf.to_csv(results_dir / "regime_characterization" / "sector_performance" / "sector_performance_by_regime.csv", index=False)

# Verify boundary: no training forward_20D row should have been computed using a
# t+20 price from the holdout. Report the number of excluded boundary dates.
train_fwd = sector_perf[
    (sector_perf["period"] == "train") &
    (sector_perf["return_horizon"] == "forward_20D") &
    (sector_perf["model"] == "hmm") &
    (sector_perf["label_type"] == "filtered_causal") &
    (sector_perf["regime_id"] == 4)  # largest training regime
]
print(f"HMM R4 train forward_20D n_observations: {train_fwd['n_observations'].iloc[0]} (was 353 pre-fix, expect ~333 post-fix)")

print("\\n=== HMM CAUSAL (TRAIN) CONTEMPORANEOUS ANNUALIZED EXCESS RETURNS (%) ===")
hmm_perf_train = sector_perf[
    (sector_perf["model"] == "hmm") & 
    (sector_perf["label_type"] == "filtered_causal") & 
    (sector_perf["period"] == "train") & 
    (sector_perf["return_horizon"] == "contemporaneous_daily")
]
pivot_ann_excess = hmm_perf_train.pivot(index="sector", columns="regime_id", values="annualized_excess_return") * 100.0
pivot_ann_excess.columns = [f"R{c}: {REGIME_INTERPRETATIONS[('hmm', c)]['economic_name'][:18]}" for c in pivot_ann_excess.columns]
print(pivot_ann_excess.round(2))

print("\\n=== HMM CAUSAL (TRAIN) FORWARD 20D EXCESS RETURNS (%) ===")
hmm_fwd_train = sector_perf[
    (sector_perf["model"] == "hmm") & 
    (sector_perf["label_type"] == "filtered_causal") & 
    (sector_perf["period"] == "train") & 
    (sector_perf["return_horizon"] == "forward_20D")
]
pivot_fwd_excess = hmm_fwd_train.pivot(index="sector", columns="regime_id", values="mean_excess_return") * 100.0
pivot_fwd_excess.columns = [f"R{c}: {REGIME_INTERPRETATIONS[('hmm', c)]['economic_name'][:18]}" for c in pivot_fwd_excess.columns]
print(pivot_fwd_excess.round(2))"""
    ))

    # Cell 10: Sector Heatmap Code
    cells.append(nbf.v4.new_code_cell(
"""fig, ax = plt.subplots(figsize=(14, 7))
sns.heatmap(
    pivot_ann_excess, 
    annot=True, 
    fmt=".1f", 
    cmap="vlag", 
    center=0.0, 
    cbar_kws={"label": "Annualized Excess Return vs NIFTY 50 (%)"}, 
    linewidths=1.0, 
    linecolor="#ffffff",
    ax=ax
)
ax.set_title("HMM Causal Regimes: Contemporaneous Annualized Sector Excess Return (%)", fontsize=13, fontweight="bold", pad=12)
ax.set_ylabel("Sector Index", fontsize=11)
ax.set_xlabel("Discovered Economic Regime (Training Pool)", fontsize=11)
plt.tight_layout()
plt.savefig(results_dir / "regime_characterization" / "sector_leadership" / "sector_leadership_heatmap.png", dpi=150)
plt.show()
print("Saved: results/regime_characterization/sector_leadership/sector_leadership_heatmap.png")"""
    ))

    # Cell 11: Sector Leadership Markdown
    cells.append(nbf.v4.new_markdown_cell(
"""## 4. Sector Leadership, Laggards & Defensive Behavior

Identifies the strongest and weakest sectors within each market state:
- **Top 2 Leaders:** Highest benchmark-relative excess returns.
- **Bottom 2 Laggards:** Lowest benchmark-relative excess returns.
- **Defensive Candidates:** Outperforming sectors during market contractions / risk-off regimes.
- **Sample Size Safeguards:** Regimes with $N < 50$ days or $< 3$ episodes are flagged as `low_sample_unstable`."""
    ))

    # Cell 12: Sector Leadership Code
    cells.append(nbf.v4.new_code_cell(
"""leadership_df = identify_sector_leadership(sector_perf)
leadership_df.to_csv(results_dir / "regime_characterization" / "sector_leadership" / "sector_leadership_summary.csv", index=False)

print("=== HMM CAUSAL SECTOR LEADERSHIP SUMMARY (TRAIN) ===")
hmm_lead_train = leadership_df[
    (leadership_df["model"] == "hmm") & 
    (leadership_df["label_type"] == "filtered_causal") & 
    (leadership_df["period"] == "train")
]
cols_lead = [
    "regime_id", "economic_name", "sample_size_flag", "top_leader_1", 
    "top_leader_2", "bottom_laggard_1", "bottom_laggard_2", "defensive_candidate"
]
print(hmm_lead_train[cols_lead].to_string(index=False))

print("\\n=== HMM CAUSAL SECTOR LEADERSHIP SUMMARY (HOLDOUT) ===")
hmm_lead_holdout = leadership_df[
    (leadership_df["model"] == "hmm") & 
    (leadership_df["label_type"] == "filtered_causal") & 
    (leadership_df["period"] == "holdout")
]
print(hmm_lead_holdout[cols_lead].to_string(index=False))"""
    ))

    # Cell 13: HMM Holdout Sector Return Correlation Markdown
    cells.append(nbf.v4.new_markdown_cell(
r"""## 5. HMM Holdout Sector-Performance Correlation Analysis (2025–2026)

To rigorously evaluate how sector relationships behave out-of-sample, we compute Pearson correlation matrices for the six sectors (`AUTO`, `BANK`, `FMCG`, `IT`, `METAL`, `PHARMA`) within each **HMM causal-filtered regime** in the protected 2025–2026 holdout period.

### Methodological Standards:
1. **Holdout Scope & Filtering:** Strictly uses real-time `filtered_causal` regime probabilities on the 422 holdout trading days to eliminate look-ahead bias.
2. **Sample Size Reporting & Flagging:**
   - **Regime 0 (Cyclical Reflation Rally):** $n=8$ days (1.9% of holdout). Flagged as `low_sample_unstable` ($n < 30$).
   - **Regimes 1 & 3 (Post-Crash Bounce & Acute Crisis):** $n=0$ days (0.0%). Flagged as `absent_in_holdout`.
   - **Regime 2 (Low-Volatility Consolidation):** $n=118$ days (28.0%). Flagged as `sufficient` ($n \ge 30$).
   - **Regime 4 (Steady Expansion):** $n=170$ days (40.3%). Flagged as `sufficient` ($n \ge 30$).
   - **Regime 5 (Correction / Risk-Off):** $n=126$ days (29.9%). Flagged as `sufficient` ($n \ge 30$).
3. **Artifacts Generated:** Individual heatmaps for active regimes, multi-panel comparison figure, long-format matrix CSV, and pairwise comparison summary CSV."""
    ))

    # Cell 14: HMM Holdout Sector Return Correlation Code
    cells.append(nbf.v4.new_code_cell(
"""print("Computing HMM holdout sector return correlation matrices...")
corr_results = compute_hmm_holdout_sector_correlations(labels_df, daily_returns)

corr_matrices_df = corr_results["matrices_df"]
corr_comparison_df = corr_results["comparison_df"]
corr_summary_df = corr_results["regime_summary_df"]

corr_matrices_df.to_csv(results_dir / "regime_characterization" / "correlations" / "hmm_holdout_sector_correlation_matrices.csv", index=False)
corr_comparison_df.to_csv(results_dir / "regime_characterization" / "correlations" / "hmm_holdout_sector_correlation_summary.csv", index=False)

print("=== HMM HOLDOUT REGIME CORRELATION SUMMARY ===")
print(corr_summary_df[["regime_id", "economic_name", "n_observations", "pct_holdout_days", "sample_size_flag", "mean_pairwise_correlation"]].to_string(index=False))

print("\\n=== TOP SECTOR PAIRWISE CORRELATION SHIFTS (R5 CORRECTION vs R4 EXPANSION) ===")
print(corr_comparison_df[["sector_pair", "pair_category", "R2_corr_consolidation", "R4_corr_expansion", "R5_corr_correction", "R5_minus_R4_shift", "max_regime_sufficient"]].sort_values("R5_minus_R4_shift", ascending=False).to_string(index=False))

# Generate and display heatmaps
saved_plots = plot_hmm_holdout_sector_correlations(corr_results, results_dir / "regime_characterization" / "correlations")"""
    ))

    # Cell 15: Display Comparison Heatmap Code
    cells.append(nbf.v4.new_code_cell(
"""# Display the concise multi-panel comparison figure
from IPython.display import Image, display
display(Image(filename=str(results_dir / "regime_characterization" / "correlations" / "hmm_holdout_sector_corr_comparison.png")))"""
    ))

    # Cell 16: HMM Holdout Correlation Findings Markdown
    cells.append(nbf.v4.new_markdown_cell(
r"""### Key Sector Relationship Findings in Holdout:
1. **Risk-Off Systemic Correlation Surge (Regime 5, $n=126$):**
   - Mean pairwise correlation spikes to **0.4957** (vs 0.3252 in R4 and 0.3189 in R2).
   - Cyclical pairs surge: `AUTO - BANK` reaches **0.815** (+0.300 vs R4), `AUTO - METAL` reaches **0.723** (+0.358 vs R4).
   - Spillovers hit defensive-cyclical pairs (`METAL - PHARMA` jumps from 0.343 to 0.711) as systemic de-risking causes broad equity selling.
2. **Defensive Decorrelation in Bull Expansion (Regime 4, $n=170$):**
   - Moderate cross-sector correlation (mean 0.3252) with healthy dispersion. Defensives strongly decouple from cyclicals (`FMCG - METAL` 0.177, `FMCG - IT` 0.192, `AUTO - PHARMA` 0.220), confirming real portfolio diversification.
3. **Decoupled Idiosyncratic Rotation in Consolidation (Regime 2, $n=118$):**
   - Low cross-sector correlation (mean 0.3189) with lowest correlation across consumer and commodity sectors (`FMCG - METAL` 0.114, `FMCG - PHARMA` 0.130).
4. **IT as Macro Decorrelation Anchor:**
   - Across all regimes, IT exhibits low correlation to BANK (0.251 in R2, 0.328 in R4, 0.253 in R5), functioning as an effective macro hedge during domestic banking selloffs.
5. **Caveats on Rare and Absent Regimes:**
   - **Regime 0 ($n=8$):** Sample is insufficient ($n < 30$); high correlation (0.633) is driven by a single 7-day rally episode and is statistically unstable out-of-sample.
   - **Regimes 1 & 3 ($n=0$):** Acute historical crash/bounce states never recurred in 2025–2026; they remain unvalidated out-of-sample."""
    ))

    # Cell 17: Major Event Markdown
    cells.append(nbf.v4.new_markdown_cell(
"""## 6. Major-Event Contextual Analysis

The event calendar (`data/raw/Events/major_events_2019_2026.csv`) contains 135 macro, monetary policy, and geopolitical events.
### Methodological Rules:
1. **Trading-Day Alignment:** Non-trading event dates are mapped forward to the next available trading day.
2. **Event Window:** $[-2, +2]$ trading days around each event date.
3. **Union Deduplication:** Overlapping windows are combined into a single boolean trading-day mask to avoid double-counting.
4. **Causality Caution:** Event association does **not** prove causation; it contextualizes historical regime co-occurrence."""
    ))

    # Cell 14: Event Alignment Code
    cells.append(nbf.v4.new_code_cell(
"""events_raw_path = data_dir / "raw" / "Events" / "major_events_2019_2026.csv"
events_aligned = load_and_align_events(str(events_raw_path), daily_returns.index)

print(f"Total major events loaded : {len(events_aligned)}")
print(f"Events in training window : {len(events_aligned[(events_aligned['aligned_start_date'] >= '2019-10-31') & (events_aligned['aligned_end_date'] <= '2024-12-31')])}")
print(f"Events in holdout window  : {len(events_aligned[(events_aligned['aligned_start_date'] >= '2025-01-02') & (events_aligned['aligned_end_date'] <= '2026-09-18')])}")

is_event_day, event_windows_df = build_event_windows(events_aligned, daily_returns.index, pre_days=2, post_days=2)
print(f"Total active trading days : {len(is_event_day)}")
print(f"Deduplicated event days   : {int(is_event_day.sum())} ({is_event_day.mean()*100:.1f}%)")
print(f"Normal baseline days      : {int((~is_event_day).sum())} ({(~is_event_day).mean()*100:.1f}%)")"""
    ))

    # Cell 15: Event Associations Code
    cells.append(nbf.v4.new_code_cell(
"""event_regime_assoc = analyze_event_regime_associations(labels_df, daily_returns, is_event_day, events_aligned)
event_regime_assoc.to_csv(results_dir / "event_analysis" / "event_regime_association.csv", index=False)

sector_event_perf = analyze_sector_performance_during_events(daily_returns, is_event_day, events_aligned)
sector_event_perf.to_csv(results_dir / "event_analysis" / "sector_performance_during_events.csv", index=False)

print("=== HMM CAUSAL EVENT REGIME FREQUENCY RATIOS (TRAINING POOL) ===")
hmm_ev_train = event_regime_assoc[
    (event_regime_assoc["model"] == "hmm") & 
    (event_regime_assoc["label_type"] == "filtered_causal") & 
    (event_regime_assoc["period"] == "train")
]
print(hmm_ev_train[["regime_id", "economic_name", "event_window_regime_pct", "normal_baseline_regime_pct", "frequency_ratio_event_vs_normal", "event_association_verdict"]].to_string(index=False))

print("\\n=== SECTOR PERFORMANCE: EVENT WINDOWS VS NORMAL BASELINE ===")
print(sector_event_perf[["sector", "event_annualized_excess_return", "normal_annualized_excess_return", "event_volatility_annualized", "normal_volatility_annualized"]].to_string(index=False))"""
    ))

    # Cell 16: Event Plot Code
    cells.append(nbf.v4.new_code_cell(
"""fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Plot 1: Regime Frequency During Events vs Normal Baseline
x = np.arange(len(hmm_ev_train))
width = 0.35
axes[0].bar(x - width/2, hmm_ev_train["event_window_regime_pct"], width, label="Event Windows ([-2, +2] days)", color="#e41a1c")
axes[0].bar(x + width/2, hmm_ev_train["normal_baseline_regime_pct"], width, label="Normal Baseline", color="#377eb8")
axes[0].set_title("HMM Regime Frequency: Major Events vs Normal Baseline (%)", fontweight="bold")
axes[0].set_xticks(x)
axes[0].set_xticklabels([f"R{r}\\n{name[:14]}" for r, name in zip(hmm_ev_train["regime_id"], hmm_ev_train["economic_name"])], fontsize=9)
axes[0].set_ylabel("% of Days in Condition")
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Plot 2: Sector Annualized Excess Returns: Events vs Normal
x_sec = np.arange(len(sector_event_perf))
axes[1].bar(x_sec - width/2, sector_event_perf["event_annualized_excess_return"] * 100, width, label="During Events", color="#984ea3")
axes[1].bar(x_sec + width/2, sector_event_perf["normal_annualized_excess_return"] * 100, width, label="Normal Non-Event Days", color="#4daf4a")
axes[1].set_title("Sector Annualized Excess Return: Events vs Normal (%)", fontweight="bold")
axes[1].set_xticks(x_sec)
axes[1].set_xticklabels(sector_event_perf["sector"], fontsize=11)
axes[1].set_ylabel("Annualized Excess Return vs NIFTY 50 (%)")
axes[1].axhline(0, color="black", linestyle="--", linewidth=0.8)
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(results_dir / "event_analysis" / "event_vs_normal_comparison.png", dpi=150)
plt.show()
print("Saved: results/event_analysis/event_vs_normal_comparison.png")"""
    ))

    # Cell 17: Cross Model Markdown
    cells.append(nbf.v4.new_markdown_cell(
"""## 6. Cross-Model Comparative Synthesis

Comparing models across economic interpretations, persistence, and reliability without forcing 1-to-1 regime ID mappings:
- **Gaussian HMM ($K=6$):** Demonstrates superior regime persistence (median duration ~24d in train, ~9d in holdout) and actively shifts between expansion, consolidation, and correction states. It is the only model suitable for dynamic sector rotation.
- **K-Means ($K=4$):** Prone to high-frequency churn in holdout (1.0d median duration) and severe feature-scaling instability (ARI=0.1603).
- **GMM ($K=2$):** Collapsed to a single state in holdout (100% Regime 0). It functions as a tail-shock detector rather than an ongoing rotation engine."""
    ))

    # Cell 18: Cross Model Code
    cells.append(nbf.v4.new_code_cell(
"""cross_model_df = generate_cross_model_comparison(regime_profiles, leadership_df)
cross_model_df.to_csv(results_dir / "reports" / "cross_model_comparison_summary.csv", index=False)
print("=== CROSS-MODEL COMPARISON SUMMARY ===")
print(cross_model_df[["model_name", "n_regimes_discovered", "median_episode_duration_train", "median_episode_duration_holdout", "holdout_state_collapse", "phase7_operational_verdict"]].to_string(index=False))"""
    ))

    # Cell 23: Verification Markdown
    cells.append(nbf.v4.new_markdown_cell(
"""## 8. Phase 7 Output Verification & Completion Checklist

Verifies that all required CSV deliverables and plots are successfully generated and consistent."""
    ))

    # Cell 24: Verification Code
    cells.append(nbf.v4.new_code_cell(
"""required_artifacts = [
    "regime_characterization/regime_profiles/model_regime_profiles.csv",
    "regime_characterization/sector_performance/sector_performance_by_regime.csv",
    "regime_characterization/sector_leadership/sector_leadership_summary.csv",
    "event_analysis/event_regime_association.csv",
    "event_analysis/sector_performance_during_events.csv",
    "reports/cross_model_comparison_summary.csv",
    "regime_characterization/correlations/hmm_holdout_sector_correlation_matrices.csv",
    "regime_characterization/correlations/hmm_holdout_sector_correlation_summary.csv",
    "regime_characterization/regime_profiles/regime_occupancy_persistence.png",
    "regime_characterization/sector_leadership/sector_leadership_heatmap.png",
    "event_analysis/event_vs_normal_comparison.png",
    "regime_characterization/correlations/hmm_holdout_sector_corr_regime_0.png",
    "regime_characterization/correlations/hmm_holdout_sector_corr_regime_2.png",
    "regime_characterization/correlations/hmm_holdout_sector_corr_regime_4.png",
    "regime_characterization/correlations/hmm_holdout_sector_corr_regime_5.png",
    "regime_characterization/correlations/hmm_holdout_sector_corr_comparison.png",
]

print("=== PHASE 7 DELIVERABLES VERIFICATION ===")
all_ok = True
for art in required_artifacts:
    p = results_dir / art
    exists = p.exists()
    size = p.stat().st_size if exists else 0
    status = "OK" if (exists and size > 0) else "FAIL"
    print(f"[{status}] {art:<75} ({size:,} bytes)")
    if not (exists and size > 0):
        all_ok = False

print(f"\\nPhase 7 Complete — All Deliverables Verified: {all_ok}")"""
    ))

    nb["cells"] = cells

    out_path = project_root / "notebooks" / "07_regime_characterisation.ipynb"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print(f"Generated {out_path} with {len(cells)} cells.")

    # Execute the notebook using nbconvert ExecutePreprocessor
    print("Executing notebook end-to-end to save all outputs and plots...")
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    with open(out_path, "r", encoding="utf-8") as f:
        nb_to_run = nbf.read(f, as_version=4)

    ep.preprocess(nb_to_run, {"metadata": {"path": str(project_root / "notebooks")}})

    with open(out_path, "w", encoding="utf-8") as f:
        nbf.write(nb_to_run, f)
    print("Notebook executed successfully and updated with cell outputs!")

if __name__ == "__main__":
    create_and_run_notebook()
