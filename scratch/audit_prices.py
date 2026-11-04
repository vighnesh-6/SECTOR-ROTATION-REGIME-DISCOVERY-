from pathlib import Path
import pandas as pd
import numpy as np

aligned_dir = Path("data/processed/aligned")
files = [
    "nifty_auto_aligned.csv",
    "nifty_bank_aligned.csv",
    "nifty_fmcg_aligned.csv",
    "nifty_it_aligned.csv",
    "nifty_metal_aligned.csv",
    "nifty_pharma_aligned.csv",
    "nifty50_aligned.csv",
]

print("=== MARKET PRICE DATASETS AUDIT ===")
dfs = {}
for fname in files:
    fpath = aligned_dir / fname
    exists = fpath.exists()
    size = fpath.stat().st_size if exists else 0
    if not exists:
        print(f"{fname}: NOT FOUND")
        continue
    
    df = pd.read_csv(fpath, index_col=0, parse_dates=True)
    dfs[fname] = df
    
    n_rows = len(df)
    min_date = df.index.min()
    max_date = df.index.max()
    is_sorted = df.index.is_monotonic_increasing
    is_unique = df.index.is_unique
    null_counts = df.isnull().sum().to_dict()
    has_close = "Close" in df.columns
    has_adj_close = "Adj Close" in df.columns
    
    # Check suspicious prices
    min_close = df["Close"].min() if has_close else None
    max_close = df["Close"].max() if has_close else None
    zero_neg_close = ((df["Close"] <= 0).sum()) if has_close else 0
    
    # Compare Close and Adj Close
    diff_stats = "N/A"
    if has_close and has_adj_close:
        abs_diff = (df["Close"] - df["Adj Close"]).abs()
        max_diff = abs_diff.max()
        pct_diff = (abs_diff / df["Close"]).max() * 100
        n_mismatches = (abs_diff > 1e-4).sum()
        diff_stats = f"max_diff={max_diff:.6f}, max_pct={pct_diff:.4f}%, diff_rows={n_mismatches}/{n_rows}"
    
    print(f"\n--- {fname} ---")
    print(f"Size: {size:,} bytes | Rows: {n_rows} | Range: {min_date.date()} to {max_date.date()}")
    print(f"Sorted: {is_sorted} | Unique: {is_unique} | Cols: {list(df.columns)}")
    print(f"Nulls: {null_counts}")
    print(f"Close range: [{min_close}, {max_close}] | Zero/Negative Close: {zero_neg_close}")
    print(f"Close vs Adj Close: {diff_stats}")

# Compare calendars across all 7
base_name = files[0]
base_idx = dfs[base_name].index
calendar_match = True
for fname in files[1:]:
    idx = dfs[fname].index
    if not base_idx.equals(idx):
        calendar_match = False
        missing_in_cur = base_idx.difference(idx)
        extra_in_cur = idx.difference(base_idx)
        print(f"Calendar MISMATCH: {fname} vs {base_name} (Missing: {len(missing_in_cur)}, Extra: {len(extra_in_cur)})")

if calendar_match:
    print(f"\nAll 7 price datasets share 100% IDENTICAL trading calendar ({len(base_idx)} sessions from {base_idx.min().date()} to {base_idx.max().date()}).")

