from django.db import models
from core.models import MonitoringStation

class ForecastRecord(models.Model):
    """
    Stores precomputed multi-horizon AQI forecasts for monitoring stations.
    Precomputed after ingestion so APIs and maps read directly from this table
    without running slow real-time inference on each request.
    """
    station = models.ForeignKey(
        MonitoringStation,
        on_delete=models.CASCADE,
        related_name='forecast_records',
        db_index=True
    )
    made_at = models.DateTimeField(db_index=True, help_text="Timestamp when the forecast was computed")
    target_time = models.DateTimeField(db_index=True, help_text="Future timestamp being predicted")
    horizon = models.IntegerField(help_text="Forecast horizon step in hours (+1, +3, +6, +24, etc.)")
    predicted_aqi = models.FloatField(help_text="Predicted numerical AQI")
    category = models.CharField(max_length=64, default="Moderate")
    color_hex = models.CharField(max_length=16, default="#FFFF00")
    expected_error_band = models.FloatField(default=15.0, help_text="Uncertainty residual interval (+/-) derived from validation")
    model_version = models.CharField(max_length=64, default="Random_Forest_v1")

    class Meta:
        ordering = ['station', 'target_time']
        unique_together = ('station', 'made_at', 'horizon')
        indexes = [
            models.Index(fields=['station', 'target_time']),
            models.Index(fields=['target_time', 'horizon']),
        ]
        verbose_name = 'Forecast Record'
        verbose_name_plural = 'Forecast Records'

    def __str__(self):
        return f"{self.station.name} | +{self.horizon}h -> {self.predicted_aqi} AQI @ {self.target_time.strftime('%Y-%m-%d %H:%M')}"
