"""
Polling example using DataUpdateCoordinator for py_smarthomesec.

This example demonstrates intelligent polling with automatic retry,
error backoff, and listener notifications.
"""

import asyncio
import logging

from py_smarthomesec import (
    CoordinatorState,
    InvalidCredentialsError,
    PanelStatusCoordinator,
    SmartHomesecAPI,
    SmartHomesecError,
    UpdateResult,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def on_update(result: UpdateResult) -> None:
    """Callback for coordinator updates."""
    if result.success:
        panel = result.data
        logger.info("=== Panel Status Update ===")

        # Display alarm state
        alarm = panel.primary_alarm
        if alarm:
            logger.info(
                "Alarm: %s (%s)",
                alarm.area_name or f"Zone {alarm.area}",
                alarm.state.value,
            )

        # Display device count
        logger.info("Devices: %d total", len(panel.devices))

        # Show any open doors/windows
        for device in panel.devices:
            if hasattr(device, "is_open") and device.is_open:
                logger.warning("  - %s is OPEN", device.name)

    else:
        logger.error("Update failed: %s", result.error)


async def main() -> None:
    """Example using PanelStatusCoordinator for polling."""

    # Replace with your credentials
    username = "your_username"
    password = "your_password"

    try:
        async with SmartHomesecAPI(username=username, password=password) as client:
            # Create coordinator with 30-second polling interval
            coordinator = PanelStatusCoordinator(
                api=client,
                update_interval=30,
            )

            # Register update listener
            remove_listener = coordinator.add_listener(on_update)

            # Start polling
            await coordinator.start()
            logger.info("Coordinator started, polling every %ds", coordinator.update_interval)
            logger.info("Press Ctrl+C to stop")

            try:
                # Keep running until interrupted
                while coordinator.state == CoordinatorState.RUNNING:
                    await asyncio.sleep(1)

                    # Example: Dynamically change interval
                    # coordinator.set_update_interval(60)

                    # Example: Force immediate refresh
                    # await coordinator.async_refresh(force=True)

            except KeyboardInterrupt:
                logger.info("Stopping...")
            finally:
                # Clean up
                remove_listener()
                await coordinator.stop()

    except InvalidCredentialsError:
        logger.error("Invalid credentials")
    except SmartHomesecError as e:
        logger.error("SmartHomeSec error: %s", e)


async def context_manager_example() -> None:
    """Example using coordinator as a context manager."""

    username = "your_username"
    password = "your_password"

    async with SmartHomesecAPI(username=username, password=password) as client:
        # Coordinator as context manager - auto start/stop
        async with PanelStatusCoordinator(client, update_interval=30) as coordinator:
            coordinator.add_listener(on_update)

            # Run for 2 minutes
            await asyncio.sleep(120)


if __name__ == "__main__":
    asyncio.run(main())
