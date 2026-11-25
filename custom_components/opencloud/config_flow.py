"""Config flow for the OpenCloud integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    OpenCloudApiClient,
    OpenCloudAuthError,
    OpenCloudConnectionError,
    OpenCloudDrive,
)
from .const import (
    ALL_DRIVE_CATEGORIES,
    AUTH_TYPE_BASIC,
    AUTH_TYPE_TOKEN,
    CONF_AUTH_TYPE,
    CONF_DRIVE_TYPES,
    CONF_INCLUDE_PERSONAL,
    CONF_INCLUDE_SHARES,
    CONF_INCLUDE_SPACES,
    CONF_SELECTED_DRIVES,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    DRIVE_CATEGORY_PERSONAL,
    DRIVE_CATEGORY_SHARES,
    DRIVE_CATEGORY_SPACES,
    DRIVE_TYPE_TO_CATEGORY,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _normalize_url(raw_url: str) -> str:
    """Normalize base URL by stripping whitespace and trailing slashes."""
    return raw_url.strip().rstrip("/")


def _is_valid_url(url: str) -> bool:
    """Return True if URL has http or https scheme and a host."""
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _create_client(hass: HomeAssistant, data: dict[str, Any]) -> OpenCloudApiClient:
    """Build an OpenCloudApiClient from config/options data."""
    verify_ssl = data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    return OpenCloudApiClient(
        session=session,
        base_url=data[CONF_URL],
        auth_type=data.get(CONF_AUTH_TYPE, AUTH_TYPE_BASIC),
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
        token=data.get(CONF_TOKEN),
        verify_ssl=verify_ssl,
    )


def _categories_from_flags(data: dict[str, Any]) -> list[str]:
    """Convert boolean area toggles into drive category list."""
    categories: list[str] = []
    if data.get(CONF_INCLUDE_PERSONAL, True):
        categories.append(DRIVE_CATEGORY_PERSONAL)
    if data.get(CONF_INCLUDE_SPACES, True):
        categories.append(DRIVE_CATEGORY_SPACES)
    if data.get(CONF_INCLUDE_SHARES, False):
        categories.append(DRIVE_CATEGORY_SHARES)
    return categories


def _filter_drives_by_categories(
    drives: list[OpenCloudDrive], categories: list[str]
) -> list[OpenCloudDrive]:
    """Filter drives belonging to the selected categories."""
    allowed = set(categories)
    return [
        drive
        for drive in drives
        if DRIVE_TYPE_TO_CATEGORY.get(drive.drive_type.lower(), DRIVE_CATEGORY_SPACES)
        in allowed
    ]


def _build_drives_selector(drives: list[OpenCloudDrive]) -> SelectSelector:
    """Build a multi-select list for individual OpenCloud drives."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(
                    value=drive.drive_id,
                    label=f"{drive.name} ({drive.drive_type})",
                )
                for drive in drives
            ],
            multiple=True,
            mode=SelectSelectorMode.LIST,
        )
    )


class OpenCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenCloud."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._user_input: dict[str, Any] = {}
        self._discovered_drives: list[OpenCloudDrive] = []
        self._reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OpenCloudOptionsFlow:
        """Return the options flow handler."""
        return OpenCloudOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step (URL, auth type, SSL)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = _normalize_url(user_input[CONF_URL])
            if not _is_valid_url(url):
                errors[CONF_URL] = "invalid_url"
            else:
                self._user_input = {
                    CONF_URL: url,
                    CONF_AUTH_TYPE: user_input[CONF_AUTH_TYPE],
                    CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                }
                return await self.async_step_credentials()

        schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
                vol.Required(CONF_AUTH_TYPE, default=AUTH_TYPE_BASIC): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=AUTH_TYPE_BASIC, label="basic"),
                            SelectOptionDict(value=AUTH_TYPE_TOKEN, label="token"),
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="auth_type",
                    )
                ),
                vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle credential entry and connection validation."""
        errors: dict[str, str] = {}
        auth_type = self._user_input[CONF_AUTH_TYPE]

        if user_input is not None:
            data = {**self._user_input, **user_input}
            error, drives = await self._async_validate_input(data)
            if error:
                errors["base"] = error
            else:
                url = data[CONF_URL]
                identity = data.get(CONF_USERNAME) or "token"
                await self.async_set_unique_id(f"{url}|{identity}")
                self._abort_if_unique_id_configured()

                self._user_input = data
                self._discovered_drives = drives
                return await self.async_step_drive_categories()

        if auth_type == AUTH_TYPE_TOKEN:
            schema = vol.Schema({vol.Required(CONF_TOKEN): str})
        else:
            schema = vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            )

        return self.async_show_form(
            step_id="credentials",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_drive_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1 of selection: choose which OpenCloud areas to integrate."""
        if user_input is not None:
            categories = _categories_from_flags(user_input)
            self._user_input[CONF_INCLUDE_PERSONAL] = user_input[CONF_INCLUDE_PERSONAL]
            self._user_input[CONF_INCLUDE_SPACES] = user_input[CONF_INCLUDE_SPACES]
            self._user_input[CONF_INCLUDE_SHARES] = user_input[CONF_INCLUDE_SHARES]
            self._user_input[CONF_DRIVE_TYPES] = categories
            return await self.async_step_drives()

        schema = vol.Schema(
            {
                vol.Required(CONF_INCLUDE_PERSONAL, default=True): bool,
                vol.Required(CONF_INCLUDE_SPACES, default=True): bool,
                vol.Required(CONF_INCLUDE_SHARES, default=False): bool,
            }
        )
        return self.async_show_form(step_id="drive_categories", data_schema=schema)

    async def async_step_drives(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2 of selection: refine individual drives/spaces."""
        matching_drives = _filter_drives_by_categories(
            self._discovered_drives,
            self._user_input.get(CONF_DRIVE_TYPES, ALL_DRIVE_CATEGORIES),
        )

        if not matching_drives:
            data = {**self._user_input, CONF_SELECTED_DRIVES: []}
            host = urlparse(data[CONF_URL]).netloc
            return self.async_create_entry(title=f"OpenCloud ({host})", data=data)

        if user_input is not None:
            data = {
                **self._user_input,
                CONF_SELECTED_DRIVES: user_input.get(CONF_SELECTED_DRIVES, []),
            }
            host = urlparse(data[CONF_URL]).netloc
            return self.async_create_entry(title=f"OpenCloud ({host})", data=data)

        default_ids = [drive.drive_id for drive in matching_drives]
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SELECTED_DRIVES, default=default_ids
                ): _build_drives_selector(matching_drives),
            }
        )
        return self.async_show_form(step_id="drives", data_schema=schema)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when credentials become invalid."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with updated credentials."""
        assert self._reauth_entry is not None
        errors: dict[str, str] = {}
        auth_type = self._reauth_entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_BASIC)

        if user_input is not None:
            updated_data = {**self._reauth_entry.data, **user_input}
            error, _ = await self._async_validate_input(updated_data)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data=updated_data,
                )

        if auth_type == AUTH_TYPE_TOKEN:
            schema = vol.Schema({vol.Required(CONF_TOKEN): str})
        else:
            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=self._reauth_entry.data.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )

    async def _async_validate_input(
        self, data: dict[str, Any]
    ) -> tuple[str | None, list[OpenCloudDrive]]:
        """Validate connection to OpenCloud and return (error_key, drives)."""
        client = _create_client(self.hass, data)
        try:
            drives = await client.async_validate_connection()
        except OpenCloudAuthError:
            return "invalid_auth", []
        except OpenCloudConnectionError:
            return "cannot_connect", []
        except Exception:
            _LOGGER.exception("Unexpected exception validating OpenCloud connection")
            return "unknown", []
        return None, drives


class OpenCloudOptionsFlow(OptionsFlow):
    """Handle OpenCloud options in two steps (areas -> specific drives)."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._options_input: dict[str, Any] = {}
        self._discovered_drives: list[OpenCloudDrive] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: choose areas and general options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            categories = _categories_from_flags(user_input)
            self._options_input = {
                **user_input,
                CONF_DRIVE_TYPES: categories,
            }
            try:
                client = _create_client(
                    self.hass,
                    {**self.config_entry.data, CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL]},
                )
                self._discovered_drives = await client.async_get_drives()
            except (OpenCloudAuthError, OpenCloudConnectionError):
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_drives()

        current_categories = set(
            self.config_entry.options.get(
                CONF_DRIVE_TYPES,
                self.config_entry.data.get(CONF_DRIVE_TYPES, ALL_DRIVE_CATEGORIES),
            )
        )
        current_personal = self.config_entry.options.get(
            CONF_INCLUDE_PERSONAL,
            self.config_entry.data.get(
                CONF_INCLUDE_PERSONAL, DRIVE_CATEGORY_PERSONAL in current_categories
            ),
        )
        current_spaces = self.config_entry.options.get(
            CONF_INCLUDE_SPACES,
            self.config_entry.data.get(
                CONF_INCLUDE_SPACES, DRIVE_CATEGORY_SPACES in current_categories
            ),
        )
        current_shares = self.config_entry.options.get(
            CONF_INCLUDE_SHARES,
            self.config_entry.data.get(
                CONF_INCLUDE_SHARES, DRIVE_CATEGORY_SHARES in current_categories
            ),
        )
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        current_verify_ssl = self.config_entry.options.get(
            CONF_VERIFY_SSL,
            self.config_entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_INCLUDE_PERSONAL, default=current_personal): bool,
                vol.Required(CONF_INCLUDE_SPACES, default=current_spaces): bool,
                vol.Required(CONF_INCLUDE_SHARES, default=current_shares): bool,
                vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
                vol.Required(CONF_VERIFY_SSL, default=current_verify_ssl): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def async_step_drives(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: refine which specific drives/spaces should be integrated."""
        matching_drives = _filter_drives_by_categories(
            self._discovered_drives,
            self._options_input.get(CONF_DRIVE_TYPES, ALL_DRIVE_CATEGORIES),
        )

        if not matching_drives:
            return self.async_create_entry(
                title="",
                data={**self._options_input, CONF_SELECTED_DRIVES: []},
            )

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **self._options_input,
                    CONF_SELECTED_DRIVES: user_input.get(CONF_SELECTED_DRIVES, []),
                },
            )

        previous_selected = self.config_entry.options.get(
            CONF_SELECTED_DRIVES,
            self.config_entry.data.get(CONF_SELECTED_DRIVES),
        )
        matching_ids = [drive.drive_id for drive in matching_drives]
        if previous_selected is not None:
            previous_set = set(previous_selected)
            default_ids = [did for did in matching_ids if did in previous_set]
            if not default_ids:
                default_ids = matching_ids
        else:
            default_ids = matching_ids

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SELECTED_DRIVES, default=default_ids
                ): _build_drives_selector(matching_drives),
            }
        )
        return self.async_show_form(step_id="drives", data_schema=schema)
