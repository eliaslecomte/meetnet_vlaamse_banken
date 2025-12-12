"""API client for Meetnet Vlaamse Banken."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_CATALOG_URL, API_CURRENT_DATA_URL, API_TOKEN_URL

_LOGGER = logging.getLogger(__name__)


class MeetnetApiError(Exception):
    """Base exception for Meetnet API errors."""


class MeetnetAuthError(MeetnetApiError):
    """Authentication error."""


class MeetnetConnectionError(MeetnetApiError):
    """Connection error."""


@dataclass
class Location:
    """Represents a monitoring location."""

    id: str
    name: str
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass
class Parameter:
    """Represents a measurement parameter."""

    id: str
    name: str
    unit: str | None = None
    interval_minutes: int | None = None


@dataclass
class AvailableData:
    """Represents an available data combination (location + parameter)."""

    id: str
    location_id: str
    parameter_id: str


@dataclass
class Catalog:
    """Represents the full catalog response."""

    locations: dict[str, Location]
    parameters: dict[str, Parameter]
    available_data: list[AvailableData]


@dataclass
class DataValue:
    """Represents a current data value."""

    data_id: str
    location_id: str
    parameter_id: str
    value: float | None
    timestamp: datetime | None
    unit: str | None = None


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
        """Get the catalog with locations, parameters, and available data."""
        if self._catalog is not None and not force_refresh:
            return self._catalog

        data = await self._api_request(API_CATALOG_URL)

        # Parse locations
        locations: dict[str, Location] = {}
        for loc in data.get("Locations", []):
            loc_id = loc.get("ID", "")
            locations[loc_id] = Location(
                id=loc_id,
                name=loc.get("Name", loc_id),
                description=loc.get("Description"),
                latitude=loc.get("Latitude"),
                longitude=loc.get("Longitude"),
            )

        # Parse parameters
        parameters: dict[str, Parameter] = {}
        for param in data.get("Parameters", []):
            param_id = param.get("ID", "")
            parameters[param_id] = Parameter(
                id=param_id,
                name=param.get("Name", param_id),
                unit=param.get("Unit"),
                interval_minutes=param.get("CurrentInterval"),
            )

        # Parse available data combinations
        available_data: list[AvailableData] = []
        for ad in data.get("AvailableData", []):
            available_data.append(
                AvailableData(
                    id=ad.get("ID", ""),
                    location_id=ad.get("LocationID", ""),
                    parameter_id=ad.get("ParameterID", ""),
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

        Args:
            data_ids: Optional list of data IDs to filter. If None, returns all.

        Returns:
            Dictionary mapping data ID to DataValue.
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
                data_id=data_id,
                location_id=item.get("LocationID", ""),
                parameter_id=item.get("ParameterID", ""),
                value=float(value) if value is not None else None,
                timestamp=timestamp,
                unit=item.get("Unit"),
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
