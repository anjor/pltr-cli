"""Tests for `pltr connectivity` against a real FoundryClient (only HTTP is faked).

These replace Mock-based tests of a service that called ``client.file_imports``
and ``client.table_imports`` (which don't exist in the SDK) and a
``Connection.list`` the SDK doesn't have; the commands they covered could never
succeed.
"""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_connectivity as cj

# Every connectivity endpoint is GA: a stray preview= would raise a UserWarning.
pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()

CONNECTIONS = "/api/v2/connectivity/connections"
REST_CONFIG = '{"type": "rest", "domains": [{"host": "api.example.com"}]}'
WORKER = json.dumps(cj.foundry_worker())
EXPORT_SETTINGS = {
    "exportsEnabled": True,
    "exportEnabledWithoutMarkingsValidation": False,
}


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


def json_error(result) -> dict:
    return json_lines(result.stderr)[-1]


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


def test_no_connectivity_command_is_labeled_beta():
    for group in ("connection", "import"):
        result = invoke("connectivity", group, "--help")
        assert result.exit_code == 0
        assert "[beta]" not in result.stdout


def test_connection_list_was_removed():
    result = invoke("connectivity", "connection", "list")

    assert result.exit_code == 2
    assert "No such command 'list'" in result.stderr


# ------------------------------------------------------------- connection get


def test_get_connection_table(stub_foundry_http):
    stub_foundry_http.respond(json=cj.connection())

    result = invoke("connectivity", "connection", "get", cj.CONNECTION_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        cj.CONNECTION_RID,
        "Orders API",
        cj.FOLDER_RID,
        "rest",
        "foundryWorker",
        cj.EGRESS_POLICY_RID,
    ):
        assert expected in result.stdout
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{CONNECTIONS}/{cj.CONNECTION_RID}"


def test_get_connection_json_is_the_sdk_serialization(stub_foundry_http):
    stub_foundry_http.respond(json=cj.connection())

    result = invoke(
        "connectivity", "connection", "get", cj.CONNECTION_RID, "--format", "json"
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == cj.connection()
    assert result.stderr == ""


def test_get_connection_csv(stub_foundry_http):
    stub_foundry_http.respond(json=cj.connection())

    result = invoke("connectivity", "connection", "get", cj.CONNECTION_RID, "-f", "csv")

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row["RID"] == cj.CONNECTION_RID
    assert row["Configuration Type"] == "rest"
    assert row["Worker"] == "foundryWorker"
    assert row["Network Egress Policies"] == cj.EGRESS_POLICY_RID
    assert row["Exports Enabled"] == "false"
    assert row["Exports Without Markings Validation"] == "false"


def test_get_connection_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "ConnectionNotFound", parameters={"connectionRid": cj.CONNECTION_RID}
        ),
    )

    result = invoke(
        "connectivity", "connection", "get", cj.CONNECTION_RID, "--format", "json"
    )

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_error(result)
    assert (error["type"], error["errorName"]) == ("not_found", "ConnectionNotFound")
    assert error["parameters"] == {"connectionRid": cj.CONNECTION_RID}


def test_get_connection_invalid_rid_is_a_usage_error(stub_foundry_http):
    result = invoke("connectivity", "connection", "get", "orders", "-f", "json")

    assert result.exit_code == 2
    assert "not a valid RID" in json_error(result)["message"]
    assert stub_foundry_http.requests == []


# ---------------------------------------------------------- connection create


def test_create_connection_inline_json(stub_foundry_http):
    stub_foundry_http.respond(json=cj.connection())

    result = invoke(
        "connectivity",
        "connection",
        "create",
        "Orders API",
        cj.FOLDER_RID,
        REST_CONFIG,
        WORKER,
    )

    assert result.exit_code == 0, result.output
    assert cj.CONNECTION_RID in result.stdout
    assert f"Created connection 'Orders API' ({cj.CONNECTION_RID})" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", CONNECTIONS)
    assert json.loads(request.content) == {
        "parentFolderRid": cj.FOLDER_RID,
        "displayName": "Orders API",
        "configuration": json.loads(REST_CONFIG),
        "worker": cj.foundry_worker(),
    }


def test_create_connection_from_files(stub_foundry_http, tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(REST_CONFIG)
    worker_file = tmp_path / "worker.json"
    worker_file.write_text(WORKER)
    stub_foundry_http.respond(json=cj.connection())

    result = invoke(
        "connectivity",
        "connection",
        "create",
        "Orders API",
        cj.FOLDER_RID,
        "--config-file",
        str(config_file),
        "--worker-file",
        str(worker_file),
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == cj.connection()
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["configuration"]["type"] == "rest"


def test_create_connection_accepts_at_file_arguments(stub_foundry_http, tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(REST_CONFIG)
    stub_foundry_http.respond(json=cj.connection())

    result = invoke(
        "connectivity",
        "connection",
        "create",
        "Orders API",
        cj.FOLDER_RID,
        f"@{config_file}",
        WORKER,
    )

    assert result.exit_code == 0, result.output


def test_create_connection_requires_configuration(stub_foundry_http):
    result = invoke(
        "connectivity",
        "connection",
        "create",
        "Orders API",
        cj.FOLDER_RID,
        "-f",
        "json",
    )

    assert result.exit_code == 2
    error = json_error(result)
    assert error["type"] == "usage_error"
    assert "CONFIGURATION" in error["message"]
    assert stub_foundry_http.requests == []


def test_create_connection_rejects_both_inline_and_file(stub_foundry_http, tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(REST_CONFIG)

    result = invoke(
        "connectivity",
        "connection",
        "create",
        "Orders API",
        cj.FOLDER_RID,
        REST_CONFIG,
        WORKER,
        "--config-file",
        str(config_file),
    )

    assert result.exit_code == 2
    assert "not both" in result.stderr
    assert stub_foundry_http.requests == []


def test_create_connection_invalid_json(stub_foundry_http):
    result = invoke(
        "connectivity",
        "connection",
        "create",
        "Orders API",
        cj.FOLDER_RID,
        "{not json",
        WORKER,
        "-f",
        "json",
    )

    assert result.exit_code == 2
    assert "invalid JSON" in json_error(result)["message"]
    assert stub_foundry_http.requests == []


def test_create_connection_configuration_without_type(stub_foundry_http):
    result = invoke(
        "connectivity",
        "connection",
        "create",
        "Orders API",
        cj.FOLDER_RID,
        '{"domains": [{"host": "api.example.com"}]}',
        WORKER,
        "-f",
        "json",
    )

    assert result.exit_code == 2
    error = json_error(result)
    assert error["type"] == "usage_error"
    assert "configuration" in error["message"]
    assert stub_foundry_http.requests == []


# ------------------------------------------------------ connection get-config


def test_get_config_defaults_to_a_table_of_every_field(stub_foundry_http):
    stub_foundry_http.respond(json=cj.jdbc_configuration(["postgresql.jar"]))

    result = invoke("connectivity", "connection", "get-config", cj.CONNECTION_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        "jdbc",
        "jdbc:postgresql://db.example.com:5432/orders",
        "org.postgresql.Driver",
        "postgresql.jar",
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{CONNECTIONS}/{cj.CONNECTION_RID}/getConfiguration"


def test_get_config_json_is_the_configuration(stub_foundry_http):
    stub_foundry_http.respond(json=cj.rest_configuration())

    result = invoke(
        "connectivity", "connection", "get-config", cj.CONNECTION_RID, "-f", "json"
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == cj.rest_configuration()


# --------------------------------------------------- connection update-secrets


@pytest.fixture
def secrets_file(tmp_path):
    path = tmp_path / "secrets.json"
    path.write_text(json.dumps({"password": "s3cret", "apiKey": "k3y"}))
    return path


def test_update_secrets_refuses_without_yes_when_not_interactive(
    stub_foundry_http, secrets_file
):
    result = invoke(
        "connectivity",
        "connection",
        "update-secrets",
        cj.CONNECTION_RID,
        "--secrets-file",
        str(secrets_file),
        "-f",
        "json",
    )

    assert result.exit_code == 2
    assert json_error(result)["type"] == "confirmation_required"
    assert stub_foundry_http.requests == []


def test_update_secrets_with_yes(stub_foundry_http, secrets_file):
    stub_foundry_http.respond(204)

    result = invoke(
        "connectivity",
        "connection",
        "update-secrets",
        cj.CONNECTION_RID,
        "-s",
        str(secrets_file),
        "--yes",
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Updated 2 secret(s) on connection {cj.CONNECTION_RID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/updateSecrets",
    )
    assert json.loads(request.content) == {
        "secrets": {"password": "s3cret", "apiKey": "k3y"}
    }


def test_update_secrets_json_prints_null(stub_foundry_http, secrets_file):
    stub_foundry_http.respond(204)

    result = invoke(
        "connectivity",
        "connection",
        "update-secrets",
        cj.CONNECTION_RID,
        "-s",
        str(secrets_file),
        "-y",
        "-f",
        "json",
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) is None
    assert result.stderr == ""


def test_update_secrets_prompt_names_the_secrets_but_not_their_values(
    stub_foundry_http, secrets_file, interactive
):
    stub_foundry_http.respond(204)

    result = invoke(
        "connectivity",
        "connection",
        "update-secrets",
        cj.CONNECTION_RID,
        "-s",
        str(secrets_file),
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert "Overwrite 2 secret(s) (apiKey, password)" in result.stderr
    assert "s3cret" not in result.stderr + result.stdout
    assert len(stub_foundry_http.requests) == 1


def test_update_secrets_answering_no_aborts(
    stub_foundry_http, secrets_file, interactive
):
    result = invoke(
        "connectivity",
        "connection",
        "update-secrets",
        cj.CONNECTION_RID,
        "-s",
        str(secrets_file),
        input="n\n",
    )

    assert result.exit_code == 1
    assert "Aborted" in result.stderr
    assert stub_foundry_http.requests == []


@pytest.mark.parametrize("content", ['{"password": 1}', "{}", '["password"]'])
def test_update_secrets_rejects_bad_files(stub_foundry_http, tmp_path, content):
    path = tmp_path / "secrets.json"
    path.write_text(content)

    result = invoke(
        "connectivity",
        "connection",
        "update-secrets",
        cj.CONNECTION_RID,
        "-s",
        str(path),
        "--yes",
    )

    assert result.exit_code == 2
    assert "secret names to" in result.stderr
    assert stub_foundry_http.requests == []


def test_update_secrets_missing_file(stub_foundry_http, tmp_path):
    result = invoke(
        "connectivity",
        "connection",
        "update-secrets",
        cj.CONNECTION_RID,
        "-s",
        str(tmp_path / "missing.json"),
        "--yes",
    )

    assert result.exit_code == 2
    assert "does not exist" in result.stderr
    assert stub_foundry_http.requests == []


def test_update_secrets_unknown_secret_name(stub_foundry_http, secrets_file):
    stub_foundry_http.respond(
        400,
        json=fj.error(
            "SecretNamesDoNotExist",
            error_code="INVALID_ARGUMENT",
            parameters={
                "connectionRid": cj.CONNECTION_RID,
                "secretNames": ["apiKey"],
            },
        ),
    )

    result = invoke(
        "connectivity",
        "connection",
        "update-secrets",
        cj.CONNECTION_RID,
        "-s",
        str(secrets_file),
        "--yes",
        "-f",
        "json",
    )

    assert result.exit_code == 6
    error = json_error(result)
    assert (error["type"], error["errorName"]) == (
        "validation_error",
        "SecretNamesDoNotExist",
    )


# ------------------------------------------- connection update-export-settings


def test_update_export_settings_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "connectivity",
        "connection",
        "update-export-settings",
        cj.CONNECTION_RID,
        json.dumps(EXPORT_SETTINGS),
        "--yes",
    )

    assert result.exit_code == 0, result.output
    assert "Updated the export settings" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/updateExportSettings",
    )
    assert json.loads(request.content) == {"exportSettings": EXPORT_SETTINGS}


def test_update_export_settings_from_file(stub_foundry_http, tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(EXPORT_SETTINGS))
    stub_foundry_http.respond(204)

    result = invoke(
        "connectivity",
        "connection",
        "update-export-settings",
        cj.CONNECTION_RID,
        "--settings-file",
        str(path),
        "-y",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None


def test_update_export_settings_refuses_without_yes(stub_foundry_http):
    result = invoke(
        "connectivity",
        "connection",
        "update-export-settings",
        cj.CONNECTION_RID,
        json.dumps(EXPORT_SETTINGS),
    )

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub_foundry_http.requests == []


def test_update_export_settings_prompt_shows_the_new_settings(
    stub_foundry_http, interactive
):
    result = invoke(
        "connectivity",
        "connection",
        "update-export-settings",
        cj.CONNECTION_RID,
        json.dumps(EXPORT_SETTINGS),
        input="n\n",
    )

    assert result.exit_code == 1
    assert '"exportsEnabled": true' in result.stderr
    assert stub_foundry_http.requests == []


def test_update_export_settings_requires_settings(stub_foundry_http):
    result = invoke(
        "connectivity", "connection", "update-export-settings", cj.CONNECTION_RID, "-y"
    )

    assert result.exit_code == 2
    assert "SETTINGS" in result.stderr
    assert stub_foundry_http.requests == []


def test_update_export_settings_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "UpdateExportSettingsForConnectionPermissionDenied",
            error_code="PERMISSION_DENIED",
            parameters={"connectionRid": cj.CONNECTION_RID},
        ),
    )

    result = invoke(
        "connectivity",
        "connection",
        "update-export-settings",
        cj.CONNECTION_RID,
        json.dumps(EXPORT_SETTINGS),
        "-y",
        "-f",
        "json",
    )

    assert result.exit_code == 4
    assert json_error(result)["type"] == "permission_denied"


# ---------------------------------------------- connection upload-jdbc-drivers


def test_upload_jdbc_drivers_uploads_each_file_and_prints_the_connection(
    stub_foundry_http, tmp_path
):
    first = tmp_path / "postgresql.jar"
    first.write_bytes(b"first")
    second = tmp_path / "extra.JAR"
    second.write_bytes(b"second")
    stub_foundry_http.respond(
        json=cj.connection(configuration=cj.jdbc_configuration(["postgresql.jar"]))
    )
    stub_foundry_http.respond(
        json=cj.connection(
            configuration=cj.jdbc_configuration(["postgresql.jar", "extra.JAR"])
        )
    )

    result = invoke(
        "connectivity",
        "connection",
        "upload-jdbc-drivers",
        cj.CONNECTION_RID,
        str(first),
        str(second),
        "-f",
        "csv",
    )

    assert result.exit_code == 0, result.output
    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row["JDBC Drivers"] == "postgresql.jar, extra.JAR"
    assert row["Configuration Type"] == "jdbc"
    assert "Uploaded postgresql.jar" in result.stderr
    assert "Uploaded extra.JAR" in result.stderr
    requests = stub_foundry_http.requests
    assert [r.url.params["fileName"] for r in requests] == [
        "postgresql.jar",
        "extra.JAR",
    ]
    assert [r.content for r in requests] == [b"first", b"second"]


def test_upload_jdbc_drivers_json_is_the_final_connection(stub_foundry_http, tmp_path):
    jar = tmp_path / "postgresql.jar"
    jar.write_bytes(b"jar")
    body = cj.connection(configuration=cj.jdbc_configuration(["postgresql.jar"]))
    stub_foundry_http.respond(json=body)

    result = invoke(
        "connectivity",
        "connection",
        "upload-jdbc-drivers",
        cj.CONNECTION_RID,
        str(jar),
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == body
    assert result.stderr == ""


def test_upload_jdbc_drivers_rejects_non_jar_files_before_uploading(
    stub_foundry_http, tmp_path
):
    jar = tmp_path / "driver.jar"
    jar.write_bytes(b"jar")
    text = tmp_path / "driver.txt"
    text.write_text("not a jar")

    result = invoke(
        "connectivity",
        "connection",
        "upload-jdbc-drivers",
        cj.CONNECTION_RID,
        str(jar),
        str(text),
    )

    assert result.exit_code == 2
    assert "is not a .jar file" in result.stderr
    assert stub_foundry_http.requests == []


def test_upload_jdbc_drivers_missing_file(stub_foundry_http, tmp_path):
    result = invoke(
        "connectivity",
        "connection",
        "upload-jdbc-drivers",
        cj.CONNECTION_RID,
        str(tmp_path / "missing.jar"),
    )

    assert result.exit_code == 2
    assert "does not exist" in result.stderr
    assert stub_foundry_http.requests == []


# -------------------------------------------------------------- import file


def test_import_file_creates_a_file_import(stub_foundry_http):
    stub_foundry_http.respond(json=cj.file_import())

    result = invoke(
        "connectivity",
        "import",
        "file",
        cj.CONNECTION_RID,
        cj.DATASET_RID,
        "--name",
        "Daily drop",
        "--mode",
        "append",
        "--subfolder",
        "exports/daily",
        "--filters",
        '[{"type": "pathMatchesFilter", "regex": ".*\\\\.csv"}]',
    )

    assert result.exit_code == 0, result.output
    assert cj.FILE_IMPORT_RID in result.stdout
    assert f"Created file import 'Daily drop' ({cj.FILE_IMPORT_RID})" in result.stderr
    [request] = stub_foundry_http.requests
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


def test_import_file_defaults_to_no_filters(stub_foundry_http):
    stub_foundry_http.respond(json=cj.file_import(fileImportFilters=[]))

    result = invoke(
        "connectivity",
        "import",
        "file",
        cj.CONNECTION_RID,
        cj.DATASET_RID,
        "-n",
        "Daily drop",
        "--mode",
        "SNAPSHOT",
        "--branch",
        "develop",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["fileImportFilters"] == []
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["fileImportFilters"] == []
    assert body["branchName"] == "develop"
    assert "subfolder" not in body


def test_import_file_requires_name_and_mode(stub_foundry_http):
    result = invoke("connectivity", "import", "file", cj.CONNECTION_RID, cj.DATASET_RID)

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_import_file_rejects_an_unknown_mode(stub_foundry_http):
    result = invoke(
        "connectivity",
        "import",
        "file",
        cj.CONNECTION_RID,
        cj.DATASET_RID,
        "-n",
        "x",
        "--mode",
        "MIRROR",
    )

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_import_file_filters_must_be_a_json_array(stub_foundry_http):
    result = invoke(
        "connectivity",
        "import",
        "file",
        cj.CONNECTION_RID,
        cj.DATASET_RID,
        "-n",
        "x",
        "--mode",
        "APPEND",
        "--filters",
        '{"type": "pathMatchesFilter"}',
        "-f",
        "json",
    )

    assert result.exit_code == 2
    assert "JSON array" in json_error(result)["message"]
    assert stub_foundry_http.requests == []


def test_import_file_old_arguments_are_gone(stub_foundry_http):
    """The old form (source path positional, --execute) never worked."""
    result = invoke(
        "connectivity",
        "import",
        "file",
        cj.CONNECTION_RID,
        "/data/sales.csv",
        cj.DATASET_RID,
        "--execute",
    )

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_import_file_dataset_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("DatasetNotFound", parameters={"datasetRid": cj.DATASET_RID})
    )

    result = invoke(
        "connectivity",
        "import",
        "file",
        cj.CONNECTION_RID,
        cj.DATASET_RID,
        "-n",
        "x",
        "--mode",
        "APPEND",
        "-f",
        "json",
    )

    assert result.exit_code == 5
    assert json_error(result)["errorName"] == "DatasetNotFound"


# ------------------------------------------------- import get-file/list-file


def test_get_file_import_table(stub_foundry_http):
    stub_foundry_http.respond(json=cj.file_import())

    result = invoke(
        "connectivity", "import", "get-file", cj.CONNECTION_RID, cj.FILE_IMPORT_RID
    )

    assert result.exit_code == 0, result.output
    for expected in (
        cj.FILE_IMPORT_RID,
        "Daily drop",
        cj.DATASET_RID,
        "APPEND",
        "exports/daily",
        "pathMatchesFilter",
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == (
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/fileImports/{cj.FILE_IMPORT_RID}"
    )


def test_get_file_import_json(stub_foundry_http):
    stub_foundry_http.respond(json=cj.file_import())

    result = invoke(
        "connectivity",
        "import",
        "get-file",
        cj.CONNECTION_RID,
        cj.FILE_IMPORT_RID,
        "-f",
        "json",
    )

    assert json.loads(result.stdout) == cj.file_import()


def test_get_file_import_needs_the_connection_rid(stub_foundry_http):
    result = invoke("connectivity", "import", "get-file", cj.FILE_IMPORT_RID)

    assert result.exit_code == 2
    assert "Missing argument" in result.stderr
    assert stub_foundry_http.requests == []


def test_list_file_imports_json_is_the_paged_shape(stub_foundry_http):
    stub_foundry_http.respond(json=cj.page(cj.file_import(), token="tok-2"))

    result = invoke(
        "connectivity", "import", "list-file", cj.CONNECTION_RID, "--format", "json"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [cj.file_import()],
        "nextPageToken": "tok-2",
    }
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{CONNECTIONS}/{cj.CONNECTION_RID}/fileImports"


def test_list_file_imports_all_pages(stub_foundry_http):
    second = cj.file_import("ri.magritte..sync.second", "Second")
    stub_foundry_http.respond(json=cj.page(cj.file_import(), token="tok-2"))
    stub_foundry_http.respond(json=cj.page(second))

    result = invoke(
        "connectivity",
        "import",
        "list-file",
        cj.CONNECTION_RID,
        "--all",
        "--page-size",
        "1",
        "-f",
        "csv",
    )

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [row["Display Name"] for row in rows] == ["Daily drop", "Second"]
    first_request, second_request = stub_foundry_http.requests
    assert dict(first_request.url.params) == {"pageSize": "1"}
    assert dict(second_request.url.params) == {"pageSize": "1", "pageToken": "tok-2"}


def test_list_file_imports_table_hints_at_the_next_page(stub_foundry_http):
    stub_foundry_http.respond(json=cj.page(cj.file_import(), token="tok-2"))

    result = invoke("connectivity", "import", "list-file", cj.CONNECTION_RID)

    assert "Daily drop" in result.stdout
    assert "--page-token tok-2" in result.stderr


def test_list_file_imports_empty(stub_foundry_http):
    stub_foundry_http.respond(json=cj.page())

    result = invoke("connectivity", "import", "list-file", cj.CONNECTION_RID)

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "No results." in result.stderr


# ----------------------------------------------------------- import execute


def test_execute_file_import_prints_the_build_rid(stub_foundry_http):
    stub_foundry_http.respond(json=cj.BUILD_RID)

    result = invoke(
        "connectivity",
        "import",
        "execute-file",
        cj.CONNECTION_RID,
        cj.FILE_IMPORT_RID,
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == cj.BUILD_RID
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/fileImports/{cj.FILE_IMPORT_RID}/execute",
    )


def test_execute_file_import_table_points_to_the_build(stub_foundry_http):
    stub_foundry_http.respond(json=cj.BUILD_RID)

    result = invoke(
        "connectivity", "import", "execute-file", cj.CONNECTION_RID, cj.FILE_IMPORT_RID
    )

    assert result.exit_code == 0, result.output
    assert "Build RID" in result.stdout and cj.BUILD_RID in result.stdout
    assert f"pltr orchestration builds get {cj.BUILD_RID}" in result.stderr


def test_execute_file_import_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "ExecuteFileImportPermissionDenied",
            error_code="PERMISSION_DENIED",
            parameters={
                "fileImportRid": cj.FILE_IMPORT_RID,
                "connectionRid": cj.CONNECTION_RID,
            },
        ),
    )

    result = invoke(
        "connectivity",
        "import",
        "execute-file",
        cj.CONNECTION_RID,
        cj.FILE_IMPORT_RID,
        "-f",
        "json",
    )

    assert result.exit_code == 4
    assert json_error(result)["errorName"] == "ExecuteFileImportPermissionDenied"


def test_execute_table_import(stub_foundry_http):
    stub_foundry_http.respond(json=cj.BUILD_RID)

    result = invoke(
        "connectivity",
        "import",
        "execute-table",
        cj.CONNECTION_RID,
        cj.TABLE_IMPORT_RID,
        "-f",
        "csv",
    )

    assert result.exit_code == 0, result.output
    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row == {"Build RID": cj.BUILD_RID}
    [request] = stub_foundry_http.requests
    assert request.url.path == (
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/tableImports/{cj.TABLE_IMPORT_RID}/execute"
    )


# ------------------------------------------------------------- import table

TABLE_CONFIG = '{"type": "jdbcImportConfig", "query": "SELECT * FROM orders"}'


def test_import_table_creates_a_table_import(stub_foundry_http):
    stub_foundry_http.respond(json=cj.table_import())

    result = invoke(
        "connectivity",
        "import",
        "table",
        cj.CONNECTION_RID,
        cj.DATASET_RID,
        "--name",
        "Orders",
        "--mode",
        "snapshot",
        "--config",
        TABLE_CONFIG,
    )

    assert result.exit_code == 0, result.output
    assert "SELECT * FROM orders" in result.stdout
    assert f"Created table import 'Orders' ({cj.TABLE_IMPORT_RID})" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{CONNECTIONS}/{cj.CONNECTION_RID}/tableImports",
    )
    assert json.loads(request.content) == {
        "datasetRid": cj.DATASET_RID,
        "importMode": "SNAPSHOT",
        "displayName": "Orders",
        "config": json.loads(TABLE_CONFIG),
    }


def test_import_table_options_and_config_file(stub_foundry_http, tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(TABLE_CONFIG)
    stub_foundry_http.respond(json=cj.table_import(allowSchemaChanges=True))

    result = invoke(
        "connectivity",
        "import",
        "table",
        cj.CONNECTION_RID,
        cj.DATASET_RID,
        "-n",
        "Orders",
        "--mode",
        "APPEND",
        "-c",
        f"@{config_file}",
        "--allow-schema-changes",
        "--branch",
        "develop",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["allowSchemaChanges"] is True
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["allowSchemaChanges"] is True
    assert body["branchName"] == "develop"
    assert body["importMode"] == "APPEND"


def test_import_table_rejects_update_mode(stub_foundry_http):
    result = invoke(
        "connectivity",
        "import",
        "table",
        cj.CONNECTION_RID,
        cj.DATASET_RID,
        "-n",
        "Orders",
        "--mode",
        "UPDATE",
        "-c",
        TABLE_CONFIG,
    )

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_import_table_config_needs_a_known_type(stub_foundry_http):
    result = invoke(
        "connectivity",
        "import",
        "table",
        cj.CONNECTION_RID,
        cj.DATASET_RID,
        "-n",
        "Orders",
        "--mode",
        "SNAPSHOT",
        "-c",
        '{"type": "mysqlImportConfig", "query": "SELECT 1"}',
        "-f",
        "json",
    )

    assert result.exit_code == 2
    assert json_error(result)["type"] == "usage_error"
    assert stub_foundry_http.requests == []


# ----------------------------------------------- import get-table/list-table


def test_get_table_import_csv(stub_foundry_http):
    stub_foundry_http.respond(json=cj.table_import())

    result = invoke(
        "connectivity",
        "import",
        "get-table",
        cj.CONNECTION_RID,
        cj.TABLE_IMPORT_RID,
        "-f",
        "csv",
    )

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row["RID"] == cj.TABLE_IMPORT_RID
    assert row["Config Type"] == "jdbcImportConfig"
    assert row["Query"] == "SELECT * FROM orders"
    assert row["Allow Schema Changes"] == "false"
    assert row["Branch"] == "master"


def test_list_table_imports_table(stub_foundry_http):
    stub_foundry_http.respond(json=cj.page(cj.table_import()))

    result = invoke("connectivity", "import", "list-table", cj.CONNECTION_RID)

    assert result.exit_code == 0, result.output
    for expected in ("Orders", cj.TABLE_IMPORT_RID, "SNAPSHOT", "jdbcImportConfig"):
        assert expected in result.stdout
    assert result.stderr == ""


def test_list_table_imports_connection_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "ConnectionNotFound", parameters={"connectionRid": cj.CONNECTION_RID}
        ),
    )

    result = invoke("connectivity", "import", "list-table", cj.CONNECTION_RID)

    assert result.exit_code == 5
    assert "Error: ConnectionNotFound" in result.stderr
    assert result.stdout == ""
