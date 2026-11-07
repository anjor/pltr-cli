"""Tests for `pltr project` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs

# Only Project.replace is beta (it must get preview=true); a stray preview= on
# a GA endpoint would raise a UserWarning, which fails these tests.
pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()
PROJECT_PATH = f"/api/v2/filesystem/projects/{fj.PROJECT_RID}"


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


def test_only_update_is_labeled_beta():
    lines = invoke("project", "--help").stdout.splitlines()
    # The Commands panel's rows (the group's description mentions [beta] too).
    start = next(i for i, line in enumerate(lines) if "─ Commands ─" in line)
    rows = [line.strip("│ ") for line in lines[start + 1 :] if line.startswith("│")]

    update = next(row for row in rows if row.startswith("update "))
    assert "[beta]" in update
    assert sum("[beta]" in row for row in rows) == 1


# ------------------------------------------------------------------ create


def test_create_project_owned_by_the_current_user(stub_foundry_http):
    stub_foundry_http.respond(json=fs.current_user())
    stub_foundry_http.respond(json=fs.project())

    result = invoke("project", "create", "Test Project", "--space-rid", fj.SPACE_RID)

    assert result.exit_code == 0, result.output
    assert fj.PROJECT_RID in result.stdout
    assert "Test Project" in result.stdout
    assert f"Created project 'Test Project' ({fj.PROJECT_RID})" in result.stderr
    user_request, create_request = stub_foundry_http.requests
    assert user_request.url.path == "/api/v2/admin/users/getCurrent"
    body = json.loads(create_request.content)
    assert body["roleGrants"] == {
        "compass:manage": [
            {
                "principalId": fj.USER_ID,
                "principalType": "USER",
                "type": "principalWithId",
            }
        ]
    }


def test_create_project_json_with_every_option(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())

    result = invoke(
        "project",
        "create",
        "Test Project",
        "-s",
        fj.SPACE_RID,
        "-d",
        "About",
        "-org",
        fj.ORG_A,
        "--organization-rid",
        fj.ORG_B,
        "--owner-id",
        fs.GROUP_ID,
        "--owner-type",
        "group",
        "--owner-role",
        "custom:owner",
        "--default-role",
        "compass:read",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == fj.sdk_json(fs.project())
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert json.loads(request.content) == {
        "displayName": "Test Project",
        "description": "About",
        "spaceRid": fj.SPACE_RID,
        "roleGrants": {
            "custom:owner": [
                {
                    "principalId": fs.GROUP_ID,
                    "principalType": "GROUP",
                    "type": "principalWithId",
                }
            ]
        },
        "defaultRoles": ["compass:read"],
        "organizationRids": [fj.ORG_A, fj.ORG_B],
    }


def test_create_project_owner_type_needs_owner_id(stub_foundry_http):
    result = invoke(
        "project", "create", "P", "-s", fj.SPACE_RID, "--owner-type", "GROUP"
    )

    assert result.exit_code == 2
    assert "--owner-type needs --owner-id" in result.stderr
    assert stub_foundry_http.requests == []


def test_create_project_owner_id_must_be_an_id(stub_foundry_http):
    result = invoke(
        "project", "create", "P", "-s", fj.SPACE_RID, "--owner-id", "jdoe", "-f", "json"
    )

    assert result.exit_code == 2
    assert "not a user or group ID" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


def test_create_project_requires_a_space(stub_foundry_http):
    result = invoke("project", "create", "P", "--format", "json")

    assert result.exit_code == 2
    assert "--space-rid" in json_lines(result.stderr)[-1]["message"]


def test_create_project_name_conflict(stub_foundry_http):
    stub_foundry_http.respond(
        409,
        json=fj.error(
            "ProjectNameAlreadyExists",
            "CONFLICT",
            {"displayName": "P", "spaceRid": fj.SPACE_RID},
        ),
    )

    result = invoke(
        "project",
        "create",
        "P",
        "-s",
        fj.SPACE_RID,
        "--owner-id",
        fj.USER_ID,
        "-f",
        "json",
    )

    assert result.exit_code == 7
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == (
        "conflict",
        "ProjectNameAlreadyExists",
    )


# --------------------------------------------------------------------- get


def test_get_project_table(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())

    result = invoke("project", "get", fj.PROJECT_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        fj.PROJECT_RID,
        "Test Project",
        "Test project description",
        "/Test Space/Test Project",
        fj.SPACE_RID,
        "NOT_TRASHED",
        "true",  # resource-level role grants
        "2024-01-01T00:00:00+00:00",
        fj.USER_ID,
    ):
        assert expected in result.stdout
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", PROJECT_PATH)
    assert "preview" not in request.url.params


def test_get_project_json_and_csv(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())
    stub_foundry_http.respond(json=fs.project())

    as_json = invoke("project", "get", fj.PROJECT_RID, "-f", "json")
    as_csv = invoke("project", "get", fj.PROJECT_RID, "-f", "csv", "-p", "dev")

    assert json.loads(as_json.stdout) == fj.sdk_json(fs.project())
    [row] = list(csv.DictReader(io.StringIO(as_csv.stdout)))
    assert row["Space"] == fj.SPACE_RID
    assert row["Updated By"] == fj.USER_ID


def test_get_project_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("ProjectNotFound", parameters={"projectRid": fj.PROJECT_RID})
    )

    result = invoke("project", "get", fj.PROJECT_RID, "-f", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    assert json_lines(result.stderr)[-1]["errorName"] == "ProjectNotFound"


# -------------------------------------------------------------------- list


def test_list_projects_in_a_space(stub_foundry_http):
    folder = fs.child_resource("ri.compass.main.folder.f", "Folder", "COMPASS_FOLDER")
    stub_foundry_http.respond(json=fs.page([fs.project_resource(), folder], token="t2"))

    result = invoke("project", "list", "--space-rid", fj.SPACE_RID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [fj.sdk_json(fs.project_resource())],
        "nextPageToken": "t2",
    }
    [request] = stub_foundry_http.requests
    assert request.url.path == children_path(fj.SPACE_RID)
    assert dict(request.url.params) == {}


def test_list_projects_in_a_space_table_and_paging(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([fs.project_resource()], token="t2"))
    stub_foundry_http.respond(
        json=fs.page([fs.project_resource("ri.compass.main.folder.p2", "Second")])
    )

    result = invoke("project", "list", "-s", fj.SPACE_RID, "--all", "--page-size", "1")

    assert result.exit_code == 0, result.output
    assert "Test Project" in result.stdout and "Second" in result.stdout
    first, second = stub_foundry_http.requests
    assert dict(first.url.params) == {"pageSize": "1"}
    assert dict(second.url.params) == {"pageSize": "1", "pageToken": "t2"}


def test_list_projects_of_every_space(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([fj.space()]))
    stub_foundry_http.respond(json=fs.page([fs.project_resource()]))

    result = invoke("project", "list", "--format", "csv")

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert rows == [
        {
            "Display Name": "Test Project",
            "RID": fj.PROJECT_RID,
            "Space": fj.SPACE_RID,
            "Trash Status": "NOT_TRASHED",
            "Created": "2024-01-01T00:00:00+00:00",
            "Created By": fj.USER_ID,
        }
    ]
    spaces, children = stub_foundry_http.requests
    assert spaces.url.path == "/api/v2/filesystem/spaces"
    assert "preview" not in spaces.url.params
    assert children.url.path == children_path(fj.SPACE_RID)


def test_list_projects_of_every_space_json_has_no_token(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([fj.space()]))
    stub_foundry_http.respond(json=fs.page([fs.project_resource()]))

    result = invoke("project", "list", "-f", "json")

    assert json.loads(result.stdout) == {"data": [fj.sdk_json(fs.project_resource())]}


@pytest.mark.parametrize("extra", [["--page-token", "t2"], ["--max-pages", "3"]])
def test_list_projects_paging_options_need_a_space(stub_foundry_http, extra):
    result = invoke("project", "list", *extra, "-f", "json")

    assert result.exit_code == 2
    assert "need --space-rid" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


def test_list_projects_empty(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([]))

    result = invoke("project", "list", "-s", fj.SPACE_RID)

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "No results." in result.stderr


# ------------------------------------------------------------------ update


def test_update_project_keeps_the_other_field(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())
    stub_foundry_http.respond(json=fs.project(name="Renamed"))

    result = invoke(
        "project", "update", fj.PROJECT_RID, "--name", "Renamed", "-f", "json"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["displayName"] == "Renamed"
    assert result.stderr == ""
    get_request, replace_request = stub_foundry_http.requests
    assert "preview" not in get_request.url.params
    assert (replace_request.method, replace_request.url.params["preview"]) == (
        "PUT",
        "true",
    )
    assert json.loads(replace_request.content) == {
        "displayName": "Renamed",
        "description": "Test project description",
    }


def test_update_project_needs_a_field(stub_foundry_http):
    result = invoke("project", "update", fj.PROJECT_RID, "-f", "json")

    assert result.exit_code == 2
    assert "--name" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------------ delete


def test_delete_project_refuses_without_yes_when_not_interactive(stub_foundry_http):
    result = invoke("project", "delete", fj.PROJECT_RID, "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub_foundry_http.requests == []


def test_delete_project_with_yes_moves_it_to_the_trash(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())
    stub_foundry_http.respond(204)

    result = invoke("project", "delete", fj.PROJECT_RID, "--yes")

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Moved project 'Test Project'" in result.stderr
    assert f"pltr resource restore {fj.PROJECT_RID}" in result.stderr
    get_request, delete_request = stub_foundry_http.requests
    assert (get_request.method, get_request.url.path) == ("GET", PROJECT_PATH)
    assert (delete_request.method, delete_request.url.path) == (
        "DELETE",
        f"/api/v2/filesystem/resources/{fj.PROJECT_RID}",
    )


def test_delete_project_confirm_is_a_deprecated_alias(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())
    stub_foundry_http.respond(204)

    result = invoke("project", "delete", fj.PROJECT_RID, "--confirm", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    assert [line["type"] for line in json_lines(result.stderr)] == ["warning"]


def test_delete_project_prompts_when_interactive(stub_foundry_http, interactive):
    result = invoke("project", "delete", fj.PROJECT_RID, input="n\n")

    assert result.exit_code == 1
    assert f"Move project {fj.PROJECT_RID}" in result.stderr
    assert stub_foundry_http.requests == []


def test_delete_project_of_a_non_project_rid(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("ProjectNotFound", parameters={"projectRid": fs.DATASET_RID})
    )

    result = invoke("project", "delete", fs.DATASET_RID, "--yes", "-f", "json")

    assert result.exit_code == 5
    assert json_lines(result.stderr)[-1]["errorName"] == "ProjectNotFound"
    assert len(stub_foundry_http.requests) == 1  # nothing was trashed


# ---------------------------------------------------------- organizations


def test_add_orgs(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "project", "add-orgs", fj.PROJECT_RID, "-o", fj.ORG_A, "--org", fj.ORG_B
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Added 2 organization(s)" in result.stderr
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{PROJECT_PATH}/addOrganizations"
    assert "preview" not in request.url.params
    assert json.loads(request.content) == {"organizationRids": [fj.ORG_A, fj.ORG_B]}


def test_add_orgs_invalid_hierarchy(stub_foundry_http):
    stub_foundry_http.respond(
        400,
        json=fj.error(
            "InvalidOrganizationHierarchy",
            "INVALID_ARGUMENT",
            {"organizationRids": [fj.ORG_A]},
        ),
    )

    result = invoke("project", "add-orgs", fj.PROJECT_RID, "-o", fj.ORG_A, "-f", "json")

    assert result.exit_code == 6
    assert json_lines(result.stderr)[-1]["errorName"] == "InvalidOrganizationHierarchy"


def test_remove_orgs_needs_confirmation(stub_foundry_http):
    result = invoke("project", "remove-orgs", fj.PROJECT_RID, "-o", fj.ORG_A)

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub_foundry_http.requests == []


def test_remove_orgs_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "project", "remove-orgs", fj.PROJECT_RID, "-o", fj.ORG_A, "-y", "-f", "json"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{PROJECT_PATH}/removeOrganizations"
    assert json.loads(request.content) == {"organizationRids": [fj.ORG_A]}


def test_remove_orgs_prompt_names_the_organizations(stub_foundry_http, interactive):
    stub_foundry_http.respond(204)

    result = invoke(
        "project", "remove-orgs", fj.PROJECT_RID, "-o", fj.ORG_A, input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert f"Remove organization(s) {fj.ORG_A} from project" in result.stderr


def test_list_orgs(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([fj.ORG_A, fj.ORG_B], token="t2"))
    stub_foundry_http.respond(json=fs.page([fj.ORG_A]))

    as_json = invoke("project", "list-orgs", fj.PROJECT_RID, "-f", "json")
    as_table = invoke("project", "list-orgs", fj.PROJECT_RID)

    assert json.loads(as_json.stdout) == {
        "data": [fj.ORG_A, fj.ORG_B],
        "nextPageToken": "t2",
    }
    assert fj.ORG_A in as_table.stdout
    assert stub_foundry_http.requests[0].url.path == f"{PROJECT_PATH}/organizations"


# ---------------------------------------------------------------- template


def test_create_from_template(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())

    result = invoke(
        "project",
        "create-from-template",
        "-t",
        fs.TEMPLATE_RID,
        "-v",
        "name=My Project",
        "--var",
        "team=a=b",
        "-d",
        "About",
        "-o",
        fj.ORG_A,
        "--default-role",
        "compass:read",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["rid"] == fj.PROJECT_RID
    [request] = stub_foundry_http.requests
    assert request.url.path == "/api/v2/filesystem/projects/createFromTemplate"
    assert json.loads(request.content) == {
        "templateRid": fs.TEMPLATE_RID,
        "variableValues": {"name": "My Project", "team": "a=b"},
        "defaultRoles": ["compass:read"],
        "organizationRids": [fj.ORG_A],
        "projectDescription": "About",
    }


def test_create_from_template_without_variables(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=fs.project())
    path = tmp_path / "project.csv"

    result = invoke(
        "project",
        "create-from-template",
        "-t",
        fs.TEMPLATE_RID,
        "-f",
        "csv",
        "--output",
        str(path),
    )

    assert result.exit_code == 0, result.output
    assert json.loads(stub_foundry_http.requests[0].content)["variableValues"] == {}
    assert "Test Project" in path.read_text()


@pytest.mark.parametrize("bad", ["novalue", "=value"])
def test_create_from_template_rejects_bad_variables(stub_foundry_http, bad):
    result = invoke(
        "project",
        "create-from-template",
        "-t",
        fs.TEMPLATE_RID,
        "-v",
        bad,
        "-f",
        "json",
    )

    assert result.exit_code == 2
    assert "name=value" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []
