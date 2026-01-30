"""
Streams management commands for Foundry.
Provides commands for managing streaming datasets and publishing records.
"""

import typer
import json
from typing import Optional
from pathlib import Path
from rich.console import Console

from ..services.streams import StreamsService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..auth.base import ProfileNotFoundError, MissingCredentialsError
from ..utils.completion import (
    complete_rid,
    complete_profile,
    complete_output_format,
)

# Create main app and sub-apps
app = typer.Typer(help="Manage streaming datasets and streams")
dataset_app = typer.Typer(help="Manage streaming datasets")
stream_app = typer.Typer(help="Manage streams and publish records")

# Add sub-apps
app.add_typer(dataset_app, name="dataset")
app.add_typer(stream_app, name="stream")

console = Console()
formatter = OutputFormatter(console)


def parse_json_or_file(data_str: Optional[str]) -> Optional[dict]:
    """
    Parse JSON from string or file.

    Supports:
    - Inline JSON: '{"key": "value"}'
    - File reference: @data.json

    Args:
        data_str: JSON string or file reference

    Returns:
        Parsed dictionary or None

    Raises:
        FileNotFoundError: If file reference doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    if not data_str:
        return None

    # Handle file reference
    if data_str.startswith("@"):
        file_path = Path(data_str[1:])
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "r") as f:
            return json.load(f)

    # Handle inline JSON
    return json.loads(data_str)


@dataset_app.command("create")
def create_dataset(
    name: str = typer.Argument(
        ...,
        help="Dataset name",
    ),
    parent_folder_rid: str = typer.Option(
        ...,
        "--folder",
        "-f",
        help="Parent folder RID (e.g., ri.compass.main.folder.xxx)",
        autocompletion=complete_rid,
    ),
    schema: str = typer.Option(
        ...,
        "--schema",
        "-s",
        help="Stream schema as JSON or @file.json. Format: {'fieldSchemaList': [{'name': 'field', 'type': 'STRING'}]}",
    ),
    branch: Optional[str] = typer.Option(
        None,
        "--branch",
        "-b",
        help="Branch name (default: master)",
    ),
    compressed: Optional[bool] = typer.Option(
        None,
        "--compressed",
        help="Enable compression",
    ),
    partitions: Optional[int] = typer.Option(
        None,
        "--partitions",
        help="Number of partitions (default: 1). Each partition handles ~5 MB/s.",
    ),
    stream_type: Optional[str] = typer.Option(
        None,
        "--type",
        help="Stream type: HIGH_THROUGHPUT or LOW_LATENCY (default: LOW_LATENCY)",
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
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Create a new streaming dataset with an initial stream.

    The schema defines the structure of records in the stream.
    Each field must have a 'name' and 'type' (STRING, INTEGER, DOUBLE, BOOLEAN, etc.).

    Examples:

        # Create basic streaming dataset
        pltr streams dataset create my-stream \\
            --folder ri.compass.main.folder.xxx \\
            --schema '{"fieldSchemaList": [{"name": "value", "type": "STRING"}]}'

        # Create from schema file
        pltr streams dataset create sensor-data \\
            --folder ri.compass.main.folder.xxx \\
            --schema @schema.json \\
            --partitions 5 \\
            --type HIGH_THROUGHPUT

        # With specific branch
        pltr streams dataset create my-stream \\
            --folder ri.compass.main.folder.xxx \\
            --schema @schema.json \\
            --branch develop
    """
    try:
        # Parse schema
        schema_dict = parse_json_or_file(schema)
        if schema_dict is None:
            console.print("[red]Error: Schema is required[/red]")
            raise typer.Exit(1)

        with SpinnerProgressTracker().track_spinner("Creating streaming dataset"):
            service = StreamsService(profile=profile)
            result = service.create_dataset(
                name=name,
                parent_folder_rid=parent_folder_rid,
                schema=schema_dict,
                branch_name=branch,
                compressed=compressed,
                partitions_count=partitions,
                stream_type=stream_type,
                preview=preview,
            )

        console.print(
            f"[green]✓[/green] Created streaming dataset: {result.get('name')}"
        )
        console.print(f"  Dataset RID: {result.get('rid')}")
        console.print(f"  Stream RID: {result.get('streamRid')}")

        formatter.format_output(result, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Error parsing schema: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@stream_app.command("create")
def create_stream(
    dataset_rid: str = typer.Argument(
        ...,
        help="Dataset RID (e.g., ri.foundry.main.dataset.xxx)",
        autocompletion=complete_rid,
    ),
    branch: str = typer.Option(
        ...,
        "--branch",
        "-b",
        help="Branch name to create stream on",
    ),
    schema: str = typer.Option(
        ...,
        "--schema",
        "-s",
        help="Stream schema as JSON or @file.json",
    ),
    compressed: Optional[bool] = typer.Option(
        None,
        "--compressed",
        help="Enable compression",
    ),
    partitions: Optional[int] = typer.Option(
        None,
        "--partitions",
        help="Number of partitions (default: 1)",
    ),
    stream_type: Optional[str] = typer.Option(
        None,
        "--type",
        help="Stream type: HIGH_THROUGHPUT or LOW_LATENCY",
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
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Create a new stream on a branch of an existing streaming dataset.

    Creates a new branch and stream in one operation.

    Examples:

        # Create stream on new branch
        pltr streams stream create ri.foundry.main.dataset.xxx \\
            --branch feature-branch \\
            --schema '{"fieldSchemaList": [{"name": "id", "type": "INTEGER"}]}'

        # High-throughput stream
        pltr streams stream create ri.foundry.main.dataset.xxx \\
            --branch production \\
            --schema @schema.json \\
            --partitions 10 \\
            --type HIGH_THROUGHPUT
    """
    try:
        # Parse schema
        schema_dict = parse_json_or_file(schema)
        if schema_dict is None:
            console.print("[red]Error: Schema is required[/red]")
            raise typer.Exit(1)

        with SpinnerProgressTracker().track_spinner("Creating stream"):
            service = StreamsService(profile=profile)
            result = service.create_stream(
                dataset_rid=dataset_rid,
                branch_name=branch,
                schema=schema_dict,
                compressed=compressed,
                partitions_count=partitions,
                stream_type=stream_type,
                preview=preview,
            )

        console.print(f"[green]✓[/green] Created stream on branch: {branch}")
        console.print(f"  Stream RID: {result.get('streamRid')}")

        formatter.format_output(result, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Error parsing schema: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@stream_app.command("get")
def get_stream(
    dataset_rid: str = typer.Argument(
        ...,
        help="Dataset RID",
        autocompletion=complete_rid,
    ),
    branch: str = typer.Option(
        ...,
        "--branch",
        "-b",
        help="Stream branch name",
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
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Get information about a stream.

    Retrieves stream metadata including schema and configuration.

    Examples:

        # Get stream on master branch
        pltr streams stream get ri.foundry.main.dataset.xxx --branch master

        # Get stream as JSON
        pltr streams stream get ri.foundry.main.dataset.xxx \\
            --branch feature-branch \\
            --format json
    """
    try:
        with SpinnerProgressTracker().track_spinner("Fetching stream information"):
            service = StreamsService(profile=profile)
            result = service.get_stream(
                dataset_rid=dataset_rid,
                stream_branch_name=branch,
                preview=preview,
            )

        formatter.format_output(result, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@stream_app.command("publish")
def publish_record(
    dataset_rid: str = typer.Argument(
        ...,
        help="Dataset RID",
        autocompletion=complete_rid,
    ),
    branch: str = typer.Option(
        ...,
        "--branch",
        "-b",
        help="Stream branch name",
    ),
    record: str = typer.Option(
        ...,
        "--record",
        "-r",
        help="Record data as JSON or @file.json",
    ),
    view_rid: Optional[str] = typer.Option(
        None,
        "--view",
        help="View RID for partitioning",
        autocompletion=complete_rid,
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Publish a single record to a stream.

    The record must match the stream's schema.

    Examples:

        # Publish inline record
        pltr streams stream publish ri.foundry.main.dataset.xxx \\
            --branch master \\
            --record '{"id": 123, "name": "test", "timestamp": 1234567890}'

        # Publish from file
        pltr streams stream publish ri.foundry.main.dataset.xxx \\
            --branch master \\
            --record @record.json
    """
    try:
        # Parse record
        record_dict = parse_json_or_file(record)
        if record_dict is None:
            console.print("[red]Error: Record is required[/red]")
            raise typer.Exit(1)

        with SpinnerProgressTracker().track_spinner("Publishing record"):
            service = StreamsService(profile=profile)
            service.publish_record(
                dataset_rid=dataset_rid,
                stream_branch_name=branch,
                record=record_dict,
                view_rid=view_rid,
                preview=preview,
            )

        console.print("[green]✓[/green] Record published successfully")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Error parsing record: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@stream_app.command("publish-batch")
def publish_records(
    dataset_rid: str = typer.Argument(
        ...,
        help="Dataset RID",
        autocompletion=complete_rid,
    ),
    branch: str = typer.Option(
        ...,
        "--branch",
        "-b",
        help="Stream branch name",
    ),
    records: str = typer.Option(
        ...,
        "--records",
        "-r",
        help="Records as JSON array or @file.json",
    ),
    view_rid: Optional[str] = typer.Option(
        None,
        "--view",
        help="View RID for partitioning",
        autocompletion=complete_rid,
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Publish multiple records to a stream in a batch.

    More efficient than publishing records individually.

    Examples:

        # Publish multiple records inline
        pltr streams stream publish-batch ri.foundry.main.dataset.xxx \\
            --branch master \\
            --records '[{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]'

        # Publish from file
        pltr streams stream publish-batch ri.foundry.main.dataset.xxx \\
            --branch master \\
            --records @records.json
    """
    try:
        # Parse records
        records_list = parse_json_or_file(records)
        if not records_list or not isinstance(records_list, list):
            console.print("[red]Error: Records must be a JSON array[/red]")
            raise typer.Exit(1)

        with SpinnerProgressTracker().track_spinner("Publishing records"):
            service = StreamsService(profile=profile)
            service.publish_records(
                dataset_rid=dataset_rid,
                stream_branch_name=branch,
                records=records_list,
                view_rid=view_rid,
                preview=preview,
            )

        console.print(
            f"[green]✓[/green] Published {len(records_list)} records successfully"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Error parsing records: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@stream_app.command("reset")
def reset_stream(
    dataset_rid: str = typer.Argument(
        ...,
        help="Dataset RID",
        autocompletion=complete_rid,
    ),
    branch: str = typer.Option(
        ...,
        "--branch",
        "-b",
        help="Stream branch name to reset",
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
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
    confirm: bool = typer.Option(
        False,
        "--confirm",
        help="Skip confirmation prompt",
    ),
):
    """
    Reset a stream, clearing all existing data.

    WARNING: This operation is irreversible and will delete all records.

    Examples:

        # Reset with confirmation
        pltr streams stream reset ri.foundry.main.dataset.xxx --branch master

        # Skip confirmation
        pltr streams stream reset ri.foundry.main.dataset.xxx \\
            --branch master \\
            --confirm
    """
    if not confirm:
        proceed = typer.confirm(
            f"⚠️  This will delete all data in stream on branch '{branch}'. Continue?"
        )
        if not proceed:
            console.print("Operation cancelled")
            raise typer.Exit(0)

    try:
        with SpinnerProgressTracker().track_spinner("Resetting stream"):
            service = StreamsService(profile=profile)
            result = service.reset_stream(
                dataset_rid=dataset_rid,
                stream_branch_name=branch,
                preview=preview,
            )

        console.print(f"[green]✓[/green] Stream reset successfully on branch: {branch}")

        formatter.format_output(result, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        console.print(f"[red]Authentication Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
