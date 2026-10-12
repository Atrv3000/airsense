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
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_active = models.BooleanField(default=True)
    health_recommendations = models.JSONField(default=list, help_text="Specific actionable advisory points")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['severity', 'created_at']),
        ]

    def __str__(self):
        st_name = self.station.name if self.station else "Mumbai City-Wide"
        return f"[{self.severity}] {st_name} - AQI {self.aqi_value} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class UserAlertSubscription(models.Model):
    """
    User notification preferences for proactive email/webhook or mobile alerts.
    """
    email = models.EmailField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    station = models.ForeignKey(
        MonitoringStation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Subscribed station or null for all city alerts"
    )
    threshold_aqi = models.FloatField(default=200.0, help_text="Notify when AQI >= this value (Default: Poor threshold 200)")
    notify_sms = models.BooleanField(default=False)
    notify_email = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        target = self.email or self.phone_number or "Anonymous"
        return f"Subscription: {target} (Threshold: AQI {self.threshold_aqi})"
