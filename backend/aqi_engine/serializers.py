from rest_framework import serializers
from django.utils import timezone
from .models import AQIRecord

class AQIRecordSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    station_id_code = serializers.CharField(source='station.station_id', read_only=True)
    latitude = serializers.FloatField(source='station.latitude', read_only=True)
    longitude = serializers.FloatField(source='station.longitude', read_only=True)

    # Raw concentrations from the linked raw measurement
    raw_pm25 = serializers.FloatField(source='raw_measurement.pm25', read_only=True)
    raw_pm10 = serializers.FloatField(source='raw_measurement.pm10', read_only=True)
    raw_no2 = serializers.FloatField(source='raw_measurement.no2', read_only=True)
    raw_so2 = serializers.FloatField(source='raw_measurement.so2', read_only=True)
    raw_co = serializers.FloatField(source='raw_measurement.co', read_only=True)
    raw_o3 = serializers.FloatField(source='raw_measurement.o3', read_only=True)
    temperature = serializers.FloatField(source='raw_measurement.temperature', read_only=True)
    humidity = serializers.FloatField(source='raw_measurement.humidity', read_only=True)
    wind_speed = serializers.FloatField(source='raw_measurement.wind_speed', read_only=True)
    source = serializers.CharField(source='raw_measurement.source', read_only=True, default='OPEN_METEO_MODELLED')
    ingested_at = serializers.DateTimeField(source='raw_measurement.ingested_at', read_only=True, default=None)

    # Data classification and freshness metadata
    data_classification = serializers.SerializerMethodField()
    provider = serializers.SerializerMethodField()
    is_stale = serializers.SerializerMethodField()
    freshness_hours = serializers.SerializerMethodField()
    freshness_label = serializers.SerializerMethodField()

    class Meta:
        model = AQIRecord
        fields = [
            'id',
            'station_id_code',
            'station_name',
            'latitude',
            'longitude',
            'recorded_at',
            'source',
            'data_classification',
            'provider',
            'is_stale',
            'freshness_hours',
            'freshness_label',
            'ingested_at',
            'overall_aqi',
            'prominent_pollutant',
            'aqi_category',
            'color_hex',
            'valid_criteria_met',
            'is_instantaneous_fallback',
            'data_sufficiency_flags',
            # Sub-indices (Ip)
            'sub_index_pm25',
            'sub_index_pm10',
            'sub_index_no2',
            'sub_index_so2',
            'sub_index_co',
            'sub_index_o3',
            # Raw Concentrations (Cp) & Weather
            'raw_pm25',
            'raw_pm10',
            'raw_no2',
            'raw_so2',
            'raw_co',
            'raw_o3',
            'temperature',
            'humidity',
            'wind_speed'
        ]

    def get_data_classification(self, obj):
        source = obj.raw_measurement.source if obj.raw_measurement else 'OPEN_METEO_MODELLED'
        if source in ('CPCB_OFFICIAL', 'WAQI_FEED', 'OPENAQ_MEASURED'):
            return "Ground measured"
        return "Modelled"

    def get_provider(self, obj):
        source = obj.raw_measurement.source if obj.raw_measurement else 'OPEN_METEO_MODELLED'
        mapping = {
            'CPCB_OFFICIAL': 'Central Pollution Control Board (CPCB)',
            'WAQI_FEED': 'World Air Quality Index (WAQI)',
            'OPENAQ_MEASURED': 'OpenAQ Ground Sensor Network',
            'OPEN_METEO_MODELLED': 'Open-Meteo Atmospheric Model'
        }
        return mapping.get(source, 'Open-Meteo Atmospheric Model')

    def get_freshness_hours(self, obj):
        if not obj.recorded_at:
            return None
        now = timezone.now()
        return round(max(0.0, (now - obj.recorded_at).total_seconds() / 3600.0), 1)

    def get_is_stale(self, obj):
        h = self.get_freshness_hours(obj)
        return h is None or h > 6.0

    def get_freshness_label(self, obj):
        h = self.get_freshness_hours(obj)
        if h is None:
            return "Unknown"
        if h < 1.0:
            return "Just now (<1h)"
        elif h <= 3.0:
            return f"{h}h ago (Fresh)"
        elif h <= 6.0:
            return f"{h}h ago (Moderate)"
        else:
            return f"{h}h ago (Stale)"
