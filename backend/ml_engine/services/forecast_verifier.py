"""
Forecast Verifier & Model Performance Monitoring Service.
Matches past ForecastRecord predictions against ground-truth AQIRecord observations
once target_time has elapsed, stores absolute & signed errors, and computes rolling
performance metrics (MAE, RMSE, bias) per forecast horizon.
"""

import logging
import math
from datetime import timedelta
from typing import Dict, Any, Optional
from django.utils import timezone
from ml_engine.models import ForecastRecord
from aqi_engine.models import AQIRecord

logger = logging.getLogger(__name__)


class ForecastVerifier:
    """
    Coordinates verification of past multi-horizon AQI forecasts and computes
    continuous model monitoring metrics.
    """

    @classmethod
    def verify_past_forecasts(cls, station_id: Optional[str] = None, max_records: Optional[int] = None) -> Dict[str, Any]:
        """
        Scans unverified ForecastRecord rows whose target_time <= current time,
        locates the corresponding actual AQIRecord, and records absolute and signed error.
        """
        now = timezone.now()
        qs = ForecastRecord.objects.filter(is_verified=False, target_time__lte=now).select_related('station')

        if station_id:
            qs = qs.filter(station__station_id=station_id)

        if max_records:
            qs = qs[:max_records]

        records_to_verify = list(qs)
        verified_count = 0
        unmatched_count = 0

        for fr in records_to_verify:
            # Look for matching AQIRecord within ±30 minute tolerance window
            t_min = fr.target_time - timedelta(minutes=30)
            t_max = fr.target_time + timedelta(minutes=30)

            actual_record = AQIRecord.objects.filter(
                station=fr.station,
                recorded_at__gte=t_min,
                recorded_at__lte=t_max,
                overall_aqi__isnull=False
            ).order_by('recorded_at').first()

            if actual_record and actual_record.overall_aqi is not None:
                actual = round(float(actual_record.overall_aqi), 1)
                pred = round(float(fr.predicted_aqi), 1)
                abs_err = round(abs(pred - actual), 2)
                signed_err = round(pred - actual, 2)

                fr.actual_aqi = actual
                fr.absolute_error = abs_err
                fr.signed_error = signed_err
                fr.is_verified = True
                fr.verified_at = now
                fr.save(update_fields=['actual_aqi', 'absolute_error', 'signed_error', 'is_verified', 'verified_at'])
                verified_count += 1
            else:
                unmatched_count += 1

        return {
            "total_candidates": len(records_to_verify),
            "verified_count": verified_count,
            "unmatched_count": unmatched_count,
            "timestamp": now.isoformat()
        }

    @classmethod
    def get_rolling_metrics(cls, days: int = 7, station_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates rolling verification metrics (MAE, RMSE, Bias, and sample count)
        grouped by horizon (+1h, +3h, +6h, +12h, +24h, etc.) over the given window.
        """
        now = timezone.now()
        cutoff = now - timedelta(days=days)

        qs = ForecastRecord.objects.filter(is_verified=True, target_time__gte=cutoff)
        if station_id:
            qs = qs.filter(station__station_id=station_id)

        total_verified = qs.count()
        if total_verified == 0:
            return {
                "window_days": days,
                "start_time": cutoff.isoformat(),
                "end_time": now.isoformat(),
                "total_verified": 0,
                "overall_mae": None,
                "overall_rmse": None,
                "overall_bias": None,
                "horizons": {},
                "message": "No verified forecasts available in the selected window."
            }

        verified_items = list(qs.values('horizon', 'absolute_error', 'signed_error'))
        
        horizon_buckets: Dict[int, list] = {}
        all_abs_errors = []
        all_sq_errors = []
        all_signed_errors = []

        for item in verified_items:
            h = item['horizon']
            ae = item['absolute_error']
            se = item['signed_error']
            if ae is not None and se is not None:
                horizon_buckets.setdefault(h, []).append((ae, se))
                all_abs_errors.append(ae)
                all_sq_errors.append(se ** 2)
                all_signed_errors.append(se)

        horizon_metrics = {}
        for h in sorted(horizon_buckets.keys()):
            pairs = horizon_buckets[h]
            n = len(pairs)
            if n == 0:
                continue
            h_mae = sum(p[0] for p in pairs) / n
            h_rmse = math.sqrt(sum(p[1] ** 2 for p in pairs) / n)
            h_bias = sum(p[1] for p in pairs) / n
            horizon_metrics[str(h)] = {
                "horizon": h,
                "samples": n,
                "mae": round(h_mae, 2),
                "rmse": round(h_rmse, 2),
                "bias": round(h_bias, 2),
            }

        overall_mae = round(sum(all_abs_errors) / len(all_abs_errors), 2) if all_abs_errors else None
        overall_rmse = round(math.sqrt(sum(all_sq_errors) / len(all_sq_errors)), 2) if all_sq_errors else None
        overall_bias = round(sum(all_signed_errors) / len(all_signed_errors), 2) if all_signed_errors else None

        return {
            "window_days": days,
            "start_time": cutoff.isoformat(),
            "end_time": now.isoformat(),
            "total_verified": total_verified,
            "overall_mae": overall_mae,
            "overall_rmse": overall_rmse,
            "overall_bias": overall_bias,
            "horizons": horizon_metrics
        }
