"""
Main CLI entry point for pltr.
"""

import typer
from typing_extensions import Annotated

from pltr import __version__
from pltr.commands import configure, verify, dataset

app = typer.Typer(
    name="pltr",
    help="Command-line interface for Palantir Foundry APIs",
    no_args_is_help=True,
)

# Add subcommands
app.add_typer(configure.app, name="configure", help="Manage authentication profiles")
app.add_typer(verify.app, name="verify", help="Verify authentication")
app.add_typer(dataset.app, name="dataset", help="Manage datasets")


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        typer.echo(f"pltr {__version__}")
        raise typer.Exit()


@app.callback()
def main(
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


if __name__ == "__main__":
    app()
