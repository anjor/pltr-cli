"""
Token-based authentication for Palantir Foundry.
"""

from typing import Dict, Optional, Any

from .base import (
    AuthProvider,
    InvalidCredentialsError,
    MissingCredentialsError,
    normalize_host,
)


class TokenAuthProvider(AuthProvider):
    """Authentication provider using bearer tokens."""

    def __init__(self, token: Optional[str] = None, host: Optional[str] = None):
        """
        Initialize token authentication.

        The provider uses exactly the values it is given. Environment variables
        are read by ``AuthManager``, never here, so they can't fill gaps in (or
        silently override) a stored profile.

        Args:
            token: Bearer token for authentication
            host: Foundry host, with or without ``https://``
                (e.g., 'your-stack.palantirfoundry.com')
        """
        self.token = token
        self.host = host
        self._auth: Optional[Any] = None

        if not self.token:
            raise MissingCredentialsError("Token is required for authentication")
        if not self.host or not normalize_host(self.host):
            raise MissingCredentialsError("Host URL is required for authentication")

    def get_auth(self) -> Any:
        """Return the foundry_sdk auth object (created once) that clients use."""
        if self._auth is None:
            from foundry_sdk import UserTokenAuth

            self._auth = UserTokenAuth(token=self.token)  # type: ignore[arg-type]
        return self._auth

    def get_client(self) -> Any:
        """Return an authenticated Foundry client."""
        from foundry_sdk import FoundryClient

        return FoundryClient(
            auth=self.get_auth(),
            hostname=normalize_host(self.host),  # type: ignore[arg-type]
        )

    def validate(self) -> bool:
        """Validate authentication credentials."""
        try:
            # Builds the client only; this does not contact Foundry.
            # `pltr verify` checks credentials against the API (User.get_current).
            self.get_client()
            return True
        except Exception as e:
            raise InvalidCredentialsError(f"Token validation failed: {e}")

    def get_config(self) -> Dict[str, Any]:
        """Return authentication configuration."""
        return {
            "type": "token",
            "host": self.host,
            "token": "***"
            + (self.token[-4:] if self.token and len(self.token) > 4 else ""),
        }
