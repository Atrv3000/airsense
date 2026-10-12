"""
Consolidated Spatial Map Layer Service for AirSense.
Builds unified GeoJSON collections of Stations (with live AQI and forecasts)
and Hotspots (IDW polygons and points).
"""

from typing import Dict, Any, List
from core.models import MonitoringStation
from aqi_engine.models import AQIRecord
from aqi_engine.services.cpcb_calculator import CPCBCalculator, CATEGORY_CONFIG
from ml_engine.services.predictor import AQIPredictor
from .hotspot_detector import HotspotDetector

class MapLayerService:
    """
    Consolidates station points, prediction trajectories, and hotspot layers
    into a unified spatial payload for mobile maps and web GIS clients.
    """

    MUMBAI_MAP_CONFIG = {
        "center": [19.0760, 72.8777],  # Mumbai geographic center
        "default_zoom": 11,
        "bounds": [
            [18.89, 72.75],  # Southwest corner
            [19.30, 73.10]   # Northeast corner
        ]
    }

    @classmethod
    def get_unified_map_layers(cls, hotspot_threshold: float = 200.0) -> Dict[str, Any]:
        """
        Returns consolidated layers:
        - station_features: GeoJSON of all 10 stations with current AQI and 24h predictions
        - hotspot_features: GeoJSON of IDW interpolated hotspot cells
        - map_config: Center, bounds, and initial zoom
        - legend: Official CPCB category colors and bounds
        """
        active_stations = MonitoringStation.objects.filter(is_active=True)
        station_features = []
        known_stations_for_idw = []

        for station in active_stations:
            latest_aqi = AQIRecord.objects.filter(
                station=station
            ).select_related('station', 'raw_measurement').order_by('-recorded_at').first()

            if not latest_aqi:
                continue

            current_aqi = latest_aqi.overall_aqi or 100.0
            known_stations_for_idw.append({
                'station_id': station.station_id,
                'name': station.name,
                'latitude': station.latitude,
                'longitude': station.longitude,
                'aqi': current_aqi
            })

            # Fetch 24-hour forecast for this station
            forecast_summary = []
            try:
                forecast_res = AQIPredictor.forecast_station_aqi(station.station_id, horizon_hours=24)
                forecast_summary = forecast_res.get('forecasts', [])
            except Exception:
                forecast_summary = []

            raw = latest_aqi.raw_measurement
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [station.longitude, station.latitude]  # [lon, lat]
                },
                "properties": {
                    "layer": "station",
                    "station_id": station.station_id,
                    "name": station.name,
                    "zone_type": station.zone_type,
                    "recorded_at": latest_aqi.recorded_at.isoformat(),
                    # Air Quality Metrics
                    "current_aqi": current_aqi,
                    "prominent_pollutant": latest_aqi.prominent_pollutant,
                    "category": latest_aqi.aqi_category,
                    "color_hex": latest_aqi.color_hex,
                    # Raw Concentrations
                    "pm25": raw.pm25,
                    "pm10": raw.pm10,
                    "no2": raw.no2,
                    "so2": raw.so2,
                    "co": raw.co,
                    "o3": raw.o3,
                    # Meteorological
                    "temperature": raw.temperature,
                    "humidity": raw.humidity,
                    "wind_speed": raw.wind_speed,
                    "wind_direction": raw.wind_direction,
                    # Forecast Trajectory
                    "forecast_24h": forecast_summary
                }
            }
            station_features.append(feature)

        # Generate Hotspots using IDW on current station readings
        hotspot_geojson = HotspotDetector.detect_hotspots(
            known_stations=known_stations_for_idw,
            threshold=hotspot_threshold,
            resolution=22
        )

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
            "hotspots_geojson": hotspot_geojson
        }
