import os
import json
import logging
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from django.conf import settings
from .feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)

class ModelTrainer:
    """
    Trains, compares, evaluates, and serializes machine learning models
    for Mumbai AQI time-series forecasting.
    """

    @staticmethod
    def evaluate_model(y_true: pd.Series, y_pred: np.ndarray) -> Dict[str, float]:
        """
        Calculates standard time-series regression metrics: MAE, RMSE, and R2 score.
        """
        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        r2 = float(r2_score(y_true, y_pred))
        return {
            "MAE": round(mae, 2),
            "RMSE": round(rmse, 2),
            "R2_Score": round(r2, 4)
        }

    @classmethod
    def train_and_compare_models(cls, df_raw: pd.DataFrame) -> Dict[str, Any]:
        """
        Trains Baseline, Ridge, Random Forest, and XGBoost models.
        Selects the best performing model and saves it to disk.
        """
        df_features = FeatureEngineer.create_features(df_raw)
        if df_features.empty or len(df_features) < 40:
            raise ValueError(f"Insufficient historical data ({len(df_features)} samples) to train models.")

        X_train, X_test, y_train, y_test = FeatureEngineer.temporal_train_test_split(df_features, train_ratio=0.8)

        results = {}

        # -------------------------------------------------------------
        # Model 1: Baseline Persistence Model (Predicts aqi_lag_1)
        # -------------------------------------------------------------
        baseline_preds = X_test['aqi_lag_1'].values
        results['Baseline_Persistence'] = cls.evaluate_model(y_test, baseline_preds)

        # -------------------------------------------------------------
        # Model 2: Ridge Linear Regression
        # -------------------------------------------------------------
        ridge = Ridge(alpha=1.0)
        ridge.fit(X_train, y_train)
        ridge_preds = ridge.predict(X_test)
        results['Ridge_Linear'] = cls.evaluate_model(y_test, ridge_preds)

        # -------------------------------------------------------------
        # Model 3: Random Forest Regressor
        # -------------------------------------------------------------
        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=4,
            random_state=42,
            n_jobs=-1
        )
        rf.fit(X_train, y_train)
        rf_preds = rf.predict(X_test)
        results['Random_Forest'] = cls.evaluate_model(y_test, rf_preds)

        # -------------------------------------------------------------
        # Model 4: XGBoost Regressor (Champion Candidate)
        # -------------------------------------------------------------
        xgb = XGBRegressor(
            n_estimators=120,
            max_depth=5,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            n_jobs=-1
        )
        xgb.fit(X_train, y_train)
        xgb_preds = xgb.predict(X_test)
        results['XGBoost'] = cls.evaluate_model(y_test, xgb_preds)

        # Select Champion Model (Lowest RMSE)
        candidate_models = {
            'Ridge_Linear': (ridge, results['Ridge_Linear']['RMSE']),
            'Random_Forest': (rf, results['Random_Forest']['RMSE']),
            'XGBoost': (xgb, results['XGBoost']['RMSE']),
        }
        champion_name = min(candidate_models, key=lambda k: candidate_models[k][1])
        champion_model = candidate_models[champion_name][0]

        # Save Champion Model and Metadata
        save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
        os.makedirs(save_dir, exist_ok=True)

        model_path = os.path.join(save_dir, 'champion_aqi_model.joblib')
        joblib.dump(champion_model, model_path)

        metadata = {
            "champion_model": champion_name,
            "trained_samples": len(X_train),
            "test_samples": len(X_test),
            "feature_columns": FeatureEngineer.FEATURE_COLUMNS,
            "metrics_comparison": results,
            "champion_metrics": results[champion_name]
        }

        metadata_path = os.path.join(save_dir, 'model_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=4)

        logger.info(f"Model training complete. Champion: {champion_name} saved to {model_path}")
        return metadata
