"""Async WebSocket client for VESTA real-time updates."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from typing import Any

import socketio

from ..const import (
    API_HOST,
    WS_PATH,
    WS_PING_INTERVAL,
    WS_PING_TIMEOUT,
    WS_RECONNECT_INTERVAL,
    WS_CODE_UPDATE,
)
from .exceptions import VestaWebSocketError

_LOGGER = logging.getLogger(__name__)

# Callback type for state updates
UpdateCallback = Callable[[], None]


class VestaWebSocket:
    """Async WebSocket client for VESTA real-time updates using Socket.IO."""

    def __init__(
        self,
        token: str,
        on_update: UpdateCallback | None = None,
        on_connect: Callable[[], None] | None = None,
        on_disconnect: Callable[[], None] | None = None,
        host: str = API_HOST,
    ) -> None:
        """Initialize the WebSocket client.

        Args:
            token: Authentication token from REST API login.
            on_update: Callback when device/alarm update is received.
            on_connect: Callback when connection is established.
            on_disconnect: Callback when connection is lost.
            host: WebSocket host.
        """
        self._token = token
        self._host = host
        self._on_update = on_update
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

        self._sio: socketio.AsyncClient | None = None
        self._connected = False
        self._reconnect_task: asyncio.Task | None = None
        self._should_reconnect = True
        self._message_pattern = re.compile(r"^(\d+)(.*)$")

    @property
    def connected(self) -> bool:
        """Return True if connected."""
        return self._connected

    def update_token(self, token: str) -> None:
        """Update the authentication token.

        Call this after re-authentication to ensure reconnection uses new token.
        """
        self._token = token

    async def connect(self) -> None:
        """Connect to the VESTA WebSocket server."""
        if self._sio is not None and self._connected:
            _LOGGER.debug("Already connected to WebSocket")
            return

        self._should_reconnect = True

        # Create Socket.IO client
        self._sio = socketio.AsyncClient(
            reconnection=False,  # We handle reconnection ourselves
            logger=False,
            engineio_logger=False,
        )

        # Register event handlers
        self._sio.on("connect", self._handle_connect)
        self._sio.on("disconnect", self._handle_disconnect)
        self._sio.on("message", self._handle_message)
        self._sio.on("*", self._handle_any_event)

        url = f"https://{self._host}"
        socket_path = f"/{WS_PATH}"

        try:
            _LOGGER.debug("Connecting to WebSocket: %s%s", url, socket_path)
            await self._sio.connect(
                url,
                socketio_path=socket_path,
                auth={"token": self._token},
                transports=["websocket"],
                wait_timeout=WS_PING_TIMEOUT,
            )
        except Exception as err:
            _LOGGER.error("Failed to connect to WebSocket: %s", err)
            self._connected = False
            raise VestaWebSocketError(f"WebSocket connection failed: {err}") from err

    async def _handle_connect(self) -> None:
        """Handle successful connection."""
        _LOGGER.info("Connected to VESTA WebSocket")
        self._connected = True

        if self._on_connect:
            try:
                self._on_connect()
            except Exception as err:
                _LOGGER.error("Error in on_connect callback: %s", err)

    async def _handle_disconnect(self) -> None:
        """Handle disconnection."""
        _LOGGER.warning("Disconnected from VESTA WebSocket")
        self._connected = False

        if self._on_disconnect:
            try:
                self._on_disconnect()
            except Exception as err:
                _LOGGER.error("Error in on_disconnect callback: %s", err)

        # Schedule reconnection if appropriate
        if self._should_reconnect:
            self._schedule_reconnect()

    async def _handle_message(self, data: Any) -> None:
        """Handle incoming Socket.IO message."""
        _LOGGER.debug("WebSocket message received: %s", data)
        await self._process_message(str(data))

    async def _handle_any_event(self, event: str, data: Any) -> None:
        """Handle any Socket.IO event."""
        _LOGGER.debug("WebSocket event '%s': %s", event, data)

        # Some VESTA messages come as events with numeric names
        if event.isdigit():
            await self._process_message(f"{event}{data if data else ''}")

    async def _process_message(self, message: str) -> None:
        """Process a raw WebSocket message.

        VESTA messages follow the format: {code}{content}
        where code is a numeric string and content is optional JSON.
        """
        match = self._message_pattern.match(message)
        if not match:
            _LOGGER.debug("Unrecognized message format: %s", message)
            return

        code = match.group(1)
        content = match.group(2)

        _LOGGER.debug("WebSocket code=%s, content=%s", code, content[:100] if content else "")

        if code == WS_CODE_UPDATE:
            # Device/alarm state update - trigger refresh
            _LOGGER.debug("Update notification received, triggering refresh")
            if self._on_update:
                try:
                    self._on_update()
                except Exception as err:
                    _LOGGER.error("Error in on_update callback: %s", err)

        elif code == "2":
            # Ping - send pong
            if self._sio and self._connected:
                try:
                    await self._sio.send("3")
                except Exception as err:
                    _LOGGER.debug("Error sending pong: %s", err)

        elif code == "3":
            # Pong / connection acknowledgment
            _LOGGER.debug("Connection acknowledged")

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._reconnect_task and not self._reconnect_task.done():
            return

        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        attempt = 0
        max_attempts = 10
        base_delay = WS_RECONNECT_INTERVAL

        while self._should_reconnect and attempt < max_attempts:
            attempt += 1
            delay = min(base_delay * (2 ** (attempt - 1)), 300)  # Max 5 minutes

            _LOGGER.info(
                "WebSocket reconnection attempt %d/%d in %d seconds",
                attempt,
                max_attempts,
                delay,
            )

            await asyncio.sleep(delay)

            if not self._should_reconnect:
                break

            try:
                await self.connect()
                if self._connected:
                    _LOGGER.info("WebSocket reconnected successfully")
                    return
            except Exception as err:
                _LOGGER.warning("Reconnection attempt %d failed: %s", attempt, err)

        _LOGGER.error("WebSocket reconnection failed after %d attempts", max_attempts)

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self._should_reconnect = False

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

        if self._sio:
            try:
                await self._sio.disconnect()
            except Exception as err:
                _LOGGER.debug("Error during disconnect: %s", err)
            self._sio = None

        self._connected = False
        _LOGGER.debug("WebSocket disconnected")

    async def __aenter__(self) -> VestaWebSocket:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()
