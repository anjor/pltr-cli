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
        organization_rid: str,
        description: Optional[str] = None,
        default_roles: Optional[List[str]] = None,
        role_grants: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new space.

        Args:
            display_name: Space display name
            organization_rid: Organization Resource Identifier
            description: Space description (optional)
            default_roles: List of default role names (optional)
            role_grants: List of role grant specifications (optional)

        Returns:
            Created space information
        """
        try:
            # Prepare the create request payload
            create_request: Dict[str, Any] = {
                "display_name": display_name,
                "organization_rid": organization_rid,
            }

            if description:
                create_request["description"] = description
            if default_roles:
                create_request["default_roles"] = default_roles
            if role_grants:
                create_request["role_grants"] = role_grants

            space = self.service.Space.create(
                body=create_request,
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
        Update space information.

        Args:
            space_rid: Space Resource Identifier
            display_name: New display name (optional)
            description: New description (optional)

        Returns:
            Updated space information
        """
        update_request: Dict[str, Any] = {}
        if display_name:
            update_request["display_name"] = display_name
        if description:
            update_request["description"] = description

        if not update_request:
            raise ValueError("At least one field must be provided for update")

        try:
            space = self.service.Space.update(
                space_rid=space_rid,
                body=update_request,
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

    def get_spaces_batch(self, space_rids: List[str]) -> List[Dict[str, Any]]:
        """
        Get multiple spaces in a single request.

        Args:
            space_rids: List of space RIDs (max 1000)

        Returns:
            List of space information dictionaries
        """
        if len(space_rids) > 1000:
            raise ValueError("Maximum batch size is 1000 spaces")

        try:
            response = self.service.Space.get_batch(body=space_rids, preview=True)
            spaces = []
            for space in response.spaces:
                spaces.append(self._format_space_info(space))
            return spaces
        except Exception as e:
            raise RuntimeError(f"Failed to get spaces batch: {e}")

    def get_space_members(
        self,
        space_rid: str,
        principal_type: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all members (users/groups) of a space.

        Args:
            space_rid: Space Resource Identifier
            principal_type: Filter by principal type ('User' or 'Group', optional)
            page_size: Number of items per page (optional)
            page_token: Pagination token (optional)

        Returns:
            List of space member information dictionaries
        """
        try:
            members = []
            list_params: Dict[str, Any] = {"preview": True}

            if principal_type:
                list_params["principal_type"] = principal_type
            if page_size:
                list_params["page_size"] = page_size
            if page_token:
                list_params["page_token"] = page_token

            # The get_members method returns an iterator
            for member in self.service.Space.get_members(space_rid, **list_params):
                members.append(self._format_member_info(member))
            return members
        except Exception as e:
            raise RuntimeError(f"Failed to get members for space {space_rid}: {e}")

    def add_space_member(
        self,
        space_rid: str,
        principal_id: str,
        principal_type: str,
        role_name: str,
    ) -> Dict[str, Any]:
        """
        Add a member to a space with a specific role.

        Args:
            space_rid: Space Resource Identifier
            principal_id: Principal (user/group) identifier
            principal_type: Principal type ('User' or 'Group')
            role_name: Role name to grant

        Returns:
            Space member information
        """
        try:
            member_request: Dict[str, Any] = {
                "principal_id": principal_id,
                "principal_type": principal_type,
                "role_name": role_name,
            }

            result = self.service.Space.add_member(
                space_rid=space_rid,
                body=member_request,
                preview=True,
            )
            return self._format_member_info(result)
        except Exception as e:
            raise RuntimeError(
                f"Failed to add {principal_type} '{principal_id}' to space {space_rid}: {e}"
            )

    def remove_space_member(
        self,
        space_rid: str,
        principal_id: str,
        principal_type: str,
    ) -> None:
        """
        Remove a member from a space.

        Args:
            space_rid: Space Resource Identifier
            principal_id: Principal (user/group) identifier
            principal_type: Principal type ('User' or 'Group')

        Raises:
            RuntimeError: If removal fails
        """
        try:
            member_removal: Dict[str, Any] = {
                "principal_id": principal_id,
                "principal_type": principal_type,
            }

            self.service.Space.remove_member(
                space_rid=space_rid,
                body=member_removal,
                preview=True,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to remove {principal_type} '{principal_id}' from space {space_rid}: {e}"
            )

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

    def _format_member_info(self, member: Any) -> Dict[str, Any]:
        """
        Format space member information for consistent output.

        Args:
            member: Member object from Foundry SDK

        Returns:
            Formatted member information dictionary
        """
        return {
            "space_rid": getattr(member, "space_rid", None),
            "principal_id": getattr(member, "principal_id", None),
            "principal_type": getattr(member, "principal_type", None),
            "role_name": getattr(member, "role_name", None),
            "added_by": getattr(member, "added_by", None),
            "added_time": self._format_timestamp(getattr(member, "added_time", None)),
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
