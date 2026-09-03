"""Binary sensor for the VKF hail warning."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import STATE_NO_HAIL, STATE_TEST_ALARM
from .coordinator import HagelschutzConfigEntry, HagelschutzCoordinator
from .entity import HagelschutzEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HagelschutzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the hail warning binary sensor."""
    async_add_entities([HagelschutzBinarySensor(entry.runtime_data, entry.entry_id)])


class HagelschutzBinarySensor(HagelschutzEntity, BinarySensorEntity):
    """Reports whether a hail warning is active."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_translation_key = "hail_warning"

    def __init__(self, coordinator: HagelschutzCoordinator, entry_id: str) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_hail_warning"

    @property
    def is_on(self) -> bool:
        """Return True for a real hail warning as well as for a test alarm.

        The VKF specification asks explicitly not to differentiate between the
        two hail cases: the test alarm exists to verify the whole chain.
        """
        return self.coordinator.data != STATE_NO_HAIL

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the raw state for diagnostics."""
        return {
            "current_state": self.coordinator.data,
            "test_alarm": self.coordinator.data == STATE_TEST_ALARM,
        }
