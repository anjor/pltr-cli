"""Tests for `pltr data-health` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_data_health as fd

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()
API = "/api/v2/dataHealth/checks"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, ["data-health", *args], **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


# ------------------------------------------------------------------- help


@pytest.mark.parametrize(
    "group, commands",
    [
        ("check", ("get", "create", "replace", "delete")),
        ("report", ("get", "latest")),
    ],
)
def test_every_command_is_labeled_beta(group, commands):
    result = invoke(group, "--help")

    lines = result.stdout.splitlines()
    for command in commands:
        line = next(
            line for line in lines if line.lstrip("│ ").startswith(f"{command} ")
        )
        assert "[beta]" in line, line


# -------------------------------------------------------------- check get


def test_get_check_table(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check())

    result = invoke("check", "get", fd.CHECK_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        fd.CHECK_RID,
        "buildStatus",
        "Monitor production builds",
        fd.CHECK_GROUP_RID,
        fj.USER_ID,
        "2024-01-02T00:00:00+00:00",
        '"severity":"MODERATE"',
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/{fd.CHECK_RID}"
    assert request.url.params["preview"] == "true"


def test_get_check_json(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check())

    result = invoke("check", "get", fd.CHECK_RID, "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == fd.sdk_json(fd.check())
    assert result.stderr == ""


def test_get_check_csv(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check(intent=None))

    result = invoke("check", "get", fd.CHECK_RID, "-f", "csv")

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert (row["RID"], row["Type"], row["Intent"]) == (
        fd.CHECK_RID,
        "buildStatus",
        "",
    )


def test_get_check_preview_flag_is_a_deprecated_no_op(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check())

    result = invoke("check", "get", fd.CHECK_RID, "--preview", "-f", "json")

    assert result.exit_code == 0, result.output
    [warning] = json_lines(result.stderr)
    assert "--preview is deprecated" in warning["message"]


def test_get_check_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("CheckNotFound", parameters={"checkRid": fd.CHECK_RID})
    )

    result = invoke("check", "get", fd.CHECK_RID, "--format", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == ("not_found", "CheckNotFound")


# ----------------------------------------------------------- check create


def test_create_check_inline_json(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check())

    result = invoke(
        "check",
        "create",
        json.dumps(fd.BUILD_STATUS_CONFIG),
        "--intent",
        "Monitor production builds",
    )

    assert result.exit_code == 0, result.output
    assert f"Created check {fd.CHECK_RID}" in result.stderr
    assert fd.CHECK_RID in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", API)
    assert request.url.params["preview"] == "true"
    assert json.loads(request.content) == {
        "config": fd.BUILD_STATUS_CONFIG,
        "intent": "Monitor production builds",
    }


def test_create_check_from_file_json_output(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=fd.check())
    path = tmp_path / "config.json"
    path.write_text(json.dumps(fd.BUILD_STATUS_CONFIG))

    result = invoke("check", "create", f"@{path}", "-i", "why", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == fd.sdk_json(fd.check())
    assert result.stderr == ""
    assert json.loads(stub_foundry_http.requests[0].content)["intent"] == "why"


@pytest.mark.parametrize(
    "config, message",
    [
        ("{not json", "invalid JSON"),
        ("@/nonexistent/config.json", "cannot read"),
        ('{"type": "vibes"}', "Invalid argument"),
    ],
)
def test_create_check_bad_config_is_a_usage_error(stub_foundry_http, config, message):
    result = invoke("check", "create", config, "--format", "json")

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert message in error["message"]
    assert stub_foundry_http.requests == []


def test_create_check_validation_error_from_the_api(stub_foundry_http):
    stub_foundry_http.respond(
        400, json=fj.error("InvalidCheckConfig", "INVALID_ARGUMENT")
    )

    result = invoke(
        "check", "create", json.dumps(fd.BUILD_STATUS_CONFIG), "--format", "json"
    )

    assert result.exit_code == 6
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == (
        "validation_error",
        "InvalidCheckConfig",
    )


# ---------------------------------------------------------- check replace


def test_replace_check_requires_yes_when_not_interactive(stub_foundry_http):
    result = invoke(
        "check",
        "replace",
        fd.CHECK_RID,
        json.dumps(fd.REPLACE_BUILD_STATUS_CONFIG),
        "--format",
        "json",
    )

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub_foundry_http.requests == []


def test_replace_check_with_yes(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check(intent="Page on failed builds"))

    result = invoke(
        "check",
        "replace",
        fd.CHECK_RID,
        json.dumps(fd.REPLACE_BUILD_STATUS_CONFIG),
        "--intent",
        "Page on failed builds",
        "--yes",
    )

    assert result.exit_code == 0, result.output
    assert f"Replaced check {fd.CHECK_RID}" in result.stderr
    assert "Page on failed builds" in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("PUT", f"{API}/{fd.CHECK_RID}")
    assert request.url.params["preview"] == "true"
    assert json.loads(request.content) == {
        "config": fd.REPLACE_BUILD_STATUS_CONFIG,
        "intent": "Page on failed builds",
    }


def test_replace_check_prompts_when_interactive(stub_foundry_http, interactive):
    stub_foundry_http.respond(json=fd.check())

    result = invoke(
        "check",
        "replace",
        fd.CHECK_RID,
        json.dumps(fd.REPLACE_BUILD_STATUS_CONFIG),
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert f"Replace the configuration of check {fd.CHECK_RID}?" in result.stderr


def test_replace_check_invalid_json_fails_before_asking(stub_foundry_http):
    result = invoke("check", "replace", fd.CHECK_RID, "{oops", "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "usage_error"
    assert stub_foundry_http.requests == []


# ----------------------------------------------------------- check delete


def test_delete_check_requires_yes_when_not_interactive(stub_foundry_http):
    result = invoke("check", "delete", fd.CHECK_RID)

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub_foundry_http.requests == []


def test_delete_check_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("check", "delete", fd.CHECK_RID, "-y")

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Deleted check {fd.CHECK_RID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("DELETE", f"{API}/{fd.CHECK_RID}")
    assert request.url.params["preview"] == "true"


def test_delete_check_force_is_a_deprecated_alias_for_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("check", "delete", fd.CHECK_RID, "--force", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    assert json_lines(result.stderr) == [
        {
            "type": "warning",
            "message": "--force is deprecated and will be removed in a future "
            "release; use --yes.",
        }
    ]


def test_delete_check_short_f_is_now_format(stub_foundry_http):
    """-f used to mean --force; it is --format now, so a bare -f is an error."""
    result = invoke("check", "delete", fd.CHECK_RID, "-f")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_delete_check_answering_no_aborts(stub_foundry_http, interactive):
    result = invoke("check", "delete", fd.CHECK_RID, input="n\n")

    assert result.exit_code == 1
    assert "Aborted" in result.stderr
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------- report get


def test_get_report_table(stub_foundry_http):
    stub_foundry_http.respond(json=fd.check_report())

    result = invoke("report", "get", fd.CHECK_RID, fd.REPORT_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        fd.REPORT_RID,
        "FAILED",
        "The latest build failed",
        fd.CHECK_RID,
        "buildStatus",
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/{fd.CHECK_RID}/checkReports/{fd.REPORT_RID}"
    assert request.url.params["preview"] == "true"


def test_get_report_json(stub_foundry_http):
    report = fd.check_report(status="PASSED", message=None)
    stub_foundry_http.respond(json=report)

    result = invoke("report", "get", fd.CHECK_RID, fd.REPORT_RID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == fd.sdk_json(report)


def test_get_report_needs_both_rids(stub_foundry_http):
    """The old form `report get <REPORT_RID>` can't address a report."""
    result = invoke("report", "get", fd.REPORT_RID)

    assert result.exit_code == 2
    assert "CHECK_REPORT_RID" in result.stderr
    assert stub_foundry_http.requests == []


def test_get_report_not_found(stub_foundry_http):
    parameters = {"checkRid": fd.CHECK_RID, "checkReportRid": fd.REPORT_RID}
    stub_foundry_http.respond(
        404, json=fj.error("CheckReportNotFound", parameters=parameters)
    )

    result = invoke("report", "get", fd.CHECK_RID, fd.REPORT_RID, "-f", "json")

    assert result.exit_code == 5
    error = json_lines(result.stderr)[-1]
    assert (error["errorName"], error["parameters"]) == (
        "CheckReportNotFound",
        parameters,
    )


# ---------------------------------------------------------- report latest


def test_latest_reports_table(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": [
                fd.check_report(),
                fd.check_report(fd.REPORT_RID_2, "PASSED", message=None),
            ]
        }
    )

    result = invoke("report", "latest", fd.CHECK_RID, "--format", "csv")

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [(row["RID"], row["Status"], row["Message"]) for row in rows] == [
        (fd.REPORT_RID, "FAILED", "The latest build failed"),
        (fd.REPORT_RID_2, "PASSED", ""),
    ]
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/{fd.CHECK_RID}/checkReports/getLatest"
    assert dict(request.url.params) == {"preview": "true"}


def test_latest_reports_json_and_limit(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fd.check_report()]})

    result = invoke("report", "latest", fd.CHECK_RID, "--limit", "3", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": [fd.sdk_json(fd.check_report())]}
    assert dict(stub_foundry_http.requests[0].url.params) == {
        "limit": "3",
        "preview": "true",
    }


def test_latest_reports_limit_is_checked(stub_foundry_http):
    result = invoke("report", "latest", fd.CHECK_RID, "--limit", "101")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_latest_reports_empty(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    result = invoke("report", "latest", fd.CHECK_RID)

    assert result.exit_code == 0
    assert "No results." in result.stderr
