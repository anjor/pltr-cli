"""
Audit service wrapper for Foundry SDK.
Provides access to audit log file operations for compliance and security monitoring.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from .base import BaseService


class AuditService(BaseService):
    """Service wrapper for Foundry Audit operations."""

    def _get_service(self) -> Any:
        """Get the Foundry Audit service."""
        return self.client.audit

    def list_log_files(
        self,
        organization_rid: str,
        start_date: date,
        end_date: Optional[date] = None,
        page_size: Optional[int] = None,
        preview: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List audit log files for an organization.

        Args:
            organization_rid: Organization Resource Identifier
                Expected format: ri.multipass..organization.<locator>
            start_date: Start date for audit events (required)
            end_date: End date for audit events (inclusive, optional)
            page_size: Number of results per page (optional)
            preview: Enable preview mode (default: False)

        Returns:
            List of log file dictionaries containing:
            - fileId: Log file identifier
            - date: Date of the log file
            - size: Size of the log file in bytes

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> from datetime import date
            >>> service = AuditService()
            >>> logs = service.list_log_files(
            ...     organization_rid="ri.multipass..organization.abc123",
            ...     start_date=date(2024, 1, 1),
            ...     end_date=date(2024, 1, 31)
            ... )
        """
        try:
            # Build optional parameters
            kwargs: Dict[str, Any] = {}
            if end_date:
                kwargs["end_date"] = end_date
            if page_size:
                kwargs["page_size"] = page_size

            log_files = self.service.Organization.LogFile.list(
                organization_rid=organization_rid,
                start_date=start_date,
                **kwargs,
            )
            return [self._serialize_response(log) for log in log_files]
        except Exception as e:
            raise RuntimeError(f"Failed to list audit log files: {e}")

    def get_log_file_content(
        self,
        organization_rid: str,
        log_file_id: str,
        preview: bool = False,
    ) -> bytes:
        """
        Get the content of a specific audit log file.

        Args:
            organization_rid: Organization Resource Identifier
            log_file_id: Log file identifier (from list_log_files)
            preview: Enable preview mode (default: False)

        Returns:
            Raw bytes content of the log file

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = AuditService()
            >>> content = service.get_log_file_content(
            ...     organization_rid="ri.multipass..organization.abc123",
            ...     log_file_id="2024-01-15"
            ... )
        """
        try:
            content = self.service.Organization.LogFile.content(
                organization_rid=organization_rid,
                log_file_id=log_file_id,
            )
            return content
        except Exception as e:
            raise RuntimeError(
                f"Failed to get audit log file content '{log_file_id}': {e}"
            )
