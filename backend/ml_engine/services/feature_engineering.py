import numpy as np
import pandas as pd
from typing import Tuple, List

class FeatureEngineer:
    """
    Transforms raw station measurements and AQI records into tabular features
    for time-series machine learning models with per-station grouping and spatial coordinates.
    """

    FEATURE_COLUMNS = [
        # Spatial Station Coordinates
        'latitude', 'longitude',
        # Cyclical Temporal Features
        'hour_sin', 'hour_cos', 'day_of_week', 'is_weekend',
        # Meteorological Features & Decomposed Wind Vectors
        'temperature', 'humidity', 'wind_speed', 'u_wind', 'v_wind',
        # Pollutant Inputs
        'pm25', 'pm10', 'no2', 'so2', 'co', 'o3',
        # Autoregressive Lag Features (computed per station)
        'aqi_lag_1', 'aqi_lag_2', 'aqi_lag_3', 'aqi_lag_24',
        # Rolling Statistics (computed per station)
        'aqi_roll_mean_6h', 'aqi_roll_mean_24h'
    ]

    TARGET_COLUMN = 'target_aqi'

    @classmethod
    def create_features(cls, df: pd.DataFrame, is_training: bool = True) -> pd.DataFrame:
        """
        Takes a DataFrame containing:
        ['station_id', 'latitude', 'longitude', 'recorded_at', 'overall_aqi',
         'pm25', 'pm10', 'no2', 'so2', 'co', 'o3',
         'temperature', 'humidity', 'wind_speed', 'wind_direction']

        Computes lag and rolling features PER STATION (groupby station_id).
        If is_training=True: computes 'target_aqi' = overall_aqi(t+1) and drops rows with NaN target.
        If is_training=False: builds inference features for the latest available row WITHOUT requiring target.
        """
        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
        if 'station_id' not in df.columns:
            df['station_id'] = 'DEFAULT'

        # Sort by station and time
        df = df.sort_values(['station_id', 'recorded_at']).reset_index(drop=True)

        # 1. Spatial Coordinates
        df['latitude'] = df.get('latitude', pd.Series(19.076, index=df.index)).fillna(19.076)
        df['longitude'] = df.get('longitude', pd.Series(72.877, index=df.index)).fillna(72.877)

        # 2. Temporal & Diurnal Cyclical Features
        hour = df['recorded_at'].dt.hour
        df['hour_sin'] = np.sin(2 * np.pi * hour / 24.0)
        df['hour_cos'] = np.cos(2 * np.pi * hour / 24.0)
        df['day_of_week'] = df['recorded_at'].dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)

        # 3. Wind Vector Decomposition
        if 'wind_direction' in df.columns:
            wind_dir_s = df.groupby('station_id')['wind_direction'].transform(lambda s: s.ffill().bfill()).fillna(0.0)
        else:
            wind_dir_s = pd.Series(0.0, index=df.index)

        if 'wind_speed' in df.columns:
            wind_speed_s = df.groupby('station_id')['wind_speed'].transform(lambda s: s.ffill().bfill()).fillna(0.0)
        else:
            wind_speed_s = pd.Series(0.0, index=df.index)

        wind_dir_rad = np.radians(wind_dir_s)
        df['u_wind'] = -wind_speed_s * np.sin(wind_dir_rad)
        df['v_wind'] = -wind_speed_s * np.cos(wind_dir_rad)

        # 4. Handle missing core pollutant columns per station
        numeric_cols = ['overall_aqi', 'pm25', 'pm10', 'no2', 'so2', 'co', 'o3', 'temperature', 'humidity', 'wind_speed']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df.groupby('station_id')[col].transform(lambda s: s.ffill().bfill())
            else:
                df[col] = 0.0

        # 5. Autoregressive Lag Features PER STATION
        df['aqi_lag_1'] = df.groupby('station_id')['overall_aqi'].shift(1)
        df['aqi_lag_2'] = df.groupby('station_id')['overall_aqi'].shift(2)
        df['aqi_lag_3'] = df.groupby('station_id')['overall_aqi'].shift(3)
        df['aqi_lag_24'] = df.groupby('station_id')['overall_aqi'].shift(24)

        # Fallback to current or nearest lag for early history rows
        df['aqi_lag_1'] = df['aqi_lag_1'].fillna(df['overall_aqi'])
        df['aqi_lag_2'] = df['aqi_lag_2'].fillna(df['aqi_lag_1'])
        df['aqi_lag_3'] = df['aqi_lag_3'].fillna(df['aqi_lag_2'])
        df['aqi_lag_24'] = df['aqi_lag_24'].fillna(df['aqi_lag_3'])

        # 6. Rolling Window Statistics PER STATION
        df['aqi_roll_mean_6h'] = (
            df.groupby('station_id')['overall_aqi']
            .transform(lambda s: s.shift(1).rolling(window=6, min_periods=1).mean())
        ).fillna(df['overall_aqi'])
        df['aqi_roll_mean_24h'] = (
            df.groupby('station_id')['overall_aqi']
            .transform(lambda s: s.shift(1).rolling(window=24, min_periods=1).mean())
        ).fillna(df['overall_aqi'])

        if is_training:
            # Target Variable: Next Hour AQI (t+1) per station
            df[cls.TARGET_COLUMN] = df.groupby('station_id')['overall_aqi'].shift(-1)
            # Drop rows with NaN in features or target
            df_clean = df.dropna(subset=cls.FEATURE_COLUMNS + [cls.TARGET_COLUMN]).reset_index(drop=True)
            return df_clean
        else:
            # Inference mode: keep latest rows even without target_aqi
            df_clean = df.dropna(subset=cls.FEATURE_COLUMNS).reset_index(drop=True)
            return df_clean

    @classmethod
    def temporal_train_test_split(
        cls,
        df_features: pd.DataFrame,
        train_ratio: float = 0.8
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
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
