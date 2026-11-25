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
from homeassistant.core import callback
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
)
from .const import (
    ALL_DRIVE_CATEGORIES,
    AUTH_TYPE_BASIC,
    AUTH_TYPE_TOKEN,
    CONF_AUTH_TYPE,
    CONF_DRIVE_TYPES,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    DRIVE_CATEGORY_PERSONAL,
    DRIVE_CATEGORY_SHARES,
    DRIVE_CATEGORY_SPACES,
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


def _build_drive_types_selector() -> SelectSelector:
    """Build multi-select selector for OpenCloud drive categories."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=DRIVE_CATEGORY_PERSONAL, label="personal"),
                SelectOptionDict(value=DRIVE_CATEGORY_SPACES, label="spaces"),
                SelectOptionDict(value=DRIVE_CATEGORY_SHARES, label="shares"),
            ],
            multiple=True,
            mode=SelectSelectorMode.LIST,
            translation_key="drive_types",
        )
    )


class OpenCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenCloud."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._user_input: dict[str, Any] = {}
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
            error = await self._async_validate_input(data)
            if error:
                errors["base"] = error
            else:
                url = data[CONF_URL]
                identity = data.get(CONF_USERNAME) or "token"
                await self.async_set_unique_id(f"{url}|{identity}")
                self._abort_if_unique_id_configured()

                self._user_input = data
                return await self.async_step_drives()

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

    async def async_step_drives(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select which OpenCloud drive categories to integrate."""
        if user_input is not None:
            data = {
                **self._user_input,
                CONF_DRIVE_TYPES: user_input.get(CONF_DRIVE_TYPES, ALL_DRIVE_CATEGORIES),
            }
            host = urlparse(data[CONF_URL]).netloc
            return self.async_create_entry(title=f"OpenCloud ({host})", data=data)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DRIVE_TYPES, default=ALL_DRIVE_CATEGORIES
                ): _build_drive_types_selector(),
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
            error = await self._async_validate_input(updated_data)
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

    async def _async_validate_input(self, data: dict[str, Any]) -> str | None:
        """Validate connection to OpenCloud and return an error key on failure."""
        verify_ssl = data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)
        client = OpenCloudApiClient(
            session=session,
            base_url=data[CONF_URL],
            auth_type=data.get(CONF_AUTH_TYPE, AUTH_TYPE_BASIC),
            username=data.get(CONF_USERNAME),
            password=data.get(CONF_PASSWORD),
            token=data.get(CONF_TOKEN),
            verify_ssl=verify_ssl,
        )
        try:
            await client.async_validate_connection()
        except OpenCloudAuthError:
            return "invalid_auth"
        except OpenCloudConnectionError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception validating OpenCloud connection")
            return "unknown"
        return None


class OpenCloudOptionsFlow(OptionsFlow):
    """Handle OpenCloud options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        current_verify_ssl = self.config_entry.options.get(
            CONF_VERIFY_SSL,
            self.config_entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
        current_drive_types = self.config_entry.options.get(
            CONF_DRIVE_TYPES,
            self.config_entry.data.get(CONF_DRIVE_TYPES, ALL_DRIVE_CATEGORIES),
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DRIVE_TYPES, default=current_drive_types
                ): _build_drive_types_selector(),
                vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
                vol.Required(CONF_VERIFY_SSL, default=current_verify_ssl): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
