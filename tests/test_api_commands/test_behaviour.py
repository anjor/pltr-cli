"""Behaviour of generated `pltr api` commands: paging, beta, destructive, binary, errors."""

import json
from typing import Any, List

import pytest
from foundry_sdk._core import utils as sdk_utils
from foundry_sdk.v2.admin.cbac_banner import CbacBannerClient
from foundry_sdk.v2.admin.user import UserClient

from pltr.services import base as services_base

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
def test_paged_command_prints_one_page_with_next_page_token(
    stub_foundry_http, pltr_api
):
    page = {"data": [user(USER_ID, "jdoe")], "nextPageToken": "page-2"}
    stub_foundry_http.respond(200, json=page)

    result = pltr_api("admin", "user", "list", "--page-size", "1", "--format", "json")

    assert result.exit_code == 0, result.output
    (request,) = stub_foundry_http.requests
    assert request.method == "GET"
    assert request.url.path == "/api/v2/admin/users"
    assert dict(request.url.params) == {"pageSize": "1"}
    assert json.loads(result.stdout) == page
    # In JSON mode informational stderr output is suppressed.
    assert result.stderr == ""


@pytest.mark.filterwarnings("error::UserWarning")
def test_paged_command_resumes_from_page_token(stub_foundry_http, pltr_api):
    stub_foundry_http.respond(200, json={"data": [user(OTHER_USER_ID, "asmith")]})

    result = pltr_api(
        "admin", "user", "list", "--page-token", "page-2", "--format", "json"
    )

    assert result.exit_code == 0, result.output
    assert dict(stub_foundry_http.requests[0].url.params) == {"pageToken": "page-2"}
    assert json.loads(result.stdout) == {"data": [user(OTHER_USER_ID, "asmith")]}


@pytest.mark.filterwarnings("error::UserWarning")
def test_paged_command_all_fetches_every_page(stub_foundry_http, pltr_api):
    stub_foundry_http.respond(
        200, json={"data": [user(USER_ID, "jdoe")], "nextPageToken": "p2"}
    )
    stub_foundry_http.respond(200, json={"data": [user(OTHER_USER_ID, "asmith")]})

    result = pltr_api(
        "admin", "user", "list", "--all", "--page-size", "1", "--format", "json"
    )

    assert result.exit_code == 0, result.output
    first, second = stub_foundry_http.requests
    assert dict(first.url.params) == {"pageSize": "1"}
    assert dict(second.url.params) == {"pageSize": "1", "pageToken": "p2"}
    assert json.loads(result.stdout) == {
        "data": [user(USER_ID, "jdoe"), user(OTHER_USER_ID, "asmith")]
    }


@pytest.mark.filterwarnings("error::UserWarning")
def test_max_pages_stops_and_returns_the_resume_token(stub_foundry_http, pltr_api):
    stub_foundry_http.respond(
        200, json={"data": [user(USER_ID, "a")], "nextPageToken": "p2"}
    )
    stub_foundry_http.respond(
        200, json={"data": [user(OTHER_USER_ID, "b")], "nextPageToken": "p3"}
    )

    result = pltr_api("admin", "user", "list", "--max-pages", "2", "--format", "json")

    assert result.exit_code == 0, result.output
    assert len(stub_foundry_http.requests) == 2
    assert json.loads(result.stdout) == {
        "data": [user(USER_ID, "a"), user(OTHER_USER_ID, "b")],
        "nextPageToken": "p3",
    }


ORG_RID = "ri.multipass..organization.0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"


@pytest.mark.filterwarnings("error::UserWarning")
def test_audit_log_files_all_stops_at_the_first_empty_page(stub_foundry_http, pltr_api):
    """Without --end-date the API returns a nextPageToken on every page (to
    poll for new log files), so --all used to page forever."""
    stub_foundry_http.respond(
        200, json={"data": [{"id": "log-1"}], "nextPageToken": "t1"}
    )
    stub_foundry_http.respond(200, json={"data": [], "nextPageToken": "t2"})
    stub_foundry_http.respond_always(
        200, json={"data": [{"id": "log-2"}], "nextPageToken": "t3"}
    )
    list_log_files = ("audit", "organization", "log-file", "list", ORG_RID)

    result = pltr_api(
        *list_log_files, "--start-date", "2026-01-01", "--all", "--format", "json"
    )

    assert result.exit_code == 0, result.output
    first, second = stub_foundry_http.requests
    assert dict(first.url.params) == {"startDate": "2026-01-01"}
    assert second.url.params["pageToken"] == "t1"
    # The empty page's token picks up new log files later.
    assert json.loads(result.stdout) == {
        "data": [{"id": "log-1"}],
        "nextPageToken": "t2",
    }
    assert result.stderr == ""
    help_text = pltr_api(*list_log_files, "--help").stdout
    assert "--all stop at the first empty page" in help_text


@pytest.mark.filterwarnings("error::UserWarning")
def test_all_stops_when_the_api_repeats_a_page_token(stub_foundry_http, pltr_api):
    """Any paged command: a token that comes back again would loop forever."""
    stub_foundry_http.respond(
        200, json={"data": [user(USER_ID, "a")], "nextPageToken": "p2"}
    )
    stub_foundry_http.respond_always(
        200, json={"data": [user(OTHER_USER_ID, "b")], "nextPageToken": "p2"}
    )

    result = pltr_api("admin", "user", "list", "--all", "--format", "json")

    assert result.exit_code == 0, result.output
    assert len(stub_foundry_http.requests) == 2
    assert json.loads(result.stdout) == {
        "data": [user(USER_ID, "a"), user(OTHER_USER_ID, "b")],
        "nextPageToken": "p2",
    }
    warning = json.loads(result.stderr.strip().splitlines()[-1])
    assert warning["type"] == "warning"
    assert "returned the page token 'p2' again" in warning["message"]


@pytest.mark.filterwarnings("error::UserWarning")
def test_page_size_for_an_endpoint_without_one_is_a_usage_error(
    stub_foundry_http, pltr_api
):
    """OntologyObjectSet.load_links pages by token only."""
    result = pltr_api(
        "ontologies",
        "ontology-object-set",
        "load-links",
        "flights",
        "--object-set",
        '{"type": "base", "objectType": "Aircraft"}',
        "--page-size",
        "5",
        "--format",
        "json",
    )

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []
    error = json.loads(result.stderr.strip().splitlines()[-1])
    assert error["type"] == "usage_error"
    assert "page size" in error["message"]


MODEL_RID = "ri.models.main.model.11111111-2222-4333-8444-555555555555"
EXPERIMENT_RID = "ri.models.main.experiment.11111111-2222-4333-8444-555555555556"


@pytest.mark.filterwarnings("error::UserWarning")
def test_page_size_of_a_method_that_isnt_paged_is_sent(stub_foundry_http, pltr_api):
    """Series.json takes page_size but returns one series, not a page: its
    --page-size is the SDK parameter, and was silently dropped."""
    series = {
        "type": "doubleV1",
        "series": [{"value": 0.5, "timestamp": "1700000000000", "step": "1"}],
    }
    stub_foundry_http.respond(200, json=series)
    experiment = ("models", "model", "experiment")

    result = pltr_api(
        *experiment,
        "series",
        "json",
        MODEL_RID,
        EXPERIMENT_RID,
        "loss",
        "--page-size",
        "5",
        "--offset",
        "10",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    (request,) = stub_foundry_http.requests
    assert dict(request.url.params) == {
        "pageSize": "5",
        "offset": "10",
        "preview": "true",
    }
    assert json.loads(result.stdout)["series"][0]["value"] == 0.5
    # It isn't paged, so it has no paging options.
    help_text = pltr_api(*experiment, "series", "json", "--help").stdout
    assert "--page-size" in help_text
    assert "--page-token" not in help_text and "--all" not in help_text


@pytest.mark.filterwarnings("error::UserWarning")
def test_page_size_of_a_binary_method_is_sent(stub_foundry_http, pltr_api, tmp_path):
    stub_foundry_http.respond(
        200,
        content=b'[{"a": 1}]',
        headers={"Content-Type": "application/octet-stream"},
    )
    target = tmp_path / "rows.json"

    result = pltr_api(
        "models",
        "model",
        "experiment",
        "artifact-table",
        "json",
        MODEL_RID,
        EXPERIMENT_RID,
        "metrics",
        "--page-size",
        "3",
        "-o",
        str(target),
    )

    assert result.exit_code == 0, result.output
    (request,) = stub_foundry_http.requests
    assert dict(request.url.params) == {"pageSize": "3", "preview": "true"}
    assert target.read_bytes() == b'[{"a": 1}]'


def test_one_page_keeps_page_level_fields(stub_foundry_http, pltr_api):
    """A single page is the API's response as-is, e.g. with totalCount."""
    page = {
        "data": [{"__apiName": "Aircraft", "__primaryKey": "N1", "tailNumber": "N1"}],
        "nextPageToken": "p2",
        "totalCount": "7",
    }
    stub_foundry_http.respond(200, json=page)
    stub_foundry_http.respond(200, json=page)
    list_objects = ("ontologies", "ontology-object", "list", "flights", "Aircraft")

    as_json = pltr_api(*list_objects, "--page-size", "1", "--format", "json")
    as_csv = pltr_api(*list_objects, "--format", "csv")

    assert as_json.exit_code == 0, as_json.output
    assert dict(stub_foundry_http.requests[0].url.params) == {"pageSize": "1"}
    assert json.loads(as_json.stdout) == page
    assert as_csv.stdout == "__apiName,__primaryKey,tailNumber\nAircraft,N1,N1\n"
    assert "--page-token p2" in as_csv.stderr


@pytest.mark.filterwarnings("error::UserWarning")
def test_response_paged_command_keeps_extra_fields_and_pages_body(
    stub_foundry_http, pltr_api
):
    """User.search returns a response model (not an iterator) and pages in the body."""
    page = {"data": [user(USER_ID, "jdoe")], "nextPageToken": "next"}
    stub_foundry_http.respond(200, json=page)
    stub_foundry_http.respond(200, json={"data": []})

    where = '{"type": "queryString", "value": "jd"}'
    result = pltr_api(
        "admin", "user", "search", "--where", where, "--all", "--format", "json"
    )

    assert result.exit_code == 0, result.output
    first, second = stub_foundry_http.requests
    assert first.url.path == "/api/v2/admin/users/search"
    assert json.loads(first.content) == {
        "where": {"type": "queryString", "value": "jd"}
    }
    assert json.loads(second.content) == {
        "where": {"type": "queryString", "value": "jd"},
        "pageToken": "next",
    }
    assert json.loads(result.stdout) == {"data": [user(USER_ID, "jdoe")]}


def test_paged_table_output_lists_rows_and_hints_next_page(stub_foundry_http, pltr_api):
    stub_foundry_http.respond(
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


def test_csv_output(stub_foundry_http, pltr_api):
    stub_foundry_http.respond(200, json={"data": [user(USER_ID, "jdoe")]})

    result = pltr_api("admin", "user", "list", "--format", "csv")

    assert result.exit_code == 0, result.output
    header, row = result.stdout.strip().splitlines()
    assert header == "id,username,realm,status,attributes"
    assert row == f"{USER_ID},jdoe,palantir-internal-realm,ACTIVE,{{}}"


def test_pltr_format_environment_variable_selects_json(stub_foundry_http, pltr_api):
    stub_foundry_http.respond(200, json=user(USER_ID, "jdoe"))

    result = pltr_api("admin", "user", "get", USER_ID, env={"PLTR_FORMAT": "json"})

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == user(USER_ID, "jdoe")


def test_output_option_writes_file(stub_foundry_http, pltr_api, tmp_path):
    stub_foundry_http.respond(200, json=user(USER_ID, "jdoe"))
    target = tmp_path / "user.json"

    result = pltr_api(
        "admin", "user", "get", USER_ID, "--format", "json", "-o", str(target)
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert json.loads(target.read_text()) == user(USER_ID, "jdoe")


def test_output_dash_is_stdout(stub_foundry_http, pltr_api, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stub_foundry_http.respond(200, json={"data": [user(USER_ID, "jdoe")]})

    result = pltr_api("admin", "user", "list", "--format", "json", "-o", "-")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": [user(USER_ID, "jdoe")]}
    assert not (tmp_path / "-").exists()


def test_profile_is_passed_to_auth_manager(stub_foundry_http, pltr_api):
    stub_foundry_http.respond(200, json=user(USER_ID, "jdoe"))

    result = pltr_api("admin", "user", "get", USER_ID, "--profile", "prod")

    assert result.exit_code == 0, result.output
    # The same AuthManager seam as the services (stub_foundry_http replaces it).
    get_client = services_base.AuthManager.return_value.get_client
    get_client.assert_called_once_with("prod")


def test_single_object_table_output(stub_foundry_http, pltr_api):
    stub_foundry_http.respond(200, json=user(USER_ID, "jdoe"))

    result = pltr_api("admin", "user", "get", USER_ID)

    assert result.exit_code == 0, result.output
    rows = result.stdout.splitlines()
    assert any("username" in row and "jdoe" in row for row in rows)
    assert any("status" in row and "ACTIVE" in row for row in rows)


def test_non_paged_result_with_a_data_field_shows_every_field(
    stub_foundry_http, pltr_api
):
    stub_foundry_http.respond(
        200,
        json={
            "data": [[0.25, 0.5]],
            "model": "text-embedding-3-small",
            "usage": {"promptTokens": 1},
        },
    )

    result = pltr_api(
        "language-models", "open-ai-model", "embeddings", "m", "--input", "hi"
    )

    assert result.exit_code == 0, result.output
    assert "text-embedding-3-small" in result.stdout
    assert '{"promptTokens":1}' in result.stdout
    assert "--page-token" not in result.stderr


@pytest.mark.filterwarnings("error::UserWarning")
def test_non_model_results_are_plain_json(stub_foundry_http, pltr_api):
    """A dict[str, Long] result prints its decoded values (numbers)."""
    stream_args = (DATASET_RID, "master", "subscriber-1")
    stub_foundry_http.respond(200, json={"0": 42, "1": "7"})

    result = pltr_api(
        "streams",
        "dataset",
        "stream",
        "subscriber",
        "get-read-position",
        *stream_args,
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert dict(stub_foundry_http.requests[0].url.params) == {"preview": "true"}
    assert json.loads(result.stdout) == {"0": 42, "1": 7}


@pytest.mark.filterwarnings("error::UserWarning")
def test_string_result(stub_foundry_http, pltr_api):
    media_set_rid = "ri.mio.main.media-set.6a5b4c3d-2e1f-4a0b-9c8d-7e6f5a4b3c2d"
    stub_foundry_http.respond(200, json="5b4c3d2e-1f0a-4b9c-8d7e-6f5a4b3c2d1e")

    as_json = pltr_api(
        "media-sets", "media-set", "create", media_set_rid, "--format", "json"
    )
    assert as_json.exit_code == 0, as_json.output
    assert json.loads(as_json.stdout) == "5b4c3d2e-1f0a-4b9c-8d7e-6f5a4b3c2d1e"

    stub_foundry_http.respond(200, json="5b4c3d2e-1f0a-4b9c-8d7e-6f5a4b3c2d1e")
    as_table = pltr_api("media-sets", "media-set", "create", media_set_rid)
    assert as_table.exit_code == 0, as_table.output
    assert "5b4c3d2e-1f0a-4b9c-8d7e-6f5a4b3c2d1e" in as_table.stdout


@pytest.mark.filterwarnings("error::UserWarning")
def test_no_content_prints_null_in_json_and_a_message_otherwise(
    stub_foundry_http, pltr_api
):
    group_id = "0d4b1b8e-5e43-4d1f-9a7f-6b8c2f3e1a90"
    add_member = ("admin", "group", "group-member", "add", group_id)
    stub_foundry_http.respond(204)
    stub_foundry_http.respond(204)

    as_json = pltr_api(*add_member, "--principal-ids", USER_ID, "--format", "json")
    as_text = pltr_api(*add_member, "--principal-ids", USER_ID)

    assert as_json.exit_code == 0 and as_text.exit_code == 0, as_text.output
    assert json.loads(stub_foundry_http.requests[0].content) == {
        "principalIds": [USER_ID]
    }
    assert json.loads(as_json.stdout) is None
    assert as_json.stderr == ""
    assert as_text.stdout == ""
    assert "no content" in as_text.stderr


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
def test_beta_command_sends_preview(stub_foundry_http, pltr_api):
    stub_foundry_http.respond(200, json=BANNER)

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
    (request,) = stub_foundry_http.requests
    assert request.method == "POST"
    assert request.url.path == "/api/v2/admin/cbacBanner/getForResources"
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {"resourceRids": [DATASET_RID]}
    assert json.loads(result.stdout) == BANNER


@pytest.mark.filterwarnings("error::UserWarning")
def test_beta_command_against_sdk_where_method_is_ga(
    stub_foundry_http, pltr_api, monkeypatch
):
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
    stub_foundry_http.respond(200, json=BANNER)

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
    (request,) = stub_foundry_http.requests
    assert "preview" not in request.url.params
    assert json.loads(result.stdout) == BANNER


def test_missing_sdk_method_fails_clearly(stub_foundry_http, pltr_api, monkeypatch):
    monkeypatch.delattr(UserClient, "get_markings")

    result = pltr_api("admin", "user", "get-markings", USER_ID, "--format", "json")

    assert result.exit_code == 1
    assert stub_foundry_http.requests == []
    error = stderr_json(result)
    assert error["type"] == "unexpected_error"
    assert error["exitCode"] == 1
    assert "FoundryClient.admin.User.get_markings" in error["message"]
    assert "not available in foundry-platform-sdk" in error["message"]


def test_missing_sdk_method_message_in_table_mode(
    stub_foundry_http, pltr_api, monkeypatch
):
    monkeypatch.delattr(UserClient, "get_markings")

    result = pltr_api("admin", "user", "get-markings", USER_ID)

    assert result.exit_code == 1
    assert "not available in foundry-platform-sdk" in result.stderr
    assert "uv tool install pltr-cli" in result.stderr  # the hint
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# Destructive
# ---------------------------------------------------------------------------


def test_destructive_command_without_yes_fails_when_stdin_is_not_a_terminal(
    stub_foundry_http, pltr_api
):
    result = pltr_api("admin", "user", "delete", USER_ID, "--format", "json")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []
    error = stderr_json(result)
    assert error["type"] == "confirmation_required"
    assert "--yes" in error["message"]
    assert f"DELETE /v2/admin/users/{USER_ID}" in error["message"]
    assert result.stdout == ""


@pytest.mark.filterwarnings("error::UserWarning")
def test_destructive_command_with_yes(stub_foundry_http, pltr_api):
    stub_foundry_http.respond(204)

    result = pltr_api("admin", "user", "delete", USER_ID, "-y", "--format", "json")

    assert result.exit_code == 0, result.output
    (request,) = stub_foundry_http.requests
    assert request.method == "DELETE"
    assert request.url.path == f"/api/v2/admin/users/{USER_ID}"
    assert dict(request.url.params) == {}
    assert json.loads(result.stdout) is None


def test_destructive_command_prompts_on_a_terminal(
    stub_foundry_http, pltr_api, monkeypatch
):
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)

    declined = pltr_api("admin", "user", "delete", USER_ID, input="n\n")

    assert declined.exit_code == 1
    assert stub_foundry_http.requests == []
    assert f"Run DELETE /v2/admin/users/{USER_ID}" in declined.stderr
    assert declined.stdout == ""

    stub_foundry_http.respond(204)
    accepted = pltr_api("admin", "user", "delete", USER_ID, input="y\n")

    assert accepted.exit_code == 0, accepted.output
    assert [r.method for r in stub_foundry_http.requests] == ["DELETE"]
    assert accepted.stdout == ""


def test_reviewed_destructive_methods_need_yes(stub_foundry_http, pltr_api):
    """Methods whose names don't say so are still confirmed (e.g. Stream.reset)."""
    result = pltr_api("streams", "dataset", "stream", "reset", DATASET_RID, "master")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []
    assert "--yes" in result.stderr


# ---------------------------------------------------------------------------
# Binary responses and bodies
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("error::UserWarning")
def test_binary_response_goes_to_stdout_when_not_a_terminal(
    stub_foundry_http, pltr_api
):
    payload = b"\x89PNG\r\n\x1a\n\x00binary"
    stub_foundry_http.respond(200, content=payload)

    result = pltr_api("datasets", "dataset", "file", "content", DATASET_RID, "a/b.png")

    assert result.exit_code == 0, result.output
    (request,) = stub_foundry_http.requests
    assert request.method == "GET"
    assert request.url.path == f"/api/v2/datasets/{DATASET_RID}/files/a/b.png/content"
    assert request.headers["accept"] == "application/octet-stream"
    assert result.stdout_bytes == payload


@pytest.mark.filterwarnings("error::UserWarning")
def test_binary_response_to_output_file(stub_foundry_http, pltr_api, tmp_path):
    payload = bytes(range(256)) * 10
    stub_foundry_http.respond(200, content=payload)
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
        "--output",
        str(target),
    )

    assert result.exit_code == 0, result.output
    assert dict(stub_foundry_http.requests[0].url.params) == {"branchName": "dev"}
    assert target.read_bytes() == payload
    assert result.stdout == ""
    assert f"Wrote {len(payload)} bytes" in result.stderr


def test_binary_response_refuses_a_terminal(stub_foundry_http, pltr_api, monkeypatch):
    monkeypatch.setattr("pltr.contract.output._stdout_is_terminal", lambda: True)

    result = pltr_api("datasets", "dataset", "file", "content", DATASET_RID, "x.bin")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []
    assert "--output FILE" in result.stderr


def test_binary_error_leaves_no_file(stub_foundry_http, pltr_api, tmp_path):
    stub_foundry_http.respond(
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
def test_bytes_body_is_read_from_a_file(stub_foundry_http, pltr_api, tmp_path):
    source = tmp_path / "flights.csv"
    source.write_bytes(b"id,origin\n1,SFO\n")
    file_json = {
        "path": "raw/flights.csv",
        "transactionRid": TRANSACTION_RID,
        "sizeBytes": "16",
        "updatedTime": "2026-01-01T10:00:00+00:00",
    }
    stub_foundry_http.respond(200, json=file_json)

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
    (request,) = stub_foundry_http.requests
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
    stub_foundry_http, pltr_api
):
    attachment = {
        "rid": ATTACHMENT_RID,
        "filename": "notes.txt",
        "sizeBytes": "5",
        "mediaType": "text/plain",
    }
    stub_foundry_http.respond(200, json=attachment)

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
    (request,) = stub_foundry_http.requests
    assert request.url.path == "/api/v2/ontologies/attachments/upload"
    assert dict(request.url.params) == {"filename": "notes.txt"}
    assert request.headers["content-length"] == "5"
    assert request.content == b"hello"
    # The SDK's serialization includes AttachmentV2's default `type`.
    assert json.loads(result.stdout) == {**attachment, "type": "single"}


# ---------------------------------------------------------------------------
# Inputs and errors
# ---------------------------------------------------------------------------


def test_json_option_accepts_a_file(stub_foundry_http, pltr_api, tmp_path):
    where = tmp_path / "where.json"
    where.write_text('{"type": "queryString", "value": "jd"}')
    stub_foundry_http.respond(200, json={"data": []})

    result = pltr_api(
        "admin", "user", "search", "--where", f"@{where}", "--format", "json"
    )

    assert result.exit_code == 0, result.output
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body == {"where": {"type": "queryString", "value": "jd"}}


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
def test_json_file_written_by_windows_powershell(
    stub_foundry_http, pltr_api, tmp_path, encoding
):
    """PowerShell 5 writes a byte order mark (utf8) or UTF-16 (`>`)."""
    where = tmp_path / "where.json"
    where.write_bytes('{"type": "queryString", "value": "jd"}'.encode(encoding))
    stub_foundry_http.respond(200, json={"data": []})

    result = pltr_api(
        "admin", "user", "search", "--where", f"@{where}", "--format", "json"
    )

    assert result.exit_code == 0, result.output
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body == {"where": {"type": "queryString", "value": "jd"}}


@pytest.mark.filterwarnings("error::UserWarning")
def test_required_list_parameters_default_to_empty(stub_foundry_http, pltr_api):
    """`select` is required by the SDK, and [] means every property."""
    objects = {
        "data": [
            {"__apiName": "Aircraft", "__primaryKey": "N123", "tailNumber": "N123"}
        ],
        "totalCount": "1",
    }
    stub_foundry_http.respond(200, json=objects)
    stub_foundry_http.respond(200, json=objects)
    where = '{"type": "eq", "field": "tailNumber", "value": "N123"}'
    search = ("ontologies", "ontology-object", "search", "flights", "Aircraft")

    everything = pltr_api(*search, "--where", where, "--format", "json")
    some = pltr_api(
        *search, "--where", where, "--select", "tailNumber", "--format", "json"
    )

    assert everything.exit_code == 0, everything.output
    assert some.exit_code == 0, some.output
    first, second = (json.loads(r.content) for r in stub_foundry_http.requests)
    assert first == {
        "select": [],
        "where": {"type": "eq", "field": "tailNumber", "value": "N123"},
    }
    assert second["select"] == ["tailNumber"]
    assert json.loads(everything.stdout) == objects


def test_invalid_json_input_is_a_usage_error(stub_foundry_http, pltr_api):
    result = pltr_api(
        "admin", "user", "search", "--where", "{not json", "--format", "json"
    )

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []
    error = stderr_json(result)
    assert error["type"] == "usage_error"
    assert "--where" in error["message"]


def test_sdk_validation_of_arguments_is_a_usage_error(stub_foundry_http, pltr_api):
    """The SDK validates IDs before sending anything (a user id is a UUID)."""
    result = pltr_api("admin", "user", "get", "not-a-uuid", "--format", "json")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []
    assert stderr_json(result)["type"] == "usage_error"


def test_click_usage_error_in_json_mode_is_structured(stub_foundry_http, pltr_api):
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
        (401, "UNAUTHORIZED", "MissingCredentials", 3, "auth_error"),
        (403, "PERMISSION_DENIED", "GetUserPermissionDenied", 4, "permission_denied"),
        (404, "NOT_FOUND", "UserNotFound", 5, "not_found"),
        (409, "CONFLICT", "SomethingConflicted", 7, "conflict"),
        (422, "INVALID_ARGUMENT", "Unprocessable", 6, "validation_error"),
        (500, "INTERNAL", "Default:Internal", 7, "server_error"),
    ],
)
def test_api_errors_map_to_exit_codes(
    stub_foundry_http, pltr_api, status, error_code, error_name, exit_code, error_type
):
    stub_foundry_http.respond(
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


def test_auth_errors_exit_3(stub_foundry_http, pltr_api):
    from pltr.auth.base import ProfileNotFoundError

    get_client = services_base.AuthManager.return_value.get_client
    get_client.side_effect = ProfileNotFoundError("Profile 'nope' not found.")

    result = pltr_api("admin", "user", "get", USER_ID, "--profile", "nope")

    assert result.exit_code == 3
    assert "Profile 'nope' not found." in result.stderr


def test_error_in_table_mode_is_readable(stub_foundry_http, pltr_api):
    stub_foundry_http.respond(
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
