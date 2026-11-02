"""
Shared Ingestion and Source Priority Constants for AirSense.
Centralizes ground measurement source definitions, hierarchy, and classification rules.
"""

SOURCE_CPCB = 'CPCB_OFFICIAL'
SOURCE_OPENAQ = 'OPENAQ_MEASURED'
SOURCE_WAQI = 'WAQI_FEED'
SOURCE_OPEN_METEO = 'OPEN_METEO_MODELLED'

# Source Priority at identical observation timestamp:
# CPCB_OFFICIAL > OPENAQ_MEASURED > WAQI_FEED > OPEN_METEO_MODELLED
SOURCE_PRIORITY = {
    SOURCE_CPCB: 4,
    SOURCE_OPENAQ: 3,
    SOURCE_WAQI: 2,
    SOURCE_OPEN_METEO: 1,
}

# Ground-measured source categories (never to be overwritten by modelled observations)
GROUND_SOURCES = (SOURCE_CPCB, SOURCE_OPENAQ, SOURCE_WAQI)

def get_source_priority(source: str) -> int:
    """Returns numerical rank for source comparison (higher is higher priority)."""
    return SOURCE_PRIORITY.get(source, 0)

def is_ground_source(source: str) -> bool:
    """Returns True if source represents physical CAAQMS or ground sensor observations."""
    return source in GROUND_SOURCES

def should_override_source(existing_source: str, incoming_source: str) -> bool:
    """
    Evaluates whether incoming source has higher priority than existing record.
    Prevents lower-priority modelled observations from overriding higher-priority ground data.
    """
    return get_source_priority(incoming_source) > get_source_priority(existing_source)
