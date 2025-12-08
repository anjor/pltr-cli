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
            preview: Enable preview mode (default: False)

        Returns:
            Third-party application information dictionary

        Raises:
            RuntimeError: If the operation fails
        """
        try:
            application = self.service.get(application_rid, preview=preview)
            return self._serialize_response(application)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get third-party application {application_rid}: {e}"
            )
