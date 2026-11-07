"""Tests for `pltr resource-role` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs

# Every Resource.Role endpoint is GA: a stray preview= would raise a UserWarning.
pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()
RID = fs.DATASET_RID
ROLES_PATH = f"/api/v2/filesystem/resources/{RID}/roles"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


def test_removed_commands_are_gone():
    result = invoke("resource-role", "--help")

    assert result.exit_code == 0
    for removed in ("get-principal-roles", "get-available-roles"):
        assert removed not in result.stdout
    for command in ("grant", "revoke", "list"):
        assert command in result.stdout
    assert invoke("resource-role", "get-available-roles", RID).exit_code == 2


# ------------------------------------------------------------------- grant


def test_grant_role_to_a_user(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "resource-role",
        "grant",
        RID,
        "--principal-id",
        fj.USER_ID,
        "--role",
        "compass:read",
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Granted role 'compass:read' to principal {fj.USER_ID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{ROLES_PATH}/add")
    assert json.loads(request.content) == {
        "roles": [
            {
                "resourceRolePrincipal": {
                    "type": "principalIdOnly",
                    "principalId": fj.USER_ID,
                },
                "roleId": "compass:read",
            }
        ]
    }


def test_grant_role_json_prints_null(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "resource-role",
        "grant",
        RID,
        "-p",
        fj.USER_ID,
        "-r",
        "compass:read",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    assert result.stderr == ""


def test_grant_role_to_everyone(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "resource-role", "grant", RID, "--everyone", "-r", "compass:discover"
    )

    assert result.exit_code == 0, result.output
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["roles"][0]["resourceRolePrincipal"] == {"type": "everyone"}


def test_grant_normalizes_upper_case_ids(stub_foundry_http):
    stub_foundry_http.respond(204)

    invoke(
        "resource-role", "grant", RID, "-p", fj.USER_ID.upper(), "-r", "compass:read"
    )

    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["roles"][0]["resourceRolePrincipal"]["principalId"] == fj.USER_ID


def test_grant_rejects_a_username(stub_foundry_http):
    result = invoke(
        "resource-role", "grant", RID, "-p", "john.doe", "-r", "viewer", "-f", "json"
    )

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert "not a user or group ID" in error["message"]
    assert stub_foundry_http.requests == []


@pytest.mark.parametrize(
    "principal_args, message",
    [
        ([], "--principal-id"),
        (["--principal-id", fj.USER_ID, "--everyone"], "not both"),
    ],
)
def test_grant_needs_exactly_one_principal(stub_foundry_http, principal_args, message):
    result = invoke("resource-role", "grant", RID, "-r", "viewer", *principal_args)

    assert result.exit_code == 2
    assert message in result.stderr
    assert stub_foundry_http.requests == []


def test_grant_principal_type_is_a_deprecated_ignored_option(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "resource-role",
        "grant",
        RID,
        "-p",
        fj.USER_ID,
        "-t",
        "User",
        "-r",
        "compass:read",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    [warning] = json_lines(result.stderr)
    assert warning["type"] == "warning"
    assert "--principal-type is deprecated and ignored" in warning["message"]
    assert "principalType" not in stub_foundry_http.requests[0].content.decode()
    assert "--principal-type" not in invoke("resource-role", "grant", "--help").stdout


def test_grant_profile_has_no_short_flag(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "resource-role",
        "grant",
        RID,
        "-p",
        fj.USER_ID,
        "-r",
        "viewer",
        "--profile",
        "dev",
    )

    assert result.exit_code == 0, result.output


def test_grant_api_validation_error(stub_foundry_http):
    stub_foundry_http.respond(
        400,
        json=fj.error(
            "InvalidRoleIds", "INVALID_ARGUMENT", {"requestedRoleIds": ["viewer"]}
        ),
    )

    result = invoke(
        "resource-role", "grant", RID, "-p", fj.USER_ID, "-r", "viewer", "-f", "json"
    )

    assert result.exit_code == 6
    error = json_lines(result.stderr)[-1]
    assert error["errorName"] == "InvalidRoleIds"
    assert error["type"] == "validation_error"


def test_grant_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "AddResourceRolesPermissionDenied",
            "PERMISSION_DENIED",
            {"resourceRid": RID},
        ),
    )

    result = invoke("resource-role", "grant", RID, "-p", fj.USER_ID, "-r", "viewer")

    assert result.exit_code == 4
    assert "AddResourceRolesPermissionDenied" in result.stderr


# ------------------------------------------------------------------ revoke


def test_revoke_refuses_without_yes_when_not_interactive(stub_foundry_http):
    result = invoke(
        "resource-role", "revoke", RID, "-p", fj.USER_ID, "-r", "viewer", "-f", "json"
    )

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "confirmation_required"
    assert "--yes" in error["message"]
    assert stub_foundry_http.requests == []


def test_revoke_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "resource-role", "revoke", RID, "-p", fj.USER_ID, "-r", "compass:read", "--yes"
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Revoked role 'compass:read'" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{ROLES_PATH}/remove")
    assert json.loads(request.content)["roles"][0]["roleId"] == "compass:read"


def test_revoke_confirm_is_a_deprecated_alias_for_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "resource-role",
        "revoke",
        RID,
        "--everyone",
        "-r",
        "compass:discover",
        "--confirm",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    assert json_lines(result.stderr) == [
        {
            "type": "warning",
            "message": "--confirm is deprecated and will be removed in a future "
            "release; use --yes.",
        }
    ]


def test_revoke_prompts_on_stderr_when_interactive(stub_foundry_http, interactive):
    stub_foundry_http.respond(204)

    result = invoke(
        "resource-role", "revoke", RID, "-p", fj.USER_ID, "-r", "viewer", input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert (
        f"Revoke role 'viewer' from principal {fj.USER_ID} on {RID}?" in result.stderr
    )
    assert result.stdout == ""
    assert len(stub_foundry_http.requests) == 1


def test_revoke_answering_no_aborts(stub_foundry_http, interactive):
    result = invoke(
        "resource-role", "revoke", RID, "-p", fj.USER_ID, "-r", "viewer", input="n\n"
    )

    assert result.exit_code == 1
    assert "Aborted" in result.stderr
    assert stub_foundry_http.requests == []


# -------------------------------------------------------------------- list

ROLES = [fs.user_role(), fs.group_role(), fs.everyone_role()]


def test_list_roles_table(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page(ROLES))

    result = invoke("resource-role", "list", RID)

    assert result.exit_code == 0, result.output
    for expected in (
        "USER",
        fj.USER_ID,
        "compass:read",
        "GROUP",
        fs.GROUP_ID,
        "EVERYONE",
        "compass:discover",
    ):
        assert expected in result.stdout
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", ROLES_PATH)


def test_list_roles_json_is_the_paged_sdk_shape(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page(ROLES, token="tok-2"))

    result = invoke("resource-role", "list", RID, "--format", "json")

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"data": ROLES, "nextPageToken": "tok-2"}
    assert result.stderr == ""


def test_list_roles_csv(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page(ROLES))

    result = invoke("resource-role", "list", RID, "-f", "csv")

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [row["Principal Type"] for row in rows] == ["USER", "GROUP", "EVERYONE"]
    assert rows[0]["Principal ID"] == fj.USER_ID
    assert rows[2]["Principal ID"] == ""
    assert rows[1]["Role ID"] == "compass:edit"


def test_list_roles_principal_type_filters_locally(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page(ROLES, token="tok-2"))

    result = invoke("resource-role", "list", RID, "-t", "Group", "-f", "json")

    assert json.loads(result.stdout) == {"data": [ROLES[1]], "nextPageToken": "tok-2"}
    assert dict(stub_foundry_http.requests[0].url.params) == {}  # not sent


def test_list_roles_include_inherited_and_paging(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([ROLES[0]], token="tok-2"))
    stub_foundry_http.respond(json=fs.page([ROLES[2]]))

    result = invoke(
        "resource-role",
        "list",
        RID,
        "--include-inherited",
        "--page-size",
        "1",
        "--all",
        "-f",
        "json",
    )

    assert json.loads(result.stdout) == {"data": [ROLES[0], ROLES[2]]}
    first, second = stub_foundry_http.requests
    assert dict(first.url.params) == {"includeInherited": "true", "pageSize": "1"}
    assert second.url.params["pageToken"] == "tok-2"


def test_list_roles_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("ResourceNotFound", parameters={"resourceRid": RID})
    )

    result = invoke("resource-role", "list", RID, "-f", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert error["errorName"] == "ResourceNotFound"
    assert error["parameters"] == {"resourceRid": RID}
