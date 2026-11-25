"""Binary sensor platform for the OpenCloud integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenCloudConfigEntry, OpenCloudDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenCloud binary sensors from a config entry."""
    async_add_entities([OpenCloudConnectivitySensor(entry.runtime_data, entry)])


class OpenCloudConnectivitySensor(
    CoordinatorEntity[OpenCloudDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether OpenCloud is reachable."""

    _attr_has_entity_name = True
    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: OpenCloudDataUpdateCoordinator,
        entry: OpenCloudConfigEntry,
    ) -> None:
        """Initialize the connectivity sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_server_connectivity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_server")},
            name=entry.title,
            manufacturer="OpenCloud",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Connectivity sensor stays available even if last poll failed."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True if the last coordinator update succeeded."""
        return self.coordinator.last_update_success
