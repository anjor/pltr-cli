"""
Models service wrapper for the Foundry SDK (the ML model registry).

This is distinct from language models (LLM chat and embeddings). Every
endpoint used here is beta, so every call passes ``preview=True``. Methods
return SDK models (or SDK iterators) unchanged and let SDK exceptions
propagate so the error layer can classify them.
"""

from typing import Any, Optional

from .base import BaseService


class ModelsService(BaseService):
    """Service wrapper for the Foundry model registry (``client.models``)."""

    def _get_service(self) -> Any:
        """Get the Foundry models service."""
        return self.client.models

    # ------------------------------------------------------------------ models

    def create_model(self, *, name: str, parent_folder_rid: str) -> Any:
        """Create a model with no versions (``Model.create``, beta).

        Returns:
            The new ``Model`` (its ``rid``).
        """
        return self.service.Model.create(
            name=name, parent_folder_rid=parent_folder_rid, preview=True
        )

    def get_model(self, model_rid: str) -> Any:
        """Get a model (``Model.get``, beta); returns a ``Model``."""
        return self.service.Model.get(model_rid, preview=True)

    # ---------------------------------------------------------- model versions

    def get_model_version(self, model_rid: str, model_version_rid: str) -> Any:
        """Get a model version (``Model.Version.get``, beta).

        Returns:
            A ``ModelVersion`` (its API, dependencies, source and creation
            time).
        """
        return self.service.Model.Version.get(
            model_rid, model_version_rid, preview=True
        )

    def list_model_versions(
        self,
        model_rid: str,
        *,
        branch: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a model's versions (``Model.Version.list``, beta).

        Args:
            branch: The branch to list versions from (the API's default is
                usually master).

        Returns:
            The SDK ``ResourceIterator[ModelVersion]``; constructing it
            fetched one page (``.data``, ``.next_page_token``).
        """
        return self.service.Model.Version.list(
            model_rid,
            branch=branch,
            page_size=page_size,
            page_token=page_token,
            preview=True,
        )
