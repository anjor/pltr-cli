"""Tests for AuditService against a real FoundryClient (only HTTP is faked).

Both audit endpoints are GA: passing preview= would make the SDK emit a
UserWarning, which the module-level filter turns into a failure.
"""

from datetime import date

import pytest
from foundry_sdk import PermissionDeniedError
from foundry_sdk.v2.audit.models import LogFile

from pltr.services.audit import AuditService
from tests import foundry_json as fj
from tests import foundry_json_audit as aj

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

LOG_FILES = f"/api/v2/audit/organizations/{aj.ORG_RID}/logFiles"


def test_list_log_files_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(json=aj.log_files("a.json.gz", "b.json.gz", token="t2"))

    page = AuditService().list_log_files(
        aj.ORG_RID,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        page_size=50,
    )

    assert [log_file.id for log_file in page.data] == ["a.json.gz", "b.json.gz"]
    assert all(isinstance(log_file, LogFile) for log_file in page.data)
    assert page.next_page_token == "t2"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", LOG_FILES)
    assert dict(request.url.params) == {
        "startDate": "2024-01-01",
        "endDate": "2024-01-31",
        "pageSize": "50",
    }


def test_list_log_files_leaves_out_what_is_not_given(stub_foundry_http):
    stub_foundry_http.respond(json=aj.log_files())

    AuditService().list_log_files(aj.ORG_RID, page_token="t2")

    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {"pageToken": "t2"}


def test_download_log_file_streams_the_content(stub_foundry_http):
    stub_foundry_http.respond(content=b"\x1f\x8b gzip bytes")

    with AuditService().download_log_file(aj.ORG_RID, aj.LOG_FILE_ID) as response:
        content = b"".join(response.iter_bytes())

    assert content == b"\x1f\x8b gzip bytes"
    [request] = stub_foundry_http.requests
    assert request.method == "GET"
    assert request.url.path == f"{LOG_FILES}/{aj.LOG_FILE_ID}/content"
    assert request.headers["Accept"] == "application/octet-stream"
    assert "preview" not in request.url.params


def test_download_log_file_raises_api_errors_before_streaming(stub_foundry_http):
    stub_foundry_http.respond(
        403, json=fj.error("PermissionDenied", error_code="PERMISSION_DENIED")
    )

    with pytest.raises(PermissionDeniedError):
        AuditService().download_log_file(aj.ORG_RID, aj.LOG_FILE_ID)
