"""
OAuth2 client authentication for Palantir Foundry.
"""

import os
from typing import Dict, Optional, Any

from .base import AuthProvider, InvalidCredentialsError, MissingCredentialsError


class OAuthClientProvider(AuthProvider):
    """Authentication provider using OAuth2 client credentials."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        host: Optional[str] = None,
        scopes: Optional[list] = None,
    ):
        """
        Initialize OAuth2 client authentication.

        Args:
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            host: Foundry host URL (e.g., 'https://your-stack.palantirfoundry.com')
            scopes: List of scopes to request
        """
        self.client_id = client_id or os.environ.get("FOUNDRY_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("FOUNDRY_CLIENT_SECRET")
        self.host = host or os.environ.get("FOUNDRY_HOST")
        self.scopes = scopes or []

        if not self.client_id:
            raise MissingCredentialsError(
                "Client ID is required for OAuth authentication"
            )
        if not self.client_secret:
            raise MissingCredentialsError(
                "Client secret is required for OAuth authentication"
            )
        if not self.host:
            raise MissingCredentialsError(
                "Host URL is required for OAuth authentication"
            )

    def get_client(self) -> Any:
        """Return an authenticated Foundry client."""
        from foundry_sdk import FoundryClient, ConfidentialClientAuth

        auth = ConfidentialClientAuth(
            client_id=self.client_id,  # type: ignore
            client_secret=self.client_secret,  # type: ignore
            scopes=self.scopes,
        )
        return FoundryClient(auth=auth, hostname=self.host)

    def validate(self) -> bool:
        """Validate authentication credentials."""
        try:
            self.get_client()
            # Try to make a simple API call to validate the credentials
            # This would need to be replaced with an actual validation call
            # when the SDK provides one
            return True
        except Exception as e:
            raise InvalidCredentialsError(f"OAuth validation failed: {e}")

    def get_config(self) -> Dict[str, Any]:
        """Return authentication configuration."""
        return {
            "type": "oauth",
            "host": self.host,
            "client_id": self.client_id,
            "client_secret": "***"
            + (
                self.client_secret[-4:]
                if self.client_secret and len(self.client_secret) > 4
                else ""
            ),
            "scopes": self.scopes,
        }
