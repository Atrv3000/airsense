from django.db import models
from core.models import MonitoringStation

class RawMeasurement(models.Model):
    """
    Stores timestamped pollutant concentrations and meteorological parameters
    collected from monitoring stations and weather APIs.
    """
    station = models.ForeignKey(
        MonitoringStation,
        on_delete=models.CASCADE,
        related_name='raw_measurements',
        db_index=True
    )
    recorded_at = models.DateTimeField(
        db_index=True,
        help_text="Timestamp of the observation in UTC/IST"
    )

    # Core Air Pollutants (CPCB Criteria Pollutants)
    pm25 = models.FloatField(null=True, blank=True, help_text="PM2.5 concentration in ug/m3")
    pm10 = models.FloatField(null=True, blank=True, help_text="PM10 concentration in ug/m3")
    no2 = models.FloatField(null=True, blank=True, help_text="NO2 concentration in ug/m3")
    so2 = models.FloatField(null=True, blank=True, help_text="SO2 concentration in ug/m3")
    co = models.FloatField(null=True, blank=True, help_text="CO concentration in mg/m3")
    o3 = models.FloatField(null=True, blank=True, help_text="Ozone concentration in ug/m3")

    # Meteorological Dispersion Parameters
    temperature = models.FloatField(null=True, blank=True, help_text="Ambient temperature in °C")
    humidity = models.FloatField(null=True, blank=True, help_text="Relative humidity in %")
    wind_speed = models.FloatField(null=True, blank=True, help_text="Wind speed at 10m in km/h")
    wind_direction = models.FloatField(null=True, blank=True, help_text="Wind direction in degrees (0-360)")

    # Metadata & Quality Control
    source = models.CharField(max_length=64, default="OPENAQ_METEO_HYBRID")
    is_validated = models.BooleanField(default=False)
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        unique_together = ('station', 'recorded_at')
        indexes = [
            models.Index(fields=['station', '-recorded_at']),
        ]
        verbose_name = 'Raw Measurement'
        verbose_name_plural = 'Raw Measurements'

    def __str__(self):
        return f"{self.station.name} @ {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"
