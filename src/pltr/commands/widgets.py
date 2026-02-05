"""
Widget management commands for Foundry.
Provides access to widget sets, releases, repositories, and dev mode settings.

Note: All Widgets APIs are in Private Beta.
"""

from typing import Optional

import typer
from rich.console import Console

from ..auth.base import MissingCredentialsError, ProfileNotFoundError
from ..services.widgets import WidgetsService
from ..utils.completion import (
    complete_output_format,
    complete_profile,
    complete_rid,
    cache_rid,
)
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker

app = typer.Typer(help="Widget operations (Private Beta)")
dev_mode_app = typer.Typer(help="Dev mode settings management")
release_app = typer.Typer(help="Widget release management")
repository_app = typer.Typer(help="Widget repository management")

app.add_typer(dev_mode_app, name="dev-mode")
app.add_typer(release_app, name="release")
app.add_typer(repository_app, name="repository")

console = Console()
formatter = OutputFormatter(console)


# ===== Widget Set Commands =====


@app.command("get")
def get_widget_set(
    widget_set_rid: str = typer.Argument(
        ...,
        help="Widget set RID (e.g., ri.widgetregistry..widget-set.xxx)",
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
) -> None:
    """Get details of a widget set."""
    try:
        cache_rid(widget_set_rid)

        service = WidgetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching widget set..."):
            widget_set = service.get_widget_set(widget_set_rid)

        if output:
            formatter.save_to_file([widget_set], output, format)
            formatter.print_success(f"Widget set saved to {output}")
        else:
            formatter.display([widget_set], format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get widget set: {e}")
        raise typer.Exit(1)


# ===== Dev Mode Commands =====


@dev_mode_app.command("get")
def get_dev_mode_settings(
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
) -> None:
    """Get dev mode settings for the current user."""
    try:
        service = WidgetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching dev mode settings..."):
            settings = service.get_dev_mode_settings()

        if output:
            formatter.save_to_file([settings], output, format)
            formatter.print_success(f"Dev mode settings saved to {output}")
        else:
            formatter.display([settings], format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get dev mode settings: {e}")
        raise typer.Exit(1)


@dev_mode_app.command("enable")
def enable_dev_mode(
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
) -> None:
    """Enable dev mode for the current user."""
    try:
        service = WidgetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Enabling dev mode..."):
            settings = service.enable_dev_mode()

        formatter.print_success("Dev mode enabled")
        formatter.display([settings], format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to enable dev mode: {e}")
        raise typer.Exit(1)


@dev_mode_app.command("disable")
def disable_dev_mode(
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
) -> None:
    """Disable dev mode for the current user."""
    try:
        service = WidgetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Disabling dev mode..."):
            settings = service.disable_dev_mode()

        formatter.print_success("Dev mode disabled")
        formatter.display([settings], format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to disable dev mode: {e}")
        raise typer.Exit(1)


@dev_mode_app.command("pause")
def pause_dev_mode(
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
) -> None:
    """Pause dev mode for the current user."""
    try:
        service = WidgetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Pausing dev mode..."):
            settings = service.pause_dev_mode()

        formatter.print_success("Dev mode paused")
        formatter.display([settings], format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to pause dev mode: {e}")
        raise typer.Exit(1)


# ===== Release Commands =====


@release_app.command("list")
def list_releases(
    widget_set_rid: str = typer.Argument(
        ...,
        help="Widget set RID (e.g., ri.widgetregistry..widget-set.xxx)",
        autocompletion=complete_rid,
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
) -> None:
    """List releases for a widget set."""
    try:
        cache_rid(widget_set_rid)

        service = WidgetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching releases..."):
            releases = service.list_releases(
                widget_set_rid=widget_set_rid,
                page_size=page_size,
            )

        if not releases:
            formatter.print_info("No releases found for this widget set")
            return

        formatter.print_info(f"Found {len(releases)} releases")

        if output:
            formatter.save_to_file(releases, output, format)
            formatter.print_success(f"Releases saved to {output}")
        else:
            formatter.display(releases, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list releases: {e}")
        raise typer.Exit(1)


@release_app.command("get")
def get_release(
    widget_set_rid: str = typer.Argument(
        ...,
        help="Widget set RID (e.g., ri.widgetregistry..widget-set.xxx)",
        autocompletion=complete_rid,
    ),
    release_version: str = typer.Argument(
        ...,
        help="Release version (semver, e.g., 1.2.0)",
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
) -> None:
    """Get details of a specific release."""
    try:
        cache_rid(widget_set_rid)

        service = WidgetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching release {release_version}..."
        ):
            release = service.get_release(
                widget_set_rid=widget_set_rid,
                release_version=release_version,
            )

        if output:
            formatter.save_to_file([release], output, format)
            formatter.print_success(f"Release saved to {output}")
        else:
            formatter.display([release], format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get release: {e}")
        raise typer.Exit(1)


@release_app.command("delete")
def delete_release(
    widget_set_rid: str = typer.Argument(
        ...,
        help="Widget set RID (e.g., ri.widgetregistry..widget-set.xxx)",
        autocompletion=complete_rid,
    ),
    release_version: str = typer.Argument(
        ...,
        help="Release version to delete (semver, e.g., 1.2.0)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
) -> None:
    """Delete a specific release."""
    try:
        cache_rid(widget_set_rid)

        if not yes:
            confirm = typer.confirm(
                f"Are you sure you want to delete release {release_version}?"
            )
            if not confirm:
                formatter.print_info("Operation cancelled")
                raise typer.Exit(0)

        service = WidgetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Deleting release {release_version}..."
        ):
            service.delete_release(
                widget_set_rid=widget_set_rid,
                release_version=release_version,
            )

        formatter.print_success(f"Release {release_version} deleted successfully")

    except typer.Exit:
        raise  # Re-raise Exit exceptions (including cancellation)
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        formatter.print_error(f"Failed to delete release: {e}")
        raise typer.Exit(1) from e


# ===== Repository Commands =====


@repository_app.command("get")
def get_repository(
    repository_rid: str = typer.Argument(
        ...,
        help="Repository RID (e.g., ri.stemma.main.repository.xxx)",
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
) -> None:
    """Get details of a widget repository."""
    try:
        cache_rid(repository_rid)

        service = WidgetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching repository..."):
            repository = service.get_repository(repository_rid)

        if output:
            formatter.save_to_file([repository], output, format)
            formatter.print_success(f"Repository saved to {output}")
        else:
            formatter.display([repository], format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get repository: {e}")
        raise typer.Exit(1)
