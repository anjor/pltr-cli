"""
Tests for folder commands.
"""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from pltr.cli import app
from pltr.auth.base import ProfileNotFoundError, MissingCredentialsError


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_folder_service():
    """Mock the FolderService."""
    with patch("pltr.commands.folder.FolderService") as MockFolderService:
        mock_service = Mock()
        MockFolderService.return_value = mock_service
        yield mock_service


@pytest.fixture
def sample_folder():
    """Sample folder data."""
    return {
        "rid": "ri.compass.main.folder.test-folder",
        "display_name": "Test Folder",
        "description": "Test folder description",
        "parent_folder_rid": "ri.compass.main.folder.parent",
        "created": "2024-01-01T00:00:00Z",
        "modified": "2024-01-02T00:00:00Z",
        "type": "folder",
    }


@pytest.fixture
def sample_children():
    """Sample folder children data."""
    return [
        {
            "rid": "ri.compass.main.folder.child-folder",
            "display_name": "Child Folder",
            "type": "folder",
            "description": "A child folder",
        },
        {
            "rid": "ri.foundry.main.dataset.child-dataset",
            "display_name": "Child Dataset",
            "type": "dataset",
            "name": "Child Dataset",
        },
    ]


def test_create_folder(runner, mock_folder_service, sample_folder):
    """Test folder creation command."""
    mock_folder_service.create_folder.return_value = sample_folder

    result = runner.invoke(
        app,
        [
            "folder",
            "create",
            "Test Folder",
            "--parent-folder",
            "ri.compass.main.folder.parent",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully created folder 'Test Folder'" in result.stdout
    assert "ri.compass.main.folder.test-folder" in result.stdout

    mock_folder_service.create_folder.assert_called_once_with(
        display_name="Test Folder", parent_folder_rid="ri.compass.main.folder.parent"
    )


def test_create_folder_requires_parent(runner, mock_folder_service, sample_folder):
    """Test folder creation requires --parent-folder."""
    result = runner.invoke(app, ["folder", "create", "Test Folder"])

    assert result.exit_code != 0
    assert (
        "Missing option" in result.stdout
        or "required" in result.stdout.lower()
        or result.exit_code == 2
    )


def test_create_folder_json_output(runner, mock_folder_service, sample_folder):
    """Test folder creation with JSON output."""
    mock_folder_service.create_folder.return_value = sample_folder

    result = runner.invoke(
        app,
        [
            "folder",
            "create",
            "Test Folder",
            "--parent-folder",
            "ri.compass.main.folder.test-parent",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully created folder 'Test Folder'" in result.stdout


def test_get_folder(runner, mock_folder_service, sample_folder):
    """Test getting folder information."""
    mock_folder_service.get_folder.return_value = sample_folder

    result = runner.invoke(app, ["folder", "get", "ri.compass.main.folder.test-folder"])

    assert result.exit_code == 0
    assert "Test Folder" in result.stdout
    assert "ri.compass.main.folder.test-folder" in result.stdout

    mock_folder_service.get_folder.assert_called_once_with(
        "ri.compass.main.folder.test-folder"
    )


def test_get_folder_json_output(runner, mock_folder_service, sample_folder):
    """Test getting folder with JSON output."""
    mock_folder_service.get_folder.return_value = sample_folder

    result = runner.invoke(
        app, ["folder", "get", "ri.compass.main.folder.test-folder", "--format", "json"]
    )

    assert result.exit_code == 0


def test_move_folder(runner, mock_folder_service, sample_folder):
    """Test moving and renaming a folder."""
    moved_folder = {
        **sample_folder,
        "display_name": "Renamed Folder",
        "parent_folder_rid": "ri.compass.main.folder.new-parent",
    }
    mock_folder_service.move_folder.return_value = moved_folder

    result = runner.invoke(
        app,
        [
            "folder",
            "move",
            "ri.compass.main.folder.test-folder",
            "--parent-folder",
            "ri.compass.main.folder.new-parent",
            "--name",
            "Renamed Folder",
            "--confirm",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully moved folder" in result.stdout
    assert "Renamed Folder" in result.stdout
    assert "ri.compass.main.folder.new-parent" in result.stdout
    mock_folder_service.move_folder.assert_called_once_with(
        folder_rid="ri.compass.main.folder.test-folder",
        parent_folder_rid="ri.compass.main.folder.new-parent",
        display_name="Renamed Folder",
    )


def test_move_folder_requires_parent(runner, mock_folder_service):
    """Test moving a folder requires a destination parent option."""
    result = runner.invoke(
        app,
        ["folder", "move", "ri.compass.main.folder.test-folder", "--confirm"],
    )

    assert result.exit_code == 2
    mock_folder_service.move_folder.assert_not_called()


def test_move_folder_cancelled_before_service_creation(runner):
    """Test declining confirmation does not construct the service."""
    with patch("pltr.commands.folder.FolderService") as mock_service_class:
        result = runner.invoke(
            app,
            [
                "folder",
                "move",
                "ri.compass.main.folder.test-folder",
                "--parent-folder",
                "ri.compass.main.folder.new-parent",
            ],
            input="n\n",
        )

    assert result.exit_code == 0
    assert "Folder move cancelled" in result.stdout
    mock_service_class.assert_not_called()


@pytest.mark.parametrize("output_format", ["json", "csv"])
def test_move_folder_structured_output(
    runner, mock_folder_service, sample_folder, output_format
):
    """Test move supports JSON and CSV success output."""
    mock_folder_service.move_folder.return_value = sample_folder

    result = runner.invoke(
        app,
        [
            "folder",
            "move",
            "ri.compass.main.folder.test-folder",
            "--parent-folder",
            "ri.compass.main.folder.new-parent",
            "--format",
            output_format,
            "--confirm",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully moved folder" in result.stdout
    assert "ri.compass.main.folder.test-folder" in result.stdout
    mock_folder_service.move_folder.assert_called_once_with(
        folder_rid="ri.compass.main.folder.test-folder",
        parent_folder_rid="ri.compass.main.folder.new-parent",
        display_name=None,
    )


def test_move_folder_caches_returned_rid(runner, mock_folder_service, sample_folder):
    """Test move caches the RID returned by the service."""
    mock_folder_service.move_folder.return_value = sample_folder

    with patch("pltr.commands.folder.cache_rid") as mock_cache_rid:
        result = runner.invoke(
            app,
            [
                "folder",
                "move",
                "ri.compass.main.folder.test-folder",
                "--parent-folder",
                "ri.compass.main.folder.new-parent",
                "--confirm",
            ],
        )

    assert result.exit_code == 0
    mock_cache_rid.assert_called_once_with("ri.compass.main.folder.test-folder")


def test_move_folder_uses_profile(runner, sample_folder):
    """Test move passes the selected profile to the service."""
    with patch("pltr.commands.folder.FolderService") as mock_service_class:
        mock_service_class.return_value.move_folder.return_value = sample_folder
        result = runner.invoke(
            app,
            [
                "folder",
                "move",
                "ri.compass.main.folder.test-folder",
                "--parent-folder",
                "ri.compass.main.folder.new-parent",
                "--profile",
                "test-profile",
                "--confirm",
            ],
        )

    assert result.exit_code == 0
    mock_service_class.assert_called_once_with(profile="test-profile")


def test_move_folder_error(runner, mock_folder_service):
    """Test move maps service failures to the command error convention."""
    mock_folder_service.move_folder.side_effect = RuntimeError("SDK move failed")

    result = runner.invoke(
        app,
        [
            "folder",
            "move",
            "ri.compass.main.folder.test-folder",
            "--parent-folder",
            "ri.compass.main.folder.new-parent",
            "--confirm",
        ],
    )

    assert result.exit_code == 1
    assert "Failed to move folder: SDK move failed" in result.stdout


def test_list_children(runner, mock_folder_service, sample_children):
    """Test listing folder children."""
    mock_folder_service.list_children.return_value = sample_children

    result = runner.invoke(app, ["folder", "list", "ri.compass.main.folder.parent"])

    assert result.exit_code == 0
    assert "Child Folder" in result.stdout
    assert "Child Dataset" in result.stdout
    assert "Total: 2 items" in result.stdout

    mock_folder_service.list_children.assert_called_once_with(
        "ri.compass.main.folder.parent", page_size=None
    )


def test_list_children_empty(runner, mock_folder_service):
    """Test listing empty folder."""
    mock_folder_service.list_children.return_value = []

    result = runner.invoke(app, ["folder", "list", "ri.compass.main.folder.empty"])

    assert result.exit_code == 0
    assert "No children found in this folder" in result.stdout


def test_list_children_with_pagination(runner, mock_folder_service, sample_children):
    """Test listing folder children with pagination."""
    mock_folder_service.list_children.return_value = sample_children

    result = runner.invoke(
        app, ["folder", "list", "ri.compass.main.folder.parent", "--page-size", "10"]
    )

    assert result.exit_code == 0

    mock_folder_service.list_children.assert_called_once_with(
        "ri.compass.main.folder.parent", page_size=10
    )


def test_batch_get_folders(runner, mock_folder_service, sample_folder):
    """Test getting multiple folders in batch."""
    mock_folder_service.get_folders_batch.return_value = [sample_folder, sample_folder]

    result = runner.invoke(
        app,
        [
            "folder",
            "batch-get",
            "ri.compass.main.folder.folder1",
            "ri.compass.main.folder.folder2",
        ],
    )

    assert result.exit_code == 0
    assert "Total: 2 folders" in result.stdout

    mock_folder_service.get_folders_batch.assert_called_once_with(
        ["ri.compass.main.folder.folder1", "ri.compass.main.folder.folder2"]
    )


def test_create_folder_auth_error(runner, mock_folder_service):
    """Test folder creation with authentication error."""
    mock_folder_service.create_folder.side_effect = ProfileNotFoundError(
        "Profile not found"
    )

    result = runner.invoke(
        app,
        [
            "folder",
            "create",
            "Test Folder",
            "--parent-folder",
            "ri.compass.main.folder.test",
        ],
    )

    assert result.exit_code == 1
    assert "Authentication error" in result.stdout


def test_create_folder_missing_credentials(runner, mock_folder_service):
    """Test folder creation with missing credentials."""
    mock_folder_service.create_folder.side_effect = MissingCredentialsError(
        "Missing credentials"
    )

    result = runner.invoke(
        app,
        [
            "folder",
            "create",
            "Test Folder",
            "--parent-folder",
            "ri.compass.main.folder.test",
        ],
    )

    assert result.exit_code == 1
    assert "Authentication error" in result.stdout


def test_create_folder_general_error(runner, mock_folder_service):
    """Test folder creation with general error."""
    mock_folder_service.create_folder.side_effect = Exception("API error")

    result = runner.invoke(
        app,
        [
            "folder",
            "create",
            "Test Folder",
            "--parent-folder",
            "ri.compass.main.folder.test",
        ],
    )

    assert result.exit_code == 1
    assert "Failed to create folder" in result.stdout


def test_get_folder_error(runner, mock_folder_service):
    """Test get folder with error."""
    mock_folder_service.get_folder.side_effect = Exception("Folder not found")

    result = runner.invoke(app, ["folder", "get", "ri.compass.main.folder.nonexistent"])

    assert result.exit_code == 1
    assert "Failed to get folder" in result.stdout


def test_list_children_error(runner, mock_folder_service):
    """Test list children with error."""
    mock_folder_service.list_children.side_effect = Exception("Permission denied")

    result = runner.invoke(app, ["folder", "list", "ri.compass.main.folder.restricted"])

    assert result.exit_code == 1
    assert "Failed to list folder children" in result.stdout


def test_batch_get_value_error(runner, mock_folder_service):
    """Test batch get with value error (too many folders)."""
    mock_folder_service.get_folders_batch.side_effect = ValueError("Too many folders")

    result = runner.invoke(
        app, ["folder", "batch-get", "ri.compass.main.folder.folder1"]
    )

    assert result.exit_code == 1
    assert "Invalid request" in result.stdout


def test_batch_get_general_error(runner, mock_folder_service):
    """Test batch get with general error."""
    mock_folder_service.get_folders_batch.side_effect = Exception("API error")

    result = runner.invoke(
        app, ["folder", "batch-get", "ri.compass.main.folder.folder1"]
    )

    assert result.exit_code == 1
    assert "Failed to get folders batch" in result.stdout


def test_create_folder_with_profile(runner, mock_folder_service, sample_folder):
    """Test folder creation with custom profile."""
    mock_folder_service.create_folder.return_value = sample_folder

    result = runner.invoke(
        app,
        [
            "folder",
            "create",
            "Test Folder",
            "--parent-folder",
            "ri.compass.main.folder.test",
            "--profile",
            "custom-profile",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully created folder 'Test Folder'" in result.stdout


def test_get_folder_with_output_file(runner, mock_folder_service, sample_folder):
    """Test getting folder with output file."""
    mock_folder_service.get_folder.return_value = sample_folder

    result = runner.invoke(
        app,
        [
            "folder",
            "get",
            "ri.compass.main.folder.test-folder",
            "--output",
            "folder_info.json",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert "Folder information saved to folder_info.json" in result.stdout


def test_list_children_with_output_file(runner, mock_folder_service, sample_children):
    """Test listing children with output file."""
    mock_folder_service.list_children.return_value = sample_children

    result = runner.invoke(
        app,
        [
            "folder",
            "list",
            "ri.compass.main.folder.parent",
            "--output",
            "children.csv",
            "--format",
            "csv",
        ],
    )

    assert result.exit_code == 0
    assert "Folder children saved to children.csv" in result.stdout


def test_batch_get_with_output_file(runner, mock_folder_service, sample_folder):
    """Test batch get with output file."""
    mock_folder_service.get_folders_batch.return_value = [sample_folder]

    result = runner.invoke(
        app,
        [
            "folder",
            "batch-get",
            "ri.compass.main.folder.folder1",
            "--output",
            "folders.json",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert "Folders information saved to folders.json" in result.stdout
