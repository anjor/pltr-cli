"""Tests for `pltr dataset` (datasets, preview, schema, branches) against a
real FoundryClient (only HTTP is faked). Files, transactions and views are in
test_dataset_files.py, test_dataset_transactions.py and test_dataset_views.py.
"""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from pltr.config.profiles import ProfileManager
from tests import foundry_json as fj
from tests import foundry_json_dataset as dj
from tests.test_auth.fakes import (
    OAUTH_ACCESS_TOKEN,
    OAUTH_TOKEN_PATH,
    FakeFoundryHttp,
    FakeKeyring,
)

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

runner = CliRunner()
DATASET = dj.DATASET_RID
API = "/api/v2/datasets"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


@pytest.fixture
def stub(stub_foundry_http, isolated_home):
    return stub_foundry_http


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


# ------------------------------------------------------------------- help


@pytest.mark.parametrize(
    "group, beta, ga",
    [
        ("branches", {"transactions"}, {"list", "create", "get", "delete"}),
        (
            "transactions",
            {"list", "build"},
            {"start", "commit", "abort", "status"},
        ),
        ("jobs", {"list"}, set()),
        ("schedules", set(), {"list"}),
        ("files", set(), {"list", "upload", "get", "delete", "info"}),
    ],
)
def test_beta_commands_are_labeled_in_help(isolated_home, group, beta, ga):
    lines = invoke("dataset", group, "--help").stdout.splitlines()

    for command in beta | ga:
        line = next(line for line in lines if f" {command} " in line)
        assert ("[beta]" in line) == (command in beta), line


def test_views_list_was_removed(stub):
    result = invoke("dataset", "views", "list", DATASET)

    assert result.exit_code == 2
    assert "No such command 'list'" in result.stderr
    assert stub.requests == []


# -------------------------------------------------------------------- get


def test_get_dataset_table(stub):
    stub.respond(json=dj.dataset())

    result = invoke("dataset", "get", DATASET)

    assert result.exit_code == 0, result.output
    for expected in (DATASET, "sales", dj.FOLDER_RID):
        assert expected in result.stdout
    [request] = stub.requests
    assert (request.method, request.url.path) == ("GET", f"{API}/{DATASET}")
    assert "preview" not in request.url.params


def test_get_dataset_json_is_the_sdk_serialization(stub):
    stub.respond(json=dj.dataset())

    result = invoke("dataset", "get", DATASET, "--format", "json")

    assert json.loads(result.stdout) == dj.dataset()
    assert result.stderr == ""


def test_get_dataset_csv(stub):
    stub.respond(json=dj.dataset())

    result = invoke("dataset", "get", DATASET, "-f", "csv")

    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {"RID": DATASET, "Name": "sales", "Parent Folder": dj.FOLDER_RID}
    ]


def test_get_dataset_to_a_file(stub, tmp_path):
    stub.respond(json=dj.dataset())
    target = tmp_path / "dataset.json"

    result = invoke("dataset", "get", DATASET, "-f", "json", "-o", str(target))

    assert result.exit_code == 0
    assert result.stdout == ""
    assert json.loads(target.read_text()) == dj.dataset()


def test_get_dataset_not_found(stub):
    stub.respond(
        404, json=fj.error("DatasetNotFound", parameters={"datasetRid": DATASET})
    )

    result = invoke("dataset", "get", DATASET, "-f", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == ("not_found", "DatasetNotFound")
    assert error["parameters"] == {"datasetRid": DATASET}


def test_get_dataset_with_an_invalid_rid_is_a_usage_error(stub):
    result = invoke("dataset", "get", "not-a-rid", "-f", "json")

    assert result.exit_code == 2
    assert "not a valid RID" in json_lines(result.stderr)[-1]["message"]
    assert stub.requests == []


# ----------------------------------------------------------------- create


def test_create_dataset(stub):
    stub.respond(json=dj.dataset())

    result = invoke("dataset", "create", "sales", "--parent-folder", dj.FOLDER_RID)

    assert result.exit_code == 0, result.output
    assert f"Created dataset 'sales' ({DATASET})" in result.stderr
    assert DATASET in result.stdout
    [request] = stub.requests
    assert (request.method, request.url.path) == ("POST", API)
    assert json.loads(request.content) == {
        "name": "sales",
        "parentFolderRid": dj.FOLDER_RID,
    }


def test_create_dataset_json(stub):
    stub.respond(json=dj.dataset())

    result = invoke(
        "dataset", "create", "sales", "--parent-folder", dj.FOLDER_RID, "-f", "json"
    )

    assert json.loads(result.stdout) == dj.dataset()
    assert result.stderr == ""


def test_create_dataset_requires_a_parent_folder(stub):
    result = invoke("dataset", "create", "sales", "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "usage_error"
    assert stub.requests == []


# ---------------------------------------------------------------- preview


def preview_body():
    return dj.arrow_stream(
        {"id": [1, 2], "region": ["EMEA", None], "amount": [1.5, 2.25]}
    )


def test_preview_table(stub):
    stub.respond(content=preview_body())

    result = invoke("dataset", "preview", DATASET)

    assert result.exit_code == 0, result.output
    for expected in ("id", "region", "amount", "EMEA", "2.25"):
        assert expected in result.stdout
    [request] = stub.requests
    assert request.url.path == f"{API}/{DATASET}/readTable"
    assert dict(request.url.params) == {"format": "ARROW", "rowLimit": "10"}


def test_preview_json_rows(stub):
    stub.respond(content=preview_body())

    result = invoke("dataset", "preview", DATASET, "-f", "json")

    assert json.loads(result.stdout) == {
        "data": [
            {"id": 1, "region": "EMEA", "amount": 1.5},
            {"id": 2, "region": None, "amount": 2.25},
        ]
    }


def test_preview_csv_with_options(stub):
    stub.respond(content=preview_body())

    result = invoke(
        "dataset",
        "preview",
        DATASET,
        "--limit",
        "2",
        "--column",
        "id",
        "--column",
        "region",
        "--branch",
        "dev",
        "-f",
        "csv",
    )

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert rows == [
        {"id": "1", "region": "EMEA", "amount": "1.5"},
        {"id": "2", "region": "", "amount": "2.25"},
    ]
    [request] = stub.requests
    assert request.url.params.get_list("columns") == ["id", "region"]
    assert request.url.params["rowLimit"] == "2"
    assert request.url.params["branchName"] == "dev"


def test_preview_of_an_empty_dataset(stub):
    stub.respond(content=dj.arrow_stream({"id": []}))

    table = invoke("dataset", "preview", DATASET)
    stub.respond(content=dj.arrow_stream({"id": []}))
    as_csv = invoke("dataset", "preview", DATASET, "-f", "csv")
    stub.respond(content=dj.arrow_stream({"id": []}))
    as_json = invoke("dataset", "preview", DATASET, "-f", "json")

    assert table.exit_code == 0
    assert table.stdout == ""
    assert "No results." in table.stderr
    assert as_csv.stdout == "id\n"
    assert json.loads(as_json.stdout) == {"data": []}


def test_preview_rejects_a_zero_limit(stub):
    result = invoke("dataset", "preview", DATASET, "--limit", "0")

    assert result.exit_code == 2
    assert stub.requests == []


def test_preview_of_a_view_reports_the_api_error(stub):
    stub.respond(
        400,
        json=fj.error(
            "DatasetReadNotSupported",
            "INVALID_ARGUMENT",
            parameters={"datasetRid": DATASET, "branchName": "master"},
        ),
    )

    result = invoke("dataset", "preview", DATASET, "-f", "json")

    assert result.exit_code == 6
    assert json_lines(result.stderr)[-1]["errorName"] == "DatasetReadNotSupported"


# ----------------------------------------------------------------- schema


def test_schema_get_table_shows_one_row_per_field(stub):
    stub.respond(json=dj.schema_response())

    result = invoke("dataset", "schema", "get", DATASET)

    assert result.exit_code == 0, result.output
    for expected in ("region", "STRING", "DECIMAL(10,2)", "ARRAY<STRING>"):
        assert expected in result.stdout
    assert f"version {dj.VERSION_ID}" in result.stderr
    [request] = stub.requests
    assert request.url.path == f"{API}/{DATASET}/getSchema"
    assert "preview" not in request.url.params  # GA in SDK 1.111.0


def test_schema_get_json_is_the_api_response(stub):
    stub.respond(json=dj.schema_response())

    result = invoke(
        "dataset",
        "schema",
        "get",
        DATASET,
        "--branch",
        "dev",
        "--transaction-rid",
        dj.TRANSACTION_RID,
        "-f",
        "json",
    )

    assert json.loads(result.stdout) == dj.schema_response()
    assert result.stderr == ""
    [request] = stub.requests
    assert dict(request.url.params) == {
        "branchName": "dev",
        "endTransactionRid": dj.TRANSACTION_RID,
    }


def test_schema_get_csv(stub):
    stub.respond(json=dj.schema_response())

    result = invoke("dataset", "schema", "get", DATASET, "-f", "csv")

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert rows[0] == {"Name": "id", "Type": "LONG", "Nullable": "false"}
    assert [row["Type"] for row in rows] == [
        "LONG",
        "STRING",
        "DECIMAL(10,2)",
        "ARRAY<STRING>",
    ]


def test_schema_get_without_a_schema(stub):
    stub.respond(
        404,
        json=fj.error(
            "SchemaNotFound", parameters={"datasetRid": DATASET, "branchName": "master"}
        ),
    )

    result = invoke("dataset", "schema", "get", DATASET, "-f", "json")

    assert result.exit_code == 5
    assert json_lines(result.stderr)[-1]["errorName"] == "SchemaNotFound"


SCHEMA = {"fieldSchemaList": [dj.field("id", "LONG", nullable=False)]}


def test_schema_set_from_inline_json(stub):
    stub.respond(json=dj.schema_response(fields=SCHEMA["fieldSchemaList"]))

    result = invoke(
        "dataset",
        "schema",
        "set",
        DATASET,
        "--json",
        json.dumps(SCHEMA),
        "--branch",
        "dev",
        "--transaction-rid",
        dj.TRANSACTION_RID,
        "--dataframe-reader",
        "csv",
        "--yes",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["schema"] == SCHEMA
    [request] = stub.requests
    assert (request.method, request.url.path) == ("PUT", f"{API}/{DATASET}/putSchema")
    assert json.loads(request.content) == {
        "schema": SCHEMA,
        "branchName": "dev",
        "endTransactionRid": dj.TRANSACTION_RID,
        "dataframeReader": "CSV",
    }


def test_schema_set_from_a_file_in_the_legacy_shorthand(stub, tmp_path):
    path = tmp_path / "schema.json"
    path.write_text(
        json.dumps(
            {
                "fields": [
                    {"name": "id", "type": "LONG", "nullable": False},
                    {"name": "region", "type": "STRING"},
                ]
            }
        )
    )
    stub.respond(json=dj.schema_response())

    result = invoke("dataset", "schema", "set", DATASET, "--json-file", str(path), "-y")

    assert result.exit_code == 0, result.output
    assert json.loads(stub.requests[0].content) == {
        "schema": {
            "fieldSchemaList": [
                {"name": "id", "type": "LONG", "nullable": False},
                {"name": "region", "type": "STRING", "nullable": True},
            ]
        }
    }


def test_schema_set_accepts_schema_get_output(stub, tmp_path):
    """`schema get -f json` output can be fed back to `schema set`."""
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(dj.schema_response()))
    stub.respond(json=dj.schema_response())

    result = invoke("dataset", "schema", "set", DATASET, "--json", f"@{path}", "-y")

    assert result.exit_code == 0, result.output
    assert (
        json.loads(stub.requests[0].content)["schema"]
        == (dj.schema_response()["schema"])
    )


def test_schema_set_from_csv(stub, tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("id,region\n1,EMEA\n2,APAC\n")
    stub.respond(json=dj.schema_response())

    result = invoke("dataset", "schema", "set", DATASET, "--from-csv", str(path), "-y")

    assert result.exit_code == 0, result.output
    assert "Inferred 2 fields" in result.stderr
    assert json.loads(stub.requests[0].content)["schema"] == {
        "fieldSchemaList": [
            {"name": "id", "type": "INTEGER", "nullable": False},
            {"name": "region", "type": "STRING", "nullable": False},
        ]
    }


def test_schema_set_prompt_lists_the_inferred_fields(stub, interactive, tmp_path):
    """The prompt showed only the number of fields (#181 review)."""
    path = tmp_path / "excel.csv"
    path.write_bytes("﻿id,big,note\n1,3000000000,a\n2,4000000000,\n".encode())
    stub.respond(json=dj.schema_response())

    result = invoke(
        "dataset", "schema", "set", DATASET, "--from-csv", str(path), input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert (
        f"Schema inferred from {path} (3 fields):\n"
        "  id: INTEGER\n"
        "  big: LONG\n"
        "  note: STRING (nullable)\n"
        f"Replace the schema of dataset {DATASET} with it? [y/N]:"
    ) in result.stderr
    assert "id: INTEGER" not in result.stdout  # the prompt is on stderr
    assert json.loads(stub.requests[0].content)["schema"]["fieldSchemaList"] == [
        {"name": "id", "type": "INTEGER", "nullable": False},
        {"name": "big", "type": "LONG", "nullable": False},
        {"name": "note", "type": "STRING", "nullable": True},
    ]


def test_schema_set_without_yes_shows_the_fields_in_the_error(stub):
    result = invoke(
        "dataset", "schema", "set", DATASET, "--json", json.dumps(SCHEMA), "-f", "json"
    )

    assert result.exit_code == 2
    message = json_lines(result.stderr)[-1]["message"]
    assert message.startswith("Schema from --json (1 field):\n  id: LONG\n")
    assert stub.requests == []


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--json", json.dumps(SCHEMA), "--json-file", "schema.json"],
    ],
)
def test_schema_set_needs_exactly_one_source(stub, args, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "schema.json").write_text(json.dumps(SCHEMA))

    result = invoke("dataset", "schema", "set", DATASET, *args, "-y", "-f", "json")

    assert result.exit_code == 2
    assert "exactly one of" in json_lines(result.stderr)[-1]["message"]
    assert stub.requests == []


def test_schema_set_rejects_an_invalid_field_type(stub):
    bad = {"fieldSchemaList": [{"name": "id", "type": "NUMBER", "nullable": True}]}

    result = invoke(
        "dataset",
        "schema",
        "set",
        DATASET,
        "--json",
        json.dumps(bad),
        "-y",
        "-f",
        "json",
    )

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert "not a valid dataset schema" in error["message"]
    assert stub.requests == []


def test_schema_set_rejects_invalid_json(stub):
    result = invoke("dataset", "schema", "set", DATASET, "--json", "{nope", "-y")

    assert result.exit_code == 2
    assert "invalid JSON" in result.stderr
    assert stub.requests == []


def test_schema_set_requires_yes_when_not_interactive(stub):
    result = invoke(
        "dataset", "schema", "set", DATASET, "--json", json.dumps(SCHEMA), "-f", "json"
    )

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub.requests == []


def test_schema_set_prompts_when_interactive(stub, interactive):
    stub.respond(json=dj.schema_response())

    declined = invoke(
        "dataset", "schema", "set", DATASET, "--json", json.dumps(SCHEMA), input="n\n"
    )
    assert declined.exit_code == 1
    assert stub.requests == []

    accepted = invoke(
        "dataset", "schema", "set", DATASET, "--json", json.dumps(SCHEMA), input="y\n"
    )
    assert accepted.exit_code == 0, accepted.output
    assert f"Replace the schema of dataset {DATASET}" in accepted.stderr
    assert len(stub.requests) == 1


def test_schema_apply_infers_and_applies(stub):
    stub.respond(json=dj.inference_response())
    stub.respond(json=dj.metadata_response())

    result = invoke("dataset", "schema", "apply", DATASET, "--yes", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dj.metadata_response()
    infer, apply = stub.requests
    assert infer.url.path == (
        f"/foundry-schema-inference/api/datasets/{DATASET}/branches/master/schema"
    )
    assert apply.url.path == (
        f"/foundry-metadata/api/schemas/datasets/{DATASET}/branches/master"
    )


def test_schema_apply_table_output_and_branch(stub):
    stub.respond(json=dj.inference_response())
    stub.respond(json=dj.metadata_response())

    result = invoke("dataset", "schema", "apply", DATASET, "-b", "dev", "-y")

    assert result.exit_code == 0, result.output
    assert "Applied the inferred schema" in result.stderr
    assert dj.TRANSACTION_RID in result.stdout
    assert "/branches/dev/schema" in stub.requests[0].url.path


def test_schema_apply_requires_yes_when_not_interactive(stub):
    result = invoke("dataset", "schema", "apply", DATASET)

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub.requests == []


def test_schema_apply_without_inferred_schema(stub):
    stub.respond(json={"data": {}})

    result = invoke("dataset", "schema", "apply", DATASET, "-y", "-f", "json")

    assert result.exit_code == 7
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "api_error"
    assert "returned no schema" in error["message"]
    assert len(stub.requests) == 1


def test_schema_apply_success_body_that_is_not_json(stub):
    """An API problem (exit 7), not invalid user input (exit 2)."""
    stub.respond(content=b"<html>Sign in</html>")

    result = invoke("dataset", "schema", "apply", DATASET, "-y", "-f", "json")

    assert result.exit_code == 7
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "invalid_response"
    assert "isn't valid JSON" in error["message"]


def test_schema_apply_http_error_is_structured(stub):
    stub.respond(
        403,
        json=fj.error(
            "ApplySchemaPermissionDenied",
            "PERMISSION_DENIED",
            parameters={"datasetRid": DATASET},
        ),
    )

    result = invoke("dataset", "schema", "apply", DATASET, "-y", "-f", "json")

    assert result.exit_code == 4
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"], error["statusCode"]) == (
        "permission_denied",
        "ApplySchemaPermissionDenied",
        403,
    )


# The labeled direct-HTTP command must authenticate exactly like the SDK
# client: token and OAuth profiles, and FOUNDRY_* environment variables.

HOST = "stack.palantirfoundry.com"
AUTH_ENV_VARS = (
    "PLTR_PROFILE",
    "FOUNDRY_HOST",
    "FOUNDRY_HOSTNAME",
    "FOUNDRY_TOKEN",
    "FOUNDRY_CLIENT_ID",
    "FOUNDRY_CLIENT_SECRET",
    "PLTR_KEYRING_TIMEOUT",
)


@pytest.fixture
def real_auth(tmp_path, monkeypatch):
    """Real AuthManager and foundry_sdk auth; only HTTP and the keyring are fake."""
    for name in AUTH_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return FakeFoundryHttp().install(monkeypatch), FakeKeyring().install(monkeypatch)


def use_profile(keyring: FakeKeyring, credentials: dict) -> None:
    keyring.store("stack", credentials)
    manager = ProfileManager()
    manager.add_profile("stack")
    manager.set_default("stack")


@pytest.mark.parametrize(
    "auth", ["token-profile", "oauth-profile", "env-token", "env-oauth"]
)
def test_schema_apply_uses_the_sdk_auth(real_auth, monkeypatch, auth):
    http, keyring = real_auth
    token = f"Bearer {OAUTH_ACCESS_TOKEN}"
    if auth == "token-profile":
        use_profile(
            keyring, {"auth_type": "token", "host": f"https://{HOST}", "token": "pt"}
        )
        token = "Bearer pt"
    elif auth == "oauth-profile":
        use_profile(
            keyring,
            {
                "auth_type": "oauth",
                "host": f"https://{HOST}",
                "client_id": "client-id",
                "client_secret": "client-secret",
            },
        )
    elif auth == "env-token":
        monkeypatch.setenv("FOUNDRY_HOST", HOST)
        monkeypatch.setenv("FOUNDRY_TOKEN", "et")
        token = "Bearer et"
    else:
        monkeypatch.setenv("FOUNDRY_HOST", HOST)
        monkeypatch.setenv("FOUNDRY_CLIENT_ID", "client-id")
        monkeypatch.setenv("FOUNDRY_CLIENT_SECRET", "client-secret")
    if auth.endswith("oauth") or auth == "oauth-profile":
        http.route_oauth_token()
    inference = (
        f"/foundry-schema-inference/api/datasets/{DATASET}/branches/master/schema"
    )
    metadata = f"/foundry-metadata/api/schemas/datasets/{DATASET}/branches/master"
    http.route("POST", inference, body=dj.inference_response())
    http.route("POST", metadata, body=dj.metadata_response())

    result = invoke("dataset", "schema", "apply", DATASET, "--yes", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dj.metadata_response()
    infer, apply = http.direct_requests
    assert infer["url"] == f"https://{HOST}{inference}"
    assert apply["url"] == f"https://{HOST}{metadata}"
    assert infer["headers"]["Authorization"] == token
    assert apply["headers"]["Authorization"] == token
    assert apply["json"] == dj.inference_response()["data"]["foundrySchema"]
    if "oauth" in auth:
        assert http.sdk_request(OAUTH_TOKEN_PATH).url.host == HOST


# --------------------------------------------------------------- branches


def test_list_branches_json_has_the_paged_shape(stub):
    stub.respond(json=dj.page([dj.branch(), dj.branch("dev", None)], "t2"))

    result = invoke("dataset", "branches", "list", DATASET, "-f", "json")

    assert json.loads(result.stdout) == dj.page(
        [dj.branch(), dj.branch("dev", None)], "t2"
    )
    [request] = stub.requests
    assert request.url.path == f"{API}/{DATASET}/branches"


def test_list_branches_table_hints_at_the_next_page(stub):
    stub.respond(json=dj.page([dj.branch()], "t2"))

    result = invoke("dataset", "branches", "list", DATASET)

    assert "master" in result.stdout
    assert dj.TRANSACTION_RID in result.stdout
    assert "--page-token t2" in result.stderr


def test_list_branches_all_pages(stub):
    stub.respond(json=dj.page([dj.branch()], "t2"))
    stub.respond(json=dj.page([dj.branch("dev")]))

    result = invoke(
        "dataset", "branches", "list", DATASET, "--all", "--page-size", "1", "-f", "csv"
    )

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [row["Name"] for row in rows] == ["master", "dev"]
    assert [dict(r.url.params) for r in stub.requests] == [
        {"pageSize": "1"},
        {"pageSize": "1", "pageToken": "t2"},
    ]


def test_create_branch_from_master_by_default(stub):
    stub.respond(json=dj.branch("master", dj.TRANSACTION_RID))
    stub.respond(json=dj.branch("dev", dj.TRANSACTION_RID))

    result = invoke("dataset", "branches", "create", DATASET, "dev", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dj.branch("dev", dj.TRANSACTION_RID)
    get, create = stub.requests
    assert (get.method, get.url.path) == ("GET", f"{API}/{DATASET}/branches/master")
    assert (create.method, create.url.path) == ("POST", f"{API}/{DATASET}/branches")
    assert json.loads(create.content) == {
        "name": "dev",
        "transactionRid": dj.TRANSACTION_RID,
    }


def test_create_branch_from_another_parent_without_transactions(stub):
    stub.respond(json=dj.branch("empty", None))
    stub.respond(json=dj.branch("dev", None))

    result = invoke(
        "dataset", "branches", "create", DATASET, "dev", "--parent", "empty"
    )

    assert result.exit_code == 0, result.output
    assert "Created branch 'dev'" in result.stderr
    get, create = stub.requests
    assert get.url.path == f"{API}/{DATASET}/branches/empty"
    assert json.loads(create.content) == {"name": "dev"}


def test_create_branch_at_a_transaction(stub):
    stub.respond(json=dj.branch("dev", dj.OTHER_TRANSACTION_RID))

    result = invoke(
        "dataset",
        "branches",
        "create",
        DATASET,
        "dev",
        "--transaction-rid",
        dj.OTHER_TRANSACTION_RID,
    )

    assert result.exit_code == 0, result.output
    [create] = stub.requests  # no parent lookup
    assert json.loads(create.content)["transactionRid"] == dj.OTHER_TRANSACTION_RID


def test_create_branch_rejects_parent_and_transaction(stub):
    result = invoke(
        "dataset",
        "branches",
        "create",
        DATASET,
        "dev",
        "--parent",
        "master",
        "--transaction-rid",
        dj.TRANSACTION_RID,
    )

    assert result.exit_code == 2
    assert "not both" in result.stderr
    assert stub.requests == []


def test_create_branch_with_a_missing_parent(stub):
    stub.respond(
        404,
        json=fj.error(
            "BranchNotFound", parameters={"datasetRid": DATASET, "branchName": "nope"}
        ),
    )

    result = invoke(
        "dataset",
        "branches",
        "create",
        DATASET,
        "dev",
        "--parent",
        "nope",
        "-f",
        "json",
    )

    assert result.exit_code == 5
    assert json_lines(result.stderr)[-1]["errorName"] == "BranchNotFound"
    assert len(stub.requests) == 1  # nothing was created


def test_get_branch(stub):
    stub.respond(json=dj.branch("dev"))

    result = invoke("dataset", "branches", "get", DATASET, "dev", "-f", "csv")

    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {"Name": "dev", "Transaction RID": dj.TRANSACTION_RID}
    ]
    assert stub.requests[0].url.path == f"{API}/{DATASET}/branches/dev"


def test_delete_branch_with_yes(stub):
    stub.respond(204)

    result = invoke(
        "dataset", "branches", "delete", DATASET, "dev", "--yes", "-f", "json"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    [request] = stub.requests
    assert (request.method, request.url.path) == (
        "DELETE",
        f"{API}/{DATASET}/branches/dev",
    )


def test_delete_branch_refuses_without_yes_when_not_interactive(stub):
    result = invoke("dataset", "branches", "delete", DATASET, "dev", "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub.requests == []


def test_delete_branch_prompts_when_interactive(stub, interactive):
    stub.respond(204)

    result = invoke("dataset", "branches", "delete", DATASET, "dev", input="y\n")

    assert result.exit_code == 0, result.output
    assert f"Delete branch 'dev' of dataset {DATASET}?" in result.stderr
    assert "Deleted branch 'dev'" in result.stderr
    assert result.stdout == ""


def test_delete_branch_never_deletes_master(stub):
    result = invoke("dataset", "branches", "delete", DATASET, "MASTER", "--yes")

    assert result.exit_code == 2
    assert "master branch" in result.stderr
    assert stub.requests == []


def test_branch_transactions_is_beta(stub):
    stub.respond(json=dj.page([dj.transaction()]))

    result = invoke("dataset", "branches", "transactions", DATASET, "dev", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dj.sdk_json(dj.page([dj.transaction()]))
    [request] = stub.requests
    assert request.url.path == f"{API}/{DATASET}/branches/dev/transactions"
    assert request.url.params["preview"] == "true"
