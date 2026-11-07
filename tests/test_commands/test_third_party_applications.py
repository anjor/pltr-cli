"""Tests for `pltr third-party-apps` against a real FoundryClient (only HTTP is faked).

ThirdPartyApplication.get is beta: the request carries preview=true without
any flag, and --preview is a hidden, deprecated no-op. (These tests replace
Mock-based ones that patched the service and the formatter, and that asserted
the --preview flag was passed through; it was off by default, so the beta
endpoint failed without it.)
"""

import csv
import io
import json

import pytest
from foundry_sdk.v2.third_party_applications.models import ThirdPartyApplication
from typer.testing import CliRunner

from pltr.cli import app
from pltr.services.third_party_applications import ThirdPartyApplicationsService
from tests import foundry_json as fj

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()
APP_RID = (
    "ri.third-party-applications.main.application.292db3b2-b653-4de6-971c-7e97a7b881d6"
)
APP_PATH = f"/api/v2/thirdPartyApplications/{APP_RID}"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


def test_service_calls_the_beta_endpoint_with_preview(stub_foundry_http):
    stub_foundry_http.respond(json={"rid": APP_RID})

    application = ThirdPartyApplicationsService().get_application(APP_RID)

    assert isinstance(application, ThirdPartyApplication)
    assert application.rid == APP_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", APP_PATH)
    assert dict(request.url.params) == {"preview": "true"}


def test_help_is_labeled_beta():
    result = invoke("third-party-apps", "--help")

    line = next(line for line in result.stdout.splitlines() if " get " in line)
    assert "[beta]" in line
    assert "--preview" not in invoke("third-party-apps", "get", "--help").stdout


def test_get_table(stub_foundry_http):
    stub_foundry_http.respond(json={"rid": APP_RID})

    result = invoke("third-party-apps", "get", APP_RID)

    assert result.exit_code == 0, result.output
    assert APP_RID in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.params["preview"] == "true"


def test_get_json_and_csv(stub_foundry_http):
    stub_foundry_http.respond(json={"rid": APP_RID})
    stub_foundry_http.respond(json={"rid": APP_RID})

    as_json = invoke("third-party-apps", "get", APP_RID, "--format", "json")
    as_csv = invoke("third-party-apps", "get", APP_RID, "--format", "csv")

    assert json.loads(as_json.stdout) == {"rid": APP_RID}
    assert as_json.stderr == ""
    assert list(csv.DictReader(io.StringIO(as_csv.stdout))) == [{"RID": APP_RID}]


def test_preview_flag_is_a_deprecated_no_op(stub_foundry_http):
    stub_foundry_http.respond(json={"rid": APP_RID})

    result = invoke("third-party-apps", "get", APP_RID, "--preview", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"rid": APP_RID}
    [warning] = json_lines(result.stderr)
    assert warning["type"] == "warning"
    assert "--preview is deprecated and has no effect" in warning["message"]
    [request] = stub_foundry_http.requests
    assert request.url.params["preview"] == "true"


def test_get_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "ThirdPartyApplicationNotFound",
            parameters={"thirdPartyApplicationRid": APP_RID},
        ),
    )

    result = invoke("third-party-apps", "get", APP_RID, "-f", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "not_found"
    assert error["errorName"] == "ThirdPartyApplicationNotFound"
    assert error["parameters"] == {"thirdPartyApplicationRid": APP_RID}


def test_get_writes_output_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json={"rid": APP_RID})
    target = tmp_path / "app.csv"

    result = invoke("third-party-apps", "get", APP_RID, "-f", "csv", "-o", str(target))

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"to {target}" in result.stderr
    assert target.read_text() == f"RID\n{APP_RID}\n"
