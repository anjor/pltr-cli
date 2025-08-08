"""
Secure credential storage using keyring.
"""

import json
import keyring
from typing import Dict, Any

from .base import ProfileNotFoundError


class CredentialStorage:
    """Manages secure storage of authentication credentials."""

    SERVICE_NAME = "pltr-cli"

    def __init__(self):
        """Initialize credential storage."""
        self.keyring = keyring

    def save_profile(self, profile: str, credentials: Dict[str, Any]) -> None:
        """
        Save credentials for a profile.

        Args:
            profile: Profile name
            credentials: Dictionary of credentials to store
        """
        # Convert credentials to JSON string for storage
        credentials_json = json.dumps(credentials)
        self.keyring.set_password(self.SERVICE_NAME, profile, credentials_json)

    def get_profile(self, profile: str) -> Dict[str, Any]:
        """
        Retrieve credentials for a profile.

        Args:
            profile: Profile name

        Returns:
            Dictionary of stored credentials

        Raises:
            ProfileNotFoundError: If profile doesn't exist
        """
        credentials_json = self.keyring.get_password(self.SERVICE_NAME, profile)
        if not credentials_json:
            raise ProfileNotFoundError(f"Profile '{profile}' not found")

        return json.loads(credentials_json)

    def delete_profile(self, profile: str) -> None:
        """
        Delete a profile's credentials.

        Args:
            profile: Profile name
        """
        try:
            self.keyring.delete_password(self.SERVICE_NAME, profile)
        except keyring.errors.PasswordDeleteError:
            raise ProfileNotFoundError(f"Profile '{profile}' not found")

    def list_profiles(self) -> list:
        """
        List all available profiles.

        Returns:
            List of profile names
        """
        # Note: keyring doesn't provide a direct way to list all usernames
        # for a service, so we'll need to store this separately in config
        # This is a placeholder that will be integrated with config/profiles.py
        return []

    def profile_exists(self, profile: str) -> bool:
        """
        Check if a profile exists.

        Args:
            profile: Profile name

        Returns:
            True if profile exists, False otherwise
        """
        credentials = self.keyring.get_password(self.SERVICE_NAME, profile)
        return credentials is not None
