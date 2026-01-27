"""
Real-time events example using WebSocket for py_smarthomesec.

This example demonstrates how to receive real-time notifications
from the alarm system using the WebSocket client.
"""

import asyncio
import logging

from py_smarthomesec import (
    EventType,
    SmartHomesecAPI,
    SmartHomesecError,
    WebSocketClient,
    WebSocketEvent,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def on_event(event: WebSocketEvent) -> None:
    """Callback for WebSocket events."""
    logger.info("Received event: %s", event.event_type.value)

    match event.event_type:
        case EventType.ALARM_STATE_CHANGED:
            logger.info("Alarm state changed: %s", event.data)
        case EventType.DEVICE_STATUS_CHANGED:
            logger.info("Device status changed: %s", event.data)
        case EventType.DEVICE_TRIGGERED:
            logger.warning("Device triggered: %s", event.data)
        case EventType.CONNECTION_STATUS:
            connected = event.data.get("connected", False)
            logger.info("WebSocket %s", "connected" if connected else "disconnected")
        case _:
            logger.debug("Unknown event: %s", event.raw_message[:100])


async def main() -> None:
    """Example with WebSocket real-time events."""

    # Replace with your credentials
    username = "your_username"
    password = "your_password"

    try:
        # First, authenticate to get a token
        async with SmartHomesecAPI(username=username, password=password) as client:
            # Get the token from the auth manager
            token = client._auth.token

            if not token:
                logger.error("Failed to get authentication token")
                return

            logger.info("Authenticated successfully, starting WebSocket client")

            # Create WebSocket client with the token
            ws_client = WebSocketClient(
                token=token,
                auto_reconnect=True,
                reconnect_delay=5.0,
            )

            # Register event callback
            ws_client.on_event(on_event)

            # Connect and run
            try:
                await ws_client.connect()
                logger.info("WebSocket connected, listening for events...")
                logger.info("Press Ctrl+C to stop")

                # Keep running until interrupted
                while ws_client.is_connected:
                    await asyncio.sleep(1)

            except KeyboardInterrupt:
                logger.info("Stopping...")
            finally:
                await ws_client.disconnect()

    except SmartHomesecError as e:
        logger.error("SmartHomeSec error: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
