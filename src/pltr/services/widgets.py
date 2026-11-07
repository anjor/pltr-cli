"""
Widgets service wrapper for the Foundry SDK (``client.widgets``).

Every Widgets endpoint is beta, so every call passes the literal
``preview=True``. Methods return SDK models (or SDK iterators) unchanged and
let SDK exceptions propagate so the error layer can classify them.

Dev mode settings (``DevModeSettings``/``DevModeSettingsV2``: ``enable``,
``set_widget_set_by_id``, ``set_widget_set_manifest``) and
``Repository.publish`` have no curated command; they are available as
``pltr api widgets ...``.
"""

from typing import Any, Optional

from .base import BaseService


class WidgetsService(BaseService):
    """Service wrapper for Foundry Widgets operations."""

    def _get_service(self) -> Any:
        """Get the Foundry Widgets service."""
        return self.client.widgets

    def get_widget_set(self, widget_set_rid: str) -> Any:
        """Get a widget set (``WidgetSet.get``, beta); returns a ``WidgetSet``."""
        return self.service.WidgetSet.get(widget_set_rid, preview=True)

    def list_releases(
        self,
        widget_set_rid: str,
        *,
        branch: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a widget set's releases (``WidgetSet.Release.list``, beta).

        Args:
            widget_set_rid: Widget set RID.
            branch: Foundry branch (RID or dataset branch name) to list
                releases from; the default branch when omitted.
            page_size: Page size (the API's default when omitted).
            page_token: ``nextPageToken`` of an earlier page.

        Returns:
            The SDK ``ResourceIterator[Release]``; constructing it fetched one
            page (``.data``, ``.next_page_token``).
        """
        return self.service.WidgetSet.Release.list(
            widget_set_rid,
            branch=branch,
            page_size=page_size,
            page_token=page_token,
            preview=True,
        )

    def get_release(self, widget_set_rid: str, release_version: str) -> Any:
        """Get a release (``WidgetSet.Release.get``, beta); returns a ``Release``."""
        return self.service.WidgetSet.Release.get(
            widget_set_rid, release_version, preview=True
        )

    def delete_release(self, widget_set_rid: str, release_version: str) -> None:
        """Delete a release (``WidgetSet.Release.delete``, beta)."""
        self.service.WidgetSet.Release.delete(
            widget_set_rid, release_version, preview=True
        )

    def get_repository(self, repository_rid: str) -> Any:
        """Get a widget repository (``Repository.get``, beta); returns a ``Repository``."""
        return self.service.Repository.get(repository_rid, preview=True)
