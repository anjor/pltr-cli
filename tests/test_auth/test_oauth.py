"""
Tests for OAuth authentication.
"""

import pytest
import os
from unittest.mock import patch, Mock
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

    def test_init_with_environment_variables(self):
        """Test initialization with environment variables."""
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_CLIENT_ID": "env_client_id",
                "FOUNDRY_CLIENT_SECRET": "env_client_secret",
                "FOUNDRY_HOST": "https://env.palantirfoundry.com",
            },
        ):
            provider = OAuthClientProvider()
            assert provider.client_id == "env_client_id"
            assert provider.client_secret == "env_client_secret"
            assert provider.host == "https://env.palantirfoundry.com"
            assert provider.scopes == []  # Default empty

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

    def test_init_parameters_override_env(self):
        """Test that explicit parameters override environment variables."""
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_CLIENT_ID": "env_client_id",
                "FOUNDRY_CLIENT_SECRET": "env_client_secret",
                "FOUNDRY_HOST": "https://env.palantirfoundry.com",
            },
        ):
            provider = OAuthClientProvider(
                client_id="param_client_id",
                client_secret="param_secret",
                host="https://param.palantirfoundry.com",
            )
            assert provider.client_id == "param_client_id"
            assert provider.client_secret == "param_secret"
            assert provider.host == "https://param.palantirfoundry.com"

    @pytest.mark.skip(reason="Requires foundry SDK to be installed")
    def test_get_client_integration(self):
        """Integration test for getting an authenticated client (requires SDK)."""
        # This would test the actual SDK integration
        # Skip since it requires the foundry package to be installed
        pass

    def test_get_client_creates_provider(self):
        """Test that get_client method exists and can be called."""
        provider = OAuthClientProvider(
            client_id="test_client_id",
            client_secret="test_client_secret",
            host="https://test.palantirfoundry.com",
        )

        # Verify the method exists and can be called
        # (actual functionality tested in integration tests with real SDK)
        assert hasattr(provider, "get_client")
        assert callable(provider.get_client)

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
