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


# schema command removed - uses preview-only API that returns INVALID_ARGUMENT


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
    except Exception as e:
        formatter.print_error(f"Failed to upload file: {e}")
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


# Add subcommands to main app
app.add_typer(branches_app, name="branches")
app.add_typer(files_app, name="files")
app.add_typer(transactions_app, name="transactions")
app.add_typer(views_app, name="views")


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
