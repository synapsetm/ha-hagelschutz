"""Config flow for the Hagelschutz integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DEVICE_ID,
    CONF_HWTYPE_ID,
    DEVICE_ID_LENGTH,
    DEVICE_ID_SEPARATORS,
    DOMAIN,
)
from .coordinator import (
    CannotConnect,
    HagelschutzApiError,
    InvalidDevice,
    InvalidParameters,
    async_poll,
)

_LOGGER = logging.getLogger(__name__)

def normalize_device_id(value: str) -> str:
    """Strip separators and the invisible characters a paste tends to carry."""
    for separator in DEVICE_ID_SEPARATORS:
        value = value.replace(separator, "")
    return value.strip()


def parse_hwtype_id(value: Any) -> int:
    """Read the hardware type out of the text field.

    Raises ValueError if it is not a whole number.
    """
    return int(str(value).strip())


# Both fields are text on purpose. A schema-level ``int`` renders as a number
# box that Home Assistant pre-fills with 0, and typing a value next to that
# zero silently produces a different number (188 next to 0 becomes 1880).
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): selector.TextSelector(),
        vol.Required(CONF_HWTYPE_ID): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.NUMBER)
        ),
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
            device_id = normalize_device_id(user_input[CONF_DEVICE_ID])
            hwtype_id = 0

            if len(device_id) != DEVICE_ID_LENGTH:
                errors[CONF_DEVICE_ID] = "invalid_device_id_format"
            try:
                hwtype_id = parse_hwtype_id(user_input[CONF_HWTYPE_ID])
            except (TypeError, ValueError):
                errors[CONF_HWTYPE_ID] = "invalid_hwtype_id"

            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors=errors,
                )

            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            try:
                await async_poll(session, device_id, hwtype_id)
            except InvalidDevice as err:
                _LOGGER.debug("Device rejected by the API: %s", err)
                errors["base"] = "invalid_device"
            except InvalidParameters as err:
                _LOGGER.debug("API rejected the parameters: %s", err)
                errors["base"] = "invalid_parameters"
            except CannotConnect as err:
                _LOGGER.debug("Cannot reach the API: %s", err)
                errors["base"] = "cannot_connect"
            except HagelschutzApiError as err:
                # Logged at error level on purpose: this is the bucket the user
                # only sees as "unknown", so it must be diagnosable from the
                # normal log without turning on debug logging first.
                _LOGGER.error("Unexpected API response: %s", err)
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
