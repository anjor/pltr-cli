"""
Resource role service wrapper for the Foundry SDK filesystem API.

Role grants on a resource are managed with ``Resource.Role.add``,
``Resource.Role.remove`` and ``Resource.Role.list`` (all GA). Methods return
SDK models (or SDK iterators) unchanged and let SDK exceptions propagate so
the error layer can classify them.
"""

from typing import Any, Optional

from foundry_sdk.v2.filesystem.models import (
    Everyone,
    PrincipalIdOnly,
    ResourceRoleIdentifier,
)

from .base import BaseService


def role_identifier(role_id: str, principal_id: Optional[str]) -> Any:
    """The ``ResourceRoleIdentifier`` for granting/revoking ``role_id``.

    ``principal_id`` is a user or group ID (a UUID); ``None`` means the
    ``Everyone`` principal. Add/remove calls don't take the principal type.
    """
    principal: Any = (
        Everyone()
        if principal_id is None
        else PrincipalIdOnly(principal_id=principal_id)
    )
    return ResourceRoleIdentifier(resource_role_principal=principal, role_id=role_id)


class ResourceRoleService(BaseService):
    """Service wrapper for role grants on Foundry resources (``client.filesystem``)."""

    def _get_service(self) -> Any:
        """Get the Foundry filesystem service."""
        return self.client.filesystem

    def grant_role(
        self, resource_rid: str, role_id: str, principal_id: Optional[str] = None
    ) -> None:
        """Grant a role on a resource (``Resource.Role.add``, GA).

        Args:
            resource_rid: RID of the resource (a project, folder, dataset, ...)
            role_id: ID of the role to grant
            principal_id: user or group ID (UUID); ``None`` grants the role
                to everyone
        """
        self.service.Resource.Role.add(
            resource_rid, roles=[role_identifier(role_id, principal_id)]
        )

    def revoke_role(
        self, resource_rid: str, role_id: str, principal_id: Optional[str] = None
    ) -> None:
        """Revoke a role on a resource (``Resource.Role.remove``, GA).

        Args are the same as :meth:`grant_role`.
        """
        self.service.Resource.Role.remove(
            resource_rid, roles=[role_identifier(role_id, principal_id)]
        )

    def list_roles(
        self,
        resource_rid: str,
        include_inherited: Optional[bool] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of the role grants on a resource (``Resource.Role.list``, GA).

        Returns:
            The SDK ``ResourceIterator[ResourceRole]``. Constructing it fetched
            exactly one page: read ``.data`` and ``.next_page_token``.
        """
        return self.service.Resource.Role.list(
            resource_rid,
            include_inherited=include_inherited,
            page_size=page_size,
            page_token=page_token,
        )
