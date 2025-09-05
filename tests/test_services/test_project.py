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
            body={
                "display_name": "Test Project",
                "space_rid": "ri.compass.main.space.456",
            },
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

        expected_body = {
            "display_name": "Test Project",
            "space_rid": "ri.compass.main.space.456",
            "description": "Test description",
            "organization_rids": ["ri.compass.main.org.789"],
            "default_roles": ["viewer"],
            "role_grants": [
                {
                    "principal_id": "user1",
                    "principal_type": "User",
                    "role_name": "owner",
                }
            ],
        }

        mock_client.filesystem.Project.create.assert_called_once_with(
            body=expected_body, preview=True
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

        mock_client.filesystem.Project.update.return_value = mock_project
        project_service._client = mock_client

        result = project_service.update_project(
            project_rid="ri.compass.main.project.123",
            display_name="Updated Project",
            description="Updated description",
        )

        mock_client.filesystem.Project.update.assert_called_once_with(
            project_rid="ri.compass.main.project.123",
            body={
                "display_name": "Updated Project",
                "description": "Updated description",
            },
            preview=True,
        )
        assert result["display_name"] == "Updated Project"

    def test_update_project_no_fields(self, project_service):
        """Test update project with no fields raises error."""
        with pytest.raises(
            ValueError, match="At least one field must be provided for update"
        ):
            project_service.update_project("ri.compass.main.project.123")

    def test_get_projects_batch(self, project_service, mock_client):
        """Test getting multiple projects in batch."""
        mock_response = Mock()
        mock_projects = [Mock(), Mock()]
        mock_projects[0].rid = "ri.compass.main.project.123"
        mock_projects[1].rid = "ri.compass.main.project.456"
        mock_response.projects = mock_projects

        mock_client.filesystem.Project.get_batch.return_value = mock_response
        project_service._client = mock_client

        rids = ["ri.compass.main.project.123", "ri.compass.main.project.456"]
        result = project_service.get_projects_batch(rids)

        mock_client.filesystem.Project.get_batch.assert_called_once_with(
            body=rids, preview=True
        )
        assert len(result) == 2
        assert result[0]["rid"] == "ri.compass.main.project.123"
        assert result[1]["rid"] == "ri.compass.main.project.456"

    def test_get_projects_batch_too_many(self, project_service):
        """Test batch get with too many projects raises error."""
        rids = ["rid"] * 1001

        with pytest.raises(ValueError, match="Maximum batch size is 1000 projects"):
            project_service.get_projects_batch(rids)

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
