"""
Integration tests for authentication flows.

These tests verify complete authentication workflows including configuration,
verification, profile management, and token handling.
"""

from unittest.mock import Mock, patch
from click.testing import CliRunner
import pytest

from pltr.cli import app
from pltr.config.profiles import ProfileManager
from pltr.config.settings import Settings


class TestAuthenticationFlow:
    """Test complete authentication workflows."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_env(self, monkeypatch):
        """Clear environment variables for testing."""
        env_vars = [
            "FOUNDRY_TOKEN",
            "FOUNDRY_HOST",
            "FOUNDRY_CLIENT_ID",
            "FOUNDRY_CLIENT_SECRET",
        ]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)
        return monkeypatch

    def test_token_auth_configuration_flow(self, runner, temp_config_dir):
        """Test complete token authentication configuration flow."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            with patch.object(
                Settings, "_get_config_dir", return_value=temp_config_dir
            ):
                # Test interactive configuration
                with patch("pltr.commands.configure.typer.prompt") as mock_prompt:
                    with patch("pltr.commands.configure.getpass") as mock_getpass:
                        # Mock user inputs
                        mock_prompt.side_effect = [
                            "test-profile",  # Profile name
                            "https://test.palantirfoundry.com",  # Host
                            "token",  # Auth type
                        ]
                        mock_getpass.return_value = "test_token_12345"  # Token

                        result = runner.invoke(app, ["configure", "configure"])
                        assert result.exit_code == 0
                        assert (
                            "Profile 'test-profile' configured successfully"
                            in result.output
                        )

                # Verify profile was created
                profile_manager = ProfileManager()
                profiles = profile_manager.list_profiles()
                assert "test-profile" in profiles

                # Test authentication with the configured profile
                with patch("pltr.commands.verify.AuthManager") as mock_auth_manager:
                    mock_auth = Mock()
                    mock_auth.verify.return_value = {
                        "username": "test.user@example.com",
                        "id": "user-123",
                    }
                    mock_auth_manager.from_profile.return_value = mock_auth

                    result = runner.invoke(app, ["verify", "--profile", "test-profile"])
                    assert result.exit_code == 0
                    assert "Authentication successful" in result.output

    def test_oauth_auth_configuration_flow(self, runner, temp_config_dir):
        """Test complete OAuth2 authentication configuration flow."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            with patch.object(
                Settings, "_get_config_dir", return_value=temp_config_dir
            ):
                # Test OAuth configuration
                with patch("pltr.commands.configure.typer.prompt") as mock_prompt:
                    with patch("pltr.commands.configure.getpass") as mock_getpass:
                        # Mock user inputs
                        mock_prompt.side_effect = [
                            "oauth-profile",  # Profile name
                            "https://oauth.palantirfoundry.com",  # Host
                            "oauth",  # Auth type
                            "client_123",  # Client ID
                            "api:read,api:write",  # Scopes
                        ]
                        mock_getpass.return_value = "client_secret_456"  # Client secret

                        result = runner.invoke(app, ["configure", "configure"])
                        assert result.exit_code == 0
                        assert (
                            "Profile 'oauth-profile' configured successfully"
                            in result.output
                        )

                # Test OAuth token refresh
                with patch("pltr.auth.oauth.OAuth2Auth._get_token") as mock_get_token:
                    mock_get_token.return_value = "access_token_789"

                    with patch("pltr.commands.verify.AuthManager") as mock_auth_manager:
                        mock_auth = Mock()
                        mock_auth.verify.return_value = {
                            "username": "oauth.user@example.com",
                            "id": "oauth-user-123",
                        }
                        mock_auth_manager.from_profile.return_value = mock_auth

                        result = runner.invoke(
                            app, ["verify", "--profile", "oauth-profile"]
                        )
                        assert result.exit_code == 0

    def test_profile_switching_workflow(self, runner, temp_config_dir):
        """Test switching between multiple authentication profiles."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()

            # Create multiple profiles
            profile_manager.create_profile(
                "dev",
                {
                    "auth_type": "token",
                    "host": "https://dev.palantirfoundry.com",
                    "token": "dev_token",
                },
            )
            profile_manager.create_profile(
                "staging",
                {
                    "auth_type": "token",
                    "host": "https://staging.palantirfoundry.com",
                    "token": "staging_token",
                },
            )
            profile_manager.create_profile(
                "prod",
                {
                    "auth_type": "oauth",
                    "host": "https://prod.palantirfoundry.com",
                    "client_id": "prod_client",
                    "client_secret": "prod_secret",
                    "scopes": ["api:read"],
                },
            )

            # Test listing profiles
            result = runner.invoke(app, ["configure", "list-profiles"])
            assert result.exit_code == 0
            assert "dev" in result.output
            assert "staging" in result.output
            assert "prod" in result.output

            # Test setting default profile
            result = runner.invoke(app, ["configure", "set-default", "staging"])
            assert result.exit_code == 0

            # Verify default profile is used
            with patch("pltr.commands.verify.AuthManager") as mock_auth_manager:
                mock_auth = Mock()
                mock_auth.verify.return_value = {"username": "staging.user"}
                mock_auth_manager.from_profile.return_value = mock_auth

                result = runner.invoke(app, ["verify"])
                # Should use staging profile by default
                mock_auth_manager.from_profile.assert_called_with("staging")

            # Test explicit profile selection
            with patch("pltr.commands.verify.AuthManager") as mock_auth_manager:
                mock_auth = Mock()
                mock_auth.verify.return_value = {"username": "prod.user"}
                mock_auth_manager.from_profile.return_value = mock_auth

                result = runner.invoke(app, ["verify", "--profile", "prod"])
                mock_auth_manager.from_profile.assert_called_with("prod")

    def test_environment_variable_authentication(self, runner, monkeypatch):
        """Test authentication using environment variables."""
        # Set environment variables
        monkeypatch.setenv("FOUNDRY_TOKEN", "env_token_123")
        monkeypatch.setenv("FOUNDRY_HOST", "https://env.palantirfoundry.com")

        with patch("pltr.commands.verify.AuthManager") as mock_auth_manager:
            mock_auth = Mock()
            mock_auth.verify.return_value = {
                "username": "env.user@example.com",
                "id": "env-user-123",
            }
            mock_auth_manager.from_environment.return_value = mock_auth

            result = runner.invoke(app, ["verify"])
            assert result.exit_code == 0
            # Should use environment variables
            mock_auth_manager.from_environment.assert_called_once()

    def test_environment_override_profile(self, runner, temp_config_dir, monkeypatch):
        """Test that environment variables override profile settings."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            # Create a profile
            profile_manager = ProfileManager()
            profile_manager.create_profile(
                "default",
                {
                    "auth_type": "token",
                    "host": "https://profile.palantirfoundry.com",
                    "token": "profile_token",
                },
            )
            profile_manager.set_default_profile("default")

            # Set conflicting environment variables
            monkeypatch.setenv("FOUNDRY_TOKEN", "env_override_token")
            monkeypatch.setenv(
                "FOUNDRY_HOST", "https://env-override.palantirfoundry.com"
            )

            with patch("pltr.commands.verify.AuthManager") as mock_auth_manager:
                mock_auth = Mock()
                mock_auth.verify.return_value = {"username": "env.override@example.com"}
                mock_auth_manager.from_environment.return_value = mock_auth

                runner.invoke(app, ["verify"])
                # Environment variables should take precedence
                mock_auth_manager.from_environment.assert_called_once()
                mock_auth_manager.from_profile.assert_not_called()

    def test_token_expiration_handling(self, runner, temp_config_dir):
        """Test handling of expired authentication tokens."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()
            profile_manager.create_profile(
                "test",
                {
                    "auth_type": "token",
                    "host": "https://test.palantirfoundry.com",
                    "token": "expired_token",
                },
            )
            profile_manager.set_default_profile("test")

            with patch("pltr.commands.verify.AuthManager") as mock_auth_manager:
                mock_auth = Mock()
                # Simulate token expiration error
                mock_auth.verify.side_effect = Exception(
                    "401 Unauthorized: Token expired"
                )
                mock_auth_manager.from_profile.return_value = mock_auth

                result = runner.invoke(app, ["verify"])
                assert result.exit_code == 1
                assert "Authentication failed" in result.output

    def test_profile_deletion_workflow(self, runner, temp_config_dir):
        """Test profile deletion and cleanup."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()

            # Create profiles
            profile_manager.create_profile(
                "temp-profile",
                {
                    "auth_type": "token",
                    "host": "https://temp.palantirfoundry.com",
                    "token": "temp_token",
                },
            )
            profile_manager.create_profile(
                "keep-profile",
                {
                    "auth_type": "token",
                    "host": "https://keep.palantirfoundry.com",
                    "token": "keep_token",
                },
            )

            # Test deletion with confirmation
            with patch("pltr.commands.configure.typer.confirm") as mock_confirm:
                mock_confirm.return_value = True

                result = runner.invoke(app, ["configure", "delete", "temp-profile"])
                assert result.exit_code == 0
                assert "Profile 'temp-profile' deleted successfully" in result.output

            # Verify profile was deleted
            profiles = profile_manager.list_profiles()
            assert "temp-profile" not in profiles
            assert "keep-profile" in profiles

    def test_missing_credentials_error(self, runner):
        """Test error handling when no credentials are configured."""
        with patch("pltr.commands.verify.ProfileManager") as mock_profile_manager:
            mock_pm = Mock()
            mock_pm.get_default_profile.return_value = None
            mock_pm.list_profiles.return_value = []
            mock_profile_manager.return_value = mock_pm

            result = runner.invoke(app, ["verify"])
            assert result.exit_code == 1
            assert (
                "No profiles configured" in result.output
                or "configure" in result.output.lower()
            )

    def test_invalid_host_format(self, runner, temp_config_dir):
        """Test validation of host URL format."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            with patch.object(
                Settings, "_get_config_dir", return_value=temp_config_dir
            ):
                with patch("pltr.commands.configure.typer.prompt") as mock_prompt:
                    with patch("pltr.commands.configure.getpass") as mock_getpass:
                        # Mock user inputs with invalid host
                        mock_prompt.side_effect = [
                            "bad-host-profile",  # Profile name
                            "not-a-url",  # Invalid host URL
                            "https://valid.palantirfoundry.com",  # Corrected host
                            "token",  # Auth type
                        ]
                        mock_getpass.return_value = "test_token"

                        result = runner.invoke(app, ["configure", "configure"])
                        # Should handle invalid URL gracefully
                        assert "https://" in result.output or "Invalid" in result.output
