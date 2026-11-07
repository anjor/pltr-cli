"""Tests for AipAgentsService against a real FoundryClient (only HTTP is faked).

Every AIP Agents endpoint is beta: each request must carry preview=true. The
module-level filter turns the SDK's UserWarning (sent when preview= is
passed to a GA method) into a failure. (These tests replace Mock-based ones
that only checked which SDK attributes were called.)
"""

import pytest
from foundry_sdk.v2.aip_agents.errors import AgentNotFound
from foundry_sdk.v2.aip_agents.models import Agent, AgentVersion, Session

from pltr.services.aip_agents import AipAgentsService
from tests import foundry_json as fj
from tests import foundry_json_aip_agents as aj

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

AGENT_PATH = f"/api/v2/aipAgents/agents/{aj.AGENT_RID}"


def test_get_agent_latest_version(stub_foundry_http):
    stub_foundry_http.respond(json=aj.agent())

    agent = AipAgentsService().get_agent(aj.AGENT_RID)

    assert isinstance(agent, Agent)
    assert agent.metadata.display_name == "Support Assistant"
    assert agent.parameters["region"].parameter_type.type == "string"
    [request] = stub_foundry_http.requests
    assert request.method == "GET"
    assert request.url.path == AGENT_PATH
    assert dict(request.url.params) == {"preview": "true"}


def test_get_agent_specific_version(stub_foundry_http):
    stub_foundry_http.respond(json=aj.agent(version="1.0"))

    AipAgentsService().get_agent(aj.AGENT_RID, version="1.0")

    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {"version": "1.0", "preview": "true"}


def test_get_agent_not_found_propagates(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("AgentNotFound", parameters={"agentRid": aj.AGENT_RID})
    )

    with pytest.raises(AgentNotFound):
        AipAgentsService().get_agent(aj.AGENT_RID)


def test_list_sessions_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [aj.session(), aj.session(title="Other")], "nextPageToken": "t2"}
    )

    page = AipAgentsService().list_sessions(aj.AGENT_RID, page_size=2)

    assert [s.metadata.title for s in page.data] == ["Ticket triage", "Other"]
    assert all(isinstance(s, Session) for s in page.data)
    assert page.next_page_token == "t2"
    [request] = stub_foundry_http.requests  # one page, not every page
    assert request.url.path == f"{AGENT_PATH}/sessions"
    assert dict(request.url.params) == {"pageSize": "2", "preview": "true"}


def test_list_sessions_from_a_page_token(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    AipAgentsService().list_sessions(aj.AGENT_RID, page_token="t2")

    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {"pageToken": "t2", "preview": "true"}


def test_get_session(stub_foundry_http):
    stub_foundry_http.respond(json=aj.session())

    session = AipAgentsService().get_session(aj.AGENT_RID, aj.SESSION_RID)

    assert isinstance(session, Session)
    assert session.metadata.message_count == 4
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{AGENT_PATH}/sessions/{aj.SESSION_RID}"
    assert request.url.params["preview"] == "true"


def test_list_versions_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [aj.agent_version(1, 2), aj.agent_version(1, 1)]}
    )

    page = AipAgentsService().list_versions(aj.AGENT_RID, page_size=10)

    assert [v.string for v in page.data] == ["1.2", "1.1"]
    assert all(isinstance(v, AgentVersion) for v in page.data)
    assert page.next_page_token is None
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{AGENT_PATH}/agentVersions"
    assert dict(request.url.params) == {"pageSize": "10", "preview": "true"}
