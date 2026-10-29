import logging
from typing import List, Dict, Any
from django.utils import timezone
from core.models import MonitoringStation
from aqi_engine.models import AQIRecord
from ml_engine.models import ForecastRecord
from alerts.models import AlertNotification

logger = logging.getLogger(__name__)

class AlertEngine:
    """
    Evaluates live AQI metrics and forecasts against CPCB health safety levels.
    Generates structured AlertNotifications and auto-resolves alerts when AQI drops below thresholds.
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
    def evaluate_and_generate_alerts(cls, threshold_override: float = None, send_push: bool = True) -> List[AlertNotification]:
        """
        1. Evaluates latest AQIRecord for each station and creates alert when AQI >= 201 or in Poor/Very Poor/Severe.
        2. Auto-resolves active alerts if the station's current AQI drops below the alert threshold.
        3. Evaluates ForecastRecord predictions and generates proactive forecast-based alerts.
        Safely handles cases where overall_aqi is None.
        """
        created_alerts = []
        now = timezone.now()
        threshold = threshold_override if threshold_override is not None else 201.0
        stations = MonitoringStation.objects.filter(is_active=True)

        for station in stations:
            latest_record = AQIRecord.objects.filter(station=station).order_by('-recorded_at').first()

            if latest_record and latest_record.overall_aqi is not None:
                # CPCB Rule Check: only records meeting valid criteria (min 3 pollutants, one PM) drive alerts
                if not latest_record.valid_criteria_met:
                    logger.info(
                        f"Skipping alert evaluation for {station.name}: valid_criteria_met is False (CPCB criteria not met)."
                    )
                else:
                    aqi = latest_record.overall_aqi
                    cat = latest_record.aqi_category

                    # AUTO-RESOLVE check: If AQI dropped below threshold, resolve existing active alerts for this station
                    if aqi < threshold and cat not in ['Poor', 'Very Poor', 'Severe']:
                        active_alerts = AlertNotification.objects.filter(station=station, is_active=True, is_forecast_alert=False)
                        for alert in active_alerts:
                            alert.is_active = False
                            alert.resolved_at = now
                            alert.save()
                            logger.info(f"Auto-resolved alert for {station.name} as AQI dropped to {aqi}.")
                    elif aqi >= threshold or cat in ['Poor', 'Very Poor', 'Severe']:
                        advisory = cls.ADVISORY_MATRIX.get(cat, cls.ADVISORY_MATRIX['Poor'])
                        severity = advisory['severity']

                        title = f"{severity} AQI Alert: {station.name} ({cat})"
                        message = (
                            f"AQI at {station.name} has reached {round(aqi, 1)} ({cat}). "
                            f"Prominent pollutant: {latest_record.prominent_pollutant or 'Particulates'}."
                        )

                        recent_cutoff = now - timezone.timedelta(hours=6)
                        existing = AlertNotification.objects.filter(
                            station=station,
                            is_active=True,
                            is_forecast_alert=False,
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
                                is_forecast_alert=False,
                                is_active=True
                            )
                            created_alerts.append(alert)
                            logger.info(f"Created Observed Alert: {alert}")

            # 4. Proactive Forecast-based alerts (+3h, +6h, +24h)
            forecast_breaches = ForecastRecord.objects.filter(
                station=station,
                predicted_aqi__gte=threshold,
                horizon__in=[3, 6, 24]
            ).order_by('horizon')

            for fb in forecast_breaches:
                f_cat = fb.category
                f_aqi = fb.predicted_aqi
                f_h = fb.horizon
                advisory = cls.ADVISORY_MATRIX.get(f_cat, cls.ADVISORY_MATRIX['Poor'])
                f_severity = advisory['severity']

                f_existing = AlertNotification.objects.filter(
                    station=station,
                    is_active=True,
                    is_forecast_alert=True,
                    forecast_horizon_hours=f_h,
                    created_at__gte=now - timezone.timedelta(hours=6)
                ).exists()

                if not f_existing:
                    f_title = f"{f_severity} Predicted AQI Alert: {station.name} (+{f_h}h Forecast)"
                    f_msg = (
                        f"Machine learning forecast predicts AQI at {station.name} will reach "
                        f"{round(f_aqi, 1)} ({f_cat}) in {f_h} hours."
                    )
                    f_alert = AlertNotification.objects.create(
                        station=station,
                        title=f_title,
                        message=f_msg,
                        severity=f_severity,
                        aqi_value=round(f_aqi, 1),
                        category=f_cat,
                        health_recommendations=advisory['tips'],
                        is_forecast_alert=True,
                        forecast_horizon_hours=f_h,
                        is_active=True
                    )
                    created_alerts.append(f_alert)
                    logger.info(f"Created Forecast Alert: {f_alert}")

        # Dispatch push notifications to registered device tokens
        if created_alerts and send_push:
            try:
                from alerts.services_push import ExpoPushClient
                ExpoPushClient.send_alert_push_notifications(created_alerts)
            except Exception as e:
                logger.error(f"Error dispatching push notifications: {e}")

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
