"""
Project service wrapper for the Foundry SDK filesystem API.

``Project.create``, ``Project.get``, ``Project.create_from_template`` and the
organization endpoints are GA; ``Project.replace`` is beta and is always
called with ``preview=True``. The SDK has no ``Project.delete``: a project is
a filesystem resource, so it is moved to the trash with ``Resource.delete``.
Projects are listed through their space's children (``Folder.children``).

Methods return SDK models (or SDK iterators) unchanged and let SDK
exceptions propagate so the error layer can classify them.
"""

from typing import Any, Dict, List, Optional

from foundry_sdk.v2.filesystem.models import PrincipalWithId
from typing_extensions import Literal

from ..contract import Page
from .base import BaseService

#: Role granted to the new project's owner unless told otherwise: Owner
#: (``compass:manage``) in Foundry's default project role set.
OWNER_ROLE_ID = "compass:manage"

#: ``PrincipalType`` of the SDK: whether a principal ID is a user or a group.
PrincipalType = Literal["USER", "GROUP"]


def is_project(resource: Any) -> bool:
    """True for a ``Resource`` that is a project.

    ``Resource.project_rid`` is the project a resource lives in; for a
    project itself it is the project's own RID.
    """
    return resource.rid == resource.project_rid


class ProjectService(BaseService):
    """Service wrapper for Foundry project operations (``client.filesystem``)."""

    def _get_service(self) -> Any:
        """Get the Foundry filesystem service."""
        return self.client.filesystem

    def get_current_user_id(self) -> str:
        """The ID of the calling user (``admin.User.get_current``, GA)."""
        return self.client.admin.User.get_current().id

    def create_project(
        self,
        *,
        display_name: str,
        space_rid: str,
        owner_id: Optional[str] = None,
        owner_type: PrincipalType = "USER",
        owner_role: str = OWNER_ROLE_ID,
        description: Optional[str] = None,
        organization_rids: Optional[List[str]] = None,
        default_roles: Optional[List[str]] = None,
    ) -> Any:
        """Create a project (``Project.create``, GA); returns a ``Project`` model.

        The API requires an owner-like role grant: ``owner_role`` is granted
        to ``owner_id`` (a user or group ID of type ``owner_type``), or to
        the calling user when ``owner_id`` is ``None``.
        """
        if owner_id is None:
            owner_id = self.get_current_user_id()
            owner_type = "USER"
        role_grants: Dict[str, List[Any]] = {
            owner_role: [
                PrincipalWithId(principal_id=owner_id, principal_type=owner_type)
            ]
        }
        return self.service.Project.create(
            display_name=display_name,
            space_rid=space_rid,
            role_grants=role_grants,
            default_roles=list(default_roles or []),
            organization_rids=list(organization_rids or []),
            description=description,
        )

    def get_project(self, project_rid: str) -> Any:
        """Get a project (``Project.get``, GA); returns a ``Project`` model."""
        return self.service.Project.get(project_rid)

    def list_projects(
        self,
        space_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Page:
        """List one page of the projects in a space.

        Reads one page of the space's children (``Folder.children``, GA) and
        keeps the projects (see :func:`is_project`).

        Returns:
            A ``Page`` of ``Resource`` models and the page's
            ``next_page_token``.
        """
        children = self.service.Folder.children(
            space_rid, page_size=page_size, page_token=page_token
        )
        return Page(
            data=[child for child in children.data if is_project(child)],
            next_page_token=children.next_page_token,
        )

    def list_all_projects(self, page_size: Optional[int] = None) -> List[Any]:
        """List the projects of every space the caller can see.

        Reads every page of ``Space.list`` (GA) and of each space's children
        (``Folder.children``, GA); ``page_size`` is the page size of each of
        those requests.

        Returns:
            ``Resource`` models of the projects, without duplicates.
        """
        projects: Dict[str, Any] = {}
        for space in self.service.Space.list(page_size=page_size):
            for child in self.service.Folder.children(space.rid, page_size=page_size):
                if is_project(child):
                    projects.setdefault(child.rid, child)
        return list(projects.values())

    def update_project(
        self,
        project_rid: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Any:
        """Change a project's display name and/or description.

        ``Project.replace`` (beta) clears the description when it isn't
        given, so this reads the project first (``Project.get``, GA) and
        sends back the current value of the field not being changed.

        Returns:
            The updated ``Project`` model.
        """
        if display_name is None and description is None:
            raise ValueError("At least one field must be provided for update")
        current = self.service.Project.get(project_rid)
        return self.service.Project.replace(
            project_rid,
            display_name=(
                display_name if display_name is not None else current.display_name
            ),
            description=description if description is not None else current.description,
            preview=True,
        )

    def delete_project(self, project_rid: str) -> Any:
        """Move a project to the trash.

        Reads the project first (``Project.get``, GA), so a RID that isn't a
        project fails instead of trashing another kind of resource, then
        calls ``Resource.delete`` (GA).

        Returns:
            The ``Project`` model read before it was trashed.
        """
        project = self.service.Project.get(project_rid)
        self.service.Resource.delete(project_rid)
        return project

    # ==================== Organization Operations ====================

    def add_organizations(self, project_rid: str, organization_rids: List[str]) -> None:
        """Add organizations to a project (``Project.add_organizations``, GA)."""
        self.service.Project.add_organizations(
            project_rid, organization_rids=organization_rids
        )

    def remove_organizations(
        self, project_rid: str, organization_rids: List[str]
    ) -> None:
        """Remove organizations from a project (``Project.remove_organizations``, GA)."""
        self.service.Project.remove_organizations(
            project_rid, organization_rids=organization_rids
        )

    def list_organizations(
        self,
        project_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of the organizations applied directly to a project.

        ``Project.organizations`` (GA) returns organization RIDs (strings).

        Returns:
            The SDK ``ResourceIterator[str]``; constructing it fetched one page.
        """
        return self.service.Project.organizations(
            project_rid, page_size=page_size, page_token=page_token
        )

    # ==================== Template Operations ====================

    def create_project_from_template(
        self,
        *,
        template_rid: str,
        variable_values: Dict[str, str],
        default_roles: Optional[List[str]] = None,
        organization_rids: Optional[List[str]] = None,
        project_description: Optional[str] = None,
    ) -> Any:
        """Create a project from a template (``Project.create_from_template``, GA).

        Returns:
            The created ``Project`` model.
        """
        return self.service.Project.create_from_template(
            template_rid=template_rid,
            variable_values=variable_values,
            default_roles=default_roles or None,
            organization_rids=organization_rids or None,
            project_description=project_description,
        )
