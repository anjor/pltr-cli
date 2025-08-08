"""
Tests for authentication base classes.
"""

import pytest
from pltr.auth.base import (
    AuthProvider,
    AuthError,
    InvalidCredentialsError,
    MissingCredentialsError,
    ProfileNotFoundError,
)


class TestAuthProvider:
    """Tests for AuthProvider abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that AuthProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AuthProvider()

    def test_concrete_implementation(self):
        """Test that concrete implementations must implement all abstract methods."""

        class IncompleteProvider(AuthProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()

        class CompleteProvider(AuthProvider):
            def get_client(self):
                return "mock_client"

            def validate(self):
                return True

            def get_config(self):
                return {"type": "test"}

        # Should not raise an error
        provider = CompleteProvider()
        assert provider.get_client() == "mock_client"
        assert provider.validate() is True
        assert provider.get_config() == {"type": "test"}


class TestAuthExceptions:
    """Tests for authentication exception classes."""

    def test_auth_error(self):
        """Test AuthError base exception."""
        error = AuthError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_invalid_credentials_error(self):
        """Test InvalidCredentialsError."""
        error = InvalidCredentialsError("Invalid token")
        assert str(error) == "Invalid token"
        assert isinstance(error, AuthError)

    def test_missing_credentials_error(self):
        """Test MissingCredentialsError."""
        error = MissingCredentialsError("Token required")
        assert str(error) == "Token required"
        assert isinstance(error, AuthError)

    def test_profile_not_found_error(self):
        """Test ProfileNotFoundError."""
        error = ProfileNotFoundError("Profile 'test' not found")
        assert str(error) == "Profile 'test' not found"
        assert isinstance(error, AuthError)
