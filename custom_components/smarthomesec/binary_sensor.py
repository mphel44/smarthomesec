"""Binary sensor platform for SmartHomeSec integration."""

from __future__ import annotations

import logging

from py_smarthomesec import Device, DeviceType, ContactSensor, PIRSensor

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SmartHomesecConfigEntry, SmartHomesecCoordinator
from .const import DOMAIN, TYPE_CLASS_BINARY_SENSOR, TYPE_TRANSLATION

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartHomesecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for SmartHomeSec."""
    coordinator = entry.runtime_data.coordinator
    devices = coordinator.get_binary_sensor_devices()

    entities = [
        SmartHomesecBinarySensor(coordinator, device, entry.entry_id)
        for device in devices
    ]

    async_add_entities(entities)


class SmartHomesecBinarySensor(CoordinatorEntity[SmartHomesecCoordinator], BinarySensorEntity):
    """Representation of a SmartHomeSec binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SmartHomesecCoordinator,
        device: Device,
        entry_id: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, context=device.device_id)

        self._device_id = device.device_id
        self._attr_unique_id = f"{entry_id}_{device.device_id}"
        self._attr_name = device.name

        # Set device class based on device type
        if device.device_type.value in TYPE_CLASS_BINARY_SENSOR:
            self._attr_device_class = TYPE_CLASS_BINARY_SENSOR[device.device_type.value]

        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.name,
            "manufacturer": "SmartHomeSec",
            "model": TYPE_TRANSLATION.get(device.device_type.value, device.device_type.value),
            "serial_number": device.device_id,
        }

    @property
    def _device(self) -> Device | None:
        """Get current device from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get_device_by_id(self._device_id)

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        device = self._device
        if device is None:
            return None

        # Door/window contact sensor
        if isinstance(device, ContactSensor):
            return device.is_open

        # PIR motion sensor
        if isinstance(device, PIRSensor):
            return device.motion_detected

        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._device is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
