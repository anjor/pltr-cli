"""Realistic Foundry API JSON bodies for the AIP Agents API (``client.aip_agents``).

Bodies use the API's own field names and value formats (times are ISO-8601),
so the SDK decodes them into real ``foundry_sdk.v2.aip_agents.models``.
"""

from typing import Any, Dict

AGENT_RID = "ri.aip-agents..agent.ad99d1d4-5b4a-4c2a-9c4f-f5f2e1f0c5a4"
SESSION_RID = "ri.aip-agents..session.292db3b2-b653-4de6-971c-7e97a7b881d6"


def agent(rid: str = AGENT_RID, version: str = "1.2", **overrides: Any) -> Dict:
    """An ``Agent`` with one string and one object-set parameter."""
    body: Dict[str, Any] = {
        "rid": rid,
        "version": version,
        "metadata": {
            "displayName": "Support Assistant",
            "description": "Answers support questions",
            "inputPlaceholder": "Ask a question",
            "suggestedPrompts": ["Summarize open tickets", "Who is on call?"],
        },
        "parameters": {
            "region": {
                "parameterType": {"type": "string", "defaultValue": "EMEA"},
                "access": "READ_ONLY",
                "description": "Sales region",
            },
            "tickets": {
                "parameterType": {
                    "type": "objectSet",
                    "expectedObjectTypes": ["ticket"],
                },
                "access": "READ_WRITE",
            },
        },
    }
    body.update(overrides)
    return body


def session(
    rid: str = SESSION_RID, title: str = "Ticket triage", **overrides: Any
) -> Dict:
    """A ``Session`` with an agent."""
    body: Dict[str, Any] = {
        "rid": rid,
        "metadata": {
            "title": title,
            "createdTime": "2026-11-01T09:30:00Z",
            "updatedTime": "2026-11-01T10:00:00Z",
            "messageCount": 4,
            "estimatedExpiresTime": "2026-11-08T09:30:00Z",
        },
        "agentRid": AGENT_RID,
        "agentVersion": "1.2",
    }
    body.update(overrides)
    return body


def agent_version(major: int = 1, minor: int = 2) -> Dict:
    """An ``AgentVersion``."""
    return {"string": f"{major}.{minor}", "version": {"major": major, "minor": minor}}


def sdk_json(body: Dict) -> Dict:
    """What pltr's JSON output is for a ``Session`` body: the SDK re-serializes
    times in UTC with an explicit offset (``Z`` becomes ``+00:00``)."""
    result = dict(body)
    if "metadata" in result:
        metadata = dict(result["metadata"])
        for key in ("createdTime", "updatedTime", "estimatedExpiresTime"):
            value = metadata.get(key)
            if isinstance(value, str) and value.endswith("Z"):
                metadata[key] = value[:-1] + "+00:00"
        result["metadata"] = metadata
    return result
