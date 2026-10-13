"""
Hotspot Detection & GeoJSON Generation Service for Mumbai Region.
Classifies spatial grid cells based on universal HOTSPOT_THRESHOLD (AQI >= 201).
"""

from typing import List, Dict, Any
from aqi_engine.services.cpcb_calculator import CPCBCalculator
from ..constants import HOTSPOT_THRESHOLD
from .idw_interpolator import IDWInterpolator

class HotspotDetector:
    """
    Detects, filters, and formats pollution hotspots across Mumbai into GeoJSON layers.
    """

    @classmethod
    def detect_hotspots(
        cls,
        known_stations: List[Dict[str, Any]],
        threshold: float = HOTSPOT_THRESHOLD,
        resolution: int = 25
    ) -> Dict[str, Any]:
        """
        Runs IDW spatial interpolation and filters cells exceeding the hotspot threshold.
        Returns GeoJSON FeatureCollection.
        """
        grid_points = IDWInterpolator.interpolate_grid(known_stations, resolution=resolution, power=2.0)

        features = []
        hotspots_count = 0
        max_aqi = 0.0
        hottest_point = None

        for pt in grid_points:
            aqi = pt['interpolated_aqi']
            category, color = CPCBCalculator.get_category_and_color(aqi)
            is_hotspot = aqi >= threshold

            if is_hotspot:
                hotspots_count += 1
                if aqi > max_aqi:
                    max_aqi = aqi
                    hottest_point = pt

                # 1. Point Feature (for map markers/pins)
                point_feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [pt['longitude'], pt['latitude']]  # GeoJSON: [lon, lat]
                    },
                    "properties": {
                        "type": "hotspot_point",
                        "interpolated_aqi": aqi,
                        "category": category,
                        "color_hex": color,
                        "severity": "CRITICAL" if aqi >= 301 else "WARNING",
                        "is_hotspot": True
                    }
                }
                features.append(point_feature)

                # 2. Polygon Box Feature (for map heatmap/polygon overlay)
                b = pt['cell_bounds']
                min_lat, min_lon = b[0]
                max_lat, max_lon = b[1]

                polygon_coords = [
                    [
                        [min_lon, min_lat],
                        [max_lon, min_lat],
                        [max_lon, max_lat],
                        [min_lon, max_lat],
                        [min_lon, min_lat]
                    ]
                ]

                polygon_feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": polygon_coords
                    },
                    "properties": {
                        "type": "hotspot_polygon",
                        "interpolated_aqi": aqi,
                        "category": category,
                        "color_hex": color,
                        "fill_opacity": 0.35 if aqi >= 301 else 0.22,
                        "stroke_color": color
                    }
                }
                features.append(polygon_feature)

        geojson_payload = {
            "type": "FeatureCollection",
            "metadata": {
                "region": "Greater Mumbai",
                "threshold_applied": threshold,
                "grid_resolution": f"{resolution}x{resolution}",
                "total_grid_cells": len(grid_points),
                "hotspot_cells_count": hotspots_count,
                "peak_hotspot_aqi": round(max_aqi, 1) if max_aqi > 0 else None,
                "peak_location": {
                    "latitude": hottest_point['latitude'] if hottest_point else None,
                    "longitude": hottest_point['longitude'] if hottest_point else None,
                } if hottest_point else None
            },
            "features": features
        }

        return geojson_payload

    @classmethod
    def get_full_interpolated_grid_geojson(
        cls,
        known_stations: List[Dict[str, Any]],
        resolution: int = 25
    ) -> Dict[str, Any]:
        """
        Emits the continuous Mumbai land grid as a GeoJSON FeatureCollection.
        """
        grid_points = IDWInterpolator.interpolate_grid(known_stations, resolution=resolution, power=2.0)
        features = []

        for pt in grid_points:
            aqi = pt['interpolated_aqi']
            category, color = CPCBCalculator.get_category_and_color(aqi)

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [pt['longitude'], pt['latitude']]
                },
                "properties": {
                    "interpolated_aqi": aqi,
                    "category": category,
                    "color_hex": color,
                    "is_hotspot": aqi >= HOTSPOT_THRESHOLD
                }
            })

        return {
            "type": "FeatureCollection",
            "metadata": {
                "total_points": len(grid_points),
                "resolution": f"{resolution}x{resolution}"
            },
            "features": features
        }
