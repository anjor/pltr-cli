"""
Widgets service wrapper for Foundry SDK.
Provides access to widget set operations for managing Foundry widgets.

Note: All Widgets APIs are in Private Beta and require preview=True.
"""

from typing import Any, Dict, List, Optional

from .base import BaseService


class WidgetsService(BaseService):
    """Service wrapper for Foundry Widgets operations."""

    def _get_service(self) -> Any:
        """Get the Foundry Widgets service."""
        return self.client.widgets

    # ===== DevModeSettings =====

    def get_dev_mode_settings(self) -> Dict[str, Any]:
        """
        Get the dev mode settings for the current user.

        Returns:
            Dictionary containing dev mode settings:
            - enabled: Whether dev mode is enabled
            - paused: Whether dev mode is paused
            - widgetSetSettings: Settings per widget set

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = WidgetsService()
            >>> settings = service.get_dev_mode_settings()
        """
        try:
            settings = self.service.DevModeSettings.get(preview=True)
            return self._serialize_response(settings)
        except Exception as e:
            raise RuntimeError(f"Failed to get dev mode settings: {e}") from e

    def enable_dev_mode(self) -> Dict[str, Any]:
        """
        Enable dev mode for the current user.

        Returns:
            Dictionary containing updated dev mode settings

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = WidgetsService()
            >>> settings = service.enable_dev_mode()
        """
        try:
            settings = self.service.DevModeSettings.enable(preview=True)
            return self._serialize_response(settings)
        except Exception as e:
            raise RuntimeError(f"Failed to enable dev mode: {e}") from e

    def disable_dev_mode(self) -> Dict[str, Any]:
        """
        Disable dev mode for the current user.

        Returns:
            Dictionary containing updated dev mode settings

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = WidgetsService()
            >>> settings = service.disable_dev_mode()
        """
        try:
            settings = self.service.DevModeSettings.disable(preview=True)
            return self._serialize_response(settings)
        except Exception as e:
            raise RuntimeError(f"Failed to disable dev mode: {e}") from e

    def pause_dev_mode(self) -> Dict[str, Any]:
        """
        Pause dev mode for the current user.

        Returns:
            Dictionary containing updated dev mode settings

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = WidgetsService()
            >>> settings = service.pause_dev_mode()
        """
        try:
            settings = self.service.DevModeSettings.pause(preview=True)
            return self._serialize_response(settings)
        except Exception as e:
            raise RuntimeError(f"Failed to pause dev mode: {e}") from e

    # ===== WidgetSet =====

    def get_widget_set(self, widget_set_rid: str) -> Dict[str, Any]:
        """
        Get a widget set by RID.

        Args:
            widget_set_rid: Widget set Resource Identifier
                Expected format: ri.widgetregistry..widget-set.<locator>

        Returns:
            Dictionary containing widget set details:
            - rid: Widget set RID
            - name: Widget set name
            - widgets: List of widgets in the set

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = WidgetsService()
            >>> widget_set = service.get_widget_set(
            ...     "ri.widgetregistry..widget-set.abc123"
            ... )
        """
        try:
            widget_set = self.service.WidgetSet.get(
                widget_set_rid=widget_set_rid,
                preview=True,
            )
            return self._serialize_response(widget_set)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get widget set '{widget_set_rid}': {e}"
            ) from e

    # ===== Releases =====

    def list_releases(
        self,
        widget_set_rid: str,
        page_size: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List releases for a widget set.

        Args:
            widget_set_rid: Widget set Resource Identifier
            page_size: Number of results per page (optional)

        Returns:
            List of release dictionaries containing:
            - version: Release version (semver)
            - createdAt: Creation timestamp
            - createdBy: User who created the release

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = WidgetsService()
            >>> releases = service.list_releases(
            ...     widget_set_rid="ri.widgetregistry..widget-set.abc123"
            ... )
        """
        try:
            kwargs: Dict[str, Any] = {}
            if page_size:
                kwargs["page_size"] = page_size

            releases = self.service.WidgetSet.Release.list(
                widget_set_rid=widget_set_rid,
                preview=True,
                **kwargs,
            )
            return [self._serialize_response(r) for r in releases]
        except Exception as e:
            raise RuntimeError(
                f"Failed to list releases for '{widget_set_rid}': {e}"
            ) from e

    def get_release(
        self,
        widget_set_rid: str,
        release_version: str,
    ) -> Dict[str, Any]:
        """
        Get a specific release of a widget set.

        Args:
            widget_set_rid: Widget set Resource Identifier
            release_version: Semantic version of the release (e.g., "1.2.0")

        Returns:
            Dictionary containing release details:
            - version: Release version
            - createdAt: Creation timestamp
            - widgets: Widgets included in this release

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = WidgetsService()
            >>> release = service.get_release(
            ...     widget_set_rid="ri.widgetregistry..widget-set.abc123",
            ...     release_version="1.0.0"
            ... )
        """
        try:
            release = self.service.WidgetSet.Release.get(
                widget_set_rid=widget_set_rid,
                release_version=release_version,
                preview=True,
            )
            return self._serialize_response(release)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get release '{release_version}' for '{widget_set_rid}': {e}"
            ) from e

    def delete_release(
        self,
        widget_set_rid: str,
        release_version: str,
    ) -> None:
        """
        Delete a specific release of a widget set.

        Args:
            widget_set_rid: Widget set Resource Identifier
            release_version: Semantic version of the release to delete

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = WidgetsService()
            >>> service.delete_release(
            ...     widget_set_rid="ri.widgetregistry..widget-set.abc123",
            ...     release_version="1.0.0"
            ... )
        """
        try:
            self.service.WidgetSet.Release.delete(
                widget_set_rid=widget_set_rid,
                release_version=release_version,
                preview=True,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to delete release '{release_version}' for '{widget_set_rid}': {e}"
            ) from e

    # ===== Repository =====

    def get_repository(self, repository_rid: str) -> Dict[str, Any]:
        """
        Get a widget repository by RID.

        Args:
            repository_rid: Repository Resource Identifier
                Expected format: ri.stemma.main.repository.<locator>

        Returns:
            Dictionary containing repository details:
            - rid: Repository RID
            - name: Repository name
            - widgetSetRid: Associated widget set RID

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = WidgetsService()
            >>> repo = service.get_repository(
            ...     "ri.stemma.main.repository.abc123"
            ... )
        """
        try:
            repository = self.service.Repository.get(
                repository_rid=repository_rid,
                preview=True,
            )
            return self._serialize_response(repository)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get repository '{repository_rid}': {e}"
            ) from e
