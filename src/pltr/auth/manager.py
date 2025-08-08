"""
Authentication manager for getting configured Foundry clients.
"""

from typing import Optional, Any

from .base import AuthProvider, ProfileNotFoundError, MissingCredentialsError
from .storage import CredentialStorage
from .token import TokenAuthProvider
from .oauth import OAuthClientProvider
from ..config.profiles import ProfileManager


class AuthManager:
    """Manages authentication and provides configured Foundry clients."""

    def __init__(self):
        """Initialize authentication manager."""
        self.storage = CredentialStorage()
        self.profile_manager = ProfileManager()

    def get_client(self, profile: Optional[str] = None) -> Any:
        """
        Get an authenticated Foundry client for a profile.

        Args:
            profile: Profile name (uses active profile if not specified)

        Returns:
            Configured FoundryClient instance

        Raises:
            ProfileNotFoundError: If profile doesn't exist
            MissingCredentialsError: If credentials are incomplete
        """
        # Determine which profile to use
        if not profile:
            profile = self.profile_manager.get_active_profile()
            if not profile:
                raise ProfileNotFoundError(
                    "No profile specified and no default profile configured. "
                    "Run 'pltr configure configure' to set up authentication."
                )

        # Get credentials for the profile
        try:
            credentials = self.storage.get_profile(profile)
        except ProfileNotFoundError:
            raise ProfileNotFoundError(
                f"Profile '{profile}' not found. "
                f"Run 'pltr configure configure --profile {profile}' to set it up."
            )

        # Create appropriate auth provider
        provider = self._create_provider(credentials)

        # Return authenticated client
        return provider.get_client()

    def _create_provider(self, credentials: dict) -> AuthProvider:
        """
        Create an auth provider from credentials.

        Args:
            credentials: Dictionary containing auth configuration

        Returns:
            Configured AuthProvider instance

        Raises:
            MissingCredentialsError: If auth type is unknown or credentials incomplete
        """
        auth_type = credentials.get("auth_type")
        host = credentials.get("host")

        if not auth_type:
            raise MissingCredentialsError(
                "Authentication type not specified in credentials"
            )
        if not host:
            raise MissingCredentialsError("Host URL not specified in credentials")

        if auth_type == "token":
            token = credentials.get("token")
            if not token:
                raise MissingCredentialsError("Token not found in credentials")
            return TokenAuthProvider(token=token, host=host)

        elif auth_type == "oauth":
            client_id = credentials.get("client_id")
            client_secret = credentials.get("client_secret")
            if not client_id or not client_secret:
                raise MissingCredentialsError("OAuth client credentials incomplete")
            return OAuthClientProvider(
                client_id=client_id,
                client_secret=client_secret,
                host=host,
                scopes=credentials.get("scopes", []),
            )

        else:
            raise MissingCredentialsError(f"Unknown authentication type: {auth_type}")

    def get_current_profile(self) -> Optional[str]:
        """
        Get the name of the currently active profile.

        Returns:
            Profile name or None if no profile is configured
        """
        return self.profile_manager.get_active_profile()

    def validate_profile(self, profile: Optional[str] = None) -> bool:
        """
        Validate that a profile's credentials work.

        Args:
            profile: Profile name (uses active profile if not specified)

        Returns:
            True if credentials are valid

        Raises:
            Exception if validation fails
        """
        self.get_client(profile)
        # The actual validation will happen when we try to use the client
        # in the verify command
        return True
