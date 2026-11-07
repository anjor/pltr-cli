"""Tests for `pltr aip-agents` against a real FoundryClient (only HTTP is faked).

Every AIP Agents endpoint is beta: requests carry preview=true and every
command's help starts with [beta]. (These tests replace Mock-based ones that
patched the service and the formatter.)
"""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_aip_agents as aj

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()
AGENT_PATH = f"/api/v2/aipAgents/agents/{aj.AGENT_RID}"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


# ------------------------------------------------------------------- help


@pytest.mark.parametrize(
    "group, commands",
    [
        (["aip-agents"], ["get"]),
        (["aip-agents", "sessions"], ["list", "get"]),
        (["aip-agents", "versions"], ["list"]),
    ],
)
def test_every_command_is_labeled_beta(group, commands):
    result = invoke(*group, "--help")

    assert result.exit_code == 0
    for command in commands:
        line = next(
            line for line in result.stdout.splitlines() if f" {command} " in line
        )
        assert "[beta]" in line, line


# -------------------------------------------------------------------- get


def test_get_agent_table(stub_foundry_http):
    stub_foundry_http.respond(json=aj.agent())

    result = invoke("aip-agents", "get", aj.AGENT_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        aj.AGENT_RID,
        "Support Assistant",
        "Answers support questions",
        "Ask a question",
        "Summarize open tickets",
        "region (string, READ_ONLY), tickets (objectSet, READ_WRITE)",
    ):
        assert expected in result.stdout, expected
    [request] = stub_foundry_http.requests
    assert request.url.path == AGENT_PATH
    assert dict(request.url.params) == {"preview": "true"}


def test_get_agent_json_is_the_sdk_serialization(stub_foundry_http):
    stub_foundry_http.respond(json=aj.agent())

    result = invoke("aip-agents", "get", aj.AGENT_RID, "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == aj.agent()
    assert result.stderr == ""


def test_get_agent_version_option(stub_foundry_http):
    stub_foundry_http.respond(json=aj.agent(version="1.0"))

    result = invoke("aip-agents", "get", aj.AGENT_RID, "-v", "1.0", "-f", "csv")

    assert result.exit_code == 0, result.output
    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row["Version"] == "1.0"
    assert row["Suggested Prompts"] == '["Summarize open tickets","Who is on call?"]'
    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {"version": "1.0", "preview": "true"}


def test_get_agent_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("AgentNotFound", parameters={"agentRid": aj.AGENT_RID})
    )

    result = invoke("aip-agents", "get", aj.AGENT_RID, "-f", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == ("not_found", "AgentNotFound")
    assert error["statusCode"] == 404


def test_get_agent_unknown_version_is_a_validation_error(stub_foundry_http):
    stub_foundry_http.respond(
        400,
        json=fj.error(
            "InvalidAgentVersion",
            "INVALID_ARGUMENT",
            parameters={"agentRid": aj.AGENT_RID, "version": "x"},
        ),
    )

    result = invoke("aip-agents", "get", aj.AGENT_RID, "--version", "x")

    assert result.exit_code == 6
    assert "InvalidAgentVersion" in result.stderr


# ---------------------------------------------------------- sessions list


def test_list_sessions_json(stub_foundry_http):
    body = {"data": [aj.session()], "nextPageToken": "t2"}
    stub_foundry_http.respond(json=body)

    result = invoke("aip-agents", "sessions", "list", aj.AGENT_RID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [aj.sdk_json(aj.session())],
        "nextPageToken": "t2",
    }
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{AGENT_PATH}/sessions"
    assert dict(request.url.params) == {"preview": "true"}


def test_list_sessions_csv(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.session()]})

    result = invoke("aip-agents", "sessions", "list", aj.AGENT_RID, "-f", "csv")

    assert result.exit_code == 0, result.output
    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row == {
        "RID": aj.SESSION_RID,
        "Title": "Ticket triage",
        "Agent Version": "1.2",
        "Messages": "4",
        "Created": "2026-11-01T09:30:00+00:00",
        "Updated": "2026-11-01T10:00:00+00:00",
        "Expires": "2026-11-08T09:30:00+00:00",
    }


def test_list_sessions_all_pages(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.session()], "nextPageToken": "t2"})
    stub_foundry_http.respond(json={"data": [aj.session(title="Second")]})

    result = invoke(
        "aip-agents",
        "sessions",
        "list",
        aj.AGENT_RID,
        "--page-size",
        "1",
        "--all",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert [s["metadata"]["title"] for s in document["data"]] == [
        "Ticket triage",
        "Second",
    ]
    assert "nextPageToken" not in document
    assert [dict(r.url.params) for r in stub_foundry_http.requests] == [
        {"pageSize": "1", "preview": "true"},
        {"pageSize": "1", "pageToken": "t2", "preview": "true"},
    ]


def test_list_sessions_max_pages(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.session()], "nextPageToken": "t2"})
    stub_foundry_http.respond(json={"data": [aj.session()], "nextPageToken": "t3"})

    result = invoke(
        "aip-agents", "sessions", "list", aj.AGENT_RID, "--max-pages", "2", "-f", "json"
    )

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert len(document["data"]) == 2
    assert document["nextPageToken"] == "t3"
    assert len(stub_foundry_http.requests) == 2


def test_list_sessions_empty_table(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    result = invoke("aip-agents", "sessions", "list", aj.AGENT_RID)

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "No results." in result.stderr


# ----------------------------------------------------------- sessions get


def test_get_session_table(stub_foundry_http):
    stub_foundry_http.respond(json=aj.session())

    result = invoke("aip-agents", "sessions", "get", aj.AGENT_RID, aj.SESSION_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        aj.SESSION_RID,
        "Ticket triage",
        aj.AGENT_RID,
        "2026-11-08T09:30:00+00:00",
    ):
        assert expected in result.stdout, expected
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{AGENT_PATH}/sessions/{aj.SESSION_RID}"
    assert request.url.params["preview"] == "true"


def test_get_session_json(stub_foundry_http):
    stub_foundry_http.respond(json=aj.session())

    result = invoke(
        "aip-agents", "sessions", "get", aj.AGENT_RID, aj.SESSION_RID, "-f", "json"
    )

    assert json.loads(result.stdout) == aj.sdk_json(aj.session())


def test_get_session_writes_output_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=aj.session())
    target = tmp_path / "session.json"

    result = invoke(
        "aip-agents",
        "sessions",
        "get",
        aj.AGENT_RID,
        aj.SESSION_RID,
        "-f",
        "json",
        "-o",
        str(target),
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert json.loads(target.read_text()) == aj.sdk_json(aj.session())


def test_get_session_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "SessionNotFound",
            parameters={"agentRid": aj.AGENT_RID, "sessionRid": aj.SESSION_RID},
        ),
    )

    result = invoke(
        "aip-agents", "sessions", "get", aj.AGENT_RID, aj.SESSION_RID, "-f", "json"
    )

    assert result.exit_code == 5
    assert json_lines(result.stderr)[-1]["errorName"] == "SessionNotFound"


# ---------------------------------------------------------- versions list


def test_list_versions_table(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [aj.agent_version(1, 2), aj.agent_version(1, 1)]}
    )

    result = invoke("aip-agents", "versions", "list", aj.AGENT_RID)

    assert result.exit_code == 0, result.output
    assert "1.2" in result.stdout and "1.1" in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{AGENT_PATH}/agentVersions"
    assert dict(request.url.params) == {"preview": "true"}


def test_list_versions_csv(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.agent_version(2, 0)]})

    result = invoke("aip-agents", "versions", "list", aj.AGENT_RID, "-f", "csv")

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row == {"Version": "2.0", "Major": "2", "Minor": "0"}


def test_list_versions_json_with_page_token(stub_foundry_http):
    body = {"data": [aj.agent_version(1, 0)]}
    stub_foundry_http.respond(json=body)

    result = invoke(
        "aip-agents",
        "versions",
        "list",
        aj.AGENT_RID,
        "--page-token",
        "t2",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == body
    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {"pageToken": "t2", "preview": "true"}
