"""
Configuration commands for pltr CLI.
"""

import typer
from typing import NoReturn, Optional
from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt, Confirm

from ..auth.storage import CredentialStorage
from ..auth.base import KeyringUnavailableError, ProfileNotFoundError
from ..config.profiles import ProfileManager

app = typer.Typer()
console = Console()
err_console = Console(stderr=True)

# Exit code for authentication/credential problems (roadmap decision 6).
EXIT_AUTH = 3


def _keyring_unavailable(error: KeyringUnavailableError) -> NoReturn:
    """Explain that the keyring can't be used (pointing to env-var auth) and exit."""
    err_console.print(f"[red]Error:[/red] {escape(str(error))}", soft_wrap=True)
    raise typer.Exit(EXIT_AUTH)


@app.command()
def configure(
    profile: Optional[str] = typer.Option(
        "default", "--profile", "-p", help="Profile name"
    ),
    auth_type: Optional[str] = typer.Option(
        None, "--auth-type", help="Authentication type (token or oauth)"
    ),
    host: Optional[str] = typer.Option(None, "--host", help="Foundry host URL"),
    token: Optional[str] = typer.Option(
        None, "--token", help="Bearer token (for token auth)"
    ),
    client_id: Optional[str] = typer.Option(
        None, "--client-id", help="OAuth client ID"
    ),
    client_secret: Optional[str] = typer.Option(
        None, "--client-secret", help="OAuth client secret"
    ),
):
    """Configure authentication for Palantir Foundry."""
    storage = CredentialStorage()
    profile_manager = ProfileManager()

    # Ensure profile is not None
    if not profile:
        profile = "default"

    # Check if profile already exists (this also fails fast, before any prompt,
    # when there is no usable keyring)
    try:
        profile_exists = storage.profile_exists(profile)
    except KeyringUnavailableError as e:
        _keyring_unavailable(e)
    if profile_exists:
        if not Confirm.ask(f"Profile '{profile}' already exists. Overwrite?"):
            console.print("[yellow]Configuration cancelled.[/yellow]")
            raise typer.Exit()

    # Interactive mode if no auth type specified
    if not auth_type:
        auth_type = Prompt.ask(
            "Authentication type", choices=["token", "oauth"], default="token"
        )

    # Get host URL
    if not host:
        host = Prompt.ask(
            "Foundry host URL", default="https://your-stack.palantirfoundry.com"
        )

    credentials = {"auth_type": auth_type, "host": host}

    if auth_type == "token":
        # Token authentication
        if not token:
            token = Prompt.ask("Bearer token", password=True)
        credentials["token"] = token

    elif auth_type == "oauth":
        # OAuth authentication
        if not client_id:
            client_id = Prompt.ask("OAuth client ID")
        if not client_secret:
            client_secret = Prompt.ask("OAuth client secret", password=True)

        credentials["client_id"] = client_id
        credentials["client_secret"] = client_secret

    # Save credentials
    try:
        storage.save_profile(profile, credentials)
    except KeyringUnavailableError as e:
        _keyring_unavailable(e)
    profile_manager.add_profile(profile)

    # Set as default if it's the first profile
    if len(profile_manager.list_profiles()) == 1:
        profile_manager.set_default(profile)

    console.print(f"[green]✓[/green] Profile '{profile}' configured successfully")


@app.command()
def list_profiles():
    """List all configured profiles."""
    profile_manager = ProfileManager()
    profiles = profile_manager.list_profiles()
    default = profile_manager.get_default()

    if not profiles:
        console.print("[yellow]No profiles configured.[/yellow]")
        console.print("Run 'pltr configure' to set up your first profile.")
        return

    console.print("[bold]Configured profiles:[/bold]")
    for profile in profiles:
        if profile == default:
            console.print(f"  * {profile} [green](default)[/green]")
        else:
            console.print(f"    {profile}")


@app.command()
def set_default(
    profile: str = typer.Argument(..., help="Profile name to set as default"),
):
    """Set a profile as the default."""
    profile_manager = ProfileManager()

    if profile not in profile_manager.list_profiles():
        console.print(f"[red]Error:[/red] Profile '{profile}' not found")
        raise typer.Exit(1)

    profile_manager.set_default(profile)
    console.print(f"[green]✓[/green] Profile '{profile}' set as default")


@app.command()
def delete(
    profile: str = typer.Argument(..., help="Profile name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a profile."""
    storage = CredentialStorage()
    profile_manager = ProfileManager()

    if profile not in profile_manager.list_profiles():
        console.print(f"[red]Error:[/red] Profile '{profile}' not found")
        raise typer.Exit(1)

    if not force:
        if not Confirm.ask(f"Delete profile '{profile}'?"):
            console.print("[yellow]Deletion cancelled.[/yellow]")
            raise typer.Exit()

    try:
        storage.delete_profile(profile)
        profile_manager.remove_profile(profile)
        console.print(f"[green]✓[/green] Profile '{profile}' deleted")
    except KeyringUnavailableError as e:
        _keyring_unavailable(e)
    except ProfileNotFoundError:
        console.print(f"[red]Error:[/red] Could not delete profile '{profile}'")
        raise typer.Exit(1)
