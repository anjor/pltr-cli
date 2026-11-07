"""The ``@pltr_command`` decorator, command metadata and the root group.

``@pltr_command(...)`` goes directly under ``@app.command(...)`` (Typer) or
``@click.command(...)`` (click). It

* records :class:`CommandMeta` (SDK method paths, direct-HTTP endpoints,
  beta / destructive / paged / binary) on the callback, where it survives Typer's
  callback wrapping and can be read back from the click command tree with
  :func:`get_command_meta` / :func:`iter_commands`;
* prefixes the help (the docstring) of beta commands with ``[beta]``;
* activates the command's ``--format`` for stderr messages, routes Python
  warnings through :func:`pltr.contract.warn`, and turns any exception into
  a structured error plus exit code (:mod:`pltr.contract.errors`).
"""

import functools
import inspect
import re
import sys
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
)

import click
import typer
from typer.core import TyperGroup

from .errors import classify_error, fail, render_error
from .runtime import (
    begin_invocation,
    capture_warnings,
    debug_enabled,
    ensure_utf8_output,
    format_from_context,
    is_json,
    output_format,
    set_output_format,
)

F = TypeVar("F", bound=Callable[..., Any])

#: Attribute holding the CommandMeta on a command callback.
META_ATTR = "__pltr_meta__"

#: Prefix of the help text of commands that call beta endpoints.
BETA_LABEL = "[beta]"

_SDK_PATH = re.compile(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)+")
_HTTP_ENDPOINT = re.compile(r"(GET|POST|PUT|PATCH|DELETE) /\S*")


@dataclass(frozen=True)
class CommandMeta:
    """What a command calls and how it behaves (for the manifest and tests).

    Attributes:
        sdk: SDK method paths relative to ``FoundryClient``, e.g.
            ``("filesystem.Folder.get",)``.
        http: direct-HTTP endpoints (labeled exceptions only), e.g.
            ``("POST /foundry-schema-inference/api/...",)``.
        beta: the command calls at least one beta endpoint (with
            ``preview=True``); its help starts with ``[beta]``.
        destructive: the command deletes/overwrites; it asks for
            confirmation and has ``--yes``.
        paged: the command returns a paged list and has the paging options.
        binary: the command writes raw bytes (file content, Arrow, Parquet,
            images) to a file or stdout, not table/JSON/CSV; its
            ``--format`` only changes how errors are reported.
    """

    sdk: Tuple[str, ...] = ()
    http: Tuple[str, ...] = ()
    beta: bool = False
    destructive: bool = False
    paged: bool = False
    binary: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sdk": list(self.sdk),
            "http": list(self.http),
            "beta": self.beta,
            "destructive": self.destructive,
            "paged": self.paged,
            "binary": self.binary,
        }


def _as_tuple(
    value: Union[str, Sequence[str]], pattern: "re.Pattern[str]"
) -> Tuple[str, ...]:
    items = (value,) if isinstance(value, str) else tuple(value)
    for item in items:
        if not pattern.fullmatch(item):
            raise ValueError(f"Invalid command metadata entry: {item!r}")
    return items


def beta_help(text: Optional[str]) -> str:
    """Return help text starting with the ``[beta]`` label (idempotent)."""
    cleaned = inspect.cleandoc(text) if text else ""
    if cleaned.startswith(BETA_LABEL):
        return cleaned
    return f"{BETA_LABEL} {cleaned}".rstrip()


def pltr_command(
    *,
    sdk: Union[str, Sequence[str]] = (),
    http: Union[str, Sequence[str]] = (),
    beta: bool = False,
    destructive: bool = False,
    paged: bool = False,
    binary: bool = False,
) -> Callable[[F], F]:
    """Declare a command's metadata and give it the error/output contract.

    Usage (Typer; for click put it under ``@click.command()``)::

        @app.command("get")
        @pltr_command(sdk="filesystem.Folder.get")
        def get_folder(...): ...

    Inside the command, any exception becomes a structured error on stderr
    and the matching exit code; ``typer.Exit``/``click.Abort`` pass through.
    Click usage errors raised in the body (``typer.BadParameter``) keep
    click's usual rendering in text mode and become JSON in JSON mode.
    """
    meta = CommandMeta(
        sdk=_as_tuple(sdk, _SDK_PATH),
        http=_as_tuple(http, _HTTP_ENDPOINT),
        beta=beta,
        destructive=destructive,
        paged=paged,
        binary=binary,
    )

    def decorate(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with capture_warnings():
                try:
                    return func(*args, **kwargs)
                except (click.exceptions.Exit, click.Abort):
                    raise
                except BrokenPipeError:
                    # stdout was closed early (e.g. `| head`): click's main()
                    # exits quietly on EPIPE; don't report it as an error.
                    raise
                except click.ClickException as exc:
                    if not is_json():
                        raise
                    fail(exc)
                except Exception as exc:
                    fail(exc)

        if beta:
            wrapper.__doc__ = beta_help(func.__doc__)
        setattr(wrapper, META_ATTR, meta)
        return wrapper  # type: ignore[return-value]

    return decorate


def get_command_meta(command: click.Command) -> Optional[CommandMeta]:
    """Return the metadata recorded by ``@pltr_command``, if any."""
    callback: Any = getattr(command, "callback", None)
    for _ in range(10):  # follow __wrapped__ through other decorators
        if callback is None:
            return None
        meta = getattr(callback, META_ATTR, None)
        if isinstance(meta, CommandMeta):
            return meta
        callback = getattr(callback, "__wrapped__", None)
    return None


class CommandEntry(NamedTuple):
    """One leaf command of the CLI tree."""

    path: str  # e.g. "folder get" (without the program name)
    command: click.Command
    meta: Optional[CommandMeta]


def iter_commands(root: Union[typer.Typer, click.Command]) -> Iterator[CommandEntry]:
    """Walk the CLI tree and yield every runnable command with its metadata.

    ``root`` is the Typer app (``pltr.cli.app``) or a click command/group.
    Yields every leaf command, plus groups that run their own callback when
    called without a subcommand (``invoke_without_command``, e.g.
    ``pltr verify``). Hidden commands are included (check
    ``entry.command.hidden``). Groups are walked through their public
    ``list_commands``/``get_command``, so lazily loaded groups are loaded.
    """
    command = typer.main.get_command(root) if isinstance(root, typer.Typer) else root
    yield from _walk(command, click.Context(command, info_name="pltr"), ())


def _walk(
    command: click.Command, ctx: click.Context, prefix: Tuple[str, ...]
) -> Iterator[CommandEntry]:
    if isinstance(command, click.Group):
        # A group that runs its own callback when called without a
        # subcommand (e.g. `pltr verify`) is a command too.
        if prefix and command.invoke_without_command and command.callback:
            yield CommandEntry(" ".join(prefix), command, get_command_meta(command))
        for name in command.list_commands(ctx):
            sub = command.get_command(ctx, name)
            if sub is None:
                continue
            sub_ctx = click.Context(sub, info_name=name, parent=ctx)
            yield from _walk(sub, sub_ctx, prefix + (name,))
    else:
        yield CommandEntry(" ".join(prefix), command, get_command_meta(command))


# ------------------------------------------------------------------ root group

_NO_ARGS_IS_HELP: Tuple[type, ...] = tuple(
    cls
    for cls in (getattr(click.exceptions, "NoArgsIsHelpError", None),)
    if isinstance(cls, type)
)


def _usage_error_as_json(exc: click.ClickException) -> None:
    """In JSON mode, render a parse-time click error as JSON and exit."""
    if isinstance(exc, _NO_ARGS_IS_HELP):
        return
    fmt = format_from_context(getattr(exc, "ctx", None)) or output_format()
    if fmt != "json":
        return
    render_error(classify_error(exc), as_json=True)
    raise click.exceptions.Exit(exc.exit_code)


def hide_missing_envvars(root: click.Command) -> None:
    """Turn off ``show_envvar`` on options that have no environment variable.

    click 8.2.0 and 8.2.1 append ``(env var: '<envvar>')`` to an option's
    error hint whenever ``show_envvar`` is set, and ``typer.Option`` sets it
    by default, so errors read ``Missing option '--parent-folder' / '-p'
    (env var: 'None')``. Options with an environment variable (``--format``,
    ``PLTR_FORMAT``) keep naming it.

    Only the commands already built are walked (``Group.commands``, never
    ``get_command``), so lazily loaded groups such as ``pltr api`` stay
    unloaded; their options are plain click options, which don't show
    environment variables.
    """
    stack: List[click.Command] = [root]
    seen: Set[int] = set()
    while stack:
        command = stack.pop()
        if id(command) in seen:
            continue
        seen.add(id(command))
        for param in command.params:
            if isinstance(param, click.Option) and param.envvar is None:
                param.show_envvar = False
        if isinstance(command, click.Group):
            stack.extend(command.commands.values())


class PltrRootGroup(TyperGroup):
    """Click class of the root ``pltr`` group (``typer.Typer(cls=...)``).

    Per invocation it makes redirected stdout/stderr UTF-8
    (:func:`ensure_utf8_output`), resets the output mode (from ``--format``
    in the arguments or ``$PLTR_FORMAT``), routes Python warnings to stderr
    messages, renders click's parse-time usage errors as structured JSON in
    JSON mode (exit 2), and gives commands that don't use ``@pltr_command``
    the same error rendering for unexpected exceptions.

    When built, it stops options without an environment variable from
    claiming one in error messages (:func:`hide_missing_envvars`).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        hide_missing_envvars(self)

    def main(  # type: ignore[override]
        self,
        args: Optional[Sequence[str]] = None,
        prog_name: Optional[str] = None,
        complete_var: Optional[str] = None,
        standalone_mode: bool = True,
        **extra: Any,
    ) -> Any:
        ensure_utf8_output()
        previous = begin_invocation(sys.argv[1:] if args is None else list(args))
        try:
            with capture_warnings():
                return super().main(
                    args=args,
                    prog_name=prog_name,
                    complete_var=complete_var,
                    standalone_mode=standalone_mode,
                    **extra,
                )
        finally:
            set_output_format(previous)

    def make_context(
        self,
        info_name: Optional[str],
        args: Any,
        parent: Optional[click.Context] = None,
        **extra: Any,
    ) -> click.Context:
        try:
            return super().make_context(info_name, args, parent=parent, **extra)
        except click.ClickException as exc:
            _usage_error_as_json(exc)
            raise

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except (click.exceptions.Exit, click.Abort, BrokenPipeError):
            # BrokenPipeError: stdout was closed early (e.g. `| head`); click's
            # main() exits quietly on EPIPE.
            raise
        except click.ClickException as exc:
            _usage_error_as_json(exc)
            raise
        except Exception as exc:
            if debug_enabled():
                raise
            fail(exc)
