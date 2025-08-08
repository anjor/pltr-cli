"""
Tests for settings management.
"""

import pytest
from pathlib import Path
from pltr.config.settings import Settings


class TestSettings:
    """Tests for Settings class."""

    def test_init_with_temp_dir(self, mock_settings):
        """Test initialization with temporary directory."""
        settings = mock_settings

        # Check default settings are loaded
        assert settings.get("default_profile") == "default"
        assert settings.get("output_format") == "table"
        assert settings.get("color_output") is True
        assert settings.get("page_size") == 20
        assert settings.get("timeout") == 30
        assert settings.get("verify_ssl") is True

    def test_get_existing_setting(self, mock_settings):
        """Test getting an existing setting."""
        settings = mock_settings

        assert settings.get("output_format") == "table"
        assert settings.get("page_size") == 20

    def test_get_nonexistent_setting_with_default(self, mock_settings):
        """Test getting a non-existent setting with default value."""
        settings = mock_settings

        assert settings.get("nonexistent_key", "default_value") == "default_value"

    def test_get_nonexistent_setting_without_default(self, mock_settings):
        """Test getting a non-existent setting without default value."""
        settings = mock_settings

        assert settings.get("nonexistent_key") is None

    def test_set_and_get_setting(self, mock_settings):
        """Test setting and getting a value."""
        settings = mock_settings

        settings.set("test_key", "test_value")
        assert settings.get("test_key") == "test_value"

    def test_set_overwrites_existing_setting(self, mock_settings):
        """Test that set overwrites existing settings."""
        settings = mock_settings

        original_value = settings.get("output_format")
        assert original_value == "table"

        settings.set("output_format", "json")
        assert settings.get("output_format") == "json"

    def test_update_multiple_settings(self, mock_settings):
        """Test updating multiple settings at once."""
        settings = mock_settings

        new_settings = {
            "output_format": "csv",
            "page_size": 50,
            "new_setting": "new_value",
        }

        settings.update(new_settings)

        assert settings.get("output_format") == "csv"
        assert settings.get("page_size") == 50
        assert settings.get("new_setting") == "new_value"
        # Unchanged settings should remain the same
        assert settings.get("color_output") is True

    def test_get_all_settings(self, mock_settings):
        """Test getting all settings."""
        settings = mock_settings

        all_settings = settings.get_all()

        # Should contain default settings
        assert "default_profile" in all_settings
        assert "output_format" in all_settings
        assert "color_output" in all_settings
        assert "page_size" in all_settings
        assert "timeout" in all_settings
        assert "verify_ssl" in all_settings

        # Should be a copy, not the original
        all_settings["test_key"] = "test_value"
        assert settings.get("test_key") is None

    def test_reset_settings(self, mock_settings):
        """Test resetting settings to defaults."""
        settings = mock_settings

        # Modify some settings
        settings.set("output_format", "json")
        settings.set("page_size", 100)
        settings.set("custom_setting", "custom_value")

        # Verify changes
        assert settings.get("output_format") == "json"
        assert settings.get("page_size") == 100
        assert settings.get("custom_setting") == "custom_value"

        # Reset
        settings.reset()

        # Verify defaults are restored
        assert settings.get("output_format") == "table"
        assert settings.get("page_size") == 20
        assert settings.get("custom_setting") is None

    def test_config_dir_creation(self, temp_config_dir):
        """Test that config directory is created."""
        # Mock the config dir path
        with pytest.raises(FileNotFoundError):
            # Directory shouldn't exist initially
            list((temp_config_dir / "nonexistent").iterdir())

        # Create settings which should create the directory
        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                Settings,
                "_get_config_dir",
                lambda self: temp_config_dir / "test_config",
            )
            Settings()

            # Directory should now exist
            assert (temp_config_dir / "test_config").exists()
            assert (temp_config_dir / "test_config").is_dir()

    def test_settings_persistence(self, temp_config_dir):
        """Test that settings are persisted to file."""
        config_dir = temp_config_dir / "test_settings"

        # Create first instance and set some values
        with pytest.MonkeyPatch.context() as m:
            m.setattr(Settings, "_get_config_dir", lambda self: config_dir)
            settings1 = Settings()
            settings1.set("test_persistence", "persisted_value")
            settings1.set("output_format", "json")

        # Create second instance and verify values are loaded
        with pytest.MonkeyPatch.context() as m:
            m.setattr(Settings, "_get_config_dir", lambda self: config_dir)
            settings2 = Settings()

            assert settings2.get("test_persistence") == "persisted_value"
            assert settings2.get("output_format") == "json"
            # Default values should also be present
            assert settings2.get("color_output") is True

    def test_corrupted_settings_file_fallback(self, temp_config_dir):
        """Test that corrupted settings file falls back to defaults."""
        config_dir = temp_config_dir / "test_corrupted"
        config_dir.mkdir(parents=True)

        # Create corrupted settings file
        settings_file = config_dir / "settings.json"
        settings_file.write_text("invalid json {")

        # Should fall back to defaults without error
        with pytest.MonkeyPatch.context() as m:
            m.setattr(Settings, "_get_config_dir", lambda self: config_dir)
            settings = Settings()

            # Should have default values
            assert settings.get("output_format") == "table"
            assert settings.get("color_output") is True

    def test_get_config_dir_xdg(self, temp_config_dir):
        """Test XDG config directory preference."""

        xdg_dir = temp_config_dir / "xdg_config"

        with pytest.MonkeyPatch.context() as m:
            m.setenv("XDG_CONFIG_HOME", str(xdg_dir))

            settings = Settings()
            expected_path = xdg_dir / "pltr"
            assert settings.config_dir == expected_path

    def test_get_config_dir_home_fallback(self, temp_config_dir):
        """Test fallback to ~/.config/pltr when XDG_CONFIG_HOME is not set."""

        home_dir = temp_config_dir / "fake_home"

        with pytest.MonkeyPatch.context() as m:
            # Unset XDG_CONFIG_HOME
            m.delenv("XDG_CONFIG_HOME", raising=False)
            m.setattr(Path, "home", lambda: home_dir)

            settings = Settings()
            expected_path = home_dir / ".config" / "pltr"
            assert settings.config_dir == expected_path
