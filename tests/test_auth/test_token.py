"""
Tests for token authentication.
"""

import pytest
from unittest.mock import patch, Mock

import foundry_sdk
from pltr.auth.token import TokenAuthProvider
from pltr.auth.base import MissingCredentialsError, InvalidCredentialsError


class TestTokenAuthProvider:
    """Tests for TokenAuthProvider."""

    def test_init_with_parameters(self):
        """Test initialization with explicit parameters."""
        provider = TokenAuthProvider(
            token="test_token", host="https://test.palantirfoundry.com"
        )
        assert provider.token == "test_token"
        assert provider.host == "https://test.palantirfoundry.com"

    def test_init_ignores_environment_variables(self, monkeypatch):
        """Providers use only the values they are given (AuthManager reads env vars).

        Otherwise FOUNDRY_TOKEN/FOUNDRY_HOST could silently complete a stored
        profile; environment-variable auth is tested in test_headless_auth.py.
        """
        monkeypatch.setenv("FOUNDRY_TOKEN", "env_token")
        monkeypatch.setenv("FOUNDRY_HOST", "https://env.palantirfoundry.com")

        with pytest.raises(MissingCredentialsError, match="Token is required"):
            TokenAuthProvider()
        with pytest.raises(MissingCredentialsError, match="Host URL is required"):
            TokenAuthProvider(token="param_token")

        provider = TokenAuthProvider(
            token="param_token", host="https://param.palantirfoundry.com"
        )
        assert provider.token == "param_token"
        assert provider.host == "https://param.palantirfoundry.com"

    def test_init_missing_token(self):
        """Test initialization fails when token is missing."""
        with pytest.raises(MissingCredentialsError, match="Token is required"):
            TokenAuthProvider(host="https://test.palantirfoundry.com")

    def test_init_missing_host(self):
        """Test initialization fails when host is missing."""
        with pytest.raises(MissingCredentialsError, match="Host URL is required"):
            TokenAuthProvider(token="test_token")

    def test_get_client_builds_a_real_client_without_preview(self, monkeypatch):
        """The V2 FoundryClient takes auth and hostname only (no client-level preview)."""
        calls = []
        real_client = foundry_sdk.FoundryClient

        def recording_client(**kwargs):
            calls.append(kwargs)
            return real_client(**kwargs)

        monkeypatch.setattr(foundry_sdk, "FoundryClient", recording_client)
        provider = TokenAuthProvider(
            token="test_token", host="https://test.palantirfoundry.com/"
        )

        client = provider.get_client()

        assert isinstance(client, real_client)
        auth = provider.get_auth()
        assert calls == [{"auth": auth, "hostname": "test.palantirfoundry.com"}]
        assert isinstance(auth, foundry_sdk.UserTokenAuth)
        assert auth.get_token().access_token == "test_token"

    def test_get_auth_is_created_once(self):
        """Clients and direct-HTTP calls share one auth object."""
        provider = TokenAuthProvider(
            token="test_token", host="test.palantirfoundry.com"
        )

        assert provider.get_auth() is provider.get_auth()

    def test_validate_success(self):
        """Test successful validation."""
        with patch.object(TokenAuthProvider, "get_client") as mock_get_client:
            mock_get_client.return_value = Mock()

            provider = TokenAuthProvider(
                token="test_token", host="https://test.palantirfoundry.com"
            )

            assert provider.validate() is True

    def test_validate_failure(self):
        """Test validation failure."""
        with patch.object(TokenAuthProvider, "get_client") as mock_get_client:
            mock_get_client.side_effect = Exception("Connection failed")

            provider = TokenAuthProvider(
                token="test_token", host="https://test.palantirfoundry.com"
            )

            with pytest.raises(
                InvalidCredentialsError, match="Token validation failed"
            ):
                provider.validate()

    def test_get_config(self):
        """Test getting configuration."""
        provider = TokenAuthProvider(
            token="test_token_12345", host="https://test.palantirfoundry.com"
        )

        config = provider.get_config()

        expected = {
            "type": "token",
            "host": "https://test.palantirfoundry.com",
            "token": "***2345",  # Should mask token except last 4 chars
        }
        assert config == expected

    def test_get_config_short_token(self):
        """Test getting configuration with short token."""
        provider = TokenAuthProvider(
            token="123",  # Short token
            host="https://test.palantirfoundry.com",
        )

        config = provider.get_config()

        # Should show *** for short tokens
        assert config["token"] == "***"
