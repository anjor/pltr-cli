"""
Credential check for ``pltr verify``: fetch the current user through the SDK.

Uses the same ``AuthManager`` (and so the same credentials, SDK client and
auth object) as every other service.
"""

from typing import Any

from ..auth.manager import AuthContext
from .base import BaseService


class VerifyService(BaseService):
    """Fetches the current user with the credentials other commands use."""

    def _get_service(self) -> Any:
        """Get the Foundry admin service."""
        return self.client.admin

    def get_auth_context(self) -> AuthContext:
        """Resolve the credentials this service's client uses.

        Returns:
            The ``AuthContext``: where the credentials came from (``source``),
            the host and the SDK client (shared with :attr:`client`).

        Raises:
            AuthError: (a subclass from ``pltr.auth.base``) if no usable
                credentials are configured or the keyring can't be read.
        """
        return self.auth_manager.get_auth_context(self.profile)

    def get_current_user(self) -> Any:
        """Get the current user (``admin.User.get_current``, GA); a ``User`` model."""
        return self.service.User.get_current()
