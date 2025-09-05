"""
Space management commands for Foundry filesystem.
"""

import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table

from ..services.space import SpaceService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..auth.base import ProfileNotFoundError, MissingCredentialsError
from ..utils.completion import (
    complete_rid,
    complete_profile,
    complete_output_format,
    cache_rid,
)

app = typer.Typer()
console = Console()
formatter = OutputFormatter(console)


@app.command("create")
def create_space(
    name: str = typer.Argument(..., help="Space display name"),
    organization_rid: str = typer.Option(
        ...,
        "--organization-rid",
        "-org",
        help="Organization Resource Identifier",
        autocompletion=complete_rid,
    ),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Space description"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
):
    """Create a new space in Foundry."""
    try:
        service = SpaceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Creating space '{name}'..."):
            space = service.create_space(
                display_name=name,
                organization_rid=organization_rid,
                description=description,
            )

        # Cache the RID for future completions
        if space.get("rid"):
            cache_rid(space["rid"])

        formatter.print_success(f"Successfully created space '{name}'")
        formatter.print_info(f"Space RID: {space.get('rid', 'unknown')}")
        formatter.print_info(
            f"Root Folder RID: {space.get('root_folder_rid', 'unknown')}"
        )

        # Format output
        if format == "json":
            formatter.format_dict(space)
        elif format == "csv":
            formatter.format_list([space])
        else:
            _format_space_table(space)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create space: {e}")
        raise typer.Exit(1)


@app.command("get")
def get_space(
    space_rid: str = typer.Argument(
        ..., help="Space Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Get detailed information about a specific space."""
    try:
        # Cache the RID for future completions
        cache_rid(space_rid)

        service = SpaceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Fetching space {space_rid}..."):
            space = service.get_space(space_rid)

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(space, output, "json")
            else:
                formatter.format_dict(space)
        elif format == "csv":
            if output:
                formatter.save_to_file([space], output, "csv")
            else:
                formatter.format_list([space])
        else:
            _format_space_table(space)

        if output:
            formatter.print_success(f"Space information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get space: {e}")
        raise typer.Exit(1)


@app.command("list")
def list_spaces(
    organization_rid: Optional[str] = typer.Option(
        None,
        "--organization-rid",
        "-org",
        help="Organization Resource Identifier to filter by",
        autocompletion=complete_rid,
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of items per page"
    ),
):
    """List spaces, optionally filtered by organization."""
    try:
        service = SpaceService(profile=profile)

        filter_desc = f" in organization {organization_rid}" if organization_rid else ""
        with SpinnerProgressTracker().track_spinner(f"Listing spaces{filter_desc}..."):
            spaces = service.list_spaces(
                organization_rid=organization_rid, page_size=page_size
            )

        if not spaces:
            formatter.print_info("No spaces found.")
            return

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(spaces, output, "json")
            else:
                formatter.format_list(spaces)
        elif format == "csv":
            if output:
                formatter.save_to_file(spaces, output, "csv")
            else:
                formatter.format_list(spaces)
        else:
            _format_spaces_table(spaces)

        if output:
            formatter.print_success(f"Spaces list saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list spaces: {e}")
        raise typer.Exit(1)


@app.command("update")
def update_space(
    space_rid: str = typer.Argument(
        ..., help="Space Resource Identifier", autocompletion=complete_rid
    ),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="New space display name"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="New space description"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
):
    """Update space information."""
    try:
        if not name and not description:
            formatter.print_error(
                "At least one field (--name or --description) must be provided"
            )
            raise typer.Exit(1)

        service = SpaceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Updating space {space_rid}..."):
            space = service.update_space(
                space_rid=space_rid,
                display_name=name,
                description=description,
            )

        formatter.print_success(f"Successfully updated space {space_rid}")

        # Format output
        if format == "json":
            formatter.format_dict(space)
        elif format == "csv":
            formatter.format_list([space])
        else:
            _format_space_table(space)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to update space: {e}")
        raise typer.Exit(1)


@app.command("delete")
def delete_space(
    space_rid: str = typer.Argument(
        ..., help="Space Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
):
    """Delete a space."""
    try:
        if not confirm:
            confirm_delete = typer.confirm(
                f"Are you sure you want to delete space {space_rid}?"
            )
            if not confirm_delete:
                formatter.print_info("Space deletion cancelled.")
                return

        service = SpaceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Deleting space {space_rid}..."):
            service.delete_space(space_rid)

        formatter.print_success(f"Successfully deleted space {space_rid}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to delete space: {e}")
        raise typer.Exit(1)


@app.command("batch-get")
def get_spaces_batch(
    space_rids: List[str] = typer.Argument(
        ..., help="Space Resource Identifiers (space-separated)"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Get multiple spaces in a single request (max 1000)."""
    try:
        service = SpaceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching {len(space_rids)} spaces..."
        ):
            spaces = service.get_spaces_batch(space_rids)

        # Cache RIDs for future completions
        for space in spaces:
            if space.get("rid"):
                cache_rid(space["rid"])

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(spaces, output, "json")
            else:
                formatter.format_list(spaces)
        elif format == "csv":
            if output:
                formatter.save_to_file(spaces, output, "csv")
            else:
                formatter.format_list(spaces)
        else:
            _format_spaces_table(spaces)

        if output:
            formatter.print_success(f"Spaces information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get spaces batch: {e}")
        raise typer.Exit(1)


@app.command("list-members")
def list_space_members(
    space_rid: str = typer.Argument(
        ..., help="Space Resource Identifier", autocompletion=complete_rid
    ),
    principal_type: Optional[str] = typer.Option(
        None,
        "--principal-type",
        "-t",
        help="Filter by principal type (User or Group)",
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of items per page"
    ),
):
    """Get all members (users/groups) of a space."""
    try:
        service = SpaceService(profile=profile)

        filter_desc = f" ({principal_type}s only)" if principal_type else ""
        with SpinnerProgressTracker().track_spinner(
            f"Listing members of space {space_rid}{filter_desc}..."
        ):
            members = service.get_space_members(
                space_rid=space_rid,
                principal_type=principal_type.title() if principal_type else None,
                page_size=page_size,
            )

        if not members:
            formatter.print_info(f"No members found in space {space_rid}.")
            return

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(members, output, "json")
            else:
                formatter.format_list(members)
        elif format == "csv":
            if output:
                formatter.save_to_file(members, output, "csv")
            else:
                formatter.format_list(members)
        else:
            _format_space_members_table(members)

        if output:
            formatter.print_success(f"Space members saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list space members: {e}")
        raise typer.Exit(1)


@app.command("add-member")
def add_space_member(
    space_rid: str = typer.Argument(
        ..., help="Space Resource Identifier", autocompletion=complete_rid
    ),
    principal_id: str = typer.Option(
        ..., "--principal-id", "-p", help="Principal (user/group) identifier"
    ),
    principal_type: str = typer.Option(
        ...,
        "--principal-type",
        "-t",
        help="Principal type (User or Group)",
    ),
    role_name: str = typer.Option(..., "--role", "-r", help="Role name to grant"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
):
    """Add a member to a space with a specific role."""
    try:
        service = SpaceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Adding {principal_type} '{principal_id}' to space {space_rid} with role '{role_name}'..."
        ):
            member = service.add_space_member(
                space_rid=space_rid,
                principal_id=principal_id,
                principal_type=principal_type.title(),
                role_name=role_name,
            )

        formatter.print_success(
            f"Successfully added {principal_type} '{principal_id}' to space with role '{role_name}'"
        )

        # Format output
        if format == "json":
            formatter.format_dict(member)
        elif format == "csv":
            formatter.format_list([member])
        else:
            _format_space_member_table(member)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to add space member: {e}")
        raise typer.Exit(1)


@app.command("remove-member")
def remove_space_member(
    space_rid: str = typer.Argument(
        ..., help="Space Resource Identifier", autocompletion=complete_rid
    ),
    principal_id: str = typer.Option(
        ..., "--principal-id", "-p", help="Principal (user/group) identifier"
    ),
    principal_type: str = typer.Option(
        ...,
        "--principal-type",
        "-t",
        help="Principal type (User or Group)",
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
):
    """Remove a member from a space."""
    try:
        if not confirm:
            confirm_remove = typer.confirm(
                f"Are you sure you want to remove {principal_type} '{principal_id}' from space {space_rid}?"
            )
            if not confirm_remove:
                formatter.print_info("Member removal cancelled.")
                return

        service = SpaceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Removing {principal_type} '{principal_id}' from space {space_rid}..."
        ):
            service.remove_space_member(
                space_rid=space_rid,
                principal_id=principal_id,
                principal_type=principal_type.title(),
            )

        formatter.print_success(
            f"Successfully removed {principal_type} '{principal_id}' from space"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to remove space member: {e}")
        raise typer.Exit(1)


def _format_space_table(space: dict):
    """Format space information as a table."""
    table = Table(title="Space Information", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("RID", space.get("rid", "N/A"))
    table.add_row("Display Name", space.get("display_name", "N/A"))
    table.add_row("Description", space.get("description", "N/A"))
    table.add_row("Organization RID", space.get("organization_rid", "N/A"))
    table.add_row("Root Folder RID", space.get("root_folder_rid", "N/A"))
    table.add_row("Created By", space.get("created_by", "N/A"))
    table.add_row("Created Time", space.get("created_time", "N/A"))
    table.add_row("Modified By", space.get("modified_by", "N/A"))
    table.add_row("Modified Time", space.get("modified_time", "N/A"))
    table.add_row("Trash Status", space.get("trash_status", "N/A"))

    console.print(table)


def _format_spaces_table(spaces: List[dict]):
    """Format multiple spaces as a table."""
    table = Table(title="Spaces", show_header=True, header_style="bold cyan")
    table.add_column("Display Name")
    table.add_column("RID")
    table.add_column("Organization RID")
    table.add_column("Created By")
    table.add_column("Created Time")

    for space in spaces:
        table.add_row(
            space.get("display_name", "N/A"),
            space.get("rid", "N/A"),
            space.get("organization_rid", "N/A"),
            space.get("created_by", "N/A"),
            space.get("created_time", "N/A"),
        )

    console.print(table)
    console.print(f"\nTotal: {len(spaces)} spaces")


def _format_space_member_table(member: dict):
    """Format space member information as a table."""
    table = Table(
        title="Space Member Information", show_header=True, header_style="bold cyan"
    )
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Space RID", member.get("space_rid", "N/A"))
    table.add_row("Principal ID", member.get("principal_id", "N/A"))
    table.add_row("Principal Type", member.get("principal_type", "N/A"))
    table.add_row("Role Name", member.get("role_name", "N/A"))
    table.add_row("Added By", member.get("added_by", "N/A"))
    table.add_row("Added Time", member.get("added_time", "N/A"))

    console.print(table)


def _format_space_members_table(members: List[dict]):
    """Format multiple space members as a table."""
    table = Table(title="Space Members", show_header=True, header_style="bold cyan")
    table.add_column("Principal Type")
    table.add_column("Principal ID")
    table.add_column("Role Name")
    table.add_column("Added By")
    table.add_column("Added Time")

    for member in members:
        table.add_row(
            member.get("principal_type", "N/A"),
            member.get("principal_id", "N/A"),
            member.get("role_name", "N/A"),
            member.get("added_by", "N/A"),
            member.get("added_time", "N/A"),
        )

    console.print(table)
    console.print(f"\nTotal: {len(members)} members")


@app.callback()
def main():
    """
    Space operations using foundry-platform-sdk.

    Manage spaces in the Foundry filesystem. Create, retrieve, update, and delete
    spaces, and manage space membership using Resource Identifiers (RIDs).

    Examples:
        # Create a space in an organization
        pltr space create "My Space" --organization-rid ri.compass.main.organization.xyz123

        # List all spaces
        pltr space list

        # List spaces in a specific organization
        pltr space list --organization-rid ri.compass.main.organization.xyz123

        # Get space information
        pltr space get ri.compass.main.space.abc456

        # Update space
        pltr space update ri.compass.main.space.abc456 --name "Updated Name"

        # List space members
        pltr space list-members ri.compass.main.space.abc456

        # Add a user to a space
        pltr space add-member ri.compass.main.space.abc456 \\
            --principal-id user123 --principal-type User --role viewer

        # Remove a user from a space
        pltr space remove-member ri.compass.main.space.abc456 \\
            --principal-id user123 --principal-type User

        # Delete space
        pltr space delete ri.compass.main.space.abc456
    """
    pass
