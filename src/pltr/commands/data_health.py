"""
DataHealth management commands for Foundry.
Provides commands for managing data quality checks and reports.
"""

import typer
import json
from typing import Optional
from rich.console import Console

from ..services.data_health import DataHealthService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..auth.base import ProfileNotFoundError, MissingCredentialsError
from ..utils.completion import (
    complete_rid,
    complete_profile,
    complete_output_format,
)

# Create main app and sub-apps
app = typer.Typer(help="Manage data health checks and reports")
check_app = typer.Typer(help="Manage data health checks")
report_app = typer.Typer(help="View data health check reports")

# Add sub-apps
app.add_typer(check_app, name="check")
app.add_typer(report_app, name="report")

console = Console()
formatter = OutputFormatter(console)


@check_app.command("get")
def get_check(
    check_rid: str = typer.Argument(
        ...,
        help="Check RID (e.g., ri.data-health.main.check.xxx)",
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
    Get information about a data health check.

    Retrieves check details including configuration, status, and metadata.

    Examples:

        # Get check details
        pltr data-health check get ri.data-health.main.check.abc123

        # Get as JSON
        pltr data-health check get ri.data-health.main.check.abc123 --format json

        # Save to file
        pltr data-health check get ri.data-health.main.check.abc123 \\
            --format json \\
            --output check-details.json
    """
    try:
        with SpinnerProgressTracker().track_spinner("Fetching check information"):
            service = DataHealthService(profile=profile)
            result = service.get_check(
                check_rid=check_rid,
                preview=preview,
            )

        formatter.format_output(result, format, output)

        if output:
            console.print(f"[green]✓[/green] Check information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@check_app.command("create")
def create_check(
    config: str = typer.Argument(
        ...,
        help="Check configuration as JSON string or @filepath",
    ),
    intent: Optional[str] = typer.Option(
        None,
        "--intent",
        "-i",
        help="Note about why the check was set up",
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
    Create a new data health check.

    The config argument should be a JSON string or @filepath containing
    the check configuration. The configuration must include a 'type' field.

    Supported check types include:
    - buildStatus: Check dataset build status
    - buildDuration: Check dataset build duration
    - nullPercentage: Check percentage of null values in a column
    - columnType: Check column existence and type
    - numericColumnRange: Check numeric column value ranges
    - And more...

    Examples:

        # Create a build status check from JSON string
        pltr data-health check create '{
            "type": "buildStatus",
            "subject": {
                "datasetRid": "ri.foundry.main.dataset.xxx",
                "branchId": "master"
            },
            "statusCheckConfig": {"severity": "WARNING"}
        }' --intent "Monitor production builds"

        # Create from JSON file
        pltr data-health check create @check-config.json

        # Create with JSON output
        pltr data-health check create @config.json --format json
    """
    try:
        # Parse config from JSON string or file
        config_dict = _parse_json_config(config)

        with SpinnerProgressTracker().track_spinner("Creating check"):
            service = DataHealthService(profile=profile)
            result = service.create_check(
                config=config_dict,
                intent=intent,
                preview=preview,
            )

        console.print(f"[green]✓[/green] Created check: {result.get('rid')}")

        formatter.format_output(result, format, output)

        if output:
            console.print(f"[green]✓[/green] Check information saved to {output}")

    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON configuration: {e}[/red]")
        raise typer.Exit(1)
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@check_app.command("replace")
def replace_check(
    check_rid: str = typer.Argument(
        ...,
        help="Check RID (e.g., ri.data-health.main.check.xxx)",
        autocompletion=complete_rid,
    ),
    config: str = typer.Argument(
        ...,
        help="New check configuration as JSON string or @filepath",
    ),
    intent: Optional[str] = typer.Option(
        None,
        "--intent",
        "-i",
        help="Updated note about the check",
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
    Replace/update a data health check.

    Note: Changing the type of a check after creation is not supported.

    Examples:

        # Update check configuration
        pltr data-health check replace ri.data-health.main.check.abc123 \\
            '{"type": "buildStatus", ...}' \\
            --intent "Updated threshold"

        # Update from file
        pltr data-health check replace ri.data-health.main.check.abc123 \\
            @updated-config.json
    """
    try:
        # Parse config from JSON string or file
        config_dict = _parse_json_config(config)

        with SpinnerProgressTracker().track_spinner("Updating check"):
            service = DataHealthService(profile=profile)
            result = service.replace_check(
                check_rid=check_rid,
                config=config_dict,
                intent=intent,
                preview=preview,
            )

        console.print(f"[green]✓[/green] Updated check: {result.get('rid')}")

        formatter.format_output(result, format, output)

        if output:
            console.print(f"[green]✓[/green] Check information saved to {output}")

    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON configuration: {e}[/red]")
        raise typer.Exit(1)
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@check_app.command("delete")
def delete_check(
    check_rid: str = typer.Argument(
        ...,
        help="Check RID (e.g., ri.data-health.main.check.xxx)",
        autocompletion=complete_rid,
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Delete a data health check.

    Examples:

        # Delete with confirmation
        pltr data-health check delete ri.data-health.main.check.abc123

        # Delete without confirmation
        pltr data-health check delete ri.data-health.main.check.abc123 --force
    """
    # Handle confirmation outside try-except to avoid catching typer.Exit
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete check '{check_rid}'?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    try:
        with SpinnerProgressTracker().track_spinner("Deleting check"):
            service = DataHealthService(profile=profile)
            service.delete_check(
                check_rid=check_rid,
                preview=preview,
            )

        console.print(f"[green]✓[/green] Deleted check: {check_rid}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@report_app.command("get")
def get_report(
    check_report_rid: str = typer.Argument(
        ...,
        help="CheckReport RID (e.g., ri.data-health.main.check-report.xxx)",
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
    Get a data health check report.

    Retrieves the result of a check execution including status and details.

    Check result statuses:
    - PASSED: Check passed successfully
    - FAILED: Check failed
    - WARNING: Check completed with warnings
    - ERROR: Check encountered an error
    - NOT_APPLICABLE: Check was not applicable
    - NOT_COMPUTABLE: Check result could not be computed

    Examples:

        # Get report details
        pltr data-health report get ri.data-health.main.check-report.abc123

        # Get as JSON
        pltr data-health report get ri.data-health.main.check-report.abc123 \\
            --format json

        # Save to file
        pltr data-health report get ri.data-health.main.check-report.abc123 \\
            --format json \\
            --output report.json
    """
    try:
        with SpinnerProgressTracker().track_spinner("Fetching check report"):
            service = DataHealthService(profile=profile)
            result = service.get_check_report(
                check_report_rid=check_report_rid,
                preview=preview,
            )

        # Display status prominently
        status = result.get("result", {}).get("status", "UNKNOWN")
        status_colors = {
            "PASSED": "green",
            "FAILED": "red",
            "WARNING": "yellow",
            "ERROR": "red",
            "NOT_APPLICABLE": "dim",
            "NOT_COMPUTABLE": "dim",
        }
        color = status_colors.get(status, "white")
        console.print(f"Status: [{color}]{status}[/{color}]")

        message = result.get("result", {}).get("message")
        if message:
            console.print(f"Message: {message}")

        console.print()
        formatter.format_output(result, format, output)

        if output:
            console.print(f"[green]✓[/green] Report information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def _parse_json_config(config: str) -> dict:
    """
    Parse JSON configuration from a string or file.

    Args:
        config: JSON string or @filepath

    Returns:
        Parsed dictionary

    Raises:
        json.JSONDecodeError: If JSON is invalid
        FileNotFoundError: If file doesn't exist
    """
    if config.startswith("@"):
        # Load from file
        filepath = config[1:]
        with open(filepath, "r") as f:
            return json.load(f)
    else:
        # Parse JSON string
        return json.loads(config)
