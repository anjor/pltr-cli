"""
SQL commands for the pltr CLI.
Provides commands for executing SQL queries against Foundry datasets.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ..services.sql import SqlService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..utils.completion import (
    complete_profile,
    complete_output_format,
    complete_sql_query,
)

app = typer.Typer(name="sql", help="Execute SQL queries against Foundry datasets")


@app.command("execute")
def execute_query(
    query: str = typer.Argument(
        ..., help="SQL query to execute", autocompletion=complete_sql_query
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use", autocompletion=complete_profile
    ),
    output_format: str = typer.Option(
        "table",
        "--format",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
    timeout: int = typer.Option(300, "--timeout", help="Query timeout in seconds"),
    fallback_branches: Optional[str] = typer.Option(
        None, "--fallback-branches", help="Comma-separated list of fallback branch IDs"
    ),
) -> None:
    """Execute a SQL query and display results."""
    console = Console()
    formatter = OutputFormatter()

    try:
        # Parse fallback branches if provided
        fallback_branch_ids = (
            fallback_branches.split(",") if fallback_branches else None
        )

        # Create service and execute query
        service = SqlService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Executing SQL query..."):
            result = service.execute_query(
                query=query,
                fallback_branch_ids=fallback_branch_ids,
                timeout=timeout,
                format="table" if output_format in ["table", "csv"] else "json",
            )

        # Extract results
        query_results = result.get("results", {})

        # Display results
        if output_file:
            formatter.save_to_file(query_results, output_file, output_format)
            console.print(f"[green]Results saved to {output_file}[/green]")
        else:
            formatter.display(query_results, output_format)

        # Show query metadata
        if "query_id" in result:
            console.print(f"\n[dim]Query ID: {result['query_id']}[/dim]")

    except Exception as e:
        formatter.print_error(f"Failed to execute query: {e}")
        raise typer.Exit(1)


@app.command("submit")
def submit_query(
    query: str = typer.Argument(..., help="SQL query to submit"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    fallback_branches: Optional[str] = typer.Option(
        None, "--fallback-branches", help="Comma-separated list of fallback branch IDs"
    ),
) -> None:
    """Submit a SQL query without waiting for completion."""
    console = Console()
    formatter = OutputFormatter()

    try:
        # Parse fallback branches if provided
        fallback_branch_ids = (
            fallback_branches.split(",") if fallback_branches else None
        )

        # Create service and submit query
        service = SqlService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Submitting SQL query..."):
            result = service.submit_query(
                query=query, fallback_branch_ids=fallback_branch_ids
            )

        console.print("[green]Query submitted successfully[/green]")
        console.print(f"Query ID: [bold]{result.get('query_id', 'N/A')}[/bold]")
        console.print(f"Status: [yellow]{result.get('status', 'unknown')}[/yellow]")

        if result.get("status") == "succeeded":
            console.print("[green]Query completed immediately[/green]")
        elif result.get("status") == "running":
            console.print(
                "Use [bold]pltr sql status <query-id>[/bold] to check progress"
            )
            console.print(
                "Use [bold]pltr sql results <query-id>[/bold] to get results when completed"
            )

    except Exception as e:
        formatter.print_error(f"Failed to submit query: {e}")
        raise typer.Exit(1)


@app.command("status")
def get_query_status(
    query_id: str = typer.Argument(..., help="Query ID to check"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
) -> None:
    """Get the status of a submitted query."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = SqlService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Checking query status..."):
            result = service.get_query_status(query_id)

        console.print(f"Query ID: [bold]{query_id}[/bold]")

        status = result.get("status", "unknown")
        if status == "running":
            console.print(f"Status: [yellow]{status}[/yellow]")
            console.print("Query is still executing...")
        elif status == "succeeded":
            console.print(f"Status: [green]{status}[/green]")
            console.print("Use [bold]pltr sql results <query-id>[/bold] to get results")
        elif status == "failed":
            console.print(f"Status: [red]{status}[/red]")
            error_msg = result.get("error_message", "Unknown error")
            console.print(f"Error: {error_msg}")
        elif status == "canceled":
            console.print(f"Status: [red]{status}[/red]")
            console.print("Query was canceled")
        else:
            console.print(f"Status: [dim]{status}[/dim]")

    except Exception as e:
        formatter.print_error(f"Failed to get query status: {e}")
        raise typer.Exit(1)


@app.command("results")
def get_query_results(
    query_id: str = typer.Argument(..., help="Query ID to get results for"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: str = typer.Option(
        "table", "--format", help="Output format (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file"
    ),
) -> None:
    """Get the results of a completed query."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = SqlService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Retrieving query results..."):
            result = service.get_query_results(
                query_id,
                format="table" if output_format in ["table", "csv"] else "json",
            )

        # Display or save results
        if output_file:
            formatter.save_to_file(result, output_file, output_format)
            console.print(f"[green]Results saved to {output_file}[/green]")
        else:
            formatter.display(result, output_format)

        console.print(f"\n[dim]Query ID: {query_id}[/dim]")

    except Exception as e:
        formatter.print_error(f"Failed to get query results: {e}")
        raise typer.Exit(1)


@app.command("cancel")
def cancel_query(
    query_id: str = typer.Argument(..., help="Query ID to cancel"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
) -> None:
    """Cancel a running query."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = SqlService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Canceling query..."):
            result = service.cancel_query(query_id)

        console.print(f"Query ID: [bold]{query_id}[/bold]")

        status = result.get("status", "unknown")
        if status == "canceled":
            console.print(f"Status: [red]{status}[/red]")
            console.print("Query has been canceled successfully")
        else:
            console.print(f"Status: [yellow]{status}[/yellow]")
            console.print("Query may have already completed or was not running")

    except Exception as e:
        formatter.print_error(f"Failed to cancel query: {e}")
        raise typer.Exit(1)


@app.command("export")
def export_query_results(
    query: str = typer.Argument(..., help="SQL query to execute and export"),
    output_file: Path = typer.Argument(..., help="Output file path"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    output_format: Optional[str] = typer.Option(
        None,
        "--format",
        help="Output format (auto-detected from file extension if not specified)",
    ),
    timeout: int = typer.Option(300, "--timeout", help="Query timeout in seconds"),
    fallback_branches: Optional[str] = typer.Option(
        None, "--fallback-branches", help="Comma-separated list of fallback branch IDs"
    ),
) -> None:
    """Execute a SQL query and export results to a file."""
    console = Console()
    formatter = OutputFormatter()

    try:
        # Auto-detect format from file extension if not specified
        if output_format is None:
            ext = output_file.suffix.lower()
            if ext == ".json":
                output_format = "json"
            elif ext == ".csv":
                output_format = "csv"
            else:
                output_format = "table"  # Default

        # Parse fallback branches if provided
        fallback_branch_ids = (
            fallback_branches.split(",") if fallback_branches else None
        )

        # Create service and execute query
        service = SqlService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Executing SQL query..."):
            result = service.execute_query(
                query=query,
                fallback_branch_ids=fallback_branch_ids,
                timeout=timeout,
                format="table" if output_format in ["table", "csv"] else "json",
            )

        # Save results to file
        query_results = result.get("results", {})
        formatter.save_to_file(query_results, output_file, output_format)

        console.print(
            f"[green]Query executed and results saved to {output_file}[/green]"
        )

        # Show query metadata
        if "query_id" in result:
            console.print(f"[dim]Query ID: {result['query_id']}[/dim]")

    except Exception as e:
        formatter.print_error(f"Failed to export query results: {e}")
        raise typer.Exit(1)


@app.command("wait")
def wait_for_query(
    query_id: str = typer.Argument(..., help="Query ID to wait for"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use"
    ),
    timeout: int = typer.Option(300, "--timeout", help="Maximum wait time in seconds"),
    output_format: str = typer.Option(
        "table", "--format", help="Output format for results (table, json, csv)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", help="Save results to file when completed"
    ),
) -> None:
    """Wait for a query to complete and optionally display results."""
    console = Console()
    formatter = OutputFormatter()

    try:
        service = SqlService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Waiting for query to complete..."):
            status_result = service.wait_for_completion(query_id, timeout)

        console.print(f"Query ID: [bold]{query_id}[/bold]")
        console.print(
            f"Status: [green]{status_result.get('status', 'completed')}[/green]"
        )

        # Get and display results if requested
        if output_file or output_format != "table":
            with SpinnerProgressTracker().track_spinner("Retrieving results..."):
                result = service.get_query_results(
                    query_id,
                    format="table" if output_format in ["table", "csv"] else "json",
                )

            if output_file:
                formatter.save_to_file(result, output_file, output_format)
                console.print(f"[green]Results saved to {output_file}[/green]")
            else:
                formatter.display(result, output_format)
        else:
            console.print("Use [bold]pltr sql results <query-id>[/bold] to get results")

    except Exception as e:
        formatter.print_error(f"Failed while waiting for query: {e}")
        raise typer.Exit(1)
