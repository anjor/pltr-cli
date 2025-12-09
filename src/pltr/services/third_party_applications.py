"""
Third-party applications service wrapper for Foundry SDK.
Provides access to third-party application management operations.
"""

from typing import Any, Dict

from .base import BaseService


class ThirdPartyApplicationsService(BaseService):
    """Service wrapper for Foundry third-party applications operations."""

    def _get_service(self) -> Any:
        """Get the Foundry third-party applications service."""
        return self.client.third_party_applications.ThirdPartyApplication

    def get_application(
        self, application_rid: str, preview: bool = False
    ) -> Dict[str, Any]:
        """
        Get information about a specific third-party application.

        Args:
            application_rid: Third-party application Resource Identifier
                Expected format: ri.third-party-applications.<realm>.third-party-application.<locator>
                Example: ri.third-party-applications.main.third-party-application.my-app-123
            preview: Enable preview mode (default: False)

        Returns:
            Third-party application information dictionary containing:
            - rid: Application resource identifier
            - name: Application name
            - description: Application description (if available)
            - status: Application status (if available)

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = ThirdPartyApplicationsService()
            >>> app = service.get_application(
            ...     "ri.third-party-applications.main.third-party-application.my-app"
            ... )
            >>> print(app['name'])
        """
        try:
            application = self.service.get(application_rid, preview=preview)
            return self._serialize_response(application)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get third-party application {application_rid}: {e}"
            )
