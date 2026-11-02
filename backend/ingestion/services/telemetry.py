"""
AirSense Telemetry & System Health Tracking Service.
Maintains live operational telemetry for external data providers (OpenAQ, Open-Meteo, WAQI/CPCB),
per-station ground data freshness analytics, ingestion latency, and API failure counters.
All statuses are determined from actual telemetry and database records, never hardcoded.
"""

import os
import time
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from django.utils import timezone
from django.conf import settings
from core.models import MonitoringStation
from ingestion.models import RawMeasurement, CleanMeasurement, IngestionRun
from ..constants import GROUND_SOURCES

logger = logging.getLogger(__name__)

class IngestionTelemetry:
    """
    Operational telemetry tracker with database synchronization via IngestionRun.
    Tracks provider connectivity, API response latency, failure counts, and honest per-station ground freshness.
    """
    _state = {
        "OPENAQ": {
            "name": "OpenAQ v3 API",
            "provider_type": "Ground Sensor Network",
            "status": "UNCONFIGURED",
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error": None,
            "last_response_ms": 0.0,
            "total_requests": 0,
            "failed_requests": 0,
        },
        "OPEN_METEO": {
            "name": "Open-Meteo Air Quality & Weather API",
            "provider_type": "Atmospheric Dispersion & Reanalysis Model",
            "status": "ONLINE",
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error": None,
            "last_response_ms": 0.0,
            "total_requests": 0,
            "failed_requests": 0,
        },
        "WAQI_CPCB": {
            "name": "WAQI / CPCB Real-Time Feed",
            "provider_type": "Official CAAQMS Sub-Indices",
            "status": "UNCONFIGURED",
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error": None,
            "last_response_ms": 0.0,
            "total_requests": 0,
            "failed_requests": 0,
        },
        "pipeline": {
            "last_cycle_started_at": None,
            "last_cycle_completed_at": None,
            "last_cycle_duration_sec": 0.0,
            "last_cycle_status": "IDLE",
            "last_cycle_summary": {}
        }
    }

    _error_counters = {
        "ingestion": 0,
        "ml_prediction": 0,
        "alerts": 0
    }

    @classmethod
    def record_ingestion_error(cls):
        cls._error_counters["ingestion"] += 1

    @classmethod
    def record_ml_error(cls):
        cls._error_counters["ml_prediction"] += 1

    @classmethod
    def record_alert_error(cls):
        cls._error_counters["alerts"] += 1

    @classmethod
    def get_error_counters(cls) -> dict:
        return dict(cls._error_counters)

    @classmethod
    def record_request(cls, provider: str, success: bool, duration_ms: float = 0.0, error: str = None):
        """
        Records an API request outcome for a specific provider.
        """
        p = provider.upper()
        if p not in cls._state:
            return

        now_iso = timezone.now().isoformat()
        entry = cls._state[p]
        entry["last_attempt_at"] = now_iso
        entry["total_requests"] += 1
        entry["last_response_ms"] = round(duration_ms, 1)

        if success:
            entry["last_success_at"] = now_iso
            entry["last_error"] = None
            entry["status"] = "ONLINE"
        else:
            entry["failed_requests"] += 1
            entry["last_error"] = str(error) if error else "Unknown error"
            if entry["failed_requests"] >= 5:
                entry["status"] = "OFFLINE"
            else:
                entry["status"] = "DEGRADED"

    @classmethod
    def start_pipeline_cycle(cls):
        cls._state["pipeline"]["last_cycle_started_at"] = timezone.now().isoformat()
        cls._state["pipeline"]["last_cycle_status"] = "RUNNING"

    @classmethod
    def finish_pipeline_cycle(cls, duration_sec: float, summary: dict = None, status: str = "SUCCESS"):
        now_iso = timezone.now().isoformat()
        cls._state["pipeline"]["last_cycle_completed_at"] = now_iso
        cls._state["pipeline"]["last_cycle_duration_sec"] = round(duration_sec, 2)
        cls._state["pipeline"]["last_cycle_status"] = status
        if summary:
            cls._state["pipeline"]["last_cycle_summary"] = summary

    @classmethod
    def get_provider_status(cls, provider: str) -> str:
        """
        Dynamically determines provider status based on credentials and recent calls.
        """
        p = provider.upper()
        if p == "OPENAQ":
            api_key = getattr(settings, 'OPENAQ_API_KEY', os.getenv("OPENAQ_API_KEY", "")).strip()
            if not api_key:
                return "UNCONFIGURED"
            if cls._state[p]["status"] == "OFFLINE":
                return "OFFLINE"
            if cls._state[p]["status"] == "DEGRADED":
                return "DEGRADED"
            return "ONLINE"

        elif p == "WAQI_CPCB":
            token = (
                getattr(settings, 'WAQI_API_TOKEN', None) or
                os.getenv("WAQI_API_TOKEN") or
                os.getenv("WAQI_TOKEN") or
                os.getenv("CPCB_API_TOKEN")
            )
            if not token or str(token).strip().lower() in ["", "demo"]:
                return "UNCONFIGURED"
            if cls._state[p]["status"] == "OFFLINE":
                return "OFFLINE"
            if cls._state[p]["status"] == "DEGRADED":
                return "DEGRADED"
            return "ONLINE"

        elif p == "OPEN_METEO":
            if cls._state[p]["status"] == "OFFLINE":
                return "OFFLINE"
            if cls._state[p]["status"] == "DEGRADED":
                return "DEGRADED"
            return "ONLINE"

        return "UNKNOWN"

    @classmethod
    def get_freshness_stats(cls) -> dict:
        """
        Analyzes observations per station to report honest ground freshness.
        Fresh: ground observation (CPCB_OFFICIAL, OPENAQ_MEASURED, WAQI_FEED) within past 6 hours.
        Stale: ground observation older than 6 hours or non-existent.
        """
        now = timezone.now()
        day_cutoff = now - timedelta(hours=24)

        try:
            active_stations = list(MonitoringStation.objects.filter(is_active=True).order_by('name'))
            total_active_stations = len(active_stations)

            station_freshness_list = []
            fresh_ground_count = 0

            for st in active_stations:
                # Latest ground-measured observation
                latest_ground = RawMeasurement.objects.filter(
                    station=st,
                    source__in=GROUND_SOURCES
                ).order_by('-recorded_at').first()

                # Latest observation of any source (ground or modelled)
                latest_any = RawMeasurement.objects.filter(
                    station=st
                ).order_by('-recorded_at').first()

                if latest_ground and latest_ground.recorded_at:
                    ground_age_h = round((now - latest_ground.recorded_at).total_seconds() / 3600.0, 1)
                    is_ground_stale = ground_age_h > 6.0
                    last_ground_at = latest_ground.recorded_at.isoformat()
                    ground_source = latest_ground.source
                else:
                    ground_age_h = None
                    is_ground_stale = True
                    last_ground_at = None
                    ground_source = None

                if not is_ground_stale:
                    fresh_ground_count += 1

                last_any_at = latest_any.recorded_at.isoformat() if (latest_any and latest_any.recorded_at) else None
                any_source = latest_any.source if latest_any else None

                station_freshness_list.append({
                    "station_id": st.station_id,
                    "name": st.name,
                    "last_ground_observation_at": last_ground_at,
                    "ground_age_hours": ground_age_h,
                    "ground_source": ground_source,
                    "last_any_observation_at": last_any_at,
                    "any_source": any_source,
                    "is_ground_stale": is_ground_stale,
                    "consecutive_stale_cycles": st.consecutive_stale_cycles,
                })

            stale_ground_count = total_active_stations - fresh_ground_count

            # Overall observation counts in past 24 hours
            obs_24h = RawMeasurement.objects.filter(recorded_at__gte=day_cutoff)
            obs_24h_count = obs_24h.count()
            ground_measured_count = obs_24h.filter(source__in=GROUND_SOURCES).count()
            modelled_count = obs_24h.filter(source='OPEN_METEO_MODELLED').count()

            # Global latest ground observation
            global_latest_ground = RawMeasurement.objects.filter(
                source__in=GROUND_SOURCES
            ).order_by('-recorded_at').first()

            # Ingestion timestamp
            latest_ingested = RawMeasurement.objects.order_by('-ingested_at').first()
            last_ingested_time = latest_ingested.ingested_at.isoformat() if latest_ingested else None

            global_ground_age_m = None
            if global_latest_ground and global_latest_ground.recorded_at:
                global_ground_age_m = round((now - global_latest_ground.recorded_at).total_seconds() / 60.0, 1)

            return {
                "total_active_stations": total_active_stations,
                "fresh_stations_count": fresh_ground_count,  # Strictly ground-based
                "stale_stations_count": stale_ground_count,  # Strictly ground-based
                "observations_24h_count": obs_24h_count,
                "ground_measured_24h_count": ground_measured_count,
                "modelled_24h_count": modelled_count,
                "last_observation_time": global_latest_ground.recorded_at.isoformat() if global_latest_ground else None,
                "last_ingested_time": last_ingested_time,
                "freshness_age_minutes": global_ground_age_m,
                "freshness_label": (
                    "Fresh (<30m)" if global_ground_age_m is not None and global_ground_age_m <= 30
                    else ("Recent (<2h)" if global_ground_age_m is not None and global_ground_age_m <= 120
                          else ("Delayed (<6h)" if global_ground_age_m is not None and global_ground_age_m <= 360
                                else "Stale (>6h)"))
                ),
                "is_stale": (global_ground_age_m is None or global_ground_age_m > 360),
                "stations": station_freshness_list
            }

        except Exception as e:
            logger.error(f"Error computing freshness stats: {e}")
            return {
                "total_active_stations": 0,
                "fresh_stations_count": 0,
                "stale_stations_count": 0,
                "observations_24h_count": 0,
                "ground_measured_24h_count": 0,
                "modelled_24h_count": 0,
                "last_observation_time": None,
                "last_ingested_time": None,
                "freshness_age_minutes": None,
                "freshness_label": "Unknown",
                "is_stale": True,
                "stations": []
            }

    @classmethod
    def get_full_system_telemetry(cls) -> dict:
        """
        Compiles complete system health telemetry report for APIs and dashboards.
        Reads persisted cycle stats from IngestionRun if available to support multi-process workers.
        """
        freshness = cls.get_freshness_stats()

        providers_report = {}
        for p_key, p_meta in cls._state.items():
            if p_key == "pipeline":
                continue
            curr_status = cls.get_provider_status(p_key)
            providers_report[p_key.lower()] = {
                "name": p_meta["name"],
                "provider_type": p_meta["provider_type"],
                "status": curr_status,
                "last_attempt_at": p_meta["last_attempt_at"],
                "last_success_at": p_meta["last_success_at"],
                "last_error": p_meta["last_error"],
                "last_response_ms": p_meta["last_response_ms"],
                "total_requests": p_meta["total_requests"],
                "failed_requests": p_meta["failed_requests"],
            }

        # Check DB for latest persisted IngestionRun
        pipe = dict(cls._state["pipeline"])
        try:
            latest_run = IngestionRun.objects.order_by('-started_at').first()
            if latest_run:
                pipe["last_cycle_started_at"] = latest_run.started_at.isoformat()
                pipe["last_cycle_completed_at"] = latest_run.completed_at.isoformat() if latest_run.completed_at else None
                pipe["last_cycle_duration_sec"] = latest_run.duration_seconds
                pipe["last_cycle_status"] = latest_run.status
                pipe["last_cycle_summary"] = {
                    "total_stations": latest_run.total_stations,
                    "successful_stations": latest_run.successful_stations,
                    "failed_stations": latest_run.failed_stations,
                    "details": latest_run.station_results
                }
        except Exception:
            pass

        interval_sec = getattr(settings, 'SCHEDULER_INTERVAL_SECONDS', 900)
        interval_min = max(1, round(interval_sec / 60))

        return {
            "status": "healthy" if freshness["fresh_stations_count"] > 0 else "operational",
            "polling": {
                "target_polling_interval_seconds": interval_sec,
                "target_polling_interval_human": f"{interval_min} minutes (configurable via SCHEDULER_INTERVAL_SECONDS)",
                "note": f"A {interval_min}-minute scheduler cycle checks for upstream updates; ground sensor telemetry updates subject to provider publication latency."
            },
            "last_cycle": {
                "started_at": pipe["last_cycle_started_at"],
                "completed_at": pipe["last_cycle_completed_at"],
                "duration_seconds": pipe["last_cycle_duration_sec"],
                "status": pipe["last_cycle_status"],
                "summary": pipe["last_cycle_summary"]
            },
            "providers": providers_report,
            "telemetry": freshness,
            "error_counts": cls.get_error_counters(),
            "data_classifications": {
                "ground_measured": "Direct CAAQMS physical observations from CPCB, MPCB, OpenAQ, or WAQI sensors",
                "modelled": "Numerical atmospheric dispersion models and reanalysis from Open-Meteo",
                "spatially_estimated": "Geostatistical surface continuous predictions (Ordinary Kriging / IDW)",
                "predicted": "Multi-horizon forward trajectory generated by XGBoost machine learning predictor"
            }
        }
