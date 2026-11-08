"""
Widget set commands (Foundry Widgets API).

Every Widgets endpoint is beta, so every command here is labeled [beta] and
pltr calls it with preview=True. Dev mode settings and repository publishing
have no curated command; use the generated ones (``pltr api widgets ...``).
"""

from typing import Optional

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
    YesOption,
    collect_pages,
    confirm_destructive,
    emit,
    pltr_command,
    resource_argument,
    spinner,
    success,
)
from ..services.widgets import WidgetsService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()
release_app = typer.Typer(help="Releases of a widget set.")
repository_app = typer.Typer(help="Repositories that store widget set releases.")

app.add_typer(release_app, name="release")
app.add_typer(repository_app, name="repository")

#: Table/CSV columns for a ``WidgetSet`` model.
WIDGET_SET_COLUMNS: Columns = {
    "RID": "rid",
    "Publish Repository": "publish_repository_rid",
}

#: Table/CSV columns for a ``Release`` model.
RELEASE_COLUMNS: Columns = {
    "Version": "version",
    "Description": "description",
    "Widget Set": "widget_set_rid",
    "Repository": "locator.repository_rid",
    "Repository Version": "locator.repository_version",
}

#: Table/CSV columns for a ``Repository`` model.
REPOSITORY_COLUMNS: Columns = {
    "RID": "rid",
    "Widget Set": "widget_set_rid",
}

WidgetSetRid = Annotated[
    str,
    typer.Argument(
        help="Widget set RID (ri.widgetregistry..widget-set.<id>).",
        autocompletion=complete_rid,
    ),
]
ReleaseVersion = Annotated[
    str,
    typer.Argument(help="Release version (a semantic version, e.g. 1.2.0)."),
]


@app.command("get")
@pltr_command(sdk="widgets.WidgetSet.get", beta=True)
def get_widget_set(
    widget_set_rid: WidgetSetRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a widget set."""
    with spinner(f"Fetching widget set {widget_set_rid}..."):
        widget_set = WidgetsService(profile=profile).get_widget_set(widget_set_rid)
    cache_rid(widget_set_rid)
    emit(
        widget_set,
        format=format,
        output=output,
        columns=WIDGET_SET_COLUMNS,
        title="Widget Set",
    )


@release_app.command("list")
@pltr_command(sdk="widgets.WidgetSet.Release.list", beta=True, paged=True)
def list_releases(
    widget_set_rid: WidgetSetRid,
    branch: Annotated[
        Optional[str],
        typer.Option(
            "--branch",
            help=(
                "Foundry branch (RID or branch name) to list releases from "
                "(default: the default branch)."
            ),
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
    """List the releases of a widget set.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = WidgetsService(profile=profile)
    with spinner(f"Listing releases of widget set {widget_set_rid}..."):
        page = collect_pages(
            lambda token: service.list_releases(
                widget_set_rid, branch=branch, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(widget_set_rid)
    emit(page, format=format, output=output, columns=RELEASE_COLUMNS)


@release_app.command("get")
@pltr_command(sdk="widgets.WidgetSet.Release.get", beta=True)
def get_release(
    widget_set_rid: WidgetSetRid,
    release_version: ReleaseVersion,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a release of a widget set."""
    with spinner(f"Fetching release {release_version}..."):
        release = WidgetsService(profile=profile).get_release(
            widget_set_rid, release_version
        )
    cache_rid(widget_set_rid)
    emit(
        release, format=format, output=output, columns=RELEASE_COLUMNS, title="Release"
    )


@release_app.command("delete")
@pltr_command(sdk="widgets.WidgetSet.Release.delete", beta=True, destructive=True)
def delete_release(
    widget_set_rid: WidgetSetRid,
    release_version: ReleaseVersion,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Delete a release of a widget set."""
    confirm_destructive(
        f"Delete release {release_version} of widget set {widget_set_rid}?", yes=yes
    )
    with spinner(f"Deleting release {release_version}..."):
        WidgetsService(profile=profile).delete_release(widget_set_rid, release_version)
    cache_rid(widget_set_rid)
    success(f"Deleted release {release_version} of widget set {widget_set_rid}")
    emit(None, format=format)


@repository_app.command("get")
@pltr_command(sdk="widgets.Repository.get", beta=True)
def get_repository(
    repository_rid: Annotated[
        str,
        resource_argument(
            "repository",
            help="Repository RID (ri.stemma.main.repository.<id>).",
            autocompletion=complete_rid,
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a widget repository."""
    with spinner(f"Fetching repository {repository_rid}..."):
        repository = WidgetsService(profile=profile).get_repository(repository_rid)
    cache_rid(repository_rid)
    emit(
        repository,
        format=format,
        output=output,
        columns=REPOSITORY_COLUMNS,
        title="Widget Repository",
    )
