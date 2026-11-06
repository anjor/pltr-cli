"""Per-invocation output mode and everything pltr writes to stderr.

stdout carries data only (see :mod:`pltr.contract.output`). Everything else
(status, progress, success/info/warning messages, prompts, errors) goes to
stderr through this module, which knows the active output format:

* ``table``/``csv``: human-readable messages on stderr.
* ``json``: informational messages are suppressed and stderr carries only
  JSON Lines (``{"type": "warning", "message": ...}``; errors are written by
  :mod:`pltr.contract.errors`).
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional, Sequence

import click

#: Output formats every command accepts through ``--format``.
FORMATS = ("table", "json", "csv")

#: Environment variable that sets the default ``--format``.
FORMAT_ENVVAR = "PLTR_FORMAT"

#: Set to any non-empty value to re-raise errors with a traceback.
DEBUG_ENVVAR = "PLTR_DEBUG"


#: ``ctx.meta`` key where the eager ``--format`` callback records the format.
FORMAT_META_KEY = "pltr.contract.format"


class _State:
    """Fallback format for code running outside a click context.

    Set by the root group for the duration of an invocation (from the raw
    arguments and ``$PLTR_FORMAT``) and restored afterwards, so nothing
    leaks from one invocation to the next.
    """

    def __init__(self) -> None:
        self.format = "table"


_STATE = _State()


def format_from_env() -> Optional[str]:
    """Return the format named by ``$PLTR_FORMAT`` (lower-cased), if valid."""
    value = os.environ.get(FORMAT_ENVVAR, "").strip().lower()
    return value if value in FORMATS else None


def format_from_args(args: Sequence[str]) -> Optional[str]:
    """Best-effort scan of raw CLI arguments for ``--format X`` / ``-f X``.

    Used only before the command's own ``--format`` option has been parsed
    (for example for a usage error raised while parsing).
    """
    found: Optional[str] = None
    items = list(args)
    for index, arg in enumerate(items):
        if arg == "--":
            break
        value: Optional[str] = None
        if arg in ("--format", "-f") and index + 1 < len(items):
            value = items[index + 1]
        elif arg.startswith("--format="):
            value = arg.split("=", 1)[1]
        elif arg.startswith("-f") and not arg.startswith("--") and len(arg) > 2:
            value = arg[2:]
        if value is not None and value.lower() in FORMATS:
            found = value.lower()
    return found


def _normalize(value: Any) -> Optional[str]:
    value = getattr(value, "value", value)  # tolerate Enum-typed legacy options
    if isinstance(value, str) and value.lower() in FORMATS:
        return value.lower()
    return None


def format_from_context(ctx: Optional[click.Context]) -> Optional[str]:
    """The format of the command running in ``ctx``, if known.

    Reads the parsed value of the command's ``--format`` option, or else the
    value the eager ``--format`` callback recorded in ``ctx.meta`` (which is
    shared by every context of an invocation) while arguments were parsed.
    """
    if ctx is None:
        return None
    for param in ctx.command.params:
        if isinstance(param, click.Option) and "--format" in param.opts:
            if param.name in ctx.params:
                return _normalize(ctx.params[param.name])
            break
    return _normalize(ctx.meta.get(FORMAT_META_KEY))


def set_output_format(value: Optional[str]) -> None:
    """Set the fallback output format (unknown values mean ``table``)."""
    _STATE.format = _normalize(value) or "table"


def output_format() -> str:
    """Return the active output format: ``table``, ``json`` or ``csv``.

    The running command's ``--format`` wins; outside a command (or for a
    command without ``--format``) it's the invocation's fallback format.
    """
    current = format_from_context(click.get_current_context(silent=True))
    return current or _STATE.format


def is_json() -> bool:
    """True when the active output format is ``json``."""
    return output_format() == "json"


def begin_invocation(args: Sequence[str]) -> str:
    """Set the fallback format for a new invocation; return the previous one."""
    previous = _STATE.format
    set_output_format(format_from_args(args) or format_from_env() or "table")
    return previous


def debug_enabled() -> bool:
    """True when ``$PLTR_DEBUG`` asks for tracebacks."""
    return bool(os.environ.get(DEBUG_ENVVAR, "").strip())


# --------------------------------------------------------------------- stderr


def stderr_console() -> Any:
    """Return a Rich console bound to the *current* ``sys.stderr``.

    Created per call so it always follows ``sys.stderr`` (Click's test runner
    swaps it) and so terminal detection is never stale.
    """
    from rich.console import Console

    return Console(stderr=True, highlight=False, soft_wrap=True)


def write_json_line(payload: Dict[str, Any]) -> None:
    """Write one compact JSON object as a line on stderr."""
    click.echo(json.dumps(payload, separators=(",", ":"), default=str), err=True)


def info(message: str) -> None:
    """Informational message on stderr. Suppressed in JSON mode."""
    if is_json():
        return
    stderr_console().print(message, markup=False, style="cyan")


def success(message: str) -> None:
    """Success message on stderr. Suppressed in JSON mode."""
    if is_json():
        return
    stderr_console().print(message, markup=False, style="green")


def warn(message: str) -> None:
    """Warning on stderr; a ``{"type": "warning"}`` JSON line in JSON mode."""
    if is_json():
        write_json_line({"type": "warning", "message": message})
        return
    stderr_console().print(f"Warning: {message}", markup=False, style="yellow")


def _stderr_is_terminal() -> bool:
    try:
        return sys.stderr.isatty()
    except (AttributeError, ValueError):
        return False


@contextmanager
def spinner(message: str) -> Iterator[None]:
    """Show a transient spinner on stderr while the block runs.

    Does nothing in JSON mode or when stderr is not a terminal, so it can
    never leak into captured output.
    """
    if is_json() or not _stderr_is_terminal():
        yield
        return

    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        console=stderr_console(),
        transient=True,
    ) as progress:
        progress.add_task(message, total=None)
        yield


# ------------------------------------------------------------ python warnings


def _show_warning(
    message: Any,
    category: Any,
    filename: str,
    lineno: int,
    file: Any = None,
    line: Optional[str] = None,
) -> None:
    name = getattr(category, "__name__", "Warning")
    warn(f"{name}: {message}")


@contextmanager
def capture_warnings() -> Iterator[None]:
    """Route Python ``warnings`` (e.g. SDK ``UserWarning``) through :func:`warn`.

    Inside the block a warning is printed as ``Warning: ...`` in text mode
    and as a ``{"type": "warning"}`` JSON line in JSON mode, so it can never
    corrupt JSON-mode stderr. Warning filters are untouched: a filter that
    turns warnings into errors (``-W error``, pytest ``filterwarnings``) still
    raises.
    """
    with warnings.catch_warnings():
        warnings.showwarning = _show_warning
        yield
