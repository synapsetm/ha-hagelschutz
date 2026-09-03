"""Tests for the Hagelschutz coordinator and entities."""

from __future__ import annotations

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.hagelschutz.const import UPDATE_INTERVAL

from .conftest import ERROR_URL, HWTYPE_ID, POLL_URL, load_fixture_json

BINARY_SENSOR = "binary_sensor.hagelschutz_hail_warning"
STATUS_SENSOR = "sensor.hagelschutz_status"
POLL_PATTERN = f"{POLL_URL}?hwtypeId={HWTYPE_ID}"


async def _setup(hass: HomeAssistant, config_entry) -> None:
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("fixture", "is_on", "status", "test_alarm"),
    [
        ("poll_no_hail.json", STATE_OFF, "no_hail", False),
        ("poll_hail.json", STATE_ON, "hail", False),
        ("poll_test_alarm.json", STATE_ON, "test_alarm", True),
    ],
)
async def test_states(
    hass: HomeAssistant,
    config_entry,
    fixture: str,
    is_on: str,
    status: str,
    test_alarm: bool,
) -> None:
    """All three states map to the documented entity states."""
    payload = load_fixture_json(fixture)
    with aioresponses() as mocked:
        mocked.get(POLL_PATTERN, payload=payload, repeat=True)
        await _setup(hass, config_entry)

    state = hass.states.get(BINARY_SENSOR)
    assert state is not None
    assert state.state == is_on
    assert state.attributes["current_state"] == payload["currentState"]
    assert state.attributes["test_alarm"] is test_alarm

    assert hass.states.get(STATUS_SENSOR).state == status


@pytest.mark.parametrize(
    "failure",
    [
        {"status": 500},
        {"exception": TimeoutError()},
    ],
)
async def test_update_failed_makes_entity_unavailable(
    hass: HomeAssistant,
    config_entry,
    freezer: FrozenDateTimeFactory,
    failure: dict,
) -> None:
    """A failing poll turns the entity unavailable — the built-in watchdog."""
    with aioresponses() as mocked:
        mocked.get(
            POLL_PATTERN, payload=load_fixture_json("poll_no_hail.json"), repeat=True
        )
        await _setup(hass, config_entry)
    assert hass.states.get(BINARY_SENSOR).state == STATE_OFF

    with aioresponses() as mocked:
        mocked.get(POLL_PATTERN, repeat=True, **failure)
        mocked.post(ERROR_URL, status=200, repeat=True)
        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(BINARY_SENSOR).state == STATE_UNAVAILABLE


async def test_invalid_json_fails_update(
    hass: HomeAssistant, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    """A response without currentState is treated as a failure."""
    with aioresponses() as mocked:
        mocked.get(
            POLL_PATTERN, payload=load_fixture_json("poll_no_hail.json"), repeat=True
        )
        await _setup(hass, config_entry)

    with aioresponses() as mocked:
        mocked.get(POLL_PATTERN, payload={"foo": "bar"}, repeat=True)
        mocked.post(ERROR_URL, status=200, repeat=True)
        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(BINARY_SENSOR).state == STATE_UNAVAILABLE


async def test_error_report_is_rate_limited(
    hass: HomeAssistant, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    """Two failures inside 15 minutes produce exactly one error report."""
    with aioresponses() as mocked:
        mocked.get(
            POLL_PATTERN, payload=load_fixture_json("poll_no_hail.json"), repeat=True
        )
        await _setup(hass, config_entry)

    with aioresponses() as mocked:
        mocked.get(POLL_PATTERN, status=500, repeat=True)
        mocked.post(ERROR_URL, status=200, repeat=True)
        for _ in range(3):
            freezer.tick(UPDATE_INTERVAL)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

        posts = [key for key in mocked.requests if key[0] == "POST"]
        assert len(mocked.requests[posts[0]]) == 1


async def test_connection_error_sends_no_report(
    hass: HomeAssistant, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    """A pure connection error must not attempt an error report."""
    with aioresponses() as mocked:
        mocked.get(
            POLL_PATTERN, payload=load_fixture_json("poll_no_hail.json"), repeat=True
        )
        await _setup(hass, config_entry)

    with aioresponses() as mocked:
        mocked.get(POLL_PATTERN, exception=TimeoutError(), repeat=True)
        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert not [key for key in mocked.requests if key[0] == "POST"]


async def test_unload_entry(hass: HomeAssistant, config_entry) -> None:
    """The entry unloads cleanly."""
    with aioresponses() as mocked:
        mocked.get(
            POLL_PATTERN, payload=load_fixture_json("poll_no_hail.json"), repeat=True
        )
        await _setup(hass, config_entry)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(BINARY_SENSOR).state == STATE_UNAVAILABLE
