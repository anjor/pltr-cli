"""
Dataset service wrapper for Foundry SDK v2 API.
This is a simplified version that works with the actual foundry_sdk API.
"""

from typing import Any, Optional, Dict

from .base import BaseService


class DatasetServiceV2(BaseService):
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
            # The v2 API returns a Dataset object
            dataset = self.service.Dataset.get(dataset_rid)

            # Format the response
            return {
                "rid": dataset_rid,
                "name": getattr(dataset, "name", "Unknown"),
                "description": getattr(dataset, "description", ""),
                "path": getattr(dataset, "path", ""),
                "created": getattr(dataset, "created_time", None),
                "modified": getattr(dataset, "modified_time", None),
                # The actual attributes available depend on the SDK version
                "status": "Retrieved successfully",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get dataset {dataset_rid}: {e}")

    def create_dataset(
        self, name: str, parent_folder_rid: Optional[str] = None
    ) -> Dict[str, Any]:
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
                name=name, parent_folder_rid=parent_folder_rid
            )

            return {
                "rid": getattr(dataset, "rid", "unknown"),
                "name": name,
                "parent_folder_rid": parent_folder_rid,
                "status": "Created successfully",
            }
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

            # Format schema for display
            return {
                "dataset_rid": dataset_rid,
                "schema": schema,
                "status": "Schema retrieved successfully",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get schema for dataset {dataset_rid}: {e}")

    def list_datasets(self, limit: Optional[int] = None) -> list:
        """
        List datasets - NOT SUPPORTED BY SDK v2.

        The foundry_sdk v2 API doesn't provide a list_datasets method.
        Dataset operations are RID-based. You need to know the dataset RID
        to interact with it.

        Raises:
            NotImplementedError: This operation is not supported by the SDK
        """
        raise NotImplementedError(
            "Dataset listing is not supported by foundry_sdk v2. "
            "The SDK requires knowing dataset RIDs in advance. "
            "Consider using the Foundry web interface to find dataset RIDs, "
            "or contact your Foundry administrator for dataset information."
        )
