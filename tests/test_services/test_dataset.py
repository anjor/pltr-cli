"""
Tests for dataset service.
"""

import pytest
from unittest.mock import Mock, patch

from pltr.services.dataset import DatasetService


@pytest.fixture
def mock_dataset_service():
    """Create a mocked DatasetService."""
    with patch("pltr.services.base.AuthManager") as mock_auth:
        # Set up client mock
        mock_client = Mock()
        mock_datasets = Mock()
        mock_dataset_class = Mock()  # The Dataset class
        mock_datasets.Dataset = mock_dataset_class
        mock_client.datasets = mock_datasets
        mock_auth.return_value.get_client.return_value = mock_client

        # Create service
        service = DatasetService()
        return service, mock_dataset_class


@pytest.fixture
def sample_dataset():
    """Create sample dataset object."""
    dataset = Mock()
    dataset.rid = "ri.foundry.main.dataset.test-dataset"
    dataset.name = "Test Dataset"
    dataset.parent_folder_rid = "ri.foundry.main.folder.parent"
    return dataset


@pytest.fixture
def sample_dataset_full():
    """Create sample dataset object with all available attributes."""
    dataset = Mock()
    dataset.rid = "ri.foundry.main.dataset.test-dataset"
    dataset.name = "Test Dataset"
    dataset.parent_folder_rid = "ri.foundry.main.folder.parent"
    # The v2 API only has these three attributes
    return dataset


def test_dataset_service_initialization():
    """Test DatasetService initialization."""
    with patch("pltr.services.base.AuthManager"):
        service = DatasetService()
        assert service is not None


def test_dataset_service_get_service(mock_dataset_service):
    """Test getting the underlying datasets service."""
    service, mock_dataset_class = mock_dataset_service
    # The service returns self.client.datasets, not the Dataset class
    assert service._get_service().Dataset == mock_dataset_class


def test_get_dataset_success(mock_dataset_service, sample_dataset):
    """Test successful dataset retrieval."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Dataset.get static method response
    mock_dataset_class.get.return_value = sample_dataset

    result = service.get_dataset("ri.foundry.main.dataset.test-dataset")

    assert result["rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["name"] == "Test Dataset"
    assert result["parent_folder_rid"] == "ri.foundry.main.folder.parent"
    mock_dataset_class.get.assert_called_once_with(
        "ri.foundry.main.dataset.test-dataset"
    )


def test_get_dataset_with_full_attributes(mock_dataset_service, sample_dataset_full):
    """Test dataset retrieval with all attributes present."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Dataset.get static method response
    mock_dataset_class.get.return_value = sample_dataset_full

    result = service.get_dataset("ri.foundry.main.dataset.test-dataset")

    assert result["rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["name"] == "Test Dataset"
    assert result["parent_folder_rid"] == "ri.foundry.main.folder.parent"
    mock_dataset_class.get.assert_called_once_with(
        "ri.foundry.main.dataset.test-dataset"
    )


def test_get_dataset_error(mock_dataset_service):
    """Test dataset retrieval with error."""
    service, mock_dataset_class = mock_dataset_service

    # Mock error response
    mock_dataset_class.get.side_effect = Exception("Dataset not found")

    with pytest.raises(RuntimeError, match="Failed to get dataset"):
        service.get_dataset("ri.foundry.main.dataset.nonexistent")


def test_create_dataset_success(mock_dataset_service, sample_dataset):
    """Test successful dataset creation."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Dataset.create static method response
    mock_dataset_class.create.return_value = sample_dataset

    result = service.create_dataset(name="New Dataset")

    assert result["rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["name"] == "Test Dataset"
    assert result["parent_folder_rid"] == "ri.foundry.main.folder.parent"

    # Verify the create method was called with correct parameters
    mock_dataset_class.create.assert_called_once_with(
        name="New Dataset", parent_folder_rid=None
    )


def test_create_dataset_with_parent_folder(mock_dataset_service, sample_dataset):
    """Test dataset creation with parent folder."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Dataset.create static method response
    mock_dataset_class.create.return_value = sample_dataset

    result = service.create_dataset(
        name="New Dataset", parent_folder_rid="ri.foundry.main.folder.parent"
    )

    assert result["rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["parent_folder_rid"] == "ri.foundry.main.folder.parent"

    # Verify the create method was called with parent folder
    mock_dataset_class.create.assert_called_once_with(
        name="New Dataset", parent_folder_rid="ri.foundry.main.folder.parent"
    )


def test_create_dataset_error(mock_dataset_service):
    """Test dataset creation with error."""
    service, mock_dataset_class = mock_dataset_service

    # Mock error response
    mock_dataset_class.create.side_effect = Exception("Creation failed")

    with pytest.raises(RuntimeError, match="Failed to create dataset"):
        service.create_dataset(name="New Dataset")


def test_read_table_arrow_format(mock_dataset_service):
    """Test reading dataset as Arrow table."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Dataset.read_table static method response
    mock_table = Mock()
    mock_dataset_class.read_table.return_value = mock_table

    result = service.read_table("ri.foundry.main.dataset.test-dataset", format="arrow")

    assert result == mock_table
    mock_dataset_class.read_table.assert_called_once_with(
        "ri.foundry.main.dataset.test-dataset", format="arrow"
    )


def test_read_table_pandas_format(mock_dataset_service):
    """Test reading dataset as Pandas DataFrame."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Dataset.read_table static method response
    mock_df = Mock()
    mock_dataset_class.read_table.return_value = mock_df

    result = service.read_table("ri.foundry.main.dataset.test-dataset", format="pandas")

    assert result == mock_df
    mock_dataset_class.read_table.assert_called_once_with(
        "ri.foundry.main.dataset.test-dataset", format="pandas"
    )


def test_read_table_error(mock_dataset_service):
    """Test reading dataset with error."""
    service, mock_dataset_class = mock_dataset_service

    # Mock error response
    mock_dataset_class.read_table.side_effect = Exception("Read failed")

    with pytest.raises(RuntimeError, match="Failed to read dataset"):
        service.read_table("ri.foundry.main.dataset.test-dataset")


def test_format_dataset_info(mock_dataset_service, sample_dataset):
    """Test dataset info formatting."""
    service, mock_dataset_class = mock_dataset_service

    result = service._format_dataset_info(sample_dataset)

    assert result["rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["name"] == "Test Dataset"
    assert result["parent_folder_rid"] == "ri.foundry.main.folder.parent"
    # Only these three fields are returned by _format_dataset_info


def test_format_dataset_info_minimal():
    """Test dataset info formatting with minimal attributes."""
    with patch("pltr.services.base.AuthManager"):
        service = DatasetService()

        # Create a minimal dataset object
        minimal_dataset = Mock()
        minimal_dataset.rid = "ri.foundry.main.dataset.minimal"
        minimal_dataset.name = "Minimal Dataset"
        minimal_dataset.parent_folder_rid = None

        result = service._format_dataset_info(minimal_dataset)

        assert result["rid"] == "ri.foundry.main.dataset.minimal"
        assert result["name"] == "Minimal Dataset"
        assert result["parent_folder_rid"] is None
        # Only rid, name, and parent_folder_rid are returned


def test_format_dataset_info_with_parent(mock_dataset_service):
    """Test dataset info formatting with parent folder."""
    service, mock_dataset_class = mock_dataset_service

    # Create dataset with parent folder
    dataset = Mock()
    dataset.rid = "ri.foundry.main.dataset.test"
    dataset.name = "Test Dataset"
    dataset.parent_folder_rid = "ri.foundry.main.folder.specific"

    result = service._format_dataset_info(dataset)

    assert result["rid"] == "ri.foundry.main.dataset.test"
    assert result["name"] == "Test Dataset"
    assert result["parent_folder_rid"] == "ri.foundry.main.folder.specific"
    # The v2 API only returns these three fields


def test_get_schedules_success(mock_dataset_service):
    """Test successful dataset schedules retrieval."""
    service, mock_dataset_class = mock_dataset_service

    # Mock schedules response
    mock_schedule = Mock()
    mock_schedule.rid = "ri.foundry.main.schedule.test"
    mock_schedule.name = "Test Schedule"
    mock_schedule.description = "Test schedule description"
    mock_schedule.enabled = True
    mock_schedule.created_time = "2023-01-01T00:00:00Z"

    mock_dataset_class.get_schedules.return_value = [mock_schedule]

    result = service.get_schedules("ri.foundry.main.dataset.test-dataset")

    assert len(result) == 1
    assert result[0]["schedule_rid"] == "ri.foundry.main.schedule.test"
    assert result[0]["name"] == "Test Schedule"
    assert result[0]["enabled"] is True


def test_get_jobs_success(mock_dataset_service):
    """Test successful dataset jobs retrieval."""
    service, mock_dataset_class = mock_dataset_service

    # Mock jobs response
    mock_job = Mock()
    mock_job.rid = "ri.foundry.main.job.test"
    mock_job.name = "Test Job"
    mock_job.status = "SUCCEEDED"
    mock_job.created_time = "2023-01-01T00:00:00Z"
    mock_job.started_time = "2023-01-01T01:00:00Z"
    mock_job.completed_time = "2023-01-01T02:00:00Z"

    mock_dataset_class.jobs.return_value = [mock_job]

    result = service.get_jobs("ri.foundry.main.dataset.test-dataset", "master")

    assert len(result) == 1
    assert result[0]["job_rid"] == "ri.foundry.main.job.test"
    assert result[0]["name"] == "Test Job"
    assert result[0]["status"] == "SUCCEEDED"


def test_delete_branch_success(mock_dataset_service):
    """Test successful branch deletion."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Branch.delete method
    mock_dataset_class.Branch = Mock()
    mock_dataset_class.Branch.delete = Mock()

    result = service.delete_branch(
        "ri.foundry.main.dataset.test-dataset", "test-branch"
    )

    assert result["dataset_rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["branch_name"] == "test-branch"
    assert result["status"] == "deleted"
    assert result["success"] is True

    mock_dataset_class.Branch.delete.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test-dataset", branch_name="test-branch"
    )


def test_get_branch_success(mock_dataset_service):
    """Test successful branch retrieval."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Branch.get method
    mock_branch = Mock()
    mock_branch.transaction_rid = "ri.foundry.main.transaction.test"
    mock_branch.created_time = "2023-01-01T00:00:00Z"
    mock_branch.created_by = "test-user"

    mock_dataset_class.Branch = Mock()
    mock_dataset_class.Branch.get = Mock(return_value=mock_branch)

    result = service.get_branch("ri.foundry.main.dataset.test-dataset", "test-branch")

    assert result["name"] == "test-branch"
    assert result["dataset_rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["transaction_rid"] == "ri.foundry.main.transaction.test"
    assert result["created_by"] == "test-user"


def test_delete_file_success(mock_dataset_service):
    """Test successful file deletion."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the File.delete method
    mock_dataset_class.File = Mock()
    mock_dataset_class.File.delete = Mock()

    result = service.delete_file(
        "ri.foundry.main.dataset.test-dataset", "test-file.csv", "master"
    )

    assert result["dataset_rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["file_path"] == "test-file.csv"
    assert result["branch"] == "master"
    assert result["status"] == "deleted"
    assert result["success"] is True


def test_get_file_info_success(mock_dataset_service):
    """Test successful file info retrieval."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the File.get method
    mock_file = Mock()
    mock_file.size_bytes = 1024
    mock_file.last_modified = "2023-01-01T00:00:00Z"
    mock_file.transaction_rid = "ri.foundry.main.transaction.test"
    mock_file.created_time = "2023-01-01T00:00:00Z"
    mock_file.content_type = "text/csv"

    mock_dataset_class.File = Mock()
    mock_dataset_class.File.get = Mock(return_value=mock_file)

    result = service.get_file_info(
        "ri.foundry.main.dataset.test-dataset", "test-file.csv", "master"
    )

    assert result["path"] == "test-file.csv"
    assert result["dataset_rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["branch"] == "master"
    assert result["size_bytes"] == 1024
    assert result["content_type"] == "text/csv"


def test_get_transaction_build_success(mock_dataset_service):
    """Test successful transaction build retrieval."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Transaction.build method
    mock_build = Mock()
    mock_build.rid = "ri.foundry.main.build.test"
    mock_build.status = "SUCCEEDED"
    mock_build.started_time = "2023-01-01T00:00:00Z"
    mock_build.completed_time = "2023-01-01T01:00:00Z"
    mock_build.duration_ms = 3600000

    mock_transaction = Mock()
    mock_transaction.build = Mock(return_value=mock_build)
    mock_dataset_class.Transaction = mock_transaction

    result = service.get_transaction_build(
        "ri.foundry.main.dataset.test-dataset", "ri.foundry.main.transaction.test"
    )

    assert result["transaction_rid"] == "ri.foundry.main.transaction.test"
    assert result["dataset_rid"] == "ri.foundry.main.dataset.test-dataset"
    assert result["build_rid"] == "ri.foundry.main.build.test"
    assert result["status"] == "SUCCEEDED"
    assert result["duration_ms"] == 3600000


def test_get_view_success(mock_dataset_service):
    """Test successful view retrieval."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the View.get method
    mock_view = Mock()
    mock_view.name = "Test View"
    mock_view.description = "Test view description"
    mock_view.created_time = "2023-01-01T00:00:00Z"
    mock_view.created_by = "test-user"
    mock_view.backing_datasets = ["ri.foundry.main.dataset.backing"]
    mock_view.primary_key = ["id", "name"]

    mock_view_class = Mock()
    mock_view_class.get = Mock(return_value=mock_view)
    mock_dataset_class.View = mock_view_class

    result = service.get_view("ri.foundry.main.view.test", "master")

    assert result["view_rid"] == "ri.foundry.main.view.test"
    assert result["name"] == "Test View"
    assert result["description"] == "Test view description"
    assert result["branch"] == "master"
    assert result["backing_datasets"] == ["ri.foundry.main.dataset.backing"]
    assert result["primary_key"] == ["id", "name"]


def test_add_backing_datasets_success(mock_dataset_service):
    """Test successful addition of backing datasets to view."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the View.add_backing_datasets method
    mock_result = Mock()
    mock_view_class = Mock()
    mock_view_class.add_backing_datasets = Mock(return_value=mock_result)
    mock_dataset_class.View = mock_view_class

    dataset_rids = ["ri.foundry.main.dataset.new1", "ri.foundry.main.dataset.new2"]
    result = service.add_backing_datasets("ri.foundry.main.view.test", dataset_rids)

    assert result["view_rid"] == "ri.foundry.main.view.test"
    assert result["added_datasets"] == dataset_rids
    assert result["success"] is True

    mock_view_class.add_backing_datasets.assert_called_once_with(
        dataset_rid="ri.foundry.main.view.test", backing_datasets=dataset_rids
    )
