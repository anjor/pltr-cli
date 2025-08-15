"""
Verification command to test authentication.
"""

import typer
import requests
from typing import Optional
from rich.console import Console
from rich.table import Table

from ..auth.manager import AuthManager
from ..auth.base import (
    ProfileNotFoundError,
    MissingCredentialsError,
    InvalidCredentialsError,
)

app = typer.Typer()
console = Console()


@app.callback(invoke_without_command=True)
def verify(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile to verify"
    ),
):
    """Verify authentication by connecting to Palantir Foundry."""
    if ctx.invoked_subcommand is not None:
        return

    auth_manager = AuthManager()

    # Show which profile we're using
    active_profile = profile or auth_manager.get_current_profile()
    if not active_profile:
        console.print("[red]Error:[/red] No profile configured")
        console.print("Run 'pltr configure configure' to set up authentication")
        raise typer.Exit(1)

    console.print(f"Verifying profile: [bold]{active_profile}[/bold]")

    try:
        # Get credentials directly without creating SDK client
        from ..auth.storage import CredentialStorage

        storage = CredentialStorage()

        # Get credentials for the profile
        try:
            credentials = storage.get_profile(active_profile)
        except ProfileNotFoundError:
            console.print(f"[red]Error:[/red] Profile '{active_profile}' not found")
            raise typer.Exit(1)

        # Extract authentication details
        host = credentials.get("host")
        auth_type = credentials.get("auth_type")

        if not host:
            console.print(
                f"[red]Error:[/red] No host URL configured for profile '{active_profile}'"
            )
            raise typer.Exit(1)

        # Prepare the request
        url = f"{host}/multipass/api/me"
        headers = {}

        # Set up authentication headers based on type
        if auth_type == "token":
            token = credentials.get("token")
            if not token:
                console.print(
                    f"[red]Error:[/red] No token configured for profile '{active_profile}'"
                )
                raise typer.Exit(1)
            headers["Authorization"] = f"Bearer {token}"

        elif auth_type == "oauth":
            # OAuth - need to get access token first
            client_id = credentials.get("client_id")
            client_secret = credentials.get("client_secret")

            if not client_id or not client_secret:
                console.print(
                    f"[red]Error:[/red] OAuth credentials incomplete for profile '{active_profile}'"
                )
                raise typer.Exit(1)

            token_url = f"{host}/multipass/api/oauth2/token"
            token_response = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=30,
            )
            if token_response.status_code == 200:
                access_token = token_response.json().get("access_token")
                headers["Authorization"] = f"Bearer {access_token}"
            else:
                console.print(
                    f"[red]Error:[/red] Failed to get OAuth token: {token_response.text}"
                )
                raise typer.Exit(1)

        # Make the request to /multipass/api/me
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            user_info = response.json()

            # Display success with user information
            console.print("[green]✓[/green] Authentication successful!")
            console.print()

            # Create a table with user information
            table = Table(title="User Information", show_header=False)
            table.add_column("Field", style="cyan")
            table.add_column("Value")

            # Add user details
            table.add_row("Username", user_info.get("username", "N/A"))
            table.add_row("Email", user_info.get("email", "N/A"))
            table.add_row("User ID", user_info.get("id", "N/A"))

            # Add organization info if available
            if "organization" in user_info:
                table.add_row(
                    "Organization", user_info["organization"].get("rid", "N/A")
                )

            # Add groups if available
            if "groups" in user_info and user_info["groups"]:
                groups_list = ", ".join(
                    g.get("name", "N/A") for g in user_info["groups"][:3]
                )
                if len(user_info["groups"]) > 3:
                    groups_list += f" (+{len(user_info['groups']) - 3} more)"
                table.add_row("Groups", groups_list)

            console.print(table)
            console.print()
            console.print(
                f"[green]Profile '{active_profile}' is properly configured![/green]"
            )

        elif response.status_code == 401:
            console.print("[red]✗[/red] Authentication failed: Invalid credentials")
            console.print(
                f"Please check your token/credentials for profile '{active_profile}'"
            )
            raise typer.Exit(1)
        elif response.status_code == 403:
            console.print("[red]✗[/red] Authentication failed: Access forbidden")
            console.print(
                "Your credentials are valid but you don't have access to this endpoint"
            )
            raise typer.Exit(1)
        else:
            console.print(f"[red]✗[/red] Request failed: {response.status_code}")
            console.print(f"Response: {response.text}")
            raise typer.Exit(1)

    except ProfileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except MissingCredentialsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except InvalidCredentialsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except requests.exceptions.ConnectionError:
        console.print(
            "[red]✗[/red] Connection failed: Unable to reach the Foundry host"
        )
        console.print("Please check your network connection and host URL")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] Unexpected error: {e}")
        raise typer.Exit(1)
