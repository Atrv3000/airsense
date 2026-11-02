import os
import logging
import requests
from django.conf import settings
from core.models import MonitoringStation

logger = logging.getLogger(__name__)

# Verified real continuous ambient air quality monitoring stations in the Mumbai Metropolitan Region
# Discovered from OpenAQ v3 /locations endpoint (bounding box: 72.75 to 73.10 E, 18.85 to 19.35 N)
VERIFIED_MUMBAI_STATIONS = [
    {
        "station_id": "OPENAQ_6927",
        "name": "Colaba, Mumbai - MPCB",
        "latitude": 18.91,
        "longitude": 72.82,
        "zone_type": "COASTAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_6945",
        "name": "Kurla, Mumbai - MPCB",
        "latitude": 19.0863,
        "longitude": 72.8888,
        "zone_type": "COMMERCIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_6948",
        "name": "Chhatrapati Shivaji Intl. Airport (T2), Mumbai - MPCB",
        "latitude": 19.10078,
        "longitude": 72.87462,
        "zone_type": "COMMERCIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_6956",
        "name": "Powai, Mumbai - MPCB",
        "latitude": 19.1375,
        "longitude": 72.915056,
        "zone_type": "RESIDENTIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_6959",
        "name": "Siddharth Nagar-Worli, Mumbai - IITM",
        "latitude": 19.000083,
        "longitude": 72.813993,
        "zone_type": "RESIDENTIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_6965",
        "name": "Borivali East, Mumbai - MPCB",
        "latitude": 19.227474,
        "longitude": 72.864394,
        "zone_type": "RESIDENTIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_6967",
        "name": "Sion, Mumbai - MPCB",
        "latitude": 19.047,
        "longitude": 72.8746,
        "zone_type": "COMMERCIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_8039",
        "name": "Mumbai - US Consulate General",
        "latitude": 19.07283,
        "longitude": 72.88261,
        "zone_type": "COMMERCIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_3409328",
        "name": "Bandra Kurla Complex, Mumbai - IITM",
        "latitude": 19.0627,
        "longitude": 72.84614,
        "zone_type": "COMMERCIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_3409329",
        "name": "Deonar, Mumbai - IITM",
        "latitude": 19.04946,
        "longitude": 72.923,
        "zone_type": "INDUSTRIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_3409483",
        "name": "Chembur, Mumbai - MPCB",
        "latitude": 19.0364585,
        "longitude": 72.8954371,
        "zone_type": "INDUSTRIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_3409487",
        "name": "Sanpada, Navi Mumbai - MPCB",
        "latitude": 19.0575752,
        "longitude": 73.0151367,
        "zone_type": "COMMERCIAL",
        "city": "Navi Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_12040",
        "name": "Mulund West, Mumbai - MPCB",
        "latitude": 19.175,
        "longitude": 72.9419,
        "zone_type": "RESIDENTIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_11611",
        "name": "Malad West, Mumbai - IITM",
        "latitude": 19.19709,
        "longitude": 72.82204,
        "zone_type": "RESIDENTIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_12024",
        "name": "Chakala-Andheri East, Mumbai - IITM",
        "latitude": 19.11074,
        "longitude": 72.86084,
        "zone_type": "COMMERCIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    },
    {
        "station_id": "OPENAQ_3409514",
        "name": "Ghatkopar, Mumbai - BMC",
        "latitude": 19.083694,
        "longitude": 72.920967,
        "zone_type": "RESIDENTIAL",
        "city": "Mumbai",
        "state": "Maharashtra"
    }
]


def seed_mumbai_stations(discover_from_api: bool = False):
    """
    Idempotently populates verified Mumbai monitoring stations discovered via OpenAQ.
    If discover_from_api=True and OPENAQ_API_KEY is available, queries OpenAQ v3 /locations
    around the Mumbai bounding box to register newly active stations automatically.
    """
    created_count = 0
    updated_count = 0
    stations = []

    station_list = list(VERIFIED_MUMBAI_STATIONS)

    if discover_from_api:
        api_key = os.getenv("OPENAQ_API_KEY", "")
        base_url = os.getenv("OPENAQ_API_BASE", "https://api.openaq.org/v3")
        if api_key:
            try:
                headers = {"X-API-Key": api_key}
                params = {
                    "bbox": "72.75,18.85,73.10,19.35",
                    "limit": 100
                }
                res = requests.get(f"{base_url}/locations", headers=headers, params=params, timeout=10)
                if res.status_code == 200:
                    results = res.json().get("results", [])
                    for loc in results:
                        loc_id = loc.get("id")
                        coords = loc.get("coordinates", {})
                        lat = coords.get("latitude")
                        lon = coords.get("longitude")
                        name = loc.get("name", f"Station {loc_id}")
                        if loc_id and lat and lon:
                            st_dict = {
                                "station_id": f"OPENAQ_{loc_id}",
                                "name": name,
                                "latitude": float(lat),
                                "longitude": float(lon),
                                "zone_type": "RESIDENTIAL",
                                "city": "Mumbai",
                                "state": "Maharashtra"
                            }
                            # Replace or add
                            if not any(s["station_id"] == st_dict["station_id"] for s in station_list):
                                station_list.append(st_dict)
            except Exception as e:
                logger.warning(f"Dynamic OpenAQ station discovery failed: {e}. Using verified list.")

    for station_data in station_list:
        station, created = MonitoringStation.objects.update_or_create(
            station_id=station_data["station_id"],
            defaults=station_data
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
        stations.append(station)

    logger.info(f"Seeded {len(stations)} verified Mumbai monitoring stations ({created_count} created, {updated_count} updated).")
    return {
        "created": created_count,
        "updated": updated_count,
        "total": len(stations),
        "stations": stations
    }
