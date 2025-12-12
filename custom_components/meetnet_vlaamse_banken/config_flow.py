"""Config flow for Meetnet Vlaamse Banken integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MeetnetApiClient, MeetnetAuthError, MeetnetConnectionError
from .const import CONF_LOCATIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MeetnetVlaamseBankenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meetnet Vlaamse Banken."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._password: str | None = None
        self._api_client: MeetnetApiClient | None = None
        self._locations: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - credentials entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            session = async_get_clientsession(self.hass)
            self._api_client = MeetnetApiClient(
                username=self._username,
                password=self._password,
                session=session,
            )

            try:
                if await self._api_client.validate_credentials():
                    # Fetch catalog to get available locations
                    catalog = await self._api_client.get_catalog()
                    self._locations = {
                        loc_id: loc.name
                        for loc_id, loc in catalog.locations.items()
                    }
                    return await self.async_step_locations()
                else:
                    errors["base"] = "invalid_auth"
            except MeetnetConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_locations(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle location selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_locations = user_input.get(CONF_LOCATIONS, [])

            if not selected_locations:
                errors["base"] = "no_locations_selected"
            else:
                # Create the config entry
                await self.async_set_unique_id(self._username)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Meetnet ({self._username})",
                    data={
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: self._password,
                        CONF_LOCATIONS: selected_locations,
                    },
                )

        # Sort locations by name for better UX
        sorted_locations = dict(
            sorted(self._locations.items(), key=lambda x: x[1])
        )

        return self.async_show_form(
            step_id="locations",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATIONS): vol.All(
                        cv.multi_select(sorted_locations),
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "location_count": str(len(self._locations)),
            },
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api_client = MeetnetApiClient(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=session,
            )

            try:
                if await api_client.validate_credentials():
                    # Update the existing entry
                    entry = self.hass.config_entries.async_get_entry(
                        self.context["entry_id"]
                    )
                    if entry:
                        self.hass.config_entries.async_update_entry(
                            entry,
                            data={
                                **entry.data,
                                CONF_USERNAME: user_input[CONF_USERNAME],
                                CONF_PASSWORD: user_input[CONF_PASSWORD],
                            },
                        )
                        await self.hass.config_entries.async_reload(entry.entry_id)
                        return self.async_abort(reason="reauth_successful")
                else:
                    errors["base"] = "invalid_auth"
            except MeetnetConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return MeetnetOptionsFlowHandler(config_entry)


class MeetnetOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Meetnet Vlaamse Banken."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._locations: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        # Get the API client from hass.data
        if DOMAIN not in self.hass.data:
            return self.async_abort(reason="not_set_up")

        entry_data = self.hass.data[DOMAIN].get(self.config_entry.entry_id)
        if not entry_data:
            return self.async_abort(reason="not_set_up")

        api_client: MeetnetApiClient = entry_data["api"]

        if user_input is not None:
            selected_locations = user_input.get(CONF_LOCATIONS, [])

            if not selected_locations:
                errors["base"] = "no_locations_selected"
            else:
                # Update the config entry
                new_data = {**self.config_entry.data, CONF_LOCATIONS: selected_locations}
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )
                return self.async_create_entry(title="", data={})

        # Fetch current catalog
        try:
            catalog = await api_client.get_catalog()
            self._locations = {
                loc_id: loc.name for loc_id, loc in catalog.locations.items()
            }
        except Exception:
            _LOGGER.exception("Failed to fetch catalog for options")
            return self.async_abort(reason="cannot_connect")

        # Sort locations by name
        sorted_locations = dict(
            sorted(self._locations.items(), key=lambda x: x[1])
        )

        # Get currently selected locations
        current_locations = self.config_entry.data.get(CONF_LOCATIONS, [])

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCATIONS, default=current_locations
                    ): cv.multi_select(sorted_locations),
                }
            ),
            errors=errors,
        )


# Import cv here to avoid circular imports
import homeassistant.helpers.config_validation as cv
