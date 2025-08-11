"""
Tests for Admin service.
"""

import pytest
from unittest.mock import Mock

from pltr.services.admin import AdminService


class TestAdminService:
    """Test Admin service functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.admin = Mock()
        client.admin.User = Mock()
        client.admin.Group = Mock()
        client.admin.Role = Mock()
        client.admin.Organization = Mock()
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create AdminService with mocked client."""
        service = AdminService()
        service._client = mock_client
        return service

    # User Management Tests
    def test_list_users(self, service, mock_client):
        """Test listing all users."""
        # Setup
        mock_response = Mock()
        mock_response.dict.return_value = {
            "users": [
                {"id": "user1", "username": "john.doe", "email": "john@example.com"},
                {"id": "user2", "username": "jane.doe", "email": "jane@example.com"},
            ],
            "nextPageToken": None,
        }
        mock_client.admin.User.list.return_value = mock_response

        # Execute
        result = service.list_users()

        # Assert
        mock_client.admin.User.list.assert_called_once_with(
            page_size=None, page_token=None
        )
        assert "users" in result
        assert len(result["users"]) == 2

    def test_list_users_with_pagination(self, service, mock_client):
        """Test listing users with pagination."""
        # Setup
        mock_response = Mock()
        mock_response.dict.return_value = {
            "users": [{"id": "user1", "username": "john.doe"}],
            "nextPageToken": "token123",
        }
        mock_client.admin.User.list.return_value = mock_response

        # Execute
        result = service.list_users(page_size=10, page_token="prev_token")

        # Assert
        mock_client.admin.User.list.assert_called_once_with(
            page_size=10, page_token="prev_token"
        )
        assert result["nextPageToken"] == "token123"

    def test_get_user(self, service, mock_client):
        """Test getting a specific user."""
        # Setup
        user_id = "user123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": user_id,
            "username": "john.doe",
            "email": "john@example.com",
            "displayName": "John Doe",
        }
        mock_client.admin.User.get.return_value = mock_response

        # Execute
        result = service.get_user(user_id)

        # Assert
        mock_client.admin.User.get.assert_called_once_with(user_id)
        assert result["id"] == user_id
        assert result["username"] == "john.doe"

    def test_get_current_user(self, service, mock_client):
        """Test getting current user."""
        # Setup
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": "current_user",
            "username": "current.user",
            "email": "current@example.com",
        }
        mock_client.admin.User.get_current.return_value = mock_response

        # Execute
        result = service.get_current_user()

        # Assert
        mock_client.admin.User.get_current.assert_called_once()
        assert result["id"] == "current_user"

    def test_search_users(self, service, mock_client):
        """Test searching users."""
        # Setup
        query = "john"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "users": [{"id": "user1", "username": "john.doe"}],
            "nextPageToken": None,
        }
        mock_client.admin.User.search.return_value = mock_response

        # Execute
        result = service.search_users(query)

        # Assert
        mock_client.admin.User.search.assert_called_once_with(
            query=query, page_size=None, page_token=None
        )
        assert len(result["users"]) == 1

    def test_get_user_markings(self, service, mock_client):
        """Test getting user markings."""
        # Setup
        user_id = "user123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "markings": ["public", "internal"],
            "permissions": ["read", "write"],
        }
        mock_client.admin.User.get_markings.return_value = mock_response

        # Execute
        result = service.get_user_markings(user_id)

        # Assert
        mock_client.admin.User.get_markings.assert_called_once_with(user_id)
        assert result["markings"] == ["public", "internal"]

    def test_revoke_user_tokens(self, service, mock_client):
        """Test revoking user tokens."""
        # Setup
        user_id = "user123"
        mock_client.admin.User.revoke_all_tokens.return_value = None

        # Execute
        result = service.revoke_user_tokens(user_id)

        # Assert
        mock_client.admin.User.revoke_all_tokens.assert_called_once_with(user_id)
        assert result["success"] is True
        assert "revoked" in result["message"]

    # Group Management Tests
    def test_list_groups(self, service, mock_client):
        """Test listing all groups."""
        # Setup
        mock_response = Mock()
        mock_response.dict.return_value = {
            "groups": [
                {
                    "id": "group1",
                    "name": "Engineering",
                    "description": "Engineering team",
                },
                {"id": "group2", "name": "Product", "description": "Product team"},
            ],
            "nextPageToken": None,
        }
        mock_client.admin.Group.list.return_value = mock_response

        # Execute
        result = service.list_groups()

        # Assert
        mock_client.admin.Group.list.assert_called_once_with(
            page_size=None, page_token=None
        )
        assert "groups" in result
        assert len(result["groups"]) == 2

    def test_get_group(self, service, mock_client):
        """Test getting a specific group."""
        # Setup
        group_id = "group123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": group_id,
            "name": "Engineering",
            "description": "Engineering team",
            "memberCount": 25,
        }
        mock_client.admin.Group.get.return_value = mock_response

        # Execute
        result = service.get_group(group_id)

        # Assert
        mock_client.admin.Group.get.assert_called_once_with(group_id)
        assert result["id"] == group_id
        assert result["name"] == "Engineering"

    def test_search_groups(self, service, mock_client):
        """Test searching groups."""
        # Setup
        query = "engineering"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "groups": [{"id": "group1", "name": "Engineering"}],
            "nextPageToken": None,
        }
        mock_client.admin.Group.search.return_value = mock_response

        # Execute
        result = service.search_groups(query)

        # Assert
        mock_client.admin.Group.search.assert_called_once_with(
            query=query, page_size=None, page_token=None
        )
        assert len(result["groups"]) == 1

    def test_create_group(self, service, mock_client):
        """Test creating a new group."""
        # Setup
        group_name = "New Team"
        description = "A new team"
        org_rid = "org123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": "new_group_id",
            "name": group_name,
            "description": description,
        }
        mock_client.admin.Group.create.return_value = mock_response

        # Execute
        result = service.create_group(
            name=group_name, description=description, organization_rid=org_rid
        )

        # Assert
        mock_client.admin.Group.create.assert_called_once_with(
            name=group_name, description=description, organization_rid=org_rid
        )
        assert result["name"] == group_name

    def test_create_group_minimal(self, service, mock_client):
        """Test creating a group with only name."""
        # Setup
        group_name = "Simple Group"
        mock_response = Mock()
        mock_response.dict.return_value = {"id": "simple_group_id", "name": group_name}
        mock_client.admin.Group.create.return_value = mock_response

        # Execute
        result = service.create_group(name=group_name)

        # Assert
        mock_client.admin.Group.create.assert_called_once_with(name=group_name)
        assert result["name"] == group_name

    def test_delete_group(self, service, mock_client):
        """Test deleting a group."""
        # Setup
        group_id = "group123"
        mock_client.admin.Group.delete.return_value = None

        # Execute
        result = service.delete_group(group_id)

        # Assert
        mock_client.admin.Group.delete.assert_called_once_with(group_id)
        assert result["success"] is True
        assert "deleted" in result["message"]

    # Organization Management Tests
    def test_get_organization(self, service, mock_client):
        """Test getting organization information."""
        # Setup
        org_id = "org123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": org_id,
            "name": "Acme Corp",
            "description": "Example organization",
        }
        mock_client.admin.Organization.get.return_value = mock_response

        # Execute
        result = service.get_organization(org_id)

        # Assert
        mock_client.admin.Organization.get.assert_called_once_with(org_id)
        assert result["id"] == org_id
        assert result["name"] == "Acme Corp"

    # Role Management Tests
    def test_get_role(self, service, mock_client):
        """Test getting role information."""
        # Setup
        role_id = "role123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": role_id,
            "name": "Admin",
            "description": "Administrator role",
        }
        mock_client.admin.Role.get.return_value = mock_response

        # Execute
        result = service.get_role(role_id)

        # Assert
        mock_client.admin.Role.get.assert_called_once_with(role_id)
        assert result["id"] == role_id
        assert result["name"] == "Admin"

    # Error Handling Tests
    def test_list_users_error(self, service, mock_client):
        """Test error handling in list_users."""
        # Setup
        mock_client.admin.User.list.side_effect = Exception("API Error")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to list users"):
            service.list_users()

    def test_get_user_error(self, service, mock_client):
        """Test error handling in get_user."""
        # Setup
        user_id = "user123"
        mock_client.admin.User.get.side_effect = Exception("User not found")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to get user"):
            service.get_user(user_id)

    def test_create_group_error(self, service, mock_client):
        """Test error handling in create_group."""
        # Setup
        group_name = "Bad Group"
        mock_client.admin.Group.create.side_effect = Exception("Validation error")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to create group"):
            service.create_group(name=group_name)

    # Serialization Tests
    def test_serialize_response_with_dict_method(self, service):
        """Test serialization of response with dict() method."""
        # Setup
        mock_response = Mock()
        mock_response.dict.return_value = {"key": "value"}

        # Execute
        result = service._serialize_response(mock_response)

        # Assert
        assert result == {"key": "value"}

    def test_serialize_response_with_dict_attr(self, service):
        """Test serialization of response with __dict__ attribute."""

        # Setup
        class MockResponse:
            def __init__(self):
                self.key = "value"
                self._private = "private"

        mock_response = MockResponse()

        # Execute
        result = service._serialize_response(mock_response)

        # Assert
        assert result == {"key": "value"}
        assert "_private" not in result

    def test_serialize_response_primitive(self, service):
        """Test serialization of primitive response."""
        # Execute & Assert
        assert service._serialize_response("string") == "string"
        assert service._serialize_response(123) == 123
        assert service._serialize_response(None) == {}

    def test_serialize_response_non_serializable(self, service):
        """Test serialization of non-serializable response."""

        # Setup
        class NonSerializableResponse:
            def __init__(self):
                self.data = object()  # non-serializable

        mock_response = NonSerializableResponse()

        # Execute
        result = service._serialize_response(mock_response)

        # Assert
        assert "data" in result
        assert isinstance(result["data"], str)
