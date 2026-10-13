"""
CPCB (Central Pollution Control Board) Indian National Air Quality Index (NAQI) Engine.
Implements official continuous piecewise linear interpolation breakpoints methodology.
Reference: CPCB NAQI Technical Report (MoEFCC, Govt of India).
"""

import math
from typing import Dict, Optional, Tuple

# Continuous CPCB Breakpoint Table: (B_low, B_high, I_low, I_high)
# Bands are continuous so decimals like PM2.5 = 30.5 fall into (30.0, 60.0]
# Concentrations: PM2.5, PM10, NO2, SO2, O3 in ug/m3; CO in mg/m3
BREAKPOINTS = {
    'pm25': [
        (0.0, 30.0, 0, 50),        # Good
        (30.0, 60.0, 51, 100),     # Satisfactory
        (60.0, 90.0, 101, 200),    # Moderate
        (90.0, 120.0, 201, 300),   # Poor
        (120.0, 250.0, 301, 400),  # Very Poor
        (250.0, 500.0, 401, 500),  # Severe
    ],
    'pm10': [
        (0.0, 50.0, 0, 50),
        (50.0, 100.0, 51, 100),
        (100.0, 250.0, 101, 200),
        (250.0, 350.0, 201, 300),
        (350.0, 430.0, 301, 400),
        (430.0, 600.0, 401, 500),
    ],
    'no2': [
        (0.0, 40.0, 0, 50),
        (40.0, 80.0, 51, 100),
        (80.0, 180.0, 101, 200),
        (180.0, 280.0, 201, 300),
        (280.0, 400.0, 301, 400),
        (400.0, 600.0, 401, 500),
    ],
    'so2': [
        (0.0, 40.0, 0, 50),
        (40.0, 80.0, 51, 100),
        (80.0, 380.0, 101, 200),
        (380.0, 800.0, 201, 300),
        (800.0, 1600.0, 301, 400),
        (1600.0, 2000.0, 401, 500),
    ],
    'co': [
        (0.0, 1.0, 0, 50),
        (1.0, 2.0, 51, 100),
        (2.0, 10.0, 101, 200),
        (10.0, 17.0, 201, 300),
        (17.0, 34.0, 301, 400),
        (34.0, 50.0, 401, 500),
    ],
    'o3': [
        (0.0, 50.0, 0, 50),
        (50.0, 100.0, 51, 100),
        (100.0, 168.0, 101, 200),
        (168.0, 208.0, 201, 300),
        (208.0, 748.0, 301, 400),
        (748.0, 1000.0, 401, 500),
    ],
}

CATEGORY_CONFIG = [
    (0, 50, "Good", "#00B050"),
    (51, 100, "Satisfactory", "#92D050"),
    (101, 200, "Moderate", "#FFFF00"),
    (201, 300, "Poor", "#FF9900"),
    (301, 400, "Very Poor", "#FF0000"),
    (401, 500, "Severe", "#C00000"),
]


class CPCBCalculator:
    """
    Computes pollutant sub-indices, overall NAQI, prominent pollutant,
    and official health category according to Indian CPCB standards.
    """

    @classmethod
    def calculate_sub_index(cls, pollutant: str, concentration: Optional[float]) -> Optional[float]:
        """
        Calculates sub-index Ip for a given pollutant concentration using:
        Ip = I_low + ((I_high - I_low) / (B_high - B_low)) * (C - B_low)
        Uses continuous bands (B_low < C <= B_high, or B_low <= C <= B_high for first band)
        so no decimal values fall through.
        """
        if concentration is None or concentration < 0:
            return None

        pollutant_key = pollutant.lower()
        if pollutant_key not in BREAKPOINTS:
            return None

        ranges = BREAKPOINTS[pollutant_key]

        # Handle zero or near-zero concentration
        if concentration == 0.0:
            return 0.0

        for idx, (b_low, b_high, i_low, i_high) in enumerate(ranges):
            # First band includes lower bound 0.0; subsequent bands are (b_low, b_high]
            in_range = (b_low <= concentration <= b_high) if idx == 0 else (b_low < concentration <= b_high)
            if in_range:
                slope = (i_high - i_low) / (b_high - b_low)
                sub_index = i_low + slope * (concentration - b_low)
                return round(sub_index, 1)

        # Beyond upper range: cap at 500.0 per CPCB scale
        last_b_low, last_b_high, last_i_low, last_i_high = ranges[-1]
        if concentration > last_b_high:
            return 500.0

        return None

    @classmethod
    def get_category_and_color(cls, aqi: Optional[float]) -> Tuple[str, str]:
        """
        Maps numerical AQI to CPCB category name and hex color.
        Strictly returns clean category names without extra suffixes.
        """
        if aqi is None:
            return ("Insufficient Data", "#9E9E9E")

        aqi_round = round(aqi)
        for min_val, max_val, name, color in CATEGORY_CONFIG:
            if min_val <= aqi_round <= max_val:
                return (name, color)

        if aqi_round > 500:
            return ("Severe", "#C00000")

        return ("Unknown", "#9E9E9E")

    @classmethod
    def calculate_overall_aqi(cls, pollutants_dict: Dict[str, Optional[float]]) -> Dict:
        """
        Calculates all sub-indices and validates CPCB criteria:
        1. Minimum 3 criteria pollutants available.
        2. At least one must be PM10 or PM2.5.
        3. Overall AQI = max(sub-indices).
        4. Prominent Pollutant = pollutant with max sub-index.
        5. Does not mutate the category string; valid_criteria_met is tracked cleanly as a boolean.

        Returns:
        {
            'sub_indices': {'pm25': ..., 'pm10': ..., ...},
            'overall_aqi': float or None,
            'prominent_pollutant': str or None,
            'category': str,
            'color_hex': str,
            'valid_criteria_met': bool,
            'available_pollutant_count': int
        }
        """
        sub_indices = {}
        for p in ['pm25', 'pm10', 'no2', 'so2', 'co', 'o3']:
            c_val = pollutants_dict.get(p)
            sub_indices[p] = cls.calculate_sub_index(p, c_val)

        # Filter out valid (non-null) sub-indices
        valid_subs = {k: v for k, v in sub_indices.items() if v is not None}

        # CPCB Rule Check:
        # 1. At least 3 pollutants present
        # 2. One must be PM2.5 or PM10
        has_particulate = ('pm25' in valid_subs) or ('pm10' in valid_subs)
        has_min_pollutants = len(valid_subs) >= 3
        criteria_met = bool(has_particulate and has_min_pollutants)

        if len(valid_subs) > 0:
            overall_aqi = max(valid_subs.values())
            prominent = max(valid_subs, key=valid_subs.get).upper()
            category, color = cls.get_category_and_color(overall_aqi)
        else:
            overall_aqi = None
            prominent = None
            category, color = cls.get_category_and_color(None)

        return {
            'sub_indices': sub_indices,
            'overall_aqi': round(overall_aqi, 1) if overall_aqi is not None else None,
            'prominent_pollutant': prominent,
            'category': category,
            'color_hex': color,
            'valid_criteria_met': criteria_met,
            'available_pollutant_count': len(valid_subs)
        }
