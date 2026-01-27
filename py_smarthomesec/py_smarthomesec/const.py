"""
Constants for the py_smarthomesec library.
"""

from enum import Enum


# =============================================================================
# API Configuration
# =============================================================================

DEFAULT_BASE_URL = "https://smarthomesec.bydemes.com"
API_PATH = "REST/v2"
WEBSOCKET_PATH = "ws/socket.io/"

# Endpoints
ENDPOINT_LOGIN = "auth/login"
ENDPOINT_PANEL_CYCLE = "panel/cycle"
ENDPOINT_PANEL_MODE = "panel/mode"

# Timeouts (seconds)
DEFAULT_TIMEOUT = 30.0
DEFAULT_CONNECT_TIMEOUT = 10.0
WEBSOCKET_PING_INTERVAL = 25

# Polling
DEFAULT_POLL_INTERVAL = 30  # seconds
MIN_POLL_INTERVAL = 10
MAX_POLL_INTERVAL = 300

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_MAX_DELAY = 60.0  # seconds
RETRY_EXPONENTIAL_BASE = 2


# =============================================================================
# Device types
# =============================================================================


class DeviceType(str, Enum):
    """Device types supported by the VESTA system."""

    DOOR_CONTACT = "device_type.door_contact"
    PIR = "device_type.pir"
    KEYPAD = "device_type.keypad"
    IPCAM = "device_type.ipcam"
    SMOKE_DETECTOR = "device_type.smoke"
    CO_DETECTOR = "device_type.co"
    WATER_LEAK = "device_type.water"
    GLASS_BREAK = "device_type.glass"
    SIREN = "device_type.siren"
    REMOTE = "device_type.remote"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "DeviceType":
        """Convert a string to DeviceType, returns UNKNOWN if not recognized."""
        for member in cls:
            if member.value == value:
                return member
        return cls.UNKNOWN


# =============================================================================
# Device states
# =============================================================================


class DeviceStatus(str, Enum):
    """Possible sensor states."""

    # Door/window contact
    DC_OPEN = "device_status.dc_open"
    DC_CLOSED = "device_status.dc_closed"

    # PIR Motion
    MOTION_DETECTED = "1"
    NO_MOTION = "0"

    # Battery
    BATTERY_LOW = "device_status.battery_low"
    BATTERY_OK = "device_status.battery_ok"

    # Tamper
    TAMPER_OPEN = "device_status.tamper_open"
    TAMPER_CLOSED = "device_status.tamper_closed"


# =============================================================================
# Alarm modes
# =============================================================================


class AlarmMode(str, Enum):
    """Alarm modes."""

    DISARM = "disarm"
    ARM = "arm"
    HOME = "home"

    @classmethod
    def from_string(cls, value: str) -> "AlarmMode":
        """Convert a string to AlarmMode."""
        value_lower = value.lower()
        for member in cls:
            if member.value == value_lower:
                return member
        raise ValueError(f"Unknown alarm mode: {value}")


class AlarmState(str, Enum):
    """Alarm states (including transitional states)."""

    DISARMED = "disarmed"
    ARMED_AWAY = "armed_away"
    ARMED_HOME = "armed_home"
    ARMING = "arming"
    PENDING = "pending"
    TRIGGERED = "triggered"
    UNKNOWN = "unknown"

    @classmethod
    def from_mode(cls, mode: str) -> "AlarmState":
        """Convert a VESTA mode to AlarmState."""
        mapping = {
            "disarm": cls.DISARMED,
            "arm": cls.ARMED_AWAY,
            "home": cls.ARMED_HOME,
            "triggered": cls.TRIGGERED,
            "arming": cls.ARMING,
            "pending": cls.PENDING,
        }
        return mapping.get(mode.lower(), cls.UNKNOWN)


# =============================================================================
# Cookies and headers
# =============================================================================

COOKIE_PRIVACY = "isPrivacy=1"
COOKIE_PATH = "cookiePath=%2FByDemes%2F0%2F0%2F"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}
