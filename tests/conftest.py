"""Fixtures for the Hagelschutz tests."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hagelschutz.const import CONF_DEVICE_ID, CONF_HWTYPE_ID, DOMAIN

DEVICE_ID = "AABBCCDDEEFF"
HWTYPE_ID = 7
POLL_URL = f"https://meteo.netitservices.com/api/v1/devices/{DEVICE_ID}/poll"
ERROR_URL = f"https://meteo.netitservices.com/api/v1/devices/{DEVICE_ID}/errorLogs"


def load_fixture_json(name: str) -> dict:
    """Load one of the poll fixtures."""
    path = Path(__file__).parent / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of the custom integration in every test."""


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Skip the actual entry setup during config flow tests."""
    with patch(
        "custom_components.hagelschutz.async_setup_entry", return_value=True
    ) as mock:
        yield mock


@pytest.fixture
def config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Return a config entry added to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Hagelschutz {DEVICE_ID}",
        unique_id=DEVICE_ID,
        data={CONF_DEVICE_ID: DEVICE_ID, CONF_HWTYPE_ID: HWTYPE_ID},
    )
    entry.add_to_hass(hass)
    return entry
