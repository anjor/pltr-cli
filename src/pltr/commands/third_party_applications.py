"""
Third-party applications management commands for Foundry.
"""

import typer
from typing import Optional
from rich.console import Console

from ..services.third_party_applications import ThirdPartyApplicationsService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..auth.base import ProfileNotFoundError, MissingCredentialsError
from ..utils.completion import (
    complete_rid,
    complete_profile,
    complete_output_format,
    cache_rid,
)

app = typer.Typer(help="Manage third-party applications in Foundry")
console = Console()
formatter = OutputFormatter(console)


@app.command("get")
def get_application(
    application_rid: str = typer.Argument(
        ...,
        help="Third-party application Resource Identifier",
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
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """Get detailed information about a third-party application."""
    try:
        # Cache the RID for future completions
        cache_rid(application_rid)

        service = ThirdPartyApplicationsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching third-party application {application_rid}..."
        ):
            application = service.get_application(application_rid, preview=preview)

        # Format output
        if output:
            formatter.save_to_file(application, output, format)
            formatter.print_success(f"Application information saved to {output}")
        else:
            formatter.display(application, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get third-party application: {e}")
        raise typer.Exit(1)
