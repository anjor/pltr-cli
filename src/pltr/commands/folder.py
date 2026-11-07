"""
Folder commands (Foundry filesystem API).
"""

from typing import List, Optional

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
    ProfileOption,
    collect_pages,
    emit,
    pltr_command,
    profile_option,
    resource_argument,
    resource_option,
    spinner,
    success,
)
from ..services.folder import MAX_BATCH_SIZE, FolderService
from ..services.resource import ROOT_FOLDER_RID, ROOT_FOLDER_UNSUPPORTED
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()

#: Table/CSV columns for a ``Folder`` model.
FOLDER_COLUMNS: Columns = {
    "RID": "rid",
    "Display Name": "display_name",
    "Path": "path",
    "Description": "description",
    "Parent Folder": "parent_folder_rid",
    "Project": "project_rid",
    "Space": "space_rid",
    "Trash Status": "trash_status",
    "Created": "created_time",
    "Created By": "created_by",
    "Updated": "updated_time",
    "Updated By": "updated_by",
}

#: Table/CSV columns for the ``Resource`` models returned by ``folder list``.
CHILD_COLUMNS: Columns = {
    "Type": "type",
    "Display Name": "display_name",
    "RID": "rid",
    "Updated": "updated_time",
}

#: Table/CSV columns for ``folder batch-get`` (one row per ``Folder``).
BATCH_COLUMNS: Columns = {
    "Display Name": "display_name",
    "RID": "rid",
    "Path": "path",
    "Parent Folder": "parent_folder_rid",
}

FolderRid = Annotated[
    str,
    resource_argument(
        "folder",
        help="Folder RID (ri.compass.main.folder.<id>).",
        autocompletion=complete_rid,
    ),
]


@app.command("create")
@pltr_command(sdk="filesystem.Folder.create")
def create_folder(
    name: Annotated[str, typer.Argument(help="Display name of the new folder.")],
    parent_folder: Annotated[
        str,
        resource_option(
            "--parent-folder",
            "-p",
            kind="folder",
            help=(
                "RID of the project or folder to create the folder in. Folders "
                "can only be created inside a project; find one with "
                "'pltr project list'."
            ),
            autocompletion=complete_rid,
        ),
    ],
    # -p is --parent-folder here, so --profile has no short flag.
    profile: Annotated[Optional[str], profile_option(short=False)] = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create a folder inside a project or another folder."""
    with spinner(f"Creating folder '{name}'..."):
        folder = FolderService(profile=profile).create_folder(
            display_name=name, parent_folder_rid=parent_folder
        )
    cache_rid(folder.rid)
    success(f"Created folder '{folder.display_name}' ({folder.rid})")
    emit(folder, format=format, output=output, columns=FOLDER_COLUMNS, title="Folder")


def _check_not_root(folder_rid: str) -> None:
    """Fail fast on the root folder, which the API can't get or list."""
    if folder_rid == ROOT_FOLDER_RID:
        raise typer.BadParameter(ROOT_FOLDER_UNSUPPORTED, param_hint="'FOLDER_RID'")


@app.command("get")
@pltr_command(sdk="filesystem.Folder.get")
def get_folder(
    folder_rid: FolderRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a folder's metadata."""
    _check_not_root(folder_rid)
    with spinner(f"Fetching folder {folder_rid}..."):
        folder = FolderService(profile=profile).get_folder(folder_rid)
    cache_rid(folder_rid)
    emit(folder, format=format, output=output, columns=FOLDER_COLUMNS, title="Folder")


@app.command("list")
@pltr_command(sdk="filesystem.Folder.children", paged=True)
def list_children(
    folder_rid: Annotated[
        str,
        resource_argument(
            "folder",
            help=(
                "RID of the folder, project or space to list (the API can't "
                "list the root folder: find spaces with 'pltr space list')."
            ),
            autocompletion=complete_rid,
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the resources directly inside a folder.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    _check_not_root(folder_rid)
    service = FolderService(profile=profile)
    with spinner(f"Listing children of folder {folder_rid}..."):
        page = collect_pages(
            lambda token: service.list_children(
                folder_rid, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(folder_rid)
    emit(page, format=format, output=output, columns=CHILD_COLUMNS)


@app.command("batch-get")
@pltr_command(sdk="filesystem.Folder.get_batch")
def get_folders_batch(
    folder_rids: Annotated[
        List[str],
        resource_argument(
            "folder",
            help=f"Folder RIDs, separated by spaces (at most {MAX_BATCH_SIZE}).",
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get several folders in one request.

    JSON output is the API's response: {"data": {"<folder RID>": {...}}}.
    """
    if len(folder_rids) > MAX_BATCH_SIZE:
        raise typer.BadParameter(
            f"at most {MAX_BATCH_SIZE} folder RIDs per request, got {len(folder_rids)}",
            param_hint="FOLDER_RIDS",
        )
    with spinner(f"Fetching {len(folder_rids)} folders..."):
        response = FolderService(profile=profile).get_folders_batch(folder_rids)
    for rid in list(response.data)[:50]:
        cache_rid(rid)
    emit(
        response,
        format=format,
        output=output,
        columns=BATCH_COLUMNS,
        rows=lambda batch: list(batch.data.values()),
    )


@app.callback()
def main():
    """
    Folder operations using foundry-platform-sdk.

    Folders are addressed by RID (ri.compass.main.folder.<id>). Folders live
    inside projects, and projects inside spaces: find a space with
    'pltr space list' and a project with 'pltr project list'. The API can't
    get or list the root folder (ri.compass.main.folder.0).

    Examples:

    \b
        # Create a folder inside a project
        pltr folder create "My Folder" --parent-folder ri.compass.main.folder.xyz123
    \b
        # List a folder's contents (one page; --all for every page)
        pltr folder list ri.compass.main.folder.xyz123
    \b
        # Get folder information as JSON
        pltr folder get ri.compass.main.folder.xyz123 --format json
    """
