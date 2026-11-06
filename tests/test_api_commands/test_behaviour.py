"""Behaviour of generated `pltr api` commands: paging, beta, destructive, binary, errors."""

import json
from typing import Any, List

import pytest
from foundry_sdk._core import utils as sdk_utils
from foundry_sdk.v2.admin.cbac_banner import CbacBannerClient
from foundry_sdk.v2.admin.user import UserClient

from pltr.commands.api import _adapter

USER_ID = "f05f8da4-b84c-4fca-9c77-8af0b13d11de"
OTHER_USER_ID = "0d4b1b8e-5e43-4d1f-9a7f-6b8c2f3e1a90"
DATASET_RID = "ri.foundry.main.dataset.c26f11c8-cdb3-4f44-9f5d-9816ea1c82da"
TRANSACTION_RID = "ri.foundry.main.transaction.0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
ATTACHMENT_RID = "ri.attachments.main.attachment.5d4c3b2a-1f0e-4d9c-8b7a-6f5e4d3c2b1a"
BANNER = {
    "classificationString": "UNCLASSIFIED",
    "markings": [],
    "textColor": "#000000",
    "backgroundColors": ["#FFFFFF"],
}


def user(user_id: str, username: str) -> dict:
    return {
        "id": user_id,
        "username": username,
        "realm": "palantir-internal-realm",
        "status": "ACTIVE",
        "attributes": {},
    }


def stderr_json(result) -> Any:
    """The structured error: the last non-empty stderr line, parsed."""
    lines: List[str] = [line for line in result.stderr.splitlines() if line.strip()]
    assert lines, "expected a JSON error on stderr"
    return json.loads(lines[-1])


# ---------------------------------------------------------------------------
# Paging
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("error::UserWarning")
def test_paged_command_prints_one_page_with_next_page_token(api_stub, pltr_api):
    page = {"data": [user(USER_ID, "jdoe")], "nextPageToken": "page-2"}
    api_stub.respond(200, json=page)

    result = pltr_api("admin", "user", "list", "--page-size", "1", "--format", "json")

    assert result.exit_code == 0, result.output
    (request,) = api_stub.requests
    assert request.method == "GET"
    assert request.url.path == "/api/v2/admin/users"
    assert dict(request.url.params) == {"pageSize": "1"}
    assert json.loads(result.stdout) == page
    # In JSON mode informational stderr output is suppressed.
    assert result.stderr == ""


@pytest.mark.filterwarnings("error::UserWarning")
def test_paged_command_resumes_from_page_token(api_stub, pltr_api):
    api_stub.respond(200, json={"data": [user(OTHER_USER_ID, "asmith")]})

    result = pltr_api(
        "admin", "user", "list", "--page-token", "page-2", "--format", "json"
    )

    assert result.exit_code == 0, result.output
    assert dict(api_stub.requests[0].url.params) == {"pageToken": "page-2"}
    assert json.loads(result.stdout) == {"data": [user(OTHER_USER_ID, "asmith")]}


@pytest.mark.filterwarnings("error::UserWarning")
def test_paged_command_all_fetches_every_page(api_stub, pltr_api):
    api_stub.respond(200, json={"data": [user(USER_ID, "jdoe")], "nextPageToken": "p2"})
    api_stub.respond(200, json={"data": [user(OTHER_USER_ID, "asmith")]})

    result = pltr_api(
        "admin", "user", "list", "--all", "--page-size", "1", "--format", "json"
    )

    assert result.exit_code == 0, result.output
    first, second = api_stub.requests
    assert dict(first.url.params) == {"pageSize": "1"}
    assert dict(second.url.params) == {"pageSize": "1", "pageToken": "p2"}
    assert json.loads(result.stdout) == {
        "data": [user(USER_ID, "jdoe"), user(OTHER_USER_ID, "asmith")]
    }


@pytest.mark.filterwarnings("error::UserWarning")
def test_response_paged_command_keeps_extra_fields_and_pages_body(api_stub, pltr_api):
    """User.search returns a response model (not an iterator) and pages in the body."""
    page = {"data": [user(USER_ID, "jdoe")], "nextPageToken": "next"}
    api_stub.respond(200, json=page)
    api_stub.respond(200, json={"data": []})

    where = '{"type": "queryString", "value": "jd"}'
    result = pltr_api(
        "admin", "user", "search", "--where", where, "--all", "--format", "json"
    )

    assert result.exit_code == 0, result.output
    first, second = api_stub.requests
    assert first.url.path == "/api/v2/admin/users/search"
    assert json.loads(first.content) == {
        "where": {"type": "queryString", "value": "jd"}
    }
    assert json.loads(second.content) == {
        "where": {"type": "queryString", "value": "jd"},
        "pageToken": "next",
    }
    assert json.loads(result.stdout) == {"data": [user(USER_ID, "jdoe")]}


def test_paged_table_output_lists_rows_and_hints_next_page(api_stub, pltr_api):
    api_stub.respond(
        200,
        json={
            "data": [user(USER_ID, "jdoe"), user(OTHER_USER_ID, "asmith")],
            "nextPageToken": "page-2",
        },
    )

    result = pltr_api("admin", "user", "list")

    assert result.exit_code == 0, result.output
    assert "username" in result.stdout
    assert "jdoe" in result.stdout and "asmith" in result.stdout
    assert "--page-token page-2" in result.stderr
    assert "page-2" not in result.stdout


def test_csv_output(api_stub, pltr_api):
    api_stub.respond(200, json={"data": [user(USER_ID, "jdoe")]})

    result = pltr_api("admin", "user", "list", "--format", "csv")

    assert result.exit_code == 0, result.output
    header, row = result.stdout.strip().splitlines()
    assert header == "id,username,realm,status,attributes"
    assert row == f"{USER_ID},jdoe,palantir-internal-realm,ACTIVE,{{}}"


def test_pltr_format_environment_variable_selects_json(api_stub, pltr_api):
    api_stub.respond(200, json=user(USER_ID, "jdoe"))

    result = pltr_api("admin", "user", "get", USER_ID, env={"PLTR_FORMAT": "json"})

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == user(USER_ID, "jdoe")


def test_output_option_writes_file(api_stub, pltr_api, tmp_path):
    api_stub.respond(200, json=user(USER_ID, "jdoe"))
    target = tmp_path / "user.json"

    result = pltr_api(
        "admin", "user", "get", USER_ID, "--format", "json", "-o", str(target)
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert json.loads(target.read_text()) == user(USER_ID, "jdoe")


def test_profile_is_passed_to_auth_manager(api_stub, pltr_api):
    api_stub.respond(200, json=user(USER_ID, "jdoe"))

    result = pltr_api("admin", "user", "get", USER_ID, "--profile", "prod")

    assert result.exit_code == 0, result.output
    api_stub.auth_manager.return_value.get_client.assert_called_once_with("prod")


# ---------------------------------------------------------------------------
# Beta
# ---------------------------------------------------------------------------


def test_beta_command_is_labeled_in_help(pltr_api):
    result = pltr_api("admin", "cbac-banner", "--help")
    assert result.exit_code == 0
    assert "[beta] Returns a combined CBAC banner" in result.stdout

    result = pltr_api("admin", "cbac-banner", "get-for-resources", "--help")
    assert result.stdout.split("\n\n")[1].strip().startswith("[beta] ")


def test_ga_command_is_not_labeled_beta(pltr_api):
    result = pltr_api("admin", "cbac-banner", "get", "--help")
    assert result.exit_code == 0
    assert "[beta]" not in result.stdout


@pytest.mark.filterwarnings("error::UserWarning")
def test_beta_command_sends_preview(api_stub, pltr_api):
    api_stub.respond(200, json=BANNER)

    result = pltr_api(
        "admin",
        "cbac-banner",
        "get-for-resources",
        "--resource-rids",
        DATASET_RID,
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    (request,) = api_stub.requests
    assert request.method == "POST"
    assert request.url.path == "/api/v2/admin/cbacBanner/getForResources"
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {"resourceRids": [DATASET_RID]}
    assert json.loads(result.stdout) == BANNER


@pytest.mark.filterwarnings("error::UserWarning")
def test_beta_command_against_sdk_where_method_is_ga(api_stub, pltr_api, monkeypatch):
    """A newer SDK may promote a beta method to GA (no `preview` parameter).

    The generated command must then not pass `preview`, which would make the SDK
    warn (an error here) and is no longer needed.
    """
    beta_method = CbacBannerClient.get_for_resources

    def get_for_resources(
        self,
        *,
        resource_rids,
        display_type=None,
        request_timeout=None,
        _sdk_internal={},
    ):
        return beta_method(
            self,
            resource_rids=resource_rids,
            display_type=display_type,
            request_timeout=request_timeout,
            _sdk_internal=_sdk_internal,
        )

    ga_method = sdk_utils.maybe_ignore_preview(get_for_resources)
    monkeypatch.setattr(CbacBannerClient, "get_for_resources", ga_method)
    api_stub.respond(200, json=BANNER)

    result = pltr_api(
        "admin",
        "cbac-banner",
        "get-for-resources",
        "--resource-rids",
        DATASET_RID,
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    (request,) = api_stub.requests
    assert "preview" not in request.url.params
    assert json.loads(result.stdout) == BANNER


def test_missing_sdk_method_fails_clearly(api_stub, pltr_api, monkeypatch):
    monkeypatch.delattr(UserClient, "get_markings")

    result = pltr_api("admin", "user", "get-markings", USER_ID, "--format", "json")

    assert result.exit_code == 1
    assert api_stub.requests == []
    error = stderr_json(result)
    assert error["type"] == "sdk_unavailable"
    assert error["exitCode"] == 1
    assert "FoundryClient.admin.User.get_markings" in error["message"]
    assert "not available in foundry-platform-sdk" in error["message"]


def test_missing_sdk_method_message_in_table_mode(api_stub, pltr_api, monkeypatch):
    monkeypatch.delattr(UserClient, "get_markings")

    result = pltr_api("admin", "user", "get-markings", USER_ID)

    assert result.exit_code == 1
    assert "not available in foundry-platform-sdk" in result.stderr
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# Destructive
# ---------------------------------------------------------------------------


def test_destructive_command_without_yes_fails_when_stdin_is_not_a_terminal(
    api_stub, pltr_api
):
    result = pltr_api("admin", "user", "delete", USER_ID, "--format", "json")

    assert result.exit_code == 2
    assert api_stub.requests == []
    error = stderr_json(result)
    assert error["type"] == "usage_error"
    assert "--yes" in error["message"]
    assert result.stdout == ""


@pytest.mark.filterwarnings("error::UserWarning")
def test_destructive_command_with_yes(api_stub, pltr_api):
    api_stub.respond(204)

    result = pltr_api("admin", "user", "delete", USER_ID, "-y", "--format", "json")

    assert result.exit_code == 0, result.output
    (request,) = api_stub.requests
    assert request.method == "DELETE"
    assert request.url.path == f"/api/v2/admin/users/{USER_ID}"
    assert dict(request.url.params) == {}
    assert json.loads(result.stdout) is None


def test_destructive_command_prompts_on_a_terminal(api_stub, pltr_api, monkeypatch):
    monkeypatch.setattr(_adapter, "stdin_is_terminal", lambda: True)

    declined = pltr_api("admin", "user", "delete", USER_ID, input="n\n")

    assert declined.exit_code == 1
    assert api_stub.requests == []
    assert f"DELETE /v2/admin/users/{USER_ID}" in declined.stderr
    # CliRunner echoes the typed answer to stdout, as a terminal would show it.
    assert declined.stdout.strip() == "n"

    api_stub.respond(204)
    accepted = pltr_api("admin", "user", "delete", USER_ID, input="y\n")

    assert accepted.exit_code == 0, accepted.output
    assert [r.method for r in api_stub.requests] == ["DELETE"]
    assert accepted.stdout.strip() == "y"


def test_reviewed_destructive_methods_need_yes(api_stub, pltr_api):
    """Methods whose names don't say so are still confirmed (e.g. Stream.reset)."""
    result = pltr_api("streams", "dataset", "stream", "reset", DATASET_RID, "master")

    assert result.exit_code == 2
    assert api_stub.requests == []
    assert "--yes" in result.stderr


# ---------------------------------------------------------------------------
# Binary responses and bodies
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("error::UserWarning")
def test_binary_response_goes_to_stdout_when_not_a_terminal(api_stub, pltr_api):
    payload = b"\x89PNG\r\n\x1a\n\x00binary"
    api_stub.respond(200, content=payload)

    result = pltr_api("datasets", "dataset", "file", "content", DATASET_RID, "a/b.png")

    assert result.exit_code == 0, result.output
    (request,) = api_stub.requests
    assert request.method == "GET"
    assert request.url.path == f"/api/v2/datasets/{DATASET_RID}/files/a/b.png/content"
    assert request.headers["accept"] == "application/octet-stream"
    assert result.stdout_bytes == payload


@pytest.mark.filterwarnings("error::UserWarning")
def test_binary_response_to_output_file(api_stub, pltr_api, tmp_path):
    payload = bytes(range(256)) * 10
    api_stub.respond(200, content=payload)
    target = tmp_path / "out.bin"

    result = pltr_api(
        "datasets",
        "dataset",
        "file",
        "content",
        DATASET_RID,
        "data.bin",
        "--branch-name",
        "dev",
        "--output-file",
        str(target),
    )

    assert result.exit_code == 0, result.output
    assert dict(api_stub.requests[0].url.params) == {"branchName": "dev"}
    assert target.read_bytes() == payload
    assert result.stdout == ""
    assert f"Wrote {len(payload)} bytes" in result.stderr


def test_binary_response_refuses_a_terminal(api_stub, pltr_api, monkeypatch):
    monkeypatch.setattr(_adapter, "stdout_is_terminal", lambda: True)

    result = pltr_api("datasets", "dataset", "file", "content", DATASET_RID, "x.bin")

    assert result.exit_code == 2
    assert api_stub.requests == []
    assert "--output-file" in result.stderr


def test_binary_error_leaves_no_file(api_stub, pltr_api, tmp_path):
    api_stub.respond(
        404,
        json={
            "errorCode": "NOT_FOUND",
            "errorName": "FileNotFound",
            "errorInstanceId": "0c1f2e3d-0000-4000-8000-000000000000",
            "parameters": {"datasetRid": DATASET_RID, "filePath": "x.bin"},
        },
    )
    target = tmp_path / "out.bin"

    result = pltr_api(
        "datasets",
        "dataset",
        "file",
        "content",
        DATASET_RID,
        "x.bin",
        "-o",
        str(target),
        "--format",
        "json",
    )

    assert result.exit_code == 5
    assert not target.exists()
    assert stderr_json(result)["errorName"] == "FileNotFound"


@pytest.mark.filterwarnings("error::UserWarning")
def test_bytes_body_is_read_from_a_file(api_stub, pltr_api, tmp_path):
    source = tmp_path / "flights.csv"
    source.write_bytes(b"id,origin\n1,SFO\n")
    file_json = {
        "path": "raw/flights.csv",
        "transactionRid": TRANSACTION_RID,
        "sizeBytes": "16",
        "updatedTime": "2026-01-01T10:00:00+00:00",
    }
    api_stub.respond(200, json=file_json)

    result = pltr_api(
        "datasets",
        "dataset",
        "file",
        "upload",
        DATASET_RID,
        "raw/flights.csv",
        "--body",
        str(source),
        "--transaction-type",
        "APPEND",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    (request,) = api_stub.requests
    assert request.method == "POST"
    assert (
        request.url.path
        == f"/api/v2/datasets/{DATASET_RID}/files/raw/flights.csv/upload"
    )
    assert dict(request.url.params) == {"transactionType": "APPEND"}
    assert request.headers["content-type"] == "application/octet-stream"
    assert request.content == b"id,origin\n1,SFO\n"
    assert json.loads(result.stdout) == file_json


@pytest.mark.filterwarnings("error::UserWarning")
def test_bytes_body_from_stdin_and_content_length_defaults_to_its_size(
    api_stub, pltr_api
):
    attachment = {
        "rid": ATTACHMENT_RID,
        "filename": "notes.txt",
        "sizeBytes": "5",
        "mediaType": "text/plain",
    }
    api_stub.respond(200, json=attachment)

    result = pltr_api(
        "ontologies",
        "attachment",
        "upload",
        "--body",
        "-",
        "--content-type",
        "text/plain",
        "--filename",
        "notes.txt",
        "--format",
        "json",
        input=b"hello",
    )

    assert result.exit_code == 0, result.output
    (request,) = api_stub.requests
    assert request.url.path == "/api/v2/ontologies/attachments/upload"
    assert dict(request.url.params) == {"filename": "notes.txt"}
    assert request.headers["content-length"] == "5"
    assert request.content == b"hello"
    # The SDK's serialization includes AttachmentV2's default `type`.
    assert json.loads(result.stdout) == {**attachment, "type": "single"}


# ---------------------------------------------------------------------------
# Inputs and errors
# ---------------------------------------------------------------------------


def test_json_option_accepts_a_file(api_stub, pltr_api, tmp_path):
    where = tmp_path / "where.json"
    where.write_text('{"type": "queryString", "value": "jd"}')
    api_stub.respond(200, json={"data": []})

    result = pltr_api(
        "admin", "user", "search", "--where", f"@{where}", "--format", "json"
    )

    assert result.exit_code == 0, result.output
    body = json.loads(api_stub.requests[0].content)
    assert body == {"where": {"type": "queryString", "value": "jd"}}


def test_invalid_json_input_is_a_usage_error(api_stub, pltr_api):
    result = pltr_api(
        "admin", "user", "search", "--where", "{not json", "--format", "json"
    )

    assert result.exit_code == 2
    assert api_stub.requests == []
    error = stderr_json(result)
    assert error["type"] == "usage_error"
    assert "--where" in error["message"]


def test_sdk_validation_of_arguments_is_a_usage_error(api_stub, pltr_api):
    """The SDK validates IDs before sending anything (a user id is a UUID)."""
    result = pltr_api("admin", "user", "get", "not-a-uuid", "--format", "json")

    assert result.exit_code == 2
    assert api_stub.requests == []
    assert stderr_json(result)["type"] == "usage_error"


def test_click_usage_error_in_json_mode_is_structured(api_stub, pltr_api):
    result = pltr_api("admin", "user", "get", "--format", "json")

    assert result.exit_code == 2
    error = stderr_json(result)
    assert error == {
        "type": "usage_error",
        "message": error["message"],
        "exitCode": 2,
    }
    assert "USER_ID" in error["message"]


def test_unknown_command_in_json_mode_is_structured(pltr_api):
    result = pltr_api("admin", "user", "frobnicate", env={"PLTR_FORMAT": "json"})

    assert result.exit_code == 2
    assert stderr_json(result)["type"] == "usage_error"


@pytest.mark.parametrize(
    "status, error_code, error_name, exit_code, error_type",
    [
        (400, "INVALID_ARGUMENT", "InvalidUserStatus", 6, "validation_error"),
        (401, "UNAUTHORIZED", "MissingCredentials", 3, "authentication_error"),
        (403, "PERMISSION_DENIED", "GetUserPermissionDenied", 4, "permission_denied"),
        (404, "NOT_FOUND", "UserNotFound", 5, "not_found"),
        (409, "CONFLICT", "SomethingConflicted", 7, "api_error"),
        (422, "INVALID_ARGUMENT", "Unprocessable", 6, "validation_error"),
        (500, "INTERNAL", "Default:Internal", 7, "api_error"),
    ],
)
def test_api_errors_map_to_exit_codes(
    api_stub, pltr_api, status, error_code, error_name, exit_code, error_type
):
    api_stub.respond(
        status,
        json={
            "errorCode": error_code,
            "errorName": error_name,
            "errorInstanceId": "8a5e2f1c-0000-4000-8000-000000000000",
            "parameters": {"userId": USER_ID},
        },
    )

    result = pltr_api("admin", "user", "get", USER_ID, "--format", "json")

    assert result.exit_code == exit_code
    assert result.stdout == ""
    error = stderr_json(result)
    assert error["type"] == error_type
    assert error["exitCode"] == exit_code
    assert error["errorName"] == error_name
    assert error["errorInstanceId"] == "8a5e2f1c-0000-4000-8000-000000000000"
    assert error["parameters"] == {"userId": USER_ID}
    if status != 500:
        assert error["statusCode"] == status


def test_rate_limit_and_network_errors_map_to_exit_code_7():
    # The SDK retries 429/503 itself, so check the mapping of what it finally raises.
    from foundry_sdk import ConnectionError, RateLimitError, ReadTimeout

    rate_limited = _adapter.describe_error(
        RateLimitError("slow down", reason="client-qos-response")
    )
    assert rate_limited["exitCode"] == 7
    assert rate_limited["statusCode"] == 429
    assert _adapter.describe_error(ReadTimeout("timed out"))["exitCode"] == 7
    assert _adapter.describe_error(ConnectionError("refused"))["exitCode"] == 7


def test_wrapped_errors_are_classified_by_their_cause():
    from foundry_sdk import PermissionDeniedError

    try:
        try:
            raise PermissionDeniedError({"errorName": "Denied", "parameters": {}})
        except PermissionDeniedError as exc:
            raise RuntimeError("service failed") from exc
    except RuntimeError as wrapped:
        details = _adapter.describe_error(wrapped)
    assert details["exitCode"] == 4
    assert details["errorName"] == "Denied"


def test_auth_errors_exit_3(api_stub, pltr_api):
    from pltr.auth.base import ProfileNotFoundError

    api_stub.auth_manager.return_value.get_client.side_effect = ProfileNotFoundError(
        "Profile 'nope' not found."
    )

    result = pltr_api("admin", "user", "get", USER_ID, "--profile", "nope")

    assert result.exit_code == 3
    assert "Profile 'nope' not found." in result.stderr


def test_error_in_table_mode_is_readable(api_stub, pltr_api):
    api_stub.respond(
        404,
        json={
            "errorCode": "NOT_FOUND",
            "errorName": "UserNotFound",
            "errorInstanceId": "8a5e2f1c-0000-4000-8000-000000000000",
            "parameters": {"userId": USER_ID},
        },
    )

    result = pltr_api("admin", "user", "get", USER_ID)

    assert result.exit_code == 5
    assert "UserNotFound: The given User could not be found." in result.stderr
    assert result.stdout == ""
