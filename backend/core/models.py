from django.db import models

class MonitoringStation(models.Model):
    """
    Represents an ambient air quality monitoring station in the Mumbai region.
    """
    ZONE_CHOICES = [
        ('COMMERCIAL', 'Commercial Area'),
        ('INDUSTRIAL', 'Industrial Area'),
        ('RESIDENTIAL', 'Residential Area'),
        ('COASTAL', 'Coastal / Marine Area'),
    ]

    station_id = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    latitude = models.FloatField(help_text="Latitude in decimal degrees (e.g., 19.0657)")
    longitude = models.FloatField(help_text="Longitude in decimal degrees (e.g., 72.8687)")
    zone_type = models.CharField(max_length=32, choices=ZONE_CHOICES, default='RESIDENTIAL')
    city = models.CharField(max_length=64, default="Mumbai")
    state = models.CharField(max_length=64, default="Maharashtra")
    is_active = models.BooleanField(default=True)
    last_ground_observation_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of most recent verified ground observation")
    consecutive_stale_cycles = models.IntegerField(default=0, help_text="Consecutive scheduler cycles where ground data was stale (>GROUND_MAX_AGE_HOURS)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Monitoring Station'
        verbose_name_plural = 'Monitoring Stations'

    def __str__(self):
        return f"{self.name} ({self.station_id})"
