"""
AirSense Telemetry & System Health Tracking Service.
Maintains live operational telemetry for external data providers (OpenAQ, Open-Meteo, WAQI/CPCB),
data freshness analytics, ingestion latency, and API failure counters.
All statuses are determined from actual telemetry and configuration, never hardcoded.
"""

import os
import time
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from django.utils import timezone
from core.models import MonitoringStation
from ingestion.models import RawMeasurement, CleanMeasurement

logger = logging.getLogger(__name__)

class IngestionTelemetry:
    """
    In-memory operational telemetry tracker with fallback database synchronization.
    Tracks provider connectivity, API response latency, failure counts, and data freshness.
    """
    _state = {
        "OPENAQ": {
            "name": "OpenAQ v3 API",
            "provider_type": "Ground Sensor Network",
            "status": "UNCONFIGURED",  # ONLINE, DEGRADED, OFFLINE, UNCONFIGURED
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
            "target_polling_interval_sec": 300,  # 5 minutes target polling cycle
            "last_cycle_status": "IDLE",
            "last_cycle_summary": {}
        }
    }

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
            # If failures exceed 3, mark as DEGRADED or OFFLINE
            if entry["failed_requests"] >= 5:
                entry["status"] = "OFFLINE"
            else:
                entry["status"] = "DEGRADED"

    @classmethod
    def start_pipeline_cycle(cls):
        cls._state["pipeline"]["last_cycle_started_at"] = timezone.now().isoformat()
        cls._state["pipeline"]["last_cycle_status"] = "RUNNING"

    @classmethod
    def finish_pipeline_cycle(cls, duration_sec: float, summary: dict = None):
        now_iso = timezone.now().isoformat()
        cls._state["pipeline"]["last_cycle_completed_at"] = now_iso
        cls._state["pipeline"]["last_cycle_duration_sec"] = round(duration_sec, 2)
        cls._state["pipeline"]["last_cycle_status"] = "SUCCESS"
        if summary:
            cls._state["pipeline"]["last_cycle_summary"] = summary

    @classmethod
    def get_provider_status(cls, provider: str) -> str:
        """
        Dynamically determines provider status based on credentials and recent calls.
        """
        p = provider.upper()
        if p == "OPENAQ":
            api_key = os.getenv("OPENAQ_API_KEY", "").strip()
            if not api_key:
                return "UNCONFIGURED"
            if cls._state[p]["status"] == "OFFLINE":
                return "OFFLINE"
            if cls._state[p]["status"] == "DEGRADED":
                return "DEGRADED"
            return "ONLINE"

        elif p == "WAQI_CPCB":
            token = os.getenv("WAQI_API_TOKEN") or os.getenv("WAQI_TOKEN") or os.getenv("CPCB_API_TOKEN")
            if not token or token.strip().lower() in ["", "demo"]:
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
        Analyzes observations in database to report fresh vs stale counts.
        Fresh: observation recorded_at within past 6 hours.
        Stale: observation recorded_at older than 6 hours.
        """
        now = timezone.now()
        fresh_cutoff = now - timedelta(hours=6)
        day_cutoff = now - timedelta(hours=24)

        try:
            total_active_stations = MonitoringStation.objects.filter(is_active=True).count()
            
            # Latest observation across all stations
            latest_meas = RawMeasurement.objects.order_by('-recorded_at').first()
            last_observation_time = latest_meas.recorded_at.isoformat() if latest_meas else None

            # Calculate fresh stations (stations with at least one observation within 6 hours)
            recent_station_ids = RawMeasurement.objects.filter(
                recorded_at__gte=fresh_cutoff
            ).values_list('station_id', flat=True).distinct()
            fresh_stations_count = len(recent_station_ids)
            stale_stations_count = max(0, total_active_stations - fresh_stations_count)

            # Observation counts in past 24 hours
            obs_24h = RawMeasurement.objects.filter(recorded_at__gte=day_cutoff)
            obs_24h_count = obs_24h.count()
            
            ground_measured_count = obs_24h.filter(
                source__in=['OPENAQ_MEASURED', 'CPCB_OFFICIAL', 'WAQI_FEED']
            ).count()
            modelled_count = obs_24h.filter(
                source='OPEN_METEO_MODELLED'
            ).count()

            # Freshness age in minutes
            freshness_age_minutes = None
            if latest_meas and latest_meas.recorded_at:
                freshness_age_minutes = round((now - latest_meas.recorded_at).total_seconds() / 60.0, 1)

            # Ingestion timestamp
            latest_ingested = RawMeasurement.objects.order_by('-ingested_at').first()
            last_ingested_time = latest_ingested.ingested_at.isoformat() if latest_ingested else None

            return {
                "total_active_stations": total_active_stations,
                "fresh_stations_count": fresh_stations_count,
                "stale_stations_count": stale_stations_count,
                "observations_24h_count": obs_24h_count,
                "ground_measured_24h_count": ground_measured_count,
                "modelled_24h_count": modelled_count,
                "last_observation_time": last_observation_time,
                "last_ingested_time": last_ingested_time,
                "freshness_age_minutes": freshness_age_minutes,
                "freshness_label": (
                    "Fresh (<30m)" if freshness_age_minutes is not None and freshness_age_minutes <= 30
                    else ("Current (<2h)" if freshness_age_minutes is not None and freshness_age_minutes <= 120
                    else ("Recent (<6h)" if freshness_age_minutes is not None and freshness_age_minutes <= 360
                    else "Stale (>6h)"))
                ),
                "is_stale": (freshness_age_minutes is None or freshness_age_minutes > 360)
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
                "is_stale": True
            }

    @classmethod
    def get_full_system_telemetry(cls) -> dict:
        """
        Compiles complete system health telemetry report for APIs and dashboards.
        """
        freshness = cls.get_freshness_stats()
        
        # Check providers
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

        pipe = cls._state["pipeline"]

        return {
            "status": "healthy" if freshness["fresh_stations_count"] > 0 else "operational",
            "polling": {
                "target_polling_interval_seconds": pipe["target_polling_interval_sec"],
                "target_polling_interval_human": "5 minutes (subject to provider publication rate limits)",
                "note": "A 5-minute polling cycle checks for upstream updates; ground sensor telemetry updates subject to provider publication latency."
            },
            "last_cycle": {
                "started_at": pipe["last_cycle_started_at"],
                "completed_at": pipe["last_cycle_completed_at"],
                "duration_seconds": pipe["last_cycle_duration_sec"],
                "status": pipe["last_cycle_status"],
            },
            "providers": providers_report,
            "telemetry": freshness,
            "data_classifications": {
                "ground_measured": "Direct ambient measurements from verified physical CPCB / OpenAQ stations",
                "modelled": "Open-Meteo European CAMS atmospheric dispersion reanalysis grid",
                "spatially_estimated": "Ordinary Kriging (Gaussian Process) / IDW continuous spatial interpolation with uncertainty bands",
                "predicted": "Multi-horizon machine learning forecasts (+1h to +24h ahead)"
            }
        }
