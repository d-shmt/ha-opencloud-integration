"""Sensor platform for the OpenCloud integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import OpenCloudData, OpenCloudDrive
from .const import DOMAIN, QUOTA_STATES, format_drive_type
from .coordinator import OpenCloudConfigEntry, OpenCloudDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class OpenCloudServerSensorDescription(SensorEntityDescription):
    """Describes an OpenCloud server-level sensor."""

    value_fn: Callable[[OpenCloudData], str | int | None]


@dataclass(frozen=True, kw_only=True)
class OpenCloudDriveSensorDescription(SensorEntityDescription):
    """Describes an OpenCloud drive-level sensor."""

    value_fn: Callable[[OpenCloudDrive], str | int | float | None]


def _calculate_usage_percent(drive: OpenCloudDrive) -> float | None:
    """Calculate storage usage percentage for a drive."""
    total = drive.quota.total
    used = drive.quota.used
    if total > 0:
        return round((used / total) * 100, 1)
    available_pool = used + drive.quota.remaining
    if available_pool > 0:
        return round((used / available_pool) * 100, 1)
    return None


SERVER_SENSORS: tuple[OpenCloudServerSensorDescription, ...] = (
    OpenCloudServerSensorDescription(
        key="drive_count",
        translation_key="drive_count",
        icon="mdi:folder-multiple",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: len(data.drives),
    ),
    OpenCloudServerSensorDescription(
        key="version",
        translation_key="version",
        icon="mdi:information-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.server_info.version if data.server_info else None,
    ),
)

DRIVE_SENSORS: tuple[OpenCloudDriveSensorDescription, ...] = (
    OpenCloudDriveSensorDescription(
        key="used",
        translation_key="used_space",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:harddisk",
        value_fn=lambda drive: drive.quota.used,
    ),
    OpenCloudDriveSensorDescription(
        key="remaining",
        translation_key="remaining_space",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:harddisk-plus",
        value_fn=lambda drive: drive.quota.remaining,
    ),
    OpenCloudDriveSensorDescription(
        key="total",
        translation_key="total_space",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:database",
        value_fn=lambda drive: drive.quota.total if drive.quota.total > 0 else None,
    ),
    OpenCloudDriveSensorDescription(
        key="usage_percent",
        translation_key="usage_percent",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chart-donut",
        value_fn=_calculate_usage_percent,
    ),
    OpenCloudDriveSensorDescription(
        key="quota_state",
        translation_key="quota_state",
        device_class=SensorDeviceClass.ENUM,
        options=QUOTA_STATES,
        icon="mdi:gauge",
        value_fn=lambda drive: (
            drive.quota.state.lower()
            if drive.quota.state and drive.quota.state.lower() in QUOTA_STATES
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenCloud sensors from a config entry."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        OpenCloudServerSensor(coordinator, entry, description)
        for description in SERVER_SENSORS
        if description.key != "version"
        or (coordinator.data.server_info and coordinator.data.server_info.version)
    ]

    known_drive_ids: set[str] = set()

    @callback
    def _async_add_new_drives() -> None:
        new_entities: list[SensorEntity] = []
        for drive_id in coordinator.data.drives:
            if drive_id in known_drive_ids:
                continue
            known_drive_ids.add(drive_id)
            for description in DRIVE_SENSORS:
                new_entities.append(
                    OpenCloudDriveSensor(coordinator, entry, drive_id, description)
                )
        if new_entities:
            async_add_entities(new_entities)

    async_add_entities(entities)
    _async_add_new_drives()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_drives))


class OpenCloudServerSensor(
    CoordinatorEntity[OpenCloudDataUpdateCoordinator], SensorEntity
):
    """Server-level OpenCloud sensor."""

    entity_description: OpenCloudServerSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OpenCloudDataUpdateCoordinator,
        entry: OpenCloudConfigEntry,
        description: OpenCloudServerSensorDescription,
    ) -> None:
        """Initialize the server sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_server_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_server")},
            name=entry.title,
            manufacturer="OpenCloud",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> str | int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class OpenCloudDriveSensor(
    CoordinatorEntity[OpenCloudDataUpdateCoordinator], SensorEntity
):
    """Drive-level OpenCloud sensor."""

    entity_description: OpenCloudDriveSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OpenCloudDataUpdateCoordinator,
        entry: OpenCloudConfigEntry,
        drive_id: str,
        description: OpenCloudDriveSensorDescription,
    ) -> None:
        """Initialize the drive sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._drive_id = drive_id
        drive = coordinator.data.drives[drive_id]
        drive_label = format_drive_type(drive.drive_type)

        self._attr_unique_id = f"{entry.entry_id}_{drive_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{drive_id}")},
            name=f"{drive.name} ({drive_label})",
            manufacturer="OpenCloud",
            model=f"Drive ({drive_label})",
            via_device=(DOMAIN, f"{entry.entry_id}_server"),
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Return True if the drive is present in the latest coordinator data."""
        return super().available and self._drive_id in self.coordinator.data.drives

    @property
    def native_value(self) -> str | int | float | None:
        """Return the sensor value for this drive."""
        drive = self.coordinator.data.drives.get(self._drive_id)
        if drive is None:
            return None
        return self.entity_description.value_fn(drive)
