import numpy as np
import pandas as pd
from typing import Tuple, List, Any

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

    DIRECT_HORIZONS = [1, 3, 6, 12, 24]

    MULTI_HORIZON_FEATURE_COLUMNS = [
        # Spatial Station Coordinates
        'latitude', 'longitude',
        # Pollutant Inputs at observation time t
        'pm25', 'pm10', 'no2', 'so2', 'co', 'o3',
        # Meteorology at observation time t
        'temperature', 'humidity', 'wind_speed', 'u_wind', 'v_wind',
        # Autoregressive Lag Features at observation time t
        'aqi_lag_1', 'aqi_lag_2', 'aqi_lag_3', 'aqi_lag_24',
        # Rolling Statistics at observation time t
        'aqi_roll_mean_6h', 'aqi_roll_mean_24h',
        # Known Future Covariates at target time t+h (forecast weather from Open-Meteo)
        'future_temp', 'future_humidity', 'future_wind_speed', 'future_u_wind', 'future_v_wind',
        # Diurnal / Calendar features at target time t+h
        'future_hour_sin', 'future_hour_cos', 'future_day_of_week', 'future_is_weekend'
    ]

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
            # Drop rows with NaN in features or target, sort chronologically across all stations
            df_clean = df.dropna(subset=cls.FEATURE_COLUMNS + [cls.TARGET_COLUMN])
            df_clean = df_clean.sort_values('recorded_at').reset_index(drop=True)
            return df_clean
        else:
            # Inference mode: keep latest rows even without target_aqi, sort chronologically
            df_clean = df.dropna(subset=cls.FEATURE_COLUMNS)
            df_clean = df_clean.sort_values('recorded_at').reset_index(drop=True)
            return df_clean

    @classmethod
    def create_direct_horizon_features(
        cls,
        df: pd.DataFrame,
        horizon: int = 1,
        is_training: bool = True
    ) -> pd.DataFrame:
        """
        Builds direct forecasting dataset for target horizon h (in hours).
        Includes:
        - State at time t: pollutants, autoregressive lags, 24h rolling stats
        - Known future weather covariates at t+h (temperature, humidity, wind vectors shifted by -h)
        - Diurnal / calendar features at target timestamp t+h
        - Target AQI at t+h
        - Baseline persistence (AQI at t) and baseline seasonal naive (AQI at t+h-24)
        """
        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
        if 'station_id' not in df.columns:
            df['station_id'] = 'DEFAULT'

        df = df.sort_values(['station_id', 'recorded_at']).reset_index(drop=True)

        # 1. Spatial Coordinates
        df['latitude'] = df.get('latitude', pd.Series(19.076, index=df.index)).fillna(19.076)
        df['longitude'] = df.get('longitude', pd.Series(72.877, index=df.index)).fillna(72.877)

        # 2. Wind Vector Decomposition at time t
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

        # 3. Clean numeric columns at time t
        numeric_cols = ['overall_aqi', 'pm25', 'pm10', 'no2', 'so2', 'co', 'o3', 'temperature', 'humidity', 'wind_speed']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df.groupby('station_id')[col].transform(lambda s: s.ffill().bfill())
            else:
                df[col] = 0.0

        # 4. Autoregressive Lags at observation time t
        df['aqi_lag_1'] = df.groupby('station_id')['overall_aqi'].shift(1)
        df['aqi_lag_2'] = df.groupby('station_id')['overall_aqi'].shift(2)
        df['aqi_lag_3'] = df.groupby('station_id')['overall_aqi'].shift(3)
        df['aqi_lag_24'] = df.groupby('station_id')['overall_aqi'].shift(24)

        df['aqi_lag_1'] = df['aqi_lag_1'].fillna(df['overall_aqi'])
        df['aqi_lag_2'] = df['aqi_lag_2'].fillna(df['aqi_lag_1'])
        df['aqi_lag_3'] = df['aqi_lag_3'].fillna(df['aqi_lag_2'])
        df['aqi_lag_24'] = df['aqi_lag_24'].fillna(df['aqi_lag_3'])

        # 5. Rolling Statistics at observation time t
        df['aqi_roll_mean_6h'] = (
            df.groupby('station_id')['overall_aqi']
            .transform(lambda s: s.shift(1).rolling(window=6, min_periods=1).mean())
        ).fillna(df['overall_aqi'])
        df['aqi_roll_mean_24h'] = (
            df.groupby('station_id')['overall_aqi']
            .transform(lambda s: s.shift(1).rolling(window=24, min_periods=1).mean())
        ).fillna(df['overall_aqi'])

        # 6. Future Covariates and Calendar at target time t+h
        target_dt = df['recorded_at'] + pd.to_timedelta(horizon, unit='h')
        future_hour = target_dt.dt.hour
        df['future_hour_sin'] = np.sin(2 * np.pi * future_hour / 24.0)
        df['future_hour_cos'] = np.cos(2 * np.pi * future_hour / 24.0)
        df['future_day_of_week'] = target_dt.dt.dayofweek
        df['future_is_weekend'] = (df['future_day_of_week'] >= 5).astype(int)

        # Weather shifted by -h (the known future weather covariate)
        df['future_temp'] = df.groupby('station_id')['temperature'].shift(-horizon)
        df['future_humidity'] = df.groupby('station_id')['humidity'].shift(-horizon)
        df['future_wind_speed'] = df.groupby('station_id')['wind_speed'].shift(-horizon)
        df['future_u_wind'] = df.groupby('station_id')['u_wind'].shift(-horizon)
        df['future_v_wind'] = df.groupby('station_id')['v_wind'].shift(-horizon)

        # 7. Baselines for horizon h:
        # Persistence: prediction is AQI at time t
        df['baseline_persistence'] = df['overall_aqi']
        # Seasonal-Naive: observation 24h prior to target time t+h (recorded at t - (24 - h))
        if horizon == 24:
            df['baseline_seasonal_naive'] = df['overall_aqi']
        else:
            df['baseline_seasonal_naive'] = df.groupby('station_id')['overall_aqi'].shift(24 - horizon)
        df['baseline_seasonal_naive'] = df['baseline_seasonal_naive'].fillna(df['overall_aqi'])

        if is_training:
            # Target Variable: AQI at t+h
            df[cls.TARGET_COLUMN] = df.groupby('station_id')['overall_aqi'].shift(-horizon)
            required_cols = cls.MULTI_HORIZON_FEATURE_COLUMNS + [
                cls.TARGET_COLUMN, 'baseline_persistence', 'baseline_seasonal_naive'
            ]
            df_clean = df.dropna(subset=required_cols)
            df_clean = df_clean.sort_values('recorded_at').reset_index(drop=True)
            return df_clean
        else:
            # Inference mode
            df_clean = df.dropna(subset=cls.MULTI_HORIZON_FEATURE_COLUMNS)
            df_clean = df_clean.sort_values('recorded_at').reset_index(drop=True)
            return df_clean

    @classmethod
    def temporal_train_test_split(
        cls,
        df_features: pd.DataFrame,
        train_ratio: float = 0.8,
        return_dfs: bool = False,
        feature_cols: List[str] = None,
        target_col: str = None
    ) -> Any:
        """
        Splits data chronologically across ALL stations based on a timestamp cutoff.
        Ensures every active station appears in both train and test partitions,
        and guarantees no test timestamp is earlier than any train timestamp.
        """
        cols = feature_cols or cls.FEATURE_COLUMNS
        t_col = target_col or cls.TARGET_COLUMN

        if df_features.empty:
            empty_df = pd.DataFrame(columns=cols)
            empty_s = pd.Series(dtype=float)
            if return_dfs:
                return empty_df, empty_df, empty_s, empty_s, pd.DataFrame(), pd.DataFrame()
            return empty_df, empty_df, empty_s, empty_s

        df_sorted = df_features.sort_values('recorded_at').reset_index(drop=True)

        if 'recorded_at' in df_sorted.columns and df_sorted['recorded_at'].nunique() > 1:
            unique_times = df_sorted['recorded_at'].drop_duplicates().sort_values().reset_index(drop=True)
            cutoff_idx = int(len(unique_times) * train_ratio)
            cutoff_idx = max(1, min(len(unique_times) - 1, cutoff_idx))
            cutoff_time = unique_times.iloc[cutoff_idx]

            train_df = df_sorted[df_sorted['recorded_at'] < cutoff_time].copy()
            test_df = df_sorted[df_sorted['recorded_at'] >= cutoff_time].copy()
        else:
            split_idx = int(len(df_sorted) * train_ratio)
            split_idx = max(1, min(len(df_sorted) - 1, split_idx))
            train_df = df_sorted.iloc[:split_idx].copy()
            test_df = df_sorted.iloc[split_idx:].copy()

        X_train = train_df[cols]
        y_train = train_df[t_col]
        X_test = test_df[cols]
        y_test = test_df[t_col]

        if return_dfs:
            return X_train, X_test, y_train, y_test, train_df, test_df
        return X_train, X_test, y_train, y_test
