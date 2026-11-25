"""Constants for the OpenCloud integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "opencloud"

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.UPDATE]

GITHUB_RELEASES_URL = "https://api.github.com/repos/opencloud-eu/opencloud/releases/latest"
UPDATE_CHECK_INTERVAL = 21600

CONF_AUTH_TYPE = "auth_type"
CONF_DRIVE_TYPES = "drive_types"
CONF_INCLUDE_PERSONAL = "include_personal"
CONF_INCLUDE_SHARES = "include_shares"
CONF_INCLUDE_SPACES = "include_spaces"
CONF_SELECTED_DRIVES = "selected_drives"
CONF_TOKEN = "token"

AUTH_TYPE_BASIC = "basic"
AUTH_TYPE_TOKEN = "token"

DRIVE_CATEGORY_PERSONAL = "personal"
DRIVE_CATEGORY_SPACES = "spaces"
DRIVE_CATEGORY_SHARES = "shares"

ALL_DRIVE_CATEGORIES: list[str] = [
    DRIVE_CATEGORY_PERSONAL,
    DRIVE_CATEGORY_SPACES,
    DRIVE_CATEGORY_SHARES,
]

DRIVE_TYPE_TO_CATEGORY: dict[str, str] = {
    "personal": DRIVE_CATEGORY_PERSONAL,
    "project": DRIVE_CATEGORY_SPACES,
    "projectspaces": DRIVE_CATEGORY_SPACES,
    "share": DRIVE_CATEGORY_SHARES,
    "shares": DRIVE_CATEGORY_SHARES,
    "mountpoint": DRIVE_CATEGORY_SHARES,
    "virtual": DRIVE_CATEGORY_SHARES,
}

DRIVE_TYPE_LABELS: dict[str, str] = {
    "personal": "Personal",
    "project": "Space",
    "projectspaces": "Space",
    "share": "Shares",
    "shares": "Shares",
    "mountpoint": "Shares",
    "virtual": "Shares",
}


def format_drive_type(drive_type: str) -> str:
    """Return a user-friendly label for an OpenCloud driveType."""
    return DRIVE_TYPE_LABELS.get(drive_type.lower(), drive_type.capitalize())

DEFAULT_SCAN_INTERVAL = 300
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 3600
DEFAULT_VERIFY_SSL = True

QUOTA_STATES: list[str] = ["normal", "nearing", "critical", "exceeded"]
