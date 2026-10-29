from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Min, Max
from core.models import MonitoringStation
from ingestion.models import CleanMeasurement

class Command(BaseCommand):
    help = "Generates and prints a comprehensive data quality report: rows per station, % measured vs modelled, % imputed, and date coverage."

    def add_arguments(self, parser):
        parser.add_argument(
            '--station',
            type=str,
            default=None,
            help='Optional specific station ID (e.g. OPENAQ_6927)'
        )

    def handle(self, *args, **options):
        station_filter = options.get('station')
        stations_qs = MonitoringStation.objects.filter(is_active=True).order_by('name')
        if station_filter:
            stations_qs = stations_qs.filter(station_id=station_filter)

        if not stations_qs.exists():
            self.stdout.write(self.style.WARNING("No active monitoring stations found matching filter."))
            return

        self.stdout.write("\n" + "=" * 115)
        self.stdout.write(self.style.SUCCESS("                         AIRSENSE MUMBAI - DATA QUALITY REPORT"))
        self.stdout.write("=" * 115)
        header = (
            f"{'Station ID':<16} | {'Station Name':<32} | {'Rows':<7} | "
            f"{'% Measured':<10} | {'% Modelled':<10} | {'% Imputed':<9} | "
            f"{'Date Coverage (Earliest -> Latest)':<35} | {'Complete %':<10}"
        )
        self.stdout.write(header)
        self.stdout.write("-" * 140)

        total_all_rows = 0
        total_measured_rows = 0
        total_modelled_rows = 0
        total_imputed_rows = 0
        global_earliest = None
        global_latest = None

        for station in stations_qs:
            qs = CleanMeasurement.objects.filter(station=station)
            station_rows = qs.count()

            if station_rows == 0:
                self.stdout.write(
                    f"{station.station_id:<16} | {station.name[:32]:<32} | {'0':<7} | "
                    f"{'0.0%':<10} | {'0.0%':<10} | {'0.0%':<9} | "
                    f"{'NO DATA':<35} | {'0.0%':<10}"
                )
                continue

            stats = qs.aggregate(
                measured=Count('id', filter=Q(source__in=['OPENAQ_MEASURED', 'CPCB_OFFICIAL', 'WAQI_FEED'])),
                modelled=Count('id', filter=Q(source='OPEN_METEO_MODELLED')),
                imputed=Count('id', filter=Q(is_imputed=True)),
                earliest=Min('recorded_at'),
                latest=Max('recorded_at')
            )

            measured = stats['measured']
            modelled = stats['modelled']
            imputed = stats['imputed']
            earliest = stats['earliest']
            latest = stats['latest']

            total_all_rows += station_rows
            total_measured_rows += measured
            total_modelled_rows += modelled
            total_imputed_rows += imputed

            if earliest and (global_earliest is None or earliest < global_earliest):
                global_earliest = earliest
            if latest and (global_latest is None or latest > global_latest):
                global_latest = latest

            pct_measured = (measured / station_rows) * 100.0
            pct_modelled = (modelled / station_rows) * 100.0
            pct_imputed = (imputed / station_rows) * 100.0

            if earliest and latest:
                span_hours = max(1, int((latest - earliest).total_seconds() / 3600) + 1)
                completeness = min(100.0, (station_rows / span_hours) * 100.0)
                cov_str = f"{earliest.strftime('%Y-%m-%d')} -> {latest.strftime('%Y-%m-%d')}"
            else:
                completeness = 0.0
                cov_str = "N/A"

            self.stdout.write(
                f"{station.station_id:<16} | {station.name[:32]:<32} | {station_rows:<7} | "
                f"{pct_measured:>8.1f}% | {pct_modelled:>8.1f}% | {pct_imputed:>7.1f}% | "
                f"{cov_str:<35} | {completeness:>8.1f}%"
            )

        self.stdout.write("=" * 140)

        # Regional Aggregation Summary
        if total_all_rows > 0:
            overall_pct_meas = (total_measured_rows / total_all_rows) * 100.0
            overall_pct_mod = (total_modelled_rows / total_all_rows) * 100.0
            overall_pct_imp = (total_imputed_rows / total_all_rows) * 100.0
            glob_cov = (
                f"{global_earliest.strftime('%Y-%m-%d %H:%M')} to {global_latest.strftime('%Y-%m-%d %H:%M')}"
                if global_earliest and global_latest else "N/A"
            )
            self.stdout.write(self.style.SUCCESS(
                f"SUMMARY:\n"
                f"  - Total Clean Measurements:   {total_all_rows:,}\n"
                f"  - Ground Measured Records:    {total_measured_rows:,} ({overall_pct_meas:.1f}%)\n"
                f"  - Modelled Fallback Records:  {total_modelled_rows:,} ({overall_pct_mod:.1f}%)\n"
                f"  - Imputed Data Points:        {total_imputed_rows:,} ({overall_pct_imp:.1f}%)\n"
                f"  - Global Date Coverage:       {glob_cov}\n"
                f"  - Active Stations Audited:    {stations_qs.count()}"
            ))
        else:
            self.stdout.write(self.style.WARNING("No measurements recorded in CleanMeasurement table."))
        self.stdout.write("=" * 140 + "\n")
