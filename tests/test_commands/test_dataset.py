"""
Tests for dataset CLI commands.
"""

import pytest
import tempfile
from pathlib import Path
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
def sample_datasets():
    """Sample dataset list for testing."""
    return [
        {
            "rid": "ri.foundry.main.dataset.dataset1",
            "name": "Dataset 1",
            "description": "First test dataset",
            "created_time": "2023-01-01T00:00:00Z",
            "size_bytes": 1024000
        },
        {
            "rid": "ri.foundry.main.dataset.dataset2", 
            "name": "Dataset 2",
            "description": "Second test dataset",
            "created_time": "2023-01-02T00:00:00Z",
            "size_bytes": 2048000
        }
    ]


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
        "parent_folder_rid": "ri.foundry.main.folder.parent"
    }


@pytest.fixture
def sample_files():
    """Sample file list for testing."""
    return [
        {
            "path": "data1.csv",
            "size_bytes": 1024,
            "last_modified": "2023-01-01T12:00:00Z",
            "transaction_rid": "ri.foundry.main.transaction.test1"
        },
        {
            "path": "data2.csv",
            "size_bytes": 2048,
            "last_modified": "2023-01-01T13:00:00Z",
            "transaction_rid": "ri.foundry.main.transaction.test2"
        }
    ]


@pytest.fixture
def sample_branches():
    """Sample branch list for testing."""
    return [
        {
            "name": "master",
            "transaction_rid": "ri.foundry.main.transaction.master",
            "created_time": "2023-01-01T00:00:00Z",
            "created_by": "admin@example.com"
        },
        {
            "name": "feature-branch",
            "transaction_rid": "ri.foundry.main.transaction.feature",
            "created_time": "2023-01-01T10:00:00Z",
            "created_by": "developer@example.com"
        }
    ]


def test_list_datasets_success(mock_dataset_service, sample_datasets):
    """Test successful dataset listing."""
    mock_dataset_service.list_datasets.return_value = sample_datasets
    
    result = runner.invoke(app, ["list"])
    
    assert result.exit_code == 0
    mock_dataset_service.list_datasets.assert_called_once_with(limit=None)


def test_list_datasets_with_limit(mock_dataset_service, sample_datasets):
    """Test dataset listing with limit."""
    mock_dataset_service.list_datasets.return_value = sample_datasets[:1]
    
    result = runner.invoke(app, ["list", "--limit", "1"])
    
    assert result.exit_code == 0
    mock_dataset_service.list_datasets.assert_called_once_with(limit=1)


def test_list_datasets_with_profile(mock_dataset_service, sample_datasets):
    """Test dataset listing with specific profile."""
    mock_dataset_service.list_datasets.return_value = sample_datasets
    
    result = runner.invoke(app, ["list", "--profile", "test-profile"])
    
    assert result.exit_code == 0
    # Check that DatasetService was initialized with correct profile
    # Note: This is checked in the service initialization, not the method call


def test_list_datasets_json_format(mock_dataset_service, sample_datasets):
    """Test dataset listing with JSON format."""
    mock_dataset_service.list_datasets.return_value = sample_datasets
    
    result = runner.invoke(app, ["list", "--format", "json"])
    
    assert result.exit_code == 0
    mock_dataset_service.list_datasets.assert_called_once_with(limit=None)


def test_list_datasets_empty(mock_dataset_service):
    """Test dataset listing with no results."""
    mock_dataset_service.list_datasets.return_value = []
    
    result = runner.invoke(app, ["list"])
    
    assert result.exit_code == 0
    assert "No datasets found" in result.stdout


def test_list_datasets_profile_not_found(mock_dataset_service):
    """Test dataset listing with non-existent profile."""
    mock_dataset_service.list_datasets.side_effect = ProfileNotFoundError("Profile not found")
    
    result = runner.invoke(app, ["list"])
    
    assert result.exit_code == 1
    assert "Authentication error" in result.stdout


def test_list_datasets_missing_credentials(mock_dataset_service):
    """Test dataset listing with missing credentials."""
    mock_dataset_service.list_datasets.side_effect = MissingCredentialsError("Missing token")
    
    result = runner.invoke(app, ["list"])
    
    assert result.exit_code == 1
    assert "Authentication error" in result.stdout


def test_list_datasets_api_error(mock_dataset_service):
    """Test dataset listing with API error."""
    mock_dataset_service.list_datasets.side_effect = Exception("API Error")
    
    result = runner.invoke(app, ["list"])
    
    assert result.exit_code == 1
    assert "Failed to list datasets" in result.stdout


def test_get_dataset_success(mock_dataset_service, sample_dataset):
    """Test successful dataset retrieval."""
    mock_dataset_service.get_dataset.return_value = sample_dataset
    
    result = runner.invoke(app, ["get", "ri.foundry.main.dataset.test"])
    
    assert result.exit_code == 0
    mock_dataset_service.get_dataset.assert_called_once_with("ri.foundry.main.dataset.test")


def test_get_dataset_json_format(mock_dataset_service, sample_dataset):
    """Test dataset retrieval with JSON format."""
    mock_dataset_service.get_dataset.return_value = sample_dataset
    
    result = runner.invoke(app, ["get", "ri.foundry.main.dataset.test", "--format", "json"])
    
    assert result.exit_code == 0


def test_get_dataset_error(mock_dataset_service):
    """Test dataset retrieval with error."""
    mock_dataset_service.get_dataset.side_effect = Exception("Dataset not found")
    
    result = runner.invoke(app, ["get", "ri.foundry.main.dataset.test"])
    
    assert result.exit_code == 1
    assert "Failed to get dataset" in result.stdout


def test_upload_file_success(mock_dataset_service):
    """Test successful file upload."""
    mock_result = {
        "dataset_rid": "ri.foundry.main.dataset.test",
        "file_path": "/tmp/test.csv",
        "branch": "master",
        "size_bytes": 1024,
        "uploaded": True,
        "transaction_rid": "ri.foundry.main.transaction.test"
    }
    mock_dataset_service.upload_file.return_value = mock_result
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
        temp_file.write(b"test data")
        temp_path = temp_file.name
    
    try:
        result = runner.invoke(app, [
            "upload", 
            "ri.foundry.main.dataset.test", 
            temp_path
        ])
        
        assert result.exit_code == 0
        assert "Successfully uploaded" in result.stdout
        mock_dataset_service.upload_file.assert_called_once()
        
    finally:
        Path(temp_path).unlink()


def test_upload_file_not_found(mock_dataset_service):
    """Test file upload with non-existent file."""
    result = runner.invoke(app, [
        "upload", 
        "ri.foundry.main.dataset.test", 
        "/nonexistent/file.csv"
    ])
    
    assert result.exit_code == 1
    assert "File not found" in result.stdout


def test_upload_file_directory(mock_dataset_service):
    """Test file upload with directory path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = runner.invoke(app, [
            "upload", 
            "ri.foundry.main.dataset.test", 
            temp_dir
        ])
        
        assert result.exit_code == 1
        assert "Path is not a file" in result.stdout


def test_upload_file_with_branch(mock_dataset_service):
    """Test file upload with custom branch."""
    mock_result = {
        "dataset_rid": "ri.foundry.main.dataset.test",
        "file_path": "/tmp/test.csv",
        "branch": "feature",
        "size_bytes": 1024,
        "uploaded": True
    }
    mock_dataset_service.upload_file.return_value = mock_result
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
        temp_file.write(b"test data")
        temp_path = temp_file.name
    
    try:
        result = runner.invoke(app, [
            "upload", 
            "ri.foundry.main.dataset.test", 
            temp_path,
            "--branch", "feature"
        ])
        
        assert result.exit_code == 0
        
    finally:
        Path(temp_path).unlink()


def test_upload_file_no_progress(mock_dataset_service):
    """Test file upload without progress bar."""
    mock_result = {
        "dataset_rid": "ri.foundry.main.dataset.test",
        "file_path": "/tmp/test.csv",
        "branch": "master",
        "size_bytes": 1024,
        "uploaded": True
    }
    mock_dataset_service.upload_file.return_value = mock_result
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
        temp_file.write(b"test data")
        temp_path = temp_file.name
    
    try:
        result = runner.invoke(app, [
            "upload", 
            "ri.foundry.main.dataset.test", 
            temp_path,
            "--no-progress"
        ])
        
        assert result.exit_code == 0
        
    finally:
        Path(temp_path).unlink()


def test_upload_file_error(mock_dataset_service):
    """Test file upload with error."""
    mock_dataset_service.upload_file.side_effect = Exception("Upload failed")
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
        temp_file.write(b"test data")
        temp_path = temp_file.name
    
    try:
        result = runner.invoke(app, [
            "upload", 
            "ri.foundry.main.dataset.test", 
            temp_path
        ])
        
        assert result.exit_code == 1
        assert "Failed to upload file" in result.stdout
        
    finally:
        Path(temp_path).unlink()


def test_download_file_success(mock_dataset_service):
    """Test successful file download."""
    mock_result = {
        "dataset_rid": "ri.foundry.main.dataset.test",
        "file_path": "data.csv",
        "output_path": "/tmp/data.csv",
        "branch": "master",
        "size_bytes": 1024,
        "downloaded": True
    }
    mock_dataset_service.download_file.return_value = mock_result
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "data.csv"
        
        result = runner.invoke(app, [
            "download", 
            "ri.foundry.main.dataset.test", 
            "data.csv",
            "--output", str(output_path)
        ])
        
        assert result.exit_code == 0
        assert "Successfully downloaded" in result.stdout
        mock_dataset_service.download_file.assert_called_once()


def test_download_file_default_output(mock_dataset_service):
    """Test file download with default output path."""
    mock_result = {
        "dataset_rid": "ri.foundry.main.dataset.test",
        "file_path": "data.csv",
        "output_path": "./data.csv",
        "branch": "master",
        "size_bytes": 1024,
        "downloaded": True
    }
    mock_dataset_service.download_file.return_value = mock_result
    
    result = runner.invoke(app, [
        "download", 
        "ri.foundry.main.dataset.test", 
        "data.csv"
    ])
    
    assert result.exit_code == 0


def test_download_file_error(mock_dataset_service):
    """Test file download with error."""
    mock_dataset_service.download_file.side_effect = Exception("Download failed")
    
    result = runner.invoke(app, [
        "download", 
        "ri.foundry.main.dataset.test", 
        "data.csv"
    ])
    
    assert result.exit_code == 1
    assert "Failed to download file" in result.stdout


def test_list_files_success(mock_dataset_service, sample_files):
    """Test successful file listing."""
    mock_dataset_service.list_files.return_value = sample_files
    
    result = runner.invoke(app, ["files", "ri.foundry.main.dataset.test"])
    
    assert result.exit_code == 0
    mock_dataset_service.list_files.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test", 
        branch="master"
    )


def test_list_files_with_branch(mock_dataset_service, sample_files):
    """Test file listing with custom branch."""
    mock_dataset_service.list_files.return_value = sample_files
    
    result = runner.invoke(app, [
        "files", 
        "ri.foundry.main.dataset.test", 
        "--branch", "feature"
    ])
    
    assert result.exit_code == 0
    mock_dataset_service.list_files.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test", 
        branch="feature"
    )


def test_list_files_empty(mock_dataset_service):
    """Test file listing with no results."""
    mock_dataset_service.list_files.return_value = []
    
    result = runner.invoke(app, ["files", "ri.foundry.main.dataset.test"])
    
    assert result.exit_code == 0
    assert "No files found" in result.stdout


def test_list_files_error(mock_dataset_service):
    """Test file listing with error."""
    mock_dataset_service.list_files.side_effect = Exception("List failed")
    
    result = runner.invoke(app, ["files", "ri.foundry.main.dataset.test"])
    
    assert result.exit_code == 1
    assert "Failed to list files" in result.stdout


def test_create_dataset_success(mock_dataset_service, sample_dataset):
    """Test successful dataset creation."""
    mock_dataset_service.create_dataset.return_value = sample_dataset
    
    result = runner.invoke(app, ["create", "New Dataset"])
    
    assert result.exit_code == 0
    assert "Successfully created dataset" in result.stdout
    mock_dataset_service.create_dataset.assert_called_once_with(
        name="New Dataset", 
        parent_folder_rid=None
    )


def test_create_dataset_with_parent_folder(mock_dataset_service, sample_dataset):
    """Test dataset creation with parent folder."""
    mock_dataset_service.create_dataset.return_value = sample_dataset
    
    result = runner.invoke(app, [
        "create", 
        "New Dataset", 
        "--parent-folder", "ri.foundry.main.folder.parent"
    ])
    
    assert result.exit_code == 0
    mock_dataset_service.create_dataset.assert_called_once_with(
        name="New Dataset", 
        parent_folder_rid="ri.foundry.main.folder.parent"
    )


def test_create_dataset_error(mock_dataset_service):
    """Test dataset creation with error."""
    mock_dataset_service.create_dataset.side_effect = Exception("Creation failed")
    
    result = runner.invoke(app, ["create", "New Dataset"])
    
    assert result.exit_code == 1
    assert "Failed to create dataset" in result.stdout


def test_delete_dataset_success(mock_dataset_service):
    """Test successful dataset deletion with confirmation."""
    mock_dataset_service.delete_dataset.return_value = True
    
    result = runner.invoke(app, ["delete", "ri.foundry.main.dataset.test"], input="y\n")
    
    assert result.exit_code == 0
    assert "Successfully deleted dataset" in result.stdout
    mock_dataset_service.delete_dataset.assert_called_once_with("ri.foundry.main.dataset.test")


def test_delete_dataset_cancelled(mock_dataset_service):
    """Test dataset deletion cancelled by user."""
    result = runner.invoke(app, ["delete", "ri.foundry.main.dataset.test"], input="n\n")
    
    assert result.exit_code == 0
    assert "Deletion cancelled" in result.stdout
    mock_dataset_service.delete_dataset.assert_not_called()


def test_delete_dataset_force(mock_dataset_service):
    """Test dataset deletion with force flag."""
    mock_dataset_service.delete_dataset.return_value = True
    
    result = runner.invoke(app, ["delete", "ri.foundry.main.dataset.test", "--force"])
    
    assert result.exit_code == 0
    assert "Successfully deleted dataset" in result.stdout
    mock_dataset_service.delete_dataset.assert_called_once_with("ri.foundry.main.dataset.test")


def test_delete_dataset_error(mock_dataset_service):
    """Test dataset deletion with error."""
    mock_dataset_service.delete_dataset.side_effect = Exception("Deletion failed")
    
    result = runner.invoke(app, ["delete", "ri.foundry.main.dataset.test", "--force"])
    
    assert result.exit_code == 1
    assert "Failed to delete dataset" in result.stdout


def test_list_branches_success(mock_dataset_service, sample_branches):
    """Test successful branch listing."""
    mock_dataset_service.get_branches.return_value = sample_branches
    
    result = runner.invoke(app, ["branches", "ri.foundry.main.dataset.test"])
    
    assert result.exit_code == 0
    mock_dataset_service.get_branches.assert_called_once_with("ri.foundry.main.dataset.test")


def test_list_branches_empty(mock_dataset_service):
    """Test branch listing with no results."""
    mock_dataset_service.get_branches.return_value = []
    
    result = runner.invoke(app, ["branches", "ri.foundry.main.dataset.test"])
    
    assert result.exit_code == 0
    assert "No branches found" in result.stdout


def test_list_branches_error(mock_dataset_service):
    """Test branch listing with error."""
    mock_dataset_service.get_branches.side_effect = Exception("Branch list failed")
    
    result = runner.invoke(app, ["branches", "ri.foundry.main.dataset.test"])
    
    assert result.exit_code == 1
    assert "Failed to list branches" in result.stdout


def test_create_branch_success(mock_dataset_service):
    """Test successful branch creation."""
    mock_branch = {
        "name": "new-branch",
        "dataset_rid": "ri.foundry.main.dataset.test",
        "parent_branch": "master",
        "transaction_rid": "ri.foundry.main.transaction.new"
    }
    mock_dataset_service.create_branch.return_value = mock_branch
    
    result = runner.invoke(app, [
        "create-branch", 
        "ri.foundry.main.dataset.test", 
        "new-branch"
    ])
    
    assert result.exit_code == 0
    assert "Successfully created branch" in result.stdout
    mock_dataset_service.create_branch.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test",
        branch_name="new-branch",
        parent_branch="master"
    )


def test_create_branch_with_parent(mock_dataset_service):
    """Test branch creation with custom parent."""
    mock_branch = {
        "name": "new-branch",
        "dataset_rid": "ri.foundry.main.dataset.test",
        "parent_branch": "feature",
        "transaction_rid": "ri.foundry.main.transaction.new"
    }
    mock_dataset_service.create_branch.return_value = mock_branch
    
    result = runner.invoke(app, [
        "create-branch", 
        "ri.foundry.main.dataset.test", 
        "new-branch",
        "--parent", "feature"
    ])
    
    assert result.exit_code == 0
    mock_dataset_service.create_branch.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test",
        branch_name="new-branch",
        parent_branch="feature"
    )


def test_create_branch_error(mock_dataset_service):
    """Test branch creation with error."""
    mock_dataset_service.create_branch.side_effect = Exception("Branch creation failed")
    
    result = runner.invoke(app, [
        "create-branch", 
        "ri.foundry.main.dataset.test", 
        "new-branch"
    ])
    
    assert result.exit_code == 1
    assert "Failed to create branch" in result.stdout