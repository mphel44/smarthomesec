"""
DataUpdateCoordinator for intelligent polling of SmartHomeSec data.

Provides a centralized mechanism to poll the API at regular intervals
with automatic retry, backoff on errors, and listener notifications.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Generic, TypeVar

from py_smarthomesec.const import (
    DEFAULT_POLL_INTERVAL,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)
from py_smarthomesec.exceptions import (
    AuthenticationError,
    SmartHomesecError,
)

logger = logging.getLogger(__name__)

# Type variable for generic coordinator data
T = TypeVar("T")


class CoordinatorState(str, Enum):
    """State of the coordinator."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class UpdateResult(Generic[T]):
    """Result of a data update."""

    success: bool
    data: T | None = None
    error: Exception | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_fresh(self) -> bool:
        """Check if data is less than 5 minutes old."""
        if self.data is None:
            return False
        return (datetime.now() - self.timestamp) < timedelta(minutes=5)


# Type alias for update callbacks
UpdateCallback = Callable[[], Awaitable[T]]
ListenerCallback = Callable[[UpdateResult[T]], Awaitable[None] | None]


class DataUpdateCoordinator(Generic[T]):
    """
    Coordinator for periodic data updates with intelligent polling.

    Features:
    - Configurable polling interval with min/max bounds
    - Automatic retry with exponential backoff on errors
    - Listener system for update notifications
    - Manual refresh capability
    - Smart interval adjustment based on errors
    - Cooldown period after errors

    Usage:
        async def fetch_data():
            return await api.get_panel_status()

        coordinator = DataUpdateCoordinator(
            update_method=fetch_data,
            update_interval=30,
            name="panel_status",
        )

        # Register listener
        coordinator.add_listener(my_callback)

        # Start polling
        await coordinator.start()

        # Force immediate refresh
        await coordinator.async_refresh()

        # Stop when done
        await coordinator.stop()
    """

    def __init__(
        self,
        update_method: UpdateCallback[T],
        update_interval: int = DEFAULT_POLL_INTERVAL,
        name: str = "coordinator",
        error_backoff_factor: float = 2.0,
        max_error_backoff: int = MAX_POLL_INTERVAL,
        max_consecutive_errors: int = 5,
    ) -> None:
        """
        Initialize the coordinator.

        Args:
            update_method: Async callable that fetches the data.
            update_interval: Polling interval in seconds.
            name: Coordinator name (for logging).
            error_backoff_factor: Multiplier for backoff on errors.
            max_error_backoff: Maximum backoff interval in seconds.
            max_consecutive_errors: Max errors before pausing polling.
        """
        self._update_method = update_method
        self._base_interval = self._clamp_interval(update_interval)
        self._current_interval = self._base_interval
        self._name = name
        self._error_backoff_factor = error_backoff_factor
        self._max_error_backoff = max_error_backoff
        self._max_consecutive_errors = max_consecutive_errors

        # State
        self._state = CoordinatorState.IDLE
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

        # Data
        self._last_result: UpdateResult[T] | None = None
        self._consecutive_errors = 0
        self._last_update_time: datetime | None = None

        # Listeners
        self._listeners: list[ListenerCallback[T]] = []
        self._listener_lock = asyncio.Lock()

    @staticmethod
    def _clamp_interval(interval: int) -> int:
        """Clamp interval to valid bounds."""
        return max(MIN_POLL_INTERVAL, min(interval, MAX_POLL_INTERVAL))

    @property
    def state(self) -> CoordinatorState:
        """Current coordinator state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if the coordinator is actively polling."""
        return self._state == CoordinatorState.RUNNING

    @property
    def data(self) -> T | None:
        """Latest successfully fetched data."""
        if self._last_result and self._last_result.success:
            return self._last_result.data
        return None

    @property
    def last_result(self) -> UpdateResult[T] | None:
        """Last update result (success or failure)."""
        return self._last_result

    @property
    def last_update_time(self) -> datetime | None:
        """Timestamp of last successful update."""
        return self._last_update_time

    @property
    def update_interval(self) -> int:
        """Current polling interval (may be adjusted due to errors)."""
        return self._current_interval

    @property
    def consecutive_errors(self) -> int:
        """Number of consecutive update failures."""
        return self._consecutive_errors

    def add_listener(self, callback: ListenerCallback[T]) -> Callable[[], None]:
        """
        Register a listener for update notifications.

        Args:
            callback: Async or sync function called after each update.

        Returns:
            Callable to remove the listener.
        """
        self._listeners.append(callback)

        def remove_listener() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return remove_listener

    def remove_listener(self, callback: ListenerCallback[T]) -> None:
        """Remove a listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def _notify_listeners(self, result: UpdateResult[T]) -> None:
        """Notify all listeners of an update."""
        async with self._listener_lock:
            for listener in self._listeners:
                try:
                    result_or_coro = listener(result)
                    if asyncio.iscoroutine(result_or_coro):
                        await result_or_coro
                except Exception as e:
                    logger.exception(
                        "[%s] Error in listener callback: %s",
                        self._name,
                        e,
                    )

    async def _do_update(self) -> UpdateResult[T]:
        """
        Perform a single data update.

        Returns:
            UpdateResult with data or error.
        """
        try:
            data = await self._update_method()
            result = UpdateResult(success=True, data=data)

            # Reset error state on success
            self._consecutive_errors = 0
            self._current_interval = self._base_interval
            self._last_update_time = result.timestamp

            logger.debug(
                "[%s] Update successful at %s",
                self._name,
                result.timestamp.isoformat(),
            )

        except AuthenticationError as e:
            # Auth errors should not count toward backoff
            # as they require re-login, not waiting
            logger.error(
                "[%s] Authentication error: %s",
                self._name,
                e,
            )
            result = UpdateResult(success=False, error=e)

        except SmartHomesecError as e:
            self._consecutive_errors += 1
            self._apply_error_backoff()

            logger.warning(
                "[%s] Update failed (%d consecutive errors): %s",
                self._name,
                self._consecutive_errors,
                e,
            )
            result = UpdateResult(success=False, error=e)

        except Exception as e:
            self._consecutive_errors += 1
            self._apply_error_backoff()

            logger.exception(
                "[%s] Unexpected error during update (%d consecutive errors)",
                self._name,
                self._consecutive_errors,
            )
            result = UpdateResult(success=False, error=e)

        self._last_result = result
        return result

    def _apply_error_backoff(self) -> None:
        """Increase polling interval after errors."""
        new_interval = int(
            self._base_interval * (self._error_backoff_factor ** self._consecutive_errors)
        )
        self._current_interval = min(new_interval, self._max_error_backoff)

        logger.debug(
            "[%s] Backoff applied: interval now %ds (base: %ds)",
            self._name,
            self._current_interval,
            self._base_interval,
        )

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        logger.info(
            "[%s] Starting polling loop (interval: %ds)",
            self._name,
            self._current_interval,
        )

        while self._state == CoordinatorState.RUNNING:
            async with self._lock:
                result = await self._do_update()

            # Notify listeners
            await self._notify_listeners(result)

            # Check for too many consecutive errors
            if self._consecutive_errors >= self._max_consecutive_errors:
                logger.error(
                    "[%s] Too many consecutive errors (%d), pausing polling",
                    self._name,
                    self._consecutive_errors,
                )
                self._state = CoordinatorState.ERROR
                break

            # Wait for next update
            try:
                await asyncio.sleep(self._current_interval)
            except asyncio.CancelledError:
                logger.debug("[%s] Poll loop cancelled", self._name)
                break

        logger.info("[%s] Polling loop stopped", self._name)

    async def start(self) -> None:
        """
        Start the polling loop.

        Does nothing if already running.
        """
        if self._state == CoordinatorState.RUNNING:
            logger.debug("[%s] Already running", self._name)
            return

        self._state = CoordinatorState.RUNNING
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("[%s] Coordinator started", self._name)

    async def stop(self) -> None:
        """
        Stop the polling loop.

        Waits for the current update to complete before stopping.
        """
        if self._state not in (CoordinatorState.RUNNING, CoordinatorState.ERROR):
            return

        self._state = CoordinatorState.STOPPED

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("[%s] Coordinator stopped", self._name)

    async def pause(self) -> None:
        """
        Pause polling temporarily.

        Use resume() to continue.
        """
        if self._state != CoordinatorState.RUNNING:
            return

        self._state = CoordinatorState.PAUSED

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("[%s] Coordinator paused", self._name)

    async def resume(self) -> None:
        """
        Resume polling after pause or error.

        Resets the error counter.
        """
        if self._state not in (CoordinatorState.PAUSED, CoordinatorState.ERROR):
            return

        # Reset error state
        self._consecutive_errors = 0
        self._current_interval = self._base_interval

        await self.start()
        logger.info("[%s] Coordinator resumed", self._name)

    async def async_refresh(self, force: bool = False) -> UpdateResult[T]:
        """
        Request an immediate data refresh.

        Args:
            force: If True, refresh even if recently updated.

        Returns:
            UpdateResult with data or error.
        """
        # Skip if recently updated (within 5 seconds) and not forced
        if not force and self._last_update_time:
            elapsed = (datetime.now() - self._last_update_time).total_seconds()
            if elapsed < 5 and self._last_result and self._last_result.success:
                logger.debug(
                    "[%s] Skipping refresh, last update was %ds ago",
                    self._name,
                    int(elapsed),
                )
                return self._last_result

        async with self._lock:
            result = await self._do_update()

        await self._notify_listeners(result)
        return result

    def set_update_interval(self, interval: int) -> None:
        """
        Change the polling interval.

        Takes effect on next polling cycle.

        Args:
            interval: New interval in seconds.
        """
        self._base_interval = self._clamp_interval(interval)
        self._current_interval = self._base_interval
        logger.info(
            "[%s] Update interval changed to %ds",
            self._name,
            self._base_interval,
        )

    async def __aenter__(self) -> "DataUpdateCoordinator[T]":
        """Context manager entry - starts polling."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - stops polling."""
        await self.stop()


class PanelStatusCoordinator(DataUpdateCoordinator):
    """
    Specialized coordinator for PanelStatus updates.

    Provides convenience properties for accessing alarm and device data.
    """

    def __init__(
        self,
        api: Any,  # SmartHomesecAPI - avoiding circular import
        update_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        """
        Initialize the panel status coordinator.

        Args:
            api: Connected SmartHomesecAPI instance.
            update_interval: Polling interval in seconds.
        """
        self._api = api
        super().__init__(
            update_method=self._fetch_panel_status,
            update_interval=update_interval,
            name="panel_status",
        )

    async def _fetch_panel_status(self) -> Any:
        """Fetch panel status from API."""
        return await self._api.get_panel_status()

    @property
    def panel_status(self) -> Any | None:
        """Current panel status (alias for data)."""
        return self.data

    @property
    def devices(self) -> list[Any]:
        """List of devices from latest update."""
        if self.data is not None:
            return self.data.devices
        return []

    @property
    def alarm_areas(self) -> list[Any]:
        """List of alarm areas from latest update."""
        if self.data is not None:
            return self.data.alarm_areas
        return []

    @property
    def primary_alarm(self) -> Any | None:
        """Primary alarm area from latest update."""
        if self.data is not None:
            return self.data.primary_alarm
        return None

    def get_device_by_id(self, device_id: str) -> Any | None:
        """Find a device by ID from latest data."""
        if self.data is not None:
            return self.data.get_device_by_id(device_id)
        return None
