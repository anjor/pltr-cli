"""
Copy resources between Compass folders.
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from ..auth.base import MissingCredentialsError, ProfileNotFoundError
from ..services.copy import CopyService
from ..utils.completion import complete_profile, complete_rid
from ..utils.formatting import OutputFormatter


def cp_command(
    source_rid: str = typer.Argument(
        ...,
        help="Resource Identifier to copy (dataset or folder)",
        autocompletion=complete_rid,
    ),
    target_folder_rid: str = typer.Argument(
        ...,
        help="Destination Compass folder RID",
        autocompletion=complete_rid,
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="Authentication profile",
        autocompletion=complete_profile,
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Copy folder contents recursively (required when SOURCE_RID is a folder)",
    ),
    branch: str = typer.Option(
        "master",
        "--branch",
        "-b",
        help="Dataset branch to copy file-backed datasets from",
    ),
    name_suffix: str = typer.Option(
        "-copy",
        "--name-suffix",
        help="Suffix appended to cloned folder/dataset names",
    ),
    copy_schema: bool = typer.Option(
        True,
        "--schema/--no-schema",
        help="Copy dataset schemas when available",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Log actions without creating any resources",
    ),
    fail_fast: bool = typer.Option(
        False,
        "--fail-fast",
        help="Stop immediately on first error when copying folders recursively",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Print stack traces when errors occur",
    ),
):
    """Copy a resource identified by RID into another Compass folder."""
    console = Console()
    formatter = OutputFormatter(console)

    try:
        service = CopyService(
            profile=profile,
            branch=branch,
            name_suffix=name_suffix,
            copy_schema=copy_schema,
            dry_run=dry_run,
            fail_fast=fail_fast,
            debug=debug,
            console=console,
        )
        summary = service.copy_resource(
            source_rid, target_folder_rid, recursive=recursive
        )
        formatter.print_success("Copy operation completed")
        formatter.print_info(
            "Folders copied: {folders_copied} | Datasets copied: {datasets_copied} | "
            "Skipped: {skipped} | Errors: {errors}".format(**summary)
        )
    except (ProfileNotFoundError, MissingCredentialsError) as exc:
        formatter.print_error(f"Authentication error: {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        if debug:
            raise
        formatter.print_error(f"Failed to copy resource: {exc}")
        raise typer.Exit(1)
