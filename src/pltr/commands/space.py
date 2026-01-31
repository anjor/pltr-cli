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
    enrollment_rid: str = typer.Option(
        ...,
        "--enrollment-rid",
        "-e",
        help="Enrollment Resource Identifier",
        autocompletion=complete_rid,
    ),
    organizations: List[str] = typer.Option(
        ...,
        "--organization",
        "-org",
        help="Organization RID(s) (can specify multiple)",
    ),
    deletion_policy_organizations: List[str] = typer.Option(
        ...,
        "--deletion-policy-org",
        "-dpo",
        help="Organization RID(s) for deletion policy (can specify multiple)",
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
                enrollment_rid=enrollment_rid,
                organizations=organizations,
                deletion_policy_organizations=deletion_policy_organizations,
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


@app.callback()
def main():
    """
    Space operations using foundry-platform-sdk.

    Manage spaces in the Foundry filesystem. Create, retrieve, update, and delete
    spaces using Resource Identifiers (RIDs).

    Examples:
        # Create a space with required parameters
        pltr space create "My Space" \\
            --enrollment-rid ri.enrollment.main.enrollment.xyz123 \\
            --organization ri.compass.main.organization.abc456 \\
            --deletion-policy-org ri.compass.main.organization.abc456

        # List all spaces
        pltr space list

        # List spaces in a specific organization
        pltr space list --organization-rid ri.compass.main.organization.xyz123

        # Get space information
        pltr space get ri.compass.main.space.abc456

        # Update space
        pltr space update ri.compass.main.space.abc456 --name "Updated Name"

        # Delete space
        pltr space delete ri.compass.main.space.abc456
    """
    pass
