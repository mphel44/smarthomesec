"""
WebSocket client for real-time notifications from SmartHomeSec/VESTA.

Uses Socket.IO protocol for bidirectional communication with the alarm panel.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from py_smarthomesec.const import (
    DEFAULT_BASE_URL,
    WEBSOCKET_PATH,
    WEBSOCKET_PING_INTERVAL,
)
from py_smarthomesec.exceptions import ConnectionError, SmartHomesecError

logger = logging.getLogger(__name__)


class WebSocketState(str, Enum):
    """WebSocket connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


class EventType(str, Enum):
    """Types of events received from the WebSocket."""

    ALARM_STATE_CHANGED = "alarm_state_changed"
    DEVICE_STATUS_CHANGED = "device_status_changed"
    DEVICE_TRIGGERED = "device_triggered"
    CONNECTION_STATUS = "connection_status"
    UNKNOWN = "unknown"


@dataclass
class WebSocketEvent:
    """Represents an event received from the WebSocket."""

    event_type: EventType
    data: dict[str, Any]
    raw_message: str = ""
    timestamp: float = field(default_factory=lambda: __import__("time").time())

    @classmethod
    def from_raw_message(cls, message: str) -> "WebSocketEvent":
        """
        Parse a raw Socket.IO message into a WebSocketEvent.

        Socket.IO message format:
        - "2" = ping/pong
        - "3" = pong response
        - "42" = event message with JSON payload
        """
        event_type = EventType.UNKNOWN
        data: dict[str, Any] = {}

        try:
            # Socket.IO event messages start with "42"
            if message.startswith("42"):
                json_str = message[2:]
                parsed = json.loads(json_str)

                if isinstance(parsed, list) and len(parsed) >= 2:
                    event_name = parsed[0]
                    event_data = parsed[1] if len(parsed) > 1 else {}

                    # Map event names to EventType
                    event_mapping = {
                        "alarm": EventType.ALARM_STATE_CHANGED,
                        "device": EventType.DEVICE_STATUS_CHANGED,
                        "trigger": EventType.DEVICE_TRIGGERED,
                        "status": EventType.CONNECTION_STATUS,
                    }

                    for key, evt_type in event_mapping.items():
                        if key in event_name.lower():
                            event_type = evt_type
                            break

                    data = event_data if isinstance(event_data, dict) else {"value": event_data}

        except (json.JSONDecodeError, IndexError, TypeError) as e:
            logger.debug("Failed to parse WebSocket message: %s - %s", message[:100], e)

        return cls(event_type=event_type, data=data, raw_message=message)


# Type alias for event callbacks
EventCallback = Callable[[WebSocketEvent], Awaitable[None] | None]


class WebSocketClient:
    """
    Async WebSocket client for SmartHomeSec real-time notifications.

    Features:
    - Automatic reconnection with exponential backoff
    - Ping/pong keep-alive handling
    - Event-based callback system
    - Thread-safe state management

    Usage:
        async def on_event(event: WebSocketEvent):
            print(f"Received: {event.event_type}")

        client = WebSocketClient(token="your_token")
        client.on_event(on_event)
        await client.connect()
    """

    def __init__(
        self,
        token: str,
        base_url: str = DEFAULT_BASE_URL,
        auto_reconnect: bool = True,
        reconnect_delay: float = 5.0,
        max_reconnect_delay: float = 300.0,
        ping_interval: int = WEBSOCKET_PING_INTERVAL,
    ) -> None:
        """
        Initialize the WebSocket client.

        Args:
            token: Authentication token from login.
            base_url: Base URL of the SmartHomeSec server.
            auto_reconnect: Enable automatic reconnection on disconnect.
            reconnect_delay: Initial delay between reconnection attempts (seconds).
            max_reconnect_delay: Maximum delay between reconnection attempts.
            ping_interval: Interval for ping/pong keep-alive (seconds).
        """
        self._token = token
        self._base_url = base_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
        self._auto_reconnect = auto_reconnect
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay
        self._ping_interval = ping_interval

        self._state = WebSocketState.DISCONNECTED
        self._callbacks: list[EventCallback] = []
        self._ws: Any = None  # websockets.WebSocketClientProtocol
        self._tasks: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        self._reconnect_attempts = 0

    @property
    def state(self) -> WebSocketState:
        """Current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Whether the client is currently connected."""
        return self._state == WebSocketState.CONNECTED

    def _build_ws_url(self) -> str:
        """Build the WebSocket URL with authentication token."""
        return f"{self._base_url}/{WEBSOCKET_PATH}?token={self._token}&transport=websocket"

    def on_event(self, callback: EventCallback) -> None:
        """
        Register a callback for WebSocket events.

        Args:
            callback: Async or sync function called on each event.
        """
        self._callbacks.append(callback)
        logger.debug("Registered event callback: %s", callback.__name__)

    def remove_callback(self, callback: EventCallback) -> bool:
        """
        Remove a previously registered callback.

        Args:
            callback: The callback to remove.

        Returns:
            True if callback was found and removed.
        """
        try:
            self._callbacks.remove(callback)
            return True
        except ValueError:
            return False

    async def _notify_callbacks(self, event: WebSocketEvent) -> None:
        """Notify all registered callbacks of an event."""
        for callback in self._callbacks:
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error("Error in event callback %s: %s", callback.__name__, e)

    async def connect(self) -> None:
        """
        Connect to the WebSocket server.

        Raises:
            ConnectionError: If connection fails.
        """
        try:
            import websockets
        except ImportError:
            raise SmartHomesecError(
                "websockets package required for WebSocket support. "
                "Install with: pip install py_smarthomesec[websocket]"
            )

        if self._state in (WebSocketState.CONNECTED, WebSocketState.CONNECTING):
            logger.warning("WebSocket already connected or connecting")
            return

        self._state = WebSocketState.CONNECTING
        self._stop_event.clear()

        url = self._build_ws_url()
        logger.info("Connecting to WebSocket: %s", url.split("?")[0])

        try:
            self._ws = await websockets.connect(
                url,
                ping_interval=None,  # We handle ping/pong manually
                close_timeout=10,
            )
            self._state = WebSocketState.CONNECTED
            self._reconnect_attempts = 0

            logger.info("WebSocket connected successfully")

            # Start background tasks
            self._tasks = [
                asyncio.create_task(self._receive_loop()),
                asyncio.create_task(self._ping_loop()),
            ]

            # Notify connection status
            await self._notify_callbacks(
                WebSocketEvent(
                    event_type=EventType.CONNECTION_STATUS,
                    data={"connected": True},
                )
            )

        except Exception as e:
            self._state = WebSocketState.DISCONNECTED
            raise ConnectionError(self._base_url, f"WebSocket connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        logger.info("Disconnecting WebSocket")
        self._auto_reconnect = False  # Prevent reconnection
        self._stop_event.set()
        self._state = WebSocketState.CLOSED

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()

        # Close WebSocket connection
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.debug("Error closing WebSocket: %s", e)
            self._ws = None

        # Notify disconnection
        await self._notify_callbacks(
            WebSocketEvent(
                event_type=EventType.CONNECTION_STATUS,
                data={"connected": False},
            )
        )

    async def _receive_loop(self) -> None:
        """Main loop for receiving WebSocket messages."""
        import websockets

        while not self._stop_event.is_set() and self._ws:
            try:
                message = await self._ws.recv()
                logger.debug("WS received: %s", message[:100] if len(message) > 100 else message)

                # Handle Socket.IO protocol messages
                if message == "2":
                    # Ping - respond with pong
                    await self._ws.send("3")
                    continue

                if message == "3":
                    # Pong - ignore
                    continue

                # Parse and dispatch event
                event = WebSocketEvent.from_raw_message(message)
                if event.event_type != EventType.UNKNOWN or event.data:
                    await self._notify_callbacks(event)

            except websockets.ConnectionClosed as e:
                logger.warning("WebSocket connection closed: %s", e)
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in WebSocket receive loop: %s", e)
                break

        # Handle reconnection
        if self._auto_reconnect and not self._stop_event.is_set():
            await self._reconnect()

    async def _ping_loop(self) -> None:
        """Send periodic pings to keep the connection alive."""
        while not self._stop_event.is_set() and self._ws:
            try:
                await asyncio.sleep(self._ping_interval)
                if self._ws and self._state == WebSocketState.CONNECTED:
                    await self._ws.send("2")
                    logger.debug("Sent ping")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Error sending ping: %s", e)

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        if self._state == WebSocketState.CLOSED:
            return

        self._state = WebSocketState.RECONNECTING
        self._reconnect_attempts += 1

        # Calculate delay with exponential backoff
        delay = min(
            self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            self._max_reconnect_delay,
        )

        logger.info(
            "Reconnecting in %.1f seconds (attempt %d)",
            delay,
            self._reconnect_attempts,
        )

        await asyncio.sleep(delay)

        if self._stop_event.is_set():
            return

        try:
            self._state = WebSocketState.DISCONNECTED
            await self.connect()
        except Exception as e:
            logger.error("Reconnection failed: %s", e)
            if self._auto_reconnect and not self._stop_event.is_set():
                await self._reconnect()

    def update_token(self, token: str) -> None:
        """
        Update the authentication token.

        Use this after re-authentication to update the WebSocket token.

        Args:
            token: New authentication token.
        """
        self._token = token
        logger.debug("WebSocket token updated")

    async def run_forever(self) -> None:
        """
        Connect and run until explicitly disconnected.

        This is a convenience method for simple use cases.
        """
        await self.connect()
        try:
            await self._stop_event.wait()
        finally:
            await self.disconnect()
