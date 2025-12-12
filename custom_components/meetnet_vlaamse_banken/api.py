"""API client for Meetnet Vlaamse Banken.

API Documentation: See docs/API_SCHEMA.md for full schema details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import re
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_CATALOG_URL, API_CURRENT_DATA_URL, API_TOKEN_URL

_LOGGER = logging.getLogger(__name__)

# Default language for extracting names from MessageModelList
DEFAULT_LANGUAGE = "en"
FALLBACK_LANGUAGE = "nl"


class MeetnetApiError(Exception):
    """Base exception for Meetnet API errors."""


class MeetnetAuthError(MeetnetApiError):
    """Authentication error."""


class MeetnetConnectionError(MeetnetApiError):
    """Connection error."""


def extract_message(message_list: list[dict[str, str]] | None, default: str = "") -> str:
    """Extract a message from a MessageModelList.

    MessageModelList format: [{"Culture": "nl", "Message": "Dutch"}, {"Culture": "en", "Message": "English"}]
    """
    if not message_list:
        return default

    if not isinstance(message_list, list):
        # If it's already a string, return it
        if isinstance(message_list, str):
            return message_list
        return default

    # Try preferred language first
    for item in message_list:
        if isinstance(item, dict) and item.get("Culture") == DEFAULT_LANGUAGE:
            return item.get("Message", default)

    # Try fallback language
    for item in message_list:
        if isinstance(item, dict) and item.get("Culture") == FALLBACK_LANGUAGE:
            return item.get("Message", default)

    # Return first available message
    for item in message_list:
        if isinstance(item, dict) and "Message" in item:
            return item.get("Message", default)

    return default


@dataclass
class Location:
    """Represents a monitoring location."""

    id: str  # LocationKey: 3 alphanumeric chars (e.g., "NPT")
    name: str
    description: str | None = None
    position_wkt: str | None = None  # WKT format position


@dataclass
class Parameter:
    """Represents a measurement parameter."""

    id: str  # ParameterKey: 3 alphanumeric chars (e.g., "WVC")
    name: str
    unit: str | None = None
    parameter_type_id: int | None = None


@dataclass
class AvailableData:
    """Represents an available data combination (location + parameter)."""

    id: str  # LocationParameterKey: 6 alphanumeric chars (e.g., "NPTWVC")
    location_id: str  # LocationKey
    parameter_id: str  # ParameterKey
    current_interval: int | None = None  # Interval in minutes


@dataclass
class Catalog:
    """Represents the full catalog response."""

    locations: dict[str, Location]
    parameters: dict[str, Parameter]
    available_data: list[AvailableData]


@dataclass
class DataValue:
    """Represents a current data value."""

    id: str  # LocationParameterKey
    value: float | None
    timestamp: datetime | None


class MeetnetApiClient:
    """Client for the Meetnet Vlaamse Banken API."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._session = session
        self._access_token: str | None = None
        self._token_expires: datetime | None = None
        self._catalog: Catalog | None = None
        self._owns_session = session is None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _authenticate(self) -> None:
        """Authenticate and obtain an access token."""
        session = await self._ensure_session()

        data = {
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
        }

        try:
            async with session.post(
                API_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if response.status == 400:
                    error_data = await response.json()
                    error_msg = error_data.get("error_description", "Invalid credentials")
                    raise MeetnetAuthError(error_msg)

                if response.status != 200:
                    raise MeetnetAuthError(f"Authentication failed with status {response.status}")

                result = await response.json()
                self._access_token = result["access_token"]
                expires_in = result.get("expires_in", 3600)
                # Set expiry slightly early to avoid edge cases
                self._token_expires = datetime.now() + timedelta(seconds=expires_in - 60)
                _LOGGER.debug("Successfully authenticated, token expires in %s seconds", expires_in)

        except aiohttp.ClientError as err:
            raise MeetnetConnectionError(f"Connection error during authentication: {err}") from err

    async def _ensure_authenticated(self) -> str:
        """Ensure we have a valid access token."""
        if (
            self._access_token is None
            or self._token_expires is None
            or datetime.now() >= self._token_expires
        ):
            await self._authenticate()

        return self._access_token  # type: ignore[return-value]

    async def _get_headers(self) -> dict[str, str]:
        """Get headers with authentication."""
        token = await self._ensure_authenticated()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def _api_request(self, url: str, method: str = "GET", **kwargs: Any) -> Any:
        """Make an authenticated API request."""
        session = await self._ensure_session()
        headers = await self._get_headers()

        try:
            async with session.request(method, url, headers=headers, **kwargs) as response:
                if response.status == 401:
                    # Token might have expired, try to re-authenticate once
                    self._access_token = None
                    headers = await self._get_headers()
                    async with session.request(method, url, headers=headers, **kwargs) as retry_response:
                        if retry_response.status == 401:
                            raise MeetnetAuthError("Authentication failed after retry")
                        retry_response.raise_for_status()
                        return await retry_response.json()

                response.raise_for_status()
                return await response.json()

        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise MeetnetAuthError("Authentication failed") from err
            raise MeetnetConnectionError(f"API request failed: {err}") from err
        except aiohttp.ClientError as err:
            raise MeetnetConnectionError(f"Connection error: {err}") from err

    async def validate_credentials(self) -> bool:
        """Validate the credentials by attempting to authenticate."""
        try:
            await self._authenticate()
            return True
        except MeetnetAuthError:
            return False

    async def get_catalog(self, force_refresh: bool = False) -> Catalog:
        """Get the catalog with locations, parameters, and available data.

        API Response structure (see docs/API_SCHEMA.md):
        - Locations[]: ID, Name (MessageModelList), Description (MessageModelList), PositionWKT
        - Parameters[]: ID, Name (MessageModelList), Unit, ParameterTypeID
        - AvailableData[]: ID, Location, Parameter, CurrentInterval
        """
        if self._catalog is not None and not force_refresh:
            return self._catalog

        data = await self._api_request(API_CATALOG_URL)

        # Parse locations
        locations: dict[str, Location] = {}
        for loc in data.get("Locations", []):
            loc_id = loc.get("ID", "")
            locations[loc_id] = Location(
                id=loc_id,
                name=extract_message(loc.get("Name"), loc_id),
                description=extract_message(loc.get("Description")),
                position_wkt=loc.get("PositionWKT"),
            )

        # Parse parameters
        parameters: dict[str, Parameter] = {}
        for param in data.get("Parameters", []):
            param_id = param.get("ID", "")
            parameters[param_id] = Parameter(
                id=param_id,
                name=extract_message(param.get("Name"), param_id),
                unit=param.get("Unit"),
                parameter_type_id=param.get("ParameterTypeID"),
            )

        # Parse available data combinations
        # Note: Field names are "Location" and "Parameter", not "LocationID" and "ParameterID"
        available_data: list[AvailableData] = []
        for ad in data.get("AvailableData", []):
            available_data.append(
                AvailableData(
                    id=ad.get("ID", ""),
                    location_id=ad.get("Location", ""),
                    parameter_id=ad.get("Parameter", ""),
                    current_interval=ad.get("CurrentInterval"),
                )
            )

        self._catalog = Catalog(
            locations=locations,
            parameters=parameters,
            available_data=available_data,
        )

        _LOGGER.debug(
            "Loaded catalog with %d locations, %d parameters, %d available data",
            len(locations),
            len(parameters),
            len(available_data),
        )

        return self._catalog

    async def get_current_data(
        self, data_ids: list[str] | None = None
    ) -> dict[str, DataValue]:
        """Get current data values.

        API Response structure (see docs/API_SCHEMA.md):
        - Values[]: ID (LocationParameterKey), Timestamp, Value

        Args:
            data_ids: Optional list of LocationParameterKeys to filter. If None, returns all.

        Returns:
            Dictionary mapping LocationParameterKey to DataValue.
        """
        url = API_CURRENT_DATA_URL
        if data_ids:
            # API supports filtering via query parameter
            ids_param = ",".join(data_ids)
            url = f"{url}?ids={ids_param}"

        data = await self._api_request(url)

        result: dict[str, DataValue] = {}
        for item in data.get("Values", []):
            data_id = item.get("ID", "")
            value = item.get("Value")
            timestamp_str = item.get("Timestamp")
            timestamp = None
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except ValueError:
                    _LOGGER.warning("Could not parse timestamp: %s", timestamp_str)

            result[data_id] = DataValue(
                id=data_id,
                value=float(value) if value is not None else None,
                timestamp=timestamp,
            )

        return result

    def get_available_data_for_locations(
        self, location_ids: list[str]
    ) -> list[AvailableData]:
        """Get available data for specific locations."""
        if self._catalog is None:
            return []

        return [
            ad
            for ad in self._catalog.available_data
            if ad.location_id in location_ids
        ]
