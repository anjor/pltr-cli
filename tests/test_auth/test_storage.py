"""
Tests for credential storage.
"""

import pytest
import json
from pltr.auth.storage import CredentialStorage
from pltr.auth.base import ProfileNotFoundError


class TestCredentialStorage:
    """Tests for CredentialStorage."""

    def test_init(self, mock_keyring):
        """Test initialization."""
        storage = CredentialStorage()
        assert storage.SERVICE_NAME == "pltr-cli"
        assert storage.keyring is not None

    def test_save_profile(self, mock_keyring):
        """Test saving a profile."""
        storage = CredentialStorage()
        credentials = {
            "auth_type": "token",
            "host": "https://test.palantirfoundry.com",
            "token": "test_token",
        }

        storage.save_profile("test_profile", credentials)

        # Verify keyring.set_password was called correctly
        mock_keyring["set"].assert_called_once_with(
            "pltr-cli", "test_profile", json.dumps(credentials)
        )

    def test_get_profile_success(self, mock_credential_storage):
        """Test successfully retrieving a profile."""
        storage = mock_credential_storage
        credentials = {
            "auth_type": "token",
            "host": "https://test.palantirfoundry.com",
            "token": "test_token",
        }

        # Save first, then get to test round trip
        storage.save_profile("test_profile", credentials)
        result = storage.get_profile("test_profile")

        assert result == credentials

    def test_get_profile_not_found(self, mock_keyring):
        """Test retrieving a non-existent profile."""
        storage = CredentialStorage()

        # Setup mock to return None (profile not found)
        mock_keyring["get"].return_value = None

        with pytest.raises(
            ProfileNotFoundError, match="Profile 'nonexistent' not found"
        ):
            storage.get_profile("nonexistent")

    def test_get_profile_invalid_json(self, mock_keyring):
        """Test retrieving profile with corrupted JSON data."""
        storage = CredentialStorage()

        # Setup mock to return invalid JSON
        mock_keyring["get"].return_value = "invalid json {"

        # Should raise ProfileNotFoundError when JSON is corrupted
        with pytest.raises(ProfileNotFoundError):
            storage.get_profile("corrupted_profile")

    def test_delete_profile_success(self, mock_keyring):
        """Test successfully deleting a profile."""
        storage = CredentialStorage()

        storage.delete_profile("test_profile")

        mock_keyring["delete"].assert_called_once_with("pltr-cli", "test_profile")

    def test_delete_profile_not_found(self, mock_keyring):
        """Test deleting a non-existent profile."""
        import keyring.errors

        storage = CredentialStorage()

        # Setup mock to raise PasswordDeleteError
        mock_keyring["delete"].side_effect = keyring.errors.PasswordDeleteError()

        with pytest.raises(
            ProfileNotFoundError, match="Profile 'nonexistent' not found"
        ):
            storage.delete_profile("nonexistent")

    def test_profile_exists_true(self, mock_credential_storage):
        """Test checking if a profile exists (true case)."""
        storage = mock_credential_storage

        # Save a profile first
        storage.save_profile("test_profile", {"test": "data"})

        assert storage.profile_exists("test_profile") is True

    def test_profile_exists_false(self, mock_keyring):
        """Test checking if a profile exists (false case)."""
        storage = CredentialStorage()

        # Setup mock to return None
        mock_keyring["get"].return_value = None

        assert storage.profile_exists("nonexistent") is False
        mock_keyring["get"].assert_called_once_with("pltr-cli", "nonexistent")

    def test_list_profiles_placeholder(self, mock_keyring):
        """Test list_profiles returns empty list (placeholder implementation)."""
        storage = CredentialStorage()

        # The current implementation is a placeholder
        result = storage.list_profiles()
        assert result == []

    def test_save_and_get_round_trip(self, mock_keyring):
        """Test saving and retrieving credentials (round trip)."""
        storage = CredentialStorage()
        original_credentials = {
            "auth_type": "oauth",
            "host": "https://test.palantirfoundry.com",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["api:read"],
        }

        # Save the profile
        storage.save_profile("test_profile", original_credentials)

        # Retrieve the profile
        retrieved_credentials = storage.get_profile("test_profile")

        assert retrieved_credentials == original_credentials

    def test_multiple_profiles(self, mock_keyring):
        """Test handling multiple profiles."""
        storage = CredentialStorage()

        # Save multiple profiles
        profile1 = {"auth_type": "token", "token": "token1"}
        profile2 = {"auth_type": "oauth", "client_id": "id2"}

        storage.save_profile("profile1", profile1)
        storage.save_profile("profile2", profile2)

        # Verify both can be retrieved independently
        assert storage.get_profile("profile1") == profile1
        assert storage.get_profile("profile2") == profile2

        # Verify both exist
        assert storage.profile_exists("profile1") is True
        assert storage.profile_exists("profile2") is True
