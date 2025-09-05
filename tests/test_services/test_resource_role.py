"""Tests for resource role service."""

import pytest
from unittest.mock import Mock, patch

from pltr.services.resource_role import ResourceRoleService


class TestResourceRoleService:
    """Test cases for ResourceRoleService."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.filesystem = Mock()
        client.filesystem.ResourceRole = Mock()
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
    def resource_role_service(self, mock_auth_manager):
        """Create a ResourceRoleService instance with mocked dependencies."""
        return ResourceRoleService()

    def test_get_service(self, resource_role_service, mock_client):
        """Test _get_service returns filesystem service."""
        resource_role_service._client = mock_client
        assert resource_role_service._get_service() == mock_client.filesystem

    def test_grant_role(self, resource_role_service, mock_client):
        """Test granting a role."""
        mock_role_grant = Mock()
        mock_role_grant.resource_rid = "ri.compass.main.dataset.123"
        mock_role_grant.principal_id = "user123"
        mock_role_grant.principal_type = "User"
        mock_role_grant.role_name = "viewer"

        mock_client.filesystem.ResourceRole.grant.return_value = mock_role_grant
        resource_role_service._client = mock_client

        result = resource_role_service.grant_role(
            resource_rid="ri.compass.main.dataset.123",
            principal_id="user123",
            principal_type="User",
            role_name="viewer",
        )

        expected_role_grant = {
            "principal_id": "user123",
            "principal_type": "User",
            "role_name": "viewer",
        }

        mock_client.filesystem.ResourceRole.grant.assert_called_once_with(
            resource_rid="ri.compass.main.dataset.123",
            body=expected_role_grant,
            preview=True,
        )

        assert result["resource_rid"] == "ri.compass.main.dataset.123"
        assert result["principal_id"] == "user123"
        assert result["principal_type"] == "User"
        assert result["role_name"] == "viewer"

    def test_grant_role_failure(self, resource_role_service, mock_client):
        """Test handling role grant failure."""
        mock_client.filesystem.ResourceRole.grant.side_effect = Exception(
            "Grant failed"
        )
        resource_role_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to grant role 'viewer' to User 'user123' on resource ri.compass.main.dataset.123: Grant failed",
        ):
            resource_role_service.grant_role(
                resource_rid="ri.compass.main.dataset.123",
                principal_id="user123",
                principal_type="User",
                role_name="viewer",
            )

    def test_revoke_role(self, resource_role_service, mock_client):
        """Test revoking a role."""
        resource_role_service._client = mock_client

        resource_role_service.revoke_role(
            resource_rid="ri.compass.main.dataset.123",
            principal_id="user123",
            principal_type="User",
            role_name="viewer",
        )

        expected_role_revocation = {
            "principal_id": "user123",
            "principal_type": "User",
            "role_name": "viewer",
        }

        mock_client.filesystem.ResourceRole.revoke.assert_called_once_with(
            resource_rid="ri.compass.main.dataset.123",
            body=expected_role_revocation,
            preview=True,
        )

    def test_revoke_role_failure(self, resource_role_service, mock_client):
        """Test handling role revoke failure."""
        mock_client.filesystem.ResourceRole.revoke.side_effect = Exception(
            "Revoke failed"
        )
        resource_role_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to revoke role 'viewer' from User 'user123' on resource ri.compass.main.dataset.123: Revoke failed",
        ):
            resource_role_service.revoke_role(
                resource_rid="ri.compass.main.dataset.123",
                principal_id="user123",
                principal_type="User",
                role_name="viewer",
            )

    def test_list_resource_roles(self, resource_role_service, mock_client):
        """Test listing resource roles."""
        mock_role_grants = [Mock(), Mock()]
        mock_role_grants[0].resource_rid = "ri.compass.main.dataset.123"
        mock_role_grants[0].principal_id = "user123"
        mock_role_grants[0].role_name = "viewer"
        mock_role_grants[1].resource_rid = "ri.compass.main.dataset.123"
        mock_role_grants[1].principal_id = "group456"
        mock_role_grants[1].role_name = "editor"

        mock_client.filesystem.ResourceRole.list.return_value = iter(mock_role_grants)
        resource_role_service._client = mock_client

        result = resource_role_service.list_resource_roles(
            "ri.compass.main.dataset.123"
        )

        mock_client.filesystem.ResourceRole.list.assert_called_once_with(
            "ri.compass.main.dataset.123", preview=True
        )
        assert len(result) == 2
        assert result[0]["principal_id"] == "user123"
        assert result[0]["role_name"] == "viewer"
        assert result[1]["principal_id"] == "group456"
        assert result[1]["role_name"] == "editor"

    def test_list_resource_roles_with_filters(self, resource_role_service, mock_client):
        """Test listing resource roles with filters."""
        mock_role_grants = [Mock()]
        mock_role_grants[0].resource_rid = "ri.compass.main.dataset.123"
        mock_role_grants[0].principal_id = "user123"

        mock_client.filesystem.ResourceRole.list.return_value = iter(mock_role_grants)
        resource_role_service._client = mock_client

        resource_role_service.list_resource_roles(
            resource_rid="ri.compass.main.dataset.123",
            principal_type="User",
            page_size=10,
            page_token="token123",
        )

        mock_client.filesystem.ResourceRole.list.assert_called_once_with(
            "ri.compass.main.dataset.123",
            preview=True,
            principal_type="User",
            page_size=10,
            page_token="token123",
        )

    def test_get_principal_roles(self, resource_role_service, mock_client):
        """Test getting principal roles."""
        mock_role_grants = [Mock(), Mock()]
        mock_role_grants[0].resource_rid = "ri.compass.main.dataset.123"
        mock_role_grants[0].role_name = "viewer"
        mock_role_grants[1].resource_rid = "ri.compass.main.dataset.456"
        mock_role_grants[1].role_name = "editor"

        mock_client.filesystem.ResourceRole.get_principal_roles.return_value = iter(
            mock_role_grants
        )
        resource_role_service._client = mock_client

        result = resource_role_service.get_principal_roles(
            principal_id="user123", principal_type="User"
        )

        mock_client.filesystem.ResourceRole.get_principal_roles.assert_called_once_with(
            principal_id="user123", principal_type="User", preview=True
        )
        assert len(result) == 2
        assert result[0]["resource_rid"] == "ri.compass.main.dataset.123"
        assert result[0]["role_name"] == "viewer"
        assert result[1]["resource_rid"] == "ri.compass.main.dataset.456"
        assert result[1]["role_name"] == "editor"

    def test_get_principal_roles_with_filters(self, resource_role_service, mock_client):
        """Test getting principal roles with filters."""
        mock_role_grants = [Mock()]
        mock_role_grants[0].resource_rid = "ri.compass.main.dataset.123"

        mock_client.filesystem.ResourceRole.get_principal_roles.return_value = iter(
            mock_role_grants
        )
        resource_role_service._client = mock_client

        resource_role_service.get_principal_roles(
            principal_id="user123",
            principal_type="User",
            resource_rid="ri.compass.main.dataset.123",
            page_size=10,
            page_token="token123",
        )

        mock_client.filesystem.ResourceRole.get_principal_roles.assert_called_once_with(
            principal_id="user123",
            principal_type="User",
            preview=True,
            resource_rid="ri.compass.main.dataset.123",
            page_size=10,
            page_token="token123",
        )

    def test_bulk_grant_roles(self, resource_role_service, mock_client):
        """Test bulk granting roles."""
        role_grants = [
            {
                "principal_id": "user123",
                "principal_type": "User",
                "role_name": "viewer",
            },
            {
                "principal_id": "group456",
                "principal_type": "Group",
                "role_name": "editor",
            },
        ]

        mock_result = Mock()
        mock_result.role_grants = [Mock(), Mock()]
        mock_result.role_grants[0].principal_id = "user123"
        mock_result.role_grants[0].role_name = "viewer"
        mock_result.role_grants[1].principal_id = "group456"
        mock_result.role_grants[1].role_name = "editor"

        mock_client.filesystem.ResourceRole.bulk_grant.return_value = mock_result
        resource_role_service._client = mock_client

        result = resource_role_service.bulk_grant_roles(
            "ri.compass.main.dataset.123", role_grants
        )

        mock_client.filesystem.ResourceRole.bulk_grant.assert_called_once_with(
            resource_rid="ri.compass.main.dataset.123",
            body={"role_grants": role_grants},
            preview=True,
        )
        assert len(result) == 2
        assert result[0]["principal_id"] == "user123"
        assert result[0]["role_name"] == "viewer"

    def test_bulk_revoke_roles(self, resource_role_service, mock_client):
        """Test bulk revoking roles."""
        role_revocations = [
            {
                "principal_id": "user123",
                "principal_type": "User",
                "role_name": "viewer",
            },
            {
                "principal_id": "group456",
                "principal_type": "Group",
                "role_name": "editor",
            },
        ]

        resource_role_service._client = mock_client

        resource_role_service.bulk_revoke_roles(
            "ri.compass.main.dataset.123", role_revocations
        )

        mock_client.filesystem.ResourceRole.bulk_revoke.assert_called_once_with(
            resource_rid="ri.compass.main.dataset.123",
            body={"role_revocations": role_revocations},
            preview=True,
        )

    def test_get_available_roles(self, resource_role_service, mock_client):
        """Test getting available roles."""
        mock_roles = [Mock(), Mock()]
        mock_roles[0].name = "viewer"
        mock_roles[0].display_name = "Viewer"
        mock_roles[0].description = "Can view resource"
        mock_roles[0].is_owner_like = False
        mock_roles[1].name = "owner"
        mock_roles[1].display_name = "Owner"
        mock_roles[1].description = "Can manage resource"
        mock_roles[1].is_owner_like = True

        mock_client.filesystem.ResourceRole.get_available_roles.return_value = iter(
            mock_roles
        )
        resource_role_service._client = mock_client

        result = resource_role_service.get_available_roles(
            "ri.compass.main.dataset.123"
        )

        mock_client.filesystem.ResourceRole.get_available_roles.assert_called_once_with(
            "ri.compass.main.dataset.123", preview=True
        )
        assert len(result) == 2
        assert result[0]["name"] == "viewer"
        assert result[0]["display_name"] == "Viewer"
        assert result[0]["is_owner_like"] is False
        assert result[1]["name"] == "owner"
        assert result[1]["display_name"] == "Owner"
        assert result[1]["is_owner_like"] is True

    def test_format_role_grant(self, resource_role_service):
        """Test formatting role grant information."""
        mock_role_grant = Mock()
        mock_role_grant.resource_rid = "ri.compass.main.dataset.123"
        mock_role_grant.principal_id = "user123"
        mock_role_grant.principal_type = "User"
        mock_role_grant.role_name = "viewer"
        mock_role_grant.granted_by = "admin"
        mock_role_grant.granted_time = Mock()
        mock_role_grant.granted_time.time = "2023-01-01T00:00:00Z"
        mock_role_grant.expires_at = Mock()
        mock_role_grant.expires_at.time = "2024-01-01T00:00:00Z"

        result = resource_role_service._format_role_grant(mock_role_grant)

        assert result["resource_rid"] == "ri.compass.main.dataset.123"
        assert result["principal_id"] == "user123"
        assert result["principal_type"] == "User"
        assert result["role_name"] == "viewer"
        assert result["granted_by"] == "admin"
        assert result["granted_time"] == "2023-01-01T00:00:00Z"
        assert result["expires_at"] == "2024-01-01T00:00:00Z"

    def test_format_role_info(self, resource_role_service):
        """Test formatting role information."""
        mock_role = Mock()
        mock_role.name = "viewer"
        mock_role.display_name = "Viewer"
        mock_role.description = "Can view resource"
        mock_role.permissions = ["read"]
        mock_role.is_owner_like = False

        result = resource_role_service._format_role_info(mock_role)

        assert result["name"] == "viewer"
        assert result["display_name"] == "Viewer"
        assert result["description"] == "Can view resource"
        assert result["permissions"] == ["read"]
        assert result["is_owner_like"] is False
