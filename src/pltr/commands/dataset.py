"""
Dataset commands for pltr CLI.
"""

import typer
from typing import Optional
from pathlib import Path
from rich.console import Console

from ..services.dataset import DatasetService
from ..utils.formatting import OutputFormatter
from ..utils.progress import FileProgressTracker, SpinnerProgressTracker
from ..auth.base import ProfileNotFoundError, MissingCredentialsError

app = typer.Typer()
console = Console()
formatter = OutputFormatter(console)


@app.command("list")
def list_datasets(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Maximum number of datasets to return"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (table, json, csv)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """List datasets accessible to the user."""
    try:
        service = DatasetService(profile=profile)
        
        with SpinnerProgressTracker().track_spinner("Fetching datasets..."):
            datasets = service.list_datasets(limit=limit)
        
        if not datasets:
            formatter.print_info("No datasets found")
            return
            
        formatter.format_dataset_list(datasets, format, output)
        
        if output:
            formatter.print_success(f"Dataset list saved to {output}")
        else:
            formatter.print_info(f"Found {len(datasets)} dataset(s)")
            
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list datasets: {e}")
        raise typer.Exit(1)


@app.command("get")
def get_dataset(
    dataset_rid: str = typer.Argument(..., help="Dataset Resource Identifier"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (table, json, csv)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Get detailed information about a specific dataset."""
    try:
        service = DatasetService(profile=profile)
        
        with SpinnerProgressTracker().track_spinner(f"Fetching dataset {dataset_rid}..."):
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


@app.command("upload")
def upload_file(
    dataset_rid: str = typer.Argument(..., help="Dataset Resource Identifier"),
    file_path: str = typer.Argument(..., help="Path to file to upload"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    branch: str = typer.Option("master", "--branch", "-b", help="Dataset branch"),
    progress: bool = typer.Option(True, "--progress/--no-progress", help="Show progress bar"),
    transaction_rid: Optional[str] = typer.Option(None, "--transaction", "-t", help="Transaction RID"),
):
    """Upload a file to a dataset."""
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        formatter.print_error(f"File not found: {file_path}")
        raise typer.Exit(1)
    
    if not file_path_obj.is_file():
        formatter.print_error(f"Path is not a file: {file_path}")
        raise typer.Exit(1)
    
    try:
        service = DatasetService(profile=profile)
        
        if progress:
            tracker = FileProgressTracker()
            with tracker.track_upload(file_path_obj, f"Uploading {file_path_obj.name}"):
                result = service.upload_file(
                    dataset_rid=dataset_rid,
                    file_path=file_path_obj,
                    branch=branch,
                    transaction_rid=transaction_rid
                )
        else:
            with SpinnerProgressTracker().track_spinner(f"Uploading {file_path_obj.name}..."):
                result = service.upload_file(
                    dataset_rid=dataset_rid,
                    file_path=file_path_obj,
                    branch=branch,
                    transaction_rid=transaction_rid
                )
        
        formatter.print_success(f"Successfully uploaded {file_path_obj.name} to dataset {dataset_rid}")
        formatter.print_info(f"Branch: {result['branch']}")
        formatter.print_info(f"File size: {formatter._format_file_size(result['size_bytes'])}")
        
        if result.get('transaction_rid'):
            formatter.print_info(f"Transaction: {result['transaction_rid']}")
            
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to upload file: {e}")
        raise typer.Exit(1)


@app.command("download")
def download_file(
    dataset_rid: str = typer.Argument(..., help="Dataset Resource Identifier"),
    file_path: str = typer.Argument(..., help="Path of file within dataset"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    branch: str = typer.Option("master", "--branch", "-b", help="Dataset branch"),
    progress: bool = typer.Option(True, "--progress/--no-progress", help="Show progress bar"),
):
    """Download a file from a dataset."""
    # Determine output path
    if output:
        output_path = Path(output)
    else:
        output_path = Path.cwd() / Path(file_path).name
    
    try:
        service = DatasetService(profile=profile)
        
        if progress:
            tracker = FileProgressTracker()
            with tracker.track_download(output_path, description=f"Downloading {Path(file_path).name}"):
                result = service.download_file(
                    dataset_rid=dataset_rid,
                    file_path=file_path,
                    output_path=output_path,
                    branch=branch
                )
        else:
            with SpinnerProgressTracker().track_spinner(f"Downloading {Path(file_path).name}..."):
                result = service.download_file(
                    dataset_rid=dataset_rid,
                    file_path=file_path,
                    output_path=output_path,
                    branch=branch
                )
        
        formatter.print_success(f"Successfully downloaded {file_path} to {output_path}")
        formatter.print_info(f"Branch: {result['branch']}")
        formatter.print_info(f"File size: {formatter._format_file_size(result['size_bytes'])}")
        
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to download file: {e}")
        raise typer.Exit(1)


@app.command("files")
def list_files(
    dataset_rid: str = typer.Argument(..., help="Dataset Resource Identifier"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    branch: str = typer.Option("master", "--branch", "-b", help="Dataset branch"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (table, json, csv)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """List files in a dataset."""
    try:
        service = DatasetService(profile=profile)
        
        with SpinnerProgressTracker().track_spinner(f"Listing files in dataset {dataset_rid}..."):
            files = service.list_files(dataset_rid=dataset_rid, branch=branch)
        
        if not files:
            formatter.print_info(f"No files found in dataset {dataset_rid} on branch {branch}")
            return
            
        formatter.format_file_list(files, format, output)
        
        if output:
            formatter.print_success(f"File list saved to {output}")
        else:
            formatter.print_info(f"Found {len(files)} file(s) in dataset {dataset_rid}")
            
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list files: {e}")
        raise typer.Exit(1)


@app.command("create")
def create_dataset(
    name: str = typer.Argument(..., help="Dataset name"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    parent_folder: Optional[str] = typer.Option(None, "--parent-folder", help="Parent folder RID"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (table, json, csv)"),
):
    """Create a new dataset."""
    try:
        service = DatasetService(profile=profile)
        
        with SpinnerProgressTracker().track_spinner(f"Creating dataset '{name}'..."):
            dataset = service.create_dataset(name=name, parent_folder_rid=parent_folder)
        
        formatter.print_success(f"Successfully created dataset '{name}'")
        formatter.print_info(f"Dataset RID: {dataset['rid']}")
        
        # Show dataset details
        formatter.format_dataset_detail(dataset, format)
        
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create dataset: {e}")
        raise typer.Exit(1)


@app.command("delete")
def delete_dataset(
    dataset_rid: str = typer.Argument(..., help="Dataset Resource Identifier"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Delete a dataset."""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete dataset {dataset_rid}?")
        if not confirm:
            formatter.print_info("Deletion cancelled")
            return
    
    try:
        service = DatasetService(profile=profile)
        
        with SpinnerProgressTracker().track_spinner(f"Deleting dataset {dataset_rid}..."):
            success = service.delete_dataset(dataset_rid)
        
        if success:
            formatter.print_success(f"Successfully deleted dataset {dataset_rid}")
        else:
            formatter.print_error(f"Failed to delete dataset {dataset_rid}")
            raise typer.Exit(1)
        
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to delete dataset: {e}")
        raise typer.Exit(1)


@app.command("branches")
def list_branches(
    dataset_rid: str = typer.Argument(..., help="Dataset Resource Identifier"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (table, json, csv)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """List branches for a dataset."""
    try:
        service = DatasetService(profile=profile)
        
        with SpinnerProgressTracker().track_spinner(f"Listing branches for dataset {dataset_rid}..."):
            branches = service.get_branches(dataset_rid)
        
        if not branches:
            formatter.print_info(f"No branches found for dataset {dataset_rid}")
            return
            
        formatter.format_output(branches, format, output)
        
        if output:
            formatter.print_success(f"Branch list saved to {output}")
        else:
            formatter.print_info(f"Found {len(branches)} branch(es) for dataset {dataset_rid}")
            
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list branches: {e}")
        raise typer.Exit(1)


@app.command("create-branch")
def create_branch(
    dataset_rid: str = typer.Argument(..., help="Dataset Resource Identifier"),
    branch_name: str = typer.Argument(..., help="Name for the new branch"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name"),
    parent_branch: str = typer.Option("master", "--parent", help="Parent branch to branch from"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (table, json, csv)"),
):
    """Create a new branch for a dataset."""
    try:
        service = DatasetService(profile=profile)
        
        with SpinnerProgressTracker().track_spinner(f"Creating branch '{branch_name}' for dataset {dataset_rid}..."):
            branch = service.create_branch(
                dataset_rid=dataset_rid,
                branch_name=branch_name,
                parent_branch=parent_branch
            )
        
        formatter.print_success(f"Successfully created branch '{branch_name}'")
        formatter.print_info(f"Parent branch: {parent_branch}")
        
        # Show branch details
        formatter.format_output([branch], format)
        
    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create branch: {e}")
        raise typer.Exit(1)