"""
Ontology commands for interacting with Foundry ontologies.
"""

import json
import typer
from typing import Optional
from rich.console import Console

from ..services.ontology import (
    OntologyService,
    ObjectTypeService,
    OntologyObjectService,
    ActionService,
    QueryService,
)
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..auth.base import ProfileNotFoundError, MissingCredentialsError

app = typer.Typer(help="Ontology operations")
console = Console()
formatter = OutputFormatter(console)


# Ontology management commands
@app.command("list")
def list_ontologies(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """List all available ontologies."""
    try:
        service = OntologyService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching ontologies..."):
            ontologies = service.list_ontologies()

        formatter.format_table(
            ontologies,
            columns=["rid", "api_name", "display_name", "description"],
            format=format,
            output=output,
        )

        if output:
            formatter.print_success(f"Ontologies saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list ontologies: {e}")
        raise typer.Exit(1)


@app.command("get")
def get_ontology(
    ontology_rid: str = typer.Argument(..., help="Ontology Resource Identifier"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Get details of a specific ontology."""
    try:
        service = OntologyService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching ontology {ontology_rid}..."
        ):
            ontology = service.get_ontology(ontology_rid)

        formatter.format_dict(ontology, format=format, output=output)

        if output:
            formatter.print_success(f"Ontology information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get ontology: {e}")
        raise typer.Exit(1)


# Object Type commands
@app.command("object-type-list")
def list_object_types(
    ontology_rid: str = typer.Argument(..., help="Ontology Resource Identifier"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """List object types in an ontology."""
    try:
        service = ObjectTypeService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Fetching object types..."):
            object_types = service.list_object_types(ontology_rid)

        formatter.format_table(
            object_types,
            columns=["api_name", "display_name", "description", "primary_key"],
            format=format,
            output=output,
        )

        if output:
            formatter.print_success(f"Object types saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list object types: {e}")
        raise typer.Exit(1)


@app.command("object-type-get")
def get_object_type(
    ontology_rid: str = typer.Argument(..., help="Ontology Resource Identifier"),
    object_type: str = typer.Argument(..., help="Object type API name"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Get details of a specific object type."""
    try:
        service = ObjectTypeService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching object type {object_type}..."
        ):
            obj_type = service.get_object_type(ontology_rid, object_type)

        formatter.format_dict(obj_type, format=format, output=output)

        if output:
            formatter.print_success(f"Object type information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get object type: {e}")
        raise typer.Exit(1)


# Object operations
@app.command("object-list")
def list_objects(
    ontology_rid: str = typer.Argument(..., help="Ontology Resource Identifier"),
    object_type: str = typer.Argument(..., help="Object type API name"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of results per page"
    ),
    properties: Optional[str] = typer.Option(
        None, "--properties", help="Comma-separated list of properties to include"
    ),
):
    """List objects of a specific type."""
    try:
        service = OntologyObjectService(profile=profile)

        prop_list = properties.split(",") if properties else None

        with SpinnerProgressTracker().track_spinner(
            f"Fetching {object_type} objects..."
        ):
            objects = service.list_objects(
                ontology_rid, object_type, page_size=page_size, properties=prop_list
            )

        if format == "table" and objects:
            # Use first object's keys as columns
            columns = list(objects[0].keys()) if objects else []
            formatter.format_table(
                objects, columns=columns, format=format, output=output
            )
        else:
            formatter.format_list(objects, format=format, output=output)

        if output:
            formatter.print_success(f"Objects saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list objects: {e}")
        raise typer.Exit(1)


@app.command("object-get")
def get_object(
    ontology_rid: str = typer.Argument(..., help="Ontology Resource Identifier"),
    object_type: str = typer.Argument(..., help="Object type API name"),
    primary_key: str = typer.Argument(..., help="Object primary key"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    properties: Optional[str] = typer.Option(
        None, "--properties", help="Comma-separated list of properties to include"
    ),
):
    """Get a specific object by primary key."""
    try:
        service = OntologyObjectService(profile=profile)

        prop_list = properties.split(",") if properties else None

        with SpinnerProgressTracker().track_spinner(
            f"Fetching object {primary_key}..."
        ):
            obj = service.get_object(
                ontology_rid, object_type, primary_key, properties=prop_list
            )

        formatter.format_dict(obj, format=format, output=output)

        if output:
            formatter.print_success(f"Object information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get object: {e}")
        raise typer.Exit(1)


@app.command("object-aggregate")
def aggregate_objects(
    ontology_rid: str = typer.Argument(..., help="Ontology Resource Identifier"),
    object_type: str = typer.Argument(..., help="Object type API name"),
    aggregations: str = typer.Argument(..., help="JSON string of aggregation specs"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    group_by: Optional[str] = typer.Option(
        None, "--group-by", help="Comma-separated list of fields to group by"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", help="JSON string of filter criteria"
    ),
):
    """Aggregate objects with specified functions."""
    try:
        service = OntologyObjectService(profile=profile)

        # Parse JSON inputs
        agg_list = json.loads(aggregations)
        group_list = group_by.split(",") if group_by else None
        filter_dict = json.loads(filter) if filter else None

        with SpinnerProgressTracker().track_spinner("Aggregating objects..."):
            result = service.aggregate_objects(
                ontology_rid,
                object_type,
                agg_list,
                group_by=group_list,
                filter=filter_dict,
            )

        formatter.format_dict(result, format=format, output=output)

        if output:
            formatter.print_success(f"Aggregation results saved to {output}")

    except json.JSONDecodeError as e:
        formatter.print_error(f"Invalid JSON: {e}")
        raise typer.Exit(1)
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to aggregate objects: {e}")
        raise typer.Exit(1)


@app.command("object-linked")
def list_linked_objects(
    ontology_rid: str = typer.Argument(..., help="Ontology Resource Identifier"),
    object_type: str = typer.Argument(..., help="Object type API name"),
    primary_key: str = typer.Argument(..., help="Object primary key"),
    link_type: str = typer.Argument(..., help="Link type API name"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of results per page"
    ),
    properties: Optional[str] = typer.Option(
        None, "--properties", help="Comma-separated list of properties to include"
    ),
):
    """List objects linked to a specific object."""
    try:
        service = OntologyObjectService(profile=profile)

        prop_list = properties.split(",") if properties else None

        with SpinnerProgressTracker().track_spinner("Fetching linked objects..."):
            objects = service.list_linked_objects(
                ontology_rid,
                object_type,
                primary_key,
                link_type,
                page_size=page_size,
                properties=prop_list,
            )

        if format == "table" and objects:
            # Use first object's keys as columns
            columns = list(objects[0].keys()) if objects else []
            formatter.format_table(
                objects, columns=columns, format=format, output=output
            )
        else:
            formatter.format_list(objects, format=format, output=output)

        if output:
            formatter.print_success(f"Linked objects saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list linked objects: {e}")
        raise typer.Exit(1)


# Action commands
@app.command("action-apply")
def apply_action(
    ontology_rid: str = typer.Argument(..., help="Ontology Resource Identifier"),
    action_type: str = typer.Argument(..., help="Action type API name"),
    parameters: str = typer.Argument(..., help="JSON string of action parameters"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Apply an action with given parameters."""
    try:
        service = ActionService(profile=profile)

        # Parse JSON parameters
        params = json.loads(parameters)

        with SpinnerProgressTracker().track_spinner(
            f"Applying action {action_type}..."
        ):
            result = service.apply_action(ontology_rid, action_type, params)

        formatter.format_dict(result, format=format, output=output)

        if output:
            formatter.print_success(f"Action result saved to {output}")

    except json.JSONDecodeError as e:
        formatter.print_error(f"Invalid JSON: {e}")
        raise typer.Exit(1)
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to apply action: {e}")
        raise typer.Exit(1)


@app.command("action-validate")
def validate_action(
    ontology_rid: str = typer.Argument(..., help="Ontology Resource Identifier"),
    action_type: str = typer.Argument(..., help="Action type API name"),
    parameters: str = typer.Argument(..., help="JSON string of action parameters"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Validate action parameters without executing."""
    try:
        service = ActionService(profile=profile)

        # Parse JSON parameters
        params = json.loads(parameters)

        with SpinnerProgressTracker().track_spinner(
            f"Validating action {action_type}..."
        ):
            result = service.validate_action(ontology_rid, action_type, params)

        formatter.format_dict(result, format=format, output=output)

        if result.get("valid"):
            formatter.print_success("Action parameters are valid")
        else:
            formatter.print_error("Action parameters are invalid")

        if output:
            formatter.print_success(f"Validation result saved to {output}")

    except json.JSONDecodeError as e:
        formatter.print_error(f"Invalid JSON: {e}")
        raise typer.Exit(1)
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to validate action: {e}")
        raise typer.Exit(1)


# Query commands
@app.command("query-execute")
def execute_query(
    ontology_rid: str = typer.Argument(..., help="Ontology Resource Identifier"),
    query_name: str = typer.Argument(..., help="Query API name"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    parameters: Optional[str] = typer.Option(
        None, "--parameters", help="JSON string of query parameters"
    ),
):
    """Execute a predefined query."""
    try:
        service = QueryService(profile=profile)

        # Parse JSON parameters if provided
        params = json.loads(parameters) if parameters else None

        with SpinnerProgressTracker().track_spinner(f"Executing query {query_name}..."):
            result = service.execute_query(ontology_rid, query_name, parameters=params)

        # Handle different result formats
        if "rows" in result:
            formatter.format_list(result["rows"], format=format, output=output)
        elif "objects" in result:
            formatter.format_list(result["objects"], format=format, output=output)
        else:
            formatter.format_dict(result, format=format, output=output)

        if output:
            formatter.print_success(f"Query results saved to {output}")

    except json.JSONDecodeError as e:
        formatter.print_error(f"Invalid JSON: {e}")
        raise typer.Exit(1)
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to execute query: {e}")
        raise typer.Exit(1)
