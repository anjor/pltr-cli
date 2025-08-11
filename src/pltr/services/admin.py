"""
Admin service wrapper for Foundry SDK admin operations.
Provides a high-level interface for user, group, role, and organization management.
"""

from typing import Any, Dict, Optional
import json

from .base import BaseService


class AdminService(BaseService):
    """Service wrapper for Foundry admin operations."""

    def _get_service(self) -> Any:
        """Get the Foundry admin service."""
        return self.client.admin

    # User Management Methods
    def list_users(
        self, page_size: Optional[int] = None, page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List all users in the organization.

        Args:
            page_size: Maximum number of users to return per page
            page_token: Token for pagination (from previous response)

        Returns:
            Dictionary containing user list and pagination info
        """
        try:
            response = self.service.User.list(
                page_size=page_size, page_token=page_token
            )
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to list users: {str(e)}")

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get a specific user by ID.

        Args:
            user_id: The user ID or RID

        Returns:
            Dictionary containing user information
        """
        try:
            response = self.service.User.get(user_id)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get user {user_id}: {str(e)}")

    def get_current_user(self) -> Dict[str, Any]:
        """
        Get information about the current authenticated user.

        Returns:
            Dictionary containing current user information
        """
        try:
            response = self.service.User.get_current()
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get current user: {str(e)}")

    def search_users(
        self,
        query: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for users by query string.

        Args:
            query: Search query string
            page_size: Maximum number of users to return per page
            page_token: Token for pagination (from previous response)

        Returns:
            Dictionary containing search results and pagination info
        """
        try:
            response = self.service.User.search(
                query=query, page_size=page_size, page_token=page_token
            )
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to search users: {str(e)}")

    def get_user_markings(self, user_id: str) -> Dict[str, Any]:
        """
        Get markings/permissions for a specific user.

        Args:
            user_id: The user ID or RID

        Returns:
            Dictionary containing user markings information
        """
        try:
            response = self.service.User.get_markings(user_id)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get user markings for {user_id}: {str(e)}")

    def revoke_user_tokens(self, user_id: str) -> Dict[str, Any]:
        """
        Revoke all tokens for a specific user.

        Args:
            user_id: The user ID or RID

        Returns:
            Dictionary containing operation result
        """
        try:
            self.service.User.revoke_all_tokens(user_id)
            return {
                "success": True,
                "message": f"All tokens revoked for user {user_id}",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to revoke tokens for user {user_id}: {str(e)}")

    # Group Management Methods
    def list_groups(
        self, page_size: Optional[int] = None, page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List all groups in the organization.

        Args:
            page_size: Maximum number of groups to return per page
            page_token: Token for pagination (from previous response)

        Returns:
            Dictionary containing group list and pagination info
        """
        try:
            response = self.service.Group.list(
                page_size=page_size, page_token=page_token
            )
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to list groups: {str(e)}")

    def get_group(self, group_id: str) -> Dict[str, Any]:
        """
        Get a specific group by ID.

        Args:
            group_id: The group ID or RID

        Returns:
            Dictionary containing group information
        """
        try:
            response = self.service.Group.get(group_id)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get group {group_id}: {str(e)}")

    def search_groups(
        self,
        query: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for groups by query string.

        Args:
            query: Search query string
            page_size: Maximum number of groups to return per page
            page_token: Token for pagination (from previous response)

        Returns:
            Dictionary containing search results and pagination info
        """
        try:
            response = self.service.Group.search(
                query=query, page_size=page_size, page_token=page_token
            )
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to search groups: {str(e)}")

    def create_group(
        self,
        name: str,
        description: Optional[str] = None,
        organization_rid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new group.

        Args:
            name: The group name
            description: Optional group description
            organization_rid: Optional organization RID

        Returns:
            Dictionary containing created group information
        """
        try:
            # Build create request parameters
            create_params = {"name": name}
            if description:
                create_params["description"] = description
            if organization_rid:
                create_params["organization_rid"] = organization_rid

            response = self.service.Group.create(**create_params)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to create group '{name}': {str(e)}")

    def delete_group(self, group_id: str) -> Dict[str, Any]:
        """
        Delete a specific group.

        Args:
            group_id: The group ID or RID

        Returns:
            Dictionary containing operation result
        """
        try:
            self.service.Group.delete(group_id)
            return {
                "success": True,
                "message": f"Group {group_id} deleted successfully",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to delete group {group_id}: {str(e)}")

    # Organization Management Methods
    def get_organization(self, organization_id: str) -> Dict[str, Any]:
        """
        Get organization information.

        Args:
            organization_id: The organization ID or RID

        Returns:
            Dictionary containing organization information
        """
        try:
            response = self.service.Organization.get(organization_id)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get organization {organization_id}: {str(e)}"
            )

    # Role Management Methods
    def get_role(self, role_id: str) -> Dict[str, Any]:
        """
        Get role information.

        Args:
            role_id: The role ID or RID

        Returns:
            Dictionary containing role information
        """
        try:
            response = self.service.Role.get(role_id)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get role {role_id}: {str(e)}")

    def _serialize_response(self, response: Any) -> Dict[str, Any]:
        """
        Convert response object to serializable dictionary.

        Args:
            response: Response object from SDK

        Returns:
            Serializable dictionary representation
        """
        if response is None:
            return {}

        # Handle different response types
        if hasattr(response, "dict"):
            # Pydantic models
            return response.dict()
        elif hasattr(response, "__dict__"):
            # Regular objects
            result = {}
            for key, value in response.__dict__.items():
                if not key.startswith("_"):
                    try:
                        # Try to serialize the value
                        json.dumps(value)
                        result[key] = value
                    except (TypeError, ValueError):
                        # Convert non-serializable values to string
                        result[key] = str(value)
            return result
        else:
            # Primitive types or already serializable
            try:
                json.dumps(response)
                return response
            except (TypeError, ValueError):
                return {"data": str(response)}
