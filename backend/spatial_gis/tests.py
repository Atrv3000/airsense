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
from spatial_gis.services.spatial_validator import SpatialValidator

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

    def test_hotspot_excludes_station_failing_valid_criteria(self):
        station2 = MonitoringStation.objects.create(
            station_id="OPENAQ_FAIL_CRITERIA",
            name="Invalid Criteria Station",
            latitude=19.12,
            longitude=72.88,
            zone_type="INDUSTRIAL"
        )
        now = datetime.now(self.tz)
        raw2 = RawMeasurement.objects.create(
            station=station2,
            recorded_at=now,
            pm25=190.0,
            source="OPENAQ_MEASURED"
        )
        AQIRecord.objects.create(
            station=station2,
            raw_measurement=raw2,
            recorded_at=now,
            overall_aqi=350.0,
            aqi_category='Very Poor',
            valid_criteria_met=False
        )

        from spatial_gis.views import get_latest_station_readings
        readings = get_latest_station_readings()
        reading_ids = [r['station_id'] for r in readings]
        self.assertNotIn("OPENAQ_FAIL_CRITERIA", reading_ids)


class SpatialValidationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dummy_stations = [
            {'station_id': 'OPENAQ_6927', 'name': 'Colaba', 'latitude': 18.9067, 'longitude': 72.8147, 'aqi': 65.0},
            {'station_id': 'OPENAQ_6959', 'name': 'Worli', 'latitude': 19.0166, 'longitude': 72.8167, 'aqi': 120.0},
            {'station_id': 'OPENAQ_3409328', 'name': 'Bandra', 'latitude': 19.0657, 'longitude': 72.8333, 'aqi': 145.0},
            {'station_id': 'OPENAQ_6945', 'name': 'Kurla', 'latitude': 19.0667, 'longitude': 72.8833, 'aqi': 180.0},
            {'station_id': 'OPENAQ_6967', 'name': 'Sion', 'latitude': 19.0333, 'longitude': 72.8667, 'aqi': 160.0},
            {'station_id': 'OPENAQ_6956', 'name': 'Powai', 'latitude': 19.1167, 'longitude': 72.9000, 'aqi': 95.0},
        ]

    def test_losocv_idw_powers(self):
        for p in [1.0, 2.0, 3.0]:
            res = SpatialValidator.leave_one_station_out_cv(self.dummy_stations, method="idw", power=p)
            self.assertEqual(res["stations_evaluated"], len(self.dummy_stations))
            self.assertIsNotNone(res["rmse"])
            self.assertIsNotNone(res["mae"])
            self.assertGreater(res["rmse"], 0.0)
            self.assertGreater(res["mae"], 0.0)
            self.assertEqual(len(res["station_evaluations"]), len(self.dummy_stations))

    def test_ordinary_kriging_interpolation(self):
        # 1. Point prediction
        target_lat = np.array([19.05])
        target_lon = np.array([72.85])
        pred = IDWInterpolator.predict_points_kriging(target_lat, target_lon, self.dummy_stations)
        self.assertEqual(len(pred), 1)
        self.assertGreaterEqual(pred[0], 0.0)
        self.assertLessEqual(pred[0], 500.0)

        # 2. LOSOCV evaluation with Kriging
        cv_res = SpatialValidator.leave_one_station_out_cv(self.dummy_stations, method="kriging")
        self.assertEqual(cv_res["stations_evaluated"], len(self.dummy_stations))
        self.assertIsNotNone(cv_res["rmse"])
        self.assertGreater(cv_res["rmse"], 0.0)

    def test_spatial_gbm_interpolation(self):
        # 1. Point prediction
        target_lat = np.array([19.05])
        target_lon = np.array([72.85])
        pred = IDWInterpolator.predict_points_gbm(target_lat, target_lon, self.dummy_stations)
        self.assertEqual(len(pred), 1)
        self.assertGreaterEqual(pred[0], 0.0)
        self.assertLessEqual(pred[0], 500.0)

        # 2. LOSOCV evaluation with GBM
        cv_res = SpatialValidator.leave_one_station_out_cv(self.dummy_stations, method="gbm")
        self.assertEqual(cv_res["stations_evaluated"], len(self.dummy_stations))
        self.assertIsNotNone(cv_res["rmse"])

    def test_compare_interpolators_ranks_all_models(self):
        comp = SpatialValidator.compare_interpolators(self.dummy_stations)
        self.assertEqual(comp["stations_count"], len(self.dummy_stations))
        self.assertIn("comparison", comp)
        self.assertIn("champion", comp)

        expected_configs = ["IDW_p1", "IDW_p2", "IDW_p3", "Ordinary_Kriging", "Spatial_GBM"]
        for cfg in expected_configs:
            self.assertIn(cfg, comp["comparison"])
            self.assertIsNotNone(comp["comparison"][cfg]["rmse"])

        champ = comp["champion"]
        self.assertIn(champ["name"], expected_configs)
        self.assertGreater(champ["rmse"], 0.0)

    def test_spatial_validation_api_endpoint(self):
        # Create station and aqi records in test db
        station = MonitoringStation.objects.create(
            station_id="OPENAQ_TEST_1",
            name="Test Station 1",
            latitude=19.05,
            longitude=72.85,
            zone_type="URBAN"
        )
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        raw = RawMeasurement.objects.create(
            station=station,
            recorded_at=now,
            pm25=50.0,
            pm10=90.0,
            source="OPENAQ_MEASURED"
        )
        AQIService.calculate_for_measurement(raw)

        response = self.client.get('/api/v1/gis/validation/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_spatial_cv_benchmark_command(self):
        from io import StringIO
        from django.core.management import call_command
        from django.utils import timezone

        now = timezone.now()
        for i, s_info in enumerate(self.dummy_stations[:4]):
            st = MonitoringStation.objects.create(
                station_id=f"TEST_BENCH_ST_{i}",
                name=s_info['name'],
                latitude=s_info['latitude'],
                longitude=s_info['longitude'],
                zone_type="URBAN"
            )
            raw = RawMeasurement.objects.create(
                station=st,
                recorded_at=now,
                pm25=s_info['aqi'] / 2.0,
                pm10=s_info['aqi'],
                source="OPENAQ_MEASURED"
            )
            AQIRecord.objects.create(
                station=st,
                raw_measurement=raw,
                recorded_at=now,
                overall_aqi=s_info['aqi'],
                prominent_pollutant="pm10",
                aqi_category="Moderate"
            )

        out = StringIO()
        call_command('spatial_cv_benchmark', hours=1, stdout=out)
        output = out.getvalue()
        self.assertIn("SPATIAL INTERPOLATION VALIDATION", output)
        self.assertIn("Inverse Distance Weighting (p=1)", output)
        self.assertIn("Inverse Distance Weighting (p=2)", output)
        self.assertIn("Ordinary Kriging", output)

