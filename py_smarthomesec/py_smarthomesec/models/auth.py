"""
Models for authentication and session management.
"""

from datetime import datetime
from hashlib import md5

from pydantic import Field, SecretStr

from py_smarthomesec.models.base import SmartHomesecBaseModel


class Credentials(SmartHomesecBaseModel):
    """User credentials."""

    username: str = Field(..., min_length=1, description="Username / account")
    password: SecretStr = Field(..., min_length=1, description="Password")

    def get_password_hash(self) -> str:
        """Return the MD5 hash of the password (format expected by the API)."""
        return md5(self.password.get_secret_value().encode("utf-8")).hexdigest()


class LoginRequest(SmartHomesecBaseModel):
    """Login request payload for the VESTA API."""

    account: str = Field(..., description="Account name")
    password: str = Field(..., description="MD5 hashed password")
    pw_encrypted: str = Field(default="hashed", description="Indicates password is hashed")
    login_entry: str = Field(default="web", description="Login source")

    @classmethod
    def from_credentials(cls, credentials: Credentials) -> "LoginRequest":
        """Create a LoginRequest from Credentials."""
        return cls(
            account=credentials.username,
            password=credentials.get_password_hash(),
        )


class UserData(SmartHomesecBaseModel):
    """User data returned by the API."""

    user_id: str = Field(..., alias="user_id", description="User ID")
    user_name: str | None = Field(default=None, alias="user_name")
    account: str | None = Field(default=None)


class LoginResponse(SmartHomesecBaseModel):
    """API response on login."""

    token: str = Field(..., description="Authentication token")
    data: UserData = Field(..., description="User data")

    @property
    def user_id(self) -> str:
        """Shortcut to user ID."""
        return self.data.user_id


class Session(SmartHomesecBaseModel):
    """Active session with the VESTA server."""

    token: str = Field(..., description="Active authentication token")
    user_id: str = Field(..., description="Connected user ID")
    created_at: datetime = Field(default_factory=datetime.now)
    last_used_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_login_response(cls, response: LoginResponse) -> "Session":
        """Create a Session from a LoginResponse."""
        return cls(
            token=response.token,
            user_id=response.user_id,
        )

    def touch(self) -> None:
        """Update the last used timestamp."""
        self.last_used_at = datetime.now()

    def build_cookie_header(self) -> str:
        """Build the Cookie header value for authenticated requests."""
        return (
            f"isPrivacy=1; "
            f"api_token={self.token}; "
            f"id={self.user_id}; "
            f"cookiePath=%2FByDemes%2F0%2F0%2F"
        )

    @property
    def age_seconds(self) -> float:
        """Return the session age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()
