"""
MediaSets commands for managing media sets and media content.
"""

import typer
from typing import Optional
from pathlib import Path
from rich.console import Console

from ..services.mediasets import MediaSetsService
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
console = Console()
formatter = OutputFormatter(console)


@app.command("get")
def get_media_item(
    media_set_rid: str = typer.Argument(
        ..., help="Media Set Resource Identifier", autocompletion=complete_rid
    ),
    media_item_rid: str = typer.Argument(
        ..., help="Media Item Resource Identifier", autocompletion=complete_rid
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
    preview: bool = typer.Option(False, "--preview", help="Enable preview mode"),
):
    """Get detailed information about a specific media item."""
    try:
        cache_rid(media_set_rid)
        cache_rid(media_item_rid)
        service = MediaSetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Fetching media item {media_item_rid}..."
        ):
            media_info = service.get_media_set_info(
                media_set_rid, media_item_rid, preview=preview
            )

        formatter.format_media_item_info(media_info, format, output)

        if output:
            formatter.print_success(f"Media item information saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get media item: {e}")
        raise typer.Exit(1)


@app.command("get-by-path")
def get_media_by_path(
    media_set_rid: str = typer.Argument(
        ..., help="Media Set Resource Identifier", autocompletion=complete_rid
    ),
    media_item_path: str = typer.Argument(
        ..., help="Path to media item within the media set"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
    branch: Optional[str] = typer.Option(None, "--branch", help="Branch name"),
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
    preview: bool = typer.Option(False, "--preview", help="Enable preview mode"),
):
    """Get media item RID by its path within the media set."""
    try:
        cache_rid(media_set_rid)
        service = MediaSetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Looking up media item at path {media_item_path}..."
        ):
            result = service.get_media_item_by_path(
                media_set_rid, media_item_path, branch_name=branch, preview=preview
            )

        formatter.format_media_path_lookup(result, format, output)

        if output:
            formatter.print_success(f"Media item lookup saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to lookup media item by path: {e}")
        raise typer.Exit(1)


@app.command("create")
def create_transaction(
    media_set_rid: str = typer.Argument(
        ..., help="Media Set Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
    branch: Optional[str] = typer.Option(None, "--branch", help="Branch name"),
    preview: bool = typer.Option(False, "--preview", help="Enable preview mode"),
):
    """Create a new transaction for uploading to a media set."""
    try:
        cache_rid(media_set_rid)
        service = MediaSetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Creating transaction..."):
            transaction_id = service.create_transaction(
                media_set_rid, branch_name=branch, preview=preview
            )

        formatter.print_success("Successfully created transaction")
        formatter.print_info(f"Transaction ID: {transaction_id}")
        formatter.print_info(
            "Use this transaction ID for uploads, then commit or abort as needed"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to create transaction: {e}")
        raise typer.Exit(1)


@app.command("commit")
def commit_transaction(
    media_set_rid: str = typer.Argument(
        ..., help="Media Set Resource Identifier", autocompletion=complete_rid
    ),
    transaction_id: str = typer.Argument(..., help="Transaction ID to commit"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
    preview: bool = typer.Option(False, "--preview", help="Enable preview mode"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Commit a transaction, making uploaded items available."""
    try:
        if not confirm:
            typer.confirm(
                f"Are you sure you want to commit transaction {transaction_id}?",
                abort=True,
            )

        service = MediaSetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Committing transaction {transaction_id}..."
        ):
            service.commit_transaction(media_set_rid, transaction_id, preview=preview)

        formatter.print_success(f"Successfully committed transaction {transaction_id}")
        formatter.print_info("Uploaded items are now available in the media set")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to commit transaction: {e}")
        raise typer.Exit(1)


@app.command("abort")
def abort_transaction(
    media_set_rid: str = typer.Argument(
        ..., help="Media Set Resource Identifier", autocompletion=complete_rid
    ),
    transaction_id: str = typer.Argument(..., help="Transaction ID to abort"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
    preview: bool = typer.Option(False, "--preview", help="Enable preview mode"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Abort a transaction, deleting any uploaded items."""
    try:
        if not confirm:
            typer.confirm(
                f"Are you sure you want to abort transaction {transaction_id}? This will delete uploaded items.",
                abort=True,
            )

        service = MediaSetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Aborting transaction {transaction_id}..."
        ):
            service.abort_transaction(media_set_rid, transaction_id, preview=preview)

        formatter.print_success(f"Successfully aborted transaction {transaction_id}")
        formatter.print_warning(
            "Any uploaded items in this transaction have been deleted"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to abort transaction: {e}")
        raise typer.Exit(1)


@app.command("upload")
def upload_media(
    media_set_rid: str = typer.Argument(
        ..., help="Media Set Resource Identifier", autocompletion=complete_rid
    ),
    file_path: str = typer.Argument(..., help="Local path to the file to upload"),
    media_item_path: str = typer.Argument(
        ..., help="Path within media set where file should be stored"
    ),
    transaction_id: str = typer.Argument(..., help="Transaction ID for the upload"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
    preview: bool = typer.Option(False, "--preview", help="Enable preview mode"),
):
    """Upload a media file to a media set within a transaction."""
    try:
        # Validate file exists
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            formatter.print_error(f"File not found: {file_path}")
            raise typer.Exit(1)

        cache_rid(media_set_rid)
        service = MediaSetsService(profile=profile)

        file_size = file_path_obj.stat().st_size
        formatter.print_info(
            f"Uploading {file_path} ({file_size} bytes) to {media_item_path}"
        )

        with SpinnerProgressTracker().track_spinner(
            f"Uploading {file_path_obj.name}..."
        ):
            service.upload_media(
                media_set_rid,
                file_path,
                media_item_path,
                transaction_id,
                preview=preview,
            )

        formatter.print_success(f"Successfully uploaded {file_path_obj.name}")
        formatter.print_info(f"Media item path: {media_item_path}")
        formatter.print_info(f"Transaction ID: {transaction_id}")
        formatter.print_warning(
            "Remember to commit the transaction to make the upload available"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except FileNotFoundError as e:
        formatter.print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to upload media: {e}")
        raise typer.Exit(1)


@app.command("download")
def download_media(
    media_set_rid: str = typer.Argument(
        ..., help="Media Set Resource Identifier", autocompletion=complete_rid
    ),
    media_item_rid: str = typer.Argument(
        ..., help="Media Item Resource Identifier", autocompletion=complete_rid
    ),
    output_path: str = typer.Argument(
        ..., help="Local path where file should be saved"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
    original: bool = typer.Option(
        False, "--original", help="Download original version instead of processed"
    ),
    preview: bool = typer.Option(False, "--preview", help="Enable preview mode"),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Overwrite existing file"
    ),
):
    """Download a media item from a media set."""
    try:
        # Check if output file already exists
        output_path_obj = Path(output_path)
        if output_path_obj.exists() and not overwrite:
            formatter.print_error(f"File already exists: {output_path}")
            formatter.print_info("Use --overwrite to replace existing file")
            raise typer.Exit(1)

        cache_rid(media_set_rid)
        cache_rid(media_item_rid)
        service = MediaSetsService(profile=profile)

        version_type = "original" if original else "processed"
        with SpinnerProgressTracker().track_spinner(
            f"Downloading {version_type} media item..."
        ):
            result = service.download_media(
                media_set_rid,
                media_item_rid,
                output_path,
                original=original,
                preview=preview,
            )

        formatter.print_success("Successfully downloaded media item")
        formatter.print_info(f"Saved to: {result['output_path']}")
        formatter.print_info(f"File size: {result['file_size']} bytes")
        formatter.print_info(
            f"Version: {'original' if result['original'] else 'processed'}"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to download media: {e}")
        raise typer.Exit(1)


@app.command("reference")
def get_media_reference(
    media_set_rid: str = typer.Argument(
        ..., help="Media Set Resource Identifier", autocompletion=complete_rid
    ),
    media_item_rid: str = typer.Argument(
        ..., help="Media Item Resource Identifier", autocompletion=complete_rid
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
    preview: bool = typer.Option(False, "--preview", help="Enable preview mode"),
):
    """Get a reference to a media item (e.g., for embedding)."""
    try:
        cache_rid(media_set_rid)
        cache_rid(media_item_rid)
        service = MediaSetsService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Getting reference for media item {media_item_rid}..."
        ):
            reference = service.get_media_reference(
                media_set_rid, media_item_rid, preview=preview
            )

        formatter.format_media_reference(reference, format, output)

        if output:
            formatter.print_success(f"Media reference saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get media reference: {e}")
        raise typer.Exit(1)


@app.callback()
def main():
    """
    MediaSets operations for managing media sets and media content.

    This module provides commands to:
    - Get media item information and references
    - Create, commit, and abort upload transactions
    - Upload media files to media sets
    - Download media items from media sets

    All operations require Resource Identifiers (RIDs) like:
    ri.mediasets.main.media-set.12345678-1234-1234-1234-123456789abc
    """
    pass
