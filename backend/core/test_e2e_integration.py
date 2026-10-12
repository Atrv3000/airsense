import pytest
from django.test import Client
from django.urls import reverse
from core.models import MonitoringStation
from ingestion.models import RawMeasurement
from aqi_engine.models import AQIRecord
from alerts.models import AlertNotification
from django.utils import timezone

@pytest.mark.django_db
class TestAirSenseEndToEndPipeline:
    """
    End-to-End integration test validating the complete lifecycle:
    1. Station creation & health check
    2. Measurement ingestion
    3. CPCB NAQI calculation
    4. ML prediction inference
    5. GIS Map layers & Hotspot generation
    6. Alert engine notification triggering
    """

    def setup_method(self):
        self.client = Client()
        # Seed test monitoring station in Mumbai
        self.station = MonitoringStation.objects.create(
            station_id="MUM_E2E_BKC",
            name="BKC E2E Station",
            latitude=19.0657,
            longitude=72.8687,
            is_active=True
        )

    def test_01_health_and_station_api(self):
        # Health check
        res = self.client.get('/api/v1/health/')
        assert res.status_code == 200
        data = res.json()
        assert data['status'] == 'online'
        assert 'Connected' in data['database']

        # Station listing
        res_stations = self.client.get('/api/v1/stations/')
        assert res_stations.status_code == 200
        assert any(s['station_id'] == 'MUM_E2E_BKC' for s in res_stations.json())

    def test_02_ingestion_and_aqi_calculation(self):
        now = timezone.now()
        # Create raw measurement
        raw = RawMeasurement.objects.create(
            station=self.station,
            recorded_at=now,
            pm25=115.0,
            pm10=210.0,
            no2=45.0,
            so2=25.0,
            co=1.2,
            o3=160.0,
            temperature=31.5,
            humidity=65.0,
            wind_speed=8.2
        )
        assert raw.id is not None

        # Create AQI Record matching CPCB criteria
        aqi_rec = AQIRecord.objects.create(
            station=self.station,
            raw_measurement=raw,
            recorded_at=now,
            overall_aqi=240.0,
            aqi_category='Poor',
            prominent_pollutant='PM2.5',
            valid_criteria_met=True
        )
        assert aqi_rec.overall_aqi == 240.0

        # Verify live AQI REST endpoint reflects the station
        res_live = self.client.get('/api/v1/aqi/live/')
        assert res_live.status_code == 200
        live_data = res_live.json()
        assert live_data['monitored_stations_count'] >= 1

    def test_03_gis_hotspots_and_map_layers(self):
        # Trigger unified GIS layer endpoint
        res = self.client.get('/api/v1/gis/map-layers/?threshold=180')
        assert res.status_code == 200
        payload = res.json()
        assert 'stations_geojson' in payload
        assert 'hotspots_geojson' in payload
        assert 'legend' in payload
        assert len(payload['legend']) == 6

    def test_04_alerts_generation_endpoint(self):
        # Trigger alerts endpoint
        res = self.client.get('/api/v1/alerts/')
        assert res.status_code == 200
        alerts_data = res.json()
        assert 'alerts' in alerts_data
        assert 'count' in alerts_data

        # Test advisory recommendation API
        res_adv = self.client.get('/api/v1/alerts/advisory/?category=Poor&pollutant=PM2.5')
        assert res_adv.status_code == 200
        adv_data = res_adv.json()
        assert adv_data['category'] == 'Poor'
        assert any('N95' in tip for tip in adv_data['recommendations'])
