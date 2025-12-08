"""
Base service class for Foundry API wrappers.
"""

from typing import Any, Optional, Dict, Callable, Iterator
from abc import ABC, abstractmethod
import json
import requests

from ..auth.manager import AuthManager
from ..auth.storage import CredentialStorage
from ..config.profiles import ProfileManager
from ..utils.pagination import (
    PaginationConfig,
    PaginationResult,
    IteratorPaginationHandler,
    ResponsePaginationHandler,
)


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

    def _paginate_iterator(
        self,
        iterator: Iterator[Any],
        config: PaginationConfig,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> PaginationResult:
        """
        Handle pagination for iterator-based SDK methods.

        Args:
            iterator: Iterator returned from SDK (e.g., ResourceIterator)
            config: Pagination configuration
            progress_callback: Optional progress callback

        Returns:
            PaginationResult with collected items and metadata

        Example:
            >>> iterator = self.service.Dataset.File.list(dataset_rid, page_size=20)
            >>> result = self._paginate_iterator(iterator, config)
        """
        handler = IteratorPaginationHandler()
        return handler.collect_pages(iterator, config, progress_callback)

    def _paginate_response(
        self,
        fetch_fn: Callable[[Optional[str]], Dict[str, Any]],
        config: PaginationConfig,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> PaginationResult:
        """
        Handle pagination for response-based SDK methods.

        Args:
            fetch_fn: Function that accepts page_token and returns dict with
                     'data' and 'next_page_token' keys
            config: Pagination configuration
            progress_callback: Optional progress callback

        Returns:
            PaginationResult with collected items and metadata

        Example:
            >>> def fetch(token):
            ...     response = self.service.User.list(page_token=token)
            ...     return self._serialize_response(response)
            >>> result = self._paginate_response(fetch, config)
        """
        handler = ResponsePaginationHandler()
        return handler.collect_pages(fetch_fn, config, progress_callback)

    def _serialize_response(self, response: Any) -> Dict[str, Any]:
        """
        Convert response object to serializable dictionary.

        This handles various SDK response types including Pydantic models,
        regular objects, and primitives.

        Args:
            response: Response object from SDK

        Returns:
            Serializable dictionary representation

        Note:
            This method was moved from AdminService to provide consistent
            serialization across all services.
        """
        if response is None:
            return {}

        # Handle different response types
        if hasattr(response, "dict"):
            # Pydantic models
            return response.dict()
        elif hasattr(response, "__dict__"):
            # Regular objects
            result = {}
            for key, value in response.__dict__.items():
                if not key.startswith("_"):
                    try:
                        # Try to serialize the value
                        json.dumps(value)
                        result[key] = value
                    except (TypeError, ValueError):
                        # Convert non-serializable values to string
                        result[key] = str(value)
            return result
        else:
            # Primitive types or already serializable
            try:
                json.dumps(response)
                return response
            except (TypeError, ValueError):
                return {"data": str(response)}
