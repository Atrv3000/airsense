"""
Leave-One-Station-Out Cross-Validation (LOSOCV) & Spatial Interpolator Evaluation Service.
Benchmarks Inverse Distance Weighting (powers 1, 2, 3), Ordinary Kriging,
and Spatial Gradient Boosting to validate spatial pollution field accuracy across Mumbai.
"""

import math
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import timedelta
from django.utils import timezone
from core.models import MonitoringStation
from aqi_engine.models import AQIRecord
from .idw_interpolator import IDWInterpolator

logger = logging.getLogger(__name__)


class SpatialValidator:
    """
    Coordinates Leave-One-Station-Out Cross-Validation (LOSOCV) for spatial interpolators.
    """

    CANDIDATE_CONFIGS = [
        {"name": "IDW_p1", "label": "Inverse Distance Weighting (p=1)", "method": "idw", "power": 1.0},
        {"name": "IDW_p2", "label": "Inverse Distance Weighting (p=2)", "method": "idw", "power": 2.0},
        {"name": "IDW_p3", "label": "Inverse Distance Weighting (p=3)", "method": "idw", "power": 3.0},
        {"name": "Ordinary_Kriging", "label": "Ordinary Kriging (Gaussian Process Matern)", "method": "kriging", "power": None},
        {"name": "Spatial_GBM", "label": "Spatial Gradient Boosted Regressor", "method": "gbm", "power": None},
    ]

    @classmethod
    def leave_one_station_out_cv(
        cls,
        known_stations: List[Dict[str, Any]],
        method: str = "idw",
        power: float = 2.0
    ) -> Dict[str, Any]:
        """
        Executes Leave-One-Station-Out Cross-Validation for a given spatial configuration.
        Returns RMSE, MAE, Max Error, and per-station residuals.
        """
        n = len(known_stations)
        if n < 3:
            return {
                "method": method,
                "power": power,
                "stations_count": n,
                "stations_evaluated": n,
                "rmse": None,
                "mae": None,
                "max_error": None,
                "mape": None,
                "station_evaluations": [],
                "message": "Insufficient stations for spatial cross-validation (need >= 3)."
            }

        actuals = []
        predictions = []
        residuals = []
        station_evals = []

        for i in range(n):
            test_station = known_stations[i]
            train_stations = known_stations[:i] + known_stations[i+1:]

            target_lat = np.array([test_station['latitude']], dtype=float)
            target_lon = np.array([test_station['longitude']], dtype=float)
            actual_aqi = float(test_station['aqi'])

            if method == "kriging":
                pred_aqi = float(IDWInterpolator.predict_points_kriging(target_lat, target_lon, train_stations)[0])
            elif method == "gbm":
                pred_aqi = float(IDWInterpolator.predict_points_gbm(target_lat, target_lon, train_stations)[0])
            else:
                pred_aqi = float(IDWInterpolator.predict_points_idw(target_lat, target_lon, train_stations, power=power)[0])

            err = pred_aqi - actual_aqi
            abs_err = abs(err)

            actuals.append(actual_aqi)
            predictions.append(pred_aqi)
            residuals.append(err)

            station_evals.append({
                "station_id": test_station.get("station_id", f"station_{i}"),
                "name": test_station.get("name", f"Station {i}"),
                "actual": round(actual_aqi, 1),
                "predicted": round(pred_aqi, 1),
                "residual": round(err, 2),
                "abs_error": round(abs_err, 2),
            })

        actuals_np = np.array(actuals)
        predictions_np = np.array(predictions)
        residuals_np = np.array(residuals)

        rmse = float(np.sqrt(np.mean(residuals_np ** 2)))
        mae = float(np.mean(np.abs(residuals_np)))
        max_error = float(np.max(np.abs(residuals_np)))

        # Mean Absolute Percentage Error (MAPE) where actual > 0
        valid_idx = actuals_np > 0
        mape = float(np.mean(np.abs(residuals_np[valid_idx] / actuals_np[valid_idx])) * 100.0) if valid_idx.any() else 0.0

        return {
            "method": method,
            "power": power,
            "stations_evaluated": n,
            "rmse": round(rmse, 2),
            "mae": round(mae, 2),
            "max_error": round(max_error, 2),
            "mape": round(mape, 2),
            "station_evaluations": station_evals,
        }

    @classmethod
    def compare_interpolators(cls, known_stations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Runs LOSOCV across all candidate spatial interpolators on the given station set
        and identifies the champion with the lowest RMSE.
        """
        results = {}
        for cfg in cls.CANDIDATE_CONFIGS:
            cv_res = cls.leave_one_station_out_cv(
                known_stations,
                method=cfg["method"],
                power=cfg["power"] if cfg["power"] is not None else 2.0
            )
            results[cfg["name"]] = {
                "label": cfg["label"],
                "method": cfg["method"],
                "power": cfg["power"],
                "rmse": cv_res.get("rmse"),
                "mae": cv_res.get("mae"),
                "max_error": cv_res.get("max_error"),
                "mape": cv_res.get("mape"),
            }

        # Identify champion (lowest RMSE among non-null)
        valid_candidates = {k: v for k, v in results.items() if v["rmse"] is not None}
        if valid_candidates:
            champion_name = min(valid_candidates.keys(), key=lambda k: valid_candidates[k]["rmse"])
            champion_info = valid_candidates[champion_name]
        else:
            champion_name = "IDW_p2"
            champion_info = results.get("IDW_p2", {})

        return {
            "stations_count": len(known_stations),
            "comparison": results,
            "champion": {
                "name": champion_name,
                "label": champion_info.get("label"),
                "rmse": champion_info.get("rmse"),
                "mae": champion_info.get("mae"),
            }
        }

    @classmethod
    def run_historical_losocv_benchmark(cls, sample_hours: int = 12) -> Dict[str, Any]:
        """
        Gathers distinct historical hourly timestamps from AQIRecord,
        evaluates LOSOCV across each hour, and computes time-averaged RMSE and MAE.
        """
        # Find distinct recent timestamps with at least 5 station readings
        timestamps = list(
            AQIRecord.objects.filter(overall_aqi__isnull=False)
            .values_list('recorded_at', flat=True)
            .distinct()
            .order_by('-recorded_at')[:sample_hours * 3]
        )

        sampled_hours_data = []
        for t in timestamps:
            records = list(
                AQIRecord.objects.filter(recorded_at=t, overall_aqi__isnull=False)
                .select_related('station')
            )
            if len(records) >= 5:
                stations_data = [{
                    "station_id": r.station.station_id,
                    "name": r.station.name,
                    "latitude": r.station.latitude,
                    "longitude": r.station.longitude,
                    "aqi": r.overall_aqi
                } for r in records]
                sampled_hours_data.append((t, stations_data))
                if len(sampled_hours_data) >= sample_hours:
                    break

        if not sampled_hours_data:
            return {"error": "Insufficient historical AQIRecord readings for multi-hour benchmark."}

        # Accumulate metrics across all sampled hours
        method_rmses: Dict[str, List[float]] = {cfg["name"]: [] for cfg in cls.CANDIDATE_CONFIGS}
        method_maes: Dict[str, List[float]] = {cfg["name"]: [] for cfg in cls.CANDIDATE_CONFIGS}

        for t_stamp, st_list in sampled_hours_data:
            comp = cls.compare_interpolators(st_list)
            for m_name, m_stats in comp["comparison"].items():
                if m_stats["rmse"] is not None:
                    method_rmses[m_name].append(m_stats["rmse"])
                if m_stats["mae"] is not None:
                    method_maes[m_name].append(m_stats["mae"])

        summary = {}
        for cfg in cls.CANDIDATE_CONFIGS:
            name = cfg["name"]
            rmses = method_rmses[name]
            maes = method_maes[name]
            mean_rmse = round(float(np.mean(rmses)), 2) if rmses else None
            std_rmse = round(float(np.std(rmses)), 2) if rmses else None
            mean_mae = round(float(np.mean(maes)), 2) if maes else None
            summary[name] = {
                "label": cfg["label"],
                "mean_rmse": mean_rmse,
                "std_rmse": std_rmse,
                "mean_mae": mean_mae,
                "evaluated_hours": len(rmses)
            }

        valid_summary = {k: v for k, v in summary.items() if v["mean_rmse"] is not None}
        champion_name = min(valid_summary.keys(), key=lambda k: valid_summary[k]["mean_rmse"]) if valid_summary else "IDW_p2"

        return {
            "hours_sampled": len(sampled_hours_data),
            "benchmark_summary": summary,
            "champion": {
                "name": champion_name,
                "label": summary[champion_name]["label"],
                "mean_rmse": summary[champion_name]["mean_rmse"],
                "std_rmse": summary[champion_name]["std_rmse"],
                "mean_mae": summary[champion_name]["mean_mae"],
            }
        }
