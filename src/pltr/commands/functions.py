"""
Functions commands: queries and value types (Foundry Functions API).

Every Functions endpoint pltr uses is beta, so every command is labeled
[beta].
"""

from typing import Any, List, Optional

import click
import typer
from typing_extensions import Annotated

from ..contract import (
    Columns,
    FormatOption,
    OutputOption,
    PreviewNoopOption,
    ProfileOption,
    emit,
    load_json_input,
    pltr_command,
    spinner,
)
from ..services.functions import FunctionsService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer(help="Manage Functions queries and value types")
query_app = typer.Typer(help="Inspect and execute queries")
value_type_app = typer.Typer(help="Inspect value types")
app.add_typer(query_app, name="query")
app.add_typer(value_type_app, name="value-type")


def _query_parameters(query: Any) -> str:
    """``name (type)`` for each parameter, marking the optional ones."""
    return ", ".join(
        f"{name} ({parameter.data_type.type}"
        + ("" if parameter.required else ", optional")
        + ")"
        for name, parameter in query.parameters.items()
    )


#: Table/CSV columns for a ``Query``.
QUERY_COLUMNS: Columns = {
    "API Name": "api_name",
    "Display Name": "display_name",
    "Description": "description",
    "RID": "rid",
    "Version": "version",
    "Parameters": _query_parameters,
    "Output Type": "output.type",
}

#: Table/CSV columns for a ``ValueType``.
VALUE_TYPE_COLUMNS: Columns = {
    "RID": "rid",
    "API Name": "api_name",
    "Display Name": "display_name",
    "Description": "description",
    "Version": "version",
    "Version ID": "version_id",
    "Base Type": "base_type.type",
    "Constraints": "constraints",
}


def _result_rows(response: Any) -> List[Any]:
    """Table/CSV rows of a query result: one per item of a list result."""
    value = response.value
    return list(value) if isinstance(value, list) else [value]


QueryApiName = Annotated[
    str,
    typer.Argument(help="Query API name (e.g. myQuery)."),
]
QueryRid = Annotated[
    str,
    typer.Argument(help="Query RID.", autocompletion=complete_rid),
]
VersionOption = Annotated[
    Optional[str],
    typer.Option(
        "--version",
        "-v",
        help="Query version (e.g. 1.0.0). Default: the latest version.",
    ),
]
IncludePrereleaseOption = Annotated[
    bool,
    typer.Option(
        "--include-prerelease",
        help=(
            "Without --version, let the latest version be a pre-release "
            "(e.g. 1.2.3-beta)."
        ),
    ),
]
LatestVersionResolutionOption = Annotated[
    Optional[str],
    typer.Option(
        "--latest-version-resolution",
        help=(
            "Without --version, how the latest version is picked: "
            "SEMANTIC_VERSION (the highest version, the API's default) or "
            "PUBLISH_TIME (the most recently published, pre-releases "
            "included)."
        ),
        click_type=click.Choice(
            ("SEMANTIC_VERSION", "PUBLISH_TIME"), case_sensitive=False
        ),
        show_default=False,
    ),
]
ParametersOption = Annotated[
    Optional[str],
    typer.Option(
        "--parameters",
        "-params",
        help=(
            "Query parameters as a JSON object or @file.json, keyed by "
            "parameter name (default: no parameters)."
        ),
    ),
]


def _flag(value: bool) -> Optional[bool]:
    """Send a flag only when it is set, so the API's default applies otherwise."""
    return True if value else None


def _upper(value: Optional[str]) -> Optional[str]:
    return value.upper() if value else None


def _parameters(value: Optional[str]) -> Any:
    if value is None:
        return {}
    return load_json_input(value, param_hint="'--parameters'")


@query_app.command("get")
@pltr_command(sdk="functions.Query.get", beta=True)
def get_query(
    query_api_name: QueryApiName,
    version: VersionOption = None,
    include_prerelease: IncludePrereleaseOption = False,
    latest_version_resolution: LatestVersionResolutionOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Get a query's definition (parameters, output type, version) by API name.

    Examples:

    \b
        pltr functions query get myQuery
        pltr functions query get myQuery --version 1.0.0 --format json
        pltr functions query get myQuery --latest-version-resolution PUBLISH_TIME
    """
    with spinner(f"Fetching query '{query_api_name}'..."):
        query = FunctionsService(profile=profile).get_query(
            query_api_name,
            version=version,
            include_prerelease=_flag(include_prerelease),
            latest_version_resolution=_upper(latest_version_resolution),
        )
    cache_rid(query.rid)
    emit(query, format=format, output=output, columns=QUERY_COLUMNS, title="Query")


@query_app.command("get-by-rid")
@pltr_command(sdk="functions.Query.get_by_rid", beta=True)
def get_query_by_rid(
    query_rid: QueryRid,
    version: VersionOption = None,
    include_prerelease: IncludePrereleaseOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Get a query's definition by RID.

    Examples:

    \b
        pltr functions query get-by-rid <QUERY_RID>
        pltr functions query get-by-rid <QUERY_RID> --version 1.0.0 --format json
    """
    with spinner(f"Fetching query {query_rid}..."):
        query = FunctionsService(profile=profile).get_query_by_rid(
            query_rid,
            version=version,
            include_prerelease=_flag(include_prerelease),
        )
    cache_rid(query_rid)
    emit(query, format=format, output=output, columns=QUERY_COLUMNS, title="Query")


@query_app.command("execute")
@pltr_command(sdk="functions.Query.execute", beta=True)
def execute_query(
    query_api_name: QueryApiName,
    parameters: ParametersOption = None,
    version: VersionOption = None,
    include_prerelease: IncludePrereleaseOption = False,
    latest_version_resolution: LatestVersionResolutionOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Execute a query by API name.

    Parameter values are JSON: strings, numbers, booleans, lists and objects;
    dates and timestamps as ISO-8601 strings. JSON output is the API's
    response, {"value": <result>}. Table and CSV output show one row per item
    when the result is a list.

    Examples:

    \b
        pltr functions query execute myQuery --parameters '{"limit": 10}'
        pltr functions query execute myQuery --parameters @params.json
        pltr functions query execute myQuery --version 1.0.0 --format json
    """
    params = _parameters(parameters)
    with spinner(f"Executing query '{query_api_name}'..."):
        result = FunctionsService(profile=profile).execute_query(
            query_api_name,
            parameters=params,
            version=version,
            include_prerelease=_flag(include_prerelease),
            latest_version_resolution=_upper(latest_version_resolution),
        )
    emit(result, format=format, output=output, rows=_result_rows)


@query_app.command("execute-by-rid")
@pltr_command(sdk=("functions.Query.get_by_rid", "functions.Query.execute"), beta=True)
def execute_query_by_rid(
    query_rid: QueryRid,
    parameters: ParametersOption = None,
    version: VersionOption = None,
    include_prerelease: IncludePrereleaseOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Execute a query given its RID.

    The API executes queries by API name, so pltr first looks the query up by
    RID and then executes the version it found (--version, or the latest).
    JSON output is the API's response, {"value": <result>}.

    Examples:

    \b
        pltr functions query execute-by-rid <QUERY_RID> --parameters '{"limit": 10}'
    """
    params = _parameters(parameters)
    with spinner(f"Executing query {query_rid}..."):
        result = FunctionsService(profile=profile).execute_query_by_rid(
            query_rid,
            parameters=params,
            version=version,
            include_prerelease=_flag(include_prerelease),
        )
    cache_rid(query_rid)
    emit(result, format=format, output=output, rows=_result_rows)


@value_type_app.command("get")
@pltr_command(sdk="functions.ValueType.get", beta=True)
def get_value_type(
    value_type_rid: Annotated[
        str, typer.Argument(help="Value type RID.", autocompletion=complete_rid)
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Get a value type: its base type, constraints and version.

    Examples:

    \b
        pltr functions value-type get <VALUE_TYPE_RID>
        pltr functions value-type get <VALUE_TYPE_RID> --format json
    """
    with spinner(f"Fetching value type {value_type_rid}..."):
        value_type = FunctionsService(profile=profile).get_value_type(value_type_rid)
    cache_rid(value_type_rid)
    emit(
        value_type,
        format=format,
        output=output,
        columns=VALUE_TYPE_COLUMNS,
        title="Value Type",
    )
