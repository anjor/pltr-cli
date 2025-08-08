"""
Configuration settings management for pltr CLI.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any


class Settings:
    """Manages application settings and configuration."""

    def __init__(self):
        """Initialize settings manager."""
        self.config_dir = self._get_config_dir()
        self.settings_file = self.config_dir / "settings.json"
        self._ensure_config_dir()
        self._settings = self._load_settings()

    def _get_config_dir(self) -> Path:
        """Get the configuration directory path."""
        # Follow XDG Base Directory specification
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            return Path(xdg_config_home) / "pltr"

        # Default to ~/.config/pltr
        return Path.home() / ".config" / "pltr"

    def _ensure_config_dir(self) -> None:
        """Ensure configuration directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file."""
        if not self.settings_file.exists():
            return self._get_default_settings()

        try:
            with open(self.settings_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return self._get_default_settings()

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings."""
        return {
            "default_profile": "default",
            "output_format": "table",
            "color_output": True,
            "page_size": 20,
            "timeout": 30,
            "verify_ssl": True,
        }

    def save(self) -> None:
        """Save settings to file."""
        with open(self.settings_file, "w") as f:
            json.dump(self._settings, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.

        Args:
            key: Setting key
            default: Default value if key doesn't exist

        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a setting value.

        Args:
            key: Setting key
            value: Setting value
        """
        self._settings[key] = value
        self.save()

    def update(self, settings: Dict[str, Any]) -> None:
        """
        Update multiple settings.

        Args:
            settings: Dictionary of settings to update
        """
        self._settings.update(settings)
        self.save()

    def reset(self) -> None:
        """Reset settings to defaults."""
        self._settings = self._get_default_settings()
        self.save()

    def get_all(self) -> Dict[str, Any]:
        """Get all settings."""
        return self._settings.copy()
