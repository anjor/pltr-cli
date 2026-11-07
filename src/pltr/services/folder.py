"""
Folder service wrapper for the Foundry SDK filesystem API.

Methods return SDK models (or SDK iterators) unchanged; the command layer
formats them (``pltr.contract.emit``). SDK exceptions propagate unchanged so
the error layer can classify them.
"""

from typing import Any, List, Optional


from .base import BaseService

#: Maximum number of folders ``Folder.get_batch`` accepts in one request.
MAX_BATCH_SIZE = 1000


class FolderService(BaseService):
    """Service wrapper for Foundry folder operations (``client.filesystem``)."""

    def _get_service(self) -> Any:
        """Get the Foundry filesystem service."""
        return self.client.filesystem

    def create_folder(self, display_name: str, parent_folder_rid: str) -> Any:
        """Create a folder (``Folder.create``, GA).

        Args:
            display_name: Folder display name
            parent_folder_rid: RID of the parent folder or project

        Returns:
            The created ``Folder`` model
        """
        return self.service.Folder.create(
            display_name=display_name, parent_folder_rid=parent_folder_rid
        )

    def get_folder(self, folder_rid: str) -> Any:
        """Get a folder (``Folder.get``, GA); returns a ``Folder`` model."""
        return self.service.Folder.get(folder_rid)

    def list_children(
        self,
        folder_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a folder's children (``Folder.children``, GA).

        Returns:
            The SDK ``ResourceIterator[Resource]``. Constructing it fetched
            exactly one page: read ``.data`` and ``.next_page_token``.
            Iterating it fetches the remaining pages too.
        """
        return self.service.Folder.children(
            folder_rid, page_size=page_size, page_token=page_token
        )

    def get_folders_batch(self, folder_rids: List[str]) -> Any:
        """Get up to 1000 folders in one request (``Folder.get_batch``, GA).

        Returns:
            ``GetFoldersBatchResponse``; its ``data`` maps folder RID to
            ``Folder``.
        """
        if len(folder_rids) > MAX_BATCH_SIZE:
            raise ValueError(f"Maximum batch size is {MAX_BATCH_SIZE} folders")
        from foundry_sdk.v2.filesystem.models import GetFoldersBatchRequestElement

        elements = [
            GetFoldersBatchRequestElement(folder_rid=rid) for rid in folder_rids
        ]
        return self.service.Folder.get_batch(body=elements)
