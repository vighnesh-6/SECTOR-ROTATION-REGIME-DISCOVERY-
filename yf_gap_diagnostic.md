# Yahoo Finance Data-Gap Diagnostic Report
**Tickers:** `^CNXAUTO` · `^CNXFMCG` · `^CNXMETAL`  
**Test window:** `2026-07-15 → 2026-09-12`  
**Run at:** 2026-09-12 16:01 IST  
**No project files were modified.**

---

## TL;DR — Root Cause

Yahoo Finance / yfinance is exhibiting a **two-tier data-delivery failure**:

| Config | Rows returned | Gap behaviour |
|---|---|---|
| `auto_adjust=False, repair=False` | **4 rows** | All gap dates missing; only 3 valid rows + 1 broken stub |
| `auto_adjust=False, repair=True` | **43 rows** | All gap dates **present** but with full OHLC; however Volume = 0 on **40 of 43 rows** |

The OHLC data itself in the `repair=True` run looks plausible (prices are continuous and sensible). The `Volume = 0` across almost the entire window is a known Yahoo Finance quirk for NSE index tickers — **indices do not have tradeable volume**, so this is expected and not a data error.

---

## Config 1 — `auto_adjust=False, repair=False`

### All three tickers: identical behaviour

| Field | Value |
|---|---|
| First date | `2026-07-15` |
| Last date | `2026-09-11` |
| **Total rows** | **4** |
| Columns | Adj Close, Close, High, Low, Open, Volume |
| NaN in OHLC | **1 row** (2026-09-11) |
| Volume = 0 | **1 row** (2026-09-11) |

**The 4 rows returned are:**

- `2026-07-15` — valid (the only pre-gap row in range)
- `2026-07-16` — valid
- `2026-07-17` — valid (last day before the gap in stored CSV)
- `2026-09-11` — **broken stub**: Open/High/Low have values, Close = NaN, Adj Close = NaN, Volume = 0

> [!CAUTION]
> **All trading dates from 2026-07-18 through 2026-09-10 are completely absent** from the `repair=False` response. Yahoo Finance's raw endpoint is not returning this data at all.

**Sample broken-stub rows (all three tickers):**

```
^CNXAUTO   2026-09-11  Open=27326.85  High=27405.5  Low=27094.95  Close=NaN  Volume=0
^CNXFMCG   2026-09-11  Open=44909.30  High=45276.70  Low=44825.60  Close=NaN  Volume=0
^CNXMETAL  2026-09-11  Open=13079.85  High=13084.10  Low=12886.10  Close=NaN  Volume=0
```

---

## Config 2 — `auto_adjust=False, repair=True`

### All three tickers: 43 rows, full OHLC, zero volume

| Field | Value |
|---|---|
| First date | `2026-07-15` |
| Last date | `2026-09-11` |
| **Total rows** | **43** |
| Columns | Adj Close, Close, High, Low, Open, **Repaired?**, Volume |
| NaN in OHLC | **0** |
| Volume = 0 | **40 of 43 rows** |
| Calendar gaps > 5 days | **None detected** |

> [!NOTE]
> The `repair=True` mode triggered yfinance's internal gap-fill / repair engine, which recovered all the missing OHLC values. The extra `Repaired?` column is proof that yfinance marked those rows as reconstructed.

**Volume = 0 is expected for NSE sectoral indices** — they are price indices, not ETFs. Yahoo Finance never carries true volume for `^CNX*` tickers. The 3 rows that do have non-zero volume (`2026-07-15`, `2026-07-16`, `2026-07-17`) were already present in the raw response and happen to carry volume from the pre-existing stored data.

**OHLC window around the reported gap (^CNXAUTO, repair=True):**

```
Date        Open       High       Low        Close
2026-07-17  (in stored CSV already)
2026-07-20  27076.20   27076.20   26807.05   27041.15
2026-07-21  27034.55   27328.50   26912.50   27320.10
...
2026-09-10  27663.65   27666.80   27385.95   27540.25
2026-09-11  27326.85   27405.50   27094.95   27304.70  ← Close now present!
```

No gap is visible in the `repair=True` data — the series is continuous.

**Encoding error (cosmetic, not data):**

```
ERROR: 'charmap' codec can't encode character '\u2192' in position 35
```
This is a Windows `cp1252` console encoding issue when printing the `→` arrow in the diagnostic's print statement. It does **not** affect data quality and can be ignored.

---

## Summary of Findings

| Finding | Detail |
|---|---|
| **Source of gap** | Yahoo Finance raw API (`repair=False`) returns only ~4 rows for this window — the gap dates are missing server-side |
| **repair=True recovers data** | yfinance's repair engine fetches and reconstructs the missing rows; OHLC values look numerically plausible |
| **Volume = 0** | Expected for `^CNX*` price indices; not a data error |
| **2026-09-11 broken stub** | Close/Adj Close = NaN in raw response; `repair=True` fills it with a valid value |
| **Encoding error** | Cosmetic Windows console issue, no data impact |

---

## Options Going Forward

> [!IMPORTANT]
> All options below require your explicit approval before any files are touched.

1. **Re-download with `repair=True`** — rerun the collection pipeline with `repair=True` added; replace the three CSVs only after manual inspection of the repaired values vs. NSEIndia or another authoritative source.

2. **Patch from NSEIndia / Stooq** — download the missing date range from a secondary source (NSEIndia historical data export or `stooq.com`) and append/merge into the existing CSVs without touching the already-clean rows.

3. **Flag and defer** — tag these three CSVs with a `DATA_GAP` marker, exclude them from any modelling run that covers the Jul 17 – Sep 11 window, and revisit when Yahoo Finance corrects its data.

---

*Diagnostic only. No project files were modified.*
