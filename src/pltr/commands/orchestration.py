"""
Orchestration commands for managing builds, jobs, and schedules.
"""

import typer
import json
from typing import Optional
from rich.console import Console

from ..services.orchestration import OrchestrationService
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

# Create sub-apps for different orchestration components
builds_app = typer.Typer()
jobs_app = typer.Typer()
schedules_app = typer.Typer()

# ============================================================================
# Build Commands
# ============================================================================


@builds_app.command("get")
def get_build(
    build_rid: str = typer.Argument(
        ..., help="Build Resource Identifier", autocompletion=complete_rid
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
    """Get detailed information about a specific build."""
    try:
        cache_rid(build_rid)
        service = OrchestrationService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Fetching build {build_rid}..."):
            build = service.get_build(build_rid)

        formatter.format_build_detail(build, format, output)

        if output:
            formatter.print_success(f"Build information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get build: {e}")
        raise typer.Exit(1)


@builds_app.command("create")
def create_build(
    target: str = typer.Argument(..., help="Build target (JSON format)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    branch_name: Optional[str] = typer.Option(
        None, "--branch", help="Branch name for the build"
    ),
    force_build: bool = typer.Option(
        False, "--force", help="Force build even if no changes"
    ),
    abort_on_failure: bool = typer.Option(
        False, "--abort-on-failure", help="Abort on failure"
    ),
    notifications: bool = typer.Option(
        True, "--notifications/--no-notifications", help="Enable notifications"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
):
    """
    Create a new build with specified target datasets.

    The target parameter must be a JSON object with a 'type' field that specifies
    the build strategy. Three types are supported:

    \b
    1. Manual Build - Explicitly specify datasets to build:
       {
         "type": "manual",
         "targetRids": ["ri.foundry.main.dataset.abc123..."]
       }

    \b
    2. Upstream Build - Build target datasets and all their upstream dependencies:
       {
         "type": "upstream",
         "targetRids": ["ri.foundry.main.dataset.abc123..."],
         "ignoredRids": []
       }

    \b
    3. Connecting Build - Build datasets between input and target datasets:
       {
         "type": "connecting",
         "inputRids": ["ri.foundry.main.dataset.input123..."],
         "targetRids": ["ri.foundry.main.dataset.target123..."],
         "ignoredRids": []
       }

    Examples:

    \b
      # Build specific datasets manually
      pltr orchestration builds create '{"type": "manual", "targetRids": ["ri.foundry.main.dataset.abc123"]}' --branch master

    \b
      # Build dataset and all upstream dependencies
      pltr orchestration builds create '{"type": "upstream", "targetRids": ["ri.foundry.main.dataset.abc123"], "ignoredRids": []}' --branch master --force
    """
    try:
        service = OrchestrationService(profile=profile)

        # Parse target JSON
        try:
            target_dict = json.loads(target)
        except json.JSONDecodeError:
            formatter.print_error("Invalid JSON format for target")
            raise typer.Exit(1)

        with SpinnerProgressTracker().track_spinner("Creating build..."):
            build = service.create_build(
                target=target_dict,
                branch_name=branch_name,
                force_build=force_build,
                abort_on_failure=abort_on_failure,
                notifications_enabled=notifications,
            )

        formatter.print_success("Successfully created build")
        formatter.print_info(f"Build RID: {build.get('rid', 'unknown')}")
        formatter.format_build_detail(build, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create build: {e}")
        raise typer.Exit(1)


@builds_app.command("cancel")
def cancel_build(
    build_rid: str = typer.Argument(
        ..., help="Build Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
):
    """Cancel a build and all its unfinished jobs."""
    try:
        service = OrchestrationService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Cancelling build {build_rid}..."):
            service.cancel_build(build_rid)

        formatter.print_success(f"Successfully cancelled build {build_rid}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to cancel build: {e}")
        raise typer.Exit(1)


@builds_app.command("jobs")
def get_build_jobs(
    build_rid: str = typer.Argument(
        ..., help="Build Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of results per page"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """List all jobs in a build."""
    try:
        cache_rid(build_rid)
        service = OrchestrationService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching jobs for build {build_rid}..."
        ):
            response = service.get_build_jobs(build_rid, page_size=page_size)

        jobs = response.get("jobs", [])

        if not jobs:
            formatter.print_warning("No jobs found for this build")
            return

        formatter.format_jobs_list(jobs, format, output)

        if output:
            formatter.print_success(f"Jobs list saved to {output}")

        if response.get("next_page_token"):
            formatter.print_info(
                "More results available. Use pagination token to fetch next page."
            )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get build jobs: {e}")
        raise typer.Exit(1)


@builds_app.command("search")
def search_builds(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of results per page"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Search for builds."""
    try:
        service = OrchestrationService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Searching builds..."):
            response = service.search_builds(page_size=page_size)

        builds = response.get("builds", [])

        if not builds:
            formatter.print_warning("No builds found")
            return

        formatter.format_builds_list(builds, format, output)

        if output:
            formatter.print_success(f"Builds list saved to {output}")

        if response.get("next_page_token"):
            formatter.print_info(
                "More results available. Use pagination token to fetch next page."
            )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to search builds: {e}")
        raise typer.Exit(1)


# ============================================================================
# Job Commands
# ============================================================================


@jobs_app.command("get")
def get_job(
    job_rid: str = typer.Argument(
        ..., help="Job Resource Identifier", autocompletion=complete_rid
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
    """Get detailed information about a specific job."""
    try:
        cache_rid(job_rid)
        service = OrchestrationService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Fetching job {job_rid}..."):
            job = service.get_job(job_rid)

        formatter.format_job_detail(job, format, output)

        if output:
            formatter.print_success(f"Job information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get job: {e}")
        raise typer.Exit(1)


@jobs_app.command("get-batch")
def get_jobs_batch(
    job_rids: str = typer.Argument(
        ..., help="Comma-separated list of Job RIDs (max 500)"
    ),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Get multiple jobs in batch (max 500)."""
    try:
        # Parse job RIDs
        rids_list = [rid.strip() for rid in job_rids.split(",")]

        if len(rids_list) > 500:
            formatter.print_error("Maximum batch size is 500 jobs")
            raise typer.Exit(1)

        service = OrchestrationService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching {len(rids_list)} jobs..."
        ):
            response = service.get_jobs_batch(rids_list)

        jobs = response.get("jobs", [])

        if not jobs:
            formatter.print_warning("No jobs found")
            return

        formatter.format_jobs_list(jobs, format, output)

        if output:
            formatter.print_success(f"Jobs information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get jobs batch: {e}")
        raise typer.Exit(1)


# ============================================================================
# Schedule Commands
# ============================================================================


@schedules_app.command("get")
def get_schedule(
    schedule_rid: str = typer.Argument(
        ..., help="Schedule Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
    preview: bool = typer.Option(False, "--preview", help="Enable preview mode"),
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
    """Get detailed information about a specific schedule."""
    try:
        cache_rid(schedule_rid)
        service = OrchestrationService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching schedule {schedule_rid}..."
        ):
            schedule = service.get_schedule(schedule_rid, preview=preview)

        formatter.format_schedule_detail(schedule, format, output)

        if output:
            formatter.print_success(f"Schedule information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get schedule: {e}")
        raise typer.Exit(1)


@schedules_app.command("create")
def create_schedule(
    action: str = typer.Argument(..., help="Schedule action (JSON format)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    display_name: Optional[str] = typer.Option(
        None, "--name", help="Display name for the schedule"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="Schedule description"
    ),
    trigger: Optional[str] = typer.Option(
        None, "--trigger", help="Trigger configuration (JSON format)"
    ),
    preview: bool = typer.Option(False, "--preview", help="Enable preview mode"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
):
    """Create a new schedule."""
    try:
        service = OrchestrationService(profile=profile)

        # Parse action JSON
        try:
            action_dict = json.loads(action)
        except json.JSONDecodeError:
            formatter.print_error("Invalid JSON format for action")
            raise typer.Exit(1)

        # Parse trigger JSON if provided
        trigger_dict = None
        if trigger:
            try:
                trigger_dict = json.loads(trigger)
            except json.JSONDecodeError:
                formatter.print_error("Invalid JSON format for trigger")
                raise typer.Exit(1)

        with SpinnerProgressTracker().track_spinner("Creating schedule..."):
            schedule = service.create_schedule(
                action=action_dict,
                display_name=display_name,
                description=description,
                trigger=trigger_dict,
                preview=preview,
            )

        formatter.print_success("Successfully created schedule")
        formatter.print_info(f"Schedule RID: {schedule.get('rid', 'unknown')}")
        formatter.format_schedule_detail(schedule, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create schedule: {e}")
        raise typer.Exit(1)


@schedules_app.command("delete")
def delete_schedule(
    schedule_rid: str = typer.Argument(
        ..., help="Schedule Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a schedule."""
    try:
        if not confirm:
            typer.confirm(
                f"Are you sure you want to delete schedule {schedule_rid}?", abort=True
            )

        service = OrchestrationService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Deleting schedule {schedule_rid}..."
        ):
            service.delete_schedule(schedule_rid)

        formatter.print_success(f"Successfully deleted schedule {schedule_rid}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to delete schedule: {e}")
        raise typer.Exit(1)


@schedules_app.command("pause")
def pause_schedule(
    schedule_rid: str = typer.Argument(
        ..., help="Schedule Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
):
    """Pause a schedule."""
    try:
        service = OrchestrationService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Pausing schedule {schedule_rid}..."
        ):
            service.pause_schedule(schedule_rid)

        formatter.print_success(f"Successfully paused schedule {schedule_rid}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to pause schedule: {e}")
        raise typer.Exit(1)


@schedules_app.command("unpause")
def unpause_schedule(
    schedule_rid: str = typer.Argument(
        ..., help="Schedule Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
):
    """Unpause a schedule."""
    try:
        service = OrchestrationService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Unpausing schedule {schedule_rid}..."
        ):
            service.unpause_schedule(schedule_rid)

        formatter.print_success(f"Successfully unpaused schedule {schedule_rid}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to unpause schedule: {e}")
        raise typer.Exit(1)


@schedules_app.command("run")
def run_schedule(
    schedule_rid: str = typer.Argument(
        ..., help="Schedule Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
):
    """Execute a schedule immediately."""
    try:
        service = OrchestrationService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Running schedule {schedule_rid}..."
        ):
            service.run_schedule(schedule_rid)

        formatter.print_success(f"Successfully triggered schedule {schedule_rid}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to run schedule: {e}")
        raise typer.Exit(1)


@schedules_app.command("replace")
def replace_schedule(
    schedule_rid: str = typer.Argument(
        ..., help="Schedule Resource Identifier", autocompletion=complete_rid
    ),
    action: str = typer.Argument(..., help="Schedule action (JSON format)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    display_name: Optional[str] = typer.Option(
        None, "--name", help="Display name for the schedule"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="Schedule description"
    ),
    trigger: Optional[str] = typer.Option(
        None, "--trigger", help="Trigger configuration (JSON format)"
    ),
    preview: bool = typer.Option(False, "--preview", help="Enable preview mode"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
):
    """Replace an existing schedule."""
    try:
        service = OrchestrationService(profile=profile)

        # Parse action JSON
        try:
            action_dict = json.loads(action)
        except json.JSONDecodeError:
            formatter.print_error("Invalid JSON format for action")
            raise typer.Exit(1)

        # Parse trigger JSON if provided
        trigger_dict = None
        if trigger:
            try:
                trigger_dict = json.loads(trigger)
            except json.JSONDecodeError:
                formatter.print_error("Invalid JSON format for trigger")
                raise typer.Exit(1)

        with SpinnerProgressTracker().track_spinner(
            f"Replacing schedule {schedule_rid}..."
        ):
            schedule = service.replace_schedule(
                schedule_rid=schedule_rid,
                action=action_dict,
                display_name=display_name,
                description=description,
                trigger=trigger_dict,
                preview=preview,
            )

        formatter.print_success(f"Successfully replaced schedule {schedule_rid}")
        formatter.format_schedule_detail(schedule, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to replace schedule: {e}")
        raise typer.Exit(1)


# ============================================================================
# Main app setup
# ============================================================================

# Add sub-apps to main app
app.add_typer(builds_app, name="builds", help="Manage builds")
app.add_typer(jobs_app, name="jobs", help="Manage jobs")
app.add_typer(schedules_app, name="schedules", help="Manage schedules")


@app.callback()
def main():
    """
    Orchestration operations for managing builds, jobs, and schedules.

    This module provides commands to:
    - Create, monitor, and cancel builds
    - View job details and statuses
    - Create, manage, and execute schedules

    All operations require Resource Identifiers (RIDs) like:
    ri.orchestration.main.build.12345678-1234-1234-1234-123456789abc
    """
    pass
