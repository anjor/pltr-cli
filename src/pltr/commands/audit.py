"""
Audit log file commands (Foundry audit API), for compliance and security
monitoring.
"""

from datetime import datetime
from typing import Any, Callable, List, Optional

import typer
from typing_extensions import Annotated

from ..contract import (
    AllPagesOption,
    Columns,
    FormatOption,
    MaxPagesOption,
    OutputOption,
    Page,
    PageSizeOption,
    PageTokenOption,
    ProfileOption,
    check_binary_output,
    emit,
    emit_bytes,
    pltr_command,
    spinner,
)
from ..services.audit import AuditService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer(help="Audit log operations for compliance and security monitoring")

#: Table/CSV columns for a ``LogFile`` (the API returns only its ID).
LOG_FILE_COLUMNS: Columns = {"Log File ID": "id"}

DATE_FORMATS = ["%Y-%m-%d"]

OrganizationRid = Annotated[
    str,
    typer.Argument(
        help=(
            "Organization RID (ri.multipass..organization.<id>); yours is the "
            "organization of 'pltr admin user current'."
        ),
        autocompletion=complete_rid,
        show_default=False,
    ),
]


@app.command("list")
@pltr_command(sdk="audit.Organization.LogFile.list", paged=True)
def list_log_files(
    organization_rid: OrganizationRid,
    start_date: Annotated[
        datetime,
        typer.Argument(
            formats=DATE_FORMATS,
            help="List log files for audit events from this date on (YYYY-MM-DD).",
            show_default=False,
        ),
    ],
    end_date: Annotated[
        Optional[datetime],
        typer.Option(
            "--end-date",
            "-e",
            formats=DATE_FORMATS,
            help=(
                "List log files for audit events up to this date, inclusive "
                "(YYYY-MM-DD). Default: no end date."
            ),
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
    """List an organization's audit log files.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue. Without
    --end-date the listing has no end: paging stops at the first empty page,
    and its nextPageToken picks up new log files later. Download a file with
    'pltr audit get'.
    """
    service = AuditService(profile=profile)
    start = start_date.date()
    end = end_date.date() if end_date else None
    with spinner("Fetching audit log files..."):
        page = _collect_until_caught_up(
            lambda token: service.list_log_files(
                organization_rid,
                start_date=start,
                end_date=end,
                page_size=page_size,
                page_token=token,
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(organization_rid)
    emit(page, format=format, output=output, columns=LOG_FILE_COLUMNS)


def _collect_until_caught_up(
    fetch_page: Callable[[Optional[str]], Any],
    *,
    page_token: Optional[str],
    max_pages: int,
    all_pages: bool,
) -> Page:
    """``collect_pages``, but stop at an empty page and keep its token.

    Without an end date, ``LogFile.list`` returns a ``nextPageToken`` on
    every page so that clients can poll for new log files, so paging until
    there is no token (``collect_pages`` with ``--all``) would never end.
    """
    items: List[Any] = []
    token = page_token
    pages = 0
    while True:
        page = fetch_page(token)
        items.extend(page.data or [])
        token = page.next_page_token
        pages += 1
        if not token or not page.data or (not all_pages and pages >= max_pages):
            break
    return Page(data=items, next_page_token=token or None)


@app.command("get")
@pltr_command(sdk="audit.Organization.LogFile.content")
def get_log_file_content(
    organization_rid: OrganizationRid,
    log_file_id: Annotated[
        str,
        typer.Argument(
            help="Log file ID (an id from 'pltr audit list').", show_default=False
        ),
    ],
    output: OutputOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Download an audit log file.

    Streams the file's content, unchanged, to FILE with --output, or to
    stdout when stdout is a file or a pipe; it is never written to a
    terminal. --format only changes how errors are reported (with --format
    json, as a JSON object on stderr).

    Example:

    \b
    pltr audit get <ORGANIZATION_RID> <LOG_FILE_ID> --output audit.log
    """
    check_binary_output(output)
    with spinner(f"Fetching audit log file {log_file_id}..."):
        download = AuditService(profile=profile).download_log_file(
            organization_rid, log_file_id
        )
    cache_rid(organization_rid)
    with download as response:
        emit_bytes(response.iter_bytes(), output=output)
