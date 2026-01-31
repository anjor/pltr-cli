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

        # Verify the call was made with GetResourcesBatchRequestElement objects
        call_args = mock_client.filesystem.Resource.get_batch.call_args
        assert call_args.kwargs["preview"] is True
        elements = call_args.kwargs["body"]
        assert len(elements) == 2
        assert elements[0].resource_rid == "ri.compass.main.dataset.123"
        assert elements[1].resource_rid == "ri.compass.main.dataset.456"

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

    # ==================== Trash Operations Tests ====================

    def test_delete_resource(self, resource_service, mock_client):
        """Test moving resource to trash."""
        mock_client.filesystem.Resource.delete.return_value = None
        resource_service._client = mock_client

        resource_service.delete_resource("ri.compass.main.dataset.123")

        mock_client.filesystem.Resource.delete.assert_called_once_with(
            "ri.compass.main.dataset.123", preview=True
        )

    def test_delete_resource_failure(self, resource_service, mock_client):
        """Test handling delete resource failure."""
        mock_client.filesystem.Resource.delete.side_effect = Exception("Delete failed")
        resource_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to delete resource ri.compass.main.dataset.123: Delete failed",
        ):
            resource_service.delete_resource("ri.compass.main.dataset.123")

    def test_restore_resource(self, resource_service, mock_client):
        """Test restoring resource from trash."""
        mock_client.filesystem.Resource.restore.return_value = None
        resource_service._client = mock_client

        resource_service.restore_resource("ri.compass.main.dataset.123")

        mock_client.filesystem.Resource.restore.assert_called_once_with(
            "ri.compass.main.dataset.123", preview=True
        )

    def test_restore_resource_failure(self, resource_service, mock_client):
        """Test handling restore resource failure."""
        mock_client.filesystem.Resource.restore.side_effect = Exception(
            "Restore failed"
        )
        resource_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to restore resource ri.compass.main.dataset.123: Restore failed",
        ):
            resource_service.restore_resource("ri.compass.main.dataset.123")

    def test_permanently_delete_resource(self, resource_service, mock_client):
        """Test permanently deleting resource from trash."""
        mock_client.filesystem.Resource.permanently_delete.return_value = None
        resource_service._client = mock_client

        resource_service.permanently_delete_resource("ri.compass.main.dataset.123")

        mock_client.filesystem.Resource.permanently_delete.assert_called_once_with(
            "ri.compass.main.dataset.123", preview=True
        )

    def test_permanently_delete_resource_failure(self, resource_service, mock_client):
        """Test handling permanently delete resource failure."""
        mock_client.filesystem.Resource.permanently_delete.side_effect = Exception(
            "Not in trash"
        )
        resource_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to permanently delete resource ri.compass.main.dataset.123: Not in trash",
        ):
            resource_service.permanently_delete_resource("ri.compass.main.dataset.123")

    # ==================== Markings Operations Tests ====================

    def test_add_markings(self, resource_service, mock_client):
        """Test adding markings to a resource."""
        mock_client.filesystem.Resource.add_markings.return_value = None
        resource_service._client = mock_client

        marking_ids = ["marking-1", "marking-2"]
        resource_service.add_markings("ri.compass.main.dataset.123", marking_ids)

        mock_client.filesystem.Resource.add_markings.assert_called_once_with(
            "ri.compass.main.dataset.123", marking_ids=marking_ids, preview=True
        )

    def test_add_markings_failure(self, resource_service, mock_client):
        """Test handling add markings failure."""
        mock_client.filesystem.Resource.add_markings.side_effect = Exception(
            "Invalid marking"
        )
        resource_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to add markings to resource ri.compass.main.dataset.123: Invalid marking",
        ):
            resource_service.add_markings("ri.compass.main.dataset.123", ["marking-1"])

    def test_remove_markings(self, resource_service, mock_client):
        """Test removing markings from a resource."""
        mock_client.filesystem.Resource.remove_markings.return_value = None
        resource_service._client = mock_client

        marking_ids = ["marking-1", "marking-2"]
        resource_service.remove_markings("ri.compass.main.dataset.123", marking_ids)

        mock_client.filesystem.Resource.remove_markings.assert_called_once_with(
            "ri.compass.main.dataset.123", marking_ids=marking_ids, preview=True
        )

    def test_remove_markings_failure(self, resource_service, mock_client):
        """Test handling remove markings failure."""
        mock_client.filesystem.Resource.remove_markings.side_effect = Exception(
            "Marking not found"
        )
        resource_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to remove markings from resource ri.compass.main.dataset.123: Marking not found",
        ):
            resource_service.remove_markings(
                "ri.compass.main.dataset.123", ["marking-1"]
            )

    def test_list_markings(self, resource_service, mock_client):
        """Test listing markings on a resource."""
        mock_markings = [Mock(), Mock()]
        mock_markings[0].marking_id = "marking-1"
        mock_markings[0].display_name = "Confidential"
        mock_markings[1].marking_id = "marking-2"
        mock_markings[1].display_name = "Internal"

        mock_client.filesystem.Resource.markings.return_value = iter(mock_markings)
        resource_service._client = mock_client

        result = resource_service.list_markings("ri.compass.main.dataset.123")

        mock_client.filesystem.Resource.markings.assert_called_once_with(
            "ri.compass.main.dataset.123", preview=True
        )
        assert len(result) == 2
        assert result[0]["marking_id"] == "marking-1"
        assert result[0]["display_name"] == "Confidential"
        assert result[1]["marking_id"] == "marking-2"
        assert result[1]["display_name"] == "Internal"

    def test_list_markings_with_pagination(self, resource_service, mock_client):
        """Test listing markings with pagination."""
        mock_markings = [Mock()]
        mock_markings[0].marking_id = "marking-1"

        mock_client.filesystem.Resource.markings.return_value = iter(mock_markings)
        resource_service._client = mock_client

        resource_service.list_markings(
            "ri.compass.main.dataset.123", page_size=10, page_token="token123"
        )

        mock_client.filesystem.Resource.markings.assert_called_once_with(
            "ri.compass.main.dataset.123",
            preview=True,
            page_size=10,
            page_token="token123",
        )

    # ==================== Access & Batch Operations Tests ====================

    def test_get_access_requirements(self, resource_service, mock_client):
        """Test getting access requirements for a resource."""
        mock_requirements = Mock()
        mock_org = Mock()
        mock_org.organization_rid = "org-1"
        mock_org.display_name = "My Org"
        mock_marking = Mock()
        mock_marking.marking_id = "marking-1"
        mock_marking.display_name = "Confidential"
        mock_requirements.organizations = [mock_org]
        mock_requirements.markings = [mock_marking]

        mock_client.filesystem.Resource.get_access_requirements.return_value = (
            mock_requirements
        )
        resource_service._client = mock_client

        result = resource_service.get_access_requirements("ri.compass.main.dataset.123")

        mock_client.filesystem.Resource.get_access_requirements.assert_called_once_with(
            "ri.compass.main.dataset.123", preview=True
        )
        assert len(result["organizations"]) == 1
        assert result["organizations"][0]["organization_rid"] == "org-1"
        assert result["organizations"][0]["display_name"] == "My Org"
        assert len(result["markings"]) == 1
        assert result["markings"][0]["marking_id"] == "marking-1"

    def test_get_access_requirements_failure(self, resource_service, mock_client):
        """Test handling get access requirements failure."""
        mock_client.filesystem.Resource.get_access_requirements.side_effect = Exception(
            "Access denied"
        )
        resource_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to get access requirements for resource ri.compass.main.dataset.123: Access denied",
        ):
            resource_service.get_access_requirements("ri.compass.main.dataset.123")

    def test_get_resources_by_path_batch(self, resource_service, mock_client):
        """Test getting multiple resources by paths in batch."""
        mock_response = Mock()
        mock_resources = [Mock(), Mock()]
        mock_resources[0].rid = "ri.compass.main.dataset.123"
        mock_resources[0].path = "/Org/Project/Dataset1"
        mock_resources[1].rid = "ri.compass.main.dataset.456"
        mock_resources[1].path = "/Org/Project/Dataset2"
        mock_response.resources = mock_resources

        mock_client.filesystem.Resource.get_by_path_batch.return_value = mock_response
        resource_service._client = mock_client

        paths = ["/Org/Project/Dataset1", "/Org/Project/Dataset2"]
        result = resource_service.get_resources_by_path_batch(paths)

        # Verify the call was made with GetByPathResourcesBatchRequestElement objects
        call_args = mock_client.filesystem.Resource.get_by_path_batch.call_args
        assert call_args.kwargs["preview"] is True
        elements = call_args.kwargs["body"]
        assert len(elements) == 2
        assert elements[0].path == "/Org/Project/Dataset1"
        assert elements[1].path == "/Org/Project/Dataset2"

        assert len(result) == 2
        assert result[0]["rid"] == "ri.compass.main.dataset.123"
        assert result[1]["rid"] == "ri.compass.main.dataset.456"

    def test_get_resources_by_path_batch_too_many(self, resource_service):
        """Test batch get by path with too many paths raises error."""
        paths = ["/path"] * 1001

        with pytest.raises(ValueError, match="Maximum batch size is 1000 paths"):
            resource_service.get_resources_by_path_batch(paths)

    def test_get_resources_by_path_batch_failure(self, resource_service, mock_client):
        """Test handling batch get by path failure."""
        mock_client.filesystem.Resource.get_by_path_batch.side_effect = Exception(
            "Invalid paths"
        )
        resource_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to get resources by path batch: Invalid paths",
        ):
            resource_service.get_resources_by_path_batch(["/Org/Project/Dataset1"])

    # ==================== Formatting Tests ====================

    def test_format_marking_info(self, resource_service):
        """Test formatting marking information."""
        mock_marking = Mock()
        mock_marking.marking_id = "marking-1"
        mock_marking.display_name = "Confidential"
        mock_marking.description = "Confidential data"
        mock_marking.category_id = "cat-1"
        mock_marking.category_display_name = "Security"

        result = resource_service._format_marking_info(mock_marking)

        assert result["marking_id"] == "marking-1"
        assert result["display_name"] == "Confidential"
        assert result["description"] == "Confidential data"
        assert result["category_id"] == "cat-1"
        assert result["category_display_name"] == "Security"

    def test_format_access_requirements(self, resource_service):
        """Test formatting access requirements."""
        mock_requirements = Mock()
        mock_org = Mock()
        mock_org.organization_rid = "org-1"
        mock_org.display_name = "My Org"
        mock_marking = Mock()
        mock_marking.marking_id = "marking-1"
        mock_marking.display_name = "Confidential"
        mock_requirements.organizations = [mock_org]
        mock_requirements.markings = [mock_marking]

        result = resource_service._format_access_requirements(mock_requirements)

        assert len(result["organizations"]) == 1
        assert result["organizations"][0]["organization_rid"] == "org-1"
        assert len(result["markings"]) == 1
        assert result["markings"][0]["marking_id"] == "marking-1"

    def test_format_access_requirements_empty(self, resource_service):
        """Test formatting access requirements with no orgs or markings."""
        mock_requirements = Mock()
        mock_requirements.organizations = None
        mock_requirements.markings = None

        result = resource_service._format_access_requirements(mock_requirements)

        assert result["organizations"] == []
        assert result["markings"] == []
