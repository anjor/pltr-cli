"""
Authentication manager: decides which credentials a command uses and builds
Foundry clients from them.

pltr uses the first of these that applies:

1. the ``--profile`` option (the ``profile`` argument)
2. the ``PLTR_PROFILE`` environment variable
3. the default profile (``profiles.json`` in the configuration directory)
4. environment variables: ``FOUNDRY_HOST`` with ``FOUNDRY_TOKEN``, or
   ``FOUNDRY_HOST`` with ``FOUNDRY_CLIENT_ID`` and ``FOUNDRY_CLIENT_SECRET``

Environment variables never override, or fill gaps in, a stored profile. The
environment-variable path doesn't touch the system keyring and doesn't need a
configuration directory.
"""

import os
from dataclasses import dataclass, replace
from typing import Any, Dict, Optional, Tuple, Union

from .base import (
    InvalidCredentialsError,
    KeyringUnavailableError,
    MissingCredentialsError,
    ProfileNotFoundError,
    normalize_host,
)
from .environment import (
    ENV_AUTH_HINT,
    PROFILE_ENV_VAR,
    EnvironmentCredentials,
    read_environment_credentials,
)
from .storage import CredentialStorage
from .token import TokenAuthProvider
from .oauth import OAuthClientProvider
from ..config.profiles import ProfileManager

# AuthSource.kind
SOURCE_PROFILE = "profile"
SOURCE_ENVIRONMENT = "environment"

# AuthSource.selected_by (profiles only)
SELECTED_BY_OPTION = "--profile"
SELECTED_BY_ENV_VAR = PROFILE_ENV_VAR
SELECTED_BY_DEFAULT = "default"

NO_AUTH_CONFIGURED_MESSAGE = (
    "No profile specified and no default profile configured, and no FOUNDRY_* "
    "environment variables are set. Run 'pltr configure configure' to create a "
    "profile, or for headless use (CI, containers, agents) "
    f"{ENV_AUTH_HINT}."
)

Provider = Union[TokenAuthProvider, OAuthClientProvider]


@dataclass(frozen=True)
class AuthSource:
    """
    Which credentials pltr uses, and why. Holds no secrets.

    Attributes:
        kind: ``"profile"`` (a stored profile) or ``"environment"``
            (FOUNDRY_* environment variables)
        profile: Profile name (profiles only)
        selected_by: How the profile was chosen: ``"--profile"``,
            ``"PLTR_PROFILE"`` or ``"default"`` (profiles only)
        auth_type: ``"token"`` or ``"oauth"``. For a profile it is known once
            the profile's credentials have been read.
        host: Foundry host without scheme. For a profile it is known once the
            profile's credentials have been read.
        variables: Environment variables the credentials came from
            (environment only)
    """

    kind: str
    profile: Optional[str] = None
    selected_by: Optional[str] = None
    auth_type: Optional[str] = None
    host: Optional[str] = None
    variables: Tuple[str, ...] = ()

    def describe(self) -> str:
        """Return a short human-readable description, e.g. for status lines."""
        if self.kind == SOURCE_PROFILE:
            reason = {
                SELECTED_BY_OPTION: " (from --profile)",
                SELECTED_BY_ENV_VAR: f" (from {PROFILE_ENV_VAR})",
                SELECTED_BY_DEFAULT: " (default profile)",
            }.get(self.selected_by or "", "")
            return f"profile '{self.profile}'{reason}"
        names = list(self.variables)
        if len(names) > 1:
            names = [", ".join(names[:-1]) + " and " + names[-1]]
        return " ".join(["environment variables", *names])

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe dict with camelCase keys, leaving out unset fields."""
        data: Dict[str, Any] = {
            "kind": self.kind,
            "profile": self.profile,
            "selectedBy": self.selected_by,
            "authType": self.auth_type,
            "host": self.host,
            "variables": list(self.variables) or None,
        }
        return {key: value for key, value in data.items() if value is not None}


class AuthContext:
    """
    Resolved credentials: where they came from, the SDK client and its auth.

    The SDK client and pltr's labeled direct-HTTP calls share one context, so
    they use the same ``foundry_sdk`` auth object and send the same token (for
    OAuth: one token request, refreshed by the SDK).
    """

    def __init__(self, source: AuthSource, provider: Provider, host: str):
        """
        Create a context for resolved credentials.

        Args:
            source: Where the credentials came from (complete: auth type and host set)
            provider: The provider built from the credentials
            host: Foundry host without scheme
        """
        self.source = source
        self.provider = provider
        self.host = host
        self._client: Optional[Any] = None

    @property
    def base_url(self) -> str:
        """HTTPS base URL of the Foundry host, as the SDK client uses it."""
        return f"https://{self.host}"

    @property
    def auth(self) -> Any:
        """The ``foundry_sdk`` auth object that the SDK client uses."""
        return self.provider.get_auth()

    @property
    def client(self) -> Any:
        """The ``FoundryClient`` for these credentials (created once)."""
        if self._client is None:
            self._client = self.provider.get_client()
        return self._client

    def get_token(self) -> str:
        """
        Return a bearer token from the auth object the SDK client uses.

        For a user token this is the token itself. For OAuth it is the
        client-credentials access token, which the SDK requests on first use
        and refreshes.

        Raises:
            InvalidCredentialsError: If Foundry rejects the OAuth client credentials
        """
        import httpx

        # An OAuth auth object learns the Foundry host from the client, when the
        # client first builds an API client with it. Build one now, so a token
        # can be fetched before (or without) any SDK call.
        _ = self.client.admin.User
        try:
            return self.auth.get_token().access_token
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status not in (400, 401, 403):
                raise
            raise InvalidCredentialsError(
                f"Foundry rejected the OAuth client credentials from "
                f"{self.source.describe()}: the token request returned HTTP "
                f"{status} ({e.response.text.strip()[:200]}). Check the client "
                "ID and secret."
            ) from e


class AuthManager:
    """Decides which credentials to use and provides configured Foundry clients."""

    def __init__(self):
        """Initialize authentication manager. Nothing is read until needed."""
        self._storage: Optional[CredentialStorage] = None
        self._profile_manager: Optional[ProfileManager] = None
        self._contexts: Dict[Optional[str], AuthContext] = {}

    @property
    def storage(self) -> CredentialStorage:
        """Keyring-backed credential storage, created on first use."""
        if self._storage is None:
            self._storage = CredentialStorage()
        return self._storage

    @property
    def profile_manager(self) -> ProfileManager:
        """Profile list and default profile, loaded on first use."""
        if self._profile_manager is None:
            self._profile_manager = ProfileManager()
        return self._profile_manager

    def resolve_auth_source(self, profile: Optional[str] = None) -> AuthSource:
        """
        Say which credentials a command would use, without reading any secret.

        Never touches the system keyring. For a profile, ``auth_type`` and
        ``host`` are left unset, because they are stored with the profile's
        credentials; ``get_auth_context(...).source`` has them.

        Args:
            profile: Profile name from ``--profile`` (None if not given)

        Returns:
            The auth source

        Raises:
            ProfileNotFoundError: If no profile is selected and no FOUNDRY_*
                environment variables are set
            MissingCredentialsError: If FOUNDRY_* environment variables are set
                but incomplete
        """
        return self._resolve(profile)[0]

    def get_auth_context(self, profile: Optional[str] = None) -> AuthContext:
        """
        Return the resolved credentials: their source, SDK client and auth object.

        The result is cached per profile argument, so a service's SDK client and
        its direct-HTTP calls share one auth object.

        Args:
            profile: Profile name from ``--profile`` (None if not given)

        Raises:
            ProfileNotFoundError: If the selected profile doesn't exist, or
                nothing is configured
            MissingCredentialsError: If credentials are incomplete
            KeyringUnavailableError: If a stored profile is needed but the
                system keyring can't be used
        """
        key = profile or None
        context = self._contexts.get(key)
        if context is None:
            context = self._load_auth_context(key)
            self._contexts[key] = context
        return context

    def get_client(self, profile: Optional[str] = None) -> Any:
        """
        Get an authenticated Foundry client.

        Args:
            profile: Profile name from ``--profile`` (None if not given; see the
                module docstring for the precedence)

        Returns:
            Configured FoundryClient instance

        Raises:
            ProfileNotFoundError: If the selected profile doesn't exist, or
                nothing is configured
            MissingCredentialsError: If credentials are incomplete
            KeyringUnavailableError: If a stored profile is needed but the
                system keyring can't be used
        """
        return self.get_auth_context(profile).client

    def _resolve(
        self, profile: Optional[str]
    ) -> Tuple[AuthSource, Optional[EnvironmentCredentials]]:
        selected = self._select_profile(profile)
        if selected is not None:
            name, selected_by = selected
            source = AuthSource(
                kind=SOURCE_PROFILE, profile=name, selected_by=selected_by
            )
            return source, None

        environment = read_environment_credentials()
        if environment is None:
            raise ProfileNotFoundError(NO_AUTH_CONFIGURED_MESSAGE)
        source = AuthSource(
            kind=SOURCE_ENVIRONMENT,
            auth_type=environment.auth_type,
            host=environment.host,
            variables=environment.variables,
        )
        return source, environment

    def _select_profile(self, profile: Optional[str]) -> Optional[Tuple[str, str]]:
        """Return (profile name, selected_by), or None when no profile is selected."""
        if profile:
            return profile, SELECTED_BY_OPTION
        active = self.profile_manager.get_active_profile()
        if not active:
            return None
        env_profile = os.environ.get(PROFILE_ENV_VAR, "").strip()
        if env_profile and active == env_profile:
            return active, SELECTED_BY_ENV_VAR
        return active, SELECTED_BY_DEFAULT

    def _load_auth_context(self, profile: Optional[str]) -> AuthContext:
        source, environment = self._resolve(profile)
        if environment is not None:
            credentials = environment.as_profile_credentials()
        else:
            credentials = self._read_profile_credentials(source)

        provider = self._create_provider(credentials)
        host = normalize_host(credentials["host"])
        source = replace(source, auth_type=credentials["auth_type"], host=host)
        return AuthContext(source=source, provider=provider, host=host)

    def _read_profile_credentials(self, source: AuthSource) -> Dict[str, Any]:
        name = source.profile or ""
        try:
            return self.storage.get_profile(name)
        except KeyringUnavailableError as e:
            raise KeyringUnavailableError(f"{e} {self._env_auth_note(source)}") from e
        except ProfileNotFoundError:
            selection = {
                SELECTED_BY_ENV_VAR: f" (selected by {PROFILE_ENV_VAR})",
                SELECTED_BY_DEFAULT: " (the default profile)",
            }.get(source.selected_by or "", "")
            raise ProfileNotFoundError(
                f"Profile '{name}' not found{selection}. "
                f"Run 'pltr configure configure --profile {name}' to set it up."
            ) from None

    def _env_auth_note(self, source: AuthSource) -> str:
        """Explain why environment variables weren't used for this command."""
        prefix = "Environment variables are only used when no profile is selected"
        if source.selected_by == SELECTED_BY_OPTION:
            return f"{prefix}, so also drop --profile."
        if source.selected_by == SELECTED_BY_ENV_VAR:
            return f"{prefix}, so also unset {PROFILE_ENV_VAR}."
        return (
            f"{prefix}, and '{source.profile}' is the default profile "
            f"(set in {self.profile_manager.profiles_file})."
        )

    def _create_provider(self, credentials: dict) -> Provider:
        """
        Create an auth provider from credentials.

        Args:
            credentials: Dictionary containing auth configuration

        Returns:
            Configured auth provider

        Raises:
            MissingCredentialsError: If auth type is unknown or credentials incomplete
        """
        auth_type = credentials.get("auth_type")
        host = credentials.get("host")

        if not auth_type:
            raise MissingCredentialsError(
                "Authentication type not specified in credentials"
            )
        if not host:
            raise MissingCredentialsError("Host URL not specified in credentials")

        if auth_type == "token":
            token = credentials.get("token")
            if not token:
                raise MissingCredentialsError("Token not found in credentials")
            return TokenAuthProvider(token=token, host=host)

        elif auth_type == "oauth":
            client_id = credentials.get("client_id")
            client_secret = credentials.get("client_secret")
            if not client_id or not client_secret:
                raise MissingCredentialsError("OAuth client credentials incomplete")
            return OAuthClientProvider(
                client_id=client_id,
                client_secret=client_secret,
                host=host,
                scopes=credentials.get("scopes", []),
            )

        else:
            raise MissingCredentialsError(f"Unknown authentication type: {auth_type}")

    def get_current_profile(self) -> Optional[str]:
        """
        Get the name of the profile commands use when no --profile is given.

        Returns:
            Profile name, or None when no profile is selected (commands then
            use environment variables, if set)
        """
        selected = self._select_profile(None)
        return selected[0] if selected else None

    def validate_profile(self, profile: Optional[str] = None) -> bool:
        """
        Validate that a profile's credentials work.

        Args:
            profile: Profile name (uses active profile if not specified)

        Returns:
            True if credentials are valid

        Raises:
            Exception if validation fails
        """
        self.get_client(profile)
        # The actual validation will happen when we try to use the client
        # in the verify command
        return True
