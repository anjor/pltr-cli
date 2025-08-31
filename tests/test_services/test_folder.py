"""
Tests for folder service.
"""

import pytest
from unittest.mock import Mock, patch

from pltr.services.folder import FolderService


@pytest.fixture
def mock_folder_service():
    """Create a mock folder service with mocked client."""
    with patch("pltr.services.base.AuthManager") as MockAuthManager:
        mock_client = Mock()
        mock_filesystem = Mock()
        mock_folder_class = Mock()

        mock_client.filesystem = mock_filesystem
        mock_filesystem.Folder = mock_folder_class

        MockAuthManager.return_value.get_client.return_value = mock_client

        service = FolderService()
        return service, mock_folder_class


@pytest.fixture
def sample_folder():
    """Create a sample folder object."""
    folder = Mock()
    folder.rid = "ri.compass.main.folder.test-folder"
    folder.display_name = "Test Folder"
    folder.description = "Test folder description"
    folder.parent_folder_rid = "ri.compass.main.folder.parent"

    # Mock timestamp
    created = Mock()
    created.time = "2024-01-01T00:00:00Z"
    folder.created = created

    modified = Mock()
    modified.time = "2024-01-02T00:00:00Z"
    folder.modified = modified

    return folder


@pytest.fixture
def sample_children():
    """Create sample child resources."""
    folder_child = Mock()
    folder_child.rid = "ri.compass.main.folder.child-folder"
    folder_child.display_name = "Child Folder"
    folder_child.type = "folder"
    folder_child.description = "A child folder"

    dataset_child = Mock()
    dataset_child.rid = "ri.foundry.main.dataset.child-dataset"
    dataset_child.display_name = "Child Dataset"
    dataset_child.type = "dataset"
    dataset_child.name = "Child Dataset"

    return [folder_child, dataset_child]


def test_create_folder(mock_folder_service, sample_folder):
    """Test folder creation."""
    service, mock_folder_class = mock_folder_service
    mock_folder_class.create.return_value = sample_folder

    result = service.create_folder(
        display_name="Test Folder", parent_folder_rid="ri.compass.main.folder.parent"
    )

    assert result["rid"] == "ri.compass.main.folder.test-folder"
    assert result["display_name"] == "Test Folder"
    assert result["description"] == "Test folder description"
    assert result["parent_folder_rid"] == "ri.compass.main.folder.parent"
    assert result["created"] == "2024-01-01T00:00:00Z"
    assert result["modified"] == "2024-01-02T00:00:00Z"
    assert result["type"] == "folder"

    mock_folder_class.create.assert_called_once_with(
        display_name="Test Folder",
        parent_folder_rid="ri.compass.main.folder.parent",
        preview=True,
    )


def test_get_folder(mock_folder_service, sample_folder):
    """Test getting folder information."""
    service, mock_folder_class = mock_folder_service
    mock_folder_class.get.return_value = sample_folder

    result = service.get_folder("ri.compass.main.folder.test-folder")

    assert result["rid"] == "ri.compass.main.folder.test-folder"
    assert result["display_name"] == "Test Folder"
    assert result["description"] == "Test folder description"

    mock_folder_class.get.assert_called_once_with(
        "ri.compass.main.folder.test-folder", preview=True
    )


def test_list_children(mock_folder_service, sample_children):
    """Test listing folder children."""
    service, mock_folder_class = mock_folder_service

    # Mock the children method to return an iterator
    mock_folder_class.children.return_value = iter(sample_children)

    result = service.list_children("ri.compass.main.folder.parent")

    assert len(result) == 2

    # Check folder child
    assert result[0]["rid"] == "ri.compass.main.folder.child-folder"
    assert result[0]["display_name"] == "Child Folder"
    assert result[0]["type"] == "folder"
    assert result[0]["description"] == "A child folder"

    # Check dataset child
    assert result[1]["rid"] == "ri.foundry.main.dataset.child-dataset"
    assert result[1]["display_name"] == "Child Dataset"
    assert result[1]["type"] == "dataset"
    assert result[1]["name"] == "Child Dataset"

    mock_folder_class.children.assert_called_once_with(
        "ri.compass.main.folder.parent", page_size=None, page_token=None, preview=True
    )


def test_list_children_with_pagination(mock_folder_service, sample_children):
    """Test listing folder children with pagination."""
    service, mock_folder_class = mock_folder_service
    mock_folder_class.children.return_value = iter(sample_children)

    result = service.list_children(
        "ri.compass.main.folder.parent", page_size=10, page_token="next-page-token"
    )

    assert len(result) == 2

    mock_folder_class.children.assert_called_once_with(
        "ri.compass.main.folder.parent",
        page_size=10,
        page_token="next-page-token",
        preview=True,
    )


def test_get_folders_batch(mock_folder_service, sample_folder):
    """Test getting multiple folders in batch."""
    service, mock_folder_class = mock_folder_service

    # Create response mock
    response = Mock()
    response.folders = [sample_folder, sample_folder]
    mock_folder_class.get_batch.return_value = response

    folder_rids = ["ri.compass.main.folder.folder1", "ri.compass.main.folder.folder2"]

    result = service.get_folders_batch(folder_rids)

    assert len(result) == 2
    assert result[0]["rid"] == "ri.compass.main.folder.test-folder"
    assert result[1]["rid"] == "ri.compass.main.folder.test-folder"

    mock_folder_class.get_batch.assert_called_once_with(body=folder_rids, preview=True)


def test_get_folders_batch_exceeds_limit(mock_folder_service):
    """Test batch request with too many folders."""
    service, _ = mock_folder_service

    # Create list with more than 1000 RIDs
    folder_rids = [f"ri.compass.main.folder.folder{i}" for i in range(1001)]

    with pytest.raises(ValueError, match="Maximum batch size is 1000 folders"):
        service.get_folders_batch(folder_rids)


def test_create_folder_error(mock_folder_service):
    """Test folder creation error handling."""
    service, mock_folder_class = mock_folder_service
    mock_folder_class.create.side_effect = Exception("API error")

    with pytest.raises(
        RuntimeError, match="Failed to create folder 'Test Folder': API error"
    ):
        service.create_folder("Test Folder", "ri.compass.main.folder.parent")


def test_get_folder_error(mock_folder_service):
    """Test get folder error handling."""
    service, mock_folder_class = mock_folder_service
    mock_folder_class.get.side_effect = Exception("Not found")

    with pytest.raises(RuntimeError, match="Failed to get folder .* Not found"):
        service.get_folder("ri.compass.main.folder.nonexistent")


def test_list_children_error(mock_folder_service):
    """Test list children error handling."""
    service, mock_folder_class = mock_folder_service
    mock_folder_class.children.side_effect = Exception("Permission denied")

    with pytest.raises(
        RuntimeError, match="Failed to list children .* Permission denied"
    ):
        service.list_children("ri.compass.main.folder.restricted")


def test_format_timestamp_none(mock_folder_service):
    """Test timestamp formatting with None value."""
    service, _ = mock_folder_service
    result = service._format_timestamp(None)
    assert result is None


def test_format_timestamp_with_time_attr(mock_folder_service):
    """Test timestamp formatting with time attribute."""
    service, _ = mock_folder_service
    timestamp = Mock()
    timestamp.time = "2024-01-01T00:00:00Z"
    result = service._format_timestamp(timestamp)
    assert result == "2024-01-01T00:00:00Z"


def test_format_timestamp_without_time_attr(mock_folder_service):
    """Test timestamp formatting without time attribute."""
    service, _ = mock_folder_service
    timestamp = "2024-01-01T00:00:00Z"
    result = service._format_timestamp(timestamp)
    assert result == "2024-01-01T00:00:00Z"


def test_format_folder_info_minimal(mock_folder_service):
    """Test formatting folder info with minimal attributes."""
    service, _ = mock_folder_service

    folder = Mock()
    folder.rid = "ri.compass.main.folder.minimal"
    folder.display_name = "Minimal Folder"

    # Set other attributes to not exist
    del folder.description
    del folder.created
    del folder.modified
    del folder.parent_folder_rid

    result = service._format_folder_info(folder)

    assert result["rid"] == "ri.compass.main.folder.minimal"
    assert result["display_name"] == "Minimal Folder"
    assert result["description"] is None
    assert result["created"] is None
    assert result["modified"] is None
    assert result["parent_folder_rid"] is None
    assert result["type"] == "folder"
