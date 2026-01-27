"""Authentication manager for VESTA API."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import aiohttp

from ..const import (
    API_HOST,
    API_BASE_PATH,
    API_TIMEOUT,
    ENDPOINT_LOGIN,
)
from .exceptions import (
    VestaAuthenticationError,
    VestaConnectionError,
    VestaTokenExpiredError,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)

# Token refresh buffer (refresh 5 minutes before expiry)
TOKEN_REFRESH_BUFFER = 300


@dataclass
class AuthToken:
    """Represents an authentication token."""

    token: str
    user_id: str
    created_at: float = field(default_factory=time.time)
    expires_in: int = 3600  # Default 1 hour, adjust based on API response

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired or about to expire."""
        return time.time() >= (self.created_at + self.expires_in - TOKEN_REFRESH_BUFFER)

    @property
    def time_until_expiry(self) -> float:
        """Return seconds until token expires."""
        return max(0, (self.created_at + self.expires_in) - time.time())


class VestaAuthManager:
    """Manages authentication for VESTA API."""

    def __init__(
        self,
        username: str,
        password: str,
        session: ClientSession | None = None,
        host: str = API_HOST,
    ) -> None:
        """Initialize the auth manager."""
        self._username = username
        self._password = password
        self._password_hash = hashlib.md5(password.encode("utf-8")).hexdigest()
        self._host = host
        self._session = session
        self._owns_session = session is None
        self._token: AuthToken | None = None
        self._lock = asyncio.Lock()

    @property
    def token(self) -> str | None:
        """Return the current token."""
        return self._token.token if self._token else None

    @property
    def user_id(self) -> str | None:
        """Return the current user ID."""
        return self._token.user_id if self._token else None

    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated with a valid token."""
        return self._token is not None and not self._token.is_expired

    @property
    def auth_headers(self) -> dict[str, str]:
        """Return headers for authenticated requests."""
        if not self._token:
            return {}
        return {
            "cookie": (
                f"isPrivacy=1; api_token={self._token.token}; "
                f"id={self._token.user_id}; cookiePath=%2FByDemes%2F0%2F0%2F"
            ),
            "token": self._token.token,
        }

    async def _ensure_session(self) -> ClientSession:
        """Ensure we have an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def authenticate(self, force: bool = False) -> AuthToken:
        """Authenticate with the VESTA API.

        Args:
            force: Force re-authentication even if token is valid.

        Returns:
            AuthToken: The authentication token.

        Raises:
            VestaAuthenticationError: If authentication fails.
            VestaConnectionError: If connection fails.
        """
        async with self._lock:
            # Return existing token if valid and not forcing refresh
            if not force and self.is_authenticated:
                return self._token  # type: ignore

            _LOGGER.debug("Authenticating with VESTA API")

            session = await self._ensure_session()
            url = f"https://{self._host}/{API_BASE_PATH}/{ENDPOINT_LOGIN}"

            payload = {
                "account": self._username,
                "password": self._password_hash,
                "pw_encrypted": "hashed",
                "login_entry": "web",
            }

            headers = {
                "cookie": "isPrivacy=1;",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            }

            try:
                async with session.post(
                    url,
                    data=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
                ) as response:
                    if response.status == 401:
                        raise VestaAuthenticationError("Invalid credentials")
                    if response.status != 200:
                        body = await response.text()
                        raise VestaAuthenticationError(
                            f"Authentication failed with status {response.status}: {body}"
                        )

                    data = await response.json()

                    if "token" not in data:
                        raise VestaAuthenticationError("No token in response")

                    self._token = AuthToken(
                        token=data["token"],
                        user_id=str(data.get("data", {}).get("user_id", "")),
                    )

                    _LOGGER.debug("Successfully authenticated with VESTA API")
                    return self._token

            except aiohttp.ClientError as err:
                raise VestaConnectionError(
                    f"Failed to connect to VESTA API: {err}"
                ) from err

    async def ensure_valid_token(self) -> AuthToken:
        """Ensure we have a valid token, refreshing if needed.

        Returns:
            AuthToken: A valid authentication token.

        Raises:
            VestaAuthenticationError: If authentication fails.
        """
        if self._token is None or self._token.is_expired:
            return await self.authenticate(force=True)
        return self._token

    async def invalidate_token(self) -> None:
        """Invalidate the current token (call on 401 responses)."""
        async with self._lock:
            self._token = None
            _LOGGER.debug("Token invalidated")

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
            self._session = None
