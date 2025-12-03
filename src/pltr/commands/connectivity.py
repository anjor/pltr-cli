"""
Connectivity management commands for Foundry connections and imports.
"""

import typer
import json
from typing import Optional
from rich.console import Console

from ..services.connectivity import ConnectivityService
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
connection_app = typer.Typer()
import_app = typer.Typer()
console = Console()
formatter = OutputFormatter(console)

# Add sub-apps
app.add_typer(connection_app, name="connection", help="Manage connections")
app.add_typer(import_app, name="import", help="Manage data imports")


@connection_app.command("list")
def list_connections(
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
    """List available connections."""
    try:
        with SpinnerProgressTracker().track_spinner("Fetching connections..."):
            service = ConnectivityService(profile=profile)
            connections = service.list_connections()

        if not connections:
            console.print("[yellow]No connections found[/yellow]")
            return

        formatter.format_output(connections, format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error listing connections: {e}[/red]")
        raise typer.Exit(1)


@connection_app.command("get")
def get_connection(
    connection_rid: str = typer.Argument(
        ..., help="Connection Resource Identifier", autocompletion=complete_rid
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
    """Get detailed information about a specific connection."""
    try:
        cache_rid(connection_rid)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching connection {connection_rid}..."
        ):
            service = ConnectivityService(profile=profile)
            connection = service.get_connection(connection_rid)

        formatter.format_output([connection], format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error getting connection: {e}[/red]")
        raise typer.Exit(1)


@connection_app.command("create")
def create_connection(
    display_name: str = typer.Argument(..., help="Display name for the connection"),
    parent_folder_rid: str = typer.Argument(
        ..., help="Parent folder Resource Identifier", autocompletion=complete_rid
    ),
    configuration: str = typer.Argument(
        ..., help="Connection configuration in JSON format"
    ),
    worker: str = typer.Argument(..., help="Worker configuration in JSON format"),
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
    """Create a new connection."""
    try:
        cache_rid(parent_folder_rid)

        # Parse configuration JSON
        try:
            config_dict = json.loads(configuration)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON configuration: {e}[/red]")
            raise typer.Exit(1)

        # Parse worker JSON
        try:
            worker_dict = json.loads(worker)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON worker configuration: {e}[/red]")
            raise typer.Exit(1)

        service = ConnectivityService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Creating connection..."):
            connection = service.create_connection(
                display_name=display_name,
                parent_folder_rid=parent_folder_rid,
                configuration=config_dict,
                worker=worker_dict,
            )

        cache_rid(connection.get("rid", ""))
        console.print(f"[green]Connection created: {connection.get('rid')}[/green]")
        formatter.format_output([connection], format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error creating connection: {e}[/red]")
        raise typer.Exit(1)


@connection_app.command("get-config")
def get_connection_configuration(
    connection_rid: str = typer.Argument(
        ..., help="Connection Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Get connection configuration."""
    try:
        cache_rid(connection_rid)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching configuration for {connection_rid}..."
        ):
            service = ConnectivityService(profile=profile)
            config = service.get_connection_configuration(connection_rid)

        formatter.format_output([config], format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error getting connection configuration: {e}[/red]")
        raise typer.Exit(1)


@connection_app.command("update-secrets")
def update_connection_secrets(
    connection_rid: str = typer.Argument(
        ..., help="Connection Resource Identifier", autocompletion=complete_rid
    ),
    secrets: str = typer.Argument(
        ..., help="Secrets in JSON format (mapping secret names to values)"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
):
    """Update connection secrets."""
    try:
        cache_rid(connection_rid)

        # Parse secrets JSON
        try:
            secrets_dict = json.loads(secrets)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON secrets: {e}[/red]")
            raise typer.Exit(1)

        service = ConnectivityService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Updating secrets..."):
            service.update_secrets(connection_rid, secrets_dict)

        console.print(
            f"[green]Secrets updated for connection: {connection_rid}[/green]"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error updating secrets: {e}[/red]")
        raise typer.Exit(1)


@connection_app.command("update-export-settings")
def update_export_settings(
    connection_rid: str = typer.Argument(
        ..., help="Connection Resource Identifier", autocompletion=complete_rid
    ),
    settings: str = typer.Argument(..., help="Export settings in JSON format"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
):
    """Update connection export settings."""
    try:
        cache_rid(connection_rid)

        # Parse settings JSON
        try:
            settings_dict = json.loads(settings)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON settings: {e}[/red]")
            raise typer.Exit(1)

        service = ConnectivityService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Updating export settings..."):
            service.update_export_settings(connection_rid, settings_dict)

        console.print(
            f"[green]Export settings updated for connection: {connection_rid}[/green]"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error updating export settings: {e}[/red]")
        raise typer.Exit(1)


@connection_app.command("upload-jdbc-drivers")
def upload_jdbc_drivers(
    connection_rid: str = typer.Argument(
        ..., help="Connection Resource Identifier", autocompletion=complete_rid
    ),
    driver_files: list[str] = typer.Argument(
        ..., help="Path(s) to JAR file(s) to upload"
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
    """Upload custom JDBC drivers to a connection."""
    try:
        cache_rid(connection_rid)

        service = ConnectivityService(profile=profile)
        results = []

        for driver_file in driver_files:
            with SpinnerProgressTracker().track_spinner(f"Uploading {driver_file}..."):
                result = service.upload_custom_jdbc_drivers(connection_rid, driver_file)
                results.append(result)
            console.print(f"[green]Uploaded: {driver_file}[/green]")

        formatter.format_output(results, format, output)

    except FileNotFoundError as e:
        console.print(f"[red]File not found: {e}[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Invalid file: {e}[/red]")
        raise typer.Exit(1)
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error uploading JDBC drivers: {e}[/red]")
        raise typer.Exit(1)


@import_app.command("file")
def import_file(
    connection_rid: str = typer.Argument(
        ..., help="Connection Resource Identifier", autocompletion=complete_rid
    ),
    source_path: str = typer.Argument(..., help="Source file path in the connection"),
    target_dataset_rid: str = typer.Argument(
        ..., help="Target dataset RID", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
    config: Optional[str] = typer.Option(
        None, "--config", "-c", help="Import configuration in JSON format"
    ),
    execute: bool = typer.Option(
        False, "--execute", help="Execute the import immediately after creation"
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
    """Create and optionally execute a file import via connection."""
    try:
        cache_rid(connection_rid)
        cache_rid(target_dataset_rid)

        # Parse import configuration if provided
        import_config = None
        if config:
            try:
                import_config = json.loads(config)
            except json.JSONDecodeError as e:
                console.print(f"[red]Invalid JSON configuration: {e}[/red]")
                raise typer.Exit(1)

        service = ConnectivityService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Creating file import..."):
            file_import = service.create_file_import(
                connection_rid=connection_rid,
                source_path=source_path,
                target_dataset_rid=target_dataset_rid,
                import_config=import_config,
            )

        result_data = [file_import]

        # Execute import if requested
        if execute:
            import_rid = file_import.get("rid")
            if import_rid:
                with SpinnerProgressTracker().track_spinner("Executing file import..."):
                    execution_result = service.execute_file_import(import_rid)
                result_data.append({"execution": execution_result})
                console.print(f"[green]File import executed: {import_rid}[/green]")
            else:
                console.print(
                    "[yellow]Warning: Could not execute - missing import RID[/yellow]"
                )

        formatter.format_output(result_data, format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error creating file import: {e}[/red]")
        raise typer.Exit(1)


@import_app.command("table")
def import_table(
    connection_rid: str = typer.Argument(
        ..., help="Connection Resource Identifier", autocompletion=complete_rid
    ),
    source_table: str = typer.Argument(..., help="Source table name in the connection"),
    target_dataset_rid: str = typer.Argument(
        ..., help="Target dataset RID", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
    config: Optional[str] = typer.Option(
        None, "--config", "-c", help="Import configuration in JSON format"
    ),
    execute: bool = typer.Option(
        False, "--execute", help="Execute the import immediately after creation"
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
    """Create and optionally execute a table import via connection."""
    try:
        cache_rid(connection_rid)
        cache_rid(target_dataset_rid)

        # Parse import configuration if provided
        import_config = None
        if config:
            try:
                import_config = json.loads(config)
            except json.JSONDecodeError as e:
                console.print(f"[red]Invalid JSON configuration: {e}[/red]")
                raise typer.Exit(1)

        service = ConnectivityService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Creating table import..."):
            table_import = service.create_table_import(
                connection_rid=connection_rid,
                source_table=source_table,
                target_dataset_rid=target_dataset_rid,
                import_config=import_config,
            )

        result_data = [table_import]

        # Execute import if requested
        if execute:
            import_rid = table_import.get("rid")
            if import_rid:
                with SpinnerProgressTracker().track_spinner(
                    "Executing table import..."
                ):
                    execution_result = service.execute_table_import(import_rid)
                result_data.append({"execution": execution_result})
                console.print(f"[green]Table import executed: {import_rid}[/green]")
            else:
                console.print(
                    "[yellow]Warning: Could not execute - missing import RID[/yellow]"
                )

        formatter.format_output(result_data, format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error creating table import: {e}[/red]")
        raise typer.Exit(1)


@import_app.command("list-file")
def list_file_imports(
    connection_rid: Optional[str] = typer.Option(
        None,
        "--connection",
        "-c",
        help="Filter by connection RID",
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
    """List file imports, optionally filtered by connection."""
    try:
        if connection_rid:
            cache_rid(connection_rid)

        with SpinnerProgressTracker().track_spinner("Fetching file imports..."):
            service = ConnectivityService(profile=profile)
            imports = service.list_file_imports(connection_rid=connection_rid)

        if not imports:
            console.print("[yellow]No file imports found[/yellow]")
            return

        formatter.format_output(imports, format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error listing file imports: {e}[/red]")
        raise typer.Exit(1)


@import_app.command("list-table")
def list_table_imports(
    connection_rid: Optional[str] = typer.Option(
        None,
        "--connection",
        "-c",
        help="Filter by connection RID",
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
    """List table imports, optionally filtered by connection."""
    try:
        if connection_rid:
            cache_rid(connection_rid)

        with SpinnerProgressTracker().track_spinner("Fetching table imports..."):
            service = ConnectivityService(profile=profile)
            imports = service.list_table_imports(connection_rid=connection_rid)

        if not imports:
            console.print("[yellow]No table imports found[/yellow]")
            return

        formatter.format_output(imports, format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error listing table imports: {e}[/red]")
        raise typer.Exit(1)


@import_app.command("get-file")
def get_file_import(
    import_rid: str = typer.Argument(
        ..., help="File import Resource Identifier", autocompletion=complete_rid
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
    """Get detailed information about a specific file import."""
    try:
        cache_rid(import_rid)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching file import {import_rid}..."
        ):
            service = ConnectivityService(profile=profile)
            file_import = service.get_file_import(import_rid)

        formatter.format_output([file_import], format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error getting file import: {e}[/red]")
        raise typer.Exit(1)


@import_app.command("get-table")
def get_table_import(
    import_rid: str = typer.Argument(
        ..., help="Table import Resource Identifier", autocompletion=complete_rid
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
    """Get detailed information about a specific table import."""
    try:
        cache_rid(import_rid)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching table import {import_rid}..."
        ):
            service = ConnectivityService(profile=profile)
            table_import = service.get_table_import(import_rid)

        formatter.format_output([table_import], format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error getting table import: {e}[/red]")
        raise typer.Exit(1)
