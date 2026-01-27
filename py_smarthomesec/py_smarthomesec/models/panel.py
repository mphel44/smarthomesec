"""
Model for the complete panel response (endpoint /panel/cycle).
"""

from typing import Any

from pydantic import Field

from py_smarthomesec.models.alarm import AlarmArea
from py_smarthomesec.models.base import SmartHomesecBaseModel, TimestampMixin
from py_smarthomesec.models.device import Device, create_device


class PanelData(SmartHomesecBaseModel):
    """Internal panel data."""

    device_status: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Raw list of device statuses",
    )
    model: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Raw list of alarm zones",
    )

    # Complete raw data
    raw_data: dict[str, Any] = Field(default_factory=dict, exclude=True)


class PanelStatus(SmartHomesecBaseModel, TimestampMixin):
    """
    Complete response from the /panel/cycle endpoint.

    Contains the state of all devices and alarm zones.
    """

    data: PanelData = Field(..., description="Panel data")

    # Caches for parsed objects
    _devices: list[Device] | None = None
    _alarms: list[AlarmArea] | None = None

    @property
    def devices(self) -> list[Device]:
        """
        Return the list of parsed devices.

        Uses a cache to avoid re-parsing on each access.
        """
        if self._devices is None:
            self._devices = [
                create_device(device_data)
                for device_data in self.data.device_status
            ]
        return self._devices

    @property
    def alarm_areas(self) -> list[AlarmArea]:
        """
        Return the list of parsed alarm zones.

        Uses a cache to avoid re-parsing on each access.
        """
        if self._alarms is None:
            self._alarms = [
                AlarmArea.from_api_data(area_data)
                for area_data in self.data.model
            ]
        return self._alarms

    @property
    def primary_alarm(self) -> AlarmArea | None:
        """
        Return the primary alarm zone (area=1).

        Most installations have only one zone.
        """
        for alarm in self.alarm_areas:
            if alarm.area == 1:
                return alarm
        return self.alarm_areas[0] if self.alarm_areas else None

    def get_device_by_id(self, device_id: str) -> Device | None:
        """Find a device by its ID."""
        for device in self.devices:
            if device.device_id == device_id:
                return device
        return None

    def get_devices_by_type(self, device_type: str) -> list[Device]:
        """Return all devices of a given type."""
        return [
            device for device in self.devices
            if device.device_type.value == device_type
        ]

    def get_alarm_area(self, area: int = 1) -> AlarmArea | None:
        """Find an alarm zone by its number."""
        for alarm in self.alarm_areas:
            if alarm.area == area:
                return alarm
        return None

    @classmethod
    def from_api_response(cls, response: dict[str, Any]) -> "PanelStatus":
        """
        Create a PanelStatus from the raw API response.

        Args:
            response: JSON response from GET /panel/cycle

        Returns:
            PanelStatus instance with all parsed data.
        """
        from datetime import datetime

        data = response.get("data", {})
        panel_data = PanelData(
            device_status=data.get("device_status", []),
            model=data.get("model", []),
            raw_data=data,
        )

        return cls(
            data=panel_data,
            updated_at=datetime.now(),
        )
