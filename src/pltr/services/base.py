"""
Base service class for Foundry API wrappers.
"""

from typing import Any, Optional
from abc import ABC, abstractmethod

from ..auth.manager import AuthManager


class BaseService(ABC):
    """Base class for Foundry service wrappers."""

    def __init__(self, profile: Optional[str] = None):
        """
        Initialize base service.

        Args:
            profile: Authentication profile name (uses default if not specified)
        """
        self.profile = profile
        self.auth_manager = AuthManager()
        self._client: Optional[Any] = None

    @property
    def client(self) -> Any:
        """
        Get authenticated Foundry client.

        Returns:
            Configured FoundryClient instance

        Raises:
            ProfileNotFoundError: If profile doesn't exist
            MissingCredentialsError: If credentials are incomplete
        """
        if self._client is None:
            self._client = self.auth_manager.get_client(self.profile)
        return self._client

    @abstractmethod
    def _get_service(self) -> Any:
        """
        Get the specific Foundry SDK service instance.

        Returns:
            Configured service instance from foundry-platform-sdk

        This method should be implemented by subclasses to return the
        appropriate service (e.g., client.datasets, client.ontology)
        """
        pass

    @property
    def service(self) -> Any:
        """
        Get the Foundry SDK service instance.

        Returns:
            Configured service instance
        """
        return self._get_service()
