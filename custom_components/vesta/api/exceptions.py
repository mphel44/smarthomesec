"""Exceptions for the VESTA API client."""

from __future__ import annotations


class VestaError(Exception):
    """Base exception for VESTA integration."""

    def __init__(self, message: str = "An error occurred with the VESTA API") -> None:
        """Initialize the exception."""
        self.message = message
        super().__init__(self.message)


class VestaConnectionError(VestaError):
    """Exception raised when connection to VESTA API fails."""

    def __init__(self, message: str = "Failed to connect to VESTA API") -> None:
        """Initialize the exception."""
        super().__init__(message)


class VestaAuthenticationError(VestaError):
    """Exception raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed") -> None:
        """Initialize the exception."""
        super().__init__(message)


class VestaTokenExpiredError(VestaAuthenticationError):
    """Exception raised when the token has expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        """Initialize the exception."""
        super().__init__(message)


class VestaApiError(VestaError):
    """Exception raised when an API call fails."""

    def __init__(
        self,
        message: str = "API request failed",
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        """Initialize the exception."""
        self.status_code = status_code
        self.response_body = response_body
        full_message = message
        if status_code:
            full_message = f"{message} (HTTP {status_code})"
        super().__init__(full_message)


class VestaWebSocketError(VestaError):
    """Exception raised when WebSocket connection fails."""

    def __init__(self, message: str = "WebSocket connection failed") -> None:
        """Initialize the exception."""
        super().__init__(message)
