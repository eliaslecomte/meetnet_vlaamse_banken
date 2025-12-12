"""Sensor platform for Meetnet Vlaamse Banken."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfPressure,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MeetnetDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Mapping of parameter IDs to sensor configuration
# Based on common Meetnet parameters
PARAMETER_CONFIG: dict[str, dict[str, Any]] = {
    # Wind parameters
    "WVC": {
        "name": "Wind Speed",
        "device_class": SensorDeviceClass.WIND_SPEED,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit": UnitOfSpeed.METERS_PER_SECOND,
        "icon": "mdi:weather-windy",
    },
    "WRS": {
        "name": "Wind Direction",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit": DEGREE,
        "icon": "mdi:compass",
    },
    "WC3": {
        "name": "Wind Gust",
        "device_class": SensorDeviceClass.WIND_SPEED,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit": UnitOfSpeed.METERS_PER_SECOND,
        "icon": "mdi:weather-windy-variant",
    },
    "WC1": {
        "name": "Wind Speed (1 min avg)",
        "device_class": SensorDeviceClass.WIND_SPEED,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit": UnitOfSpeed.METERS_PER_SECOND,
        "icon": "mdi:weather-windy",
    },
    # Temperature
    "WT": {
        "name": "Water Temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer-water",
    },
    "LT": {
        "name": "Air Temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
    },
    # Pressure
    "LP": {
        "name": "Air Pressure",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit": UnitOfPressure.HPA,
        "icon": "mdi:gauge",
    },
    # Water level
    "WL": {
        "name": "Water Level",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit": UnitOfLength.METERS,
        "icon": "mdi:waves",
    },
    # Wave height
    "GH": {
        "name": "Wave Height",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit": UnitOfLength.METERS,
        "icon": "mdi:wave",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meetnet Vlaamse Banken sensors from a config entry."""
    coordinator: MeetnetDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities: list[MeetnetSensor] = []

    # Create sensors for each available data point in selected locations
    for location_id in coordinator.selected_locations:
        available_data = coordinator.get_available_data_for_location(location_id)

        for data in available_data:
            entities.append(
                MeetnetSensor(
                    coordinator=coordinator,
                    data_id=data.id,
                    location_id=location_id,
                    parameter_id=data.parameter_id,
                )
            )

    _LOGGER.debug("Setting up %d sensor entities", len(entities))
    async_add_entities(entities)


class MeetnetSensor(CoordinatorEntity[MeetnetDataUpdateCoordinator], SensorEntity):
    """Representation of a Meetnet Vlaamse Banken sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MeetnetDataUpdateCoordinator,
        data_id: str,
        location_id: str,
        parameter_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._data_id = data_id
        self._location_id = location_id
        self._parameter_id = parameter_id

        # Get location and parameter info
        location_name = coordinator.get_location_name(location_id)
        parameter_name = coordinator.get_parameter_name(parameter_id)

        # Set unique ID
        self._attr_unique_id = f"{DOMAIN}_{data_id}"

        # Configure based on parameter type
        config = PARAMETER_CONFIG.get(parameter_id, {})

        # Set entity name (will be combined with device name)
        self._attr_name = config.get("name", parameter_name)

        # Set device class and state class for proper history/statistics
        self._attr_device_class = config.get("device_class")
        self._attr_state_class = config.get("state_class", SensorStateClass.MEASUREMENT)

        # Set unit - use API unit if available, otherwise from config
        api_unit = coordinator.get_parameter_unit(parameter_id)
        self._attr_native_unit_of_measurement = config.get("native_unit", api_unit)

        # Set icon
        self._attr_icon = config.get("icon", "mdi:chart-line")

        # Set device info - group sensors by location
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, location_id)},
            name=location_name,
            manufacturer="Meetnet Vlaamse Banken",
            model="Monitoring Station",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        data_value = self.coordinator.data.get(self._data_id)
        if data_value is None:
            return None

        return data_value.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {
            "data_id": self._data_id,
            "location_id": self._location_id,
            "parameter_id": self._parameter_id,
        }

        if self.coordinator.data:
            data_value = self.coordinator.data.get(self._data_id)
            if data_value and data_value.timestamp:
                attrs["measurement_time"] = data_value.timestamp.isoformat()

        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False

        # Check if we have data for this sensor
        if self.coordinator.data is None:
            return False

        return self._data_id in self.coordinator.data
