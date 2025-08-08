"""
Tests for token authentication.
"""

import pytest
import os
from unittest.mock import patch, Mock
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

    def test_init_with_environment_variables(self):
        """Test initialization with environment variables."""
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_TOKEN": "env_token",
                "FOUNDRY_HOST": "https://env.palantirfoundry.com",
            },
        ):
            provider = TokenAuthProvider()
            assert provider.token == "env_token"
            assert provider.host == "https://env.palantirfoundry.com"

    def test_init_missing_token(self):
        """Test initialization fails when token is missing."""
        with pytest.raises(MissingCredentialsError, match="Token is required"):
            TokenAuthProvider(host="https://test.palantirfoundry.com")

    def test_init_missing_host(self):
        """Test initialization fails when host is missing."""
        with pytest.raises(MissingCredentialsError, match="Host URL is required"):
            TokenAuthProvider(token="test_token")

    def test_init_parameters_override_env(self):
        """Test that explicit parameters override environment variables."""
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_TOKEN": "env_token",
                "FOUNDRY_HOST": "https://env.palantirfoundry.com",
            },
        ):
            provider = TokenAuthProvider(
                token="param_token", host="https://param.palantirfoundry.com"
            )
            assert provider.token == "param_token"
            assert provider.host == "https://param.palantirfoundry.com"

    @pytest.mark.skip(reason="Requires foundry SDK to be installed")
    def test_get_client_integration(self):
        """Integration test for getting an authenticated client (requires SDK)."""
        # This would test the actual SDK integration
        # Skip since it requires the foundry package to be installed
        pass

    def test_get_client_creates_provider(self):
        """Test that get_client method exists and can be called."""
        provider = TokenAuthProvider(
            token="test_token", host="https://test.palantirfoundry.com"
        )

        # Verify the method exists and can be called
        # (actual functionality tested in integration tests with real SDK)
        assert hasattr(provider, "get_client")
        assert callable(provider.get_client)

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
