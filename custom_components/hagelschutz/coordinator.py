"""Data update coordinator and API access for the Hagelschutz integration."""

from __future__ import annotations

import logging
from datetime import datetime

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    API_BASE,
    CONF_DEVICE_ID,
    CONF_HWTYPE_ID,
    DOMAIN,
    ERROR_REPORT_INTERVAL,
    REQUEST_TIMEOUT,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type HagelschutzConfigEntry = ConfigEntry[HagelschutzCoordinator]


class HagelschutzApiError(Exception):
    """Base error for the Hagelschutz API."""


class CannotConnect(HagelschutzApiError):
    """The API could not be reached at all (timeout, DNS, connection reset)."""


class InvalidDevice(HagelschutzApiError):
    """The device is unknown to the API or not authorised (401/403/404)."""


async def async_poll(
    session: aiohttp.ClientSession, device_id: str, hwtype_id: int
) -> int:
    """Poll the API once and return the raw ``currentState``.

    The device ID is the only secret in this API, so it must never end up in an
    exception message or a log line.
    """
    url = f"{API_BASE}/devices/{device_id}/poll"
    try:
        async with session.get(
            url,
            params={"hwtypeId": hwtype_id},
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as response:
            if response.status in (401, 403, 404):
                raise InvalidDevice(f"API rejected the device (HTTP {response.status})")
            if response.status != 200:
                raise HagelschutzApiError(f"Unexpected HTTP status {response.status}")
            # The API does not always announce application/json.
            payload = await response.json(content_type=None)
    except TimeoutError as err:
        raise CannotConnect("Timeout while polling the Hagelschutz API") from err
    except aiohttp.ClientResponseError as err:
        raise HagelschutzApiError(f"Unexpected HTTP status {err.status}") from err
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Connection error: {err}") from err
    except ValueError as err:
        raise HagelschutzApiError("API returned a non-JSON response") from err

    if not isinstance(payload, dict) or "currentState" not in payload:
        raise HagelschutzApiError("API response has no currentState")

    try:
        return int(payload["currentState"])
    except (TypeError, ValueError) as err:
        raise HagelschutzApiError("currentState is not an integer") from err


class HagelschutzCoordinator(DataUpdateCoordinator[int]):
    """Poll the VKF hail warning signal every 120 seconds."""

    config_entry: HagelschutzConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: HagelschutzConfigEntry
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=UPDATE_INTERVAL,
        )
        self._session = async_get_clientsession(hass)
        self.device_id: str = config_entry.data[CONF_DEVICE_ID]
        self.hwtype_id: int = config_entry.data[CONF_HWTYPE_ID]
        self._last_error_report: datetime | None = None

    async def _async_update_data(self) -> int:
        """Fetch the current state.

        Any failure raises ``UpdateFailed``, which turns the entities
        ``unavailable`` — that is the watchdog an automation can trigger on.
        """
        try:
            return await async_poll(self._session, self.device_id, self.hwtype_id)
        except CannotConnect as err:
            # No point reporting a connection problem over the same connection.
            raise UpdateFailed(str(err)) from err
        except HagelschutzApiError as err:
            await self._async_report_error(str(err))
            raise UpdateFailed(str(err)) from err

    async def _async_report_error(self, message: str) -> None:
        """Send an error report, rate limited and never fatal."""
        now = dt_util.utcnow()
        if (
            self._last_error_report is not None
            and now - self._last_error_report < ERROR_REPORT_INTERVAL
        ):
            return
        self._last_error_report = now

        url = f"{API_BASE}/devices/{self.device_id}/errorLogs"
        try:
            async with self._session.post(
                url,
                json={"errlog": message},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                if response.status >= 400:
                    _LOGGER.debug(
                        "Error report rejected with HTTP %s", response.status
                    )
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug("Could not send error report: %s", err)
