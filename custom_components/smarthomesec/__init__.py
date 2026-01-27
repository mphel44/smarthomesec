"""SmartHomeSec integration for Home Assistant.

This integration uses the py_smarthomesec library for API communication.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from py_smarthomesec import (
    SmartHomesecAPI,
    SmartHomesecError,
    InvalidCredentialsError,
    PanelStatus,
    DeviceType,
    AlarmArea,
    Device,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, TYPE_CLASS_BINARY_SENSOR

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.ALARM_CONTROL_PANEL,
]

type SmartHomesecConfigEntry = ConfigEntry[SmartHomesecData]


class SmartHomesecData:
    """Runtime data for SmartHomeSec integration."""

    def __init__(
        self,
        api: SmartHomesecAPI,
        coordinator: "SmartHomesecCoordinator",
    ) -> None:
        """Initialize runtime data."""
        self.api = api
        self.coordinator = coordinator


async def async_setup_entry(hass: HomeAssistant, entry: SmartHomesecConfigEntry) -> bool:
    """Set up SmartHomeSec from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # Create API client
    api = SmartHomesecAPI(username=username, password=password)

    try:
        await api.connect()
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed("Invalid credentials") from err
    except SmartHomesecError as err:
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err

    # Create coordinator
    coordinator = SmartHomesecCoordinator(hass, api)

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data
    entry.runtime_data = SmartHomesecData(api=api, coordinator=coordinator)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartHomesecConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Disconnect API
    if unload_ok:
        await entry.runtime_data.api.disconnect()

    return unload_ok


class SmartHomesecCoordinator(DataUpdateCoordinator[PanelStatus]):
    """Coordinator for SmartHomeSec data updates."""

    def __init__(self, hass: HomeAssistant, api: SmartHomesecAPI) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.api = api

    async def _async_update_data(self) -> PanelStatus:
        """Fetch data from API."""
        try:
            return await self.api.get_panel_status()
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except SmartHomesecError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def get_binary_sensor_devices(self) -> list[Device]:
        """Get devices that should be binary sensors."""
        if self.data is None:
            return []
        return [
            device for device in self.data.devices
            if device.device_type.value in TYPE_CLASS_BINARY_SENSOR
        ]

    def get_alarm_areas(self) -> list[AlarmArea]:
        """Get alarm areas."""
        if self.data is None:
            return []
        return self.data.alarm_areas

    async def async_set_alarm_mode(
        self, area: int, mode: str, pin_code: str
    ) -> None:
        """Set alarm mode."""
        await self.api.set_alarm_mode(mode=mode, pin_code=pin_code, area=area)
        # Request refresh to get new state
        await self.async_request_refresh()
