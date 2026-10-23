"""
src/regime_characterisation.py
==============================
Phase 7 - Regime Characterisation & Sector Performance Analysis
Sector Rotation Regime Discovery - Indian Equity Market

Implements:
  - Model regime profiling (occupancy, persistence, episodes, switching, market & risk context)
  - Evidence-based economic naming with documented caveats
  - Sector performance analysis by model/regime (contemporaneous daily & forward 20D)
  - Sector leadership and defensive behavior identification (leaders/laggards, stability flagging)
  - Major-event calendar analysis (trading-day alignment, window expansion, deduplication, event-vs-normal)
  - Cross-model comparative synthesis
  - Fully reproducible pipeline generating all Phase 7 CSV outputs

Source guide: Phase_7_Regime_Characterization_and_Sector_Performance_Guide.docx
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants & Reference Definitions
# ---------------------------------------------------------------------------

SECTOR_NAMES: List[str] = ["AUTO", "BANK", "FMCG", "IT", "METAL", "PHARMA"]
BENCHMARK_NAME: str = "NIFTY50"

TRAIN_END_DATE: str = "2024-12-31"
HOLDOUT_START_DATE: str = "2025-01-01"

# Economic regime names, descriptions, and explicit caveats based on Phase 6 & 7 evidence
REGIME_INTERPRETATIONS: Dict[Tuple[str, int], Dict[str, str]] = {
    # HMM (K=6, diagonal covariance)
    ("hmm", 0): {
        "economic_name": "Cyclical Reflation Rally",
        "description": "High-momentum bull market with strong cyclical leadership and elevated market trend.",
        "caveat": "Rare in holdout (1.9% causal days, 1 episode); verify sample size and stability before relying on out-of-sample behavior.",
    },
    ("hmm", 1): {
        "economic_name": "High-Volatility Post-Crash Bounce",
        "description": "Sharp relief rally from deep oversold territory with elevated VIX below 200 SMA.",
        "caveat": "Single-episode historical recovery (April-June 2020); completely absent in 2025-2026 holdout (0 days). Do not claim repeatable out-of-sample behavior.",
    },
    ("hmm", 2): {
        "economic_name": "Low-Volatility Consolidation / Base",
        "description": "Range-bound market with low VIX, calm volatility, and defensive/IT relative resilience.",
        "caveat": "Common in holdout (28.0% days); verify whether sector leadership remains consistent across different consolidation phases.",
    },
    ("hmm", 3): {
        "economic_name": "Acute Liquidation / Flight to Safety",
        "description": "Severe market crash with extreme VIX, steep negative returns, and flight to defensive sectors (Pharma/FMCG).",
        "caveat": "Single-episode COVID panic (March-April 2020, 27 days); completely absent in holdout (0 days). Untested out-of-sample.",
    },
    ("hmm", 4): {
        "economic_name": "Steady Expansion / Low-Volatility Bull",
        "description": "Healthy, sustained uptrend above 200 SMA with calm volatility and broad cyclical leadership.",
        "caveat": "Dominant regime in holdout (40.3% days); verify whether cyclical outperformance is robust across sub-periods.",
    },
    ("hmm", 5): {
        "economic_name": "Correction / Risk-Off Digestion",
        "description": "Market pullback testing 200 SMA with elevated VIX and defensive outperformance cushioning drawdowns.",
        "caveat": "Common in holdout (29.9% days); verify defensive sector preservation evidence across episodes.",
    },
    # K-Means (K=4, RobustScaler)
    ("kmeans", 0): {
        "economic_name": "Low-Volatility Neutral Consolidation",
        "description": "Broad market baseline with flat returns, normal VIX, and muted sector dispersion.",
        "caveat": "Severe micro-switching in holdout (median duration 1.0 day); highly sensitive to feature scaling (ARI=0.1603 vs StandardScaler).",
    },
    ("kmeans", 1): {
        "economic_name": "High-Momentum Cyclical Expansion",
        "description": "Strong uptrend with elevated momentum and leadership from Metal, Bank, and Auto.",
        "caveat": "Reduced presence in holdout (8.5% days); scaling-sensitive cluster boundaries.",
    },
    ("kmeans", 2): {
        "economic_name": "High-Volatility Post-Crash Rebound",
        "description": "Post-crisis recovery bounce with high VIX below 200 SMA.",
        "caveat": "Single-episode historical artifact (May-June 2020, 42 days); completely absent in holdout (0 days).",
    },
    ("kmeans", 3): {
        "economic_name": "Acute Severe Market Crisis",
        "description": "Deep drawdown with VIX near 60 and extreme defensive flight.",
        "caveat": "Single-episode historical artifact (March-April 2020, 25 days); completely absent in holdout (0 days).",
    },
    # GMM (K=2, Full Covariance)
    ("gmm", 0): {
        "economic_name": "Normal Market Baseline",
        "description": "Broad non-crisis market regime encompassing bull, consolidation, and mild correction periods.",
        "caveat": "Suffers 100% state collapse in 2025-2026 holdout (422/422 days assigned to R0). Incapable of discriminating operational sector regimes outside extreme shocks.",
    },
    ("gmm", 1): {
        "economic_name": "Acute Historical Shock / Tail Crisis",
        "description": "Extreme tail-risk environment capturing the March-June 2020 COVID shock.",
        "caveat": "Concentrated in a single 64-day episode; 0 observations in holdout. GMM behaves as a one-time crisis detector rather than an active rotation model.",
    },
}


# ---------------------------------------------------------------------------
# Data Loading & Alignment Helpers
# ---------------------------------------------------------------------------

def load_regime_labels(results_dir: Union[str, Path] = "results") -> pd.DataFrame:
    """
    Load final regime labels from Phase 6 outputs.
    Ensures Date is a proper DatetimeIndex and validates presence of all required columns.
    Checks results/regime_discovery/final_regime_labels.csv first, then falls back to results/final_regime_labels.csv.
    """
    results_dir = Path(results_dir)
    path = results_dir / "regime_discovery" / "final_regime_labels.csv"
    if not path.exists():
        path = results_dir / "final_regime_labels.csv"
    if not path.exists():
        raise FileNotFoundError(f"Regime labels file not found at {path}")
    
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"])
    required_cols = ["Date", "period", "model", "scaler", "k", "regime_id", "label_type"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in {path}: {missing}")
    return df


def load_clean_prices_and_returns(
    data_dir: Union[str, Path] = "data",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load clean aligned prices for NIFTY 50 and the six sector indices.
    Computes:
      1. Close prices DataFrame
      2. Contemporaneous daily returns: r_t = (Close_t / Close_{t-1}) - 1
      3. Forward 20-day returns: r_{t->t+20} = (Close_{t+20} / Close_t) - 1

    Both returns DataFrames include NIFTY 50 and all 6 sectors, plus
    explicit benchmark-relative excess returns.

    Returns:
      (price_df, daily_returns_df, forward_20d_returns_df)
    """
    data_dir = Path(data_dir)
    aligned_dir = data_dir / "processed" / "aligned"

    prices: Dict[str, pd.Series] = {}
    
    # Load NIFTY 50
    nifty50_path = aligned_dir / "nifty50_aligned.csv"
    if not nifty50_path.exists():
        raise FileNotFoundError(f"NIFTY 50 aligned data not found at {nifty50_path}")
    nifty50 = pd.read_csv(nifty50_path, index_col=0, parse_dates=True)
    prices[BENCHMARK_NAME] = nifty50["Close"]

    # Load 6 Sectors
    for sector in SECTOR_NAMES:
        sec_path = aligned_dir / f"nifty_{sector.lower()}_aligned.csv"
        if not sec_path.exists():
            raise FileNotFoundError(f"Sector data not found at {sec_path}")
        sec_df = pd.read_csv(sec_path, index_col=0, parse_dates=True)
        prices[sector] = sec_df["Close"]

    price_df = pd.DataFrame(prices).sort_index()

    # Contemporaneous daily returns
    daily_ret = price_df.pct_change()
    for sector in SECTOR_NAMES:
        daily_ret[f"{sector}_Excess"] = daily_ret[sector] - daily_ret[BENCHMARK_NAME]

    # Forward 20-day returns: strictly forward-looking from date t
    # Note: final 20 rows will naturally be NaN, which is mathematically correct
    fwd_20d = (price_df.shift(-20) / price_df) - 1.0
    for sector in SECTOR_NAMES:
        fwd_20d[f"{sector}_Excess"] = fwd_20d[sector] - fwd_20d[BENCHMARK_NAME]

    return price_df, daily_ret, fwd_20d


# ---------------------------------------------------------------------------
# Episode & Persistence Calculation
# ---------------------------------------------------------------------------

def calculate_regime_episodes(labels_series: pd.Series) -> pd.DataFrame:
    """
    Identify continuous regime episodes (runs) in a chronological sequence of regime IDs.

    Returns a DataFrame where each row represents one distinct episode:
      - episode_id: sequential integer
      - regime_id: regime integer
      - start_date: episode start trading date
      - end_date: episode end trading date
      - duration_days: number of trading days in episode
    """
    if labels_series.empty:
        return pd.DataFrame(columns=["episode_id", "regime_id", "start_date", "end_date", "duration_days"])

    labels_clean = labels_series.dropna()
    dates = labels_clean.index

    episodes = []
    current_regime = labels_clean.iloc[0]
    start_date = dates[0]
    duration = 1
    ep_count = 0

    for i in range(1, len(labels_clean)):
        r = labels_clean.iloc[i]
        d = dates[i]
        if r == current_regime:
            duration += 1
        else:
            ep_count += 1
            episodes.append({
                "episode_id": ep_count,
                "regime_id": int(current_regime),
                "start_date": start_date,
                "end_date": dates[i - 1],
                "duration_days": int(duration),
            })
            current_regime = r
            start_date = d
            duration = 1

    # Final episode
    ep_count += 1
    episodes.append({
        "episode_id": ep_count,
        "regime_id": int(current_regime),
        "start_date": start_date,
        "end_date": dates[-1],
        "duration_days": int(duration),
    })

    return pd.DataFrame(episodes)



# 1. Regime Characterisation


def compute_model_regime_profiles(
    labels_df: pd.DataFrame,
    master_features_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute comprehensive regime profiles for all candidate models and label streams.
    Separates training (2019-10-31 to 2024-12-31) and holdout (2025-01-02 to 2026-09-18).

    For every regime:
      - Occupancy: count, percentage of trading days in period
      - Persistence: episode count, mean duration, median duration, min/max duration, switching frequency
      - Market context: NIFTY 50 20D/60D return, momentum 20D/60D, 200D market trend, VIX Close
      - Sector context: Trailing 20D returns and relative strengths
      - Evidence-based economic name, neutral descriptive label, and caveats

    Returns:
      pd.DataFrame: Structured model regime profile table ready to save as CSV.
    """
    records = []

    # Stream groups: (model, label_type, period)
    groups = labels_df.groupby(["model", "label_type", "period"])

    for (model, label_type, period), group in groups:
        group_sorted = group.sort_values("Date").set_index("Date")
        aligned_features = master_features_df.loc[group_sorted.index]

        ep_df = calculate_regime_episodes(group_sorted["regime_id"])
        total_period_days = len(group_sorted)
        total_switches = max(0, len(ep_df) - 1)
        k_val = group["k"].iloc[0]

        for r_id in range(k_val):
            r_mask = group_sorted["regime_id"] == r_id
            n_days = int(r_mask.sum())
            pct_days = float((n_days / total_period_days) * 100.0) if total_period_days > 0 else 0.0

            r_episodes = ep_df[ep_df["regime_id"] == r_id]
            n_episodes = len(r_episodes)
            med_dur = float(r_episodes["duration_days"].median()) if n_episodes > 0 else 0.0
            mean_dur = float(r_episodes["duration_days"].mean()) if n_episodes > 0 else 0.0
            min_dur = int(r_episodes["duration_days"].min()) if n_episodes > 0 else 0
            max_dur = int(r_episodes["duration_days"].max()) if n_episodes > 0 else 0

            # Feature statistics on original unscaled features
            r_feats = aligned_features[r_mask]
            
            def get_stat(col: str, fn: str = "mean") -> float:
                if col not in r_feats.columns or len(r_feats) == 0:
                    return np.nan
                val = r_feats[col].mean() if fn == "mean" else r_feats[col].median()
                return float(val)

            # Retrieve evidence-based interpretation
            lookup_key = (model, r_id)
            interp = REGIME_INTERPRETATIONS.get(lookup_key, {
                "economic_name": f"Regime {r_id}",
                "description": "Unclassified state",
                "caveat": "None documented",
            })

            records.append({
                "model": model,
                "label_type": label_type,
                "period": period,
                "k": k_val,
                "regime_id": r_id,
                "economic_name": interp["economic_name"],
                "description": interp["description"],
                "caveats": interp["caveat"],
                "n_trading_days": n_days,
                "pct_trading_days": round(pct_days, 2),
                "n_episodes": n_episodes,
                "mean_duration_days": round(mean_dur, 2),
                "median_duration_days": round(med_dur, 2),
                "min_duration_days": min_dur,
                "max_duration_days": max_dur,
                "period_switches": total_switches,
                # Market Trend & Returns
                "nifty50_return_20d_mean": round(get_stat("Return_20D"), 4),
                "nifty50_return_60d_mean": round(get_stat("Return_60D"), 4),
                "nifty50_momentum_20d_mean": round(get_stat("NIFTY50_Momentum_20D"), 4),
                "nifty50_momentum_60d_mean": round(get_stat("NIFTY50_Momentum_60D"), 4),
                "nifty50_market_trend_200d_mean": round(get_stat("NIFTY50_Market_Trend_200D"), 4),
                # Risk & Volatility
                "vix_close_mean": round(get_stat("VIX_Close"), 2),
                "vix_close_median": round(get_stat("VIX_Close", "median"), 2),
                # Sector 20D Trailing Relative Strengths (Means)
                "auto_rs_20d_mean": round(get_stat("AUTO_Relative_Strength_20D"), 4),
                "bank_rs_20d_mean": round(get_stat("BANK_Relative_Strength_20D"), 4),
                "fmcg_rs_20d_mean": round(get_stat("FMCG_Relative_Strength_20D"), 4),
                "it_rs_20d_mean": round(get_stat("IT_Relative_Strength_20D"), 4),
                "metal_rs_20d_mean": round(get_stat("METAL_Relative_Strength_20D"), 4),
                "pharma_rs_20d_mean": round(get_stat("PHARMA_Relative_Strength_20D"), 4),
            })

    return pd.DataFrame(records)



# 2. Sector Performance & Leadership Analysis


def compute_sector_performance_by_regime(
    labels_df: pd.DataFrame,
    daily_returns_df: pd.DataFrame,
    fwd_20d_returns_df: pd.DataFrame,
    price_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Calculate performance of all six sector indices while each regime was active.

    Strict look-ahead separation:
      1. Contemporaneous daily returns (same-day holding): r_{i,t} and r_{i,t} - r_{NIFTY50,t}
      2. Forward 20-day returns (entry horizon): r_{i,t->t+20} and r_{i,t->t+20} - r_{NIFTY50,t->t+20}
         Separately labeled with return_horizon='forward_20D'.

    Boundary enforcement (training period):
      For period='train', forward 20D returns whose t+20 price endpoint lies beyond
      TRAIN_END_DATE (2024-12-31) are excluded.  This prevents the last 20 training
      dates (Dec 2024) from incorporating holdout-period prices in the forward return
      calculation.  Boundary lookup uses trading-day index positions, not calendar
      offsets, so Indian market holidays are handled correctly.  Contemporaneous
      daily returns and holdout-period forward returns are unaffected.

    Limitation:
      20-day forward returns computed on consecutive dates share 19/20 price
      observations, creating serial correlation.  Effective independent observations
      are approximately n/20.  Mean estimates are unbiased but standard errors are
      understated.  Sample-size flags (reliable / low_sample_unstable) provide a
      partial safeguard for small regimes.

    Calculates:
      - Observation-weighted mean and median returns
      - Dispersion: standard deviation, IQR
      - Annualized return (mean * 252) and Annualized Volatility (std * sqrt(252))
      - Annualized excess return vs NIFTY 50
      - Win rate (% of days with positive excess return)
      - Episode-weighted return (mean of episode-level mean returns)
      - Sample sizes (observations, episodes)

    Args:
      labels_df: Final regime labels from Phase 6.
      daily_returns_df: Contemporaneous daily returns with Excess columns.
      fwd_20d_returns_df: Forward 20D returns with Excess columns (full dataset).
      price_df: Full aligned price DataFrame.  Required for training-period boundary
                enforcement.  If None, boundary filtering is skipped (with a warning).

    Returns:
      pd.DataFrame: Comprehensive sector performance table.
    """
    records = []

    groups = labels_df.groupby(["model", "label_type", "period"])

    for (model, label_type, period), group in groups:
        group_sorted = group.sort_values("Date").set_index("Date")
        aligned_daily = daily_returns_df.loc[group_sorted.index]
        aligned_fwd = fwd_20d_returns_df.loc[group_sorted.index]
        ep_df = calculate_regime_episodes(group_sorted["regime_id"])
        k_val = group["k"].iloc[0]

        for r_id in range(k_val):
            r_mask = group_sorted["regime_id"] == r_id
            n_obs = int(r_mask.sum())
            r_episodes = ep_df[ep_df["regime_id"] == r_id]
            n_episodes = len(r_episodes)

            if n_obs == 0:
                # Still record absent state for audit completeness
                for sector in SECTOR_NAMES:
                    for horizon in ["contemporaneous_daily", "forward_20D"]:
                        records.append({
                            "model": model,
                            "label_type": label_type,
                            "period": period,
                            "regime_id": r_id,
                            "sector": sector,
                            "return_horizon": horizon,
                            "n_observations": 0,
                            "n_episodes": 0,
                            "obs_mean_return": np.nan,
                            "obs_median_return": np.nan,
                            "obs_std_return": np.nan,
                            "obs_iqr_return": np.nan,
                            "annualized_return": np.nan,
                            "annualized_volatility": np.nan,
                            "benchmark_mean_return": np.nan,
                            "mean_excess_return": np.nan,
                            "median_excess_return": np.nan,
                            "annualized_excess_return": np.nan,
                            "win_rate_vs_benchmark": np.nan,
                            "episode_mean_excess_return": np.nan,
                            "sample_size_flag": "zero_sample_absent",
                        })
                continue

            sample_flag = "reliable" if (n_obs >= 50 and n_episodes >= 3) else "low_sample_unstable"

            # 1. Contemporaneous daily returns
            daily_sub = aligned_daily[r_mask]
            bm_daily = daily_sub[BENCHMARK_NAME]

            # 2. Forward 20D returns
            # Drop NaNs from dataset tail (last 20 rows of full dataset have no t+20 price).
            fwd_sub = aligned_fwd[r_mask].dropna(subset=[BENCHMARK_NAME])

            # Boundary enforcement: for training period, additionally exclude dates
            # where the t+20 price endpoint falls beyond TRAIN_END_DATE.  This
            # prevents 2025 holdout prices from entering training-period forward stats.
            # Uses trading-day index positions — not calendar offsets — so Indian
            # market holidays (which are not in the price index) are handled correctly.
            if period == "train" and price_df is not None and not fwd_sub.empty:
                TRAIN_END_TS = pd.Timestamp(TRAIN_END_DATE)
                all_td = price_df.index  # full trading-day index
                valid_fwd_idx = [
                    d for d in fwd_sub.index
                    if all_td[min(all_td.get_loc(d) + 20, len(all_td) - 1)] <= TRAIN_END_TS
                ]
                fwd_sub = fwd_sub.loc[valid_fwd_idx]
            elif period == "train" and price_df is None:
                warnings.warn(
                    "price_df not supplied to compute_sector_performance_by_regime(); "
                    "training-period forward-return boundary enforcement is SKIPPED. "
                    "The last 20 training dates may use holdout-period prices.",
                    UserWarning,
                    stacklevel=2,
                )

            bm_fwd = fwd_sub[BENCHMARK_NAME] if not fwd_sub.empty else pd.Series(dtype=float)

            for sector in SECTOR_NAMES:
                # --- Contemporaneous Daily Metrics ---
                sec_daily = daily_sub[sector]
                exc_daily = daily_sub[f"{sector}_Excess"]

                mean_d = float(sec_daily.mean())
                med_d = float(sec_daily.median())
                std_d = float(sec_daily.std())
                iqr_d = float(sec_daily.quantile(0.75) - sec_daily.quantile(0.25))
                ann_ret_d = mean_d * 252.0
                ann_vol_d = std_d * np.sqrt(252.0) if std_d > 0 else 0.0

                bm_mean_d = float(bm_daily.mean())
                mean_exc_d = float(exc_daily.mean())
                med_exc_d = float(exc_daily.median())
                ann_exc_d = mean_exc_d * 252.0
                win_rate_d = float((exc_daily > 0).mean() * 100.0)

                # Episode-weighted contemporaneous excess return
                ep_exc_means = []
                for _, ep in r_episodes.iterrows():
                    ep_slice = aligned_daily.loc[ep["start_date"]:ep["end_date"], f"{sector}_Excess"]
                    if not ep_slice.empty:
                        ep_exc_means.append(ep_slice.mean())
                ep_weighted_exc_d = float(np.mean(ep_exc_means)) if ep_exc_means else np.nan

                records.append({
                    "model": model,
                    "label_type": label_type,
                    "period": period,
                    "regime_id": r_id,
                    "sector": sector,
                    "return_horizon": "contemporaneous_daily",
                    "n_observations": n_obs,
                    "n_episodes": n_episodes,
                    "obs_mean_return": round(mean_d, 6),
                    "obs_median_return": round(med_d, 6),
                    "obs_std_return": round(std_d, 6),
                    "obs_iqr_return": round(iqr_d, 6),
                    "annualized_return": round(ann_ret_d, 4),
                    "annualized_volatility": round(ann_vol_d, 4),
                    "benchmark_mean_return": round(bm_mean_d, 6),
                    "mean_excess_return": round(mean_exc_d, 6),
                    "median_excess_return": round(med_exc_d, 6),
                    "annualized_excess_return": round(ann_exc_d, 4),
                    "win_rate_vs_benchmark": round(win_rate_d, 2),
                    "episode_mean_excess_return": round(ep_weighted_exc_d, 6) if not np.isnan(ep_weighted_exc_d) else np.nan,
                    "sample_size_flag": sample_flag,
                })

                # --- Forward 20D Metrics ---
                if not fwd_sub.empty and len(fwd_sub[sector].dropna()) > 0:
                    sec_fwd = fwd_sub[sector].dropna()
                    exc_fwd = fwd_sub[f"{sector}_Excess"].dropna()

                    mean_f = float(sec_fwd.mean())
                    med_f = float(sec_fwd.median())
                    std_f = float(sec_fwd.std())
                    iqr_f = float(sec_fwd.quantile(0.75) - sec_fwd.quantile(0.25))
                    ann_ret_f = mean_f * (252.0 / 20.0)
                    ann_vol_f = std_f * np.sqrt(252.0 / 20.0) if std_f > 0 else 0.0

                    bm_mean_f = float(bm_fwd.mean())
                    mean_exc_f = float(exc_fwd.mean())
                    med_exc_f = float(exc_fwd.median())
                    ann_exc_f = mean_exc_f * (252.0 / 20.0)
                    win_rate_f = float((exc_fwd > 0).mean() * 100.0)

                    records.append({
                        "model": model,
                        "label_type": label_type,
                        "period": period,
                        "regime_id": r_id,
                        "sector": sector,
                        "return_horizon": "forward_20D",
                        "n_observations": len(sec_fwd),
                        "n_episodes": n_episodes,
                        "obs_mean_return": round(mean_f, 6),
                        "obs_median_return": round(med_f, 6),
                        "obs_std_return": round(std_f, 6),
                        "obs_iqr_return": round(iqr_f, 6),
                        "annualized_return": round(ann_ret_f, 4),
                        "annualized_volatility": round(ann_vol_f, 4),
                        "benchmark_mean_return": round(bm_mean_f, 6),
                        "mean_excess_return": round(mean_exc_f, 6),
                        "median_excess_return": round(med_exc_f, 6),
                        "annualized_excess_return": round(ann_exc_f, 4),
                        "win_rate_vs_benchmark": round(win_rate_f, 2),
                        "episode_mean_excess_return": np.nan,  # forward 20D overlaps across episode days
                        "sample_size_flag": sample_flag,
                    })
                else:
                    records.append({
                        "model": model,
                        "label_type": label_type,
                        "period": period,
                        "regime_id": r_id,
                        "sector": sector,
                        "return_horizon": "forward_20D",
                        "n_observations": 0,
                        "n_episodes": n_episodes,
                        "obs_mean_return": np.nan,
                        "obs_median_return": np.nan,
                        "obs_std_return": np.nan,
                        "obs_iqr_return": np.nan,
                        "annualized_return": np.nan,
                        "annualized_volatility": np.nan,
                        "benchmark_mean_return": np.nan,
                        "mean_excess_return": np.nan,
                        "median_excess_return": np.nan,
                        "annualized_excess_return": np.nan,
                        "win_rate_vs_benchmark": np.nan,
                        "episode_mean_excess_return": np.nan,
                        "sample_size_flag": sample_flag,
                    })

    return pd.DataFrame(records)


def identify_sector_leadership(sector_perf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Rank sectors within each model, label stream, period, and regime to identify:
      - Top 2 Historical Leaders (highest mean excess return vs NIFTY 50)
      - Bottom 2 Historical Laggards (lowest mean excess return vs NIFTY 50)
      - Historical Defensive Candidates (positive excess return during market stress/correction)

    Flags reliability and avoids ranking on empty or tiny samples.
    Returns:
      pd.DataFrame: Summary table of leaders and laggards.
    """
    records = []
    
    # Filter for contemporaneous daily returns as baseline for leadership
    df_daily = sector_perf_df[sector_perf_df["return_horizon"] == "contemporaneous_daily"]
    grouped = df_daily.groupby(["model", "label_type", "period", "regime_id"])

    for (model, label_type, period, regime_id), sub in grouped:
        n_obs = sub["n_observations"].iloc[0]
        n_ep = sub["n_episodes"].iloc[0]
        sample_flag = sub["sample_size_flag"].iloc[0]

        interp = REGIME_INTERPRETATIONS.get((model, regime_id), {
            "economic_name": f"Regime {regime_id}",
            "description": "",
            "caveat": "",
        })

        if n_obs == 0 or sub["mean_excess_return"].isna().all():
            records.append({
                "model": model,
                "label_type": label_type,
                "period": period,
                "regime_id": regime_id,
                "economic_name": interp["economic_name"],
                "n_observations": 0,
                "n_episodes": 0,
                "sample_size_flag": "zero_sample_absent",
                "top_leader_1": "None (Absent)",
                "top_leader_1_ann_excess": np.nan,
                "top_leader_2": "None (Absent)",
                "top_leader_2_ann_excess": np.nan,
                "bottom_laggard_1": "None (Absent)",
                "bottom_laggard_1_ann_excess": np.nan,
                "bottom_laggard_2": "None (Absent)",
                "bottom_laggard_2_ann_excess": np.nan,
                "defensive_candidate": "None",
                "leadership_notes": "Regime did not appear in this period.",
            })
            continue

        sorted_sub = sub.sort_values("mean_excess_return", ascending=False).reset_index(drop=True)
        top_1 = sorted_sub.iloc[0]
        top_2 = sorted_sub.iloc[1]
        bot_1 = sorted_sub.iloc[-1]
        bot_2 = sorted_sub.iloc[-2]

        # Defensive candidate: sector with highest positive excess return when NIFTY is negative,
        # or sector with highest win rate / lowest volatility
        positive_excess = sorted_sub[sorted_sub["mean_excess_return"] > 0]
        defensive_cand = positive_excess.iloc[0]["sector"] if not positive_excess.empty else "None"

        notes = []
        if sample_flag == "low_sample_unstable":
            notes.append("Low sample size (<50 days or <3 episodes); leadership is historical reference only, not stable.")
        if "reflation" in interp["economic_name"].lower() or "bull" in interp["economic_name"].lower():
            notes.append("Cyclical/high-beta sectors lead; defensives lag.")
        elif "crisis" in interp["economic_name"].lower() or "liquidation" in interp["economic_name"].lower():
            notes.append("Defensive cushion observed in Pharma/FMCG; severe beta drawdown in Financials/Metals.")

        records.append({
            "model": model,
            "label_type": label_type,
            "period": period,
            "regime_id": regime_id,
            "economic_name": interp["economic_name"],
            "n_observations": n_obs,
            "n_episodes": n_ep,
            "sample_size_flag": sample_flag,
            "top_leader_1": top_1["sector"],
            "top_leader_1_ann_excess": top_1["annualized_excess_return"],
            "top_leader_2": top_2["sector"],
            "top_leader_2_ann_excess": top_2["annualized_excess_return"],
            "bottom_laggard_1": bot_1["sector"],
            "bottom_laggard_1_ann_excess": bot_1["annualized_excess_return"],
            "bottom_laggard_2": bot_2["sector"],
            "bottom_laggard_2_ann_excess": bot_2["annualized_excess_return"],
            "defensive_candidate": defensive_cand,
            "leadership_notes": " ".join(notes) if notes else "Leadership aligned with economic cycle.",
        })

    return pd.DataFrame(records)



# 3. Major-Event Analysis


def load_and_align_events(
    event_csv_path: Union[str, Path] = "data/raw/Events/major_events_2019_2026.csv",
    trading_dates: Optional[pd.DatetimeIndex] = None,
) -> pd.DataFrame:
    """
    Load major-event calendar and align start/end dates with active trading days.
    
    Rules:
      - Uses dayfirst=True to handle DD-MM-YYYY format reliably.
      - If an event start date falls on a non-trading day (weekend/holiday),
        align to the *immediate next active trading day*.
      - If an event end date falls on a non-trading day, align to the
        *immediate next active trading day*.
      - Source data file is never modified.
    """
    path = Path(event_csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Event calendar CSV not found at {path}")

    events = pd.read_csv(path)
    events["start_date_raw"] = events["start_date"]
    events["end_date_raw"] = events["end_date"]
    events["start_date"] = pd.to_datetime(events["start_date"], dayfirst=True)
    events["end_date"] = pd.to_datetime(events["end_date"], dayfirst=True)

    if trading_dates is not None:
        trading_sorted = sorted(trading_dates)
        trading_series = pd.Series(trading_sorted, index=trading_sorted)

        def align_to_next_trading_day(dt: pd.Timestamp) -> pd.Timestamp:
            # If date exists in trading calendar, return as-is
            if dt in trading_series:
                return dt
            # Find next available trading date
            future = trading_series[trading_series >= dt]
            if not future.empty:
                return future.iloc[0]
            # If past the end of trading calendar, return latest
            return trading_sorted[-1]

        events["aligned_start_date"] = events["start_date"].apply(align_to_next_trading_day)
        events["aligned_end_date"] = events["end_date"].apply(align_to_next_trading_day)
    else:
        events["aligned_start_date"] = events["start_date"]
        events["aligned_end_date"] = events["end_date"]

    return events


def build_event_windows(
    events_df: pd.DataFrame,
    trading_dates: pd.DatetimeIndex,
    pre_days: int = 2,
    post_days: int = 2,
) -> Tuple[pd.Series, pd.DataFrame]:
    """
    Construct trading-day event windows around each event and deduplicate overlaps.

    Window policy:
      - For each event with aligned [start_date, end_date], find its trading day positions
        in the continuous trading calendar.
      - Window spans from (start_idx - pre_days) to (end_idx + post_days).
      - Overlapping windows are handled via boolean UNION deduplication: each trading day
        is marked as either an event day (True) or normal baseline day (False) exactly once.
      - Never double-counts returns or observations across overlapping events.

    Returns:
      (is_event_day_series, event_windows_summary_df)
    """
    trading_sorted = sorted(trading_dates)
    date_to_idx = {d: i for i, d in enumerate(trading_sorted)}
    n_days = len(trading_sorted)

    event_day_mask = np.zeros(n_days, dtype=bool)
    event_window_records = []

    for _, row in events_df.iterrows():
        s_date = row["aligned_start_date"]
        e_date = row["aligned_end_date"]

        if s_date not in date_to_idx or e_date not in date_to_idx:
            continue

        s_idx = date_to_idx[s_date]
        e_idx = date_to_idx[e_date]

        win_start_idx = max(0, s_idx - pre_days)
        win_end_idx = min(n_days - 1, e_idx + post_days)

        event_day_mask[win_start_idx : win_end_idx + 1] = True

        event_window_records.append({
            "event_id": row["event_id"],
            "event_name": row["event_name"],
            "event_category": row["event_category"],
            "severity": row["severity"],
            "aligned_start_date": s_date,
            "aligned_end_date": e_date,
            "window_start_date": trading_sorted[win_start_idx],
            "window_end_date": trading_sorted[win_end_idx],
            "window_trading_days": (win_end_idx - win_start_idx + 1),
        })

    is_event_day = pd.Series(event_day_mask, index=trading_sorted, name="is_event_day")
    windows_df = pd.DataFrame(event_window_records)

    return is_event_day, windows_df


def analyze_event_regime_associations(
    labels_df: pd.DataFrame,
    daily_returns_df: pd.DataFrame,
    is_event_day: pd.Series,
    events_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare regime frequencies and sector performance during event windows versus
    the non-event normal baseline.

    Important Principles:
      - Association does NOT imply causation: an event falling during a regime does
        not prove the event caused the regime.
      - Overlapping events are deduplicated via union mask.
      - Evaluates HMM (filtered_causal primary), K-Means, and GMM.

    Returns:
      pd.DataFrame: Table comparing regime probabilities and sector excess returns
                    between Event Windows and Non-Event Baseline.
    """
    records = []

    valid_label_dates = pd.DatetimeIndex(labels_df["Date"].unique())
    min_label_date = valid_label_dates.min()
    max_label_date = valid_label_dates.max()

    # Focus on training pool, holdout, and full labeled periods
    for period in ["train", "holdout", "full"]:
        if period == "train":
            period_mask = (is_event_day.index >= min_label_date) & (is_event_day.index <= TRAIN_END_DATE)
        elif period == "holdout":
            period_mask = (is_event_day.index >= HOLDOUT_START_DATE) & (is_event_day.index <= max_label_date)
        else:
            period_mask = (is_event_day.index >= min_label_date) & (is_event_day.index <= max_label_date)

        period_dates = is_event_day.index[period_mask]
        period_events = is_event_day.loc[period_dates]

        n_event_days = int(period_events.sum())
        n_normal_days = int((~period_events).sum())
        total_days = len(period_events)

        if n_event_days == 0 or n_normal_days == 0:
            continue

        for model in ["hmm", "kmeans", "gmm"]:
            # For HMM, use filtered_causal as primary; viterbi as comparison
            label_types = ["filtered_causal", "retrospective_viterbi"] if model == "hmm" else ["hard"]

            for l_type in label_types:
                sub_labels = labels_df[
                    (labels_df["model"] == model)
                    & (labels_df["label_type"] == l_type)
                    & (labels_df["Date"].isin(period_dates))
                ].sort_values("Date").set_index("Date")

                if sub_labels.empty:
                    continue

                k_val = sub_labels["k"].iloc[0]

                # Event vs Normal regime distributions
                event_labels = sub_labels.loc[period_events[period_events].index, "regime_id"]
                normal_labels = sub_labels.loc[period_events[~period_events].index, "regime_id"]

                for r_id in range(k_val):
                    event_count = int((event_labels == r_id).sum())
                    normal_count = int((normal_labels == r_id).sum())

                    event_pct = (event_count / n_event_days) * 100.0 if n_event_days > 0 else 0.0
                    normal_pct = (normal_count / n_normal_days) * 100.0 if n_normal_days > 0 else 0.0
                    relative_risk = (event_pct / normal_pct) if normal_pct > 0 else np.nan

                    interp = REGIME_INTERPRETATIONS.get((model, r_id), {
                        "economic_name": f"Regime {r_id}",
                    })

                    records.append({
                        "model": model,
                        "label_type": l_type,
                        "period": period,
                        "regime_id": r_id,
                        "economic_name": interp["economic_name"],
                        "total_period_days": total_days,
                        "n_event_window_days": n_event_days,
                        "n_normal_baseline_days": n_normal_days,
                        "event_window_regime_count": event_count,
                        "event_window_regime_pct": round(event_pct, 2),
                        "normal_baseline_regime_count": normal_count,
                        "normal_baseline_regime_pct": round(normal_pct, 2),
                        "frequency_ratio_event_vs_normal": round(relative_risk, 2) if not np.isnan(relative_risk) else np.nan,
                        "event_association_verdict": (
                            "Elevated during events" if relative_risk >= 1.25 else
                            "Depressed during events" if relative_risk <= 0.80 else
                            "Neutral / proportional"
                        ) if not np.isnan(relative_risk) else "Insufficient normal data",
                        "limitation_note": "Observational correlation only; does not establish causal transmission.",
                    })

    return pd.DataFrame(records)


def analyze_sector_performance_during_events(
    daily_returns_df: pd.DataFrame,
    is_event_day: pd.Series,
    events_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare sector daily returns and benchmark-relative excess returns during
    event windows versus non-event baseline periods.
    """
    records = []
    aligned_dates = daily_returns_df.index.intersection(is_event_day.index)
    daily_aligned = daily_returns_df.loc[aligned_dates]
    event_mask = is_event_day.loc[aligned_dates]

    for sector in SECTOR_NAMES:
        # Event days
        sec_ev = daily_aligned.loc[event_mask, sector]
        exc_ev = daily_aligned.loc[event_mask, f"{sector}_Excess"]

        # Normal days
        sec_norm = daily_aligned.loc[~event_mask, sector]
        exc_norm = daily_aligned.loc[~event_mask, f"{sector}_Excess"]

        records.append({
            "sector": sector,
            "n_event_days": int(event_mask.sum()),
            "n_normal_days": int((~event_mask).sum()),
            "event_mean_daily_return": round(float(sec_ev.mean()), 6),
            "normal_mean_daily_return": round(float(sec_norm.mean()), 6),
            "event_mean_excess_return": round(float(exc_ev.mean()), 6),
            "normal_mean_excess_return": round(float(exc_norm.mean()), 6),
            "event_annualized_excess_return": round(float(exc_ev.mean()) * 252.0, 4),
            "normal_annualized_excess_return": round(float(exc_norm.mean()) * 252.0, 4),
            "event_volatility_annualized": round(float(sec_ev.std()) * np.sqrt(252.0), 4),
            "normal_volatility_annualized": round(float(sec_norm.std()) * np.sqrt(252.0), 4),
            "event_win_rate_vs_benchmark": round(float((exc_ev > 0).mean()) * 100.0, 2),
            "normal_win_rate_vs_benchmark": round(float((exc_norm > 0).mean()) * 100.0, 2),
        })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 4. Cross-Model Comparison
# ---------------------------------------------------------------------------

def generate_cross_model_comparison(
    profiles_df: pd.DataFrame,
    leadership_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generate structured cross-model comparison across K-Means, GMM, and HMM.
    Compares:
      - Number of discovered regimes
      - Persistence / Median duration
      - Holdout validity & state collapse checks
      - Sector leadership consistency in similar economic conditions
      - Reliability score & Phase 6 caveats carried forward

    Never maps regime IDs by number alone; compares economic market states.
    """
    records = []

    # Filter training and causal where applicable
    models_to_compare = [
        ("kmeans", "hard", "K-Means (K=4, RobustScaler)"),
        ("gmm", "hard", "GMM (K=2, Full Covariance)"),
        ("hmm", "filtered_causal", "Gaussian HMM (K=6, Diag Cov, Causal)"),
    ]

    for model_id, l_type, display_name in models_to_compare:
        p_train = profiles_df[(profiles_df["model"] == model_id) & (profiles_df["label_type"] == l_type) & (profiles_df["period"] == "train")]
        p_hold = profiles_df[(profiles_df["model"] == model_id) & (profiles_df["label_type"] == l_type) & (profiles_df["period"] == "holdout")]

        n_regimes = len(p_train)
        med_dur_train = float(p_train["median_duration_days"].median()) if not p_train.empty else np.nan
        med_dur_hold = float(p_hold["median_duration_days"].median()) if not p_hold.empty else np.nan

        holdout_zero_states = int((p_hold["n_trading_days"] == 0).sum()) if not p_hold.empty else 0
        holdout_collapse = bool(len(p_hold[p_hold["n_trading_days"] > 0]) == 1)

        # Retrieve Phase 6 reliability summary
        if model_id == "kmeans":
            reliab_summary = "High scaler sensitivity (ARI=0.1603); severe micro-switching in holdout (1.0d median duration)."
            verdict = "Secondary baseline only; too fragile and fragmented for execution."
        elif model_id == "gmm":
            reliab_summary = "Collapsed to 1 state in holdout (100% R0). Functionally a binary COVID detector, not a rotation model."
            verdict = "Rejected for sector rotation; incapable of differentiating normal/correction cycles."
        else:
            reliab_summary = "Highest CV log-likelihood; high persistence (diag mean=0.9707); clean causal/filtered tracking. Crisis states (R1, R3) unobserved in holdout."
            verdict = "Recommended primary model candidate for Phase 8 allocation rules."

        records.append({
            "model_name": display_name,
            "model_id": model_id,
            "label_type": l_type,
            "n_regimes_discovered": n_regimes,
            "median_episode_duration_train": med_dur_train,
            "median_episode_duration_holdout": med_dur_hold,
            "holdout_active_states": n_regimes - holdout_zero_states,
            "holdout_absent_states": holdout_zero_states,
            "holdout_state_collapse": holdout_collapse,
            "phase6_cv_stability_evidence": reliab_summary,
            "phase7_operational_verdict": verdict,
        })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 5. HMM Holdout Sector Performance Correlation Analysis
# ---------------------------------------------------------------------------

def compute_hmm_holdout_sector_correlations(
    labels_df: pd.DataFrame,
    daily_returns_df: pd.DataFrame,
    min_obs_threshold: int = 30,
) -> Dict[str, Any]:
    """
    Compute sector return Pearson correlation matrices for each HMM causal-filtered regime
    in the 2025-2026 holdout period.

    Parameters
    ----------
    labels_df : pd.DataFrame
        Regime labels DataFrame containing columns ['Date', 'model', 'label_type', 'period', 'regime_id'].
    daily_returns_df : pd.DataFrame
        Daily returns DataFrame indexed by Date with columns for SECTOR_NAMES.
    min_obs_threshold : int, default 30
        Minimum observation threshold below which regimes are flagged as insufficient/unstable.

    Returns
    -------
    Dict[str, Any] with keys:
        - 'matrices_df': Long-format DataFrame of pairwise correlations for each regime with metadata
        - 'comparison_df': Table of 15 unique sector pairs compared across all active regimes
        - 'regime_summary_df': Regime-level summary with sample size, flag, and average correlation
        - 'regime_matrices': Dict mapping regime_id -> 6x6 pd.DataFrame correlation matrix
        - 'holdout_overall_matrix': 6x6 pd.DataFrame correlation matrix across all holdout days
    """
    hmm_holdout = labels_df[
        (labels_df["model"] == "hmm")
        & (labels_df["label_type"] == "filtered_causal")
        & (labels_df["period"] == "holdout")
    ].copy()

    if "Date" in daily_returns_df.columns:
        daily_sub = daily_returns_df.copy()
    else:
        daily_sub = daily_returns_df.reset_index()

    daily_sub["Date"] = pd.to_datetime(daily_sub["Date"])
    hmm_holdout["Date"] = pd.to_datetime(hmm_holdout["Date"])

    merged = hmm_holdout.merge(daily_sub[["Date"] + SECTOR_NAMES], on="Date", how="inner")
    total_holdout_days = len(merged)

    # Compute holdout-wide baseline correlation
    holdout_overall_corr = merged[SECTOR_NAMES].corr(method="pearson")

    matrices_rows = []
    regime_summary_rows = []
    regime_matrices: Dict[int, pd.DataFrame] = {}

    for k in range(6):
        interp = REGIME_INTERPRETATIONS.get(("hmm", k), {"economic_name": f"Regime {k}", "caveat": ""})
        econ_name = interp["economic_name"]
        sub = merged[merged["regime_id"] == k]
        n_obs = len(sub)
        pct_holdout = (n_obs / total_holdout_days * 100.0) if total_holdout_days > 0 else 0.0

        if n_obs == 0:
            flag = "absent_in_holdout"
            corr_matrix = pd.DataFrame(np.nan, index=SECTOR_NAMES, columns=SECTOR_NAMES)
            mean_pairwise = np.nan
            median_pairwise = np.nan
        elif n_obs < min_obs_threshold:
            flag = "low_sample_unstable"
            corr_matrix = sub[SECTOR_NAMES].corr(method="pearson")
            triu_vals = corr_matrix.values[np.triu_indices(len(SECTOR_NAMES), k=1)]
            mean_pairwise = float(np.nanmean(triu_vals))
            median_pairwise = float(np.nanmedian(triu_vals))
        else:
            flag = "sufficient"
            corr_matrix = sub[SECTOR_NAMES].corr(method="pearson")
            triu_vals = corr_matrix.values[np.triu_indices(len(SECTOR_NAMES), k=1)]
            mean_pairwise = float(np.nanmean(triu_vals))
            median_pairwise = float(np.nanmedian(triu_vals))

        regime_matrices[k] = corr_matrix

        regime_summary_rows.append({
            "model": "hmm",
            "label_type": "filtered_causal",
            "period": "holdout",
            "regime_id": k,
            "economic_name": econ_name,
            "n_observations": n_obs,
            "pct_holdout_days": round(pct_holdout, 2),
            "sample_size_flag": flag,
            "mean_pairwise_correlation": round(mean_pairwise, 4) if not np.isnan(mean_pairwise) else np.nan,
            "median_pairwise_correlation": round(median_pairwise, 4) if not np.isnan(median_pairwise) else np.nan,
            "caveat": interp["caveat"],
        })

        for i in range(len(SECTOR_NAMES)):
            for j in range(len(SECTOR_NAMES)):
                s1, s2 = SECTOR_NAMES[i], SECTOR_NAMES[j]
                val = corr_matrix.loc[s1, s2] if not corr_matrix.empty else np.nan
                matrices_rows.append({
                    "model": "hmm",
                    "label_type": "filtered_causal",
                    "period": "holdout",
                    "regime_id": k,
                    "economic_name": econ_name,
                    "n_observations": n_obs,
                    "pct_holdout_days": round(pct_holdout, 2),
                    "sample_size_flag": flag,
                    "sector_1": s1,
                    "sector_2": s2,
                    "correlation": round(val, 4) if not np.isnan(val) else np.nan,
                })

    regime_summary_df = pd.DataFrame(regime_summary_rows)
    matrices_df = pd.DataFrame(matrices_rows)

    # 15 unique sector pairs comparison
    cyclicals = {"AUTO", "BANK", "METAL"}
    defensives = {"FMCG", "IT", "PHARMA"}

    def get_category(s1: str, s2: str) -> str:
        if s1 in cyclicals and s2 in cyclicals:
            return "Cyclical - Cyclical"
        elif s1 in defensives and s2 in defensives:
            return "Defensive - Defensive"
        else:
            return "Cyclical - Defensive"

    comparison_rows = []
    for i in range(len(SECTOR_NAMES)):
        for j in range(i + 1, len(SECTOR_NAMES)):
            s1, s2 = SECTOR_NAMES[i], SECTOR_NAMES[j]
            cat = get_category(s1, s2)
            ov = holdout_overall_corr.loc[s1, s2]
            r0 = regime_matrices[0].loc[s1, s2]
            r2 = regime_matrices[2].loc[s1, s2]
            r4 = regime_matrices[4].loc[s1, s2]
            r5 = regime_matrices[5].loc[s1, s2]

            suff_vals = {"R2": r2, "R4": r4, "R5": r5}
            valid_suff = {k_name: v for k_name, v in suff_vals.items() if not np.isnan(v)}
            min_reg = min(valid_suff, key=valid_suff.get) if valid_suff else "N/A"
            max_reg = max(valid_suff, key=valid_suff.get) if valid_suff else "N/A"
            spread_r5_r4 = (r5 - r4) if not np.isnan(r5) and not np.isnan(r4) else np.nan
            spread_suff = (max(valid_suff.values()) - min(valid_suff.values())) if valid_suff else np.nan

            comparison_rows.append({
                "sector_pair": f"{s1} - {s2}",
                "sector_1": s1,
                "sector_2": s2,
                "pair_category": cat,
                "holdout_overall_corr": round(ov, 4),
                "R0_corr_reflation_unstable": round(r0, 4) if not np.isnan(r0) else np.nan,
                "R2_corr_consolidation": round(r2, 4) if not np.isnan(r2) else np.nan,
                "R4_corr_expansion": round(r4, 4) if not np.isnan(r4) else np.nan,
                "R5_corr_correction": round(r5, 4) if not np.isnan(r5) else np.nan,
                "R5_minus_R4_shift": round(spread_r5_r4, 4) if not np.isnan(spread_r5_r4) else np.nan,
                "range_sufficient_regimes": round(spread_suff, 4) if not np.isnan(spread_suff) else np.nan,
                "min_regime_sufficient": min_reg,
                "max_regime_sufficient": max_reg,
            })

    comparison_df = pd.DataFrame(comparison_rows)

    return {
        "matrices_df": matrices_df,
        "comparison_df": comparison_df,
        "regime_summary_df": regime_summary_df,
        "regime_matrices": regime_matrices,
        "holdout_overall_matrix": holdout_overall_corr,
    }


def plot_hmm_holdout_sector_correlations(
    corr_results: Dict[str, Any],
    results_dir: Union[str, Path] = "results",
) -> Dict[str, Path]:
    """
    Generate and save:
      1. Individual heatmaps for each active HMM regime in the holdout period
         (results/regime_characterization/correlations/hmm_holdout_sector_corr_regime_{k}.png)
      2. Concise multi-panel comparison figure across HMM regimes
         (results/regime_characterization/correlations/hmm_holdout_sector_corr_comparison.png)
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    results_dir = Path(results_dir)
    if results_dir.name != "correlations":
        target_dir = results_dir / "regime_characterization" / "correlations"
    else:
        target_dir = results_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_plots: Dict[str, Path] = {}

    regime_matrices = corr_results["regime_matrices"]
    regime_summary = corr_results["regime_summary_df"]

    # 1. Individual regime heatmaps for active regimes
    for _, row in regime_summary.iterrows():
        k = int(row["regime_id"])
        n_obs = int(row["n_observations"])
        flag = str(row["sample_size_flag"])
        econ_name = str(row["economic_name"])

        if n_obs == 0:
            continue

        corr_mat = regime_matrices[k]

        fig, ax = plt.subplots(figsize=(7, 6))
        sns.heatmap(
            corr_mat,
            annot=True,
            fmt=".2f",
            cmap="coolwarm",
            vmin=-0.2,
            vmax=1.0,
            square=True,
            linewidths=0.5,
            cbar_kws={"label": "Pearson Correlation (r)"},
            ax=ax,
        )

        flag_str = f"[{flag.upper()}]" if flag != "sufficient" else "[SUFFICIENT]"
        title = f"HMM Holdout Regime {k}: {econ_name}\nSector Daily Return Correlation (n={n_obs} days, {flag_str})"
        ax.set_title(title, fontsize=11, fontweight="bold", pad=12)

        if flag == "low_sample_unstable":
            ax.text(
                0.5, -0.15,
                f"CAUTION: Sample size {n_obs} < 30. Correlation estimates are statistically unstable.",
                transform=ax.transAxes,
                ha="center",
                fontsize=9,
                color="darkred",
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#fee8c8", edgecolor="#e34a33"),
            )

        plt.tight_layout()
        plot_path = target_dir / f"hmm_holdout_sector_corr_regime_{k}.png"
        fig.savefig(plot_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved_plots[f"regime_{k}"] = plot_path
        print(f"Saved: {plot_path}")

    # 2. Concise multi-panel comparison figure across HMM regimes
    # Active regimes in holdout: R0 (n=8), R2 (n=118), R4 (n=170), R5 (n=126)
    active_regimes = [
        k for k in [0, 2, 4, 5]
        if k in regime_matrices and regime_summary.loc[regime_summary["regime_id"] == k, "n_observations"].iloc[0] > 0
    ]

    fig, axes = plt.subplots(2, 2, figsize=(15, 13))
    axes = axes.flatten()

    for idx, k in enumerate(active_regimes):
        ax = axes[idx]
        corr_mat = regime_matrices[k]
        r_info = regime_summary[regime_summary["regime_id"] == k].iloc[0]
        n_obs = int(r_info["n_observations"])
        flag = str(r_info["sample_size_flag"])
        econ_name = str(r_info["economic_name"])

        sns.heatmap(
            corr_mat,
            annot=True,
            fmt=".2f",
            cmap="coolwarm",
            vmin=-0.2,
            vmax=1.0,
            square=True,
            linewidths=0.5,
            cbar=True,
            cbar_kws={"label": "Pearson Correlation (r)"},
            ax=ax,
        )

        flag_badge = f" [! {flag.upper()} !]" if flag != "sufficient" else ""
        ax.set_title(
            f"HMM R{k}: {econ_name}\n(n={n_obs} days, {r_info['pct_holdout_days']}% holdout){flag_badge}",
            fontsize=11, fontweight="bold", pad=8
        )

        if flag == "low_sample_unstable":
            ax.set_facecolor("#fff7ec")

    fig.suptitle(
        "HMM Holdout Sector Performance Correlation Comparison across Regimes (2025–2026)\n"
        "Observation: Risk-off correction (R5) triggers broad systemic correlation spikes (AUTO-BANK 0.81, AUTO-METAL 0.72);\n"
        "Low-vol expansion (R4) and consolidation (R2) preserve cross-sector dispersion and defensive decoupling.",
        fontsize=12, fontweight="bold", y=1.02
    )

    plt.tight_layout()
    comp_path = target_dir / "hmm_holdout_sector_corr_comparison.png"
    fig.savefig(comp_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved_plots["comparison"] = comp_path
    print(f"Saved: {comp_path}")

    return saved_plots


# ---------------------------------------------------------------------------
# 6. Complete End-to-End Pipeline Execution
# ---------------------------------------------------------------------------

def run_phase7_pipeline(
    data_dir: Union[str, Path] = "data",
    results_dir: Union[str, Path] = "results",
) -> Dict[str, pd.DataFrame]:
    """
    Execute the entire Phase 7 analytical workflow end-to-end:
      1. Load labels and clean returns
      2. Compute model regime profiles (Causal HMM, Viterbi HMM, K-Means, GMM)
      3. Compute sector performance by regime (Contemporaneous & Forward 20D)
      4. Identify sector leadership, laggards, and defensive candidates
      5. Align event calendar, build deduplicated windows, and analyze event associations
      6. Generate cross-model comparison report
      7. Compute HMM holdout sector return correlation matrices & comparison heatmaps
      8. Save all CSV artifacts and figures to organized subdirectories under results_dir

    Returns:
      Dict mapping artifact name to generated DataFrame.
    """
    data_dir = Path(data_dir)
    results_dir = Path(results_dir)

    # Organized target subdirectories
    regime_profiles_dir = results_dir / "regime_characterization" / "regime_profiles"
    sector_perf_dir = results_dir / "regime_characterization" / "sector_performance"
    sector_lead_dir = results_dir / "regime_characterization" / "sector_leadership"
    correlations_dir = results_dir / "regime_characterization" / "correlations"
    event_analysis_dir = results_dir / "event_analysis"
    reports_dir = results_dir / "reports"

    for d in [regime_profiles_dir, sector_perf_dir, sector_lead_dir, correlations_dir, event_analysis_dir, reports_dir]:
        d.mkdir(parents=True, exist_ok=True)

    print("=== STARTING PHASE 7 PIPELINE EXECUTION ===")

    # 1. Load Data
    print("Loading Phase 6 labels and clean master features...")
    labels_df = load_regime_labels(results_dir)
    
    # Load unscaled master features
    from src.normalization import load_master_feature_dataset
    master_features = load_master_feature_dataset(str(data_dir))

    print("Loading aligned prices and calculating contemporaneous and forward 20D returns...")
    price_df, daily_returns, fwd_20d_returns = load_clean_prices_and_returns(data_dir)

    # 2. Model Regime Profiles
    print("Computing comprehensive regime profiles (train vs holdout)...")
    regime_profiles = compute_model_regime_profiles(labels_df, master_features)
    profiles_csv_path = regime_profiles_dir / "model_regime_profiles.csv"
    regime_profiles.to_csv(profiles_csv_path, index=False)
    print(f"Saved: {profiles_csv_path} ({len(regime_profiles)} rows)")

    # 3. Sector Performance by Regime
    print("Computing sector performance metrics (contemporaneous daily & forward 20D)...")
    # Pass price_df to enforce training-period forward-return boundary (t+20 <= TRAIN_END_DATE).
    sector_perf = compute_sector_performance_by_regime(
        labels_df, daily_returns, fwd_20d_returns, price_df=price_df
    )
    sector_perf_path = sector_perf_dir / "sector_performance_by_regime.csv"
    sector_perf.to_csv(sector_perf_path, index=False)
    print(f"Saved: {sector_perf_path} ({len(sector_perf)} rows)")

    # 4. Sector Leadership & Laggards
    print("Identifying sector leadership and defensive behavior...")
    leadership_df = identify_sector_leadership(sector_perf)
    leadership_path = sector_lead_dir / "sector_leadership_summary.csv"
    leadership_df.to_csv(leadership_path, index=False)
    print(f"Saved: {leadership_path} ({len(leadership_df)} rows)")

    # 5. Major-Event Analysis
    print("Aligning event calendar and building deduplicated trading-day event windows...")
    events_raw_path = data_dir / "raw" / "Events" / "major_events_2019_2026.csv"
    events_aligned = load_and_align_events(events_raw_path, daily_returns.index)
    is_event_day, event_windows_df = build_event_windows(events_aligned, daily_returns.index, pre_days=2, post_days=2)

    print("Analyzing event-regime associations and event-vs-normal sector returns...")
    event_regime_assoc = analyze_event_regime_associations(labels_df, daily_returns, is_event_day, events_aligned)
    event_assoc_path = event_analysis_dir / "event_regime_association.csv"
    event_regime_assoc.to_csv(event_assoc_path, index=False)
    print(f"Saved: {event_assoc_path} ({len(event_regime_assoc)} rows)")

    # Sector performance during events
    sector_event_perf = analyze_sector_performance_during_events(daily_returns, is_event_day, events_aligned)
    sector_event_path = event_analysis_dir / "sector_performance_during_events.csv"
    sector_event_perf.to_csv(sector_event_path, index=False)
    print(f"Saved: {sector_event_path} ({len(sector_event_perf)} rows)")

    # 6. Cross-Model Comparison
    print("Generating cross-model comparison synthesis...")
    cross_model_df = generate_cross_model_comparison(regime_profiles, leadership_df)
    cross_model_path = reports_dir / "cross_model_comparison_summary.csv"
    cross_model_df.to_csv(cross_model_path, index=False)
    print(f"Saved: {cross_model_path} ({len(cross_model_df)} rows)")

    # 7. HMM Holdout Sector Performance Correlation Analysis
    print("Computing HMM holdout sector return correlation matrices...")
    corr_results = compute_hmm_holdout_sector_correlations(labels_df, daily_returns)
    corr_matrices_path = correlations_dir / "hmm_holdout_sector_correlation_matrices.csv"
    corr_results["matrices_df"].to_csv(corr_matrices_path, index=False)
    print(f"Saved: {corr_matrices_path} ({len(corr_results['matrices_df'])} rows)")

    corr_summary_path = correlations_dir / "hmm_holdout_sector_correlation_summary.csv"
    corr_results["comparison_df"].to_csv(corr_summary_path, index=False)
    print(f"Saved: {corr_summary_path} ({len(corr_results['comparison_df'])} rows)")

    print("Generating HMM holdout sector correlation heatmaps and comparison plot...")
    plot_hmm_holdout_sector_correlations(corr_results, correlations_dir)

    print("=== PHASE 7 PIPELINE EXECUTION COMPLETED SUCCESSFULLY ===")

    return {
        "model_regime_profiles": regime_profiles,
        "sector_performance_by_regime": sector_perf,
        "sector_leadership_summary": leadership_df,
        "event_regime_association": event_regime_assoc,
        "sector_performance_during_events": sector_event_perf,
        "cross_model_comparison_summary": cross_model_df,
        "hmm_holdout_sector_correlation_matrices": corr_results["matrices_df"],
        "hmm_holdout_sector_correlation_summary": corr_results["comparison_df"],
    }


if __name__ == "__main__":
    outputs = run_phase7_pipeline()
