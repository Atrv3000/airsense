from django.db import models
from core.models import MonitoringStation

class RawMeasurement(models.Model):
    """
    Raw ingested values directly from external APIs (OpenAQ or Open-Meteo).
    Keeps unchanged measurements before any cleaning or imputation.
    """
    SOURCE_CHOICES = [
        ('CPCB_OFFICIAL', 'Central Pollution Control Board Official CAAQMS'),
        ('WAQI_FEED', 'World Air Quality Index (WAQI / aqicn) Feed'),
        ('OPENAQ_MEASURED', 'OpenAQ Ground Station Measured'),
        ('OPEN_METEO_MODELLED', 'Open-Meteo Modelled / Fallback'),
    ]

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
    source = models.CharField(max_length=64, choices=SOURCE_CHOICES, default="OPENAQ_MEASURED")
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
        return f"{self.station.name} @ {self.recorded_at.strftime('%Y-%m-%d %H:%M')} ({self.source})"


class CleanMeasurement(models.Model):
    """
    Cleaned, range-checked, and quality-controlled pollutant and weather measurements.
    Preprocessed from RawMeasurement.
    """
    SOURCE_CHOICES = [
        ('CPCB_OFFICIAL', 'Central Pollution Control Board Official CAAQMS'),
        ('WAQI_FEED', 'World Air Quality Index (WAQI / aqicn) Feed'),
        ('OPENAQ_MEASURED', 'OpenAQ Ground Station Measured'),
        ('OPEN_METEO_MODELLED', 'Open-Meteo Modelled / Fallback'),
    ]

    station = models.ForeignKey(
        MonitoringStation,
        on_delete=models.CASCADE,
        related_name='clean_measurements',
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

    # Data Quality & Imputation Tracking
    source = models.CharField(max_length=64, choices=SOURCE_CHOICES, default="OPENAQ_MEASURED")
    is_imputed = models.BooleanField(default=False, help_text="True if any value was interpolated")
    imputed_fields = models.JSONField(default=list, blank=True, help_text="List of pollutant field names that were interpolated")
    raw_measurement = models.OneToOneField(
        RawMeasurement,
        on_delete=models.CASCADE,
        related_name='clean_measurement',
        null=True,
        blank=True
    )
    cleaned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        unique_together = ('station', 'recorded_at')
        indexes = [
            models.Index(fields=['station', '-recorded_at']),
        ]
        verbose_name = 'Clean Measurement'
        verbose_name_plural = 'Clean Measurements'

    def __str__(self):
        return f"{self.station.name} Clean @ {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"
