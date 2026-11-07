"""Tests for `pltr streams` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_streams as st

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()

SCHEMA = json.dumps(st.SCHEMA)


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


# -------------------------------------------------------------------- help


def help_line(help_text: str, command: str) -> str:
    return next(row for row in help_text.splitlines() if f" {command} " in row)


def test_beta_commands_are_labeled():
    dataset_help = invoke("streams", "dataset", "--help").stdout
    assert "[beta]" in help_line(dataset_help, "create")

    stream_help = invoke("streams", "stream", "--help").stdout
    for command in ("create", "reset"):
        assert "[beta]" in help_line(stream_help, command), command
    for command in ("get", "publish", "publish-batch"):
        assert "[beta]" not in help_line(stream_help, command), command


def test_schema_help_documents_the_real_stream_schema_format():
    help_text = invoke("streams", "dataset", "create", "--help").stdout
    assert '"fields"' in help_text
    assert "fieldSchemaList" not in help_text


# ---------------------------------------------------------- dataset create


def test_create_dataset(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=st.dataset())
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(SCHEMA)

    result = invoke(
        "streams",
        "dataset",
        "create",
        "sensor-data",
        "--folder",
        st.FOLDER_RID,
        "--schema",
        f"@{schema_file}",
        "--partitions",
        "5",
        "--type",
        "high_throughput",
        "--compressed",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == st.dataset()
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.params["preview"]) == ("POST", "true")
    assert json.loads(request.content) == {
        "name": "sensor-data",
        "parentFolderRid": st.FOLDER_RID,
        "schema": st.SCHEMA,
        "partitionsCount": 5,
        "streamType": "HIGH_THROUGHPUT",
        "compressed": True,
    }


def test_create_dataset_table_and_short_flags(stub_foundry_http):
    stub_foundry_http.respond(json=st.dataset())

    result = invoke(
        "streams",
        "dataset",
        "create",
        "sensor-data",
        "-f",
        st.FOLDER_RID,
        "-s",
        SCHEMA,
        "-b",
        "develop",
    )

    assert result.exit_code == 0, result.output
    for expected in (st.DATASET_RID, "sensor-data", st.FOLDER_RID):
        assert expected in result.stdout
    assert (
        f"Created streaming dataset 'sensor-data' ({st.DATASET_RID})" in result.stderr
    )
    assert json.loads(stub_foundry_http.requests[0].content)["branchName"] == "develop"


def test_create_dataset_rejects_the_old_documented_schema_format(stub_foundry_http):
    result = invoke(
        "streams",
        "dataset",
        "create",
        "x",
        "-f",
        st.FOLDER_RID,
        "-s",
        '{"fieldSchemaList": [{"name": "value", "type": "STRING"}]}',
        "--format",
        "json",
    )

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert '"fields" list' in error["message"]
    assert stub_foundry_http.requests == []


def test_create_dataset_invalid_schema_field_is_a_usage_error(stub_foundry_http):
    bad = json.dumps({"fields": [{"name": "id"}]})  # no "schema"

    result = invoke(
        "streams",
        "dataset",
        "create",
        "x",
        "-f",
        st.FOLDER_RID,
        "-s",
        bad,
        "--format",
        "json",
    )

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "usage_error"
    assert stub_foundry_http.requests == []


def test_create_dataset_invalid_json(stub_foundry_http):
    result = invoke("streams", "dataset", "create", "x", "-f", st.FOLDER_RID, "-s", "{")

    assert result.exit_code == 2
    assert "invalid JSON" in result.stderr


def test_create_dataset_rejects_unknown_stream_type(stub_foundry_http):
    result = invoke(
        "streams",
        "dataset",
        "create",
        "x",
        "-f",
        st.FOLDER_RID,
        "-s",
        SCHEMA,
        "--type",
        "FAST",
    )

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_create_dataset_name_conflict(stub_foundry_http):
    stub_foundry_http.respond(
        409,
        json=fj.error(
            "ResourceNameAlreadyExists",
            "CONFLICT",
            parameters={"parentFolderRid": st.FOLDER_RID, "displayName": "sensor-data"},
        ),
    )

    result = invoke(
        "streams",
        "dataset",
        "create",
        "sensor-data",
        "-f",
        st.FOLDER_RID,
        "-s",
        SCHEMA,
        "--format",
        "json",
    )

    assert result.exit_code == 7
    assert json_lines(result.stderr)[-1]["errorName"] == "ResourceNameAlreadyExists"


def test_create_dataset_preview_is_a_deprecated_no_op(stub_foundry_http):
    stub_foundry_http.respond(json=st.dataset())

    result = invoke(
        "streams",
        "dataset",
        "create",
        "x",
        "-f",
        st.FOLDER_RID,
        "-s",
        SCHEMA,
        "--preview",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    [warning] = json_lines(result.stderr)
    assert "--preview is deprecated" in warning["message"]
    assert stub_foundry_http.requests[0].url.params["preview"] == "true"


# ----------------------------------------------------------- stream create


def test_create_stream(stub_foundry_http):
    stub_foundry_http.respond(json=st.stream("feature"))

    result = invoke(
        "streams",
        "stream",
        "create",
        st.DATASET_RID,
        "--branch",
        "feature",
        "--schema",
        SCHEMA,
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == st.stream("feature")
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/streams/datasets/{st.DATASET_RID}/streams"
    assert request.url.params["preview"] == "true"
    assert json.loads(request.content) == {"branchName": "feature", "schema": st.SCHEMA}


def test_create_stream_branch_exists(stub_foundry_http):
    stub_foundry_http.respond(
        409,
        json=fj.error(
            "BranchAlreadyExists",
            "CONFLICT",
            parameters={"datasetRid": st.DATASET_RID, "branchName": "feature"},
        ),
    )

    result = invoke(
        "streams", "stream", "create", st.DATASET_RID, "-b", "feature", "-s", SCHEMA
    )

    assert result.exit_code == 7
    assert "BranchAlreadyExists" in result.stderr
    assert result.stdout == ""


# -------------------------------------------------------------- stream get


def test_get_stream_table(stub_foundry_http):
    stub_foundry_http.respond(json=st.stream())

    result = invoke("streams", "stream", "get", st.DATASET_RID, "--branch", "master")

    assert result.exit_code == 0, result.output
    for expected in ("master", st.VIEW_RID, "LOW_LATENCY", "id (long), value (string)"):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {}  # GA


def test_get_stream_csv(stub_foundry_http):
    stub_foundry_http.respond(json=st.stream(compressed=True))

    result = invoke(
        "streams", "stream", "get", st.DATASET_RID, "-b", "master", "-f", "csv"
    )

    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {
            "Branch": "master",
            "View RID": st.VIEW_RID,
            "Stream Type": "LOW_LATENCY",
            "Partitions": "1",
            "Compressed": "true",
            "Fields": "id (long), value (string)",
            "Key Fields": "id",
        }
    ]


def test_get_stream_json_is_the_sdk_serialization(stub_foundry_http):
    stub_foundry_http.respond(json=st.stream())

    result = invoke(
        "streams", "stream", "get", st.DATASET_RID, "-b", "master", "-f", "json"
    )

    assert json.loads(result.stdout) == st.stream()


def test_get_stream_not_found(stub_foundry_http):
    stub_foundry_http.respond(404, json=st.stream_not_found("nope"))

    result = invoke(
        "streams", "stream", "get", st.DATASET_RID, "-b", "nope", "-f", "json"
    )

    assert result.exit_code == 5
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == ("not_found", "StreamNotFound")
    assert error["parameters"]["streamBranchName"] == "nope"


def test_get_stream_invalid_rid(stub_foundry_http):
    result = invoke(
        "streams", "stream", "get", "not-a-rid", "-b", "master", "-f", "json"
    )

    assert result.exit_code == 2
    assert "is not a valid RID" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


# ----------------------------------------------------------------- publish


def test_publish_record(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "streams",
        "stream",
        "publish",
        st.DATASET_RID,
        "-b",
        "master",
        "--record",
        '{"id": 1, "value": "a"}',
        "--view",
        st.VIEW_RID,
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Published 1 record to the stream on branch 'master'" in result.stderr
    [request] = stub_foundry_http.requests
    assert request.url.path.endswith("/streams/master/publishRecord")
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {
        "record": {"id": 1, "value": "a"},
        "viewRid": st.VIEW_RID,
    }


def test_publish_record_json_prints_null(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "streams",
        "stream",
        "publish",
        st.DATASET_RID,
        "-b",
        "master",
        "-r",
        '{"id": 1}',
        "-f",
        "json",
    )

    assert json.loads(result.stdout) is None
    assert result.stderr == ""


def test_publish_record_from_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(204)
    record_file = tmp_path / "record.json"
    record_file.write_text('{"id": 7}')

    result = invoke(
        "streams",
        "stream",
        "publish",
        st.DATASET_RID,
        "-b",
        "master",
        "-r",
        f"@{record_file}",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(stub_foundry_http.requests[0].content) == {"record": {"id": 7}}


@pytest.mark.parametrize("record", ["[1, 2]", "{"])
def test_publish_record_rejects_non_objects(stub_foundry_http, record):
    result = invoke(
        "streams", "stream", "publish", st.DATASET_RID, "-b", "master", "-r", record
    )

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_publish_record_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "PublishRecordToStreamPermissionDenied",
            "PERMISSION_DENIED",
            parameters={"datasetRid": st.DATASET_RID, "streamBranchName": "master"},
        ),
    )

    result = invoke(
        "streams",
        "stream",
        "publish",
        st.DATASET_RID,
        "-b",
        "master",
        "-r",
        '{"id": 1}',
        "-f",
        "json",
    )

    assert result.exit_code == 4
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == (
        "permission_denied",
        "PublishRecordToStreamPermissionDenied",
    )


def test_publish_batch(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "streams",
        "stream",
        "publish-batch",
        st.DATASET_RID,
        "-b",
        "master",
        "--records",
        '[{"id": 1}, {"id": 2}]',
    )

    assert result.exit_code == 0, result.output
    assert "Published 2 records" in result.stderr
    [request] = stub_foundry_http.requests
    assert request.url.path.endswith("/streams/master/publishRecords")
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {"records": [{"id": 1}, {"id": 2}]}


@pytest.mark.parametrize("records", ["[]", '{"id": 1}', "[1]"])
def test_publish_batch_needs_an_array_of_objects(stub_foundry_http, records):
    result = invoke(
        "streams",
        "stream",
        "publish-batch",
        st.DATASET_RID,
        "-b",
        "master",
        "-r",
        records,
        "-f",
        "json",
    )

    assert result.exit_code == 2
    assert "non-empty JSON array of objects" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------------- reset


def test_reset_requires_yes_when_not_interactive(stub_foundry_http):
    result = invoke("streams", "stream", "reset", st.DATASET_RID, "-b", "master")

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub_foundry_http.requests == []


def test_reset_with_yes(stub_foundry_http):
    stub_foundry_http.respond(json=st.stream())

    result = invoke(
        "streams",
        "stream",
        "reset",
        st.DATASET_RID,
        "-b",
        "master",
        "--yes",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == st.stream()
    [request] = stub_foundry_http.requests
    assert request.url.path.endswith(f"{st.DATASET_RID}/streams/master/reset")
    assert request.url.params["preview"] == "true"
    assert json.loads(request.content) == {}


def test_reset_with_new_settings(stub_foundry_http):
    stub_foundry_http.respond(json=st.stream(partitionsCount=4))

    result = invoke(
        "streams",
        "stream",
        "reset",
        st.DATASET_RID,
        "-b",
        "master",
        "-y",
        "--schema",
        SCHEMA,
        "--partitions",
        "4",
        "--type",
        "LOW_LATENCY",
        "--no-compressed",
    )

    assert result.exit_code == 0, result.output
    assert f"new view {st.VIEW_RID}" in result.stderr
    assert json.loads(stub_foundry_http.requests[0].content) == {
        "schema": st.SCHEMA,
        "partitionsCount": 4,
        "streamType": "LOW_LATENCY",
        "compressed": False,
    }


def test_reset_validates_the_schema_before_asking(stub_foundry_http):
    result = invoke(
        "streams", "stream", "reset", st.DATASET_RID, "-b", "master", "-s", "[]"
    )

    assert result.exit_code == 2
    assert '"fields" list' in result.stderr
    assert stub_foundry_http.requests == []


def test_reset_confirm_is_a_deprecated_alias_for_yes(stub_foundry_http):
    stub_foundry_http.respond(json=st.stream())

    result = invoke(
        "streams",
        "stream",
        "reset",
        st.DATASET_RID,
        "-b",
        "master",
        "--confirm",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json_lines(result.stderr) == [
        {
            "type": "warning",
            "message": "--confirm is deprecated and will be removed in a future "
            "release; use --yes.",
        }
    ]


def test_reset_prompts_on_stderr_when_interactive(stub_foundry_http, interactive):
    stub_foundry_http.respond(json=st.stream())

    result = invoke(
        "streams", "stream", "reset", st.DATASET_RID, "-b", "master", input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert "Reset the stream on branch 'master'" in result.stderr
    assert "deletes all of its records" in result.stderr
    assert len(stub_foundry_http.requests) == 1


def test_reset_answering_no_aborts(stub_foundry_http, interactive):
    result = invoke(
        "streams", "stream", "reset", st.DATASET_RID, "-b", "master", input="n\n"
    )

    assert result.exit_code == 1
    assert "Aborted" in result.stderr
    assert stub_foundry_http.requests == []
