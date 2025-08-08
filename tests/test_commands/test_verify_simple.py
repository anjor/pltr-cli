"""
Simplified tests for verify command.
"""

from unittest.mock import Mock, patch
from typer.testing import CliRunner
from pltr.commands.verify import app


class TestVerifyCommandSimple:
    """Simplified tests for the verify command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_verify_no_profile_configured(self):
        """Test verify when no profile is configured."""
        with patch("pltr.commands.verify.AuthManager") as mock_auth_manager_class:
            # Mock AuthManager to return None for active profile
            mock_auth_manager = Mock()
            mock_auth_manager.get_current_profile.return_value = None
            mock_auth_manager_class.return_value = mock_auth_manager

            result = self.runner.invoke(app, [])

            assert result.exit_code == 1
            assert "No profile configured" in result.stdout

    def test_verify_success_basic(self):
        """Test basic successful verification."""
        with (
            patch("pltr.commands.verify.AuthManager") as mock_auth_manager_class,
            patch("pltr.auth.storage.CredentialStorage") as mock_storage_class,
            patch("pltr.commands.verify.requests") as mock_requests,
        ):
            # Mock AuthManager
            mock_auth_manager = Mock()
            mock_auth_manager.get_current_profile.return_value = "test_profile"
            mock_auth_manager_class.return_value = mock_auth_manager

            # Mock storage
            mock_storage = Mock()
            mock_storage.get_profile.return_value = {
                "auth_type": "token",
                "host": "https://test.palantirfoundry.com",
                "token": "test_token",
            }
            mock_storage_class.return_value = mock_storage

            # Mock successful HTTP response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "username": "test.user@example.com",
                "id": "12345-abcde",
            }
            mock_requests.get.return_value = mock_response

            result = self.runner.invoke(app, [])

            assert result.exit_code == 0
            assert "Authentication successful!" in result.stdout
            assert "test.user@example.com" in result.stdout

    def test_verify_401_failure(self):
        """Test verification with 401 authentication failure."""
        with (
            patch("pltr.commands.verify.AuthManager") as mock_auth_manager_class,
            patch("pltr.auth.storage.CredentialStorage") as mock_storage_class,
            patch("pltr.commands.verify.requests") as mock_requests,
        ):
            # Mock AuthManager
            mock_auth_manager = Mock()
            mock_auth_manager.get_current_profile.return_value = "test_profile"
            mock_auth_manager_class.return_value = mock_auth_manager

            # Mock storage
            mock_storage = Mock()
            mock_storage.get_profile.return_value = {
                "auth_type": "token",
                "host": "https://test.palantirfoundry.com",
                "token": "invalid_token",
            }
            mock_storage_class.return_value = mock_storage

            # Mock 401 response
            mock_response = Mock()
            mock_response.status_code = 401
            mock_requests.get.return_value = mock_response

            result = self.runner.invoke(app, [])

            assert result.exit_code == 1
            assert "Authentication failed: Invalid credentials" in result.stdout
