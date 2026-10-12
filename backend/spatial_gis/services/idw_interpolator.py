"""
Spatial Interpolation Engine for Mumbai using Inverse Distance Weighting (IDW).
Reference: Tobler's First Law of Geography ("Near things are more related than distant things").
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
        'min_lon': 72.75,  # Western coast
        'max_lon': 73.10   # Eastern border / Navi Mumbai
    }

    @staticmethod
    def haversine_distance_matrix(lats1: np.ndarray, lons1: np.ndarray, lats2: np.ndarray, lons2: np.ndarray) -> np.ndarray:
        """
        Computes great-circle distance matrix (in kilometers) between two sets of coordinates.
        lats1, lons1: shape (M,)
        lats2, lons2: shape (N,)
        Returns: shape (M, N) matrix of pairwise distances in km.
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
        Returns (lats_flat, lons_flat, lat_step, lon_step)
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
        Interpolates AQI across the Mumbai grid using known station coordinates and readings.
        known_stations format:
            [{'latitude': 19.0657, 'longitude': 72.8687, 'aqi': 210.5}, ...]

        Returns a list of interpolated points:
            [{'latitude': ..., 'longitude': ..., 'interpolated_aqi': ...}, ...]
        """
        if not known_stations:
            return []

        station_lats = np.array([s['latitude'] for s in known_stations], dtype=float)
        station_lons = np.array([s['longitude'] for s in known_stations], dtype=float)
        station_aqis = np.array([s['aqi'] for s in known_stations], dtype=float)

        grid_lats, grid_lons, lat_step, lon_step = cls.generate_mumbai_grid(resolution)

        # Pairwise distance matrix between all grid points (M) and all stations (N)
        dist_matrix = cls.haversine_distance_matrix(grid_lats, grid_lons, station_lats, station_lons)

        # Avoid division by zero with small epsilon (0.01 km = 10 meters)
        epsilon = 0.01
        weights = 1.0 / (np.power(dist_matrix + epsilon, power))

        # Vectorized IDW: (weights @ station_aqis) / weights.sum(axis=1)
        weights_sum = weights.sum(axis=1)
        interpolated_aqi = np.dot(weights, station_aqis) / weights_sum
        interpolated_aqi = np.round(interpolated_aqi, 1)

        results = []
        half_lat = lat_step / 2.0
        half_lon = lon_step / 2.0

        for i in range(len(grid_lats)):
            lat = round(float(grid_lats[i]), 5)
            lon = round(float(grid_lons[i]), 5)
            aqi = float(interpolated_aqi[i])

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
