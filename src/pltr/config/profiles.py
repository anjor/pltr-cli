"""
Profile management for pltr CLI.
"""

import json
from typing import List, Optional

from .settings import Settings


class ProfileManager:
    """Manages authentication profiles."""

    def __init__(self):
        """Initialize profile manager."""
        self.settings = Settings()
        self.profiles_file = self.settings.config_dir / "profiles.json"
        self._profiles = self._load_profiles()

    def _load_profiles(self) -> dict:
        """Load profiles from file."""
        if not self.profiles_file.exists():
            return {"profiles": [], "default": None}

        try:
            with open(self.profiles_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"profiles": [], "default": None}

    def _save_profiles(self) -> None:
        """Save profiles to file."""
        with open(self.profiles_file, "w") as f:
            json.dump(self._profiles, f, indent=2)

    def add_profile(self, profile: str) -> None:
        """
        Add a new profile.

        Args:
            profile: Profile name
        """
        if profile not in self._profiles["profiles"]:
            self._profiles["profiles"].append(profile)
            self._save_profiles()

    def remove_profile(self, profile: str) -> None:
        """
        Remove a profile.

        Args:
            profile: Profile name
        """
        if profile in self._profiles["profiles"]:
            self._profiles["profiles"].remove(profile)

            # If this was the default profile, clear the default
            if self._profiles["default"] == profile:
                self._profiles["default"] = None
                # Set a new default if there are other profiles
                if self._profiles["profiles"]:
                    self._profiles["default"] = self._profiles["profiles"][0]

            self._save_profiles()

    def list_profiles(self) -> List[str]:
        """
        List all profiles.

        Returns:
            List of profile names
        """
        return self._profiles["profiles"].copy()

    def get_default(self) -> Optional[str]:
        """
        Get the default profile.

        Returns:
            Default profile name or None
        """
        return self._profiles["default"]

    def set_default(self, profile: str) -> None:
        """
        Set the default profile.

        Args:
            profile: Profile name
        """
        if profile in self._profiles["profiles"]:
            self._profiles["default"] = profile
            self._save_profiles()
            # Also update in settings
            self.settings.set("default_profile", profile)

    def profile_exists(self, profile: str) -> bool:
        """
        Check if a profile exists.

        Args:
            profile: Profile name

        Returns:
            True if profile exists, False otherwise
        """
        return profile in self._profiles["profiles"]

    def get_active_profile(self) -> Optional[str]:
        """
        Get the active profile (from environment or default).

        Returns:
            Active profile name
        """
        import os

        # Check environment variable first
        env_profile = os.environ.get("PLTR_PROFILE")
        if env_profile and self.profile_exists(env_profile):
            return env_profile

        # Fall back to default
        return self.get_default()
