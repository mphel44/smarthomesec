"""Async REST client for VESTA API."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import aiohttp

from ..const import (
    API_HOST,
    API_BASE_PATH,
    API_TIMEOUT,
    ENDPOINT_PANEL_CYCLE,
    ENDPOINT_PANEL_MODE,
)
from .auth import VestaAuthManager
from .exceptions import (
    VestaApiError,
    VestaConnectionError,
    VestaTokenExpiredError,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)


class VestaApiClient:
    """Async REST client for VESTA API."""

    def __init__(
        self,
        username: str,
        password: str,
        session: ClientSession | None = None,
        host: str = API_HOST,
    ) -> None:
        """Initialize the API client.

        Args:
            username: VESTA account username.
            password: VESTA account password (plain text).
            session: Optional aiohttp ClientSession to use.
            host: API host (default: smarthomesec.bydemes.com).
        """
        self._host = host
        self._session = session
        self._owns_session = session is None
        self._auth = VestaAuthManager(username, password, session, host)

    @property
    def auth(self) -> VestaAuthManager:
        """Return the auth manager."""
        return self._auth

    @property
    def token(self) -> str | None:
        """Return the current auth token."""
        return self._auth.token

    async def _ensure_session(self) -> ClientSession:
        """Ensure we have an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        """Make an authenticated request to the VESTA API.

        Args:
            method: HTTP method (GET or POST).
            endpoint: API endpoint (without base path).
            data: Request data for POST requests.
            retry_auth: Whether to retry with fresh auth on 401.

        Returns:
            dict: JSON response from the API.

        Raises:
            VestaApiError: If the API returns an error.
            VestaConnectionError: If connection fails.
            VestaTokenExpiredError: If token expired and retry failed.
        """
        await self._auth.ensure_valid_token()
        session = await self._ensure_session()

        url = f"https://{self._host}/{API_BASE_PATH}/{endpoint}"
        params = {"_": round(time.time() * 1000)}
        headers = {
            **self._auth.auth_headers,
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

        try:
            if method.upper() == "GET":
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
                ) as response:
                    return await self._handle_response(response, endpoint, retry_auth)
            else:
                async with session.post(
                    url,
                    params=params,
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
                ) as response:
                    return await self._handle_response(response, endpoint, retry_auth)

        except aiohttp.ClientError as err:
            raise VestaConnectionError(
                f"Connection error for {endpoint}: {err}"
            ) from err

    async def _handle_response(
        self,
        response: aiohttp.ClientResponse,
        endpoint: str,
        retry_auth: bool,
    ) -> dict[str, Any]:
        """Handle API response.

        Args:
            response: The aiohttp response object.
            endpoint: The endpoint that was called.
            retry_auth: Whether to retry with fresh auth on 401.

        Returns:
            dict: Parsed JSON response.

        Raises:
            VestaApiError: If the API returns an error.
            VestaTokenExpiredError: If token expired.
        """
        if response.status == 401:
            await self._auth.invalidate_token()
            if retry_auth:
                _LOGGER.debug("Token expired, re-authenticating")
                return await self._request(
                    response.method,
                    endpoint,
                    retry_auth=False,
                )
            raise VestaTokenExpiredError("Token expired and retry failed")

        if response.status == 400:
            body = await response.text()
            raise VestaApiError(
                f"Bad request to {endpoint}",
                status_code=400,
                response_body=body,
            )

        if response.status != 200:
            body = await response.text()
            raise VestaApiError(
                f"Request to {endpoint} failed",
                status_code=response.status,
                response_body=body,
            )

        try:
            return await response.json()
        except Exception as err:
            raise VestaApiError(f"Failed to parse response: {err}") from err

    async def async_get_panel_status(self) -> dict[str, Any]:
        """Get the current panel status including all devices and alarms.

        Returns:
            dict: Panel status data containing:
                - device_status: List of all devices
                - model: List of alarm areas/zones
        """
        response = await self._request("GET", ENDPOINT_PANEL_CYCLE)
        _LOGGER.debug("Panel status response keys: %s", response.get("data", {}).keys())
        return response.get("data", {})

    async def async_set_alarm_mode(
        self,
        area: int,
        mode: str,
        pin_code: str,
    ) -> dict[str, Any]:
        """Set the alarm mode for a specific area.

        Args:
            area: Area number (usually 1).
            mode: Alarm mode ('arm', 'home', 'disarm').
            pin_code: User PIN code for the panel.

        Returns:
            dict: API response.

        Raises:
            VestaApiError: If the command fails (e.g., wrong PIN).
        """
        payload = {
            "area": int(area),
            "pincode": int(pin_code),
            "mode": mode,
            "format": 1,
        }

        _LOGGER.debug("Setting alarm mode: area=%s, mode=%s", area, mode)
        return await self._request("POST", ENDPOINT_PANEL_MODE, data=payload)

    async def async_test_connection(self) -> bool:
        """Test the connection and authentication.

        Returns:
            bool: True if connection and auth succeeded.

        Raises:
            VestaAuthenticationError: If authentication fails.
            VestaConnectionError: If connection fails.
        """
        await self._auth.authenticate(force=True)
        # Verify we can actually fetch data
        await self.async_get_panel_status()
        return True

    async def close(self) -> None:
        """Close the client and release resources."""
        await self._auth.close()
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
            self._session = None
