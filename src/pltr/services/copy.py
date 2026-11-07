"""
High-level service that copies Foundry resources between Compass folders.

``pltr cp`` copies a dataset (the files of one branch and their schema) or,
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
from typing import Any, Dict, List, Optional, Sequence, Set

from ..contract import ExitCode, PltrError, classify_error, info, success, warn
from .dataset import DatasetService
from .folder import FolderService
from .resource import ResourceService

#: ``Resource.type`` of the resources cp copies.
DATASET_TYPE = "FOUNDRY_DATASET"
FOLDER_TYPE = "COMPASS_FOLDER"

#: Dataframe readers ``put_schema`` accepts that cp picks from file extensions.
#: The API doesn't report the source dataset's reader; anything else gets the
#: API's default (PARQUET), which fits datasets that Foundry builds.
_READERS_BY_EXTENSION = {".csv": "CSV", ".avro": "AVRO"}


def dataframe_reader_for(paths: Sequence[str]) -> Optional[str]:
    """The dataframe reader for a copied schema, from the copied files' paths.

    ``CSV`` when every file is a ``.csv`` file, ``AVRO`` when every file is an
    ``.avro`` file, otherwise ``None`` (the API's default, PARQUET).
    """
    readers = {
        _READERS_BY_EXTENSION.get(PurePosixPath(path).suffix.lower()) for path in paths
    }
    if len(readers) == 1:
        return readers.pop()
    return None


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


@dataclass
class _CopiedFiles:
    """The committed transaction holding a dataset copy's files."""

    transaction_rid: str
    paths: List[str]


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
        #: RIDs of the folders and datasets this copy created.
        self._created: Set[str] = set()

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
        self._created = set()
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
            self._check_target_outside(source, target_folder_rid)
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

        new_dataset = self.dataset_service.create(
            new_name, parent_folder_rid=target_folder_rid
        )
        new_dataset_rid = new_dataset.rid
        self._created.add(new_dataset_rid)
        success(
            f"Created dataset '{new_name}' ({new_dataset_rid}) in {target_folder_rid}"
        )

        try:
            self._create_branch_on_copy(new_dataset_rid)
            copied = self._copy_dataset_files(dataset_rid, new_dataset_rid)
            if self.copy_schema:
                self._copy_dataset_schema(dataset_rid, new_dataset_rid, copied)
        except BaseException:
            # Trash the partly copied dataset, also on Ctrl-C (KeyboardInterrupt),
            # then report the failure.
            warn(f"Removing the partly copied dataset {new_dataset_rid}")
            try:
                self.resource_service.delete_resource(new_dataset_rid)
                info(f"  Moved dataset {new_dataset_rid} to the trash")
            except Exception as delete_exc:
                warn(
                    f"Could not remove dataset {new_dataset_rid}: "
                    f"{classify_error(delete_exc).message}"
                )
            raise

        self.result.stats.datasets += 1
        self.result.items.append(new_dataset)
        success(f"Finished copying dataset to {new_dataset_rid}")

    def _create_branch_on_copy(self, target_rid: str) -> None:
        """Create ``self.branch`` on the new dataset unless it already has it.

        ``Dataset.create`` creates only the default branch (master on most
        enrollments), and the files are committed on ``self.branch``. The
        branch is created without transactions.
        """
        try:
            # Iterating the SDK iterator reads every page of the branches.
            names = [b.name for b in self.dataset_service.list_branches(target_rid)]
            if self.branch in names:
                return
            self.dataset_service.create_branch(target_rid, self.branch)
        except Exception as exc:
            if self.debug:
                traceback.print_exc()
            raise RuntimeError(
                f"Failed to create branch '{self.branch}' on {target_rid}"
            ) from exc
        default = f" (its default branch is '{names[0]}')" if names else ""
        info(f"  Created branch '{self.branch}' on the copy{default}")

    def _copy_dataset_files(
        self, source_rid: str, target_rid: str
    ) -> Optional[_CopiedFiles]:
        """Copy the files of ``self.branch`` into one SNAPSHOT transaction.

        Returns the committed transaction and the copied paths, or ``None``
        when the source has no files on the branch (nothing is committed).
        """
        transaction_rid: Optional[str] = None
        try:
            # Iterating the SDK iterator reads every page of the listing.
            files = list(
                self.dataset_service.list_dataset_files(source_rid, branch=self.branch)
            )
            if not files:
                info(
                    f"  Source dataset has no files on branch '{self.branch}'; "
                    "the copy is empty"
                )
                return None

            transaction_rid = self.dataset_service.start_transaction(
                target_rid, transaction_type="SNAPSHOT", branch=self.branch
            ).rid
            paths: List[str] = []
            with tempfile.TemporaryDirectory(prefix="pltr-cp-") as tmpdir:
                temp_dir = Path(tmpdir)
                for index, file in enumerate(files):
                    # Named by a counter, not by the remote path: any remote
                    # name works, and none can point outside temp_dir.
                    download_path = temp_dir / f"file-{index}"
                    self.dataset_service.download_file(
                        source_rid, file.path, download_path, branch=self.branch
                    )
                    remote_path = PurePosixPath(file.path.lstrip("/")).as_posix()
                    # Into the open transaction: no branch (the API rejects both).
                    self.dataset_service.upload_file(
                        target_rid,
                        download_path,
                        remote_path,
                        transaction_rid=transaction_rid,
                    )
                    paths.append(remote_path)
                    info(f"  Copied dataset file: {file.path}")

            committed = self.dataset_service.commit_transaction(
                target_rid, transaction_rid
            )
            info(f"  Committed transaction {committed.rid}")
        except BaseException as exc:
            if transaction_rid is not None:
                try:
                    self.dataset_service.abort_transaction(target_rid, transaction_rid)
                    warn(f"Rolled back transaction {transaction_rid}")
                except Exception:
                    warn(f"Failed to roll back transaction {transaction_rid}")
            if not isinstance(exc, Exception):
                raise  # Ctrl-C (KeyboardInterrupt): rolled back, not an error

            if self.debug:
                traceback.print_exc()

            raise RuntimeError(
                f"Failed to copy the files of {source_rid} to {target_rid}"
            ) from exc
        return _CopiedFiles(transaction_rid=committed.rid, paths=paths)

    def _copy_dataset_schema(
        self, source_rid: str, target_rid: str, copied: Optional[_CopiedFiles]
    ) -> None:
        """Put the source's schema on the committed copy of its files.

        A schema applies to a committed transaction, so this runs after the
        files are committed, on the same branch. A source without a schema
        (``SchemaNotFound``) has nothing to copy; any other failure is raised.
        """
        if copied is None:
            info("  No files were copied, so there is no schema to copy either")
            return

        from foundry_sdk.v2.datasets.errors import SchemaNotFound

        reader = dataframe_reader_for(copied.paths)
        try:
            response = self.dataset_service.get_dataset_schema(
                source_rid, branch=self.branch
            )
            self.dataset_service.put_schema(
                target_rid,
                response.schema_,
                branch=self.branch,
                transaction_rid=copied.transaction_rid,
                dataframe_reader=reader,
            )
        except SchemaNotFound:
            info("  Source dataset has no schema to copy")
            return
        except Exception as exc:
            if self.debug:
                traceback.print_exc()
            raise RuntimeError(
                f"Failed to copy the schema of {source_rid} to {target_rid}"
            ) from exc
        info(f"  Copied dataset schema ({reader or 'PARQUET'} reader)")

    # ------------------------------------------------------------------ folders
    def _check_target_outside(self, folder: Any, target_folder_rid: str) -> None:
        """Refuse to copy a folder into itself or into a folder inside it.

        The copy is created before the source's children are listed, so it
        would be among them and be copied into itself without end. A
        ``Resource.path`` is the display names from the root joined by ``/``
        (names can't contain ``/``), so the target is inside the source when
        its path starts with the source's path and a ``/``.
        """
        where = "is that folder"
        if target_folder_rid != folder.rid:
            target = self.resource_service.get_resource(target_folder_rid)
            if target.path.startswith(folder.path.rstrip("/") + "/"):
                where = f"is inside it ({target.path})"
            elif target.rid != folder.rid:
                return
        raise PltrError(
            f"Can't copy folder '{folder.display_name}' ({folder.rid}) into "
            f"itself: the target {target_folder_rid} {where}.",
            error_type="usage_error",
            exit_code=ExitCode.USAGE,
            hint="Copy it into a folder outside it, such as its parent folder "
            f"{folder.parent_folder_rid}.",
        )

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
            self._created.add(new_folder_rid)
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
            if child.rid in self._created:
                # Never copy a copy (the target is inside the source after
                # all): it would copy itself again and again.
                self._skip(child.display_name, child.rid, "this copy created it")
                continue
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
