"""
Tests for widget commands.
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

    # ===== WidgetSet Commands =====

    def test_get_widget_set_success(self, runner, mock_service) -> None:
        """Test successful get widget set command."""
        mock_service.get_widget_set.return_value = {
            "rid": "ri.ontology-metadata.main.widget-set.abc123",
            "name": "Test Widget Set",
        }

        result = runner.invoke(
            app,
            [
                "widgets",
                "get",
                "ri.ontology-metadata.main.widget-set.abc123",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        mock_service.get_widget_set.assert_called_once_with(
            "ri.ontology-metadata.main.widget-set.abc123",
            preview=False,
        )

    def test_get_widget_set_with_preview(self, runner, mock_service) -> None:
        """Test get widget set with preview mode."""
        mock_service.get_widget_set.return_value = {"rid": "test-rid"}

        result = runner.invoke(
            app,
            [
                "widgets",
                "get",
                "ri.ontology-metadata.main.widget-set.abc123",
                "--preview",
            ],
        )

        assert result.exit_code == 0
        mock_service.get_widget_set.assert_called_once_with(
            "ri.ontology-metadata.main.widget-set.abc123",
            preview=True,
        )

    def test_get_widget_set_error(self, runner, mock_service) -> None:
        """Test get widget set with error."""
        mock_service.get_widget_set.side_effect = RuntimeError("Widget set not found")

        result = runner.invoke(
            app,
            ["widgets", "get", "ri.ontology-metadata.main.widget-set.invalid"],
        )

        assert result.exit_code == 1
        assert "Failed to get widget set" in result.stdout

    # ===== Release Commands =====

    def test_list_releases_success(self, runner, mock_service) -> None:
        """Test successful list releases command."""
        mock_service.list_releases.return_value = [
            {"version": "1.0.0", "createdAt": "2024-01-01T00:00:00Z"},
            {"version": "1.0.1", "createdAt": "2024-01-15T00:00:00Z"},
        ]

        result = runner.invoke(
            app,
            [
                "widgets",
                "releases",
                "list",
                "ri.ontology-metadata.main.widget-set.abc123",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        mock_service.list_releases.assert_called_once_with(
            "ri.ontology-metadata.main.widget-set.abc123",
            page_size=None,
            preview=False,
        )

    def test_list_releases_empty(self, runner, mock_service) -> None:
        """Test list releases with no results."""
        mock_service.list_releases.return_value = []

        result = runner.invoke(
            app,
            [
                "widgets",
                "releases",
                "list",
                "ri.ontology-metadata.main.widget-set.abc123",
            ],
        )

        assert result.exit_code == 0
        assert "No releases found" in result.stdout

    def test_list_releases_with_page_size(self, runner, mock_service) -> None:
        """Test list releases with page size."""
        mock_service.list_releases.return_value = [{"version": "1.0.0"}]

        result = runner.invoke(
            app,
            [
                "widgets",
                "releases",
                "list",
                "ri.ontology-metadata.main.widget-set.abc123",
                "--page-size",
                "10",
            ],
        )

        assert result.exit_code == 0
        mock_service.list_releases.assert_called_once_with(
            "ri.ontology-metadata.main.widget-set.abc123",
            page_size=10,
            preview=False,
        )

    def test_get_release_success(self, runner, mock_service) -> None:
        """Test successful get release command."""
        mock_service.get_release.return_value = {
            "version": "1.0.0",
            "createdAt": "2024-01-01T00:00:00Z",
        }

        result = runner.invoke(
            app,
            [
                "widgets",
                "releases",
                "get",
                "ri.ontology-metadata.main.widget-set.abc123",
                "1.0.0",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        mock_service.get_release.assert_called_once_with(
            "ri.ontology-metadata.main.widget-set.abc123",
            "1.0.0",
            preview=False,
        )

    def test_get_release_error(self, runner, mock_service) -> None:
        """Test get release with error."""
        mock_service.get_release.side_effect = RuntimeError("Release not found")

        result = runner.invoke(
            app,
            [
                "widgets",
                "releases",
                "get",
                "ri.ontology-metadata.main.widget-set.abc123",
                "9.9.9",
            ],
        )

        assert result.exit_code == 1
        assert "Failed to get release" in result.stdout

    def test_delete_release_success(self, runner, mock_service) -> None:
        """Test successful delete release command."""
        mock_service.delete_release.return_value = None

        result = runner.invoke(
            app,
            [
                "widgets",
                "releases",
                "delete",
                "ri.ontology-metadata.main.widget-set.abc123",
                "1.0.0",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        mock_service.delete_release.assert_called_once_with(
            "ri.ontology-metadata.main.widget-set.abc123",
            "1.0.0",
            preview=False,
        )
        assert "deleted successfully" in result.stdout

    def test_delete_release_error(self, runner, mock_service) -> None:
        """Test delete release with error."""
        mock_service.delete_release.side_effect = RuntimeError("Cannot delete release")

        result = runner.invoke(
            app,
            [
                "widgets",
                "releases",
                "delete",
                "ri.ontology-metadata.main.widget-set.abc123",
                "1.0.0",
                "--yes",
            ],
        )

        assert result.exit_code == 1
        assert "Failed to delete release" in result.stdout

    # ===== Repository Commands =====

    def test_get_repository_success(self, runner, mock_service) -> None:
        """Test successful get repository command."""
        mock_service.get_repository.return_value = {
            "rid": "ri.artifacts.main.repository.abc123",
            "name": "Test Repository",
        }

        result = runner.invoke(
            app,
            [
                "widgets",
                "repository",
                "get",
                "ri.artifacts.main.repository.abc123",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        mock_service.get_repository.assert_called_once_with(
            "ri.artifacts.main.repository.abc123",
            preview=False,
        )

    def test_get_repository_with_preview(self, runner, mock_service) -> None:
        """Test get repository with preview mode."""
        mock_service.get_repository.return_value = {"rid": "test-rid"}

        result = runner.invoke(
            app,
            [
                "widgets",
                "repository",
                "get",
                "ri.artifacts.main.repository.abc123",
                "--preview",
            ],
        )

        assert result.exit_code == 0
        mock_service.get_repository.assert_called_once_with(
            "ri.artifacts.main.repository.abc123",
            preview=True,
        )

    def test_get_repository_error(self, runner, mock_service) -> None:
        """Test get repository with error."""
        mock_service.get_repository.side_effect = RuntimeError("Repository not found")

        result = runner.invoke(
            app,
            ["widgets", "repository", "get", "ri.artifacts.main.repository.invalid"],
        )

        assert result.exit_code == 1
        assert "Failed to get repository" in result.stdout

    def test_publish_repository_success(self, runner, mock_service) -> None:
        """Test successful publish repository command."""
        mock_service.publish_repository.return_value = {
            "version": "1.0.2",
            "createdAt": "2024-01-20T00:00:00Z",
        }

        result = runner.invoke(
            app,
            [
                "widgets",
                "repository",
                "publish",
                "ri.artifacts.main.repository.abc123",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        mock_service.publish_repository.assert_called_once_with(
            "ri.artifacts.main.repository.abc123",
            preview=False,
        )
        assert "published successfully" in result.stdout

    def test_publish_repository_error(self, runner, mock_service) -> None:
        """Test publish repository with error."""
        mock_service.publish_repository.side_effect = RuntimeError("Cannot publish")

        result = runner.invoke(
            app,
            ["widgets", "repository", "publish", "ri.artifacts.main.repository.abc123"],
        )

        assert result.exit_code == 1
        assert "Failed to publish repository" in result.stdout

    # ===== Help Commands =====

    def test_help_widgets(self, runner) -> None:
        """Test widgets help command."""
        result = runner.invoke(app, ["widgets", "--help"])
        assert result.exit_code == 0
        assert "widget" in result.stdout.lower()

    def test_help_releases(self, runner) -> None:
        """Test releases help command."""
        result = runner.invoke(app, ["widgets", "releases", "--help"])
        assert result.exit_code == 0
        assert "release" in result.stdout.lower()

    def test_help_repository(self, runner) -> None:
        """Test repository help command."""
        result = runner.invoke(app, ["widgets", "repository", "--help"])
        assert result.exit_code == 0
        assert "repository" in result.stdout.lower()

    # ===== File Output Tests =====

    def test_get_widget_set_with_output(self, runner, mock_service) -> None:
        """Test get widget set with file output."""
        mock_service.get_widget_set.return_value = {"rid": "test-rid", "name": "Test"}

        with patch("pltr.commands.widgets.formatter") as mock_formatter:
            result = runner.invoke(
                app,
                [
                    "widgets",
                    "get",
                    "ri.ontology-metadata.main.widget-set.abc123",
                    "--output",
                    "/tmp/widget.json",
                    "--format",
                    "json",
                ],
            )

            assert result.exit_code == 0
            mock_formatter.save_to_file.assert_called_once()

    def test_list_releases_with_output(self, runner, mock_service) -> None:
        """Test list releases with file output."""
        mock_service.list_releases.return_value = [{"version": "1.0.0"}]

        with patch("pltr.commands.widgets.formatter") as mock_formatter:
            result = runner.invoke(
                app,
                [
                    "widgets",
                    "releases",
                    "list",
                    "ri.ontology-metadata.main.widget-set.abc123",
                    "--output",
                    "/tmp/releases.json",
                    "--format",
                    "json",
                ],
            )

            assert result.exit_code == 0
            mock_formatter.save_to_file.assert_called_once()
