"""
Admin service wrapper for Foundry SDK admin operations.
Provides a high-level interface for user, group, role, and organization management.
"""

from typing import Any, Dict, List, Optional, Callable
import json

from .base import BaseService
from ..utils.pagination import PaginationConfig, PaginationResult
from ..config.settings import Settings


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

        DEPRECATED: Use list_users_paginated() instead for better pagination support.

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

    def list_users_paginated(
        self,
        config: PaginationConfig,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> PaginationResult:
        """
        List users with full pagination control.

        Args:
            config: Pagination configuration (page_size, max_pages, etc.)
            progress_callback: Optional callback(page_num, items_count)

        Returns:
            PaginationResult with users and metadata

        Example:
            >>> config = PaginationConfig(page_size=50, max_pages=2)
            >>> result = service.list_users_paginated(config)
            >>> print(f"Fetched {result.metadata.items_fetched} users")
        """
        try:
            settings = Settings()

            def fetch_page(page_token: Optional[str]) -> Dict[str, Any]:
                """Fetch a single page of users."""
                response = self.service.User.list(
                    page_size=config.page_size or settings.get("page_size", 20),
                    page_token=page_token,
                )
                return self._serialize_response(response)

            # Use response pagination handler
            return self._paginate_response(fetch_page, config, progress_callback)
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

    def delete_user(self, user_id: str) -> Dict[str, Any]:
        """
        Delete a specific user.

        Args:
            user_id: The user ID or RID

        Returns:
            Dictionary containing operation result
        """
        try:
            self.service.User.delete(user_id)
            return {
                "success": True,
                "message": f"User {user_id} deleted successfully",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to delete user {user_id}: {str(e)}")

    def get_batch_users(self, user_ids: List[str]) -> Dict[str, Any]:
        """
        Batch retrieve multiple users (up to 500).

        Args:
            user_ids: List of user IDs or RIDs

        Returns:
            Dictionary containing user information
        """
        if len(user_ids) > 500:
            raise ValueError("Maximum batch size is 500 users")
        try:
            response = self.service.User.get_batch(body=user_ids)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get users batch: {str(e)}")

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

    def get_batch_groups(self, group_ids: List[str]) -> Dict[str, Any]:
        """
        Batch retrieve multiple groups (up to 500).

        Args:
            group_ids: List of group IDs or RIDs

        Returns:
            Dictionary containing group information
        """
        if len(group_ids) > 500:
            raise ValueError("Maximum batch size is 500 groups")
        try:
            response = self.service.Group.get_batch(body=group_ids)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get groups batch: {str(e)}")

    # Marking Management Methods
    def list_markings(
        self, page_size: Optional[int] = None, page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List all markings.

        Args:
            page_size: Maximum number of markings to return per page
            page_token: Token for pagination (from previous response)

        Returns:
            Dictionary containing marking list and pagination info
        """
        try:
            response = self.service.Marking.list(
                page_size=page_size, page_token=page_token, preview=True
            )
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to list markings: {str(e)}")

    def get_marking(self, marking_id: str) -> Dict[str, Any]:
        """
        Get a specific marking by ID.

        Args:
            marking_id: The marking ID

        Returns:
            Dictionary containing marking information
        """
        try:
            response = self.service.Marking.get(marking_id, preview=True)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get marking {marking_id}: {str(e)}")

    def get_batch_markings(self, marking_ids: List[str]) -> Dict[str, Any]:
        """
        Batch retrieve multiple markings (up to 500).

        Args:
            marking_ids: List of marking IDs

        Returns:
            Dictionary containing marking information
        """
        if len(marking_ids) > 500:
            raise ValueError("Maximum batch size is 500 markings")
        try:
            response = self.service.Marking.get_batch(body=marking_ids, preview=True)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get markings batch: {str(e)}")

    def create_marking(
        self,
        name: str,
        description: Optional[str] = None,
        category_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new marking.

        Args:
            name: The marking name
            description: Optional marking description
            category_id: Optional category ID for the marking

        Returns:
            Dictionary containing created marking information
        """
        try:
            create_params: Dict[str, Any] = {"name": name, "preview": True}
            if description:
                create_params["description"] = description
            if category_id:
                create_params["category_id"] = category_id

            response = self.service.Marking.create(**create_params)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to create marking '{name}': {str(e)}")

    def replace_marking(
        self,
        marking_id: str,
        name: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Replace/update an existing marking.

        Args:
            marking_id: The marking ID
            name: The new marking name
            description: Optional new marking description

        Returns:
            Dictionary containing updated marking information
        """
        try:
            replace_params: Dict[str, Any] = {"name": name, "preview": True}
            if description:
                replace_params["description"] = description

            response = self.service.Marking.replace(marking_id, **replace_params)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to replace marking {marking_id}: {str(e)}")

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

    def create_organization(
        self,
        name: str,
        enrollment_rid: str,
        admin_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new organization.

        Args:
            name: The organization name
            enrollment_rid: The enrollment RID
            admin_ids: Optional list of admin user IDs

        Returns:
            Dictionary containing created organization information
        """
        try:
            create_params: Dict[str, Any] = {
                "name": name,
                "enrollment_rid": enrollment_rid,
                "preview": True,
            }
            if admin_ids:
                create_params["admin_ids"] = admin_ids

            response = self.service.Organization.create(**create_params)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to create organization '{name}': {str(e)}")

    def replace_organization(
        self,
        organization_rid: str,
        name: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Replace/update an existing organization.

        Args:
            organization_rid: The organization RID
            name: The new organization name
            description: Optional new organization description

        Returns:
            Dictionary containing updated organization information
        """
        try:
            replace_params: Dict[str, Any] = {"name": name, "preview": True}
            if description:
                replace_params["description"] = description

            response = self.service.Organization.replace(
                organization_rid, **replace_params
            )
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(
                f"Failed to replace organization {organization_rid}: {str(e)}"
            )

    def list_available_roles(
        self,
        organization_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List available roles for an organization.

        Args:
            organization_rid: The organization RID
            page_size: Maximum number of roles to return per page
            page_token: Token for pagination (from previous response)

        Returns:
            Dictionary containing role list and pagination info
        """
        try:
            response = self.service.Organization.list_available_roles(
                organization_rid,
                page_size=page_size,
                page_token=page_token,
                preview=True,
            )
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(
                f"Failed to list available roles for organization {organization_rid}: {str(e)}"
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

    def get_batch_roles(self, role_ids: List[str]) -> Dict[str, Any]:
        """
        Batch retrieve multiple roles (up to 500).

        Args:
            role_ids: List of role IDs or RIDs

        Returns:
            Dictionary containing role information
        """
        if len(role_ids) > 500:
            raise ValueError("Maximum batch size is 500 roles")
        try:
            response = self.service.Role.get_batch(body=role_ids, preview=True)
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get roles batch: {str(e)}")

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
