"""Tests for space service."""

import pytest
from unittest.mock import Mock, patch

from pltr.services.space import SpaceService


class TestSpaceService:
    """Test cases for SpaceService."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.filesystem = Mock()
        client.filesystem.Space = Mock()
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
    def space_service(self, mock_auth_manager):
        """Create a SpaceService instance with mocked dependencies."""
        return SpaceService()

    def test_get_service(self, space_service, mock_client):
        """Test _get_service returns filesystem service."""
        space_service._client = mock_client
        assert space_service._get_service() == mock_client.filesystem

    def test_create_space_basic(self, space_service, mock_client):
        """Test creating a space with basic parameters."""
        mock_space = Mock()
        mock_space.rid = "ri.compass.main.space.123"
        mock_space.display_name = "Test Space"
        mock_space.organization_rid = "ri.compass.main.organization.456"
        mock_space.root_folder_rid = "ri.compass.main.folder.789"

        mock_client.filesystem.Space.create.return_value = mock_space
        space_service._client = mock_client

        result = space_service.create_space(
            display_name="Test Space",
            organization_rid="ri.compass.main.organization.456",
        )

        mock_client.filesystem.Space.create.assert_called_once_with(
            body={
                "display_name": "Test Space",
                "organization_rid": "ri.compass.main.organization.456",
            },
            preview=True,
        )

        assert result["rid"] == "ri.compass.main.space.123"
        assert result["display_name"] == "Test Space"
        assert result["organization_rid"] == "ri.compass.main.organization.456"
        assert result["root_folder_rid"] == "ri.compass.main.folder.789"

    def test_create_space_with_all_params(self, space_service, mock_client):
        """Test creating a space with all optional parameters."""
        mock_space = Mock()
        mock_space.rid = "ri.compass.main.space.123"

        mock_client.filesystem.Space.create.return_value = mock_space
        space_service._client = mock_client

        space_service.create_space(
            display_name="Test Space",
            organization_rid="ri.compass.main.organization.456",
            description="Test description",
            default_roles=["viewer"],
            role_grants=[
                {
                    "principal_id": "user1",
                    "principal_type": "User",
                    "role_name": "owner",
                }
            ],
        )

        expected_body = {
            "display_name": "Test Space",
            "organization_rid": "ri.compass.main.organization.456",
            "description": "Test description",
            "default_roles": ["viewer"],
            "role_grants": [
                {
                    "principal_id": "user1",
                    "principal_type": "User",
                    "role_name": "owner",
                }
            ],
        }

        mock_client.filesystem.Space.create.assert_called_once_with(
            body=expected_body, preview=True
        )

    def test_create_space_failure(self, space_service, mock_client):
        """Test handling space creation failure."""
        mock_client.filesystem.Space.create.side_effect = Exception("Creation failed")
        space_service._client = mock_client

        with pytest.raises(
            RuntimeError, match="Failed to create space 'Test Space': Creation failed"
        ):
            space_service.create_space(
                display_name="Test Space",
                organization_rid="ri.compass.main.organization.456",
            )

    def test_get_space(self, space_service, mock_client):
        """Test getting a space."""
        mock_space = Mock()
        mock_space.rid = "ri.compass.main.space.123"
        mock_space.display_name = "Test Space"

        mock_client.filesystem.Space.get.return_value = mock_space
        space_service._client = mock_client

        result = space_service.get_space("ri.compass.main.space.123")

        mock_client.filesystem.Space.get.assert_called_once_with(
            "ri.compass.main.space.123", preview=True
        )
        assert result["rid"] == "ri.compass.main.space.123"
        assert result["display_name"] == "Test Space"

    def test_get_space_failure(self, space_service, mock_client):
        """Test handling space get failure."""
        mock_client.filesystem.Space.get.side_effect = Exception("Not found")
        space_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to get space ri.compass.main.space.123: Not found",
        ):
            space_service.get_space("ri.compass.main.space.123")

    def test_list_spaces(self, space_service, mock_client):
        """Test listing spaces."""
        mock_spaces = [Mock(), Mock()]
        mock_spaces[0].rid = "ri.compass.main.space.123"
        mock_spaces[1].rid = "ri.compass.main.space.456"

        mock_client.filesystem.Space.list.return_value = iter(mock_spaces)
        space_service._client = mock_client

        result = space_service.list_spaces()

        mock_client.filesystem.Space.list.assert_called_once_with(preview=True)
        assert len(result) == 2
        assert result[0]["rid"] == "ri.compass.main.space.123"
        assert result[1]["rid"] == "ri.compass.main.space.456"

    def test_list_spaces_with_filters(self, space_service, mock_client):
        """Test listing spaces with filters."""
        mock_spaces = [Mock()]
        mock_spaces[0].rid = "ri.compass.main.space.123"

        mock_client.filesystem.Space.list.return_value = iter(mock_spaces)
        space_service._client = mock_client

        space_service.list_spaces(
            organization_rid="ri.compass.main.organization.789",
            page_size=10,
            page_token="token123",
        )

        mock_client.filesystem.Space.list.assert_called_once_with(
            preview=True,
            organization_rid="ri.compass.main.organization.789",
            page_size=10,
            page_token="token123",
        )

    def test_update_space(self, space_service, mock_client):
        """Test updating a space."""
        mock_space = Mock()
        mock_space.rid = "ri.compass.main.space.123"
        mock_space.display_name = "Updated Space"

        mock_client.filesystem.Space.update.return_value = mock_space
        space_service._client = mock_client

        result = space_service.update_space(
            space_rid="ri.compass.main.space.123",
            display_name="Updated Space",
            description="Updated description",
        )

        mock_client.filesystem.Space.update.assert_called_once_with(
            space_rid="ri.compass.main.space.123",
            body={
                "display_name": "Updated Space",
                "description": "Updated description",
            },
            preview=True,
        )
        assert result["display_name"] == "Updated Space"

    def test_update_space_no_fields(self, space_service):
        """Test update space with no fields raises error."""
        with pytest.raises(
            ValueError, match="At least one field must be provided for update"
        ):
            space_service.update_space("ri.compass.main.space.123")

    def test_delete_space(self, space_service, mock_client):
        """Test deleting a space."""
        space_service._client = mock_client

        space_service.delete_space("ri.compass.main.space.123")

        mock_client.filesystem.Space.delete.assert_called_once_with(
            "ri.compass.main.space.123", preview=True
        )

    def test_delete_space_failure(self, space_service, mock_client):
        """Test handling space deletion failure."""
        mock_client.filesystem.Space.delete.side_effect = Exception("Deletion failed")
        space_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to delete space ri.compass.main.space.123: Deletion failed",
        ):
            space_service.delete_space("ri.compass.main.space.123")

    def test_get_spaces_batch(self, space_service, mock_client):
        """Test getting multiple spaces in batch."""
        mock_response = Mock()
        mock_spaces = [Mock(), Mock()]
        mock_spaces[0].rid = "ri.compass.main.space.123"
        mock_spaces[1].rid = "ri.compass.main.space.456"
        mock_response.spaces = mock_spaces

        mock_client.filesystem.Space.get_batch.return_value = mock_response
        space_service._client = mock_client

        rids = ["ri.compass.main.space.123", "ri.compass.main.space.456"]
        result = space_service.get_spaces_batch(rids)

        mock_client.filesystem.Space.get_batch.assert_called_once_with(
            body=rids, preview=True
        )
        assert len(result) == 2
        assert result[0]["rid"] == "ri.compass.main.space.123"
        assert result[1]["rid"] == "ri.compass.main.space.456"

    def test_get_spaces_batch_too_many(self, space_service):
        """Test batch get with too many spaces raises error."""
        rids = ["rid"] * 1001

        with pytest.raises(ValueError, match="Maximum batch size is 1000 spaces"):
            space_service.get_spaces_batch(rids)

    def test_get_space_members(self, space_service, mock_client):
        """Test getting space members."""
        mock_members = [Mock(), Mock()]
        mock_members[0].space_rid = "ri.compass.main.space.123"
        mock_members[0].principal_id = "user123"
        mock_members[0].principal_type = "User"
        mock_members[0].role_name = "viewer"
        mock_members[1].space_rid = "ri.compass.main.space.123"
        mock_members[1].principal_id = "group456"
        mock_members[1].principal_type = "Group"
        mock_members[1].role_name = "editor"

        mock_client.filesystem.Space.get_members.return_value = iter(mock_members)
        space_service._client = mock_client

        result = space_service.get_space_members("ri.compass.main.space.123")

        mock_client.filesystem.Space.get_members.assert_called_once_with(
            "ri.compass.main.space.123", preview=True
        )
        assert len(result) == 2
        assert result[0]["principal_id"] == "user123"
        assert result[0]["role_name"] == "viewer"
        assert result[1]["principal_id"] == "group456"
        assert result[1]["role_name"] == "editor"

    def test_add_space_member(self, space_service, mock_client):
        """Test adding a space member."""
        mock_member = Mock()
        mock_member.space_rid = "ri.compass.main.space.123"
        mock_member.principal_id = "user123"
        mock_member.principal_type = "User"
        mock_member.role_name = "viewer"

        mock_client.filesystem.Space.add_member.return_value = mock_member
        space_service._client = mock_client

        result = space_service.add_space_member(
            space_rid="ri.compass.main.space.123",
            principal_id="user123",
            principal_type="User",
            role_name="viewer",
        )

        expected_member_request = {
            "principal_id": "user123",
            "principal_type": "User",
            "role_name": "viewer",
        }

        mock_client.filesystem.Space.add_member.assert_called_once_with(
            space_rid="ri.compass.main.space.123",
            body=expected_member_request,
            preview=True,
        )

        assert result["space_rid"] == "ri.compass.main.space.123"
        assert result["principal_id"] == "user123"
        assert result["principal_type"] == "User"
        assert result["role_name"] == "viewer"

    def test_remove_space_member(self, space_service, mock_client):
        """Test removing a space member."""
        space_service._client = mock_client

        space_service.remove_space_member(
            space_rid="ri.compass.main.space.123",
            principal_id="user123",
            principal_type="User",
        )

        expected_member_removal = {
            "principal_id": "user123",
            "principal_type": "User",
        }

        mock_client.filesystem.Space.remove_member.assert_called_once_with(
            space_rid="ri.compass.main.space.123",
            body=expected_member_removal,
            preview=True,
        )

    def test_format_space_info(self, space_service):
        """Test formatting space information."""
        mock_space = Mock()
        mock_space.rid = "ri.compass.main.space.123"
        mock_space.display_name = "Test Space"
        mock_space.description = "Test description"
        mock_space.organization_rid = "ri.compass.main.organization.456"
        mock_space.root_folder_rid = "ri.compass.main.folder.789"
        mock_space.created_by = "user123"
        mock_space.created_time = Mock()
        mock_space.created_time.time = "2023-01-01T00:00:00Z"

        result = space_service._format_space_info(mock_space)

        assert result["rid"] == "ri.compass.main.space.123"
        assert result["display_name"] == "Test Space"
        assert result["description"] == "Test description"
        assert result["organization_rid"] == "ri.compass.main.organization.456"
        assert result["root_folder_rid"] == "ri.compass.main.folder.789"
        assert result["created_by"] == "user123"
        assert result["created_time"] == "2023-01-01T00:00:00Z"
        assert result["type"] == "space"

    def test_format_member_info(self, space_service):
        """Test formatting space member information."""
        mock_member = Mock()
        mock_member.space_rid = "ri.compass.main.space.123"
        mock_member.principal_id = "user123"
        mock_member.principal_type = "User"
        mock_member.role_name = "viewer"
        mock_member.added_by = "admin"
        mock_member.added_time = Mock()
        mock_member.added_time.time = "2023-01-01T00:00:00Z"

        result = space_service._format_member_info(mock_member)

        assert result["space_rid"] == "ri.compass.main.space.123"
        assert result["principal_id"] == "user123"
        assert result["principal_type"] == "User"
        assert result["role_name"] == "viewer"
        assert result["added_by"] == "admin"
        assert result["added_time"] == "2023-01-01T00:00:00Z"
