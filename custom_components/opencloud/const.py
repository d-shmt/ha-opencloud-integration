"""Constants for the OpenCloud integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "opencloud"

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONF_AUTH_TYPE = "auth_type"
CONF_TOKEN = "token"

AUTH_TYPE_BASIC = "basic"
AUTH_TYPE_TOKEN = "token"

DEFAULT_SCAN_INTERVAL = 300
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 3600
DEFAULT_VERIFY_SSL = True

QUOTA_STATES: list[str] = ["normal", "nearing", "critical", "exceeded"]
