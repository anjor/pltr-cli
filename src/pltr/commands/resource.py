"""
Resource commands (Foundry filesystem API).
"""

import difflib
from typing import Any, List, Optional

import typer
from typing_extensions import Annotated

from ..contract import (
    AllPagesOption,
    Columns,
    ForceAliasOption,
    FormatOption,
    MaxPagesOption,
    OutputOption,
    PageSizeOption,
    PageTokenOption,
    ProfileOption,
    YesOption,
    collect_pages,
    confirm_destructive,
    emit,
    format_option,
    output_option,
    pltr_command,
    spinner,
    success,
    warn,
)
from ..services.resource import (
    DEFAULT_MAX_SEARCH_FOLDERS,
    MAX_BATCH_SIZE,
    ROOT_FOLDER_RID,
    ROOT_FOLDER_UNSUPPORTED,
    ResourceService,
    normalize_resource_type,
    resource_types,
)
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()

#: Table/CSV columns for a single ``Resource`` model.
RESOURCE_COLUMNS: Columns = {
    "RID": "rid",
    "Display Name": "display_name",
    "Type": "type",
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

#: Table/CSV columns for lists of ``Resource`` models (one row each).
RESOURCE_LIST_COLUMNS: Columns = {
    "Type": "type",
    "Display Name": "display_name",
    "RID": "rid",
    "Path": "path",
    "Updated": "updated_time",
}

#: ``Resource.markings`` returns marking IDs (strings).
MARKING_COLUMNS: Columns = {"Marking ID": lambda marking_id: marking_id}


def _requirement(item: Any) -> str:
    from foundry_sdk.v2.filesystem.models import Organization

    return "organization" if isinstance(item, Organization) else "marking"


def _requirement_organization(item: Any) -> Optional[str]:
    from foundry_sdk.v2.filesystem.models import Organization

    return item.organization_rid if isinstance(item, Organization) else None


#: Table/CSV columns for ``access-requirements``: one row per ``Organization``
#: or ``Marking`` of the ``AccessRequirements`` response.
ACCESS_REQUIREMENT_COLUMNS: Columns = {
    "Requirement": _requirement,
    "Organization RID": _requirement_organization,
    "Marking ID": "marking_id",
    "Directly Applied": "is_directly_applied",
}

ResourceRid = Annotated[
    str,
    typer.Argument(
        help=(
            "Resource RID (ri.<service>.<instance>.<type>.<id>), for example "
            "a dataset (ri.foundry.main.dataset.<id>) or a folder or project "
            "(ri.compass.main.folder.<id>)."
        ),
        autocompletion=complete_rid,
    ),
]
TypeOption = Annotated[
    Optional[str],
    typer.Option(
        "--type",
        "-t",
        help=(
            "Only show resources of this type: an API type name such as "
            "FOUNDRY_DATASET or COMPASS_FOLDER (case-insensitive; 'dataset' "
            "and 'folder' work too). Filtered locally: the API has no type "
            "filter."
        ),
        show_default=False,
    ),
]
FolderRidOption = Annotated[
    str,
    typer.Option(
        "--folder-rid",
        "-f",
        help=(
            "RID of the folder, project or space (the API can't list the "
            "root folder: find spaces with 'pltr space list')."
        ),
        autocompletion=complete_rid,
        show_default=False,
    ),
]


def _check_not_root(folder_rid: str) -> None:
    """Fail fast on the root folder, which the API can't list."""
    if folder_rid == ROOT_FOLDER_RID:
        raise typer.BadParameter(ROOT_FOLDER_UNSUPPORTED, param_hint="'--folder-rid'")


# On `list` and `search`, -f is --folder-rid, so --format has no short flag.
# -o used to be --format's short flag there; --output gets none, so old
# `-o json` invocations fail instead of writing a file named "json".
FormatNoShortOption = Annotated[str, format_option(short=False)]
OutputNoShortOption = Annotated[Optional[str], output_option(short=False)]
MarkingsOption = Annotated[
    List[str],
    typer.Option(
        "--marking",
        "-m",
        help="Marking ID (repeat for several).",
    ),
]


def _resource_type(value: Optional[str]) -> Optional[str]:
    """Validate --type; returns the API type name."""
    if value is None:
        return None
    try:
        return normalize_resource_type(value)
    except ValueError:
        close = difflib.get_close_matches(
            value.strip().upper(), resource_types(), n=3, cutoff=0.6
        )
        suggestion = f" Did you mean {', '.join(close)}?" if close else ""
        raise typer.BadParameter(
            f"unknown resource type {value!r}. Use an API type name such as "
            f"FOUNDRY_DATASET or COMPASS_FOLDER.{suggestion}",
            param_hint="'--type'",
        ) from None


def _check_batch_size(values: List[str], what: str, hint: str) -> None:
    if len(values) > MAX_BATCH_SIZE:
        raise typer.BadParameter(
            f"at most {MAX_BATCH_SIZE} {what} per request, got {len(values)}",
            param_hint=hint,
        )


@app.command("get")
@pltr_command(sdk="filesystem.Resource.get")
def get_resource(
    resource_rid: ResourceRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a resource's metadata by RID.

    Works for projects, folders, datasets and every other filesystem
    resource. Spaces aren't resources: use 'pltr space get'.
    """
    with spinner(f"Fetching resource {resource_rid}..."):
        resource = ResourceService(profile=profile).get_resource(resource_rid)
    cache_rid(resource_rid)
    emit(
        resource,
        format=format,
        output=output,
        columns=RESOURCE_COLUMNS,
        title="Resource",
    )


@app.command("get-by-path")
@pltr_command(sdk="filesystem.Resource.get_by_path")
def get_resource_by_path(
    path: Annotated[
        str,
        typer.Argument(
            help=(
                "Absolute path of the resource, e.g. '/My Space/My Project/"
                "Sales' (the leading slash is optional)."
            )
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a resource's metadata by its path."""
    with spinner(f"Fetching resource at path '{path}'..."):
        resource = ResourceService(profile=profile).get_resource_by_path(path)
    cache_rid(resource.rid)
    emit(
        resource,
        format=format,
        output=output,
        columns=RESOURCE_COLUMNS,
        title="Resource",
    )


@app.command("list")
@pltr_command(sdk="filesystem.Folder.children", paged=True)
def list_resources(
    folder_rid: FolderRidOption,
    resource_type: TypeOption = None,
    profile: ProfileOption = None,
    format: FormatNoShortOption = "table",
    output: OutputNoShortOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the resources directly inside a folder (not its subfolders).

    --type filters each fetched page locally, so a page can hold fewer items
    than --page-size.
    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    _check_not_root(folder_rid)
    wanted_type = _resource_type(resource_type)
    service = ResourceService(profile=profile)
    with spinner(f"Listing resources in {folder_rid}..."):
        page = collect_pages(
            lambda token: service.list_children(
                folder_rid,
                resource_type=wanted_type,
                page_size=page_size,
                page_token=token,
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(folder_rid)
    emit(page, format=format, output=output, columns=RESOURCE_LIST_COLUMNS)


@app.command("search")
@pltr_command(sdk="filesystem.Folder.children")
def search_resources(
    query: Annotated[
        str,
        typer.Argument(
            help=(
                "Text to look for (case-insensitive) in display names, paths, "
                "descriptions, RIDs and types."
            )
        ),
    ],
    folder_rid: FolderRidOption,
    resource_type: TypeOption = None,
    limit: Annotated[
        Optional[int],
        typer.Option(
            "--limit", min=1, help="Stop after this many matches.", show_default=False
        ),
    ] = None,
    max_folders: Annotated[
        int,
        typer.Option(
            "--max-folders",
            min=1,
            help="Stop after listing this many folders (one request per page each).",
        ),
    ] = DEFAULT_MAX_SEARCH_FOLDERS,
    page_size: Annotated[
        Optional[int],
        typer.Option(
            "--page-size", min=1, hidden=True, help="Deprecated alias for --limit."
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatNoShortOption = "table",
    output: OutputNoShortOption = None,
):
    """Find resources below a folder by name, path, description, RID or type.

    The Foundry API has no search endpoint, so pltr scans: it lists the
    children of --folder-rid and of every folder below it, breadth-first, and
    matches QUERY locally. Each folder costs at
    least one request, so start from the narrowest folder you can. After
    --max-folders folders it stops and warns that the results may be
    incomplete. Output is {"data": [...]}, with no nextPageToken.
    """
    if not query.strip():
        raise typer.BadParameter("the search query is empty", param_hint="'QUERY'")
    if page_size is not None:
        warn("--page-size is deprecated for 'resource search'; use --limit.")
        if limit is None:
            limit = page_size
    _check_not_root(folder_rid)
    wanted_type = _resource_type(resource_type)
    with spinner(f"Searching {folder_rid} for '{query}'..."):
        result = ResourceService(profile=profile).search_resources(
            query,
            folder_rid=folder_rid,
            resource_type=wanted_type,
            limit=limit,
            max_folders=max_folders,
        )
    if result.truncated:
        warn(
            f"Stopped after listing {result.folders_scanned} folders "
            "(--max-folders): the results may be incomplete. Search a narrower "
            "--folder-rid or raise --max-folders."
        )
    emit(result.matches, format=format, output=output, columns=RESOURCE_LIST_COLUMNS)


@app.command("batch-get")
@pltr_command(sdk="filesystem.Resource.get_batch")
def get_resources_batch(
    resource_rids: Annotated[
        List[str],
        typer.Argument(
            help=f"Resource RIDs, separated by spaces (at most {MAX_BATCH_SIZE})."
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get several resources in one request.

    JSON output is the API's response: {"data": {"<RID>": {...}}}. RIDs that
    don't exist or that you can't read are left out, with a warning.
    """
    _check_batch_size(resource_rids, "resource RIDs", "RESOURCE_RIDS")
    with spinner(f"Fetching {len(resource_rids)} resources..."):
        response = ResourceService(profile=profile).get_resources_batch(resource_rids)
    missing = [rid for rid in dict.fromkeys(resource_rids) if rid not in response.data]
    if missing:
        warn(f"Not found or not readable: {', '.join(missing)}")
    for rid in list(response.data)[:50]:
        cache_rid(rid)
    emit(
        response,
        format=format,
        output=output,
        columns=RESOURCE_LIST_COLUMNS,
        rows=lambda batch: list(batch.data.values()),
    )


@app.command("batch-get-by-path")
@pltr_command(sdk="filesystem.Resource.get_by_path_batch")
def get_resources_by_path_batch(
    paths: Annotated[
        List[str],
        typer.Argument(
            help=(
                "Absolute resource paths, separated by spaces (at most "
                f"{MAX_BATCH_SIZE}); quote paths that contain spaces."
            )
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get several resources by path in one request.

    JSON output is the API's response: {"data": [...]}. Paths that don't
    exist or that you can't read are left out, with a warning.
    """
    _check_batch_size(paths, "paths", "PATHS")
    with spinner(f"Fetching {len(paths)} resources by path..."):
        response = ResourceService(profile=profile).get_resources_by_path_batch(paths)
    found = {resource.path.strip("/") for resource in response.data}
    missing = [path for path in dict.fromkeys(paths) if path.strip("/") not in found]
    if missing:
        warn(f"Not found or not readable: {', '.join(missing)}")
    for resource in response.data[:50]:
        cache_rid(resource.rid)
    emit(
        response,
        format=format,
        output=output,
        columns=RESOURCE_LIST_COLUMNS,
        rows=lambda batch: batch.data,
    )


# ==================== Trash Operations ====================


@app.command("delete")
@pltr_command(sdk="filesystem.Resource.delete", destructive=True)
def delete_resource(
    resource_rid: ResourceRid,
    yes: YesOption = False,
    force: ForceAliasOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Move a resource to the trash.

    Restore it with 'pltr resource restore', or delete it for good with
    'pltr resource permanently-delete'. Asks for confirmation; --yes skips
    it. Prints nothing on stdout (JSON: null).
    """
    confirm_destructive(f"Move resource {resource_rid} to the trash?", yes=yes)
    with spinner(f"Moving resource {resource_rid} to the trash..."):
        ResourceService(profile=profile).delete_resource(resource_rid)
    success(f"Moved resource {resource_rid} to the trash")
    emit(None, format=format)


@app.command("restore")
@pltr_command(sdk="filesystem.Resource.restore")
def restore_resource(
    resource_rid: ResourceRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Restore a resource, and its directly trashed ancestors, from the trash.

    Prints nothing on stdout (JSON: null).
    """
    with spinner(f"Restoring resource {resource_rid}..."):
        ResourceService(profile=profile).restore_resource(resource_rid)
    cache_rid(resource_rid)
    success(f"Restored resource {resource_rid} from the trash")
    emit(None, format=format)


@app.command("permanently-delete")
@pltr_command(sdk="filesystem.Resource.permanently_delete", destructive=True)
def permanently_delete_resource(
    resource_rid: ResourceRid,
    yes: YesOption = False,
    force: ForceAliasOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Permanently delete a resource that is in the trash. This can't be undone.

    Move the resource to the trash first ('pltr resource delete'). Asks for
    confirmation; --yes skips it. Prints nothing on stdout (JSON: null).
    """
    confirm_destructive(
        f"PERMANENTLY delete resource {resource_rid}? This can't be undone.",
        yes=yes,
    )
    with spinner(f"Permanently deleting resource {resource_rid}..."):
        ResourceService(profile=profile).permanently_delete_resource(resource_rid)
    success(f"Permanently deleted resource {resource_rid}")
    emit(None, format=format)


# ==================== Markings Operations ====================


@app.command("add-markings")
@pltr_command(sdk="filesystem.Resource.add_markings")
def add_markings(
    resource_rid: ResourceRid,
    marking_ids: MarkingsOption,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Apply markings to a resource.

    Prints nothing on stdout (JSON: null).
    """
    with spinner(f"Adding {len(marking_ids)} marking(s) to {resource_rid}..."):
        ResourceService(profile=profile).add_markings(resource_rid, marking_ids)
    success(f"Added {len(marking_ids)} marking(s) to resource {resource_rid}")
    emit(None, format=format)


@app.command("remove-markings")
@pltr_command(sdk="filesystem.Resource.remove_markings", destructive=True)
def remove_markings(
    resource_rid: ResourceRid,
    marking_ids: MarkingsOption,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Remove markings from a resource.

    Asks for confirmation; --yes skips it. Prints nothing on stdout (JSON:
    null).
    """
    confirm_destructive(
        f"Remove marking(s) {', '.join(marking_ids)} from resource {resource_rid}?",
        yes=yes,
    )
    with spinner(f"Removing {len(marking_ids)} marking(s) from {resource_rid}..."):
        ResourceService(profile=profile).remove_markings(resource_rid, marking_ids)
    success(f"Removed {len(marking_ids)} marking(s) from resource {resource_rid}")
    emit(None, format=format)


@app.command("list-markings")
@pltr_command(sdk="filesystem.Resource.markings", paged=True)
def list_markings(
    resource_rid: ResourceRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the IDs of the markings applied directly to a resource.

    Inherited markings aren't listed: 'pltr resource access-requirements'
    shows every marking and organization needed to view the resource.
    Fetches one page by default; use --all for every page.
    """
    service = ResourceService(profile=profile)
    with spinner(f"Listing markings of {resource_rid}..."):
        page = collect_pages(
            lambda token: service.list_markings(
                resource_rid, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(resource_rid)
    emit(page, format=format, output=output, columns=MARKING_COLUMNS)


# ==================== Access Requirements ====================


@app.command("access-requirements")
@pltr_command(sdk="filesystem.Resource.get_access_requirements")
def get_access_requirements(
    resource_rid: ResourceRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Show the organizations and markings a user needs to view a resource.

    Includes inherited requirements. Table and CSV show one row per
    requirement; JSON is the API response ({"organizations": [...],
    "markings": [...]}).
    """
    with spinner(f"Fetching access requirements of {resource_rid}..."):
        requirements = ResourceService(profile=profile).get_access_requirements(
            resource_rid
        )
    cache_rid(resource_rid)
    emit(
        requirements,
        format=format,
        output=output,
        columns=ACCESS_REQUIREMENT_COLUMNS,
        rows=lambda response: [*response.organizations, *response.markings],
    )


@app.callback()
def main():
    """
    Resource operations using foundry-platform-sdk.

    Work with any filesystem resource (projects, folders, datasets, ...) by
    RID or by path: get metadata, list a folder, search below a folder, move
    to and restore from the trash, and manage markings. RIDs look like
    ri.<service>.<instance>.<type>.<id>; folders and projects are
    ri.compass.main.folder.<id>, datasets ri.foundry.main.dataset.<id>.

    Examples:

    \b
        # Get a resource by RID, or by path
        pltr resource get ri.foundry.main.dataset.xyz123
        pltr resource get-by-path "/My Space/My Project/Sales"
    \b
        # List a folder's datasets (one page; --all for every page)
        pltr resource list --folder-rid ri.compass.main.folder.abc456 --type dataset
    \b
        # Search a project for "sales" (scans its folders)
        pltr resource search "sales" --folder-rid ri.compass.main.folder.abc456
    \b
        # Trash, restore, permanently delete (asks for confirmation; --yes skips it)
        pltr resource delete ri.foundry.main.dataset.xyz123
        pltr resource restore ri.foundry.main.dataset.xyz123
        pltr resource permanently-delete ri.foundry.main.dataset.xyz123
    \b
        # Markings and access requirements
        pltr resource add-markings ri.foundry.main.dataset.xyz123 -m <MARKING_ID>
        pltr resource list-markings ri.foundry.main.dataset.xyz123
        pltr resource access-requirements ri.foundry.main.dataset.xyz123
    """
