"""
Models for alarm zones and modes.
"""

from typing import Any

from pydantic import Field, computed_field, field_validator

from py_smarthomesec.const import AlarmMode, AlarmState
from py_smarthomesec.models.base import SmartHomesecBaseModel


class AlarmArea(SmartHomesecBaseModel):
    """
    VESTA system alarm zone/area.

    Represents a logical partition of the alarm system.
    Most installations have only one zone (area=1).
    """

    area: int = Field(..., ge=1, description="Zone number (typically 1)")
    mode: str = Field(..., description="Current alarm mode")
    area_name: str | None = Field(default=None, description="Zone name")

    # Raw data for unmapped fields
    raw_data: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, v: Any) -> str:
        """Normalize mode to lowercase."""
        if isinstance(v, str):
            return v.lower()
        return str(v).lower()

    @computed_field
    @property
    def state(self) -> AlarmState:
        """Convert VESTA mode to AlarmState."""
        return AlarmState.from_mode(self.mode)

    @computed_field
    @property
    def is_armed(self) -> bool:
        """Indicates if the alarm is armed (away or home)."""
        return self.state in (AlarmState.ARMED_AWAY, AlarmState.ARMED_HOME)

    @computed_field
    @property
    def is_disarmed(self) -> bool:
        """Indicates if the alarm is disarmed."""
        return self.state == AlarmState.DISARMED

    @computed_field
    @property
    def is_triggered(self) -> bool:
        """Indicates if the alarm is triggered."""
        return self.state == AlarmState.TRIGGERED

    @classmethod
    def from_api_data(cls, data: dict[str, Any]) -> "AlarmArea":
        """Create an AlarmArea from API data."""
        return cls(**data, raw_data=data)


class AlarmModeRequest(SmartHomesecBaseModel):
    """
    Alarm mode change request.

    Payload sent to POST /panel/mode.
    """

    area: int = Field(default=1, ge=1, description="Target zone number")
    mode: AlarmMode = Field(..., description="Target mode")
    pincode: int = Field(..., description="Numeric PIN code")
    format: int = Field(default=1, description="Request format (always 1)")

    @field_validator("pincode", mode="before")
    @classmethod
    def convert_pincode(cls, v: Any) -> int:
        """Convert PIN to integer if needed."""
        if isinstance(v, str):
            if not v.isdigit():
                raise ValueError("PIN code must contain only digits")
            return int(v)
        return int(v)

    def to_payload(self) -> dict[str, Any]:
        """Convert to API payload."""
        return {
            "area": self.area,
            "mode": self.mode.value if isinstance(self.mode, AlarmMode) else self.mode,
            "pincode": self.pincode,
            "format": self.format,
        }
