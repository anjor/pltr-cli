"""
Base service class for Foundry API wrappers.
"""

from typing import Any, Optional, Dict
from abc import ABC, abstractmethod
import requests

from ..auth.manager import AuthManager
from ..auth.storage import CredentialStorage
from ..config.profiles import ProfileManager


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

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> requests.Response:
        """
        Make a direct HTTP request to Foundry API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., '/foundry-schema-inference/api/...')
            data: Form data to send
            json_data: JSON data to send
            headers: Additional headers

        Returns:
            Response object

        Raises:
            requests.HTTPError: If request fails
        """
        # Get credentials for authentication
        storage = CredentialStorage()
        profile_manager = ProfileManager()
        profile_name = self.profile or profile_manager.get_active_profile()
        if not profile_name:
            from ..auth.base import ProfileNotFoundError

            raise ProfileNotFoundError(
                "No profile specified and no default profile configured. "
                "Run 'pltr configure configure' to set up authentication."
            )
        credentials = storage.get_profile(profile_name)

        # Build full URL
        host = credentials.get("host", "").rstrip("/")
        url = f"{host}{endpoint}"

        # Set up headers with authentication
        request_headers = {
            "Authorization": f"Bearer {credentials.get('token')}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        # Make the request
        response = requests.request(
            method=method,
            url=url,
            data=data,
            json=json_data,
            headers=request_headers,
        )

        # Raise an error for bad status codes
        response.raise_for_status()

        return response
