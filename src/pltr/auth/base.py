"""
Base authentication classes for Palantir Foundry.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class AuthProvider(ABC):
    """Abstract base class for authentication providers."""

    @abstractmethod
    def get_client(self) -> Any:
        """Return an authenticated Foundry client."""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate authentication credentials."""
        pass

    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Return authentication configuration."""
        pass


class AuthError(Exception):
    """Base exception for authentication errors."""

    pass


class InvalidCredentialsError(AuthError):
    """Raised when credentials are invalid."""

    pass


class MissingCredentialsError(AuthError):
    """Raised when required credentials are missing."""

    pass


class ProfileNotFoundError(AuthError):
    """Raised when a profile cannot be found."""

    pass
