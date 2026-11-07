"""
Tests for profile management.
"""

import pytest
from pltr.config.profiles import ProfileManager
from pltr.config.settings import Settings


class TestProfileManager:
    """Tests for ProfileManager class."""

    def test_init(self, mock_profile_manager):
        """Test initialization."""
        manager = mock_profile_manager

        # Should start with empty profiles
        assert manager.list_profiles() == []
        assert manager.get_default() is None

    def test_add_profile(self, mock_profile_manager):
        """Test adding a profile."""
        manager = mock_profile_manager

        manager.add_profile("test_profile")

        assert "test_profile" in manager.list_profiles()
        assert len(manager.list_profiles()) == 1

    def test_add_duplicate_profile(self, mock_profile_manager):
        """Test adding a duplicate profile (should not create duplicates)."""
        manager = mock_profile_manager

        manager.add_profile("test_profile")
        manager.add_profile("test_profile")  # Add same profile again

        profiles = manager.list_profiles()
        assert profiles.count("test_profile") == 1
        assert len(profiles) == 1

    def test_add_multiple_profiles(self, mock_profile_manager):
        """Test adding multiple profiles."""
        manager = mock_profile_manager

        manager.add_profile("profile1")
        manager.add_profile("profile2")
        manager.add_profile("profile3")

        profiles = manager.list_profiles()
        assert "profile1" in profiles
        assert "profile2" in profiles
        assert "profile3" in profiles
        assert len(profiles) == 3

    def test_remove_profile(self, mock_profile_manager):
        """Test removing a profile."""
        manager = mock_profile_manager

        manager.add_profile("test_profile")
        assert "test_profile" in manager.list_profiles()

        manager.remove_profile("test_profile")
        assert "test_profile" not in manager.list_profiles()

    def test_remove_nonexistent_profile(self, mock_profile_manager):
        """Test removing a profile that doesn't exist (should not error)."""
        manager = mock_profile_manager

        # Should not raise an error
        manager.remove_profile("nonexistent_profile")
        assert manager.list_profiles() == []

    def test_set_and_get_default(self, mock_profile_manager):
        """Test setting and getting default profile."""
        manager = mock_profile_manager

        manager.add_profile("test_profile")
        manager.set_default("test_profile")

        assert manager.get_default() == "test_profile"

    def test_set_default_nonexistent_profile(self, mock_profile_manager):
        """Test setting default to a profile that doesn't exist."""
        manager = mock_profile_manager

        # Should not set default if profile doesn't exist
        manager.set_default("nonexistent_profile")
        assert manager.get_default() is None

    def test_remove_default_profile_clears_default(self, mock_profile_manager):
        """Test that removing the default profile clears the default."""
        manager = mock_profile_manager

        manager.add_profile("profile1")
        manager.add_profile("profile2")
        manager.set_default("profile1")

        assert manager.get_default() == "profile1"

        manager.remove_profile("profile1")

        # Default should be set to another available profile
        assert manager.get_default() == "profile2"

    def test_remove_last_default_profile(self, mock_profile_manager):
        """Test removing the last profile clears default completely."""
        manager = mock_profile_manager

        manager.add_profile("only_profile")
        manager.set_default("only_profile")

        assert manager.get_default() == "only_profile"

        manager.remove_profile("only_profile")

        assert manager.get_default() is None
        assert manager.list_profiles() == []

    def test_profile_exists(self, mock_profile_manager):
        """Test checking if a profile exists."""
        manager = mock_profile_manager

        assert manager.profile_exists("test_profile") is False

        manager.add_profile("test_profile")

        assert manager.profile_exists("test_profile") is True
        assert manager.profile_exists("nonexistent") is False

    def test_get_active_profile_from_default(self, mock_profile_manager):
        """Test getting active profile from default."""
        manager = mock_profile_manager

        manager.add_profile("default_profile")
        manager.set_default("default_profile")

        assert manager.get_active_profile() == "default_profile"

    def test_get_active_profile_from_environment(self, mock_profile_manager):
        """Test getting active profile from environment variable."""

        manager = mock_profile_manager
        manager.add_profile("env_profile")
        manager.add_profile("default_profile")
        manager.set_default("default_profile")

        # Environment variable should take precedence
        with pytest.MonkeyPatch.context() as m:
            m.setenv("PLTR_PROFILE", "env_profile")

            assert manager.get_active_profile() == "env_profile"

    def test_get_active_profile_env_nonexistent(self, mock_profile_manager):
        """PLTR_PROFILE naming a missing profile is not silently replaced.

        Falling back to the default profile would run commands against a
        different profile than the one requested; commands now fail with
        "profile not found" instead (see tests/test_auth/test_headless_auth.py).
        """

        manager = mock_profile_manager
        manager.add_profile("default_profile")
        manager.set_default("default_profile")

        with pytest.MonkeyPatch.context() as m:
            m.setenv("PLTR_PROFILE", "nonexistent_profile")

            assert manager.get_active_profile() == "nonexistent_profile"

    def test_get_active_profile_ignores_empty_env(self, mock_profile_manager):
        """An empty PLTR_PROFILE counts as unset."""
        manager = mock_profile_manager
        manager.add_profile("default_profile")
        manager.set_default("default_profile")

        with pytest.MonkeyPatch.context() as m:
            m.setenv("PLTR_PROFILE", "  ")

            assert manager.get_active_profile() == "default_profile"

    def test_reading_profiles_does_not_create_the_config_dir(self, temp_config_dir):
        """Reading never creates the config dir (read-only or missing HOME)."""
        config_dir = temp_config_dir / "missing"

        with pytest.MonkeyPatch.context() as m:
            m.setattr(Settings, "_get_config_dir", lambda self: config_dir)
            m.delenv("PLTR_PROFILE", raising=False)
            manager = ProfileManager()

            assert manager.get_active_profile() is None
            assert manager.list_profiles() == []
            assert not config_dir.exists()

            manager.add_profile("first")

            assert (config_dir / "profiles.json").exists()

    def test_get_active_profile_no_default_no_env(self, mock_profile_manager):
        """Test getting active profile when no default or env is set."""
        manager = mock_profile_manager

        assert manager.get_active_profile() is None

    def test_profiles_persistence(self, temp_config_dir):
        """Test that profiles are persisted across instances."""
        from pltr.config.settings import Settings

        config_dir = temp_config_dir / "test_profiles"

        # Create first instance and add profiles
        with pytest.MonkeyPatch.context() as m:
            m.setattr(Settings, "_get_config_dir", lambda self: config_dir)
            manager1 = ProfileManager()
            manager1.add_profile("profile1")
            manager1.add_profile("profile2")
            manager1.set_default("profile1")

        # Create second instance and verify profiles are loaded
        with pytest.MonkeyPatch.context() as m:
            m.setattr(Settings, "_get_config_dir", lambda self: config_dir)
            manager2 = ProfileManager()

            profiles = manager2.list_profiles()
            assert "profile1" in profiles
            assert "profile2" in profiles
            assert manager2.get_default() == "profile1"

    def test_corrupted_profiles_file_fallback(self, temp_config_dir):
        """Test that corrupted profiles file falls back to empty state."""
        from pltr.config.settings import Settings

        config_dir = temp_config_dir / "test_corrupted_profiles"
        config_dir.mkdir(parents=True)

        # Create corrupted profiles file
        profiles_file = config_dir / "profiles.json"
        profiles_file.write_text("invalid json {")

        # Should fall back to empty state without error
        with pytest.MonkeyPatch.context() as m:
            m.setattr(Settings, "_get_config_dir", lambda self: config_dir)
            manager = ProfileManager()

            assert manager.list_profiles() == []
            assert manager.get_default() is None
