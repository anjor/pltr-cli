"""
Token-based authentication for Palantir Foundry.
"""

import os
from typing import Dict, Optional, Any

from .base import AuthProvider, InvalidCredentialsError, MissingCredentialsError


class TokenAuthProvider(AuthProvider):
    """Authentication provider using bearer tokens."""

    def __init__(self, token: Optional[str] = None, host: Optional[str] = None):
        """
        Initialize token authentication.

        Args:
            token: Bearer token for authentication
            host: Foundry host URL (e.g., 'https://your-stack.palantirfoundry.com')
        """
        self.token = token or os.environ.get("FOUNDRY_TOKEN")
        self.host = host or os.environ.get("FOUNDRY_HOST")

        if not self.token:
            raise MissingCredentialsError("Token is required for authentication")
        if not self.host:
            raise MissingCredentialsError("Host URL is required for authentication")

    def get_client(self) -> Any:
        """Return an authenticated Foundry client."""
        from foundry_sdk import FoundryClient, UserTokenAuth

        auth = UserTokenAuth(token=self.token)  # type: ignore
        return FoundryClient(auth=auth, hostname=self.host)

    def validate(self) -> bool:
        """Validate authentication credentials."""
        try:
            self.get_client()
            # Try to make a simple API call to validate the token
            # This would need to be replaced with an actual validation call
            # when the SDK provides one
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
