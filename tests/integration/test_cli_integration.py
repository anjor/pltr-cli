"""
Integration tests for CLI command execution.

These tests verify end-to-end command execution with mocked Foundry API responses.
"""

import json
from unittest.mock import Mock, patch
from click.testing import CliRunner
import pytest

from pltr.cli import app
from pltr.config.profiles import ProfileManager


class TestCLIIntegration:
    """Test complete CLI command execution paths."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_auth(self, temp_config_dir):
        """Mock authentication setup."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()
            profile_manager.create_profile(
                "test",
                {
                    "auth_type": "token",
                    "host": "https://test.palantirfoundry.com",
                    "token": "test_token",
                },
            )
            profile_manager.set_default_profile("test")

            with patch("pltr.commands.verify.AuthManager") as mock_auth_cls:
                mock_auth = Mock()
                mock_auth_cls.from_profile.return_value = mock_auth
                yield mock_auth

    def test_help_command(self, runner):
        """Test that help command works."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Palantir Foundry CLI" in result.output
        assert "configure" in result.output
        assert "dataset" in result.output
        assert "ontology" in result.output
        assert "sql" in result.output

    def test_version_command(self, runner):
        """Test version display."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "pltr" in result.output.lower()

    @patch("pltr.commands.verify.AuthManager")
    def test_verify_command_success(self, mock_auth_manager, runner, temp_config_dir):
        """Test successful authentication verification."""
        # Setup profile
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()
            profile_manager.create_profile(
                "test",
                {
                    "auth_type": "token",
                    "host": "https://test.palantirfoundry.com",
                    "token": "test_token",
                },
            )
            profile_manager.set_default_profile("test")

            # Mock successful verification
            mock_auth = Mock()
            mock_auth.verify.return_value = {
                "username": "test.user@example.com",
                "id": "user-123",
                "organization": {"rid": "ri.foundry.main.organization.abc123"},
            }
            mock_auth_manager.from_profile.return_value = mock_auth

            result = runner.invoke(app, ["verify"])
            assert result.exit_code == 0
            assert "Authentication successful" in result.output
            assert "test.user@example.com" in result.output

    @patch("pltr.commands.verify.AuthManager")
    def test_verify_command_failure(self, mock_auth_manager, runner, temp_config_dir):
        """Test failed authentication verification."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()
            profile_manager.create_profile(
                "test",
                {
                    "auth_type": "token",
                    "host": "https://test.palantirfoundry.com",
                    "token": "invalid_token",
                },
            )
            profile_manager.set_default_profile("test")

            # Mock failed verification
            mock_auth = Mock()
            mock_auth.verify.side_effect = Exception("Invalid credentials")
            mock_auth_manager.from_profile.return_value = mock_auth

            result = runner.invoke(app, ["verify"])
            assert result.exit_code == 1
            assert "Authentication failed" in result.output

    @patch("pltr.services.dataset.DatasetService")
    @patch("pltr.commands.dataset.AuthManager")
    def test_dataset_get_command(
        self, mock_auth_manager, mock_dataset_service, runner, temp_config_dir
    ):
        """Test dataset get command with mocked response."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()
            profile_manager.create_profile(
                "test",
                {
                    "auth_type": "token",
                    "host": "https://test.palantirfoundry.com",
                    "token": "test_token",
                },
            )
            profile_manager.set_default_profile("test")

            # Mock auth
            mock_auth = Mock()
            mock_auth_manager.from_profile.return_value = mock_auth

            # Mock dataset service
            mock_service = Mock()
            mock_service.get.return_value = {
                "rid": "ri.foundry.main.dataset.123",
                "name": "Test Dataset",
                "created": {"time": "2024-01-01T00:00:00Z", "userId": "user-123"},
                "modified": {"time": "2024-01-02T00:00:00Z", "userId": "user-123"},
                "description": "Test dataset description",
            }
            mock_dataset_service.return_value = mock_service

            result = runner.invoke(
                app, ["dataset", "get", "ri.foundry.main.dataset.123"]
            )
            assert result.exit_code == 0
            assert "Test Dataset" in result.output
            assert "ri.foundry.main.dataset.123" in result.output

    @patch("pltr.services.sql.SqlService")
    @patch("pltr.commands.sql.AuthManager")
    def test_sql_execute_command(
        self, mock_auth_manager, mock_sql_service, runner, temp_config_dir
    ):
        """Test SQL execute command with mocked response."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()
            profile_manager.create_profile(
                "test",
                {
                    "auth_type": "token",
                    "host": "https://test.palantirfoundry.com",
                    "token": "test_token",
                },
            )
            profile_manager.set_default_profile("test")

            # Mock auth
            mock_auth = Mock()
            mock_auth_manager.from_profile.return_value = mock_auth

            # Mock SQL service
            mock_service = Mock()
            mock_service.execute.return_value = {
                "columns": [
                    {"name": "id", "type": "INTEGER"},
                    {"name": "name", "type": "STRING"},
                ],
                "rows": [
                    [1, "Alice"],
                    [2, "Bob"],
                ],
            }
            mock_sql_service.return_value = mock_service

            result = runner.invoke(
                app, ["sql", "execute", "SELECT * FROM users LIMIT 2"]
            )
            assert result.exit_code == 0
            assert "Alice" in result.output
            assert "Bob" in result.output

    @patch("pltr.services.ontology.OntologyService")
    @patch("pltr.commands.ontology.AuthManager")
    def test_ontology_list_command(
        self, mock_auth_manager, mock_ontology_service, runner, temp_config_dir
    ):
        """Test ontology list command with mocked response."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()
            profile_manager.create_profile(
                "test",
                {
                    "auth_type": "token",
                    "host": "https://test.palantirfoundry.com",
                    "token": "test_token",
                },
            )
            profile_manager.set_default_profile("test")

            # Mock auth
            mock_auth = Mock()
            mock_auth_manager.from_profile.return_value = mock_auth

            # Mock ontology service
            mock_service = Mock()
            mock_service.list.return_value = [
                {
                    "rid": "ri.ontology.main.ontology.123",
                    "apiName": "test-ontology",
                    "displayName": "Test Ontology",
                    "description": "Test ontology for integration tests",
                }
            ]
            mock_ontology_service.return_value = mock_service

            result = runner.invoke(app, ["ontology", "list"])
            assert result.exit_code == 0
            assert "Test Ontology" in result.output
            assert "test-ontology" in result.output

    def test_profile_switching(self, runner, temp_config_dir):
        """Test switching between profiles."""
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
                "prod",
                {
                    "auth_type": "token",
                    "host": "https://prod.palantirfoundry.com",
                    "token": "prod_token",
                },
            )

            # Test listing profiles
            result = runner.invoke(app, ["configure", "list-profiles"])
            assert result.exit_code == 0
            assert "dev" in result.output
            assert "prod" in result.output

            # Test setting default profile
            result = runner.invoke(app, ["configure", "set-default", "prod"])
            assert result.exit_code == 0
            assert "Default profile set to: prod" in result.output

    def test_output_format_json(self, runner, temp_config_dir):
        """Test JSON output format."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()
            profile_manager.create_profile(
                "test",
                {
                    "auth_type": "token",
                    "host": "https://test.palantirfoundry.com",
                    "token": "test_token",
                },
            )
            profile_manager.set_default_profile("test")

            with patch("pltr.services.dataset.DatasetService") as mock_dataset_service:
                with patch("pltr.commands.dataset.AuthManager") as mock_auth_manager:
                    # Mock auth
                    mock_auth = Mock()
                    mock_auth_manager.from_profile.return_value = mock_auth

                    # Mock dataset service
                    mock_service = Mock()
                    mock_service.get.return_value = {
                        "rid": "ri.foundry.main.dataset.123",
                        "name": "Test Dataset",
                    }
                    mock_dataset_service.return_value = mock_service

                    result = runner.invoke(
                        app,
                        [
                            "dataset",
                            "get",
                            "ri.foundry.main.dataset.123",
                            "--format",
                            "json",
                        ],
                    )
                    assert result.exit_code == 0
                    # Verify JSON output
                    output_json = json.loads(result.output)
                    assert output_json["rid"] == "ri.foundry.main.dataset.123"
                    assert output_json["name"] == "Test Dataset"

    def test_error_handling_invalid_rid(self, runner, temp_config_dir):
        """Test error handling for invalid RID format."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()
            profile_manager.create_profile(
                "test",
                {
                    "auth_type": "token",
                    "host": "https://test.palantirfoundry.com",
                    "token": "test_token",
                },
            )
            profile_manager.set_default_profile("test")

            with patch("pltr.commands.dataset.AuthManager") as mock_auth_manager:
                # Mock auth
                mock_auth = Mock()
                mock_auth_manager.from_profile.return_value = mock_auth

                result = runner.invoke(app, ["dataset", "get", "invalid-rid"])
                assert result.exit_code == 1
                assert "Error" in result.output or "error" in result.output.lower()

    def test_environment_variable_override(self, runner, monkeypatch):
        """Test that environment variables override profile settings."""
        monkeypatch.setenv("FOUNDRY_TOKEN", "env_token")
        monkeypatch.setenv("FOUNDRY_HOST", "https://env.palantirfoundry.com")

        with patch("pltr.commands.verify.AuthManager") as mock_auth_manager:
            # Mock auth with env variables
            mock_auth = Mock()
            mock_auth.verify.return_value = {
                "username": "env.user@example.com",
                "id": "env-user-123",
            }
            mock_auth_manager.from_environment.return_value = mock_auth

            runner.invoke(app, ["verify"])
            # Should use environment variables
            mock_auth_manager.from_environment.assert_called_once()
