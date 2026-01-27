"""
Exceptions for the py_smarthomesec library.

Exception hierarchy:

SmartHomesecError (base)
├── AuthenticationError
│   ├── InvalidCredentialsError
│   ├── SessionExpiredError
│   └── AuthenticationTimeoutError
├── APIError
│   ├── ConnectionError
│   ├── TimeoutError
│   ├── RateLimitError
│   └── ServerError
├── ValidationError
│   └── InvalidResponseError
└── DeviceError
    ├── DeviceNotFoundError
    └── DeviceUnavailableError
"""

from __future__ import annotations

from typing import Any


class SmartHomesecError(Exception):
    """Base exception for all py_smarthomesec errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# =============================================================================
# Authentication errors
# =============================================================================


class AuthenticationError(SmartHomesecError):
    """Authentication-related error."""

    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid credentials (wrong username/password)."""

    def __init__(self, username: str | None = None) -> None:
        message = "Invalid credentials"
        details = {"username": username} if username else {}
        super().__init__(message, details)


class SessionExpiredError(AuthenticationError):
    """Session expired, re-authentication required."""

    def __init__(self, token_hint: str | None = None) -> None:
        message = "Session expired, re-authentication required"
        details = {"token_hint": token_hint[:10] + "..."} if token_hint else {}
        super().__init__(message, details)


class AuthenticationTimeoutError(AuthenticationError):
    """Timeout during authentication attempt."""

    def __init__(self, timeout_seconds: float) -> None:
        message = f"Authentication timed out after {timeout_seconds}s"
        super().__init__(message, {"timeout": timeout_seconds})


# =============================================================================
# API / Network errors
# =============================================================================


class APIError(SmartHomesecError):
    """Error during an API call."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        endpoint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        full_details = details or {}
        if status_code is not None:
            full_details["status_code"] = status_code
        if endpoint:
            full_details["endpoint"] = endpoint
        super().__init__(message, full_details)
        self.status_code = status_code
        self.endpoint = endpoint


class ConnectionError(APIError):
    """Cannot connect to the server."""

    def __init__(self, host: str, reason: str | None = None) -> None:
        message = f"Cannot connect to {host}"
        if reason:
            message += f": {reason}"
        super().__init__(message, details={"host": host, "reason": reason})


class TimeoutError(APIError):
    """API call timeout."""

    def __init__(
        self, endpoint: str, timeout_seconds: float, method: str = "GET"
    ) -> None:
        message = f"{method} {endpoint} timed out after {timeout_seconds}s"
        super().__init__(
            message,
            endpoint=endpoint,
            details={"timeout": timeout_seconds, "method": method},
        )


class RateLimitError(APIError):
    """Too many requests, rate limit exceeded."""

    def __init__(
        self, endpoint: str, retry_after: int | None = None
    ) -> None:
        message = "Rate limit exceeded"
        details: dict[str, Any] = {}
        if retry_after:
            message += f", retry after {retry_after}s"
            details["retry_after"] = retry_after
        super().__init__(message, status_code=429, endpoint=endpoint, details=details)
        self.retry_after = retry_after


class ServerError(APIError):
    """Server error (5xx)."""

    def __init__(
        self, endpoint: str, status_code: int, response_body: str | None = None
    ) -> None:
        message = f"Server error {status_code}"
        details = {"response_body": response_body[:200]} if response_body else {}
        super().__init__(message, status_code=status_code, endpoint=endpoint, details=details)


# =============================================================================
# Validation errors
# =============================================================================


class ValidationError(SmartHomesecError):
    """Data validation error."""

    pass


class InvalidResponseError(ValidationError):
    """Invalid or malformed API response."""

    def __init__(
        self,
        message: str,
        endpoint: str | None = None,
        raw_response: str | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if endpoint:
            details["endpoint"] = endpoint
        if raw_response:
            details["raw_response"] = raw_response[:500]
        super().__init__(message, details)


# =============================================================================
# Device-related errors
# =============================================================================


class DeviceError(SmartHomesecError):
    """Device-related error."""

    def __init__(self, message: str, device_id: str | None = None) -> None:
        details = {"device_id": device_id} if device_id else {}
        super().__init__(message, details)
        self.device_id = device_id


class DeviceNotFoundError(DeviceError):
    """Device not found."""

    def __init__(self, device_id: str) -> None:
        super().__init__(f"Device not found: {device_id}", device_id)


class DeviceUnavailableError(DeviceError):
    """Device unavailable (offline, low battery, etc.)."""

    def __init__(self, device_id: str, reason: str | None = None) -> None:
        message = f"Device unavailable: {device_id}"
        if reason:
            message += f" ({reason})"
        super().__init__(message, device_id)
