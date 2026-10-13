from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from core.models import MonitoringStation
from ingestion.models import RawMeasurement, CleanMeasurement
from aqi_engine.models import AQIRecord
from aqi_engine.services.cpcb_calculator import CPCBCalculator
from aqi_engine.services.aqi_service import AQIService

class CPCBAQICalculatorTestCase(TestCase):
    def test_pm25_sub_index_calculation(self):
        # 1. Breakpoint Good: 0.0 to 30.0 ug/m3 -> 0 to 50 index
        # 15.0 ug/m3 -> 0 + (50/30) * 15 = 25.0
        self.assertEqual(CPCBCalculator.calculate_sub_index('pm25', 15.0), 25.0)

        # 2. Decimal boundary case: 30.5 ug/m3 falls into (30.0, 60.0] -> 51 to 100 index
        # 51 + (49 / 30.0) * (30.5 - 30.0) = 51 + 0.8166... = 51.8
        idx_dec = CPCBCalculator.calculate_sub_index('pm25', 30.5)
        self.assertIsNotNone(idx_dec)
        self.assertEqual(idx_dec, 51.8)

        # 3. Exact boundary: 30.0 ug/m3 -> top of Good band = 50.0
        self.assertEqual(CPCBCalculator.calculate_sub_index('pm25', 30.0), 50.0)

        # 4. Exact boundary: 60.0 ug/m3 -> top of Satisfactory band = 100.0
        self.assertEqual(CPCBCalculator.calculate_sub_index('pm25', 60.0), 100.0)

        # 5. Moderate range: 75.0 ug/m3 in (60.0, 90.0] -> 101 to 200 index
        # 101 + (99 / 30.0) * (75.0 - 60.0) = 101 + 49.5 = 150.5
        self.assertEqual(CPCBCalculator.calculate_sub_index('pm25', 75.0), 150.5)

    def test_pm10_sub_index_calculation(self):
        # Good: 50.0 ug/m3 -> 50.0
        self.assertEqual(CPCBCalculator.calculate_sub_index('pm10', 50.0), 50.0)

        # Satisfactory: 100.0 ug/m3 in (50.0, 100.0] -> 100.0
        self.assertEqual(CPCBCalculator.calculate_sub_index('pm10', 100.0), 100.0)

        # Decimal: 50.5 ug/m3 -> 51 + (49/50.0) * 0.5 = 51 + 0.49 = 51.5
        self.assertEqual(CPCBCalculator.calculate_sub_index('pm10', 50.5), 51.5)

        # Moderate: 175.0 ug/m3 in (100.0, 250.0] -> 101 to 200 index
        # 101 + (99 / 150.0) * 75.0 = 101 + 49.5 = 150.5
        self.assertEqual(CPCBCalculator.calculate_sub_index('pm10', 175.0), 150.5)

    def test_category_and_color_mapping(self):
        self.assertEqual(CPCBCalculator.get_category_and_color(35)[0], "Good")
        self.assertEqual(CPCBCalculator.get_category_and_color(75)[0], "Satisfactory")
        self.assertEqual(CPCBCalculator.get_category_and_color(150)[0], "Moderate")
        self.assertEqual(CPCBCalculator.get_category_and_color(250)[0], "Poor")
        self.assertEqual(CPCBCalculator.get_category_and_color(350)[0], "Very Poor")
        self.assertEqual(CPCBCalculator.get_category_and_color(450)[0], "Severe")

    def test_overall_aqi_prominent_pollutant_rule(self):
        # PM2.5 = 75 (sub-index 150.5), PM10 = 60 (sub-index ~60.8), NO2 = 30 (sub-index ~37.5)
        # Criteria met (3 pollutants, particulate included)
        # Prominent pollutant must be PM25
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
        self.assertEqual(res['overall_aqi'], 150.5)

    def test_insufficient_pollutants_keeps_clean_category_and_flag(self):
        # Only 2 pollutants: valid_criteria_met is False, but category remains clean
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
        # Category must NOT contain "(Partial Data)"
        self.assertNotIn("Partial Data", res['category'])
        self.assertEqual(res['category'], 'Satisfactory')


class AQIEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tz = ZoneInfo("Asia/Kolkata")
        self.station = MonitoringStation.objects.create(
            station_id="OPENAQ_6927",
            name="Colaba, Mumbai - MPCB",
            latitude=18.91,
            longitude=72.82,
            zone_type="COASTAL"
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
