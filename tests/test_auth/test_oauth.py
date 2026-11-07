"""
Tests for OAuth authentication.
"""

import pytest
from unittest.mock import patch, Mock

import foundry_sdk
from pltr.auth.oauth import OAuthClientProvider
from pltr.auth.base import MissingCredentialsError, InvalidCredentialsError


class TestOAuthClientProvider:
    """Tests for OAuthClientProvider."""

    def test_init_with_parameters(self):
        """Test initialization with explicit parameters."""
        provider = OAuthClientProvider(
            client_id="test_client_id",
            client_secret="test_client_secret",
            host="https://test.palantirfoundry.com",
            scopes=["api:read", "api:write"],
        )
        assert provider.client_id == "test_client_id"
        assert provider.client_secret == "test_client_secret"
        assert provider.host == "https://test.palantirfoundry.com"
        assert provider.scopes == ["api:read", "api:write"]

    def test_init_ignores_environment_variables(self, monkeypatch):
        """Providers use only the values they are given (AuthManager reads env vars).

        Otherwise FOUNDRY_CLIENT_ID/SECRET/HOST could silently complete a stored
        profile; environment-variable auth is tested in test_headless_auth.py.
        """
        monkeypatch.setenv("FOUNDRY_CLIENT_ID", "env_client_id")
        monkeypatch.setenv("FOUNDRY_CLIENT_SECRET", "env_client_secret")
        monkeypatch.setenv("FOUNDRY_HOST", "https://env.palantirfoundry.com")

        with pytest.raises(MissingCredentialsError, match="Client ID is required"):
            OAuthClientProvider()
        with pytest.raises(MissingCredentialsError, match="Client secret is required"):
            OAuthClientProvider(client_id="param_client_id")
        with pytest.raises(MissingCredentialsError, match="Host URL is required"):
            OAuthClientProvider(
                client_id="param_client_id", client_secret="param_secret"
            )

    def test_init_missing_client_id(self):
        """Test initialization fails when client_id is missing."""
        with pytest.raises(MissingCredentialsError, match="Client ID is required"):
            OAuthClientProvider(
                client_secret="test_secret", host="https://test.palantirfoundry.com"
            )

    def test_init_missing_client_secret(self):
        """Test initialization fails when client_secret is missing."""
        with pytest.raises(MissingCredentialsError, match="Client secret is required"):
            OAuthClientProvider(
                client_id="test_client_id", host="https://test.palantirfoundry.com"
            )

    def test_init_missing_host(self):
        """Test initialization fails when host is missing."""
        with pytest.raises(MissingCredentialsError, match="Host URL is required"):
            OAuthClientProvider(client_id="test_client_id", client_secret="test_secret")

    def test_init_default_scopes(self):
        """Test initialization with default empty scopes."""
        provider = OAuthClientProvider(
            client_id="test_client_id",
            client_secret="test_client_secret",
            host="https://test.palantirfoundry.com",
        )
        assert provider.scopes == []

    def test_init_parameters_override_env(self, monkeypatch):
        """Test that explicit parameters override environment variables."""
        monkeypatch.setenv("FOUNDRY_CLIENT_ID", "env_client_id")
        monkeypatch.setenv("FOUNDRY_CLIENT_SECRET", "env_client_secret")
        monkeypatch.setenv("FOUNDRY_HOST", "https://env.palantirfoundry.com")

        provider = OAuthClientProvider(
            client_id="param_client_id",
            client_secret="param_secret",
            host="https://param.palantirfoundry.com",
        )
        assert provider.client_id == "param_client_id"
        assert provider.client_secret == "param_secret"
        assert provider.host == "https://param.palantirfoundry.com"

    def test_get_client_builds_a_real_client_without_preview(self, monkeypatch):
        """The V2 FoundryClient takes auth and hostname only (no client-level preview)."""
        calls = []
        real_client = foundry_sdk.FoundryClient

        def recording_client(**kwargs):
            calls.append(kwargs)
            return real_client(**kwargs)

        monkeypatch.setattr(foundry_sdk, "FoundryClient", recording_client)
        provider = OAuthClientProvider(
            client_id="test_client_id",
            client_secret="test_client_secret",
            host="https://test.palantirfoundry.com/",
            scopes=["api:read"],
        )

        client = provider.get_client()

        assert isinstance(client, real_client)
        auth = provider.get_auth()
        assert calls == [{"auth": auth, "hostname": "test.palantirfoundry.com"}]
        assert isinstance(auth, foundry_sdk.ConfidentialClientAuth)
        assert auth.scopes == ["api:read"]

    def test_get_auth_is_created_once(self):
        """Clients and direct-HTTP calls share one auth object (and OAuth token)."""
        provider = OAuthClientProvider(
            client_id="test_client_id",
            client_secret="test_client_secret",
            host="test.palantirfoundry.com",
        )

        assert provider.get_auth() is provider.get_auth()

    def test_validate_success(self):
        """Test successful validation."""
        with patch.object(OAuthClientProvider, "get_client") as mock_get_client:
            mock_get_client.return_value = Mock()

            provider = OAuthClientProvider(
                client_id="test_client_id",
                client_secret="test_client_secret",
                host="https://test.palantirfoundry.com",
            )

            assert provider.validate() is True

    def test_validate_failure(self):
        """Test validation failure."""
        with patch.object(OAuthClientProvider, "get_client") as mock_get_client:
            mock_get_client.side_effect = Exception("OAuth failed")

            provider = OAuthClientProvider(
                client_id="test_client_id",
                client_secret="test_client_secret",
                host="https://test.palantirfoundry.com",
            )

            with pytest.raises(
                InvalidCredentialsError, match="OAuth validation failed"
            ):
                provider.validate()

    def test_get_config(self):
        """Test getting configuration."""
        provider = OAuthClientProvider(
            client_id="test_client_id",
            client_secret="test_client_secret_12345",
            host="https://test.palantirfoundry.com",
            scopes=["api:read", "api:write"],
        )

        config = provider.get_config()

        expected = {
            "type": "oauth",
            "host": "https://test.palantirfoundry.com",
            "client_id": "test_client_id",
            "client_secret": "***2345",  # Should mask secret except last 4 chars
            "scopes": ["api:read", "api:write"],
        }
        assert config == expected

    def test_get_config_short_secret(self):
        """Test getting configuration with short client secret."""
        provider = OAuthClientProvider(
            client_id="test_client_id",
            client_secret="123",  # Short secret
            host="https://test.palantirfoundry.com",
        )

        config = provider.get_config()

        # Should show *** for short secrets
        assert config["client_secret"] == "***"
