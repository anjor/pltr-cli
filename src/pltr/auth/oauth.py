"""
OAuth2 client authentication for Palantir Foundry.
"""

from typing import Dict, Optional, Any

from .base import (
    AuthProvider,
    InvalidCredentialsError,
    MissingCredentialsError,
    normalize_host,
)


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

        The provider uses exactly the values it is given. Environment variables
        are read by ``AuthManager``, never here, so they can't fill gaps in (or
        silently override) a stored profile.

        Args:
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            host: Foundry host, with or without ``https://``
                (e.g., 'your-stack.palantirfoundry.com')
            scopes: List of scopes to request (default: all scopes granted to
                the client)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.host = host
        self.scopes = scopes or []
        self._auth: Optional[Any] = None

        if not self.client_id:
            raise MissingCredentialsError(
                "Client ID is required for OAuth authentication"
            )
        if not self.client_secret:
            raise MissingCredentialsError(
                "Client secret is required for OAuth authentication"
            )
        if not self.host or not normalize_host(self.host):
            raise MissingCredentialsError(
                "Host URL is required for OAuth authentication"
            )

    def get_auth(self) -> Any:
        """
        Return the foundry_sdk auth object (created once) that clients use.

        It gets its hostname from the FoundryClient it is given to, and shares
        one token (requested on first use, then refreshed) across its clients.
        """
        if self._auth is None:
            from foundry_sdk import ConfidentialClientAuth

            self._auth = ConfidentialClientAuth(
                client_id=self.client_id,  # type: ignore[arg-type]
                client_secret=self.client_secret,  # type: ignore[arg-type]
                scopes=self.scopes,
            )
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
