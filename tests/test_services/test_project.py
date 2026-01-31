"""Tests for project service."""

import pytest
from unittest.mock import Mock, patch

from pltr.services.project import ProjectService


class TestProjectService:
    """Test cases for ProjectService."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.filesystem = Mock()
        client.filesystem.Project = Mock()
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
    def project_service(self, mock_auth_manager):
        """Create a ProjectService instance with mocked dependencies."""
        return ProjectService()

    def test_get_service(self, project_service, mock_client):
        """Test _get_service returns filesystem service."""
        project_service._client = mock_client
        assert project_service._get_service() == mock_client.filesystem

    def test_create_project_basic(self, project_service, mock_client):
        """Test creating a project with basic parameters."""
        mock_project = Mock()
        mock_project.rid = "ri.compass.main.project.123"
        mock_project.display_name = "Test Project"
        mock_project.space_rid = "ri.compass.main.space.456"

        mock_client.filesystem.Project.create.return_value = mock_project
        project_service._client = mock_client

        result = project_service.create_project(
            display_name="Test Project", space_rid="ri.compass.main.space.456"
        )

        mock_client.filesystem.Project.create.assert_called_once_with(
            display_name="Test Project",
            space_rid="ri.compass.main.space.456",
            description=None,
            organization_rids=[],
            default_roles=[],
            role_grants=[],
            preview=True,
        )

        assert result["rid"] == "ri.compass.main.project.123"
        assert result["display_name"] == "Test Project"
        assert result["space_rid"] == "ri.compass.main.space.456"

    def test_create_project_with_all_params(self, project_service, mock_client):
        """Test creating a project with all optional parameters."""
        mock_project = Mock()
        mock_project.rid = "ri.compass.main.project.123"

        mock_client.filesystem.Project.create.return_value = mock_project
        project_service._client = mock_client

        project_service.create_project(
            display_name="Test Project",
            space_rid="ri.compass.main.space.456",
            description="Test description",
            organization_rids=["ri.compass.main.org.789"],
            default_roles=["viewer"],
            role_grants=[
                {
                    "principal_id": "user1",
                    "principal_type": "User",
                    "role_name": "owner",
                }
            ],
        )

        mock_client.filesystem.Project.create.assert_called_once_with(
            display_name="Test Project",
            space_rid="ri.compass.main.space.456",
            description="Test description",
            organization_rids=["ri.compass.main.org.789"],
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

    def test_create_project_failure(self, project_service, mock_client):
        """Test handling project creation failure."""
        mock_client.filesystem.Project.create.side_effect = Exception("Creation failed")
        project_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to create project 'Test Project': Creation failed",
        ):
            project_service.create_project(
                display_name="Test Project", space_rid="ri.compass.main.space.456"
            )

    def test_get_project(self, project_service, mock_client):
        """Test getting a project."""
        mock_project = Mock()
        mock_project.rid = "ri.compass.main.project.123"
        mock_project.display_name = "Test Project"

        mock_client.filesystem.Project.get.return_value = mock_project
        project_service._client = mock_client

        result = project_service.get_project("ri.compass.main.project.123")

        mock_client.filesystem.Project.get.assert_called_once_with(
            "ri.compass.main.project.123", preview=True
        )
        assert result["rid"] == "ri.compass.main.project.123"
        assert result["display_name"] == "Test Project"

    def test_get_project_failure(self, project_service, mock_client):
        """Test handling project get failure."""
        mock_client.filesystem.Project.get.side_effect = Exception("Not found")
        project_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to get project ri.compass.main.project.123: Not found",
        ):
            project_service.get_project("ri.compass.main.project.123")

    def test_list_projects(self, project_service, mock_client):
        """Test listing projects."""
        mock_projects = [Mock(), Mock()]
        mock_projects[0].rid = "ri.compass.main.project.123"
        mock_projects[1].rid = "ri.compass.main.project.456"

        mock_client.filesystem.Project.list.return_value = iter(mock_projects)
        project_service._client = mock_client

        result = project_service.list_projects()

        mock_client.filesystem.Project.list.assert_called_once_with(preview=True)
        assert len(result) == 2
        assert result[0]["rid"] == "ri.compass.main.project.123"
        assert result[1]["rid"] == "ri.compass.main.project.456"

    def test_list_projects_with_filters(self, project_service, mock_client):
        """Test listing projects with filters."""
        mock_projects = [Mock()]
        mock_projects[0].rid = "ri.compass.main.project.123"

        mock_client.filesystem.Project.list.return_value = iter(mock_projects)
        project_service._client = mock_client

        project_service.list_projects(
            space_rid="ri.compass.main.space.789", page_size=10, page_token="token123"
        )

        mock_client.filesystem.Project.list.assert_called_once_with(
            preview=True,
            space_rid="ri.compass.main.space.789",
            page_size=10,
            page_token="token123",
        )

    def test_delete_project(self, project_service, mock_client):
        """Test deleting a project."""
        project_service._client = mock_client

        project_service.delete_project("ri.compass.main.project.123")

        mock_client.filesystem.Project.delete.assert_called_once_with(
            "ri.compass.main.project.123", preview=True
        )

    def test_delete_project_failure(self, project_service, mock_client):
        """Test handling project deletion failure."""
        mock_client.filesystem.Project.delete.side_effect = Exception("Deletion failed")
        project_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to delete project ri.compass.main.project.123: Deletion failed",
        ):
            project_service.delete_project("ri.compass.main.project.123")

    def test_update_project(self, project_service, mock_client):
        """Test updating a project."""
        mock_project = Mock()
        mock_project.rid = "ri.compass.main.project.123"
        mock_project.display_name = "Updated Project"

        mock_client.filesystem.Project.replace.return_value = mock_project
        project_service._client = mock_client

        result = project_service.update_project(
            project_rid="ri.compass.main.project.123",
            display_name="Updated Project",
            description="Updated description",
        )

        mock_client.filesystem.Project.replace.assert_called_once_with(
            project_rid="ri.compass.main.project.123",
            display_name="Updated Project",
            description="Updated description",
            preview=True,
        )
        assert result["display_name"] == "Updated Project"

    def test_update_project_without_display_name(self, project_service, mock_client):
        """Test updating a project when display_name not provided - fetches current."""
        mock_current_project = Mock()
        mock_current_project.display_name = "Current Name"

        mock_updated_project = Mock()
        mock_updated_project.rid = "ri.compass.main.project.123"
        mock_updated_project.display_name = "Current Name"
        mock_updated_project.description = "New description"

        mock_client.filesystem.Project.get.return_value = mock_current_project
        mock_client.filesystem.Project.replace.return_value = mock_updated_project
        project_service._client = mock_client

        result = project_service.update_project(
            project_rid="ri.compass.main.project.123",
            description="New description",
        )

        mock_client.filesystem.Project.get.assert_called_once_with(
            "ri.compass.main.project.123", preview=True
        )
        mock_client.filesystem.Project.replace.assert_called_once_with(
            project_rid="ri.compass.main.project.123",
            display_name="Current Name",
            description="New description",
            preview=True,
        )
        assert result["display_name"] == "Current Name"

    def test_update_project_no_fields(self, project_service):
        """Test update project with no fields raises error."""
        with pytest.raises(
            ValueError, match="At least one field must be provided for update"
        ):
            project_service.update_project("ri.compass.main.project.123")

    def test_format_project_info(self, project_service):
        """Test formatting project information."""
        mock_project = Mock()
        mock_project.rid = "ri.compass.main.project.123"
        mock_project.display_name = "Test Project"
        mock_project.description = "Test description"
        mock_project.space_rid = "ri.compass.main.space.456"
        mock_project.created_by = "user123"
        mock_project.created_time = Mock()
        mock_project.created_time.time = "2023-01-01T00:00:00Z"

        result = project_service._format_project_info(mock_project)

        assert result["rid"] == "ri.compass.main.project.123"
        assert result["display_name"] == "Test Project"
        assert result["description"] == "Test description"
        assert result["space_rid"] == "ri.compass.main.space.456"
        assert result["created_by"] == "user123"
        assert result["created_time"] == "2023-01-01T00:00:00Z"
        assert result["type"] == "project"

    # ==================== Organization Operations Tests ====================

    def test_add_organizations(self, project_service, mock_client):
        """Test adding organizations to a project."""
        mock_client.filesystem.Project.add_organizations.return_value = None
        project_service._client = mock_client

        org_rids = ["ri.compass.main.org.123", "ri.compass.main.org.456"]
        project_service.add_organizations("ri.compass.main.project.789", org_rids)

        mock_client.filesystem.Project.add_organizations.assert_called_once_with(
            "ri.compass.main.project.789", organization_rids=org_rids, preview=True
        )

    def test_add_organizations_failure(self, project_service, mock_client):
        """Test handling add organizations failure."""
        mock_client.filesystem.Project.add_organizations.side_effect = Exception(
            "Invalid org"
        )
        project_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to add organizations to project ri.compass.main.project.123: Invalid org",
        ):
            project_service.add_organizations(
                "ri.compass.main.project.123", ["ri.compass.main.org.456"]
            )

    def test_remove_organizations(self, project_service, mock_client):
        """Test removing organizations from a project."""
        mock_client.filesystem.Project.remove_organizations.return_value = None
        project_service._client = mock_client

        org_rids = ["ri.compass.main.org.123", "ri.compass.main.org.456"]
        project_service.remove_organizations("ri.compass.main.project.789", org_rids)

        mock_client.filesystem.Project.remove_organizations.assert_called_once_with(
            "ri.compass.main.project.789", organization_rids=org_rids, preview=True
        )

    def test_remove_organizations_failure(self, project_service, mock_client):
        """Test handling remove organizations failure."""
        mock_client.filesystem.Project.remove_organizations.side_effect = Exception(
            "Org not found"
        )
        project_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to remove organizations from project ri.compass.main.project.123: Org not found",
        ):
            project_service.remove_organizations(
                "ri.compass.main.project.123", ["ri.compass.main.org.456"]
            )

    def test_list_organizations(self, project_service, mock_client):
        """Test listing organizations on a project."""
        mock_orgs = [Mock(), Mock()]
        mock_orgs[0].organization_rid = "ri.compass.main.org.123"
        mock_orgs[0].display_name = "Org 1"
        mock_orgs[1].organization_rid = "ri.compass.main.org.456"
        mock_orgs[1].display_name = "Org 2"

        mock_client.filesystem.Project.organizations.return_value = iter(mock_orgs)
        project_service._client = mock_client

        result = project_service.list_organizations("ri.compass.main.project.789")

        mock_client.filesystem.Project.organizations.assert_called_once_with(
            "ri.compass.main.project.789", preview=True
        )
        assert len(result) == 2
        assert result[0]["organization_rid"] == "ri.compass.main.org.123"
        assert result[0]["display_name"] == "Org 1"
        assert result[1]["organization_rid"] == "ri.compass.main.org.456"
        assert result[1]["display_name"] == "Org 2"

    def test_list_organizations_with_pagination(self, project_service, mock_client):
        """Test listing organizations with pagination."""
        mock_orgs = [Mock()]
        mock_orgs[0].organization_rid = "ri.compass.main.org.123"

        mock_client.filesystem.Project.organizations.return_value = iter(mock_orgs)
        project_service._client = mock_client

        project_service.list_organizations(
            "ri.compass.main.project.789", page_size=10, page_token="token123"
        )

        mock_client.filesystem.Project.organizations.assert_called_once_with(
            "ri.compass.main.project.789",
            preview=True,
            page_size=10,
            page_token="token123",
        )

    def test_list_organizations_failure(self, project_service, mock_client):
        """Test handling list organizations failure."""
        mock_client.filesystem.Project.organizations.side_effect = Exception(
            "Access denied"
        )
        project_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to list organizations for project ri.compass.main.project.123: Access denied",
        ):
            project_service.list_organizations("ri.compass.main.project.123")

    # ==================== Template Operations Tests ====================

    def test_create_project_from_template(self, project_service, mock_client):
        """Test creating a project from template."""
        mock_project = Mock()
        mock_project.rid = "ri.compass.main.project.123"
        mock_project.display_name = "Project from Template"

        mock_client.filesystem.Project.create_from_template.return_value = mock_project
        project_service._client = mock_client

        result = project_service.create_project_from_template(
            template_rid="ri.compass.main.template.456",
            variable_values={"name": "MyProject", "env": "prod"},
        )

        mock_client.filesystem.Project.create_from_template.assert_called_once_with(
            template_rid="ri.compass.main.template.456",
            variable_values={"name": "MyProject", "env": "prod"},
            preview=True,
        )
        assert result["rid"] == "ri.compass.main.project.123"
        assert result["display_name"] == "Project from Template"

    def test_create_project_from_template_with_all_params(
        self, project_service, mock_client
    ):
        """Test creating project from template with all parameters."""
        mock_project = Mock()
        mock_project.rid = "ri.compass.main.project.123"

        mock_client.filesystem.Project.create_from_template.return_value = mock_project
        project_service._client = mock_client

        project_service.create_project_from_template(
            template_rid="ri.compass.main.template.456",
            variable_values={"name": "MyProject"},
            default_roles=["viewer"],
            organization_rids=["ri.compass.main.org.789"],
            project_description="Test project",
        )

        mock_client.filesystem.Project.create_from_template.assert_called_once_with(
            template_rid="ri.compass.main.template.456",
            variable_values={"name": "MyProject"},
            preview=True,
            default_roles=["viewer"],
            organization_rids=["ri.compass.main.org.789"],
            project_description="Test project",
        )

    def test_create_project_from_template_failure(self, project_service, mock_client):
        """Test handling create from template failure."""
        mock_client.filesystem.Project.create_from_template.side_effect = Exception(
            "Invalid template"
        )
        project_service._client = mock_client

        with pytest.raises(
            RuntimeError,
            match="Failed to create project from template: Invalid template",
        ):
            project_service.create_project_from_template(
                template_rid="ri.compass.main.template.456",
                variable_values={"name": "MyProject"},
            )

    # ==================== Formatting Tests ====================

    def test_format_organization_info(self, project_service):
        """Test formatting organization information."""
        mock_org = Mock()
        mock_org.organization_rid = "ri.compass.main.org.123"
        mock_org.display_name = "My Organization"
        mock_org.description = "Organization description"

        result = project_service._format_organization_info(mock_org)

        assert result["organization_rid"] == "ri.compass.main.org.123"
        assert result["display_name"] == "My Organization"
        assert result["description"] == "Organization description"
