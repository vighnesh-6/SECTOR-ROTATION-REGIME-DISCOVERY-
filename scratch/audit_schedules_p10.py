import pandas as pd
import numpy as np
from pathlib import Path

schedule_files = {
    "1A": Path("results/portfolio_construction/target_weights_1A.csv"),
    "1B": Path("results/portfolio_construction/target_weights_1B.csv"),
    "2A": Path("results/portfolio_construction/target_weights_2A.csv"),
    "2B": Path("results/portfolio_construction/target_weights_2B.csv"),
}

expected_assets = ["AUTO", "BANK", "FMCG", "IT", "METAL", "PHARMA", "NIFTY50", "CASH"]
expected_weight_cols = [f"w_{a}" for a in expected_assets]

print("=== FOUR PHASE 9 PORTFOLIO SCHEDULES AUDIT ===")
sched_dfs = {}

for v, p in schedule_files.items():
    exists = p.exists()
    size = p.stat().st_size if exists else 0
    df = pd.read_csv(p, parse_dates=["Date", "exec_date"]).set_index("Date")
    sched_dfs[v] = df
    
    n_rows = len(df)
    train_mask = df["period"] == "train"
    holdout_mask = df["period"] == "holdout"
    train_rows = train_mask.sum()
    holdout_rows = holdout_mask.sum()
    
    is_sorted = df.index.is_monotonic_increasing
    is_unique = df.index.is_unique
    
    # exec_date timing check
    # For dates t < T, exec_date should be dates[t+1]
    exec_match = True
    for i in range(len(df) - 1):
        if df["exec_date"].iloc[i] != df.index[i + 1]:
            exec_match = False
            break
    
    # Weight checks
    w_mat = df[expected_weight_cols].values
    min_w = w_mat.min()
    max_w = w_mat.max()
    row_sums = w_mat.sum(axis=1)
    max_dev = np.abs(row_sums - 1.0).max()
    
    # Rebalance & turnover
    rebal_tot = int(df["rebalance_triggered"].sum())
    rebal_train = int(df[train_mask]["rebalance_triggered"].sum())
    rebal_holdout = int(df[holdout_mask]["rebalance_triggered"].sum())
    r3_overrides = int(df["rebalance_bypassed_r3"].sum())
    mean_turnover = float(df["turnover"].mean() * 100.0)
    
    # Cash stats
    cash_min = df["w_CASH"].min()
    cash_max = df["w_CASH"].max()
    cash_mean = df["w_CASH"].mean() * 100.0
    
    print(f"\n--- Variant {v} ---")
    print(f"Path: {p} | Size: {size:,} bytes | Rows: {n_rows} (Train: {train_rows}, Holdout: {holdout_rows})")
    print(f"Index: {df.index.min().date()} to {df.index.max().date()} | Sorted: {is_sorted} | Unique: {is_unique}")
    print(f"exec_date t+1 timing valid: {exec_match}")
    print(f"Weights: min={min_w:.6f}, max={max_w:.6f}, max_sum_dev={max_dev:.2e}")
    print(f"Cash (%): min={cash_min:.2f}%, max={cash_max*100:.2f}%, mean={cash_mean:.2f}%")
    print(f"Rebalances: {rebal_tot} (Train: {rebal_train}, Holdout: {rebal_holdout}) | R3 Overrides: {r3_overrides}")
    print(f"Turnover mean: {mean_turnover:.3f}%")
    print(f"Columns: {list(df.columns)}")

# Check calendar consistency across all four
base_v = "1A"
base_cal = sched_dfs[base_v].index
all_cal_match = True
for v in ["1B", "2A", "2B"]:
    if not base_cal.equals(sched_dfs[v].index):
        all_cal_match = False
        print(f"Calendar mismatch between {v} and {base_v}")

if all_cal_match:
    print(f"\nAll 4 portfolio schedules share 100% IDENTICAL trading calendar ({len(base_cal)} sessions).")

