"""Reusable CLI options, the confirmation rule and JSON-input parsing.

Typer commands declare options with the ``Annotated`` aliases::

    def get_folder(
        folder_rid: Annotated[str, typer.Argument(help="Folder RID")],
        profile: ProfileOption = None,
        format: FormatOption = "table",
        output: OutputOption = None,
    ): ...

Plain click commands (e.g. generated ones) use the ``click_*`` decorators,
which declare the same options with the same names and behaviour.
"""

import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Union

import click
import typer
from typing_extensions import Annotated

from ..utils.completion import complete_output_format, complete_profile
from .errors import Aborted, ConfirmationRequired
from .runtime import FORMAT_ENVVAR, FORMATS, is_json, remember_format, warn

F = TypeVar("F", bound=Callable[..., Any])

# Set on the command's own context when a deprecated --yes alias is used
# (not ctx.meta, which click shares with longer-lived parent contexts).
_YES_ATTR = "_pltr_contract_yes"

_FORMAT_HELP = "Output format: table, json or csv."
_OUTPUT_HELP = "Write the output to FILE instead of stdout."
_PROFILE_HELP = "Authentication profile to use (default: the active profile)."
_YES_HELP = "Don't ask for confirmation. Required when stdin is not a terminal."
_PAGE_SIZE_HELP = "Number of items per page (default: the API's page size)."
_PAGE_TOKEN_HELP = "Resume from the nextPageToken of an earlier response."
_MAX_PAGES_HELP = "Maximum number of pages to fetch."
_ALL_PAGES_HELP = "Fetch every page (overrides --max-pages)."


# ---------------------------------------------------------------- callbacks


def _format_callback(
    ctx: click.Context, param: click.Parameter, value: Optional[str]
) -> Optional[str]:
    """Record the format as soon as it's parsed (the option is eager).

    Parse errors raised later in the same invocation (a missing argument,
    say) can then already be reported as JSON.
    """
    if value is not None:
        value = value.lower()
        remember_format(ctx, value)
    return value


def _yes_alias_callback(flag: str) -> Callable[..., bool]:
    def callback(ctx: click.Context, param: click.Parameter, value: bool) -> bool:
        if value and not ctx.resilient_parsing:
            setattr(ctx, _YES_ATTR, True)
            warn(
                f"{flag} is deprecated and will be removed in a future release; use --yes."
            )
        return value

    return callback


def _preview_callback(ctx: click.Context, param: click.Parameter, value: bool) -> bool:
    if value and not ctx.resilient_parsing:
        warn(
            "--preview is deprecated and has no effect: pltr always enables beta "
            "endpoints it calls. It will be removed in a future release."
        )
    return value


def _click_complete_format(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> Any:
    return complete_output_format(incomplete)


def _click_complete_profile(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> Any:
    return complete_profile(incomplete)


# ----------------------------------------------- Typer option factories
#
# The Annotated aliases below are built from these. Use a factory with
# short=False only when the command already uses the short flag for another
# option (e.g. `folder create --parent-folder/-p`):
#
#     profile: Annotated[Optional[str], profile_option(short=False)] = None


def profile_option(*, short: bool = True) -> Any:
    """``typer.Option`` for ``--profile`` (and ``-p`` unless ``short=False``)."""
    decls = ("--profile", "-p") if short else ("--profile",)
    return typer.Option(
        *decls, help=_PROFILE_HELP, autocompletion=complete_profile, show_default=False
    )


def format_option(*, short: bool = True) -> Any:
    """``typer.Option`` for ``--format`` (and ``-f`` unless ``short=False``)."""
    decls = ("--format", "-f") if short else ("--format",)
    return typer.Option(
        *decls,
        help=_FORMAT_HELP,
        envvar=FORMAT_ENVVAR,
        click_type=click.Choice(FORMATS, case_sensitive=False),
        autocompletion=complete_output_format,
        is_eager=True,
        callback=_format_callback,
    )


def output_option(*, short: bool = True) -> Any:
    """``typer.Option`` for ``--output FILE`` (and ``-o`` unless ``short=False``)."""
    decls = ("--output", "-o") if short else ("--output",)
    return typer.Option(*decls, help=_OUTPUT_HELP, metavar="FILE", show_default=False)


# ------------------------------------------------------- Typer option types

#: ``--profile/-p``: authentication profile name.
ProfileOption = Annotated[Optional[str], profile_option()]

#: ``--format/-f``: table (default), json or csv; default from ``$PLTR_FORMAT``.
FormatOption = Annotated[str, format_option()]

#: ``--output/-o FILE``: write the data to a file instead of stdout.
OutputOption = Annotated[Optional[str], output_option()]

#: ``--yes/-y``: skip the confirmation prompt of a destructive command.
YesOption = Annotated[bool, typer.Option("--yes", "-y", help=_YES_HELP)]

#: Hidden, deprecated alias of ``--yes`` (warns when used).
ConfirmAliasOption = Annotated[
    bool,
    typer.Option(
        "--confirm",
        hidden=True,
        help="Deprecated alias for --yes.",
        callback=_yes_alias_callback("--confirm"),
    ),
]

#: Hidden, deprecated alias of ``--yes`` (warns when used). Only for commands
#: whose ``--force`` meant "skip the confirmation prompt".
ForceAliasOption = Annotated[
    bool,
    typer.Option(
        "--force",
        hidden=True,
        help="Deprecated alias for --yes.",
        callback=_yes_alias_callback("--force"),
    ),
]

#: Hidden, deprecated no-op ``--preview`` (warns when used).
PreviewNoopOption = Annotated[
    bool,
    typer.Option(
        "--preview",
        hidden=True,
        help="Deprecated; has no effect.",
        callback=_preview_callback,
    ),
]

#: Paging options; pass them to :func:`pltr.contract.collect_pages`.
PageSizeOption = Annotated[
    Optional[int],
    typer.Option("--page-size", min=1, help=_PAGE_SIZE_HELP, show_default=False),
]
PageTokenOption = Annotated[
    Optional[str],
    typer.Option("--page-token", help=_PAGE_TOKEN_HELP, show_default=False),
]
MaxPagesOption = Annotated[
    int, typer.Option("--max-pages", min=1, help=_MAX_PAGES_HELP)
]
AllPagesOption = Annotated[bool, typer.Option("--all", help=_ALL_PAGES_HELP)]


# ------------------------------------------------- click option decorators


def click_profile_option(func: F) -> F:
    """``--profile/-p`` for a plain click command (parameter ``profile``)."""
    return click.option(
        "--profile",
        "-p",
        default=None,
        help=_PROFILE_HELP,
        shell_complete=_click_complete_profile,
    )(func)


def click_format_option(func: F) -> F:
    """``--format/-f`` for a plain click command (parameter ``format``)."""
    return click.option(
        "--format",
        "-f",
        "format",
        type=click.Choice(FORMATS, case_sensitive=False),
        default="table",
        show_default=True,
        envvar=FORMAT_ENVVAR,
        show_envvar=True,
        is_eager=True,
        callback=_format_callback,
        shell_complete=_click_complete_format,
        help=_FORMAT_HELP,
    )(func)


def click_output_option(func: F) -> F:
    """``--output/-o FILE`` for a plain click command (parameter ``output``)."""
    return click.option(
        "--output", "-o", default=None, metavar="FILE", help=_OUTPUT_HELP
    )(func)


def click_yes_option(func: F) -> F:
    """``--yes/-y`` for a plain click command (parameter ``yes``)."""
    return click.option("--yes", "-y", is_flag=True, default=False, help=_YES_HELP)(
        func
    )


def click_page_options(func: F) -> F:
    """``--page-size``, ``--page-token``, ``--max-pages``, ``--all``.

    Parameters: ``page_size``, ``page_token``, ``max_pages``, ``all_pages``.
    """
    func = click.option(
        "--all", "all_pages", is_flag=True, default=False, help=_ALL_PAGES_HELP
    )(func)
    func = click.option(
        "--max-pages", type=click.IntRange(min=1), default=1, help=_MAX_PAGES_HELP
    )(func)
    func = click.option("--page-token", default=None, help=_PAGE_TOKEN_HELP)(func)
    return click.option(
        "--page-size", type=click.IntRange(min=1), default=None, help=_PAGE_SIZE_HELP
    )(func)


# --------------------------------------------------------------- confirmation


def stdin_is_interactive() -> bool:
    """True when stdin is a terminal a person can answer a prompt on."""
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def confirm_destructive(prompt: str, *, yes: bool = False) -> None:
    """Ask before a destructive operation; return only when confirmed.

    * ``yes`` (``--yes``, or a deprecated ``--confirm``/``--force`` alias)
      skips the prompt.
    * In JSON mode (``--format json`` or ``PLTR_FORMAT=json``), or when
      stdin is not a terminal, nothing is ever prompted: raises
      :class:`ConfirmationRequired` (exit code 2) telling the user to pass
      ``--yes``. (Agent harnesses often run commands under a pseudo-terminal;
      a JSON-mode command must never wait for an answer.)
    * Otherwise prompts on stderr; "no" raises :class:`Aborted` (exit 1).

    ``prompt`` is a question such as ``"Delete space ri.compass.main.space.x?"``.
    """
    from .emit import emit_mode

    if emit_mode():
        return  # --emit-code: nothing runs, so there is nothing to confirm
    ctx = click.get_current_context(silent=True)
    if yes or (ctx is not None and getattr(ctx, _YES_ATTR, False)):
        return
    if not stdin_is_interactive():
        raise ConfirmationRequired(
            f"{prompt} Confirmation is required, but stdin is not a terminal. "
            "Re-run with --yes to proceed."
        )
    if is_json():
        raise ConfirmationRequired(
            f"{prompt} Confirmation is required, and --format json never "
            "prompts. Re-run with --yes to proceed."
        )
    # Not click.confirm(): it writes part of its prompt to stdout via input().
    click.echo(f"{prompt} [y/N]: ", nl=False, err=True)
    answer = sys.stdin.readline()
    if not answer.endswith("\n"):  # EOF: end the prompt line
        click.echo("", err=True)
    if answer.strip().lower() not in ("y", "yes"):
        raise Aborted("Aborted; nothing was changed.")


# ----------------------------------------------------------------- JSON input


#: A leading byte order mark (U+FEFF), as Windows tools write.
BYTE_ORDER_MARK = "\ufeff"


def load_json_input(value: str, *, param_hint: str) -> Any:
    """Parse a JSON option value given inline, as ``@path/to/file.json``, or
    as ``@-`` (read from stdin).

    Invalid JSON (or an unreadable file) is a usage error (exit code 2).
    Files and stdin are decoded the way JSON specifies: UTF-8 with or
    without a byte order mark (Windows PowerShell 5 writes one), or UTF-16
    or UTF-32 (PowerShell 5's ``>`` writes UTF-16).
    """
    data: Union[str, bytes] = value
    source = "the value"
    if value == "@-":
        data = click.get_binary_stream("stdin").read()
        source = "stdin"
    elif value.startswith("@"):
        file = value[1:]
        source = file
        try:
            data = Path(file).read_bytes()
        except OSError as exc:
            raise typer.BadParameter(
                f"cannot read {file}: {exc.strerror or exc}", param_hint=param_hint
            ) from exc
    if isinstance(data, str) and data.startswith(BYTE_ORDER_MARK):
        data = data[1:]
    try:
        # From bytes, json.loads detects UTF-8 (BOM or not), UTF-16 and UTF-32.
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            f"invalid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno})",
            param_hint=param_hint,
        ) from exc
    except UnicodeDecodeError as exc:
        raise typer.BadParameter(
            f"invalid JSON: {source} isn't UTF-8, UTF-16 or UTF-32 text "
            f"({exc.reason} at byte {exc.start})",
            param_hint=param_hint,
        ) from exc


#: ``--wait`` on commands that start asynchronous work (#195).
WaitOption = Annotated[
    bool,
    typer.Option(
        "--wait",
        help=(
            "Wait until the work finishes and print its final state: exit 8 if "
            "it failed, 9 if --timeout passed first (it keeps running)."
        ),
    ),
]

#: How long ``--wait`` waits (seconds).
WaitTimeoutOption = Annotated[
    float,
    typer.Option(
        "--timeout",
        min=0,
        help="Seconds to wait before giving up (exit 9; the work keeps running).",
    ),
]
