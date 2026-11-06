"""Output, error and confirmation adapter for the generated `pltr api` commands.

REPLACED IN PHASE 2: this module is a small, self-contained stand-in for the shared
output/error/confirmation layer of #187 (`pltr.utils`). The runtime calls only the
functions listed in `__all__`; phase 2 swaps their bodies for the shared layer and
keeps their signatures.

It follows the roadmap's global decisions where that is cheap:
- JSON is `model_dump(mode="json", by_alias=True, exclude_none=True)`; paged results
  keep the API's shape `{"data": [...], "nextPageToken": ...}`.
- stdout carries data only; messages, prompts and errors go to stderr. In JSON mode
  informational messages are suppressed and a failure ends with one compact JSON
  error object on stderr.
- Exit codes: 0 ok, 1 unexpected (or "no" at a prompt), 2 usage, 3 auth, 4 permission
  denied, 5 not found, 6 API validation, 7 other API or network errors.
- Destructive commands confirm on stderr; `--yes` skips it; without a terminal on
  stdin they fail with exit code 2 instead of prompting.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from typing import Any, Dict, Iterable, List, NoReturn, Optional, Tuple

import click

__all__ = [
    "FORMATS",
    "ApiCommandError",
    "confirm",
    "confirmation_unavailable",
    "describe_error",
    "emit_binary",
    "emit_result",
    "fail",
    "fail_usage",
    "info",
    "is_json",
    "stdin_is_terminal",
    "stdout_is_terminal",
    "to_jsonable",
    "unavailable",
    "usage_error",
]

FORMATS = ("table", "json", "csv")

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_PERMISSION = 4
EXIT_NOT_FOUND = 5
EXIT_VALIDATION = 6
EXIT_API = 7


class ApiCommandError(Exception):
    """An error detected by pltr itself, carrying its exit code and error type."""

    def __init__(self, message: str, *, exit_code: int, error_type: str) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.error_type = error_type


def usage_error(message: str) -> ApiCommandError:
    """Bad or missing input (exit code 2)."""
    return ApiCommandError(message, exit_code=EXIT_USAGE, error_type="usage_error")


def unavailable(message: str) -> ApiCommandError:
    """The installed SDK lacks a method or parameter the command needs (exit code 1)."""
    return ApiCommandError(
        message, exit_code=EXIT_UNEXPECTED, error_type="sdk_unavailable"
    )


def is_json(fmt: Optional[str]) -> bool:
    return (fmt or "").lower() == "json"


def _isatty(stream: Any) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def stdin_is_terminal() -> bool:
    return _isatty(sys.stdin)


def stdout_is_terminal() -> bool:
    return _isatty(sys.stdout)


def info(message: str, *, fmt: Optional[str]) -> None:
    """An informational message on stderr (suppressed in JSON mode)."""
    if not is_json(fmt):
        click.echo(message, err=True)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def to_jsonable(value: Any, annotation: Any = None) -> Any:
    """The SDK's own JSON serialization of a result.

    Models use `model_dump(mode="json", by_alias=True, exclude_none=True)`. Other
    values are dumped through a pydantic TypeAdapter of the method's return
    annotation when it is known (so SDK types such as Long serialize as the SDK
    does), and otherwise converted generically.
    """
    import pydantic

    if isinstance(value, pydantic.BaseModel):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if annotation is not None:
        try:
            return pydantic.TypeAdapter(annotation).dump_python(
                value, mode="json", by_alias=True, exclude_none=True
            )
        except Exception:
            pass
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    import pydantic_core

    return pydantic_core.to_jsonable_python(value)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _rows(document: Any) -> Optional[List[Any]]:
    """The list a table/CSV should show: a paged result's data, or a list."""
    if isinstance(document, dict) and isinstance(document.get("data"), list):
        return document["data"]
    if isinstance(document, list):
        return document
    return None


def _columns(rows: List[Any]) -> List[str]:
    columns: List[str] = []
    for row in rows:
        if isinstance(row, dict):
            for key in row:
                if key not in columns:
                    columns.append(key)
    return columns


def _table_text(document: Any, width: Optional[int]) -> str:
    from rich.console import Console
    from rich.table import Table

    rows = _rows(document)
    if rows is not None and all(isinstance(row, dict) for row in rows):
        columns = _columns(rows)
        table = Table(show_lines=False)
        for column in columns:
            table.add_column(column, overflow="fold")
        for row in rows:
            table.add_row(*(_cell(row.get(column)) for column in columns))
    elif rows is not None:
        table = Table(show_lines=False)
        table.add_column("value", overflow="fold")
        for row in rows:
            table.add_row(_cell(row))
    elif isinstance(document, dict):
        table = Table(show_header=True)
        table.add_column("field", no_wrap=True)
        table.add_column("value", overflow="fold")
        for key, value in document.items():
            table.add_row(str(key), _cell(value))
    else:
        return _cell(document) + "\n"
    buffer = io.StringIO()
    console = Console(
        file=buffer, width=width or 120, no_color=True, highlight=False, soft_wrap=False
    )
    console.print(table)
    return buffer.getvalue()


def _csv_text(document: Any) -> str:
    rows = _rows(document)
    if rows is None:
        rows = [document] if isinstance(document, dict) else [{"value": document}]
    if rows and not all(isinstance(row, dict) for row in rows):
        rows = [{"value": row} for row in rows]
    columns = _columns(rows)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    if columns:
        writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(row.get(column)) for column in columns])
    return buffer.getvalue()


def _render(document: Any, fmt: str) -> str:
    if is_json(fmt):
        return json.dumps(document, indent=2, ensure_ascii=True) + "\n"
    if fmt == "csv":
        return _csv_text(document)
    width = None
    if stdout_is_terminal():
        import shutil

        width = shutil.get_terminal_size().columns
    return _table_text(document, width)


def emit_result(
    document: Any,
    *,
    fmt: str,
    output: Optional[str],
    empty_message: Optional[str] = None,
) -> None:
    """Write one already JSON-safe result to stdout (or `output`).

    `None` means the API returned no content: JSON mode prints `null`, the other
    formats print nothing and say so on stderr.
    """
    if document is None and not is_json(fmt):
        info(empty_message or "Done (the API returned no content).", fmt=fmt)
        return
    text = _render(document, fmt)
    if output:
        with open(output, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        info(f"Wrote {fmt} output to {output}", fmt=fmt)
        return
    click.echo(text, nl=False)
    if isinstance(document, dict) and document.get("nextPageToken"):
        info(
            "More results are available: rerun with --page-token "
            f"{document['nextPageToken']} or use --all.",
            fmt=fmt,
        )


def emit_binary(chunks: Iterable[bytes], *, output_file: Optional[str]) -> int:
    """Stream binary response chunks to `output_file` (or stdout); return bytes written.

    A partially written file is removed if the stream fails.
    """
    written = 0
    if output_file and output_file != "-":
        import os

        try:
            with open(output_file, "wb") as handle:
                for chunk in chunks:
                    handle.write(chunk)
                    written += len(chunk)
        except BaseException:
            try:
                os.remove(output_file)
            except OSError:
                pass
            raise
        return written
    stream = click.get_binary_stream("stdout")
    for chunk in chunks:
        stream.write(chunk)
        written += len(chunk)
    stream.flush()
    return written


# ---------------------------------------------------------------------------
# Confirmation
# ---------------------------------------------------------------------------


def confirmation_unavailable() -> ApiCommandError:
    """A destructive command without --yes and no terminal to ask on (exit 2)."""
    return usage_error(
        "This command is destructive and stdin is not a terminal, so pltr can't "
        "ask for confirmation. Pass --yes to run it."
    )


def confirm(message: str, *, yes: bool, fmt: str) -> None:
    """Ask before a destructive call. `--yes` skips it; no terminal means exit 2."""
    if yes:
        return
    if not stdin_is_terminal():
        raise confirmation_unavailable()
    try:
        accepted = click.confirm(message, default=False, err=True)
    except click.Abort:
        accepted = False
    if not accepted:
        raise ApiCommandError(
            "Cancelled at the confirmation prompt.",
            exit_code=EXIT_UNEXPECTED,
            error_type="cancelled",
        )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def _causes(exc: BaseException) -> List[BaseException]:
    chain: List[BaseException] = []
    current: Optional[BaseException] = exc
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__
    return chain


def _rpc_error(exc: Any, error_type: str, exit_code: int, status: Optional[int]):
    name = getattr(exc, "name", None)
    description = getattr(exc, "error_description", None)
    if not description:
        try:
            import typing

            hints = typing.get_type_hints(type(exc))
            parameters_type = hints.get("parameters")
            description = getattr(parameters_type, "__doc__", None)
        except Exception:
            description = None
    message = ": ".join(part for part in (name, description) if part) or str(exc)
    details: Dict[str, Any] = {
        "type": error_type,
        "message": message,
        "exitCode": exit_code,
    }
    if status is not None:
        details["statusCode"] = status
    for key, attr in (
        ("errorCode", "error_code"),
        ("errorName", "name"),
        ("errorInstanceId", "error_instance_id"),
        ("parameters", "parameters"),
    ):
        value = getattr(exc, attr, None)
        if value:
            details[key] = to_jsonable(value)
    return details


def describe_error(exc: BaseException) -> Dict[str, Any]:
    """Structured error: type, message, exitCode and, for API errors, details."""
    import pydantic
    from foundry_sdk import _errors as sdk_errors

    from pltr.auth.base import AuthError

    for error in _causes(exc):
        if isinstance(error, ApiCommandError):
            return {
                "type": error.error_type,
                "message": error.message,
                "exitCode": error.exit_code,
            }
        if isinstance(error, pydantic.ValidationError):
            problems = "; ".join(
                f"{'.'.join(str(part) for part in item['loc']) or 'value'}: "
                f"{item['msg']}"
                for item in error.errors()[:5]
            )
            return {
                "type": "usage_error",
                "message": f"Invalid argument value ({problems})",
                "exitCode": EXIT_USAGE,
            }
        if isinstance(error, AuthError):
            return {
                "type": "authentication_error",
                "message": str(error),
                "exitCode": EXIT_AUTH,
            }
        # (exception class, error type, exit code, HTTP status) in match order;
        # subclasses of PalantirRPCException carry errorName/parameters.
        sdk_classes: List[Tuple[type, str, int, Optional[int]]] = [
            (sdk_errors.UnauthorizedError, "authentication_error", EXIT_AUTH, 401),
            (
                sdk_errors.PermissionDeniedError,
                "permission_denied",
                EXIT_PERMISSION,
                403,
            ),
            (sdk_errors.NotFoundError, "not_found", EXIT_NOT_FOUND, 404),
            (sdk_errors.BadRequestError, "validation_error", EXIT_VALIDATION, 400),
            (
                sdk_errors.UnprocessableEntityError,
                "validation_error",
                EXIT_VALIDATION,
                422,
            ),
            (sdk_errors.ConflictError, "api_error", EXIT_API, 409),
            (sdk_errors.RequestEntityTooLargeError, "api_error", EXIT_API, 413),
            (sdk_errors.InternalServerError, "api_error", EXIT_API, None),
            (sdk_errors.PalantirRPCException, "api_error", EXIT_API, None),
            (sdk_errors.NotAuthenticated, "authentication_error", EXIT_AUTH, None),
            (sdk_errors.ApiNotFoundError, "not_found", EXIT_NOT_FOUND, 404),
            (sdk_errors.RateLimitError, "api_error", EXIT_API, 429),
            (sdk_errors.ServiceUnavailable, "api_error", EXIT_API, 503),
            (sdk_errors.TimeoutError, "api_error", EXIT_API, None),
            (sdk_errors.ConnectionError, "api_error", EXIT_API, None),
        ]
        for cls, error_type, exit_code, status in sdk_classes:
            if not isinstance(error, cls):
                continue
            if isinstance(error, sdk_errors.PalantirRPCException):
                return _rpc_error(error, error_type, exit_code, status)
            details: Dict[str, Any] = {
                "type": error_type,
                "message": str(error) or cls.__name__,
                "exitCode": exit_code,
            }
            if status is not None:
                details["statusCode"] = status
            return details
    return {
        "type": "unexpected_error",
        "message": f"{type(exc).__name__}: {exc}",
        "exitCode": EXIT_UNEXPECTED,
    }


def fail(exc: BaseException, *, fmt: Optional[str]) -> NoReturn:
    """Report `exc` on stderr and exit with its code."""
    details = describe_error(exc)
    if is_json(fmt):
        click.echo(json.dumps(details, separators=(",", ":")), err=True)
    else:
        message = f"Error: {details['message']}"
        if details.get("parameters"):
            message += " " + json.dumps(details["parameters"], separators=(",", ":"))
        click.echo(message, err=True)
    raise click.exceptions.Exit(details["exitCode"])


def fail_usage(exc: click.UsageError) -> NoReturn:
    """Report a click usage error as a JSON error object (JSON mode only)."""
    ctx = exc.ctx
    if type(exc).__name__ == "NoArgsIsHelpError" and ctx is not None:
        # A group run without a subcommand: name the subcommands, not the help.
        message = f"Missing command for '{ctx.command_path}'."
        if isinstance(ctx.command, click.Group):
            names = ctx.command.list_commands(ctx)
            message += f" Commands: {', '.join(names)}."
    else:
        message = exc.format_message()
        if ctx is not None:
            message = f"{message} ({ctx.get_usage().strip()})"
    details = {"type": "usage_error", "message": message, "exitCode": EXIT_USAGE}
    click.echo(json.dumps(details, separators=(",", ":")), err=True)
    raise click.exceptions.Exit(EXIT_USAGE)
