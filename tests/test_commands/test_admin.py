"""Tests for `pltr admin` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_admin as aj

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()


def invoke(*args: str, **kwargs):
    return runner.invoke(app, ["admin", *args], **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


def csv_rows(stdout: str) -> list:
    return list(csv.DictReader(io.StringIO(stdout)))


def not_found(name: str, **parameters) -> dict:
    return fj.error(name, "NOT_FOUND", parameters)


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


# ------------------------------------------------------------------- help


def help_line(group: str, command: str) -> str:
    result = invoke(group, "--help")
    return next(line for line in result.stdout.splitlines() if f" {command} " in line)


@pytest.mark.parametrize(
    "group, command",
    [("role", "get"), ("role", "batch-get"), ("org", "create")],
)
def test_beta_commands_are_labeled(group, command):
    assert "[beta]" in help_line(group, command)


@pytest.mark.parametrize(
    "group, command",
    [
        ("user", "list"),
        ("user", "search"),
        ("group", "create"),
        ("org", "get"),
        ("org", "replace"),
        ("org", "available-roles"),
        ("marking", "create"),
        ("marking", "list"),
    ],
)
def test_ga_commands_are_not_labeled_beta(group, command):
    assert "[beta]" not in help_line(group, command)


# ------------------------------------------------------------- user list


def test_user_list_table(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [aj.user(), aj.user(aj.USER_ID_2, "john.roe")]}
    )

    result = invoke("user", "list")

    assert result.exit_code == 0, result.output
    for expected in (aj.USER_ID, "jane.doe", "john.roe", "Jane", "Doe", "ACTIVE"):
        assert expected in result.stdout
    request = stub_foundry_http.requests[0]
    assert (request.method, request.url.path) == ("GET", "/api/v2/admin/users")
    assert dict(request.url.params) == {}


def test_user_list_json_is_the_paged_api_shape(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.user()], "nextPageToken": "t2"})

    result = invoke("user", "list", "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": [aj.user()], "nextPageToken": "t2"}
    assert result.stderr == ""


def test_user_list_csv(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.user()]})

    result = invoke("user", "list", "--format", "csv")

    assert csv_rows(result.stdout) == [
        {
            "ID": aj.USER_ID,
            "Username": "jane.doe",
            "Given Name": "Jane",
            "Family Name": "Doe",
            "Email": "jane.doe@example.com",
            "Status": "ACTIVE",
        }
    ]


def test_user_list_all_pages(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.user()], "nextPageToken": "t2"})
    stub_foundry_http.respond(json={"data": [aj.user(aj.USER_ID_2, "john.roe")]})

    result = invoke("user", "list", "--all", "--page-size", "1", "-f", "json")

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert [user["username"] for user in document["data"]] == ["jane.doe", "john.roe"]
    assert "nextPageToken" not in document
    assert [dict(r.url.params) for r in stub_foundry_http.requests] == [
        {"pageSize": "1"},
        {"pageSize": "1", "pageToken": "t2"},
    ]


def test_user_list_hints_at_the_next_page_on_stderr(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.user()], "nextPageToken": "t2"})

    result = invoke("user", "list")

    assert "--page-token t2" in result.stderr
    assert "t2" not in result.stdout


# --------------------------------------------------------------- user get


def test_user_get_table(stub_foundry_http):
    stub_foundry_http.respond(json=aj.user())

    result = invoke("user", "get", aj.USER_ID)

    assert result.exit_code == 0, result.output
    for expected in (
        aj.USER_ID,
        "jane.doe",
        "jane.doe@example.com",
        aj.ORG_RID,
        aj.REALM,
        "ACTIVE",
        '{"multipass:email:primary":["jane.doe@example.com"]}',
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/admin/users/{aj.USER_ID}"


def test_user_get_json(stub_foundry_http):
    stub_foundry_http.respond(json=aj.user(email=None))

    result = invoke("user", "get", aj.USER_ID, "--format", "json")

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document == {k: v for k, v in aj.user().items() if k != "email"}


def test_user_get_rejects_a_username(stub_foundry_http):
    result = invoke("user", "get", "jane.doe", "--format", "json")

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert "'jane.doe' is not a user ID" in error["message"]
    assert "pltr admin user search" in error["message"]
    assert stub_foundry_http.requests == []


def test_user_get_not_found(stub_foundry_http):
    stub_foundry_http.respond(404, json=not_found("UserNotFound", userId=aj.USER_ID))

    result = invoke("user", "get", aj.USER_ID, "-f", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == ("not_found", "UserNotFound")
    assert error["parameters"] == {"userId": aj.USER_ID}


def test_user_get_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403, json=fj.error("GetUserPermissionDenied", "PERMISSION_DENIED")
    )

    result = invoke("user", "get", aj.USER_ID, "-f", "json")

    assert result.exit_code == 4
    assert json_lines(result.stderr)[-1]["type"] == "permission_denied"


# ----------------------------------------------------------- user current


def test_user_current_json(stub_foundry_http):
    stub_foundry_http.respond(json=aj.user())

    result = invoke("user", "current", "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == aj.user()
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        "/api/v2/admin/users/getCurrent",
    )


def test_user_current_table(stub_foundry_http):
    stub_foundry_http.respond(json=aj.user())

    result = invoke("user", "current")

    assert result.exit_code == 0, result.output
    assert "jane.doe" in result.stdout and aj.USER_ID in result.stdout


def test_user_current_writes_to_a_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=aj.user())
    target = tmp_path / "me.json"

    result = invoke("user", "current", "-f", "json", "-o", str(target))

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert json.loads(target.read_text()) == aj.user()


# ------------------------------------------------------------ user search


def test_user_search_json_and_request(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.user()], "nextPageToken": "t2"})

    result = invoke("user", "search", "jan", "--page-size", "5", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": [aj.user()], "nextPageToken": "t2"}
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/admin/users/search",
    )
    assert json.loads(request.content) == {
        "where": {"type": "queryString", "value": "jan"},
        "pageSize": 5,
    }


def test_user_search_all_pages_passes_the_token_in_the_body(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.user()], "nextPageToken": "t2"})
    stub_foundry_http.respond(json={"data": [aj.user(aj.USER_ID_2, "jane.roe")]})

    result = invoke("user", "search", "jan", "--all", "--format", "csv")

    assert result.exit_code == 0, result.output
    assert [row["Username"] for row in csv_rows(result.stdout)] == [
        "jane.doe",
        "jane.roe",
    ]
    bodies = [json.loads(r.content) for r in stub_foundry_http.requests]
    assert [body.get("pageToken") for body in bodies] == [None, "t2"]


def test_user_search_resumes_from_a_page_token(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    result = invoke("user", "search", "jan", "--page-token", "t2")

    assert result.exit_code == 0, result.output
    assert "No results." in result.stderr
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["pageToken"] == "t2"


# ---------------------------------------------------------- user markings


def test_user_markings_table_lists_marking_ids(stub_foundry_http):
    stub_foundry_http.respond(json={"view": [aj.MARKING_ID, aj.MARKING_ID_2]})

    result = invoke("user", "markings", aj.USER_ID)

    assert result.exit_code == 0, result.output
    assert aj.MARKING_ID in result.stdout and aj.MARKING_ID_2 in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/admin/users/{aj.USER_ID}/getMarkings"


def test_user_markings_json_is_the_api_response(stub_foundry_http):
    stub_foundry_http.respond(json={"view": [aj.MARKING_ID]})

    result = invoke("user", "markings", aj.USER_ID, "-f", "json")

    assert json.loads(result.stdout) == {"view": [aj.MARKING_ID]}


def test_user_markings_csv(stub_foundry_http):
    stub_foundry_http.respond(json={"view": [aj.MARKING_ID, aj.MARKING_ID_2]})

    result = invoke("user", "markings", aj.USER_ID, "-f", "csv")

    assert csv_rows(result.stdout) == [
        {"Marking ID": aj.MARKING_ID},
        {"Marking ID": aj.MARKING_ID_2},
    ]


# ----------------------------------------------------- user revoke-tokens


def test_revoke_tokens_refuses_without_yes_when_not_interactive(stub_foundry_http):
    result = invoke("user", "revoke-tokens", aj.USER_ID, "-f", "json")

    assert result.exit_code == 2
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "confirmation_required"
    assert "--yes" in error["message"]
    assert stub_foundry_http.requests == []


def test_revoke_tokens_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("user", "revoke-tokens", aj.USER_ID, "--yes")

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Revoked all tokens of user {aj.USER_ID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"/api/v2/admin/users/{aj.USER_ID}/revokeAllTokens",
    )


def test_revoke_tokens_json_prints_null(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("user", "revoke-tokens", aj.USER_ID, "-y", "-f", "json")

    assert result.exit_code == 0
    assert json.loads(result.stdout) is None
    assert result.stderr == ""


def test_revoke_tokens_confirm_is_a_deprecated_alias(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("user", "revoke-tokens", aj.USER_ID, "--confirm", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json_lines(result.stderr) == [
        {
            "type": "warning",
            "message": "--confirm is deprecated and will be removed in a future "
            "release; use --yes.",
        }
    ]
    assert len(stub_foundry_http.requests) == 1


def test_revoke_tokens_prompts_on_stderr(stub_foundry_http, interactive):
    stub_foundry_http.respond(204)

    result = invoke("user", "revoke-tokens", aj.USER_ID, input="y\n")

    assert result.exit_code == 0, result.output
    assert "Revoke all tokens and browser sessions" in result.stderr
    assert result.stdout == ""
    assert len(stub_foundry_http.requests) == 1


def test_revoke_tokens_answering_no_aborts(stub_foundry_http, interactive):
    result = invoke("user", "revoke-tokens", aj.USER_ID, input="n\n")

    assert result.exit_code == 1
    assert "Aborted" in result.stderr
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------ user delete


def test_user_delete_refuses_without_yes(stub_foundry_http):
    result = invoke("user", "delete", aj.USER_ID)

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub_foundry_http.requests == []


def test_user_delete_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("user", "delete", aj.USER_ID, "--yes", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "DELETE",
        f"/api/v2/admin/users/{aj.USER_ID}",
    )


def test_user_delete_confirm_alias_and_message(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("user", "delete", aj.USER_ID, "--confirm")

    assert result.exit_code == 0, result.output
    assert "--confirm is deprecated" in result.stderr
    assert f"Deleted user {aj.USER_ID}" in result.stderr


def test_user_delete_answering_no_aborts(stub_foundry_http, interactive):
    result = invoke("user", "delete", aj.USER_ID, input="n\n")

    assert result.exit_code == 1
    assert f"Delete user {aj.USER_ID}?" in result.stderr
    assert stub_foundry_http.requests == []


def test_user_delete_not_found(stub_foundry_http):
    stub_foundry_http.respond(404, json=not_found("UserNotFound", userId=aj.USER_ID))

    result = invoke("user", "delete", aj.USER_ID, "-y", "-f", "json")

    assert result.exit_code == 5
    assert json_lines(result.stderr)[-1]["errorName"] == "UserNotFound"


# --------------------------------------------------------- user batch-get


def test_user_batch_get_json_is_the_api_response(stub_foundry_http):
    body = {
        "data": {
            aj.USER_ID: aj.user(),
            aj.USER_ID_2: aj.user(aj.USER_ID_2, "john.roe"),
        }
    }
    stub_foundry_http.respond(json=body)

    result = invoke("user", "batch-get", aj.USER_ID, aj.USER_ID_2, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == body
    [request] = stub_foundry_http.requests
    assert json.loads(request.content) == [
        {"userId": aj.USER_ID},
        {"userId": aj.USER_ID_2},
    ]


def test_user_batch_get_table(stub_foundry_http):
    stub_foundry_http.respond(json={"data": {aj.USER_ID: aj.user()}})

    result = invoke("user", "batch-get", aj.USER_ID)

    assert result.exit_code == 0, result.output
    assert "jane.doe" in result.stdout


def test_user_batch_get_rejects_more_than_500(stub_foundry_http):
    result = invoke("user", "batch-get", *([aj.USER_ID] * 501), "-f", "json")

    assert result.exit_code == 2
    assert "at most 500 IDs" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


def test_user_batch_get_rejects_a_non_uuid(stub_foundry_http):
    result = invoke("user", "batch-get", aj.USER_ID, "john@example.com")

    assert result.exit_code == 2
    assert "'john@example.com' is not a user ID" in result.stderr
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------------ groups


def test_group_list_json(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.group()], "nextPageToken": "t2"})

    result = invoke("group", "list", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": [aj.group()], "nextPageToken": "t2"}
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", "/api/v2/admin/groups")


def test_group_list_csv(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [aj.group(organizations=[aj.ORG_RID, aj.ORG_RID_2])]}
    )

    result = invoke("group", "list", "-f", "csv")

    assert csv_rows(result.stdout) == [
        {
            "ID": aj.GROUP_ID,
            "Name": "Data Science",
            "Description": "Machine learning team",
            "Organizations": f"{aj.ORG_RID}, {aj.ORG_RID_2}",
        }
    ]


def test_group_get_table(stub_foundry_http):
    stub_foundry_http.respond(json=aj.group())

    result = invoke("group", "get", aj.GROUP_ID)

    assert result.exit_code == 0, result.output
    for expected in (aj.GROUP_ID, "Data Science", aj.ORG_RID, aj.REALM, '"ds"'):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/admin/groups/{aj.GROUP_ID}"


def test_group_get_rejects_a_group_name(stub_foundry_http):
    result = invoke("group", "get", "engineering-team")

    assert result.exit_code == 2
    assert "is not a group ID" in result.stderr
    assert stub_foundry_http.requests == []


def test_group_search(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.group()]})

    result = invoke("group", "search", "data", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": [aj.group()]}
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/admin/groups/search",
    )
    assert json.loads(request.content) == {
        "where": {"type": "queryString", "value": "data"}
    }


def test_group_create(stub_foundry_http):
    stub_foundry_http.respond(json=aj.group())

    result = invoke(
        "group",
        "create",
        "Data Science",
        "--organization",
        aj.ORG_RID,
        "--organization",
        aj.ORG_RID_2,
        "--attribute",
        "team=ds",
        "--attribute",
        "team=ml",
        "--attribute",
        "site=ldn=1",
        "--description",
        "Machine learning team",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == aj.group()
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", "/api/v2/admin/groups")
    assert json.loads(request.content) == {
        "name": "Data Science",
        "organizations": [aj.ORG_RID, aj.ORG_RID_2],
        "attributes": {"team": ["ds", "ml"], "site": ["ldn=1"]},
        "description": "Machine learning team",
    }


def test_group_create_minimal_sends_empty_attributes(stub_foundry_http):
    stub_foundry_http.respond(json=aj.group(attributes={}))

    result = invoke("group", "create", "Data Science", "--organization", aj.ORG_RID)

    assert result.exit_code == 0, result.output
    assert f"Created group 'Data Science' ({aj.GROUP_ID})" in result.stderr
    assert json.loads(stub_foundry_http.requests[0].content) == {
        "name": "Data Science",
        "organizations": [aj.ORG_RID],
        "attributes": {},
    }


def test_group_create_requires_an_organization(stub_foundry_http):
    result = invoke("group", "create", "Data Science", "-f", "json")

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert "--organization" in error["message"]
    assert stub_foundry_http.requests == []


def test_group_create_rejects_a_malformed_attribute(stub_foundry_http):
    result = invoke(
        "group", "create", "X", "--organization", aj.ORG_RID, "--attribute", "team"
    )

    assert result.exit_code == 2
    assert "expected NAME=VALUE" in result.stderr
    assert stub_foundry_http.requests == []


def test_group_create_rejects_an_invalid_organization_rid(stub_foundry_http):
    result = invoke("group", "create", "X", "--organization", "research", "-f", "json")

    assert result.exit_code == 2
    assert "is not a valid RID" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


def test_group_create_org_rid_is_a_deprecated_alias(stub_foundry_http):
    stub_foundry_http.respond(json=aj.group())

    result = invoke("group", "create", "X", "--org-rid", aj.ORG_RID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json_lines(result.stderr) == [
        {
            "type": "warning",
            "message": "--org-rid is deprecated and will be removed in a future "
            "release; use --organization.",
        }
    ]
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["organizations"] == [aj.ORG_RID]


def test_group_create_hides_the_org_rid_alias():
    result = invoke("group", "create", "--help")

    assert "--organization" in result.stdout
    assert "--org-rid" not in result.stdout


def test_group_delete_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("group", "delete", aj.GROUP_ID, "--yes")

    assert result.exit_code == 0, result.output
    assert f"Deleted group {aj.GROUP_ID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "DELETE",
        f"/api/v2/admin/groups/{aj.GROUP_ID}",
    )


def test_group_delete_refuses_without_yes(stub_foundry_http):
    result = invoke("group", "delete", aj.GROUP_ID, "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub_foundry_http.requests == []


def test_group_delete_confirm_alias(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("group", "delete", aj.GROUP_ID, "--confirm")

    assert result.exit_code == 0, result.output
    assert "--confirm is deprecated" in result.stderr


def test_group_batch_get(stub_foundry_http):
    body = {"data": {aj.GROUP_ID: aj.group(), aj.GROUP_ID_2: aj.group(aj.GROUP_ID_2)}}
    stub_foundry_http.respond(json=body)

    result = invoke("group", "batch-get", aj.GROUP_ID, aj.GROUP_ID_2, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == body
    assert json.loads(stub_foundry_http.requests[0].content) == [
        {"groupId": aj.GROUP_ID},
        {"groupId": aj.GROUP_ID_2},
    ]


def test_group_batch_get_csv(stub_foundry_http):
    stub_foundry_http.respond(json={"data": {aj.GROUP_ID: aj.group()}})

    result = invoke("group", "batch-get", aj.GROUP_ID, "-f", "csv")

    assert [row["ID"] for row in csv_rows(result.stdout)] == [aj.GROUP_ID]


# ------------------------------------------------------------------- roles


def test_role_get_uses_preview(stub_foundry_http):
    stub_foundry_http.respond(json=aj.role())

    result = invoke("role", "get", aj.ROLE_ID)

    assert result.exit_code == 0, result.output
    for expected in (
        aj.ROLE_ID,
        "Administrator",
        "organization:edit, organization:manage-members",
        aj.ROLE_ID_2,
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/admin/roles/{aj.ROLE_ID}"
    assert dict(request.url.params) == {"preview": "true"}


def test_role_get_json(stub_foundry_http):
    stub_foundry_http.respond(json=aj.role())

    result = invoke("role", "get", aj.ROLE_ID, "-f", "json")

    assert json.loads(result.stdout) == aj.role()


def test_role_batch_get(stub_foundry_http):
    body = {"data": {aj.ROLE_ID: aj.role(), aj.ROLE_ID_2: aj.role(aj.ROLE_ID_2)}}
    stub_foundry_http.respond(json=body)

    result = invoke("role", "batch-get", aj.ROLE_ID, aj.ROLE_ID_2, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == body
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/admin/roles/getBatch",
    )
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == [
        {"roleId": aj.ROLE_ID},
        {"roleId": aj.ROLE_ID_2},
    ]


def test_role_batch_get_rejects_more_than_500(stub_foundry_http):
    result = invoke("role", "batch-get", *(["r"] * 501))

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


# ----------------------------------------------------------- organizations


def test_org_get_table(stub_foundry_http):
    stub_foundry_http.respond(json=aj.organization())

    result = invoke("org", "get", aj.ORG_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        aj.ORG_RID,
        "Research",
        "Research department",
        "research.example.com",
        aj.ORG_MARKING_ID,
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/admin/organizations/{aj.ORG_RID}"
    assert dict(request.url.params) == {}


def test_org_get_json(stub_foundry_http):
    stub_foundry_http.respond(json=aj.organization())

    result = invoke("org", "get", aj.ORG_RID, "-f", "json")

    assert json.loads(result.stdout) == aj.organization()


def test_org_get_rejects_an_invalid_rid(stub_foundry_http):
    result = invoke("org", "get", "my-organization", "-f", "json")

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert "'my-organization' is not a valid RID" in error["message"]
    assert stub_foundry_http.requests == []


def test_org_create_is_beta_and_sends_administrators(stub_foundry_http):
    stub_foundry_http.respond(json=aj.organization())

    result = invoke(
        "org",
        "create",
        "Research",
        "--enrollment-rid",
        aj.ENROLLMENT_RID,
        "--admin-id",
        aj.USER_ID,
        "--admin-id",
        aj.GROUP_ID,
        "--description",
        "Research department",
        "--host",
        "research.example.com",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == aj.organization()
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/admin/organizations",
    )
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {
        "name": "Research",
        "enrollmentRid": aj.ENROLLMENT_RID,
        "administrators": [aj.USER_ID, aj.GROUP_ID],
        "description": "Research department",
        "host": "research.example.com",
    }


def test_org_create_success_message(stub_foundry_http):
    stub_foundry_http.respond(json=aj.organization())

    result = invoke(
        "org",
        "create",
        "Research",
        "--enrollment-rid",
        aj.ENROLLMENT_RID,
        "--admin-id",
        aj.USER_ID,
    )

    assert result.exit_code == 0, result.output
    assert f"Created organization 'Research' ({aj.ORG_RID})" in result.stderr


def test_org_create_requires_an_administrator(stub_foundry_http):
    result = invoke("org", "create", "Research", "--enrollment-rid", aj.ENROLLMENT_RID)

    assert result.exit_code == 2
    assert "--admin-id" in result.stderr
    assert stub_foundry_http.requests == []


def test_org_create_rejects_a_non_uuid_administrator(stub_foundry_http):
    result = invoke(
        "org",
        "create",
        "Research",
        "--enrollment-rid",
        aj.ENROLLMENT_RID,
        "--admin-id",
        "admin@example.com",
        "-f",
        "json",
    )

    assert result.exit_code == 2
    message = json_lines(result.stderr)[-1]["message"]
    assert "'admin@example.com' is not a user or group ID" in message
    assert stub_foundry_http.requests == []


def test_org_replace_refuses_without_yes(stub_foundry_http):
    result = invoke("org", "replace", aj.ORG_RID, "Lab", "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub_foundry_http.requests == []


def test_org_replace_keeps_the_description_and_host(stub_foundry_http):
    stub_foundry_http.respond(json=aj.organization())
    stub_foundry_http.respond(json=aj.organization(name="Lab"))

    result = invoke("org", "replace", aj.ORG_RID, "Lab", "--yes", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == aj.organization(name="Lab")
    get_request, put_request = stub_foundry_http.requests
    assert get_request.method == "GET"
    assert (put_request.method, put_request.url.path) == (
        "PUT",
        f"/api/v2/admin/organizations/{aj.ORG_RID}",
    )
    assert dict(put_request.url.params) == {}
    assert json.loads(put_request.content) == {
        "name": "Lab",
        "description": "Research department",
        "host": "research.example.com",
    }


def test_org_replace_with_every_field_skips_the_read(stub_foundry_http):
    stub_foundry_http.respond(json=aj.organization(name="Lab"))

    result = invoke(
        "org",
        "replace",
        aj.ORG_RID,
        "Lab",
        "--description",
        "New",
        "--host",
        "lab.example.com",
        "--confirm",
    )

    assert result.exit_code == 0, result.output
    assert "--confirm is deprecated" in result.stderr
    assert f"Replaced organization {aj.ORG_RID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert json.loads(request.content) == {
        "name": "Lab",
        "description": "New",
        "host": "lab.example.com",
    }


def test_org_replace_prompt_names_the_new_name(stub_foundry_http, interactive):
    result = invoke("org", "replace", aj.ORG_RID, "Lab", input="n\n")

    assert result.exit_code == 1
    assert f"Replace organization {aj.ORG_RID} (new name: 'Lab')?" in result.stderr
    assert stub_foundry_http.requests == []


def test_org_available_roles_table(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": [
                aj.organization_role(),
                aj.organization_role(aj.ROLE_ID_2, "Viewer", isDefault=False),
            ]
        }
    )

    result = invoke("org", "available-roles", aj.ORG_RID)

    assert result.exit_code == 0, result.output
    for expected in (aj.ROLE_ID, aj.ROLE_ID_2, "Viewer", aj.ROLE_SET_ID, "false"):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == (
        f"/api/v2/admin/organizations/{aj.ORG_RID}/listAvailableRoles"
    )
    assert dict(request.url.params) == {}


def test_org_available_roles_json_is_the_api_response(stub_foundry_http):
    body = {"data": [aj.organization_role()]}
    stub_foundry_http.respond(json=body)

    result = invoke("org", "available-roles", aj.ORG_RID, "-f", "json")

    assert json.loads(result.stdout) == body


def test_org_available_roles_csv(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.organization_role()]})

    result = invoke("org", "available-roles", aj.ORG_RID, "-f", "csv")

    assert csv_rows(result.stdout) == [
        {
            "ID": aj.ROLE_ID,
            "Name": "Administrator",
            "Role Set": aj.ROLE_SET_ID,
            "Default": "true",
            "Description": "Manages the organization",
        }
    ]


def test_org_available_roles_paging_options_are_deprecated_no_ops(
    stub_foundry_http,
):
    stub_foundry_http.respond(json={"data": [aj.organization_role()]})

    result = invoke(
        "org",
        "available-roles",
        aj.ORG_RID,
        "--page-size",
        "5",
        "--page-token",
        "t",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    warnings = json_lines(result.stderr)
    assert [w["type"] for w in warnings] == ["warning", "warning"]
    assert all("has no effect" in w["message"] for w in warnings)
    assert dict(stub_foundry_http.requests[0].url.params) == {}


def test_org_available_roles_hides_the_paging_options():
    result = invoke("org", "available-roles", "--help")

    assert "--page-size" not in result.stdout
    assert "--page-token" not in result.stdout


# ---------------------------------------------------------------- markings


def test_marking_list_sends_no_filters_by_default(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.marking()]})

    result = invoke("marking", "list")

    assert result.exit_code == 0, result.output
    for expected in (aj.MARKING_ID, "Project X", aj.CATEGORY_ID, "false"):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", "/api/v2/admin/markings")
    assert dict(request.url.params) == {}


@pytest.mark.parametrize(
    "args, params",
    [
        (["--exclude-deleted"], {"includeDeleted": "false"}),
        (["--include-deleted"], {"includeDeleted": "true"}),
        (["--marking-type", "cbac"], {"markingType": "CBAC"}),
        (
            ["--marking-type", "MANDATORY", "--page-size", "100"],
            {"markingType": "MANDATORY", "pageSize": "100"},
        ),
    ],
)
def test_marking_list_filters(stub_foundry_http, args, params):
    stub_foundry_http.respond(json={"data": []})

    result = invoke("marking", "list", *args)

    assert result.exit_code == 0, result.output
    assert dict(stub_foundry_http.requests[0].url.params) == params


def test_marking_list_rejects_an_unknown_type(stub_foundry_http):
    result = invoke("marking", "list", "--marking-type", "SECRET")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_marking_list_json(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.marking()], "nextPageToken": "t2"})

    result = invoke("marking", "list", "-f", "json")

    assert json.loads(result.stdout) == {
        "data": [fj.sdk_json(aj.marking())],
        "nextPageToken": "t2",
    }


def test_marking_list_csv(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.marking()]})

    result = invoke("marking", "list", "-f", "csv")

    assert csv_rows(result.stdout) == [
        {
            "ID": aj.MARKING_ID,
            "Name": "Project X",
            "Category ID": aj.CATEGORY_ID,
            "Deleted": "false",
            "Created": "2024-01-01T00:00:00+00:00",
        }
    ]


def test_marking_get_table(stub_foundry_http):
    stub_foundry_http.respond(json=aj.marking())

    result = invoke("marking", "get", aj.MARKING_ID)

    assert result.exit_code == 0, result.output
    for expected in (
        aj.MARKING_ID,
        "Project X",
        "Data about Project X",
        aj.CATEGORY_ID,
        aj.ORG_RID,
        "COMMON",
        "2024-01-01T00:00:00+00:00",
        aj.USER_ID,
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/admin/markings/{aj.MARKING_ID}"
    assert dict(request.url.params) == {}


def test_marking_get_json(stub_foundry_http):
    stub_foundry_http.respond(json=aj.marking())

    result = invoke("marking", "get", aj.MARKING_ID, "-f", "json")

    assert json.loads(result.stdout) == fj.sdk_json(aj.marking())


def test_marking_get_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=not_found("MarkingNotFound", markingId=aj.MARKING_ID)
    )

    result = invoke("marking", "get", aj.MARKING_ID, "-f", "json")

    assert result.exit_code == 5
    assert json_lines(result.stderr)[-1]["errorName"] == "MarkingNotFound"


def test_marking_batch_get(stub_foundry_http):
    stub_foundry_http.respond(json={"data": {aj.MARKING_ID: aj.marking()}})

    result = invoke("marking", "batch-get", aj.MARKING_ID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": {aj.MARKING_ID: fj.sdk_json(aj.marking())}
    }
    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == [{"markingId": aj.MARKING_ID}]


def test_marking_create(stub_foundry_http):
    stub_foundry_http.respond(json=aj.marking())

    result = invoke(
        "marking",
        "create",
        "Project X",
        "--category-id",
        aj.CATEGORY_ID,
        "--role",
        f"ADMINISTER:{aj.USER_ID}",
        "--role",
        f"use:{aj.GROUP_ID}",
        "--member",
        aj.GROUP_ID,
        "--description",
        "Data about Project X",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == fj.sdk_json(aj.marking())
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", "/api/v2/admin/markings")
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {
        "name": "Project X",
        "categoryId": aj.CATEGORY_ID,
        "initialMembers": [aj.GROUP_ID],
        "initialRoleAssignments": [
            {"role": "ADMINISTER", "principalId": aj.USER_ID},
            {"role": "USE", "principalId": aj.GROUP_ID},
        ],
        "description": "Data about Project X",
    }


def test_marking_create_without_members(stub_foundry_http):
    stub_foundry_http.respond(json=aj.marking())

    result = invoke(
        "marking",
        "create",
        "Project X",
        "--category-id",
        aj.CATEGORY_ID,
        "--role",
        f"ADMINISTER:{aj.USER_ID}",
    )

    assert result.exit_code == 0, result.output
    assert f"Created marking 'Project X' ({aj.MARKING_ID})" in result.stderr
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["initialMembers"] == []


@pytest.mark.parametrize(
    "role, message",
    [
        (f"USE:{aj.USER_ID}", "at least one ADMINISTER role is required"),
        (f"OWNER:{aj.USER_ID}", "expected ROLE:PRINCIPAL_ID"),
        (aj.USER_ID, "expected ROLE:PRINCIPAL_ID"),
        ("ADMINISTER:jane.doe", "'jane.doe' is not a user or group ID"),
    ],
)
def test_marking_create_validates_roles(stub_foundry_http, role, message):
    result = invoke(
        "marking",
        "create",
        "Project X",
        "--category-id",
        aj.CATEGORY_ID,
        "--role",
        role,
        "-f",
        "json",
    )

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert message in error["message"]
    assert stub_foundry_http.requests == []


def test_marking_create_rejects_a_non_uuid_member(stub_foundry_http):
    result = invoke(
        "marking",
        "create",
        "Project X",
        "--category-id",
        aj.CATEGORY_ID,
        "--role",
        f"ADMINISTER:{aj.USER_ID}",
        "--member",
        "data-team",
    )

    assert result.exit_code == 2
    assert "'data-team' is not a user or group ID" in result.stderr
    assert stub_foundry_http.requests == []


def test_marking_create_requires_a_category_and_a_role(stub_foundry_http):
    result = invoke("marking", "create", "Project X")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_marking_create_missing_admin_role_from_the_api(stub_foundry_http):
    stub_foundry_http.respond(
        400,
        json=fj.error("CreateMarkingMissingInitialAdminRole", "INVALID_ARGUMENT"),
    )

    result = invoke(
        "marking",
        "create",
        "Project X",
        "--category-id",
        aj.CATEGORY_ID,
        "--role",
        f"ADMINISTER:{aj.USER_ID}",
        "-f",
        "json",
    )

    assert result.exit_code == 6
    error = json_lines(result.stderr)[-1]
    assert error["errorName"] == "CreateMarkingMissingInitialAdminRole"


def test_marking_replace_keeps_the_description(stub_foundry_http):
    stub_foundry_http.respond(json=aj.marking())
    stub_foundry_http.respond(json=aj.marking(name="Renamed"))

    result = invoke("marking", "replace", aj.MARKING_ID, "Renamed", "--yes")

    assert result.exit_code == 0, result.output
    assert "Renamed" in result.stdout
    assert f"Replaced marking {aj.MARKING_ID}" in result.stderr
    get_request, put_request = stub_foundry_http.requests
    assert get_request.method == "GET"
    assert (put_request.method, put_request.url.path) == (
        "PUT",
        f"/api/v2/admin/markings/{aj.MARKING_ID}",
    )
    assert dict(put_request.url.params) == {}
    assert json.loads(put_request.content) == {
        "name": "Renamed",
        "description": "Data about Project X",
    }


def test_marking_replace_with_description(stub_foundry_http):
    stub_foundry_http.respond(json=aj.marking(name="Renamed", description="New"))

    result = invoke(
        "marking",
        "replace",
        aj.MARKING_ID,
        "Renamed",
        "--description",
        "New",
        "--confirm",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["description"] == "New"
    [request] = stub_foundry_http.requests
    assert json.loads(request.content) == {"name": "Renamed", "description": "New"}


def test_marking_replace_refuses_without_yes(stub_foundry_http):
    result = invoke("marking", "replace", aj.MARKING_ID, "Renamed")

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub_foundry_http.requests == []


def test_marking_replace_prompts_when_interactive(stub_foundry_http, interactive):
    stub_foundry_http.respond(json=aj.marking())
    stub_foundry_http.respond(json=aj.marking(name="Renamed"))

    result = invoke("marking", "replace", aj.MARKING_ID, "Renamed", input="yes\n")

    assert result.exit_code == 0, result.output
    assert f"Replace marking {aj.MARKING_ID} (new name: 'Renamed')?" in result.stderr
    assert len(stub_foundry_http.requests) == 2
