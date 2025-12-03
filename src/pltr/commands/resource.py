"""
Resource management commands for Foundry filesystem.
"""

import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table

from ..services.resource import ResourceService
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


@app.command("get")
def get_resource(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
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
    """Get detailed information about a specific resource."""
    try:
        # Cache the RID for future completions
        cache_rid(resource_rid)

        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching resource {resource_rid}..."
        ):
            resource = service.get_resource(resource_rid)

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(resource, output, "json")
            else:
                formatter.format_dict(resource)
        elif format == "csv":
            if output:
                formatter.save_to_file([resource], output, "csv")
            else:
                formatter.format_list([resource])
        else:
            _format_resource_table(resource)

        if output:
            formatter.print_success(f"Resource information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get resource: {e}")
        raise typer.Exit(1)


@app.command("get-by-path")
def get_resource_by_path(
    path: str = typer.Argument(
        ...,
        help="Absolute path to the resource (e.g., '/My Organization/Project/Dataset')",
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
    """Get detailed information about a specific resource by its path."""
    try:
        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching resource at path '{path}'..."
        ):
            resource = service.get_resource_by_path(path)

        # Cache the RID for future completions
        if resource.get("rid"):
            cache_rid(resource["rid"])

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(resource, output, "json")
            else:
                formatter.format_dict(resource)
        elif format == "csv":
            if output:
                formatter.save_to_file([resource], output, "csv")
            else:
                formatter.format_list([resource])
        else:
            _format_resource_table(resource)

        if output:
            formatter.print_success(f"Resource information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get resource: {e}")
        raise typer.Exit(1)


@app.command("list")
def list_resources(
    folder_rid: Optional[str] = typer.Option(
        None,
        "--folder-rid",
        "-f",
        help="Folder Resource Identifier to filter by",
        autocompletion=complete_rid,
    ),
    resource_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Resource type to filter by (e.g., dataset, folder)"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-o",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(None, "--output", help="Output file path"),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of items per page"
    ),
):
    """List resources, optionally filtered by folder and type."""
    try:
        service = ResourceService(profile=profile)

        filter_parts = []
        if folder_rid:
            filter_parts.append(f"in folder {folder_rid}")
        if resource_type:
            filter_parts.append(f"of type {resource_type}")

        filter_desc = f" ({', '.join(filter_parts)})" if filter_parts else ""

        with SpinnerProgressTracker().track_spinner(
            f"Listing resources{filter_desc}..."
        ):
            resources = service.list_resources(
                folder_rid=folder_rid,
                resource_type=resource_type,
                page_size=page_size,
            )

        if not resources:
            formatter.print_info("No resources found.")
            return

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(resources, output, "json")
            else:
                formatter.format_list(resources)
        elif format == "csv":
            if output:
                formatter.save_to_file(resources, output, "csv")
            else:
                formatter.format_list(resources)
        else:
            _format_resources_table(resources)

        if output:
            formatter.print_success(f"Resources list saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list resources: {e}")
        raise typer.Exit(1)


@app.command("search")
def search_resources(
    query: str = typer.Argument(..., help="Search query string"),
    resource_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Resource type to filter by (e.g., dataset, folder)"
    ),
    folder_rid: Optional[str] = typer.Option(
        None,
        "--folder-rid",
        "-f",
        help="Folder to search within",
        autocompletion=complete_rid,
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-o",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(None, "--output", help="Output file path"),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of items per page"
    ),
):
    """Search for resources by query string."""
    try:
        service = ResourceService(profile=profile)

        filter_parts = []
        if resource_type:
            filter_parts.append(f"type={resource_type}")
        if folder_rid:
            filter_parts.append(f"folder={folder_rid}")

        filter_desc = f" ({', '.join(filter_parts)})" if filter_parts else ""

        with SpinnerProgressTracker().track_spinner(
            f"Searching resources for '{query}'{filter_desc}..."
        ):
            resources = service.search_resources(
                query=query,
                resource_type=resource_type,
                folder_rid=folder_rid,
                page_size=page_size,
            )

        if not resources:
            formatter.print_info(f"No resources found matching '{query}'.")
            return

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(resources, output, "json")
            else:
                formatter.format_list(resources)
        elif format == "csv":
            if output:
                formatter.save_to_file(resources, output, "csv")
            else:
                formatter.format_list(resources)
        else:
            _format_resources_table(resources)

        if output:
            formatter.print_success(f"Search results saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to search resources: {e}")
        raise typer.Exit(1)


@app.command("batch-get")
def get_resources_batch(
    resource_rids: List[str] = typer.Argument(
        ..., help="Resource Identifiers (space-separated)"
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
    """Get multiple resources in a single request (max 1000)."""
    try:
        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching {len(resource_rids)} resources..."
        ):
            resources = service.get_resources_batch(resource_rids)

        # Cache RIDs for future completions
        for resource in resources:
            if resource.get("rid"):
                cache_rid(resource["rid"])

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(resources, output, "json")
            else:
                formatter.format_list(resources)
        elif format == "csv":
            if output:
                formatter.save_to_file(resources, output, "csv")
            else:
                formatter.format_list(resources)
        else:
            _format_resources_table(resources)

        if output:
            formatter.print_success(f"Resources information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get resources batch: {e}")
        raise typer.Exit(1)


@app.command("get-metadata")
def get_resource_metadata(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
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
    """Get metadata for a specific resource."""
    try:
        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching metadata for {resource_rid}..."
        ):
            metadata = service.get_resource_metadata(resource_rid)

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(metadata, output, "json")
            else:
                formatter.format_dict(metadata)
        elif format == "csv":
            # Convert metadata dict to list for CSV output
            metadata_list = [{"key": k, "value": v} for k, v in metadata.items()]
            if output:
                formatter.save_to_file(metadata_list, output, "csv")
            else:
                formatter.format_list(metadata_list)
        else:
            _format_metadata_table(metadata)

        if output:
            formatter.print_success(f"Resource metadata saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get resource metadata: {e}")
        raise typer.Exit(1)


@app.command("move")
def move_resource(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
    ),
    target_folder_rid: str = typer.Option(
        ...,
        "--target-folder",
        "-t",
        help="Target folder Resource Identifier",
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
    """Move a resource to a different folder."""
    try:
        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Moving resource {resource_rid} to {target_folder_rid}..."
        ):
            resource = service.move_resource(resource_rid, target_folder_rid)

        formatter.print_success(f"Successfully moved resource to {target_folder_rid}")

        # Format output
        if format == "json":
            formatter.format_dict(resource)
        elif format == "csv":
            formatter.format_list([resource])
        else:
            _format_resource_table(resource)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to move resource: {e}")
        raise typer.Exit(1)


# ==================== Trash Operations ====================


@app.command("delete")
def delete_resource(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Move a resource to trash."""
    try:
        if not force:
            confirm = typer.confirm(
                f"Are you sure you want to move resource {resource_rid} to trash?"
            )
            if not confirm:
                formatter.print_info("Operation cancelled.")
                return

        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Moving resource {resource_rid} to trash..."
        ):
            service.delete_resource(resource_rid)

        formatter.print_success(f"Successfully moved resource {resource_rid} to trash")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to delete resource: {e}")
        raise typer.Exit(1)


@app.command("restore")
def restore_resource(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
):
    """Restore a resource from trash."""
    try:
        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Restoring resource {resource_rid} from trash..."
        ):
            service.restore_resource(resource_rid)

        formatter.print_success(
            f"Successfully restored resource {resource_rid} from trash"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to restore resource: {e}")
        raise typer.Exit(1)


@app.command("permanently-delete")
def permanently_delete_resource(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Permanently delete a resource from trash. This action is irreversible."""
    try:
        if not force:
            confirm = typer.confirm(
                f"Are you sure you want to PERMANENTLY delete resource {resource_rid}? "
                "This action cannot be undone!"
            )
            if not confirm:
                formatter.print_info("Operation cancelled.")
                return

        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Permanently deleting resource {resource_rid}..."
        ):
            service.permanently_delete_resource(resource_rid)

        formatter.print_success(
            f"Successfully permanently deleted resource {resource_rid}"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to permanently delete resource: {e}")
        raise typer.Exit(1)


# ==================== Markings Operations ====================


@app.command("add-markings")
def add_markings(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
    ),
    marking_ids: List[str] = typer.Option(
        ...,
        "--marking",
        "-m",
        help="Marking identifier(s) to add (can specify multiple)",
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
):
    """Add markings to a resource."""
    try:
        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Adding {len(marking_ids)} marking(s) to resource {resource_rid}..."
        ):
            service.add_markings(resource_rid, marking_ids)

        formatter.print_success(
            f"Successfully added {len(marking_ids)} marking(s) to resource {resource_rid}"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to add markings: {e}")
        raise typer.Exit(1)


@app.command("remove-markings")
def remove_markings(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
    ),
    marking_ids: List[str] = typer.Option(
        ...,
        "--marking",
        "-m",
        help="Marking identifier(s) to remove (can specify multiple)",
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
):
    """Remove markings from a resource."""
    try:
        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Removing {len(marking_ids)} marking(s) from resource {resource_rid}..."
        ):
            service.remove_markings(resource_rid, marking_ids)

        formatter.print_success(
            f"Successfully removed {len(marking_ids)} marking(s) from resource {resource_rid}"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to remove markings: {e}")
        raise typer.Exit(1)


@app.command("list-markings")
def list_markings(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
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
    """List markings directly applied to a resource."""
    try:
        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching markings for resource {resource_rid}..."
        ):
            markings = service.list_markings(resource_rid, page_size=page_size)

        if not markings:
            formatter.print_info("No markings found on this resource.")
            return

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(markings, output, "json")
            else:
                formatter.format_list(markings)
        elif format == "csv":
            if output:
                formatter.save_to_file(markings, output, "csv")
            else:
                formatter.format_list(markings)
        else:
            _format_markings_table(markings)

        if output:
            formatter.print_success(f"Markings list saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list markings: {e}")
        raise typer.Exit(1)


# ==================== Access & Batch Operations ====================


@app.command("access-requirements")
def get_access_requirements(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
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
    """Get access requirements (organizations and markings) for a resource."""
    try:
        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching access requirements for resource {resource_rid}..."
        ):
            requirements = service.get_access_requirements(resource_rid)

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(requirements, output, "json")
            else:
                formatter.format_dict(requirements)
        elif format == "csv":
            # Flatten for CSV output
            flat_data = []
            for org in requirements.get("organizations", []):
                flat_data.append({"type": "organization", **org})
            for marking in requirements.get("markings", []):
                flat_data.append({"type": "marking", **marking})
            if output:
                formatter.save_to_file(flat_data, output, "csv")
            else:
                formatter.format_list(flat_data)
        else:
            _format_access_requirements_table(requirements)

        if output:
            formatter.print_success(f"Access requirements saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get access requirements: {e}")
        raise typer.Exit(1)


@app.command("batch-get-by-path")
def get_resources_by_path_batch(
    paths: List[str] = typer.Argument(
        ..., help="Absolute paths to resources (space-separated)"
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
    """Get multiple resources by their absolute paths (max 1000)."""
    try:
        service = ResourceService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching {len(paths)} resources by path..."
        ):
            resources = service.get_resources_by_path_batch(paths)

        # Cache RIDs for future completions
        for resource in resources:
            if resource.get("rid"):
                cache_rid(resource["rid"])

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(resources, output, "json")
            else:
                formatter.format_list(resources)
        elif format == "csv":
            if output:
                formatter.save_to_file(resources, output, "csv")
            else:
                formatter.format_list(resources)
        else:
            _format_resources_table(resources)

        if output:
            formatter.print_success(f"Resources information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get resources by path batch: {e}")
        raise typer.Exit(1)


def _format_resource_table(resource: dict):
    """Format resource information as a table."""
    table = Table(
        title="Resource Information", show_header=True, header_style="bold cyan"
    )
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("RID", resource.get("rid", "N/A"))
    table.add_row("Display Name", resource.get("display_name", "N/A"))
    table.add_row("Name", resource.get("name", "N/A"))
    table.add_row("Description", resource.get("description", "N/A"))
    table.add_row("Type", resource.get("type", "N/A"))
    table.add_row("Path", resource.get("path", "N/A"))
    table.add_row("Folder RID", resource.get("folder_rid", "N/A"))
    table.add_row("Created By", resource.get("created_by", "N/A"))
    table.add_row("Created Time", resource.get("created_time", "N/A"))
    table.add_row("Modified By", resource.get("modified_by", "N/A"))
    table.add_row("Modified Time", resource.get("modified_time", "N/A"))
    table.add_row("Size (bytes)", resource.get("size_bytes", "N/A"))
    table.add_row("Trash Status", resource.get("trash_status", "N/A"))

    console.print(table)


def _format_resources_table(resources: List[dict]):
    """Format multiple resources as a table."""
    table = Table(title="Resources", show_header=True, header_style="bold cyan")
    table.add_column("Type")
    table.add_column("Display Name")
    table.add_column("RID")
    table.add_column("Folder RID")
    table.add_column("Created By")

    for resource in resources:
        table.add_row(
            resource.get("type", "N/A"),
            resource.get("display_name") or resource.get("name", "N/A"),
            resource.get("rid", "N/A"),
            resource.get("folder_rid", "N/A"),
            resource.get("created_by", "N/A"),
        )

    console.print(table)
    console.print(f"\nTotal: {len(resources)} resources")


def _format_metadata_table(metadata: dict):
    """Format metadata as a table."""
    table = Table(title="Resource Metadata", show_header=True, header_style="bold cyan")
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    for key, value in metadata.items():
        # Convert complex values to strings
        value_str = str(value) if value is not None else "N/A"
        table.add_row(key, value_str)

    console.print(table)


def _format_markings_table(markings: List[dict]):
    """Format markings as a table."""
    table = Table(title="Markings", show_header=True, header_style="bold cyan")
    table.add_column("Marking ID")
    table.add_column("Display Name")
    table.add_column("Category")
    table.add_column("Description")

    for marking in markings:
        table.add_row(
            marking.get("marking_id", "N/A"),
            marking.get("display_name", "N/A"),
            marking.get("category_display_name", "N/A"),
            marking.get("description", "N/A"),
        )

    console.print(table)
    console.print(f"\nTotal: {len(markings)} markings")


def _format_access_requirements_table(requirements: dict):
    """Format access requirements as tables."""
    organizations = requirements.get("organizations", [])
    markings = requirements.get("markings", [])

    if organizations:
        org_table = Table(
            title="Required Organizations", show_header=True, header_style="bold cyan"
        )
        org_table.add_column("Organization RID")
        org_table.add_column("Display Name")

        for org in organizations:
            org_table.add_row(
                org.get("organization_rid", "N/A"),
                org.get("display_name", "N/A"),
            )

        console.print(org_table)
        console.print(f"Total: {len(organizations)} organizations\n")
    else:
        console.print("[dim]No organization requirements[/dim]\n")

    if markings:
        marking_table = Table(
            title="Required Markings", show_header=True, header_style="bold cyan"
        )
        marking_table.add_column("Marking ID")
        marking_table.add_column("Display Name")
        marking_table.add_column("Category")

        for marking in markings:
            marking_table.add_row(
                marking.get("marking_id", "N/A"),
                marking.get("display_name", "N/A"),
                marking.get("category_display_name", "N/A"),
            )

        console.print(marking_table)
        console.print(f"Total: {len(markings)} markings")
    else:
        console.print("[dim]No marking requirements[/dim]")


@app.callback()
def main():
    """
    Resource operations using foundry-platform-sdk.

    Manage resources in the Foundry filesystem. Get resource information,
    search resources, manage metadata, and perform operations using Resource
    Identifiers (RIDs) or paths.

    Examples:
        # Get resource information by RID
        pltr resource get ri.compass.main.dataset.xyz123

        # Get resource information by path
        pltr resource get-by-path "/My Organization/Project/Dataset Name"

        # List all resources
        pltr resource list

        # List resources in a specific folder
        pltr resource list --folder-rid ri.compass.main.folder.abc456

        # List only datasets
        pltr resource list --type dataset

        # Search for resources
        pltr resource search "sales data"

        # Search for datasets containing "user"
        pltr resource search "user" --type dataset

        # Get resource metadata
        pltr resource get-metadata ri.compass.main.dataset.xyz123

        # Move resource to different folder
        pltr resource move ri.compass.main.dataset.xyz123 --target-folder ri.compass.main.folder.new456

        # Trash operations
        pltr resource delete ri.compass.main.dataset.xyz123
        pltr resource restore ri.compass.main.dataset.xyz123
        pltr resource permanently-delete ri.compass.main.dataset.xyz123

        # Markings operations
        pltr resource add-markings ri.compass.main.dataset.xyz123 -m marking-id-1 -m marking-id-2
        pltr resource remove-markings ri.compass.main.dataset.xyz123 -m marking-id-1
        pltr resource list-markings ri.compass.main.dataset.xyz123

        # Access requirements
        pltr resource access-requirements ri.compass.main.dataset.xyz123

        # Batch get by path
        pltr resource batch-get-by-path "/Org/Project/Dataset1" "/Org/Project/Dataset2"
    """
    pass
