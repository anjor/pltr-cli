"""
Copy resources between Compass folders (``pltr cp``).
"""

from __future__ import annotations

import os
from typing import Any

import typer
from typing_extensions import Annotated

from ..contract import (
    Columns,
    FormatOption,
    OutputOption,
    ProfileOption,
    emit,
    pltr_command,
    warn,
)
from ..services.copy import DATASET_TYPE, FOLDER_TYPE, CopyService
from ..utils.completion import cache_rid, complete_rid


class CopyIncomplete(RuntimeError):
    """Some items of a recursive copy failed; the first failure is the cause."""


def _item_type(item: Any) -> str:
    from foundry_sdk.v2.datasets.models import Dataset
    from foundry_sdk.v2.filesystem.models import Folder

    if isinstance(item, Dataset):
        return DATASET_TYPE
    if isinstance(item, Folder):
        return FOLDER_TYPE
    return item.type  # a source Resource (dry run)


def _item_name(item: Any) -> str:
    from foundry_sdk.v2.datasets.models import Dataset

    return item.name if isinstance(item, Dataset) else item.display_name


#: Table/CSV columns for the created ``Folder``/``Dataset`` models (or, in a
#: dry run, the source ``Resource`` models).
COPY_COLUMNS: Columns = {
    "Type": _item_type,
    "Name": _item_name,
    "RID": "rid",
    "Parent Folder": "parent_folder_rid",
}


@pltr_command(
    sdk=(
        "filesystem.Resource.get",
        "filesystem.Folder.create",
        "filesystem.Folder.children",
        "datasets.Dataset.create",
        "datasets.Dataset.get_schema",
        "datasets.Dataset.put_schema",
        "datasets.Dataset.File.list",
        "datasets.Dataset.File.content",
        "datasets.Dataset.File.upload",
        "datasets.Dataset.Transaction.create",
        "datasets.Dataset.Transaction.commit",
        "datasets.Dataset.Transaction.abort",
        "filesystem.Resource.delete",
    )
)
def cp_command(
    source_rid: Annotated[
        str,
        typer.Argument(
            help="RID of the dataset or folder to copy.",
            autocompletion=complete_rid,
        ),
    ],
    target_folder_rid: Annotated[
        str,
        typer.Argument(
            help="RID of the folder or project to copy into.",
            autocompletion=complete_rid,
        ),
    ],
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Copy a folder with its contents (required when SOURCE_RID is a folder).",
        ),
    ] = False,
    branch: Annotated[
        str,
        typer.Option(
            "--branch", "-b", help="Branch whose files are copied, on both sides."
        ),
    ] = "master",
    name_suffix: Annotated[
        str,
        typer.Option(
            "--name-suffix", help="Suffix appended to the names of the copies."
        ),
    ] = "-copy",
    copy_schema: Annotated[
        bool,
        typer.Option(
            "--schema/--no-schema", help="Copy dataset schemas when available."
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Create nothing; list the resources that would be copied.",
        ),
    ] = False,
    fail_fast: Annotated[
        bool,
        typer.Option(
            "--fail-fast",
            help="Stop at the first item that fails when copying a folder.",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            hidden=True,
            help="Deprecated: set PLTR_DEBUG=1 to see tracebacks.",
        ),
    ] = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Copy a dataset, or a folder with its contents, into another folder.

    SOURCE_RID and TARGET_FOLDER_RID are RIDs, e.g.
    ri.foundry.main.dataset.<id> and ri.compass.main.folder.<id> (a project
    RID works as the target too). Copies get the name of the source plus
    --name-suffix.

    A dataset copy gets the files of --branch, committed in one SNAPSHOT
    transaction on the same branch of the copy. With --schema (the default)
    the source's schema on that branch is then put on the committed copy; a
    source without a schema is copied without one. The API doesn't report the
    source's dataframe reader: the schema gets CSV when every file is a .csv
    file, AVRO when every file is .avro, otherwise PARQUET (the API default).
    A source without files on the branch gives an empty copy with no schema.
    If any step fails, the partial copy is moved to the trash and pltr exits
    with the error; use --no-schema to copy only the files.

    A folder copy (--recursive) recreates its subfolders and datasets; other
    resource types are skipped with a warning.

    Prints the resources created: {"data": [...]} in JSON, with the API's
    Folder and Dataset fields. With --dry-run nothing is created and it
    prints the source resources that would be copied. If some items of a
    folder fail, the rest is still copied (unless --fail-fast); pltr then
    prints what was created and exits with the error of the first failure.
    """
    if debug:
        warn("--debug is deprecated; set PLTR_DEBUG=1 to see tracebacks.")
    service = CopyService(
        profile=profile,
        branch=branch,
        name_suffix=name_suffix,
        copy_schema=copy_schema,
        dry_run=dry_run,
        fail_fast=fail_fast,
        debug=debug or bool(os.environ.get("PLTR_DEBUG", "").strip()),
    )
    result = service.copy_resource(source_rid, target_folder_rid, recursive=recursive)
    cache_rid(source_rid)
    if not dry_run:
        for item in result.items[:50]:
            cache_rid(item.rid)
    emit(result.items, format=format, output=output, columns=COPY_COLUMNS)
    if result.failures:
        failed = len(result.failures)
        raise CopyIncomplete(
            f"{failed} item(s) could not be copied; the first failure was"
        ) from result.failures[0]
