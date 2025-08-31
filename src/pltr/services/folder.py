"""
Folder service wrapper for Foundry SDK filesystem API.
"""

from typing import Any, Optional, Dict, List

from .base import BaseService


class FolderService(BaseService):
    """Service wrapper for Foundry folder operations using filesystem API."""

    def _get_service(self) -> Any:
        """Get the Foundry filesystem service."""
        return self.client.filesystem

    def create_folder(
        self, display_name: str, parent_folder_rid: str
    ) -> Dict[str, Any]:
        """
        Create a new folder.

        Args:
            display_name: Folder display name
            parent_folder_rid: Parent folder RID (use 'ri.compass.main.folder.0' for root)

        Returns:
            Created folder information
        """
        try:
            folder = self.service.Folder.create(
                display_name=display_name,
                parent_folder_rid=parent_folder_rid,
                preview=True,
            )
            return self._format_folder_info(folder)
        except Exception as e:
            raise RuntimeError(f"Failed to create folder '{display_name}': {e}")

    def get_folder(self, folder_rid: str) -> Dict[str, Any]:
        """
        Get information about a specific folder.

        Args:
            folder_rid: Folder Resource Identifier

        Returns:
            Folder information dictionary
        """
        try:
            folder = self.service.Folder.get(folder_rid, preview=True)
            return self._format_folder_info(folder)
        except Exception as e:
            raise RuntimeError(f"Failed to get folder {folder_rid}: {e}")

    def list_children(
        self,
        folder_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all child resources of a folder.

        Args:
            folder_rid: Folder Resource Identifier
            page_size: Number of items per page (optional)
            page_token: Pagination token (optional)

        Returns:
            List of child resources
        """
        try:
            children = []
            # The children method returns an iterator
            for child in self.service.Folder.children(
                folder_rid, page_size=page_size, page_token=page_token, preview=True
            ):
                children.append(self._format_resource_info(child))
            return children
        except Exception as e:
            raise RuntimeError(f"Failed to list children of folder {folder_rid}: {e}")

    def get_folders_batch(self, folder_rids: List[str]) -> List[Dict[str, Any]]:
        """
        Get multiple folders in a single request.

        Args:
            folder_rids: List of folder RIDs (max 1000)

        Returns:
            List of folder information dictionaries
        """
        if len(folder_rids) > 1000:
            raise ValueError("Maximum batch size is 1000 folders")

        try:
            response = self.service.Folder.get_batch(body=folder_rids, preview=True)
            folders = []
            for folder in response.folders:
                folders.append(self._format_folder_info(folder))
            return folders
        except Exception as e:
            raise RuntimeError(f"Failed to get folders batch: {e}")

    def _format_folder_info(self, folder: Any) -> Dict[str, Any]:
        """
        Format folder information for consistent output.

        Args:
            folder: Folder object from Foundry SDK

        Returns:
            Formatted folder information dictionary
        """
        return {
            "rid": getattr(folder, "rid", None),
            "display_name": getattr(folder, "display_name", None),
            "description": getattr(folder, "description", None),
            "created": self._format_timestamp(getattr(folder, "created", None)),
            "modified": self._format_timestamp(getattr(folder, "modified", None)),
            "parent_folder_rid": getattr(folder, "parent_folder_rid", None),
            "type": "folder",
        }

    def _format_resource_info(self, resource: Any) -> Dict[str, Any]:
        """
        Format resource information (can be folder, dataset, etc.).

        Args:
            resource: Resource object from Foundry SDK

        Returns:
            Formatted resource information dictionary
        """
        resource_type = getattr(resource, "type", "unknown")
        base_info = {
            "rid": getattr(resource, "rid", None),
            "display_name": getattr(resource, "display_name", None),
            "type": resource_type,
        }

        # Add type-specific fields
        if resource_type == "folder":
            base_info["description"] = getattr(resource, "description", None)
        elif resource_type == "dataset":
            base_info["name"] = getattr(resource, "name", None)

        return base_info

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
