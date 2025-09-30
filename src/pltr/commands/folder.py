"""
Folder management commands for Foundry filesystem.
"""

import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table

from ..services.folder import FolderService
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
def create_folder(
    name: str = typer.Argument(..., help="Folder display name"),
    parent_folder: str = typer.Option(
        "ri.compass.main.folder.0",
        "--parent-folder",
        "-p",
        help="Parent folder RID (default: root folder)",
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
):
    """Create a new folder in Foundry."""
    try:
        service = FolderService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Creating folder '{name}'..."):
            folder = service.create_folder(
                display_name=name, parent_folder_rid=parent_folder
            )

        # Cache the RID for future completions
        if folder.get("rid"):
            cache_rid(folder["rid"])

        formatter.print_success(f"Successfully created folder '{name}'")
        formatter.print_info(f"Folder RID: {folder.get('rid', 'unknown')}")

        # Format output
        if format == "json":
            formatter.format_dict(folder)
        elif format == "csv":
            formatter.format_list([folder])
        else:
            _format_folder_table(folder)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create folder: {e}")
        raise typer.Exit(1)


@app.command("get")
def get_folder(
    folder_rid: str = typer.Argument(
        ..., help="Folder Resource Identifier", autocompletion=complete_rid
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
    """Get detailed information about a specific folder."""
    try:
        # Cache the RID for future completions
        cache_rid(folder_rid)

        service = FolderService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Fetching folder {folder_rid}..."):
            folder = service.get_folder(folder_rid)

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(folder, output, "json")
            else:
                formatter.format_dict(folder)
        elif format == "csv":
            if output:
                formatter.save_to_file([folder], output, "csv")
            else:
                formatter.format_list([folder])
        else:
            _format_folder_table(folder)

        if output:
            formatter.print_success(f"Folder information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get folder: {e}")
        raise typer.Exit(1)


@app.command("list")
def list_children(
    folder_rid: str = typer.Argument(
        ...,
        help="Folder Resource Identifier (use 'ri.compass.main.folder.0' for root)",
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
    """List all child resources of a folder."""
    try:
        # Cache the RID for future completions
        cache_rid(folder_rid)

        service = FolderService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Listing children of folder {folder_rid}..."
        ):
            children = service.list_children(folder_rid, page_size=page_size)

        if not children:
            formatter.print_info("No children found in this folder.")
            return

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(children, output, "json")
            else:
                formatter.format_list(children)
        elif format == "csv":
            if output:
                formatter.save_to_file(children, output, "csv")
            else:
                formatter.format_list(children)
        else:
            _format_children_table(children)

        if output:
            formatter.print_success(f"Folder children saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list folder children: {e}")
        raise typer.Exit(1)


@app.command("batch-get")
def get_folders_batch(
    folder_rids: List[str] = typer.Argument(
        ..., help="Folder Resource Identifiers (space-separated)"
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
    """Get multiple folders in a single request (max 1000)."""
    try:
        service = FolderService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching {len(folder_rids)} folders..."
        ):
            folders = service.get_folders_batch(folder_rids)

        # Cache RIDs for future completions
        for folder in folders:
            if folder.get("rid"):
                cache_rid(folder["rid"])

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(folders, output, "json")
            else:
                formatter.format_list(folders)
        elif format == "csv":
            if output:
                formatter.save_to_file(folders, output, "csv")
            else:
                formatter.format_list(folders)
        else:
            _format_folders_batch_table(folders)

        if output:
            formatter.print_success(f"Folders information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get folders batch: {e}")
        raise typer.Exit(1)


def _format_folder_table(folder: dict):
    """Format folder information as a table."""
    table = Table(
        title="Folder Information", show_header=True, header_style="bold cyan"
    )
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("RID", folder.get("rid", "N/A"))
    table.add_row("Display Name", folder.get("display_name", "N/A"))
    table.add_row("Description", folder.get("description", "N/A"))
    table.add_row("Parent Folder", folder.get("parent_folder_rid", "N/A"))
    table.add_row("Created", folder.get("created", "N/A"))
    table.add_row("Modified", folder.get("modified", "N/A"))

    console.print(table)


def _format_children_table(children: List[dict]):
    """Format folder children as a table."""
    table = Table(title="Folder Children", show_header=True, header_style="bold cyan")
    table.add_column("Type", style="cyan")
    table.add_column("Display Name")
    table.add_column("RID", no_wrap=True)

    for child in children:
        table.add_row(
            child.get("type", "unknown"),
            child.get("display_name", child.get("name", "N/A")),
            child.get("rid", "N/A"),
        )

    console.print(table)
    console.print(f"\nTotal: {len(children)} items")


def _format_folders_batch_table(folders: List[dict]):
    """Format multiple folders as a table."""
    table = Table(title="Folders", show_header=True, header_style="bold cyan")
    table.add_column("Display Name")
    table.add_column("RID", no_wrap=True)
    table.add_column("Parent Folder", no_wrap=True)
    table.add_column("Description")

    for folder in folders:
        table.add_row(
            folder.get("display_name", "N/A"),
            folder.get("rid", "N/A"),
            folder.get("parent_folder_rid", "N/A"),
            folder.get("description", "N/A") or "",
        )

    console.print(table)
    console.print(f"\nTotal: {len(folders)} folders")


@app.callback()
def main():
    """
    Folder operations using foundry-platform-sdk.

    Manage folders in the Foundry filesystem. Create, retrieve, and list
    folder contents using Resource Identifiers (RIDs).

    The root folder RID is: ri.compass.main.folder.0

    Examples:
        # Create a folder in root
        pltr folder create "My Folder"

        # Create a folder in a specific parent
        pltr folder create "Sub Folder" --parent-folder ri.compass.main.folder.xyz123

        # List root folder contents
        pltr folder list ri.compass.main.folder.0

        # Get folder information
        pltr folder get ri.compass.main.folder.xyz123
    """
    pass
