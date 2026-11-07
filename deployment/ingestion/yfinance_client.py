"""
deployment/ingestion/yfinance_client.py
=======================================
Production Yahoo Finance (yfinance) Market Data Client.

Primary daily EOD data provider for:
  - 8 required index series: NIFTY 50, NIFTY BANK, NIFTY AUTO, NIFTY FMCG,
    NIFTY IT, NIFTY METAL, NIFTY PHARMA, INDIA VIX.
  - Zero authentication / TOTP / static IP requirements.
  - Bounded exponential backoff retries.
  - Idempotent and normalized candle output.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd
import yfinance as yf

logger = logging.getLogger("yfinance_client")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [yfinance_client]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Exact canonical symbol to Yahoo Finance ticker mapping
INDEX_TICKER_MAP: Dict[str, str] = {
    "NIFTY 50": "^NSEI",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY AUTO": "^CNXAUTO",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY IT": "^CNXIT",
    "NIFTY METAL": "^CNXMETAL",
    "NIFTY PHARMA": "^CNXPHARMA",
    "INDIA VIX": "^INDIAVIX",
}

# Reverse mapping: ticker -> canonical symbol
TICKER_TO_SYMBOL_MAP: Dict[str, str] = {v: k for k, v in INDEX_TICKER_MAP.items()}


class YahooFinanceClient:
    """
    Client for downloading daily EOD OHLC candles from Yahoo Finance.
    """

    def __init__(
        self,
        ticker_map: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
        retry_delay_seconds: float = 2.0,
        request_timeout_seconds: int = 15,
    ) -> None:
        self.ticker_map = ticker_map or INDEX_TICKER_MAP.copy()
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.request_timeout_seconds = request_timeout_seconds

    @property
    def is_configured(self) -> bool:
        """yfinance requires no API credentials."""
        return True

    def _normalize_date_range(self, from_date: str, to_date: str) -> Tuple[str, str]:
        """
        Ensures to_date covers the entire trading session.
        yfinance history() end parameter is exclusive, so we add 1 day to to_date.
        """
        f_dt = datetime.strptime(from_date, "%Y-%m-%d").date()
        t_dt = datetime.strptime(to_date, "%Y-%m-%d").date()
        if f_dt > t_dt:
            raise ValueError(f"from_date ({from_date}) cannot be after to_date ({to_date})")
        
        # yfinance end is exclusive; advance by 1 day
        yf_end_str = (t_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        return from_date, yf_end_str

    def fetch_historical_candles(
        self,
        symbol_name: str,
        from_date: str,
        to_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Download historical daily candles for a single symbol between from_date and to_date (inclusive).
        
        Returns:
            List of candle dicts:
            {
                "symbol": str,
                "date": "YYYY-MM-DD",
                "open": float,
                "high": float,
                "low": float,
                "close": float,
                "adj_close": float,
                "volume": int,
                "source": "yahoo_finance"
            }
        """
        if symbol_name not in self.ticker_map:
            raise ValueError(
                f"Unknown symbol: '{symbol_name}'. Allowed: {list(self.ticker_map.keys())}"
            )

        ticker = self.ticker_map[symbol_name]
        yf_start, yf_end = self._normalize_date_range(from_date, to_date)
        
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Fetching {symbol_name} ({ticker}) from {from_date} to {to_date} "
                    f"(attempt {attempt}/{self.max_retries})..."
                )
                t = yf.Ticker(ticker)
                df = t.history(
                    start=yf_start,
                    end=yf_end,
                    interval="1d",
                    auto_adjust=False,
                    timeout=self.request_timeout_seconds,
                )

                if df is None or df.empty:
                    logger.warning(
                        f"Empty DataFrame returned for {symbol_name} ({ticker}) "
                        f"between {from_date} and {to_date}."
                    )
                    return []

                # Clean timezone in index
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)

                candles: List[Dict[str, Any]] = []
                for ts, row in df.iterrows():
                    d_str = ts.strftime("%Y-%m-%d")
                    # Bound to the requested window strictly
                    if d_str < from_date or d_str > to_date:
                        continue

                    # Validate non-null OHLC
                    o = float(row.get("Open", 0.0))
                    h = float(row.get("High", 0.0))
                    l = float(row.get("Low", 0.0))
                    c = float(row.get("Close", 0.0))
                    ac = float(row.get("Adj Close", c))
                    v = int(row.get("Volume", 0)) if pd.notnull(row.get("Volume")) else 0

                    if pd.isna(o) or pd.isna(h) or pd.isna(l) or pd.isna(c):
                        logger.warning(f"Skipping candle with NaN OHLC for {symbol_name} on {d_str}")
                        continue

                    if o <= 0 or h <= 0 or l <= 0 or c <= 0:
                        logger.warning(f"Skipping candle with non-positive values for {symbol_name} on {d_str}")
                        continue

                    candles.append({
                        "symbol": symbol_name,
                        "date": d_str,
                        "open": o,
                        "high": h,
                        "low": l,
                        "close": c,
                        "adj_close": ac,
                        "volume": v,
                        "source": "yahoo_finance",
                    })

                logger.info(f"Successfully fetched {len(candles)} candles for {symbol_name}.")
                return candles

            except Exception as e:
                last_exception = e
                logger.warning(f"Error fetching {symbol_name} (attempt {attempt}): {e}")
                if attempt < self.max_retries:
                    sleep_time = self.retry_delay_seconds * (2 ** (attempt - 1))
                    time.sleep(sleep_time)

        raise RuntimeError(
            f"Failed to fetch {symbol_name} ({ticker}) after {self.max_retries} attempts: {last_exception}"
        )

    def fetch_all_historical(
        self,
        from_date: str,
        to_date: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Download historical candles for all 8 universe indices.
        """
        results: Dict[str, List[Dict[str, Any]]] = {}
        for symbol in self.ticker_map.keys():
            candles = self.fetch_historical_candles(symbol, from_date, to_date)
            results[symbol] = candles
        return results

    def fetch_daily_eod(
        self,
        target_date: str,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Fetch completed daily EOD candle for each of the 8 indices for a specific target session date.
        """
        results: Dict[str, Optional[Dict[str, Any]]] = {}
        for symbol in self.ticker_map.keys():
            candles = self.fetch_historical_candles(symbol, target_date, target_date)
            # Find candle matching target_date
            matched = [c for c in candles if c["date"] == target_date]
            if matched:
                results[symbol] = matched[0]
            else:
                results[symbol] = None
        return results

