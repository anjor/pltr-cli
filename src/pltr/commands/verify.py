"""
Verification command to test authentication.

``pltr verify`` fetches the current user with the SDK's
``admin.User.get_current()``, through the same client and credentials every
other command uses, and reports which auth source it used: a stored profile
(and how it was selected) or environment variables.

stdout carries the result; status lines and errors go to stderr. With
``--format json`` stdout is one JSON document,
``{"authSource": {...}, "user": {...}}``, and a failure writes one JSON error
object to stderr.
"""

import csv
import io
import json
import os
import sys
from typing import Any, Dict, List, NoReturn, Optional, Tuple

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from ..auth.base import AuthError
from ..auth.manager import AuthContext, AuthManager

app = typer.Typer()
console = Console()  # stdout: result data only
err_console = Console(stderr=True)  # stderr: status lines and errors

FORMATS = ("table", "json", "csv")

# Exit codes (roadmap decision 6) and error types for structured errors.
EXIT_UNEXPECTED = 1
EXIT_AUTH = 3
EXIT_PERMISSION_DENIED = 4
EXIT_NOT_FOUND = 5
EXIT_API = 7

ERROR_TYPES = {
    EXIT_UNEXPECTED: "unexpected",
    EXIT_AUTH: "auth",
    EXIT_PERMISSION_DENIED: "permission_denied",
    EXIT_NOT_FOUND: "not_found",
    EXIT_API: "api",
}


@app.callback(invoke_without_command=True)
def verify(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile to verify (default: whatever other commands would use)",
    ),
    output_format: Optional[str] = typer.Option(
        None,
        "--format",
        "-f",
        help="Output format: table, json or csv (default: PLTR_FORMAT, else table)",
    ),
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

    if output_format is None:
        # PLTR_FORMAT sets the default; a value that isn't a format is ignored.
        env_format = os.environ.get("PLTR_FORMAT", "").strip().lower()
        output_format = env_format if env_format in FORMATS else "table"
    output_format = output_format.strip().lower()
    if output_format not in FORMATS:
        raise typer.BadParameter(
            f"'{output_format}' is not one of {', '.join(FORMATS)}.",
            param_hint="'--format'",
        )
    json_mode = output_format == "json"

    try:
        context = AuthManager().get_auth_context(profile)
    except AuthError as e:
        _fail(json_mode, EXIT_AUTH, str(e))

    if not json_mode:
        err_console.print(
            f"Verifying {escape(context.source.describe())} "
            f"against {escape(context.base_url)}",
            soft_wrap=True,
        )

    try:
        user = context.client.admin.User.get_current()
    except Exception as e:
        exit_code, message, details = _describe_failure(e, context)
        _fail(json_mode, exit_code, message, details)

    if json_mode:
        result = {
            "authSource": context.source.to_dict(),
            "user": user.model_dump(mode="json", by_alias=True, exclude_none=True),
        }
        print(json.dumps(result, indent=2))
        return

    rows = _summary_rows(context, user)
    if output_format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([label for label, _ in rows])
        writer.writerow([value for _, value in rows])
        sys.stdout.write(buffer.getvalue())
    else:
        table = Table(title="Authentication verified", show_header=False)
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Value", overflow="fold")
        for label, value in rows:
            table.add_row(label, escape(value))
        console.print(table)
    err_console.print("[green]✓[/green] Authentication successful")


def _summary_rows(context: AuthContext, user: Any) -> List[Tuple[str, str]]:
    """Curated rows for table and CSV output (fields of admin.User)."""
    name = " ".join(part for part in (user.given_name, user.family_name) if part)
    return [
        ("Auth source", context.source.describe()),
        ("Auth type", context.source.auth_type or ""),
        ("Host", context.host),
        ("Username", user.username),
        ("Name", name),
        ("Email", user.email or ""),
        ("User ID", user.id),
        ("Organization", user.organization or ""),
        ("Realm", user.realm),
        ("Status", user.status),
    ]


def _describe_failure(
    error: Exception, context: AuthContext
) -> Tuple[int, str, Dict[str, Any]]:
    """Map a failed User.get_current call to (exit code, message, error details)."""
    import foundry_sdk

    source = context.source.describe()

    token_error = _oauth_token_error(error)
    if token_error is not None:
        status = token_error.response.status_code
        body = token_error.response.text.strip()[:200]
        return (
            EXIT_AUTH if status in (400, 401, 403) else EXIT_API,
            f"The OAuth token request for {source} failed with HTTP {status}"
            f"{f' ({body})' if body else ''}. Check the client ID and secret.",
            {"statusCode": status},
        )

    details = (
        _rpc_details(error)
        if isinstance(error, foundry_sdk.PalantirRPCException)
        else {}
    )
    if isinstance(error, foundry_sdk.UnauthorizedError):
        return (
            EXIT_AUTH,
            f"Authentication failed (HTTP 401): Foundry rejected the credentials "
            f"from {source}. Check the token or client credentials.",
            {"statusCode": 401, **details},
        )
    if isinstance(error, foundry_sdk.PermissionDeniedError):
        return (
            EXIT_PERMISSION_DENIED,
            f"Permission denied (HTTP 403): Foundry accepted the credentials "
            f"from {source} but refused to return the current user. OAuth "
            "clients need the api:admin-read scope for this check.",
            {"statusCode": 403, **details},
        )
    if isinstance(error, (foundry_sdk.NotFoundError, foundry_sdk.ApiNotFoundError)):
        return (
            EXIT_NOT_FOUND,
            f"The current-user endpoint was not found on {context.base_url} "
            f"(HTTP 404): {_error_text(error)}",
            {"statusCode": 404, **details},
        )
    if isinstance(error, (foundry_sdk.ConnectionError, foundry_sdk.TimeoutError)):
        return (
            EXIT_API,
            f"Could not reach {context.base_url}: {_error_text(error)}. Check "
            "the host and your network connection.",
            {},
        )
    if isinstance(
        error,
        (
            foundry_sdk.PalantirRPCException,
            foundry_sdk.RateLimitError,
            foundry_sdk.ServiceUnavailable,
        ),
    ):
        return (EXIT_API, f"Foundry returned an error: {_error_text(error)}", details)
    if isinstance(error, AuthError):
        return (EXIT_AUTH, str(error), {})
    return (EXIT_UNEXPECTED, f"Unexpected error: {_error_text(error)}", {})


def _oauth_token_error(error: BaseException) -> Optional[Any]:
    """Return the httpx error of a failed OAuth token request in the cause chain."""
    import httpx

    current: Optional[BaseException] = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, httpx.HTTPStatusError) and str(
            current.request.url.path
        ).endswith("/oauth2/token"):
            return current
        current = current.__cause__ or current.__context__
    return None


def _rpc_details(error: Any) -> Dict[str, Any]:
    """errorCode, errorName, errorInstanceId and parameters of an SDK API error."""
    details = {
        # Typed SDK errors (e.g. GetCurrentUserPermissionDenied) are dataclasses
        # with only name, parameters and error_instance_id: no error_code.
        "errorCode": getattr(error, "error_code", None),
        "errorName": error.name,
        "errorInstanceId": error.error_instance_id,
        "parameters": error.parameters,
    }
    return {key: value for key, value in details.items() if value}


def _error_text(error: Exception) -> str:
    """Readable text for an exception (typed SDK errors have an empty str())."""
    return str(error) or getattr(error, "name", None) or type(error).__name__


def _fail(
    json_mode: bool,
    exit_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> NoReturn:
    """Report a failure on stderr and exit with the given code."""
    if json_mode:
        error = {
            "type": ERROR_TYPES[exit_code],
            "message": message,
            "exitCode": exit_code,
            **(details or {}),
        }
        sys.stderr.write(json.dumps(error, separators=(",", ":")) + "\n")
    else:
        err_console.print(f"[red]✗[/red] {escape(message)}", soft_wrap=True)
    raise typer.Exit(exit_code)
