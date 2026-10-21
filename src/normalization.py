import pandas as pd
import numpy as np
from sklearn.preprocessing import RobustScaler, StandardScaler
from typing import Dict, List, Tuple, Union
from pathlib import Path
import os

SECTOR_FEATURES = [
    'Return_20D', 'Return_60D', 
    'Relative_Strength_20D', 'Relative_Strength_60D', 
    'Volatility_20D', 'Volatility_60D'
]

NIFTY50_FEATURES = [
    'Return_20D', 'Return_60D', 
    'NIFTY50_Momentum_20D', 'NIFTY50_Momentum_60D', 
    'NIFTY50_Market_Trend_200D'
]

def get_42_features() -> List[str]:
    """Returns the expected list of 42 feature names in the master dataset."""
    features = NIFTY50_FEATURES.copy()
    features.append('VIX_Close')
    sectors = ['AUTO', 'BANK', 'FMCG', 'IT', 'METAL', 'PHARMA']
    for sector in sectors:
        for feat in SECTOR_FEATURES:
            features.append(f'{sector}_{feat}')
    return features

def load_master_feature_dataset(data_dir: str) -> pd.DataFrame:
    """
    Loads Phase 3 engineered datasets and VIX, combines them into a single master dataframe 
    containing exactly the approved 42 features.
    """
    data_dir = Path(data_dir)
    feat_dir = data_dir / 'processed' / 'feature_engineered'
    aligned_dir = data_dir / 'processed' / 'aligned'
    
    # Load NIFTY 50
    nifty50 = pd.read_csv(feat_dir / 'nifty50_features.csv', index_col='Date', parse_dates=True)
    master_df = nifty50[NIFTY50_FEATURES].copy()
    
    # Load VIX
    vix = pd.read_csv(aligned_dir / 'india_vix_aligned.csv', index_col='Date', parse_dates=True)
    master_df['VIX_Close'] = vix['Close']
    
    # Load Sectors
    sectors = ['auto', 'bank', 'fmcg', 'it', 'metal', 'pharma']
    for sector in sectors:
        sector_df = pd.read_csv(feat_dir / f'nifty_{sector}_features.csv', index_col='Date', parse_dates=True)
        for feat in SECTOR_FEATURES:
            master_df[f'{sector.upper()}_{feat}'] = sector_df[feat]
            
    return master_df

def temporal_train_test_split(df: pd.DataFrame, train_end_date: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits the dataframe into training and testing sets strictly by date to prevent data leakage.
    """
    # Convert string to datetime to ensure correct slicing
    train_end = pd.to_datetime(train_end_date)
    train_df = df.loc[:train_end].copy()
    test_df = df.loc[train_end + pd.Timedelta(days=1):].copy()
    return train_df, test_df

def fit_transform_scaler(train_df: pd.DataFrame, test_df: pd.DataFrame, scaler_type: str = 'robust') -> Tuple[pd.DataFrame, pd.DataFrame, object]:
    """
    Fits the specified scaler on the training data ONLY, then transforms both training and test data.
    NaN values (from rolling windows) are preserved.
    """
    if scaler_type == 'robust':
        scaler = RobustScaler()
    elif scaler_type == 'standard':
        scaler = StandardScaler()
    else:
        raise ValueError("scaler_type must be 'robust' or 'standard'")
        
    train_scaled = pd.DataFrame(index=train_df.index, columns=train_df.columns)
    test_scaled = pd.DataFrame(index=test_df.index, columns=test_df.columns)
    
    # Fit scaler on training data only
    scaler.fit(train_df)
    
    # Transform both sets
    train_scaled.loc[:, train_df.columns] = scaler.transform(train_df)
    test_scaled.loc[:, test_df.columns] = scaler.transform(test_df)
    
    # Enforce float dtype explicitly to avoid object dtypes
    train_scaled = train_scaled.astype(float)
    test_scaled = test_scaled.astype(float)
    
    return train_scaled, test_scaled, scaler

def scale_and_save_master_datasets(data_dir: str, train_end_date: str = '2024-12-31'):
    """
    Complete Phase 5 workflow: Loads features, splits train/test, scales using Robust and Standard methods,
    and saves the results to data/processed/normalized/
    """
    data_dir = Path(data_dir)
    norm_dir = data_dir / 'processed' / 'normalized'
    
    robust_dir = norm_dir / 'robust'
    standard_dir = norm_dir / 'standard'
    robust_dir.mkdir(parents=True, exist_ok=True)
    standard_dir.mkdir(parents=True, exist_ok=True)
    
    master_df = load_master_feature_dataset(data_dir)
    train_df, test_df = temporal_train_test_split(master_df, train_end_date)
    
    # 1. Robust Scaling (Primary)
    train_robust, test_robust, _ = fit_transform_scaler(train_df, test_df, scaler_type='robust')
    full_robust = pd.concat([train_robust, test_robust]).sort_index()
    full_robust.to_csv(robust_dir / 'master_features_robust.csv')
    
    # 2. Standard Scaling (Sensitivity)
    train_standard, test_standard, _ = fit_transform_scaler(train_df, test_df, scaler_type='standard')
    full_standard = pd.concat([train_standard, test_standard]).sort_index()
    full_standard.to_csv(standard_dir / 'master_features_standard.csv')
    
    return full_robust, full_standard
