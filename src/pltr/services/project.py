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
            project = self.service.Project.create(
                display_name=display_name,
                space_rid=space_rid,
                description=description,
                organization_rids=organization_rids if organization_rids else [],
                default_roles=default_roles if default_roles else [],
                role_grants=role_grants if role_grants else [],
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
        Update project information using replace().

        Args:
            project_rid: Project Resource Identifier
            display_name: New display name (optional, fetches current if not provided)
            description: New description (optional)

        Returns:
            Updated project information
        """
        if not display_name and not description:
            raise ValueError("At least one field must be provided for update")

        try:
            # Fetch current project to get display_name if not provided (required for replace)
            if not display_name:
                current_project = self.service.Project.get(project_rid, preview=True)
                display_name = current_project.display_name

            project = self.service.Project.replace(
                project_rid=project_rid,
                display_name=display_name,
                description=description,
                preview=True,
            )
            return self._format_project_info(project)
        except Exception as e:
            raise RuntimeError(f"Failed to update project {project_rid}: {e}")

    # ==================== Organization Operations ====================

    def add_organizations(self, project_rid: str, organization_rids: List[str]) -> None:
        """
        Add organizations to a project.

        Args:
            project_rid: Project Resource Identifier
            organization_rids: List of organization RIDs to add

        Raises:
            RuntimeError: If adding organizations fails
        """
        try:
            self.service.Project.add_organizations(
                project_rid, organization_rids=organization_rids, preview=True
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to add organizations to project {project_rid}: {e}"
            )

    def remove_organizations(
        self, project_rid: str, organization_rids: List[str]
    ) -> None:
        """
        Remove organizations from a project.

        Args:
            project_rid: Project Resource Identifier
            organization_rids: List of organization RIDs to remove

        Raises:
            RuntimeError: If removing organizations fails
        """
        try:
            self.service.Project.remove_organizations(
                project_rid, organization_rids=organization_rids, preview=True
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to remove organizations from project {project_rid}: {e}"
            )

    def list_organizations(
        self,
        project_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List organizations directly applied to a project.

        Args:
            project_rid: Project Resource Identifier
            page_size: Number of items per page (optional)
            page_token: Pagination token (optional)

        Returns:
            List of organization information dictionaries
        """
        try:
            organizations = []
            list_params: Dict[str, Any] = {"preview": True}

            if page_size:
                list_params["page_size"] = page_size
            if page_token:
                list_params["page_token"] = page_token

            for org in self.service.Project.organizations(project_rid, **list_params):
                organizations.append(self._format_organization_info(org))
            return organizations
        except Exception as e:
            raise RuntimeError(
                f"Failed to list organizations for project {project_rid}: {e}"
            )

    # ==================== Template Operations ====================

    def create_project_from_template(
        self,
        template_rid: str,
        variable_values: Dict[str, str],
        default_roles: Optional[List[str]] = None,
        organization_rids: Optional[List[str]] = None,
        project_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a project from a template.

        Args:
            template_rid: Template Resource Identifier
            variable_values: Dictionary mapping template variable names to values
            default_roles: List of default role names (optional)
            organization_rids: List of organization RIDs (optional)
            project_description: Project description (optional)

        Returns:
            Created project information
        """
        try:
            create_params: Dict[str, Any] = {
                "template_rid": template_rid,
                "variable_values": variable_values,
                "preview": True,
            }

            if default_roles:
                create_params["default_roles"] = default_roles
            if organization_rids:
                create_params["organization_rids"] = organization_rids
            if project_description:
                create_params["project_description"] = project_description

            project = self.service.Project.create_from_template(**create_params)
            return self._format_project_info(project)
        except Exception as e:
            raise RuntimeError(f"Failed to create project from template: {e}")

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

    def _format_organization_info(self, organization: Any) -> Dict[str, Any]:
        """
        Format organization information for consistent output.

        Args:
            organization: Organization object from Foundry SDK

        Returns:
            Formatted organization information dictionary
        """
        return {
            "organization_rid": getattr(organization, "organization_rid", None),
            "display_name": getattr(organization, "display_name", None),
            "description": getattr(organization, "description", None),
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
