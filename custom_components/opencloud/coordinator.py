"""DataUpdateCoordinator for the OpenCloud integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    OpenCloudApiClient,
    OpenCloudApiError,
    OpenCloudAuthError,
    OpenCloudData,
)
from .const import (
    ALL_DRIVE_CATEGORIES,
    CONF_DRIVE_TYPES,
    CONF_SELECTED_DRIVES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DRIVE_CATEGORY_SPACES,
    DRIVE_TYPE_TO_CATEGORY,
)

_LOGGER = logging.getLogger(__name__)

OpenCloudConfigEntry = ConfigEntry["OpenCloudDataUpdateCoordinator"]


class OpenCloudDataUpdateCoordinator(DataUpdateCoordinator[OpenCloudData]):
    """Coordinator to poll OpenCloud drives and server status."""

    config_entry: OpenCloudConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OpenCloudConfigEntry,
        client: OpenCloudApiClient,
    ) -> None:
        """Initialize the coordinator."""
        scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL,
            config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client

    async def _async_update_data(self) -> OpenCloudData:
        """Fetch latest data from OpenCloud."""
        try:
            data = await self.client.async_get_data()
        except OpenCloudAuthError as err:
            raise ConfigEntryAuthFailed("Invalid OpenCloud credentials or expired token") from err
        except OpenCloudApiError as err:
            raise UpdateFailed(f"Error fetching OpenCloud data: {err}") from err

        selected_drives = self.config_entry.options.get(
            CONF_SELECTED_DRIVES,
            self.config_entry.data.get(CONF_SELECTED_DRIVES),
        )
        if selected_drives is not None:
            allowed_ids = set(selected_drives)
            filtered_drives = {
                drive_id: drive
                for drive_id, drive in data.drives.items()
                if drive_id in allowed_ids
            }
        else:
            selected_categories = set(
                self.config_entry.options.get(
                    CONF_DRIVE_TYPES,
                    self.config_entry.data.get(CONF_DRIVE_TYPES, ALL_DRIVE_CATEGORIES),
                )
            )
            filtered_drives = {
                drive_id: drive
                for drive_id, drive in data.drives.items()
                if DRIVE_TYPE_TO_CATEGORY.get(
                    drive.drive_type.lower(), DRIVE_CATEGORY_SPACES
                )
                in selected_categories
            }
        return OpenCloudData(
            drives=filtered_drives,
            server_info=data.server_info,
            user_count=data.user_count,
            group_count=data.group_count,
        )
