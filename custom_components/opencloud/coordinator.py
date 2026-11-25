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
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

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
            return await self.client.async_get_data()
        except OpenCloudAuthError as err:
            raise ConfigEntryAuthFailed("Invalid OpenCloud credentials or expired token") from err
        except OpenCloudApiError as err:
            raise UpdateFailed(f"Error fetching OpenCloud data: {err}") from err
