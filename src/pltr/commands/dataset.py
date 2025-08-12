"""
Simplified dataset commands that work with foundry-platform-sdk v1.27.0.
"""

import typer
from typing import Optional
from rich.console import Console

from ..services.dataset import DatasetService
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
def get_dataset(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
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
    """Get detailed information about a specific dataset."""
    try:
        # Cache the RID for future completions
        cache_rid(dataset_rid)

        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching dataset {dataset_rid}..."
        ):
            dataset = service.get_dataset(dataset_rid)

        formatter.format_dataset_detail(dataset, format, output)

        if output:
            formatter.print_success(f"Dataset information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get dataset: {e}")
        raise typer.Exit(1)


# schema command removed - uses preview-only API that returns INVALID_ARGUMENT


@app.command("create")
def create_dataset(
    name: str = typer.Argument(..., help="Dataset name"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    parent_folder: Optional[str] = typer.Option(
        None, "--parent-folder", help="Parent folder RID"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
):
    """Create a new dataset."""
    try:
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Creating dataset '{name}'..."):
            dataset = service.create_dataset(name=name, parent_folder_rid=parent_folder)

        formatter.print_success(f"Successfully created dataset '{name}'")
        formatter.print_info(f"Dataset RID: {dataset.get('rid', 'unknown')}")

        # Show dataset details
        formatter.format_dataset_detail(dataset, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create dataset: {e}")
        raise typer.Exit(1)


@app.callback()
def main():
    """
    Dataset operations using foundry-platform-sdk.

    Note: This SDK version requires knowing dataset RIDs in advance.
    Find dataset RIDs in the Foundry web interface.

    Available commands work with Resource Identifiers (RIDs) like:
    ri.foundry.main.dataset.12345678-1234-1234-1234-123456789abc
    """
    pass
