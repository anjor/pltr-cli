"""
Tests for third-party applications commands.
"""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from pltr.cli import app


class TestThirdPartyApplicationsCommands:
    """Test third-party applications CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock ThirdPartyApplicationsService."""
        with patch(
            "pltr.commands.third_party_applications.ThirdPartyApplicationsService"
        ) as MockService:
            mock_svc = Mock()
            MockService.return_value = mock_svc
            yield mock_svc

    def test_get_command_success(self, runner, mock_service):
        """Test successful get application command."""
        # Setup
        app_result = {
            "rid": "ri.third-party-applications.main.third-party-application.test-app",
            "name": "Test Application",
            "description": "A test third-party application",
            "status": "ACTIVE",
        }
        mock_service.get_application.return_value = app_result

        result = runner.invoke(
            app,
            [
                "third-party-apps",
                "get",
                "ri.third-party-applications.main.third-party-application.test-app",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_application.assert_called_once_with(
            "ri.third-party-applications.main.third-party-application.test-app",
            preview=False,
        )

    def test_get_command_with_preview(self, runner, mock_service):
        """Test get command with preview flag."""
        # Setup
        app_result = {
            "rid": "ri.third-party-applications.main.third-party-application.preview-app",
            "name": "Preview Application",
        }
        mock_service.get_application.return_value = app_result

        result = runner.invoke(
            app,
            [
                "third-party-apps",
                "get",
                "ri.third-party-applications.main.third-party-application.preview-app",
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_application.assert_called_once_with(
            "ri.third-party-applications.main.third-party-application.preview-app",
            preview=True,
        )

    def test_get_command_with_profile(self, runner, mock_service):
        """Test get command with custom profile."""
        # Setup
        app_result = {
            "rid": "ri.third-party-applications.main.third-party-application.app1"
        }
        mock_service.get_application.return_value = app_result

        result = runner.invoke(
            app,
            [
                "third-party-apps",
                "get",
                "ri.third-party-applications.main.third-party-application.app1",
                "--profile",
                "production",
            ],
        )

        # Assert
        assert result.exit_code == 0

    def test_get_command_error(self, runner, mock_service):
        """Test get command with service error."""
        # Setup
        mock_service.get_application.side_effect = RuntimeError("Application not found")

        result = runner.invoke(
            app,
            [
                "third-party-apps",
                "get",
                "ri.third-party-applications.main.third-party-application.invalid",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get third-party application" in result.stdout

    def test_help_command(self, runner):
        """Test help output for commands."""
        # Test main help
        result = runner.invoke(app, ["third-party-apps", "--help"])
        assert result.exit_code == 0
        assert "third-party applications" in result.stdout.lower()

        # Test get command help
        result = runner.invoke(app, ["third-party-apps", "get", "--help"])
        assert result.exit_code == 0
        assert "Third-party application Resource Identifier" in result.stdout
