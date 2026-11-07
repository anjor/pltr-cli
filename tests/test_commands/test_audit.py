"""Tests for `pltr audit` against a real FoundryClient (only HTTP is faked).

These replace Mock-based tests that patched the service; the old service
passed list arguments through a kwargs dict and read every page.
"""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_audit as aj

# Both audit endpoints are GA: a stray preview= would raise a UserWarning.
pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()

LOG_FILES = f"/api/v2/audit/organizations/{aj.ORG_RID}/logFiles"
CONTENT = f"{LOG_FILES}/{aj.LOG_FILE_ID}/content"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_error(result) -> dict:
    lines = [json.loads(line) for line in result.stderr.splitlines() if line.strip()]
    return lines[-1]


@pytest.fixture
def stdout_is_a_terminal(monkeypatch):
    monkeypatch.setattr("pltr.contract.output._stdout_is_terminal", lambda: True)


# --------------------------------------------------------------------- list


def test_list_table(stub_foundry_http):
    stub_foundry_http.respond(json=aj.log_files("a.json.gz", "b.json.gz"))

    result = invoke("audit", "list", aj.ORG_RID, "2024-01-01")

    assert result.exit_code == 0, result.output
    assert "Log File ID" in result.stdout
    assert "a.json.gz" in result.stdout and "b.json.gz" in result.stdout
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", LOG_FILES)
    assert dict(request.url.params) == {"startDate": "2024-01-01"}


def test_list_json_is_the_paged_shape(stub_foundry_http):
    stub_foundry_http.respond(json=aj.log_files("a.json.gz", token="t2"))

    result = invoke("audit", "list", aj.ORG_RID, "2024-01-01", "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [{"id": "a.json.gz"}],
        "nextPageToken": "t2",
    }
    assert result.stderr == ""


def test_list_csv(stub_foundry_http):
    stub_foundry_http.respond(json=aj.log_files("a.json.gz", "b.json.gz"))

    result = invoke("audit", "list", aj.ORG_RID, "2024-01-01", "-f", "csv")

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert rows == [{"Log File ID": "a.json.gz"}, {"Log File ID": "b.json.gz"}]


def test_list_end_date_and_page_size(stub_foundry_http):
    stub_foundry_http.respond(json=aj.log_files("a.json.gz"))

    result = invoke(
        "audit",
        "list",
        aj.ORG_RID,
        "2024-01-01",
        "--end-date",
        "2024-01-31",
        "--page-size",
        "100",
    )

    assert result.exit_code == 0, result.output
    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {
        "startDate": "2024-01-01",
        "endDate": "2024-01-31",
        "pageSize": "100",
    }


def test_list_fetches_one_page_by_default_and_hints_at_the_next(stub_foundry_http):
    stub_foundry_http.respond(json=aj.log_files("a.json.gz", token="t2"))

    result = invoke("audit", "list", aj.ORG_RID, "2024-01-01")

    assert len(stub_foundry_http.requests) == 1
    assert "--page-token t2" in result.stderr


def test_list_all_pages(stub_foundry_http):
    stub_foundry_http.respond(json=aj.log_files("a.json.gz", token="t2"))
    stub_foundry_http.respond(json=aj.log_files("b.json.gz"))

    result = invoke("audit", "list", aj.ORG_RID, "2024-01-01", "--all", "-f", "json")

    assert json.loads(result.stdout) == {
        "data": [{"id": "a.json.gz"}, {"id": "b.json.gz"}]
    }
    first, second = stub_foundry_http.requests
    assert dict(second.url.params) == {"startDate": "2024-01-01", "pageToken": "t2"}


def test_list_all_stops_at_an_empty_page_and_keeps_its_token(stub_foundry_http):
    """Without an end date the API always returns a token, for polling."""
    stub_foundry_http.respond(json=aj.log_files("a.json.gz", token="t2"))
    stub_foundry_http.respond(json=aj.log_files(token="t3"))
    stub_foundry_http.respond_always(json=aj.log_files(token="t3"))

    result = invoke("audit", "list", aj.ORG_RID, "2024-01-01", "--all", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [{"id": "a.json.gz"}],
        "nextPageToken": "t3",
    }
    assert len(stub_foundry_http.requests) == 2


def test_list_max_pages_stops_at_an_empty_page(stub_foundry_http):
    stub_foundry_http.respond(json=aj.log_files("a.json.gz", token="t2"))
    stub_foundry_http.respond(json=aj.log_files(token="t2"))
    stub_foundry_http.respond_always(json=aj.log_files("never.json.gz", token="t9"))

    result = invoke(
        "audit", "list", aj.ORG_RID, "2024-01-01", "--max-pages", "5", "-f", "json"
    )

    assert json.loads(result.stdout) == {
        "data": [{"id": "a.json.gz"}],
        "nextPageToken": "t2",
    }
    assert len(stub_foundry_http.requests) == 2


def test_list_resumes_from_a_page_token(stub_foundry_http):
    stub_foundry_http.respond(json=aj.log_files("b.json.gz"))

    result = invoke(
        "audit", "list", aj.ORG_RID, "2024-01-01", "--page-token", "t2", "-f", "json"
    )

    assert result.exit_code == 0, result.output
    [request] = stub_foundry_http.requests
    assert request.url.params["pageToken"] == "t2"


def test_list_empty(stub_foundry_http):
    stub_foundry_http.respond(json=aj.log_files())

    result = invoke("audit", "list", aj.ORG_RID, "2024-01-01")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "No results." in result.stderr


@pytest.mark.parametrize("value", ["01/15/2024", "2024-13-01", "yesterday"])
def test_list_rejects_bad_dates(stub_foundry_http, value):
    result = invoke("audit", "list", aj.ORG_RID, value)

    assert result.exit_code == 2
    assert "does not match the format '%Y-%m-%d'" in result.stderr
    assert stub_foundry_http.requests == []


def test_list_bad_end_date_json(stub_foundry_http):
    result = invoke(
        "audit", "list", aj.ORG_RID, "2024-01-01", "-e", "31-01-2024", "-f", "json"
    )

    assert result.exit_code == 2
    assert json_error(result)["type"] == "usage_error"
    assert stub_foundry_http.requests == []


def test_list_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403,
        json=fj.error("ListLogFilesPermissionDenied", error_code="PERMISSION_DENIED"),
    )

    result = invoke("audit", "list", aj.ORG_RID, "2024-01-01", "-f", "json")

    assert result.exit_code == 4
    assert result.stdout == ""
    error = json_error(result)
    assert (error["type"], error["errorName"]) == (
        "permission_denied",
        "ListLogFilesPermissionDenied",
    )


def test_list_invalid_organization_rid(stub_foundry_http):
    result = invoke("audit", "list", "my-org", "2024-01-01", "-f", "json")

    assert result.exit_code == 2
    assert "not a valid RID" in json_error(result)["message"]
    assert stub_foundry_http.requests == []


# ---------------------------------------------------------------------- get


def test_get_writes_the_content_unchanged_to_stdout(stub_foundry_http):
    stub_foundry_http.respond(content=b'{"event": "login"}\n{"event": "logout"}\n')

    result = invoke("audit", "get", aj.ORG_RID, aj.LOG_FILE_ID)

    assert result.exit_code == 0, result.output
    assert result.stdout_bytes == b'{"event": "login"}\n{"event": "logout"}\n'
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", CONTENT)


def test_get_binary_content_to_a_pipe(stub_foundry_http):
    stub_foundry_http.respond(content=b"\x1f\x8b\x08\x00binary")

    result = invoke("audit", "get", aj.ORG_RID, aj.LOG_FILE_ID, "--format", "json")

    assert result.exit_code == 0, result.output
    assert result.stdout_bytes == b"\x1f\x8b\x08\x00binary"
    assert result.stderr == ""


def test_get_output_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(content=b"\x1f\x8b\x08\x00binary")
    target = tmp_path / "audit.log.gz"

    result = invoke("audit", "get", aj.ORG_RID, aj.LOG_FILE_ID, "-o", str(target))

    assert result.exit_code == 0, result.output
    assert target.read_bytes() == b"\x1f\x8b\x08\x00binary"
    assert result.stdout == ""
    assert f"Wrote 10 bytes to {target}" in result.stderr


def test_get_refuses_a_terminal_before_downloading(
    stub_foundry_http, stdout_is_a_terminal
):
    result = invoke("audit", "get", aj.ORG_RID, aj.LOG_FILE_ID, "-f", "json")

    assert result.exit_code == 2
    error = json_error(result)
    assert error["type"] == "usage_error"
    assert "--output" in error["message"]
    assert stub_foundry_http.requests == []


def test_get_output_dash_means_stdout_even_on_a_terminal(
    stub_foundry_http, stdout_is_a_terminal
):
    stub_foundry_http.respond(content=b"text log\n")

    result = invoke("audit", "get", aj.ORG_RID, aj.LOG_FILE_ID, "--output", "-")

    assert result.exit_code == 0, result.output
    assert result.stdout_bytes == b"text log\n"


def test_get_permission_denied_writes_no_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "GetLogFileContentPermissionDenied",
            error_code="PERMISSION_DENIED",
            parameters={"organizationRid": aj.ORG_RID, "logFileId": aj.LOG_FILE_ID},
        ),
    )
    target = tmp_path / "audit.log"

    result = invoke(
        "audit", "get", aj.ORG_RID, aj.LOG_FILE_ID, "-o", str(target), "-f", "json"
    )

    assert result.exit_code == 4
    assert json_error(result)["errorName"] == "GetLogFileContentPermissionDenied"
    assert not target.exists()


def test_get_not_found_text(stub_foundry_http):
    stub_foundry_http.respond(404, json=fj.error("LogFileNotFound"))

    result = invoke("audit", "get", aj.ORG_RID, aj.LOG_FILE_ID)

    assert result.exit_code == 5
    assert result.stdout == ""
    assert "Error: LogFileNotFound" in result.stderr
