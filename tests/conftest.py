"""
Pytest configuration and fixtures for pltr tests.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Generator

from pltr.auth.storage import CredentialStorage
from pltr.config.settings import Settings
from pltr.config.profiles import ProfileManager


@pytest.fixture
def temp_config_dir() -> Generator[Path, None, None]:
    """Create a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_keyring():
    """Mock keyring for credential storage tests."""
    with (
        patch("keyring.set_password") as mock_set,
        patch("keyring.get_password") as mock_get,
        patch("keyring.delete_password") as mock_delete,
    ):
        # Set up mock storage
        storage = {}

        def set_password(service, username, password):
            storage[f"{service}:{username}"] = password

        def get_password(service, username):
            return storage.get(f"{service}:{username}")

        def delete_password(service, username):
            key = f"{service}:{username}"
            if key in storage:
                del storage[key]

        mock_set.side_effect = set_password
        mock_get.side_effect = get_password
        mock_delete.side_effect = delete_password

        yield {
            "set": mock_set,
            "get": mock_get,
            "delete": mock_delete,
            "storage": storage,
        }


@pytest.fixture
def mock_settings(temp_config_dir):
    """Mock settings with temporary directory."""
    with patch.object(Settings, "_get_config_dir", return_value=temp_config_dir):
        settings = Settings()
        yield settings


@pytest.fixture
def mock_credential_storage(mock_keyring):
    """Mock credential storage with keyring mocked."""
    storage = CredentialStorage()
    yield storage


@pytest.fixture
def mock_profile_manager(temp_config_dir):
    """Mock profile manager with temporary directory."""
    with patch.object(Settings, "_get_config_dir", return_value=temp_config_dir):
        manager = ProfileManager()
        yield manager


@pytest.fixture
def sample_token_credentials():
    """Sample token-based credentials."""
    return {
        "auth_type": "token",
        "host": "https://test.palantirfoundry.com",
        "token": "test_token_12345",
    }


@pytest.fixture
def sample_oauth_credentials():
    """Sample OAuth credentials."""
    return {
        "auth_type": "oauth",
        "host": "https://test.palantirfoundry.com",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "scopes": ["api:read"],
    }


@pytest.fixture
def mock_requests():
    """Mock requests for HTTP calls."""
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # Default successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "username": "test.user@example.com",
            "id": "12345-abcde",
            "organization": {"rid": "ri.organization.main"},
        }

        mock_get.return_value = mock_response
        mock_post.return_value = mock_response

        yield {"get": mock_get, "post": mock_post, "response": mock_response}
