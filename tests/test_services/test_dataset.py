"""
Tests for dataset service functionality.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pltr.services.dataset import DatasetService


@pytest.fixture
def mock_foundry_client():
    """Mock Foundry client with datasets service."""
    client = Mock()
    datasets_service = Mock()
    client.datasets = datasets_service
    return client, datasets_service


@pytest.fixture
def mock_dataset_service(mock_foundry_client):
    """Mock DatasetService with mocked client."""
    client, datasets_service = mock_foundry_client

    with patch("pltr.services.base.AuthManager") as mock_auth_manager:
        mock_auth_instance = Mock()
        mock_auth_instance.get_client.return_value = client
        mock_auth_manager.return_value = mock_auth_instance

        service = DatasetService()
        yield service, datasets_service


@pytest.fixture
def sample_dataset():
    """Sample dataset object."""
    dataset = Mock()
    dataset.rid = "ri.foundry.main.dataset.test-dataset"
    dataset.name = "Test Dataset"
    dataset.description = "A test dataset"
    dataset.created_time = "2023-01-01T00:00:00Z"
    dataset.created_by = "test.user@example.com"
    dataset.last_modified = "2023-01-02T00:00:00Z"
    dataset.size_bytes = 1024000
    dataset.schema_id = "test-schema-id"
    dataset.parent_folder_rid = "ri.foundry.main.folder.parent"
    return dataset


@pytest.fixture
def sample_file():
    """Sample file object."""
    file = Mock()
    file.path = "data.csv"
    file.size_bytes = 2048
    file.last_modified = "2023-01-01T12:00:00Z"
    file.transaction_rid = "ri.foundry.main.transaction.test"
    return file


@pytest.fixture
def sample_branch():
    """Sample branch object."""
    branch = Mock()
    branch.name = "test-branch"
    branch.transaction_rid = "ri.foundry.main.transaction.branch"
    branch.created_time = "2023-01-01T10:00:00Z"
    branch.created_by = "test.user@example.com"
    return branch


def test_dataset_service_initialization():
    """Test DatasetService initialization."""
    with patch("pltr.services.base.AuthManager"):
        service = DatasetService()
        assert service.profile is None

        service_with_profile = DatasetService(profile="test")
        assert service_with_profile.profile == "test"


def test_dataset_service_get_service(mock_dataset_service):
    """Test _get_service returns datasets service."""
    service, datasets_service = mock_dataset_service

    result = service._get_service()
    assert result == datasets_service


def test_list_datasets_success(mock_dataset_service, sample_dataset):
    """Test successful dataset listing."""
    service, datasets_service = mock_dataset_service

    # Mock the list_datasets response
    mock_response = Mock()
    mock_response.data = [sample_dataset]
    mock_response.next_page_token = None
    datasets_service.list_datasets.return_value = mock_response

    result = service.list_datasets()

    assert len(result) == 1
    assert result[0]["rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result[0]["name"] == "Test Dataset"
    datasets_service.list_datasets.assert_called_once()


def test_list_datasets_with_limit(mock_dataset_service, sample_dataset):
    """Test dataset listing with limit."""
    service, datasets_service = mock_dataset_service

    # Create multiple sample datasets
    datasets = [sample_dataset, sample_dataset, sample_dataset]
    mock_response = Mock()
    mock_response.data = datasets
    mock_response.next_page_token = None
    datasets_service.list_datasets.return_value = mock_response

    result = service.list_datasets(limit=2)

    assert len(result) == 2
    datasets_service.list_datasets.assert_called_once_with(limit=2, page_token=None)


def test_list_datasets_pagination(mock_dataset_service, sample_dataset):
    """Test dataset listing with pagination."""
    service, datasets_service = mock_dataset_service

    # First page
    mock_response1 = Mock()
    mock_response1.data = [sample_dataset]
    mock_response1.next_page_token = "page2"

    # Second page
    mock_response2 = Mock()
    mock_response2.data = [sample_dataset]
    mock_response2.next_page_token = None

    datasets_service.list_datasets.side_effect = [mock_response1, mock_response2]

    result = service.list_datasets()

    assert len(result) == 2
    assert datasets_service.list_datasets.call_count == 2


def test_list_datasets_error(mock_dataset_service):
    """Test dataset listing with error."""
    service, datasets_service = mock_dataset_service

    datasets_service.list_datasets.side_effect = Exception("API Error")

    with pytest.raises(RuntimeError, match="Failed to list datasets"):
        service.list_datasets()


def test_get_dataset_success(mock_dataset_service, sample_dataset):
    """Test successful dataset retrieval."""
    service, datasets_service = mock_dataset_service

    datasets_service.get_dataset.return_value = sample_dataset

    result = service.get_dataset("ri.foundry.main.dataset.test-dataset")

    assert result["rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["name"] == "Test Dataset"
    datasets_service.get_dataset.assert_called_once_with(
        "ri.foundry.main.dataset.test-dataset"
    )


def test_get_dataset_error(mock_dataset_service):
    """Test dataset retrieval with error."""
    service, datasets_service = mock_dataset_service

    datasets_service.get_dataset.side_effect = Exception("Dataset not found")

    with pytest.raises(RuntimeError, match="Failed to get dataset"):
        service.get_dataset("ri.foundry.main.dataset.nonexistent")


def test_create_dataset_success(mock_dataset_service, sample_dataset):
    """Test successful dataset creation."""
    service, datasets_service = mock_dataset_service

    datasets_service.create_dataset.return_value = sample_dataset

    result = service.create_dataset("New Dataset", "ri.foundry.main.folder.parent")

    assert result["rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["name"] == "Test Dataset"
    datasets_service.create_dataset.assert_called_once_with(
        name="New Dataset", parent_folder_rid="ri.foundry.main.folder.parent"
    )


def test_create_dataset_error(mock_dataset_service):
    """Test dataset creation with error."""
    service, datasets_service = mock_dataset_service

    datasets_service.create_dataset.side_effect = Exception("Creation failed")

    with pytest.raises(RuntimeError, match="Failed to create dataset"):
        service.create_dataset("New Dataset")


def test_delete_dataset_success(mock_dataset_service):
    """Test successful dataset deletion."""
    service, datasets_service = mock_dataset_service

    datasets_service.delete_dataset.return_value = None

    result = service.delete_dataset("ri.foundry.main.dataset.test-dataset")

    assert result is True
    datasets_service.delete_dataset.assert_called_once_with(
        "ri.foundry.main.dataset.test-dataset"
    )


def test_delete_dataset_error(mock_dataset_service):
    """Test dataset deletion with error."""
    service, datasets_service = mock_dataset_service

    datasets_service.delete_dataset.side_effect = Exception("Deletion failed")

    with pytest.raises(RuntimeError, match="Failed to delete dataset"):
        service.delete_dataset("ri.foundry.main.dataset.test-dataset")


def test_upload_file_success(mock_dataset_service):
    """Test successful file upload."""
    service, datasets_service = mock_dataset_service

    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"test data")
        temp_path = Path(temp_file.name)

    try:
        mock_result = Mock()
        mock_result.transaction_rid = "ri.foundry.main.transaction.test"
        datasets_service.upload_file.return_value = mock_result

        result = service.upload_file("ri.foundry.main.dataset.test-dataset", temp_path)

        assert result["dataset_rid"] == "ri.foundry.main.dataset.test-dataset"
        assert result["file_path"] == str(temp_path)
        assert result["branch"] == "master"
        assert result["uploaded"] is True
        assert result["size_bytes"] > 0

        datasets_service.upload_file.assert_called_once()

    finally:
        temp_path.unlink()


def test_upload_file_not_found(mock_dataset_service):
    """Test file upload with non-existent file."""
    service, datasets_service = mock_dataset_service

    with pytest.raises(FileNotFoundError):
        service.upload_file(
            "ri.foundry.main.dataset.test-dataset", "/nonexistent/file.csv"
        )


def test_upload_file_error(mock_dataset_service):
    """Test file upload with API error."""
    service, datasets_service = mock_dataset_service

    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"test data")
        temp_path = Path(temp_file.name)

    try:
        datasets_service.upload_file.side_effect = Exception("Upload failed")

        with pytest.raises(RuntimeError, match="Failed to upload file"):
            service.upload_file("ri.foundry.main.dataset.test-dataset", temp_path)

    finally:
        temp_path.unlink()


def test_download_file_success(mock_dataset_service):
    """Test successful file download."""
    service, datasets_service = mock_dataset_service

    # Mock file content
    file_content = b"downloaded data"
    datasets_service.download_file.return_value = file_content

    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "output.csv"

        result = service.download_file(
            "ri.foundry.main.dataset.test-dataset", "data.csv", output_path
        )

        assert result["dataset_rid"] == "ri.foundry.main.dataset.test-dataset"
        assert result["file_path"] == "data.csv"
        assert result["output_path"] == str(output_path)
        assert result["downloaded"] is True
        assert result["size_bytes"] == len(file_content)

        # Check file was created with correct content
        assert output_path.exists()
        assert output_path.read_bytes() == file_content

        datasets_service.download_file.assert_called_once_with(
            dataset_rid="ri.foundry.main.dataset.test-dataset",
            file_path="data.csv",
            branch="master",
        )


def test_download_file_stream(mock_dataset_service):
    """Test file download with stream content."""
    service, datasets_service = mock_dataset_service

    # Mock file content as stream
    file_content = b"downloaded data"
    mock_stream = Mock()
    mock_stream.read.return_value = file_content
    datasets_service.download_file.return_value = mock_stream

    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "output.csv"

        result = service.download_file(
            "ri.foundry.main.dataset.test-dataset", "data.csv", output_path
        )

        assert result["downloaded"] is True
        assert output_path.exists()
        assert output_path.read_bytes() == file_content
        mock_stream.read.assert_called_once()


def test_download_file_error(mock_dataset_service):
    """Test file download with error."""
    service, datasets_service = mock_dataset_service

    datasets_service.download_file.side_effect = Exception("Download failed")

    with pytest.raises(RuntimeError, match="Failed to download file"):
        service.download_file(
            "ri.foundry.main.dataset.test-dataset", "data.csv", "/tmp/output.csv"
        )


def test_list_files_success(mock_dataset_service, sample_file):
    """Test successful file listing."""
    service, datasets_service = mock_dataset_service

    datasets_service.list_files.return_value = [sample_file]

    result = service.list_files("ri.foundry.main.dataset.test-dataset")

    assert len(result) == 1
    assert result[0]["path"] == "data.csv"
    assert result[0]["size_bytes"] == 2048
    datasets_service.list_files.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test-dataset", branch="master"
    )


def test_list_files_error(mock_dataset_service):
    """Test file listing with error."""
    service, datasets_service = mock_dataset_service

    datasets_service.list_files.side_effect = Exception("List failed")

    with pytest.raises(RuntimeError, match="Failed to list files"):
        service.list_files("ri.foundry.main.dataset.test-dataset")


def test_get_branches_success(mock_dataset_service, sample_branch):
    """Test successful branch listing."""
    service, datasets_service = mock_dataset_service

    datasets_service.list_branches.return_value = [sample_branch]

    result = service.get_branches("ri.foundry.main.dataset.test-dataset")

    assert len(result) == 1
    assert result[0]["name"] == "test-branch"
    datasets_service.list_branches.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test-dataset"
    )


def test_get_branches_error(mock_dataset_service):
    """Test branch listing with error."""
    service, datasets_service = mock_dataset_service

    datasets_service.list_branches.side_effect = Exception("Branch list failed")

    with pytest.raises(RuntimeError, match="Failed to get branches"):
        service.get_branches("ri.foundry.main.dataset.test-dataset")


def test_create_branch_success(mock_dataset_service, sample_branch):
    """Test successful branch creation."""
    service, datasets_service = mock_dataset_service

    datasets_service.create_branch.return_value = sample_branch

    result = service.create_branch(
        "ri.foundry.main.dataset.test-dataset", "new-branch", "master"
    )

    assert result["name"] == "test-branch"
    assert result["dataset_rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["parent_branch"] == "master"
    datasets_service.create_branch.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test-dataset",
        branch_name="new-branch",
        parent_branch="master",
    )


def test_create_branch_error(mock_dataset_service):
    """Test branch creation with error."""
    service, datasets_service = mock_dataset_service

    datasets_service.create_branch.side_effect = Exception("Branch creation failed")

    with pytest.raises(RuntimeError, match="Failed to create branch"):
        service.create_branch("ri.foundry.main.dataset.test-dataset", "new-branch")


def test_format_dataset_info(mock_dataset_service, sample_dataset):
    """Test dataset info formatting."""
    service, datasets_service = mock_dataset_service

    result = service._format_dataset_info(sample_dataset)

    assert result["rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["name"] == "Test Dataset"
    assert result["description"] == "A test dataset"
    assert result["created_time"] == "2023-01-01T00:00:00Z"
    assert result["created_by"] == "test.user@example.com"
    assert result["last_modified"] == "2023-01-02T00:00:00Z"
    assert result["size_bytes"] == 1024000
    assert result["schema_id"] == "test-schema-id"
    assert result["parent_folder_rid"] == "ri.foundry.main.folder.parent"


def test_format_dataset_info_minimal():
    """Test dataset info formatting with minimal attributes."""
    service_cls = DatasetService

    # Create a minimal dataset object
    minimal_dataset = Mock()
    minimal_dataset.rid = "ri.foundry.main.dataset.minimal"
    # Remove all other attributes
    for attr in [
        "name",
        "description",
        "created_time",
        "created_by",
        "last_modified",
        "size_bytes",
        "schema_id",
        "parent_folder_rid",
    ]:
        if hasattr(minimal_dataset, attr):
            delattr(minimal_dataset, attr)

    with patch("pltr.services.base.AuthManager"):
        service = service_cls()
        result = service._format_dataset_info(minimal_dataset)

    assert result["rid"] == "ri.foundry.main.dataset.minimal"
    assert result["name"] == "Unknown"
    assert result["description"] == ""
    assert result["created_time"] is None
    assert result["created_by"] is None
    assert result["last_modified"] is None
    assert result["size_bytes"] is None
    assert result["schema_id"] is None
    assert result["parent_folder_rid"] is None
