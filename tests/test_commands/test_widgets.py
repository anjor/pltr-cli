"""
Tests for widget management commands.
"""

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from pltr.cli import app


class TestWidgetsCommands:
    """Test widgets CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock WidgetsService."""
        with patch("pltr.commands.widgets.WidgetsService") as MockService:
            mock_svc = Mock()
            MockService.return_value = mock_svc
            yield mock_svc

    # ===== Widget Set Get Command Tests =====

    def test_get_widget_set_success(self, runner, mock_service) -> None:
        """Test successful get widget set command."""
        # Setup
        widget_set_result = {
            "rid": "ri.widgetregistry..widget-set.abc123",
            "name": "my-widgets",
            "widgets": [{"id": "widget1", "name": "Widget One"}],
        }
        mock_service.get_widget_set.return_value = widget_set_result

        result = runner.invoke(
            app,
            [
                "widgets",
                "get",
                "ri.widgetregistry..widget-set.abc123",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_widget_set.assert_called_once_with(
            "ri.widgetregistry..widget-set.abc123"
        )

    def test_get_widget_set_error(self, runner, mock_service) -> None:
        """Test get widget set command with error."""
        # Setup
        mock_service.get_widget_set.side_effect = RuntimeError("Widget set not found")

        result = runner.invoke(
            app,
            [
                "widgets",
                "get",
                "ri.widgetregistry..widget-set.invalid",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get widget set" in result.stdout

    # ===== Dev Mode Get Command Tests =====

    def test_dev_mode_get_success(self, runner, mock_service) -> None:
        """Test successful get dev mode settings command."""
        # Setup
        settings_result = {
            "enabled": True,
            "paused": False,
            "widgetSetSettings": {},
        }
        mock_service.get_dev_mode_settings.return_value = settings_result

        result = runner.invoke(
            app,
            [
                "widgets",
                "dev-mode",
                "get",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_dev_mode_settings.assert_called_once()

    def test_dev_mode_get_error(self, runner, mock_service) -> None:
        """Test get dev mode settings command with error."""
        # Setup
        mock_service.get_dev_mode_settings.side_effect = RuntimeError("API error")

        result = runner.invoke(
            app,
            [
                "widgets",
                "dev-mode",
                "get",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get dev mode settings" in result.stdout

    # ===== Dev Mode Enable Command Tests =====

    def test_dev_mode_enable_success(self, runner, mock_service) -> None:
        """Test successful enable dev mode command."""
        # Setup
        settings_result = {
            "enabled": True,
            "paused": False,
        }
        mock_service.enable_dev_mode.return_value = settings_result

        result = runner.invoke(
            app,
            [
                "widgets",
                "dev-mode",
                "enable",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.enable_dev_mode.assert_called_once()
        assert "enabled" in result.stdout.lower()

    def test_dev_mode_enable_error(self, runner, mock_service) -> None:
        """Test enable dev mode command with error."""
        # Setup
        mock_service.enable_dev_mode.side_effect = RuntimeError("Permission denied")

        result = runner.invoke(
            app,
            [
                "widgets",
                "dev-mode",
                "enable",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to enable dev mode" in result.stdout

    # ===== Dev Mode Disable Command Tests =====

    def test_dev_mode_disable_success(self, runner, mock_service) -> None:
        """Test successful disable dev mode command."""
        # Setup
        settings_result = {
            "enabled": False,
            "paused": False,
        }
        mock_service.disable_dev_mode.return_value = settings_result

        result = runner.invoke(
            app,
            [
                "widgets",
                "dev-mode",
                "disable",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.disable_dev_mode.assert_called_once()
        assert "disabled" in result.stdout.lower()

    # ===== Dev Mode Pause Command Tests =====

    def test_dev_mode_pause_success(self, runner, mock_service) -> None:
        """Test successful pause dev mode command."""
        # Setup
        settings_result = {
            "enabled": True,
            "paused": True,
        }
        mock_service.pause_dev_mode.return_value = settings_result

        result = runner.invoke(
            app,
            [
                "widgets",
                "dev-mode",
                "pause",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.pause_dev_mode.assert_called_once()
        assert "paused" in result.stdout.lower()

    # ===== Release List Command Tests =====

    def test_release_list_success(self, runner, mock_service) -> None:
        """Test successful list releases command."""
        # Setup
        releases_result = [
            {"version": "1.0.0", "createdAt": "2024-01-01T00:00:00Z"},
            {"version": "1.1.0", "createdAt": "2024-02-01T00:00:00Z"},
        ]
        mock_service.list_releases.return_value = releases_result

        result = runner.invoke(
            app,
            [
                "widgets",
                "release",
                "list",
                "ri.widgetregistry..widget-set.abc123",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_releases.assert_called_once_with(
            widget_set_rid="ri.widgetregistry..widget-set.abc123",
            page_size=None,
        )

    def test_release_list_empty(self, runner, mock_service) -> None:
        """Test list releases command with no results."""
        # Setup
        mock_service.list_releases.return_value = []

        result = runner.invoke(
            app,
            [
                "widgets",
                "release",
                "list",
                "ri.widgetregistry..widget-set.abc123",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "No releases found" in result.stdout

    def test_release_list_with_page_size(self, runner, mock_service) -> None:
        """Test list releases command with page size."""
        # Setup
        mock_service.list_releases.return_value = [{"version": "1.0.0"}]

        result = runner.invoke(
            app,
            [
                "widgets",
                "release",
                "list",
                "ri.widgetregistry..widget-set.abc123",
                "--page-size",
                "10",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_releases.assert_called_once_with(
            widget_set_rid="ri.widgetregistry..widget-set.abc123",
            page_size=10,
        )

    def test_release_list_error(self, runner, mock_service) -> None:
        """Test list releases command with error."""
        # Setup
        mock_service.list_releases.side_effect = RuntimeError("Widget set not found")

        result = runner.invoke(
            app,
            [
                "widgets",
                "release",
                "list",
                "ri.widgetregistry..widget-set.invalid",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to list releases" in result.stdout

    # ===== Release Get Command Tests =====

    def test_release_get_success(self, runner, mock_service) -> None:
        """Test successful get release command."""
        # Setup
        release_result = {
            "version": "1.0.0",
            "createdAt": "2024-01-01T00:00:00Z",
            "widgets": [{"id": "widget1"}],
        }
        mock_service.get_release.return_value = release_result

        result = runner.invoke(
            app,
            [
                "widgets",
                "release",
                "get",
                "ri.widgetregistry..widget-set.abc123",
                "1.0.0",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_release.assert_called_once_with(
            widget_set_rid="ri.widgetregistry..widget-set.abc123",
            release_version="1.0.0",
        )

    def test_release_get_error(self, runner, mock_service) -> None:
        """Test get release command with error."""
        # Setup
        mock_service.get_release.side_effect = RuntimeError("Release not found")

        result = runner.invoke(
            app,
            [
                "widgets",
                "release",
                "get",
                "ri.widgetregistry..widget-set.abc123",
                "99.99.99",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get release" in result.stdout

    # ===== Release Delete Command Tests =====

    def test_release_delete_success(self, runner, mock_service) -> None:
        """Test successful delete release command."""
        # Setup
        mock_service.delete_release.return_value = None

        result = runner.invoke(
            app,
            [
                "widgets",
                "release",
                "delete",
                "ri.widgetregistry..widget-set.abc123",
                "1.0.0",
                "--yes",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.delete_release.assert_called_once_with(
            widget_set_rid="ri.widgetregistry..widget-set.abc123",
            release_version="1.0.0",
        )
        assert "deleted" in result.stdout.lower()

    def test_release_delete_cancelled(self, runner, mock_service) -> None:
        """Test delete release command cancelled by user."""
        result = runner.invoke(
            app,
            [
                "widgets",
                "release",
                "delete",
                "ri.widgetregistry..widget-set.abc123",
                "1.0.0",
            ],
            input="n\n",
        )

        # Assert
        assert result.exit_code == 0
        mock_service.delete_release.assert_not_called()
        assert "cancelled" in result.stdout.lower()

    def test_release_delete_error(self, runner, mock_service) -> None:
        """Test delete release command with error."""
        # Setup
        mock_service.delete_release.side_effect = RuntimeError("Cannot delete release")

        result = runner.invoke(
            app,
            [
                "widgets",
                "release",
                "delete",
                "ri.widgetregistry..widget-set.abc123",
                "1.0.0",
                "--yes",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to delete release" in result.stdout

    # ===== Repository Get Command Tests =====

    def test_repository_get_success(self, runner, mock_service) -> None:
        """Test successful get repository command."""
        # Setup
        repository_result = {
            "rid": "ri.stemma.main.repository.abc123",
            "name": "my-widget-repo",
            "widgetSetRid": "ri.widgetregistry..widget-set.def456",
        }
        mock_service.get_repository.return_value = repository_result

        result = runner.invoke(
            app,
            [
                "widgets",
                "repository",
                "get",
                "ri.stemma.main.repository.abc123",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_repository.assert_called_once_with(
            "ri.stemma.main.repository.abc123"
        )

    def test_repository_get_error(self, runner, mock_service) -> None:
        """Test get repository command with error."""
        # Setup
        mock_service.get_repository.side_effect = RuntimeError("Repository not found")

        result = runner.invoke(
            app,
            [
                "widgets",
                "repository",
                "get",
                "ri.stemma.main.repository.invalid",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get repository" in result.stdout

    # ===== Help Command Tests =====

    def test_help_command(self, runner) -> None:
        """Test help output for commands."""
        # Test main help
        result = runner.invoke(app, ["widgets", "--help"])
        assert result.exit_code == 0
        assert "widgets" in result.stdout.lower()

        # Test dev-mode help
        result = runner.invoke(app, ["widgets", "dev-mode", "--help"])
        assert result.exit_code == 0
        assert "dev" in result.stdout.lower()

        # Test release help
        result = runner.invoke(app, ["widgets", "release", "--help"])
        assert result.exit_code == 0
        assert "release" in result.stdout.lower()

        # Test repository help
        result = runner.invoke(app, ["widgets", "repository", "--help"])
        assert result.exit_code == 0
        assert "repository" in result.stdout.lower()

    # ===== File Output Tests =====

    def test_get_widget_set_with_file_output(
        self, runner, mock_service, tmp_path
    ) -> None:
        """Test get widget set command with file output."""
        # Setup
        widget_set_result = {
            "rid": "ri.widgetregistry..widget-set.abc123",
            "name": "my-widgets",
        }
        mock_service.get_widget_set.return_value = widget_set_result
        output_file = tmp_path / "widget_set.json"

        with patch("pltr.commands.widgets.formatter") as mock_formatter:
            result = runner.invoke(
                app,
                [
                    "widgets",
                    "get",
                    "ri.widgetregistry..widget-set.abc123",
                    "--output",
                    str(output_file),
                    "--format",
                    "json",
                ],
            )

            # Assert
            assert result.exit_code == 0
            mock_formatter.save_to_file.assert_called_once_with(
                [widget_set_result], str(output_file), "json"
            )

    def test_release_list_with_file_output(
        self, runner, mock_service, tmp_path
    ) -> None:
        """Test list releases command with file output."""
        # Setup
        releases_result = [{"version": "1.0.0"}]
        mock_service.list_releases.return_value = releases_result
        output_file = tmp_path / "releases.json"

        with patch("pltr.commands.widgets.formatter") as mock_formatter:
            result = runner.invoke(
                app,
                [
                    "widgets",
                    "release",
                    "list",
                    "ri.widgetregistry..widget-set.abc123",
                    "--output",
                    str(output_file),
                    "--format",
                    "json",
                ],
            )

            # Assert
            assert result.exit_code == 0
            mock_formatter.save_to_file.assert_called_once_with(
                releases_result, str(output_file), "json"
            )
