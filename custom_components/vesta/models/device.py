"""Device models for VESTA API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..const import (
    DEVICE_TYPE_TO_BINARY_SENSOR_CLASS,
    DEVICE_TYPE_NAMES,
    STATUS_OPEN,
    STATUS_BATTERY_LOW,
    STATUS_TAMPER,
)


class DeviceStatus(str, Enum):
    """Device status values."""

    OPEN = "device_status.dc_open"
    CLOSED = "device_status.dc_close"
    BATTERY_LOW = "device_status.bat_low"
    BATTERY_OK = "device_status.bat_ok"
    TAMPER = "device_status.tamper"
    FAULT = "device_status.fault"
    AC_FAILURE = "device_status.ac_failure"
    RESTORE = "device_status.restore"


class VestaDevice(BaseModel):
    """Represents a VESTA device (sensor, detector, etc.)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    device_id: str = Field(..., description="Unique device identifier")
    name: str = Field(..., description="Device name")
    type: str = Field(..., alias="type", description="Device type string")

    # Status fields - these are lists of status strings
    status_open: list[str] = Field(default_factory=list, description="Open/close status")
    status_motion: str = Field(default="", description="Motion status (1 = motion)")
    status_battery: list[str] = Field(default_factory=list, description="Battery status")
    status_tamper: list[str] = Field(default_factory=list, description="Tamper status")
    status_fault: list[str] = Field(default_factory=list, description="Fault status")

    # Additional fields that may be present
    zone: int | None = Field(default=None, description="Zone number")
    area: int | None = Field(default=None, description="Area number")
    rssi: int | None = Field(default=None, description="Signal strength (RSSI)")
    lqi: int | None = Field(default=None, description="Link quality indicator")
    bypass: bool = Field(default=False, description="Whether device is bypassed")

    @field_validator("status_open", "status_battery", "status_tamper", "status_fault", mode="before")
    @classmethod
    def ensure_list(cls, v: Any) -> list[str]:
        """Ensure status fields are lists."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v else []
        if isinstance(v, list):
            return v
        return []

    @field_validator("status_motion", mode="before")
    @classmethod
    def ensure_string(cls, v: Any) -> str:
        """Ensure motion status is a string."""
        if v is None:
            return ""
        return str(v)

    @property
    def is_open(self) -> bool:
        """Check if the device is in open state (door/window contact)."""
        return STATUS_OPEN in self.status_open

    @property
    def has_motion(self) -> bool:
        """Check if motion is detected (PIR sensor)."""
        return self.status_motion == "1"

    @property
    def is_triggered(self) -> bool:
        """Check if device is triggered (open or motion)."""
        return self.is_open or self.has_motion

    @property
    def battery_low(self) -> bool:
        """Check if battery is low."""
        return STATUS_BATTERY_LOW in self.status_battery

    @property
    def battery_level(self) -> int | None:
        """Estimate battery level based on status.

        Returns 10 if battery_low, 100 if ok, None if unknown.
        """
        if STATUS_BATTERY_LOW in self.status_battery:
            return 10
        if self.status_battery:  # Has battery info but not low
            return 100
        return None  # No battery info available

    @property
    def is_tampered(self) -> bool:
        """Check if device is tampered."""
        return STATUS_TAMPER in self.status_tamper

    @property
    def has_fault(self) -> bool:
        """Check if device has a fault."""
        return len(self.status_fault) > 0

    @property
    def is_binary_sensor(self) -> bool:
        """Check if this device should be a binary sensor."""
        return self.type in DEVICE_TYPE_TO_BINARY_SENSOR_CLASS

    @property
    def friendly_type(self) -> str:
        """Return a friendly name for the device type."""
        return DEVICE_TYPE_NAMES.get(self.type, self.type)

    @property
    def signal_strength(self) -> int | None:
        """Return signal strength percentage (0-100)."""
        if self.rssi is not None:
            # Convert RSSI to percentage (typical range: -100 to -30 dBm)
            return max(0, min(100, 2 * (self.rssi + 100)))
        if self.lqi is not None:
            # LQI is typically 0-255, convert to percentage
            return max(0, min(100, int(self.lqi / 255 * 100)))
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for coordinator storage."""
        return self.model_dump(by_alias=True)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> VestaDevice:
        """Create a VestaDevice from API response data."""
        return cls.model_validate(data)
