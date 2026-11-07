"""
Data health service wrapper for the Foundry SDK (checks and check reports).

Every data health endpoint is beta, so every call passes ``preview=True``.
Methods return SDK models unchanged and let SDK exceptions propagate so the
error layer can classify them.
"""

from typing import Any, Dict, Optional

from .base import BaseService


class DataHealthService(BaseService):
    """Service wrapper for Foundry data health (``client.data_health``)."""

    def _get_service(self) -> Any:
        """Get the Foundry data health service."""
        return self.client.data_health

    # ------------------------------------------------------------------ checks

    def create_check(
        self, *, config: Dict[str, Any], intent: Optional[str] = None
    ) -> Any:
        """Create a check (``Check.create``, beta); returns the ``Check``.

        Args:
            config: The check configuration in the API's JSON shape; its
                ``type`` picks the kind of check, e.g.
                ``{"type": "buildStatus", "subject": {...},
                "statusCheckConfig": {"severity": "MODERATE"}}``. The SDK
                validates it.
            intent: Why the check was set up.
        """
        return self.service.Check.create(config=config, intent=intent, preview=True)

    def get_check(self, check_rid: str) -> Any:
        """Get a check (``Check.get``, beta); returns a ``Check``."""
        return self.service.Check.get(check_rid, preview=True)

    def replace_check(
        self, check_rid: str, *, config: Dict[str, Any], intent: Optional[str] = None
    ) -> Any:
        """Replace a check's configuration (``Check.replace``, beta).

        ``config`` has the shape of the create config without its
        ``subject``; a check's type and subject can't be changed. Returns
        the updated ``Check``.
        """
        return self.service.Check.replace(
            check_rid, config=config, intent=intent, preview=True
        )

    def delete_check(self, check_rid: str) -> None:
        """Delete a check (``Check.delete``, beta)."""
        self.service.Check.delete(check_rid, preview=True)

    # ----------------------------------------------------------- check reports

    def get_check_report(self, check_rid: str, check_report_rid: str) -> Any:
        """Get one report of a check (``Check.CheckReport.get``, beta).

        Returns a ``CheckReport`` (the result and a snapshot of the check).
        """
        return self.service.Check.CheckReport.get(
            check_rid, check_report_rid, preview=True
        )

    def get_latest_check_reports(
        self, check_rid: str, limit: Optional[int] = None
    ) -> Any:
        """Get a check's most recent reports (``Check.CheckReport.get_latest``, beta).

        Args:
            limit: Maximum number of reports (the API's default is 10, its
                maximum 100).

        Returns:
            ``GetLatestCheckReportsResponse`` (``.data``: ``CheckReport`` list).
        """
        return self.service.Check.CheckReport.get_latest(
            check_rid, limit=limit, preview=True
        )
