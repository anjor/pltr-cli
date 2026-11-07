"""
Dataset commands (Foundry datasets API).
"""

import ntpath
import posixpath
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Any, List, Optional, Tuple, TypeVar

import click
import typer
from typing_extensions import Annotated

from ..contract import (
    AllPagesOption,
    Columns,
    FormatOption,
    MaxPagesOption,
    OutputOption,
    PageSizeOption,
    PageTokenOption,
    PltrError,
    ProfileOption,
    YesOption,
    collect_pages,
    confirm_destructive,
    emit,
    emit_bytes,
    info,
    load_json_input,
    pltr_command,
    spinner,
    success,
    table_rows,
    warn,
)
from ..services.dataset import (
    DATAFRAME_READERS,
    SCHEMA_INFERENCE_ENDPOINT,
    SCHEMA_METADATA_ENDPOINT,
    TRANSACTION_TYPES,
    BackingDataset,
    DatasetService,
)
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()
branches_app = typer.Typer()
files_app = typer.Typer()
transactions_app = typer.Typer()
views_app = typer.Typer()
schema_app = typer.Typer()
schedules_app = typer.Typer()
jobs_app = typer.Typer()


# ------------------------------------------------------------------ columns


def _identity(value: Any) -> Any:
    return value


def _field_type(field: Any) -> str:
    """A ``DatasetFieldSchema``'s type, with its parameters (e.g. ARRAY<LONG>)."""
    kind = field.type
    if kind == "DECIMAL" and field.precision is not None:
        return f"DECIMAL({field.precision},{field.scale or 0})"
    if kind == "ARRAY" and field.array_subtype is not None:
        return f"ARRAY<{_field_type(field.array_subtype)}>"
    if kind == "MAP" and field.map_key_type is not None:
        value_type = _field_type(field.map_value_type) if field.map_value_type else "?"
        return f"MAP<{_field_type(field.map_key_type)},{value_type}>"
    if kind == "STRUCT" and field.sub_schemas:
        members = ",".join(
            f"{sub.name}:{_field_type(sub)}" for sub in field.sub_schemas
        )
        return f"STRUCT<{members}>"
    return str(kind)


def _count_fields(schema: Any) -> str:
    count = len(schema.field_schema_list)
    return f"{count} field" if count == 1 else f"{count} fields"


def _describe_field(field: Any) -> str:
    """``name: TYPE``, plus ``(nullable)``, for a ``DatasetFieldSchema``."""
    nullable = " (nullable)" if field.nullable else ""
    return f"{field.name}: {_field_type(field)}{nullable}"


def _backing_datasets(view: Any) -> str:
    return ", ".join(
        f"{backing.dataset_rid}@{backing.branch}"
        if backing.branch
        else backing.dataset_rid
        for backing in view.backing_datasets
    )


def _primary_key(view: Any) -> Optional[str]:
    key = view.primary_key
    if key is None:
        return None
    resolution = key.resolution
    if resolution.type == "unique":
        detail = "unique"
    else:
        strategy = resolution.resolution_strategy
        detail = f"duplicates resolved by latest {', '.join(strategy.columns)}"
        if resolution.deletion_column:
            detail += f"; deletion column {resolution.deletion_column}"
    return f"{', '.join(key.columns)} ({detail})"


#: Table/CSV columns for a ``Dataset`` model.
DATASET_COLUMNS: Columns = {
    "RID": "rid",
    "Name": "name",
    "Parent Folder": "parent_folder_rid",
}

#: Table/CSV columns for a ``Branch`` model.
BRANCH_COLUMNS: Columns = {
    "Name": "name",
    "Transaction RID": "transaction_rid",
}

#: Table/CSV columns for a ``File`` model.
FILE_COLUMNS: Columns = {
    "Path": "path",
    "Size (bytes)": "size_bytes",
    "Updated": "updated_time",
    "Transaction RID": "transaction_rid",
}

#: Table/CSV columns for a ``Transaction`` model.
TRANSACTION_COLUMNS: Columns = {
    "RID": "rid",
    "Type": "transaction_type",
    "Status": "status",
    "Created": "created_time",
    "Closed": "closed_time",
}

#: Table/CSV columns for the fields of a schema (``DatasetFieldSchema``).
FIELD_COLUMNS: Columns = {
    "Name": "name",
    "Type": _field_type,
    "Nullable": "nullable",
}

#: Table/CSV columns for a ``View`` model.
VIEW_COLUMNS: Columns = {
    "View Name": "view_name",
    "RID": "dataset_rid",
    "Parent Folder": "parent_folder_rid",
    "Branch": "branch",
    "Backing Datasets": _backing_datasets,
    "Primary Key": _primary_key,
}

#: Table/CSV columns for ``dataset jobs list`` (``JobDetails`` has only the RID).
JOB_COLUMNS: Columns = {"Job RID": "job_rid"}

#: Table/CSV columns for ``dataset schedules list`` (the API returns RIDs).
SCHEDULE_COLUMNS: Columns = {"Schedule RID": _identity}

#: Table/CSV columns for ``dataset transactions build`` (a build RID).
BUILD_COLUMNS: Columns = {"Build RID": _identity}


# -------------------------------------------------------------- arguments

DatasetRid = Annotated[
    str,
    typer.Argument(
        help="Dataset RID (ri.foundry.main.dataset.<id>).",
        autocompletion=complete_rid,
    ),
]
ViewRid = Annotated[
    str,
    typer.Argument(
        help="View RID (views are datasets: ri.foundry.main.dataset.<id>).",
        autocompletion=complete_rid,
    ),
]
TransactionRid = Annotated[
    str,
    typer.Argument(help="Transaction RID (ri.foundry.main.transaction.<id>)."),
]
BranchName = Annotated[str, typer.Argument(help="Branch name, e.g. master.")]


def _dataset_path(value: str) -> str:
    """Dataset file paths never start with / (the API rejects them): drop it."""
    return value.lstrip("/")


FilePathArgument = Annotated[
    str,
    typer.Argument(
        help="Path of the file in the dataset, e.g. data/sales.csv.",
        callback=_dataset_path,
    ),
]
BranchOption = Annotated[
    Optional[str],
    typer.Option(
        "--branch",
        help="Branch name (default: the dataset's default branch, master on "
        "most enrollments).",
        show_default=False,
    ),
]
StartTransactionOption = Annotated[
    Optional[str],
    typer.Option(
        "--start-transaction-rid",
        help="Start of a transaction range (RID); with --end-transaction-rid "
        "set to the same RID, only that transaction's files.",
        show_default=False,
    ),
]
EndTransactionOption = Annotated[
    Optional[str],
    typer.Option(
        "--end-transaction-rid",
        help="Read the dataset as of this transaction (RID).",
        show_default=False,
    ),
]
ParentFolderOption = Annotated[
    str,
    typer.Option(
        "--parent-folder",
        help="RID of the project or folder to create it in "
        "(ri.compass.main.folder.<id>); find one with 'pltr project list' or "
        "'pltr folder list'.",
        autocompletion=complete_rid,
    ),
]


def _backing_dataset(value: str, param_hint: str) -> BackingDataset:
    """Parse ``DATASET_RID`` or ``DATASET_RID@BRANCH``."""
    dataset_rid, separator, branch = value.partition("@")
    if not dataset_rid or (separator and not branch):
        raise typer.BadParameter(
            f"expected DATASET_RID or DATASET_RID@BRANCH, got {value!r}",
            param_hint=param_hint,
        )
    return dataset_rid, branch or None


# ------------------------------------------------------------- datasets


@app.command("get")
@pltr_command(sdk="datasets.Dataset.get")
def get_dataset(
    dataset_rid: DatasetRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a dataset's metadata: its RID, name and parent folder."""
    with spinner(f"Fetching dataset {dataset_rid}..."):
        dataset = DatasetService(profile=profile).get_dataset(dataset_rid)
    cache_rid(dataset_rid)
    emit(
        dataset, format=format, output=output, columns=DATASET_COLUMNS, title="Dataset"
    )


@app.command("create")
@pltr_command(sdk="datasets.Dataset.create")
def create_dataset(
    name: Annotated[str, typer.Argument(help="Name of the new dataset.")],
    parent_folder: ParentFolderOption,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create an empty dataset in a project or folder."""
    with spinner(f"Creating dataset '{name}'..."):
        dataset = DatasetService(profile=profile).create(
            name=name, parent_folder_rid=parent_folder
        )
    cache_rid(dataset.rid)
    success(f"Created dataset '{dataset.name}' ({dataset.rid})")
    emit(
        dataset, format=format, output=output, columns=DATASET_COLUMNS, title="Dataset"
    )


@app.command("preview")
@pltr_command(sdk="datasets.Dataset.read_table")
def preview_dataset(
    dataset_rid: DatasetRid,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", min=1, help="Maximum number of rows to read."),
    ] = 10,
    columns: Annotated[
        Optional[List[str]],
        typer.Option(
            "--column",
            help="Only read this column (repeat for several; default: all).",
            show_default=False,
        ),
    ] = None,
    branch: BranchOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Read rows of a dataset as a table, JSON or CSV.

    Reads up to --limit rows with Dataset.read_table (Arrow format); the API
    doesn't guarantee row order and can't read views. JSON output is
    {"data": [{"<column>": <value>, ...}, ...]}; BINARY values are base64.
    Datasets that aren't stored as Parquet can be read up to 1,000,000 rows.
    """
    with spinner(f"Reading up to {limit} rows of {dataset_rid}..."):
        table = DatasetService(profile=profile).preview_table(
            dataset_rid, limit=limit, branch=branch, columns=columns or None
        )
    cache_rid(dataset_rid)
    row_columns, rows = table_rows(table)
    emit(rows, format=format, output=output, columns=row_columns)


# --------------------------------------------------------------- schema


def _parse_schema(document: Any, param_hint: str) -> Any:
    """A ``DatasetSchema`` from JSON input.

    Accepts the API's schema (``{"fieldSchemaList": [...]}``), the JSON
    output of ``pltr dataset schema get`` (``{"schema": {...}, ...}``) and
    pltr's older shorthand (``{"fields": [{"name", "type", "nullable"}]}``,
    nullable defaults to true).
    """
    import pydantic
    from foundry_sdk.v2.core.models import DatasetSchema

    if isinstance(document, dict) and "fieldSchemaList" not in document:
        if isinstance(document.get("schema"), dict):
            document = document["schema"]
        elif isinstance(document.get("fields"), list):
            document = {
                "fieldSchemaList": [
                    {"nullable": True, **field} if isinstance(field, dict) else field
                    for field in document["fields"]
                ]
            }
    try:
        return DatasetSchema.model_validate(document)
    except pydantic.ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'schema'}: {error['msg']}"
            for error in exc.errors()[:3]
        )
        raise typer.BadParameter(
            f"not a valid dataset schema ({problems})", param_hint=param_hint
        ) from exc


def _emit_schema(response: Any, dataset_rid: str, format: str, output: Optional[str]):
    info(
        f"Schema of {dataset_rid} on branch {response.branch_name} "
        f"(version {response.version_id}, transaction {response.end_transaction_rid})"
    )
    emit(
        response,
        format=format,
        output=output,
        columns=FIELD_COLUMNS,
        rows=lambda schema: schema.schema_.field_schema_list,
    )


@schema_app.command("get")
@pltr_command(sdk="datasets.Dataset.get_schema")
def get_schema(
    dataset_rid: DatasetRid,
    branch: BranchOption = None,
    transaction_rid: Annotated[
        Optional[str],
        typer.Option(
            "--transaction-rid",
            help="Get the schema as of this transaction (RID).",
            show_default=False,
        ),
    ] = None,
    version_id: Annotated[
        Optional[str],
        typer.Option(
            "--version-id", help="Get this schema version (UUID).", show_default=False
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a dataset's schema (one row per field in table and CSV output).

    JSON output is the API's response: {"branchName", "endTransactionRid",
    "schema": {"fieldSchemaList": [...]}, "versionId"}.
    """
    with spinner(f"Fetching schema of {dataset_rid}..."):
        response = DatasetService(profile=profile).get_dataset_schema(
            dataset_rid,
            branch=branch,
            end_transaction_rid=transaction_rid,
            version_id=version_id,
        )
    cache_rid(dataset_rid)
    _emit_schema(response, dataset_rid, format, output)


@schema_app.command("set")
@pltr_command(sdk="datasets.Dataset.put_schema", destructive=True)
def set_schema(
    dataset_rid: DatasetRid,
    from_csv: Annotated[
        Optional[Path],
        typer.Option(
            "--from-csv",
            exists=True,
            dir_okay=False,
            help="Infer the schema from a local CSV file (header and first 100 rows).",
            show_default=False,
        ),
    ] = None,
    json_schema: Annotated[
        Optional[str],
        typer.Option(
            "--json",
            help='Schema as JSON, inline or @file.json: {"fieldSchemaList": '
            '[{"name": "id", "type": "LONG", "nullable": false}]}. Also accepts '
            "the JSON output of 'pltr dataset schema get'.",
            show_default=False,
        ),
    ] = None,
    json_file: Annotated[
        Optional[Path],
        typer.Option(
            "--json-file",
            exists=True,
            dir_okay=False,
            help="Path of a JSON file with the schema (same forms as --json).",
            show_default=False,
        ),
    ] = None,
    branch: BranchOption = None,
    transaction_rid: Annotated[
        Optional[str],
        typer.Option(
            "--transaction-rid",
            help="Transaction the schema applies to (default: the latest "
            "committed transaction).",
            show_default=False,
        ),
    ] = None,
    dataframe_reader: Annotated[
        Optional[str],
        typer.Option(
            "--dataframe-reader",
            click_type=click.Choice(DATAFRAME_READERS, case_sensitive=False),
            help="How Foundry reads the dataset's files with this schema "
            "(default: PARQUET). Use CSV for CSV files you uploaded.",
            show_default=False,
        ),
    ] = None,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Replace a dataset's schema on a branch.

    Give the schema with exactly one of --from-csv, --json or --json-file.
    Field types: ARRAY, BINARY, BOOLEAN, BYTE, DATE, DECIMAL, DOUBLE, FLOAT,
    INTEGER, LONG, MAP, SHORT, STRING, STRUCT, TIMESTAMP. Asks for
    confirmation; --yes skips it.
    """
    given = [value is not None for value in (from_csv, json_schema, json_file)]
    if sum(given) != 1:
        raise typer.BadParameter(
            "pass exactly one of --from-csv, --json or --json-file"
        )
    service = DatasetService(profile=profile)
    if from_csv is not None:
        try:
            schema = service.infer_schema_from_csv(from_csv)
        except ValueError as exc:  # no header row, not UTF-8
            raise typer.BadParameter(str(exc), param_hint="'--from-csv'") from exc
        info(f"Inferred {_count_fields(schema)} from {from_csv}")
        origin = f"Schema inferred from {from_csv}"
    elif json_schema is not None:
        document = load_json_input(json_schema, param_hint="'--json'")
        schema = _parse_schema(document, "'--json'")
        origin = "Schema from --json"
    else:
        document = load_json_input(f"@{json_file}", param_hint="'--json-file'")
        schema = _parse_schema(document, "'--json-file'")
        origin = f"Schema from {json_file}"

    where = f" on branch '{branch}'" if branch else ""
    confirm_destructive(
        f"{origin} ({_count_fields(schema)}):\n"
        + "".join(f"  {_describe_field(f)}\n" for f in schema.field_schema_list)
        + f"Replace the schema of dataset {dataset_rid}{where} with it?",
        yes=yes,
    )
    with spinner(f"Setting the schema of {dataset_rid}..."):
        response = service.put_schema(
            dataset_rid,
            schema,
            branch=branch,
            transaction_rid=transaction_rid,
            dataframe_reader=dataframe_reader,
        )
    cache_rid(dataset_rid)
    success(f"Set the schema of {dataset_rid} ({_count_fields(schema)})")
    _emit_schema(response, dataset_rid, format, output)


@schema_app.command("apply")
@pltr_command(
    http=(f"POST {SCHEMA_INFERENCE_ENDPOINT}", f"POST {SCHEMA_METADATA_ENDPOINT}"),
    destructive=True,
)
def apply_schema(
    dataset_rid: DatasetRid,
    branch: Annotated[
        str,
        typer.Option("--branch", "-b", help="Branch to infer and apply the schema on."),
    ] = "master",
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Infer a dataset's schema from its files and apply it to a branch.

    Replaces the branch's current schema, so it asks for confirmation; --yes
    skips it. The public API can't infer schemas, so this calls Foundry's
    schema-inference and foundry-metadata endpoints directly (a labeled
    exception to pltr's SDK-only rule). JSON output is the foundry-metadata
    response. To set a schema you define yourself, use 'pltr dataset schema
    set'.
    """
    confirm_destructive(
        f"Infer a schema for dataset {dataset_rid} and apply it to branch "
        f"'{branch}' (replaces the current schema)?",
        yes=yes,
    )
    with spinner(f"Inferring and applying the schema of {dataset_rid}..."):
        result = DatasetService(profile=profile).apply_schema(dataset_rid, branch)
    cache_rid(dataset_rid)
    success(f"Applied the inferred schema to {dataset_rid} (branch '{branch}')")
    emit(result, format=format, output=output, title="Applied schema")


# ------------------------------------------------------------- branches


@branches_app.command("list")
@pltr_command(sdk="datasets.Dataset.Branch.list", paged=True)
def list_branches(
    dataset_rid: DatasetRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List a dataset's branches.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = DatasetService(profile=profile)
    with spinner(f"Listing branches of {dataset_rid}..."):
        page = collect_pages(
            lambda token: service.list_branches(
                dataset_rid, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(dataset_rid)
    emit(page, format=format, output=output, columns=BRANCH_COLUMNS)


@branches_app.command("create")
@pltr_command(sdk=("datasets.Dataset.Branch.get", "datasets.Dataset.Branch.create"))
def create_branch(
    dataset_rid: DatasetRid,
    branch_name: Annotated[str, typer.Argument(help="Name of the new branch.")],
    parent: Annotated[
        Optional[str],
        typer.Option(
            "--parent",
            help="Branch to start from: the new branch points at its latest "
            "transaction (default: master).",
            show_default=False,
        ),
    ] = None,
    transaction_rid: Annotated[
        Optional[str],
        typer.Option(
            "--transaction-rid",
            help="Start the new branch at this committed transaction (RID) "
            "instead of a parent branch.",
            show_default=False,
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create a branch, starting from a parent branch or a transaction."""
    if parent is not None and transaction_rid is not None:
        raise typer.BadParameter("pass --parent or --transaction-rid, not both")
    service = DatasetService(profile=profile)
    with spinner(f"Creating branch '{branch_name}' on {dataset_rid}..."):
        if transaction_rid is None:
            parent_branch = service.get_branch(dataset_rid, parent or "master")
            transaction_rid = parent_branch.transaction_rid
        branch = service.create_branch(
            dataset_rid, branch_name, transaction_rid=transaction_rid
        )
    cache_rid(dataset_rid)
    success(f"Created branch '{branch.name}' on {dataset_rid}")
    emit(branch, format=format, output=output, columns=BRANCH_COLUMNS, title="Branch")


@branches_app.command("get")
@pltr_command(sdk="datasets.Dataset.Branch.get")
def get_branch(
    dataset_rid: DatasetRid,
    branch_name: BranchName,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a branch: its name and latest open or committed transaction."""
    with spinner(f"Fetching branch '{branch_name}' of {dataset_rid}..."):
        branch = DatasetService(profile=profile).get_branch(dataset_rid, branch_name)
    cache_rid(dataset_rid)
    emit(branch, format=format, output=output, columns=BRANCH_COLUMNS, title="Branch")


@branches_app.command("delete")
@pltr_command(sdk="datasets.Dataset.Branch.delete", destructive=True)
def delete_branch(
    dataset_rid: DatasetRid,
    branch_name: Annotated[str, typer.Argument(help="Name of the branch to delete.")],
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Delete a branch (not master). Asks for confirmation; --yes skips it."""
    if branch_name.lower() == "master":
        raise typer.BadParameter(
            "pltr doesn't delete the master branch", param_hint="'BRANCH_NAME'"
        )
    confirm_destructive(
        f"Delete branch '{branch_name}' of dataset {dataset_rid}? "
        "This can't be undone.",
        yes=yes,
    )
    with spinner(f"Deleting branch '{branch_name}' of {dataset_rid}..."):
        DatasetService(profile=profile).delete_branch(dataset_rid, branch_name)
    success(f"Deleted branch '{branch_name}' of {dataset_rid}")
    emit(None, format=format)


@branches_app.command("transactions")
@pltr_command(sdk="datasets.Dataset.Branch.transactions", beta=True, paged=True)
def list_branch_transactions(
    dataset_rid: DatasetRid,
    branch_name: BranchName,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List a branch's transactions, newest first.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = DatasetService(profile=profile)
    with spinner(f"Listing transactions of branch '{branch_name}'..."):
        page = collect_pages(
            lambda token: service.list_branch_transactions(
                dataset_rid, branch_name, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(dataset_rid)
    emit(page, format=format, output=output, columns=TRANSACTION_COLUMNS)


# ---------------------------------------------------------------- files


@files_app.command("list")
@pltr_command(sdk="datasets.Dataset.File.list", paged=True)
def list_files(
    dataset_rid: DatasetRid,
    branch: BranchOption = None,
    path_prefix: Annotated[
        Optional[str],
        typer.Option(
            "--path-prefix",
            help="Only files whose path starts with this, e.g. data/2024/.",
            show_default=False,
        ),
    ] = None,
    start_transaction_rid: StartTransactionOption = None,
    end_transaction_rid: EndTransactionOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the files in a dataset's current view of a branch.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = DatasetService(profile=profile)
    with spinner(f"Listing files of {dataset_rid}..."):
        page = collect_pages(
            lambda token: service.list_dataset_files(
                dataset_rid,
                branch=branch,
                path_prefix=path_prefix,
                start_transaction_rid=start_transaction_rid,
                end_transaction_rid=end_transaction_rid,
                page_size=page_size,
                page_token=token,
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(dataset_rid)
    emit(page, format=format, output=output, columns=FILE_COLUMNS)


def _upload_plan(
    local_path: Path, dataset_path: Optional[str]
) -> List[Tuple[Path, str]]:
    """(local file, path in the dataset) for each file to upload."""
    if local_path.is_dir():
        files = sorted(path for path in local_path.rglob("*") if path.is_file())
        if not files:
            raise typer.BadParameter(
                f"{local_path} contains no files", param_hint="'FILE_PATH'"
            )
        prefix = (dataset_path or "").strip("/")
        return [
            (
                path,
                "/".join(
                    filter(None, (prefix, path.relative_to(local_path).as_posix()))
                ),
            )
            for path in files
        ]
    target = (dataset_path or "").lstrip("/")
    if not target or target.endswith("/"):
        target += local_path.name
    return [(local_path, target)]


def _abort_after_failure(
    service: DatasetService, dataset_rid: str, transaction_rid: str
) -> None:
    try:
        service.abort_transaction(dataset_rid, transaction_rid)
    except Exception as exc:  # report, then let the original error surface
        warn(
            f"Couldn't abort transaction {transaction_rid} ({type(exc).__name__}); "
            f"abort it with: pltr dataset transactions abort {dataset_rid} "
            f"{transaction_rid} --yes"
        )
    else:
        warn(f"Aborted transaction {transaction_rid}; the dataset is unchanged.")


def _upload_directory(
    service: DatasetService,
    dataset_rid: str,
    plan: List[Tuple[Path, str]],
    *,
    branch: Optional[str],
    transaction_rid: Optional[str],
    transaction_type: Optional[str],
) -> List[Any]:
    """Upload every file of ``plan`` in one transaction (see upload_file)."""
    if transaction_rid is not None:
        uploaded = []
        for local, remote in plan:
            uploaded.append(
                service.upload_file(
                    dataset_rid, local, remote, transaction_rid=transaction_rid
                )
            )
            info(f"Uploaded {remote}")
        success(f"Uploaded {len(uploaded)} files into transaction {transaction_rid}")
        info(
            "The transaction is still open. Commit it with: pltr dataset "
            f"transactions commit {dataset_rid} {transaction_rid}"
        )
        return uploaded

    transaction = service.start_transaction(
        dataset_rid, transaction_type=transaction_type or "UPDATE", branch=branch
    )
    info(f"Opened {transaction.transaction_type} transaction {transaction.rid}")
    uploaded = []
    try:
        for local, remote in plan:
            uploaded.append(
                service.upload_file(
                    dataset_rid, local, remote, transaction_rid=transaction.rid
                )
            )
            info(f"Uploaded {remote}")
        service.commit_transaction(dataset_rid, transaction.rid)
    except BaseException:
        _abort_after_failure(service, dataset_rid, transaction.rid)
        raise
    success(
        f"Uploaded {len(uploaded)} files and committed transaction {transaction.rid}"
    )
    return uploaded


@files_app.command("upload")
@pltr_command(
    sdk=(
        "datasets.Dataset.File.upload",
        "datasets.Dataset.Transaction.create",
        "datasets.Dataset.Transaction.commit",
        "datasets.Dataset.Transaction.abort",
    )
)
def upload_file(
    file_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            readable=True,
            help="Local file or directory to upload (directories recursively).",
        ),
    ],
    dataset_rid: DatasetRid,
    dataset_path: Annotated[
        Optional[str],
        typer.Option(
            "--path",
            help="Where to put it in the dataset: the file's path (default: the "
            "local file name; a path ending in / is a folder), or for a "
            "directory the folder to upload into (default: the dataset root).",
            show_default=False,
        ),
    ] = None,
    branch: Annotated[
        Optional[str],
        typer.Option(
            "--branch",
            help="Branch to upload to, in a new transaction that is committed "
            "(default: the dataset's default branch). Not with --transaction-rid.",
            show_default=False,
        ),
    ] = None,
    transaction_rid: Annotated[
        Optional[str],
        typer.Option(
            "--transaction-rid",
            help="Upload into this open transaction and leave it open (commit "
            "it with 'pltr dataset transactions commit'). Not with --branch.",
            show_default=False,
        ),
    ] = None,
    transaction_type: Annotated[
        Optional[str],
        typer.Option(
            "--transaction-type",
            click_type=click.Choice(
                ("APPEND", "UPDATE", "SNAPSHOT"), case_sensitive=False
            ),
            help="Type of the transaction the upload creates (default: UPDATE). "
            "SNAPSHOT replaces the dataset's files. Not with --transaction-rid.",
            show_default=False,
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Upload a local file or directory to a dataset.

    A file is uploaded in one request (read into memory: the API has no
    chunked upload); the API opens and commits a transaction for it unless
    you pass --transaction-rid. A directory is uploaded file by file in one
    transaction that pltr opens and commits, or aborts if any upload fails,
    so the dataset never shows a partial upload. JSON output is the uploaded
    File, or {"data": [...]} of Files for a directory.
    """
    if transaction_rid is not None and branch is not None:
        raise typer.BadParameter("pass --branch or --transaction-rid, not both")
    if transaction_rid is not None and transaction_type is not None:
        raise typer.BadParameter(
            "--transaction-type applies to the transaction pltr creates; it "
            "can't be used with --transaction-rid"
        )
    plan = _upload_plan(file_path, dataset_path)
    service = DatasetService(profile=profile)

    if file_path.is_dir():
        # One progress line per file instead of a spinner.
        uploaded = _upload_directory(
            service,
            dataset_rid,
            plan,
            branch=branch,
            transaction_rid=transaction_rid,
            transaction_type=transaction_type,
        )
        cache_rid(dataset_rid)
        emit(uploaded, format=format, output=output, columns=FILE_COLUMNS)
        return

    [(local, remote)] = plan
    with spinner(f"Uploading {local.name} to {dataset_rid}..."):
        uploaded_file = service.upload_file(
            dataset_rid,
            local,
            remote,
            branch=branch,
            transaction_rid=transaction_rid,
            transaction_type=transaction_type,
        )
    cache_rid(dataset_rid)
    success(f"Uploaded {local} to {dataset_rid} as {uploaded_file.path}")
    if transaction_rid is not None:
        info(
            "The transaction is still open. Commit it with: pltr dataset "
            f"transactions commit {dataset_rid} {transaction_rid}"
        )
    emit(
        uploaded_file, format=format, output=output, columns=FILE_COLUMNS, title="File"
    )


#: A local path: a real ``Path``, or a pure one in tests.
_P = TypeVar("_P", bound=PurePath)


def _resolved(path: PurePath) -> PurePath:
    """``path`` resolved (symlinks too), or normalized when it's a pure path
    (tests simulate Windows with ``PureWindowsPath``)."""
    if isinstance(path, Path):
        return path.resolve()
    flavour = ntpath if isinstance(path, PureWindowsPath) else posixpath
    return type(path)(flavour.normpath(str(path)))


def _unsafe_part(part: str, windows: bool) -> bool:
    """Whether a part of a remote path can't be one local path component."""
    if part == "..":
        return True
    # On Windows "\" separates paths too, ":" names a drive or a stream, and a
    # trailing "." or " " is dropped ("..." or ".. " become ".."). Elsewhere
    # they are ordinary characters.
    return windows and ("\\" in part or ":" in part or part.endswith((".", " ")))


def _download_targets(
    files: List[Any], prefix: Optional[str], output_dir: _P
) -> List[Tuple[Any, _P]]:
    """Local paths under ``output_dir`` for files listed under ``prefix``.

    Each "/"-separated part of a remote path becomes one local path
    component. A path that is absolute, has a part that isn't safe as a
    component (see ``_unsafe_part``), or resolves outside ``output_dir`` (for
    example through a symlink) stops the download before any file is written.
    """
    windows = isinstance(output_dir, PureWindowsPath)
    root = _resolved(output_dir)
    targets = []
    for file in files:
        relative = PurePosixPath(file.path[len(prefix) :] if prefix else file.path)
        parts = relative.parts
        safe = (
            bool(parts)
            and not relative.is_absolute()
            and not any(_unsafe_part(part, windows) for part in parts)
        )
        target = output_dir.joinpath(*parts)
        if not safe or not _resolved(target).is_relative_to(root):
            raise PltrError(
                f"Refusing to download {file.path!r}: it can't be written safely "
                f"inside {output_dir}. Nothing was downloaded.",
                hint="Download that file on its own to a local path you choose: "
                "pltr dataset files get DATASET_RID REMOTE_PATH LOCAL_FILE",
            )
        targets.append((file, target))
    return targets


@files_app.command("get")
@pltr_command(
    sdk=(
        "datasets.Dataset.File.get",
        "datasets.Dataset.File.content",
        "datasets.Dataset.File.list",
    )
)
def get_file(
    dataset_rid: DatasetRid,
    file_path: Annotated[
        str,
        typer.Argument(
            help="Path of the file in the dataset; with --recursive, a folder "
            "(/ for the whole dataset).",
            callback=_dataset_path,
        ),
    ],
    output_path: Annotated[
        Path,
        typer.Argument(
            help="Local file to write (an existing directory keeps the file's "
            "name), or - for stdout; with --recursive, the local directory to "
            "write into."
        ),
    ],
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Download every file under the FILE_PATH folder, keeping their "
            "paths relative to it.",
        ),
    ] = False,
    branch: BranchOption = None,
    start_transaction_rid: StartTransactionOption = None,
    end_transaction_rid: EndTransactionOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Download a file, or a folder with --recursive, from a dataset.

    Content is streamed to disk, so large files don't need to fit in memory;
    a failed download leaves no partial file and keeps an existing one.
    stdout gets the downloaded files' metadata: the File (JSON), or
    {"data": [...]} with --recursive. With OUTPUT_PATH - the file's content
    goes to stdout instead. With --recursive, a file whose path can't be
    written safely inside OUTPUT_PATH (a .. part, a symlink out of it, or on
    Windows a \\ or : in a name) stops the download before any file is
    written.
    """
    service = DatasetService(profile=profile)
    if str(output_path) == "-":
        if recursive:
            raise typer.BadParameter(
                "--recursive writes files into a directory, not to stdout",
                param_hint="'OUTPUT_PATH'",
            )
        with service.open_file_content(
            dataset_rid,
            file_path,
            branch=branch,
            start_transaction_rid=start_transaction_rid,
            end_transaction_rid=end_transaction_rid,
        ) as chunks:
            emit_bytes(chunks, output="-")
        cache_rid(dataset_rid)
        return

    if recursive:
        folder = file_path.strip("/")
        prefix = f"{folder}/" if folder and folder != "." else None
        with spinner(f"Listing files under '{prefix or '/'}'..."):
            # Iterating the SDK iterator fetches every page.
            files = list(
                service.list_dataset_files(
                    dataset_rid,
                    branch=branch,
                    path_prefix=prefix,
                    start_transaction_rid=start_transaction_rid,
                    end_transaction_rid=end_transaction_rid,
                )
            )
        targets = _download_targets(files, prefix, output_path)
        for file, target in targets:  # one progress line per file, no spinner
            written = service.download_file(
                dataset_rid,
                file.path,
                target,
                branch=branch,
                start_transaction_rid=start_transaction_rid,
                end_transaction_rid=end_transaction_rid,
            )
            info(f"Downloaded {file.path} to {target} ({written} bytes)")
        cache_rid(dataset_rid)
        success(f"Downloaded {len(targets)} files to {output_path}")
        emit(files, format=format, columns=FILE_COLUMNS)
        return

    target = output_path
    if target.is_dir():
        target = target / PurePosixPath(file_path).name
    with spinner(f"Downloading {file_path} from {dataset_rid}..."):
        file = service.get_file(
            dataset_rid,
            file_path,
            branch=branch,
            start_transaction_rid=start_transaction_rid,
            end_transaction_rid=end_transaction_rid,
        )
        written = service.download_file(
            dataset_rid,
            file_path,
            target,
            branch=branch,
            start_transaction_rid=start_transaction_rid,
            end_transaction_rid=end_transaction_rid,
        )
    cache_rid(dataset_rid)
    success(f"Downloaded {file_path} to {target} ({written} bytes)")
    emit(file, format=format, columns=FILE_COLUMNS, title="File")


@files_app.command("delete")
@pltr_command(sdk="datasets.Dataset.File.delete", destructive=True)
def delete_file(
    dataset_rid: DatasetRid,
    file_path: FilePathArgument,
    branch: Annotated[
        Optional[str],
        typer.Option(
            "--branch",
            help="Branch to delete the file on, in a new DELETE transaction that "
            "is committed (default: the dataset's default branch). Not with "
            "--transaction-rid.",
            show_default=False,
        ),
    ] = None,
    transaction_rid: Annotated[
        Optional[str],
        typer.Option(
            "--transaction-rid",
            help="Delete the file in this open DELETE transaction. Not with --branch.",
            show_default=False,
        ),
    ] = None,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Delete a file from a dataset's current view.

    The file stays in the dataset's history. Asks for confirmation; --yes
    skips it.
    """
    if transaction_rid is not None and branch is not None:
        raise typer.BadParameter("pass --branch or --transaction-rid, not both")
    confirm_destructive(f"Delete '{file_path}' from dataset {dataset_rid}?", yes=yes)
    with spinner(f"Deleting {file_path} from {dataset_rid}..."):
        DatasetService(profile=profile).delete_file(
            dataset_rid, file_path, branch=branch, transaction_rid=transaction_rid
        )
    cache_rid(dataset_rid)
    success(f"Deleted '{file_path}' from {dataset_rid}")
    emit(None, format=format)


@files_app.command("info")
@pltr_command(sdk="datasets.Dataset.File.get")
def get_file_info(
    dataset_rid: DatasetRid,
    file_path: FilePathArgument,
    branch: BranchOption = None,
    start_transaction_rid: StartTransactionOption = None,
    end_transaction_rid: EndTransactionOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a file's metadata: path, size, last update and transaction."""
    with spinner(f"Fetching {file_path} of {dataset_rid}..."):
        file = DatasetService(profile=profile).get_file(
            dataset_rid,
            file_path,
            branch=branch,
            start_transaction_rid=start_transaction_rid,
            end_transaction_rid=end_transaction_rid,
        )
    cache_rid(dataset_rid)
    emit(file, format=format, output=output, columns=FILE_COLUMNS, title="File")


# --------------------------------------------------------- transactions


@transactions_app.command("start")
@pltr_command(sdk="datasets.Dataset.Transaction.create")
def start_transaction(
    dataset_rid: DatasetRid,
    branch: BranchOption = None,
    transaction_type: Annotated[
        str,
        typer.Option(
            "--type",
            click_type=click.Choice(TRANSACTION_TYPES, case_sensitive=False),
            help="APPEND adds files; UPDATE adds and replaces files; SNAPSHOT "
            "replaces all files; DELETE removes files.",
        ),
    ] = "APPEND",
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Open a transaction on a branch (one open transaction per branch)."""
    with spinner(f"Opening a {transaction_type} transaction on {dataset_rid}..."):
        transaction = DatasetService(profile=profile).start_transaction(
            dataset_rid, transaction_type=transaction_type.upper(), branch=branch
        )
    cache_rid(dataset_rid)
    success(f"Opened {transaction.transaction_type} transaction {transaction.rid}")
    info(
        "Next steps:\n"
        f"  Upload files: pltr dataset files upload <path> {dataset_rid} "
        f"--transaction-rid {transaction.rid}\n"
        f"  Commit:       pltr dataset transactions commit {dataset_rid} {transaction.rid}\n"
        f"  Abort:        pltr dataset transactions abort {dataset_rid} {transaction.rid}"
    )
    emit(
        transaction,
        format=format,
        output=output,
        columns=TRANSACTION_COLUMNS,
        title="Transaction",
    )


@transactions_app.command("commit")
@pltr_command(sdk="datasets.Dataset.Transaction.commit")
def commit_transaction(
    dataset_rid: DatasetRid,
    transaction_rid: TransactionRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Commit an open transaction, making its changes visible."""
    with spinner(f"Committing transaction {transaction_rid}..."):
        transaction = DatasetService(profile=profile).commit_transaction(
            dataset_rid, transaction_rid
        )
    cache_rid(dataset_rid)
    success(f"Committed transaction {transaction.rid}")
    emit(
        transaction,
        format=format,
        output=output,
        columns=TRANSACTION_COLUMNS,
        title="Transaction",
    )


@transactions_app.command("abort")
@pltr_command(sdk="datasets.Dataset.Transaction.abort", destructive=True)
def abort_transaction(
    dataset_rid: DatasetRid,
    transaction_rid: TransactionRid,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Abort an open transaction, discarding its changes.

    Asks for confirmation; --yes skips it.
    """
    confirm_destructive(
        f"Abort transaction {transaction_rid} of dataset {dataset_rid}? Its "
        "changes are discarded.",
        yes=yes,
    )
    with spinner(f"Aborting transaction {transaction_rid}..."):
        transaction = DatasetService(profile=profile).abort_transaction(
            dataset_rid, transaction_rid
        )
    cache_rid(dataset_rid)
    success(f"Aborted transaction {transaction.rid}")
    emit(
        transaction,
        format=format,
        output=output,
        columns=TRANSACTION_COLUMNS,
        title="Transaction",
    )


@transactions_app.command("status")
@pltr_command(sdk="datasets.Dataset.Transaction.get")
def get_transaction_status(
    dataset_rid: DatasetRid,
    transaction_rid: TransactionRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a transaction: type, status (OPEN, COMMITTED, ABORTED) and times."""
    with spinner(f"Fetching transaction {transaction_rid}..."):
        transaction = DatasetService(profile=profile).get_transaction(
            dataset_rid, transaction_rid
        )
    cache_rid(dataset_rid)
    emit(
        transaction,
        format=format,
        output=output,
        columns=TRANSACTION_COLUMNS,
        title="Transaction",
    )


@transactions_app.command("list")
@pltr_command(
    sdk=("datasets.Dataset.transactions", "datasets.Dataset.Branch.transactions"),
    beta=True,
    paged=True,
)
def list_transactions(
    dataset_rid: DatasetRid,
    branch: Annotated[
        Optional[str],
        typer.Option(
            "--branch",
            help="Only this branch's transactions (default: every branch).",
            show_default=False,
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List a dataset's transactions, newest first.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = DatasetService(profile=profile)

    def fetch(token: Optional[str]) -> Any:
        if branch is not None:
            return service.list_branch_transactions(
                dataset_rid, branch, page_size=page_size, page_token=token
            )
        return service.list_transactions(
            dataset_rid, page_size=page_size, page_token=token
        )

    with spinner(f"Listing transactions of {dataset_rid}..."):
        page = collect_pages(
            fetch, page_token=page_token, max_pages=max_pages, all_pages=all_pages
        )
    cache_rid(dataset_rid)
    emit(page, format=format, output=output, columns=TRANSACTION_COLUMNS)


@transactions_app.command("build")
@pltr_command(sdk="datasets.Dataset.Transaction.build", beta=True)
def get_transaction_build(
    dataset_rid: DatasetRid,
    transaction_rid: TransactionRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get the RID of the build that computed a transaction.

    Prints nothing (JSON: null) when no build produced the transaction, for
    example an upload. See the build with 'pltr orchestration builds get'.
    """
    with spinner(f"Fetching the build of transaction {transaction_rid}..."):
        build_rid = DatasetService(profile=profile).get_transaction_build(
            dataset_rid, transaction_rid
        )
    cache_rid(dataset_rid)
    if build_rid is None:
        info(f"No build produced transaction {transaction_rid}.")
    emit(build_rid, format=format, output=output, columns=BUILD_COLUMNS)


# ---------------------------------------------------------------- views

BackingDatasetsArgument = Annotated[
    List[str],
    typer.Argument(
        help="Backing dataset RIDs, each DATASET_RID or DATASET_RID@BRANCH "
        "(default branch: the view's)."
    ),
]
ViewBranchOption = Annotated[
    Optional[str],
    typer.Option(
        "--branch",
        help="Branch of the view (default: master on most enrollments).",
        show_default=False,
    ),
]


def _backing_list(values: List[str], param_hint: str) -> List[BackingDataset]:
    return [_backing_dataset(value, param_hint) for value in values]


@views_app.command("create")
@pltr_command(sdk="datasets.View.create")
def create_view(
    view_name: Annotated[str, typer.Argument(help="Name of the new view.")],
    parent_folder: ParentFolderOption,
    backing_dataset_rids: Annotated[
        List[str],
        typer.Option(
            "--backing-dataset",
            help="A dataset backing the view: DATASET_RID or DATASET_RID@BRANCH "
            "(repeat for several).",
            show_default=False,
        ),
    ],
    branch: ViewBranchOption = None,
    description: Annotated[
        Optional[str],
        typer.Option(
            "--description",
            hidden=True,
            help="Removed: views have no description in the API.",
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create a view: a virtual dataset that unions its backing datasets.

    Every marking of the backing datasets propagates to the view.
    """
    if description is not None:
        raise typer.BadParameter(
            "views have no description in the Foundry API, so this option was removed",
            param_hint="'--description'",
        )
    backing = _backing_list(backing_dataset_rids, "'--backing-dataset'")
    with spinner(f"Creating view '{view_name}'..."):
        view = DatasetService(profile=profile).create_view(
            view_name,
            parent_folder_rid=parent_folder,
            backing_datasets=backing,
            branch=branch,
        )
    cache_rid(view.dataset_rid)
    success(f"Created view '{view.view_name}' ({view.dataset_rid})")
    emit(view, format=format, output=output, columns=VIEW_COLUMNS, title="View")


@views_app.command("get")
@pltr_command(sdk="datasets.View.get")
def get_view(
    view_rid: ViewRid,
    branch: ViewBranchOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a view: its backing datasets, primary key and parent folder."""
    with spinner(f"Fetching view {view_rid}..."):
        view = DatasetService(profile=profile).get_view(view_rid, branch=branch)
    cache_rid(view_rid)
    emit(view, format=format, output=output, columns=VIEW_COLUMNS, title="View")


@views_app.command("add-datasets")
@pltr_command(sdk="datasets.View.add_backing_datasets")
def add_backing_datasets(
    view_rid: ViewRid,
    dataset_rids: BackingDatasetsArgument,
    branch: ViewBranchOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Add backing datasets to a view (datasets it already has are ignored)."""
    backing = _backing_list(dataset_rids, "'DATASET_RIDS'")
    with spinner(f"Adding {len(backing)} backing datasets to {view_rid}..."):
        view = DatasetService(profile=profile).add_backing_datasets(
            view_rid, backing, branch=branch
        )
    cache_rid(view_rid)
    success(f"Added {len(backing)} backing datasets to {view_rid}")
    emit(view, format=format, output=output, columns=VIEW_COLUMNS, title="View")


@views_app.command("remove-datasets")
@pltr_command(sdk="datasets.View.remove_backing_datasets", destructive=True)
def remove_backing_datasets(
    view_rid: ViewRid,
    dataset_rids: BackingDatasetsArgument,
    branch: ViewBranchOption = None,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Remove backing datasets from a view.

    The view's next update is a SNAPSHOT. Asks for confirmation; --yes
    skips it.
    """
    backing = _backing_list(dataset_rids, "'DATASET_RIDS'")
    confirm_destructive(
        f"Remove {len(backing)} backing datasets from view {view_rid}?", yes=yes
    )
    with spinner(f"Removing backing datasets from {view_rid}..."):
        view = DatasetService(profile=profile).remove_backing_datasets(
            view_rid, backing, branch=branch
        )
    cache_rid(view_rid)
    success(f"Removed {len(backing)} backing datasets from {view_rid}")
    emit(view, format=format, output=output, columns=VIEW_COLUMNS, title="View")


@views_app.command("replace-datasets")
@pltr_command(sdk="datasets.View.replace_backing_datasets", destructive=True)
def replace_backing_datasets(
    view_rid: ViewRid,
    dataset_rids: BackingDatasetsArgument,
    branch: ViewBranchOption = None,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Replace all of a view's backing datasets with these.

    Removing a backing dataset makes the view's next update a SNAPSHOT. Asks
    for confirmation; --yes skips it.
    """
    backing = _backing_list(dataset_rids, "'DATASET_RIDS'")
    confirm_destructive(
        f"Replace the backing datasets of view {view_rid} with {len(backing)} "
        "datasets?",
        yes=yes,
    )
    with spinner(f"Replacing the backing datasets of {view_rid}..."):
        view = DatasetService(profile=profile).replace_backing_datasets(
            view_rid, backing, branch=branch
        )
    cache_rid(view_rid)
    success(f"Replaced the backing datasets of {view_rid}")
    emit(view, format=format, output=output, columns=VIEW_COLUMNS, title="View")


@views_app.command("add-primary-key")
@pltr_command(sdk="datasets.View.add_primary_key")
def add_primary_key(
    view_rid: ViewRid,
    columns: Annotated[
        List[str],
        typer.Argument(
            help="Columns that make up the key (types BYTE, SHORT, DECIMAL, "
            "INTEGER, LONG, STRING, BOOLEAN, TIMESTAMP or DATE)."
        ),
    ],
    latest_wins: Annotated[
        Optional[List[str]],
        typer.Option(
            "--latest-wins",
            help="Allow duplicate keys and keep the row with the highest value "
            "of this column (repeat to compare several in order). Without it, "
            "key values are declared unique.",
            show_default=False,
        ),
    ] = None,
    deletion_column: Annotated[
        Optional[str],
        typer.Option(
            "--deletion-column",
            help="With --latest-wins: boolean column; a kept row with true in "
            "it counts as deleted.",
            show_default=False,
        ),
    ] = None,
    branch: ViewBranchOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Add a primary key to a view that has none.

    Foundry treats the key as a guarantee from you: unique values, or with
    --latest-wins, duplicates resolved by keeping the latest row.
    """
    if deletion_column is not None and not latest_wins:
        raise typer.BadParameter(
            "--deletion-column needs --latest-wins", param_hint="'--deletion-column'"
        )
    with spinner(f"Adding a primary key to {view_rid}..."):
        view = DatasetService(profile=profile).add_primary_key(
            view_rid,
            columns,
            latest_wins_columns=latest_wins or None,
            deletion_column=deletion_column,
            branch=branch,
        )
    cache_rid(view_rid)
    success(f"Added primary key ({', '.join(columns)}) to {view_rid}")
    emit(view, format=format, output=output, columns=VIEW_COLUMNS, title="View")


# ------------------------------------------------------ schedules, jobs


@schedules_app.command("list")
@pltr_command(sdk="datasets.Dataset.get_schedules", paged=True)
def list_schedules(
    dataset_rid: DatasetRid,
    branch: BranchOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the RIDs of the schedules that target a dataset.

    The API returns only RIDs; see a schedule with 'pltr orchestration
    schedules get <RID>'. Recent schedule changes can take up to an hour to
    show up. Fetches one page by default; use --all for every page.
    """
    service = DatasetService(profile=profile)
    with spinner(f"Listing schedules of {dataset_rid}..."):
        page = collect_pages(
            lambda token: service.list_schedules(
                dataset_rid, branch=branch, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(dataset_rid)
    emit(page, format=format, output=output, columns=SCHEDULE_COLUMNS)


@jobs_app.command("list")
@pltr_command(sdk="datasets.Dataset.jobs", beta=True, paged=True)
def list_jobs(
    dataset_rid: DatasetRid,
    branch: BranchOption = None,
    order_by: Annotated[
        str,
        typer.Option(
            "--order-by",
            click_type=click.Choice(("started", "finished"), case_sensitive=False),
            help="Sort by job start or finish time.",
        ),
    ] = "started",
    ascending: Annotated[
        bool,
        typer.Option("--ascending", help="Oldest first (default: newest first)."),
    ] = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the RIDs of a dataset's jobs, newest first.

    The API returns only job RIDs; see a job with 'pltr orchestration jobs
    get <RID>'. Fetches one page by default; use --all for every page.
    """
    sort = "BY_FINISHED_TIME" if order_by.lower() == "finished" else "BY_STARTED_TIME"
    service = DatasetService(profile=profile)
    with spinner(f"Listing jobs of {dataset_rid}..."):
        page = collect_pages(
            lambda token: service.list_jobs(
                dataset_rid,
                branch=branch,
                order_by=sort,
                descending=not ascending,
                page_size=page_size,
                page_token=token,
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(dataset_rid)
    emit(page, format=format, output=output, columns=JOB_COLUMNS)


# Add subcommands to main app
app.add_typer(branches_app, name="branches", help="Manage a dataset's branches.")
app.add_typer(files_app, name="files", help="Upload, download and manage files.")
app.add_typer(
    transactions_app, name="transactions", help="Open, commit and inspect transactions."
)
app.add_typer(views_app, name="views", help="Manage views (virtual datasets).")
app.add_typer(schema_app, name="schema", help="Get, set or infer a dataset's schema.")
app.add_typer(schedules_app, name="schedules", help="Schedules that target a dataset.")
app.add_typer(jobs_app, name="jobs", help="Jobs that built a dataset.")


@app.callback()
def main():
    """
    Dataset operations using foundry-platform-sdk.

    Datasets are addressed by RID (ri.foundry.main.dataset.<id>); views are
    datasets too. Find a dataset's RID in the Foundry UI, or list a folder
    with 'pltr folder list <FOLDER_RID>'. Branches are addressed by name
    (master on most enrollments), transactions by RID
    (ri.foundry.main.transaction.<id>). Commands labeled [beta] call beta
    Foundry endpoints.

    Examples:

    \b
        # Show a dataset and read its first rows
        pltr dataset get ri.foundry.main.dataset.abc123
        pltr dataset preview ri.foundry.main.dataset.abc123 --limit 20
    \b
        # Upload a directory in one transaction, then list the files
        pltr dataset files upload ./exports ri.foundry.main.dataset.abc123
        pltr dataset files list ri.foundry.main.dataset.abc123 --all
    \b
        # Several uploads in one transaction you commit yourself
        pltr dataset transactions start ri.foundry.main.dataset.abc123 --type SNAPSHOT
        pltr dataset files upload a.csv ri.foundry.main.dataset.abc123 \\
            --transaction-rid <TRANSACTION_RID>
        pltr dataset transactions commit ri.foundry.main.dataset.abc123 <TRANSACTION_RID>
    """
