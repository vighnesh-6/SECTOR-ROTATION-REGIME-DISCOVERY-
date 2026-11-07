"""
deployment/engine/feature_adapter.py
====================================
Production Market Feature Adapter for Incremental Inference.

Implements:
  1. Exact 42-feature calculation methodology matching research baseline:
     - NIFTY 50 (5 features): Return_20D, Return_60D, NIFTY50_Momentum_20D,
                              NIFTY50_Momentum_60D, NIFTY50_Market_Trend_200D
     - INDIA VIX (1 feature): VIX_Close
     - 6 Sectors (36 features): For each sector in [AUTO, BANK, FMCG, IT, METAL, PHARMA]:
                                Return_20D, Return_60D, Relative_Strength_20D,
                                Relative_Strength_60D, Volatility_20D, Volatility_60D
  2. Incremental calculation using trailing historical candles stored in Neon PostgreSQL.
  3. Numerical validation against frozen RobustScaler parameters.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from database.connection import NeonClient, get_db_client

# Canonical Sector & Index Names
SECTOR_NAMES: List[str] = ["AUTO", "BANK", "FMCG", "IT", "METAL", "PHARMA"]
REQUIRED_INDEX_SYMBOLS: List[str] = [
    "NIFTY 50",
    "INDIA VIX",
    "NIFTY AUTO",
    "NIFTY BANK",
    "NIFTY FMCG",
    "NIFTY IT",
    "NIFTY METAL",
    "NIFTY PHARMA",
]

# Minimum trailing sessions required for 200-day SMA + 1 session shift
MIN_LOOKBACK_SESSIONS: int = 201
DEFAULT_FETCH_LOOKBACK: int = 250


class MarketFeatureAdapter:
    """
    Adapter for computing the canonical 42-feature dataset from database candles.
    """

    def __init__(
        self,
        db_client: Optional[NeonClient] = None,
        models_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self.db = db_client or get_db_client()

        if models_dir is None:
            models_dir = Path(__file__).resolve().parent / "models"
        else:
            models_dir = Path(models_dir)

        scaler_path = models_dir / "frozen_scaler.json"
        if not scaler_path.exists():
            raise FileNotFoundError(f"Missing frozen scaler parameters: {scaler_path}")

        with open(scaler_path, "r", encoding="utf-8") as f:
            scaler_data = json.load(f)

        self.feature_names: List[str] = scaler_data["feature_names"]
        self.center: np.ndarray = np.array(scaler_data["center"], dtype=np.float64)
        self.scale: np.ndarray = np.array(scaler_data["scale"], dtype=np.float64)

        assert len(self.feature_names) == 42, f"Expected 42 features, got {len(self.feature_names)}"

    def fetch_trailing_prices(
        self,
        as_of_date: Union[str, date],
        lookback_sessions: int = DEFAULT_FETCH_LOOKBACK,
    ) -> pd.DataFrame:
        """
        Fetch trailing daily closing prices up to as_of_date from Neon PostgreSQL.

        Args:
          as_of_date: Evaluation date string ('YYYY-MM-DD') or date object.
          lookback_sessions: Number of historical trading sessions to retrieve (default 250).

        Returns:
          pd.DataFrame: Wide DataFrame indexed by Date with 8 symbol columns.
        """
        date_str = str(as_of_date)[:10]

        query = """
            SELECT symbol, date::text as date, close
            FROM index_candles_daily
            WHERE date <= $1
            ORDER BY date DESC, symbol ASC;
        """
        # Fetch up to lookback_sessions * 8 records
        limit_count = lookback_sessions * len(REQUIRED_INDEX_SYMBOLS) * 2
        paged_query = f"""
            SELECT symbol, date::text as date, close
            FROM (
                SELECT symbol, date, close
                FROM index_candles_daily
                WHERE date <= $1
                ORDER BY date DESC
                LIMIT {limit_count}
            ) sub
            ORDER BY date ASC, symbol ASC;
        """
        rows = self.db.query(paged_query, params=[date_str])
        if not rows:
            raise ValueError(f"No candle data found in Neon for dates <= {date_str}")

        df = pd.DataFrame(rows)
        df["close"] = df["close"].astype(float)
        df["date"] = pd.to_datetime(df["date"])

        # Pivot to wide format
        pivot_df = df.pivot(index="date", columns="symbol", values="close").sort_index()

        # Validate that target date exists
        target_ts = pd.to_datetime(date_str)
        if target_ts not in pivot_df.index:
            raise KeyError(f"Target date {date_str} not found in database price series.")

        # Truncate to sessions up to target_ts
        pivot_df = pivot_df.loc[:target_ts]

        # Verify all 8 index symbols are present
        missing_symbols = [s for s in REQUIRED_INDEX_SYMBOLS if s not in pivot_df.columns]
        if missing_symbols:
            raise KeyError(f"Missing required index series in database: {missing_symbols}")

        # Slice to the trailing lookback_sessions
        if len(pivot_df) < MIN_LOOKBACK_SESSIONS:
            raise ValueError(
                f"Insufficient candle history for 200D trend calculation: "
                f"requires at least {MIN_LOOKBACK_SESSIONS} sessions, got {len(pivot_df)}."
            )

        window_df = pivot_df.iloc[-lookback_sessions:] if len(pivot_df) >= lookback_sessions else pivot_df
        return window_df[REQUIRED_INDEX_SYMBOLS]

    def compute_features_from_prices(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute the 42 canonical features from a wide DataFrame of closing prices.

        Args:
          price_df: DataFrame indexed by DatetimeIndex containing all 8 REQUIRED_INDEX_SYMBOLS.

        Returns:
          pd.DataFrame: DataFrame containing exactly the 42 features in canonical order.
        """
        for sym in REQUIRED_INDEX_SYMBOLS:
            if sym not in price_df.columns:
                raise KeyError(f"Missing required price column: {sym}")

        features = pd.DataFrame(index=price_df.index)

        # 1. NIFTY 50 Features (5 features)
        n50 = price_df["NIFTY 50"]
        features["Return_20D"] = (n50 / n50.shift(20)) - 1.0
        features["Return_60D"] = (n50 / n50.shift(60)) - 1.0
        features["NIFTY50_Momentum_20D"] = n50 / n50.rolling(window=20).mean()
        features["NIFTY50_Momentum_60D"] = n50 / n50.rolling(window=60).mean()
        features["NIFTY50_Market_Trend_200D"] = n50 / n50.rolling(window=200).mean()

        # 2. VIX Feature (1 feature)
        features["VIX_Close"] = price_df["INDIA VIX"]

        # 3. Sector Features (6 sectors * 6 features = 36 features)
        for s in SECTOR_NAMES:
            sec_sym = f"NIFTY {s}"
            sec_close = price_df[sec_sym]

            # Trailing simple returns
            r20 = (sec_close / sec_close.shift(20)) - 1.0
            r60 = (sec_close / sec_close.shift(60)) - 1.0

            # Daily log returns for realized volatility
            log_returns = np.log(sec_close / sec_close.shift(1))
            v20 = log_returns.rolling(window=20).std(ddof=1) * np.sqrt(252.0)
            v60 = log_returns.rolling(window=60).std(ddof=1) * np.sqrt(252.0)

            features[f"{s}_Return_20D"] = r20
            features[f"{s}_Return_60D"] = r60
            features[f"{s}_Relative_Strength_20D"] = r20 - features["Return_20D"]
            features[f"{s}_Relative_Strength_60D"] = r60 - features["Return_60D"]
            features[f"{s}_Volatility_20D"] = v20
            features[f"{s}_Volatility_60D"] = v60

        # Enforce exact canonical 42-feature column ordering
        return features[self.feature_names]

    def compute_features_for_date(
        self,
        as_of_date: Union[str, date],
        lookback_sessions: int = DEFAULT_FETCH_LOOKBACK,
    ) -> Dict[str, float]:
        """
        Incremental production entrypoint: Computes the 42-feature dictionary for a single date.
        """
        date_str = str(as_of_date)[:10]
        prices = self.fetch_trailing_prices(as_of_date=date_str, lookback_sessions=lookback_sessions)
        feats_df = self.compute_features_from_prices(prices)

        target_ts = pd.to_datetime(date_str)
        if target_ts not in feats_df.index:
            raise KeyError(f"Date {date_str} not in computed feature index.")

        row = feats_df.loc[target_ts]
        if row.isna().any():
            nan_cols = row[row.isna()].index.tolist()
            raise ValueError(f"Computed features on {date_str} contain NaN values: {nan_cols}")

        return {k: float(row[k]) for k in self.feature_names}

    def scale_feature_dict(self, features_dict: Dict[str, float]) -> np.ndarray:
        """
        Transform unscaled 42-feature dictionary using frozen RobustScaler parameters.
        Formula: (x - center) / scale.
        """
        x = np.empty(42, dtype=np.float64)
        for i, feat in enumerate(self.feature_names):
            if feat not in features_dict:
                raise KeyError(f"Missing required feature: {feat}")
            val = float(features_dict[feat])
            if np.isnan(val) or np.isinf(val):
                raise ValueError(f"Feature '{feat}' has non-finite value: {val}")
            x[i] = val

        return (x - self.center) / self.scale

    def store_features(
        self,
        as_of_date: Union[str, date],
        period: str = "live",
    ) -> Dict[str, Any]:
        """
        Compute features for as_of_date and upsert into market_features_daily.
        """
        date_str = str(as_of_date)[:10]
        raw_dict = self.compute_features_for_date(date_str)
        scaled_arr = self.scale_feature_dict(raw_dict)
        scaled_dict = {feat: float(scaled_arr[i]) for i, feat in enumerate(self.feature_names)}

        upsert_sql = """
            INSERT INTO market_features_daily (date, period, features_raw, features_robust_scaled)
            VALUES ($1, $2, $3::jsonb, $4::jsonb)
            ON CONFLICT (date) DO UPDATE
            SET period = EXCLUDED.period,
                features_raw = EXCLUDED.features_raw,
                features_robust_scaled = EXCLUDED.features_robust_scaled,
                created_at = NOW();
        """
        self.db.execute(
            upsert_sql,
            params=[
                date_str,
                period,
                json.dumps(raw_dict),
                json.dumps(scaled_dict),
            ],
        )

        return {
            "status": "STORED",
            "date": date_str,
            "period": period,
            "feature_count": 42,
        }

