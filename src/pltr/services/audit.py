"""
Audit service wrapper for Foundry SDK.
Provides access to audit log operations for compliance and security monitoring.
"""

from typing import Any, Dict, List, Optional
from .base import BaseService


class AuditService(BaseService):
    """Service wrapper for Foundry Audit operations."""

    def _get_service(self) -> Any:
        """Get the Foundry Audit service."""
        return self.client.audit

    def list_audit_logs(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        user_id: Optional[str] = None,
        preview: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List audit log entries.

        Args:
            start_time: Start time filter (ISO 8601 format)
            end_time: End time filter (ISO 8601 format)
            user_id: Filter by user ID
            preview: Enable preview mode (default: False)

        Returns:
            List of audit log entries

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = AuditService()
            >>> logs = service.list_audit_logs(
            ...     start_time="2024-01-01T00:00:00Z",
            ...     end_time="2024-01-31T23:59:59Z"
            ... )
        """
        try:
            # Build filter parameters
            kwargs = {"preview": preview}
            if start_time:
                kwargs["start_time"] = start_time
            if end_time:
                kwargs["end_time"] = end_time
            if user_id:
                kwargs["user_id"] = user_id

            logs = self.service.AuditLog.list(**kwargs)
            return [self._serialize_response(log) for log in logs]
        except Exception as e:
            raise RuntimeError(f"Failed to list audit logs: {e}")

    def get_audit_log(
        self,
        log_id: str,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Get a specific audit log entry.

        Args:
            log_id: Audit log identifier
            preview: Enable preview mode (default: False)

        Returns:
            Audit log entry dictionary containing:
            - id: Log entry identifier
            - timestamp: When the event occurred
            - user: User who performed the action
            - action: Type of action performed
            - resource: Resource that was affected
            - details: Additional event details

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = AuditService()
            >>> log = service.get_audit_log("audit-log-123")
        """
        try:
            log = self.service.AuditLog.get(log_id, preview=preview)
            return self._serialize_response(log)
        except Exception as e:
            raise RuntimeError(f"Failed to get audit log '{log_id}': {e}")

    def export_audit_logs(
        self,
        start_time: str,
        end_time: str,
        format: str = "json",
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Export audit logs for a time range.

        Args:
            start_time: Start time (ISO 8601 format)
            end_time: End time (ISO 8601 format)
            format: Export format (json, csv)
            preview: Enable preview mode (default: False)

        Returns:
            Export result with download URL or data

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = AuditService()
            >>> export = service.export_audit_logs(
            ...     start_time="2024-01-01T00:00:00Z",
            ...     end_time="2024-01-31T23:59:59Z",
            ...     format="csv"
            ... )
        """
        try:
            result = self.service.AuditLogExport.create(
                start_time=start_time,
                end_time=end_time,
                format=format,
                preview=preview,
            )
            return self._serialize_response(result)
        except Exception as e:
            raise RuntimeError(f"Failed to export audit logs: {e}")

    def get_export_status(
        self,
        export_id: str,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Get the status of an audit log export.

        Args:
            export_id: Export job identifier
            preview: Enable preview mode (default: False)

        Returns:
            Export status dictionary containing:
            - id: Export identifier
            - status: Current status (PENDING, IN_PROGRESS, COMPLETED, FAILED)
            - download_url: URL to download the export (if completed)
            - error: Error message (if failed)

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = AuditService()
            >>> status = service.get_export_status("export-123")
        """
        try:
            result = self.service.AuditLogExport.get(export_id, preview=preview)
            return self._serialize_response(result)
        except Exception as e:
            raise RuntimeError(f"Failed to get export status '{export_id}': {e}")
