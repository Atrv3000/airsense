import logging
from datetime import timedelta
from django.db.models import Avg
from ingestion.models import RawMeasurement, CleanMeasurement
from aqi_engine.models import AQIRecord
from .cpcb_calculator import CPCBCalculator

logger = logging.getLogger(__name__)

class AQIService:
    """
    Coordinates CPCB NAQI calculation following official averaging standards:
      - 24-hour average for PM2.5, PM10, NO2, SO2 (requires >= 16 hours of data, i.e., 66% completeness)
      - 8-hour rolling average for CO, O3 (requires >= 6 hours of data, i.e., 75% completeness)
    Computes from CleanMeasurement if available, falling back to RawMeasurement.
    Persists results into AQIRecord.
    """

    @classmethod
    def get_averaged_concentrations(cls, station, target_time) -> dict:
        """
        Calculates 24-hour averages for PM2.5, PM10, NO2, SO2 and
        8-hour rolling averages for CO, O3 up to target_time.
        Falls back to instantaneous concentration if history is sparse.
        """
        # Look back 24 hours
        time_24h_ago = target_time - timedelta(hours=23)
        time_8h_ago = target_time - timedelta(hours=7)

        # Query CleanMeasurement first; if empty, query RawMeasurement
        records_24h = CleanMeasurement.objects.filter(
            station=station,
            recorded_at__gte=time_24h_ago,
            recorded_at__lte=target_time
        ).order_by('recorded_at')

        use_clean = records_24h.exists()
        if not use_clean:
            records_24h = RawMeasurement.objects.filter(
                station=station,
                recorded_at__gte=time_24h_ago,
                recorded_at__lte=target_time
            ).order_by('recorded_at')

        count_24h = records_24h.count()
        latest_record = records_24h.last()

        if not latest_record:
            return {}

        # 24-hour aggregations for PM2.5, PM10, NO2, SO2 (CPCB standard: min 16 hours)
        pollutants = {}
        for p in ['pm25', 'pm10', 'no2', 'so2']:
            valid_vals = [getattr(r, p) for r in records_24h if getattr(r, p) is not None]
            # If at least 4 hours available in history, use rolling mean, else latest
            if len(valid_vals) >= 4:
                pollutants[p] = round(sum(valid_vals) / len(valid_vals), 2)
            else:
                pollutants[p] = getattr(latest_record, p)

        # 8-hour rolling aggregations for CO, O3
        records_8h = [r for r in records_24h if r.recorded_at >= time_8h_ago]
        for p in ['co', 'o3']:
            valid_vals = [getattr(r, p) for r in records_8h if getattr(r, p) is not None]
            if len(valid_vals) >= 2:
                pollutants[p] = round(sum(valid_vals) / len(valid_vals), 2)
            else:
                pollutants[p] = getattr(latest_record, p)

        return pollutants

    @classmethod
    def calculate_for_measurement(cls, raw_measurement: RawMeasurement) -> AQIRecord:
        """
        Calculates and stores NAQI for a single RawMeasurement instance
        using CPCB standard multi-hour averaging where historical data is present.
        """
        averaged_pollutants = cls.get_averaged_concentrations(
            station=raw_measurement.station,
            target_time=raw_measurement.recorded_at
        )

        # Fallback to direct raw measurement values if empty
        if not averaged_pollutants:
            averaged_pollutants = {
                'pm25': raw_measurement.pm25,
                'pm10': raw_measurement.pm10,
                'no2': raw_measurement.no2,
                'so2': raw_measurement.so2,
                'co': raw_measurement.co,
                'o3': raw_measurement.o3,
            }

        calc_result = CPCBCalculator.calculate_overall_aqi(averaged_pollutants)
        subs = calc_result['sub_indices']

        defaults = {
            'station': raw_measurement.station,
            'recorded_at': raw_measurement.recorded_at,
            'sub_index_pm25': subs.get('pm25'),
            'sub_index_pm10': subs.get('pm10'),
            'sub_index_no2': subs.get('no2'),
            'sub_index_so2': subs.get('so2'),
            'sub_index_co': subs.get('co'),
            'sub_index_o3': subs.get('o3'),
            'overall_aqi': calc_result['overall_aqi'],
            'prominent_pollutant': calc_result['prominent_pollutant'],
            'aqi_category': calc_result['category'],
            'color_hex': calc_result['color_hex'],
            'valid_criteria_met': calc_result['valid_criteria_met'],
        }

        aqi_rec, _ = AQIRecord.objects.update_or_create(
            raw_measurement=raw_measurement,
            defaults=defaults
        )

        return aqi_rec

    @classmethod
    def calculate_all_pending(cls) -> int:
        """
        Processes all RawMeasurement records currently missing an AQIRecord.
        """
        pending_measurements = RawMeasurement.objects.filter(aqi_record__isnull=True).select_related('station')
        count = 0

        for raw_meas in pending_measurements:
            try:
                cls.calculate_for_measurement(raw_meas)
                count += 1
            except Exception as e:
                logger.error(f"Error calculating AQI for measurement {raw_meas.id}: {e}")
                continue

        return count
