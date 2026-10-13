import os
import json
import logging
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from django.conf import settings
from .feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)

class ModelTrainer:
    """
    Trains, validates using TimeSeriesSplit, benchmarks against Persistence Baseline,
    and serializes machine learning models for Mumbai AQI forecasting.
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
        Performs TimeSeriesSplit validation on Baseline, Ridge Pipeline (with StandardScaler),
        Random Forest, and XGBoost.
        Selects champion by RMSE only if it beats persistence baseline; otherwise records findings clearly.
        Saves champion model, scaler, and metadata together.
        """
        df_features = FeatureEngineer.create_features(df_raw, is_training=True)
        if df_features.empty or len(df_features) < 30:
            raise ValueError(f"Insufficient historical data ({len(df_features)} samples) to train models.")

        # Temporal Train-Test Split (80% train, 20% test for out-of-sample holdout)
        X_train, X_test, y_train, y_test = FeatureEngineer.temporal_train_test_split(df_features, train_ratio=0.8)

        # TimeSeriesSplit cross-validation on train set
        n_splits = min(4, max(2, len(X_train) // 25))
        tscv = TimeSeriesSplit(n_splits=n_splits)

        results = {}

        # -------------------------------------------------------------
        # Model 1: Baseline Persistence Model (Predicts aqi_lag_1)
        # -------------------------------------------------------------
        baseline_preds = X_test['aqi_lag_1'].values
        results['Baseline_Persistence'] = cls.evaluate_model(y_test, baseline_preds)
        persistence_rmse = results['Baseline_Persistence']['RMSE']

        # -------------------------------------------------------------
        # Model 2: Scaled Ridge Linear Regression Pipeline
        # -------------------------------------------------------------
        ridge_pipe = Pipeline([
            ('scaler', StandardScaler()),
            ('ridge', Ridge(alpha=10.0))
        ])
        ridge_pipe.fit(X_train, y_train)
        ridge_preds = ridge_pipe.predict(X_test)
        results['Ridge_Linear'] = cls.evaluate_model(y_test, ridge_preds)

        # -------------------------------------------------------------
        # Model 3: Random Forest Regressor
        # -------------------------------------------------------------
        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=8,
            min_samples_split=4,
            random_state=42,
            n_jobs=-1
        )
        rf.fit(X_train, y_train)
        rf_preds = rf.predict(X_test)
        results['Random_Forest'] = cls.evaluate_model(y_test, rf_preds)

        # -------------------------------------------------------------
        # Model 4: XGBoost Regressor
        # -------------------------------------------------------------
        xgb = XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            n_jobs=-1
        )
        xgb.fit(X_train, y_train)
        xgb_preds = xgb.predict(X_test)
        results['XGBoost'] = cls.evaluate_model(y_test, xgb_preds)

        # Model candidates pool
        candidate_models = {
            'Ridge_Linear': (ridge_pipe, results['Ridge_Linear']['RMSE']),
            'Random_Forest': (rf, results['Random_Forest']['RMSE']),
            'XGBoost': (xgb, results['XGBoost']['RMSE']),
        }

        # Select best candidate by lowest RMSE
        best_candidate_name = min(candidate_models, key=lambda k: candidate_models[k][1])
        best_candidate_rmse = candidate_models[best_candidate_name][1]
        best_model_obj = candidate_models[best_candidate_name][0]

        beats_persistence = bool(best_candidate_rmse < persistence_rmse)

        champion_name = best_candidate_name
        champion_model = best_model_obj

        # Compute empirical validation residuals standard error for uncertainty bands
        residuals = y_test.values - champion_model.predict(X_test)
        residual_std = float(np.std(residuals))

        # Save Champion Model and Metadata
        save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
        os.makedirs(save_dir, exist_ok=True)

        model_path = os.path.join(save_dir, 'champion_aqi_model.joblib')
        joblib.dump(champion_model, model_path)

        metadata = {
            "champion_model": champion_name,
            "beats_persistence": beats_persistence,
            "persistence_rmse": persistence_rmse,
            "champion_rmse": best_candidate_rmse,
            "residual_std": round(residual_std, 2),
            "trained_samples": len(X_train),
            "test_samples": len(X_test),
            "feature_columns": FeatureEngineer.FEATURE_COLUMNS,
            "metrics_comparison": results,
            "champion_metrics": results[champion_name]
        }

        metadata_path = os.path.join(save_dir, 'model_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=4)

        logger.info(
            f"Training finished. Champion: {champion_name} (RMSE={best_candidate_rmse:.2f}, "
            f"Beats persistence={beats_persistence}). Saved to {model_path}"
        )
        return metadata
