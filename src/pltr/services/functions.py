"""
Functions service wrapper for the Foundry SDK (queries and value types).

Every Functions endpoint pltr uses is beta, so every call passes
``preview=True``. Methods return SDK models unchanged and let SDK exceptions
propagate so the error layer can classify them.
"""

from typing import Any, Dict, Optional

from .base import BaseService


class FunctionsService(BaseService):
    """Service wrapper for Foundry Functions (``client.functions``)."""

    def _get_service(self) -> Any:
        """Get the Foundry Functions service."""
        return self.client.functions

    # ----------------------------------------------------------------- queries

    def get_query(
        self,
        query_api_name: str,
        *,
        version: Optional[str] = None,
        include_prerelease: Optional[bool] = None,
        latest_version_resolution: Optional[str] = None,
    ) -> Any:
        """Get a query's definition by API name (``Query.get``, beta).

        Without ``version`` the API returns the highest semantic version,
        excluding pre-releases, unless ``include_prerelease`` or
        ``latest_version_resolution="PUBLISH_TIME"`` say otherwise.

        Returns:
            A ``Query`` model.
        """
        return self.service.Query.get(
            query_api_name,
            version=version,
            include_prerelease=include_prerelease,
            latest_version_resolution=latest_version_resolution,
            preview=True,
        )

    def get_query_by_rid(
        self,
        query_rid: str,
        *,
        version: Optional[str] = None,
        include_prerelease: Optional[bool] = None,
    ) -> Any:
        """Get a query's definition by RID (``Query.get_by_rid``, beta).

        Returns:
            A ``Query`` model.
        """
        return self.service.Query.get_by_rid(
            rid=query_rid,
            version=version,
            include_prerelease=include_prerelease,
            preview=True,
        )

    def execute_query(
        self,
        query_api_name: str,
        *,
        parameters: Dict[str, Any],
        version: Optional[str] = None,
        include_prerelease: Optional[bool] = None,
        latest_version_resolution: Optional[str] = None,
    ) -> Any:
        """Execute a query by API name (``Query.execute``, beta).

        Args:
            parameters: Parameter values keyed by parameter name, as JSON
                values (strings, numbers, booleans, lists, objects; dates and
                timestamps as ISO-8601 strings).

        Returns:
            ``ExecuteQueryResponse``; the result is its ``value``.
        """
        return self.service.Query.execute(
            query_api_name,
            parameters=parameters,
            version=version,
            include_prerelease=include_prerelease,
            latest_version_resolution=latest_version_resolution,
            preview=True,
        )

    def execute_query_by_rid(
        self,
        query_rid: str,
        *,
        parameters: Dict[str, Any],
        version: Optional[str] = None,
        include_prerelease: Optional[bool] = None,
    ) -> Any:
        """Execute a query given its RID.

        The API executes queries by API name only, so this resolves the RID
        with ``Query.get_by_rid`` (beta) and then executes exactly the
        version it resolved with ``Query.execute`` (beta).

        Returns:
            ``ExecuteQueryResponse``; the result is its ``value``.
        """
        query = self.get_query_by_rid(
            query_rid, version=version, include_prerelease=include_prerelease
        )
        return self.service.Query.execute(
            query.api_name,
            parameters=parameters,
            version=query.version,
            preview=True,
        )

    # ------------------------------------------------------------- value types

    def get_value_type(self, value_type_rid: str) -> Any:
        """Get a value type (``ValueType.get``, beta); returns a ``ValueType``."""
        return self.service.ValueType.get(value_type_rid, preview=True)
