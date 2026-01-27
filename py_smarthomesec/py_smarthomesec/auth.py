"""
Authentication manager for the SmartHomeSec/VESTA API.

Handles login, session storage, and automatic re-authentication.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

from py_smarthomesec.const import (
    API_PATH,
    COOKIE_PRIVACY,
    DEFAULT_BASE_URL,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_TIMEOUT,
    ENDPOINT_LOGIN,
)
from py_smarthomesec.exceptions import (
    AuthenticationError,
    AuthenticationTimeoutError,
    InvalidCredentialsError,
    InvalidResponseError,
    SessionExpiredError,
)
from py_smarthomesec.models.auth import (
    Credentials,
    LoginRequest,
    LoginResponse,
    Session,
)

if TYPE_CHECKING:
    from py_smarthomesec.api import SmartHomesecAPI

logger = logging.getLogger(__name__)


class AuthManager:
    """
    Authentication manager.

    Responsibilities:
    - Perform initial login
    - Maintain active session
    - Handle automatic re-authentication on expiration
    - Provide headers/cookies for authenticated requests
    """

    def __init__(
        self,
        credentials: Credentials,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize the authentication manager.

        Args:
            credentials: Login credentials.
            base_url: API base URL.
            timeout: Default timeout for requests.
        """
        self._credentials = credentials
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session: Session | None = None
        self._lock = asyncio.Lock()
        self._login_attempts = 0
        self._max_login_attempts = 3

    @property
    def is_authenticated(self) -> bool:
        """Indicates if an active session exists."""
        return self._session is not None

    @property
    def session(self) -> Session | None:
        """Returns the current session."""
        return self._session

    @property
    def token(self) -> str | None:
        """Returns the current token."""
        return self._session.token if self._session else None

    @property
    def user_id(self) -> str | None:
        """Returns the current user ID."""
        return self._session.user_id if self._session else None

    def get_auth_headers(self) -> dict[str, str]:
        """
        Returns authentication headers for requests.

        Raises:
            AuthenticationError: If no active session.
        """
        if not self._session:
            raise AuthenticationError("No active session, login required")

        self._session.touch()
        return {
            "cookie": self._session.build_cookie_header(),
            "token": self._session.token,
        }

    async def login(self, http_client: httpx.AsyncClient) -> Session:
        """
        Authenticate with the API.

        Args:
            http_client: HTTP client to use for the request.

        Returns:
            Session created after successful authentication.

        Raises:
            InvalidCredentialsError: Invalid credentials.
            AuthenticationTimeoutError: Login timeout.
            AuthenticationError: Other authentication error.
        """
        async with self._lock:
            # Avoid multiple simultaneous login attempts
            if self._session is not None:
                logger.debug("Session already exists, skipping login")
                return self._session

            self._login_attempts += 1
            if self._login_attempts > self._max_login_attempts:
                raise AuthenticationError(
                    f"Max login attempts ({self._max_login_attempts}) exceeded"
                )

            logger.debug(
                "Attempting login for user: %s (attempt %d/%d)",
                self._credentials.username,
                self._login_attempts,
                self._max_login_attempts,
            )

            url = f"{self._base_url}/{API_PATH}/{ENDPOINT_LOGIN}"
            login_request = LoginRequest.from_credentials(self._credentials)

            try:
                response = await http_client.post(
                    url,
                    data=login_request.model_dump(),
                    headers={
                        "cookie": f"{COOKIE_PRIVACY};",
                        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                    },
                    timeout=httpx.Timeout(self._timeout, connect=DEFAULT_CONNECT_TIMEOUT),
                )
            except httpx.TimeoutException as e:
                raise AuthenticationTimeoutError(self._timeout) from e
            except httpx.RequestError as e:
                raise AuthenticationError(f"Connection error during login: {e}") from e

            # Response analysis
            if response.status_code == 401:
                raise InvalidCredentialsError(self._credentials.username)

            if response.status_code == 400:
                raise AuthenticationError(
                    "Security error (400)",
                    details={"response": response.text[:200]},
                )

            if response.status_code != 200:
                raise AuthenticationError(
                    f"Unexpected status code: {response.status_code}",
                    details={"response": response.text[:200]},
                )

            # Parse JSON response
            try:
                json_data = response.json()
            except Exception as e:
                raise InvalidResponseError(
                    "Failed to parse login response",
                    endpoint=ENDPOINT_LOGIN,
                    raw_response=response.text,
                ) from e

            # Pydantic validation
            try:
                login_response = LoginResponse.model_validate(json_data)
            except Exception as e:
                raise InvalidResponseError(
                    f"Invalid login response structure: {e}",
                    endpoint=ENDPOINT_LOGIN,
                    raw_response=response.text,
                ) from e

            # Create session
            self._session = Session.from_login_response(login_response)
            self._login_attempts = 0  # Reset after success

            logger.info(
                "Login successful for user: %s (user_id: %s)",
                self._credentials.username,
                self._session.user_id,
            )

            return self._session

    async def ensure_authenticated(self, http_client: httpx.AsyncClient) -> Session:
        """
        Ensure a valid session exists, perform login if necessary.

        Args:
            http_client: HTTP client to use.

        Returns:
            Active session.
        """
        if self._session is None:
            return await self.login(http_client)
        return self._session

    async def refresh_session(self, http_client: httpx.AsyncClient) -> Session:
        """
        Force session refresh (re-login).

        Used after a 401/403 error indicating an expired session.

        Args:
            http_client: HTTP client to use.

        Returns:
            New session.
        """
        async with self._lock:
            logger.info("Refreshing session (forced re-authentication)")
            self._session = None

        return await self.login(http_client)

    def invalidate_session(self) -> None:
        """Invalidate the current session."""
        if self._session:
            logger.debug("Invalidating session")
            self._session = None

    def handle_auth_error(self, status_code: int) -> None:
        """
        Handle an authentication error received during an API call.

        Args:
            status_code: HTTP code received (401, 403).

        Raises:
            SessionExpiredError: If the session has expired.
        """
        if status_code in (401, 403):
            token_hint = self._session.token if self._session else None
            self.invalidate_session()
            raise SessionExpiredError(token_hint)
