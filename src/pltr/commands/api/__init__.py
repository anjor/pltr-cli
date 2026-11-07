"""`pltr api`: one generated command per Foundry Platform SDK (V2) method.

The tree mirrors the SDK client: `pltr api <namespace> <resource> [<sub-resource>...]
<method>`, with snake_case and CamelCase names turned into kebab-case. Commands are
generated ahead of time by `scripts/generate_api_commands.py` into declarative specs
(`_specs/`) and built lazily by `_runtime`, so importing this module stays cheap.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import click
import typer
from typer.core import TyperGroup

from . import _runtime

HELP = "Generated commands for every Foundry Platform SDK (V2) method"

DESCRIPTION = (
    "Generated commands for every Foundry Platform SDK (V2) method, mirroring the "
    "SDK: pltr api <namespace> <resource> [<sub-resource>...] <method>.\n\n"
    "Arguments are the endpoint's path parameters (mostly RIDs, the Resource "
    "Identifiers such as ri.foundry.main.dataset.<uuid>); everything else is an "
    "option. Complex values take JSON (inline, @file.json or @- for stdin). Beta "
    "endpoints are labeled [beta] and called with preview=True automatically. "
    "Destructive methods ask for confirmation (--yes skips it). The curated "
    "top-level commands (pltr dataset, pltr ontology, ...) remain the polished "
    "path for common tasks."
)


class ApiGroup(TyperGroup):
    """The `pltr api` group: namespaces come from the generated index."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.short_help = HELP
        self.help = DESCRIPTION
        self._built: Dict[str, click.Command] = {}

    def list_commands(self, ctx: click.Context) -> List[str]:
        return sorted(_runtime._index().NAMESPACES)

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        return _runtime.index_child(
            _runtime._index().NAMESPACES, cmd_name, ("api",), self._built
        )

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        # Plain click help, like the rest of the generated tree (SDK docstrings
        # contain brackets that rich markup would interpret).
        click.Group.format_help(self, ctx, formatter)


app = typer.Typer(
    name="api",
    cls=ApiGroup,
    help=HELP,
    no_args_is_help=True,
)
