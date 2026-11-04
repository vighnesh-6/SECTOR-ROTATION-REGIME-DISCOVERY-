import pandas as pd
import numpy as np
from pathlib import Path

prob_path = Path("results/regime_discovery/hmm_causal_probabilities.csv")
labels_path = Path("results/regime_discovery/final_regime_labels.csv")

print("=== HMM CAUSAL PROBABILITIES AUDIT ===")
prob_df = pd.read_csv(prob_path, parse_dates=["Date"]).set_index("Date")
print(f"File size: {prob_path.stat().st_size:,} bytes")
print(f"Total observations: {len(prob_df)}")
print(f"Columns: {list(prob_df.columns)}")
print(f"Date range: {prob_df.index.min().date()} to {prob_df.index.max().date()}")
print(f"Sorted: {prob_df.index.is_monotonic_increasing}")
print(f"Unique dates: {prob_df.index.is_unique}")
print(f"Missing dates vs business days: {len(pd.bdate_range(prob_df.index.min(), prob_df.index.max())) - len(prob_df)}")

# Partitions
train_mask = prob_df["period"] == "train"
holdout_mask = prob_df["period"] == "holdout"
print(f"Train rows: {train_mask.sum()} ({prob_df[train_mask].index.min().date()} to {prob_df[train_mask].index.max().date()})")
print(f"Holdout rows: {holdout_mask.sum()} ({prob_df[holdout_mask].index.min().date()} to {prob_df[holdout_mask].index.max().date()})")

# Probability checks
prob_cols = [f"prob_{j}" for j in range(6)]
p_arr = prob_df[prob_cols].values
print(f"Null count in prob columns: {prob_df[prob_cols].isnull().sum().to_dict()}")
print(f"Non-finite count: {np.isnan(p_arr).sum() + np.isinf(p_arr).sum()}")
print(f"Min probability: {p_arr.min():.6f}, Max probability: {p_arr.max():.6f}")
row_sums = p_arr.sum(axis=1)
max_dev = np.abs(row_sums - 1.0).max()
print(f"Max row sum deviation from 1.0: {max_dev:.2e}")

# Compare argmax against final_regime_labels.csv
labels_df = pd.read_csv(labels_path, parse_dates=["Date"]).set_index("Date")
hmm_causal = labels_df[(labels_df["model"] == "hmm") & (labels_df["label_type"] == "filtered_causal")]
hmm_viterbi = labels_df[(labels_df["model"] == "hmm") & (labels_df["label_type"] == "retrospective_viterbi")]

argmax_regimes = np.argmax(p_arr, axis=1)
prob_df["argmax_regime"] = argmax_regimes

causal_match = (prob_df["argmax_regime"] == hmm_causal["regime_id"]).all()
causal_match_count = (prob_df["argmax_regime"] == hmm_causal["regime_id"]).sum()
print(f"\nAgreement with final_regime_labels (filtered_causal): {causal_match_count}/{len(prob_df)} ({causal_match_count/len(prob_df)*100:.2f}%) -> {causal_match}")

viterbi_match_count = (prob_df["argmax_regime"] == hmm_viterbi["regime_id"]).sum()
print(f"Agreement with final_regime_labels (retrospective_viterbi): {viterbi_match_count}/{len(prob_df)} ({viterbi_match_count/len(prob_df)*100:.2f}%)")
print(f"Viterbi vs Causal divergence: {len(prob_df) - viterbi_match_count} dates differ, proving filtered_causal is NOT retrospective Viterbi.")

