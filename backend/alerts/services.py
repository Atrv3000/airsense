import logging
from typing import List, Dict, Any
from django.utils import timezone
from core.models import MonitoringStation
from aqi_engine.models import AQIRecord
from alerts.models import AlertNotification

logger = logging.getLogger(__name__)

class AlertEngine:
    """
    Evaluates live AQI metrics and forecasts against CPCB health safety levels.
    Generates structured AlertNotifications and actionable recommendations.
    """

    ADVISORY_MATRIX = {
        'Good': {
            'severity': 'INFO',
            'tips': [
                "Air quality is clean and healthy.",
                "Ideal conditions for outdoor sports, walking, and outdoor ventilation.",
                "No health precautions required."
            ]
        },
        'Satisfactory': {
            'severity': 'INFO',
            'tips': [
                "Air quality is acceptable for the general public.",
                "Highly sensitive individuals should monitor for minor respiratory symptoms.",
                "Outdoor activities are fully permissible."
            ]
        },
        'Moderate': {
            'severity': 'WARNING',
            'tips': [
                "People with asthma or lung conditions may experience discomfort.",
                "Sensitive groups should reduce prolonged heavy exertion outdoors.",
                "Keep windows closed during peak traffic hours."
            ]
        },
        'Poor': {
            'severity': 'WARNING',
            'tips': [
                "General public may experience breathing discomfort on prolonged exposure.",
                "Sensitive groups, children, and elderly should avoid outdoor morning walks.",
                "Wear an N95/FFP2 mask when commuting outdoors.",
                "Operate indoor HEPA air filtration if available."
            ]
        },
        'Very Poor': {
            'severity': 'CRITICAL',
            'tips': [
                "Respiratory illness risk significantly increased on prolonged exposure.",
                "Strictly avoid outdoor jogging, sports, or high-intensity exercise.",
                "Keep windows tightly shut; run indoor air purifiers.",
                "Vulnerable individuals should keep quick-relief medication handy."
            ]
        },
        'Severe': {
            'severity': 'EMERGENCY',
            'tips': [
                "Health emergency: Serious impacts on healthy individuals and critical impacts on existing diseases.",
                "Avoid all outdoor activities entirely.",
                "Use high-efficiency particulate respirators (N95/N99) even for brief outdoor transit.",
                "Consult healthcare professionals immediately upon respiratory distress."
            ]
        }
    }

    @classmethod
    def evaluate_and_generate_alerts(cls, threshold_override: float = None) -> List[AlertNotification]:
        """
        Inspects the latest AQIRecord for each station and creates alert records
        when AQI breaches safety criteria (AQI >= 150 or threshold_override).
        """
        created_alerts = []
        stations = MonitoringStation.objects.filter(is_active=True)

        for station in stations:
            latest_record = AQIRecord.objects.filter(station=station).order_by('-recorded_at').first()
            if not latest_record:
                continue

            aqi = latest_record.overall_aqi
            cat = latest_record.aqi_category
            threshold = threshold_override if threshold_override is not None else 180.0

            # If AQI crosses warning threshold or belongs to Poor/Very Poor/Severe
            if aqi >= threshold or cat in ['Poor', 'Very Poor', 'Severe']:
                advisory = cls.ADVISORY_MATRIX.get(cat, cls.ADVISORY_MATRIX['Poor'])
                severity = advisory['severity']

                title = f"{severity} AQI Alert: {station.name} ({cat})"
                message = (
                    f"AQI at {station.name} has reached {round(aqi, 1)} ({cat}). "
                    f"Prominent pollutant: {latest_record.prominent_pollutant or 'Particulates'}."
                )

                # Avoid duplicate alerts within the same 6-hour window for this station
                recent_cutoff = timezone.now() - timezone.timedelta(hours=6)
                existing = AlertNotification.objects.filter(
                    station=station,
                    category=cat,
                    created_at__gte=recent_cutoff
                ).exists()

                if not existing:
                    alert = AlertNotification.objects.create(
                        station=station,
                        title=title,
                        message=message,
                        severity=severity,
                        aqi_value=round(aqi, 1),
                        category=cat,
                        prominent_pollutant=latest_record.prominent_pollutant,
                        health_recommendations=advisory['tips'],
                        is_active=True
                    )
                    created_alerts.append(alert)
                    logger.info(f"Created Alert: {alert}")

        return created_alerts

    @classmethod
    def get_station_advisory(cls, category: str, prominent_pollutant: str = None) -> Dict[str, Any]:
        """
        Returns structured guidance based on CPCB category and prominent pollutant.
        """
        adv = cls.ADVISORY_MATRIX.get(category, cls.ADVISORY_MATRIX['Moderate'])
        tips = list(adv['tips'])

        if prominent_pollutant == 'O3':
            tips.append("Ozone levels peak in afternoon sunlight; prefer early morning outdoor tasks.")
        elif prominent_pollutant in ['PM2.5', 'PM10']:
            tips.append("Particulate matter is high; wear a certified particulate mask (N95).")

        return {
            'severity': adv['severity'],
            'category': category,
            'recommendations': tips
        }
