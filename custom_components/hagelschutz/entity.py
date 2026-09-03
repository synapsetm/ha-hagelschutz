"""Shared entity base for the Hagelschutz integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONFIGURATION_URL, DOMAIN, MANUFACTURER, MODEL
from .coordinator import HagelschutzCoordinator


class HagelschutzEntity(CoordinatorEntity[HagelschutzCoordinator]):
    """Base entity tied to the single Hagelschutz service device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HagelschutzCoordinator) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            # The device ID is a secret, so it must not become part of the
            # device name (and through it, of the entity IDs).
            name="Hagelschutz",
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=CONFIGURATION_URL,
        )
