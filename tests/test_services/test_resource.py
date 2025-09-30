"""Tests for resource service."""

import pytest
from unittest.mock import Mock, patch

from pltr.services.resource import ResourceService


class TestResourceService:
    """Test cases for ResourceService."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.filesystem = Mock()
        client.filesystem.Resource = Mock()
        return client

    @pytest.fixture
    def mock_auth_manager(self, mock_client):
        """Create a mock auth manager."""
        with patch("pltr.services.base.AuthManager") as MockAuthManager:
            mock_auth_manager = Mock()
            mock_auth_manager.get_client.return_value = mock_client
            MockAuthManager.return_value = mock_auth_manager
            yield mock_auth_manager

    @pytest.fixture
    def resource_service(self, mock_auth_manager):
        """Create a ResourceService instance with mocked dependencies."""
        return ResourceService()

    def test_get_service(self, resource_service, mock_client):
        """Test _get_service returns filesystem service."""
        resource_service._client = mock_client
        assert resource_service._get_service() == mock_client.filesystem

    def test_get_resource(self, resource_service, mock_client):
        """Test getting a resource."""
        mock_resource = Mock()
        mock_resource.rid = "ri.compass.main.dataset.123"
        mock_resource.display_name = "Test Dataset"
        mock_resource.type = "dataset"

        mock_client.filesystem.Resource.get.return_value = mock_resource
        resource_service._client = mock_client

        result = resource_service.get_resource("ri.compass.main.dataset.123")

        mock_client.filesystem.Resource.get.assert_called_once_with(
            "ri.compass.main.dataset.123", preview=True
        )
        assert result["rid"] == "ri.compass.main.dataset.123"
        assert result["display_name"] == "Test Dataset"
        assert result["type"] == "dataset"

    def test_get_resource_failure(self, resource_service, mock_client):
        """Test handling resource get failure."""
        mock_client.filesystem.Resource.get.side_effect = Exception("Not found")
        resource_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to get resource ri.compass.main.dataset.123: Not found",
        ):
            resource_service.get_resource("ri.compass.main.dataset.123")

    def test_get_resource_by_path(self, resource_service, mock_client):
        """Test getting a resource by path."""
        mock_resource = Mock()
        mock_resource.rid = "ri.compass.main.dataset.123"
        mock_resource.display_name = "Test Dataset"
        mock_resource.type = "dataset"
        mock_resource.path = "/My Organization/Project/Test Dataset"

        mock_client.filesystem.Resource.get_by_path.return_value = mock_resource
        resource_service._client = mock_client

        result = resource_service.get_resource_by_path(
            "/My Organization/Project/Test Dataset"
        )

        mock_client.filesystem.Resource.get_by_path.assert_called_once_with(
            path="/My Organization/Project/Test Dataset", preview=True
        )
        assert result["rid"] == "ri.compass.main.dataset.123"
        assert result["display_name"] == "Test Dataset"
        assert result["type"] == "dataset"
        assert result["path"] == "/My Organization/Project/Test Dataset"

    def test_get_resource_by_path_failure(self, resource_service, mock_client):
        """Test handling resource get by path failure."""
        mock_client.filesystem.Resource.get_by_path.side_effect = Exception(
            "Path not found"
        )
        resource_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to get resource at path '/Invalid/Path': Path not found",
        ):
            resource_service.get_resource_by_path("/Invalid/Path")

    def test_list_resources(self, resource_service, mock_client):
        """Test listing resources."""
        mock_resources = [Mock(), Mock()]
        mock_resources[0].rid = "ri.compass.main.dataset.123"
        mock_resources[0].type = "dataset"
        mock_resources[1].rid = "ri.compass.main.folder.456"
        mock_resources[1].type = "folder"

        mock_client.filesystem.Resource.list.return_value = iter(mock_resources)
        resource_service._client = mock_client

        result = resource_service.list_resources()

        mock_client.filesystem.Resource.list.assert_called_once_with(preview=True)
        assert len(result) == 2
        assert result[0]["rid"] == "ri.compass.main.dataset.123"
        assert result[0]["type"] == "dataset"
        assert result[1]["rid"] == "ri.compass.main.folder.456"
        assert result[1]["type"] == "folder"

    def test_list_resources_with_filters(self, resource_service, mock_client):
        """Test listing resources with filters."""
        mock_resources = [Mock()]
        mock_resources[0].rid = "ri.compass.main.dataset.123"

        mock_client.filesystem.Resource.list.return_value = iter(mock_resources)
        resource_service._client = mock_client

        resource_service.list_resources(
            folder_rid="ri.compass.main.folder.789",
            resource_type="dataset",
            page_size=10,
            page_token="token123",
        )

        mock_client.filesystem.Resource.list.assert_called_once_with(
            preview=True,
            folder_rid="ri.compass.main.folder.789",
            resource_type="dataset",
            page_size=10,
            page_token="token123",
        )

    def test_get_resources_batch(self, resource_service, mock_client):
        """Test getting multiple resources in batch."""
        mock_response = Mock()
        mock_resources = [Mock(), Mock()]
        mock_resources[0].rid = "ri.compass.main.dataset.123"
        mock_resources[1].rid = "ri.compass.main.dataset.456"
        mock_response.resources = mock_resources

        mock_client.filesystem.Resource.get_batch.return_value = mock_response
        resource_service._client = mock_client

        rids = ["ri.compass.main.dataset.123", "ri.compass.main.dataset.456"]
        result = resource_service.get_resources_batch(rids)

        mock_client.filesystem.Resource.get_batch.assert_called_once_with(
            body=rids, preview=True
        )
        assert len(result) == 2
        assert result[0]["rid"] == "ri.compass.main.dataset.123"
        assert result[1]["rid"] == "ri.compass.main.dataset.456"

    def test_get_resources_batch_too_many(self, resource_service):
        """Test batch get with too many resources raises error."""
        rids = ["rid"] * 1001

        with pytest.raises(ValueError, match="Maximum batch size is 1000 resources"):
            resource_service.get_resources_batch(rids)

    def test_get_resource_metadata(self, resource_service, mock_client):
        """Test getting resource metadata."""
        mock_metadata = {"key1": "value1", "key2": "value2"}

        mock_client.filesystem.Resource.get_metadata.return_value = mock_metadata
        resource_service._client = mock_client

        result = resource_service.get_resource_metadata("ri.compass.main.dataset.123")

        mock_client.filesystem.Resource.get_metadata.assert_called_once_with(
            "ri.compass.main.dataset.123", preview=True
        )
        assert result == mock_metadata

    def test_set_resource_metadata(self, resource_service, mock_client):
        """Test setting resource metadata."""
        metadata_to_set = {"key1": "value1", "key2": "value2"}
        mock_updated_metadata = {"key1": "value1", "key2": "value2", "key3": "value3"}

        mock_client.filesystem.Resource.set_metadata.return_value = (
            mock_updated_metadata
        )
        resource_service._client = mock_client

        result = resource_service.set_resource_metadata(
            "ri.compass.main.dataset.123", metadata_to_set
        )

        mock_client.filesystem.Resource.set_metadata.assert_called_once_with(
            resource_rid="ri.compass.main.dataset.123",
            body=metadata_to_set,
            preview=True,
        )
        assert result == mock_updated_metadata

    def test_delete_resource_metadata(self, resource_service, mock_client):
        """Test deleting resource metadata."""
        resource_service._client = mock_client
        keys_to_delete = ["key1", "key2"]

        resource_service.delete_resource_metadata(
            "ri.compass.main.dataset.123", keys_to_delete
        )

        mock_client.filesystem.Resource.delete_metadata.assert_called_once_with(
            resource_rid="ri.compass.main.dataset.123",
            body={"keys": keys_to_delete},
            preview=True,
        )

    def test_move_resource(self, resource_service, mock_client):
        """Test moving a resource."""
        mock_resource = Mock()
        mock_resource.rid = "ri.compass.main.dataset.123"
        mock_resource.folder_rid = "ri.compass.main.folder.456"

        mock_client.filesystem.Resource.move.return_value = mock_resource
        resource_service._client = mock_client

        result = resource_service.move_resource(
            "ri.compass.main.dataset.123", "ri.compass.main.folder.456"
        )

        mock_client.filesystem.Resource.move.assert_called_once_with(
            resource_rid="ri.compass.main.dataset.123",
            body={"target_folder_rid": "ri.compass.main.folder.456"},
            preview=True,
        )
        assert result["rid"] == "ri.compass.main.dataset.123"
        assert result["folder_rid"] == "ri.compass.main.folder.456"

    def test_search_resources(self, resource_service, mock_client):
        """Test searching resources."""
        mock_resources = [Mock(), Mock()]
        mock_resources[0].rid = "ri.compass.main.dataset.123"
        mock_resources[0].display_name = "Sales Data"
        mock_resources[1].rid = "ri.compass.main.dataset.456"
        mock_resources[1].display_name = "Sales Report"

        mock_client.filesystem.Resource.search.return_value = iter(mock_resources)
        resource_service._client = mock_client

        result = resource_service.search_resources("sales")

        mock_client.filesystem.Resource.search.assert_called_once_with(
            query="sales", preview=True
        )
        assert len(result) == 2
        assert result[0]["display_name"] == "Sales Data"
        assert result[1]["display_name"] == "Sales Report"

    def test_search_resources_with_filters(self, resource_service, mock_client):
        """Test searching resources with filters."""
        mock_resources = [Mock()]
        mock_resources[0].rid = "ri.compass.main.dataset.123"

        mock_client.filesystem.Resource.search.return_value = iter(mock_resources)
        resource_service._client = mock_client

        resource_service.search_resources(
            query="sales",
            resource_type="dataset",
            folder_rid="ri.compass.main.folder.789",
            page_size=10,
            page_token="token123",
        )

        mock_client.filesystem.Resource.search.assert_called_once_with(
            query="sales",
            preview=True,
            resource_type="dataset",
            folder_rid="ri.compass.main.folder.789",
            page_size=10,
            page_token="token123",
        )

    def test_format_resource_info(self, resource_service):
        """Test formatting resource information."""
        mock_resource = Mock()
        mock_resource.rid = "ri.compass.main.dataset.123"
        mock_resource.display_name = "Test Dataset"
        mock_resource.name = "test_dataset"
        mock_resource.type = "dataset"
        mock_resource.folder_rid = "ri.compass.main.folder.456"
        mock_resource.created_by = "user123"
        mock_resource.created_time = Mock()
        mock_resource.created_time.time = "2023-01-01T00:00:00Z"
        mock_resource.size_bytes = 1024

        result = resource_service._format_resource_info(mock_resource)

        assert result["rid"] == "ri.compass.main.dataset.123"
        assert result["display_name"] == "Test Dataset"
        assert result["name"] == "test_dataset"
        assert result["type"] == "dataset"
        assert result["folder_rid"] == "ri.compass.main.folder.456"
        assert result["created_by"] == "user123"
        assert result["created_time"] == "2023-01-01T00:00:00Z"
        assert result["size_bytes"] == 1024

    def test_format_metadata_dict(self, resource_service):
        """Test formatting metadata as dict."""
        metadata = {"key1": "value1", "key2": "value2"}

        result = resource_service._format_metadata(metadata)

        assert result == metadata

    def test_format_metadata_object(self, resource_service):
        """Test formatting metadata object with __dict__."""
        metadata = Mock()
        metadata.__dict__ = {"key1": "value1", "key2": "value2"}

        result = resource_service._format_metadata(metadata)

        assert result == {"key1": "value1", "key2": "value2"}

    def test_format_metadata_other(self, resource_service):
        """Test formatting other metadata types."""
        metadata = "some string"

        result = resource_service._format_metadata(metadata)

        assert result == {"raw": "some string"}
