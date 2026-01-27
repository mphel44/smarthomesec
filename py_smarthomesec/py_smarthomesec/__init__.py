"""
py_smarthomesec - Python library for SmartHomeSec alarm systems (VESTA/Climax).

Basic usage:
    from py_smarthomesec import SmartHomesecAPI

    async with SmartHomesecAPI(username="user", password="pass") as client:
        status = await client.get_panel_status()
        print(status.primary_alarm.state)
"""

__version__ = "0.1.0"

# Public exports
from py_smarthomesec.api import SmartHomesecAPI
from py_smarthomesec.auth import AuthManager
from py_smarthomesec.const import AlarmMode, AlarmState, DeviceType
from py_smarthomesec.exceptions import (
    APIError,
    AuthenticationError,
    ConnectionError,
    DeviceError,
    DeviceNotFoundError,
    InvalidCredentialsError,
    InvalidResponseError,
    RateLimitError,
    ServerError,
    SessionExpiredError,
    SmartHomesecError,
    TimeoutError,
    ValidationError,
)
from py_smarthomesec.models import (
    AlarmArea,
    AlarmModeRequest,
    ContactSensor,
    Credentials,
    Device,
    IPCamera,
    Keypad,
    LoginResponse,
    PanelStatus,
    PIRSensor,
    Session,
)
from py_smarthomesec.websocket import EventType, WebSocketClient, WebSocketEvent
from py_smarthomesec.coordinator import (
    CoordinatorState,
    DataUpdateCoordinator,
    PanelStatusCoordinator,
    UpdateResult,
)

__all__ = [
    # Version
    "__version__",
    # Client
    "SmartHomesecAPI",
    "AuthManager",
    # WebSocket
    "WebSocketClient",
    "WebSocketEvent",
    "EventType",
    # Coordinator
    "DataUpdateCoordinator",
    "PanelStatusCoordinator",
    "CoordinatorState",
    "UpdateResult",
    # Enums
    "AlarmMode",
    "AlarmState",
    "DeviceType",
    # Exceptions
    "SmartHomesecError",
    "AuthenticationError",
    "InvalidCredentialsError",
    "SessionExpiredError",
    "APIError",
    "ConnectionError",
    "TimeoutError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
    "InvalidResponseError",
    "DeviceError",
    "DeviceNotFoundError",
    # Models
    "Credentials",
    "LoginResponse",
    "Session",
    "Device",
    "ContactSensor",
    "PIRSensor",
    "Keypad",
    "IPCamera",
    "AlarmArea",
    "AlarmModeRequest",
    "PanelStatus",
]
