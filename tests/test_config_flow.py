"""Tests for the Hagelschutz config flow."""

from __future__ import annotations

import pytest
from aioresponses import aioresponses
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hagelschutz.const import CONF_DEVICE_ID, CONF_HWTYPE_ID, DOMAIN

from .conftest import DEVICE_ID, HWTYPE_ID, POLL_URL, load_fixture_json

USER_INPUT = {CONF_DEVICE_ID: DEVICE_ID, CONF_HWTYPE_ID: str(HWTYPE_ID)}


async def _start_flow(hass: HomeAssistant) -> dict:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def test_user_flow_happy_path(
    hass: HomeAssistant, mock_setup_entry: None
) -> None:
    """A reachable device creates an entry."""
    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with aioresponses() as mocked:
        mocked.get(
            f"{POLL_URL}?hwtypeId={HWTYPE_ID}",
            payload=load_fixture_json("poll_no_hail.json"),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Hagelschutz {DEVICE_ID}"
    # Stored as parsed values, not as the raw text from the form.
    assert result["data"] == {CONF_DEVICE_ID: DEVICE_ID, CONF_HWTYPE_ID: HWTYPE_ID}
    assert result["result"].unique_id == DEVICE_ID


async def test_user_flow_duplicate_aborts(
    hass: HomeAssistant, config_entry, mock_setup_entry: None
) -> None:
    """A device that is already configured aborts the flow."""
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (404, "invalid_device"),
        (403, "invalid_device"),
        (400, "invalid_parameters"),
        (422, "invalid_parameters"),
        (500, "unknown"),
    ],
)
async def test_user_flow_http_errors(
    hass: HomeAssistant, mock_setup_entry: None, status: int, expected: str
) -> None:
    """HTTP errors map to the documented form errors."""
    result = await _start_flow(hass)

    with aioresponses() as mocked:
        mocked.get(f"{POLL_URL}?hwtypeId={HWTYPE_ID}", status=status)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: None
) -> None:
    """A timeout shows cannot_connect and lets the user retry."""
    result = await _start_flow(hass)

    with aioresponses() as mocked:
        mocked.get(f"{POLL_URL}?hwtypeId={HWTYPE_ID}", exception=TimeoutError())
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recovering from the error must still be possible.
    with aioresponses() as mocked:
        mocked.get(
            f"{POLL_URL}?hwtypeId={HWTYPE_ID}",
            payload=load_fixture_json("poll_no_hail.json"),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_device_id_separators_are_stripped(
    hass: HomeAssistant, mock_setup_entry: None
) -> None:
    """A MAC address entered with colons is normalised to 12 characters."""
    result = await _start_flow(hass)

    with aioresponses() as mocked:
        mocked.get(
            f"{POLL_URL}?hwtypeId={HWTYPE_ID}",
            payload=load_fixture_json("poll_no_hail.json"),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_ID: "AA:BB:CC:DD:EE:FF", CONF_HWTYPE_ID: str(HWTYPE_ID)},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == DEVICE_ID


async def test_device_id_wrong_length_is_rejected(
    hass: HomeAssistant, mock_setup_entry: None
) -> None:
    """A device ID that is not 12 characters never reaches the API."""
    result = await _start_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: "TOOSHORT", CONF_HWTYPE_ID: str(HWTYPE_ID)}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_DEVICE_ID: "invalid_device_id_format"}


@pytest.mark.parametrize("entered", ["188", " 188 ", "0188"])
async def test_hwtype_id_accepts_text_and_numbers(
    hass: HomeAssistant, mock_setup_entry: None, entered: str
) -> None:
    """The field is text, so it must survive stray whitespace and leading zeros."""
    result = await _start_flow(hass)

    with aioresponses() as mocked:
        mocked.get(
            f"{POLL_URL}?hwtypeId=188",
            payload=load_fixture_json("poll_no_hail.json"),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_ID: DEVICE_ID, CONF_HWTYPE_ID: entered},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HWTYPE_ID] == 188


async def test_hwtype_id_rejects_non_numeric(
    hass: HomeAssistant, mock_setup_entry: None
) -> None:
    """A non-numeric hardware type never reaches the API."""
    result = await _start_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: DEVICE_ID, CONF_HWTYPE_ID: "abc"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HWTYPE_ID: "invalid_hwtype_id"}


async def test_invisible_characters_are_stripped(
    hass: HomeAssistant, mock_setup_entry: None
) -> None:
    """A device ID pasted from an email may carry invisible characters."""
    result = await _start_flow(hass)

    with aioresponses() as mocked:
        mocked.get(
            f"{POLL_URL}?hwtypeId={HWTYPE_ID}",
            payload=load_fixture_json("poll_no_hail.json"),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: f"\u200b{DEVICE_ID}\u00a0",
                CONF_HWTYPE_ID: str(HWTYPE_ID),
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == DEVICE_ID
