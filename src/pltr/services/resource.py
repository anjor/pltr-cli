"""
Resource service wrapper for Foundry SDK filesystem API.
"""

from typing import Any, Optional, Dict, List

from foundry_sdk.v2.filesystem.models import (
    GetResourcesBatchRequestElement,
    GetByPathResourcesBatchRequestElement,
)

from .base import BaseService


class ResourceService(BaseService):
    """Service wrapper for Foundry resource operations using filesystem API."""

    ROOT_FOLDER_RID = "ri.compass.main.folder.0"

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
            detail = self._format_error_detail(e)
            raise RuntimeError(f"Failed to get resource {resource_rid}: {detail}")

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
            detail = self._format_error_detail(e)
            raise RuntimeError(f"Failed to get resource at path '{path}': {detail}")

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
            parent_folder_rid = folder_rid or self.ROOT_FOLDER_RID
            resources = []
            list_params: Dict[str, Any] = {"preview": True}
            if page_size:
                list_params["page_size"] = page_size
            if page_token:
                list_params["page_token"] = page_token

            for resource in self.service.Folder.children(
                parent_folder_rid, **list_params
            ):
                if self._matches_resource_type(resource, resource_type):
                    resources.append(self._format_resource_info(resource))
            return resources
        except Exception as e:
            detail = self._format_error_detail(e)
            raise RuntimeError(f"Failed to list resources: {detail}")

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
            elements = [
                GetResourcesBatchRequestElement(resource_rid=rid)
                for rid in resource_rids
            ]
            response = self.service.Resource.get_batch(body=elements, preview=True)
            resources = []
            for resource in response.resources:
                resources.append(self._format_resource_info(resource))
            return resources
        except Exception as e:
            detail = self._format_error_detail(e)
            raise RuntimeError(f"Failed to get resources batch: {detail}")

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
            detail = self._format_error_detail(e)
            raise RuntimeError(
                f"Failed to get metadata for resource {resource_rid}: {detail}"
            )

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
            normalized_query = query.strip().lower()
            if not normalized_query:
                return []

            start_folder_rid = folder_rid or self.ROOT_FOLDER_RID
            search_params: Dict[str, Any] = {"preview": True}
            if page_size:
                search_params["page_size"] = page_size
            if page_token:
                search_params["page_token"] = page_token

            matches: List[Dict[str, Any]] = []
            pending_folders = [start_folder_rid]
            visited_folders = set()
            max_folders = 1000

            while pending_folders and len(visited_folders) < max_folders:
                current_folder_rid = pending_folders.pop(0)
                if current_folder_rid in visited_folders:
                    continue
                visited_folders.add(current_folder_rid)

                children = self.service.Folder.children(
                    current_folder_rid, **search_params
                )
                for resource in children:
                    if self._matches_resource_type(
                        resource, resource_type
                    ) and self._resource_matches_query(resource, normalized_query):
                        matches.append(self._format_resource_info(resource))

                    if self._is_container_resource(resource):
                        child_rid = getattr(resource, "rid", None)
                        if child_rid and child_rid not in visited_folders:
                            pending_folders.append(child_rid)

            return matches
        except Exception as e:
            detail = self._format_error_detail(e)
            raise RuntimeError(f"Failed to search resources: {detail}")

    # ==================== Trash Operations ====================

    def delete_resource(self, resource_rid: str) -> None:
        """
        Move a resource to trash.

        The resource can be restored later or permanently deleted.

        Args:
            resource_rid: Resource Identifier

        Raises:
            RuntimeError: If deletion fails
        """
        try:
            self.service.Resource.delete(resource_rid, preview=True)
        except Exception as e:
            detail = self._format_error_detail(e)
            raise RuntimeError(f"Failed to delete resource {resource_rid}: {detail}")

    def restore_resource(self, resource_rid: str) -> None:
        """
        Restore a resource from trash.

        This also restores any directly trashed ancestors.
        Operation is ignored if the resource is not trashed.

        Args:
            resource_rid: Resource Identifier

        Raises:
            RuntimeError: If restoration fails
        """
        try:
            self.service.Resource.restore(resource_rid, preview=True)
        except Exception as e:
            detail = self._format_error_detail(e)
            raise RuntimeError(f"Failed to restore resource {resource_rid}: {detail}")

    def permanently_delete_resource(self, resource_rid: str) -> None:
        """
        Permanently delete a resource from trash.

        The resource must already be in the trash. This operation is irreversible.

        Args:
            resource_rid: Resource Identifier

        Raises:
            RuntimeError: If permanent deletion fails
        """
        try:
            self.service.Resource.permanently_delete(resource_rid, preview=True)
        except Exception as e:
            detail = self._format_error_detail(e)
            raise RuntimeError(
                f"Failed to permanently delete resource {resource_rid}: {detail}"
            )

    # ==================== Markings Operations ====================

    def add_markings(self, resource_rid: str, marking_ids: List[str]) -> None:
        """
        Add markings to a resource.

        Args:
            resource_rid: Resource Identifier
            marking_ids: List of marking identifiers to add

        Raises:
            RuntimeError: If adding markings fails
        """
        try:
            self.service.Resource.add_markings(
                resource_rid, marking_ids=marking_ids, preview=True
            )
        except Exception as e:
            detail = self._format_error_detail(e)
            raise RuntimeError(
                f"Failed to add markings to resource {resource_rid}: {detail}"
            )

    def remove_markings(self, resource_rid: str, marking_ids: List[str]) -> None:
        """
        Remove markings from a resource.

        Args:
            resource_rid: Resource Identifier
            marking_ids: List of marking identifiers to remove

        Raises:
            RuntimeError: If removing markings fails
        """
        try:
            self.service.Resource.remove_markings(
                resource_rid, marking_ids=marking_ids, preview=True
            )
        except Exception as e:
            detail = self._format_error_detail(e)
            raise RuntimeError(
                f"Failed to remove markings from resource {resource_rid}: {detail}"
            )

    def list_markings(
        self,
        resource_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List markings directly applied to a resource.

        Args:
            resource_rid: Resource Identifier
            page_size: Number of items per page (optional)
            page_token: Pagination token (optional)

        Returns:
            List of marking information dictionaries
        """
        try:
            markings = []
            list_params: Dict[str, Any] = {"preview": True}

            if page_size:
                list_params["page_size"] = page_size
            if page_token:
                list_params["page_token"] = page_token

            for marking in self.service.Resource.markings(resource_rid, **list_params):
                markings.append(self._format_marking_info(marking))
            return markings
        except Exception as e:
            detail = self._format_error_detail(e)
            raise RuntimeError(
                f"Failed to list markings for resource {resource_rid}: {detail}"
            )

    # ==================== Access & Batch Operations ====================

    def get_access_requirements(self, resource_rid: str) -> Dict[str, Any]:
        """
        Get access requirements for a resource.

        Returns the Organizations and Markings required to view the resource.

        Args:
            resource_rid: Resource Identifier

        Returns:
            Access requirements dictionary with organizations and markings
        """
        try:
            requirements = self.service.Resource.get_access_requirements(
                resource_rid, preview=True
            )
            return self._format_access_requirements(requirements)
        except Exception as e:
            detail = self._format_error_detail(e)
            raise RuntimeError(
                f"Failed to get access requirements for resource {resource_rid}: {detail}"
            )

    def get_resources_by_path_batch(self, paths: List[str]) -> List[Dict[str, Any]]:
        """
        Get multiple resources by their absolute paths in a single request.

        Args:
            paths: List of absolute paths (max 1000)

        Returns:
            List of resource information dictionaries
        """
        if len(paths) > 1000:
            raise ValueError("Maximum batch size is 1000 paths")

        try:
            elements = [GetByPathResourcesBatchRequestElement(path=p) for p in paths]
            response = self.service.Resource.get_by_path_batch(
                body=elements, preview=True
            )
            resources = []
            for resource in response.resources:
                resources.append(self._format_resource_info(resource))
            return resources
        except Exception as e:
            detail = self._format_error_detail(e)
            raise RuntimeError(f"Failed to get resources by path batch: {detail}")

    def _format_resource_info(self, resource: Any) -> Dict[str, Any]:
        """
        Format resource information for consistent output.

        Args:
            resource: Resource object from Foundry SDK

        Returns:
            Formatted resource information dictionary
        """
        modified_by = getattr(resource, "modified_by", None)
        if modified_by is None:
            modified_by = getattr(resource, "updated_by", None)

        modified_time = getattr(resource, "modified_time", None)
        if modified_time is None:
            modified_time = getattr(resource, "updated_time", None)

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
            "modified_by": modified_by,
            "modified_time": self._format_timestamp(modified_time),
            "size_bytes": getattr(resource, "size_bytes", None),
            "trash_status": getattr(resource, "trash_status", None),
        }

    @staticmethod
    def _matches_resource_type(resource: Any, expected_type: Optional[str]) -> bool:
        """Check whether a resource matches a requested type filter."""
        if not expected_type:
            return True
        actual_type = str(getattr(resource, "type", "") or "").lower()
        return actual_type == expected_type.lower()

    @staticmethod
    def _resource_matches_query(resource: Any, query: str) -> bool:
        """Check whether a resource matches a text query across common fields."""
        searchable_parts = [
            getattr(resource, "rid", ""),
            getattr(resource, "display_name", ""),
            getattr(resource, "name", ""),
            getattr(resource, "description", ""),
            getattr(resource, "path", ""),
            getattr(resource, "type", ""),
        ]
        haystack = " ".join(str(part) for part in searchable_parts if part).lower()
        return query in haystack

    @staticmethod
    def _is_container_resource(resource: Any) -> bool:
        """Check whether a resource can have filesystem children."""
        resource_type = str(getattr(resource, "type", "") or "").lower()
        return resource_type in {"folder", "project", "space", "compass_folder"}

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

    @staticmethod
    def _format_error_detail(error: Exception) -> str:
        """Format exception details, including fallback for empty SDK error strings."""
        message = str(error).strip()
        if message:
            return message

        args = getattr(error, "args", ())
        if args:
            joined = " ".join(str(arg) for arg in args if arg is not None)
            if joined:
                return joined

        return error.__class__.__name__

    def _format_marking_info(self, marking: Any) -> Dict[str, Any]:
        """
        Format marking information for consistent output.

        Args:
            marking: Marking object from Foundry SDK

        Returns:
            Formatted marking information dictionary
        """
        return {
            "marking_id": getattr(marking, "marking_id", None),
            "display_name": getattr(marking, "display_name", None),
            "description": getattr(marking, "description", None),
            "category_id": getattr(marking, "category_id", None),
            "category_display_name": getattr(marking, "category_display_name", None),
        }

    def _format_access_requirements(self, requirements: Any) -> Dict[str, Any]:
        """
        Format access requirements for consistent output.

        Args:
            requirements: AccessRequirements object from Foundry SDK

        Returns:
            Formatted access requirements dictionary
        """
        organizations = []
        markings = []

        if hasattr(requirements, "organizations"):
            for org in getattr(requirements, "organizations", []) or []:
                organizations.append(
                    {
                        "organization_rid": getattr(org, "organization_rid", None),
                        "display_name": getattr(org, "display_name", None),
                    }
                )

        if hasattr(requirements, "markings"):
            for marking in getattr(requirements, "markings", []) or []:
                markings.append(self._format_marking_info(marking))

        return {
            "organizations": organizations,
            "markings": markings,
        }
