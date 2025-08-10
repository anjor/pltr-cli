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
