from django.db import models
from core.models import MonitoringStation
from ingestion.models import RawMeasurement

class AQIRecord(models.Model):
    """
    Stores calculated Indian National AQI (NAQI), sub-indices for each criteria pollutant,
    the prominent pollutant, and the official health category.
    """
    station = models.ForeignKey(
        MonitoringStation,
        on_delete=models.CASCADE,
        related_name='aqi_records',
        db_index=True
    )
    raw_measurement = models.OneToOneField(
        RawMeasurement,
        on_delete=models.CASCADE,
        related_name='aqi_record'
    )
    recorded_at = models.DateTimeField(db_index=True)

    # Individual Pollutant Sub-Indices (Ip)
    sub_index_pm25 = models.FloatField(null=True, blank=True, help_text="Sub-index for PM2.5")
    sub_index_pm10 = models.FloatField(null=True, blank=True, help_text="Sub-index for PM10")
    sub_index_no2 = models.FloatField(null=True, blank=True, help_text="Sub-index for NO2")
    sub_index_so2 = models.FloatField(null=True, blank=True, help_text="Sub-index for SO2")
    sub_index_co = models.FloatField(null=True, blank=True, help_text="Sub-index for CO")
    sub_index_o3 = models.FloatField(null=True, blank=True, help_text="Sub-index for O3")

    # Overall CPCB NAQI Metrics
    overall_aqi = models.FloatField(null=True, blank=True, db_index=True, help_text="max(Sub-indices)")
    prominent_pollutant = models.CharField(max_length=16, null=True, blank=True, help_text="Pollutant with highest sub-index")
    aqi_category = models.CharField(max_length=64, help_text="Good, Satisfactory, Moderate, Poor, Very Poor, Severe")
    color_hex = models.CharField(max_length=16, default="#00B050")
    valid_criteria_met = models.BooleanField(default=True, help_text="True if >=3 pollutants and PM included")

    # CPCB Data Sufficiency & Fallback Tracking
    is_instantaneous_fallback = models.BooleanField(
        default=False,
        help_text="True if any pollutant fell back to instantaneous concentration due to insufficient multi-hour history (<16h for 24h, <6h for 8h)"
    )
    data_sufficiency_flags = models.JSONField(
        default=dict,
        blank=True,
        help_text="Pollutant-specific CPCB data sufficiency metadata, valid hour counts, and averaging method used"
    )

    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['station', '-recorded_at']),
            models.Index(fields=['overall_aqi']),
        ]
        verbose_name = 'AQI Record'
        verbose_name_plural = 'AQI Records'

    def __str__(self):
        return f"{self.station.name} | AQI: {self.overall_aqi} ({self.aqi_category}) @ {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"
