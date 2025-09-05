"""
Resource Role service wrapper for Foundry SDK filesystem API.
"""

from typing import Any, Optional, Dict, List

from .base import BaseService


class ResourceRoleService(BaseService):
    """Service wrapper for Foundry resource role operations using filesystem API."""

    def _get_service(self) -> Any:
        """Get the Foundry filesystem service."""
        return self.client.filesystem

    def grant_role(
        self,
        resource_rid: str,
        principal_id: str,
        principal_type: str,
        role_name: str,
    ) -> Dict[str, Any]:
        """
        Grant a role to a principal on a resource.

        Args:
            resource_rid: Resource Identifier
            principal_id: Principal (user/group) identifier
            principal_type: Principal type ('User' or 'Group')
            role_name: Role name to grant

        Returns:
            Role grant information
        """
        try:
            role_grant: Dict[str, Any] = {
                "principal_id": principal_id,
                "principal_type": principal_type,
                "role_name": role_name,
            }

            result = self.service.ResourceRole.grant(
                resource_rid=resource_rid,
                body=role_grant,
                preview=True,
            )
            return self._format_role_grant(result)
        except Exception as e:
            raise RuntimeError(
                f"Failed to grant role '{role_name}' to {principal_type} '{principal_id}' on resource {resource_rid}: {e}"
            )

    def revoke_role(
        self,
        resource_rid: str,
        principal_id: str,
        principal_type: str,
        role_name: str,
    ) -> None:
        """
        Revoke a role from a principal on a resource.

        Args:
            resource_rid: Resource Identifier
            principal_id: Principal (user/group) identifier
            principal_type: Principal type ('User' or 'Group')
            role_name: Role name to revoke

        Raises:
            RuntimeError: If revocation fails
        """
        try:
            role_revocation: Dict[str, Any] = {
                "principal_id": principal_id,
                "principal_type": principal_type,
                "role_name": role_name,
            }

            self.service.ResourceRole.revoke(
                resource_rid=resource_rid,
                body=role_revocation,
                preview=True,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to revoke role '{role_name}' from {principal_type} '{principal_id}' on resource {resource_rid}: {e}"
            )

    def list_resource_roles(
        self,
        resource_rid: str,
        principal_type: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all roles granted on a resource.

        Args:
            resource_rid: Resource Identifier
            principal_type: Filter by principal type ('User' or 'Group', optional)
            page_size: Number of items per page (optional)
            page_token: Pagination token (optional)

        Returns:
            List of role grant information dictionaries
        """
        try:
            role_grants = []
            list_params: Dict[str, Any] = {"preview": True}

            if principal_type:
                list_params["principal_type"] = principal_type
            if page_size:
                list_params["page_size"] = page_size
            if page_token:
                list_params["page_token"] = page_token

            # The list method returns an iterator
            for role_grant in self.service.ResourceRole.list(
                resource_rid, **list_params
            ):
                role_grants.append(self._format_role_grant(role_grant))
            return role_grants
        except Exception as e:
            raise RuntimeError(f"Failed to list roles for resource {resource_rid}: {e}")

    def get_principal_roles(
        self,
        principal_id: str,
        principal_type: str,
        resource_rid: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all roles granted to a principal, optionally filtered by resource.

        Args:
            principal_id: Principal (user/group) identifier
            principal_type: Principal type ('User' or 'Group')
            resource_rid: Filter by resource RID (optional)
            page_size: Number of items per page (optional)
            page_token: Pagination token (optional)

        Returns:
            List of role grant information dictionaries
        """
        try:
            role_grants = []
            list_params = {
                "principal_id": principal_id,
                "principal_type": principal_type,
                "preview": True,
            }

            if resource_rid:
                list_params["resource_rid"] = resource_rid
            if page_size:
                list_params["page_size"] = page_size
            if page_token:
                list_params["page_token"] = page_token

            # The get_principal_roles method returns an iterator
            for role_grant in self.service.ResourceRole.get_principal_roles(
                **list_params
            ):
                role_grants.append(self._format_role_grant(role_grant))
            return role_grants
        except Exception as e:
            raise RuntimeError(
                f"Failed to get roles for {principal_type} '{principal_id}': {e}"
            )

    def bulk_grant_roles(
        self,
        resource_rid: str,
        role_grants: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        Grant multiple roles in a single request.

        Args:
            resource_rid: Resource Identifier
            role_grants: List of role grant specifications, each containing:
                        - principal_id: Principal identifier
                        - principal_type: 'User' or 'Group'
                        - role_name: Role name to grant

        Returns:
            List of granted role information dictionaries
        """
        try:
            result = self.service.ResourceRole.bulk_grant(
                resource_rid=resource_rid,
                body={"role_grants": role_grants},
                preview=True,
            )

            granted_roles = []
            if hasattr(result, "role_grants"):
                for role_grant in result.role_grants:
                    granted_roles.append(self._format_role_grant(role_grant))

            return granted_roles
        except Exception as e:
            raise RuntimeError(
                f"Failed to bulk grant roles on resource {resource_rid}: {e}"
            )

    def bulk_revoke_roles(
        self,
        resource_rid: str,
        role_revocations: List[Dict[str, str]],
    ) -> None:
        """
        Revoke multiple roles in a single request.

        Args:
            resource_rid: Resource Identifier
            role_revocations: List of role revocation specifications, each containing:
                            - principal_id: Principal identifier
                            - principal_type: 'User' or 'Group'
                            - role_name: Role name to revoke

        Raises:
            RuntimeError: If revocation fails
        """
        try:
            self.service.ResourceRole.bulk_revoke(
                resource_rid=resource_rid,
                body={"role_revocations": role_revocations},
                preview=True,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to bulk revoke roles on resource {resource_rid}: {e}"
            )

    def get_available_roles(self, resource_rid: str) -> List[Dict[str, Any]]:
        """
        Get all available roles for a resource type.

        Args:
            resource_rid: Resource Identifier

        Returns:
            List of available role information dictionaries
        """
        try:
            roles = []
            for role in self.service.ResourceRole.get_available_roles(
                resource_rid, preview=True
            ):
                roles.append(self._format_role_info(role))
            return roles
        except Exception as e:
            raise RuntimeError(
                f"Failed to get available roles for resource {resource_rid}: {e}"
            )

    def _format_role_grant(self, role_grant: Any) -> Dict[str, Any]:
        """
        Format role grant information for consistent output.

        Args:
            role_grant: Role grant object from Foundry SDK

        Returns:
            Formatted role grant information dictionary
        """
        return {
            "resource_rid": getattr(role_grant, "resource_rid", None),
            "principal_id": getattr(role_grant, "principal_id", None),
            "principal_type": getattr(role_grant, "principal_type", None),
            "role_name": getattr(role_grant, "role_name", None),
            "granted_by": getattr(role_grant, "granted_by", None),
            "granted_time": self._format_timestamp(
                getattr(role_grant, "granted_time", None)
            ),
            "expires_at": self._format_timestamp(
                getattr(role_grant, "expires_at", None)
            ),
        }

    def _format_role_info(self, role: Any) -> Dict[str, Any]:
        """
        Format role information for consistent output.

        Args:
            role: Role object from Foundry SDK

        Returns:
            Formatted role information dictionary
        """
        return {
            "name": getattr(role, "name", None),
            "display_name": getattr(role, "display_name", None),
            "description": getattr(role, "description", None),
            "permissions": getattr(role, "permissions", []),
            "is_owner_like": getattr(role, "is_owner_like", False),
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
