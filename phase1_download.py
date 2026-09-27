"""
phase1_download.py
------------------
Standalone script that:
1. Verifies all tickers (test window 2024-01-01 → 2024-06-30)
2. Downloads full research data 2019-01-01 → latest
3. Saves raw CSVs
4. Runs basic validation
5. Prints a final summary table

Run from project root:
    python phase1_download.py
"""

import sys
import os

# Make sure src/ is importable regardless of cwd
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import pandas as pd
from src.data_loader import (
    VERIFIED_TICKERS,
    download_data,
    save_raw_data,
    load_data,
    validate_downloaded_data,
    verify_ticker,
    DEFAULT_START,
)

RAW_BASE = os.path.join(ROOT, "data", "raw")


# STEP 1 — Ticker verification (2024 test window)

print("\n" + "=" * 70)
print("STEP 1: TICKER VERIFICATION  (test period 2024-01-01 → 2024-06-30)")
print("=" * 70)

verification_results = []
for key, meta in VERIFIED_TICKERS.items():
    r = verify_ticker(
        ticker=meta["ticker"],
        instrument_label=meta["label"],
        test_start="2024-01-01",
        test_end="2024-06-30",
    )
    verification_results.append(r)
    status = r["status"]
    rows   = r["rows"]
    fd     = r["first_date"]
    ld     = r["last_date"]
    cols   = r["columns"]
    err    = r["error"] or ""
    print(
        f"  [{status:6s}]  {meta['label']:<16s}  {meta['ticker']:<14s}"
        f"  rows={rows:3d}  {fd} → {ld}  cols={cols}  {err}"
    )

# Flag any failures
failed = [r for r in verification_results if r["status"] != "PASS"]
if failed:
    print("\n  ⚠  WARNING: The following tickers FAILED verification:")
    for r in failed:
        print(f"     {r['instrument']} ({r['ticker']}): {r['error']}")
    print("\n  Continuing with available tickers only.\n")
else:
    print("\n  ✓  All tickers verified.\n")

# Build set of passing ticker keys
passing_keys = {
    key for key, meta in VERIFIED_TICKERS.items()
    if any(r["ticker"] == meta["ticker"] and r["status"] == "PASS"
           for r in verification_results)
}

# ============================================================
# STEP 2 — Full download 2019-01-01 → latest
# ============================================================
print("=" * 70)
print(f"STEP 2: DOWNLOADING  {DEFAULT_START} → latest available")
print("=" * 70)

downloaded: dict[str, pd.DataFrame] = {}
for key, meta in VERIFIED_TICKERS.items():
    if key not in passing_keys:
        print(f"  SKIP  {meta['label']} — ticker failed verification.")
        continue
    df = download_data(
        ticker=meta["ticker"],
        start=DEFAULT_START,
        instrument_label=meta["label"],
    )
    downloaded[key] = df


# STEP 3 — Save raw CSVs  (overwrite=False by default)

print("\n" + "=" * 70)
print("STEP 3: SAVING RAW CSVs  (overwrite=False)")
print("=" * 70)

for key, df in downloaded.items():
    meta = VERIFIED_TICKERS[key]
    out_path = os.path.join(RAW_BASE, meta["subdir"], meta["output_file"])
    saved = save_raw_data(df, output_path=out_path, overwrite=False)
    if not saved:
        print(f"  ↳  {meta['output_file']} already exists — preserved.")


# STEP 4 — Reload and validate

print("\n" + "=" * 70)
print("STEP 4: VALIDATION")
print("=" * 70)

validation_rows = []
for key, meta in VERIFIED_TICKERS.items():
    out_path = os.path.join(RAW_BASE, meta["subdir"], meta["output_file"])
    if not os.path.exists(out_path):
        print(f"  MISSING  {meta['output_file']}")
        validation_rows.append({
            "Instrument": meta["label"],
            "Category":   meta["category"],
            "Ticker":     meta["ticker"],
            "Rows":       0,
            "First Date": None,
            "Last Date":  None,
            "Missing":    "N/A",
            "Duplicates": "N/A",
            "Status":     "FAILED",
            "Output File": meta["output_file"],
        })
        continue

    df_loaded = load_data(out_path)
    v = validate_downloaded_data(df_loaded, meta["label"], meta["ticker"])

    print(f"\n  {meta['label']} ({meta['ticker']})")
    print(f"    rows        : {v['rows']}")
    print(f"    first date  : {v['first_date']}")
    print(f"    last date   : {v['last_date']}")
    print(f"    columns     : {v['columns']}")
    print(f"    missing     : {v['total_missing']}")
    print(f"    duplicates  : {v['duplicate_dates']}")
    print(f"    OHLC viol.  : {v['ohlc_violations']}")
    print(f"    status      : {v['status']}")
    for note in v["notes"]:
        print(f"    note        : {note}")

    validation_rows.append({
        "Instrument": meta["label"],
        "Category":   meta["category"],
        "Ticker":     meta["ticker"],
        "Rows":       v["rows"],
        "First Date": str(v["first_date"]),
        "Last Date":  str(v["last_date"]),
        "Missing":    v["total_missing"],
        "Duplicates": v["duplicate_dates"],
        "Status":     v["status"],
        "Output File": meta["output_file"],
    })


# STEP 5 — Final summary table

print("\n" + "=" * 70)
print("STEP 5: FINAL SUMMARY TABLE")
print("=" * 70)

summary_df = pd.DataFrame(validation_rows)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
print(summary_df.to_string(index=False))

print("\n  Done.")
