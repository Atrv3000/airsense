"""
Spatial Interpolation Engine for Mumbai using Inverse Distance Weighting (IDW).
Applies landmass boundary clipping so interpolated pollution values do not spill
into the Arabian Sea or distant offshore water bodies.
"""

import math
import numpy as np
from typing import List, Dict, Any, Tuple

class IDWInterpolator:
    """
    Computes 2D spatial interpolation across Greater Mumbai using Inverse Distance Weighting.
    Formula:
        Z_hat(x, y) = sum(w_i * Z_i) / sum(w_i)
        where w_i = 1 / (distance(p, p_i) + epsilon)^power
    """

    # Greater Mumbai Bounding Box
    MUMBAI_BOUNDS = {
        'min_lat': 18.89,  # Colaba / South tip
        'max_lat': 19.30,  # Borivali / Dahisar / Mira-Bhayandar border
        'min_lon': 72.78,  # Adjusted landward western coastline
        'max_lon': 73.08   # Eastern border / Navi Mumbai
    }

    # Simplified landmass polygon enclosing the Mumbai urban peninsula, suburbs & Thane creek
    # Expressed as (lat, lon) vertices
    MUMBAI_LAND_POLYGON = [
        (18.8950, 72.8100),  # Colaba Point
        (18.9200, 72.8050),  # Nariman Point / Marine Drive
        (18.9600, 72.7950),  # Malabar Hill
        (18.9900, 72.8100),  # Haji Ali / Worli South
        (19.0300, 72.8150),  # Worli Seaface
        (19.0600, 72.8250),  # Bandra Bandstand
        (19.0900, 72.8200),  # Juhu Beach
        (19.1400, 72.8050),  # Versova / Madh
        (19.1900, 72.7950),  # Marve / Manori
        (19.2500, 72.8000),  # Gorai / Uttan
        (19.3000, 72.8300),  # Bhayandar North
        (19.3000, 72.9900),  # Thane North-East
        (19.2300, 73.0200),  # Kalwa / Diva
        (19.1800, 73.0500),  # Airoli East
        (19.1200, 73.0600),  # Mahape / Turbhe
        (19.0500, 73.0600),  # Vashi / Sanpada East
        (18.9800, 73.0400),  # Seawoods / Belapur
        (18.9300, 72.9800),  # Uran / JNPT
        (18.9000, 72.8500),  # Mumbai Harbour
        (18.8950, 72.8100)   # Close loop
    ]

    @classmethod
    def is_point_on_land(cls, lat: float, lon: float) -> bool:
        """
        Ray-casting algorithm to determine if (lat, lon) is inside Mumbai land polygon.
        """
        poly = cls.MUMBAI_LAND_POLYGON
        inside = False
        n = len(poly)
        p1_lat, p1_lon = poly[0]

        for i in range(1, n):
            p2_lat, p2_lon = poly[i]
            if lon > min(p1_lon, p2_lon):
                if lon <= max(p1_lon, p2_lon):
                    if lat <= max(p1_lat, p2_lat):
                        if p1_lon != p2_lon:
                            lat_inters = (lon - p1_lon) * (p2_lat - p1_lat) / (p2_lon - p1_lon) + p1_lat
                        if p1_lat == p2_lat or lat <= lat_inters:
                            inside = not inside
            p1_lat, p1_lon = p2_lat, p2_lon

        return inside

    @staticmethod
    def haversine_distance_matrix(lats1: np.ndarray, lons1: np.ndarray, lats2: np.ndarray, lons2: np.ndarray) -> np.ndarray:
        """
        Computes great-circle distance matrix (in kilometers) between two sets of coordinates.
        """
        R = 6371.0  # Earth radius in kilometers

        lat1_rad = np.radians(lats1)[:, np.newaxis]
        lon1_rad = np.radians(lons1)[:, np.newaxis]
        lat2_rad = np.radians(lats2)[np.newaxis, :]
        lon2_rad = np.radians(lons2)[np.newaxis, :]

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = np.sin(dlat / 2.0)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2.0)**2
        c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))

        return R * c

    @classmethod
    def generate_mumbai_grid(cls, resolution: int = 25) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Generates a 2D regular grid covering Greater Mumbai.
        """
        b = cls.MUMBAI_BOUNDS
        lat_linspace = np.linspace(b['min_lat'], b['max_lat'], resolution)
        lon_linspace = np.linspace(b['min_lon'], b['max_lon'], resolution)

        lat_step = (b['max_lat'] - b['min_lat']) / (resolution - 1)
        lon_step = (b['max_lon'] - b['min_lon']) / (resolution - 1)

        lon_grid, lat_grid = np.meshgrid(lon_linspace, lat_linspace)
        return lat_grid.flatten(), lon_grid.flatten(), lat_step, lon_step

    @classmethod
    def interpolate_grid(
        cls,
        known_stations: List[Dict[str, Any]],
        resolution: int = 25,
        power: float = 2.0
    ) -> List[Dict[str, Any]]:
        """
        Interpolates AQI across Mumbai landmass using known station coordinates and readings.
        Filters out offshore/sea cells so pollution gradients do not spill into the Arabian Sea.
        """
        if not known_stations:
            return []

        station_lats = np.array([s['latitude'] for s in known_stations], dtype=float)
        station_lons = np.array([s['longitude'] for s in known_stations], dtype=float)
        station_aqis = np.array([s['aqi'] for s in known_stations], dtype=float)

        grid_lats, grid_lons, lat_step, lon_step = cls.generate_mumbai_grid(resolution)

        # Pairwise distance matrix between all grid points (M) and all stations (N)
        dist_matrix = cls.haversine_distance_matrix(grid_lats, grid_lons, station_lats, station_lons)

        # Small epsilon avoids division by zero
        epsilon = 0.01
        weights = 1.0 / (np.power(dist_matrix + epsilon, power))

        # Vectorized IDW
        weights_sum = weights.sum(axis=1)
        interpolated_aqi = np.dot(weights, station_aqis) / weights_sum
        interpolated_aqi = np.round(interpolated_aqi, 1)

        # Also calculate minimum distance to closest station to avoid unbounded offshore extrapolation
        min_dists = dist_matrix.min(axis=1)

        results = []
        half_lat = lat_step / 2.0
        half_lon = lon_step / 2.0

        for i in range(len(grid_lats)):
            lat = round(float(grid_lats[i]), 5)
            lon = round(float(grid_lons[i]), 5)
            aqi = float(interpolated_aqi[i])

            # Offshore filter: Must be within Mumbai land polygon AND within 9km of a monitoring station
            if not cls.is_point_on_land(lat, lon) or min_dists[i] > 9.0:
                continue

            results.append({
                'latitude': lat,
                'longitude': lon,
                'interpolated_aqi': aqi,
                'cell_bounds': [
                    [round(lat - half_lat, 5), round(lon - half_lon, 5)],
                    [round(lat + half_lat, 5), round(lon + half_lon, 5)]
                ]
            })

        return results
