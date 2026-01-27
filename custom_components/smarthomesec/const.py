"""Constants for the SmartHomeSec integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

DOMAIN = "smarthomesec"
INTEGRATION_TITLE = "SmartHomeSec"

# Device type to binary sensor class mapping
TYPE_CLASS_BINARY_SENSOR = {
    "device_type.door_contact": BinarySensorDeviceClass.DOOR,
    "device_type.pir": BinarySensorDeviceClass.MOTION,
}

# Device type translations
TYPE_TRANSLATION = {
    "device_type.door_contact": "Door Contact",
    "device_type.keypad": "Keypad",
    "device_type.pir": "Motion Detector",
    "device_type.ipcam": "IP Camera",
    "device_type.smoke": "Smoke Detector",
    "device_type.co": "CO Detector",
    "device_type.water": "Water Leak Sensor",
    "device_type.glass": "Glass Break Sensor",
    "device_type.siren": "Siren",
    "device_type.remote": "Remote",
}

# Default alarm areas to monitor
DEFAULT_ALARM_AREAS = [1]

# Update interval in seconds
DEFAULT_UPDATE_INTERVAL = 30
