"""
Tests for the DataUpdateCoordinator.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from py_smarthomesec.coordinator import (
    CoordinatorState,
    DataUpdateCoordinator,
    PanelStatusCoordinator,
    UpdateResult,
)
from py_smarthomesec.exceptions import ConnectionError, SmartHomesecError


@pytest.fixture
def mock_update_method() -> AsyncMock:
    """Create a mock update method."""
    mock = AsyncMock()
    mock.return_value = {"status": "ok", "data": [1, 2, 3]}
    return mock


@pytest.fixture
def coordinator(mock_update_method: AsyncMock) -> DataUpdateCoordinator:
    """Create a coordinator for testing."""
    return DataUpdateCoordinator(
        update_method=mock_update_method,
        update_interval=10,
        name="test_coordinator",
        max_consecutive_errors=3,
    )


class TestUpdateResult:
    """Tests for UpdateResult."""

    def test_successful_result(self) -> None:
        """Test successful update result."""
        result = UpdateResult(success=True, data={"test": "data"})
        assert result.success is True
        assert result.data == {"test": "data"}
        assert result.error is None
        assert result.is_fresh is True

    def test_failed_result(self) -> None:
        """Test failed update result."""
        error = SmartHomesecError("Test error")
        result = UpdateResult(success=False, error=error)
        assert result.success is False
        assert result.data is None
        assert result.error is error
        assert result.is_fresh is False


class TestDataUpdateCoordinator:
    """Tests for DataUpdateCoordinator."""

    def test_initial_state(self, coordinator: DataUpdateCoordinator) -> None:
        """Test initial coordinator state."""
        assert coordinator.state == CoordinatorState.IDLE
        assert coordinator.is_running is False
        assert coordinator.data is None
        assert coordinator.last_result is None
        assert coordinator.consecutive_errors == 0

    @pytest.mark.asyncio
    async def test_single_update(
        self, coordinator: DataUpdateCoordinator, mock_update_method: AsyncMock
    ) -> None:
        """Test a single manual update."""
        result = await coordinator.async_refresh()

        assert result.success is True
        assert result.data == {"status": "ok", "data": [1, 2, 3]}
        assert coordinator.data == {"status": "ok", "data": [1, 2, 3]}
        assert coordinator.consecutive_errors == 0
        mock_update_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_with_error(
        self, coordinator: DataUpdateCoordinator, mock_update_method: AsyncMock
    ) -> None:
        """Test update that raises an error."""
        mock_update_method.side_effect = ConnectionError("localhost", "Connection failed")

        result = await coordinator.async_refresh()

        assert result.success is False
        assert isinstance(result.error, ConnectionError)
        assert coordinator.data is None
        assert coordinator.consecutive_errors == 1

    @pytest.mark.asyncio
    async def test_error_backoff(
        self, coordinator: DataUpdateCoordinator, mock_update_method: AsyncMock
    ) -> None:
        """Test exponential backoff on errors."""
        mock_update_method.side_effect = SmartHomesecError("API error")
        initial_interval = coordinator.update_interval

        # First error
        await coordinator.async_refresh()
        assert coordinator.consecutive_errors == 1
        first_interval = coordinator.update_interval
        assert first_interval > initial_interval

        # Second error - interval should increase more
        await coordinator.async_refresh()
        assert coordinator.consecutive_errors == 2
        assert coordinator.update_interval > first_interval

    @pytest.mark.asyncio
    async def test_error_recovery(
        self, coordinator: DataUpdateCoordinator, mock_update_method: AsyncMock
    ) -> None:
        """Test error counter reset after successful update."""
        # Cause some errors
        mock_update_method.side_effect = SmartHomesecError("API error")
        await coordinator.async_refresh()
        await coordinator.async_refresh()
        assert coordinator.consecutive_errors == 2

        # Successful update should reset counter
        mock_update_method.side_effect = None
        mock_update_method.return_value = {"data": "recovered"}
        await coordinator.async_refresh()

        assert coordinator.consecutive_errors == 0
        assert coordinator.data == {"data": "recovered"}

    @pytest.mark.asyncio
    async def test_listener_notification(
        self, coordinator: DataUpdateCoordinator
    ) -> None:
        """Test listener callbacks are invoked."""
        received_results = []

        async def listener(result: UpdateResult) -> None:
            received_results.append(result)

        coordinator.add_listener(listener)
        await coordinator.async_refresh()

        assert len(received_results) == 1
        assert received_results[0].success is True

    @pytest.mark.asyncio
    async def test_listener_removal(
        self, coordinator: DataUpdateCoordinator
    ) -> None:
        """Test listener can be removed."""
        call_count = 0

        async def listener(result: UpdateResult) -> None:
            nonlocal call_count
            call_count += 1

        remove = coordinator.add_listener(listener)
        await coordinator.async_refresh()
        assert call_count == 1

        # Remove listener
        remove()
        await coordinator.async_refresh()
        assert call_count == 1  # Should not have increased

    @pytest.mark.asyncio
    async def test_start_stop(
        self, coordinator: DataUpdateCoordinator, mock_update_method: AsyncMock
    ) -> None:
        """Test start and stop."""
        await coordinator.start()
        assert coordinator.state == CoordinatorState.RUNNING
        assert coordinator.is_running is True

        # Let one update happen
        await asyncio.sleep(0.1)

        await coordinator.stop()
        assert coordinator.state == CoordinatorState.STOPPED
        assert coordinator.is_running is False

    @pytest.mark.asyncio
    async def test_pause_resume(
        self, coordinator: DataUpdateCoordinator
    ) -> None:
        """Test pause and resume."""
        await coordinator.start()
        assert coordinator.state == CoordinatorState.RUNNING

        await coordinator.pause()
        assert coordinator.state == CoordinatorState.PAUSED

        await coordinator.resume()
        assert coordinator.state == CoordinatorState.RUNNING

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_context_manager(
        self, mock_update_method: AsyncMock
    ) -> None:
        """Test coordinator as context manager."""
        coordinator = DataUpdateCoordinator(
            update_method=mock_update_method,
            update_interval=10,
            name="test",
        )

        async with coordinator:
            assert coordinator.state == CoordinatorState.RUNNING
            await asyncio.sleep(0.1)

        assert coordinator.state == CoordinatorState.STOPPED

    def test_set_update_interval(self, coordinator: DataUpdateCoordinator) -> None:
        """Test changing update interval."""
        coordinator.set_update_interval(60)
        assert coordinator.update_interval == 60

        # Test bounds clamping
        coordinator.set_update_interval(5)  # Below minimum
        assert coordinator.update_interval == 10  # MIN_POLL_INTERVAL

        coordinator.set_update_interval(1000)  # Above maximum
        assert coordinator.update_interval == 300  # MAX_POLL_INTERVAL

    @pytest.mark.asyncio
    async def test_skip_recent_refresh(
        self, coordinator: DataUpdateCoordinator, mock_update_method: AsyncMock
    ) -> None:
        """Test skipping refresh when recently updated."""
        # First refresh
        await coordinator.async_refresh()
        assert mock_update_method.call_count == 1

        # Second refresh immediately after should be skipped
        await coordinator.async_refresh(force=False)
        assert mock_update_method.call_count == 1

        # Force refresh should work
        await coordinator.async_refresh(force=True)
        assert mock_update_method.call_count == 2


class TestPanelStatusCoordinator:
    """Tests for PanelStatusCoordinator."""

    @pytest.fixture
    def mock_api(self) -> MagicMock:
        """Create a mock API."""
        api = MagicMock()
        api.get_panel_status = AsyncMock()

        # Create mock panel status
        mock_panel = MagicMock()
        mock_panel.devices = [MagicMock(name="device1"), MagicMock(name="device2")]
        mock_panel.alarm_areas = [MagicMock(area=1)]
        mock_panel.primary_alarm = MagicMock()
        mock_panel.get_device_by_id = MagicMock(return_value=mock_panel.devices[0])

        api.get_panel_status.return_value = mock_panel
        return api

    @pytest.fixture
    def panel_coordinator(self, mock_api: MagicMock) -> PanelStatusCoordinator:
        """Create a panel coordinator for testing."""
        return PanelStatusCoordinator(api=mock_api, update_interval=30)

    @pytest.mark.asyncio
    async def test_fetch_panel_status(
        self, panel_coordinator: PanelStatusCoordinator, mock_api: MagicMock
    ) -> None:
        """Test fetching panel status."""
        result = await panel_coordinator.async_refresh()

        assert result.success is True
        mock_api.get_panel_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_convenience_properties(
        self, panel_coordinator: PanelStatusCoordinator
    ) -> None:
        """Test convenience properties."""
        await panel_coordinator.async_refresh()

        assert panel_coordinator.panel_status is not None
        assert len(panel_coordinator.devices) == 2
        assert len(panel_coordinator.alarm_areas) == 1
        assert panel_coordinator.primary_alarm is not None

    @pytest.mark.asyncio
    async def test_get_device_by_id(
        self, panel_coordinator: PanelStatusCoordinator
    ) -> None:
        """Test getting device by ID."""
        await panel_coordinator.async_refresh()

        device = panel_coordinator.get_device_by_id("test_id")
        assert device is not None

    def test_empty_data_properties(
        self, panel_coordinator: PanelStatusCoordinator
    ) -> None:
        """Test properties when no data is available."""
        assert panel_coordinator.devices == []
        assert panel_coordinator.alarm_areas == []
        assert panel_coordinator.primary_alarm is None
        assert panel_coordinator.get_device_by_id("test") is None
