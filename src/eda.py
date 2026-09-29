import pandas as pd
import numpy as np
import os
from pathlib import Path
from typing import Dict, Any, List
# pyrefly: ignore [missing-import]
import matplotlib.pyplot as plt
# pyrefly: ignore [missing-import]
import matplotlib.ticker as mticker
import seaborn as sns

def load_feature_engineered_data(data_dir: str) -> Dict[str, pd.DataFrame]:
    """
    Loads all feature-engineered CSV files from the specified directory.
    
    Args:
        data_dir (str): Path to the directory containing feature-engineered CSV files.
        
    Returns:
        Dict[str, pd.DataFrame]: A dictionary with dataset names as keys and DataFrames as values.
    """
    # The actual filenames present in the project
    expected_files = {
        "NIFTY 50": "nifty50_features.csv",
        "NIFTY Auto": "nifty_auto_features.csv",
        "NIFTY Bank": "nifty_bank_features.csv",
        "NIFTY FMCG": "nifty_fmcg_features.csv",
        "NIFTY IT": "nifty_it_features.csv",
        "NIFTY Metal": "nifty_metal_features.csv",
        "NIFTY Pharma": "nifty_pharma_features.csv",
    }
    
    datasets = {}
    base_path = Path(data_dir)
    
    for key, filename in expected_files.items():
        file_path = base_path / filename
        if file_path.exists():
            datasets[key] = pd.read_csv(file_path, parse_dates=["Date"])
        else:
            # Fallback if filename uses _feature_engineered.csv
            fallback_filename = filename.replace("_features.csv", "_feature_engineered.csv")
            fallback_path = base_path / fallback_filename
            if fallback_path.exists():
                datasets[key] = pd.read_csv(fallback_path, parse_dates=["Date"])
            else:
                print(f"Warning: Neither {filename} nor {fallback_filename} found in {data_dir}")
                
    return datasets

def get_dataset_overview(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Returns basic information about a dataset: shape, columns, data types, 
    missing values, duplicate rows, and descriptive statistics.
    
    Args:
        df (pd.DataFrame): The dataset to inspect.
        
    Returns:
        Dict[str, Any]: A dictionary containing overview metrics.
    """
    overview = {
        "Shape": df.shape,
        "Columns": df.columns.tolist(),
        "Data Types": df.dtypes.to_dict(),
        "Missing Values": df.isnull().sum().to_dict(),
        "Total Missing Values": int(df.isnull().sum().sum()),
        "Duplicate Rows": int(df.duplicated().sum()),
        "Descriptive Statistics": df.describe(include='all')
    }
    return overview

def get_date_info(df: pd.DataFrame, date_col_name: str = 'Date') -> Dict[str, Any]:
    """
    Inspects date/index information of a dataset.
    
    Args:
        df (pd.DataFrame): The dataset to inspect.
        date_col_name (str): The expected name of the date column/index (default 'Date').
        
    Returns:
        Dict[str, Any]: A dictionary containing date-related metrics.
    """
    info = {
        "Date is Index": False,
        "Date is Column": False,
        "Date Type": None,
        "Min Date": None,
        "Max Date": None,
        "Unique Dates": 0
    }
    
    date_series = None
    
    # Check if index is datetime or named date_col_name
    if df.index.name and date_col_name.lower() in df.index.name.lower():
        info["Date is Index"] = True
        date_series = pd.Series(df.index)
    elif isinstance(df.index, pd.DatetimeIndex):
         info["Date is Index"] = True
         date_series = pd.Series(df.index)
    else:
        # Find column that matches date_col_name (case insensitive)
        date_cols = [col for col in df.columns if date_col_name.lower() in col.lower()]
        if date_cols:
            info["Date is Column"] = True
            date_col = date_cols[0]
            date_series = df[date_col]
            
    if date_series is not None:
        try:
            info["Date Type"] = str(date_series.dtype)
            info["Min Date"] = date_series.min().strftime('%Y-%m-%d') if pd.notnull(date_series.min()) else None
            info["Max Date"] = date_series.max().strftime('%Y-%m-%d') if pd.notnull(date_series.max()) else None
            info["Unique Dates"] = int(date_series.nunique())
        except Exception as e:
            info["Date Type"] = f"Error evaluating: {str(e)}"
            info["Unique Dates"] = int(date_series.nunique())
            
    return info

def analyze_zero_volume(datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Analyzes zero-volume observations across a dictionary of datasets.
    """
    results = []
    for name, df in datasets.items():
        total_rows = len(df)
        vol_cols = [col for col in df.columns if 'volume' in col.lower()]
        if vol_cols:
            vol_col = vol_cols[0]
            zero_vol_count = int(df[vol_col].eq(0).sum())
            non_zero_vol_count = total_rows - zero_vol_count
            zero_vol_pct = round((zero_vol_count / total_rows) * 100, 2) if total_rows > 0 else 0.0
        else:
            zero_vol_count, zero_vol_pct, non_zero_vol_count = 0, 0.0, total_rows
            
        results.append({
            "Dataset": name,
            "Total Rows": total_rows,
            "Zero Volume Count": zero_vol_count,
            "Zero Volume %": zero_vol_pct,
            "Non-Zero Volume Count": non_zero_vol_count
        })
    return pd.DataFrame(results)

def check_chronological_order(datasets: Dict[str, pd.DataFrame], date_col: str = 'Date') -> pd.DataFrame:
    """
    Verifies whether the Date column is monotonically increasing for each dataset.
    """
    results = []
    for name, df in datasets.items():
        is_monotonic = False
        date_cols = [col for col in df.columns if date_col.lower() in col.lower()]
        if date_cols:
            is_monotonic = df[date_cols[0]].is_monotonic_increasing
        results.append({
            "Dataset": name,
            "Dates Monotonically Increasing": is_monotonic
        })
    return pd.DataFrame(results)

def validate_missing_values(datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Compares actual missing values against expected rolling-window missing values.
    """
    results = []
    for name, df in datasets.items():
        missing = df.isnull().sum()
        missing = missing[missing > 0]
        for feature, count in missing.items():
            expected = 0
            if '200' in feature:
                expected = 200
            elif '60' in feature:
                expected = 60
            elif '20' in feature:
                expected = 20
            elif '14' in feature:
                expected = 14
            elif '10' in feature:
                expected = 10
            elif '5' in feature:
                expected = 5
                
            # Using exact match or close (rolling windows sometimes yield N-1 NaNs)
            if count == expected or count == expected - 1:
                status = "Expected"
            else:
                status = "Unexpected"
                
            results.append({
                "Dataset": name,
                "Feature": feature,
                "Missing Count": int(count),
                "Expected Count": expected,
                "Status": status
            })
    if not results:
        return pd.DataFrame(columns=["Dataset", "Feature", "Missing Count", "Expected Count", "Status"])
    return pd.DataFrame(results)

def get_numerical_sanity_check(datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Inspects min, max, mean, median, and std deviation for numerical features.
    """
    results = []
    for name, df in datasets.items():
        numeric_df = df.select_dtypes(include=[np.number])
        for col in numeric_df.columns:
            results.append({
                "Dataset": name,
                "Feature": col,
                "Min": numeric_df[col].min(),
                "Max": numeric_df[col].max(),
                "Mean": numeric_df[col].mean(),
                "Median": numeric_df[col].median(),
                "Std Dev": numeric_df[col].std()
            })
    return pd.DataFrame(results)

def identify_outliers_iqr(datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Identifies potential statistical outliers using the IQR rule.
    """
    results = []
    for name, df in datasets.items():
        numeric_df = df.select_dtypes(include=[np.number])
        for col in numeric_df.columns:
            Q1 = numeric_df[col].quantile(0.25)
            Q3 = numeric_df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outliers = numeric_df[(numeric_df[col] < lower_bound) | (numeric_df[col] > upper_bound)]
            outlier_count = len(outliers)
            
            if outlier_count > 0:
                results.append({
                    "Dataset": name,
                    "Feature": col,
                    "Potential Outlier Count": outlier_count
                })
    if not results:
        return pd.DataFrame(columns=["Dataset", "Feature", "Potential Outlier Count"])
    return pd.DataFrame(results)

def investigate_zero_volume_dates(datasets: Dict[str, pd.DataFrame], date_col: str = 'Date') -> pd.DataFrame:
    """
    Investigates the first and last occurrence of zero-volume rows for each dataset.
    """
    results = []
    for name, df in datasets.items():
        vol_cols = [col for col in df.columns if 'volume' in col.lower()]
        date_cols = [col for col in df.columns if date_col.lower() in col.lower()]
        
        if vol_cols and date_cols:
            vol_col = vol_cols[0]
            d_col = date_cols[0]
            zero_vol_df = df[df[vol_col] == 0]
            
            count = len(zero_vol_df)
            first_date = zero_vol_df[d_col].min() if count > 0 else None
            last_date = zero_vol_df[d_col].max() if count > 0 else None
            
            if pd.notnull(first_date):
                first_date = pd.to_datetime(first_date).strftime('%Y-%m-%d')
            if pd.notnull(last_date):
                last_date = pd.to_datetime(last_date).strftime('%Y-%m-%d')
        else:
            count = 0
            first_date = None
            last_date = None
            
        results.append({
            "Dataset": name,
            "Zero Volume Count": count,
            "First Zero Volume Date": first_date,
            "Last Zero Volume Date": last_date
        })
        
    return pd.DataFrame(results)

def get_zero_volume_clustering(df: pd.DataFrame, date_col: str = 'Date') -> str:
    """
    Groups zero-volume observations by year to determine if they are clustered or spread out.
    """
    vol_cols = [col for col in df.columns if 'volume' in col.lower()]
    date_cols = [col for col in df.columns if date_col.lower() in col.lower()]
    
    if not vol_cols or not date_cols:
        return "N/A"
    
    zero_vol_df = df[df[vol_cols[0]] == 0].copy()
    if zero_vol_df.empty:
        return "No zero-volume dates."
        
    zero_vol_df[date_cols[0]] = pd.to_datetime(zero_vol_df[date_cols[0]])
    counts_by_year = zero_vol_df[date_cols[0]].dt.year.value_counts().sort_index()
    
    summary = [f"{year}: {count} obs" for year, count in counts_by_year.items()]
    return ", ".join(summary)


def plot_feature_distributions(
    datasets: Dict[str, pd.DataFrame],
    features_dict: Dict[str, List[str]],
    bins: int = 60,
    fig_width: int = 14,
    row_height: float = 3.8,
) -> None:
    """
    Plot histogram + KDE distributions for specified features across datasets.

    For each dataset the function selects the feature list from `features_dict`
    using the dataset name as key, falling back to the 'default' key when no
    exact match exists.  Features absent from a dataset's columns are silently
    skipped.

    NaN values are excluded **only for plotting**; the underlying DataFrames are
    never modified.

    Parameters
    ----------
    datasets : dict
        Mapping of dataset-name → DataFrame (as loaded by
        ``load_feature_engineered_data``).
    features_dict : dict
        Mapping of dataset-name → list of feature column names.
        Use the key ``'default'`` for features that apply to all sector datasets
        that are not explicitly listed.
    bins : int
        Number of histogram bins (default 60).
    fig_width : int
        Total figure width in inches (default 14).
    row_height : float
        Height in inches per subplot row (default 3.8).
    """
    sns.set_theme(style="whitegrid", context="notebook")
    COLS = 2  # subplots per row

    for name, df in datasets.items():
        # Resolve feature list for this dataset
        if name in features_dict:
            requested = features_dict[name]
        elif "default" in features_dict:
            requested = features_dict["default"]
        else:
            continue

        # Keep only features that actually exist in this dataset
        valid = [f for f in requested if f in df.columns]
        if not valid:
            continue

        n = len(valid)
        rows = int(np.ceil(n / COLS))
        fig, axes = plt.subplots(
            rows, COLS,
            figsize=(fig_width, row_height * rows),
            squeeze=False,
        )
        fig.suptitle(f"Feature Distributions — {name}", fontsize=14, fontweight="bold", y=1.01)

        for idx, feature in enumerate(valid):
            ax = axes[idx // COLS][idx % COLS]
            # Drop NaNs only for plotting — data not modified
            plot_data = df[feature].dropna()

            sns.histplot(
                plot_data,
                bins=bins,
                kde=True,
                ax=ax,
                color="steelblue",
                edgecolor="none",
                alpha=0.75,
                line_kws={"lw": 1.8},
            )

            mean_val = plot_data.mean()
            median_val = plot_data.median()
            skewness = float(plot_data.skew())

            ax.axvline(mean_val, color="#e74c3c", lw=1.4, ls="--", label=f"Mean: {mean_val:.4f}")
            ax.axvline(median_val, color="#2ecc71", lw=1.4, ls="-", label=f"Median: {median_val:.4f}")

            ax.set_title(
                f"{feature}  (n={len(plot_data):,}, skew={skewness:.2f})",
                fontsize=9.5,
            )
            ax.set_xlabel(feature, fontsize=8.5)
            ax.set_ylabel("Count", fontsize=8.5)
            ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.3g"))
            ax.legend(fontsize=7.5, framealpha=0.7)

        # Hide any unused subplots
        for empty_idx in range(n, rows * COLS):
            axes[empty_idx // COLS][empty_idx % COLS].set_visible(False)

        plt.tight_layout()
        plt.show()


def plot_feature_outliers(
    datasets: Dict[str, pd.DataFrame],
    features_dict: Dict[str, List[str]],
    fig_width: int = 14,
    row_height: float = 4.0,
) -> None:
    """
    Plot boxplots to visually identify potential extreme observations in
    numerical engineered features across datasets.

    For each dataset the function resolves the feature list from
    ``features_dict`` using the dataset name as the primary key, falling back
    to the ``'default'`` key for datasets that are not explicitly listed.
    Features absent from a dataset's columns are silently skipped.

    NaN values are excluded **only for plotting**; the underlying DataFrames
    are never modified.

    The whiskers follow the standard Tukey 1.5 × IQR rule, consistent with
    the ``identify_outliers_iqr`` tabular summary in Section 3.5.  Points
    beyond the whiskers are rendered as individual flier markers and represent
    *potential* extreme observations — not confirmed data errors.

    Parameters
    ----------
    datasets : dict
        Mapping of dataset-name → DataFrame (as loaded by
        ``load_feature_engineered_data``).
    features_dict : dict
        Mapping of dataset-name → list of feature column names.
        Use the key ``'default'`` for features that apply to all sector
        datasets that are not explicitly listed.
    fig_width : int
        Total figure width in inches (default 14).
    row_height : float
        Height in inches per subplot row (default 4.0).
    """
    sns.set_theme(style="whitegrid", context="notebook")
    COLS = 2  # subplots per row

    for name, df in datasets.items():
        # Resolve feature list for this dataset
        if name in features_dict:
            requested = features_dict[name]
        elif "default" in features_dict:
            requested = features_dict["default"]
        else:
            continue

        # Keep only features that actually exist in this dataset
        valid = [f for f in requested if f in df.columns]
        if not valid:
            continue

        n = len(valid)
        rows = int(np.ceil(n / COLS))
        fig, axes = plt.subplots(
            rows, COLS,
            figsize=(fig_width, row_height * rows),
            squeeze=False,
        )
        fig.suptitle(
            f"Outlier Visualization (Boxplots) — {name}",
            fontsize=14,
            fontweight="bold",
            y=1.01,
        )

        for idx, feature in enumerate(valid):
            ax = axes[idx // COLS][idx % COLS]
            # Drop NaNs only for plotting — data not modified
            plot_data = df[feature].dropna()

            ax.boxplot(
                plot_data,
                vert=True,
                patch_artist=True,
                widths=0.5,
                boxprops=dict(facecolor="steelblue", alpha=0.55, linewidth=1.2),
                medianprops=dict(color="#e74c3c", linewidth=2.0),
                whiskerprops=dict(linewidth=1.2, linestyle="--"),
                capprops=dict(linewidth=1.5),
                flierprops=dict(
                    marker="o",
                    markersize=3.5,
                    markerfacecolor="#e67e22",
                    markeredgewidth=0.4,
                    alpha=0.6,
                ),
                # whis=1.5 is the matplotlib default (Tukey rule) — stated
                # explicitly here for documentation clarity
                whis=1.5,
            )

            n_obs = len(plot_data)
            # Count fliers for annotation
            q1 = plot_data.quantile(0.25)
            q3 = plot_data.quantile(0.75)
            iqr = q3 - q1
            n_fliers = int(
                ((plot_data < q1 - 1.5 * iqr) | (plot_data > q3 + 1.5 * iqr)).sum()
            )

            ax.set_title(
                f"{feature}  (n={n_obs:,}, fliers={n_fliers:,})",
                fontsize=9.5,
            )
            ax.set_ylabel(feature, fontsize=8.5)
            ax.set_xticks([])          # single box — x tick label not needed
            ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3g"))

            # Annotate dataset/sector name inside the plot for clarity
            ax.text(
                0.97, 0.97, name,
                transform=ax.transAxes,
                fontsize=7.5,
                color="dimgray",
                ha="right", va="top",
            )

        # Hide any unused subplots
        for empty_idx in range(n, rows * COLS):
            axes[empty_idx // COLS][empty_idx % COLS].set_visible(False)

        plt.tight_layout()
        plt.show()


def plot_feature_correlations(
    datasets: Dict[str, pd.DataFrame],
    features_dict: Dict[str, List[str]],
    method: str = "pearson",
    fig_width: int = 9,
) -> None:
    """
    Plot a Pearson (or Spearman) correlation heatmap for selected features
    within each dataset.

    The goal is to surface potentially redundant feature pairs (high positive
    correlation) or strongly opposing relationships (high negative correlation).
    This is an observational step only — no features are removed.

    NaN values are excluded pairwise (i.e. each pair is computed over the rows
    where both values are present); the underlying DataFrames are never
    modified.

    Parameters
    ----------
    datasets : dict
        Mapping of dataset-name → DataFrame (as produced by
        ``load_feature_engineered_data``).
    features_dict : dict
        Mapping of dataset-name → list of feature column names.
        Use the key ``'default'`` for features that apply to all sector
        datasets that are not explicitly listed.
    method : str
        Correlation method passed to ``DataFrame.corr()``.
        Either ``'pearson'`` (default) or ``'spearman'``.
    fig_width : int
        Width of each heatmap figure in inches.  Height is computed
        automatically from the number of features (default 9).
    """
    sns.set_theme(style="white", context="notebook")

    for name, df in datasets.items():
        # Resolve feature list for this dataset
        if name in features_dict:
            requested = features_dict[name]
        elif "default" in features_dict:
            requested = features_dict["default"]
        else:
            continue

        # Keep only features that exist in this dataset
        valid = [f for f in requested if f in df.columns]
        if len(valid) < 2:
            print(f"[{name}] Fewer than 2 valid features — skipping.")
            continue

        # Compute correlation on a NaN-safe copy (pairwise complete)
        corr_matrix = df[valid].corr(method=method)

        n_feat = len(valid)
        cell_size = 1.0          # inches per cell
        fig_h = max(4, n_feat * cell_size + 1.2)
        fig_w = max(fig_width, n_feat * cell_size + 2.0)

        fig, ax = plt.subplots(figsize=(fig_w, fig_h))

        mask = np.zeros_like(corr_matrix, dtype=bool)  # show full matrix
        sns.heatmap(
            corr_matrix,
            ax=ax,
            mask=mask,
            cmap="coolwarm",
            vmin=-1.0,
            vmax=1.0,
            center=0.0,
            annot=True,
            fmt=".2f",
            annot_kws={"size": 8.5},
            linewidths=0.5,
            linecolor="white",
            cbar_kws={"shrink": 0.75, "label": f"{method.capitalize()} r"},
        )

        ax.set_title(
            f"{method.capitalize()} Correlation — {name}",
            fontsize=12,
            fontweight="bold",
            pad=12,
        )
        ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8.5)
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=8.5)

        plt.tight_layout()
        plt.show()



# Section 4.4 — Sector Comparison


_SECTOR_KEYS = [
    "NIFTY Auto",
    "NIFTY Bank",
    "NIFTY FMCG",
    "NIFTY IT",
    "NIFTY Metal",
    "NIFTY Pharma",
]

# Palette: one distinct colour per sector, order matches _SECTOR_KEYS
_SECTOR_PALETTE = [
    "#4C72B0",  # Auto   — muted blue
    "#DD8452",  # Bank   — muted orange
    "#55A868",  # FMCG   — muted green
    "#C44E52",  # IT     — muted red
    "#8172B3",  # Metal  — muted purple
    "#937860",  # Pharma — muted brown
]


def plot_sector_comparison(
    datasets: Dict[str, pd.DataFrame],
    features: List[str],
    fig_width: int = 12,
    fig_height: float = 5.2,
) -> None:
    """
    Compare the distribution of each feature across the six sector indices
    using grouped boxplots — one figure per feature.

    NIFTY 50 is **always excluded** from the comparison because it is the
    benchmark/reference index rather than a sector index.  Volume is excluded
    by passing only the six primary sector features to ``features``.

    The function is purely descriptive: it does not rank sectors, does not
    make investment recommendations, and does not make feature-selection
    decisions.

    NaN values are excluded **only for plotting**; the underlying DataFrames
    are never modified.

    Parameters
    ----------
    datasets : dict
        Mapping of dataset-name → DataFrame (as loaded by
        ``load_feature_engineered_data``).  Must include the six sector keys.
    features : list of str
        Feature column names to compare across sectors.
        Typically the six primary sector features:
        ``['Return_20D', 'Return_60D',
           'Relative_Strength_20D', 'Relative_Strength_60D',
           'Volatility_20D', 'Volatility_60D']``.
        Features missing from all sector DataFrames are silently skipped.
    fig_width : int
        Width of each figure in inches (default 12).
    fig_height : float
        Height of each figure in inches (default 5.2).
    """
    sns.set_theme(style="whitegrid", context="notebook")

    # Resolve which sector datasets are actually available
    available_sectors = [k for k in _SECTOR_KEYS if k in datasets]
    if not available_sectors:
        print("No sector datasets found in `datasets`. Nothing to plot.")
        return

    for feature in features:
        # Build a long-form DataFrame: one row per (sector, value) pair
        frames = []
        for sector in available_sectors:
            df = datasets[sector]
            if feature not in df.columns:
                continue
            series = df[feature].dropna()
            if series.empty:
                continue
            frames.append(
                pd.DataFrame({"Sector": sector, feature: series.values})
            )

        if not frames:
            print(f"[{feature}] Not available in any sector dataset — skipping.")
            continue

        plot_df = pd.concat(frames, ignore_index=True)

        # Short labels for x-axis (drop the "NIFTY " prefix)
        plot_df["Sector_Short"] = plot_df["Sector"].str.replace(
            "NIFTY ", "", regex=False
        )

        # Preserve order matching _SECTOR_KEYS
        sector_order_short = [
            k.replace("NIFTY ", "") for k in available_sectors
        ]
        palette = {
            k.replace("NIFTY ", ""): _SECTOR_PALETTE[_SECTOR_KEYS.index(k)]
            for k in available_sectors
        }

        fig, ax = plt.subplots(figsize=(fig_width, fig_height))

        sns.boxplot(
            data=plot_df,
            x="Sector_Short",
            y=feature,
            hue="Sector_Short",
            order=sector_order_short,
            hue_order=sector_order_short,
            palette=palette,
            legend=False,
            width=0.55,
            linewidth=1.2,
            flierprops=dict(
                marker="o",
                markersize=3.0,
                markerfacecolor="#7f8c8d",
                markeredgewidth=0.3,
                alpha=0.55,
            ),
            medianprops=dict(color="#e74c3c", linewidth=2.0),
            boxprops=dict(alpha=0.75),
            ax=ax,
        )

        # Overlay individual sector medians as text annotations
        for i, sector_short in enumerate(sector_order_short):
            vals = plot_df.loc[
                plot_df["Sector_Short"] == sector_short, feature
            ]
            if vals.empty:
                continue
            median_val = vals.median()
            ax.text(
                i,
                ax.get_ylim()[1],
                f"med={median_val:.3f}",
                ha="center",
                va="bottom",
                fontsize=7.0,
                color="dimgray",
            )

        ax.set_title(
            f"Sector Comparison — {feature}",
            fontsize=13,
            fontweight="bold",
            pad=10,
        )
        ax.set_xlabel("Sector", fontsize=10)
        ax.set_ylabel(feature, fontsize=10)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3g"))
        ax.tick_params(axis="x", labelsize=9.5)
        ax.tick_params(axis="y", labelsize=8.5)

        # Footnote: NIFTY 50 and Volume are excluded
        fig.text(
            0.5, -0.03,
            "NIFTY 50 excluded (benchmark). "
            "Whiskers: Tukey 1.5 × IQR. Points beyond whiskers are potential extremes.",
            ha="center",
            fontsize=7.5,
            color="dimgray",
            style="italic",
        )

        plt.tight_layout()
        plt.show()



# Section 4.5 — Time-Series / Sector Behaviour


# Colour map reused from 4.4 so sectors are visually consistent across sections
_TS_SECTOR_COLORS = dict(zip(_SECTOR_KEYS, _SECTOR_PALETTE))


def plot_sector_time_series(
    datasets: Dict[str, pd.DataFrame],
    features: List[str],
    date_col: str = "Date",
    fig_width: int = 16,
    fig_height: float = 5.0,
) -> None:
    """
    Plot the time evolution of selected features across all six sector indices.

    One figure is produced per feature.  Within each figure, all six sectors
    are drawn as overlapping coloured lines against a shared Date x-axis,
    making it easy to see which sectors move together and which diverge.

    Design rationale
    ----------------
    Overlaying all sectors on a single axes (rather than small-multiples)
    preserves a common y-scale so amplitude differences are directly visible.
    The 20D features are sufficient for capturing responsive temporal variation;
    passing a short ``features`` list keeps the number of figures manageable.

    Constraints
    -----------
    * NIFTY 50 is **always excluded** (it is the benchmark, not a sector).
    * Volume is excluded by the caller — do not pass it in ``features``.
    * No event annotations are added here (deferred to Section 4.6).
    * No regimes are manually defined.
    * NaN values are handled by Matplotlib's default line-break behaviour
      (gaps appear where data is missing); the DataFrames are never modified.

    Parameters
    ----------
    datasets : dict
        Mapping of dataset-name → DataFrame.
    features : list of str
        Feature column names to plot over time.
        Recommended: ``['Return_20D', 'Relative_Strength_20D', 'Volatility_20D']``.
    date_col : str
        Name of the date column (default ``'Date'``).
    fig_width : int
        Figure width in inches (default 16).
    fig_height : float
        Figure height in inches per feature figure (default 5.0).
    """
    sns.set_theme(style="whitegrid", context="notebook", font_scale=1.05)

    available_sectors = [k for k in _SECTOR_KEYS if k in datasets]
    if not available_sectors:
        print("No sector datasets found in `datasets`. Nothing to plot.")
        return

    for feature in features:
        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=150)
        plotted_any = False

        for sector in available_sectors:
            df = datasets[sector]
            if feature not in df.columns or date_col not in df.columns:
                continue

            # Work on a view — never modify the original DataFrame
            ts = (
                df[[date_col, feature]]
                .copy()
                .sort_values(date_col)
            )

            color = _TS_SECTOR_COLORS.get(sector, None)
            label = sector.replace("NIFTY ", "")

            ax.plot(
                ts[date_col],
                ts[feature],
                color=color,
                linewidth=1.4,
                alpha=0.88,
                label=label,
            )
            plotted_any = True

        if not plotted_any:
            plt.close(fig)
            print(f"[{feature}] Not available in any sector dataset — skipping.")
            continue

        ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.45)

        ax.set_title(
            f"Sector Time Series — {feature}",
            fontsize=15,
            fontweight="bold",
            pad=14,
        )
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel(feature, fontsize=12)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3g"))
        ax.tick_params(axis="x", labelsize=10.5, rotation=25)
        ax.tick_params(axis="y", labelsize=10.5)

        leg = ax.legend(
            title="Sector",
            fontsize=10.0,
            title_fontsize=10.5,
            loc="upper left",
            framealpha=0.85,
            edgecolor="#cccccc",
            ncol=2,
            handlelength=2.0,
            handleheight=0.8,
            borderpad=0.6,
            labelspacing=0.4,
        )
        leg.get_frame().set_linewidth(0.8)

        fig.text(
            0.5, -0.01,
            "NIFTY 50 excluded (benchmark). Volume excluded (data-quality issue). "
            "No regimes are manually defined at this stage.",
            ha="center",
            fontsize=8.5,
            color="dimgray",
            style="italic",
        )

        plt.tight_layout(rect=[0, 0.03, 1, 1])
        plt.show()


def plot_nifty50_time_series(
    datasets: Dict[str, pd.DataFrame],
    features: List[str],
    date_col: str = "Date",
    fig_width: int = 16,
    row_height: float = 3.8,
) -> None:
    """
    Plot the time evolution of selected NIFTY 50 market-level features on
    stacked subplots sharing a common Date x-axis.

    Each feature occupies its own subplot row, allowing different y-scales
    while keeping the time axis aligned for cross-feature visual comparison.

    Constraints
    -----------
    * Only the ``'NIFTY 50'`` dataset is used.
    * No event annotations (deferred to Section 4.6).
    * No manual regime labels.
    * NaN values produce line gaps; DataFrames are never modified.

    Parameters
    ----------
    datasets : dict
        Mapping of dataset-name → DataFrame.  Must include ``'NIFTY 50'``.
    features : list of str
        NIFTY 50 feature column names to plot.
        Recommended:
        ``['Return_20D', 'Volatility_20D', 'NIFTY50_Market_Trend_200D']``.
    date_col : str
        Name of the date column (default ``'Date'``).
    fig_width : int
        Figure width in inches (default 16).
    row_height : float
        Height per subplot row in inches (default 3.8).
    """
    sns.set_theme(style="whitegrid", context="notebook", font_scale=1.05)

    nifty_key = "NIFTY 50"
    if nifty_key not in datasets:
        print("'NIFTY 50' not found in `datasets`. Nothing to plot.")
        return

    df = datasets[nifty_key]

    # Keep only features that exist
    valid = [f for f in features if f in df.columns]
    if not valid:
        print("None of the requested features exist in the NIFTY 50 dataset.")
        return

    # Sort chronologically on a copy — original DataFrame not modified
    ts = df[[date_col] + valid].copy().sort_values(date_col)

    n = len(valid)
    fig, axes = plt.subplots(
        n, 1,
        figsize=(fig_width, row_height * n),
        dpi=150,
        sharex=True,
        squeeze=False,
    )
    fig.suptitle(
        "NIFTY 50 — Market-Level Feature Time Series",
        fontsize=15,
        fontweight="bold",
        y=1.02,
    )

    # A stable colour sequence for the NIFTY 50 subplots
    nifty_colors = ["#2c7bb6", "#d7191c", "#1a9641"]

    for idx, feature in enumerate(valid):
        ax = axes[idx][0]
        color = nifty_colors[idx % len(nifty_colors)]

        ax.plot(
            ts[date_col],
            ts[feature],
            color=color,
            linewidth=1.4,
            alpha=0.90,
        )
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.45)

        ax.set_ylabel(feature, fontsize=11.0)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3g"))
        ax.tick_params(axis="y", labelsize=10.0)
        ax.set_title(feature, fontsize=11.5, fontweight="semibold", pad=6)

    axes[-1][0].set_xlabel("Date", fontsize=12)
    axes[-1][0].tick_params(axis="x", labelsize=10.5, rotation=25)

    fig.text(
        0.5, -0.01,
        "No event annotations or manual regime labels at this stage.",
        ha="center",
        fontsize=8.5,
        color="dimgray",
        style="italic",
    )

    plt.tight_layout(rect=[0, 0.02, 1, 0.98])
    plt.subplots_adjust(hspace=0.38)
    plt.show()


# ---------------------------------------------------------------------------
# Section 4.6 — Event-Based Market Behaviour
# ---------------------------------------------------------------------------

# Absolute path to the existing event-calendar file, resolved from eda.py's
# own location so it works regardless of the notebook's working directory.
# eda.py lives at <project_root>/src/eda.py  →  parents[1] = <project_root>
_EVENT_CALENDAR_PATH: Path = (
    Path(__file__).resolve().parents[1]
    / "data" / "raw" / "Events" / "major_events_2019_2026.csv"
)

# Colour coding by event category group for the vertical markers
_EVENT_CATEGORY_COLORS = {
    "pandemic":           "#e74c3c",   # red
    "geopolitical":       "#c0392b",   # dark red
    "monetary policy":    "#2980b9",   # blue
    "us monetary policy": "#2980b9",
    "indian policy":      "#27ae60",   # green
    "fiscal":             "#27ae60",
    "elections":          "#8e44ad",   # purple
    "trade policy":       "#e67e22",   # orange
    "global trade":       "#e67e22",
    "banking crisis":     "#f39c12",   # amber
    "international summit": "#7f8c8d", # grey
    "natural disaster":   "#16a085",   # teal
    "domestic market shock": "#c0392b",
    "global market shock":   "#e74c3c",
    "global financial shock": "#e74c3c",
}

def _resolve_event_color(category: str) -> str:
    """Return a marker colour for an event category string."""
    cat_lower = category.lower()
    for key, color in _EVENT_CATEGORY_COLORS.items():
        if key in cat_lower:
            return color
    return "#95a5a6"  # default grey


def load_event_calendar(
    event_csv_path: "str | Path" = _EVENT_CALENDAR_PATH,
) -> pd.DataFrame:
    """
    Load and parse the major-event calendar from the existing project CSV.

    The default path is resolved **relative to this module's location** (i.e.
    ``<project_root>/data/raw/Events/major_events_2019_2026.csv``), so the
    function works correctly regardless of the notebook's working directory.

    The CSV uses DD-MM-YYYY date format for ``start_date`` and ``end_date``.
    Both columns are converted to ``datetime64[ns]``.

    The source file is **never modified**.

    Parameters
    ----------
    event_csv_path : str or Path
        Absolute or relative path to ``major_events_2019_2026.csv``.
        Defaults to the project-root-relative location resolved from
        ``eda.py``'s own directory.

    Returns
    -------
    pd.DataFrame
        Parsed event calendar with ``start_date`` and ``end_date`` as
        ``datetime64[ns]`` columns.
    """
    df = pd.read_csv(Path(event_csv_path))
    df["start_date"] = pd.to_datetime(df["start_date"], dayfirst=True)
    df["end_date"]   = pd.to_datetime(df["end_date"],   dayfirst=True)
    return df


def plot_event_annotated_market_behaviour(
    datasets: Dict[str, pd.DataFrame],
    features: List[str],
    events: pd.DataFrame,
    date_col: str = "Date",
    severity_filter: str = "high",
    max_annotations: int = 14,
    fig_width: int = 17,
    fig_height: float = 6.0,
) -> None:
    """
    Plot NIFTY 50 market-level features as time series with annotated
    major-event markers sourced from the existing project event calendar.

    One high-resolution figure is produced per feature.  Vertical dashed
    lines mark each selected event date; labels are staggered in alternating
    y-positions to minimise overlap when many events are present.

    Purpose / constraints
    ---------------------
    * Events are used for **contextual interpretation** only — not as ML
      features, not as manual regime boundaries.
    * No event names or dates are fabricated; ``events`` must be loaded via
      ``load_event_calendar()``.
    * NaN values produce line gaps; no DataFrame is ever modified.
    * No event annotations from Section 4.6 carry forward into 4.7 decisions.

    Annotation strategy
    -------------------
    1. Filter the calendar to ``severity == severity_filter`` (default
       ``'high'``).
    2. Keep only events whose ``start_date`` falls within the dataset's date
       range.
    3. If the filtered set still exceeds ``max_annotations``, the most
       India-relevant categories are prioritised (Indian policy, monetary
       policy, pandemic, geopolitical, domestic market shock) and the
       remainder are kept only if space permits.
    4. Alternating y-positions (two levels) prevent vertical label stacking.
    5. Colour coding groups events visually by broad category.

    Parameters
    ----------
    datasets : dict
        Mapping of dataset-name → DataFrame.  Must include ``'NIFTY 50'``.
    features : list of str
        NIFTY 50 feature column names to plot.
        Recommended: ``['Return_20D', 'Volatility_20D']``.
    events : pd.DataFrame
        Parsed event calendar as returned by ``load_event_calendar()``.
        Must contain: ``start_date`` (datetime), ``event_name`` (str),
        ``event_category`` (str), ``severity`` (str).
    date_col : str
        Name of the date column in the NIFTY 50 DataFrame (default ``'Date'``).
    severity_filter : str
        Severity level to include in annotations (default ``'high'``).
    max_annotations : int
        Maximum number of event lines drawn per figure to preserve readability
        (default 14).
    fig_width : int
        Figure width in inches (default 17).
    fig_height : float
        Figure height in inches (default 6.0).
    """
    sns.set_theme(style="whitegrid", context="notebook", font_scale=1.1)

    nifty_key = "NIFTY 50"
    if nifty_key not in datasets:
        print("'NIFTY 50' not found in `datasets`. Nothing to plot.")
        return

    nifty_df = datasets[nifty_key]

    # Determine the dataset date range for filtering events
    date_series = pd.to_datetime(nifty_df[date_col])
    ds_start = date_series.min()
    ds_end   = date_series.max()

    # ------------------------------------------------------------------
    # Filter events: severity + within dataset range
    # ------------------------------------------------------------------
    ev = events.copy()
    ev = ev[ev["severity"].str.lower() == severity_filter.lower()]
    ev = ev[
        (ev["start_date"] >= ds_start) &
        (ev["start_date"] <= ds_end)
    ].sort_values("start_date").reset_index(drop=True)

    if ev.empty:
        print(
            f"No '{severity_filter}' severity events found within the dataset "
            "date range. Try a different severity_filter."
        )
        return

    # ------------------------------------------------------------------
    # Prioritise India/market-critical categories to resolve clutter
    # ------------------------------------------------------------------
    priority_cats = [
        "pandemic", "global market shock", "domestic market shock",
        "global financial shock", "geopolitical", "banking crisis",
        "indian policy", "monetary policy", "elections", "trade policy"
    ]
    def _priority(cat: str) -> int:
        cat_l = cat.lower()
        for i, p in enumerate(priority_cats):
            if p in cat_l:
                return i
        return len(priority_cats)

    ev = (
        ev.assign(_pri=ev["event_category"].apply(_priority))
        .sort_values(["_pri", "start_date"])
        .head(max_annotations)
    )

    # ------------------------------------------------------------------
    # Plot one figure per feature
    # ------------------------------------------------------------------
    for feature in features:
        if feature not in nifty_df.columns:
            print(f"[{feature}] Not found in NIFTY 50 dataset — skipping.")
            continue

        # Work on a sorted copy — original not modified
        ts = (
            nifty_df[[date_col, feature]]
            .copy()
            .sort_values(date_col)
        )

        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=150)

        # ---- Main time-series line ----
        ax.plot(
            ts[date_col],
            ts[feature],
            color="#2c3e50",
            linewidth=1.4,
            alpha=0.90,
            zorder=3,
            label=f"NIFTY 50 — {feature}",
        )
        ax.axhline(0, color="black", linewidth=0.7, linestyle="--", alpha=0.35, zorder=2)

        # ---- Event annotations ----
        # Proximity-aware multi-level staggering with strict overlap prevention
        # ---------------------------------------------------------------
        
        N_LANES     = 4      # vertical stagger levels above the plot
        LANE_STEP   = 0.075  # fraction of y_range per lane step
        BASE_OFFSET = 0.03   # fraction of y_range for lane-0 (lowest) label
        MIN_CLEAR   = 0.038  # min normalised-x gap before forcing a new lane
        MAX_CHARS   = 28     # maximum displayed label length (chars)

        y_min_ax, y_max_ax = ax.get_ylim()
        y_range_ax = y_max_ax - y_min_ax
        
        # Normalise event x-positions to [0,1] for proximity detection
        x_min_dt = pd.Timestamp(ax.get_xlim()[0], unit="D")
        x_max_dt = pd.Timestamp(ax.get_xlim()[1], unit="D")
        x_span   = (x_max_dt - x_min_dt).total_seconds()

        def _norm_x(dt: pd.Timestamp) -> float:
            return (dt - x_min_dt).total_seconds() / x_span if x_span > 0 else 0.0

        # Assign each event to a lane in order of PRIORITY to guarantee the most important fit.
        # We check all existing items in a lane to ensure clearance.
        lane_occupancy = {i: [] for i in range(N_LANES)}
        
        plotted_events = []
        
        for _, row in ev.iterrows():
            evt_date = row["start_date"]
            norm_x = _norm_x(evt_date)
            
            chosen_lane = None
            for lane_idx in range(N_LANES):
                conflict = False
                for occupied_x in lane_occupancy[lane_idx]:
                    if abs(norm_x - occupied_x) < MIN_CLEAR:
                        conflict = True
                        break
                if not conflict:
                    chosen_lane = lane_idx
                    break
            
            # If it fits without overlapping higher-priority events, keep it
            if chosen_lane is not None:
                lane_occupancy[chosen_lane].append(norm_x)
                plotted_events.append({
                    "row": row,
                    "lane": chosen_lane,
                })
        
        # Sort plotted events chronologically for drawing
        plotted_events.sort(key=lambda x: x["row"]["start_date"])

        # Draw vertical markers and labels only for events that fit
        for item in plotted_events:
            row = item["row"]
            chosen_lane = item["lane"]
            
            evt_date = row["start_date"]
            evt_name = row["event_name"]
            evt_cat  = row["event_category"]
            color    = _resolve_event_color(evt_cat)

            ax.axvline(
                evt_date,
                color=color,
                linewidth=0.85,
                linestyle=":",
                alpha=0.65,
                zorder=1,
            )

            label_y = y_max_ax + y_range_ax * (BASE_OFFSET + chosen_lane * LANE_STEP)

            short_label = (
                evt_name if len(evt_name) <= MAX_CHARS
                else evt_name[:MAX_CHARS - 1] + "…"
            )

            # Annotate with a vertical leader line from label foot → axis top
            ax.annotate(
                short_label,
                xy=(evt_date, y_max_ax),
                xytext=(evt_date, label_y),
                xycoords="data",
                textcoords="data",
                fontsize=6.2,
                color=color,
                rotation=60,
                ha="left",
                va="bottom",
                clip_on=False,
                arrowprops=dict(
                    arrowstyle="-",
                    color=color,
                    lw=0.55,
                    alpha=0.55,
                ),
                annotation_clip=False,
            )

        # ---- Titles / labels ----
        ax.set_title(
            f"NIFTY 50 — {feature} with Major Market Event Annotations",
            fontsize=14,
            fontweight="bold",
            pad=14,
        )
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel(feature, fontsize=12)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3g"))
        ax.tick_params(axis="x", labelsize=10.5, rotation=25)
        ax.tick_params(axis="y", labelsize=10.5)

        # ---- Legend: feature line only ----
        ax.legend(
            fontsize=10,
            loc="lower left",
            framealpha=0.80,
            edgecolor="#cccccc",
        )

        # ---- Footnote ----
        fig.text(
            0.5, -0.02,
            f"Events: severity='{severity_filter}' from data/raw/Events/major_events_2019_2026.csv  |  "
            f"{len(ev)} events shown  |  "
            "Events are used for contextual interpretation only — not as ML features or manual regime labels.",
            ha="center",
            fontsize=7.5,
            color="dimgray",
            style="italic",
        )

        # Top margin enlarged to accommodate N_LANES stagger levels
        top_margin = 1.0 - (BASE_OFFSET + (N_LANES - 1) * LANE_STEP + 0.18)
        plt.tight_layout(rect=[0, 0.03, 1, max(top_margin, 0.72)])
        plt.show()


def plot_sector_event_response(
    datasets: Dict[str, pd.DataFrame],
    features: List[str],
    events: pd.DataFrame,
    event_ids: List[str],
    window_days: int = 30,
    date_col: str = "Date",
    fig_width: int = 18,
    fig_height: float = 4.5,
) -> None:
    """
    Plot event-centered time-series comparisons across all six sectors for a 
    specific list of major market-wide events.

    This generates one figure per event. Each figure contains one subplot
    per requested feature, allowing direct comparison of sector magnitudes
    and behaviour around the shock.

    The event date is matched to the nearest available trading day in the 
    dataset to gracefully handle events occurring on weekends/holidays.

    Purpose / constraints
    ---------------------
    * To interpret whether sectors respond homogeneously or divergently to 
      the same macro-shock.
    * No sector ranking is performed.
    * Events are used for contextual interpretation only.

    Parameters
    ----------
    datasets : dict
        Mapping of dataset-name → DataFrame. Must contain all six NIFTY 
        sector datasets. 'NIFTY 50' is used as the trading-day reference.
    features : list of str
        Features to plot as subplots (e.g. ``['Return_20D', 'Volatility_20D', 
        'Relative_Strength_20D']``).
    events : pd.DataFrame
        Parsed event calendar.
    event_ids : list of str
        List of ``event_id``s from the calendar to generate plots for.
    window_days : int
        Number of trading days before and after the event to include in 
        the plot window (default 30).
    date_col : str
        Name of the date column (default ``'Date'``).
    fig_width : int
        Figure width in inches (default 18).
    fig_height : float
        Figure height in inches (default 4.5).
    """
    sns.set_theme(style="whitegrid", context="notebook", font_scale=1.1)

    ref_df = datasets.get("NIFTY 50")
    if ref_df is None:
        print("Error: 'NIFTY 50' required in datasets to establish trading days.")
        return

    # Extract clean series of all trading dates
    ref_dates = pd.to_datetime(ref_df[date_col]).sort_values().reset_index(drop=True)

    for event_id in event_ids:
        evt_row = events[events["event_id"] == event_id]
        if evt_row.empty:
            print(f"Event ID {event_id} not found in calendar. Skipping.")
            continue
        
        evt_row = evt_row.iloc[0]
        target_date = pd.to_datetime(evt_row["start_date"])
        evt_name = evt_row["event_name"]

        # 1. Map calendar date to nearest trading day
        diffs = (ref_dates - target_date).abs()
        center_idx = diffs.idxmin()
        actual_date = ref_dates.iloc[center_idx]
        
        # 2. Define trading-day window
        start_idx = max(0, center_idx - window_days)
        end_idx = min(len(ref_dates) - 1, center_idx + window_days)
        window_dates = set(ref_dates.iloc[start_idx : end_idx + 1])

        # 3. Create figure (1 row × N features)
        fig, axes = plt.subplots(1, len(features), figsize=(fig_width, fig_height), dpi=150)
        if len(features) == 1:
            axes = [axes]
            
        fig.suptitle(
            f"Sector Response: {evt_name}\n"
            f"(Event: {target_date.date()} | Nearest Trading Day: {actual_date.date()} | ±{window_days} Trading Days)",
            fontsize=15, 
            fontweight="bold", 
            y=1.06
        )

        for ax, feature in zip(axes, features):
            # Plot each sector
            for sector in _SECTOR_KEYS:
                if sector not in datasets:
                    continue
                
                df_sec = datasets[sector]
                # Filter to window
                df_win = df_sec[df_sec[date_col].isin(window_dates)].sort_values(date_col)
                if df_win.empty or feature not in df_win.columns:
                    continue
                
                ax.plot(
                    df_win[date_col], 
                    df_win[feature],
                    color=_TS_SECTOR_COLORS.get(sector, "#95a5a6"),
                    label=sector,
                    linewidth=1.7,
                    alpha=0.88
                )

            # Draw vertical line for the actual trading date of the event
            ax.axvline(actual_date, color="#e74c3c", linestyle=":", linewidth=1.5, alpha=0.8, zorder=1)
            # Draw zero-line for reference
            ax.axhline(0, color="black", linestyle="-", linewidth=0.8, alpha=0.4, zorder=1)
            
            ax.set_title(feature, fontsize=13, fontweight="semibold", pad=10)
            ax.set_xlabel("Date", fontsize=11)
            ax.tick_params(axis="x", rotation=25, labelsize=9.5)
            ax.tick_params(axis="y", labelsize=9.5)
            ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3g"))

        # Single shared legend at the bottom
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(
            handles, labels, 
            loc="lower center", 
            ncol=len(_SECTOR_KEYS), 
            bbox_to_anchor=(0.5, -0.12), 
            frameon=False, 
            fontsize=11
        )
        
        plt.tight_layout()
        plt.show()
