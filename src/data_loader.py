"""
src/data_loader.py
==================
Reusable data-collection functions for Phase 1 of the
Sector Rotation Regime Discovery research project.

Responsibilities
----------------
- Download raw OHLCV data from Yahoo Finance
- Save raw CSVs with a clean Date column (no Unnamed index)
- Load saved CSVs back into DataFrames
- Run basic validation checks (non-destructive — never modifies data)

This module is intentionally kept free of:
- Feature engineering
- Normalisation / standardisation
- Date alignment across instruments
- Missing-value imputation
- Regime labels or event annotations
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

# Logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# Constants

DEFAULT_START = "2019-01-01"

# Verified Yahoo Finance ticker mapping for the research universe
VERIFIED_TICKERS: dict[str, dict[str, str]] = {
    "nifty50": {
        "ticker": "^NSEI",
        "label": "NIFTY 50",
        "category": "Market",
        "output_file": "nifty50.csv",
        "subdir": "market",
    },
    "india_vix": {
        "ticker": "^INDIAVIX",
        "label": "India VIX",
        "category": "Market",
        "output_file": "india_vix.csv",
        "subdir": "market",
    },
    "nifty_it": {
        "ticker": "^CNXIT",
        "label": "NIFTY IT",
        "category": "Sector",
        "output_file": "nifty_it.csv",
        "subdir": "sector_indices",
    },
    "nifty_bank": {
        "ticker": "^NSEBANK",
        "label": "NIFTY Bank",
        "category": "Sector",
        "output_file": "nifty_bank.csv",
        "subdir": "sector_indices",
    },
    "nifty_auto": {
        "ticker": "^CNXAUTO",
        "label": "NIFTY Auto",
        "category": "Sector",
        "output_file": "nifty_auto.csv",
        "subdir": "sector_indices",
    },
    "nifty_pharma": {
        "ticker": "^CNXPHARMA",
        "label": "NIFTY Pharma",
        "category": "Sector",
        "output_file": "nifty_pharma.csv",
        "subdir": "sector_indices",
    },
    "nifty_fmcg": {
        "ticker": "^CNXFMCG",
        "label": "NIFTY FMCG",
        "category": "Sector",
        "output_file": "nifty_fmcg.csv",
        "subdir": "sector_indices",
    },
    "nifty_metal": {
        "ticker": "^CNXMETAL",
        "label": "NIFTY Metal",
        "category": "Sector",
        "output_file": "nifty_metal.csv",
        "subdir": "sector_indices",
    },
}



# Public API


def download_data(
    ticker: str,
    start: str = DEFAULT_START,
    end: Optional[str] = None,
    instrument_label: str = "",
) -> pd.DataFrame:
    """Download OHLCV data from Yahoo Finance.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker symbol (e.g. ``"^NSEI"``).
    start : str
        ISO-8601 start date, inclusive (e.g. ``"2019-01-01"``).
    end : str or None
        ISO-8601 end date, inclusive.  When ``None`` (default) the download
        runs up to the latest available trading session.
    instrument_label : str
        Human-readable name used only for log messages.

    Returns
    -------
    pd.DataFrame
        DataFrame with a timezone-naive DatetimeIndex named ``"Date"`` and
        columns ``[Open, High, Low, Close, Adj Close, Volume]`` where
        Yahoo Finance provides them.  Returns an empty DataFrame on failure.

    Notes
    -----
    - The raw data is returned as-is from Yahoo Finance.
    - No imputation, feature engineering, or date-alignment is performed.
    """
    label = instrument_label or ticker
    logger.info("Downloading %-18s  ticker=%-14s  start=%s  end=%s",
                label, ticker, start, end or "latest")

    try:
        df: pd.DataFrame = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=False,   # keep Adj Close as a separate column
            progress=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Download failed for %s (%s): %s", label, ticker, exc)
        return pd.DataFrame()

    if df is None or df.empty:
        logger.warning("No data returned for %s (%s)", label, ticker)
        return pd.DataFrame()

    #  Flatten MultiIndex columns that yfinance >=0.2.x sometimes returns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    #  Ensure the index is a proper DatetimeIndex named "Date"
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df.index.name = "Date"

    #  Strip timezone (NSE timestamps are +05:30; we store tz-naive dates)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    logger.info(
        "  → %d rows  [%s → %s]",
        len(df),
        df.index[0].date(),
        df.index[-1].date(),
    )
    return df


def save_raw_data(
    df: pd.DataFrame,
    output_path: str | Path,
    overwrite: bool = False,
) -> bool:
    """Save a raw DataFrame to CSV.

    The Date index is written as an explicit ``Date`` column so that:

    .. code-block:: python

        pd.read_csv("file.csv", parse_dates=["Date"])

    works cleanly and produces no ``Unnamed: 0`` column.

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame returned by :func:`download_data`.
    output_path : str or Path
        Destination file path (including filename).
    overwrite : bool
        When ``False`` (default) an existing file is **not** overwritten and
        the function returns ``False``.  Set to ``True`` to force replacement.

    Returns
    -------
    bool
        ``True`` if the file was written, ``False`` otherwise.
    """
    output_path = Path(output_path)

    if output_path.exists() and not overwrite:
        logger.warning(
            "File already exists (overwrite=False): %s  — skipped.", output_path
        )
        return False

    if df is None or df.empty:
        logger.error("DataFrame is empty — nothing saved to %s.", output_path)
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write with Date as an explicit column, not an unnamed index
    df.to_csv(output_path, index=True, index_label="Date")
    logger.info("Saved  → %s  (%d rows)", output_path, len(df))
    return True


def load_data(file_path: str | Path) -> pd.DataFrame:
    """Load a raw CSV saved by :func:`save_raw_data`.

    Parameters
    ----------
    file_path : str or Path
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
        DataFrame with a DatetimeIndex named ``"Date"``.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {file_path}")

    df = pd.read_csv(file_path, parse_dates=["Date"], index_col="Date")
    logger.info("Loaded  ← %s  (%d rows)", file_path, len(df))
    return df


def validate_downloaded_data(
    df: pd.DataFrame,
    instrument_label: str = "",
    ticker: str = "",
) -> dict:
    """Run non-destructive basic validation on a raw DataFrame.

    Checks performed
    ----------------
    - Dataset non-empty
    - Date range (first date, last date, row count)
    - Missing values (reported, not filled)
    - Duplicate dates (reported, not removed)
    - Chronological ordering
    - OHLC sanity (where columns exist)
    - Volume non-negative (where column exists)

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame to validate (returned by :func:`download_data` or
        :func:`load_data`).
    instrument_label : str
        Human-readable name for display purposes.
    ticker : str
        Yahoo Finance ticker symbol for display purposes.

    Returns
    -------
    dict
        Validation result dictionary with keys:

        ``instrument``, ``ticker``, ``rows``, ``first_date``, ``last_date``,
        ``columns``, ``missing_values``, ``duplicate_dates``,
        ``is_chronological``, ``ohlc_violations``, ``volume_violations``,
        ``status``  (``"PASS"`` / ``"WARNING"`` / ``"FAILED"``),
        ``notes``  (list of strings).
    """
    result: dict = {
        "instrument": instrument_label,
        "ticker": ticker,
        "rows": 0,
        "first_date": None,
        "last_date": None,
        "columns": [],
        "missing_values": {},
        "total_missing": 0,
        "duplicate_dates": 0,
        "is_chronological": None,
        "ohlc_violations": 0,
        "volume_violations": 0,
        "status": "FAILED",
        "notes": [],
    }

    # ---- Empty dataset
    if df is None or df.empty:
        result["notes"].append("FAILED: DataFrame is empty or None.")
        return result

    result["rows"] = len(df)
    result["columns"] = list(df.columns)

    # ---- Date range
    result["first_date"] = df.index[0].date() if isinstance(df.index[0], datetime) \
        else pd.Timestamp(df.index[0]).date()
    result["last_date"] = df.index[-1].date() if isinstance(df.index[-1], datetime) \
        else pd.Timestamp(df.index[-1]).date()

    # ---- Missing values
    missing = df.isnull().sum()
    result["missing_values"] = {col: int(cnt) for col, cnt in missing.items() if cnt > 0}
    result["total_missing"] = int(missing.sum())
    if result["total_missing"] > 0:
        result["notes"].append(
            f"WARNING: {result['total_missing']} missing value(s) detected "
            f"({result['missing_values']})."
        )

    # ---- Duplicate dates
    dup_count = int(df.index.duplicated().sum())
    result["duplicate_dates"] = dup_count
    if dup_count > 0:
        result["notes"].append(f"WARNING: {dup_count} duplicate date(s) found.")

    # ---- Chronological order
    is_sorted = df.index.is_monotonic_increasing
    result["is_chronological"] = is_sorted
    if not is_sorted:
        result["notes"].append("WARNING: Dates are not in chronological order.")

    # ---- OHLC sanity (only if relevant columns exist)
    ohlc_cols = {"Open", "High", "Low", "Close"}
    present_ohlc = ohlc_cols.intersection(df.columns)
    ohlc_violations = 0
    if len(present_ohlc) == 4:
        violations_mask = (
            (df["High"] < df["Open"])
            | (df["High"] < df["Close"])
            | (df["Low"] > df["Open"])
            | (df["Low"] > df["Close"])
            | (df["High"] < df["Low"])
        )
        ohlc_violations = int(violations_mask.sum())
        result["ohlc_violations"] = ohlc_violations
        if ohlc_violations > 0:
            result["notes"].append(
                f"WARNING: {ohlc_violations} OHLC sanity violation(s) detected."
            )
    else:
        result["notes"].append(
            f"INFO: Partial OHLC columns present ({present_ohlc}); "
            "full OHLC check skipped."
        )

    # ---- Volume non-negative
    vol_violations = 0
    if "Volume" in df.columns:
        vol_violations = int((df["Volume"] < 0).sum())
        result["volume_violations"] = vol_violations
        if vol_violations > 0:
            result["notes"].append(
                f"WARNING: {vol_violations} negative Volume value(s)."
            )

    # ---- Overall status
    critical_flags = (
        result["rows"] == 0
        or dup_count > 0
        or ohlc_violations > 0
        or vol_violations > 0
    )
    warning_flags = result["total_missing"] > 0 or not is_sorted

    if critical_flags:
        result["status"] = "WARNING"
    elif warning_flags:
        result["status"] = "WARNING"
    else:
        result["status"] = "PASS"

    if not result["notes"]:
        result["notes"].append("All checks passed.")

    return result


def verify_ticker(
    ticker: str,
    instrument_label: str = "",
    test_start: str = "2024-01-01",
    test_end: str = "2024-06-30",
) -> dict:
    """Quick verification download to confirm a Yahoo Finance ticker is valid.

    This is used **only** during the ticker-verification stage and is NOT
    used for the final research data download.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker symbol to test.
    instrument_label : str
        Human-readable label for display.
    test_start, test_end : str
        Short date range used for the quick test.

    Returns
    -------
    dict
        Keys: ``ticker``, ``instrument``, ``status``, ``rows``,
        ``first_date``, ``last_date``, ``columns``, ``error``.
    """
    label = instrument_label or ticker
    result = {
        "instrument": label,
        "ticker": ticker,
        "status": "FAILED",
        "rows": 0,
        "first_date": None,
        "last_date": None,
        "columns": [],
        "error": None,
    }

    try:
        df = yf.download(ticker, start=test_start, end=test_end,
                        auto_adjust=False, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        result["status"] = "FAILED"
        return result

    if df is None or df.empty:
        result["status"] = "FAILED"
        result["error"] = "Empty response from Yahoo Finance."
        return result

    result["rows"] = len(df)
    result["first_date"] = str(df.index[0].date())
    result["last_date"] = str(df.index[-1].date())
    result["columns"] = list(df.columns)
    result["status"] = "PASS"
    return result


# ---------------------------------------------------------------------------
# Phase 1 safe collection function
# ---------------------------------------------------------------------------

# Minimum rows expected for a full history download (2019-01-01 → today).
# ~245 trading days/year × 5 years minimum = ~1225. Using 1000 as a floor.
_MIN_ROWS_FULL_HISTORY = 1000

# Latest date threshold: downloaded data must extend at least this close to
# today to be considered a real full-history response (not a stale/partial one).
_MIN_LAST_DATE_OFFSET_DAYS = 30  # must have data within last 30 days


def collect_phase1_data(
    raw_base_dir: str | Path = "data/raw",
    tickers: Optional[dict] = None,
    start: str = DEFAULT_START,
    overwrite: bool = True,
) -> list[dict]:
    """Download and safely save raw OHLCV data for every instrument in the
    verified ticker registry.

    Safety contract
    ---------------
    For **each** ticker:

    1. Download the complete history (``start`` → latest).
    2. Immediately reject (do NOT write) if the response is:
       - Empty / None
       - Fewer than :data:`_MIN_ROWS_FULL_HISTORY` rows
       - Missing required columns (Open, High, Low, Close, Adj Close, Volume)
       - First date later than 2019-06-30 (suspiciously late start)
       - Last date more than :data:`_MIN_LAST_DATE_OFFSET_DAYS` days in the past
         (Yahoo returned stale/partial data)
    3. Only if **all** checks pass: write the CSV to ``raw_base_dir/<subdir>/<output_file>``.
    4. If validation fails: leave the existing CSV completely untouched and
       record a REJECTED status for that ticker.
    5. Never overwrite a good historical dataset with a smaller/incomplete one.

    Parameters
    ----------
    raw_base_dir : str or Path
        Root directory for raw data (e.g. ``"data/raw"``).
    tickers : dict or None
        Ticker mapping identical in shape to :data:`VERIFIED_TICKERS`.
        When ``None`` (default) :data:`VERIFIED_TICKERS` is used.
    start : str
        ISO-8601 start date. Defaults to :data:`DEFAULT_START` (``"2019-01-01"``).
    overwrite : bool
        If ``True`` (default) existing CSVs are replaced when the new download
        passes validation.  If ``False`` existing files are skipped.

    Returns
    -------
    list[dict]
        One result dict per ticker with keys:
        ``key``, ``label``, ``ticker``, ``status``, ``rows``,
        ``first_date``, ``last_date``, ``output_path``, ``rejection_reason``.
    """
    from datetime import date as _date

    tickers   = tickers or VERIFIED_TICKERS
    base      = Path(raw_base_dir)
    results   = []
    today     = _date.today()
    min_last  = pd.Timestamp(today) - pd.Timedelta(days=_MIN_LAST_DATE_OFFSET_DAYS)

    REQUIRED_COLS = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
    EARLY_START_CUTOFF = pd.Timestamp("2019-06-30")

    header = f"{'Key':<18} {'Label':<20} {'Status':<10} {'Rows':>6}  {'First':<12} {'Last':<12}  Note"
    sep    = "-" * 100
    print(sep)
    print("PHASE 1 DATA COLLECTION  (safe mode — validate before write)")
    print(f"  Start date : {start}")
    print(f"  Base dir   : {base.resolve()}")
    print(f"  Min rows   : {_MIN_ROWS_FULL_HISTORY}")
    print(f"  Max last-date lag : {_MIN_LAST_DATE_OFFSET_DAYS} days")
    print(sep)
    print(header)
    print(sep)

    for key, meta in tickers.items():
        sym    = meta["ticker"]
        label  = meta["label"]
        subdir = meta["subdir"]
        fname  = meta["output_file"]
        out    = base / subdir / fname

        row = {
            "key": key, "label": label, "ticker": sym,
            "status": "FAILED", "rows": 0,
            "first_date": None, "last_date": None,
            "output_path": str(out), "rejection_reason": "",
        }

        # ── 1. Download ────────────────────────────────────────────────────
        df = download_data(ticker=sym, start=start, end=None, instrument_label=label)

        # ── 2. Pre-write validation gates ─────────────────────────────────
        reason = ""

        if df is None or df.empty:
            reason = "Empty / None response from Yahoo Finance."

        elif len(df) < _MIN_ROWS_FULL_HISTORY:
            reason = (
                f"REJECTED: only {len(df)} rows returned "
                f"(minimum required: {_MIN_ROWS_FULL_HISTORY}). "
                "Yahoo Finance returned suspiciously incomplete history. "
                "Existing file left untouched."
            )

        else:
            # Flatten MultiIndex just in case
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            missing_cols = REQUIRED_COLS - set(df.columns)
            if missing_cols:
                reason = f"REJECTED: missing required columns {missing_cols}."

            elif df.index[0] > EARLY_START_CUTOFF:
                reason = (
                    f"REJECTED: first date {df.index[0].date()} is later than "
                    f"{EARLY_START_CUTOFF.date()} — history appears truncated."
                )

            elif df.index[-1] < min_last:
                reason = (
                    f"REJECTED: last date {df.index[-1].date()} is more than "
                    f"{_MIN_LAST_DATE_OFFSET_DAYS} days old — Yahoo returned stale data."
                )

        if reason:
            row["rejection_reason"] = reason
            row["status"] = "REJECTED"
            if not df.empty:
                row["rows"] = len(df)
                row["first_date"] = str(df.index[0].date())
                row["last_date"]  = str(df.index[-1].date())
            note = reason.split(".")[0]           # first sentence for table
            print(f"{key:<18} {label:<20} {'REJECTED':<10} {row['rows']:>6}  "
                  f"{'N/A':<12} {'N/A':<12}  {note}")
            results.append(row)
            continue

        # ── 3. Deeper validation (non-blocking warnings) ───────────────────
        vr = validate_downloaded_data(df, instrument_label=label, ticker=sym)

        row["rows"]       = len(df)
        row["first_date"] = str(df.index[0].date())
        row["last_date"]  = str(df.index[-1].date())

        # ── 4. Write only after all gates pass ─────────────────────────────
        if out.exists() and not overwrite:
            row["status"] = "SKIPPED"
            row["rejection_reason"] = "File exists and overwrite=False."
            note = "existing file kept (overwrite=False)"
            print(f"{key:<18} {label:<20} {'SKIPPED':<10} {row['rows']:>6}  "
                  f"{row['first_date']:<12} {row['last_date']:<12}  {note}")
            results.append(row)
            continue

        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=True, index_label="Date")

        row["status"] = vr["status"]   # PASS / WARNING
        note = vr["notes"][0] if vr["notes"] else ""
        print(f"{key:<18} {label:<20} {row['status']:<10} {row['rows']:>6}  "
              f"{row['first_date']:<12} {row['last_date']:<12}  {note}")
        results.append(row)

    print(sep)

    # ── 5. Summary ─────────────────────────────────────────────────────────
    n_pass     = sum(1 for r in results if r["status"] in ("PASS", "WARNING"))
    n_rejected = sum(1 for r in results if r["status"] == "REJECTED")
    n_skipped  = sum(1 for r in results if r["status"] == "SKIPPED")
    print(f"\nPhase 1 complete — SAVED:{n_pass}  REJECTED:{n_rejected}  SKIPPED:{n_skipped}")
    if n_rejected:
        print("\nREJECTED tickers (existing files NOT modified):")
        for r in results:
            if r["status"] == "REJECTED":
                print(f"  {r['label']:<20}  {r['rejection_reason']}")
    print(sep)

    return results

