"""Tests for ConnectivityService against a real FoundryClient (only HTTP is faked).

Every connectivity endpoint is GA: passing preview= would make the SDK emit a
UserWarning, which the module-level filter turns into a failure.

These replace Mock-based tests that asserted calls to ``client.file_imports``
and ``client.table_imports``, which don't exist in the SDK (the commands could
never succeed), and to a ``Connection.list`` the SDK doesn't have.
"""

import json

import pytest
from foundry_sdk.v2.connectivity.errors import ConnectionNotFound, FileImportNotFound
from foundry_sdk.v2.connectivity.models import (
    Connection,
    FileImport,
    RestConnectionConfiguration,
    TableImport,
)

from pltr.services.connectivity import ConnectivityService
from tests import foundry_json as fj
from tests import foundry_json_connectivity as cj

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

CONNECTIONS = "/api/v2/connectivity/connections"


def only_request(stub):
    [request] = stub.requests
    assert "preview" not in request.url.params
    return request


# ------------------------------------------------------------- connections


def test_get_connection(stub_foundry_http):
    stub_foundry_http.respond(json=cj.connection())

    connection = ConnectivityService().get_connection(cj.CONNECTION_RID)

    assert isinstance(connection, Connection)
    assert connection.display_name == "Orders API"
    assert connection.configuration.type == "rest"
    assert connection.worker.type == "foundryWorker"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "GET",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}",
    )


def test_get_connection_not_found_raises_the_sdk_error(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "ConnectionNotFound", parameters={"connectionRid": cj.CONNECTION_RID}
        ),
    )

    with pytest.raises(ConnectionNotFound):
        ConnectivityService().get_connection(cj.CONNECTION_RID)


def test_create_connection_sends_the_api_request(stub_foundry_http):
    stub_foundry_http.respond(json=cj.connection())

    connection = ConnectivityService().create_connection(
        display_name="Orders API",
        parent_folder_rid=cj.FOLDER_RID,
        configuration={"type": "rest", "domains": [{"host": "api.example.com"}]},
        worker=cj.foundry_worker(),
    )

    assert connection.rid == cj.CONNECTION_RID
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("POST", CONNECTIONS)
    assert json.loads(request.content) == {
        "parentFolderRid": cj.FOLDER_RID,
        "displayName": "Orders API",
        "configuration": {"type": "rest", "domains": [{"host": "api.example.com"}]},
        "worker": cj.foundry_worker(),
    }


def test_create_connection_without_configuration_type_sends_nothing(
    stub_foundry_http,
):
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        ConnectivityService().create_connection(
            display_name="Orders API",
            parent_folder_rid=cj.FOLDER_RID,
            configuration={"domains": [{"host": "api.example.com"}]},
            worker=cj.foundry_worker(),
        )
    assert stub_foundry_http.requests == []


def test_get_connection_configuration(stub_foundry_http):
    stub_foundry_http.respond(json=cj.rest_configuration())

    configuration = ConnectivityService().get_connection_configuration(
        cj.CONNECTION_RID
    )

    assert isinstance(configuration, RestConnectionConfiguration)
    assert configuration.domains[0].host == "api.example.com"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "GET",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/getConfiguration",
    )


def test_update_export_settings(stub_foundry_http):
    stub_foundry_http.respond(204)
    settings = {"exportsEnabled": True, "exportEnabledWithoutMarkingsValidation": False}

    assert (
        ConnectivityService().update_export_settings(cj.CONNECTION_RID, settings)
        is None
    )

    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/updateExportSettings",
    )
    assert json.loads(request.content) == {"exportSettings": settings}


def test_update_secrets(stub_foundry_http):
    stub_foundry_http.respond(204)

    ConnectivityService().update_secrets(cj.CONNECTION_RID, {"password": "s3cret"})

    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/updateSecrets",
    )
    assert json.loads(request.content) == {"secrets": {"password": "s3cret"}}


def test_upload_custom_jdbc_drivers_sends_the_jar_bytes(stub_foundry_http, tmp_path):
    jar = tmp_path / "postgresql-42.7.3.jar"
    jar.write_bytes(b"PK\x03\x04 driver bytes")
    stub_foundry_http.respond(
        json=cj.connection(
            configuration=cj.jdbc_configuration(["postgresql-42.7.3.jar"])
        )
    )

    connection = ConnectivityService().upload_custom_jdbc_drivers(
        cj.CONNECTION_RID, jar
    )

    assert connection.configuration.uploaded_jdbc_drivers == ["postgresql-42.7.3.jar"]
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/uploadCustomJdbcDrivers",
    )
    assert dict(request.url.params) == {"fileName": "postgresql-42.7.3.jar"}
    assert request.headers["Content-Type"] == "application/octet-stream"
    assert request.content == b"PK\x03\x04 driver bytes"


# ------------------------------------------------------------ file imports


def test_create_file_import(stub_foundry_http):
    stub_foundry_http.respond(json=cj.file_import())

    file_import = ConnectivityService().create_file_import(
        cj.CONNECTION_RID,
        dataset_rid=cj.DATASET_RID,
        display_name="Daily drop",
        import_mode="APPEND",
        file_import_filters=[{"type": "pathMatchesFilter", "regex": ".*\\.csv"}],
        subfolder="exports/daily",
    )

    assert isinstance(file_import, FileImport)
    assert file_import.import_mode == "APPEND"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/fileImports",
    )
    assert json.loads(request.content) == {
        "datasetRid": cj.DATASET_RID,
        "importMode": "APPEND",
        "displayName": "Daily drop",
        "subfolder": "exports/daily",
        "fileImportFilters": [{"type": "pathMatchesFilter", "regex": ".*\\.csv"}],
    }


def test_get_file_import_addresses_the_connection_and_the_import(stub_foundry_http):
    stub_foundry_http.respond(json=cj.file_import())

    file_import = ConnectivityService().get_file_import(
        cj.CONNECTION_RID, cj.FILE_IMPORT_RID
    )

    assert file_import.dataset_rid == cj.DATASET_RID
    request = only_request(stub_foundry_http)
    assert request.url.path == (
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/fileImports/{cj.FILE_IMPORT_RID}"
    )


def test_get_file_import_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "FileImportNotFound",
            parameters={
                "fileImportRid": cj.FILE_IMPORT_RID,
                "connectionRid": cj.CONNECTION_RID,
            },
        ),
    )

    with pytest.raises(FileImportNotFound):
        ConnectivityService().get_file_import(cj.CONNECTION_RID, cj.FILE_IMPORT_RID)


def test_list_file_imports_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(json=cj.page(cj.file_import(), token="tok-2"))

    page = ConnectivityService().list_file_imports(
        cj.CONNECTION_RID, page_size=10, page_token="tok-1"
    )

    assert [item.display_name for item in page.data] == ["Daily drop"]
    assert page.next_page_token == "tok-2"
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{CONNECTIONS}/{cj.CONNECTION_RID}/fileImports"
    assert dict(request.url.params) == {"pageSize": "10", "pageToken": "tok-1"}


def test_execute_file_import_returns_the_build_rid(stub_foundry_http):
    stub_foundry_http.respond(json=cj.BUILD_RID)

    build_rid = ConnectivityService().execute_file_import(
        cj.CONNECTION_RID, cj.FILE_IMPORT_RID
    )

    assert build_rid == cj.BUILD_RID
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/fileImports/{cj.FILE_IMPORT_RID}/execute",
    )


# ----------------------------------------------------------- table imports


def test_create_table_import(stub_foundry_http):
    stub_foundry_http.respond(json=cj.table_import())

    table_import = ConnectivityService().create_table_import(
        cj.CONNECTION_RID,
        dataset_rid=cj.DATASET_RID,
        display_name="Orders",
        import_mode="SNAPSHOT",
        config={"type": "jdbcImportConfig", "query": "SELECT * FROM orders"},
        allow_schema_changes=True,
        branch_name="develop",
    )

    assert isinstance(table_import, TableImport)
    assert table_import.config.query == "SELECT * FROM orders"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/tableImports",
    )
    assert json.loads(request.content) == {
        "datasetRid": cj.DATASET_RID,
        "importMode": "SNAPSHOT",
        "displayName": "Orders",
        "allowSchemaChanges": True,
        "branchName": "develop",
        "config": {"type": "jdbcImportConfig", "query": "SELECT * FROM orders"},
    }


def test_get_table_import(stub_foundry_http):
    stub_foundry_http.respond(json=cj.table_import())

    table_import = ConnectivityService().get_table_import(
        cj.CONNECTION_RID, cj.TABLE_IMPORT_RID
    )

    assert table_import.config.type == "jdbcImportConfig"
    request = only_request(stub_foundry_http)
    assert request.url.path == (
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/tableImports/{cj.TABLE_IMPORT_RID}"
    )


def test_list_table_imports_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(json=cj.page(cj.table_import()))

    page = ConnectivityService().list_table_imports(cj.CONNECTION_RID)

    assert [item.rid for item in page.data] == [cj.TABLE_IMPORT_RID]
    assert page.next_page_token is None
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{CONNECTIONS}/{cj.CONNECTION_RID}/tableImports"
    assert dict(request.url.params) == {}


def test_execute_table_import_returns_the_build_rid(stub_foundry_http):
    stub_foundry_http.respond(json=cj.BUILD_RID)

    build_rid = ConnectivityService().execute_table_import(
        cj.CONNECTION_RID, cj.TABLE_IMPORT_RID
    )

    assert build_rid == cj.BUILD_RID
    request = only_request(stub_foundry_http)
    assert request.url.path == (
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/tableImports/{cj.TABLE_IMPORT_RID}/execute"
    )
