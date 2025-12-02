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
        client.admin.Marking = Mock()
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

    # New User Management Tests
    def test_delete_user(self, service, mock_client):
        """Test deleting a user."""
        # Setup
        user_id = "user123"
        mock_client.admin.User.delete.return_value = None

        # Execute
        result = service.delete_user(user_id)

        # Assert
        mock_client.admin.User.delete.assert_called_once_with(user_id)
        assert result["success"] is True
        assert "deleted" in result["message"]

    def test_delete_user_error(self, service, mock_client):
        """Test error handling in delete_user."""
        # Setup
        user_id = "user123"
        mock_client.admin.User.delete.side_effect = Exception("User not found")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to delete user"):
            service.delete_user(user_id)

    def test_get_batch_users(self, service, mock_client):
        """Test batch getting users."""
        # Setup
        user_ids = ["user1", "user2"]
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [
                {"id": "user1", "username": "john"},
                {"id": "user2", "username": "jane"},
            ]
        }
        mock_client.admin.User.get_batch.return_value = mock_response

        # Execute
        result = service.get_batch_users(user_ids)

        # Assert
        mock_client.admin.User.get_batch.assert_called_once_with(body=user_ids)
        assert "data" in result

    def test_get_batch_users_exceeds_limit(self, service, mock_client):
        """Test batch get users exceeds limit."""
        # Setup
        user_ids = [f"user{i}" for i in range(501)]

        # Execute & Assert
        with pytest.raises(ValueError, match="Maximum batch size is 500"):
            service.get_batch_users(user_ids)

    # New Group Management Tests
    def test_get_batch_groups(self, service, mock_client):
        """Test batch getting groups."""
        # Setup
        group_ids = ["group1", "group2"]
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [
                {"id": "group1", "name": "Engineering"},
                {"id": "group2", "name": "Product"},
            ]
        }
        mock_client.admin.Group.get_batch.return_value = mock_response

        # Execute
        result = service.get_batch_groups(group_ids)

        # Assert
        mock_client.admin.Group.get_batch.assert_called_once_with(body=group_ids)
        assert "data" in result

    def test_get_batch_groups_exceeds_limit(self, service, mock_client):
        """Test batch get groups exceeds limit."""
        # Setup
        group_ids = [f"group{i}" for i in range(501)]

        # Execute & Assert
        with pytest.raises(ValueError, match="Maximum batch size is 500"):
            service.get_batch_groups(group_ids)

    # Marking Management Tests
    def test_list_markings(self, service, mock_client):
        """Test listing markings."""
        # Setup
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [
                {"id": "marking1", "name": "Confidential"},
                {"id": "marking2", "name": "Public"},
            ],
            "nextPageToken": None,
        }
        mock_client.admin.Marking.list.return_value = mock_response

        # Execute
        result = service.list_markings()

        # Assert
        mock_client.admin.Marking.list.assert_called_once_with(
            page_size=None, page_token=None, preview=True
        )
        assert "data" in result

    def test_get_marking(self, service, mock_client):
        """Test getting a specific marking."""
        # Setup
        marking_id = "marking123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": marking_id,
            "name": "Confidential",
            "description": "Confidential marking",
        }
        mock_client.admin.Marking.get.return_value = mock_response

        # Execute
        result = service.get_marking(marking_id)

        # Assert
        mock_client.admin.Marking.get.assert_called_once_with(marking_id, preview=True)
        assert result["id"] == marking_id

    def test_get_batch_markings(self, service, mock_client):
        """Test batch getting markings."""
        # Setup
        marking_ids = ["marking1", "marking2"]
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [
                {"id": "marking1", "name": "Confidential"},
                {"id": "marking2", "name": "Public"},
            ]
        }
        mock_client.admin.Marking.get_batch.return_value = mock_response

        # Execute
        result = service.get_batch_markings(marking_ids)

        # Assert
        mock_client.admin.Marking.get_batch.assert_called_once_with(
            body=marking_ids, preview=True
        )
        assert "data" in result

    def test_get_batch_markings_exceeds_limit(self, service, mock_client):
        """Test batch get markings exceeds limit."""
        # Setup
        marking_ids = [f"marking{i}" for i in range(501)]

        # Execute & Assert
        with pytest.raises(ValueError, match="Maximum batch size is 500"):
            service.get_batch_markings(marking_ids)

    def test_create_marking(self, service, mock_client):
        """Test creating a marking."""
        # Setup
        marking_name = "New Marking"
        description = "Test description"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": "new_marking_id",
            "name": marking_name,
            "description": description,
        }
        mock_client.admin.Marking.create.return_value = mock_response

        # Execute
        result = service.create_marking(name=marking_name, description=description)

        # Assert
        mock_client.admin.Marking.create.assert_called_once_with(
            name=marking_name, description=description, preview=True
        )
        assert result["name"] == marking_name

    def test_create_marking_minimal(self, service, mock_client):
        """Test creating a marking with only name."""
        # Setup
        marking_name = "Simple Marking"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": "simple_marking_id",
            "name": marking_name,
        }
        mock_client.admin.Marking.create.return_value = mock_response

        # Execute
        result = service.create_marking(name=marking_name)

        # Assert
        mock_client.admin.Marking.create.assert_called_once_with(
            name=marking_name, preview=True
        )
        assert result["name"] == marking_name

    def test_replace_marking(self, service, mock_client):
        """Test replacing a marking."""
        # Setup
        marking_id = "marking123"
        new_name = "Updated Marking"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": marking_id,
            "name": new_name,
        }
        mock_client.admin.Marking.replace.return_value = mock_response

        # Execute
        result = service.replace_marking(marking_id=marking_id, name=new_name)

        # Assert
        mock_client.admin.Marking.replace.assert_called_once_with(
            marking_id, name=new_name, preview=True
        )
        assert result["name"] == new_name

    def test_create_marking_error(self, service, mock_client):
        """Test error handling in create_marking."""
        # Setup
        mock_client.admin.Marking.create.side_effect = Exception("Permission denied")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to create marking"):
            service.create_marking(name="Test Marking")

    # New Organization Management Tests
    def test_create_organization(self, service, mock_client):
        """Test creating an organization."""
        # Setup
        org_name = "New Org"
        enrollment_rid = "enrollment123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": "new_org_id",
            "name": org_name,
        }
        mock_client.admin.Organization.create.return_value = mock_response

        # Execute
        result = service.create_organization(
            name=org_name, enrollment_rid=enrollment_rid
        )

        # Assert
        mock_client.admin.Organization.create.assert_called_once_with(
            name=org_name, enrollment_rid=enrollment_rid, preview=True
        )
        assert result["name"] == org_name

    def test_create_organization_with_admins(self, service, mock_client):
        """Test creating an organization with admin IDs."""
        # Setup
        org_name = "New Org"
        enrollment_rid = "enrollment123"
        admin_ids = ["admin1", "admin2"]
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": "new_org_id",
            "name": org_name,
        }
        mock_client.admin.Organization.create.return_value = mock_response

        # Execute
        result = service.create_organization(
            name=org_name, enrollment_rid=enrollment_rid, admin_ids=admin_ids
        )

        # Assert
        mock_client.admin.Organization.create.assert_called_once_with(
            name=org_name,
            enrollment_rid=enrollment_rid,
            admin_ids=admin_ids,
            preview=True,
        )
        assert result["name"] == org_name

    def test_replace_organization(self, service, mock_client):
        """Test replacing an organization."""
        # Setup
        org_rid = "org123"
        new_name = "Updated Org"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "id": org_rid,
            "name": new_name,
        }
        mock_client.admin.Organization.replace.return_value = mock_response

        # Execute
        result = service.replace_organization(organization_rid=org_rid, name=new_name)

        # Assert
        mock_client.admin.Organization.replace.assert_called_once_with(
            org_rid, name=new_name, preview=True
        )
        assert result["name"] == new_name

    def test_list_available_roles(self, service, mock_client):
        """Test listing available roles for an organization."""
        # Setup
        org_rid = "org123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [
                {"id": "role1", "name": "Admin"},
                {"id": "role2", "name": "Editor"},
            ],
            "nextPageToken": None,
        }
        mock_client.admin.Organization.list_available_roles.return_value = mock_response

        # Execute
        result = service.list_available_roles(org_rid)

        # Assert
        mock_client.admin.Organization.list_available_roles.assert_called_once_with(
            org_rid, page_size=None, page_token=None, preview=True
        )
        assert "data" in result

    # New Role Management Tests
    def test_get_batch_roles(self, service, mock_client):
        """Test batch getting roles."""
        # Setup
        role_ids = ["role1", "role2"]
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [
                {"id": "role1", "name": "Admin"},
                {"id": "role2", "name": "Editor"},
            ]
        }
        mock_client.admin.Role.get_batch.return_value = mock_response

        # Execute
        result = service.get_batch_roles(role_ids)

        # Assert
        mock_client.admin.Role.get_batch.assert_called_once_with(
            body=role_ids, preview=True
        )
        assert "data" in result

    def test_get_batch_roles_exceeds_limit(self, service, mock_client):
        """Test batch get roles exceeds limit."""
        # Setup
        role_ids = [f"role{i}" for i in range(501)]

        # Execute & Assert
        with pytest.raises(ValueError, match="Maximum batch size is 500"):
            service.get_batch_roles(role_ids)
