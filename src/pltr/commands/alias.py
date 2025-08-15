"""Command alias management commands."""

import json
from typing import Optional

import typer
from rich import print as rprint

from pltr.config.aliases import AliasManager
from pltr.utils.completion import complete_alias_names

app = typer.Typer(name="alias", help="Manage command aliases", no_args_is_help=True)


@app.command()
def add(
    name: str = typer.Argument(..., help="Alias name"),
    command: str = typer.Argument(..., help="Command to alias"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing alias"),
) -> None:
    """Create a new command alias."""
    manager = AliasManager()

    # Check if alias already exists
    if manager.get_alias(name) and not force:
        rprint(f"[red]Alias '{name}' already exists. Use --force to overwrite.[/red]")
        raise typer.Exit(1)

    # Check for reserved command names
    reserved_commands = [
        "configure",
        "verify",
        "dataset",
        "ontology",
        "sql",
        "admin",
        "shell",
        "completion",
        "alias",
        "help",
        "--version",
    ]
    if name in reserved_commands:
        rprint(f"[red]Cannot use reserved command name '{name}' as alias[/red]")
        raise typer.Exit(1)

    try:
        if force and manager.get_alias(name):
            success = manager.edit_alias(name, command)
            action = "Updated"
        else:
            success = manager.add_alias(name, command)
            action = "Created"

        if success:
            rprint(f"[green]{action} alias:[/green] {name} → {command}")
        else:
            rprint(f"[red]Failed to create alias '{name}'[/red]")
            raise typer.Exit(1)
    except ValueError as e:
        rprint(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def remove(
    name: str = typer.Argument(
        ..., help="Alias name to remove", autocompletion=complete_alias_names
    ),
    confirm: bool = typer.Option(
        True, "--confirm/--no-confirm", help="Confirm removal"
    ),
) -> None:
    """Remove a command alias."""
    manager = AliasManager()

    command = manager.get_alias(name)
    if not command:
        rprint(f"[red]Alias '{name}' not found[/red]")
        raise typer.Exit(1)

    if confirm:
        confirmation = typer.confirm(f"Remove alias '{name}' → {command}?")
        if not confirmation:
            rprint("[yellow]Removal cancelled[/yellow]")
            return

    if manager.remove_alias(name):
        rprint(f"[green]Removed alias '{name}'[/green]")
    else:
        rprint(f"[red]Failed to remove alias '{name}'[/red]")
        raise typer.Exit(1)


@app.command()
def edit(
    name: str = typer.Argument(
        ..., help="Alias name to edit", autocompletion=complete_alias_names
    ),
    command: str = typer.Argument(..., help="New command for the alias"),
) -> None:
    """Edit an existing command alias."""
    manager = AliasManager()

    if not manager.get_alias(name):
        rprint(f"[red]Alias '{name}' not found[/red]")
        raise typer.Exit(1)

    try:
        if manager.edit_alias(name, command):
            rprint(f"[green]Updated alias:[/green] {name} → {command}")
        else:
            rprint(f"[red]Failed to edit alias '{name}'[/red]")
            raise typer.Exit(1)
    except ValueError as e:
        rprint(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("list")
def list_aliases() -> None:
    """List all command aliases."""
    manager = AliasManager()
    manager.display_aliases()


@app.command()
def show(
    name: str = typer.Argument(
        ..., help="Alias name to show", autocompletion=complete_alias_names
    ),
) -> None:
    """Show details of a specific alias."""
    manager = AliasManager()
    manager.display_aliases(name)


@app.command()
def clear(
    confirm: bool = typer.Option(
        True, "--confirm/--no-confirm", help="Confirm clearing all aliases"
    ),
) -> None:
    """Clear all command aliases."""
    manager = AliasManager()

    aliases = manager.list_aliases()
    if not aliases:
        rprint("[yellow]No aliases to clear[/yellow]")
        return

    if confirm:
        confirmation = typer.confirm(f"Clear all {len(aliases)} aliases?")
        if not confirmation:
            rprint("[yellow]Clear cancelled[/yellow]")
            return

    count = manager.clear_all()
    rprint(f"[green]Cleared {count} aliases[/green]")


@app.command("export")
def export_aliases(
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
) -> None:
    """Export aliases to JSON format."""
    manager = AliasManager()
    aliases = manager.export_aliases()

    if not aliases:
        rprint("[yellow]No aliases to export[/yellow]")
        return

    json_data = json.dumps(aliases, indent=2, sort_keys=True)

    if output:
        with open(output, "w") as f:
            f.write(json_data)
        rprint(f"[green]Exported {len(aliases)} aliases to {output}[/green]")
    else:
        print(json_data)


@app.command("import")
def import_aliases(
    input_file: str = typer.Argument(..., help="JSON file containing aliases"),
    merge: bool = typer.Option(
        False, "--merge", "-m", help="Merge with existing aliases (default: replace)"
    ),
) -> None:
    """Import aliases from a JSON file."""
    manager = AliasManager()

    try:
        with open(input_file, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        rprint(f"[red]Error reading file: {e}[/red]")
        raise typer.Exit(1)

    if not isinstance(data, dict):
        rprint("[red]Invalid format: expected JSON object with alias mappings[/red]")
        raise typer.Exit(1)

    # Clear existing aliases if not merging
    if not merge and manager.list_aliases():
        confirmation = typer.confirm("Replace existing aliases?")
        if not confirmation:
            rprint("[yellow]Import cancelled[/yellow]")
            return
        manager.clear_all()

    count = manager.import_aliases(data)
    rprint(f"[green]Imported {count} aliases from {input_file}[/green]")


@app.command()
def resolve(
    command: str = typer.Argument(
        ..., help="Command to resolve", autocompletion=complete_alias_names
    ),
) -> None:
    """Resolve an alias to show the actual command."""
    manager = AliasManager()

    resolved = manager.resolve_alias(command)
    if resolved == command:
        if command in manager.list_aliases():
            rprint(
                f"[yellow]'{command}' is an alias but may have circular references[/yellow]"
            )
        else:
            rprint(f"[yellow]'{command}' is not an alias[/yellow]")
    else:
        rprint(f"[green]{command}[/green] → {resolved}")


if __name__ == "__main__":
    app()
