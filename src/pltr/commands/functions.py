"""
Functions management commands for Foundry.
Provides commands for query execution and value type inspection.
"""

import typer
import json
from typing import Optional
from pathlib import Path
from rich.console import Console

from ..services.functions import FunctionsService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..auth.base import ProfileNotFoundError, MissingCredentialsError
from ..utils.completion import (
    complete_rid,
    complete_profile,
    complete_output_format,
    cache_rid,
)

# Create main app and sub-apps
app = typer.Typer(help="Manage Functions queries and value types")
query_app = typer.Typer(help="Manage and execute queries")
value_type_app = typer.Typer(help="Manage value types")

# Add sub-apps
app.add_typer(query_app, name="query")
app.add_typer(value_type_app, name="value-type")

console = Console()
formatter = OutputFormatter(console)


def parse_parameters(parameters_str: Optional[str]) -> Optional[dict]:
    """
    Parse parameters from string or file.

    Supports:
    - Inline JSON: '{"key": "value"}'
    - File reference: @params.json

    Args:
        parameters_str: Parameter string or file reference

    Returns:
        Parsed parameters dictionary or None

    Raises:
        FileNotFoundError: If file reference doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    if not parameters_str:
        return None

    # Handle file reference
    if parameters_str.startswith("@"):
        file_path = Path(parameters_str[1:])
        if not file_path.exists():
            raise FileNotFoundError(f"Parameter file not found: {file_path}")

        with open(file_path, "r") as f:
            return json.load(f)

    # Handle inline JSON
    return json.loads(parameters_str)


@query_app.command("get")
def get_query(
    query_api_name: str = typer.Argument(
        ...,
        help="Query API name (e.g., myQuery)",
    ),
    version: Optional[str] = typer.Option(
        None,
        "--version",
        "-v",
        help="Query version to retrieve (e.g., '1.0.0'). Defaults to latest.",
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
    """
    Get query metadata by API name.

    Retrieves query configuration including parameters, output structure,
    and version information.

    Examples:

        # Get latest version of query
        pltr functions query get myQuery

        # Get specific version
        pltr functions query get myQuery --version 1.0.0

        # Output as JSON
        pltr functions query get myQuery --format json

        # Enable preview mode
        pltr functions query get myQuery --preview
    """
    try:
        service = FunctionsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching query '{query_api_name}'..."
        ):
            query = service.get_query(query_api_name, preview=preview, version=version)

        if output:
            formatter.save_to_file(query, output, format)
            formatter.print_success(f"Query information saved to {output}")
        else:
            formatter.display(query, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get query: {e}")
        raise typer.Exit(1)


@query_app.command("get-by-rid")
def get_query_by_rid(
    query_rid: str = typer.Argument(
        ...,
        help="Query Resource Identifier (e.g., ri.functions.main.query.abc123)",
        autocompletion=complete_rid,
    ),
    version: Optional[str] = typer.Option(
        None,
        "--version",
        "-v",
        help="Query version to retrieve (e.g., '1.0.0'). Defaults to latest.",
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
    """
    Get query metadata by RID.

    Retrieves query configuration including parameters, output structure,
    and version information.

    Examples:

        # Get query by RID
        pltr functions query get-by-rid ri.functions.main.query.abc123

        # Get specific version
        pltr functions query get-by-rid ri.functions.main.query.abc123 --version 1.0.0

        # Output as JSON
        pltr functions query get-by-rid ri.functions.main.query.abc123 --format json
    """
    try:
        cache_rid(query_rid)

        service = FunctionsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Fetching query {query_rid}..."):
            query = service.get_query_by_rid(
                query_rid, preview=preview, version=version
            )

        if output:
            formatter.save_to_file(query, output, format)
            formatter.print_success(f"Query information saved to {output}")
        else:
            formatter.display(query, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get query: {e}")
        raise typer.Exit(1)


@query_app.command("execute")
def execute_query(
    query_api_name: str = typer.Argument(
        ...,
        help="Query API name (e.g., myQuery)",
    ),
    parameters: Optional[str] = typer.Option(
        None,
        "--parameters",
        "-params",
        help="Query parameters as JSON string or @file.json",
    ),
    version: Optional[str] = typer.Option(
        None,
        "--version",
        "-v",
        help="Query version to execute (e.g., '1.0.0'). Defaults to latest.",
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
    """
    Execute a query by API name with parameters.

    Parameters can be provided as inline JSON or loaded from a file.
    Supports complex data types including primitives, arrays, structs,
    dates, and timestamps.

    Examples:

        # Execute with inline parameters
        pltr functions query execute myQuery --parameters '{"limit": 10}'

        # Execute with parameters from file
        pltr functions query execute myQuery --parameters @params.json

        # Execute with complex parameters
        pltr functions query execute myQuery --parameters '{
            "limit": 100,
            "filter": "active",
            "config": {"enabled": true}
        }'

        # Execute specific version
        pltr functions query execute myQuery --version 1.0.0 --parameters '{}'

        # Execute with preview mode
        pltr functions query execute myQuery --preview --parameters '{}'
    """
    try:
        # Parse parameters
        try:
            params = parse_parameters(parameters)
        except FileNotFoundError as e:
            formatter.print_error(str(e))
            raise typer.Exit(1)
        except json.JSONDecodeError as e:
            formatter.print_error(f"Invalid JSON in parameters: {e}")
            raise typer.Exit(1)

        service = FunctionsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Executing query '{query_api_name}'..."
        ):
            result = service.execute_query(
                query_api_name, parameters=params, preview=preview, version=version
            )

        if output:
            formatter.save_to_file(result, output, format)
            formatter.print_success(f"Query result saved to {output}")
        else:
            formatter.display(result, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to execute query: {e}")
        raise typer.Exit(1)


@query_app.command("execute-by-rid")
def execute_query_by_rid(
    query_rid: str = typer.Argument(
        ...,
        help="Query Resource Identifier (e.g., ri.functions.main.query.abc123)",
        autocompletion=complete_rid,
    ),
    parameters: Optional[str] = typer.Option(
        None,
        "--parameters",
        "-params",
        help="Query parameters as JSON string or @file.json",
    ),
    version: Optional[str] = typer.Option(
        None,
        "--version",
        "-v",
        help="Query version to execute (e.g., '1.0.0'). Defaults to latest.",
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
    """
    Execute a query by RID with parameters.

    Parameters can be provided as inline JSON or loaded from a file.
    Supports complex data types including primitives, arrays, structs,
    dates, and timestamps.

    Examples:

        # Execute with inline parameters
        pltr functions query execute-by-rid ri.functions.main.query.abc123 --parameters '{"limit": 10}'

        # Execute with parameters from file
        pltr functions query execute-by-rid ri.functions.main.query.abc123 --parameters @params.json

        # Execute specific version
        pltr functions query execute-by-rid ri.functions.main.query.abc123 --version 1.0.0 --parameters '{}'
    """
    try:
        cache_rid(query_rid)

        # Parse parameters
        try:
            params = parse_parameters(parameters)
        except FileNotFoundError as e:
            formatter.print_error(str(e))
            raise typer.Exit(1)
        except json.JSONDecodeError as e:
            formatter.print_error(f"Invalid JSON in parameters: {e}")
            raise typer.Exit(1)

        service = FunctionsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Executing query {query_rid}..."):
            result = service.execute_query_by_rid(
                query_rid, parameters=params, preview=preview, version=version
            )

        if output:
            formatter.save_to_file(result, output, format)
            formatter.print_success(f"Query result saved to {output}")
        else:
            formatter.display(result, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to execute query: {e}")
        raise typer.Exit(1)


@value_type_app.command("get")
def get_value_type(
    value_type_rid: str = typer.Argument(
        ...,
        help="Value Type Resource Identifier (e.g., ri.functions.main.value-type.xyz)",
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
    """
    Get value type details by RID.

    Retrieves value type definition and structure information.

    Examples:

        # Get value type details
        pltr functions value-type get ri.functions.main.value-type.xyz

        # Output as JSON
        pltr functions value-type get ri.functions.main.value-type.xyz --format json

        # Enable preview mode
        pltr functions value-type get ri.functions.main.value-type.xyz --preview
    """
    try:
        cache_rid(value_type_rid)

        service = FunctionsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching value type {value_type_rid}..."
        ):
            value_type = service.get_value_type(value_type_rid, preview=preview)

        if output:
            formatter.save_to_file(value_type, output, format)
            formatter.print_success(f"Value type information saved to {output}")
        else:
            formatter.display(value_type, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        formatter.print_error(f"Invalid request: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get value type: {e}")
        raise typer.Exit(1)
