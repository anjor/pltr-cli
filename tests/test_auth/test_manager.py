"""
Tests for authentication manager.
"""

import os
import pytest
from unittest.mock import Mock, patch
from pltr.auth.manager import AuthManager
from pltr.auth.base import ProfileNotFoundError, MissingCredentialsError
from pltr.auth.token import TokenAuthProvider
from pltr.auth.oauth import OAuthClientProvider


class TestAuthManager:
    """Tests for AuthManager."""

    def test_init(self):
        """Test initialization."""
        with (
            patch("pltr.auth.manager.CredentialStorage") as mock_storage_class,
            patch("pltr.auth.manager.ProfileManager") as mock_profile_class,
        ):
            manager = AuthManager()

            # Storage should be lazy-loaded, so CredentialStorage not called yet
            assert manager._storage is None
            assert manager.profile_manager is not None
            mock_storage_class.assert_not_called()
            mock_profile_class.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)  # Clear env vars to test profile behavior
    @patch("pltr.auth.manager.CredentialStorage")
    @patch("pltr.auth.manager.ProfileManager")
    def test_get_client_with_explicit_profile(
        self, mock_profile_class, mock_storage_class
    ):
        """Test getting client with explicit profile name."""
        # Setup mocks
        mock_storage = Mock()
        mock_profile_manager = Mock()
        mock_storage_class.return_value = mock_storage
        mock_profile_class.return_value = mock_profile_manager

        # Mock credentials
        credentials = {
            "auth_type": "token",
            "host": "https://test.palantirfoundry.com",
            "token": "test_token",
        }
        mock_storage.get_profile.return_value = credentials

        # Mock the token provider
        with patch("pltr.auth.manager.TokenAuthProvider") as mock_token_provider_class:
            mock_provider = Mock()
            mock_client = Mock()
            mock_provider.get_client.return_value = mock_client
            mock_token_provider_class.return_value = mock_provider

            manager = AuthManager()
            result = manager.get_client("test_profile")

            # Verify storage was called with correct profile
            mock_storage.get_profile.assert_called_once_with("test_profile")

            # Verify token provider was created correctly
            mock_token_provider_class.assert_called_once_with(
                token="test_token", host="https://test.palantirfoundry.com"
            )

            # Verify client was returned
            assert result == mock_client

    @patch.dict(os.environ, {}, clear=True)  # Clear env vars to test profile behavior
    @patch("pltr.auth.manager.CredentialStorage")
    @patch("pltr.auth.manager.ProfileManager")
    def test_get_client_with_default_profile(
        self, mock_profile_class, mock_storage_class
    ):
        """Test getting client with default profile."""
        # Setup mocks
        mock_storage = Mock()
        mock_profile_manager = Mock()
        mock_storage_class.return_value = mock_storage
        mock_profile_class.return_value = mock_profile_manager

        # Mock default profile
        mock_profile_manager.get_active_profile.return_value = "default_profile"

        # Mock credentials
        credentials = {
            "auth_type": "token",
            "host": "https://test.palantirfoundry.com",
            "token": "test_token",
        }
        mock_storage.get_profile.return_value = credentials

        with patch("pltr.auth.manager.TokenAuthProvider") as mock_token_provider_class:
            mock_provider = Mock()
            mock_client = Mock()
            mock_provider.get_client.return_value = mock_client
            mock_token_provider_class.return_value = mock_provider

            manager = AuthManager()
            result = manager.get_client()  # No profile specified

            # Verify default profile was used
            mock_profile_manager.get_active_profile.assert_called_once()
            mock_storage.get_profile.assert_called_once_with("default_profile")

            assert result == mock_client

    @patch.dict(os.environ, {}, clear=True)  # Clear env vars to test profile behavior
    @patch("pltr.auth.manager.CredentialStorage")
    @patch("pltr.auth.manager.ProfileManager")
    def test_get_client_no_profile_configured(
        self, mock_profile_class, mock_storage_class
    ):
        """Test error when no profile is configured."""
        mock_profile_manager = Mock()
        mock_profile_class.return_value = mock_profile_manager

        # Mock no default profile
        mock_profile_manager.get_active_profile.return_value = None

        manager = AuthManager()

        with pytest.raises(
            ProfileNotFoundError,
            match="No profile specified and no default profile configured",
        ):
            manager.get_client()

    @patch.dict(os.environ, {}, clear=True)  # Clear env vars to test profile behavior
    @patch("pltr.auth.manager.CredentialStorage")
    @patch("pltr.auth.manager.ProfileManager")
    def test_get_client_profile_not_found(self, mock_profile_class, mock_storage_class):
        """Test error when profile is not found."""
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        # Mock profile not found
        mock_storage.get_profile.side_effect = ProfileNotFoundError("Profile not found")

        manager = AuthManager()

        with pytest.raises(
            ProfileNotFoundError, match="Profile 'missing_profile' not found"
        ):
            manager.get_client("missing_profile")

    def test_create_provider_token_auth(self):
        """Test creating token auth provider."""
        manager = AuthManager()
        credentials = {
            "auth_type": "token",
            "host": "https://test.palantirfoundry.com",
            "token": "test_token",
        }

        provider = manager._create_provider(credentials)

        assert isinstance(provider, TokenAuthProvider)
        assert provider.token == "test_token"
        assert provider.host == "https://test.palantirfoundry.com"

    def test_create_provider_oauth_auth(self):
        """Test creating OAuth auth provider."""
        manager = AuthManager()
        credentials = {
            "auth_type": "oauth",
            "host": "https://test.palantirfoundry.com",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["api:read"],
        }

        provider = manager._create_provider(credentials)

        assert isinstance(provider, OAuthClientProvider)
        assert provider.client_id == "test_client_id"
        assert provider.client_secret == "test_client_secret"
        assert provider.host == "https://test.palantirfoundry.com"
        assert provider.scopes == ["api:read"]

    def test_create_provider_missing_auth_type(self):
        """Test error when auth_type is missing."""
        manager = AuthManager()
        credentials = {
            "host": "https://test.palantirfoundry.com",
            "token": "test_token",
        }

        with pytest.raises(
            MissingCredentialsError, match="Authentication type not specified"
        ):
            manager._create_provider(credentials)

    def test_create_provider_missing_host(self):
        """Test error when host is missing."""
        manager = AuthManager()
        credentials = {"auth_type": "token", "token": "test_token"}

        with pytest.raises(MissingCredentialsError, match="Host URL not specified"):
            manager._create_provider(credentials)

    def test_create_provider_token_missing_token(self):
        """Test error when token is missing for token auth."""
        manager = AuthManager()
        credentials = {"auth_type": "token", "host": "https://test.palantirfoundry.com"}

        with pytest.raises(
            MissingCredentialsError, match="Token not found in credentials"
        ):
            manager._create_provider(credentials)

    def test_create_provider_oauth_missing_credentials(self):
        """Test error when OAuth credentials are missing."""
        manager = AuthManager()
        credentials = {
            "auth_type": "oauth",
            "host": "https://test.palantirfoundry.com",
            "client_id": "test_client_id",
            # Missing client_secret
        }

        with pytest.raises(
            MissingCredentialsError, match="OAuth client credentials incomplete"
        ):
            manager._create_provider(credentials)

    def test_create_provider_unknown_auth_type(self):
        """Test error with unknown auth type."""
        manager = AuthManager()
        credentials = {
            "auth_type": "unknown_type",
            "host": "https://test.palantirfoundry.com",
        }

        with pytest.raises(
            MissingCredentialsError, match="Unknown authentication type: unknown_type"
        ):
            manager._create_provider(credentials)

    @patch("pltr.auth.manager.ProfileManager")
    def test_get_current_profile(self, mock_profile_class):
        """Test getting current profile."""
        mock_profile_manager = Mock()
        mock_profile_class.return_value = mock_profile_manager
        mock_profile_manager.get_active_profile.return_value = "current_profile"

        manager = AuthManager()
        result = manager.get_current_profile()

        assert result == "current_profile"
        mock_profile_manager.get_active_profile.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "FOUNDRY_TOKEN": "env_token",
            "FOUNDRY_HOST": "https://env.palantirfoundry.com",
        },
    )
    @patch("pltr.auth.manager.TokenAuthProvider")
    def test_get_client_with_env_vars(self, mock_token_provider_class):
        """Test getting client with environment variables (bypasses keyring)."""
        mock_provider = Mock()
        mock_client = Mock()
        mock_provider.get_client.return_value = mock_client
        mock_token_provider_class.return_value = mock_provider

        # Should not initialize storage when env vars are present
        with (
            patch("pltr.auth.manager.CredentialStorage") as mock_storage_class,
            patch("pltr.auth.manager.ProfileManager"),
        ):
            manager = AuthManager()
            result = manager.get_client("any_profile")

            # Verify TokenAuthProvider was created with env vars
            mock_token_provider_class.assert_called_once_with(
                token="env_token", host="https://env.palantirfoundry.com"
            )

            # Verify storage was not accessed (keyring avoided)
            mock_storage_class.assert_not_called()

            # Verify client was returned
            assert result == mock_client

    @patch.dict(os.environ, {"FOUNDRY_TOKEN": "env_token"})  # Missing FOUNDRY_HOST
    @patch("pltr.auth.manager.CredentialStorage")
    @patch("pltr.auth.manager.ProfileManager")
    def test_get_client_with_partial_env_vars(
        self, mock_profile_class, mock_storage_class
    ):
        """Test getting client with only partial env vars falls back to profile."""
        # Setup mocks for fallback to profile
        mock_storage = Mock()
        mock_profile_manager = Mock()
        mock_storage_class.return_value = mock_storage
        mock_profile_class.return_value = mock_profile_manager

        mock_profile_manager.get_active_profile.return_value = "default_profile"

        credentials = {
            "auth_type": "token",
            "host": "https://test.palantirfoundry.com",
            "token": "profile_token",
        }
        mock_storage.get_profile.return_value = credentials

        with patch("pltr.auth.manager.TokenAuthProvider") as mock_token_provider_class:
            mock_provider = Mock()
            mock_client = Mock()
            mock_provider.get_client.return_value = mock_client
            mock_token_provider_class.return_value = mock_provider

            manager = AuthManager()
            result = manager.get_client()  # No profile specified

            # Should fall back to profile since env vars incomplete
            mock_storage.get_profile.assert_called_once_with("default_profile")
            mock_token_provider_class.assert_called_once_with(
                token="profile_token", host="https://test.palantirfoundry.com"
            )

            assert result == mock_client

    @patch.dict(os.environ, {}, clear=True)  # Clear all env vars
    @patch("pltr.auth.manager.CredentialStorage")
    @patch("pltr.auth.manager.ProfileManager")
    def test_get_client_without_env_vars_uses_profile(
        self, mock_profile_class, mock_storage_class
    ):
        """Test getting client without env vars uses profile (existing behavior)."""
        # Setup mocks
        mock_storage = Mock()
        mock_profile_manager = Mock()
        mock_storage_class.return_value = mock_storage
        mock_profile_class.return_value = mock_profile_manager

        # Mock credentials
        credentials = {
            "auth_type": "token",
            "host": "https://test.palantirfoundry.com",
            "token": "profile_token",
        }
        mock_storage.get_profile.return_value = credentials

        with patch("pltr.auth.manager.TokenAuthProvider") as mock_token_provider_class:
            mock_provider = Mock()
            mock_client = Mock()
            mock_provider.get_client.return_value = mock_client
            mock_token_provider_class.return_value = mock_provider

            manager = AuthManager()
            result = manager.get_client("test_profile")

            # Verify storage was called (keyring accessed)
            mock_storage.get_profile.assert_called_once_with("test_profile")

            # Verify token provider was created with profile credentials
            mock_token_provider_class.assert_called_once_with(
                token="profile_token", host="https://test.palantirfoundry.com"
            )

            assert result == mock_client

    @patch.dict(
        os.environ,
        {
            "FOUNDRY_TOKEN": "env_token",
            "FOUNDRY_HOST": "https://env.palantirfoundry.com",
        },
    )
    @patch("pltr.auth.manager.TokenAuthProvider")
    def test_validate_profile_with_env_vars(self, mock_token_provider_class):
        """Test validating profile with environment variables."""
        mock_provider = Mock()
        mock_provider.validate.return_value = True
        mock_token_provider_class.return_value = mock_provider

        manager = AuthManager()
        result = manager.validate_profile("any_profile")

        # Verify TokenAuthProvider was created with env vars
        mock_token_provider_class.assert_called_once_with(
            token="env_token", host="https://env.palantirfoundry.com"
        )

        # Verify validate was called
        mock_provider.validate.assert_called_once()
        assert result is True

    @patch.dict(os.environ, {}, clear=True)  # Clear all env vars
    def test_validate_profile_without_env_vars(self):
        """Test validating profile without env vars uses existing behavior."""
        with patch.object(AuthManager, "get_client") as mock_get_client:
            mock_get_client.return_value = Mock()  # Mock client

            manager = AuthManager()
            result = manager.validate_profile("test_profile")

            assert result is True
            mock_get_client.assert_called_once_with("test_profile")

    def test_lazy_storage_initialization(self):
        """Test that storage is only initialized when accessed."""
        with (
            patch("pltr.auth.manager.CredentialStorage") as mock_storage_class,
            patch("pltr.auth.manager.ProfileManager"),
        ):
            manager = AuthManager()

            # Storage should not be initialized yet
            mock_storage_class.assert_not_called()

            # Accessing storage should initialize it
            storage = manager.storage
            mock_storage_class.assert_called_once()

            # Subsequent access should return the same instance
            storage2 = manager.storage
            assert storage is storage2
            # Should still only be called once
            mock_storage_class.assert_called_once()

    def test_validate_profile(self):
        """Test validating a profile."""
        with patch.object(AuthManager, "get_client") as mock_get_client:
            mock_get_client.return_value = Mock()  # Mock client

            manager = AuthManager()
            result = manager.validate_profile("test_profile")

            assert result is True
            mock_get_client.assert_called_once_with("test_profile")
