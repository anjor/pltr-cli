"""
DataHealth service wrapper for Foundry SDK.
Provides access to data quality check operations (create, get, update, delete).
"""

from typing import Any, Dict, Optional
from .base import BaseService


class DataHealthService(BaseService):
    """Service wrapper for Foundry DataHealth operations."""

    def _get_service(self) -> Any:
        """Get the Foundry DataHealth service."""
        return self.client.data_health

    # ===== Check Operations =====

    def create_check(
        self,
        config: Dict[str, Any],
        intent: Optional[str] = None,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new data health check.

        Args:
            config: Check configuration dictionary specifying the check type and parameters.
                    Must include a 'type' field indicating the check type.
            intent: Optional note about why the check was set up
            preview: Enable preview mode (default: False)

        Returns:
            Check information dictionary containing:
            - rid: Check resource identifier
            - groups: List of check group RIDs
            - config: Check configuration
            - intent: Check intent (if provided)
            - createdBy: User who created the check
            - updatedTime: Last update timestamp

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = DataHealthService()
            >>> check = service.create_check(
            ...     config={
            ...         "type": "buildStatus",
            ...         "subject": {
            ...             "datasetRid": "ri.foundry.main.dataset.xxx",
            ...             "branchId": "master"
            ...         },
            ...         "statusCheckConfig": {"severity": "WARNING"}
            ...     },
            ...     intent="Monitor build health"
            ... )
        """
        try:
            check = self.service.Check.create(
                config=config,
                intent=intent,
                preview=preview,
            )
            return self._serialize_response(check)
        except Exception as e:
            raise RuntimeError(f"Failed to create check: {e}")

    def get_check(
        self,
        check_rid: str,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Get information about a data health check.

        Args:
            check_rid: Check RID (e.g., ri.data-health.main.check.xxx)
            preview: Enable preview mode (default: False)

        Returns:
            Check information dictionary

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = DataHealthService()
            >>> check = service.get_check(
            ...     check_rid="ri.data-health.main.check.abc123"
            ... )
        """
        try:
            check = self.service.Check.get(
                check_rid=check_rid,
                preview=preview,
            )
            return self._serialize_response(check)
        except Exception as e:
            raise RuntimeError(f"Failed to get check '{check_rid}': {e}")

    def replace_check(
        self,
        check_rid: str,
        config: Dict[str, Any],
        intent: Optional[str] = None,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Replace/update a data health check.

        Note: Changing the type of a check after creation is not supported.

        Args:
            check_rid: Check RID (e.g., ri.data-health.main.check.xxx)
            config: New check configuration dictionary
            intent: Optional updated note about the check
            preview: Enable preview mode (default: False)

        Returns:
            Updated check information dictionary

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = DataHealthService()
            >>> check = service.replace_check(
            ...     check_rid="ri.data-health.main.check.abc123",
            ...     config={"type": "buildStatus", ...},
            ...     intent="Updated monitoring parameters"
            ... )
        """
        try:
            check = self.service.Check.replace(
                check_rid=check_rid,
                config=config,
                intent=intent,
                preview=preview,
            )
            return self._serialize_response(check)
        except Exception as e:
            raise RuntimeError(f"Failed to replace check '{check_rid}': {e}")

    def delete_check(
        self,
        check_rid: str,
        preview: bool = False,
    ) -> None:
        """
        Delete a data health check.

        Args:
            check_rid: Check RID (e.g., ri.data-health.main.check.xxx)
            preview: Enable preview mode (default: False)

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = DataHealthService()
            >>> service.delete_check(
            ...     check_rid="ri.data-health.main.check.abc123"
            ... )
        """
        try:
            self.service.Check.delete(
                check_rid=check_rid,
                preview=preview,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to delete check '{check_rid}': {e}")

    # ===== CheckReport Operations =====

    def get_check_report(
        self,
        check_report_rid: str,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Get a data health check report.

        Args:
            check_report_rid: CheckReport RID (e.g., ri.data-health.main.check-report.xxx)
            preview: Enable preview mode (default: False)

        Returns:
            CheckReport information dictionary containing:
            - rid: CheckReport resource identifier
            - check: Snapshot of the check configuration when report was created
            - result: Check result with status and message
            - createdTime: When the report was created

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = DataHealthService()
            >>> report = service.get_check_report(
            ...     check_report_rid="ri.data-health.main.check-report.abc123"
            ... )
        """
        try:
            report = self.service.CheckReport.get(
                check_report_rid=check_report_rid,
                preview=preview,
            )
            return self._serialize_response(report)
        except Exception as e:
            raise RuntimeError(f"Failed to get check report '{check_report_rid}': {e}")
