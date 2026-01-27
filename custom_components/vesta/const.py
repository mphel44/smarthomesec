"""Constants for the VESTA Alarm Panel integration."""

from __future__ import annotations

from typing import Final

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)

# Integration domain
DOMAIN: Final = "vesta"

# API Configuration
API_HOST: Final = "smarthomesec.bydemes.com"
API_BASE_PATH: Final = "REST/v2"
API_TIMEOUT: Final = 30

# API Endpoints
ENDPOINT_LOGIN: Final = "auth/login"
ENDPOINT_PANEL_CYCLE: Final = "panel/cycle"
ENDPOINT_PANEL_MODE: Final = "panel/mode"

# WebSocket Configuration
WS_PATH: Final = "ws/socket.io/"
WS_RECONNECT_INTERVAL: Final = 5
WS_PING_INTERVAL: Final = 25
WS_PING_TIMEOUT: Final = 10

# WebSocket Message Codes
WS_CODE_PING: Final = "2"
WS_CODE_PONG: Final = "3"
WS_CODE_UPDATE: Final = "42"

# Coordinator Configuration
SCAN_INTERVAL: Final = 30  # seconds (fallback polling)

# Configuration keys
CONF_PIN_CODE: Final = "pin_code"

# Device type mappings
DEVICE_TYPE_DOOR_CONTACT: Final = "device_type.door_contact"
DEVICE_TYPE_PIR: Final = "device_type.pir"
DEVICE_TYPE_KEYPAD: Final = "device_type.keypad"
DEVICE_TYPE_IPCAM: Final = "device_type.ipcam"
DEVICE_TYPE_SMOKE: Final = "device_type.smoke_detector"
DEVICE_TYPE_CO: Final = "device_type.co_detector"
DEVICE_TYPE_WATER: Final = "device_type.water_sensor"
DEVICE_TYPE_GLASS: Final = "device_type.glass_break"

# Device type to friendly name
DEVICE_TYPE_NAMES: Final[dict[str, str]] = {
    DEVICE_TYPE_DOOR_CONTACT: "Door/Window Contact",
    DEVICE_TYPE_PIR: "Motion Detector",
    DEVICE_TYPE_KEYPAD: "Keypad",
    DEVICE_TYPE_IPCAM: "IP Camera",
    DEVICE_TYPE_SMOKE: "Smoke Detector",
    DEVICE_TYPE_CO: "CO Detector",
    DEVICE_TYPE_WATER: "Water Sensor",
    DEVICE_TYPE_GLASS: "Glass Break Detector",
}

# Device type to binary sensor device class
DEVICE_TYPE_TO_BINARY_SENSOR_CLASS: Final[dict[str, BinarySensorDeviceClass]] = {
    DEVICE_TYPE_DOOR_CONTACT: BinarySensorDeviceClass.DOOR,
    DEVICE_TYPE_PIR: BinarySensorDeviceClass.MOTION,
    DEVICE_TYPE_SMOKE: BinarySensorDeviceClass.SMOKE,
    DEVICE_TYPE_CO: BinarySensorDeviceClass.CO,
    DEVICE_TYPE_WATER: BinarySensorDeviceClass.MOISTURE,
    DEVICE_TYPE_GLASS: BinarySensorDeviceClass.VIBRATION,
}

# Device status strings
STATUS_OPEN: Final = "device_status.dc_open"
STATUS_CLOSED: Final = "device_status.dc_close"
STATUS_BATTERY_LOW: Final = "device_status.bat_low"
STATUS_BATTERY_OK: Final = "device_status.bat_ok"
STATUS_TAMPER: Final = "device_status.tamper"
STATUS_FAULT: Final = "device_status.fault"

# Alarm modes (VESTA -> Home Assistant)
ALARM_MODE_DISARM: Final = "disarm"
ALARM_MODE_ARM: Final = "arm"
ALARM_MODE_HOME: Final = "home"
ALARM_MODE_TRIGGERED: Final = "triggered"

# Supported alarm areas (can be extended via options flow)
DEFAULT_ALARM_AREAS: Final[list[str]] = ["1"]

# Platforms
PLATFORMS: Final[list[str]] = [
    "alarm_control_panel",
    "binary_sensor",
    "sensor",
]

# Sensor attributes
ATTR_DEVICE_ID: Final = "device_id"
ATTR_DEVICE_TYPE: Final = "device_type"
ATTR_ZONE: Final = "zone"
ATTR_RSSI: Final = "rssi"
ATTR_BATTERY_LEVEL: Final = "battery_level"
ATTR_LAST_TRIGGERED: Final = "last_triggered"

# Entity categories for diagnostic sensors
DIAGNOSTIC_SENSORS: Final[dict[str, EntityCategory]] = {
    "battery": EntityCategory.DIAGNOSTIC,
    "signal_strength": EntityCategory.DIAGNOSTIC,
    "tamper": EntityCategory.DIAGNOSTIC,
}
