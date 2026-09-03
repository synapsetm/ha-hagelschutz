"""Diagnostic sensor exposing the raw Hagelschutz state."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import STATE_HAIL, STATE_NO_HAIL, STATE_TEST_ALARM
from .coordinator import HagelschutzConfigEntry, HagelschutzCoordinator
from .entity import HagelschutzEntity

STATE_OPTIONS: dict[int, str] = {
    STATE_NO_HAIL: "no_hail",
    STATE_HAIL: "hail",
    STATE_TEST_ALARM: "test_alarm",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HagelschutzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diagnostic status sensor."""
    async_add_entities([HagelschutzStatusSensor(entry.runtime_data, entry.entry_id)])


class HagelschutzStatusSensor(HagelschutzEntity, SensorEntity):
    """Raw state as an enum — for debugging only, automations use the binary sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "status"

    def __init__(self, coordinator: HagelschutzCoordinator, entry_id: str) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_status"
        self._attr_options = list(STATE_OPTIONS.values())

    @property
    def native_value(self) -> str | None:
        """Return the mapped state, or None for an unknown value."""
        return STATE_OPTIONS.get(self.coordinator.data)
