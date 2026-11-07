"""Tests for DataHealthService against a real FoundryClient (only HTTP is faked).

Every data health endpoint is beta: every request must carry preview=true.
The module-level filter turns the SDK's UserWarning about a stray preview=
on a GA call into a failure.
"""

import json

import pydantic
import pytest
from foundry_sdk.v2.data_health.models import (
    Check,
    CheckReport,
    GetLatestCheckReportsResponse,
)

from pltr.services.data_health import DataHealthService
from tests import foundry_json_data_health as fd

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

API = "/api/v2/dataHealth/checks"


def test_create_check_is_beta_and_sends_config_and_intent(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check())

    check = DataHealthService().create_check(
        config=fd.BUILD_STATUS_CONFIG, intent="Monitor production builds"
    )

    assert isinstance(check, Check)
    assert check.config.type == "buildStatus"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", API)
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {
        "config": fd.BUILD_STATUS_CONFIG,
        "intent": "Monitor production builds",
    }


def test_create_check_without_intent(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check(intent=None))

    DataHealthService().create_check(config=fd.BUILD_STATUS_CONFIG)

    assert json.loads(stub_foundry_http.requests[0].content) == {
        "config": fd.BUILD_STATUS_CONFIG
    }


def test_create_check_rejects_an_unknown_type_before_sending(stub_foundry_http):
    with pytest.raises(pydantic.ValidationError):
        DataHealthService().create_check(config={"type": "vibes"})
    assert stub_foundry_http.requests == []


def test_get_check_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check())

    check = DataHealthService().get_check(fd.CHECK_RID)

    assert check.groups == [fd.CHECK_GROUP_RID]
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", f"{API}/{fd.CHECK_RID}")
    assert dict(request.url.params) == {"preview": "true"}


def test_replace_check_is_beta_and_a_put(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check(intent="Page on failed builds"))

    check = DataHealthService().replace_check(
        fd.CHECK_RID,
        config=fd.REPLACE_BUILD_STATUS_CONFIG,
        intent="Page on failed builds",
    )

    assert check.intent == "Page on failed builds"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("PUT", f"{API}/{fd.CHECK_RID}")
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {
        "config": fd.REPLACE_BUILD_STATUS_CONFIG,
        "intent": "Page on failed builds",
    }


def test_delete_check_is_beta(stub_foundry_http):
    stub_foundry_http.respond(204)

    assert DataHealthService().delete_check(fd.CHECK_RID) is None

    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("DELETE", f"{API}/{fd.CHECK_RID}")
    assert dict(request.url.params) == {"preview": "true"}


def test_get_check_report_needs_the_check_rid(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check_report())

    report = DataHealthService().get_check_report(fd.CHECK_RID, fd.REPORT_RID)

    assert isinstance(report, CheckReport)
    assert (report.result.status, report.check.rid) == ("FAILED", fd.CHECK_RID)
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/{fd.CHECK_RID}/checkReports/{fd.REPORT_RID}",
    )
    assert dict(request.url.params) == {"preview": "true"}


def test_get_latest_check_reports(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [fd.check_report(), fd.check_report(fd.REPORT_RID_2, "PASSED")]}
    )

    response = DataHealthService().get_latest_check_reports(fd.CHECK_RID, limit=5)

    assert isinstance(response, GetLatestCheckReportsResponse)
    assert [report.result.status for report in response.data] == ["FAILED", "PASSED"]
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/{fd.CHECK_RID}/checkReports/getLatest",
    )
    assert dict(request.url.params) == {"limit": "5", "preview": "true"}


def test_get_latest_check_reports_default_limit(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    DataHealthService().get_latest_check_reports(fd.CHECK_RID)

    assert dict(stub_foundry_http.requests[0].url.params) == {"preview": "true"}
