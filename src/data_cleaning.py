"""
src/data_cleaning.py
====================
Reusable functions for Phase 2 data cleaning and alignment.

Responsibilities:
- Verify data types, indices, and required columns
- Handle and document duplicated/missing values
- Clean event dates
- Align multiple market datasets to their common trading days
"""

import logging
import pandas as pd
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

def clean_market_data(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    """
    Cleans a market dataset (raw Phase 1 format) without modifying values.
    
    Operations:
    1. Ensures the index is a DatetimeIndex named 'Date'.
    2. Drops exact duplicate rows.
    3. Drops duplicate index dates (keeps last).
    4. Sorts chronologically.
    
    Parameters
    ----------
    df : pd.DataFrame
        The raw dataframe.
    dataset_name : str
        Name of the dataset for logging.
        
    Returns
    -------
    pd.DataFrame
        The cleaned dataframe.
    """
    df = df.copy()
    
    # Ensure index is Datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
        else:
            df.index = pd.to_datetime(df.index)
    
    df.index.name = "Date"
    
    initial_rows = len(df)
    
    # 1. Exact duplicates
    df = df.drop_duplicates()
    exact_dupes = initial_rows - len(df)
    
    # 2. Duplicate indices
    dup_index = df.index.duplicated(keep='last')
    idx_dupes = dup_index.sum()
    df = df[~dup_index]
    
    # 3. Sort chronologically
    df = df.sort_index()
    
    logger.info(f"[{dataset_name}] Cleaned. Dropped {exact_dupes} exact dupes, {idx_dupes} index dupes. Final rows: {len(df)}.")
    return df


def clean_event_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans the major events dataset by parsing dates to standard datetimes.
    
    Parameters
    ----------
    df : pd.DataFrame
        Raw events dataframe.
        
    Returns
    -------
    pd.DataFrame
        Cleaned events dataframe with datetime columns.
    """
    df = df.copy()
    
    date_cols = ['start_date', 'end_date']
    for col in date_cols:
        if col in df.columns:
            # The raw data uses DD-MM-YYYY format
            df[col] = pd.to_datetime(df[col], format='%d-%m-%Y', errors='coerce')
    
    # Sort by start_date
    df = df.sort_values(by='start_date').reset_index(drop=True)
    
    logger.info(f"[Events] Parsed dates. Total events: {len(df)}.")
    return df


def align_market_datasets(datasets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Aligns multiple market datasets to their strict common intersection of trading days.
    
    Parameters
    ----------
    datasets : dict[str, pd.DataFrame]
        A dictionary mapping dataset names to their cleaned DataFrames.
        
    Returns
    -------
    dict[str, pd.DataFrame]
        A dictionary containing the aligned DataFrames.
    """
    if not datasets:
        return {}
    
    # Find intersection of all dates
    common_dates = None
    for name, df in datasets.items():
        if common_dates is None:
            common_dates = df.index
        else:
            common_dates = common_dates.intersection(df.index)
            
    common_dates = common_dates.sort_values()
    logger.info(f"[Alignment] Found {len(common_dates)} common trading days across {len(datasets)} datasets.")
    
    aligned = {}
    for name, df in datasets.items():
        # Filter to common dates
        df_aligned = df.loc[common_dates].copy()
        
        # Verify alignment
        assert len(df_aligned) == len(common_dates), f"Dataset {name} alignment length mismatch."
        
        aligned[name] = df_aligned
        logger.info(f"[{name}] Aligned from {len(df)} -> {len(df_aligned)} rows.")
        
    return aligned
