from django.db import models
from django.utils import timezone
from core.models import MonitoringStation

class AlertNotification(models.Model):
    """
    Persisted alert notification generated when station or city AQI
    breaches regulatory or user-configured health thresholds.
    """
    SEVERITY_LEVELS = [
        ('INFO', 'Information / Moderate'),
        ('WARNING', 'Warning / Poor'),
        ('CRITICAL', 'Critical / Very Poor'),
        ('EMERGENCY', 'Emergency / Severe'),
    ]

    station = models.ForeignKey(
        MonitoringStation,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True,
        help_text="Associated station or null for city-wide alerts"
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='WARNING')
    aqi_value = models.FloatField(help_text="AQI reading triggering this alert")
    category = models.CharField(max_length=50)
    prominent_pollutant = models.CharField(max_length=20, null=True, blank=True)
    is_forecast_alert = models.BooleanField(default=False, help_text="True if generated from predicted AQI breach")
    forecast_horizon_hours = models.IntegerField(null=True, blank=True, help_text="Forecast horizon (+3, +6, +24h)")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when alert auto-resolved")
    is_active = models.BooleanField(default=True, db_index=True)
    health_recommendations = models.JSONField(default=list, help_text="Specific actionable advisory points")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['severity', 'created_at']),
            models.Index(fields=['is_active', 'station']),
        ]

    def __str__(self):
        st_name = self.station.name if self.station else "Mumbai City-Wide"
        tag = f"Forecast +{self.forecast_horizon_hours}h" if self.is_forecast_alert else "Observed"
        return f"[{self.severity}] ({tag}) {st_name} - AQI {self.aqi_value} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class DeviceToken(models.Model):
    """
    Stores anonymous mobile client push notification tokens (Expo Push Tokens).
    No private email/phone listing exposed.
    """
    PLATFORM_CHOICES = [
        ('IOS', 'Apple iOS'),
        ('ANDROID', 'Google Android'),
        ('WEB', 'Web Browser'),
    ]

    token = models.CharField(max_length=255, unique=True, db_index=True)
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES, default='ANDROID')
    station = models.ForeignKey(
        MonitoringStation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Optional station preference or null for all city alerts"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Device Token'
        verbose_name_plural = 'Device Tokens'

    def __str__(self):
        return f"DeviceToken ({self.platform}): {self.token[:12]}..."
