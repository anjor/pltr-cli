"""Structured errors and exit codes.

Every failure is classified into an :class:`ErrorInfo` with a stable ``type``
and an exit code, then written to stderr: a readable message in text mode,
one compact JSON object (the last stderr line) in JSON mode::

    {"type": "not_found", "message": "...", "exitCode": 5, "statusCode": 404,
     "errorCode": "NOT_FOUND", "errorName": "FolderNotFound",
     "errorInstanceId": "...", "parameters": {"folderRid": "..."}}

Keys that don't apply are omitted. Services may wrap SDK exceptions, but
must keep the original as ``__cause__`` (``raise X(...) from e``): the
exception chain (``__cause__``/``__context__``) is searched from the outside
in and the first exception with a known meaning decides the classification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, List, NoReturn, Optional, Tuple

import click

from .runtime import debug_enabled, is_json, stderr_console, write_json_line


class ExitCode(IntEnum):
    """Process exit codes (documented in the README)."""

    SUCCESS = 0
    UNEXPECTED = 1  # unexpected error; also "no" at a confirmation prompt
    USAGE = 2  # bad/missing arguments, invalid JSON input, --yes required
    AUTH = 3  # no usable credentials, HTTP 401
    PERMISSION_DENIED = 4  # HTTP 403
    NOT_FOUND = 5  # HTTP 404
    VALIDATION = 6  # HTTP 400, 422
    API = 7  # other API or network errors: 409, 413, 429, 5xx, timeouts


class PltrError(Exception):
    """An error pltr raises itself; rendered like any other error.

    Use it (or a subclass) when a command must fail for a reason that is not
    an SDK/HTTP error. For invalid user input raise ``typer.BadParameter``.
    """

    error_type: str = "unexpected_error"
    exit_code: int = ExitCode.UNEXPECTED

    def __init__(
        self,
        message: str,
        *,
        error_type: Optional[str] = None,
        exit_code: Optional[int] = None,
        hint: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if error_type is not None:
            self.error_type = error_type
        if exit_code is not None:
            self.exit_code = exit_code
        self.hint = hint


class ConfirmationRequired(PltrError):
    """A destructive command ran without ``--yes`` and can't prompt."""

    error_type = "confirmation_required"
    exit_code = ExitCode.USAGE


class Aborted(PltrError):
    """The user answered "no" at a confirmation prompt."""

    error_type = "aborted"
    exit_code = ExitCode.UNEXPECTED


@dataclass
class ErrorInfo:
    """A classified error: what gets rendered and the exit code."""

    type: str
    message: str
    exit_code: int
    status_code: Optional[int] = None
    error_code: Optional[str] = None
    error_name: Optional[str] = None
    error_instance_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    hint: Optional[str] = None  # text mode only

    def to_json(self) -> Dict[str, Any]:
        """The JSON error object (camelCase keys; inapplicable keys omitted)."""
        document: Dict[str, Any] = {
            "type": self.type,
            "message": self.message,
            "exitCode": int(self.exit_code),
        }
        optional = (
            ("statusCode", self.status_code),
            ("errorCode", self.error_code),
            ("errorName", self.error_name),
            ("errorInstanceId", self.error_instance_id),
            ("parameters", self.parameters or None),
        )
        for key, value in optional:
            if value is not None:
                document[key] = value
        return document


# ------------------------------------------------------------- classification

_STATUS_TYPES: Dict[int, Tuple[str, int]] = {
    400: ("validation_error", ExitCode.VALIDATION),
    401: ("auth_error", ExitCode.AUTH),
    403: ("permission_denied", ExitCode.PERMISSION_DENIED),
    404: ("not_found", ExitCode.NOT_FOUND),
    409: ("conflict", ExitCode.API),
    413: ("request_too_large", ExitCode.API),
    422: ("validation_error", ExitCode.VALIDATION),
    429: ("rate_limited", ExitCode.API),
}

_HINTS = {
    "auth_error": (
        "Check your credentials with `pltr verify`; run `pltr configure --help` "
        "to set up a profile."
    ),
    "permission_denied": (
        "Your account lacks permission for this resource or operation."
    ),
    "not_found": (
        "Check the RID (Foundry RIDs look like ri.<service>.<instance>.<type>.<id>) "
        "and that your account can see the resource."
    ),
    "unexpected_error": "Re-run with PLTR_DEBUG=1 to see the traceback.",
}

# pydantic error types that mean pltr called the SDK with a wrong signature.
_SIGNATURE_ERRORS = {
    "unexpected_keyword_argument",
    "unexpected_positional_argument",
    "missing_argument",
    "missing_keyword_only_argument",
    "missing_positional_only_argument",
    "multiple_argument_values",
}


#: Foundry ``errorCode`` implied by an HTTP status. Typed SDK errors (e.g.
#: ``FolderNotFound``) drop the response's ``errorCode``; for these statuses
#: it is unambiguous. (5xx and 422 are not: several codes share them.)
_STATUS_ERROR_CODES: Dict[int, str] = {
    400: "INVALID_ARGUMENT",
    401: "UNAUTHORIZED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "REQUEST_ENTITY_TOO_LARGE",
}


def _status_info(status: int) -> Tuple[str, int]:
    if status in _STATUS_TYPES:
        return _STATUS_TYPES[status]
    if status >= 500:
        return "server_error", ExitCode.API
    return "api_error", ExitCode.API


def _clean_parameters(parameters: Any) -> Optional[Dict[str, Any]]:
    from .serialize import to_jsonable

    if not parameters:
        return None
    value = to_jsonable(parameters)
    return value if isinstance(value, dict) else {"value": value}


def _typed_error_description(exc: BaseException) -> Optional[str]:
    """Description of a typed SDK error (the docstring of its parameters)."""
    fields = getattr(type(exc), "__dataclass_fields__", None) or {}
    field = fields.get("parameters")
    parameters_type = getattr(field, "type", None)
    if isinstance(parameters_type, type):
        doc = parameters_type.__doc__
        if doc and not doc.startswith(("dict(", "Dict")):
            return " ".join(doc.split())
    return None


def _api_message(
    name: Optional[str],
    description: Optional[str],
    parameters: Optional[Dict[str, Any]],
    status: Optional[int],
) -> str:
    """A one-line message from the Foundry error fields.

    Typed SDK errors have an empty ``str()``, so the message is always built
    from ``errorName``, the description and the parameters, e.g.
    ``FolderNotFound: The given Folder could not be found.
    (folderRid=ri.compass.main.folder.x)``.
    """
    message = name or (f"HTTP {status} error" if status else "API error")
    if description:
        message = f"{message}: {description}" if name else description
    if parameters:
        rendered = ", ".join(
            f"{key}={value if isinstance(value, str) else _json_compact(value)}"
            for key, value in parameters.items()
        )
        if len(rendered) > 300:
            rendered = rendered[:297] + "..."
        message = f"{message} ({rendered})"
    return message


def _oauth_token_failure(exc: BaseException) -> Optional[Any]:
    """The failed OAuth2 token response in ``exc``'s chain, if there is one.

    When fetching an OAuth token fails, the SDK raises ``SDKInternalError``
    with the ``httpx.HTTPStatusError`` of the ``.../oauth2/token`` request
    in its cause chain.
    """
    import httpx

    for candidate in _chain(exc):
        if isinstance(candidate, httpx.HTTPStatusError):
            try:
                path = candidate.request.url.path
            except RuntimeError:  # request not set
                continue
            if path.rstrip("/").endswith("/oauth2/token"):
                return candidate.response
    return None


def _oauth_error(response: Any) -> ErrorInfo:
    status = int(response.status_code)
    return ErrorInfo(
        "auth_error",
        f"OAuth2 token request failed (HTTP {status}): check the client ID, "
        "client secret and scopes of your profile.",
        ExitCode.AUTH,
        status_code=status,
    )


def _from_rpc(exc: Any) -> ErrorInfo:
    from foundry_sdk import _errors as sdk

    statuses = (
        (sdk.UnauthorizedError, 401),
        (sdk.PermissionDeniedError, 403),
        (sdk.NotFoundError, 404),
        (sdk.BadRequestError, 400),
        (sdk.UnprocessableEntityError, 422),
        (sdk.ConflictError, 409),
        (sdk.RequestEntityTooLargeError, 413),
    )
    status: Optional[int] = None
    for cls, code in statuses:
        if isinstance(exc, cls):
            status = code
            break
    if status is not None:
        error_type, exit_code = _status_info(status)
    elif isinstance(exc, sdk.InternalServerError):
        error_type, exit_code = "server_error", ExitCode.API
    else:
        error_type, exit_code = "api_error", ExitCode.API

    # Typed SDK errors are dataclasses with only name/parameters/
    # error_instance_id (no error_code, empty str()): read defensively.
    name = getattr(exc, "name", None)
    description = getattr(exc, "error_description", None) or _typed_error_description(
        exc
    )
    parameters = _clean_parameters(getattr(exc, "parameters", None))
    error_code = getattr(exc, "error_code", None)
    if error_code is None and status is not None:
        error_code = _STATUS_ERROR_CODES.get(status)
    return ErrorInfo(
        type=error_type,
        message=_api_message(name, description, parameters, status),
        exit_code=exit_code,
        status_code=status,
        error_code=error_code,
        error_name=name,
        error_instance_id=getattr(exc, "error_instance_id", None),
        parameters=parameters,
    )


def _from_http_response(response: Any, fallback: str) -> ErrorInfo:
    """Classify a ``requests`` response carrying an HTTP error status."""
    status = int(response.status_code)
    error_type, exit_code = _status_info(status)
    body: Any = None
    try:
        body = response.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        body = {}
    name = body.get("errorName")
    description = body.get("errorDescription")
    parameters = _clean_parameters(body.get("parameters"))
    message = _api_message(name, description, parameters, None)
    if not (name or description):
        reason = getattr(response, "reason", None) or ""
        message = f"HTTP {status} {reason}".strip() if status else fallback
    return ErrorInfo(
        type=error_type,
        message=message,
        exit_code=exit_code,
        status_code=status,
        error_code=body.get("errorCode"),
        error_name=name,
        error_instance_id=body.get("errorInstanceId"),
        parameters=parameters,
    )


def _describe_validation_error(exc: Any) -> Tuple[str, bool]:
    """Return (message, is_signature_error) for a pydantic ValidationError."""
    parts: List[str] = []
    signature_error = False
    for error in exc.errors():
        if error.get("type") in _SIGNATURE_ERRORS:
            signature_error = True
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = str(error.get("msg", ""))
        pattern = (error.get("ctx") or {}).get("pattern")
        if isinstance(pattern, str) and pattern.startswith("^ri\\."):
            message = (
                f"{error.get('input')!r} is not a valid RID "
                "(expected ri.<service>.<instance>.<type>.<locator>)"
            )
        parts.append(f"{location}: {message}" if location else message)
    return "; ".join(parts) or str(exc), signature_error


def _classify_one(exc: BaseException) -> Optional[ErrorInfo]:
    """Classify a single exception, or None if its type means nothing to us."""
    import json

    import pydantic
    import requests
    from foundry_sdk import _errors as sdk

    from ..auth.base import AuthError

    if isinstance(exc, PltrError):
        return ErrorInfo(exc.error_type, exc.message, exc.exit_code, hint=exc.hint)
    if isinstance(exc, click.UsageError):
        return ErrorInfo("usage_error", exc.format_message(), ExitCode.USAGE)
    if isinstance(exc, click.ClickException):
        code = exc.exit_code
        kind = "usage_error" if code == ExitCode.USAGE else "unexpected_error"
        return ErrorInfo(kind, exc.format_message(), code)
    if isinstance(exc, AuthError):
        return ErrorInfo("auth_error", str(exc) or type(exc).__name__, ExitCode.AUTH)

    # foundry_sdk
    if isinstance(exc, sdk.ApiNotFoundError):
        return ErrorInfo("api_not_found", str(exc), ExitCode.NOT_FOUND, status_code=404)
    if isinstance(exc, sdk.PalantirRPCException):
        return _from_rpc(exc)
    if isinstance(exc, sdk.RateLimitError):
        return ErrorInfo(
            "rate_limited",
            "Too many requests (HTTP 429); retry after a short wait.",
            ExitCode.API,
            status_code=429,
        )
    if isinstance(exc, sdk.ServiceUnavailable):
        return ErrorInfo(
            "server_error",
            "Service unavailable (HTTP 503); retry after a short wait.",
            ExitCode.API,
            status_code=503,
        )
    if isinstance(exc, sdk.TimeoutError):
        return ErrorInfo("timeout", f"Request timed out: {exc}", ExitCode.API)
    if isinstance(exc, sdk.ConnectionError):
        return ErrorInfo(
            "network_error", f"Could not connect to Foundry: {exc}", ExitCode.API
        )
    if isinstance(exc, (sdk.NotAuthenticated, sdk.EnvironmentNotConfigured)):
        return ErrorInfo("auth_error", str(exc) or type(exc).__name__, ExitCode.AUTH)
    if isinstance(exc, sdk.SDKInternalError):
        token_response = _oauth_token_failure(exc)
        if token_response is not None:
            return _oauth_error(token_response)
        detail = exc.msg
        match = re.search(r"error response with status code (\d{3})", detail)
        if match:
            status = int(match.group(1))
            error_type, exit_code = _status_info(status)
            return ErrorInfo(error_type, detail[:500], exit_code, status_code=status)
        return ErrorInfo("unexpected_error", detail[:500], ExitCode.UNEXPECTED)

    # requests (the labeled direct-HTTP commands)
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return _from_http_response(exc.response, str(exc))
    if isinstance(exc, requests.Timeout):
        return ErrorInfo("timeout", f"Request timed out: {exc}", ExitCode.API)
    if isinstance(exc, requests.ConnectionError):
        return ErrorInfo(
            "network_error", f"Could not connect to Foundry: {exc}", ExitCode.API
        )
    if isinstance(exc, requests.RequestException):
        return None  # e.g. a JSON decode error of a response: unexpected

    # httpx errors that escaped the SDK's own wrapping (httpx is an SDK dependency)
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        token_response = _oauth_token_failure(exc)
        if token_response is not None:
            return _oauth_error(token_response)
        status = int(exc.response.status_code)
        error_type, exit_code = _status_info(status)
        return ErrorInfo(
            error_type, str(exc).splitlines()[0], exit_code, status_code=status
        )
    if isinstance(exc, httpx.TimeoutException):
        return ErrorInfo("timeout", f"Request timed out: {exc}", ExitCode.API)
    if isinstance(exc, httpx.TransportError):
        return ErrorInfo(
            "network_error", f"Could not connect to Foundry: {exc}", ExitCode.API
        )

    if isinstance(exc, pydantic.ValidationError):
        message, signature_error = _describe_validation_error(exc)
        if signature_error:
            return ErrorInfo(
                "unexpected_error",
                f"pltr called the SDK with invalid arguments (a pltr bug): {message}",
                ExitCode.UNEXPECTED,
            )
        return ErrorInfo("usage_error", f"Invalid argument: {message}", ExitCode.USAGE)
    if isinstance(exc, json.JSONDecodeError):
        return ErrorInfo("usage_error", f"Invalid JSON input: {exc}", ExitCode.USAGE)
    return None


def _chain(exc: BaseException) -> List[BaseException]:
    chain: List[BaseException] = []
    seen = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def _with_context(outer: BaseException, info: ErrorInfo) -> str:
    """Prefix the message with the first line of a wrapping exception."""
    text = str(outer).strip()
    first = text.splitlines()[0].strip().rstrip(":{[ ").strip() if text else ""
    detail = info.message
    if not first or first == detail:
        return detail
    if detail in first:
        return first
    if info.error_name and first.endswith(info.error_name):
        first = first[: -len(info.error_name)].rstrip(" :")
    return f"{first}: {detail}" if first else detail


def classify_error(exc: BaseException) -> ErrorInfo:
    """Classify an exception (searching its cause chain) into an ErrorInfo."""
    for candidate in _chain(exc):
        info = _classify_one(candidate)
        if info is not None:
            if candidate is not exc:
                info.message = _with_context(exc, info)
            break
    else:
        text = str(exc).strip()
        message = text.splitlines()[0] if text else type(exc).__name__
        if text and type(exc) not in (RuntimeError, Exception):
            message = f"{type(exc).__name__}: {message}"
        info = ErrorInfo("unexpected_error", message, ExitCode.UNEXPECTED)
    if info.hint is None:
        info.hint = _HINTS.get(info.type)
    return info


# ------------------------------------------------------------------ rendering


def render_error(info: ErrorInfo, *, as_json: Optional[bool] = None) -> None:
    """Write a classified error to stderr (a JSON line in JSON mode).

    ``as_json`` overrides the active output format.
    """
    if is_json() if as_json is None else as_json:
        write_json_line(info.to_json())
        return
    console = stderr_console()
    console.print(f"[bold red]Error:[/bold red] {_escape(info.message)}")
    details: List[str] = []
    if info.status_code is not None:
        details.append(f"status: {info.status_code}")
    if info.error_code:
        details.append(f"errorCode: {info.error_code}")
    if info.error_name and info.error_name not in info.message:
        details.append(f"errorName: {info.error_name}")
    if info.error_instance_id:
        details.append(f"errorInstanceId: {info.error_instance_id}")
    for line in details:
        console.print(f"  {line}", markup=False)
    if info.hint:
        console.print(f"Hint: {info.hint}", markup=False, style="dim")


def _escape(text: str) -> str:
    from rich.markup import escape

    return escape(text)


def _json_compact(value: Any) -> str:
    import json

    return json.dumps(value, separators=(",", ":"), default=str)


def fail(exc: BaseException) -> NoReturn:
    """Render ``exc`` as a structured error and exit with its code.

    With ``$PLTR_DEBUG`` set, the original exception is re-raised after
    rendering so the traceback is shown.
    """
    info = classify_error(exc)
    render_error(info)
    if debug_enabled():
        raise exc
    raise click.exceptions.Exit(int(info.exit_code))
