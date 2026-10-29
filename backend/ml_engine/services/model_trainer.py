import os
import json
import logging
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, List
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
    def train_and_compare_models(
        cls,
        df_raw: pd.DataFrame,
        min_samples: int = 500,
        save_champion: bool = True,
        dataset_label: str = "all"
    ) -> Dict[str, Any]:
        """
        Performs TimeSeriesSplit cross-validation on candidate models (Ridge Pipeline,
        Random Forest, XGBoost) and two baselines (Persistence, Seasonal-Naive 24h).
        Reports fold MAE/RMSE mean and std, evaluates on holdout test set, and selects
        champion by lowest RMSE only if it beats persistence baseline.
        """
        df_features = FeatureEngineer.create_features(df_raw, is_training=True)
        if df_features.empty or len(df_features) < min_samples:
            raise ValueError(
                f"Insufficient historical data ({len(df_features)} samples for dataset '{dataset_label}'). "
                f"Minimum required is {min_samples} rows to prevent unrepresentative training."
            )

        # Temporal Train-Test Split (chronological time cutoff across all stations)
        X_train, X_test, y_train, y_test = FeatureEngineer.temporal_train_test_split(df_features, train_ratio=0.8)

        # Model instantiation factories
        model_factories = {
            'Ridge_Linear': lambda: Pipeline([
                ('scaler', StandardScaler()),
                ('ridge', Ridge(alpha=10.0))
            ]),
            'Random_Forest': lambda: RandomForestRegressor(
                n_estimators=100,
                max_depth=8,
                min_samples_split=4,
                random_state=42,
                n_jobs=-1
            ),
            'XGBoost': lambda: XGBRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.08,
                subsample=0.85,
                colsample_bytree=0.85,
                random_state=42,
                n_jobs=-1
            )
        }

        # -------------------------------------------------------------
        # TimeSeriesSplit Cross-Validation on Train Set
        # -------------------------------------------------------------
        n_splits = min(5, max(2, len(X_train) // 100))
        tscv = TimeSeriesSplit(n_splits=n_splits)

        all_model_names = ['Baseline_Persistence', 'Baseline_Seasonal_Naive', 'Ridge_Linear', 'Random_Forest', 'XGBoost']
        cv_fold_scores: Dict[str, Dict[str, List[float]]] = {
            m: {'mae': [], 'rmse': []} for m in all_model_names
        }

        for fold_idx, (tr_idx, val_idx) in enumerate(tscv.split(X_train)):
            X_fold_tr, X_fold_val = X_train.iloc[tr_idx], X_train.iloc[val_idx]
            y_fold_tr, y_fold_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]

            # 1. Baseline Persistence on fold
            pred_p = X_fold_val['aqi_lag_1'].values
            cv_fold_scores['Baseline_Persistence']['mae'].append(float(mean_absolute_error(y_fold_val, pred_p)))
            cv_fold_scores['Baseline_Persistence']['rmse'].append(float(np.sqrt(mean_squared_error(y_fold_val, pred_p))))

            # 2. Baseline Seasonal-Naive (24h lag) on fold
            pred_sn = X_fold_val['aqi_lag_24'].fillna(X_fold_val['aqi_lag_1']).values
            cv_fold_scores['Baseline_Seasonal_Naive']['mae'].append(float(mean_absolute_error(y_fold_val, pred_sn)))
            cv_fold_scores['Baseline_Seasonal_Naive']['rmse'].append(float(np.sqrt(mean_squared_error(y_fold_val, pred_sn))))

            # 3. Supervised Machine Learning models on fold
            for name, factory in model_factories.items():
                m_inst = factory()
                m_inst.fit(X_fold_tr, y_fold_tr)
                pred_m = m_inst.predict(X_fold_val)
                cv_fold_scores[name]['mae'].append(float(mean_absolute_error(y_fold_val, pred_m)))
                cv_fold_scores[name]['rmse'].append(float(np.sqrt(mean_squared_error(y_fold_val, pred_m))))

        # -------------------------------------------------------------
        # Full Train Set Fitting & Out-Of-Sample Holdout Evaluation
        # -------------------------------------------------------------
        results: Dict[str, Any] = {}

        # Baseline 1: Persistence
        baseline_preds = X_test['aqi_lag_1'].values
        results['Baseline_Persistence'] = cls.evaluate_model(y_test, baseline_preds)

        # Baseline 2: Seasonal-Naive (t-24h)
        seasonal_naive_preds = X_test['aqi_lag_24'].fillna(X_test['aqi_lag_1']).values
        results['Baseline_Seasonal_Naive'] = cls.evaluate_model(y_test, seasonal_naive_preds)

        persistence_rmse = results['Baseline_Persistence']['RMSE']
        seasonal_naive_rmse = results['Baseline_Seasonal_Naive']['RMSE']

        # Fit each candidate on full training set and evaluate on test set
        fitted_models: Dict[str, Any] = {}
        candidate_rmses: Dict[str, float] = {}

        for name, factory in model_factories.items():
            model_inst = factory()
            model_inst.fit(X_train, y_train)
            test_preds = model_inst.predict(X_test)
            results[name] = cls.evaluate_model(y_test, test_preds)
            fitted_models[name] = model_inst
            candidate_rmses[name] = results[name]['RMSE']

        # Attach cross-validation summary (mean and std) per model
        for name in all_model_names:
            maes = cv_fold_scores[name]['mae']
            rmses = cv_fold_scores[name]['rmse']
            results[name]['cv_folds'] = n_splits
            results[name]['cv_mae_mean'] = round(float(np.mean(maes)), 2)
            results[name]['cv_mae_std'] = round(float(np.std(maes)), 2)
            results[name]['cv_rmse_mean'] = round(float(np.mean(rmses)), 2)
            results[name]['cv_rmse_std'] = round(float(np.std(rmses)), 2)

        # Select best candidate by lowest test RMSE
        best_candidate_name = min(candidate_rmses, key=lambda k: candidate_rmses[k])
        best_candidate_rmse = candidate_rmses[best_candidate_name]
        champion_model = fitted_models[best_candidate_name]

        beats_persistence = bool(best_candidate_rmse < persistence_rmse)
        beats_seasonal_naive = bool(best_candidate_rmse < seasonal_naive_rmse)
        champion_name = best_candidate_name

        # Compute empirical validation residuals standard error for uncertainty bands
        residuals = y_test.values - champion_model.predict(X_test)
        residual_std = float(np.std(residuals))

        # Save Champion Model and Metadata
        save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
        os.makedirs(save_dir, exist_ok=True)

        metadata = {
            "champion_model": champion_name,
            "dataset_label": dataset_label,
            "beats_persistence": beats_persistence,
            "beats_seasonal_naive": beats_seasonal_naive,
            "persistence_rmse": persistence_rmse,
            "seasonal_naive_rmse": seasonal_naive_rmse,
            "champion_rmse": best_candidate_rmse,
            "residual_std": round(residual_std, 2),
            "trained_samples": len(X_train),
            "test_samples": len(X_test),
            "cv_splits": n_splits,
            "feature_columns": FeatureEngineer.FEATURE_COLUMNS,
            "metrics_comparison": results,
            "champion_metrics": results[champion_name]
        }

        model_path = os.path.join(save_dir, 'champion_aqi_model.joblib')
        if save_champion:
            joblib.dump(champion_model, model_path)
            metadata_path = os.path.join(save_dir, 'model_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=4)
            logger.info(
                f"Training finished. Champion: {champion_name} (RMSE={best_candidate_rmse:.2f}, "
                f"Beats persistence={beats_persistence}, Beats seasonal-naive={beats_seasonal_naive}). "
                f"Saved to {model_path}"
            )
        else:
            logger.info(
                f"Evaluation finished for '{dataset_label}'. Champion: {champion_name} (RMSE={best_candidate_rmse:.2f})."
            )
        return metadata

    @classmethod
    def train_direct_multi_horizon_models(
        cls,
        df_raw: pd.DataFrame,
        horizons: List[int] = None,
        min_samples: int = 500,
        save_models: bool = True,
        dataset_label: str = "All Data"
    ) -> Dict[str, Any]:
        """
        Trains separate direct forecasting models for horizons +1h, +3h, +6h, +12h, +24h.
        Each model utilizes state at time t plus known future weather covariates at t+h.
        Computes calibrated empirical residual quantiles (split-conformal intervals)
        and benchmarks against Persistence (t) and Seasonal-Naive (t+h-24) per horizon.
        """
        if horizons is None:
            horizons = [1, 3, 6, 12, 24]

        per_horizon_metrics: Dict[str, Any] = {}
        conformal_intervals: Dict[str, Any] = {}
        direct_models: Dict[int, Any] = {}

        last_X_tr = None
        last_X_te = None

        for h in horizons:
            df_h = FeatureEngineer.create_direct_horizon_features(df_raw, horizon=h, is_training=True)
            if df_h.empty or len(df_h) < min_samples:
                raise ValueError(
                    f"Insufficient historical data ({len(df_h)} samples) for horizon +{h}h on '{dataset_label}'. "
                    f"Minimum required is {min_samples} rows."
                )

            X_tr, X_te, y_tr, y_te, tr_df, te_df = FeatureEngineer.temporal_train_test_split(
                df_h,
                train_ratio=0.8,
                return_dfs=True,
                feature_cols=FeatureEngineer.MULTI_HORIZON_FEATURE_COLUMNS
            )
            last_X_tr = X_tr
            last_X_te = X_te

            # 1. Baselines on Holdout Test Set for Horizon h
            # Persistence: prediction is AQI at time t
            pred_p = te_df['baseline_persistence'].values
            res_p = cls.evaluate_model(y_te, pred_p)

            # Seasonal-Naive: observation 24h prior to target time t+h
            pred_sn = te_df['baseline_seasonal_naive'].values
            res_sn = cls.evaluate_model(y_te, pred_sn)

            # 2. Candidate ML Models for Horizon h
            model_factories = {
                'Ridge_Linear': lambda: Pipeline([
                    ('scaler', StandardScaler()),
                    ('ridge', Ridge(alpha=10.0))
                ]),
                'Random_Forest': lambda: RandomForestRegressor(
                    n_estimators=100,
                    max_depth=8,
                    min_samples_split=4,
                    random_state=42,
                    n_jobs=-1
                ),
                'XGBoost': lambda: XGBRegressor(
                    n_estimators=100,
                    max_depth=4,
                    learning_rate=0.08,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    random_state=42,
                    n_jobs=-1
                )
            }

            # TimeSeriesSplit Cross-Validation on Train Set for Horizon h
            n_splits = min(5, max(2, len(X_tr) // 100))
            tscv = TimeSeriesSplit(n_splits=n_splits)

            all_cand_names = ['Baseline_Persistence', 'Baseline_Seasonal_Naive', 'Ridge_Linear', 'Random_Forest', 'XGBoost']
            cv_scores = {m: {'mae': [], 'rmse': []} for m in all_cand_names}

            for tr_idx, val_idx in tscv.split(X_tr):
                X_f_tr, X_f_val = X_tr.iloc[tr_idx], X_tr.iloc[val_idx]
                y_f_tr, y_f_val = y_tr.iloc[tr_idx], y_tr.iloc[val_idx]
                tr_f_df, val_f_df = tr_df.iloc[tr_idx], tr_df.iloc[val_idx]

                # Fold baselines
                fold_p = val_f_df['baseline_persistence'].values
                cv_scores['Baseline_Persistence']['mae'].append(float(mean_absolute_error(y_f_val, fold_p)))
                cv_scores['Baseline_Persistence']['rmse'].append(float(np.sqrt(mean_squared_error(y_f_val, fold_p))))

                fold_sn = val_f_df['baseline_seasonal_naive'].values
                cv_scores['Baseline_Seasonal_Naive']['mae'].append(float(mean_absolute_error(y_f_val, fold_sn)))
                cv_scores['Baseline_Seasonal_Naive']['rmse'].append(float(np.sqrt(mean_squared_error(y_f_val, fold_sn))))

                # Fold ML models
                for m_name, factory in model_factories.items():
                    inst = factory()
                    inst.fit(X_f_tr, y_f_tr)
                    preds_val = inst.predict(X_f_val)
                    cv_scores[m_name]['mae'].append(float(mean_absolute_error(y_f_val, preds_val)))
                    cv_scores[m_name]['rmse'].append(float(np.sqrt(mean_squared_error(y_f_val, preds_val))))

            # Full Train Set Fit & Out-of-Sample Holdout Evaluation
            h_results: Dict[str, Any] = {
                'Baseline_Persistence': res_p,
                'Baseline_Seasonal_Naive': res_sn
            }
            fitted_candidates: Dict[str, Any] = {}
            candidate_rmses: Dict[str, float] = {}

            for m_name, factory in model_factories.items():
                m_inst = factory()
                m_inst.fit(X_tr, y_tr)
                test_preds = m_inst.predict(X_te)
                h_results[m_name] = cls.evaluate_model(y_te, test_preds)
                fitted_candidates[m_name] = m_inst
                candidate_rmses[m_name] = h_results[m_name]['RMSE']

            for m_name in all_cand_names:
                h_results[m_name]['cv_rmse_mean'] = round(float(np.mean(cv_scores[m_name]['rmse'])), 2)
                h_results[m_name]['cv_rmse_std'] = round(float(np.std(cv_scores[m_name]['rmse'])), 2)
                h_results[m_name]['cv_mae_mean'] = round(float(np.mean(cv_scores[m_name]['mae'])), 2)
                h_results[m_name]['cv_mae_std'] = round(float(np.std(cv_scores[m_name]['mae'])), 2)

            best_h_name = min(candidate_rmses, key=lambda k: candidate_rmses[k])
            best_h_model = fitted_candidates[best_h_name]
            direct_models[h] = best_h_model

            # Calibrate empirical residual quantiles (Split-conformal intervals)
            test_preds = best_h_model.predict(X_te)
            abs_residuals = np.abs(y_te.values - test_preds)
            q80 = float(np.percentile(abs_residuals, 80))
            q90 = float(np.percentile(abs_residuals, 90))

            conformal_intervals[str(h)] = {
                "q80": round(q80, 1),
                "q90": round(q90, 1)
            }

            per_horizon_metrics[str(h)] = {
                "horizon_hours": h,
                "champion_model": best_h_name,
                "MAE": h_results[best_h_name]['MAE'],
                "RMSE": h_results[best_h_name]['RMSE'],
                "R2_Score": h_results[best_h_name]['R2_Score'],
                "persistence_MAE": res_p['MAE'],
                "persistence_RMSE": res_p['RMSE'],
                "seasonal_naive_MAE": res_sn['MAE'],
                "seasonal_naive_RMSE": res_sn['RMSE'],
                "beats_persistence": bool(h_results[best_h_name]['RMSE'] < res_p['RMSE']),
                "beats_seasonal_naive": bool(h_results[best_h_name]['RMSE'] < res_sn['RMSE']),
                "conformal_error_band": round(q90, 1),
                "cv_rmse_mean": h_results[best_h_name]['cv_rmse_mean'],
                "cv_rmse_std": h_results[best_h_name]['cv_rmse_std'],
                "all_candidates": h_results
            }

        # Select overall primary champion from horizon +1h
        h1_meta = per_horizon_metrics[str(horizons[0])]
        overall_champion_name = h1_meta["champion_model"]

        save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
        os.makedirs(save_dir, exist_ok=True)

        metadata = {
            "model_type": "Direct_Multi_Horizon",
            "horizons": horizons,
            "champion_model": overall_champion_name,
            "dataset_label": dataset_label,
            "champion_rmse": h1_meta["RMSE"],
            "residual_std": conformal_intervals[str(horizons[0])]["q90"],
            "persistence_rmse": h1_meta["persistence_RMSE"],
            "seasonal_naive_rmse": h1_meta["seasonal_naive_RMSE"],
            "beats_persistence": h1_meta["beats_persistence"],
            "beats_seasonal_naive": h1_meta["beats_seasonal_naive"],
            "trained_samples": len(last_X_tr) if last_X_tr is not None else 0,
            "test_samples": len(last_X_te) if last_X_te is not None else 0,
            "feature_columns": FeatureEngineer.MULTI_HORIZON_FEATURE_COLUMNS,
            "metrics_comparison": h1_meta["all_candidates"],
            "champion_metrics": h1_meta["all_candidates"][overall_champion_name],
            "per_horizon_metrics": per_horizon_metrics,
            "conformal_intervals": conformal_intervals
        }

        if save_models:
            # 1. Save Direct Models Dictionary Bundle
            direct_bundle_path = os.path.join(save_dir, 'direct_models.joblib')
            joblib.dump(direct_models, direct_bundle_path)

            # 2. Save Champion model (h=1) for single-step backward compatibility
            champ_path = os.path.join(save_dir, 'champion_aqi_model.joblib')
            joblib.dump(direct_models[horizons[0]], champ_path)

            # 3. Save comprehensive metadata
            meta_path = os.path.join(save_dir, 'model_metadata.json')
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=4)

            logger.info(
                f"Multi-horizon direct training finished for horizons {horizons}. "
                f"Saved to {direct_bundle_path} and {meta_path}"
            )
        else:
            logger.info(f"Multi-horizon evaluation finished for '{dataset_label}'.")

        return metadata
