"""
Verification command to test authentication.

``pltr verify`` fetches the current user with the SDK's
``admin.User.get_current()``, through the same client and credentials every
other command uses, and reports which auth source it used: a stored profile
(and how it was selected) or environment variables.

With ``--format json`` stdout is one JSON document,
``{"authSource": {...}, "user": {...}}``. Status lines go to stderr, and
failures follow the shared error contract (a structured error and the
documented exit code; see ``pltr.contract``).
"""

from typing import Any, Optional

import typer

from ..auth.manager import AuthContext, AuthSource
from ..contract import (
    Columns,
    FormatOption,
    OutputOption,
    ProfileOption,
    emit,
    info,
    pltr_command,
    spinner,
    success,
)
from ..services.verify import VerifyService

app = typer.Typer()


class VerificationFailed(Exception):
    """What verify was doing when the check failed, and what to check.

    The SDK (or HTTP) error is kept as ``__cause__``, so the error layer
    classifies that and uses this message as context.
    """


def _columns(source: AuthSource) -> Columns:
    """Curated table/CSV columns for ``{"authSource": ..., "user": User}``."""
    return {
        "Auth source": lambda _: source.describe(),
        "Auth type": "authSource.authType",
        "Host": "authSource.host",
        "Username": "user.username",
        "Name": lambda result: " ".join(
            part
            for part in (result["user"].given_name, result["user"].family_name)
            if part
        ),
        "Email": "user.email",
        "User ID": "user.id",
        "Organization": "user.organization",
        "Realm": "user.realm",
        "Status": "user.status",
    }


@app.callback(invoke_without_command=True)
@pltr_command(sdk="admin.User.get_current")
def verify(
    ctx: typer.Context,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """
    Verify authentication by fetching the current user from Foundry.

    Uses the same credentials as every other command: --profile, then
    PLTR_PROFILE, then the default profile, then the FOUNDRY_HOST plus
    FOUNDRY_TOKEN (or FOUNDRY_CLIENT_ID and FOUNDRY_CLIENT_SECRET) environment
    variables. Reports which one it used.
    """
    if ctx.invoked_subcommand is not None:
        return

    service = VerifyService(profile=profile)
    context = service.get_auth_context()
    info(f"Verifying {context.source.describe()} against {context.base_url}")
    with spinner("Fetching the current user..."):
        try:
            user = service.get_current_user()
        except Exception as error:
            raise VerificationFailed(_failure_context(error, context)) from error

    result = {"authSource": context.source.to_dict(), "user": user}
    emit(
        result,
        format=format,
        output=output,
        columns=_columns(context.source),
        title="Authentication verified",
    )
    success("Authentication successful")


def _failure_context(error: Exception, context: AuthContext) -> str:
    """Say which credentials failed and what to check, for a failed User.get_current."""
    import foundry_sdk

    source = context.source.describe()
    token_response = _oauth_token_response(error)
    if token_response is not None:
        body = " ".join(token_response.text.split())[:200]
        detail = f" (the token endpoint answered: {body})" if body else ""
        return f"The OAuth token request for {source} failed{detail}"
    if isinstance(error, foundry_sdk.UnauthorizedError):
        return f"Foundry rejected the credentials from {source}"
    if isinstance(error, foundry_sdk.PermissionDeniedError):
        return (
            f"Foundry accepted the credentials from {source} but refused to return "
            "the current user (OAuth clients need the api:admin-read scope)"
        )
    if isinstance(error, (foundry_sdk.NotFoundError, foundry_sdk.ApiNotFoundError)):
        return f"The current-user endpoint was not found on {context.base_url}"
    if isinstance(error, (foundry_sdk.ConnectionError, foundry_sdk.TimeoutError)):
        return (
            f"Could not reach {context.base_url} (check the host and your "
            "network connection)"
        )
    return f"Verifying {source} against {context.base_url} failed"


def _oauth_token_response(error: BaseException) -> Optional[Any]:
    """The response of a failed OAuth token request in ``error``'s cause chain."""
    import httpx

    current: Optional[BaseException] = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, httpx.HTTPStatusError) and str(
            current.request.url.path
        ).endswith("/oauth2/token"):
            return current.response
        current = current.__cause__ or current.__context__
    return None
