"""Base entity classes for VESTA integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from ..models import VestaDevice, AlarmArea

if TYPE_CHECKING:
    from ..coordinator import VestaCoordinator

_LOGGER = logging.getLogger(__name__)


class VestaEntity(CoordinatorEntity["VestaCoordinator"]):
    """Base class for VESTA entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VestaCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the entity.

        Args:
            coordinator: The VESTA data coordinator.
            entry_id: The config entry ID.
        """
        super().__init__(coordinator)
        self._entry_id = entry_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success


class VestaDeviceEntity(VestaEntity):
    """Base class for VESTA device entities (sensors, etc.)."""

    def __init__(
        self,
        coordinator: VestaCoordinator,
        device: VestaDevice,
        entry_id: str,
    ) -> None:
        """Initialize the device entity.

        Args:
            coordinator: The VESTA data coordinator.
            device: The VESTA device.
            entry_id: The config entry ID.
        """
        super().__init__(coordinator, entry_id)
        self._device_id = device.device_id
        self._attr_unique_id = f"{entry_id}_{device.device_id}"

        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer="VESTA by Climax",
            model=device.friendly_type,
            serial_number=device.device_id,
            via_device=(DOMAIN, entry_id),
        )

    @property
    def device(self) -> VestaDevice | None:
        """Return the current device data from coordinator."""
        if self.coordinator.data:
            return self.coordinator.data.get_device(self._device_id)
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.device is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VestaAlarmEntity(VestaEntity):
    """Base class for VESTA alarm entities."""

    def __init__(
        self,
        coordinator: VestaCoordinator,
        alarm: AlarmArea,
        entry_id: str,
    ) -> None:
        """Initialize the alarm entity.

        Args:
            coordinator: The VESTA data coordinator.
            alarm: The VESTA alarm area.
            entry_id: The config entry ID.
        """
        super().__init__(coordinator, entry_id)
        self._area_id = alarm.area_id
        self._attr_unique_id = f"{entry_id}_alarm_{alarm.area_id}"

        # Device info for the alarm panel
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"panel_{entry_id}")},
            name="VESTA Alarm Panel",
            manufacturer="VESTA by Climax",
            model="Alarm Panel",
            via_device=(DOMAIN, entry_id),
        )

    @property
    def alarm(self) -> AlarmArea | None:
        """Return the current alarm data from coordinator."""
        if self.coordinator.data:
            return self.coordinator.data.get_alarm(self._area_id)
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.alarm is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
