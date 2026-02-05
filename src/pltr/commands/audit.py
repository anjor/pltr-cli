"""
Audit log file management commands for Foundry.
Provides access to audit logs for compliance and security monitoring.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ..auth.base import MissingCredentialsError, ProfileNotFoundError
from ..services.audit import AuditService
from ..utils.completion import (
    complete_output_format,
    complete_profile,
    complete_rid,
    cache_rid,
)
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker

app = typer.Typer(help="Audit log operations for compliance and security monitoring")
console = Console()
formatter = OutputFormatter(console)


def parse_date(date_str: str) -> date:
    """Parse a date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise typer.BadParameter(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")


@app.command("list")
def list_log_files(
    organization_rid: str = typer.Argument(
        ...,
        help="Organization Resource Identifier (e.g., ri.multipass..organization.xxx)",
        autocompletion=complete_rid,
    ),
    start_date: str = typer.Argument(
        ...,
        help="Start date for audit events (YYYY-MM-DD format, required)",
    ),
    end_date: Optional[str] = typer.Option(
        None,
        "--end-date",
        "-e",
        help="End date for audit events (YYYY-MM-DD format, inclusive)",
    ),
    page_size: Optional[int] = typer.Option(
        None,
        "--page-size",
        help="Number of results per page",
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
):
    """List audit log files for an organization."""
    try:
        # Cache the RID for future completions
        cache_rid(organization_rid)

        # Parse dates
        start = parse_date(start_date)
        end = parse_date(end_date) if end_date else None

        service = AuditService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching audit log files..."):
            logs = service.list_log_files(
                organization_rid=organization_rid,
                start_date=start,
                end_date=end,
                page_size=page_size,
            )

        if not logs:
            formatter.print_info("No audit log files found for the specified criteria")
            return

        formatter.print_info(f"Found {len(logs)} audit log files")

        if output:
            formatter.save_to_file(logs, output, format)
            formatter.print_success(f"Audit log files saved to {output}")
        else:
            formatter.display(logs, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except typer.BadParameter:
        raise
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list audit log files: {e}")
        raise typer.Exit(1)


@app.command("get")
def get_log_file_content(
    organization_rid: str = typer.Argument(
        ...,
        help="Organization Resource Identifier (e.g., ri.multipass..organization.xxx)",
        autocompletion=complete_rid,
    ),
    log_file_id: str = typer.Argument(
        ...,
        help="Log file identifier (from list command)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (required for binary content)",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
):
    """Get the content of a specific audit log file."""
    try:
        # Cache the RID for future completions
        cache_rid(organization_rid)

        service = AuditService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching audit log file {log_file_id}..."
        ):
            content = service.get_log_file_content(
                organization_rid=organization_rid,
                log_file_id=log_file_id,
            )

        if output:
            # Write binary content to file
            Path(output).write_bytes(content)
            formatter.print_success(
                f"Audit log file saved to {output} ({len(content)} bytes)"
            )
        else:
            # Try to decode as text for display
            try:
                text_content = content.decode("utf-8")
                console.print(text_content)
            except UnicodeDecodeError:
                formatter.print_error(
                    "Log file contains binary content. Use --output to save to a file."
                )
                raise typer.Exit(1)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get audit log file: {e}")
        raise typer.Exit(1)
