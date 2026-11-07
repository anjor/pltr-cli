"""Tests for `pltr models` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_models as fm

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()
API = "/api/v2/models"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, ["models", *args], **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


# ------------------------------------------------------------------- help


@pytest.mark.parametrize(
    "group, commands", [("model", ("create", "get")), ("version", ("get", "list"))]
)
def test_every_command_is_labeled_beta(group, commands):
    result = invoke(group, "--help")

    lines = result.stdout.splitlines()
    for command in commands:
        line = next(
            line for line in lines if line.lstrip("│| ").startswith(f"{command} ")
        )
        assert "[beta]" in line, line


# ----------------------------------------------------------- model create


def test_create_model(stub_foundry_http):
    stub_foundry_http.respond(json=fm.model())

    result = invoke("model", "create", "fraud-detector", "--folder", fm.FOLDER_RID)

    assert result.exit_code == 0, result.output
    assert f"Created model 'fraud-detector' ({fm.MODEL_RID})" in result.stderr
    assert fm.MODEL_RID in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", API)
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {
        "name": "fraud-detector",
        "parentFolderRid": fm.FOLDER_RID,
    }


def test_create_model_short_folder_flag_and_json(stub_foundry_http):
    """-f stays --folder here, so --format has no short flag."""
    stub_foundry_http.respond(json=fm.model())

    result = invoke(
        "model", "create", "fraud-detector", "-f", fm.FOLDER_RID, "--format", "json"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == fm.model()
    assert result.stderr == ""


def test_create_model_requires_a_folder(stub_foundry_http):
    result = invoke("model", "create", "fraud-detector", "--format", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "usage_error"
    assert stub_foundry_http.requests == []


def test_create_model_preview_flag_is_a_deprecated_no_op(stub_foundry_http):
    stub_foundry_http.respond(json=fm.model())

    result = invoke(
        "model", "create", "m", "-f", fm.FOLDER_RID, "--preview", "--format", "json"
    )

    assert result.exit_code == 0, result.output
    [warning] = json_lines(result.stderr)
    assert "--preview is deprecated" in warning["message"]


def test_create_model_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403, json=fj.error("CreateModelPermissionDenied", "PERMISSION_DENIED")
    )

    result = invoke(
        "model", "create", "m", "--folder", fm.FOLDER_RID, "--format", "json"
    )

    assert result.exit_code == 4
    assert json_lines(result.stderr)[-1]["errorName"] == "CreateModelPermissionDenied"


# -------------------------------------------------------------- model get


def test_get_model(stub_foundry_http):
    stub_foundry_http.respond(json=fm.model())

    result = invoke("model", "get", fm.MODEL_RID)

    assert result.exit_code == 0, result.output
    assert fm.MODEL_RID in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/{fm.MODEL_RID}"
    assert dict(request.url.params) == {"preview": "true"}


def test_get_model_csv(stub_foundry_http):
    stub_foundry_http.respond(json=fm.model())

    result = invoke("model", "get", fm.MODEL_RID, "-f", "csv")

    assert list(csv.DictReader(io.StringIO(result.stdout))) == [{"RID": fm.MODEL_RID}]


def test_get_model_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("ModelNotFound", parameters={"modelRid": fm.MODEL_RID})
    )

    result = invoke("model", "get", fm.MODEL_RID, "-f", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == ("not_found", "ModelNotFound")


# ------------------------------------------------------------ version get


def test_get_version_table(stub_foundry_http):
    stub_foundry_http.respond(json=fm.model_version())

    result = invoke("version", "get", fm.MODEL_RID, fm.VERSION_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        fm.VERSION_RID,
        "codeRepository",
        fm.EXPERIMENT_RID,
        "transactions (tabular)",
        "score (parameter)",
        "scikit-learn=1.3.0, pandas=2.1.0",
        fm.REPOSITORY_RID,
        "2024-01-05T00:00:00+00:00",
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/{fm.MODEL_RID}/versions/{fm.VERSION_RID}"
    assert dict(request.url.params) == {"preview": "true"}


def test_get_version_json(stub_foundry_http):
    stub_foundry_http.respond(json=fm.model_version())

    result = invoke("version", "get", fm.MODEL_RID, fm.VERSION_RID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == fm.sdk_json(fm.model_version())
    assert result.stderr == ""


def test_get_version_needs_a_version_rid(stub_foundry_http):
    """The old help suggested version names such as v1.0.0; the API takes RIDs."""
    result = invoke("version", "get", fm.MODEL_RID, "v1.0.0", "-f", "json")

    assert result.exit_code == 2
    assert "not a valid RID" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


# ----------------------------------------------------------- version list


def test_list_versions_csv(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": [
                fm.model_version(),
                fm.model_version(fm.VERSION_RID_2, source={"type": "sdk"}),
            ]
        }
    )

    result = invoke("version", "list", fm.MODEL_RID, "--format", "csv")

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [(row["RID"], row["Source"]) for row in rows] == [
        (fm.VERSION_RID, "codeRepository"),
        (fm.VERSION_RID_2, "sdk"),
    ]
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/{fm.MODEL_RID}/versions"
    assert dict(request.url.params) == {"preview": "true"}


def test_list_versions_json_has_the_paged_shape(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [fm.model_version()], "nextPageToken": "next"}
    )

    result = invoke(
        "version", "list", fm.MODEL_RID, "--branch", "develop", "--format", "json"
    )

    assert json.loads(result.stdout) == {
        "data": [fm.sdk_json(fm.model_version())],
        "nextPageToken": "next",
    }
    assert dict(stub_foundry_http.requests[0].url.params) == {
        "branch": "develop",
        "preview": "true",
    }


def test_list_versions_all_pages(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [fm.model_version()], "nextPageToken": "t2"}
    )
    stub_foundry_http.respond(json={"data": [fm.model_version(fm.VERSION_RID_2)]})

    result = invoke(
        "version", "list", fm.MODEL_RID, "--all", "--page-size", "1", "-f", "json"
    )

    assert result.exit_code == 0, result.output
    assert [v["rid"] for v in json.loads(result.stdout)["data"]] == [
        fm.VERSION_RID,
        fm.VERSION_RID_2,
    ]
    assert [dict(r.url.params) for r in stub_foundry_http.requests] == [
        {"pageSize": "1", "preview": "true"},
        {"pageSize": "1", "pageToken": "t2", "preview": "true"},
    ]


def test_list_versions_table_hints_at_the_next_page(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [fm.model_version()], "nextPageToken": "next"}
    )

    result = invoke("version", "list", fm.MODEL_RID)

    assert result.exit_code == 0, result.output
    assert fm.VERSION_RID in result.stdout
    assert "--page-token next" in result.stderr


def test_list_versions_preview_flag_is_a_deprecated_no_op(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    result = invoke("version", "list", fm.MODEL_RID, "--preview")

    assert result.exit_code == 0, result.output
    assert "--preview is deprecated" in result.stderr
    assert "No results." in result.stderr
