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

    # get_schema method removed - uses preview-only API

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
        # The v2 Dataset object only has rid, name, and parent_folder_rid
        return {
            "rid": dataset.rid,
            "name": dataset.name,
            "parent_folder_rid": dataset.parent_folder_rid,
        }
