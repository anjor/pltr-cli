"""Tests for `pltr folder` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from pltr.auth.base import ProfileNotFoundError
from pltr.cli import app
from tests import foundry_json as fj

# Every Folder endpoint is GA: a stray preview= would raise a UserWarning.
pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def json_error(result) -> dict:
    """The structured error: the last stderr line, parsed."""
    return json.loads(result.stderr.strip().splitlines()[-1])


# --------------------------------------------------------------------- get


def test_get_folder_table(stub_foundry_http):
    stub_foundry_http.respond(json=fj.folder())

    result = invoke("folder", "get", fj.FOLDER_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        fj.FOLDER_RID,
        "Test Folder",
        "/Space/Project/Test Folder",
        "2024-01-01T00:00:00+00:00",  # Created
        "2024-01-02T00:00:00+00:00",  # Updated
        fj.USER_ID,
        "NOT_TRASHED",
    ):
        assert expected in result.stdout
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/filesystem/folders/{fj.FOLDER_RID}"


def test_get_folder_json_is_the_sdk_serialization(stub_foundry_http):
    stub_foundry_http.respond(json=fj.folder())

    result = invoke("folder", "get", fj.FOLDER_RID, "--format", "json")

    assert result.exit_code == 0
    assert json.loads(result.stdout) == fj.sdk_json(fj.folder())
    assert result.stderr == ""


def test_get_folder_json_omits_null_fields(stub_foundry_http):
    body = fj.folder()
    del body["description"]
    del body["projectRid"]
    stub_foundry_http.respond(json=body)

    result = invoke("folder", "get", fj.FOLDER_RID, "-f", "json")

    document = json.loads(result.stdout)
    assert "description" not in document and "projectRid" not in document


def test_get_folder_csv(stub_foundry_http):
    stub_foundry_http.respond(json=fj.folder())

    result = invoke("folder", "get", fj.FOLDER_RID, "--format", "csv")

    assert result.exit_code == 0
    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row["RID"] == fj.FOLDER_RID
    assert row["Display Name"] == "Test Folder"
    assert row["Created"] == "2024-01-01T00:00:00+00:00"
    assert row["Created By"] == fj.USER_ID
    assert row["Parent Folder"] == fj.PARENT_RID


def test_pltr_format_env_var_sets_the_default(stub_foundry_http, monkeypatch):
    monkeypatch.setenv("PLTR_FORMAT", "json")
    stub_foundry_http.respond(json=fj.folder())

    result = invoke("folder", "get", fj.FOLDER_RID)

    assert json.loads(result.stdout)["rid"] == fj.FOLDER_RID


def test_get_folder_output_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=fj.folder())
    path = tmp_path / "folder.json"

    result = invoke("folder", "get", fj.FOLDER_RID, "-f", "json", "-o", str(path))

    assert result.exit_code == 0
    assert json.loads(path.read_text()) == fj.sdk_json(fj.folder())
    assert result.stdout == ""
    assert result.stderr == ""  # JSON mode: no informational messages


def test_get_folder_output_file_table_mode_reports_path(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=fj.folder())
    path = tmp_path / "folder.txt"

    result = invoke("folder", "get", fj.FOLDER_RID, "--output", str(path))

    assert result.exit_code == 0
    assert "Test Folder" in path.read_text()
    assert result.stdout == ""
    assert str(path) in result.stderr


def test_get_folder_not_found_json(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("FolderNotFound", parameters={"folderRid": fj.FOLDER_RID})
    )

    result = invoke("folder", "get", fj.FOLDER_RID, "--format", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_error(result)
    assert error["type"] == "not_found"
    assert error["exitCode"] == 5
    assert error["statusCode"] == 404
    assert error["errorName"] == "FolderNotFound"
    assert error["errorInstanceId"] == fj.ERROR_INSTANCE_ID
    assert error["parameters"] == {"folderRid": fj.FOLDER_RID}
    assert "FolderNotFound" in error["message"]


def test_get_folder_not_found_text(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("FolderNotFound", parameters={"folderRid": fj.FOLDER_RID})
    )

    result = invoke("folder", "get", fj.FOLDER_RID)

    assert result.exit_code == 5
    assert result.stdout == ""
    assert "Error: FolderNotFound" in result.stderr
    assert fj.FOLDER_RID in result.stderr
    assert "Hint:" in result.stderr


def test_get_folder_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403, json=fj.error("PermissionDenied", error_code="PERMISSION_DENIED")
    )

    result = invoke("folder", "get", fj.FOLDER_RID, "-f", "json")

    assert result.exit_code == 4
    assert json_error(result)["type"] == "permission_denied"


def test_get_folder_invalid_rid_is_a_usage_error(stub_foundry_http):
    result = invoke("folder", "get", "not-a-rid", "--format", "json")

    assert result.exit_code == 2
    error = json_error(result)
    assert error["type"] == "usage_error"
    assert "not a valid RID" in error["message"]
    assert stub_foundry_http.requests == []


def test_missing_credentials_is_an_auth_error(monkeypatch):
    # Same seam stub_foundry_http uses: the AuthManager services construct.
    auth_manager = Mock()
    auth_manager.return_value.get_client.side_effect = ProfileNotFoundError(
        "No profile configured"
    )
    monkeypatch.setattr("pltr.services.base.AuthManager", auth_manager)

    result = invoke("folder", "get", fj.FOLDER_RID, "--format", "json")

    assert result.exit_code == 3
    error = json_error(result)
    assert error["type"] == "auth_error"
    assert error["message"] == "No profile configured"


# ------------------------------------------------------------------ create


def test_create_folder(stub_foundry_http):
    stub_foundry_http.respond(json=fj.folder())

    result = invoke("folder", "create", "Test Folder", "--parent-folder", fj.PARENT_RID)

    assert result.exit_code == 0, result.output
    assert fj.FOLDER_RID in result.stdout
    assert f"Created folder 'Test Folder' ({fj.FOLDER_RID})" in result.stderr
    [request] = stub_foundry_http.requests
    assert request.method == "POST"
    assert json.loads(request.content) == {
        "displayName": "Test Folder",
        "parentFolderRid": fj.PARENT_RID,
    }


def test_create_folder_json(stub_foundry_http):
    stub_foundry_http.respond(json=fj.folder())

    result = invoke(
        "folder", "create", "Test Folder", "-p", fj.PARENT_RID, "--format", "json"
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["displayName"] == "Test Folder"
    assert result.stderr == ""


def test_create_folder_short_p_is_still_the_parent_folder(stub_foundry_http):
    stub_foundry_http.respond(json=fj.folder())

    result = invoke(
        "folder", "create", "Test Folder", "-p", fj.PARENT_RID, "--profile", "dev"
    )

    assert result.exit_code == 0, result.output
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["parentFolderRid"] == fj.PARENT_RID


def test_get_folder_accepts_short_profile_flag(stub_foundry_http):
    stub_foundry_http.respond(json=fj.folder())
    assert invoke("folder", "get", fj.FOLDER_RID, "-p", "dev").exit_code == 0


def test_create_folder_requires_parent(stub_foundry_http):
    result = invoke("folder", "create", "Test Folder")

    assert result.exit_code == 2
    assert "--parent-folder" in result.stderr
    assert stub_foundry_http.requests == []


def test_create_folder_missing_parent_json(stub_foundry_http):
    result = invoke("folder", "create", "Test Folder", "--format", "json")

    assert result.exit_code == 2
    assert result.stdout == ""
    error = json_error(result)
    assert error["type"] == "usage_error"
    assert "--parent-folder" in error["message"]


# -------------------------------------------------------------------- list


def children_page(*resources, token=None):
    body = {"data": list(resources)}
    if token:
        body["nextPageToken"] = token
    return body


CHILD = fj.resource("ri.compass.main.folder.child", "Child Folder", "COMPASS_FOLDER")
DATASET = fj.resource(
    "ri.foundry.main.dataset.child", "Child Dataset", "FOUNDRY_DATASET"
)


def test_list_children_table(stub_foundry_http):
    stub_foundry_http.respond(json=children_page(CHILD, DATASET))

    result = invoke("folder", "list", fj.PARENT_RID)

    assert result.exit_code == 0
    for expected in ("Child Folder", "COMPASS_FOLDER", "Child Dataset", DATASET["rid"]):
        assert expected in result.stdout
    assert result.stderr == ""  # no more pages, nothing to say


def test_list_children_json_is_the_paged_shape(stub_foundry_http):
    stub_foundry_http.respond(json=children_page(CHILD, DATASET, token="tok-2"))

    result = invoke("folder", "list", fj.PARENT_RID, "--format", "json")

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "data": [fj.sdk_json(CHILD), fj.sdk_json(DATASET)],
        "nextPageToken": "tok-2",
    }
    assert result.stderr == ""
    [request] = stub_foundry_http.requests  # one page by default
    assert "pageToken" not in request.url.params


def test_list_children_table_hints_at_the_next_page(stub_foundry_http):
    stub_foundry_http.respond(json=children_page(CHILD, token="tok-2"))

    result = invoke("folder", "list", fj.PARENT_RID)

    assert "--page-token tok-2" in result.stderr
    assert "tok-2" not in result.stdout


def test_list_children_resume_with_page_token_and_size(stub_foundry_http):
    stub_foundry_http.respond(json=children_page(DATASET))

    result = invoke(
        "folder",
        "list",
        fj.PARENT_RID,
        "--page-token",
        "tok-2",
        "--page-size",
        "5",
        "-f",
        "json",
    )

    assert json.loads(result.stdout) == {"data": [fj.sdk_json(DATASET)]}
    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {"pageSize": "5", "pageToken": "tok-2"}


def test_list_children_all_pages(stub_foundry_http):
    stub_foundry_http.respond(json=children_page(CHILD, token="tok-2"))
    stub_foundry_http.respond(json=children_page(DATASET))

    result = invoke("folder", "list", fj.PARENT_RID, "--all", "-f", "json")

    document = json.loads(result.stdout)
    assert [item["rid"] for item in document["data"]] == [CHILD["rid"], DATASET["rid"]]
    assert "nextPageToken" not in document
    first, second = stub_foundry_http.requests
    assert "pageToken" not in first.url.params
    assert second.url.params["pageToken"] == "tok-2"


def test_list_children_max_pages(stub_foundry_http):
    stub_foundry_http.respond(json=children_page(CHILD, token="tok-2"))
    stub_foundry_http.respond(json=children_page(DATASET, token="tok-3"))

    result = invoke("folder", "list", fj.PARENT_RID, "--max-pages", "2", "-f", "json")

    document = json.loads(result.stdout)
    assert len(document["data"]) == 2
    assert document["nextPageToken"] == "tok-3"
    assert len(stub_foundry_http.requests) == 2


def test_list_children_empty(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})
    stub_foundry_http.respond(json={"data": []})

    as_json = invoke("folder", "list", fj.PARENT_RID, "--format", "json")
    as_table = invoke("folder", "list", fj.PARENT_RID)

    assert json.loads(as_json.stdout) == {"data": []}
    assert as_table.stdout == ""
    assert "No results." in as_table.stderr


def test_list_children_csv(stub_foundry_http):
    stub_foundry_http.respond(json=children_page(CHILD, DATASET))

    result = invoke("folder", "list", fj.PARENT_RID, "--format", "csv")

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [row["Type"] for row in rows] == ["COMPASS_FOLDER", "FOUNDRY_DATASET"]
    assert rows[1]["RID"] == DATASET["rid"]
    assert rows[0]["Updated"] == "2024-01-02T00:00:00+00:00"


# --------------------------------------------------------------- batch-get

OTHER_RID = "ri.compass.main.folder.other"


def test_batch_get_json_is_the_api_response(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": {
                fj.FOLDER_RID: fj.folder(),
                OTHER_RID: fj.folder(OTHER_RID, "Other"),
            }
        }
    )

    result = invoke("folder", "batch-get", fj.FOLDER_RID, OTHER_RID, "-f", "json")

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "data": {
            fj.FOLDER_RID: fj.sdk_json(fj.folder()),
            OTHER_RID: fj.sdk_json(fj.folder(OTHER_RID, "Other")),
        }
    }
    assert json.loads(stub_foundry_http.requests[0].content) == [
        {"folderRid": fj.FOLDER_RID},
        {"folderRid": OTHER_RID},
    ]


def test_batch_get_table_has_one_row_per_folder(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": {
                fj.FOLDER_RID: fj.folder(),
                OTHER_RID: fj.folder(OTHER_RID, "Other"),
            }
        }
    )

    result = invoke("folder", "batch-get", fj.FOLDER_RID, OTHER_RID, "-f", "csv")

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert sorted(row["Display Name"] for row in rows) == ["Other", "Test Folder"]


def test_batch_get_rejects_more_than_1000(stub_foundry_http):
    rids = [f"ri.compass.main.folder.f{i}" for i in range(1001)]

    result = invoke("folder", "batch-get", *rids, "--format", "json")

    assert result.exit_code == 2
    assert "at most 1000" in json_error(result)["message"]
    assert stub_foundry_http.requests == []


# -------------------------------------------------------------------- misc


def test_validation_error_from_the_api(stub_foundry_http):
    stub_foundry_http.respond(
        400,
        json=fj.error("InvalidDisplayName", "INVALID_ARGUMENT", {"displayName": ".."}),
    )

    result = invoke("folder", "create", "..", "-p", fj.PARENT_RID, "-f", "json")

    assert result.exit_code == 6
    error = json_error(result)
    assert error["type"] == "validation_error"
    assert error["errorName"] == "InvalidDisplayName"
    assert error["statusCode"] == 400
