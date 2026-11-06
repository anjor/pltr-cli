"""
Credential storage in the system keyring.

Some keyring backends block indefinitely when they can't show an unlock or
access prompt, for example the macOS Keychain over SSH or in an agent sandbox.
Every keyring call therefore runs with a time limit: ``PLTR_KEYRING_TIMEOUT``
seconds (30 by default; 0 or a negative value waits indefinitely). A keyring
that is missing, fails or doesn't answer in time raises
``KeyringUnavailableError``, whose message points to environment-variable
authentication, which needs no keyring.
"""

import json
import os
import threading
from typing import Any, Callable, Dict, Optional, Tuple, Type

from .base import (
    KeyringUnavailableError,
    MissingCredentialsError,
    ProfileNotFoundError,
)
from .environment import ENV_AUTH_HINT

KEYRING_TIMEOUT_ENV_VAR = "PLTR_KEYRING_TIMEOUT"
DEFAULT_KEYRING_TIMEOUT = 30.0


def keyring_timeout() -> Optional[float]:
    """
    Return how long to wait for the keyring, in seconds.

    Returns:
        The time limit from ``PLTR_KEYRING_TIMEOUT`` (or the default when it's
        unset or not a number), or None for no limit when it's 0 or negative
    """
    raw = os.environ.get(KEYRING_TIMEOUT_ENV_VAR, "").strip()
    if not raw:
        return DEFAULT_KEYRING_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_KEYRING_TIMEOUT
    return value if value > 0 else None


class _KeyringTimedOut(Exception):
    def __init__(self, timeout: float):
        super().__init__(f"the keyring did not answer within {timeout:g} seconds")


def _run_with_timeout(func: Callable[..., Any], *args: Any) -> Any:
    """Run a keyring call, giving up after keyring_timeout() seconds."""
    timeout = keyring_timeout()
    if timeout is None:
        return func(*args)

    outcome: Dict[str, Any] = {}

    def call() -> None:
        try:
            outcome["result"] = func(*args)
        except BaseException as e:  # re-raised in the calling thread
            outcome["error"] = e

    # A daemon thread: if the backend never answers, it must not keep pltr alive.
    worker = threading.Thread(target=call, name="pltr-keyring", daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise _KeyringTimedOut(timeout)
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("result")


def _as_sentence(text: str) -> str:
    text = text.strip() or "unknown error"
    return text if text.endswith((".", "!", "?")) else f"{text}."


class CredentialStorage:
    """Manages secure storage of authentication credentials."""

    SERVICE_NAME = "pltr-cli"

    def __init__(self):
        """Initialize credential storage."""
        # Imported here so that environment-variable auth never loads it.
        import keyring
        import keyring.errors

        self.keyring = keyring

    def _call_keyring(
        self,
        action: str,
        profile: str,
        func: Callable[..., Any],
        *args: Any,
        passthrough: Tuple[Type[BaseException], ...] = (),
    ) -> Any:
        try:
            return _run_with_timeout(func, *args)
        except passthrough:
            raise
        except _KeyringTimedOut as e:
            raise KeyringUnavailableError(
                self._unavailable_message(action, profile, str(e))
            ) from None
        except Exception as e:
            raise KeyringUnavailableError(
                self._unavailable_message(action, profile, str(e) or type(e).__name__)
            ) from e

    @staticmethod
    def _unavailable_message(action: str, profile: str, reason: str) -> str:
        return (
            f"The system keyring could not {action} the credentials of profile "
            f"'{profile}': {_as_sentence(reason)} pltr keeps profile credentials "
            "in the system keyring. Where no keyring is usable (CI, containers, "
            "agent sandboxes, SSH sessions), authenticate with environment "
            f"variables instead: {ENV_AUTH_HINT}."
        )

    def save_profile(self, profile: str, credentials: Dict[str, Any]) -> None:
        """
        Save credentials for a profile.

        Args:
            profile: Profile name
            credentials: Dictionary of credentials to store

        Raises:
            KeyringUnavailableError: If the keyring can't store them
        """
        # Convert credentials to JSON string for storage
        credentials_json = json.dumps(credentials)
        self._call_keyring(
            "save",
            profile,
            self.keyring.set_password,
            self.SERVICE_NAME,
            profile,
            credentials_json,
        )

    def get_profile(self, profile: str) -> Dict[str, Any]:
        """
        Retrieve credentials for a profile.

        Args:
            profile: Profile name

        Returns:
            Dictionary of stored credentials

        Raises:
            ProfileNotFoundError: If profile doesn't exist
            MissingCredentialsError: If the stored credentials are unreadable
            KeyringUnavailableError: If the keyring can't be used
        """
        credentials_json = self._call_keyring(
            "read", profile, self.keyring.get_password, self.SERVICE_NAME, profile
        )
        if not credentials_json:
            raise ProfileNotFoundError(f"Profile '{profile}' not found")

        try:
            credentials = json.loads(credentials_json)
        except ValueError:
            credentials = None
        if not isinstance(credentials, dict):
            raise MissingCredentialsError(
                f"The stored credentials of profile '{profile}' are unreadable. "
                f"Run 'pltr configure configure --profile {profile}' to store "
                "them again."
            )
        return credentials

    def delete_profile(self, profile: str) -> None:
        """
        Delete a profile's credentials.

        Args:
            profile: Profile name

        Raises:
            ProfileNotFoundError: If the keyring has no credentials for it
            KeyringUnavailableError: If the keyring can't be used
        """
        try:
            self._call_keyring(
                "delete",
                profile,
                self.keyring.delete_password,
                self.SERVICE_NAME,
                profile,
                passthrough=(self.keyring.errors.PasswordDeleteError,),
            )
        except self.keyring.errors.PasswordDeleteError:
            raise ProfileNotFoundError(f"Profile '{profile}' not found")

    def list_profiles(self) -> list:
        """
        List all available profiles.

        Returns:
            List of profile names
        """
        # Note: keyring doesn't provide a direct way to list all usernames
        # for a service, so we'll need to store this separately in config
        # This is a placeholder that will be integrated with config/profiles.py
        return []

    def profile_exists(self, profile: str) -> bool:
        """
        Check if a profile exists.

        Args:
            profile: Profile name

        Returns:
            True if profile exists, False otherwise

        Raises:
            KeyringUnavailableError: If the keyring can't be used
        """
        credentials = self._call_keyring(
            "read", profile, self.keyring.get_password, self.SERVICE_NAME, profile
        )
        return credentials is not None
