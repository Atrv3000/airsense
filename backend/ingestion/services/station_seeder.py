from core.models import MonitoringStation

# Official continuous ambient air quality monitoring stations in the Mumbai Metropolitan Region
MUMBAI_STATIONS = [
    {
        "station_id": "MUM_BKC",
        "name": "Bandra Kurla Complex (BKC)",
        "latitude": 19.0657,
        "longitude": 72.8687,
        "zone_type": "COMMERCIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "MUM_COLABA",
        "name": "Colaba Coastal Observatory",
        "latitude": 18.9067,
        "longitude": 72.8147,
        "zone_type": "COASTAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "MUM_WORLI",
        "name": "Worli Central Transit Zone",
        "latitude": 19.0178,
        "longitude": 72.8177,
        "zone_type": "RESIDENTIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "MUM_KURLA",
        "name": "Kurla Mixed Traffic Junction",
        "latitude": 19.0726,
        "longitude": 72.8845,
        "zone_type": "COMMERCIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "MUM_CHEMBUR",
        "name": "Chembur Industrial Corridor",
        "latitude": 19.0522,
        "longitude": 72.8995,
        "zone_type": "INDUSTRIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "MUM_DEONAR",
        "name": "Deonar / Sion Eastern Highway",
        "latitude": 19.0433,
        "longitude": 72.9090,
        "zone_type": "INDUSTRIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "MUM_VILEPARLE",
        "name": "Vile Parle Airport Corridor",
        "latitude": 19.1006,
        "longitude": 72.8427,
        "zone_type": "RESIDENTIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "MUM_BORIVALI",
        "name": "Borivali Suburb North",
        "latitude": 19.2291,
        "longitude": 72.8617,
        "zone_type": "RESIDENTIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "MUM_MULUND",
        "name": "Mulund Central Suburb",
        "latitude": 19.1726,
        "longitude": 72.9425,
        "zone_type": "RESIDENTIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "MUM_SANPADA",
        "name": "Navi Mumbai (Sanpada / Vashi)",
        "latitude": 19.0645,
        "longitude": 73.0163,
        "zone_type": "COMMERCIAL",
        "city": "Navi Mumbai",
        "state": "Maharashtra"
    }
]

def seed_mumbai_stations():
    """
    Idempotently populates the official Mumbai monitoring stations into the database.
    """
    created_count = 0
    updated_count = 0
    stations = []

    for station_data in MUMBAI_STATIONS:
        station, created = MonitoringStation.objects.update_or_create(
            station_id=station_data["station_id"],
            defaults=station_data
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
        stations.append(station)

    return {
        "created": created_count,
        "updated": updated_count,
        "total": len(stations),
        "stations": stations
    }
