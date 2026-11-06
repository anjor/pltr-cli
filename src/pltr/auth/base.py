"""
Base authentication classes for Palantir Foundry.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


def normalize_host(host: str) -> str:
    """
    Normalise a Foundry host the way the SDK does.

    Accepts ``stack.palantirfoundry.com``, ``https://stack.palantirfoundry.com``
    and ``https://stack.palantirfoundry.com/`` alike and returns the bare host
    (plus any path the user gave), without scheme or surrounding slashes. The SDK
    client always talks HTTPS to this host.

    Args:
        host: Host as typed by the user, stored in a profile or set in the
            environment

    Returns:
        Host without scheme, e.g. ``stack.palantirfoundry.com``
    """
    return host.strip().split("://", 1)[-1].strip("/")


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


class KeyringUnavailableError(MissingCredentialsError):
    """
    Raised when the system keyring can't be used to read or store credentials.

    The keyring backend may be missing (common in CI, containers and agent
    sandboxes), fail, or not answer in time. The message points to
    environment-variable authentication, which needs no keyring.
    """

    pass


class ProfileNotFoundError(AuthError):
    """Raised when a profile cannot be found."""

    pass
