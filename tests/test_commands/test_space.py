"""Tests for `pltr space` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


# ------------------------------------------------------------------- help


def test_beta_commands_are_labeled_in_help():
    lines = invoke("space", "--help").stdout.splitlines()

    def row(command):
        # The command's row in the Commands panel, not an example line in
        # the group's description.
        return next(
            line for line in lines if line.strip("│ ").startswith(f"{command} ")
        )

    for command in ("create", "get", "update", "delete"):
        assert "[beta]" in row(command), row(command)
    assert "[beta]" not in row("list")


# -------------------------------------------------------------------- get


def test_get_space_table(stub_foundry_http):
    stub_foundry_http.respond(json=fj.space(organizations=[fj.ORG_A, fj.ORG_B]))

    result = invoke("space", "get", fj.SPACE_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        fj.SPACE_RID,
        "Test Space",
        "Test description",
        f"{fj.ORG_A}, {fj.ORG_B}",
        "role-set-1",
        fj.USAGE_ACCOUNT_RID,
        "default-fs",
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.params["preview"] == "true"


def test_get_space_json(stub_foundry_http):
    stub_foundry_http.respond(json=fj.space())

    result = invoke("space", "get", fj.SPACE_RID, "--format", "json")

    assert json.loads(result.stdout) == fj.space()
    assert result.stderr == ""


# ------------------------------------------------------------------- list


def test_list_spaces_json(stub_foundry_http):
    second = fj.space("ri.compass.main.folder.space-2", "Second")
    stub_foundry_http.respond(
        json={"data": [fj.space(), second], "nextPageToken": "t2"}
    )

    result = invoke("space", "list", "--format", "json")

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "data": [fj.space(), second],
        "nextPageToken": "t2",
    }
    [request] = stub_foundry_http.requests
    assert request.url.path == "/api/v2/filesystem/spaces"
    assert "preview" not in request.url.params  # GA


def test_list_spaces_csv(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [fj.space(organizations=[fj.ORG_A, fj.ORG_B])]}
    )

    result = invoke("space", "list", "--format", "csv")

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row == {
        "Display Name": "Test Space",
        "RID": fj.SPACE_RID,
        "Path": "/Test Space",
        "Organizations": f"{fj.ORG_A}, {fj.ORG_B}",
    }


def test_list_spaces_all_pages(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fj.space()], "nextPageToken": "t2"})
    stub_foundry_http.respond(json={"data": [fj.space("ri.compass.main.folder.s2")]})

    result = invoke("space", "list", "--all", "--page-size", "1", "-f", "json")

    assert len(json.loads(result.stdout)["data"]) == 2
    assert [dict(r.url.params) for r in stub_foundry_http.requests] == [
        {"pageSize": "1"},
        {"pageSize": "1", "pageToken": "t2"},
    ]


def test_list_spaces_organization_filter_was_removed(stub_foundry_http):
    result = invoke("space", "list", "--organization-rid", fj.ORG_A, "-f", "json")

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert "can't filter spaces by organization" in error["message"]
    assert stub_foundry_http.requests == []


# ----------------------------------------------------------------- create


def test_create_space(stub_foundry_http):
    stub_foundry_http.respond(json=fj.space())

    result = invoke(
        "space",
        "create",
        "Test Space",
        "--enrollment-rid",
        fj.ENROLLMENT_RID,
        "--organization",
        fj.ORG_A,
        "--organization",
        fj.ORG_B,
        "--deletion-policy-org",
        fj.ORG_A,
        "--description",
        "Test description",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["rid"] == fj.SPACE_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.params["preview"]) == ("POST", "true")
    assert json.loads(request.content) == {
        "displayName": "Test Space",
        "enrollmentRid": fj.ENROLLMENT_RID,
        "organizations": [fj.ORG_A, fj.ORG_B],
        "deletionPolicyOrganizations": [fj.ORG_A],
        "description": "Test description",
    }


def test_create_space_short_flags_and_optional_fields(stub_foundry_http):
    stub_foundry_http.respond(json=fj.space())

    result = invoke(
        "space",
        "create",
        "Test Space",
        "-e",
        fj.ENROLLMENT_RID,
        "-org",
        fj.ORG_A,
        "-dpo",
        fj.ORG_A,
        "--default-role-set-id",
        "role-set-2",
        "--file-system-id",
        "fs-2",
        "--usage-account-rid",
        fj.USAGE_ACCOUNT_RID,
    )

    assert result.exit_code == 0, result.output
    assert f"Created space 'Test Space' ({fj.SPACE_RID})" in result.stderr
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["defaultRoleSetId"] == "role-set-2"
    assert body["fileSystemId"] == "fs-2"
    assert body["usageAccountRid"] == fj.USAGE_ACCOUNT_RID


def test_create_space_requires_enrollment_and_organizations(stub_foundry_http):
    result = invoke("space", "create", "Test Space", "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "usage_error"
    assert stub_foundry_http.requests == []


# ----------------------------------------------------------------- update


def test_update_space_keeps_unchanged_fields(stub_foundry_http):
    stub_foundry_http.respond(json=fj.space())
    stub_foundry_http.respond(json=fj.space(name="Renamed"))

    result = invoke("space", "update", fj.SPACE_RID, "--name", "Renamed", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["displayName"] == "Renamed"
    get_request, put_request = stub_foundry_http.requests
    assert get_request.method == "GET"
    assert put_request.method == "PUT"
    assert json.loads(put_request.content) == {
        "displayName": "Renamed",
        "description": "Test description",
        "defaultRoleSetId": "role-set-1",
        "usageAccountRid": fj.USAGE_ACCOUNT_RID,
    }


def test_update_space_requires_a_field(stub_foundry_http):
    result = invoke("space", "update", fj.SPACE_RID)

    assert result.exit_code == 2
    assert "pass at least one of --name" in result.stderr
    assert stub_foundry_http.requests == []


# ----------------------------------------------------------------- delete


def test_delete_space_refuses_without_yes_when_not_interactive(stub_foundry_http):
    result = invoke("space", "delete", fj.SPACE_RID, "--format", "json")

    assert result.exit_code == 2
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "confirmation_required"
    assert "--yes" in error["message"]
    assert stub_foundry_http.requests == []


def test_delete_space_refusal_in_text_mode(stub_foundry_http):
    result = invoke("space", "delete", fj.SPACE_RID)

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub_foundry_http.requests == []


def test_delete_space_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("space", "delete", fj.SPACE_RID, "--yes")

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Deleted space {fj.SPACE_RID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.params["preview"]) == ("DELETE", "true")


def test_delete_space_json_prints_null(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("space", "delete", fj.SPACE_RID, "-y", "-f", "json")

    assert result.exit_code == 0
    assert json.loads(result.stdout) is None
    assert result.stderr == ""


def test_delete_space_confirm_is_a_deprecated_alias_for_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("space", "delete", fj.SPACE_RID, "--confirm", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json_lines(result.stderr) == [
        {
            "type": "warning",
            "message": "--confirm is deprecated and will be removed in a future "
            "release; use --yes.",
        }
    ]
    assert len(stub_foundry_http.requests) == 1


def test_delete_space_prompts_on_stderr_when_interactive(
    stub_foundry_http, interactive
):
    stub_foundry_http.respond(204)

    result = invoke("space", "delete", fj.SPACE_RID, input="y\n")

    assert result.exit_code == 0, result.output
    assert f"Delete space {fj.SPACE_RID}" in result.stderr
    assert result.stdout == ""  # the prompt never touches stdout
    assert len(stub_foundry_http.requests) == 1


def test_delete_space_answering_no_aborts(stub_foundry_http, interactive):
    result = invoke("space", "delete", fj.SPACE_RID, input="n\n")

    assert result.exit_code == 1
    assert "Aborted" in result.stderr
    assert stub_foundry_http.requests == []


def test_delete_space_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("SpaceNotFound", parameters={"spaceRid": fj.SPACE_RID})
    )

    result = invoke("space", "delete", fj.SPACE_RID, "--yes", "-f", "json")

    assert result.exit_code == 5
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == ("not_found", "SpaceNotFound")
