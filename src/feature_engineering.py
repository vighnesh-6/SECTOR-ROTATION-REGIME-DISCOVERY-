import pandas as pd
# pyrefly: ignore [missing-import]
import numpy as np

def calculate_returns(df: pd.DataFrame, column: str = 'Close', windows: list[int] = [20, 60]) -> pd.DataFrame:
    """
    Calculate trailing returns for the specified windows.
    
    Formula: (Close_t / Close_{t-window}) - 1
    
    Args:
        df: Input DataFrame containing the price column.
        column: The name of the column to calculate returns for (e.g., 'Close').
        windows: List of lookback windows for return calculation.
        
    Returns:
        A new DataFrame with the calculated return columns added.
    """
    # Create a copy to avoid modifying the original dataframe
    out_df = df.copy()
    
    for window in windows:
        col_name = f'Return_{window}D'
        # Shift the column by the window size
        out_df[col_name] = (out_df[column] / out_df[column].shift(window)) - 1
        
    return out_df

def calculate_momentum_sma(df: pd.DataFrame, column: str = 'Close', windows: list[int] = [20, 60], prefix: str = 'Momentum') -> pd.DataFrame:
    """
    Calculate momentum using the Price-to-SMA ratio.
    
    Formula: Close_t / SMA(Close, window)_t
    
    Args:
        df: Input DataFrame containing the price column.
        column: The name of the column to calculate momentum for (e.g., 'Close').
        windows: List of lookback windows for SMA calculation.
        prefix: Prefix for the generated column name.
        
    Returns:
        A new DataFrame with the calculated momentum columns added.
    """
    out_df = df.copy()
    
    for window in windows:
        col_name = f'{prefix}_{window}D'
        # Calculate Simple Moving Average (SMA) over the window using pandas rolling
        sma = out_df[column].rolling(window=window).mean()
        # Momentum is the ratio of current price to its SMA
        out_df[col_name] = out_df[column] / sma
        
    return out_df

def calculate_relative_strength(df_sector: pd.DataFrame, df_benchmark: pd.DataFrame, windows: list[int] = [20, 60]) -> pd.DataFrame:
    """
    Calculate Sector Relative Strength against a benchmark.
    
    Formula: Sector_Return - Benchmark_Return
    
    Args:
        df_sector: Input DataFrame containing the sector features (including Returns).
        df_benchmark: Input DataFrame containing the benchmark features (including Returns).
        windows: List of lookback windows to compute relative strength for.
        
    Returns:
        A new DataFrame with the calculated relative strength columns added.
    """
    out_df = df_sector.copy()
    
    for window in windows:
        return_col = f'Return_{window}D'
        rs_col = f'Relative_Strength_{window}D'
        
        # Calculate relative strength as the difference in returns
        # The index alignment handles matching the exact trading dates
        out_df[rs_col] = out_df[return_col] - df_benchmark[return_col]
        
    return out_df

def calculate_volatility(df: pd.DataFrame, column: str = 'Close', windows: list[int] = [20, 60], prefix: str = 'Volatility') -> pd.DataFrame:
    """
    Calculate annualized historical volatility.
    
    Formula: std(log(Close_t / Close_{t-1}), window) * sqrt(252)
    
    Args:
        df: Input DataFrame containing the price column.
        column: The name of the column to calculate volatility for.
        windows: List of lookback windows for standard deviation.
        prefix: Prefix for the generated column name.
        
    Returns:
        A new DataFrame with the calculated volatility columns added.
    """
    out_df = df.copy()
    
    # Calculate daily log returns
    log_returns = np.log(out_df[column] / out_df[column].shift(1))
    
    for window in windows:
        col_name = f'{prefix}_{window}D'
        # Calculate standard deviation over the rolling window and annualize
        out_df[col_name] = log_returns.rolling(window=window).std() * np.sqrt(252)
        
    return out_df

def calculate_market_trend(df: pd.DataFrame, column: str = 'Close', window: int = 200, col_name: str = 'Market_Trend_200D') -> pd.DataFrame:
    """
    Calculate Market Trend based on Price-to-SMA ratio.
    
    Formula: Close_t / SMA(Close, window)_t
    
    Args:
        df: Input DataFrame containing the price column.
        column: The name of the column to calculate trend for.
        window: Lookback window for SMA calculation (default 200).
        col_name: Name of the generated feature column.
        
    Returns:
        A new DataFrame with the calculated market trend column added.
    """
    out_df = df.copy()
    
    # Calculate Simple Moving Average (SMA) over the window using pandas rolling
    sma = out_df[column].rolling(window=window).mean()
    
    # Market Trend is the ratio of current price to its SMA
    out_df[col_name] = out_df[column] / sma
        
    return out_df
