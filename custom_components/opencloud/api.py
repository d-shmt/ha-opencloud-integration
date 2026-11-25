"""Async API client for OpenCloud."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import AUTH_TYPE_BASIC, AUTH_TYPE_TOKEN

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


@dataclass(slots=True, frozen=True)
class OpenCloudDrive:
    """Representation of an OpenCloud drive/space."""

    drive_id: str
    name: str
    drive_type: str
    drive_alias: str | None
    quota: OpenCloudQuota


@dataclass(slots=True, frozen=True)
class OpenCloudServerInfo:
    """Optional server metadata."""

    version: str | None
    edition: str | None


@dataclass(slots=True, frozen=True)
class OpenCloudData:
    """Aggregated data fetched by the coordinator."""

    drives: dict[str, OpenCloudDrive]
    server_info: OpenCloudServerInfo | None


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
    ) -> None:
        """Initialize the OpenCloud API client."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._auth_type = auth_type
        self._username = username
        self._password = password
        self._token = token
        self._ssl: bool | None = None if verify_ssl else False

    def _build_auth_kwargs(self) -> dict[str, Any]:
        """Build aiohttp auth/header arguments."""
        headers: dict[str, str] = {"Accept": "application/json"}
        kwargs: dict[str, Any] = {"headers": headers, "ssl": self._ssl, "timeout": REQUEST_TIMEOUT}

        if self._auth_type == AUTH_TYPE_TOKEN and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        elif self._auth_type == AUTH_TYPE_BASIC and self._username and self._password is not None:
            kwargs["auth"] = aiohttp.BasicAuth(self._username, self._password)

        return kwargs

    async def _request_json(self, path: str, *, allow_not_found: bool = False) -> Any:
        """Perform an authenticated GET request and decode JSON."""
        url = f"{self._base_url}{path}"
        try:
            async with self._session.get(url, **self._build_auth_kwargs()) as response:
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
            quota = OpenCloudQuota(
                used=int(quota_raw.get("used", 0) or 0),
                remaining=int(quota_raw.get("remaining", 0) or 0),
                total=int(quota_raw.get("total", 0) or 0),
                state=quota_raw.get("state"),
            )
            drives.append(
                OpenCloudDrive(
                    drive_id=str(drive_id),
                    name=str(item.get("name") or drive_id),
                    drive_type=str(item.get("driveType") or "unknown"),
                    drive_alias=item.get("driveAlias"),
                    quota=quota,
                )
            )
        return drives

    async def async_get_server_info(self) -> OpenCloudServerInfo | None:
        """Fetch optional server version metadata from status.php or config.json."""
        for path in ("/status.php", "/config.json"):
            try:
                data = await self._request_json(path, allow_not_found=True)
            except OpenCloudConnectionError:
                continue
            if isinstance(data, dict):
                version = data.get("versionstring") or data.get("version")
                edition = data.get("edition") or data.get("productname")
                if version or edition:
                    return OpenCloudServerInfo(
                        version=str(version) if version else None,
                        edition=str(edition) if edition else None,
                    )
        return None

    async def async_get_data(self) -> OpenCloudData:
        """Fetch drives and optional server info."""
        drives_list = await self.async_get_drives()
        server_info = await self.async_get_server_info()
        return OpenCloudData(
            drives={drive.drive_id: drive for drive in drives_list},
            server_info=server_info,
        )

    async def async_validate_connection(self) -> list[OpenCloudDrive]:
        """Validate URL and credentials by fetching drives."""
        return await self.async_get_drives()
