"""
Audit log management commands for Foundry.
Provides access to audit logs for compliance and security monitoring.
"""

import typer
from typing import Optional
from rich.console import Console

from ..services.audit import AuditService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..auth.base import ProfileNotFoundError, MissingCredentialsError
from ..utils.completion import (
    complete_profile,
    complete_output_format,
)

app = typer.Typer(help="Audit log operations for compliance and security monitoring")
console = Console()
formatter = OutputFormatter(console)


@app.command("list")
def list_audit_logs(
    start_time: Optional[str] = typer.Option(
        None,
        "--start-time",
        "-s",
        help="Start time filter (ISO 8601 format, e.g., 2024-01-01T00:00:00Z)",
    ),
    end_time: Optional[str] = typer.Option(
        None,
        "--end-time",
        "-e",
        help="End time filter (ISO 8601 format, e.g., 2024-01-31T23:59:59Z)",
    ),
    user_id: Optional[str] = typer.Option(
        None,
        "--user-id",
        "-u",
        help="Filter by user ID",
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
    """List audit log entries with optional filters."""
    try:
        service = AuditService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching audit logs..."):
            logs = service.list_audit_logs(
                start_time=start_time,
                end_time=end_time,
                user_id=user_id,
                preview=preview,
            )

        if not logs:
            formatter.print_info("No audit logs found matching the criteria")
            return

        formatter.print_info(f"Found {len(logs)} audit log entries")

        if output:
            formatter.save_to_file(logs, output, format)
            formatter.print_success(f"Audit logs saved to {output}")
        else:
            formatter.display(logs, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list audit logs: {e}")
        raise typer.Exit(1)


@app.command("get")
def get_audit_log(
    log_id: str = typer.Argument(
        ...,
        help="Audit log identifier",
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
    """Get detailed information about a specific audit log entry."""
    try:
        service = AuditService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Fetching audit log {log_id}..."):
            log = service.get_audit_log(log_id, preview=preview)

        if output:
            formatter.save_to_file(log, output, format)
            formatter.print_success(f"Audit log saved to {output}")
        else:
            formatter.display(log, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get audit log: {e}")
        raise typer.Exit(1)


@app.command("export")
def export_audit_logs(
    start_time: str = typer.Argument(
        ...,
        help="Start time (ISO 8601 format, e.g., 2024-01-01T00:00:00Z)",
    ),
    end_time: str = typer.Argument(
        ...,
        help="End time (ISO 8601 format, e.g., 2024-01-31T23:59:59Z)",
    ),
    export_format: str = typer.Option(
        "json",
        "--export-format",
        help="Export format (json, csv)",
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
    """Export audit logs for a time range."""
    try:
        service = AuditService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Initiating audit log export from {start_time} to {end_time}..."
        ):
            result = service.export_audit_logs(
                start_time=start_time,
                end_time=end_time,
                format=export_format,
                preview=preview,
            )

        formatter.print_success("Audit log export initiated")

        if output:
            formatter.save_to_file(result, output, format)
            formatter.print_success(f"Export details saved to {output}")
        else:
            formatter.display(result, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to export audit logs: {e}")
        raise typer.Exit(1)


@app.command("export-status")
def get_export_status(
    export_id: str = typer.Argument(
        ...,
        help="Export job identifier",
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
    """Get the status of an audit log export job."""
    try:
        service = AuditService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Checking export status for {export_id}..."
        ):
            status = service.get_export_status(export_id, preview=preview)

        if output:
            formatter.save_to_file(status, output, format)
            formatter.print_success(f"Export status saved to {output}")
        else:
            formatter.display(status, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get export status: {e}")
        raise typer.Exit(1)
