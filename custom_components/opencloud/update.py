"""Update platform for the OpenCloud integration."""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity
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
    """Set up OpenCloud update entity from a config entry."""
    coordinator = entry.runtime_data
    server_info = coordinator.data.server_info
    if server_info and server_info.version:
        async_add_entities([OpenCloudUpdateEntity(coordinator, entry)])


class OpenCloudUpdateEntity(
    CoordinatorEntity[OpenCloudDataUpdateCoordinator], UpdateEntity
):
    """Representation of an OpenCloud server update check."""

    _attr_has_entity_name = True
    _attr_translation_key = "server_update"

    def __init__(
        self,
        coordinator: OpenCloudDataUpdateCoordinator,
        entry: OpenCloudConfigEntry,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_server_update"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_server")},
            name=entry.title,
            manufacturer="OpenCloud",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Return True when server version is available."""
        server_info = self.coordinator.data.server_info
        return super().available and server_info is not None and server_info.version is not None

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed OpenCloud version."""
        server_info = self.coordinator.data.server_info
        return server_info.version if server_info else None

    @property
    def latest_version(self) -> str | None:
        """Return the latest available OpenCloud version from GitHub."""
        server_info = self.coordinator.data.server_info
        return server_info.latest_version if server_info else None

    @property
    def release_url(self) -> str | None:
        """Return the URL to the latest GitHub release."""
        server_info = self.coordinator.data.server_info
        return server_info.release_url if server_info else None

    @property
    def release_summary(self) -> str | None:
        """Return a short summary of the latest release."""
        server_info = self.coordinator.data.server_info
        return server_info.release_summary if server_info else None
