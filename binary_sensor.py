"""Binary Sensor platform for Vesta/Climax Local integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_TYPE_TO_BINARY_SENSOR_CLASS,
    SENSOR_STATUS_OFF,
    SENSOR_STATUS_ON,
)
from .entity import VestaDeviceEntity

if TYPE_CHECKING:
    from . import VestaConfigEntry
    from .client import DeviceStatus
    from .coordinator import VestaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VestaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vesta binary sensors from a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry.
        async_add_entities: Callback to add entities.
    """
    coordinator = entry.runtime_data

    entities: list[VestaBinarySensor] = []

    # Create binary sensor entities for supported device types
    if coordinator.data:
        for device in coordinator.data.devices:
            if device.type_f in DEVICE_TYPE_TO_BINARY_SENSOR_CLASS:
                entities.append(
                    VestaBinarySensor(coordinator, device, entry.entry_id)
                )
                _LOGGER.debug(
                    "Adding binary sensor: %s (zone %d, type %s)",
                    device.name,
                    device.zone,
                    device.type_f,
                )

    async_add_entities(entities)
    _LOGGER.debug("Added %d binary sensor entities", len(entities))


class VestaBinarySensor(VestaDeviceEntity, BinarySensorEntity):
    """Binary sensor entity for Vesta devices.

    This entity represents door contacts, motion sensors, smoke detectors,
    and other binary devices connected to the alarm panel.

    Attributes:
        _attr_name: The entity name shown in Home Assistant.
    """

    _attr_name = None  # Use device name

    def __init__(
        self,
        coordinator: VestaDataUpdateCoordinator,
        device: DeviceStatus,
        entry_id: str,
    ) -> None:
        """Initialize the binary sensor.

        Args:
            coordinator: The data update coordinator.
            device: The device status information.
            entry_id: The config entry ID.
        """
        super().__init__(coordinator, device, entry_id)

        # Set device class based on device type
        self._attr_device_class = DEVICE_TYPE_TO_BINARY_SENSOR_CLASS.get(
            device.type_f
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on.

        The sensor is considered "on" when:
        - Door contacts are open
        - Motion is detected
        - Smoke/CO/Water is detected

        Returns:
            True if triggered/open, False if normal/closed, None if unknown.
        """
        device = self.device_data
        if device is None:
            return None

        status = device.status

        # Check if status indicates "on" state
        if status in SENSOR_STATUS_ON:
            return True

        # Check if status indicates "off" state
        if status in SENSOR_STATUS_OFF:
            return False

        # Handle unknown status by checking common patterns
        status_lower = status.lower()
        if "open" in status_lower or "motion" in status_lower or "alarm" in status_lower:
            return True
        if "close" in status_lower or "normal" in status_lower or "ready" in status_lower:
            return False

        _LOGGER.debug("Unknown sensor status: %s for device %s", status, device.name)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | int | bool] | None:
        """Return additional state attributes.

        Returns:
            Dictionary of extra attributes or None.
        """
        device = self.device_data
        if device is None:
            return None

        return {
            "zone": device.zone,
            "area": device.area,
            "rssi": device.rssi,
            "battery_ok": device.battery_ok,
            "tamper_ok": device.tamper_ok,
            "raw_status": device.status,
        }
