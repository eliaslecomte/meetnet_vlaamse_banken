"""Data update coordinator for Meetnet Vlaamse Banken."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AvailableData,
    Catalog,
    DataValue,
    MeetnetApiClient,
    MeetnetAuthError,
    MeetnetConnectionError,
)
from .const import CONF_LOCATIONS, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MeetnetDataUpdateCoordinator(DataUpdateCoordinator[dict[str, DataValue]]):
    """Class to manage fetching Meetnet data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: MeetnetApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api_client = api_client
        self.config_entry = config_entry
        self._catalog: Catalog | None = None
        self._available_data_ids: list[str] = []

    @property
    def catalog(self) -> Catalog | None:
        """Return the cached catalog."""
        return self._catalog

    @property
    def selected_locations(self) -> list[str]:
        """Return the selected location IDs."""
        return self.config_entry.data.get(CONF_LOCATIONS, [])

    async def async_setup(self) -> None:
        """Set up the coordinator by fetching the catalog."""
        try:
            self._catalog = await self.api_client.get_catalog()

            # Get available data IDs for selected locations
            available_data = self.api_client.get_available_data_for_locations(
                self.selected_locations
            )
            self._available_data_ids = [ad.id for ad in available_data]

            _LOGGER.debug(
                "Coordinator setup complete: %d data points for %d locations",
                len(self._available_data_ids),
                len(self.selected_locations),
            )
        except MeetnetAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except MeetnetConnectionError as err:
            raise UpdateFailed(f"Failed to fetch catalog: {err}") from err

    async def _async_update_data(self) -> dict[str, DataValue]:
        """Fetch data from API."""
        try:
            # Fetch current data for our available data IDs
            data = await self.api_client.get_current_data(self._available_data_ids)
            _LOGGER.debug("Fetched %d data values", len(data))
            return data
        except MeetnetAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except MeetnetConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching data")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def get_available_data_for_location(
        self, location_id: str
    ) -> list[AvailableData]:
        """Get available data entries for a specific location."""
        if self._catalog is None:
            return []

        return [
            ad
            for ad in self._catalog.available_data
            if ad.location_id == location_id
        ]

    def get_location_name(self, location_id: str) -> str:
        """Get the name of a location."""
        if self._catalog and location_id in self._catalog.locations:
            return self._catalog.locations[location_id].name
        return location_id

    def get_parameter_name(self, parameter_id: str) -> str:
        """Get the name of a parameter."""
        if self._catalog and parameter_id in self._catalog.parameters:
            return self._catalog.parameters[parameter_id].name
        return parameter_id

    def get_parameter_unit(self, parameter_id: str) -> str | None:
        """Get the unit of a parameter."""
        if self._catalog and parameter_id in self._catalog.parameters:
            return self._catalog.parameters[parameter_id].unit
        return None
