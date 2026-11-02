"""
Consolidated Spatial Map Layer Service for AirSense.
Builds unified GeoJSON collections of Stations (labelled measured vs modelled)
and Hotspots for Current AQI as well as Predicted AQI at +3h, +6h, +24h.
"""

from typing import Dict, Any, List
from core.models import MonitoringStation
from aqi_engine.models import AQIRecord
from aqi_engine.services.cpcb_calculator import CPCBCalculator, CATEGORY_CONFIG
from ml_engine.models import ForecastRecord
from ml_engine.services.predictor import AQIPredictor
from ..constants import HOTSPOT_THRESHOLD
from .hotspot_detector import HotspotDetector

class MapLayerService:
    """
    Consolidates station points, prediction trajectories, and multi-horizon hotspot layers
    into a unified spatial payload for mobile maps and web GIS clients.
    """

    MUMBAI_MAP_CONFIG = {
        "center": [19.0760, 72.8777],
        "default_zoom": 11,
        "bounds": [
            [18.89, 72.75],
            [19.30, 73.10]
        ],
        "hotspot_threshold": HOTSPOT_THRESHOLD
    }

    @classmethod
    def get_unified_map_layers(cls, hotspot_threshold: float = HOTSPOT_THRESHOLD) -> Dict[str, Any]:
        """
        Returns consolidated layers:
        - station_features: GeoJSON of all active stations, with source (OPENAQ_MEASURED vs OPEN_METEO_MODELLED)
        - hotspot_features: Current AQI hotspots
        - predicted_hotspots: Hotspots computed at +3h, +6h, and +24h from ForecastRecord
        - map_config & legend
        """
        active_stations = MonitoringStation.objects.filter(is_active=True)
        station_features = []
        known_stations_current = []

        # Dictionaries for horizon forecast interpolation: {horizon_int: [ {station_id, lat, lon, aqi} ]}
        horizon_stations = {3: [], 6: [], 24: []}

        for station in active_stations:
            latest_aqi = AQIRecord.objects.filter(
                station=station
            ).select_related('station', 'raw_measurement').order_by('-recorded_at').first()

            if not latest_aqi or latest_aqi.overall_aqi is None:
                station_features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [station.longitude, station.latitude]
                    },
                    "properties": {
                        "layer": "station",
                        "station_id": station.station_id,
                        "name": station.name,
                        "zone_type": station.zone_type,
                        "recorded_at": None,
                        "source": getattr(station, 'source', 'CAAQMS_STATION'),
                        "is_measured": False,
                        "data_classification": "Ground measured",
                        "source_label": "Monitoring Station (Current Reading Unavailable)",
                        "current_aqi": None,
                        "reading_available": False,
                        "prominent_pollutant": None,
                        "category": "Unavailable",
                        "color_hex": "#64748b",
                        "valid_criteria_met": False,
                        "is_instantaneous_fallback": False,
                        "pm25": None,
                        "pm10": None,
                        "no2": None,
                        "so2": None,
                        "co": None,
                        "o3": None,
                        "temperature": None,
                        "humidity": None,
                        "wind_speed": None,
                        "wind_direction": None,
                        "forecast_24h": []
                    }
                })
                continue

            current_aqi = latest_aqi.overall_aqi
            raw = latest_aqi.raw_measurement
            source_tag = raw.source if raw else "OPEN_METEO_MODELLED"
            is_measured = (source_tag in ["OPENAQ_MEASURED", "CPCB_OFFICIAL", "WAQI_FEED"])

            # CPCB Rule: only records meeting valid criteria (min 3 pollutants, one PM) drive spatial hotspots
            if latest_aqi.valid_criteria_met:
                known_stations_current.append({
                    'station_id': station.station_id,
                    'name': station.name,
                    'latitude': station.latitude,
                    'longitude': station.longitude,
                    'aqi': current_aqi
                })

            # Fetch forecasts from precomputed ForecastRecord or predictor fallback
            forecast_summary = []
            latest_f = ForecastRecord.objects.filter(station=station).order_by('-made_at').first()
            f_records = ForecastRecord.objects.filter(station=station, made_at=latest_f.made_at).order_by('horizon')[:24] if latest_f else ForecastRecord.objects.none()

            if f_records.exists():
                for fr in f_records:
                    forecast_summary.append({
                        "step_ahead_hours": fr.horizon,
                        "target_timestamp": fr.target_time.isoformat(),
                        "predicted_aqi": fr.predicted_aqi,
                        "expected_error_band": fr.expected_error_band,
                        "category": fr.category,
                        "color_hex": fr.color_hex
                    })
                    if fr.horizon in horizon_stations:
                        horizon_stations[fr.horizon].append({
                            'station_id': station.station_id,
                            'name': station.name,
                            'latitude': station.latitude,
                            'longitude': station.longitude,
                            'aqi': fr.predicted_aqi
                        })
            else:
                try:
                    forecast_res = AQIPredictor.forecast_station_aqi(station.station_id, horizon_hours=24)
                    forecast_summary = forecast_res.get('forecasts', [])
                    for fc in forecast_summary:
                        h = fc["step_ahead_hours"]
                        if h in horizon_stations:
                            horizon_stations[h].append({
                                'station_id': station.station_id,
                                'name': station.name,
                                'latitude': station.latitude,
                                'longitude': station.longitude,
                                'aqi': fc["predicted_aqi"]
                            })
                except Exception:
                    forecast_summary = []

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [station.longitude, station.latitude]
                },
                "properties": {
                    "layer": "station",
                    "station_id": station.station_id,
                    "name": station.name,
                    "zone_type": station.zone_type,
                    "recorded_at": latest_aqi.recorded_at.isoformat(),
                    "source": source_tag,
                    "is_measured": is_measured,
                    "data_classification": "Ground measured" if is_measured else "Modelled",
                    "source_label": (
                        "Official CPCB CAAQMS (Ground Measured)" if source_tag == "CPCB_OFFICIAL"
                        else ("OpenAQ Ground Sensor (Measured)" if source_tag == "OPENAQ_MEASURED"
                              else ("WAQI Feed (Sub-indices)" if source_tag == "WAQI_FEED"
                                    else "Open-Meteo Model (Modelled)"))
                    ),
                    # Air Quality Metrics
                    "current_aqi": current_aqi,
                    "prominent_pollutant": latest_aqi.prominent_pollutant,
                    "category": latest_aqi.aqi_category,
                    "color_hex": latest_aqi.color_hex,
                    "valid_criteria_met": latest_aqi.valid_criteria_met,
                    "is_instantaneous_fallback": latest_aqi.is_instantaneous_fallback,
                    # Raw Concentrations
                    "pm25": raw.pm25 if raw else None,
                    "pm10": raw.pm10 if raw else None,
                    "no2": raw.no2 if raw else None,
                    "so2": raw.so2 if raw else None,
                    "co": raw.co if raw else None,
                    "o3": raw.o3 if raw else None,
                    # Meteorological
                    "temperature": raw.temperature if raw else None,
                    "humidity": raw.humidity if raw else None,
                    "wind_speed": raw.wind_speed if raw else None,
                    "wind_direction": raw.wind_direction if raw else None,
                    # Forecast Trajectory
                    "forecast_24h": forecast_summary
                }
            }
            station_features.append(feature)

        # 1. Hotspots for Current AQI
        current_hotspots = HotspotDetector.detect_hotspots(
            known_stations=known_stations_current,
            threshold=hotspot_threshold,
            resolution=22
        )

        # 2. Predicted Hotspots for +3h, +6h, +24h
        predicted_hotspots = {}
        for h in [3, 6, 24]:
            h_stations = horizon_stations.get(h, [])
            if h_stations:
                predicted_hotspots[f"plus_{h}h"] = HotspotDetector.detect_hotspots(
                    known_stations=h_stations,
                    threshold=hotspot_threshold,
                    resolution=22
                )
            else:
                predicted_hotspots[f"plus_{h}h"] = {"type": "FeatureCollection", "features": []}

        # Full interpolated spatial grids for continuous gradient rendering
        grid_geojson = HotspotDetector.get_full_interpolated_grid_geojson(
            known_stations=known_stations_current,
            resolution=20
        ) if known_stations_current else {"type": "FeatureCollection", "features": []}

        predicted_grids = {}
        for h in [3, 6, 24]:
            h_stations = horizon_stations.get(h, [])
            if h_stations:
                predicted_grids[f"plus_{h}h"] = HotspotDetector.get_full_interpolated_grid_geojson(
                    known_stations=h_stations,
                    resolution=20
                )
            else:
                predicted_grids[f"plus_{h}h"] = {"type": "FeatureCollection", "features": []}

        # Build CPCB Legend metadata
        legend = []
        for min_v, max_v, name, color in CATEGORY_CONFIG:
            legend.append({
                "range": f"{min_v} - {max_v}",
                "min": min_v,
                "max": max_v,
                "category": name,
                "color_hex": color
            })

        return {
            "map_config": cls.MUMBAI_MAP_CONFIG,
            "legend": legend,
            "stations_geojson": {
                "type": "FeatureCollection",
                "total_stations": len(station_features),
                "features": station_features
            },
            "hotspots_geojson": current_hotspots,
            "predicted_hotspots": predicted_hotspots,
            "grid_geojson": grid_geojson,
            "predicted_grids": predicted_grids
        }
