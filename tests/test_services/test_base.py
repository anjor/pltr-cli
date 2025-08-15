"""
Tests for base service functionality.
"""

import pytest
from unittest.mock import Mock, patch

from pltr.services.base import BaseService
from pltr.auth.base import ProfileNotFoundError, MissingCredentialsError


class MockService(BaseService):
    """Mock service implementation for testing BaseService."""

    def _get_service(self):
        """Return a mock service."""
        return Mock()


def test_base_service_initialization():
    """Test BaseService initialization."""
    service = MockService()
    assert service.profile is None
    assert service._client is None
    assert service.auth_manager is not None

    # Test with profile
    service_with_profile = MockService(profile="test")
    assert service_with_profile.profile == "test"


@patch("pltr.services.base.AuthManager")
def test_base_service_client_property(mock_auth_manager):
    """Test client property creates and caches client."""
    mock_client = Mock()
    mock_auth_instance = Mock()
    mock_auth_instance.get_client.return_value = mock_client
    mock_auth_manager.return_value = mock_auth_instance

    service = MockService()

    # First call should create client
    client = service.client
    assert client == mock_client
    mock_auth_instance.get_client.assert_called_once_with(None)

    # Second call should return cached client
    client2 = service.client
    assert client2 == mock_client
    assert mock_auth_instance.get_client.call_count == 1


@patch("pltr.services.base.AuthManager")
def test_base_service_client_with_profile(mock_auth_manager):
    """Test client property with specific profile."""
    mock_client = Mock()
    mock_auth_instance = Mock()
    mock_auth_instance.get_client.return_value = mock_client
    mock_auth_manager.return_value = mock_auth_instance

    service = MockService(profile="test-profile")

    client = service.client
    assert client == mock_client
    mock_auth_instance.get_client.assert_called_once_with("test-profile")


@patch("pltr.services.base.AuthManager")
def test_base_service_client_profile_not_found(mock_auth_manager):
    """Test client property with non-existent profile."""
    mock_auth_instance = Mock()
    mock_auth_instance.get_client.side_effect = ProfileNotFoundError(
        "Profile not found"
    )
    mock_auth_manager.return_value = mock_auth_instance

    service = MockService()

    with pytest.raises(ProfileNotFoundError):
        service.client


@patch("pltr.services.base.AuthManager")
def test_base_service_client_missing_credentials(mock_auth_manager):
    """Test client property with missing credentials."""
    mock_auth_instance = Mock()
    mock_auth_instance.get_client.side_effect = MissingCredentialsError(
        "Missing credentials"
    )
    mock_auth_manager.return_value = mock_auth_instance

    service = MockService()

    with pytest.raises(MissingCredentialsError):
        service.client


@patch("pltr.services.base.AuthManager")
def test_base_service_service_property(mock_auth_manager):
    """Test service property returns result from _get_service."""
    mock_client = Mock()
    mock_service = Mock()
    mock_auth_instance = Mock()
    mock_auth_instance.get_client.return_value = mock_client
    mock_auth_manager.return_value = mock_auth_instance

    service = MockService()

    # Mock the _get_service method to return our mock service
    service._get_service = Mock(return_value=mock_service)

    result = service.service
    assert result == mock_service
    service._get_service.assert_called_once()


def test_base_service_abstract_method():
    """Test that BaseService is abstract and requires _get_service implementation."""
    with pytest.raises(TypeError):
        # This should fail because BaseService has an abstract method
        BaseService()


class InvalidService(BaseService):
    """Service without implementing _get_service (should fail)."""

    pass


def test_invalid_service_missing_implementation():
    """Test that service without _get_service implementation fails."""
    with pytest.raises(TypeError):
        InvalidService()
