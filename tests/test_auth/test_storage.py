"""
Tests for credential storage.
"""

import pytest
import json

import keyring
import keyring.errors

from pltr.auth.storage import CredentialStorage
from pltr.auth.base import (
    KeyringUnavailableError,
    MissingCredentialsError,
    ProfileNotFoundError,
)


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

    @pytest.mark.parametrize("stored", ["invalid json {", '"a string"', "[1, 2]"])
    def test_get_profile_invalid_json(self, mock_keyring, stored):
        """Corrupted stored credentials give a clear error, not a JSON traceback."""
        storage = CredentialStorage()

        # The fixture's keyring reads this dict (its side_effect wins over
        # return_value, so setting return_value would not reach get_profile).
        mock_keyring["storage"]["pltr-cli:corrupted_profile"] = stored

        with pytest.raises(
            MissingCredentialsError,
            match="stored credentials of profile 'corrupted_profile' are unreadable",
        ):
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


def _get_work_profile(storage):
    return storage.get_profile("work")


def _check_work_profile(storage):
    return storage.profile_exists("work")


def _save_work_profile(storage):
    return storage.save_profile("work", {"auth_type": "token"})


def _delete_work_profile(storage):
    return storage.delete_profile("work")


class TestCredentialStorageWithoutKeyring:
    """A missing or failing keyring gives an error that points to env-var auth."""

    @pytest.fixture
    def no_backend(self, monkeypatch):
        def fail(*args):
            raise keyring.errors.NoKeyringError("No recommended backend was available.")

        for name in ("get_password", "set_password", "delete_password"):
            monkeypatch.setattr(keyring, name, fail)

    @pytest.mark.parametrize(
        "action, call",
        [
            ("read", _get_work_profile),
            ("read", _check_work_profile),
            ("save", _save_work_profile),
            ("delete", _delete_work_profile),
        ],
    )
    def test_missing_backend(self, no_backend, action, call):
        with pytest.raises(KeyringUnavailableError) as excinfo:
            call(CredentialStorage())

        message = str(excinfo.value)
        assert f"could not {action} the credentials of profile 'work'" in message
        assert "No recommended backend was available." in message
        assert "set FOUNDRY_HOST and FOUNDRY_TOKEN" in message
        assert "FOUNDRY_CLIENT_ID and FOUNDRY_CLIENT_SECRET" in message
        assert isinstance(excinfo.value.__cause__, keyring.errors.NoKeyringError)

    def test_backend_errors_of_any_kind_are_wrapped(self, monkeypatch):
        def fail(*args):
            raise OSError("D-Bus connection refused")

        monkeypatch.setattr(keyring, "get_password", fail)

        with pytest.raises(KeyringUnavailableError, match="D-Bus connection refused"):
            CredentialStorage().get_profile("work")

    def test_delete_of_a_missing_profile_is_still_not_found(self, monkeypatch):
        def fail(*args):
            raise keyring.errors.PasswordDeleteError("missing")

        monkeypatch.setattr(keyring, "delete_password", fail)

        with pytest.raises(ProfileNotFoundError, match="Profile 'work' not found"):
            CredentialStorage().delete_profile("work")

    def test_keyring_errors_are_reported_as_auth_errors(self):
        """Commands that catch MissingCredentialsError report it as an auth error."""
        assert issubclass(KeyringUnavailableError, MissingCredentialsError)
