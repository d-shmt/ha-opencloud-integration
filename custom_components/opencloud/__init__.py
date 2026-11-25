"""The OpenCloud integration."""

from __future__ import annotations

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OpenCloudApiClient
from .const import (
    AUTH_TYPE_BASIC,
    CONF_AUTH_TYPE,
    CONF_TOKEN,
    DEFAULT_VERIFY_SSL,
    PLATFORMS,
)
from .coordinator import OpenCloudConfigEntry, OpenCloudDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: OpenCloudConfigEntry) -> bool:
    """Set up OpenCloud from a config entry."""
    verify_ssl = entry.options.get(
        CONF_VERIFY_SSL,
        entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
    )
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    client = OpenCloudApiClient(
        session=session,
        base_url=entry.data[CONF_URL],
        auth_type=entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_BASIC),
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        token=entry.data.get(CONF_TOKEN),
        verify_ssl=verify_ssl,
    )

    coordinator = OpenCloudDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: OpenCloudConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: OpenCloudConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
