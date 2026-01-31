"""
Models service wrapper for Foundry SDK.
Provides access to ML model registry operations (model lifecycle, versioning, metadata).

Note: This is distinct from LanguageModels, which handles LLM chat/embeddings operations.
"""

from typing import Any, Dict, Optional
from .base import BaseService


class ModelsService(BaseService):
    """Service wrapper for Foundry Models operations."""

    def _get_service(self) -> Any:
        """Get the Foundry Models service."""
        return self.client.models

    # ===== Model Operations =====

    def create_model(
        self,
        name: str,
        parent_folder_rid: str,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new ML model in the registry.

        Args:
            name: Model name
            parent_folder_rid: Parent folder RID (e.g., ri.compass.main.folder.xxx)
            preview: Enable preview mode (default: False)

        Returns:
            Model information dictionary containing:
            - rid: Model resource identifier
            - name: Model name
            - parentFolderRid: Parent folder RID

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = ModelsService()
            >>> model = service.create_model(
            ...     name="fraud-detector",
            ...     parent_folder_rid="ri.compass.main.folder.xxx"
            ... )
        """
        try:
            model = self.service.Model.create(
                name=name,
                parent_folder_rid=parent_folder_rid,
                preview=preview,
            )
            return self._serialize_response(model)
        except Exception as e:
            raise RuntimeError(f"Failed to create model '{name}': {e}")

    def get_model(
        self,
        model_rid: str,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Get information about a model.

        Args:
            model_rid: Model RID (e.g., ri.foundry.main.model.xxx)
            preview: Enable preview mode (default: False)

        Returns:
            Model information dictionary

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = ModelsService()
            >>> model = service.get_model(
            ...     model_rid="ri.foundry.main.model.abc123"
            ... )
        """
        try:
            model = self.service.Model.get(
                model_rid=model_rid,
                preview=preview,
            )
            return self._serialize_response(model)
        except Exception as e:
            raise RuntimeError(f"Failed to get model '{model_rid}': {e}")

    # ===== ModelVersion Operations =====

    def get_model_version(
        self,
        model_rid: str,
        model_version_rid: str,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Get information about a specific model version.

        Args:
            model_rid: Model RID (e.g., ri.foundry.main.model.xxx)
            model_version_rid: Version identifier (e.g., v1.0.0 or version RID)
            preview: Enable preview mode (default: False)

        Returns:
            Model version information dictionary

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = ModelsService()
            >>> version = service.get_model_version(
            ...     model_rid="ri.foundry.main.model.abc123",
            ...     model_version_rid="v1.0.0"
            ... )
        """
        try:
            version = self.service.ModelVersion.get(
                model_rid=model_rid,
                model_version_rid=model_version_rid,
                preview=preview,
            )
            return self._serialize_response(version)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get model version '{model_version_rid}' for model '{model_rid}': {e}"
            )

    def list_model_versions(
        self,
        model_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        List all versions of a model with pagination support.

        Args:
            model_rid: Model RID (e.g., ri.foundry.main.model.xxx)
            page_size: Maximum number of versions to return per page
            page_token: Token for fetching next page of results
            preview: Enable preview mode (default: False)

        Returns:
            Dictionary containing:
            - data: List of model version information dictionaries
            - nextPageToken: Token for next page (if available)

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = ModelsService()
            >>> result = service.list_model_versions(
            ...     model_rid="ri.foundry.main.model.abc123",
            ...     page_size=50
            ... )
            >>> versions = result['data']
            >>> next_token = result.get('nextPageToken')
        """
        try:
            response = self.service.ModelVersion.list(
                model_rid=model_rid,
                page_size=page_size,
                page_token=page_token,
                preview=preview,
            )
            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(
                f"Failed to list model versions for model '{model_rid}': {e}"
            )
