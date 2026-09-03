"""Diagnostics must never leak the device ID."""

from __future__ import annotations

from aioresponses import aioresponses
from homeassistant.core import HomeAssistant

from custom_components.hagelschutz.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import DEVICE_ID, HWTYPE_ID, POLL_URL, load_fixture_json


async def test_device_id_is_redacted(hass: HomeAssistant, config_entry) -> None:
    """The device ID is the API's only secret and must be masked."""
    with aioresponses() as mocked:
        mocked.get(
            f"{POLL_URL}?hwtypeId={HWTYPE_ID}",
            payload=load_fixture_json("poll_no_hail.json"),
            repeat=True,
        )
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert DEVICE_ID not in str(diagnostics)
    assert diagnostics["coordinator"]["current_state"] == 0
