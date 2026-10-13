import math
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Valid physical boundary ranges for pollutants and weather parameters
VALID_RANGES = {
    'pm25': (0.0, 1000.0),       # ug/m3
    'pm10': (0.0, 1500.0),       # ug/m3
    'no2': (0.0, 1000.0),        # ug/m3
    'so2': (0.0, 1000.0),        # ug/m3
    'co': (0.0, 100.0),          # mg/m3
    'o3': (0.0, 1000.0),         # ug/m3
    'temperature': (5.0, 50.0),  # °C for Mumbai tropical climate
    'humidity': (5.0, 100.0),    # %
    'wind_speed': (0.0, 150.0),  # km/h
    'wind_direction': (0.0, 360.0) # degrees
}

# Maximum allowable spike (rate of change) in 1 hour
MAX_HOURLY_DELTA = {
    'pm25': 250.0,
    'pm10': 400.0,
    'no2': 200.0,
    'so2': 200.0,
    'co': 20.0,
    'o3': 150.0,
}

class DataPreprocessor:
    """
    Cleans, validates, and normalizes raw sensor readings and meteorological feeds.
    Includes:
      - Physical boundary checks
      - Rate-of-change / spike detection against recent readings
      - Time-based linear interpolation for gaps up to 3 hours with imputation tracking
    """

    @staticmethod
    def validate_value(param_name: str, value: Any, prev_value: Optional[float] = None) -> Optional[float]:
        """
        Validates whether a numerical value falls within physical atmospheric bounds
        and does not exceed unphysical spike thresholds compared to the previous reading.
        Returns cleaned float or None if invalid.
        """
        if value is None:
            return None

        try:
            val = float(value)
        except (ValueError, TypeError):
            return None

        # Check for NaN or Inf
        if math.isnan(val) or math.isinf(val):
            return None

        # Check physical boundary
        if param_name in VALID_RANGES:
            min_val, max_val = VALID_RANGES[param_name]
            if val < min_val or val > max_val:
                logger.warning(
                    f"Outlier or unphysical reading detected for {param_name}: {val} "
                    f"(Valid range: {min_val}-{max_val}). Setting to None."
                )
                return None

        # Spike detection if previous reading exists
        if prev_value is not None and param_name in MAX_HOURLY_DELTA:
            delta = abs(val - prev_value)
            if delta > MAX_HOURLY_DELTA[param_name]:
                logger.warning(
                    f"Unphysical spike detected for {param_name}: delta={delta:.1f} "
                    f"(Max permitted={MAX_HOURLY_DELTA[param_name]}). Setting to None."
                )
                return None

        return round(val, 2)

    @classmethod
    def clean_record(cls, record_dict: dict, prev_record: Optional[dict] = None) -> dict:
        """
        Sanitizes all pollutant and weather fields of a raw record.
        """
        cleaned = {}
        for param in VALID_RANGES.keys():
            prev_val = prev_record.get(param) if prev_record else None
            cleaned[param] = cls.validate_value(param, record_dict.get(param), prev_value=prev_val)

        cleaned['station'] = record_dict.get('station')
        cleaned['recorded_at'] = record_dict.get('recorded_at')
        cleaned['source'] = record_dict.get('source', 'OPENAQ_MEASURED')
        cleaned['is_validated'] = True
        cleaned['is_imputed'] = False
        cleaned['imputed_fields'] = []

        return cleaned

    @classmethod
    def interpolate_short_gaps(cls, clean_records: List[dict], max_gap_hours: int = 3) -> List[dict]:
        """
        Takes chronologically ordered clean records and performs linear interpolation
        for missing values where the gap is <= max_gap_hours (e.g. 1 to 3 hours).
        Marks records with is_imputed=True and imputed_fields=['pm25', ...]
        """
        if len(clean_records) < 3:
            return clean_records

        pollutant_keys = ['pm25', 'pm10', 'no2', 'so2', 'co', 'o3', 'temperature', 'humidity', 'wind_speed', 'wind_direction']

        for key in pollutant_keys:
            n = len(clean_records)
            i = 0
            while i < n:
                if clean_records[i].get(key) is None:
                    # Look back for last valid value
                    prev_idx = i - 1
                    if prev_idx < 0 or clean_records[prev_idx].get(key) is None:
                        i += 1
                        continue

                    # Look forward for next valid value
                    next_idx = i
                    while next_idx < n and clean_records[next_idx].get(key) is None:
                        next_idx += 1

                    if next_idx < n and clean_records[next_idx].get(key) is not None:
                        gap_size = next_idx - prev_idx - 1
                        if 1 <= gap_size <= max_gap_hours:
                            val_start = clean_records[prev_idx][key]
                            val_end = clean_records[next_idx][key]
                            step = (val_end - val_start) / (gap_size + 1)

                            for step_i in range(1, gap_size + 1):
                                target_idx = prev_idx + step_i
                                interp_val = round(val_start + step * step_i, 2)
                                clean_records[target_idx][key] = interp_val
                                clean_records[target_idx]['is_imputed'] = True
                                if 'imputed_fields' not in clean_records[target_idx]:
                                    clean_records[target_idx]['imputed_fields'] = []
                                if key not in clean_records[target_idx]['imputed_fields']:
                                    clean_records[target_idx]['imputed_fields'].append(key)

                    i = next_idx
                else:
                    i += 1

        return clean_records
