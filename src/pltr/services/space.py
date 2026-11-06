"""
Space service wrapper for the Foundry SDK filesystem API.

``Space.create``, ``Space.get``, ``Space.replace`` and ``Space.delete`` are
beta endpoints and are always called with ``preview=True``; ``Space.list`` is
GA. Methods return SDK models (or SDK iterators) unchanged and let SDK
exceptions propagate so the error layer can classify them.
"""

from typing import Any, List, Optional

from .base import BaseService


class SpaceService(BaseService):
    """Service wrapper for Foundry space operations (``client.filesystem``)."""

    def _get_service(self) -> Any:
        """Get the Foundry filesystem service."""
        return self.client.filesystem

    def create_space(
        self,
        *,
        display_name: str,
        enrollment_rid: str,
        organizations: List[str],
        deletion_policy_organizations: List[str],
        description: Optional[str] = None,
        default_role_set_id: Optional[str] = None,
        file_system_id: Optional[str] = None,
        usage_account_rid: Optional[str] = None,
    ) -> Any:
        """Create a space (``Space.create``, beta); returns a ``Space`` model."""
        return self.service.Space.create(
            display_name=display_name,
            enrollment_rid=enrollment_rid,
            organizations=organizations,
            deletion_policy_organizations=deletion_policy_organizations,
            description=description,
            default_role_set_id=default_role_set_id,
            file_system_id=file_system_id,
            usage_account_rid=usage_account_rid,
            preview=True,
        )

    def get_space(self, space_rid: str) -> Any:
        """Get a space (``Space.get``, beta); returns a ``Space`` model."""
        return self.service.Space.get(space_rid, preview=True)

    def list_spaces(
        self, page_size: Optional[int] = None, page_token: Optional[str] = None
    ) -> Any:
        """List one page of spaces (``Space.list``, GA).

        Returns:
            The SDK ``ResourceIterator[Space]``; constructing it fetched one
            page (``.data``, ``.next_page_token``).
        """
        return self.service.Space.list(page_size=page_size, page_token=page_token)

    def update_space(
        self,
        space_rid: str,
        *,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        default_role_set_id: Optional[str] = None,
        usage_account_rid: Optional[str] = None,
    ) -> Any:
        """Change some fields of a space; the others keep their current values.

        ``Space.replace`` (beta) resets every optional field it isn't given
        (the default role set and usage account fall back to the
        enrollment's defaults), so this reads the space first (``Space.get``,
        beta) and sends the current value of every field not being changed.
        """
        if all(
            value is None
            for value in (
                display_name,
                description,
                default_role_set_id,
                usage_account_rid,
            )
        ):
            raise ValueError("At least one field must be provided for update")

        current = self.service.Space.get(space_rid, preview=True)
        return self.service.Space.replace(
            space_rid,
            display_name=display_name
            if display_name is not None
            else current.display_name,
            description=description if description is not None else current.description,
            default_role_set_id=(
                default_role_set_id
                if default_role_set_id is not None
                else current.default_role_set_id
            ),
            usage_account_rid=(
                usage_account_rid
                if usage_account_rid is not None
                else current.usage_account_rid
            ),
            preview=True,
        )

    def delete_space(self, space_rid: str) -> None:
        """Delete a space (``Space.delete``, beta)."""
        self.service.Space.delete(space_rid, preview=True)
