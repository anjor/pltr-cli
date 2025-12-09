"""
AIP Agents management commands for Foundry.
Provides commands for agent inspection, session management, and version control.
"""

import typer
from typing import Optional
from rich.console import Console

from ..services.aip_agents import AipAgentsService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..utils.pagination import PaginationConfig
from ..auth.base import ProfileNotFoundError, MissingCredentialsError
from ..utils.completion import (
    complete_rid,
    complete_profile,
    complete_output_format,
    cache_rid,
)

# Create main app and sub-apps
app = typer.Typer(help="Manage AIP Agents, sessions, and versions")
sessions_app = typer.Typer(help="Manage agent conversation sessions")
versions_app = typer.Typer(help="Manage agent versions")

# Add sub-apps
app.add_typer(sessions_app, name="sessions")
app.add_typer(versions_app, name="versions")

console = Console()
formatter = OutputFormatter(console)


@app.command("get")
def get_agent(
    agent_rid: str = typer.Argument(
        ...,
        help="Agent Resource Identifier (e.g., ri.foundry.main.agent.abc123)",
        autocompletion=complete_rid,
    ),
    version: Optional[str] = typer.Option(
        None,
        "--version",
        "-v",
        help="Agent version to retrieve (e.g., '1.0'). Defaults to latest published.",
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
    """
    Get detailed information about an AIP Agent.

    Retrieves agent configuration including name, description, parameters,
    and version information.

    Examples:

        # Get latest published version of agent
        pltr aip-agents get ri.foundry.main.agent.abc123

        # Get specific version
        pltr aip-agents get ri.foundry.main.agent.abc123 --version 1.5

        # Output as JSON
        pltr aip-agents get ri.foundry.main.agent.abc123 --format json
    """
    try:
        cache_rid(agent_rid)

        service = AipAgentsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Fetching agent {agent_rid}..."):
            agent = service.get_agent(agent_rid, version=version)

        if output:
            formatter.save_to_file(agent, output, format)
            formatter.print_success(f"Agent information saved to {output}")
        else:
            formatter.display(agent, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get agent: {e}")
        raise typer.Exit(1)


@sessions_app.command("list")
def list_sessions(
    agent_rid: str = typer.Argument(
        ...,
        help="Agent Resource Identifier",
        autocompletion=complete_rid,
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
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of sessions per page"
    ),
    max_pages: Optional[int] = typer.Option(
        1, "--max-pages", help="Maximum number of pages to fetch (default: 1)"
    ),
    all: bool = typer.Option(
        False, "--all", help="Fetch all available sessions (overrides --max-pages)"
    ),
):
    """
    List conversation sessions for an agent.

    Only lists sessions created by this client (API). Sessions created
    in AIP Agent Studio will not appear.

    Examples:

        # List first page of sessions
        pltr aip-agents sessions list ri.foundry.main.agent.abc123

        # List all sessions
        pltr aip-agents sessions list ri.foundry.main.agent.abc123 --all

        # List first 3 pages with 50 sessions each
        pltr aip-agents sessions list ri.foundry.main.agent.abc123 \\
            --page-size 50 --max-pages 3
    """
    try:
        cache_rid(agent_rid)

        service = AipAgentsService(profile=profile)
        config = PaginationConfig(
            page_size=page_size,
            max_pages=max_pages,
            fetch_all=all,
        )

        with SpinnerProgressTracker().track_spinner(
            f"Fetching sessions for agent {agent_rid}..."
        ):
            result = service.list_sessions(agent_rid, config)

        if not result.data:
            console.print("[yellow]No sessions found for this agent[/yellow]")
            return

        if output:
            formatter.format_paginated_output(result, format, output)
            console.print(f"[green]Results saved to {output}[/green]")
        else:
            formatter.format_paginated_output(result, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list sessions: {e}")
        raise typer.Exit(1)


@sessions_app.command("get")
def get_session(
    agent_rid: str = typer.Argument(
        ...,
        help="Agent Resource Identifier",
        autocompletion=complete_rid,
    ),
    session_rid: str = typer.Argument(
        ...,
        help="Session Resource Identifier",
        autocompletion=complete_rid,
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
    """
    Get detailed information about a conversation session.

    Examples:

        # Get session details
        pltr aip-agents sessions get \\
            ri.foundry.main.agent.abc123 \\
            ri.foundry.main.session.xyz789

        # Export session details to JSON
        pltr aip-agents sessions get \\
            ri.foundry.main.agent.abc123 \\
            ri.foundry.main.session.xyz789 \\
            --format json --output session.json
    """
    try:
        cache_rid(agent_rid)
        cache_rid(session_rid)

        service = AipAgentsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching session {session_rid}..."
        ):
            session = service.get_session(agent_rid, session_rid)

        if output:
            formatter.save_to_file(session, output, format)
            formatter.print_success(f"Session information saved to {output}")
        else:
            formatter.display(session, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get session: {e}")
        raise typer.Exit(1)


@versions_app.command("list")
def list_versions(
    agent_rid: str = typer.Argument(
        ...,
        help="Agent Resource Identifier",
        autocompletion=complete_rid,
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
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of versions per page"
    ),
    max_pages: Optional[int] = typer.Option(
        1, "--max-pages", help="Maximum number of pages to fetch (default: 1)"
    ),
    all: bool = typer.Option(
        False, "--all", help="Fetch all available versions (overrides --max-pages)"
    ),
):
    """
    List all versions for an AIP Agent.

    Versions are returned in descending order (most recent first).

    Examples:

        # List first page of versions
        pltr aip-agents versions list ri.foundry.main.agent.abc123

        # List all versions
        pltr aip-agents versions list ri.foundry.main.agent.abc123 --all

        # Export all versions to CSV
        pltr aip-agents versions list ri.foundry.main.agent.abc123 \\
            --all --format csv --output versions.csv
    """
    try:
        cache_rid(agent_rid)

        service = AipAgentsService(profile=profile)
        config = PaginationConfig(
            page_size=page_size,
            max_pages=max_pages,
            fetch_all=all,
        )

        with SpinnerProgressTracker().track_spinner(
            f"Fetching versions for agent {agent_rid}..."
        ):
            result = service.list_versions(agent_rid, config)

        if not result.data:
            console.print("[yellow]No versions found for this agent[/yellow]")
            return

        if output:
            formatter.format_paginated_output(result, format, output)
            console.print(f"[green]Results saved to {output}[/green]")
        else:
            formatter.format_paginated_output(result, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list versions: {e}")
        raise typer.Exit(1)
