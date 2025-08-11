"""
Admin commands for the pltr CLI.
Provides commands for user, group, role, and organization management.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ..services.admin import AdminService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker

# Create the main admin app
app = typer.Typer(
    name="admin", help="Admin operations for user, group, and organization management"
)

# Create sub-apps for different admin categories
user_app = typer.Typer(name="user", help="User management operations")
group_app = typer.Typer(name="group", help="Group management operations")
role_app = typer.Typer(name="role", help="Role management operations")
org_app = typer.Typer(name="org", help="Organization management operations")

# Add sub-apps to main admin app
app.add_typer(user_app, name="user")
app.add_typer(group_app, name="group")
app.add_typer(role_app, name="role")
app.add_typer(org_app, name="org")


# User Management Commands
@user_app.command("list")
def list_users(
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of users per page"
    ),
    page_token: Optional[str] = typer.Option(
        None, "--page-token", help="Pagination token from previous response"
    ),
) -> None:
    """List all users in the organization."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching users..."):
            result = service.list_users(page_size=page_size, page_token=page_token)

        # Format and display results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@user_app.command("get")
def get_user(
    user_id: str = typer.Argument(..., help="User ID or RID"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
) -> None:
    """Get information about a specific user."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Fetching user {user_id}..."):
            result = service.get_user(user_id)

        # Format and display results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@user_app.command("current")
def get_current_user(
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
) -> None:
    """Get information about the current authenticated user."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching current user info..."):
            result = service.get_current_user()

        # Format and display results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@user_app.command("search")
def search_users(
    query: str = typer.Argument(..., help="Search query string"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of users per page"
    ),
    page_token: Optional[str] = typer.Option(
        None, "--page-token", help="Pagination token from previous response"
    ),
) -> None:
    """Search for users by query string."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Searching users for '{query}'..."
        ):
            result = service.search_users(
                query=query, page_size=page_size, page_token=page_token
            )

        # Format and display results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@user_app.command("markings")
def get_user_markings(
    user_id: str = typer.Argument(..., help="User ID or RID"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
) -> None:
    """Get markings/permissions for a specific user."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching markings for user {user_id}..."
        ):
            result = service.get_user_markings(user_id)

        # Format and display results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@user_app.command("revoke-tokens")
def revoke_user_tokens(
    user_id: str = typer.Argument(..., help="User ID or RID"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
) -> None:
    """Revoke all tokens for a specific user."""
    console = Console()

    # Confirmation prompt
    if not confirm:
        user_confirm = typer.confirm(
            f"Are you sure you want to revoke all tokens for user {user_id}?"
        )
        if not user_confirm:
            console.print("Operation cancelled.")
            return

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Revoking tokens for user {user_id}..."
        ):
            result = service.revoke_user_tokens(user_id)

        console.print(f"[green]{result['message']}[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


# Group Management Commands
@group_app.command("list")
def list_groups(
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of groups per page"
    ),
    page_token: Optional[str] = typer.Option(
        None, "--page-token", help="Pagination token from previous response"
    ),
) -> None:
    """List all groups in the organization."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching groups..."):
            result = service.list_groups(page_size=page_size, page_token=page_token)

        # Format and display results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@group_app.command("get")
def get_group(
    group_id: str = typer.Argument(..., help="Group ID or RID"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
) -> None:
    """Get information about a specific group."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Fetching group {group_id}..."):
            result = service.get_group(group_id)

        # Format and display results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@group_app.command("search")
def search_groups(
    query: str = typer.Argument(..., help="Search query string"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of groups per page"
    ),
    page_token: Optional[str] = typer.Option(
        None, "--page-token", help="Pagination token from previous response"
    ),
) -> None:
    """Search for groups by query string."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Searching groups for '{query}'..."
        ):
            result = service.search_groups(
                query=query, page_size=page_size, page_token=page_token
            )

        # Format and display results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@group_app.command("create")
def create_group(
    name: str = typer.Argument(..., help="Group name"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="Group description"
    ),
    organization_rid: Optional[str] = typer.Option(
        None, "--org-rid", help="Organization RID"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
) -> None:
    """Create a new group."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Creating group '{name}'..."):
            result = service.create_group(
                name=name, description=description, organization_rid=organization_rid
            )

        # Format and display results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)
            console.print(f"[green]Group '{name}' created successfully[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@group_app.command("delete")
def delete_group(
    group_id: str = typer.Argument(..., help="Group ID or RID"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
) -> None:
    """Delete a specific group."""
    console = Console()

    # Confirmation prompt
    if not confirm:
        user_confirm = typer.confirm(
            f"Are you sure you want to delete group {group_id}?"
        )
        if not user_confirm:
            console.print("Operation cancelled.")
            return

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Deleting group {group_id}..."):
            result = service.delete_group(group_id)

        console.print(f"[green]{result['message']}[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


# Role Management Commands
@role_app.command("get")
def get_role(
    role_id: str = typer.Argument(..., help="Role ID or RID"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
) -> None:
    """Get information about a specific role."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Fetching role {role_id}..."):
            result = service.get_role(role_id)

        # Format and display results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


# Organization Management Commands
@org_app.command("get")
def get_organization(
    organization_id: str = typer.Argument(..., help="Organization ID or RID"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
) -> None:
    """Get information about a specific organization."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching organization {organization_id}..."
        ):
            result = service.get_organization(organization_id)

        # Format and display results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
