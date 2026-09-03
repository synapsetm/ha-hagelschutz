"""Config flow for the Hagelschutz integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_ID, CONF_HWTYPE_ID, DOMAIN
from .coordinator import CannotConnect, HagelschutzApiError, InvalidDevice, async_poll

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_HWTYPE_ID): int,
    }
)


class HagelschutzConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow. There is no options flow — nothing is tunable."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for device ID and hardware type, then verify them with one poll."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            hwtype_id = user_input[CONF_HWTYPE_ID]

            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            try:
                await async_poll(session, device_id, hwtype_id)
            except InvalidDevice:
                errors["base"] = "invalid_device"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except HagelschutzApiError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected error while validating the device")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Hagelschutz {device_id}",
                    data={
                        CONF_DEVICE_ID: device_id,
                        CONF_HWTYPE_ID: hwtype_id,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
