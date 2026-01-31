"""
Space service wrapper for Foundry SDK filesystem API.
"""

from typing import Any, Optional, Dict, List

from .base import BaseService


class SpaceService(BaseService):
    """Service wrapper for Foundry space operations using filesystem API."""

    def _get_service(self) -> Any:
        """Get the Foundry filesystem service."""
        return self.client.filesystem

    def create_space(
        self,
        display_name: str,
        enrollment_rid: str,
        organizations: List[str],
        deletion_policy_organizations: List[str],
        description: Optional[str] = None,
        default_roles: Optional[List[str]] = None,
        role_grants: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new space.

        Args:
            display_name: Space display name
            enrollment_rid: Enrollment Resource Identifier
            organizations: List of organization RIDs
            deletion_policy_organizations: List of organization RIDs for deletion policy
            description: Space description (optional)
            default_roles: List of default role names (optional)
            role_grants: List of role grant specifications (optional)

        Returns:
            Created space information
        """
        try:
            space = self.service.Space.create(
                display_name=display_name,
                enrollment_rid=enrollment_rid,
                organizations=organizations,
                deletion_policy_organizations=deletion_policy_organizations,
                description=description,
                default_roles=default_roles if default_roles else [],
                role_grants=role_grants if role_grants else [],
                preview=True,
            )
            return self._format_space_info(space)
        except Exception as e:
            raise RuntimeError(f"Failed to create space '{display_name}': {e}")

    def get_space(self, space_rid: str) -> Dict[str, Any]:
        """
        Get information about a specific space.

        Args:
            space_rid: Space Resource Identifier

        Returns:
            Space information dictionary
        """
        try:
            space = self.service.Space.get(space_rid, preview=True)
            return self._format_space_info(space)
        except Exception as e:
            raise RuntimeError(f"Failed to get space {space_rid}: {e}")

    def list_spaces(
        self,
        organization_rid: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List spaces, optionally filtered by organization.

        Args:
            organization_rid: Organization Resource Identifier to filter by (optional)
            page_size: Number of items per page (optional)
            page_token: Pagination token (optional)

        Returns:
            List of space information dictionaries
        """
        try:
            spaces = []
            list_params: Dict[str, Any] = {"preview": True}

            if organization_rid:
                list_params["organization_rid"] = organization_rid
            if page_size:
                list_params["page_size"] = page_size
            if page_token:
                list_params["page_token"] = page_token

            # The list method returns an iterator
            for space in self.service.Space.list(**list_params):
                spaces.append(self._format_space_info(space))
            return spaces
        except Exception as e:
            raise RuntimeError(f"Failed to list spaces: {e}")

    def update_space(
        self,
        space_rid: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update space information using replace().

        Args:
            space_rid: Space Resource Identifier
            display_name: New display name (optional, fetches current if not provided)
            description: New description (optional)

        Returns:
            Updated space information
        """
        if not display_name and not description:
            raise ValueError("At least one field must be provided for update")

        try:
            # Fetch current space to get display_name if not provided (required for replace)
            if not display_name:
                current_space = self.service.Space.get(space_rid, preview=True)
                display_name = current_space.display_name

            space = self.service.Space.replace(
                space_rid=space_rid,
                display_name=display_name,
                description=description,
                preview=True,
            )
            return self._format_space_info(space)
        except Exception as e:
            raise RuntimeError(f"Failed to update space {space_rid}: {e}")

    def delete_space(self, space_rid: str) -> None:
        """
        Delete a space.

        Args:
            space_rid: Space Resource Identifier

        Raises:
            RuntimeError: If deletion fails
        """
        try:
            self.service.Space.delete(space_rid, preview=True)
        except Exception as e:
            raise RuntimeError(f"Failed to delete space {space_rid}: {e}")

    def _format_space_info(self, space: Any) -> Dict[str, Any]:
        """
        Format space information for consistent output.

        Args:
            space: Space object from Foundry SDK

        Returns:
            Formatted space information dictionary
        """
        return {
            "rid": getattr(space, "rid", None),
            "display_name": getattr(space, "display_name", None),
            "description": getattr(space, "description", None),
            "organization_rid": getattr(space, "organization_rid", None),
            "root_folder_rid": getattr(space, "root_folder_rid", None),
            "created_by": getattr(space, "created_by", None),
            "created_time": self._format_timestamp(
                getattr(space, "created_time", None)
            ),
            "modified_by": getattr(space, "modified_by", None),
            "modified_time": self._format_timestamp(
                getattr(space, "modified_time", None)
            ),
            "trash_status": getattr(space, "trash_status", None),
            "type": "space",
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
