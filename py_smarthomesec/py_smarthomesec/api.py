"""
Low-level API client for SmartHomeSec/VESTA.

Handles HTTP calls with httpx, exponential retries, and auto-reconnection.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from py_smarthomesec.auth import AuthManager
from py_smarthomesec.const import (
    API_PATH,
    DEFAULT_BASE_URL,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    ENDPOINT_PANEL_CYCLE,
    ENDPOINT_PANEL_MODE,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    RETRY_EXPONENTIAL_BASE,
    RETRY_MAX_DELAY,
)
from py_smarthomesec.exceptions import (
    APIError,
    ConnectionError,
    InvalidResponseError,
    RateLimitError,
    ServerError,
    TimeoutError,
)
from py_smarthomesec.models.alarm import AlarmArea, AlarmMode, AlarmModeRequest
from py_smarthomesec.models.auth import Credentials
from py_smarthomesec.models.panel import PanelStatus

logger = logging.getLogger(__name__)


class SmartHomesecAPI:
    """
    Low-level API client for SmartHomeSec.

    Handles:
    - Async HTTP GET/POST calls with httpx
    - Exponential retries on network errors
    - Automatic re-authentication on 401/403
    - Cache-busting with timestamps
    """

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize the API client.

        Args:
            username: Username.
            password: Password.
            base_url: API base URL.
            timeout: Default timeout for requests.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        # Authentication manager
        credentials = Credentials(username=username, password=password)
        self._auth = AuthManager(credentials, base_url, timeout)

        # HTTP client (created in __aenter__)
        self._client: httpx.AsyncClient | None = None
        self._owns_client = False

    @property
    def is_connected(self) -> bool:
        """Indicates if the client is connected and authenticated."""
        return self._client is not None and self._auth.is_authenticated

    async def __aenter__(self) -> "SmartHomesecAPI":
        """Context manager entry - creates HTTP client and authenticates."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout, connect=DEFAULT_CONNECT_TIMEOUT),
            follow_redirects=True,
        )
        self._owns_client = True
        await self._auth.login(self._client)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - closes HTTP client."""
        if self._client and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def connect(self) -> None:
        """
        Establish connection and perform authentication.

        Alternative to context manager for manual management.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=DEFAULT_CONNECT_TIMEOUT),
                follow_redirects=True,
            )
            self._owns_client = True
        await self._auth.login(self._client)

    async def disconnect(self) -> None:
        """Close the connection."""
        if self._client and self._owns_client:
            await self._client.aclose()
            self._client = None
        self._auth.invalidate_session()

    def _build_url(self, endpoint: str) -> str:
        """Build the full URL for an endpoint."""
        return f"{self._base_url}/{API_PATH}/{endpoint}"

    def _get_cache_buster(self) -> str:
        """Return a timestamp for cache-busting."""
        return str(int(time.time() * 1000))

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auto_reauth: bool = True,
    ) -> dict[str, Any]:
        """
        Perform an HTTP request with retries and auto-reconnection.

        Args:
            method: HTTP method (GET, POST).
            endpoint: Relative endpoint.
            data: POST data (form-encoded).
            params: Query string parameters.
            auto_reauth: Enable automatic re-authentication on 401/403.

        Returns:
            Parsed JSON response.

        Raises:
            ConnectionError: Cannot connect.
            TimeoutError: Request timeout.
            ServerError: Server error (5xx).
            RateLimitError: Rate limit exceeded.
            APIError: Other API error.
        """
        if self._client is None:
            raise ConnectionError(self._base_url, "Client not initialized, call connect() first")

        url = self._build_url(endpoint)

        # Add cache-buster
        request_params = params or {}
        request_params["_"] = self._get_cache_buster()

        # Headers with authentication
        headers = {**DEFAULT_HEADERS, **self._auth.get_auth_headers()}

        async def _do_request() -> httpx.Response:
            """Execute the request (used by tenacity)."""
            if method.upper() == "GET":
                return await self._client.get(url, params=request_params, headers=headers)
            elif method.upper() == "POST":
                return await self._client.post(
                    url, data=data, params=request_params, headers=headers
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        # Retries with exponential backoff
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(MAX_RETRIES),
                wait=wait_exponential(
                    multiplier=RETRY_BASE_DELAY,
                    min=RETRY_BASE_DELAY,
                    max=RETRY_MAX_DELAY,
                    exp_base=RETRY_EXPONENTIAL_BASE,
                ),
                retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
                reraise=True,
            ):
                with attempt:
                    logger.debug(
                        "%s %s (attempt %d/%d)",
                        method,
                        endpoint,
                        attempt.retry_state.attempt_number,
                        MAX_RETRIES,
                    )
                    response = await _do_request()

        except httpx.TimeoutException as e:
            raise TimeoutError(endpoint, self._timeout, method) from e
        except httpx.NetworkError as e:
            raise ConnectionError(self._base_url, str(e)) from e
        except RetryError as e:
            # All attempts failed
            raise ConnectionError(
                self._base_url, f"All {MAX_RETRIES} retry attempts failed"
            ) from e

        # Handle response codes
        return await self._handle_response(
            response, endpoint, method, data, params, auto_reauth
        )

    async def _handle_response(
        self,
        response: httpx.Response,
        endpoint: str,
        method: str,
        data: dict[str, Any] | None,
        params: dict[str, Any] | None,
        auto_reauth: bool,
    ) -> dict[str, Any]:
        """
        Process the HTTP response.

        Args:
            response: httpx response.
            endpoint: Called endpoint.
            method: HTTP method used.
            data: Sent data.
            params: Query parameters.
            auto_reauth: Enable re-authentication.

        Returns:
            JSON response data.
        """
        status = response.status_code

        # Authentication expired -> re-login and retry
        if status in (401, 403) and auto_reauth:
            logger.warning(
                "Auth error %d on %s %s, attempting re-authentication",
                status,
                method,
                endpoint,
            )
            await self._auth.refresh_session(self._client)
            # Retry once after re-auth
            return await self._request(
                method, endpoint, data, params, auto_reauth=False
            )

        # Authentication error without auto-reauth
        if status in (401, 403):
            self._auth.handle_auth_error(status)

        # Rate limit
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                endpoint, int(retry_after) if retry_after else None
            )

        # Server error
        if status >= 500:
            raise ServerError(endpoint, status, response.text)

        # Client error (4xx other than auth)
        if status >= 400:
            raise APIError(
                f"Client error: {status}",
                status_code=status,
                endpoint=endpoint,
                details={"response": response.text[:500]},
            )

        # Success - parse JSON
        try:
            return response.json()
        except Exception as e:
            raise InvalidResponseError(
                f"Failed to parse JSON response: {e}",
                endpoint=endpoint,
                raw_response=response.text,
            ) from e

    # =========================================================================
    # Public API methods
    # =========================================================================

    async def get_panel_status(self) -> PanelStatus:
        """
        Retrieve the complete panel state (devices and alarms).

        Returns:
            PanelStatus with all devices and alarm zones.
        """
        response = await self._request("GET", ENDPOINT_PANEL_CYCLE)
        return PanelStatus.from_api_response(response)

    async def set_alarm_mode(
        self,
        mode: AlarmMode | str,
        pin_code: int | str,
        area: int = 1,
    ) -> dict[str, Any]:
        """
        Change the alarm mode.

        Args:
            mode: Target mode (disarm, arm, home).
            pin_code: PIN code.
            area: Zone number (default: 1).

        Returns:
            API response.
        """
        if isinstance(mode, str):
            mode = AlarmMode.from_string(mode)

        request = AlarmModeRequest(
            area=area,
            mode=mode,
            pincode=pin_code,
        )

        logger.info("Setting alarm mode to %s for area %d", mode.value, area)

        return await self._request("POST", ENDPOINT_PANEL_MODE, data=request.to_payload())

    async def arm_away(self, pin_code: int | str, area: int = 1) -> dict[str, Any]:
        """Arm the alarm in away mode."""
        return await self.set_alarm_mode(AlarmMode.ARM, pin_code, area)

    async def arm_home(self, pin_code: int | str, area: int = 1) -> dict[str, Any]:
        """Arm the alarm in home mode."""
        return await self.set_alarm_mode(AlarmMode.HOME, pin_code, area)

    async def disarm(self, pin_code: int | str, area: int = 1) -> dict[str, Any]:
        """Disarm the alarm."""
        return await self.set_alarm_mode(AlarmMode.DISARM, pin_code, area)

    async def get_devices(self) -> list:
        """
        Retrieve the device list.

        Returns:
            List of devices (Device).
        """
        status = await self.get_panel_status()
        return status.devices

    async def get_alarm_areas(self) -> list[AlarmArea]:
        """
        Retrieve the alarm zone list.

        Returns:
            List of zones (AlarmArea).
        """
        status = await self.get_panel_status()
        return status.alarm_areas
