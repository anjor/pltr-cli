"""
Third-party applications service wrapper for the Foundry SDK
(``client.third_party_applications``).

``ThirdPartyApplication.get`` is beta and is always called with
``preview=True``. Methods return SDK models unchanged and let SDK exceptions
propagate so the error layer can classify them.
"""

from typing import Any

from .base import BaseService


class ThirdPartyApplicationsService(BaseService):
    """Service wrapper for Foundry third-party application operations."""

    def _get_service(self) -> Any:
        """Get the Foundry third-party applications service."""
        return self.client.third_party_applications

    def get_application(self, application_rid: str) -> Any:
        """Get a third-party application (``ThirdPartyApplication.get``, beta).

        Returns:
            A ``ThirdPartyApplication`` model. The API returns only its
            ``rid``, so this mainly confirms the application exists and that
            you can see it.
        """
        return self.service.ThirdPartyApplication.get(application_rid, preview=True)
