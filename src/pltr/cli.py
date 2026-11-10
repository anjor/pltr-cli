"""
Main CLI entry point for pltr.
"""

import typer
from typing_extensions import Annotated

from pltr import __version__
from pltr.commands import (
    assertions,
    configure,
    context,
    verify,
    dataset,
    folder,
    project,
    resource,
    resource_role,
    space,
    ontology,
    osdk,
    orchestration,
    sql,
    admin,
    shell,
    completion,
    alias,
    mediasets,
    connectivity,
    third_party_applications,
    aip_agents,
    functions,
    streams,
    language_models,
    models,
    data_health,
    audit,
    widgets,
)
from pltr.commands import site
from pltr.commands.cp import cp_command
from pltr.commands import api as api_commands
from pltr.commands import manifest as manifest_commands
from pltr.contract import PltrRootGroup

app = typer.Typer(
    name="pltr",
    help="Command-line interface for Palantir Foundry APIs",
    epilog=(
        "Add --emit-code to any command to print the foundry-platform-sdk Python "
        "code for its call, with your arguments, instead of making the call."
    ),
    no_args_is_help=True,
    cls=PltrRootGroup,
    # PLTR_DEBUG=1 tracebacks must not print each frame's local variables:
    # they hold tokens, Authorization headers and OAuth client secrets. Only the
    # root app's settings apply: typer installs its traceback hook when the root
    # app is called, and sub-apps are only ever added to it with add_typer.
    pretty_exceptions_show_locals=False,
)

# Add subcommands
app.add_typer(configure.app, name="configure", help="Manage authentication profiles")
app.command("verify", short_help="Verify authentication")(verify.verify)
app.add_typer(dataset.app, name="dataset", short_help="Manage datasets")
app.add_typer(
    context.app,
    name="context",
    short_help="Compact summaries of a dataset, folder or ontology for writing code",
)
app.add_typer(
    assertions.app,
    name="assert",
    short_help="Check a dataset, build or object type (exit 8 when a check fails)",
)
app.add_typer(folder.app, name="folder", short_help="Manage folders")
app.add_typer(project.app, name="project", short_help="Manage projects")
app.add_typer(resource.app, name="resource", short_help="Manage resources")
app.add_typer(
    resource_role.app, name="resource-role", short_help="Manage resource permissions"
)
app.add_typer(space.app, name="space", short_help="Manage spaces")
app.add_typer(ontology.app, name="ontology", short_help="Ontology operations")
app.add_typer(
    osdk.app,
    name="osdk",
    short_help="Generate OSDK TypeScript packages for apps (needs Node.js)",
)
app.add_typer(
    orchestration.app,
    name="orchestration",
    short_help="Manage builds, jobs, and schedules",
)
app.add_typer(sql.app, name="sql")
app.add_typer(
    mediasets.app,
    name="media-sets",
    short_help="Manage media sets and media content",
)
app.add_typer(
    connectivity.app,
    name="connectivity",
    short_help="Manage connections and data imports",
)
app.add_typer(
    third_party_applications.app,
    name="third-party-apps",
    help="Manage third-party applications",
)
app.add_typer(
    site.app, name="site", short_help="Deploy a built web app to website hosting"
)
app.add_typer(
    aip_agents.app,
    name="aip-agents",
    help="Manage AIP Agents, sessions, and versions",
)
app.add_typer(
    functions.app,
    name="functions",
    help="Manage Functions queries and value types",
)
app.add_typer(
    streams.app,
    name="streams",
    help="Manage streaming datasets and streams",
)
app.add_typer(
    language_models.app,
    name="language-models",
    help="Interact with language models (Claude, OpenAI embeddings)",
)
app.add_typer(
    models.app,
    name="models",
    help="Manage ML models and versions",
)
app.add_typer(
    data_health.app,
    name="data-health",
    help="Manage data health checks and reports",
)
app.add_typer(
    audit.app,
    name="audit",
    help="Audit log operations for compliance and security monitoring",
)
app.add_typer(
    widgets.app,
    name="widgets",
    help="Manage widget sets, releases, and repositories",
)
app.add_typer(admin.app, name="admin")
app.add_typer(shell.shell_app, name="shell")
app.add_typer(completion.app, name="completion", help="Manage shell completions")
app.add_typer(alias.app, name="alias", help="Manage command aliases")
app.command("cp")(cp_command)
# Generated commands for every SDK method, loaded lazily (see pltr.commands.api).
app.add_typer(api_commands.app, name="api", help=api_commands.HELP)
# The command manifest: list, search and show every command (see pltr.manifest).
app.add_typer(manifest_commands.app, name="commands", help=manifest_commands.HELP)


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        typer.echo(f"pltr {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Annotated[
        bool, typer.Option("--version", callback=version_callback, help="Show version")
    ] = False,
):
    """
    Command-line interface for Palantir Foundry APIs.

    Built on top of the official foundry-platform-sdk, pltr provides
    intuitive commands for dataset management, ontology operations,
    SQL queries, and more.
    """
    pass


@app.command()
def hello():
    """Test command to verify CLI is working."""
    typer.echo("Hello from pltr! 🚀")
    typer.echo("CLI is working correctly.")


def main() -> None:
    """Console-script entry point (``pltr``): resolve aliases, then run the CLI."""
    from pltr.utils.alias_resolver import inject_alias_resolution

    inject_alias_resolution()
    app()


if __name__ == "__main__":
    main()
