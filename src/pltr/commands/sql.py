"""
SQL commands (Foundry SQL queries API).

Queries use the Spark SQL dialect (SELECT only) and reference datasets by
path or RID. The SQL endpoints pltr calls are GA. Query results are rows:
JSON output is ``{"data": [...]}`` with one object per row, keyed by column
name.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import typer
from click.core import ParameterSource
from foundry_sdk.v2.sql_queries.models import (
    CanceledQueryStatus,
    FailedQueryStatus,
    RunningQueryStatus,
)
from typing_extensions import Annotated

from ..contract import (
    Columns,
    FormatOption,
    OutputOption,
    ProfileOption,
    YesOption,
    confirm_destructive,
    emit,
    format_option,
    info,
    pltr_command,
    spinner,
    success,
    table_rows,
    warn,
)
from ..services.sql import SqlService, check_not_failed, query_id_of
from ..utils.completion import complete_sql_query

app = typer.Typer(name="sql", help="Execute SQL queries against Foundry datasets")

_EXECUTE_SDK = (
    "sql_queries.SqlQuery.execute",
    "sql_queries.SqlQuery.get_status",
    "sql_queries.SqlQuery.get_results",
)

#: File extensions `sql export` maps to an output format.
_EXPORT_FORMATS = {".json": "json", ".csv": "csv"}


def _deprecated_preview(
    ctx: click.Context, param: click.Parameter, value: Optional[bool]
) -> Optional[bool]:
    if value is not None and not ctx.resilient_parsing:
        warn(
            "--preview/--no-preview is deprecated and has no effect: the SQL "
            "endpoints are GA. It will be removed in a future release."
        )
    return value


QueryArgument = Annotated[
    str,
    typer.Argument(
        help=(
            "SQL query (Spark SQL dialect, SELECT only). Reference datasets by "
            "path or RID, e.g. SELECT * FROM `ri.foundry.main.dataset.<id>` LIMIT 10."
        ),
        autocompletion=complete_sql_query,
        show_default=False,
    ),
]
QueryIdArgument = Annotated[
    str,
    typer.Argument(
        help="Query ID, as printed by 'pltr sql submit' (queryId in JSON).",
        show_default=False,
    ),
]
TimeoutOption = Annotated[
    int,
    typer.Option("--timeout", min=1, help="Seconds to wait for the query to finish."),
]
FallbackBranchesOption = Annotated[
    Optional[str],
    typer.Option(
        "--fallback-branches",
        help=(
            "Comma-separated branch names to read datasets from when the query "
            "names no branch; the first that exists is used (default: the "
            "default branch, usually master)."
        ),
        show_default=False,
    ),
]


def _export_format_option() -> Any:
    """The shared --format option, whose default (None) means "from the file
    extension" for `sql export`."""
    option = format_option()
    option.show_default = False
    return option


#: Hidden, deprecated no-op: the SQL commands used to have --preview/--no-preview.
PreviewFlagNoopOption = Annotated[
    Optional[bool],
    typer.Option(
        "--preview/--no-preview",
        hidden=True,
        help="Deprecated; has no effect.",
        callback=_deprecated_preview,
    ),
]


# ------------------------------------------------------------------ helpers


def _branches(value: Optional[str]) -> Optional[List[str]]:
    """Parse --fallback-branches into a list (None when not given)."""
    if value is None:
        return None
    branches = [branch.strip() for branch in value.split(",") if branch.strip()]
    if not branches:
        raise typer.BadParameter(
            "give at least one branch name", param_hint="'--fallback-branches'"
        )
    return branches


def _status_columns(status: Any, query_id: Optional[str] = None) -> Columns:
    """Table/CSV columns for a ``QueryStatus`` (its variants differ in fields).

    Failed and canceled statuses don't carry the query ID; ``query_id`` (the
    one the user passed) fills the column then.
    """
    columns: Dict[str, Any] = {
        "Query ID": lambda item: query_id_of(item) or query_id,
        "Status": "type",
    }
    if isinstance(status, FailedQueryStatus):
        columns["Error"] = "error_message"
    return columns


def _emit_rows(table: Any, *, format: str, output: Optional[str]) -> None:
    columns, rows = table_rows(table)
    emit(rows, format=format, output=output, columns=columns)


def _export_format(output_file: Path, format: Optional[str]) -> str:
    """Format for `sql export`: --format from the command line, else the file
    extension, else --format from $PLTR_FORMAT, else table."""
    ctx = click.get_current_context()
    if format and ctx.get_parameter_source("format") is ParameterSource.COMMANDLINE:
        return format
    return _EXPORT_FORMATS.get(output_file.suffix.lower(), format or "table")


# ----------------------------------------------------------------- commands


@app.command("execute")
@pltr_command(sdk=_EXECUTE_SDK)
def execute_query(
    query: QueryArgument,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    timeout: TimeoutOption = 300,
    fallback_branches: FallbackBranchesOption = None,
    preview: PreviewFlagNoopOption = None,
):
    """Run a SQL query, wait for it to finish and print its rows.

    JSON output is {"data": [...]} with one object per row, keyed by column
    name; binary values are base64-encoded. The query ID goes to stderr. For
    long-running queries use 'pltr sql submit' and 'pltr sql wait'.
    """
    service = SqlService(profile=profile)
    with spinner("Running SQL query..."):
        query_id, table = service.execute_query(
            query, fallback_branch_ids=_branches(fallback_branches), timeout=timeout
        )
    _emit_rows(table, format=format, output=output)
    info(f"Query ID: {query_id}")


@app.command("submit")
@pltr_command(sdk="sql_queries.SqlQuery.execute")
def submit_query(
    query: QueryArgument,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    fallback_branches: FallbackBranchesOption = None,
    preview: PreviewFlagNoopOption = None,
):
    """Start a SQL query without waiting; print its status and query ID.

    Follow up with 'pltr sql status', 'pltr sql wait' or 'pltr sql results'.
    In a script: QUERY_ID=$(pltr sql submit "..." --format json | jq -r .queryId)
    Fails if the query fails or is canceled right away.
    """
    with spinner("Submitting SQL query..."):
        status = SqlService(profile=profile).submit_query(
            query, fallback_branch_ids=_branches(fallback_branches)
        )
    check_not_failed(status)
    query_id = query_id_of(status)
    success(f"Submitted query {query_id}")
    if isinstance(status, RunningQueryStatus):
        info(f"Wait for its results with: pltr sql wait {query_id}")
    emit(
        status,
        format=format,
        output=output,
        columns=_status_columns(status),
        title="SQL Query",
    )


@app.command("status")
@pltr_command(sdk="sql_queries.SqlQuery.get_status")
def get_query_status(
    query_id: QueryIdArgument,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewFlagNoopOption = None,
):
    """Get a query's status: running, succeeded, failed (with the error) or canceled."""
    with spinner(f"Checking query {query_id}..."):
        status = SqlService(profile=profile).get_query_status(query_id)
    emit(
        status,
        format=format,
        output=output,
        columns=_status_columns(status, query_id),
        title="SQL Query",
    )


@app.command("results")
@pltr_command(sdk="sql_queries.SqlQuery.get_results")
def get_query_results(
    query_id: QueryIdArgument,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewFlagNoopOption = None,
):
    """Print the rows of a finished query.

    While the query is still running the API waits up to a minute for it and
    then fails with QueryRunning; use 'pltr sql wait' to wait longer. JSON
    output is {"data": [...]} with one object per row.
    """
    with spinner(f"Fetching results of query {query_id}..."):
        table = SqlService(profile=profile).get_query_results(query_id)
    _emit_rows(table, format=format, output=output)


@app.command("cancel")
@pltr_command(
    sdk=("sql_queries.SqlQuery.cancel", "sql_queries.SqlQuery.get_status"),
    destructive=True,
)
def cancel_query(
    query_id: QueryIdArgument,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewFlagNoopOption = None,
):
    """Cancel a running query, then print its status.

    Canceling a query that has already finished changes nothing.
    """
    confirm_destructive(f"Cancel SQL query {query_id}?", yes=yes)
    service = SqlService(profile=profile)
    with spinner(f"Canceling query {query_id}..."):
        service.cancel_query(query_id)
        status = service.get_query_status(query_id)
    if isinstance(status, CanceledQueryStatus):
        success(f"Canceled query {query_id}")
    else:
        info(f"Query {query_id} is {status.type}.")
    emit(
        status,
        format=format,
        output=output,
        columns=_status_columns(status, query_id),
        title="SQL Query",
    )


@app.command("export")
@pltr_command(sdk=_EXECUTE_SDK)
def export_query_results(
    query: QueryArgument,
    output_file: Annotated[
        Path,
        typer.Argument(
            help="File to write the rows to (overwritten if it exists).",
            dir_okay=False,
            show_default=False,
        ),
    ],
    profile: ProfileOption = None,
    format: Annotated[Optional[str], _export_format_option()] = None,
    timeout: TimeoutOption = 300,
    fallback_branches: FallbackBranchesOption = None,
    preview: PreviewFlagNoopOption = None,
):
    """Run a SQL query and write its rows to a file.

    The file format follows its extension (.json, .csv; anything else gets a
    table) unless --format is given on the command line. Nothing is printed
    on stdout.
    """
    file_format = _export_format(output_file, format)
    service = SqlService(profile=profile)
    with spinner("Running SQL query..."):
        query_id, table = service.execute_query(
            query, fallback_branch_ids=_branches(fallback_branches), timeout=timeout
        )
    _emit_rows(table, format=file_format, output=str(output_file))
    info(f"Query ID: {query_id}")


@app.command("wait")
@pltr_command(
    sdk=("sql_queries.SqlQuery.get_status", "sql_queries.SqlQuery.get_results")
)
def wait_for_query(
    query_id: QueryIdArgument,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    timeout: TimeoutOption = 300,
    preview: PreviewFlagNoopOption = None,
):
    """Wait for a submitted query to finish, then print its rows.

    Fails if the query failed or was canceled, or is still running after
    --timeout seconds (it keeps running then). Output is the same as
    'pltr sql results'.
    """
    service = SqlService(profile=profile)
    with spinner(f"Waiting for query {query_id}..."):
        service.wait_for_query(query_id, timeout=timeout)
        table = service.get_query_results(query_id)
    success(f"Query {query_id} succeeded")
    _emit_rows(table, format=format, output=output)
