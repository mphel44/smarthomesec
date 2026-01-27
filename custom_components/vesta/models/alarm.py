"""Alarm models for VESTA API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from homeassistant.components.alarm_control_panel import AlarmControlPanelState


class AlarmMode(str, Enum):
    """VESTA alarm modes."""

    DISARM = "disarm"
    ARM = "arm"
    HOME = "home"
    TRIGGERED = "triggered"

    @property
    def ha_state(self) -> AlarmControlPanelState:
        """Convert to Home Assistant alarm state."""
        mapping = {
            AlarmMode.DISARM: AlarmControlPanelState.DISARMED,
            AlarmMode.ARM: AlarmControlPanelState.ARMED_AWAY,
            AlarmMode.HOME: AlarmControlPanelState.ARMED_HOME,
            AlarmMode.TRIGGERED: AlarmControlPanelState.TRIGGERED,
        }
        return mapping.get(self, AlarmControlPanelState.DISARMED)

    @classmethod
    def from_string(cls, value: str) -> AlarmMode:
        """Create AlarmMode from string value."""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.DISARM


class AlarmArea(BaseModel):
    """Represents a VESTA alarm area/partition."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    area: int = Field(..., description="Area number")
    mode: str = Field(default="disarm", description="Current alarm mode")
    name: str = Field(default="", description="Area name")

    # Additional fields that may be present
    exit_delay: int | None = Field(default=None, description="Exit delay in seconds")
    entry_delay: int | None = Field(default=None, description="Entry delay in seconds")
    alarm_length: int | None = Field(default=None, description="Alarm duration in seconds")

    @property
    def area_id(self) -> str:
        """Return the area ID as a string."""
        return str(self.area)

    @property
    def alarm_mode(self) -> AlarmMode:
        """Return the alarm mode as an enum."""
        return AlarmMode.from_string(self.mode)

    @property
    def ha_state(self) -> AlarmControlPanelState:
        """Return the Home Assistant alarm state."""
        return self.alarm_mode.ha_state

    @property
    def is_armed(self) -> bool:
        """Check if the alarm is armed in any mode."""
        return self.alarm_mode in (AlarmMode.ARM, AlarmMode.HOME)

    @property
    def is_triggered(self) -> bool:
        """Check if the alarm is triggered."""
        return self.alarm_mode == AlarmMode.TRIGGERED

    @property
    def display_name(self) -> str:
        """Return display name for the area."""
        if self.name:
            return self.name
        return f"Area {self.area}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for coordinator storage."""
        return self.model_dump(by_alias=True)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> AlarmArea:
        """Create an AlarmArea from API response data."""
        return cls.model_validate(data)
