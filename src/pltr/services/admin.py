"""
Admin service wrapper for the Foundry SDK admin API (``client.admin``):
users, groups, roles, organizations and markings.

Methods return SDK models, SDK iterators and SDK responses unchanged and let
SDK exceptions propagate, so the error layer can classify them. GA endpoints
are called without ``preview``; the beta ones (``Role.get``,
``Role.get_batch`` and ``Organization.create``) always get ``preview=True``.

Users and groups are identified by ID (a UUID), organizations by RID
(``ri.multipass..organization.<uuid>``), and markings and roles by ID.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

from .base import BaseService

if TYPE_CHECKING:
    from foundry_sdk.v2.admin.models import MarkingRole

# The SDK's admin request models are imported inside the methods that build
# them: importing foundry_sdk.v2.admin.models at module level would slow down
# every pltr invocation, not just admin commands.

#: Maximum number of IDs one ``get_batch`` request accepts (users, groups,
#: markings and roles).
MAX_BATCH_SIZE = 500


def _check_batch_size(ids: Sequence[str], kind: str) -> None:
    if len(ids) > MAX_BATCH_SIZE:
        raise ValueError(f"Maximum batch size is {MAX_BATCH_SIZE} {kind}")


class AdminService(BaseService):
    """Service wrapper for Foundry admin operations (``client.admin``)."""

    def _get_service(self) -> Any:
        """Get the Foundry admin service."""
        return self.client.admin

    # ------------------------------------------------------------------ users

    def list_users(
        self, page_size: Optional[int] = None, page_token: Optional[str] = None
    ) -> Any:
        """List one page of users (``User.list``, GA).

        Returns:
            The SDK ``ResourceIterator[User]``; constructing it fetched one
            page (``.data``, ``.next_page_token``).
        """
        return self.service.User.list(page_size=page_size, page_token=page_token)

    def get_user(self, user_id: str) -> Any:
        """Get a user by ID (``User.get``, GA); returns a ``User`` model."""
        return self.service.User.get(user_id)

    def current_user(self) -> Any:
        """Get the authenticated user (``User.get_current``, GA); returns a
        ``User`` model."""
        return self.service.User.get_current()

    def get_current_user(self) -> Dict[str, Any]:
        """The authenticated user as the SDK's dict serialization.

        ``User.to_dict()``: API field names (``id``, ``username``,
        ``givenName``, ...) with null fields left out. ``ProjectService``
        reads the user's ``"id"`` from it; commands use :meth:`current_user`.
        """
        return self.current_user().to_dict()

    def search_users(
        self,
        query: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """Search active users (``User.search``, GA).

        The API does a case-insensitive prefix match of ``query`` against
        usernames, given names and family names.

        Returns:
            One page: a ``SearchUsersResponse`` (``.data``,
            ``.next_page_token``).
        """
        from foundry_sdk.v2.admin.models import UserSearchFilter

        return self.service.User.search(
            where=UserSearchFilter(type="queryString", value=query),
            page_size=page_size,
            page_token=page_token,
        )

    def get_user_markings(self, user_id: str) -> Any:
        """Get the markings a user can access (``User.get_markings``, GA).

        Returns:
            ``GetUserMarkingsResponse``; ``view`` lists the marking IDs.
        """
        return self.service.User.get_markings(user_id)

    def revoke_user_tokens(self, user_id: str) -> None:
        """Invalidate all of a user's tokens and sessions
        (``User.revoke_all_tokens``, GA)."""
        self.service.User.revoke_all_tokens(user_id)

    def delete_user(self, user_id: str) -> None:
        """Delete a user (``User.delete``, GA)."""
        self.service.User.delete(user_id)

    def get_batch_users(self, user_ids: List[str]) -> Any:
        """Get up to 500 users in one request (``User.get_batch``, GA).

        Returns:
            ``GetUsersBatchResponse``; its ``data`` maps user ID to ``User``.
        """
        from foundry_sdk.v2.admin.models import GetUsersBatchRequestElement

        _check_batch_size(user_ids, "users")
        return self.service.User.get_batch(
            body=[GetUsersBatchRequestElement(user_id=user_id) for user_id in user_ids]
        )

    # ----------------------------------------------------------------- groups

    def list_groups(
        self, page_size: Optional[int] = None, page_token: Optional[str] = None
    ) -> Any:
        """List one page of groups (``Group.list``, GA).

        Returns:
            The SDK ``ResourceIterator[Group]``; constructing it fetched one
            page (``.data``, ``.next_page_token``).
        """
        return self.service.Group.list(page_size=page_size, page_token=page_token)

    def get_group(self, group_id: str) -> Any:
        """Get a group by ID (``Group.get``, GA); returns a ``Group`` model."""
        return self.service.Group.get(group_id)

    def search_groups(
        self,
        query: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """Search groups (``Group.search``, GA).

        The API does a case-insensitive prefix match of ``query`` against
        group names.

        Returns:
            One page: a ``SearchGroupsResponse`` (``.data``,
            ``.next_page_token``).
        """
        from foundry_sdk.v2.admin.models import GroupSearchFilter

        return self.service.Group.search(
            where=GroupSearchFilter(type="queryString", value=query),
            page_size=page_size,
            page_token=page_token,
        )

    def create_group(
        self,
        *,
        name: str,
        organizations: List[str],
        attributes: Dict[str, List[str]],
        description: Optional[str] = None,
    ) -> Any:
        """Create a group (``Group.create``, GA); returns a ``Group`` model.

        Args:
            name: Group name.
            organizations: RIDs of the organizations whose members can see the
                group (at least one).
            attributes: Group attributes (attribute name to values); may be
                empty.
            description: Optional description.
        """
        return self.service.Group.create(
            name=name,
            organizations=organizations,
            attributes=attributes,
            description=description,
        )

    def delete_group(self, group_id: str) -> None:
        """Delete a group (``Group.delete``, GA)."""
        self.service.Group.delete(group_id)

    def get_batch_groups(self, group_ids: List[str]) -> Any:
        """Get up to 500 groups in one request (``Group.get_batch``, GA).

        Returns:
            ``GetGroupsBatchResponse``; its ``data`` maps group ID to ``Group``.
        """
        from foundry_sdk.v2.admin.models import GetGroupsBatchRequestElement

        _check_batch_size(group_ids, "groups")
        return self.service.Group.get_batch(
            body=[
                GetGroupsBatchRequestElement(group_id=group_id)
                for group_id in group_ids
            ]
        )

    # --------------------------------------------------------------- markings

    def list_markings(
        self,
        *,
        include_deleted: Optional[bool] = None,
        marking_type: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of markings (``Marking.list``, GA).

        Args:
            include_deleted: Include deleted markings (the API includes them
                when this is left out).
            marking_type: ``MANDATORY`` or ``CBAC`` (all types when left out).

        Returns:
            The SDK ``ResourceIterator[Marking]``; constructing it fetched one
            page (``.data``, ``.next_page_token``).
        """
        return self.service.Marking.list(
            include_deleted=include_deleted,
            marking_type=marking_type,
            page_size=page_size,
            page_token=page_token,
        )

    def get_marking(self, marking_id: str) -> Any:
        """Get a marking by ID (``Marking.get``, GA); returns a ``Marking``."""
        return self.service.Marking.get(marking_id)

    def get_batch_markings(self, marking_ids: List[str]) -> Any:
        """Get up to 500 markings in one request (``Marking.get_batch``, GA).

        Returns:
            ``GetMarkingsBatchResponse``; its ``data`` maps marking ID to
            ``Marking``.
        """
        from foundry_sdk.v2.admin.models import GetMarkingsBatchRequestElement

        _check_batch_size(marking_ids, "markings")
        return self.service.Marking.get_batch(
            body=[
                GetMarkingsBatchRequestElement(marking_id=marking_id)
                for marking_id in marking_ids
            ]
        )

    def create_marking(
        self,
        *,
        name: str,
        category_id: str,
        initial_members: List[str],
        initial_role_assignments: Sequence[Tuple["MarkingRole", str]],
        description: Optional[str] = None,
    ) -> Any:
        """Create a marking (``Marking.create``, GA); returns a ``Marking``.

        Args:
            name: Marking name (unique within its category).
            category_id: ID of the marking category to create it in.
            initial_members: IDs of the users and groups that can view
                resources protected by the marking.
            initial_role_assignments: ``(role, principal ID)`` pairs, with
                role ``ADMINISTER``, ``DECLASSIFY`` or ``USE``. The API
                requires at least one ``ADMINISTER``.
            description: Optional description.
        """
        from foundry_sdk.v2.admin.models import MarkingRoleUpdate

        return self.service.Marking.create(
            name=name,
            category_id=category_id,
            initial_members=initial_members,
            initial_role_assignments=[
                MarkingRoleUpdate(role=role, principal_id=principal_id)
                for role, principal_id in initial_role_assignments
            ],
            description=description,
        )

    def replace_marking(
        self,
        marking_id: str,
        *,
        name: str,
        description: Optional[str] = None,
    ) -> Any:
        """Set a marking's name, and its description if given.

        ``Marking.replace`` (GA) clears a description it isn't given, so when
        ``description`` is ``None`` this reads the marking first
        (``Marking.get``, GA) and sends its current description back.

        Returns:
            The updated ``Marking``.
        """
        if description is None:
            description = self.service.Marking.get(marking_id).description
        return self.service.Marking.replace(
            marking_id, name=name, description=description
        )

    # ---------------------------------------------------------- organizations

    def get_organization(self, organization_rid: str) -> Any:
        """Get an organization by RID (``Organization.get``, GA); returns an
        ``Organization`` model."""
        return self.service.Organization.get(organization_rid)

    def create_organization(
        self,
        *,
        name: str,
        enrollment_rid: str,
        administrators: List[str],
        description: Optional[str] = None,
        host: Optional[str] = None,
    ) -> Any:
        """Create an organization (``Organization.create``, beta).

        Args:
            name: Organization name.
            enrollment_rid: RID of the enrollment the organization belongs to.
            administrators: IDs of the users or groups that administer the
                organization (at least one).
            description: Optional description.
            host: Optional primary host name of the organization.

        Returns:
            The created ``Organization``.
        """
        return self.service.Organization.create(
            name=name,
            enrollment_rid=enrollment_rid,
            administrators=administrators,
            description=description,
            host=host,
            preview=True,
        )

    def replace_organization(
        self,
        organization_rid: str,
        *,
        name: str,
        description: Optional[str] = None,
        host: Optional[str] = None,
    ) -> Any:
        """Set an organization's name, and its description and host if given.

        ``Organization.replace`` (GA) clears the description and host it isn't
        given, so when either is ``None`` this reads the organization first
        (``Organization.get``, GA) and sends its current value back.

        Returns:
            The updated ``Organization``.
        """
        if description is None or host is None:
            current = self.service.Organization.get(organization_rid)
            if description is None:
                description = current.description
            if host is None:
                host = current.host
        return self.service.Organization.replace(
            organization_rid, name=name, description=description, host=host
        )

    def list_available_roles(self, organization_rid: str) -> Any:
        """List the roles that can be assigned in an organization
        (``Organization.list_available_roles``, GA).

        Returns:
            ``ListAvailableOrganizationRolesResponse``; ``data`` lists every
            role (the endpoint isn't paged).
        """
        return self.service.Organization.list_available_roles(organization_rid)

    # ------------------------------------------------------------------ roles

    def get_role(self, role_id: str) -> Any:
        """Get a role by ID (``Role.get``, beta); returns a ``Role`` model."""
        return self.service.Role.get(role_id, preview=True)

    def get_batch_roles(self, role_ids: List[str]) -> Any:
        """Get up to 500 roles in one request (``Role.get_batch``, beta).

        Returns:
            ``GetRolesBatchResponse``; its ``data`` maps role ID to ``Role``.
        """
        from foundry_sdk.v2.admin.models import GetRolesBatchRequestElement

        _check_batch_size(role_ids, "roles")
        return self.service.Role.get_batch(
            body=[GetRolesBatchRequestElement(role_id=role_id) for role_id in role_ids],
            preview=True,
        )
