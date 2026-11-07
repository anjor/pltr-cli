"""Tests for `pltr functions` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_functions as ff

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()
API = "/api/v2/functions"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, ["functions", *args], **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


# ------------------------------------------------------------------- help


@pytest.mark.parametrize(
    "group, commands",
    [
        ("query", ("get", "get-by-rid", "execute", "execute-by-rid")),
        ("value-type", ("get",)),
    ],
)
def test_every_command_is_labeled_beta(group, commands):
    result = invoke(group, "--help")

    lines = result.stdout.splitlines()
    for command in commands:
        line = next(
            line for line in lines if line.lstrip("│ ").startswith(f"{command} ")
        )
        assert "[beta]" in line, line


# -------------------------------------------------------------- query get


def test_get_query_table(stub_foundry_http):
    stub_foundry_http.respond(json=ff.query())

    result = invoke("query", "get", ff.QUERY_API_NAME)

    assert result.exit_code == 0, result.output
    for expected in (
        ff.QUERY_API_NAME,
        "Get top customers",
        ff.QUERY_RID,
        "1.2.0",
        "limit (integer), region (string, optional)",
        "array",
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/queries/{ff.QUERY_API_NAME}"
    assert dict(request.url.params) == {"preview": "true"}


def test_get_query_json(stub_foundry_http):
    stub_foundry_http.respond(json=ff.query())

    result = invoke("query", "get", ff.QUERY_API_NAME, "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == ff.query()
    assert result.stderr == ""


def test_get_query_csv(stub_foundry_http):
    stub_foundry_http.respond(json=ff.query(description=None))

    result = invoke("query", "get", ff.QUERY_API_NAME, "-f", "csv")

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert (row["API Name"], row["Description"], row["Output Type"]) == (
        ff.QUERY_API_NAME,
        "",
        "array",
    )


def test_get_query_version_options(stub_foundry_http):
    stub_foundry_http.respond(json=ff.query())

    result = invoke(
        "query",
        "get",
        ff.QUERY_API_NAME,
        "-v",
        "1.0.0",
        "--include-prerelease",
        "--latest-version-resolution",
        "publish_time",
    )

    assert result.exit_code == 0, result.output
    assert dict(stub_foundry_http.requests[0].url.params) == {
        "version": "1.0.0",
        "includePrerelease": "true",
        "latestVersionResolution": "PUBLISH_TIME",
        "preview": "true",
    }


def test_get_query_bad_resolution_is_a_usage_error(stub_foundry_http):
    result = invoke(
        "query",
        "get",
        ff.QUERY_API_NAME,
        "--latest-version-resolution",
        "NEWEST",
        "-f",
        "json",
    )

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "usage_error"
    assert stub_foundry_http.requests == []


def test_get_query_preview_flag_is_a_deprecated_no_op(stub_foundry_http):
    stub_foundry_http.respond(json=ff.query())

    result = invoke("query", "get", ff.QUERY_API_NAME, "--preview", "-f", "json")

    assert result.exit_code == 0, result.output
    [warning] = json_lines(result.stderr)
    assert "--preview is deprecated" in warning["message"]
    assert stub_foundry_http.requests[0].url.params["preview"] == "true"


def test_get_query_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error("QueryNotFound", parameters={"queryApiName": ff.QUERY_API_NAME}),
    )

    result = invoke("query", "get", ff.QUERY_API_NAME, "--format", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == ("not_found", "QueryNotFound")


# ------------------------------------------------------- query get-by-rid


def test_get_query_by_rid(stub_foundry_http):
    stub_foundry_http.respond(json=ff.query())

    result = invoke(
        "query", "get-by-rid", ff.QUERY_RID, "--include-prerelease", "-f", "json"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == ff.query()
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/queries/getByRid"
    assert dict(request.url.params) == {
        "rid": ff.QUERY_RID,
        "includePrerelease": "true",
        "preview": "true",
    }


def test_get_query_by_rid_invalid_rid(stub_foundry_http):
    result = invoke("query", "get-by-rid", "myQuery", "-f", "json")

    assert result.exit_code == 2
    assert "not a valid RID" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


def test_get_query_by_rid_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403, json=fj.error("GetByRidPermissionDenied", "PERMISSION_DENIED")
    )

    result = invoke("query", "get-by-rid", ff.QUERY_RID, "-f", "json")

    assert result.exit_code == 4
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == (
        "permission_denied",
        "GetByRidPermissionDenied",
    )


# ---------------------------------------------------------- query execute


def test_execute_query_list_result_table(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "value": [
                {"name": "Acme", "revenue": 1200.5},
                {"name": "Globex", "revenue": 900},
            ]
        }
    )

    result = invoke(
        "query", "execute", ff.QUERY_API_NAME, "--parameters", '{"limit": 2}'
    )

    assert result.exit_code == 0, result.output
    for expected in ("name", "revenue", "Acme", "1200.5", "Globex"):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/queries/{ff.QUERY_API_NAME}/execute",
    )
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {"parameters": {"limit": 2}}


def test_execute_query_json_is_the_api_response(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json={"value": {"count": 3, "ok": True}})
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"limit": 3, "since": "2024-01-01"}))

    result = invoke(
        "query",
        "execute",
        ff.QUERY_API_NAME,
        "-params",
        f"@{params}",
        "--version",
        "1.2.0",
        "--latest-version-resolution",
        "SEMANTIC_VERSION",
        "--include-prerelease",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"value": {"count": 3, "ok": True}}
    assert result.stderr == ""
    assert json.loads(stub_foundry_http.requests[0].content) == {
        "parameters": {"limit": 3, "since": "2024-01-01"},
        "version": "1.2.0",
        "includePrerelease": True,
        "latestVersionResolution": "SEMANTIC_VERSION",
    }


def test_execute_query_scalar_result_csv(stub_foundry_http):
    stub_foundry_http.respond(json={"value": 42})

    result = invoke("query", "execute", ff.QUERY_API_NAME, "-f", "csv")

    assert result.exit_code == 0, result.output
    assert list(csv.reader(io.StringIO(result.stdout))) == [["Value"], ["42"]]
    assert json.loads(stub_foundry_http.requests[0].content) == {"parameters": {}}


@pytest.mark.parametrize(
    "parameters, message",
    [
        ("{bad", "invalid JSON"),
        ("@/nonexistent/params.json", "cannot read"),
        ("[1, 2]", "Invalid argument"),
    ],
)
def test_execute_query_bad_parameters_are_a_usage_error(
    stub_foundry_http, parameters, message
):
    result = invoke(
        "query", "execute", ff.QUERY_API_NAME, "--parameters", parameters, "-f", "json"
    )

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert message in error["message"]
    assert stub_foundry_http.requests == []


def test_execute_query_validation_error_from_the_api(stub_foundry_http):
    stub_foundry_http.respond(
        400, json=fj.error("InvalidParameterValue", "INVALID_ARGUMENT")
    )

    result = invoke("query", "execute", ff.QUERY_API_NAME, "-f", "json")

    assert result.exit_code == 6
    assert json_lines(result.stderr)[-1]["errorName"] == "InvalidParameterValue"


# --------------------------------------------------- query execute-by-rid


def test_execute_query_by_rid_resolves_then_executes(stub_foundry_http):
    stub_foundry_http.respond(json=ff.query(version="2.0.0"))
    stub_foundry_http.respond(json={"value": ["Acme"]})

    result = invoke(
        "query",
        "execute-by-rid",
        ff.QUERY_RID,
        "--parameters",
        '{"limit": 1}',
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"value": ["Acme"]}
    get_request, execute_request = stub_foundry_http.requests
    assert get_request.url.path == f"{API}/queries/getByRid"
    assert get_request.url.params["rid"] == ff.QUERY_RID
    assert execute_request.url.path == f"{API}/queries/{ff.QUERY_API_NAME}/execute"
    assert execute_request.url.params["preview"] == "true"
    assert json.loads(execute_request.content) == {
        "parameters": {"limit": 1},
        "version": "2.0.0",
    }


def test_execute_query_by_rid_unknown_query(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("QueryNotFound", parameters={"rid": ff.QUERY_RID})
    )

    result = invoke("query", "execute-by-rid", ff.QUERY_RID, "-f", "json")

    assert result.exit_code == 5
    assert len(stub_foundry_http.requests) == 1  # nothing executed


# ------------------------------------------------------- value-type get


def test_get_value_type_table(stub_foundry_http):
    stub_foundry_http.respond(json=ff.value_type())

    result = invoke("value-type", "get", ff.VALUE_TYPE_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        ff.VALUE_TYPE_RID,
        "emailAddress",
        "Email address",
        ff.VALUE_TYPE_VERSION_ID,
        "string",
        '"pattern":"^[^@]+@[^@]+$"',
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/valueTypes/{ff.VALUE_TYPE_RID}"
    assert dict(request.url.params) == {"preview": "true"}


def test_get_value_type_json(stub_foundry_http):
    stub_foundry_http.respond(json=ff.value_type(description=None))

    result = invoke("value-type", "get", ff.VALUE_TYPE_RID, "-f", "json")

    expected = ff.value_type()
    del expected["description"]
    assert json.loads(result.stdout) == expected


def test_get_value_type_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "ValueTypeNotFound", parameters={"valueTypeRid": ff.VALUE_TYPE_RID}
        ),
    )

    result = invoke("value-type", "get", ff.VALUE_TYPE_RID, "-f", "json")

    assert result.exit_code == 5
    assert json_lines(result.stderr)[-1]["type"] == "not_found"
