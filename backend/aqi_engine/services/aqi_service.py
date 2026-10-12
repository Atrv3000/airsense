import logging
from ingestion.models import RawMeasurement
from aqi_engine.models import AQIRecord
from .cpcb_calculator import CPCBCalculator

logger = logging.getLogger(__name__)

class AQIService:
    """
    Coordinates NAQI calculation from RawMeasurement instances
    and persists them to AQIRecord in PostgreSQL.
    """

    @classmethod
    def calculate_for_measurement(cls, raw_measurement: RawMeasurement) -> AQIRecord:
        """
        Calculates and stores NAQI for a single RawMeasurement instance.
        """
        pollutants_dict = {
            'pm25': raw_measurement.pm25,
            'pm10': raw_measurement.pm10,
            'no2': raw_measurement.no2,
            'so2': raw_measurement.so2,
            'co': raw_measurement.co,
            'o3': raw_measurement.o3,
        }

        calc_result = CPCBCalculator.calculate_overall_aqi(pollutants_dict)
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
