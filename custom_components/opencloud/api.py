"""Async API client for OpenCloud."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from typing import Any

import aiohttp

from .const import (
    AUTH_TYPE_BASIC,
    AUTH_TYPE_TOKEN,
    GITHUB_RELEASES_URL,
    UPDATE_CHECK_INTERVAL,
)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class OpenCloudApiError(Exception):
    """Base exception for OpenCloud API errors."""


class OpenCloudAuthError(OpenCloudApiError):
    """Authentication or authorization failure."""


class OpenCloudConnectionError(OpenCloudApiError):
    """Connection or network failure."""


@dataclass(slots=True, frozen=True)
class OpenCloudQuota:
    """Quota information for an OpenCloud drive."""

    used: int
    remaining: int
    total: int
    state: str | None
    deleted: int | None = None


@dataclass(slots=True, frozen=True)
class OpenCloudDrive:
    """Representation of an OpenCloud drive/space."""

    drive_id: str
    name: str
    drive_type: str
    drive_alias: str | None
    quota: OpenCloudQuota
    last_modified: str | None = None


@dataclass(slots=True, frozen=True)
class OpenCloudServerInfo:
    """Optional server metadata and latest release info."""

    version: str | None
    edition: str | None
    maintenance: bool = False
    latest_version: str | None = None
    release_url: str | None = None
    release_summary: str | None = None


@dataclass(slots=True, frozen=True)
class OpenCloudData:
    """Aggregated data fetched by the coordinator."""

    drives: dict[str, OpenCloudDrive]
    server_info: OpenCloudServerInfo | None
    user_count: int | None = None
    group_count: int | None = None


class OpenCloudApiClient:
    """Client to interact with OpenCloud Graph and status APIs."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        auth_type: str = AUTH_TYPE_BASIC,
        username: str | None = None,
        password: str | None = None,
        token: str | None = None,
        verify_ssl: bool = True,
        github_session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the OpenCloud API client."""
        self._session = session
        self._github_session = github_session or (session if verify_ssl else None)
        self._base_url = base_url.rstrip("/")
        self._auth_type = auth_type
        self._username = username
        self._password = password
        self._token = token
        self._ssl: bool | None = None if verify_ssl else False
        self._last_release_check: float = 0.0
        self._cached_release: tuple[str | None, str | None, str | None] = (
            None,
            None,
            None,
        )

    def _build_auth_kwargs(self) -> dict[str, Any]:
        """Build aiohttp auth/header arguments."""
        headers: dict[str, str] = {"Accept": "application/json"}
        kwargs: dict[str, Any] = {"headers": headers, "ssl": self._ssl, "timeout": REQUEST_TIMEOUT}

        if self._auth_type == AUTH_TYPE_TOKEN and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        elif self._auth_type == AUTH_TYPE_BASIC and self._username and self._password is not None:
            kwargs["auth"] = aiohttp.BasicAuth(self._username, self._password)

        return kwargs

    async def _request_json(
        self,
        path: str,
        *,
        allow_not_found: bool = False,
        allow_forbidden: bool = False,
    ) -> Any:
        """Perform an authenticated GET request and decode JSON."""
        url = f"{self._base_url}{path}"
        try:
            async with self._session.get(url, **self._build_auth_kwargs()) as response:
                if response.status == 403 and allow_forbidden:
                    return None
                if response.status in (401, 403):
                    raise OpenCloudAuthError(f"Authentication failed with status {response.status}")
                if allow_not_found and response.status == 404:
                    return None
                if response.status >= 400:
                    text = await response.text()
                    raise OpenCloudConnectionError(
                        f"Unexpected HTTP {response.status} from {path}: {text[:200]}"
                    )
                return await response.json(content_type=None)
        except OpenCloudApiError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise OpenCloudConnectionError(f"Error communicating with OpenCloud: {err}") from err

    async def async_get_drives(self) -> list[OpenCloudDrive]:
        """Fetch all drives visible to the authenticated user."""
        payload = await self._request_json("/graph/v1.0/me/drives")
        if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
            raise OpenCloudConnectionError("Invalid response format from /graph/v1.0/me/drives")

        drives: list[OpenCloudDrive] = []
        for item in payload["value"]:
            if not isinstance(item, dict):
                continue
            drive_id = item.get("id")
            if not drive_id:
                continue

            quota_raw = item.get("quota") or {}
            deleted_raw = quota_raw.get("deleted")
            quota = OpenCloudQuota(
                used=int(quota_raw.get("used", 0) or 0),
                remaining=int(quota_raw.get("remaining", 0) or 0),
                total=int(quota_raw.get("total", 0) or 0),
                state=quota_raw.get("state"),
                deleted=int(deleted_raw) if deleted_raw is not None else None,
            )
            drives.append(
                OpenCloudDrive(
                    drive_id=str(drive_id),
                    name=str(item.get("name") or drive_id),
                    drive_type=str(item.get("driveType") or "unknown"),
                    drive_alias=item.get("driveAlias"),
                    quota=quota,
                    last_modified=item.get("lastModifiedDateTime"),
                )
            )
        return drives

    async def async_get_latest_release(self) -> tuple[str | None, str | None, str | None]:
        """Fetch latest OpenCloud release metadata from GitHub (cached)."""
        if self._github_session is None:
            return self._cached_release

        now = time.monotonic()
        if (
            self._last_release_check > 0
            and (now - self._last_release_check) < UPDATE_CHECK_INTERVAL
        ):
            return self._cached_release

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ha-opencloud-integration",
        }
        try:
            async with self._github_session.get(
                GITHUB_RELEASES_URL, headers=headers, timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status != 200:
                    return self._cached_release
                data = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return self._cached_release

        if not isinstance(data, dict):
            return self._cached_release

        tag = data.get("tag_name")
        latest_version = str(tag).lstrip("v") if tag else None
        release_url = data.get("html_url")
        body = data.get("body")
        summary = str(body).strip()[:255] if body else None

        self._cached_release = (latest_version, release_url, summary)
        self._last_release_check = now
        return self._cached_release

    async def async_get_server_info(self) -> OpenCloudServerInfo | None:
        """Fetch server version metadata from status or capabilities endpoints."""
        version: str | None = None
        edition: str | None = None
        maintenance = False

        for path in ("/status.php", "/status", "/config.json"):
            try:
                data = await self._request_json(path, allow_not_found=True)
            except OpenCloudConnectionError:
                continue
            if isinstance(data, dict):
                raw_version = (
                    data.get("productversion")
                    or data.get("productVersion")
                    or data.get("versionstring")
                    or data.get("version")
                )
                raw_edition = (
                    data.get("edition")
                    or data.get("productName")
                    or data.get("productname")
                )
                if "maintenance" in data:
                    maintenance = bool(data.get("maintenance"))
                if raw_version or raw_edition:
                    version = str(raw_version).lstrip("v") if raw_version else None
                    edition = str(raw_edition) if raw_edition else None
                    break

        # Prefer productversion from OCS capabilities if status only returned legacy 10.x
        try:
            caps = await self._request_json(
                "/ocs/v1.php/cloud/capabilities?format=json", allow_not_found=True
            )
        except OpenCloudConnectionError:
            caps = None
        if isinstance(caps, dict):
            core_status = (
                caps.get("ocs", {})
                .get("data", {})
                .get("capabilities", {})
                .get("core", {})
                .get("status", {})
            )
            if isinstance(core_status, dict):
                ocs_version = core_status.get("productversion") or core_status.get(
                    "productVersion"
                )
                if ocs_version:
                    version = str(ocs_version).lstrip("v")
                if not edition:
                    raw_ed = core_status.get("edition") or core_status.get(
                        "productname"
                    )
                    if raw_ed:
                        edition = str(raw_ed)
                if "maintenance" in core_status:
                    maintenance = bool(core_status.get("maintenance"))

        if not version and not edition:
            return None

        latest_version, release_url, release_summary = (
            await self.async_get_latest_release()
        )
        return OpenCloudServerInfo(
            version=version,
            edition=edition,
            maintenance=maintenance,
            latest_version=latest_version,
            release_url=release_url,
            release_summary=release_summary,
        )

    async def _async_get_collection_count(self, path: str) -> int | None:
        """Fetch count of items in a Graph collection endpoint if permitted."""
        try:
            data = await self._request_json(
                path, allow_not_found=True, allow_forbidden=True
            )
        except OpenCloudConnectionError:
            return None
        if isinstance(data, dict) and isinstance(data.get("value"), list):
            return len(data["value"])
        return None

    async def async_get_data(self) -> OpenCloudData:
        """Fetch drives, server info, and optional admin counts."""
        drives_list = await self.async_get_drives()
        server_info, user_count, group_count = await asyncio.gather(
            self.async_get_server_info(),
            self._async_get_collection_count("/graph/v1.0/users"),
            self._async_get_collection_count("/graph/v1.0/groups"),
        )
        return OpenCloudData(
            drives={drive.drive_id: drive for drive in drives_list},
            server_info=server_info,
            user_count=user_count,
            group_count=group_count,
        )

    async def async_validate_connection(self) -> list[OpenCloudDrive]:
        """Validate URL and credentials by fetching drives."""
        return await self.async_get_drives()
