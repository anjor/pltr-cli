"""
Progress bar utilities for long-running operations.
"""

from typing import Optional, Iterator, Any, Union
from pathlib import Path
from contextlib import contextmanager

from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    FileSizeColumn,
    TotalFileSizeColumn,
    TransferSpeedColumn,
    SpinnerColumn,
)


class FileProgressTracker:
    """Progress tracker for file operations."""

    def __init__(self, show_speed: bool = True):
        """
        Initialize progress tracker.

        Args:
            show_speed: Whether to show transfer speed
        """
        self.show_speed = show_speed
        self._progress: Optional[Progress] = None

    @contextmanager
    def track_upload(
        self, file_path: Union[str, Path], description: Optional[str] = None
    ) -> Iterator[Any]:
        """
        Context manager for tracking file upload progress.

        Args:
            file_path: Path to file being uploaded
            description: Optional description for progress bar

        Yields:
            Progress update function
        """
        file_path = Path(file_path)
        total_size = file_path.stat().st_size
        description = description or f"Uploading {file_path.name}"

        columns = [
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            FileSizeColumn(),
            TotalFileSizeColumn(),
            TimeRemainingColumn(),
        ]

        if self.show_speed:
            columns.append(TransferSpeedColumn())

        with Progress(*columns) as progress:
            self._progress = progress
            task_id = progress.add_task(description, total=total_size)

            def update_progress(bytes_transferred: int):
                """Update progress with bytes transferred."""
                progress.update(task_id, completed=bytes_transferred)

            try:
                yield update_progress
            finally:
                self._progress = None

    @contextmanager
    def track_download(
        self,
        target_path: Union[str, Path],
        total_size: Optional[int] = None,
        description: Optional[str] = None,
    ) -> Iterator[Any]:
        """
        Context manager for tracking file download progress.

        Args:
            target_path: Path where file will be saved
            total_size: Total file size in bytes (if known)
            description: Optional description for progress bar

        Yields:
            Progress update function
        """
        target_path = Path(target_path)
        description = description or f"Downloading {target_path.name}"

        columns = [
            TextColumn("[bold green]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ]

        if total_size:
            columns.extend(
                [
                    FileSizeColumn(),
                    TotalFileSizeColumn(),
                    TimeRemainingColumn(),
                ]
            )
            if self.show_speed:
                columns.append(TransferSpeedColumn())

        with Progress(*columns) as progress:
            self._progress = progress
            task_id = progress.add_task(description, total=total_size)

            def update_progress(bytes_transferred: int):
                """Update progress with bytes transferred."""
                progress.update(task_id, completed=bytes_transferred)

            try:
                yield update_progress
            finally:
                self._progress = None

    @contextmanager
    def track_operation(
        self, description: str, total: Optional[int] = None
    ) -> Iterator[Any]:
        """
        Context manager for tracking general operations.

        Args:
            description: Description of the operation
            total: Total number of items (if known)

        Yields:
            Progress update function
        """
        columns = [
            TextColumn("[bold yellow]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ]

        if total:
            columns.append(TimeRemainingColumn())

        with Progress(*columns) as progress:
            self._progress = progress
            task_id = progress.add_task(description, total=total)

            def update_progress(completed: int):
                """Update progress with completed items."""
                progress.update(task_id, completed=completed)

            try:
                yield update_progress
            finally:
                self._progress = None


class SpinnerProgressTracker:
    """Simple spinner for indeterminate operations."""

    def __init__(self):
        """Initialize spinner tracker."""
        self._progress: Optional[Progress] = None

    @contextmanager
    def track_spinner(self, description: str) -> Iterator[None]:
        """
        Context manager for showing a spinner during operations.

        Args:
            description: Description of the operation

        Yields:
            None (operation runs in context)
        """
        columns = [
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
        ]

        with Progress(*columns, transient=True) as progress:
            self._progress = progress
            progress.add_task(description)

            try:
                yield
            finally:
                self._progress = None


def create_file_chunks(
    file_path: Union[str, Path], chunk_size: int = 8192
) -> Iterator[bytes]:
    """
    Create file chunks for streaming upload with progress tracking.

    Args:
        file_path: Path to file to read
        chunk_size: Size of each chunk in bytes

    Yields:
        File chunks as bytes
    """
    file_path = Path(file_path)
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


class ProgressCallbackAdapter:
    """Adapter to convert progress callbacks to different formats."""

    def __init__(self, update_callback, total_size: Optional[int] = None):
        """
        Initialize adapter.

        Args:
            update_callback: Callback function to update progress
            total_size: Total size for percentage calculations
        """
        self.update_callback = update_callback
        self.total_size = total_size
        self.bytes_transferred = 0

    def __call__(self, chunk_size: int):
        """
        Update progress with new chunk.

        Args:
            chunk_size: Size of transferred chunk
        """
        self.bytes_transferred += chunk_size
        self.update_callback(self.bytes_transferred)

    def get_percentage(self) -> Optional[float]:
        """
        Get current progress percentage.

        Returns:
            Percentage complete (0-100) or None if total size unknown
        """
        if self.total_size and self.total_size > 0:
            return (self.bytes_transferred / self.total_size) * 100
        return None


# Utility functions for common progress patterns


def with_upload_progress(
    file_path: Union[str, Path], description: Optional[str] = None
) -> FileProgressTracker:
    """
    Create a progress tracker configured for file uploads.

    Args:
        file_path: Path to file being uploaded
        description: Optional description override

    Returns:
        Configured FileProgressTracker
    """
    return FileProgressTracker(show_speed=True)


def with_download_progress(show_speed: bool = True) -> FileProgressTracker:
    """
    Create a progress tracker configured for file downloads.

    Args:
        show_speed: Whether to show transfer speed

    Returns:
        Configured FileProgressTracker
    """
    return FileProgressTracker(show_speed=show_speed)


def with_spinner(description: str = "Working...") -> SpinnerProgressTracker:
    """
    Create a spinner for indeterminate operations.

    Args:
        description: Description of the operation

    Returns:
        Configured SpinnerProgressTracker
    """
    return SpinnerProgressTracker()


# Example usage patterns
"""
# File upload with progress
tracker = with_upload_progress("data.csv")
with tracker.track_upload("data.csv") as progress:
    # Upload file chunks
    for chunk in create_file_chunks("data.csv"):
        # ... upload chunk ...
        progress(len(chunk))

# File download with progress
tracker = with_download_progress()
with tracker.track_download("output.csv", total_size=1024000) as progress:
    # Download file
    bytes_downloaded = 0
    while not complete:
        # ... download chunk ...
        bytes_downloaded += chunk_size
        progress(bytes_downloaded)

# Indeterminate operation
spinner = with_spinner("Processing dataset...")
with spinner.track_spinner("Processing dataset..."):
    # ... long running operation ...
    pass
"""
