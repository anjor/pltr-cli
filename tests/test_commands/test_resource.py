"""Tests for `pltr resource` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs

# Every Resource endpoint is GA: a stray preview= would raise a UserWarning.
pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()
RID = fs.DATASET_RID
RESOURCE_PATH = f"/api/v2/filesystem/resources/{RID}"
DATA = fs.child_resource(RID, "Sales Data", description="Quarterly sales")
SUBFOLDER = fs.child_resource("ri.compass.main.folder.sub", "Archive", "COMPASS_FOLDER")


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


def children_path(folder_rid: str) -> str:
    return f"/api/v2/filesystem/folders/{folder_rid}/children"


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


def test_get_metadata_was_removed():
    assert "get-metadata" not in invoke("resource", "--help").stdout
    assert invoke("resource", "get-metadata", RID).exit_code == 2


# --------------------------------------------------------------------- get


def test_get_resource_table(stub_foundry_http):
    stub_foundry_http.respond(json=DATA)

    result = invoke("resource", "get", RID)

    assert result.exit_code == 0, result.output
    for expected in (
        RID,
        "Sales Data",
        "FOUNDRY_DATASET",
        "/Test Space/Test Project/Sales Data",
        "Quarterly sales",
        fj.PROJECT_RID,
        fj.SPACE_RID,
        "NOT_TRASHED",
        "2024-01-01T00:00:00+00:00",
        fj.USER_ID,
    ):
        assert expected in result.stdout
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", RESOURCE_PATH)
    assert "preview" not in request.url.params


def test_get_resource_json_is_the_sdk_serialization(stub_foundry_http):
    stub_foundry_http.respond(json=DATA)

    result = invoke("resource", "get", RID, "--format", "json")

    assert result.exit_code == 0
    assert json.loads(result.stdout) == fj.sdk_json(DATA)
    assert result.stderr == ""


def test_get_resource_csv(stub_foundry_http):
    stub_foundry_http.respond(json=DATA)

    result = invoke("resource", "get", RID, "-f", "csv")

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row["RID"] == RID
    assert row["Type"] == "FOUNDRY_DATASET"
    assert row["Parent Folder"] == fj.PROJECT_RID
    assert row["Updated"] == "2024-01-02T00:00:00+00:00"


def test_get_resource_output_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=DATA)
    path = tmp_path / "resource.json"

    result = invoke("resource", "get", RID, "-f", "json", "-o", str(path), "-p", "dev")

    assert result.exit_code == 0, result.output
    assert json.loads(path.read_text()) == fj.sdk_json(DATA)
    assert result.stdout == ""


def test_get_space_is_a_validation_error(stub_foundry_http):
    stub_foundry_http.respond(
        400,
        json=fj.error(
            "GetSpaceResourceNotSupported",
            "INVALID_ARGUMENT",
            {"spaceRid": fj.SPACE_RID},
        ),
    )

    result = invoke("resource", "get", fj.SPACE_RID, "-f", "json")

    assert result.exit_code == 6
    assert json_lines(result.stderr)[-1]["errorName"] == "GetSpaceResourceNotSupported"


def test_get_resource_not_found_text(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("ResourceNotFound", parameters={"resourceRid": RID})
    )

    result = invoke("resource", "get", RID)

    assert result.exit_code == 5
    assert result.stdout == ""
    assert "Error: ResourceNotFound" in result.stderr


def test_get_resource_invalid_rid_is_a_usage_error(stub_foundry_http):
    result = invoke("resource", "get", "not-a-rid", "-f", "json")

    assert result.exit_code == 2
    assert "not a valid RID" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


def test_get_by_path(stub_foundry_http):
    stub_foundry_http.respond(json=DATA)

    result = invoke(
        "resource", "get-by-path", "/Test Space/Test Project/Sales Data", "-f", "json"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["rid"] == RID
    [request] = stub_foundry_http.requests
    assert request.url.path == "/api/v2/filesystem/resources/getByPath"
    assert request.url.params["path"] == "/Test Space/Test Project/Sales Data"


def test_get_by_path_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("PathNotFound", parameters={"path": "/nope"})
    )

    result = invoke("resource", "get-by-path", "/nope", "-f", "json")

    assert result.exit_code == 5
    assert json_lines(result.stderr)[-1]["errorName"] == "PathNotFound"


# -------------------------------------------------------------------- list


def test_list_defaults_to_the_root_folder(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([DATA, SUBFOLDER]))

    result = invoke("resource", "list")

    assert result.exit_code == 0, result.output
    for expected in ("Sales Data", "FOUNDRY_DATASET", "Archive", "COMPASS_FOLDER"):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == children_path("ri.compass.main.folder.0")


def test_list_json_is_the_paged_shape(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([DATA, SUBFOLDER], token="tok-2"))

    result = invoke(
        "resource", "list", "-f", fj.PROJECT_RID, "--format", "json", "--page-size", "2"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [fj.sdk_json(DATA), fj.sdk_json(SUBFOLDER)],
        "nextPageToken": "tok-2",
    }
    [request] = stub_foundry_http.requests
    assert request.url.path == children_path(fj.PROJECT_RID)
    assert dict(request.url.params) == {"pageSize": "2"}


@pytest.mark.parametrize(
    "type_value", ["dataset", "FOUNDRY_DATASET", "foundry_dataset"]
)
def test_list_type_filter(stub_foundry_http, type_value):
    stub_foundry_http.respond(json=fs.page([DATA, SUBFOLDER], token="tok-2"))

    result = invoke(
        "resource",
        "list",
        "--folder-rid",
        fj.PROJECT_RID,
        "-t",
        type_value,
        "--format",
        "csv",
    )

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [row["RID"] for row in rows] == [RID]
    assert "--page-token tok-2" in result.stderr


def test_list_unknown_type_is_a_usage_error(stub_foundry_http):
    result = invoke("resource", "list", "--type", "datset", "--format", "json")

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert "unknown resource type 'datset'" in error["message"]
    assert stub_foundry_http.requests == []


def test_list_all_pages(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([DATA], token="tok-2"))
    stub_foundry_http.respond(json=fs.page([SUBFOLDER]))

    result = invoke(
        "resource", "list", "-f", fj.PROJECT_RID, "--all", "--format", "json"
    )

    assert [item["rid"] for item in json.loads(result.stdout)["data"]] == [
        RID,
        SUBFOLDER["rid"],
    ]
    assert stub_foundry_http.requests[1].url.params["pageToken"] == "tok-2"


def test_list_old_short_format_flag_is_rejected(stub_foundry_http):
    # -o used to mean --format here; it must not silently become --output.
    result = invoke("resource", "list", "-o", "json")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------------ search


def test_search_scans_and_matches(stub_foundry_http):
    nested = fs.child_resource(
        "ri.foundry.main.dataset.nested", "Old sales", parent=SUBFOLDER["rid"]
    )
    stub_foundry_http.respond(json=fs.page([DATA, SUBFOLDER]))
    stub_foundry_http.respond(json=fs.page([nested]))

    result = invoke(
        "resource",
        "search",
        "sales",
        "--folder-rid",
        fj.PROJECT_RID,
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [fj.sdk_json(DATA), fj.sdk_json(nested)]
    }
    assert result.stderr == ""
    assert [request.url.path for request in stub_foundry_http.requests] == [
        children_path(fj.PROJECT_RID),
        children_path(SUBFOLDER["rid"]),
    ]


def test_search_table_and_type_filter(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([DATA, SUBFOLDER]))
    stub_foundry_http.respond(json=fs.page([]))

    result = invoke("resource", "search", "a", "-f", fj.PROJECT_RID, "--type", "folder")

    assert result.exit_code == 0, result.output
    assert "Archive" in result.stdout
    assert "Sales Data" not in result.stdout


def test_search_warns_when_the_folder_limit_stops_it(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([DATA, SUBFOLDER]))

    result = invoke(
        "resource",
        "search",
        "sales",
        "-f",
        fj.PROJECT_RID,
        "--max-folders",
        "1",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": [fj.sdk_json(DATA)]}
    [warning] = json_lines(result.stderr)
    assert warning["type"] == "warning"
    assert "results may be incomplete" in warning["message"]


def test_search_limit_and_deprecated_page_size(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([DATA, SUBFOLDER]))

    result = invoke(
        "resource",
        "search",
        "a",
        "-f",
        fj.PROJECT_RID,
        "--page-size",
        "1",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)["data"]) == 1
    assert "--page-size is deprecated" in json_lines(result.stderr)[0]["message"]
    assert len(stub_foundry_http.requests) == 1


def test_search_empty_query_is_a_usage_error(stub_foundry_http):
    result = invoke("resource", "search", " ", "--format", "json")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_search_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("FolderNotFound", parameters={"folderRid": fj.PROJECT_RID})
    )

    result = invoke("resource", "search", "x", "-f", fj.PROJECT_RID, "--format", "json")

    assert result.exit_code == 5
    assert result.stdout == ""


# --------------------------------------------------------------- batches


def test_batch_get_json_is_the_api_response(stub_foundry_http):
    other = fs.child_resource("ri.foundry.main.dataset.other", "Other")
    stub_foundry_http.respond(json={"data": {RID: DATA, other["rid"]: other}})

    result = invoke("resource", "batch-get", RID, other["rid"], "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": {RID: fj.sdk_json(DATA), other["rid"]: fj.sdk_json(other)}
    }
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert request.url.path == "/api/v2/filesystem/resources/getBatch"
    assert json.loads(request.content) == [
        {"resourceRid": RID},
        {"resourceRid": other["rid"]},
    ]


def test_batch_get_warns_about_missing_rids(stub_foundry_http):
    missing = "ri.foundry.main.dataset.missing"
    stub_foundry_http.respond(json={"data": {RID: DATA}})

    result = invoke("resource", "batch-get", RID, missing, "-f", "csv")

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [row["RID"] for row in rows] == [RID]
    assert f"Not found or not readable: {missing}" in result.stderr


def test_batch_get_rejects_more_than_1000(stub_foundry_http):
    rids = [f"ri.foundry.main.dataset.d{i}" for i in range(1001)]

    result = invoke("resource", "batch-get", *rids, "--format", "json")

    assert result.exit_code == 2
    assert "at most 1000" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


def test_batch_get_by_path(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [DATA]})

    result = invoke(
        "resource",
        "batch-get-by-path",
        "Test Space/Test Project/Sales Data",
        "/nope",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": [fj.sdk_json(DATA)]}
    [warning] = json_lines(result.stderr)
    assert warning == {"type": "warning", "message": "Not found or not readable: /nope"}
    assert json.loads(stub_foundry_http.requests[0].content) == [
        {"path": "Test Space/Test Project/Sales Data"},
        {"path": "/nope"},
    ]


# ------------------------------------------------------------------ trash


def test_delete_refuses_without_yes_when_not_interactive(stub_foundry_http):
    result = invoke("resource", "delete", RID, "--format", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub_foundry_http.requests == []


def test_delete_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("resource", "delete", RID, "-y")

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Moved resource {RID} to the trash" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("DELETE", RESOURCE_PATH)
    assert "preview" not in request.url.params


def test_delete_force_is_a_hidden_deprecated_alias(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("resource", "delete", RID, "--force", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    assert json_lines(result.stderr) == [
        {
            "type": "warning",
            "message": "--force is deprecated and will be removed in a future "
            "release; use --yes.",
        }
    ]
    assert "--force" not in invoke("resource", "delete", "--help").stdout


def test_delete_prompts_when_interactive(stub_foundry_http, interactive):
    stub_foundry_http.respond(204)

    result = invoke("resource", "delete", RID, input="y\n")

    assert result.exit_code == 0, result.output
    assert f"Move resource {RID} to the trash?" in result.stderr
    assert len(stub_foundry_http.requests) == 1


def test_delete_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "DeleteResourcePermissionDenied", "PERMISSION_DENIED", {"resourceRid": RID}
        ),
    )

    result = invoke("resource", "delete", RID, "--yes", "-f", "json")

    assert result.exit_code == 4
    assert (
        json_lines(result.stderr)[-1]["errorName"] == "DeleteResourcePermissionDenied"
    )


def test_restore(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("resource", "restore", RID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{RESOURCE_PATH}/restore")


def test_permanently_delete(stub_foundry_http, interactive):
    stub_foundry_http.respond(204)

    result = invoke("resource", "permanently-delete", RID, input="y\n")

    assert result.exit_code == 0, result.output
    assert "PERMANENTLY delete" in result.stderr
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{RESOURCE_PATH}/permanentlyDelete"


def test_permanently_delete_of_an_untrashed_resource(stub_foundry_http):
    stub_foundry_http.respond(
        400,
        json=fj.error("ResourceNotTrashed", "INVALID_ARGUMENT", {"resourceRid": RID}),
    )

    result = invoke("resource", "permanently-delete", RID, "--yes", "-f", "json")

    assert result.exit_code == 6
    assert json_lines(result.stderr)[-1]["errorName"] == "ResourceNotTrashed"


def test_permanently_delete_answering_no_aborts(stub_foundry_http, interactive):
    result = invoke("resource", "permanently-delete", RID, input="n\n")

    assert result.exit_code == 1
    assert stub_foundry_http.requests == []


# --------------------------------------------------------------- markings


def test_add_markings(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("resource", "add-markings", RID, "-m", fs.MARKING_ID, "-m", "m-2")

    assert result.exit_code == 0, result.output
    assert "Added 2 marking(s)" in result.stderr
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{RESOURCE_PATH}/addMarkings"
    assert json.loads(request.content) == {"markingIds": [fs.MARKING_ID, "m-2"]}


def test_remove_markings_needs_confirmation(stub_foundry_http):
    result = invoke("resource", "remove-markings", RID, "-m", fs.MARKING_ID)

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub_foundry_http.requests == []


def test_remove_markings_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "resource",
        "remove-markings",
        RID,
        "--marking",
        fs.MARKING_ID,
        "--yes",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{RESOURCE_PATH}/removeMarkings"
    assert json.loads(request.content) == {"markingIds": [fs.MARKING_ID]}


def test_list_markings(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([fs.MARKING_ID], token="tok-2"))

    as_json = invoke("resource", "list-markings", RID, "-f", "json")

    assert json.loads(as_json.stdout) == {
        "data": [fs.MARKING_ID],
        "nextPageToken": "tok-2",
    }
    stub_foundry_http.respond(json=fs.page([fs.MARKING_ID]))
    as_csv = invoke("resource", "list-markings", RID, "-f", "csv")
    assert list(csv.DictReader(io.StringIO(as_csv.stdout))) == [
        {"Marking ID": fs.MARKING_ID}
    ]
    assert stub_foundry_http.requests[0].url.path == f"{RESOURCE_PATH}/markings"


def test_access_requirements(stub_foundry_http):
    stub_foundry_http.respond(json=fs.access_requirements())
    stub_foundry_http.respond(json=fs.access_requirements())

    as_json = invoke("resource", "access-requirements", RID, "-f", "json")
    as_csv = invoke("resource", "access-requirements", RID, "-f", "csv")

    assert json.loads(as_json.stdout) == fs.access_requirements()
    rows = list(csv.DictReader(io.StringIO(as_csv.stdout)))
    assert rows == [
        {
            "Requirement": "organization",
            "Organization RID": fj.ORG_A,
            "Marking ID": "org-marking-a",
            "Directly Applied": "false",
        },
        {
            "Requirement": "marking",
            "Organization RID": "",
            "Marking ID": fs.MARKING_ID,
            "Directly Applied": "true",
        },
    ]


def test_access_requirements_none(stub_foundry_http):
    stub_foundry_http.respond(json={"organizations": [], "markings": []})

    result = invoke("resource", "access-requirements", RID)

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "No results." in result.stderr
