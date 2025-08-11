"""
Interactive shell (REPL) command for the pltr CLI.
Provides an interactive mode with tab completion and command history.
"""

import os
from pathlib import Path
from typing import Optional

import typer
from click_repl import repl  # type: ignore
from prompt_toolkit.history import FileHistory
from rich.console import Console

from ..config.profiles import ProfileManager

shell_app = typer.Typer(
    name="shell",
    help="Start an interactive shell session with tab completion and history",
)


def get_history_file() -> Path:
    """Get the path to the history file for the REPL."""
    config_dir = Path.home() / ".config" / "pltr"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "repl_history"


def get_prompt() -> str:
    """Get the prompt string for the REPL."""
    try:
        profile_manager = ProfileManager()
        current_profile = profile_manager.get_active_profile()
        if current_profile:
            return f"pltr ({current_profile})> "
        else:
            return "pltr> "
    except Exception:
        return "pltr> "


@shell_app.command()
def start(
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use for the session"
    ),
) -> None:
    """
    Start an interactive shell session for pltr CLI.

    Features:
    - Tab completion for all commands
    - Command history (persistent across sessions)
    - Current profile displayed in prompt
    - All pltr commands available without the 'pltr' prefix

    Examples:
        # Start interactive shell
        $ pltr shell

        # In the shell, run commands without 'pltr' prefix:
        pltr> dataset get ri.foundry.main.dataset.123
        pltr> ontology list
        pltr> sql execute "SELECT * FROM dataset LIMIT 10"

        # Exit the shell:
        pltr> exit
    """
    console = Console()

    # Set profile if specified
    if profile:
        os.environ["PLTR_PROFILE"] = profile
        console.print(f"[green]Using profile: {profile}[/green]")

    # Welcome message
    console.print("\n[bold cyan]Welcome to pltr interactive shell![/bold cyan]")
    console.print("Type 'help' for available commands, 'exit' to quit.\n")

    # Import here to avoid circular dependency
    from ..cli import app as main_app

    # Convert Typer app to Click object and create context
    # This is the correct way to integrate click-repl with Typer
    from typer.main import get_command

    click_app = get_command(main_app)
    ctx = click_app.make_context("pltr", [])

    # Start the REPL with the Click context
    repl(
        ctx,
        prompt_kwargs={
            "message": get_prompt,
            "history": FileHistory(str(get_history_file())),
            "complete_while_typing": True,
            "enable_history_search": True,
        },
    )

    console.print("\n[cyan]Goodbye![/cyan]")


# Make 'start' the default command when just running 'pltr shell'
@shell_app.callback(invoke_without_command=True)
def shell_callback(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use for the session"
    ),
) -> None:
    """Interactive shell mode with tab completion and command history."""
    if ctx.invoked_subcommand is None:
        start(profile=profile)


# Alternative command name for convenience
@shell_app.command("interactive", hidden=True)
def interactive_alias(
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use for the session"
    ),
) -> None:
    """Alias for 'start' command."""
    start(profile=profile)
