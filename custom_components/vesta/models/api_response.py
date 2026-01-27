"""API response models for VESTA API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .device import VestaDevice
from .alarm import AlarmArea


class LoginResponse(BaseModel):
    """Response from the login endpoint."""

    model_config = ConfigDict(extra="allow")

    token: str = Field(..., description="Authentication token")
    data: dict[str, Any] = Field(default_factory=dict, description="User data")

    @property
    def user_id(self) -> str:
        """Extract user ID from response data."""
        return str(self.data.get("user_id", ""))


class PanelCycleData(BaseModel):
    """Data contained in panel/cycle response."""

    model_config = ConfigDict(extra="allow")

    device_status: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of device statuses"
    )
    model: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of alarm area models"
    )

    def get_devices(self) -> list[VestaDevice]:
        """Parse and return all devices."""
        devices = []
        for device_data in self.device_status:
            try:
                devices.append(VestaDevice.from_api_response(device_data))
            except Exception:
                # Log but don't fail on individual device parse errors
                continue
        return devices

    def get_alarms(self) -> list[AlarmArea]:
        """Parse and return all alarm areas."""
        alarms = []
        for alarm_data in self.model:
            try:
                alarms.append(AlarmArea.from_api_response(alarm_data))
            except Exception:
                continue
        return alarms


class PanelCycleResponse(BaseModel):
    """Response from the panel/cycle endpoint."""

    model_config = ConfigDict(extra="allow")

    data: PanelCycleData = Field(
        default_factory=PanelCycleData,
        description="Panel cycle data"
    )

    @classmethod
    def from_api_response(cls, response: dict[str, Any]) -> PanelCycleResponse:
        """Create from raw API response.

        The API may return data directly or nested under 'data' key.
        """
        if "device_status" in response:
            # Data is at root level
            return cls(data=PanelCycleData.model_validate(response))
        elif "data" in response:
            # Data is nested
            return cls(data=PanelCycleData.model_validate(response["data"]))
        else:
            # Unknown format, return empty
            return cls()

    @property
    def devices(self) -> list[VestaDevice]:
        """Return all parsed devices."""
        return self.data.get_devices()

    @property
    def alarms(self) -> list[AlarmArea]:
        """Return all parsed alarm areas."""
        return self.data.get_alarms()
