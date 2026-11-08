"""
Connectivity commands (Foundry connectivity API): connections, file imports
and table imports.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    ProfileOption,
    YesOption,
    collect_pages,
    confirm_destructive,
    emit,
    load_json_input,
    pltr_command,
    resource_argument,
    spinner,
    success,
)
from ..services.connectivity import ConnectivityService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()
connection_app = typer.Typer()
import_app = typer.Typer()

app.add_typer(connection_app, name="connection", help="Manage connections")
app.add_typer(import_app, name="import", help="Manage file and table imports")


# ------------------------------------------------------------------ columns


def _egress_policies(connection: Any) -> Optional[str]:
    worker = connection.worker
    if worker.type != "foundryWorker":
        return None
    return ", ".join(worker.network_egress_policy_rids)


def _jdbc_drivers(connection: Any) -> Optional[str]:
    configuration = connection.configuration
    if configuration.type != "jdbc":
        return None
    return ", ".join(configuration.uploaded_jdbc_drivers)


#: Table/CSV columns for a ``Connection`` model.
CONNECTION_COLUMNS: Columns = {
    "RID": "rid",
    "Display Name": "display_name",
    "Parent Folder": "parent_folder_rid",
    "Configuration Type": "configuration.type",
    "Worker": "worker.type",
    "Network Egress Policies": _egress_policies,
    "Exports Enabled": "export_settings.exports_enabled",
    "Exports Without Markings Validation": (
        "export_settings.export_enabled_without_markings_validation"
    ),
}

#: ``connection upload-jdbc-drivers``: a ``Connection`` and its JDBC drivers.
JDBC_CONNECTION_COLUMNS: Columns = {
    **CONNECTION_COLUMNS,
    "JDBC Drivers": _jdbc_drivers,
}

#: Table/CSV columns for a ``FileImport`` model.
FILE_IMPORT_COLUMNS: Columns = {
    "RID": "rid",
    "Display Name": "display_name",
    "Connection": "connection_rid",
    "Dataset": "dataset_rid",
    "Branch": "branch_name",
    "Import Mode": "import_mode",
    "Subfolder": "subfolder",
    "Filters": "file_import_filters",
}

#: Table/CSV columns for ``import list-file`` (one row per ``FileImport``).
FILE_IMPORT_LIST_COLUMNS: Columns = {
    "Display Name": "display_name",
    "RID": "rid",
    "Dataset": "dataset_rid",
    "Import Mode": "import_mode",
    "Subfolder": "subfolder",
}

#: Table/CSV columns for a ``TableImport`` model.
TABLE_IMPORT_COLUMNS: Columns = {
    "RID": "rid",
    "Display Name": "display_name",
    "Connection": "connection_rid",
    "Dataset": "dataset_rid",
    "Branch": "branch_name",
    "Import Mode": "import_mode",
    "Allow Schema Changes": "allow_schema_changes",
    "Config Type": "config.type",
    "Query": "config.query",
}

#: Table/CSV columns for ``import list-table`` (one row per ``TableImport``).
TABLE_IMPORT_LIST_COLUMNS: Columns = {
    "Display Name": "display_name",
    "RID": "rid",
    "Dataset": "dataset_rid",
    "Import Mode": "import_mode",
    "Config Type": "config.type",
}

#: Table/CSV columns for the build RID that ``execute-file``/``execute-table`` return.
BUILD_COLUMNS: Columns = {"Build RID": lambda build_rid: build_rid}


# ---------------------------------------------------------------- arguments

ConnectionRid = Annotated[
    str,
    resource_argument(
        "connection",
        help=(
            "Connection RID (a Data Connection source, e.g. ri.magritte..source.<id>)."
        ),
        autocompletion=complete_rid,
        show_default=False,
    ),
]
DatasetRid = Annotated[
    str,
    resource_argument(
        "dataset",
        help=(
            "RID of the dataset the import writes to "
            "(ri.foundry.main.dataset.<id>); it can't be changed later."
        ),
        autocompletion=complete_rid,
        show_default=False,
    ),
]
FileImportRid = Annotated[
    str,
    typer.Argument(
        help="File import RID (find it with 'pltr connectivity import list-file').",
        autocompletion=complete_rid,
        show_default=False,
    ),
]
TableImportRid = Annotated[
    str,
    typer.Argument(
        help="Table import RID (find it with 'pltr connectivity import list-table').",
        autocompletion=complete_rid,
        show_default=False,
    ),
]
NameOption = Annotated[
    str,
    typer.Option(
        "--name", "-n", help="Display name of the import.", show_default=False
    ),
]
BranchOption = Annotated[
    Optional[str],
    typer.Option(
        "--branch",
        help="Dataset branch to write to (default: the API's, usually master).",
        show_default=False,
    ),
]


def _json_object(
    value: Optional[str],
    file: Optional[str],
    *,
    argument: str,
    file_option: str,
) -> Dict[str, Any]:
    """A JSON object given inline or as @file.json, or in a file option."""
    if value is not None and file is not None:
        raise typer.BadParameter(
            f"pass {argument} or {file_option}, not both", param_hint=file_option
        )
    if value is None and file is None:
        raise typer.BadParameter(
            f"pass {argument} as JSON (inline or @file.json), or {file_option} FILE",
            param_hint=argument,
        )
    hint = argument if value is not None else file_option
    data = load_json_input(value if value is not None else f"@{file}", param_hint=hint)
    if not isinstance(data, dict):
        raise typer.BadParameter("expected a JSON object", param_hint=hint)
    return data


def _report_build(build_rid: str, kind: str, import_rid: str) -> None:
    cache_rid(build_rid)
    success(
        f"Started build {build_rid} for {kind} import {import_rid}; follow it "
        f"with 'pltr orchestration builds get {build_rid}'"
    )


# ------------------------------------------------------------- connections


@connection_app.command("get")
@pltr_command(sdk="connectivity.Connection.get")
def get_connection(
    connection_rid: ConnectionRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a connection: its configuration type, worker and export settings."""
    with spinner(f"Fetching connection {connection_rid}..."):
        connection = ConnectivityService(profile=profile).get_connection(connection_rid)
    cache_rid(connection_rid)
    emit(
        connection,
        format=format,
        output=output,
        columns=CONNECTION_COLUMNS,
        title="Connection",
    )


@connection_app.command("create")
@pltr_command(sdk="connectivity.Connection.create")
def create_connection(
    display_name: Annotated[
        str,
        typer.Argument(help="Display name of the connection.", show_default=False),
    ],
    parent_folder_rid: Annotated[
        str,
        resource_argument(
            "folder",
            help="RID of the folder to create the connection in.",
            autocompletion=complete_rid,
            show_default=False,
        ),
    ],
    configuration: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Connection configuration as JSON (inline or @file.json), with "
                'its "type": s3, rest, snowflake, databricks, smb or jdbc.'
            ),
            show_default=False,
        ),
    ] = None,
    worker: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                'Worker as JSON (inline or @file.json), e.g. {"type": '
                '"foundryWorker", "networkEgressPolicyRids": ["<RID>"]}.'
            ),
            show_default=False,
        ),
    ] = None,
    config_file: Annotated[
        Optional[str],
        typer.Option(
            "--config-file",
            help="JSON file with the configuration.",
            show_default=False,
        ),
    ] = None,
    worker_file: Annotated[
        Optional[str],
        typer.Option(
            "--worker-file", help="JSON file with the worker.", show_default=False
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create a connection with a direct-connection (Foundry worker) runtime.

    CONFIGURATION and WORKER use the API's JSON field names. Secrets in the
    configuration are sent to Foundry over TLS.

    Example:

    \b
    pltr connectivity connection create "My API" <FOLDER_RID> \\
        '{"type": "rest", "domains": [{"host": "api.example.com"}]}' \\
        '{"type": "foundryWorker", "networkEgressPolicyRids": ["<RID>"]}'
    """
    configuration_json = _json_object(
        configuration,
        config_file,
        argument="CONFIGURATION",
        file_option="--config-file",
    )
    worker_json = _json_object(
        worker, worker_file, argument="WORKER", file_option="--worker-file"
    )
    with spinner("Creating connection..."):
        connection = ConnectivityService(profile=profile).create_connection(
            display_name=display_name,
            parent_folder_rid=parent_folder_rid,
            configuration=configuration_json,
            worker=worker_json,
        )
    cache_rid(connection.rid)
    success(f"Created connection '{connection.display_name}' ({connection.rid})")
    emit(
        connection,
        format=format,
        output=output,
        columns=CONNECTION_COLUMNS,
        title="Connection",
    )


@connection_app.command("get-config")
@pltr_command(sdk="connectivity.Connection.get_configuration")
def get_connection_configuration(
    connection_rid: ConnectionRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a connection's configuration.

    The fields depend on the connection's type (s3, rest, snowflake,
    databricks, smb or jdbc); the table shows every field the API returned.
    Secrets appear only as secret names.
    """
    with spinner(f"Fetching configuration of {connection_rid}..."):
        configuration = ConnectivityService(
            profile=profile
        ).get_connection_configuration(connection_rid)
    cache_rid(connection_rid)
    # Polymorphic model: the table shows every field the API returned.
    emit(configuration, format=format, output=output, title="Configuration")


@connection_app.command("update-secrets")
@pltr_command(sdk="connectivity.Connection.update_secrets", destructive=True)
def update_connection_secrets(
    connection_rid: ConnectionRid,
    secrets_file: Annotated[
        Path,
        typer.Option(
            "--secrets-file",
            "-s",
            exists=True,
            dir_okay=False,
            readable=True,
            help=(
                "JSON file mapping secret names to their new values. A file, so "
                "the values stay out of shell history and process listings."
            ),
            show_default=False,
        ),
    ],
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Overwrite secret values on a connection.

    The secret names must already be configured on the connection; secrets
    not in the file keep their values. Asks for confirmation (--yes skips it).
    """
    secrets = load_json_input(f"@{secrets_file}", param_hint="'--secrets-file'")
    if (
        not isinstance(secrets, dict)
        or not secrets
        or not all(isinstance(value, str) for value in secrets.values())
    ):
        raise typer.BadParameter(
            "the file must hold a non-empty JSON object mapping secret names to "
            "string values",
            param_hint="'--secrets-file'",
        )
    names = ", ".join(sorted(secrets))
    confirm_destructive(
        f"Overwrite {len(secrets)} secret(s) ({names}) on connection {connection_rid}?",
        yes=yes,
    )
    with spinner("Updating secrets..."):
        ConnectivityService(profile=profile).update_secrets(connection_rid, secrets)
    cache_rid(connection_rid)
    success(f"Updated {len(secrets)} secret(s) on connection {connection_rid}")
    emit(None, format=format)


@connection_app.command("update-export-settings")
@pltr_command(sdk="connectivity.Connection.update_export_settings", destructive=True)
def update_export_settings(
    connection_rid: ConnectionRid,
    settings: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Export settings as JSON (inline or @file.json): "
                '{"exportsEnabled": true, '
                '"exportEnabledWithoutMarkingsValidation": false}.'
            ),
            show_default=False,
        ),
    ] = None,
    settings_file: Annotated[
        Optional[str],
        typer.Option(
            "--settings-file",
            help="JSON file with the export settings.",
            show_default=False,
        ),
    ] = None,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Replace a connection's export settings.

    Both fields are required. Only users with the Information Security
    Officer role can change them. Asks for confirmation (--yes skips it).
    """
    export_settings = _json_object(
        settings, settings_file, argument="SETTINGS", file_option="--settings-file"
    )
    confirm_destructive(
        f"Replace the export settings of connection {connection_rid} with "
        f"{json.dumps(export_settings)}?",
        yes=yes,
    )
    with spinner("Updating export settings..."):
        ConnectivityService(profile=profile).update_export_settings(
            connection_rid, export_settings
        )
    cache_rid(connection_rid)
    success(f"Updated the export settings of connection {connection_rid}")
    emit(None, format=format)


@connection_app.command("upload-jdbc-drivers")
@pltr_command(sdk="connectivity.Connection.upload_custom_jdbc_drivers")
def upload_jdbc_drivers(
    connection_rid: ConnectionRid,
    driver_files: Annotated[
        List[Path],
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            help="JDBC driver JAR file(s) to upload.",
            show_default=False,
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Upload custom JDBC driver JARs to a JDBC connection.

    Uploads the files one by one and prints the connection after the last
    upload.
    """
    for path in driver_files:
        if path.suffix.lower() != ".jar":
            raise typer.BadParameter(
                f"{path} is not a .jar file", param_hint="'DRIVER_FILES...'"
            )
    service = ConnectivityService(profile=profile)
    connection = None
    for path in driver_files:
        with spinner(f"Uploading {path.name}..."):
            connection = service.upload_custom_jdbc_drivers(connection_rid, path)
        success(f"Uploaded {path.name} to connection {connection_rid}")
    cache_rid(connection_rid)
    emit(
        connection,
        format=format,
        output=output,
        columns=JDBC_CONNECTION_COLUMNS,
        title="Connection",
    )


# ------------------------------------------------------------ file imports


@import_app.command("file")
@pltr_command(sdk="connectivity.Connection.FileImport.create")
def create_file_import(
    connection_rid: ConnectionRid,
    dataset_rid: DatasetRid,
    name: NameOption,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            click_type=click.Choice(
                ["SNAPSHOT", "APPEND", "UPDATE"], case_sensitive=False
            ),
            help=(
                "SNAPSHOT replaces the dataset's files on each run, APPEND adds "
                "new files, UPDATE replaces files by name."
            ),
            show_default=False,
        ),
    ],
    subfolder: Annotated[
        Optional[str],
        typer.Option(
            "--subfolder",
            help="Folder in the source system to import (default: its root).",
            show_default=False,
        ),
    ] = None,
    branch: BranchOption = None,
    filters: Annotated[
        str,
        typer.Option(
            "--filters",
            help=(
                "File filters as a JSON array (inline or @file.json), e.g. "
                '\'[{"type": "pathMatchesFilter", "regex": ".*\\\\.csv"}]\'.'
            ),
        ),
    ] = "[]",
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create a file import (batch sync) from a connection into a dataset.

    Run it with 'pltr connectivity import execute-file CONNECTION_RID
    FILE_IMPORT_RID'.
    """
    filter_list = load_json_input(filters, param_hint="'--filters'")
    if not isinstance(filter_list, list):
        raise typer.BadParameter("expected a JSON array", param_hint="'--filters'")
    with spinner("Creating file import..."):
        file_import = ConnectivityService(profile=profile).create_file_import(
            connection_rid,
            dataset_rid=dataset_rid,
            display_name=name,
            import_mode=mode.upper(),
            file_import_filters=filter_list,
            branch_name=branch,
            subfolder=subfolder,
        )
    cache_rid(file_import.rid)
    success(f"Created file import '{file_import.display_name}' ({file_import.rid})")
    emit(
        file_import,
        format=format,
        output=output,
        columns=FILE_IMPORT_COLUMNS,
        title="File import",
    )


@import_app.command("get-file")
@pltr_command(sdk="connectivity.Connection.FileImport.get")
def get_file_import(
    connection_rid: ConnectionRid,
    file_import_rid: FileImportRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a file import."""
    with spinner(f"Fetching file import {file_import_rid}..."):
        file_import = ConnectivityService(profile=profile).get_file_import(
            connection_rid, file_import_rid
        )
    cache_rid(file_import_rid)
    emit(
        file_import,
        format=format,
        output=output,
        columns=FILE_IMPORT_COLUMNS,
        title="File import",
    )


@import_app.command("list-file")
@pltr_command(sdk="connectivity.Connection.FileImport.list", paged=True)
def list_file_imports(
    connection_rid: ConnectionRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List a connection's file imports (those you can see).

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = ConnectivityService(profile=profile)
    with spinner(f"Listing file imports of {connection_rid}..."):
        page = collect_pages(
            lambda token: service.list_file_imports(
                connection_rid, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(connection_rid)
    emit(page, format=format, output=output, columns=FILE_IMPORT_LIST_COLUMNS)


@import_app.command("execute-file")
@pltr_command(sdk="connectivity.Connection.FileImport.execute")
def execute_file_import(
    connection_rid: ConnectionRid,
    file_import_rid: FileImportRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Run a file import; prints the RID of the build that runs it.

    The import runs asynchronously as a Foundry build; check it with
    'pltr orchestration builds get BUILD_RID'.
    """
    with spinner(f"Starting file import {file_import_rid}..."):
        build_rid = ConnectivityService(profile=profile).execute_file_import(
            connection_rid, file_import_rid
        )
    _report_build(build_rid, "file", file_import_rid)
    emit(build_rid, format=format, output=output, columns=BUILD_COLUMNS, title="Build")


# ----------------------------------------------------------- table imports


@import_app.command("table")
@pltr_command(sdk="connectivity.Connection.TableImport.create")
def create_table_import(
    connection_rid: ConnectionRid,
    dataset_rid: DatasetRid,
    name: NameOption,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            click_type=click.Choice(["SNAPSHOT", "APPEND"], case_sensitive=False),
            help="SNAPSHOT replaces the dataset on each run, APPEND adds rows.",
            show_default=False,
        ),
    ],
    config: Annotated[
        str,
        typer.Option(
            "--config",
            "-c",
            help=(
                'Import config as JSON (inline or @file.json): its "type" '
                "(jdbcImportConfig, postgreSqlImportConfig, snowflakeImportConfig, "
                "databricksImportConfig, microsoftSqlServerImportConfig, "
                "oracleImportConfig or microsoftAccessImportConfig), the SQL "
                '"query" and an optional "initialIncrementalState".'
            ),
            show_default=False,
        ),
    ],
    allow_schema_changes: Annotated[
        bool,
        typer.Option(
            "--allow-schema-changes",
            help="Let runs succeed when the imported schema doesn't match the dataset's.",
        ),
    ] = False,
    branch: BranchOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create a table import (batch sync) from a connection into a dataset.

    Run it with 'pltr connectivity import execute-table CONNECTION_RID
    TABLE_IMPORT_RID'.

    Example:

    \b
    pltr connectivity import table <CONNECTION_RID> <DATASET_RID> \\
        --name "Orders" --mode SNAPSHOT \\
        --config '{"type": "jdbcImportConfig", "query": "SELECT * FROM orders"}'
    """
    config_json = load_json_input(config, param_hint="'--config'")
    if not isinstance(config_json, dict):
        raise typer.BadParameter("expected a JSON object", param_hint="'--config'")
    with spinner("Creating table import..."):
        table_import = ConnectivityService(profile=profile).create_table_import(
            connection_rid,
            dataset_rid=dataset_rid,
            display_name=name,
            import_mode=mode.upper(),
            config=config_json,
            allow_schema_changes=True if allow_schema_changes else None,
            branch_name=branch,
        )
    cache_rid(table_import.rid)
    success(f"Created table import '{table_import.display_name}' ({table_import.rid})")
    emit(
        table_import,
        format=format,
        output=output,
        columns=TABLE_IMPORT_COLUMNS,
        title="Table import",
    )


@import_app.command("get-table")
@pltr_command(sdk="connectivity.Connection.TableImport.get")
def get_table_import(
    connection_rid: ConnectionRid,
    table_import_rid: TableImportRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a table import."""
    with spinner(f"Fetching table import {table_import_rid}..."):
        table_import = ConnectivityService(profile=profile).get_table_import(
            connection_rid, table_import_rid
        )
    cache_rid(table_import_rid)
    emit(
        table_import,
        format=format,
        output=output,
        columns=TABLE_IMPORT_COLUMNS,
        title="Table import",
    )


@import_app.command("list-table")
@pltr_command(sdk="connectivity.Connection.TableImport.list", paged=True)
def list_table_imports(
    connection_rid: ConnectionRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List a connection's table imports (those you can see).

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = ConnectivityService(profile=profile)
    with spinner(f"Listing table imports of {connection_rid}..."):
        page = collect_pages(
            lambda token: service.list_table_imports(
                connection_rid, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(connection_rid)
    emit(page, format=format, output=output, columns=TABLE_IMPORT_LIST_COLUMNS)


@import_app.command("execute-table")
@pltr_command(sdk="connectivity.Connection.TableImport.execute")
def execute_table_import(
    connection_rid: ConnectionRid,
    table_import_rid: TableImportRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Run a table import; prints the RID of the build that runs it.

    The import runs asynchronously as a Foundry build; check it with
    'pltr orchestration builds get BUILD_RID'.
    """
    with spinner(f"Starting table import {table_import_rid}..."):
        build_rid = ConnectivityService(profile=profile).execute_table_import(
            connection_rid, table_import_rid
        )
    _report_build(build_rid, "table", table_import_rid)
    emit(build_rid, format=format, output=output, columns=BUILD_COLUMNS, title="Build")


@app.callback()
def main():
    """
    Data Connection operations using foundry-platform-sdk.

    Connections (Data Connection sources) and their file and table imports
    are addressed by RID. Imports belong to a connection, so import commands
    take the connection RID first. The API can't list connections: find them
    in a folder with 'pltr folder list FOLDER_RID'.

    Examples:

    \b
        # Inspect a connection and its configuration
        pltr connectivity connection get <CONNECTION_RID>
        pltr connectivity connection get-config <CONNECTION_RID>
    \b
        # Create a file import and run it
        pltr connectivity import file <CONNECTION_RID> <DATASET_RID> \\
            --name "Daily drop" --mode APPEND
        pltr connectivity import execute-file <CONNECTION_RID> <FILE_IMPORT_RID>
    \b
        # List a connection's table imports as JSON
        pltr connectivity import list-table <CONNECTION_RID> --format json
    """
