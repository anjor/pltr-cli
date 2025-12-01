"""
High-level service that copies Foundry resources between Compass folders.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional
import tempfile
import traceback

from rich.console import Console

from .dataset import DatasetService
from .folder import FolderService
from .resource import ResourceService


# Known resource types for exact matching (avoids false positives with substring matching)
DATASET_TYPES = frozenset({"foundry_dataset", "dataset"})
FOLDER_TYPES = frozenset({"folder", "compass_folder"})


@dataclass
class CopyStats:
    """Summary of a copy operation."""

    folders: int = 0
    datasets: int = 0
    skipped: int = 0
    errors: int = 0

    def as_dict(self) -> Dict[str, int]:
        """Return summary as a dictionary."""
        return {
            "folders_copied": self.folders,
            "datasets_copied": self.datasets,
            "skipped": self.skipped,
            "errors": self.errors,
        }


class CopyService:
    """Copy datasets or folders (and their children) into another Compass folder."""

    def __init__(
        self,
        *,
        profile: Optional[str] = None,
        branch: str = "master",
        name_suffix: str = "-copy",
        copy_schema: bool = True,
        dry_run: bool = False,
        debug: bool = False,
        console: Optional[Console] = None,
    ):
        self.profile = profile
        self.branch = branch
        self.name_suffix = name_suffix
        self.copy_schema = copy_schema
        self.dry_run = dry_run
        self.debug = debug
        self.console = console or Console()

        self.dataset_service = DatasetService(profile=profile)
        self.folder_service = FolderService(profile=profile)
        self.resource_service = ResourceService(profile=profile)

        self.stats = CopyStats()
        self._skipped_messages: List[str] = []

    # ------------------------------------------------------------------ public
    def copy_resource(
        self, source_rid: str, target_folder_rid: str, recursive: bool = False
    ) -> Dict[str, int]:
        """
        Copy a resource by RID into a destination folder.

        Args:
            source_rid: Resource Identifier to copy.
            target_folder_rid: Destination Compass folder RID.
            recursive: Required when copying folders. Recursively copies contents.

        Returns:
            Dictionary summary of copied items.
        """
        self._reset_stats()

        resource = self.resource_service.get_resource(source_rid)
        resource_type = (resource.get("type") or "").lower()

        if resource_type in DATASET_TYPES:
            self._log_info(
                f"Copying dataset '{self._get_resource_name(resource)}' "
                f"({source_rid}) → folder {target_folder_rid}"
            )
            try:
                self._copy_dataset(resource, target_folder_rid)
            except Exception:
                self.stats.errors += 1
                raise
        elif resource_type in FOLDER_TYPES:
            if not recursive:
                raise RuntimeError(
                    "Source resource is a folder. Pass --recursive to copy folder contents."
                )
            try:
                self._copy_folder(resource, target_folder_rid)
            except Exception:
                self.stats.errors += 1
                raise
        else:
            raise RuntimeError(
                f"Copy is only supported for datasets and folders. Resource "
                f"{source_rid} is of type '{resource.get('type')}'."
            )

        self._print_summary()
        return self.stats.as_dict()

    # ----------------------------------------------------------------- datasets
    def _copy_dataset(
        self, dataset_info: Dict[str, str], target_folder_rid: str
    ) -> None:
        dataset_rid = dataset_info["rid"]
        dataset_name = self._get_resource_name(dataset_info)
        new_name = self._derive_name(dataset_name)

        if self.dry_run:
            self._log_warning(
                f"[DRY-RUN] Would copy dataset '{dataset_name}' ({dataset_rid}) "
                f"→ '{new_name}' in folder {target_folder_rid}"
            )
            self.stats.datasets += 1
            return

        new_dataset = self.dataset_service.create_dataset(new_name, target_folder_rid)
        new_dataset_rid = new_dataset["rid"]
        self._log_success(
            f"Created dataset '{new_name}' ({new_dataset_rid}) in {target_folder_rid}"
        )

        if self.copy_schema:
            self._copy_dataset_schema(dataset_rid, new_dataset_rid)

        self._copy_dataset_files(dataset_rid, new_dataset_rid)
        self.stats.datasets += 1
        self._log_success(f"Finished copying dataset to {new_dataset_rid}")

    def _copy_dataset_schema(self, source_rid: str, target_rid: str) -> None:
        """Copy schema metadata, warning if not available."""
        try:
            schema_info = self.dataset_service.get_schema(source_rid)
            schema = schema_info.get("schema")
            if schema:
                self.dataset_service.put_schema(target_rid, schema)
                self._log_info("  Copied dataset schema")
            else:
                self._log_info("  Source dataset has no schema to copy")
        except Exception as exc:
            self._log_warning(f"  Could not copy schema for {source_rid}: {exc}")
            if self.debug:
                traceback.print_exc()

    def _copy_dataset_files(self, source_rid: str, target_rid: str) -> None:
        """Download files from source and upload them into the target dataset."""
        files = self.dataset_service.list_files(source_rid, branch=self.branch)
        if not files:
            self._log_info(
                "  Source dataset does not expose any files on the requested branch"
            )
            return

        # Wrap transaction creation in try block to ensure cleanup on any failure
        transaction_rid = None
        transaction_created = False
        try:
            transaction = self.dataset_service.create_transaction(
                target_rid, branch=self.branch, transaction_type="SNAPSHOT"
            )
            # Check both possible key names for the transaction RID
            transaction_rid = transaction.get("transaction_rid") or transaction.get(
                "rid"
            )
            if not transaction_rid:
                raise RuntimeError(
                    f"Transaction response missing RID: {list(transaction.keys())}"
                )
            transaction_created = True

            with tempfile.TemporaryDirectory(prefix="pltr-cp-") as tmpdir:
                temp_dir = Path(tmpdir)
                for file_info in files:
                    dataset_path = file_info.get("path")
                    if not dataset_path:
                        self._report_skip(
                            {
                                "rid": source_rid,
                                "display_name": dataset_path or "unknown file",
                            },
                            "File path missing; skipping file.",
                        )
                        continue

                    local_rel_path = self._sanitize_local_path(dataset_path)
                    download_path = temp_dir / local_rel_path
                    download_path.parent.mkdir(parents=True, exist_ok=True)

                    self.dataset_service.download_file(
                        source_rid, dataset_path, download_path, branch=self.branch
                    )
                    self._upload_dataset_file(
                        target_rid, dataset_path, download_path, transaction_rid
                    )
                    self._log_info(f"  Copied dataset file: {dataset_path}")

            self.dataset_service.commit_transaction(target_rid, transaction_rid)
            self._log_info(f"  Committed transaction {transaction_rid}")
        except Exception as exc:
            # Only attempt rollback if we successfully created a transaction
            if transaction_created and transaction_rid:
                try:
                    self.dataset_service.abort_transaction(target_rid, transaction_rid)
                    self._log_warning(f"  Rolled back transaction {transaction_rid}")
                except Exception:
                    self._log_warning(
                        f"  Failed to roll back transaction {transaction_rid}"
                    )

            if self.debug:
                traceback.print_exc()

            raise RuntimeError(
                f"{type(exc).__name__} while copying files from {source_rid} to {target_rid}: {exc}"
            ) from exc

    def _upload_dataset_file(
        self,
        dataset_rid: str,
        dataset_path: str,
        local_file: Path,
        transaction_rid: str,
    ) -> None:
        """Upload the downloaded file bytes back into a dataset."""
        with open(local_file, "rb") as handle:
            body = handle.read()

        remote_path = PurePosixPath(dataset_path.lstrip("/")).as_posix()
        upload_kwargs = {
            "dataset_rid": dataset_rid,
            "file_path": remote_path,
            "body": body,
            "transaction_rid": transaction_rid,
        }
        # API only allows either branchName or transactionRid. When using a transaction
        # we must omit branchName to avoid InvalidParameterCombination.
        if not transaction_rid:
            upload_kwargs["branch_name"] = self.branch

        self.dataset_service.service.Dataset.File.upload(**upload_kwargs)

    # ------------------------------------------------------------------ folders
    def _copy_folder(self, folder_info: Dict[str, str], target_folder_rid: str) -> None:
        folder_rid = folder_info["rid"]
        folder_name = self._get_resource_name(folder_info)
        new_name = self._derive_name(folder_name)

        if self.dry_run:
            self._log_warning(
                f"[DRY-RUN] Would copy folder '{folder_name}' ({folder_rid}) "
                f"→ '{new_name}' in folder {target_folder_rid}"
            )
            new_folder_rid = "<dry-run>"
        else:
            created = self.folder_service.create_folder(new_name, target_folder_rid)
            new_folder_rid = created["rid"]
            self._log_success(
                f"Created folder '{new_name}' ({new_folder_rid}) in {target_folder_rid}"
            )

        self.stats.folders += 1

        children = self.folder_service.list_children(folder_rid)
        if not children:
            self._log_info("  Folder has no children to copy.")
            return

        for child in children:
            resource_type_raw = child.get("type") or ""
            resource_type = resource_type_raw.lower()

            try:
                if resource_type in FOLDER_TYPES:
                    self._copy_folder(child, new_folder_rid)
                elif resource_type in DATASET_TYPES:
                    self._copy_dataset(child, new_folder_rid)
                else:
                    self._report_skip(
                        child, f"Unsupported child type '{resource_type_raw}'"
                    )
            except Exception as exc:
                self.stats.errors += 1
                self._log_error(
                    f"Failed to copy child {child.get('rid', 'unknown RID')}: {exc}"
                )
                if self.debug:
                    traceback.print_exc()

    # ------------------------------------------------------------------ helpers
    def _get_resource_name(self, resource: Dict[str, str]) -> str:
        """Extract display name from a resource, with fallbacks."""
        return (
            resource.get("display_name")
            or resource.get("name")
            or resource.get("rid", "unknown")
        )

    def _sanitize_local_path(self, original_path: str) -> str:
        """Return a safe relative path for storing temporary files."""
        # Check for path traversal BEFORE normalization to prevent attacks
        if ".." in original_path:
            raise ValueError(f"Path traversal detected: {original_path}")
        clean = PurePosixPath(original_path.lstrip("/"))
        # Verify no parent directory references remain after normalization
        if ".." in clean.parts:
            raise ValueError(f"Invalid path after normalization: {original_path}")
        return clean.as_posix()

    def _derive_name(self, base_name: str) -> str:
        """Append the configured suffix if provided."""
        suffix = self.name_suffix or ""
        if not suffix:
            return base_name
        if base_name.endswith(suffix):
            return base_name
        return f"{base_name}{suffix}"

    def _report_skip(self, resource: Dict[str, str], reason: str) -> None:
        """Track skipped resources."""
        rid = resource.get("rid", "unknown RID")
        display_name = resource.get("display_name") or resource.get("name") or rid
        message = f"[SKIP] {display_name} ({rid}): {reason}"
        self.console.print(message)
        self.stats.skipped += 1
        self._skipped_messages.append(message)

    def _reset_stats(self) -> None:
        self.stats = CopyStats()
        self._skipped_messages = []

    def _print_summary(self) -> None:
        """Print summary after an operation."""
        self.console.print(
            "\nSummary: "
            f"{self.stats.folders} folders copied, "
            f"{self.stats.datasets} datasets copied, "
            f"{self.stats.skipped} resources skipped, "
            f"{self.stats.errors} errors"
        )

    # ------------------------------------------------------------------ logging
    def _log_info(self, message: str) -> None:
        self.console.print(message)

    def _log_warning(self, message: str) -> None:
        self.console.print(f"[yellow]{message}[/yellow]")

    def _log_error(self, message: str) -> None:
        self.console.print(f"[red]{message}[/red]")

    def _log_success(self, message: str) -> None:
        self.console.print(f"[green]{message}[/green]")
