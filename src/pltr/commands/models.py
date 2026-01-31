"""
Models management commands for Foundry.
Provides commands for managing ML models and model versions in the registry.

Note: This is distinct from LanguageModels, which handles LLM chat/embeddings operations.
"""

import typer
from typing import Optional
from rich.console import Console

from ..services.models import ModelsService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..auth.base import ProfileNotFoundError, MissingCredentialsError
from ..utils.completion import (
    complete_rid,
    complete_profile,
    complete_output_format,
)

# Create main app and sub-apps
app = typer.Typer(help="Manage ML models and versions")
model_app = typer.Typer(help="Manage models")
version_app = typer.Typer(help="Manage model versions")

# Add sub-apps
app.add_typer(model_app, name="model")
app.add_typer(version_app, name="version")

console = Console()
formatter = OutputFormatter(console)


@model_app.command("create")
def create_model(
    name: str = typer.Argument(
        ...,
        help="Model name",
    ),
    folder: str = typer.Option(
        ...,
        "--folder",
        "-f",
        help="Parent folder RID (e.g., ri.compass.main.folder.xxx)",
        autocompletion=complete_rid,
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
    format: str = typer.Option(
        "table",
        "--format",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (writes to file instead of stdout)",
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Create a new ML model in the registry.

    Creates a model container that can hold multiple versions.

    Note: SDK does not support listing all models. Use the Foundry web UI
    or Ontology API to discover existing models.

    Examples:

        # Create a new model
        pltr models model create "fraud-detector" \\
            --folder ri.compass.main.folder.xxx

        # Create with JSON output
        pltr models model create "recommendation-engine" \\
            --folder ri.compass.main.folder.xxx \\
            --format json

        # Save to file
        pltr models model create "anomaly-detector" \\
            --folder ri.compass.main.folder.xxx \\
            --output model-info.json
    """
    try:
        with SpinnerProgressTracker().track_spinner("Creating model"):
            service = ModelsService(profile=profile)
            result = service.create_model(
                name=name,
                parent_folder_rid=folder,
                preview=preview,
            )

        console.print(f"[green]✓[/green] Created model: {result.get('name')}")
        console.print(f"  Model RID: {result.get('rid')}")

        formatter.format_output(result, format, output)

        if output:
            console.print(f"[green]✓[/green] Model information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@model_app.command("get")
def get_model(
    model_rid: str = typer.Argument(
        ...,
        help="Model RID (e.g., ri.foundry.main.model.xxx)",
        autocompletion=complete_rid,
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
    format: str = typer.Option(
        "table",
        "--format",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (writes to file instead of stdout)",
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Get information about a model.

    Retrieves model metadata including name, folder location, and other properties.

    Examples:

        # Get model details
        pltr models model get ri.foundry.main.model.abc123

        # Get as JSON
        pltr models model get ri.foundry.main.model.abc123 --format json

        # Save to file
        pltr models model get ri.foundry.main.model.abc123 \\
            --format json \\
            --output model-details.json
    """
    try:
        with SpinnerProgressTracker().track_spinner("Fetching model information"):
            service = ModelsService(profile=profile)
            result = service.get_model(
                model_rid=model_rid,
                preview=preview,
            )

        formatter.format_output(result, format, output)

        if output:
            console.print(f"[green]✓[/green] Model information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@version_app.command("get")
def get_version(
    model_rid: str = typer.Argument(
        ...,
        help="Model RID (e.g., ri.foundry.main.model.xxx)",
        autocompletion=complete_rid,
    ),
    version_rid: str = typer.Argument(
        ...,
        help="Version identifier (e.g., v1.0.0 or version RID)",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
    format: str = typer.Option(
        "table",
        "--format",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (writes to file instead of stdout)",
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Get information about a specific model version.

    Retrieves version metadata including creation time, schema, and other properties.

    Examples:

        # Get specific version
        pltr models version get ri.foundry.main.model.abc123 v1.0.0

        # Get as JSON
        pltr models version get ri.foundry.main.model.abc123 v1.0.0 \\
            --format json

        # Save to file
        pltr models version get ri.foundry.main.model.abc123 v1.0.0 \\
            --format json \\
            --output version-details.json
    """
    try:
        with SpinnerProgressTracker().track_spinner("Fetching version information"):
            service = ModelsService(profile=profile)
            result = service.get_model_version(
                model_rid=model_rid,
                model_version_rid=version_rid,
                preview=preview,
            )

        formatter.format_output(result, format, output)

        if output:
            console.print(f"[green]✓[/green] Version information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@version_app.command("list")
def list_versions(
    model_rid: str = typer.Argument(
        ...,
        help="Model RID (e.g., ri.foundry.main.model.xxx)",
        autocompletion=complete_rid,
    ),
    page_size: Optional[int] = typer.Option(
        None,
        "--page-size",
        help="Maximum number of versions to return per page",
    ),
    page_token: Optional[str] = typer.Option(
        None,
        "--page-token",
        help="Token for fetching next page of results",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
    format: str = typer.Option(
        "table",
        "--format",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (writes to file instead of stdout)",
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    List all versions of a model with pagination support.

    Returns a list of model versions with their metadata.

    Examples:

        # List all versions
        pltr models version list ri.foundry.main.model.abc123

        # List with pagination
        pltr models version list ri.foundry.main.model.abc123 \\
            --page-size 50

        # Get next page
        pltr models version list ri.foundry.main.model.abc123 \\
            --page-size 50 \\
            --page-token <token-from-previous-response>

        # Save to file
        pltr models version list ri.foundry.main.model.abc123 \\
            --format json \\
            --output versions.json
    """
    try:
        with SpinnerProgressTracker().track_spinner("Fetching model versions"):
            service = ModelsService(profile=profile)
            result = service.list_model_versions(
                model_rid=model_rid,
                page_size=page_size,
                page_token=page_token,
                preview=preview,
            )

        formatter.format_output(result, format, output)

        # Show pagination info if available (only when outputting to console, not file)
        if not output and result.get("nextPageToken"):
            console.print(
                f"[dim]Next page available. Use --page-token {result['nextPageToken']}[/dim]"
            )

        if output:
            console.print(f"[green]✓[/green] Version list saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
