"""
Shared configuration for integration tests.

This file provides common fixtures and mocking for integration tests,
particularly to handle keyring backend issues in CI environments.
"""

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True, scope="session")
def mock_keyring():
    """Mock keyring operations for all integration tests."""
    with patch("keyring.set_password") as mock_set:
        with patch("keyring.get_password", return_value=None) as mock_get:
            with patch("keyring.delete_password") as mock_delete:
                # Make these mocks available to all tests
                yield {
                    "set_password": mock_set,
                    "get_password": mock_get,
                    "delete_password": mock_delete,
                }
