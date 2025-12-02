"""
Admin commands for the pltr CLI.
Provides commands for user, group, role, and organization management.
"""

from pathlib import Path
from typing import List, Optional

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
marking_app = typer.Typer(name="marking", help="Marking management operations")

# Add sub-apps to main admin app
app.add_typer(user_app, name="user")
app.add_typer(group_app, name="group")
app.add_typer(role_app, name="role")
app.add_typer(org_app, name="org")
app.add_typer(marking_app, name="marking")


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


@user_app.command("delete")
def delete_user(
    user_id: str = typer.Argument(..., help="User ID or RID"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
) -> None:
    """Delete a specific user."""
    console = Console()

    # Confirmation prompt
    if not confirm:
        user_confirm = typer.confirm(f"Are you sure you want to delete user {user_id}?")
        if not user_confirm:
            console.print("Operation cancelled.")
            return

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Deleting user {user_id}..."):
            result = service.delete_user(user_id)

        console.print(f"[green]{result['message']}[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@user_app.command("batch-get")
def batch_get_users(
    user_ids: List[str] = typer.Argument(
        ..., help="User IDs or RIDs (space-separated, max 500)"
    ),
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
    """Batch retrieve multiple users (max 500)."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching {len(user_ids)} users..."
        ):
            result = service.get_batch_users(user_ids)

        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
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


@group_app.command("batch-get")
def batch_get_groups(
    group_ids: List[str] = typer.Argument(
        ..., help="Group IDs or RIDs (space-separated, max 500)"
    ),
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
    """Batch retrieve multiple groups (max 500)."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching {len(group_ids)} groups..."
        ):
            result = service.get_batch_groups(group_ids)

        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
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


@role_app.command("batch-get")
def batch_get_roles(
    role_ids: List[str] = typer.Argument(
        ..., help="Role IDs or RIDs (space-separated, max 500)"
    ),
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
    """Batch retrieve multiple roles (max 500)."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching {len(role_ids)} roles..."
        ):
            result = service.get_batch_roles(role_ids)

        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
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


@org_app.command("create")
def create_organization(
    name: str = typer.Argument(..., help="Organization name"),
    enrollment_rid: str = typer.Option(..., "--enrollment-rid", help="Enrollment RID"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    admin_ids: Optional[List[str]] = typer.Option(
        None, "--admin-id", help="Admin user IDs (can specify multiple)"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
) -> None:
    """Create a new organization."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Creating organization '{name}'..."
        ):
            result = service.create_organization(
                name=name, enrollment_rid=enrollment_rid, admin_ids=admin_ids
            )

        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)
            console.print(f"[green]Organization '{name}' created successfully[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@org_app.command("replace")
def replace_organization(
    organization_rid: str = typer.Argument(..., help="Organization RID"),
    name: str = typer.Argument(..., help="New organization name"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="New organization description"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
) -> None:
    """Replace/update an existing organization."""
    console = Console()
    formatter = OutputFormatter()

    if not confirm:
        user_confirm = typer.confirm(
            f"Are you sure you want to replace organization {organization_rid}?"
        )
        if not user_confirm:
            console.print("Operation cancelled.")
            return

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Replacing organization {organization_rid}..."
        ):
            result = service.replace_organization(
                organization_rid=organization_rid, name=name, description=description
            )

        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)
            console.print(
                f"[green]Organization '{organization_rid}' replaced successfully[/green]"
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@org_app.command("available-roles")
def list_available_roles(
    organization_rid: str = typer.Argument(..., help="Organization RID"),
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
        None, "--page-size", help="Number of roles per page"
    ),
    page_token: Optional[str] = typer.Option(
        None, "--page-token", help="Pagination token from previous response"
    ),
) -> None:
    """List available roles for an organization."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching available roles for organization {organization_rid}..."
        ):
            result = service.list_available_roles(
                organization_rid, page_size=page_size, page_token=page_token
            )

        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


# Marking Management Commands
@marking_app.command("list")
def list_markings(
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
        None, "--page-size", help="Number of markings per page"
    ),
    page_token: Optional[str] = typer.Option(
        None, "--page-token", help="Pagination token from previous response"
    ),
) -> None:
    """List all markings."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching markings..."):
            result = service.list_markings(page_size=page_size, page_token=page_token)

        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@marking_app.command("get")
def get_marking(
    marking_id: str = typer.Argument(..., help="Marking ID"),
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
    """Get information about a specific marking."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching marking {marking_id}..."
        ):
            result = service.get_marking(marking_id)

        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@marking_app.command("batch-get")
def batch_get_markings(
    marking_ids: List[str] = typer.Argument(
        ..., help="Marking IDs (space-separated, max 500)"
    ),
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
    """Batch retrieve multiple markings (max 500)."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching {len(marking_ids)} markings..."
        ):
            result = service.get_batch_markings(marking_ids)

        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@marking_app.command("create")
def create_marking(
    name: str = typer.Argument(..., help="Marking name"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="Marking description"
    ),
    category_id: Optional[str] = typer.Option(
        None, "--category-id", help="Category ID for the marking"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
) -> None:
    """Create a new marking."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Creating marking '{name}'..."):
            result = service.create_marking(
                name=name, description=description, category_id=category_id
            )

        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)
            console.print(f"[green]Marking '{name}' created successfully[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@marking_app.command("replace")
def replace_marking(
    marking_id: str = typer.Argument(..., help="Marking ID"),
    name: str = typer.Argument(..., help="New marking name"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="New marking description"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
) -> None:
    """Replace/update an existing marking."""
    console = Console()
    formatter = OutputFormatter()

    if not confirm:
        user_confirm = typer.confirm(
            f"Are you sure you want to replace marking {marking_id}?"
        )
        if not user_confirm:
            console.print("Operation cancelled.")
            return

    try:
        service = AdminService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Replacing marking {marking_id}..."
        ):
            result = service.replace_marking(
                marking_id=marking_id, name=name, description=description
            )

        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"Results saved to {output_file}")
        else:
            formatter.display(result, output_format)
            console.print(
                f"[green]Marking '{marking_id}' replaced successfully[/green]"
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
