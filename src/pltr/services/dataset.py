"""
Dataset service wrapper for Foundry SDK v2 API.
Only includes operations that are actually supported by foundry-platform-sdk v1.27.0.
"""

from typing import Any, Optional, Dict

from .base import BaseService


class DatasetService(BaseService):
    """Service wrapper for Foundry dataset operations using v2 API."""

    def _get_service(self) -> Any:
        """Get the Foundry datasets service."""
        return self.client.datasets

    def get_dataset(self, dataset_rid: str) -> Dict[str, Any]:
        """
        Get information about a specific dataset.

        Args:
            dataset_rid: Dataset Resource Identifier

        Returns:
            Dataset information dictionary
        """
        try:
            # Use the v2 API's Dataset.get method
            dataset = self.service.Dataset.get(dataset_rid)
            return self._format_dataset_info(dataset)
        except Exception as e:
            raise RuntimeError(f"Failed to get dataset {dataset_rid}: {e}")

    def get_schema(self, dataset_rid: str) -> Dict[str, Any]:
        """
        Get dataset schema.

        Args:
            dataset_rid: Dataset Resource Identifier

        Returns:
            Schema information
        """
        try:
            schema = self.service.Dataset.get_schema(dataset_rid)
            return {
                "dataset_rid": dataset_rid,
                "schema": schema,
                "type": str(type(schema)),
                "status": "Schema retrieved successfully"
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get schema for dataset {dataset_rid}: {e}")

    def create_dataset(self, name: str, parent_folder_rid: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new dataset.

        Args:
            name: Dataset name
            parent_folder_rid: Parent folder RID (optional)

        Returns:
            Created dataset information
        """
        try:
            # The create method parameters depend on the SDK version
            dataset = self.service.Dataset.create(
                name=name,
                parent_folder_rid=parent_folder_rid
            )
            return self._format_dataset_info(dataset)
        except Exception as e:
            raise RuntimeError(f"Failed to create dataset '{name}': {e}")

    def read_table(self, dataset_rid: str, format: str = "arrow") -> Any:
        """
        Read dataset as a table.

        Args:
            dataset_rid: Dataset Resource Identifier
            format: Output format (arrow, pandas, etc.)

        Returns:
            Table data in specified format
        """
        try:
            return self.service.Dataset.read_table(dataset_rid, format=format)
        except Exception as e:
            raise RuntimeError(f"Failed to read dataset {dataset_rid}: {e}")

    def _format_dataset_info(self, dataset: Any) -> Dict[str, Any]:
        """
        Format dataset information for consistent output.

        Args:
            dataset: Dataset object from Foundry SDK

        Returns:
            Formatted dataset information dictionary
        """
        # The v2 Dataset object has different attributes
        return {
            "rid": getattr(dataset, "rid", "unknown"),
            "name": getattr(dataset, "name", "Unknown"),
            "description": getattr(dataset, "description", ""),
            "path": getattr(dataset, "path", None),
            "created": getattr(dataset, "created", None),
            "modified": getattr(dataset, "modified", None),
            # Try to get additional attributes that might exist
            "created_time": getattr(dataset, "created_time", None),
            "created_by": getattr(dataset, "created_by", None),
            "last_modified": getattr(dataset, "last_modified", None),
            "size_bytes": getattr(dataset, "size_bytes", None),
            "schema_id": getattr(dataset, "schema_id", None),
            "parent_folder_rid": getattr(dataset, "parent_folder_rid", None),
        }