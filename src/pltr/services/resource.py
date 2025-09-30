"""
Resource service wrapper for Foundry SDK filesystem API.
"""

from typing import Any, Optional, Dict, List

from .base import BaseService


class ResourceService(BaseService):
    """Service wrapper for Foundry resource operations using filesystem API."""

    def _get_service(self) -> Any:
        """Get the Foundry filesystem service."""
        return self.client.filesystem

    def get_resource(self, resource_rid: str) -> Dict[str, Any]:
        """
        Get information about a specific resource.

        Args:
            resource_rid: Resource Identifier

        Returns:
            Resource information dictionary
        """
        try:
            resource = self.service.Resource.get(resource_rid, preview=True)
            return self._format_resource_info(resource)
        except Exception as e:
            raise RuntimeError(f"Failed to get resource {resource_rid}: {e}")

    def get_resource_by_path(self, path: str) -> Dict[str, Any]:
        """
        Get information about a specific resource by its path.

        Args:
            path: Absolute path to the resource (e.g., "/My Organization/Project/Dataset")

        Returns:
            Resource information dictionary
        """
        try:
            resource = self.service.Resource.get_by_path(path=path, preview=True)
            return self._format_resource_info(resource)
        except Exception as e:
            raise RuntimeError(f"Failed to get resource at path '{path}': {e}")

    def list_resources(
        self,
        folder_rid: Optional[str] = None,
        resource_type: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List resources, optionally filtered by folder and type.

        Args:
            folder_rid: Folder Resource Identifier to filter by (optional)
            resource_type: Resource type to filter by (optional)
            page_size: Number of items per page (optional)
            page_token: Pagination token (optional)

        Returns:
            List of resource information dictionaries
        """
        try:
            resources = []
            list_params: Dict[str, Any] = {"preview": True}

            if folder_rid:
                list_params["folder_rid"] = folder_rid
            if resource_type:
                list_params["resource_type"] = resource_type
            if page_size:
                list_params["page_size"] = page_size
            if page_token:
                list_params["page_token"] = page_token

            # The list method returns an iterator
            for resource in self.service.Resource.list(**list_params):
                resources.append(self._format_resource_info(resource))
            return resources
        except Exception as e:
            raise RuntimeError(f"Failed to list resources: {e}")

    def get_resources_batch(self, resource_rids: List[str]) -> List[Dict[str, Any]]:
        """
        Get multiple resources in a single request.

        Args:
            resource_rids: List of resource RIDs (max 1000)

        Returns:
            List of resource information dictionaries
        """
        if len(resource_rids) > 1000:
            raise ValueError("Maximum batch size is 1000 resources")

        try:
            response = self.service.Resource.get_batch(body=resource_rids, preview=True)
            resources = []
            for resource in response.resources:
                resources.append(self._format_resource_info(resource))
            return resources
        except Exception as e:
            raise RuntimeError(f"Failed to get resources batch: {e}")

    def get_resource_metadata(self, resource_rid: str) -> Dict[str, Any]:
        """
        Get metadata for a specific resource.

        Args:
            resource_rid: Resource Identifier

        Returns:
            Resource metadata dictionary
        """
        try:
            metadata = self.service.Resource.get_metadata(resource_rid, preview=True)
            return self._format_metadata(metadata)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get metadata for resource {resource_rid}: {e}"
            )

    def set_resource_metadata(
        self, resource_rid: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Set metadata for a specific resource.

        Args:
            resource_rid: Resource Identifier
            metadata: Metadata dictionary to set

        Returns:
            Updated resource metadata
        """
        try:
            updated_metadata = self.service.Resource.set_metadata(
                resource_rid=resource_rid,
                body=metadata,
                preview=True,
            )
            return self._format_metadata(updated_metadata)
        except Exception as e:
            raise RuntimeError(
                f"Failed to set metadata for resource {resource_rid}: {e}"
            )

    def delete_resource_metadata(self, resource_rid: str, keys: List[str]) -> None:
        """
        Delete specific metadata keys for a resource.

        Args:
            resource_rid: Resource Identifier
            keys: List of metadata keys to delete

        Raises:
            RuntimeError: If deletion fails
        """
        try:
            self.service.Resource.delete_metadata(
                resource_rid=resource_rid,
                body={"keys": keys},
                preview=True,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to delete metadata for resource {resource_rid}: {e}"
            )

    def move_resource(
        self, resource_rid: str, target_folder_rid: str
    ) -> Dict[str, Any]:
        """
        Move a resource to a different folder.

        Args:
            resource_rid: Resource Identifier
            target_folder_rid: Target folder Resource Identifier

        Returns:
            Updated resource information
        """
        try:
            resource = self.service.Resource.move(
                resource_rid=resource_rid,
                body={"target_folder_rid": target_folder_rid},
                preview=True,
            )
            return self._format_resource_info(resource)
        except Exception as e:
            raise RuntimeError(f"Failed to move resource {resource_rid}: {e}")

    def search_resources(
        self,
        query: str,
        resource_type: Optional[str] = None,
        folder_rid: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for resources by query string.

        Args:
            query: Search query string
            resource_type: Resource type to filter by (optional)
            folder_rid: Folder to search within (optional)
            page_size: Number of items per page (optional)
            page_token: Pagination token (optional)

        Returns:
            List of matching resource information dictionaries
        """
        try:
            resources = []
            search_params: Dict[str, Any] = {
                "query": query,
                "preview": True,
            }

            if resource_type:
                search_params["resource_type"] = resource_type
            if folder_rid:
                search_params["folder_rid"] = folder_rid
            if page_size:
                search_params["page_size"] = page_size
            if page_token:
                search_params["page_token"] = page_token

            # The search method returns an iterator
            for resource in self.service.Resource.search(**search_params):
                resources.append(self._format_resource_info(resource))
            return resources
        except Exception as e:
            raise RuntimeError(f"Failed to search resources: {e}")

    def _format_resource_info(self, resource: Any) -> Dict[str, Any]:
        """
        Format resource information for consistent output.

        Args:
            resource: Resource object from Foundry SDK

        Returns:
            Formatted resource information dictionary
        """
        return {
            "rid": getattr(resource, "rid", None),
            "display_name": getattr(resource, "display_name", None),
            "name": getattr(resource, "name", None),
            "description": getattr(resource, "description", None),
            "path": getattr(resource, "path", None),
            "type": getattr(resource, "type", None),
            "folder_rid": getattr(resource, "folder_rid", None),
            "created_by": getattr(resource, "created_by", None),
            "created_time": self._format_timestamp(
                getattr(resource, "created_time", None)
            ),
            "modified_by": getattr(resource, "modified_by", None),
            "modified_time": self._format_timestamp(
                getattr(resource, "modified_time", None)
            ),
            "size_bytes": getattr(resource, "size_bytes", None),
            "trash_status": getattr(resource, "trash_status", None),
        }

    def _format_metadata(self, metadata: Any) -> Dict[str, Any]:
        """
        Format metadata for consistent output.

        Args:
            metadata: Metadata object from Foundry SDK

        Returns:
            Formatted metadata dictionary
        """
        if hasattr(metadata, "__dict__"):
            return dict(metadata.__dict__)
        elif isinstance(metadata, dict):
            return metadata
        else:
            return {"raw": str(metadata)}

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
