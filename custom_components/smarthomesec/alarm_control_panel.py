"""Alarm control panel platform for SmartHomeSec integration."""

from __future__ import annotations

import logging

from py_smarthomesec import AlarmArea, AlarmState, AlarmMode

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SmartHomesecConfigEntry, SmartHomesecCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Map py_smarthomesec AlarmState to HA AlarmControlPanelState
STATE_MAP = {
    AlarmState.DISARMED: AlarmControlPanelState.DISARMED,
    AlarmState.ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
    AlarmState.ARMED_HOME: AlarmControlPanelState.ARMED_HOME,
    AlarmState.ARMING: AlarmControlPanelState.ARMING,
    AlarmState.PENDING: AlarmControlPanelState.PENDING,
    AlarmState.TRIGGERED: AlarmControlPanelState.TRIGGERED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartHomesecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up alarm control panels for SmartHomeSec."""
    coordinator = entry.runtime_data.coordinator
    alarm_areas = coordinator.get_alarm_areas()

    entities = [
        SmartHomesecAlarm(coordinator, area, entry)
        for area in alarm_areas
    ]

    async_add_entities(entities)


class SmartHomesecAlarm(CoordinatorEntity[SmartHomesecCoordinator], AlarmControlPanelEntity):
    """Representation of a SmartHomeSec alarm control panel."""

    _attr_has_entity_name = True
    _attr_code_arm_required = True
    _attr_code_format = CodeFormat.NUMBER
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    def __init__(
        self,
        coordinator: SmartHomesecCoordinator,
        alarm_area: AlarmArea,
        entry: SmartHomesecConfigEntry,
    ) -> None:
        """Initialize the alarm control panel."""
        super().__init__(coordinator, context=str(alarm_area.area))

        self._area = alarm_area.area
        self._attr_unique_id = f"{entry.entry_id}_alarm_{alarm_area.area}"
        self._attr_name = alarm_area.area_name or f"Zone {alarm_area.area}"

        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data[CONF_NAME],
            "manufacturer": "SmartHomeSec",
            "model": "VESTA Alarm Panel",
        }

    @property
    def _alarm_area(self) -> AlarmArea | None:
        """Get current alarm area from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get_alarm_area(self._area)

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""
        alarm_area = self._alarm_area
        if alarm_area is None:
            return None
        return STATE_MAP.get(alarm_area.state)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._alarm_area is not None

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if code is None:
            _LOGGER.warning("No PIN code provided for disarm")
            return
        _LOGGER.info("Disarming alarm area %d", self._area)
        await self.coordinator.async_set_alarm_mode(self._area, AlarmMode.DISARM.value, code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if code is None:
            _LOGGER.warning("No PIN code provided for arm home")
            return
        _LOGGER.info("Arming alarm area %d in home mode", self._area)
        await self.coordinator.async_set_alarm_mode(self._area, AlarmMode.HOME.value, code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if code is None:
            _LOGGER.warning("No PIN code provided for arm away")
            return
        _LOGGER.info("Arming alarm area %d in away mode", self._area)
        await self.coordinator.async_set_alarm_mode(self._area, AlarmMode.ARM.value, code)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
