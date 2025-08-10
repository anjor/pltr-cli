"""
Tests for dataset CLI commands.
"""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from pltr.commands.dataset import app
from pltr.auth.base import ProfileNotFoundError, MissingCredentialsError

runner = CliRunner()


@pytest.fixture
def mock_dataset_service():
    """Mock DatasetService for command tests."""
    with patch("pltr.commands.dataset.DatasetService") as mock_service_class:
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        yield mock_service


@pytest.fixture
def sample_dataset():
    """Sample single dataset for testing."""
    return {
        "rid": "ri.foundry.main.dataset.test",
        "name": "Test Dataset",
        "description": "A test dataset",
        "created_time": "2023-01-01T00:00:00Z",
        "created_by": "test.user@example.com",
        "last_modified": "2023-01-02T00:00:00Z",
        "size_bytes": 1024000,
        "schema_id": "test-schema-id",
        "parent_folder_rid": "ri.foundry.main.folder.parent",
    }


# Tests for 'get' command
def test_get_dataset_success(mock_dataset_service, sample_dataset):
    """Test successful dataset retrieval."""
    mock_dataset_service.get_dataset.return_value = sample_dataset

    result = runner.invoke(app, ["get", "ri.foundry.main.dataset.test"])

    assert result.exit_code == 0
    mock_dataset_service.get_dataset.assert_called_once_with(
        "ri.foundry.main.dataset.test"
    )


def test_get_dataset_json_format(mock_dataset_service, sample_dataset):
    """Test dataset retrieval with JSON format."""
    mock_dataset_service.get_dataset.return_value = sample_dataset

    result = runner.invoke(
        app, ["get", "ri.foundry.main.dataset.test", "--format", "json"]
    )

    assert result.exit_code == 0


def test_get_dataset_csv_format(mock_dataset_service, sample_dataset):
    """Test dataset retrieval with CSV format."""
    mock_dataset_service.get_dataset.return_value = sample_dataset

    result = runner.invoke(
        app, ["get", "ri.foundry.main.dataset.test", "--format", "csv"]
    )

    assert result.exit_code == 0


def test_get_dataset_with_profile(mock_dataset_service, sample_dataset):
    """Test dataset retrieval with specific profile."""
    mock_dataset_service.get_dataset.return_value = sample_dataset

    result = runner.invoke(
        app, ["get", "ri.foundry.main.dataset.test", "--profile", "test-profile"]
    )

    assert result.exit_code == 0


def test_get_dataset_profile_not_found(mock_dataset_service):
    """Test dataset retrieval with non-existent profile."""
    mock_dataset_service.get_dataset.side_effect = ProfileNotFoundError(
        "Profile not found"
    )

    result = runner.invoke(app, ["get", "ri.foundry.main.dataset.test"])

    assert result.exit_code == 1
    assert "Profile not found" in result.stdout


def test_get_dataset_missing_credentials(mock_dataset_service):
    """Test dataset retrieval with missing credentials."""
    mock_dataset_service.get_dataset.side_effect = MissingCredentialsError(
        "Missing token"
    )

    result = runner.invoke(app, ["get", "ri.foundry.main.dataset.test"])

    assert result.exit_code == 1
    assert "Missing token" in result.stdout


def test_get_dataset_error(mock_dataset_service):
    """Test dataset retrieval with error."""
    mock_dataset_service.get_dataset.side_effect = Exception("Dataset not found")

    result = runner.invoke(app, ["get", "ri.foundry.main.dataset.test"])

    assert result.exit_code == 1
    assert "Failed to get dataset" in result.stdout


# Tests for 'create' command
def test_create_dataset_success(mock_dataset_service, sample_dataset):
    """Test successful dataset creation."""
    mock_dataset_service.create_dataset.return_value = sample_dataset

    result = runner.invoke(app, ["create", "New Dataset"])

    assert result.exit_code == 0
    assert "Successfully created dataset" in result.stdout
    mock_dataset_service.create_dataset.assert_called_once_with(
        name="New Dataset", parent_folder_rid=None
    )


def test_create_dataset_with_parent_folder(mock_dataset_service, sample_dataset):
    """Test dataset creation with parent folder."""
    mock_dataset_service.create_dataset.return_value = sample_dataset

    result = runner.invoke(
        app,
        ["create", "New Dataset", "--parent-folder", "ri.foundry.main.folder.parent"],
    )

    assert result.exit_code == 0
    mock_dataset_service.create_dataset.assert_called_once_with(
        name="New Dataset", parent_folder_rid="ri.foundry.main.folder.parent"
    )


def test_create_dataset_json_format(mock_dataset_service, sample_dataset):
    """Test dataset creation with JSON output format."""
    mock_dataset_service.create_dataset.return_value = sample_dataset

    result = runner.invoke(app, ["create", "New Dataset", "--format", "json"])

    assert result.exit_code == 0


def test_create_dataset_with_profile(mock_dataset_service, sample_dataset):
    """Test dataset creation with specific profile."""
    mock_dataset_service.create_dataset.return_value = sample_dataset

    result = runner.invoke(app, ["create", "New Dataset", "--profile", "test-profile"])

    assert result.exit_code == 0


def test_create_dataset_profile_not_found(mock_dataset_service):
    """Test dataset creation with non-existent profile."""
    mock_dataset_service.create_dataset.side_effect = ProfileNotFoundError(
        "Profile not found"
    )

    result = runner.invoke(app, ["create", "New Dataset"])

    assert result.exit_code == 1
    assert "Profile not found" in result.stdout


def test_create_dataset_missing_credentials(mock_dataset_service):
    """Test dataset creation with missing credentials."""
    mock_dataset_service.create_dataset.side_effect = MissingCredentialsError(
        "Missing token"
    )

    result = runner.invoke(app, ["create", "New Dataset"])

    assert result.exit_code == 1
    assert "Missing token" in result.stdout


def test_create_dataset_error(mock_dataset_service):
    """Test dataset creation with error."""
    mock_dataset_service.create_dataset.side_effect = Exception("Creation failed")

    result = runner.invoke(app, ["create", "New Dataset"])

    assert result.exit_code == 1
    assert "Failed to create dataset" in result.stdout
