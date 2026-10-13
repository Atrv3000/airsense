from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
import numpy as np
from datetime import datetime
from zoneinfo import ZoneInfo
from core.models import MonitoringStation
from ingestion.models import RawMeasurement
from aqi_engine.models import AQIRecord
from aqi_engine.services.aqi_service import AQIService
from spatial_gis.constants import HOTSPOT_THRESHOLD
from spatial_gis.services.idw_interpolator import IDWInterpolator
from spatial_gis.services.hotspot_detector import HotspotDetector

class SpatialGISIDWTestCase(TestCase):
    def test_haversine_distance_calculation(self):
        # BKC to Colaba: ~18.5 km
        lats1 = np.array([19.0657])
        lons1 = np.array([72.8687])
        lats2 = np.array([18.9067])
        lons2 = np.array([72.8147])

        dist = IDWInterpolator.haversine_distance_matrix(lats1, lons1, lats2, lons2)
        self.assertEqual(dist.shape, (1, 1))
        self.assertTrue(17.0 <= dist[0, 0] <= 20.0)

        # Distance to self must be 0
        self_dist = IDWInterpolator.haversine_distance_matrix(lats1, lons1, lats1, lons1)
        self.assertAlmostEqual(self_dist[0, 0], 0.0, places=4)

    def test_mumbai_grid_bounds(self):
        lats, lons, lat_step, lon_step = IDWInterpolator.generate_mumbai_grid(resolution=15)
        self.assertEqual(len(lats), 15 * 15)
        self.assertEqual(len(lons), 15 * 15)
        self.assertGreaterEqual(lats.min(), 18.89)
        self.assertLessEqual(lats.max(), 19.30)
        self.assertGreaterEqual(lons.min(), 72.75)
        self.assertLessEqual(lons.max(), 73.10)

    def test_idw_constant_field_identity(self):
        dummy_stations = [
            {'latitude': 19.0657, 'longitude': 72.8687, 'aqi': 150.0},
            {'latitude': 18.9067, 'longitude': 72.8147, 'aqi': 150.0},
            {'latitude': 19.2291, 'longitude': 72.8617, 'aqi': 150.0},
        ]
        grid = IDWInterpolator.interpolate_grid(dummy_stations, resolution=10)
        for pt in grid:
            self.assertEqual(pt['interpolated_aqi'], 150.0)

    def test_hotspot_detector_geojson_format(self):
        stations = [
            {'latitude': 19.0522, 'longitude': 72.8995, 'aqi': 350.0},
            {'latitude': 18.9067, 'longitude': 72.8147, 'aqi': 45.0},
        ]
        geojson = HotspotDetector.detect_hotspots(stations, threshold=HOTSPOT_THRESHOLD, resolution=15)
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertIn("features", geojson)
        self.assertIn("metadata", geojson)
        self.assertGreater(geojson["metadata"]["hotspot_cells_count"], 0)

        for feature in geojson["features"]:
            geom = feature["geometry"]
            if geom["type"] == "Point":
                lon, lat = geom["coordinates"]
                self.assertTrue(72.75 <= lon <= 73.10)
                self.assertTrue(18.89 <= lat <= 19.30)


class SpatialGISAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tz = ZoneInfo("Asia/Kolkata")
        self.station1 = MonitoringStation.objects.create(
            station_id="OPENAQ_6948",
            name="Chhatrapati Shivaji Intl. Airport (T2), Mumbai - MPCB",
            latitude=19.10078,
            longitude=72.87462,
            zone_type="COMMERCIAL"
        )
        now = datetime.now(self.tz)
        raw = RawMeasurement.objects.create(
            station=self.station1,
            recorded_at=now,
            pm25=150.0,
            pm10=280.0,
            no2=50.0,
            so2=20.0,
            co=1.5,
            o3=60.0,
            source="OPENAQ_MEASURED"
        )
        AQIService.calculate_for_measurement(raw)

    def test_hotspots_api_endpoint(self):
        response = self.client.get(f'/api/v1/gis/hotspots/?threshold={HOTSPOT_THRESHOLD}&resolution=15')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("type"), "FeatureCollection")
        self.assertIn("features", response.data)

    def test_full_grid_api_endpoint(self):
        response = self.client.get('/api/v1/gis/grid/?resolution=12')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("type"), "FeatureCollection")
        # Land-masked cells within Mumbai boundary
        self.assertGreater(len(response.data.get("features", [])), 0)

    def test_unified_map_layers_api(self):
        response = self.client.get(f'/api/v1/gis/map-layers/?threshold={HOTSPOT_THRESHOLD}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("stations_geojson", response.data)
        self.assertIn("hotspots_geojson", response.data)
        self.assertIn("predicted_hotspots", response.data)
        self.assertIn("map_config", response.data)
        self.assertIn("legend", response.data)

        # Check measured vs modelled field on station feature
        stations = response.data["stations_geojson"].get("features", [])
        if stations:
            props = stations[0]["properties"]
            self.assertIn("source", props)
            self.assertIn("is_measured", props)

    def test_interactive_map_html_view(self):
        response = self.client.get('/map/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b'AirSense', response.content)
        self.assertIn(b'leaflet.js', response.content)
