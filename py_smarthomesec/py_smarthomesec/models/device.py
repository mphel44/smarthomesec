"""
Models for VESTA system devices/sensors.
"""

from typing import Any

from pydantic import Field, computed_field, field_validator

from py_smarthomesec.const import DeviceStatus, DeviceType
from py_smarthomesec.models.base import SmartHomesecBaseModel


class BaseDevice(SmartHomesecBaseModel):
    """Base model for all devices."""

    device_id: str = Field(..., description="Unique device identifier")
    name: str = Field(..., description="Device name")
    device_type: DeviceType = Field(..., alias="type", description="Device type")

    # Common statuses (may be absent depending on device type)
    status_battery: str | None = Field(default=None, description="Battery status")
    status_tamper: str | None = Field(default=None, description="Tamper status")

    # Raw data for accessing unmapped fields
    raw_data: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @field_validator("device_type", mode="before")
    @classmethod
    def parse_device_type(cls, v: Any) -> DeviceType:
        """Convert type string to DeviceType enum."""
        if isinstance(v, DeviceType):
            return v
        if isinstance(v, str):
            return DeviceType.from_string(v)
        return DeviceType.UNKNOWN

    @computed_field
    @property
    def is_battery_low(self) -> bool:
        """Indicates if the battery is low."""
        return self.status_battery == DeviceStatus.BATTERY_LOW.value

    @computed_field
    @property
    def is_tampered(self) -> bool:
        """Indicates if the tamper is open."""
        return self.status_tamper == DeviceStatus.TAMPER_OPEN.value


class ContactSensor(BaseDevice):
    """Door/window contact sensor."""

    status_open: list[str] = Field(default_factory=list, description="Open status")

    @computed_field
    @property
    def is_open(self) -> bool:
        """Indicates if the contact is open."""
        return DeviceStatus.DC_OPEN.value in self.status_open

    @computed_field
    @property
    def is_closed(self) -> bool:
        """Indicates if the contact is closed."""
        return not self.is_open


class PIRSensor(BaseDevice):
    """PIR motion sensor."""

    status_motion: str = Field(default="0", description="Motion detection status")

    @computed_field
    @property
    def motion_detected(self) -> bool:
        """Indicates if motion is detected."""
        return self.status_motion == DeviceStatus.MOTION_DETECTED.value


class Keypad(BaseDevice):
    """Control keypad."""

    # Keypads typically don't have specific statuses beyond the base
    pass


class IPCamera(BaseDevice):
    """IP camera."""

    # Camera-specific fields if available from the API
    stream_url: str | None = Field(default=None, description="Video stream URL")


# Union type for all device types
Device = ContactSensor | PIRSensor | Keypad | IPCamera | BaseDevice


def create_device(data: dict[str, Any]) -> Device:
    """
    Factory to create the appropriate device type based on the 'type' field.

    Args:
        data: Device data dictionary from the API.

    Returns:
        Instance of the appropriate device type.
    """
    device_type = DeviceType.from_string(data.get("type", ""))

    # Store raw data for later access
    base_data = {**data, "raw_data": data}

    match device_type:
        case DeviceType.DOOR_CONTACT:
            return ContactSensor(**base_data)
        case DeviceType.PIR:
            return PIRSensor(**base_data)
        case DeviceType.KEYPAD:
            return Keypad(**base_data)
        case DeviceType.IPCAM:
            return IPCamera(**base_data)
        case _:
            return BaseDevice(**base_data)
