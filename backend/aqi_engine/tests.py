from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime
from zoneinfo import ZoneInfo
from core.models import MonitoringStation
from ingestion.models import RawMeasurement
from aqi_engine.models import AQIRecord
from aqi_engine.services.cpcb_calculator import CPCBCalculator
from aqi_engine.services.aqi_service import AQIService

class CPCBAQICalculatorTestCase(TestCase):
    def test_pm25_sub_index_calculation(self):
        # Breakpoint for Good (0-30 ug/m3 -> 0-50 index)
        # 15.0 ug/m3 -> (50/30) * 15 = 25.0
        idx_good = CPCBCalculator.calculate_sub_index('pm25', 15.0)
        self.assertEqual(idx_good, 25.0)

        # Breakpoint for Satisfactory (31-60 ug/m3 -> 51-100 index)
        # 45.0 ug/m3 -> 51 + (49/29) * (45 - 31) = 51 + 23.655 = 74.7
        idx_sat = CPCBCalculator.calculate_sub_index('pm25', 45.0)
        self.assertEqual(idx_sat, 74.7)

        # Breakpoint for Moderate (61-90 ug/m3 -> 101-200 index)
        # 75.0 ug/m3 -> 101 + (99/29) * (75 - 61) = 101 + 47.79 = 148.8
        idx_mod = CPCBCalculator.calculate_sub_index('pm25', 75.0)
        self.assertEqual(idx_mod, 148.8)

    def test_pm10_sub_index_calculation(self):
        # 100.0 ug/m3 in Satisfactory range (51-100 ug/m3 -> 51-100 index)
        idx_sat = CPCBCalculator.calculate_sub_index('pm10', 100.0)
        self.assertEqual(idx_sat, 100.0)

        # 175.0 ug/m3 in Moderate range (101-250 ug/m3 -> 101-200 index)
        idx_mod = CPCBCalculator.calculate_sub_index('pm10', 175.0)
        self.assertAlmostEqual(idx_mod, 150.1, delta=0.5)

    def test_category_and_color_mapping(self):
        self.assertEqual(CPCBCalculator.get_category_and_color(35)[0], "Good")
        self.assertEqual(CPCBCalculator.get_category_and_color(75)[0], "Satisfactory")
        self.assertEqual(CPCBCalculator.get_category_and_color(150)[0], "Moderate")
        self.assertEqual(CPCBCalculator.get_category_and_color(250)[0], "Poor")
        self.assertEqual(CPCBCalculator.get_category_and_color(350)[0], "Very Poor")
        self.assertEqual(CPCBCalculator.get_category_and_color(450)[0], "Severe")

    def test_overall_aqi_prominent_pollutant_rule(self):
        # PM2.5 = 75 (sub-index ~148.8), PM10 = 60 (sub-index ~66), NO2 = 30 (sub-index ~37.5)
        # Criteria met (3 pollutants, PM included)
        # Max is PM2.5 -> Prominent pollutant must be PM25
        pollutants = {
            'pm25': 75.0,
            'pm10': 60.0,
            'no2': 30.0,
            'so2': None,
            'co': None,
            'o3': None
        }
        res = CPCBCalculator.calculate_overall_aqi(pollutants)
        self.assertTrue(res['valid_criteria_met'])
        self.assertEqual(res['prominent_pollutant'], 'PM25')
        self.assertEqual(res['category'], 'Moderate')
        self.assertEqual(res['overall_aqi'], 148.8)

    def test_insufficient_pollutants_rule(self):
        # Only 2 pollutants: criteria NOT met
        pollutants = {
            'pm25': 40.0,
            'pm10': 80.0,
            'no2': None,
            'so2': None,
            'co': None,
            'o3': None
        }
        res = CPCBCalculator.calculate_overall_aqi(pollutants)
        self.assertFalse(res['valid_criteria_met'])
        self.assertIn("Partial Data", res['category'])

class AQIEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tz = ZoneInfo("Asia/Kolkata")
        self.station = MonitoringStation.objects.create(
            station_id="TEST_BKC",
            name="Test BKC Station",
            latitude=19.0657,
            longitude=72.8687,
            zone_type="COMMERCIAL"
        )
        now = datetime.now(self.tz)
        self.raw_meas = RawMeasurement.objects.create(
            station=self.station,
            recorded_at=now,
            pm25=75.0,
            pm10=95.0,
            no2=35.0,
            so2=12.0,
            co=0.8,
            o3=45.0,
            temperature=29.0,
            humidity=70.0,
            wind_speed=14.0
        )
        self.aqi_rec = AQIService.calculate_for_measurement(self.raw_meas)

    def test_live_aqi_api(self):
        response = self.client.get('/api/v1/aqi/live/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('region'), 'Greater Mumbai')
        self.assertGreater(response.data.get('monitored_stations_count'), 0)
        self.assertIsNotNone(response.data.get('city_average_aqi'))

    def test_station_aqi_detail_api(self):
        response = self.client.get(f'/api/v1/aqi/station/{self.station.station_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('station_id_code'), self.station.station_id)
        self.assertEqual(response.data.get('prominent_pollutant'), 'PM25')

    def test_historical_aqi_trend_api(self):
        response = self.client.get(f'/api/v1/aqi/historical/?station_id={self.station.station_id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('record_count'), 1)
        self.assertEqual(len(response.data.get('history')), 1)
