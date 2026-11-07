"""
High-level service that copies Foundry resources between Compass folders.

``pltr cp`` copies a dataset (its schema and the files of one branch) or,
recursively, a folder with its datasets and subfolders into a target folder.
Progress messages go to stderr through :mod:`pltr.contract`; the resources
created (or, in a dry run, the ones that would be copied) are returned to the
command, which prints them.
"""

from __future__ import annotations

import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional

from foundry_sdk.v2.datasets.models import Dataset

from ..contract import ExitCode, PltrError, classify_error, info, success, warn
from .dataset import DatasetService
from .folder import FolderService
from .resource import ResourceService

#: ``Resource.type`` of the resources cp copies.
DATASET_TYPE = "FOUNDRY_DATASET"
FOLDER_TYPE = "COMPASS_FOLDER"


@dataclass
class CopyStats:
    """Summary counts of a copy operation."""

    folders: int = 0
    datasets: int = 0
    skipped: int = 0
    errors: int = 0

    def as_dict(self) -> Dict[str, int]:
        """Return the counts as a dictionary."""
        return {
            "folders_copied": self.folders,
            "datasets_copied": self.datasets,
            "skipped": self.skipped,
            "errors": self.errors,
        }


@dataclass
class CopyResult:
    """What a copy did.

    ``items`` are the SDK models of the resources created, in creation order
    (``Folder`` for folders, ``Dataset`` for datasets). In a dry run nothing
    is created and ``items`` are the source ``Resource`` models that would be
    copied. ``failures`` holds the exception of every item that couldn't be
    copied while copying a folder recursively.
    """

    items: List[Any] = field(default_factory=list)
    stats: CopyStats = field(default_factory=CopyStats)
    failures: List[BaseException] = field(default_factory=list)


class _StopCopy(Exception):
    """Raised after the first failure when ``fail_fast`` is set."""


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
        fail_fast: bool = False,
    ):
        self.profile = profile
        self.branch = branch
        self.name_suffix = name_suffix
        self.copy_schema = copy_schema
        self.dry_run = dry_run
        self.debug = debug
        self.fail_fast = fail_fast

        self.dataset_service = DatasetService(profile=profile)
        self.folder_service = FolderService(profile=profile)
        self.resource_service = ResourceService(profile=profile)

        self.result = CopyResult()

    # ------------------------------------------------------------------ public
    def copy_resource(
        self, source_rid: str, target_folder_rid: str, recursive: bool = False
    ) -> CopyResult:
        """Copy a dataset or folder by RID into a destination folder.

        Args:
            source_rid: RID of the dataset or folder to copy.
            target_folder_rid: RID of the folder (or project) to copy into.
            recursive: required when copying a folder; copies its contents.

        Returns:
            A :class:`CopyResult`. Failures of individual items in a recursive
            copy are recorded in it (the copy goes on unless ``fail_fast``);
            a failure before anything was created is raised.
        """
        self.result = CopyResult()
        source = self.resource_service.get_resource(source_rid)

        if source.type == DATASET_TYPE:
            info(
                f"Copying dataset '{source.display_name}' ({source_rid}) to folder "
                f"{target_folder_rid}"
            )
            self._copy_dataset(source, target_folder_rid)
        elif source.type == FOLDER_TYPE:
            if not recursive:
                raise PltrError(
                    f"{source_rid} is a folder: pass --recursive to copy it with "
                    "its contents.",
                    error_type="usage_error",
                    exit_code=ExitCode.USAGE,
                )
            try:
                self._copy_folder(source, target_folder_rid)
            except _StopCopy:
                warn("Stopped at the first failure (--fail-fast).")
        else:
            raise PltrError(
                f"cp copies datasets and folders; {source_rid} is a {source.type}.",
                error_type="usage_error",
                exit_code=ExitCode.USAGE,
            )

        self._print_summary()
        return self.result

    # ----------------------------------------------------------------- datasets
    def _copy_dataset(self, source: Any, target_folder_rid: str) -> None:
        """Copy one dataset; raises on failure after cleaning up the copy."""
        dataset_rid = source.rid
        new_name = self._derive_name(source.display_name)

        if self.dry_run:
            info(
                f"[DRY-RUN] Would copy dataset '{source.display_name}' "
                f"({dataset_rid}) to '{new_name}' in folder {target_folder_rid}"
            )
            self.result.stats.datasets += 1
            self.result.items.append(source)
            return

        new_dataset = self.dataset_service.create_dataset(new_name, target_folder_rid)
        new_dataset_rid = new_dataset["rid"]
        success(
            f"Created dataset '{new_name}' ({new_dataset_rid}) in {target_folder_rid}"
        )

        try:
            if self.copy_schema:
                self._copy_dataset_schema(dataset_rid, new_dataset_rid)

            self._copy_dataset_files(dataset_rid, new_dataset_rid)
        except Exception:
            # Clean up the partly created dataset, then report the failure.
            warn(f"Removing the partly copied dataset {new_dataset_rid}")
            try:
                self.dataset_service.delete_dataset(new_dataset_rid)
                info(f"  Removed dataset {new_dataset_rid}")
            except Exception as delete_exc:
                warn(
                    f"Could not remove dataset {new_dataset_rid}: "
                    f"{classify_error(delete_exc).message}"
                )
            raise

        self.result.stats.datasets += 1
        self.result.items.append(
            Dataset(
                rid=new_dataset_rid, name=new_name, parent_folder_rid=target_folder_rid
            )
        )
        success(f"Finished copying dataset to {new_dataset_rid}")

    def _copy_dataset_schema(self, source_rid: str, target_rid: str) -> None:
        """Copy schema metadata, warning if not available."""
        try:
            schema_info = self.dataset_service.get_schema(source_rid)
            schema = schema_info.get("schema")
            if schema:
                self.dataset_service.put_schema(target_rid, schema)
                info("  Copied dataset schema")
            else:
                info("  Source dataset has no schema to copy")
        except Exception as exc:
            warn(
                f"Could not copy the schema of {source_rid}: "
                f"{classify_error(exc).message}"
            )
            if self.debug:
                traceback.print_exc()

    def _copy_dataset_files(self, source_rid: str, target_rid: str) -> None:
        """Download files from source and upload them into the target dataset."""
        files = self.dataset_service.list_files(source_rid, branch=self.branch)
        if not files:
            info("  Source dataset has no files on the requested branch")
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
                        self._skip(
                            "a file", source_rid, "File path missing; skipping file."
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
                    info(f"  Copied dataset file: {dataset_path}")

            self.dataset_service.commit_transaction(target_rid, transaction_rid)
            info(f"  Committed transaction {transaction_rid}")
        except Exception as exc:
            # Only attempt rollback if we successfully created a transaction
            if transaction_created and transaction_rid:
                try:
                    self.dataset_service.abort_transaction(target_rid, transaction_rid)
                    warn(f"Rolled back transaction {transaction_rid}")
                except Exception:
                    warn(f"Failed to roll back transaction {transaction_rid}")

            if self.debug:
                traceback.print_exc()

            raise RuntimeError(
                f"Failed to copy the files of {source_rid} to {target_rid}"
            ) from exc

    def _upload_dataset_file(
        self,
        dataset_rid: str,
        dataset_path: str,
        local_file: Path,
        transaction_rid: Optional[str],
    ) -> None:
        """Upload the downloaded file bytes into a dataset (``Dataset.File.upload``, GA)."""
        body = Path(local_file).read_bytes()
        remote_path = PurePosixPath(dataset_path.lstrip("/")).as_posix()
        # The API takes either a transaction or a branch, not both
        # (InvalidParameterCombination): send the branch only without one.
        self.dataset_service.service.Dataset.File.upload(
            dataset_rid,
            remote_path,
            body,
            transaction_rid=transaction_rid,
            branch_name=None if transaction_rid else self.branch,
        )

    # ------------------------------------------------------------------ folders
    def _copy_folder(self, folder: Any, target_folder_rid: str) -> None:
        """Copy a folder and its children; records the failures of children."""
        new_name = self._derive_name(folder.display_name)

        if self.dry_run:
            info(
                f"[DRY-RUN] Would copy folder '{folder.display_name}' ({folder.rid}) "
                f"to '{new_name}' in folder {target_folder_rid}"
            )
            self.result.items.append(folder)
            new_folder_rid = f"<new folder '{new_name}'>"
        else:
            created = self.folder_service.create_folder(new_name, target_folder_rid)
            self.result.items.append(created)
            new_folder_rid = created.rid
            success(
                f"Created folder '{new_name}' ({new_folder_rid}) in {target_folder_rid}"
            )

        self.result.stats.folders += 1

        try:
            # Iterating the SDK iterator reads every page of the children.
            children = list(self.folder_service.list_children(folder.rid))
        except Exception as exc:
            self._record_failure(folder, exc)
            return
        if not children:
            info(f"  Folder '{folder.display_name}' has no children to copy.")
            return

        for child in children:
            try:
                if child.type == FOLDER_TYPE:
                    self._copy_folder(child, new_folder_rid)
                elif child.type == DATASET_TYPE:
                    self._copy_dataset(child, new_folder_rid)
                else:
                    self._skip(
                        child.display_name,
                        child.rid,
                        f"cp doesn't copy {child.type} resources",
                    )
            except _StopCopy:
                raise
            except Exception as exc:
                self._record_failure(child, exc)

    def _record_failure(self, resource: Any, exc: BaseException) -> None:
        self.result.stats.errors += 1
        self.result.failures.append(exc)
        warn(
            f"Failed to copy '{resource.display_name}' ({resource.rid}): "
            f"{classify_error(exc).message}"
        )
        if self.debug:
            traceback.print_exception(type(exc), exc, exc.__traceback__)
        if self.fail_fast:
            raise _StopCopy() from exc

    # ------------------------------------------------------------------ helpers
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

    def _skip(self, name: str, rid: str, reason: str) -> None:
        """Track a skipped resource."""
        self.result.stats.skipped += 1
        warn(f"Skipped {name} ({rid}): {reason}")

    def _print_summary(self) -> None:
        """Print a one-line summary (stderr; suppressed in JSON mode)."""
        stats = self.result.stats
        verb = "Would copy" if self.dry_run else "Copied"
        success(
            f"{verb} {stats.folders} folder(s) and {stats.datasets} dataset(s); "
            f"{stats.skipped} skipped, {stats.errors} failed"
        )
