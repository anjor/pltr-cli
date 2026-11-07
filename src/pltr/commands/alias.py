"""
Command alias commands: shortcuts for pltr command lines.

Aliases live in ``aliases.json`` in the configuration directory; these
commands make no Foundry API call. An alias replaces the first word of a
command line: after ``pltr alias add ds "dataset get"``, ``pltr ds <RID>``
runs ``pltr dataset get <RID>``.

The commands follow the shared contract: data on stdout (``--format json``
for list/show/resolve), messages on stderr, structured errors with the
documented exit codes (an unknown alias is ``not_found``, exit 5), and
removing aliases asks first unless ``--yes``.
"""

from typing import Any, Dict, List, Optional, Set

import click
import typer
from typing_extensions import Annotated

from ..config.aliases import AliasManager
from ..contract import (
    Columns,
    ExitCode,
    FormatOption,
    OutputOption,
    PltrError,
    YesOption,
    confirm_destructive,
    emit,
    format_option,
    info,
    load_json_input,
    pltr_command,
    success,
    warn,
)
from ..utils.completion import complete_alias_names

app = typer.Typer(name="alias", help="Manage command aliases", no_args_is_help=True)

#: Table/CSV columns for alias records (``{"name": ..., "command": ...}``).
ALIAS_COLUMNS: Columns = {"Alias": "name", "Command": "command"}

AliasName = Annotated[
    str,
    typer.Argument(
        help="Alias name (see 'pltr alias list').", autocompletion=complete_alias_names
    ),
]


def _confirm_toggle_callback(
    ctx: click.Context, param: click.Parameter, value: Optional[bool]
) -> Optional[bool]:
    if value is not None and not ctx.resilient_parsing:
        if value:
            warn(
                "--confirm is deprecated and will be removed in a future release; "
                "asking for confirmation is the default."
            )
        else:
            warn(
                "--no-confirm is deprecated and will be removed in a future release; "
                "use --yes."
            )
    return value


#: Hidden, deprecated ``--confirm/--no-confirm`` of ``remove`` and ``clear``:
#: ``--no-confirm`` skips the prompt (like ``--yes``), ``--confirm`` (asking)
#: is the default. Not the contract's ConfirmAliasOption, whose ``--confirm``
#: means the opposite.
ConfirmToggleOption = Annotated[
    Optional[bool],
    typer.Option(
        "--confirm/--no-confirm",
        hidden=True,
        help="Deprecated: use --yes instead of --no-confirm.",
        callback=_confirm_toggle_callback,
    ),
]


def _record(name: str, command: str) -> Dict[str, str]:
    return {"name": name, "command": command}


def _alias_not_found(name: str) -> PltrError:
    return PltrError(
        f"Alias '{name}' not found.",
        error_type="not_found",
        exit_code=ExitCode.NOT_FOUND,
        hint="List aliases with 'pltr alias list'.",
    )


def reserved_names() -> Set[str]:
    """Names an alias can't take: pltr's top-level commands, ``help`` and options."""
    # Imported here: pltr.cli imports this module.
    from ..cli import app as root_app

    root = typer.main.get_command(root_app)
    assert isinstance(root, click.Group)
    names = root.list_commands(click.Context(root, info_name="pltr"))
    return set(names) | {"help", "--help", "-h", "--version"}


def _reject_reserved(names: Any, param_hint: str) -> None:
    taken = sorted(set(names) & reserved_names())
    if taken:
        raise typer.BadParameter(
            f"{', '.join(repr(name) for name in taken)} "
            f"{'is a pltr command name' if len(taken) == 1 else 'are pltr command names'}; "
            "an alias can't replace a pltr command. Choose another name.",
            param_hint=param_hint,
        )


@app.command()
@pltr_command()
def add(
    name: Annotated[str, typer.Argument(help="Alias name.")],
    command: Annotated[
        str,
        typer.Argument(help='Command line to run instead, e.g. "dataset get".'),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Replace an existing alias of this name."),
    ] = False,
    # -f is --force here, so --format has no short flag.
    format: Annotated[str, format_option(short=False)] = "table",
) -> None:
    """Create an alias (--force replaces an existing one)."""
    _reject_reserved([name], "'NAME'")
    manager = AliasManager()
    existing = manager.get_alias(name)
    if existing is not None and not force:
        raise typer.BadParameter(
            f"alias '{name}' already exists ({name} → {existing}); pass --force to "
            "replace it.",
            param_hint="'NAME'",
        )
    try:
        if existing is None:
            manager.add_alias(name, command)
        else:
            manager.edit_alias(name, command)
    except ValueError as error:  # a circular reference
        raise typer.BadParameter(str(error), param_hint="'COMMAND'") from error
    success(f"{'Created' if existing is None else 'Updated'} alias: {name} → {command}")
    emit(None, format=format)


@app.command()
@pltr_command(destructive=True)
def remove(
    name: AliasName,
    yes: YesOption = False,
    confirm: ConfirmToggleOption = None,
    format: FormatOption = "table",
) -> None:
    """Remove an alias (asks first; --yes skips)."""
    manager = AliasManager()
    command = manager.get_alias(name)
    if command is None:
        raise _alias_not_found(name)
    confirm_destructive(
        f"Remove alias '{name}' ({name} → {command})?", yes=yes or confirm is False
    )
    manager.remove_alias(name)
    success(f"Removed alias '{name}'")
    emit(None, format=format)


@app.command()
@pltr_command()
def edit(
    name: AliasName,
    command: Annotated[str, typer.Argument(help="New command line for the alias.")],
    format: FormatOption = "table",
) -> None:
    """Change the command an alias runs."""
    manager = AliasManager()
    if manager.get_alias(name) is None:
        raise _alias_not_found(name)
    try:
        manager.edit_alias(name, command)
    except ValueError as error:  # a circular reference
        raise typer.BadParameter(str(error), param_hint="'COMMAND'") from error
    success(f"Updated alias: {name} → {command}")
    emit(None, format=format)


@app.command("list")
@pltr_command()
def list_aliases(
    format: FormatOption = "table",
    output: OutputOption = None,
) -> None:
    """List all aliases."""
    aliases = AliasManager().list_aliases()
    records: List[Dict[str, str]] = [
        _record(name, command) for name, command in sorted(aliases.items())
    ]
    emit(records, format=format, output=output, columns=ALIAS_COLUMNS)
    if not records:
        info('Create one with: pltr alias add NAME "COMMAND"')


@app.command()
@pltr_command()
def show(
    name: AliasName,
    format: FormatOption = "table",
    output: OutputOption = None,
) -> None:
    """Show the command an alias runs."""
    command = AliasManager().get_alias(name)
    if command is None:
        raise _alias_not_found(name)
    emit(
        _record(name, command),
        format=format,
        output=output,
        columns=ALIAS_COLUMNS,
        title="Alias",
    )


@app.command()
@pltr_command(destructive=True)
def clear(
    yes: YesOption = False,
    confirm: ConfirmToggleOption = None,
    format: FormatOption = "table",
) -> None:
    """Remove every alias (asks first; --yes skips)."""
    manager = AliasManager()
    count = len(manager.list_aliases())
    if count:
        confirm_destructive(f"Remove all {count} aliases?", yes=yes or confirm is False)
        manager.clear_all()
        success(f"Cleared {count} aliases")
    else:
        info("No aliases to clear")
    emit(None, format=format)


@app.command("export")
@pltr_command()
def export_aliases(output: OutputOption = None) -> None:
    """Write all aliases as a JSON object ({"name": "command", ...}).

    The output is the file format 'pltr alias import' reads.
    """
    aliases = AliasManager().list_aliases()
    emit(dict(sorted(aliases.items())), format="json", output=output)
    if not aliases:
        info("No aliases to export")


@app.command("import")
@pltr_command(destructive=True)
def import_aliases(
    input_file: Annotated[
        str,
        typer.Argument(
            help=(
                'JSON file of aliases ({"name": "command", ...}), as written by '
                "'pltr alias export'."
            ),
        ),
    ],
    merge: Annotated[
        bool,
        typer.Option(
            "--merge",
            "-m",
            help="Keep existing aliases (default: replace them all).",
        ),
    ] = False,
    yes: YesOption = False,
    format: FormatOption = "table",
) -> None:
    """Import aliases from a JSON file.

    Replaces all existing aliases (asks first; --yes skips) unless --merge,
    which keeps them and overwrites only aliases of the same name.
    """
    data = load_json_input(f"@{input_file}", param_hint="'INPUT_FILE'")
    if not isinstance(data, dict) or not all(
        isinstance(name, str) and isinstance(command, str)
        for name, command in data.items()
    ):
        raise typer.BadParameter(
            'expected a JSON object of alias names to commands ({"name": '
            "\"command\", ...}), as written by 'pltr alias export'",
            param_hint="'INPUT_FILE'",
        )
    _reject_reserved(data, "'INPUT_FILE'")

    manager = AliasManager()
    existing = len(manager.list_aliases())
    if existing and not merge:
        confirm_destructive(
            f"Replace your {existing} existing aliases? (--merge keeps them)", yes=yes
        )
        manager.clear_all()
    count = manager.import_aliases(data)
    if count < len(data):
        warn(
            f"Skipped {len(data) - count} alias(es) that would create a circular "
            "reference."
        )
    success(f"Imported {count} aliases from {input_file}")
    emit(None, format=format)


@app.command()
@pltr_command()
def resolve(
    name: AliasName,
    format: FormatOption = "table",
    output: OutputOption = None,
) -> None:
    """Show the command an alias finally runs, following aliases of aliases."""
    manager = AliasManager()
    if manager.get_alias(name) is None:
        raise _alias_not_found(name)
    resolved = manager.resolve_alias(name)
    if resolved == name:
        raise PltrError(
            f"Alias '{name}' refers back to itself through other aliases.",
            hint="Fix it with 'pltr alias edit'.",
        )
    emit(
        _record(name, resolved),
        format=format,
        output=output,
        columns=ALIAS_COLUMNS,
        title="Alias",
    )
