import numpy as np
import pandas as pd
from typing import Tuple, List

class FeatureEngineer:
    """
    Transforms raw station measurements and AQI records into tabular features
    for time-series machine learning models.
    """

    FEATURE_COLUMNS = [
        # Cyclical Temporal Features
        'hour_sin', 'hour_cos', 'day_of_week', 'is_weekend',
        # Meteorological Features & Decomposed Wind Vectors
        'temperature', 'humidity', 'wind_speed', 'u_wind', 'v_wind',
        # Pollutant Inputs
        'pm25', 'pm10', 'no2', 'so2', 'co', 'o3',
        # Autoregressive Lag Features
        'aqi_lag_1', 'aqi_lag_2', 'aqi_lag_3', 'aqi_lag_24',
        # Rolling Statistics
        'aqi_roll_mean_6h', 'aqi_roll_mean_24h'
    ]

    TARGET_COLUMN = 'target_aqi'

    @classmethod
    def create_features(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Takes a chronological DataFrame with columns:
        ['recorded_at', 'overall_aqi', 'pm25', 'pm10', 'no2', 'so2', 'co', 'o3',
         'temperature', 'humidity', 'wind_speed', 'wind_direction']
        and generates lag, rolling, cyclical, and wind vector features.
        """
        if df.empty or len(df) < 25:
            return pd.DataFrame()

        df = df.copy()
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
        df = df.sort_values('recorded_at').reset_index(drop=True)

        # 1. Temporal & Diurnal Cyclical Features
        hour = df['recorded_at'].dt.hour
        df['hour_sin'] = np.sin(2 * np.pi * hour / 24.0)
        df['hour_cos'] = np.cos(2 * np.pi * hour / 24.0)
        df['day_of_week'] = df['recorded_at'].dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)

        # 2. Wind Vector Decomposition (Degrees & Speed -> Orthogonal U and V components)
        # Prevents 359 deg and 1 deg discontinuity in tree/linear models
        wind_dir_rad = np.radians(df['wind_direction'].fillna(180.0))
        wind_speed = df['wind_speed'].fillna(10.0)
        df['u_wind'] = -wind_speed * np.sin(wind_dir_rad)
        df['v_wind'] = -wind_speed * np.cos(wind_dir_rad)

        # 3. Handle Missing Core Columns with forward/backward fill
        numeric_cols = ['overall_aqi', 'pm25', 'pm10', 'no2', 'so2', 'co', 'o3', 'temperature', 'humidity', 'wind_speed']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].ffill().bfill()
            else:
                df[col] = 0.0

        # 4. Autoregressive Lag Features (t-1, t-2, t-3, t-24)
        df['aqi_lag_1'] = df['overall_aqi'].shift(1)
        df['aqi_lag_2'] = df['overall_aqi'].shift(2)
        df['aqi_lag_3'] = df['overall_aqi'].shift(3)
        df['aqi_lag_24'] = df['overall_aqi'].shift(24)

        # 5. Rolling Window Statistics
        df['aqi_roll_mean_6h'] = df['overall_aqi'].shift(1).rolling(window=6, min_periods=1).mean()
        df['aqi_roll_mean_24h'] = df['overall_aqi'].shift(1).rolling(window=24, min_periods=1).mean()

        # 6. Target Variable (Next Hour AQI: t+1)
        df['target_aqi'] = df['overall_aqi'].shift(-1)

        # Drop rows where lag or target values are NaN
        df_clean = df.dropna(subset=cls.FEATURE_COLUMNS + [cls.TARGET_COLUMN]).reset_index(drop=True)
        return df_clean

    @classmethod
    def temporal_train_test_split(cls, df_features: pd.DataFrame, train_ratio: float = 0.8) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """
        Splits data chronologically (first 80% train, last 20% test).
        Strictly prohibits random shuffling to avoid data leakage in time-series!
        """
        split_idx = int(len(df_features) * train_ratio)
        train_df = df_features.iloc[:split_idx]
        test_df = df_features.iloc[split_idx:]

        X_train = train_df[cls.FEATURE_COLUMNS]
        y_train = train_df[cls.TARGET_COLUMN]
        X_test = test_df[cls.FEATURE_COLUMNS]
        y_test = test_df[cls.TARGET_COLUMN]

        return X_train, X_test, y_train, y_test
