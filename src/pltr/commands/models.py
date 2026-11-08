"""
Model registry commands: models and model versions (Foundry models API).

This is distinct from `pltr language-models` (LLM chat and embeddings).
Every endpoint used here is beta, so every command is labeled [beta].
"""

from typing import Any, List, Optional

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
    PreviewNoopOption,
    ProfileOption,
    collect_pages,
    emit,
    format_option,
    pltr_command,
    resource_argument,
    resource_option,
    spinner,
    success,
)
from ..services.models import ModelsService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer(help="Manage ML models and versions")
model_app = typer.Typer(help="Create and inspect models")
version_app = typer.Typer(help="Inspect model versions")
app.add_typer(model_app, name="model")
app.add_typer(version_app, name="version")


def _api_fields(items: List[Any]) -> str:
    """``name (kind)`` of each model API input or output."""
    names = []
    for item in items:
        if item.type in ("parameter", "tabular"):
            names.append(f"{item.name} ({item.type})")
        else:  # unsupported, or a kind added in a newer SDK
            names.append(item.type)
    return ", ".join(names)


#: Table/CSV columns for a ``Model`` (the API returns only its RID).
MODEL_COLUMNS: Columns = {"RID": "rid"}

#: Table/CSV columns for a ``ModelVersion``.
VERSION_COLUMNS: Columns = {
    "RID": "rid",
    "Created": "created_time",
    "Source": "source.type",
    "Linked Experiment": "linked_experiment",
    "Inputs": lambda version: _api_fields(version.model_api.inputs),
    "Outputs": lambda version: _api_fields(version.model_api.outputs),
    "Conda Requirements": lambda version: ", ".join(version.conda_requirements),
    "Backing Repositories": lambda version: ", ".join(version.backing_repositories),
}

#: Table/CSV columns for lists of model versions (one row per ``ModelVersion``).
VERSION_LIST_COLUMNS: Columns = {
    "RID": "rid",
    "Created": "created_time",
    "Source": "source.type",
    "Linked Experiment": "linked_experiment",
}

ModelRid = Annotated[
    str,
    resource_argument(
        "model",
        help="Model RID (shown when the model is created).",
        autocompletion=complete_rid,
    ),
]


@model_app.command("create")
@pltr_command(sdk="models.Model.create", beta=True)
def create_model(
    name: Annotated[str, typer.Argument(help="Name of the new model.")],
    folder: Annotated[
        str,
        resource_option(
            "--folder",
            "-f",
            kind="folder",
            help=(
                "RID of the folder or project to create the model in "
                "(ri.compass.main.folder.<id>)."
            ),
            autocompletion=complete_rid,
        ),
    ],
    profile: ProfileOption = None,
    # -f is --folder here, so --format has no short flag.
    format: Annotated[str, format_option(short=False)] = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Create a model (with no versions) in the model registry.

    The API can't list models, so keep the RID it returns.

    Examples:

    \b
        pltr models model create "fraud-detector" --folder ri.compass.main.folder.xyz
        pltr models model create "fraud-detector" -f ri.compass.main.folder.xyz \\
            --format json
    """
    with spinner(f"Creating model '{name}'..."):
        model = ModelsService(profile=profile).create_model(
            name=name, parent_folder_rid=folder
        )
    cache_rid(model.rid)
    success(f"Created model '{name}' ({model.rid})")
    emit(model, format=format, output=output, columns=MODEL_COLUMNS, title="Model")


@model_app.command("get")
@pltr_command(sdk="models.Model.get", beta=True)
def get_model(
    model_rid: ModelRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Get a model. The API returns only its RID; this confirms it exists.

    List its versions with 'pltr models version list <MODEL_RID>'.
    """
    with spinner(f"Fetching model {model_rid}..."):
        model = ModelsService(profile=profile).get_model(model_rid)
    cache_rid(model_rid)
    emit(model, format=format, output=output, columns=MODEL_COLUMNS, title="Model")


@version_app.command("get")
@pltr_command(sdk="models.Model.Version.get", beta=True)
def get_version(
    model_rid: ModelRid,
    model_version_rid: Annotated[
        str,
        typer.Argument(
            help=(
                "Model version RID (find it with "
                "'pltr models version list <MODEL_RID>')."
            ),
            autocompletion=complete_rid,
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Get a model version: its API (inputs, outputs), dependencies and source.

    Examples:

    \b
        pltr models version get <MODEL_RID> <MODEL_VERSION_RID>
        pltr models version get <MODEL_RID> <MODEL_VERSION_RID> --format json
    """
    with spinner(f"Fetching model version {model_version_rid}..."):
        version = ModelsService(profile=profile).get_model_version(
            model_rid, model_version_rid
        )
    cache_rid(model_rid)
    cache_rid(model_version_rid)
    emit(
        version,
        format=format,
        output=output,
        columns=VERSION_COLUMNS,
        title="Model Version",
    )


@version_app.command("list")
@pltr_command(sdk="models.Model.Version.list", beta=True, paged=True)
def list_versions(
    model_rid: ModelRid,
    branch: Annotated[
        Optional[str],
        typer.Option(
            "--branch",
            help="Branch to list versions from (the API's default is usually master).",
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
    preview: PreviewNoopOption = False,
):
    """List a model's versions.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.

    Examples:

    \b
        pltr models version list <MODEL_RID>
        pltr models version list <MODEL_RID> --all --format json
    """
    service = ModelsService(profile=profile)
    with spinner(f"Listing versions of model {model_rid}..."):
        page = collect_pages(
            lambda token: service.list_model_versions(
                model_rid, branch=branch, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(model_rid)
    emit(page, format=format, output=output, columns=VERSION_LIST_COLUMNS)
