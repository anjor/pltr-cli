"""Tests for Models commands."""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner
from pltr.cli import app


class TestModelsCommands:
    """Test Models CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock ModelsService."""
        with patch("pltr.commands.models.ModelsService") as MockService:
            mock_svc = Mock()
            MockService.return_value = mock_svc
            yield mock_svc

    # ===== Model Create Tests =====

    def test_model_create_success(self, runner, mock_service):
        """Test successful model creation."""
        # Setup
        name = "fraud-detector"
        folder_rid = "ri.compass.main.folder.123"
        response = {
            "rid": "ri.foundry.main.model.abc123",
            "name": name,
            "parentFolderRid": folder_rid,
        }
        mock_service.create_model.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "model",
                "create",
                name,
                "--folder",
                folder_rid,
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.create_model.assert_called_once_with(
            name=name,
            parent_folder_rid=folder_rid,
            preview=False,
        )
        assert "Created model" in result.output

    def test_model_create_with_preview(self, runner, mock_service):
        """Test model creation with preview mode."""
        # Setup
        name = "test-model"
        folder_rid = "ri.compass.main.folder.123"
        response = {
            "rid": "ri.foundry.main.model.abc123",
            "name": name,
        }
        mock_service.create_model.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "model",
                "create",
                name,
                "--folder",
                folder_rid,
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.create_model.assert_called_once_with(
            name=name,
            parent_folder_rid=folder_rid,
            preview=True,
        )

    def test_model_create_error(self, runner, mock_service):
        """Test model creation error handling."""
        # Setup
        mock_service.create_model.side_effect = Exception("Permission denied")

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "model",
                "create",
                "test-model",
                "--folder",
                "ri.compass.main.folder.123",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error" in result.output

    # ===== Model Get Tests =====

    def test_model_get_success(self, runner, mock_service):
        """Test successful model get."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        response = {
            "rid": model_rid,
            "name": "fraud-detector",
            "parentFolderRid": "ri.compass.main.folder.123",
        }
        mock_service.get_model.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "model",
                "get",
                model_rid,
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_model.assert_called_once_with(
            model_rid=model_rid,
            preview=False,
        )

    def test_model_get_with_preview(self, runner, mock_service):
        """Test model get with preview mode."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        response = {"rid": model_rid}
        mock_service.get_model.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "model",
                "get",
                model_rid,
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_model.assert_called_once_with(
            model_rid=model_rid,
            preview=True,
        )

    def test_model_get_error(self, runner, mock_service):
        """Test model get error handling."""
        # Setup
        mock_service.get_model.side_effect = Exception("Model not found")

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "model",
                "get",
                "ri.foundry.main.model.abc123",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error" in result.output

    # ===== Version Get Tests =====

    def test_version_get_success(self, runner, mock_service):
        """Test successful version get."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        version_rid = "v1.0.0"
        response = {
            "modelRid": model_rid,
            "versionRid": version_rid,
            "createdTime": "2024-01-01T00:00:00Z",
        }
        mock_service.get_model_version.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "version",
                "get",
                model_rid,
                version_rid,
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_model_version.assert_called_once_with(
            model_rid=model_rid,
            model_version_rid=version_rid,
            preview=False,
        )

    def test_version_get_with_preview(self, runner, mock_service):
        """Test version get with preview mode."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        version_rid = "v1.0.0"
        response = {"versionRid": version_rid}
        mock_service.get_model_version.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "version",
                "get",
                model_rid,
                version_rid,
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_model_version.assert_called_once_with(
            model_rid=model_rid,
            model_version_rid=version_rid,
            preview=True,
        )

    def test_version_get_error(self, runner, mock_service):
        """Test version get error handling."""
        # Setup
        mock_service.get_model_version.side_effect = Exception("Version not found")

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "version",
                "get",
                "ri.foundry.main.model.abc123",
                "v1.0.0",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error" in result.output

    # ===== Version List Tests =====

    def test_version_list_success(self, runner, mock_service):
        """Test successful version list."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        response = {
            "data": [
                {"versionRid": "v1.0.0"},
                {"versionRid": "v1.1.0"},
            ],
            "nextPageToken": None,
        }
        mock_service.list_model_versions.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "version",
                "list",
                model_rid,
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_model_versions.assert_called_once_with(
            model_rid=model_rid,
            page_size=None,
            page_token=None,
            preview=False,
        )

    def test_version_list_with_pagination(self, runner, mock_service):
        """Test version list with pagination."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        response = {
            "data": [{"versionRid": "v1.0.0"}],
            "nextPageToken": "token456",
        }
        mock_service.list_model_versions.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "version",
                "list",
                model_rid,
                "--page-size",
                "50",
                "--page-token",
                "token123",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_model_versions.assert_called_once_with(
            model_rid=model_rid,
            page_size=50,
            page_token="token123",
            preview=False,
        )
        assert "Next page available" in result.output

    def test_version_list_with_preview(self, runner, mock_service):
        """Test version list with preview mode."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        response = {
            "data": [],
            "nextPageToken": None,
        }
        mock_service.list_model_versions.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "version",
                "list",
                model_rid,
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_model_versions.assert_called_once_with(
            model_rid=model_rid,
            page_size=None,
            page_token=None,
            preview=True,
        )

    def test_version_list_error(self, runner, mock_service):
        """Test version list error handling."""
        # Setup
        mock_service.list_model_versions.side_effect = Exception("List failed")

        # Execute
        result = runner.invoke(
            app,
            [
                "models",
                "version",
                "list",
                "ri.foundry.main.model.abc123",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error" in result.output
