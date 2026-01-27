"""DataUpdateCoordinator for VESTA integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api.client import VestaApiClient
from .api.websocket import VestaWebSocket
from .api.exceptions import (
    VestaAuthenticationError,
    VestaConnectionError,
    VestaError,
)
from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    CONF_PIN_CODE,
)
from .models import VestaDevice, AlarmArea, PanelCycleResponse

_LOGGER = logging.getLogger(__name__)


@dataclass
class VestaData:
    """Class to hold VESTA data."""

    devices: dict[str, VestaDevice] = field(default_factory=dict)
    alarms: dict[str, AlarmArea] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)

    def get_device(self, device_id: str) -> VestaDevice | None:
        """Get a device by ID."""
        return self.devices.get(device_id)

    def get_alarm(self, area_id: str) -> AlarmArea | None:
        """Get an alarm area by ID."""
        return self.alarms.get(area_id)


class VestaCoordinator(DataUpdateCoordinator[VestaData]):
    """Coordinator for VESTA data updates.

    This coordinator uses a hybrid approach:
    - REST API for initial data load and commands
    - WebSocket for real-time push updates
    - Polling as fallback when WebSocket is disconnected
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            entry: Config entry containing credentials.
        """
        self.entry = entry
        self._client: VestaApiClient | None = None
        self._websocket: VestaWebSocket | None = None
        self._ws_connected = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    @property
    def client(self) -> VestaApiClient:
        """Return the API client, creating if needed."""
        if self._client is None:
            self._client = VestaApiClient(
                username=self.entry.data[CONF_USERNAME],
                password=self.entry.data[CONF_PASSWORD],
            )
        return self._client

    @property
    def pin_code(self) -> str | None:
        """Return the PIN code from options or data."""
        return self.entry.options.get(
            CONF_PIN_CODE,
            self.entry.data.get(CONF_PIN_CODE),
        )

    @property
    def websocket_connected(self) -> bool:
        """Return True if WebSocket is connected."""
        return self._ws_connected

    async def _async_update_data(self) -> VestaData:
        """Fetch data from the VESTA API.

        This is called by the DataUpdateCoordinator on the polling interval.
        When WebSocket is connected, updates are push-based and this serves
        as a fallback/sync mechanism.
        """
        try:
            raw_data = await self.client.async_get_panel_status()

            # Log raw response for debugging (helps discover new fields)
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug("Raw panel status: %s", raw_data)

            # Parse response using Pydantic models
            response = PanelCycleResponse.from_api_response(raw_data)

            # Build data structure
            data = VestaData(raw_response=raw_data)

            for device in response.devices:
                data.devices[device.device_id] = device
                _LOGGER.debug(
                    "Device %s (%s): open=%s, motion=%s, battery_low=%s",
                    device.device_id,
                    device.friendly_type,
                    device.is_open,
                    device.has_motion,
                    device.battery_low,
                )

            for alarm in response.alarms:
                data.alarms[alarm.area_id] = alarm
                _LOGGER.debug(
                    "Alarm area %s: mode=%s, state=%s",
                    alarm.area_id,
                    alarm.mode,
                    alarm.ha_state,
                )

            return data

        except VestaAuthenticationError as err:
            # Trigger re-authentication flow
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err

        except VestaConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

        except VestaError as err:
            raise UpdateFailed(f"API error: {err}") from err

        except Exception as err:
            _LOGGER.exception("Unexpected error fetching VESTA data")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def async_setup(self) -> None:
        """Set up the coordinator (called after first refresh)."""
        await self._setup_websocket()

    async def _setup_websocket(self) -> None:
        """Set up the WebSocket connection for real-time updates."""
        if self._websocket is not None:
            await self._websocket.disconnect()

        token = self.client.token
        if not token:
            _LOGGER.warning("No token available for WebSocket connection")
            return

        self._websocket = VestaWebSocket(
            token=token,
            on_update=self._on_websocket_update,
            on_connect=self._on_websocket_connect,
            on_disconnect=self._on_websocket_disconnect,
        )

        try:
            await self._websocket.connect()
        except Exception as err:
            _LOGGER.warning("Failed to connect WebSocket: %s", err)
            # Don't fail setup - polling will work as fallback

    @callback
    def _on_websocket_update(self) -> None:
        """Handle WebSocket update notification."""
        _LOGGER.debug("WebSocket update received, scheduling refresh")
        # Schedule a coordinator refresh
        self.hass.async_create_task(self.async_request_refresh())

    @callback
    def _on_websocket_connect(self) -> None:
        """Handle WebSocket connection."""
        _LOGGER.info("WebSocket connected")
        self._ws_connected = True

    @callback
    def _on_websocket_disconnect(self) -> None:
        """Handle WebSocket disconnection."""
        _LOGGER.warning("WebSocket disconnected")
        self._ws_connected = False

    async def async_set_alarm_mode(
        self,
        area: str,
        mode: str,
        pin_code: str | None = None,
    ) -> None:
        """Set the alarm mode for an area.

        Args:
            area: Area ID (e.g., "1").
            mode: Alarm mode ("arm", "home", "disarm").
            pin_code: Optional PIN code (uses stored PIN if not provided).

        Raises:
            VestaError: If the command fails.
        """
        pin = pin_code or self.pin_code
        if not pin:
            raise VestaError("PIN code is required to change alarm mode")

        await self.client.async_set_alarm_mode(
            area=int(area),
            mode=mode,
            pin_code=pin,
        )

        # Refresh data after command
        await self.async_request_refresh()

    async def async_refresh_token(self) -> None:
        """Force token refresh (e.g., after re-auth flow)."""
        await self.client.auth.authenticate(force=True)

        # Update WebSocket with new token
        if self._websocket:
            self._websocket.update_token(self.client.token or "")
            try:
                await self._websocket.disconnect()
                await self._websocket.connect()
            except Exception as err:
                _LOGGER.warning("Failed to reconnect WebSocket: %s", err)

    async def async_shutdown(self) -> None:
        """Shut down the coordinator."""
        if self._websocket:
            await self._websocket.disconnect()
            self._websocket = None

        if self._client:
            await self._client.close()
            self._client = None

    def get_devices_by_type(self, device_types: list[str]) -> list[VestaDevice]:
        """Get all devices matching the specified types.

        Args:
            device_types: List of device type strings to match.

        Returns:
            List of matching VestaDevice objects.
        """
        if not self.data:
            return []

        return [
            device
            for device in self.data.devices.values()
            if device.type in device_types
        ]

    def get_binary_sensor_devices(self) -> list[VestaDevice]:
        """Get all devices that should be binary sensors."""
        if not self.data:
            return []

        return [
            device
            for device in self.data.devices.values()
            if device.is_binary_sensor
        ]

    def get_all_devices(self) -> list[VestaDevice]:
        """Get all devices."""
        if not self.data:
            return []
        return list(self.data.devices.values())

    def get_all_alarms(self) -> list[AlarmArea]:
        """Get all alarm areas."""
        if not self.data:
            return []
        return list(self.data.alarms.values())
