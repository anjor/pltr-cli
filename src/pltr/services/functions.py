"""
Functions service wrapper for Foundry SDK.
Provides access to Functions query execution and value type operations.
"""

from typing import Any, Dict, Optional
from .base import BaseService


class FunctionsService(BaseService):
    """Service wrapper for Foundry Functions operations."""

    def _get_service(self) -> Any:
        """Get the Foundry Functions service."""
        return self.client.functions

    # ===== Query Operations =====

    def get_query(
        self,
        query_api_name: str,
        preview: bool = False,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get query metadata by API name.

        Args:
            query_api_name: Query API name (e.g., "myQuery")
            preview: Enable preview mode (default: False)
            version: Optional query version (e.g., "1.0.0")
                If not specified, returns latest version

        Returns:
            Query information dictionary containing:
            - rid: Query resource identifier
            - apiName: Query API name
            - version: Query version
            - parameters: Query parameters with types
            - output: Output structure definition

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = FunctionsService()
            >>> query = service.get_query("myQuery")
            >>> print(query['apiName'])
        """
        try:
            query = self.service.Query.get(
                query_api_name, preview=preview, version=version
            )
            return self._serialize_response(query)
        except Exception as e:
            raise RuntimeError(f"Failed to get query '{query_api_name}': {e}")

    def get_query_by_rid(
        self, query_rid: str, preview: bool = False, version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get query metadata by RID.

        Args:
            query_rid: Query Resource Identifier
                Format: ri.functions.main.query.<id>
            preview: Enable preview mode (default: False)
            version: Optional query version (e.g., "1.0.0")
                If not specified, returns latest version

        Returns:
            Query information dictionary containing:
            - rid: Query resource identifier
            - apiName: Query API name
            - version: Query version
            - parameters: Query parameters with types
            - output: Output structure definition

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = FunctionsService()
            >>> query = service.get_query_by_rid("ri.functions.main.query.abc123")
            >>> print(query['rid'])
        """
        try:
            query = self.service.Query.get_by_rid(
                query_rid, preview=preview, version=version
            )
            return self._serialize_response(query)
        except Exception as e:
            raise RuntimeError(f"Failed to get query {query_rid}: {e}")

    def execute_query(
        self,
        query_api_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        preview: bool = False,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a query by API name with parameters.

        Args:
            query_api_name: Query API name (e.g., "myQuery")
            parameters: Query parameters as dictionary with DataValue encoding
                Examples:
                - Primitives: {"limit": 10, "name": "John"}
                - Arrays: {"ids": [1, 2, 3]}
                - Structs: {"config": {"enabled": true}}
                - Dates: {"date": "2024-01-01"} (ISO 8601)
                - Timestamps: {"created": "2021-01-04T05:00:00Z"} (ISO 8601)
            preview: Enable preview mode (default: False)
            version: Optional query version (e.g., "1.0.0")
                If not specified, executes latest version

        Returns:
            Query execution result dictionary

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = FunctionsService()
            >>> result = service.execute_query(
            ...     "myQuery",
            ...     parameters={"limit": 10, "filter": "active"}
            ... )
            >>> print(result)
        """
        try:
            result = self.service.Query.execute(
                query_api_name,
                parameters=parameters or {},
                preview=preview,
                version=version,
            )
            return self._serialize_response(result)
        except Exception as e:
            raise RuntimeError(f"Failed to execute query '{query_api_name}': {e}")

    def execute_query_by_rid(
        self,
        query_rid: str,
        parameters: Optional[Dict[str, Any]] = None,
        preview: bool = False,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a query by RID with parameters.

        Args:
            query_rid: Query Resource Identifier
                Format: ri.functions.main.query.<id>
            parameters: Query parameters as dictionary with DataValue encoding
                Examples:
                - Primitives: {"limit": 10, "name": "John"}
                - Arrays: {"ids": [1, 2, 3]}
                - Structs: {"config": {"enabled": true}}
                - Dates: {"date": "2024-01-01"} (ISO 8601)
                - Timestamps: {"created": "2021-01-04T05:00:00Z"} (ISO 8601)
            preview: Enable preview mode (default: False)
            version: Optional query version (e.g., "1.0.0")
                If not specified, executes latest version

        Returns:
            Query execution result dictionary

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = FunctionsService()
            >>> result = service.execute_query_by_rid(
            ...     "ri.functions.main.query.abc123",
            ...     parameters={"limit": 10}
            ... )
            >>> print(result)
        """
        try:
            result = self.service.Query.execute_by_rid(
                query_rid,
                parameters=parameters or {},
                preview=preview,
                version=version,
            )
            return self._serialize_response(result)
        except Exception as e:
            raise RuntimeError(f"Failed to execute query {query_rid}: {e}")

    # ===== Value Type Operations =====

    def get_value_type(
        self, value_type_rid: str, preview: bool = False
    ) -> Dict[str, Any]:
        """
        Get value type details by RID.

        Args:
            value_type_rid: Value Type Resource Identifier
                Format: ri.functions.main.value-type.<id>
            preview: Enable preview mode (default: False)

        Returns:
            Value type information dictionary containing:
            - rid: Value type resource identifier
            - apiName: Value type API name
            - definition: Type definition and structure

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = FunctionsService()
            >>> value_type = service.get_value_type("ri.functions.main.value-type.xyz")
            >>> print(value_type['apiName'])
        """
        try:
            value_type = self.service.ValueType.get(value_type_rid, preview=preview)
            return self._serialize_response(value_type)
        except Exception as e:
            raise RuntimeError(f"Failed to get value type {value_type_rid}: {e}")
