"""
Simplified dataset commands that work with foundry-platform-sdk v1.27.0.
"""

import typer
from typing import Optional
from rich.console import Console

from ..services.dataset import DatasetService
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
branches_app = typer.Typer()
files_app = typer.Typer()
transactions_app = typer.Typer()
views_app = typer.Typer()
schema_app = typer.Typer()
schedules_app = typer.Typer()
jobs_app = typer.Typer()
console = Console()
formatter = OutputFormatter(console)


@app.command("get")
def get_dataset(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
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
    """Get detailed information about a specific dataset."""
    try:
        # Cache the RID for future completions
        cache_rid(dataset_rid)

        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching dataset {dataset_rid}..."
        ):
            dataset = service.get_dataset(dataset_rid)

        formatter.format_dataset_detail(dataset, format, output)

        if output:
            formatter.print_success(f"Dataset information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get dataset: {e}")
        raise typer.Exit(1)


# Schema commands
@schema_app.command("get")
def get_schema(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
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
    """Get the schema of a dataset (requires API preview access)."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        formatter.print_warning(
            "Note: This command requires API preview access. "
            "If you encounter an 'ApiFeaturePreviewUsageOnly' error, "
            "use 'pltr dataset schema apply' instead to infer/apply schema."
        )

        with SpinnerProgressTracker().track_spinner(
            f"Fetching schema for {dataset_rid}..."
        ):
            schema = service.get_schema(dataset_rid)

        # Format schema for display
        if format == "json":
            formatter._format_json(schema, output)
        else:
            formatter.print_info(f"Dataset: {dataset_rid}")
            formatter.print_info(f"Status: {schema.get('status', 'Unknown')}")
            if schema.get("schema"):
                formatter.print_info("\nSchema:")
                formatter._format_json(schema.get("schema"))

        if output:
            formatter.print_success(f"Schema saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        if "ApiFeaturePreviewUsageOnly" in str(e):
            formatter.print_error(
                "This command requires API preview access. "
                "Please use 'pltr dataset schema apply' instead."
            )
        else:
            formatter.print_error(f"Failed to get schema: {e}")
        raise typer.Exit(1)


@schema_app.command("apply")
def apply_schema(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    branch: str = typer.Option("master", "--branch", "-b", help="Dataset branch name"),
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
):
    """Apply/infer schema for a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Applying schema to dataset {dataset_rid} on branch '{branch}'..."
        ):
            result = service.apply_schema(dataset_rid, branch)

        formatter.print_success(f"Schema applied successfully to branch '{branch}'")

        # Display result if available
        if result.get("result"):
            formatter._format_json(result.get("result"))

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to apply schema: {e}")
        raise typer.Exit(1)


@schema_app.command("set")
def set_schema(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    from_csv: Optional[str] = typer.Option(
        None, "--from-csv", help="Infer schema from CSV file"
    ),
    json_schema: Optional[str] = typer.Option(
        None, "--json", help="JSON string defining the schema"
    ),
    json_file: Optional[str] = typer.Option(
        None, "--json-file", help="Path to JSON file containing schema definition"
    ),
    branch: str = typer.Option("master", "--branch", help="Dataset branch"),
    transaction_rid: Optional[str] = typer.Option(
        None, "--transaction-rid", help="Transaction RID to use"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
):
    """Set or update the schema of a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        # Validate that exactly one input method is provided
        input_methods = [from_csv, json_schema, json_file]
        if sum(x is not None for x in input_methods) != 1:
            formatter.print_error(
                "Exactly one of --from-csv, --json, or --json-file must be provided"
            )
            raise typer.Exit(1)

        schema = None

        # Infer schema from CSV
        if from_csv:
            with SpinnerProgressTracker().track_spinner(
                f"Inferring schema from {from_csv}..."
            ):
                schema = service.infer_schema_from_csv(from_csv)
                formatter.print_info(
                    f"Inferred schema from CSV with {len(schema.field_schema_list)} fields"
                )
                for field in schema.field_schema_list:
                    formatter.print_info(
                        f"  - {field.name}: {field.type} (nullable={field.nullable})"
                    )

        # Parse schema from JSON string
        elif json_schema:
            import json
            from foundry_sdk.v2.core.models import DatasetSchema, DatasetFieldSchema

            try:
                schema_data = json.loads(json_schema)
                fields = []
                for field_data in schema_data.get("fields", []):
                    fields.append(
                        DatasetFieldSchema(
                            name=field_data["name"],
                            type=field_data["type"],
                            nullable=field_data.get("nullable", True),
                        )
                    )
                schema = DatasetSchema(field_schema_list=fields)
            except (json.JSONDecodeError, KeyError) as e:
                formatter.print_error(f"Invalid JSON schema: {e}")
                raise typer.Exit(1)

        # Load schema from JSON file
        elif json_file:
            import json
            from foundry_sdk.v2.core.models import DatasetSchema, DatasetFieldSchema

            try:
                with open(json_file, "r") as f:
                    schema_data = json.load(f)
                fields = []
                for field_data in schema_data.get("fields", []):
                    fields.append(
                        DatasetFieldSchema(
                            name=field_data["name"],
                            type=field_data["type"],
                            nullable=field_data.get("nullable", True),
                        )
                    )
                schema = DatasetSchema(field_schema_list=fields)
            except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                formatter.print_error(f"Failed to load schema from file: {e}")
                raise typer.Exit(1)

        # Apply the schema
        with SpinnerProgressTracker().track_spinner(
            f"Setting schema on dataset {dataset_rid}..."
        ):
            service.put_schema(
                dataset_rid=dataset_rid,
                schema=schema,
                branch=branch,
                transaction_rid=transaction_rid,
            )

        formatter.print_success(f"Successfully set schema on dataset {dataset_rid}")
        if transaction_rid:
            formatter.print_info(f"Transaction RID: {transaction_rid}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except FileNotFoundError as e:
        formatter.print_error(f"File not found: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to set schema: {e}")
        raise typer.Exit(1)


@app.command("create")
def create_dataset(
    name: str = typer.Argument(..., help="Dataset name"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    parent_folder: Optional[str] = typer.Option(
        None, "--parent-folder", help="Parent folder RID"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
):
    """Create a new dataset."""
    try:
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Creating dataset '{name}'..."):
            dataset = service.create_dataset(name=name, parent_folder_rid=parent_folder)

        formatter.print_success(f"Successfully created dataset '{name}'")
        formatter.print_info(f"Dataset RID: {dataset.get('rid', 'unknown')}")

        # Show dataset details
        formatter.format_dataset_detail(dataset, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create dataset: {e}")
        raise typer.Exit(1)


# Branch commands
@branches_app.command("list")
def list_branches(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
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
    """List branches for a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching branches for {dataset_rid}..."
        ):
            branches = service.get_branches(dataset_rid)

        formatter.format_branches(branches, format, output)

        if output:
            formatter.print_success(f"Branches information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get branches: {e}")
        raise typer.Exit(1)


@branches_app.command("create")
def create_branch(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    branch_name: str = typer.Argument(..., help="Branch name"),
    parent_branch: str = typer.Option(
        "master", "--parent", help="Parent branch to branch from"
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
):
    """Create a new branch for a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Creating branch '{branch_name}' from '{parent_branch}'..."
        ):
            branch = service.create_branch(dataset_rid, branch_name, parent_branch)

        formatter.print_success(f"Successfully created branch '{branch_name}'")
        formatter.format_branch_detail(branch, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create branch: {e}")
        raise typer.Exit(1)


@branches_app.command("delete")
def delete_branch(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    branch_name: str = typer.Argument(..., help="Branch name to delete"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
):
    """Delete a branch from a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        # Prevent deleting master branch
        if branch_name.lower() == "master":
            formatter.print_error("Cannot delete the master branch")
            raise typer.Exit(1)

        # Confirmation prompt
        if not confirm:
            confirmed = typer.confirm(
                f"Are you sure you want to delete branch '{branch_name}' from dataset {dataset_rid}? "
                f"This action cannot be undone."
            )
            if not confirmed:
                formatter.print_info("Branch deletion cancelled")
                raise typer.Exit(0)

        with SpinnerProgressTracker().track_spinner(
            f"Deleting branch '{branch_name}' from {dataset_rid}..."
        ):
            service.delete_branch(dataset_rid, branch_name)

        formatter.print_success(f"Branch '{branch_name}' deleted successfully")
        formatter.print_info(f"Dataset: {dataset_rid}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to delete branch: {e}")
        raise typer.Exit(1)


@branches_app.command("get")
def get_branch(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    branch_name: str = typer.Argument(..., help="Branch name"),
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
    """Get detailed information about a specific branch."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching branch '{branch_name}' from {dataset_rid}..."
        ):
            branch = service.get_branch(dataset_rid, branch_name)

        formatter.format_branch_detail(branch, format, output)

        if output:
            formatter.print_success(f"Branch information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get branch: {e}")
        raise typer.Exit(1)


@branches_app.command("transactions")
def list_branch_transactions(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    branch_name: str = typer.Argument(..., help="Branch name"),
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
    """Get transaction history for a specific branch."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching transaction history for branch '{branch_name}' in {dataset_rid}..."
        ):
            transactions = service.get_branch_transactions(dataset_rid, branch_name)

        formatter.format_transactions(transactions, format, output)

        if output:
            formatter.print_success(f"Branch transactions saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get branch transactions: {e}")
        raise typer.Exit(1)


# Files commands
@files_app.command("list")
def list_files(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    branch: str = typer.Option("master", "--branch", help="Dataset branch"),
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
    """List files in a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching files from {dataset_rid} (branch: {branch})..."
        ):
            files = service.list_files(dataset_rid, branch)

        formatter.format_files(files, format, output)

        if output:
            formatter.print_success(f"Files information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list files: {e}")
        raise typer.Exit(1)


@files_app.command("upload")
def upload_file(
    file_path: str = typer.Argument(..., help="Local path to file to upload"),
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    branch: str = typer.Option("master", "--branch", help="Dataset branch"),
    transaction_rid: Optional[str] = typer.Option(
        None, "--transaction-rid", help="Transaction RID for the upload"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
):
    """Upload a file to a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        # Check if file exists
        from pathlib import Path

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            formatter.print_error(f"File not found: {file_path}")
            raise typer.Exit(1)

        with SpinnerProgressTracker().track_spinner(
            f"Uploading {file_path_obj.name} to {dataset_rid}..."
        ):
            result = service.upload_file(
                dataset_rid, file_path, branch, transaction_rid
            )

        formatter.print_success("File uploaded successfully")
        formatter.print_info(f"File: {result.get('file_path', file_path)}")
        formatter.print_info(f"Dataset: {dataset_rid}")
        formatter.print_info(f"Branch: {branch}")
        formatter.print_info(f"Size: {result.get('size_bytes', 'unknown')} bytes")

        if result.get("transaction_rid"):
            formatter.print_info(f"Transaction: {result['transaction_rid']}")
            formatter.print_warning(
                "Remember to commit the transaction to make changes permanent"
            )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except FileNotFoundError as e:
        formatter.print_error(f"File error: {e}")
        raise typer.Exit(1)
    except RuntimeError as e:
        # RuntimeError from our service layer contains detailed error info
        error_msg = str(e)
        formatter.print_error(f"Upload failed: {error_msg}")

        # If it looks like our enhanced error message, extract the suggestion part
        if ". Suggestions: " in error_msg:
            main_error, suggestions = error_msg.split(". Suggestions: ", 1)
            formatter.print_error(main_error)
            formatter.print_info(f"💡 Suggestions: {suggestions}")

        raise typer.Exit(1)
    except Exception as e:
        # Fallback for any other exceptions
        formatter.print_error(
            f"Unexpected error during file upload: {type(e).__name__}: {e}"
        )
        formatter.print_info(
            "💡 Try running the command again or check your connection"
        )
        raise typer.Exit(1)


@files_app.command("get")
def get_file(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    file_path: str = typer.Argument(..., help="Path of file within dataset"),
    output_path: str = typer.Argument(..., help="Local path to save the file"),
    branch: str = typer.Option("master", "--branch", help="Dataset branch"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
):
    """Download a file from a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Downloading {file_path} from {dataset_rid}..."
        ):
            result = service.download_file(dataset_rid, file_path, output_path, branch)

        formatter.print_success(f"File downloaded to {result['output_path']}")
        formatter.print_info(f"Size: {result.get('size_bytes', 'unknown')} bytes")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to download file: {e}")
        raise typer.Exit(1)


@files_app.command("delete")
def delete_file(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    file_path: str = typer.Argument(..., help="Path of file within dataset to delete"),
    branch: str = typer.Option("master", "--branch", help="Dataset branch"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
):
    """Delete a file from a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        # Confirmation prompt
        if not confirm:
            confirmed = typer.confirm(
                f"Are you sure you want to delete '{file_path}' from dataset {dataset_rid}?"
            )
            if not confirmed:
                formatter.print_info("File deletion cancelled")
                raise typer.Exit(0)

        with SpinnerProgressTracker().track_spinner(
            f"Deleting {file_path} from {dataset_rid}..."
        ):
            service.delete_file(dataset_rid, file_path, branch)

        formatter.print_success(f"File '{file_path}' deleted successfully")
        formatter.print_info(f"Dataset: {dataset_rid}")
        formatter.print_info(f"Branch: {branch}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to delete file: {e}")
        raise typer.Exit(1)


@files_app.command("info")
def get_file_info(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    file_path: str = typer.Argument(..., help="Path of file within dataset"),
    branch: str = typer.Option("master", "--branch", help="Dataset branch"),
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
    """Get metadata information about a file in a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Getting file info for {file_path} in {dataset_rid}..."
        ):
            file_info = service.get_file_info(dataset_rid, file_path, branch)

        formatter.format_file_info(file_info, format, output)

        if output:
            formatter.print_success(f"File information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get file info: {e}")
        raise typer.Exit(1)


# Transaction commands
@transactions_app.command("start")
def start_transaction(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    branch: str = typer.Option("master", "--branch", help="Dataset branch"),
    transaction_type: str = typer.Option(
        "APPEND", "--type", help="Transaction type (APPEND, UPDATE, SNAPSHOT, DELETE)"
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
):
    """Start a new transaction for a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        # Validate transaction type
        valid_types = ["APPEND", "UPDATE", "SNAPSHOT", "DELETE"]
        if transaction_type not in valid_types:
            formatter.print_error(
                f"Invalid transaction type. Must be one of: {', '.join(valid_types)}"
            )
            raise typer.Exit(1)

        with SpinnerProgressTracker().track_spinner(
            f"Starting {transaction_type} transaction for {dataset_rid} (branch: {branch})..."
        ):
            transaction = service.create_transaction(
                dataset_rid, branch, transaction_type
            )

        formatter.print_success("Transaction started successfully")
        formatter.print_info(
            f"Transaction RID: {transaction.get('transaction_rid', 'unknown')}"
        )
        formatter.print_info(f"Status: {transaction.get('status', 'OPEN')}")
        formatter.print_info(
            f"Type: {transaction.get('transaction_type', transaction_type)}"
        )

        # Show transaction details
        formatter.format_transaction_detail(transaction, format)

        # Show usage hint
        transaction_rid = transaction.get("transaction_rid", "unknown")
        if transaction_rid != "unknown":
            formatter.print_info("\nNext steps:")
            formatter.print_info(
                f"  Upload files: pltr dataset files upload <file-path> {dataset_rid} --transaction-rid {transaction_rid}"
            )
            formatter.print_info(
                f"  Commit: pltr dataset transactions commit {dataset_rid} {transaction_rid}"
            )
            formatter.print_info(
                f"  Abort: pltr dataset transactions abort {dataset_rid} {transaction_rid}"
            )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to start transaction: {e}")
        raise typer.Exit(1)


@transactions_app.command("commit")
def commit_transaction(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    transaction_rid: str = typer.Argument(..., help="Transaction Resource Identifier"),
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
):
    """Commit an open transaction."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Committing transaction {transaction_rid}..."
        ):
            result = service.commit_transaction(dataset_rid, transaction_rid)

        formatter.print_success("Transaction committed successfully")
        formatter.print_info(f"Transaction RID: {transaction_rid}")
        formatter.print_info(f"Dataset RID: {dataset_rid}")
        formatter.print_info(f"Status: {result.get('status', 'COMMITTED')}")

        # Show result details
        formatter.format_transaction_result(result, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to commit transaction: {e}")
        raise typer.Exit(1)


@transactions_app.command("abort")
def abort_transaction(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    transaction_rid: str = typer.Argument(..., help="Transaction Resource Identifier"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
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
):
    """Abort an open transaction."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        # Confirmation prompt
        if not confirm:
            confirmed = typer.confirm(
                f"Are you sure you want to abort transaction {transaction_rid}? "
                f"This will discard all changes made in this transaction."
            )
            if not confirmed:
                formatter.print_info("Transaction abort cancelled")
                raise typer.Exit(0)

        with SpinnerProgressTracker().track_spinner(
            f"Aborting transaction {transaction_rid}..."
        ):
            result = service.abort_transaction(dataset_rid, transaction_rid)

        formatter.print_success("Transaction aborted successfully")
        formatter.print_info(f"Transaction RID: {transaction_rid}")
        formatter.print_info(f"Dataset RID: {dataset_rid}")
        formatter.print_info(f"Status: {result.get('status', 'ABORTED')}")
        formatter.print_warning(
            "All changes made in this transaction have been discarded"
        )

        # Show result details
        formatter.format_transaction_result(result, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to abort transaction: {e}")
        raise typer.Exit(1)


@transactions_app.command("status")
def get_transaction_status(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    transaction_rid: str = typer.Argument(..., help="Transaction Resource Identifier"),
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
):
    """Get the status of a specific transaction."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching transaction status for {transaction_rid}..."
        ):
            transaction = service.get_transaction_status(dataset_rid, transaction_rid)

        formatter.print_success("Transaction status retrieved")

        # Show transaction details
        formatter.format_transaction_detail(transaction, format)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get transaction status: {e}")
        raise typer.Exit(1)


@transactions_app.command("list")
def list_transactions(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    branch: str = typer.Option("master", "--branch", help="Dataset branch"),
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
    """List transactions for a dataset branch."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching transactions for {dataset_rid} (branch: {branch})..."
        ):
            transactions = service.get_transactions(dataset_rid, branch)

        formatter.format_transactions(transactions, format, output)

        if output:
            formatter.print_success(f"Transactions information saved to {output}")

    except NotImplementedError as e:
        formatter.print_warning(f"Feature not available: {e}")
        raise typer.Exit(0)
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list transactions: {e}")
        raise typer.Exit(1)


@transactions_app.command("build")
def get_transaction_build(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    transaction_rid: str = typer.Argument(..., help="Transaction Resource Identifier"),
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
    """Get build information for a transaction."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching build information for transaction {transaction_rid}..."
        ):
            build_info = service.get_transaction_build(dataset_rid, transaction_rid)

        formatter.format_transaction_build(build_info, format, output)

        if output:
            formatter.print_success(f"Build information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get transaction build: {e}")
        raise typer.Exit(1)


# Views commands
@views_app.command("list")
def list_views(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
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
    """List views for a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching views for {dataset_rid}..."
        ):
            views = service.get_views(dataset_rid)

        formatter.format_views(views, format, output)

        if output:
            formatter.print_success(f"Views information saved to {output}")

    except NotImplementedError as e:
        formatter.print_warning(f"Feature not available: {e}")
        raise typer.Exit(0)
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list views: {e}")
        raise typer.Exit(1)


@views_app.command("get")
def get_view(
    view_rid: str = typer.Argument(
        ..., help="View Resource Identifier", autocompletion=complete_rid
    ),
    branch: str = typer.Option("master", "--branch", help="Branch name"),
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
    """Get detailed information about a view."""
    try:
        cache_rid(view_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(f"Fetching view {view_rid}..."):
            view = service.get_view(view_rid, branch)

        formatter.format_view_detail(view, format, output)

        if output:
            formatter.print_success(f"View information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get view: {e}")
        raise typer.Exit(1)


@views_app.command("add-datasets")
def add_backing_datasets(
    view_rid: str = typer.Argument(
        ..., help="View Resource Identifier", autocompletion=complete_rid
    ),
    dataset_rids: list[str] = typer.Argument(
        ..., help="Dataset RIDs to add as backing datasets"
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
):
    """Add backing datasets to a view."""
    try:
        cache_rid(view_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Adding {len(dataset_rids)} backing datasets to view {view_rid}..."
        ):
            result = service.add_backing_datasets(view_rid, dataset_rids)

        formatter.print_success("Successfully added backing datasets to view")
        formatter.print_info(f"View RID: {view_rid}")
        formatter.print_info(f"Added datasets: {', '.join(dataset_rids)}")

        if format == "json":
            formatter._format_json(result)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to add backing datasets: {e}")
        raise typer.Exit(1)


@views_app.command("remove-datasets")
def remove_backing_datasets(
    view_rid: str = typer.Argument(
        ..., help="View Resource Identifier", autocompletion=complete_rid
    ),
    dataset_rids: list[str] = typer.Argument(
        ..., help="Dataset RIDs to remove as backing datasets"
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
):
    """Remove backing datasets from a view."""
    try:
        cache_rid(view_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Removing {len(dataset_rids)} backing datasets from view {view_rid}..."
        ):
            result = service.remove_backing_datasets(view_rid, dataset_rids)

        formatter.print_success("Successfully removed backing datasets from view")
        formatter.print_info(f"View RID: {view_rid}")
        formatter.print_info(f"Removed datasets: {', '.join(dataset_rids)}")

        if format == "json":
            formatter._format_json(result)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to remove backing datasets: {e}")
        raise typer.Exit(1)


@views_app.command("replace-datasets")
def replace_backing_datasets(
    view_rid: str = typer.Argument(
        ..., help="View Resource Identifier", autocompletion=complete_rid
    ),
    dataset_rids: list[str] = typer.Argument(
        ..., help="Dataset RIDs to set as backing datasets"
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
):
    """Replace all backing datasets in a view."""
    try:
        cache_rid(view_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Replacing backing datasets in view {view_rid} with {len(dataset_rids)} new datasets..."
        ):
            result = service.replace_backing_datasets(view_rid, dataset_rids)

        formatter.print_success("Successfully replaced backing datasets in view")
        formatter.print_info(f"View RID: {view_rid}")
        formatter.print_info(f"New datasets: {', '.join(dataset_rids)}")

        if format == "json":
            formatter._format_json(result)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to replace backing datasets: {e}")
        raise typer.Exit(1)


@views_app.command("add-primary-key")
def add_primary_key(
    view_rid: str = typer.Argument(
        ..., help="View Resource Identifier", autocompletion=complete_rid
    ),
    key_fields: list[str] = typer.Argument(
        ..., help="Field names to use as primary key"
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
):
    """Add a primary key to a view."""
    try:
        cache_rid(view_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Adding primary key to view {view_rid}..."
        ):
            result = service.add_primary_key(view_rid, key_fields)

        formatter.print_success("Successfully added primary key to view")
        formatter.print_info(f"View RID: {view_rid}")
        formatter.print_info(f"Primary key fields: {', '.join(key_fields)}")

        if format == "json":
            formatter._format_json(result)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to add primary key: {e}")
        raise typer.Exit(1)


@views_app.command("create")
def create_view(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    view_name: str = typer.Argument(..., help="View name"),
    description: Optional[str] = typer.Option(
        None, "--description", help="View description"
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
):
    """Create a new view for a dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Creating view '{view_name}' for {dataset_rid}..."
        ):
            view = service.create_view(dataset_rid, view_name, description)

        formatter.print_success(f"Successfully created view '{view_name}'")
        formatter.format_view_detail(view, format)

    except NotImplementedError as e:
        formatter.print_warning(f"Feature not available: {e}")
        raise typer.Exit(0)
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create view: {e}")
        raise typer.Exit(1)


# Schedules commands
@schedules_app.command("list")
def list_schedules(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
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
    """List schedules that target a specific dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching schedules for dataset {dataset_rid}..."
        ):
            schedules = service.get_schedules(dataset_rid)

        formatter.format_schedules(schedules, format, output)

        if output:
            formatter.print_success(f"Schedules information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get schedules: {e}")
        raise typer.Exit(1)


# Jobs commands
@jobs_app.command("list")
def list_jobs(
    dataset_rid: str = typer.Argument(
        ..., help="Dataset Resource Identifier", autocompletion=complete_rid
    ),
    branch: str = typer.Option("master", "--branch", help="Dataset branch"),
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
    """List jobs for a specific dataset."""
    try:
        cache_rid(dataset_rid)
        service = DatasetService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching jobs for dataset {dataset_rid} (branch: {branch})..."
        ):
            jobs = service.get_jobs(dataset_rid, branch)

        formatter.format_jobs(jobs, format, output)

        if output:
            formatter.print_success(f"Jobs information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get jobs: {e}")
        raise typer.Exit(1)


# Add subcommands to main app
app.add_typer(branches_app, name="branches")
app.add_typer(files_app, name="files")
app.add_typer(transactions_app, name="transactions")
app.add_typer(views_app, name="views")
app.add_typer(schema_app, name="schema")
app.add_typer(schedules_app, name="schedules")
app.add_typer(jobs_app, name="jobs")


@app.callback()
def main():
    """
    Dataset operations using foundry-platform-sdk.

    Note: This SDK version requires knowing dataset RIDs in advance.
    Find dataset RIDs in the Foundry web interface.

    Available commands work with Resource Identifiers (RIDs) like:
    ri.foundry.main.dataset.12345678-1234-1234-1234-123456789abc
    """
    pass
