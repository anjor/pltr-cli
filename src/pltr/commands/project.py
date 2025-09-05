"""
Project management commands for Foundry filesystem.
"""

import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table

from ..services.project import ProjectService
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
def create_project(
    name: str = typer.Argument(..., help="Project display name"),
    space_rid: str = typer.Option(
        ...,
        "--space-rid",
        "-s",
        help="Space Resource Identifier",
        autocompletion=complete_rid,
    ),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Project description"
    ),
    organization_rids: Optional[List[str]] = typer.Option(
        None,
        "--organization-rid",
        "-org",
        help="Organization RIDs (can be specified multiple times)",
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
    """Create a new project in Foundry."""
    try:
        service = ProjectService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Creating project '{name}'..."):
            project = service.create_project(
                display_name=name,
                space_rid=space_rid,
                description=description,
                organization_rids=organization_rids,
            )

        # Cache the RID for future completions
        if project.get("rid"):
            cache_rid(project["rid"])

        formatter.print_success(f"Successfully created project '{name}'")
        formatter.print_info(f"Project RID: {project.get('rid', 'unknown')}")

        # Format output
        if format == "json":
            formatter.format_dict(project)
        elif format == "csv":
            formatter.format_list([project])
        else:
            _format_project_table(project)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create project: {e}")
        raise typer.Exit(1)


@app.command("get")
def get_project(
    project_rid: str = typer.Argument(
        ..., help="Project Resource Identifier", autocompletion=complete_rid
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
    """Get detailed information about a specific project."""
    try:
        # Cache the RID for future completions
        cache_rid(project_rid)

        service = ProjectService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching project {project_rid}..."
        ):
            project = service.get_project(project_rid)

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(project, output, "json")
            else:
                formatter.format_dict(project)
        elif format == "csv":
            if output:
                formatter.save_to_file([project], output, "csv")
            else:
                formatter.format_list([project])
        else:
            _format_project_table(project)

        if output:
            formatter.print_success(f"Project information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get project: {e}")
        raise typer.Exit(1)


@app.command("list")
def list_projects(
    space_rid: Optional[str] = typer.Option(
        None,
        "--space-rid",
        "-s",
        help="Space Resource Identifier to filter by",
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
    """List projects, optionally filtered by space."""
    try:
        service = ProjectService(profile=profile)

        filter_desc = f" in space {space_rid}" if space_rid else ""
        with SpinnerProgressTracker().track_spinner(
            f"Listing projects{filter_desc}..."
        ):
            projects = service.list_projects(space_rid=space_rid, page_size=page_size)

        if not projects:
            formatter.print_info("No projects found.")
            return

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(projects, output, "json")
            else:
                formatter.format_list(projects)
        elif format == "csv":
            if output:
                formatter.save_to_file(projects, output, "csv")
            else:
                formatter.format_list(projects)
        else:
            _format_projects_table(projects)

        if output:
            formatter.print_success(f"Projects list saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list projects: {e}")
        raise typer.Exit(1)


@app.command("update")
def update_project(
    project_rid: str = typer.Argument(
        ..., help="Project Resource Identifier", autocompletion=complete_rid
    ),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="New project display name"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="New project description"
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
    """Update project information."""
    try:
        if not name and not description:
            formatter.print_error(
                "At least one field (--name or --description) must be provided"
            )
            raise typer.Exit(1)

        service = ProjectService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Updating project {project_rid}..."
        ):
            project = service.update_project(
                project_rid=project_rid,
                display_name=name,
                description=description,
            )

        formatter.print_success(f"Successfully updated project {project_rid}")

        # Format output
        if format == "json":
            formatter.format_dict(project)
        elif format == "csv":
            formatter.format_list([project])
        else:
            _format_project_table(project)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to update project: {e}")
        raise typer.Exit(1)


@app.command("delete")
def delete_project(
    project_rid: str = typer.Argument(
        ..., help="Project Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
):
    """Delete a project."""
    try:
        if not confirm:
            confirm_delete = typer.confirm(
                f"Are you sure you want to delete project {project_rid}?"
            )
            if not confirm_delete:
                formatter.print_info("Project deletion cancelled.")
                return

        service = ProjectService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Deleting project {project_rid}..."
        ):
            service.delete_project(project_rid)

        formatter.print_success(f"Successfully deleted project {project_rid}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to delete project: {e}")
        raise typer.Exit(1)


@app.command("batch-get")
def get_projects_batch(
    project_rids: List[str] = typer.Argument(
        ..., help="Project Resource Identifiers (space-separated)"
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
    """Get multiple projects in a single request (max 1000)."""
    try:
        service = ProjectService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching {len(project_rids)} projects..."
        ):
            projects = service.get_projects_batch(project_rids)

        # Cache RIDs for future completions
        for project in projects:
            if project.get("rid"):
                cache_rid(project["rid"])

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(projects, output, "json")
            else:
                formatter.format_list(projects)
        elif format == "csv":
            if output:
                formatter.save_to_file(projects, output, "csv")
            else:
                formatter.format_list(projects)
        else:
            _format_projects_table(projects)

        if output:
            formatter.print_success(f"Projects information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get projects batch: {e}")
        raise typer.Exit(1)


def _format_project_table(project: dict):
    """Format project information as a table."""
    table = Table(
        title="Project Information", show_header=True, header_style="bold cyan"
    )
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("RID", project.get("rid", "N/A"))
    table.add_row("Display Name", project.get("display_name", "N/A"))
    table.add_row("Description", project.get("description", "N/A"))
    table.add_row("Path", project.get("path", "N/A"))
    table.add_row("Space RID", project.get("space_rid", "N/A"))
    table.add_row("Created By", project.get("created_by", "N/A"))
    table.add_row("Created Time", project.get("created_time", "N/A"))
    table.add_row("Modified By", project.get("modified_by", "N/A"))
    table.add_row("Modified Time", project.get("modified_time", "N/A"))
    table.add_row("Trash Status", project.get("trash_status", "N/A"))

    console.print(table)


def _format_projects_table(projects: List[dict]):
    """Format multiple projects as a table."""
    table = Table(title="Projects", show_header=True, header_style="bold cyan")
    table.add_column("Display Name")
    table.add_column("RID")
    table.add_column("Space RID")
    table.add_column("Created By")
    table.add_column("Created Time")

    for project in projects:
        table.add_row(
            project.get("display_name", "N/A"),
            project.get("rid", "N/A"),
            project.get("space_rid", "N/A"),
            project.get("created_by", "N/A"),
            project.get("created_time", "N/A"),
        )

    console.print(table)
    console.print(f"\nTotal: {len(projects)} projects")


@app.callback()
def main():
    """
    Project operations using foundry-platform-sdk.

    Manage projects in the Foundry filesystem. Create, retrieve, update, and delete
    projects using Resource Identifiers (RIDs).

    Examples:
        # Create a project in a space
        pltr project create "My Project" --space-rid ri.compass.main.space.xyz123

        # List all projects
        pltr project list

        # List projects in a specific space
        pltr project list --space-rid ri.compass.main.space.xyz123

        # Get project information
        pltr project get ri.compass.main.project.abc456

        # Update project
        pltr project update ri.compass.main.project.abc456 --name "Updated Name"

        # Delete project
        pltr project delete ri.compass.main.project.abc456
    """
    pass
