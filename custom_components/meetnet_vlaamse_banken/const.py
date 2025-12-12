"""Constants for the Meetnet Vlaamse Banken integration."""

from datetime import timedelta

DOMAIN = "meetnet_vlaamse_banken"

# API
API_BASE_URL = "https://api.meetnetvlaamsebanken.be"
API_TOKEN_URL = f"{API_BASE_URL}/Token"
API_CATALOG_URL = f"{API_BASE_URL}/V2/catalog"
API_CURRENT_DATA_URL = f"{API_BASE_URL}/V2/currentData"

# Config keys
CONF_LOCATIONS = "locations"

# Defaults
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

# Sensor types with their device classes and units
SENSOR_TYPES = {
    "WVC": {  # Wind speed
        "name": "Wind Speed",
        "device_class": "wind_speed",
        "unit": "m/s",
        "icon": "mdi:weather-windy",
    },
    "WRS": {  # Wind direction
        "name": "Wind Direction",
        "device_class": None,
        "unit": "°",
        "icon": "mdi:compass",
    },
    "WC3": {  # Wind gust
        "name": "Wind Gust",
        "device_class": "wind_speed",
        "unit": "m/s",
        "icon": "mdi:weather-windy-variant",
    },
}
