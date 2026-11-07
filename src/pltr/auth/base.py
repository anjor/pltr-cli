"""
Base authentication classes for Palantir Foundry.
"""

import unicodedata
from abc import ABC, abstractmethod
from typing import Dict, Any

#: What a token, client ID or client secret can't contain (for error messages).
INVALID_CREDENTIAL_CHARACTERS = (
    "whitespace or control characters (such as a line break)"
)


def has_invalid_characters(credential: str) -> bool:
    """
    Whether a credential contains whitespace or control characters.

    Tokens, client IDs and client secrets never do. One that does was usually
    read from a file with Windows line endings (``--token "$(cat token.txt)"``)
    or pasted with a line break; it can't be sent in an HTTP header. Callers
    strip surrounding whitespace first, then reject what this finds, without
    showing the value.

    Args:
        credential: The credential, without surrounding whitespace

    Returns:
        True if it contains whitespace, a control character or another
        non-printing character (Unicode category C, e.g. a byte order mark)
    """
    return any(
        char.isspace() or unicodedata.category(char).startswith("C")
        for char in credential
    )


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
