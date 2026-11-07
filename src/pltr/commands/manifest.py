"""`pltr commands`: list, search and show the manifest of every pltr command.

The manifest itself is built by :mod:`pltr.manifest` from the live command
tree. These commands make no Foundry call.
"""

from typing import Any, Dict, List, Mapping, Optional, Sequence

import typer
from typing_extensions import Annotated

from ..contract import (
    Columns,
    FormatOption,
    OutputOption,
    emit,
    info,
    pltr_command,
    spinner,
)
from ..manifest import (
    build_manifest,
    filter_manifest,
    find_command,
    find_group,
    metavar,
    normalize_path,
    search,
    suggest,
    summary_entry,
)

HELP = """Find commands: search, list and show the manifest of every pltr command.

The manifest describes every command, curated and generated (pltr api): its
arguments and options, whether it is beta, destructive or paged, its output
formats and the SDK method it calls. To find and run a command: search,
show its entry, then run it with --format json.

\b
Examples:
    pltr commands search list dataset branches
    pltr commands search Dataset.Branch.list
    pltr commands show dataset get --format json
    pltr commands list api datasets
    pltr commands list --format json > manifest.json
"""

app = typer.Typer(no_args_is_help=True)

_LABELS = ("beta", "destructive", "paged", "local", "hidden")


def labels(entry: Mapping[str, Any]) -> str:
    """The flags of a command entry that are set, e.g. ``beta, destructive``."""
    return ", ".join(label for label in _LABELS if entry.get(label))


#: Table/CSV columns for `list` and `search` (one row per command).
SUMMARY_COLUMNS: Columns = {
    "Command": "path",
    "Description": "description",
    "Labels": labels,
}


def describe_argument(argument: Mapping[str, Any]) -> str:
    name = str(argument["name"]).upper() + ("..." if argument["multiple"] else "")
    facts = [argument["type"]]
    if argument["required"]:
        facts.append("required")
    if "default" in argument:
        facts.append(f"default: {argument['default']}")
    text = f"{name} ({', '.join(facts)})"
    return f"{text}: {argument['help']}" if argument.get("help") else text


def describe_option(option: Mapping[str, Any]) -> str:
    text = ", ".join(option["flags"])
    if option["type"] != "flag":
        text += f" {metavar(option)}"
    facts = []
    if option["required"]:
        facts.append("required")
    if option["multiple"]:
        facts.append("repeatable")
    if "default" in option:
        facts.append(f"default: {option['default']}")
    if "envvar" in option:
        facts.append(f"env: {option['envvar']}")
    if facts:
        text += f" ({'; '.join(facts)})"
    return f"{text}: {option['help']}" if option.get("help") else text


def _output_formats(entry: Mapping[str, Any]) -> str:
    if "outputFormats" not in entry:
        return "unknown (not yet on the output contract)"
    return ", ".join(entry["outputFormats"]) or "text (no --format option)"


def _sdk_methods(entry: Mapping[str, Any]) -> str:
    if entry.get("local"):
        return "none (makes no Foundry call)"
    if "sdkMethods" not in entry:
        return "not recorded yet"
    return "\n".join(entry["sdkMethods"]) or "none"


def detail_columns(entry: Mapping[str, Any]) -> Columns:
    """Table/CSV rows for `show`: one property per row."""
    columns: Dict[str, Any] = {
        "Command": "path",
        "Usage": "usage",
        "Description": "description",
        "Labels": labels,
        "Output formats": _output_formats,
        "SDK methods": _sdk_methods,
    }
    if entry.get("httpEndpoints"):
        columns["HTTP endpoints"] = lambda e: "\n".join(e["httpEndpoints"])
    columns["Arguments"] = lambda e: "\n".join(map(describe_argument, e["arguments"]))
    columns["Options"] = lambda e: "\n".join(map(describe_option, e["options"]))
    columns["Help"] = "help"
    return columns


def _load() -> Dict[str, Any]:
    with spinner("Reading the command tree..."):
        return build_manifest()


def _suggestions(manifest: Mapping[str, Any], path: str) -> str:
    matches = suggest(manifest, path)
    text = f" Did you mean: {', '.join(matches)}?" if matches else ""
    return text + " Find commands with: pltr commands search <words>"


def _not_a_command(manifest: Mapping[str, Any], words: Sequence[str]) -> str:
    tokens = normalize_path(words)
    path = " ".join(("pltr", *tokens))
    if find_group(manifest, tokens) is not None:
        return (
            f"'{path}' is a group of commands, not a command. List them with: "
            f"pltr commands list {' '.join(tokens)}"
        )
    return f"no command '{path}'." + _suggestions(manifest, path)


@app.command("list")
@pltr_command()
def list_commands(
    path: Annotated[
        Optional[List[str]],
        typer.Argument(
            help="Only commands under this path, e.g. `dataset` or `api datasets`.",
            show_default=False,
        ),
    ] = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """List every command; with --format json, print the whole manifest.

    The JSON document is {"pltrVersion", "sdkVersion", "groups", "commands"}:
    one entry per command with its usage, description, arguments, options,
    beta/destructive/paged, output formats and SDK methods, sorted by path.
    The output is deterministic: two runs print the same bytes.
    """
    manifest = _load()
    if path:
        selected = filter_manifest(manifest, path)
        if not selected["commands"]:
            where = " ".join(("pltr", *normalize_path(path)))
            raise typer.BadParameter(
                f"no commands under '{where}'." + _suggestions(manifest, where),
                param_hint="'[PATH]...'",
            )
        manifest = selected
    emit(
        manifest,
        format=format,
        output=output,
        columns=SUMMARY_COLUMNS,
        rows=lambda document: document["commands"],
    )


@app.command("search")
@pltr_command()
def search_commands(
    text: Annotated[
        List[str],
        typer.Argument(
            help=(
                "What to look for: words (list dataset branches), a command "
                "path, or an SDK method (Dataset.Branch.list)."
            ),
            show_default=False,
        ),
    ],
    limit: Annotated[
        int, typer.Option("--limit", "-n", min=1, help="Maximum number of results.")
    ] = 10,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Search commands by name, description and SDK method, best match first.

    Commands that match more of the words come first; an exact command path
    or SDK method ranks highest, and curated commands rank above generated
    `pltr api` commands that match as well. JSON prints
    {"data": [...], "totalCount": N}: each item summarizes a command's
    manifest entry (path, usage, description, beta, destructive, paged,
    generated, local, sdkMethods). `pltr commands show <path>` prints the
    whole entry.
    """
    manifest = _load()
    matches = search(manifest["commands"], " ".join(text))
    document = {
        "data": [summary_entry(entry) for entry in matches[:limit]],
        "totalCount": len(matches),
    }
    emit(
        document,
        format=format,
        output=output,
        columns=SUMMARY_COLUMNS,
        rows=lambda result: result["data"],
    )
    if len(matches) > limit:
        info(f"Showing {limit} of {len(matches)} matches; use --limit to see more.")


@app.command("show")
@pltr_command()
def show_command(
    command: Annotated[
        List[str],
        typer.Argument(
            help=(
                'The command\'s path: dataset get, "dataset get" or "pltr dataset get".'
            ),
            show_default=False,
        ),
    ],
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Show one command's manifest entry: usage, arguments, options and more.

    The entry says whether the command is beta, destructive (asks for
    confirmation; --yes skips it) or paged, which output formats it has and
    which SDK method it calls. JSON prints the entry exactly as it appears in
    `pltr commands list --format json`.
    """
    manifest = _load()
    entry = find_command(manifest, command)
    if entry is None:
        raise typer.BadParameter(
            _not_a_command(manifest, command), param_hint="'COMMAND...'"
        )
    emit(entry, format=format, output=output, columns=detail_columns(entry))
