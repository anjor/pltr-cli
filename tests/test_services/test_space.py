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
        """Test creating a space with required parameters."""
        mock_space = Mock()
        mock_space.rid = "ri.compass.main.space.123"
        mock_space.display_name = "Test Space"
        mock_space.organization_rid = "ri.compass.main.organization.456"
        mock_space.root_folder_rid = "ri.compass.main.folder.789"

        mock_client.filesystem.Space.create.return_value = mock_space
        space_service._client = mock_client

        result = space_service.create_space(
            display_name="Test Space",
            enrollment_rid="ri.enrollment.main.enrollment.456",
            organizations=["ri.compass.main.organization.456"],
            deletion_policy_organizations=["ri.compass.main.organization.456"],
        )

        mock_client.filesystem.Space.create.assert_called_once_with(
            display_name="Test Space",
            enrollment_rid="ri.enrollment.main.enrollment.456",
            organizations=["ri.compass.main.organization.456"],
            deletion_policy_organizations=["ri.compass.main.organization.456"],
            description=None,
            default_roles=[],
            role_grants=[],
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
            enrollment_rid="ri.enrollment.main.enrollment.456",
            organizations=["ri.compass.main.organization.456"],
            deletion_policy_organizations=["ri.compass.main.organization.456"],
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

        mock_client.filesystem.Space.create.assert_called_once_with(
            display_name="Test Space",
            enrollment_rid="ri.enrollment.main.enrollment.456",
            organizations=["ri.compass.main.organization.456"],
            deletion_policy_organizations=["ri.compass.main.organization.456"],
            description="Test description",
            default_roles=["viewer"],
            role_grants=[
                {
                    "principal_id": "user1",
                    "principal_type": "User",
                    "role_name": "owner",
                }
            ],
            preview=True,
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
                enrollment_rid="ri.enrollment.main.enrollment.456",
                organizations=["ri.compass.main.organization.456"],
                deletion_policy_organizations=["ri.compass.main.organization.456"],
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

        mock_client.filesystem.Space.replace.return_value = mock_space
        space_service._client = mock_client

        result = space_service.update_space(
            space_rid="ri.compass.main.space.123",
            display_name="Updated Space",
            description="Updated description",
        )

        mock_client.filesystem.Space.replace.assert_called_once_with(
            space_rid="ri.compass.main.space.123",
            display_name="Updated Space",
            description="Updated description",
            preview=True,
        )
        assert result["display_name"] == "Updated Space"

    def test_update_space_without_display_name(self, space_service, mock_client):
        """Test updating a space when display_name not provided - fetches current."""
        mock_current_space = Mock()
        mock_current_space.display_name = "Current Name"

        mock_updated_space = Mock()
        mock_updated_space.rid = "ri.compass.main.space.123"
        mock_updated_space.display_name = "Current Name"
        mock_updated_space.description = "New description"

        mock_client.filesystem.Space.get.return_value = mock_current_space
        mock_client.filesystem.Space.replace.return_value = mock_updated_space
        space_service._client = mock_client

        result = space_service.update_space(
            space_rid="ri.compass.main.space.123",
            description="New description",
        )

        mock_client.filesystem.Space.get.assert_called_once_with(
            "ri.compass.main.space.123", preview=True
        )
        mock_client.filesystem.Space.replace.assert_called_once_with(
            space_rid="ri.compass.main.space.123",
            display_name="Current Name",
            description="New description",
            preview=True,
        )
        assert result["display_name"] == "Current Name"

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
