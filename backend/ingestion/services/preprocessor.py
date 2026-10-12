import math
import logging

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

class DataPreprocessor:
    """
    Cleans, validates, and normalizes raw sensor readings and meteorological feeds.
    """

    @staticmethod
    def validate_value(param_name: str, value):
        """
        Validates whether a single numerical value falls within physical atmospheric bounds.
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

        # Check parameter boundary
        if param_name in VALID_RANGES:
            min_val, max_val = VALID_RANGES[param_name]
            if val < min_val or val > max_val:
                logger.warning(
                    f"Outlier or unphysical reading detected for {param_name}: {val} "
                    f"(Valid range: {min_val}-{max_val}). Setting to None."
                )
                return None

        return round(val, 2)

    @classmethod
    def clean_record(cls, record_dict: dict) -> dict:
        """
        Takes a raw measurement dictionary and sanitizes all fields.
        """
        cleaned = {}
        for param, bounds in VALID_RANGES.items():
            cleaned[param] = cls.validate_value(param, record_dict.get(param))

        # Preserve identifiers and timestamps
        cleaned['station'] = record_dict.get('station')
        cleaned['recorded_at'] = record_dict.get('recorded_at')
        cleaned['source'] = record_dict.get('source', 'UNKNOWN')
        cleaned['is_validated'] = True

        return cleaned
