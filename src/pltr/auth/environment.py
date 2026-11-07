"""
Environment-variable credentials for headless use (CI, containers, AI agents).

pltr reads these variables only when no profile is selected (see
``pltr.auth.manager`` for the precedence). Reading them never touches the
system keyring or the configuration directory.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from .base import (
    INVALID_CREDENTIAL_CHARACTERS,
    InvalidCredentialsError,
    MissingCredentialsError,
    has_invalid_characters,
    normalize_host,
)

PROFILE_ENV_VAR = "PLTR_PROFILE"
HOST_ENV_VAR = "FOUNDRY_HOST"
# The name the Foundry SDK itself reads; accepted when FOUNDRY_HOST isn't set.
HOSTNAME_ENV_VAR = "FOUNDRY_HOSTNAME"
TOKEN_ENV_VAR = "FOUNDRY_TOKEN"
CLIENT_ID_ENV_VAR = "FOUNDRY_CLIENT_ID"
CLIENT_SECRET_ENV_VAR = "FOUNDRY_CLIENT_SECRET"

AUTH_ENV_VARS = (
    HOST_ENV_VAR,
    HOSTNAME_ENV_VAR,
    TOKEN_ENV_VAR,
    CLIENT_ID_ENV_VAR,
    CLIENT_SECRET_ENV_VAR,
)

ENV_AUTH_HINT = (
    f"set {HOST_ENV_VAR} and {TOKEN_ENV_VAR}, or {HOST_ENV_VAR}, "
    f"{CLIENT_ID_ENV_VAR} and {CLIENT_SECRET_ENV_VAR}"
)


@dataclass(frozen=True)
class EnvironmentCredentials:
    """Credentials read from environment variables. Secrets are kept out of repr."""

    auth_type: str
    host: str
    variables: Tuple[str, ...]
    token: Optional[str] = field(default=None, repr=False)
    client_id: Optional[str] = None
    client_secret: Optional[str] = field(default=None, repr=False)

    def as_profile_credentials(self) -> Dict[str, Any]:
        """Return the credentials in the shape of a stored profile."""
        credentials: Dict[str, Any] = {"auth_type": self.auth_type, "host": self.host}
        if self.auth_type == "token":
            credentials["token"] = self.token
        else:
            credentials["client_id"] = self.client_id
            credentials["client_secret"] = self.client_secret
        return credentials


#: What error messages call each credential variable's value.
_CREDENTIAL_LABELS = {
    TOKEN_ENV_VAR: "token",
    CLIENT_ID_ENV_VAR: "OAuth client ID",
    CLIENT_SECRET_ENV_VAR: "OAuth client secret",
}


def _read(name: str) -> Optional[str]:
    """The variable's value without surrounding whitespace (e.g. a trailing CR/LF)."""
    value = os.environ.get(name, "").strip()
    return value or None


def read_environment_credentials() -> Optional[EnvironmentCredentials]:
    """
    Read Foundry credentials from environment variables.

    Token auth needs ``FOUNDRY_HOST`` and ``FOUNDRY_TOKEN``. OAuth (client
    credentials) needs ``FOUNDRY_HOST``, ``FOUNDRY_CLIENT_ID`` and
    ``FOUNDRY_CLIENT_SECRET``. If ``FOUNDRY_TOKEN`` is set, token auth is used.
    ``FOUNDRY_HOSTNAME`` is accepted when ``FOUNDRY_HOST`` isn't set.
    Whitespace around a value (such as a trailing CR/LF) is ignored.

    Returns:
        The credentials, or None when none of the variables are set

    Raises:
        MissingCredentialsError: If some of the variables are set but they
            don't make a complete set
        InvalidCredentialsError: If a credential that would be used contains
            whitespace or control characters (the message names the variable,
            never its value)
    """
    values = {name: _read(name) for name in AUTH_ENV_VARS}
    if not any(values.values()):
        return None

    token = values[TOKEN_ENV_VAR]
    client_id = values[CLIENT_ID_ENV_VAR]
    client_secret = values[CLIENT_SECRET_ENV_VAR]

    host_variable = HOST_ENV_VAR if values[HOST_ENV_VAR] else HOSTNAME_ENV_VAR
    raw_host = values[host_variable]

    if token:
        credential_variables: Tuple[str, ...] = (TOKEN_ENV_VAR,)
    elif client_id and client_secret:
        credential_variables = (CLIENT_ID_ENV_VAR, CLIENT_SECRET_ENV_VAR)
    elif client_id or client_secret:
        present, missing = (
            (CLIENT_ID_ENV_VAR, CLIENT_SECRET_ENV_VAR)
            if client_id
            else (CLIENT_SECRET_ENV_VAR, CLIENT_ID_ENV_VAR)
        )
        raise MissingCredentialsError(
            f"{present} is set but {missing} is not. OAuth authentication from "
            f"environment variables needs {HOST_ENV_VAR}, {CLIENT_ID_ENV_VAR} "
            f"and {CLIENT_SECRET_ENV_VAR}."
        )
    else:
        raise MissingCredentialsError(
            f"{host_variable} is set but no credentials are: set {TOKEN_ENV_VAR}, "
            f"or {CLIENT_ID_ENV_VAR} and {CLIENT_SECRET_ENV_VAR}."
        )

    if not raw_host:
        raise MissingCredentialsError(
            f"{' and '.join(credential_variables)} "
            f"{'is' if len(credential_variables) == 1 else 'are'} set but "
            f"{HOST_ENV_VAR} is not. Set {HOST_ENV_VAR} to your Foundry host, "
            "for example your-stack.palantirfoundry.com."
        )
    host = normalize_host(raw_host)
    if not host:
        raise MissingCredentialsError(
            f"{host_variable} ({raw_host!r}) does not contain a host name. Set it "
            "to your Foundry host, for example your-stack.palantirfoundry.com."
        )
    for name in credential_variables:
        if has_invalid_characters(values[name] or ""):
            raise InvalidCredentialsError(
                f"{name} contains {INVALID_CREDENTIAL_CHARACTERS} inside its "
                f"value. Set it to the {_CREDENTIAL_LABELS[name]} alone."
            )

    variables = (host_variable,) + credential_variables
    if token:
        return EnvironmentCredentials(
            auth_type="token", host=host, variables=variables, token=token
        )
    return EnvironmentCredentials(
        auth_type="oauth",
        host=host,
        variables=variables,
        client_id=client_id,
        client_secret=client_secret,
    )
