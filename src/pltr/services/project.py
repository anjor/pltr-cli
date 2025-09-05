"""
Project service wrapper for Foundry SDK filesystem API.
"""

from typing import Any, Optional, Dict, List

from .base import BaseService


class ProjectService(BaseService):
    """Service wrapper for Foundry project operations using filesystem API."""

    def _get_service(self) -> Any:
        """Get the Foundry filesystem service."""
        return self.client.filesystem

    def create_project(
        self,
        display_name: str,
        space_rid: str,
        description: Optional[str] = None,
        organization_rids: Optional[List[str]] = None,
        default_roles: Optional[List[str]] = None,
        role_grants: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new project.

        Args:
            display_name: Project display name (cannot contain '/')
            space_rid: Space Resource Identifier where project will be created
            description: Project description (optional)
            organization_rids: List of organization RIDs (optional)
            default_roles: List of default role names (optional)
            role_grants: List of role grant specifications (optional)

        Returns:
            Created project information
        """
        try:
            # Prepare the create request payload
            create_request: Dict[str, Any] = {
                "display_name": display_name,
                "space_rid": space_rid,
            }

            if description:
                create_request["description"] = description
            if organization_rids:
                create_request["organization_rids"] = organization_rids
            if default_roles:
                create_request["default_roles"] = default_roles
            if role_grants:
                create_request["role_grants"] = role_grants

            project = self.service.Project.create(
                body=create_request,
                preview=True,
            )
            return self._format_project_info(project)
        except Exception as e:
            raise RuntimeError(f"Failed to create project '{display_name}': {e}")

    def get_project(self, project_rid: str) -> Dict[str, Any]:
        """
        Get information about a specific project.

        Args:
            project_rid: Project Resource Identifier

        Returns:
            Project information dictionary
        """
        try:
            project = self.service.Project.get(project_rid, preview=True)
            return self._format_project_info(project)
        except Exception as e:
            raise RuntimeError(f"Failed to get project {project_rid}: {e}")

    def list_projects(
        self,
        space_rid: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List projects, optionally filtered by space.

        Args:
            space_rid: Space Resource Identifier to filter by (optional)
            page_size: Number of items per page (optional)
            page_token: Pagination token (optional)

        Returns:
            List of project information dictionaries
        """
        try:
            projects = []
            list_params: Dict[str, Any] = {"preview": True}

            if space_rid:
                list_params["space_rid"] = space_rid
            if page_size:
                list_params["page_size"] = page_size
            if page_token:
                list_params["page_token"] = page_token

            # The list method returns an iterator
            for project in self.service.Project.list(**list_params):
                projects.append(self._format_project_info(project))
            return projects
        except Exception as e:
            raise RuntimeError(f"Failed to list projects: {e}")

    def delete_project(self, project_rid: str) -> None:
        """
        Delete a project.

        Args:
            project_rid: Project Resource Identifier

        Raises:
            RuntimeError: If deletion fails
        """
        try:
            self.service.Project.delete(project_rid, preview=True)
        except Exception as e:
            raise RuntimeError(f"Failed to delete project {project_rid}: {e}")

    def update_project(
        self,
        project_rid: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update project information.

        Args:
            project_rid: Project Resource Identifier
            display_name: New display name (optional)
            description: New description (optional)

        Returns:
            Updated project information
        """
        update_request: Dict[str, Any] = {}
        if display_name:
            update_request["display_name"] = display_name
        if description:
            update_request["description"] = description

        if not update_request:
            raise ValueError("At least one field must be provided for update")

        try:
            project = self.service.Project.update(
                project_rid=project_rid,
                body=update_request,
                preview=True,
            )
            return self._format_project_info(project)
        except Exception as e:
            raise RuntimeError(f"Failed to update project {project_rid}: {e}")

    def get_projects_batch(self, project_rids: List[str]) -> List[Dict[str, Any]]:
        """
        Get multiple projects in a single request.

        Args:
            project_rids: List of project RIDs (max 1000)

        Returns:
            List of project information dictionaries
        """
        if len(project_rids) > 1000:
            raise ValueError("Maximum batch size is 1000 projects")

        try:
            response = self.service.Project.get_batch(body=project_rids, preview=True)
            projects = []
            for project in response.projects:
                projects.append(self._format_project_info(project))
            return projects
        except Exception as e:
            raise RuntimeError(f"Failed to get projects batch: {e}")

    def _format_project_info(self, project: Any) -> Dict[str, Any]:
        """
        Format project information for consistent output.

        Args:
            project: Project object from Foundry SDK

        Returns:
            Formatted project information dictionary
        """
        return {
            "rid": getattr(project, "rid", None),
            "display_name": getattr(project, "display_name", None),
            "description": getattr(project, "description", None),
            "path": getattr(project, "path", None),
            "space_rid": getattr(project, "space_rid", None),
            "created_by": getattr(project, "created_by", None),
            "created_time": self._format_timestamp(
                getattr(project, "created_time", None)
            ),
            "modified_by": getattr(project, "modified_by", None),
            "modified_time": self._format_timestamp(
                getattr(project, "modified_time", None)
            ),
            "trash_status": getattr(project, "trash_status", None),
            "type": "project",
        }

    def _format_timestamp(self, timestamp: Any) -> Optional[str]:
        """
        Format timestamp for display.

        Args:
            timestamp: Timestamp object from SDK

        Returns:
            Formatted timestamp string or None
        """
        if timestamp is None:
            return None

        # Handle different timestamp formats from the SDK
        if hasattr(timestamp, "time"):
            return str(timestamp.time)
        return str(timestamp)
