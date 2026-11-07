"""
Audit service wrapper for the Foundry SDK audit API.

``Organization.LogFile.list`` and ``Organization.LogFile.content`` are GA
endpoints, called without ``preview``. Methods return the SDK results
unchanged (a one-page ``ResourceIterator`` of ``LogFile`` models, or a
streamed response of the log file's bytes) and let SDK exceptions propagate
so the error layer can classify them.
"""

from datetime import date
from typing import Any, Optional

from .base import BaseService


class AuditService(BaseService):
    """Service wrapper for Foundry audit log files (``client.audit``)."""

    def _get_service(self) -> Any:
        """Get the Foundry audit service."""
        return self.client.audit

    def list_log_files(
        self,
        organization_rid: str,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of an organization's audit log files (``LogFile.list``, GA).

        Args:
            organization_rid: Organization RID (ri.multipass..organization.<id>)
            start_date: First day of audit events to list; the API requires it
                unless ``page_token`` is given
            end_date: Last day of audit events to list (inclusive); without
                it the listing has no end
            page_size: Number of log files per page
            page_token: ``nextPageToken`` of an earlier page

        Returns:
            The SDK ``ResourceIterator[LogFile]``; constructing it fetched
            exactly one page (``.data``, ``.next_page_token``). A ``LogFile``
            has only an ``id``.
        """
        return self.service.Organization.LogFile.list(
            organization_rid,
            start_date=start_date,
            end_date=end_date,
            page_size=page_size,
            page_token=page_token,
        )

    def download_log_file(self, organization_rid: str, log_file_id: str) -> Any:
        """Request an audit log file's content as a stream (``LogFile.content``, GA).

        The request is made, and API errors are raised, before this returns;
        the body is read only while it is streamed.

        Args:
            organization_rid: Organization RID
            log_file_id: Log file ID (the ``id`` of a listed ``LogFile``)

        Returns:
            The SDK's streaming context manager: ``with download as
            response:`` then ``response.iter_bytes()`` yields the content,
            unchanged.
        """
        return self.service.Organization.LogFile.with_streaming_response.content(
            organization_rid, log_file_id
        )
