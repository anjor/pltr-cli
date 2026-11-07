"""
AIP Agents commands (Foundry AIP Agents API).

Agents, their sessions and their versions are addressed by RID. Every AIP
Agents endpoint is beta, so every command here is labeled [beta] and pltr
calls it with preview=True. Starting or continuing conversations is
available as generated commands (``pltr api aip-agents agent session ...``).
"""

from typing import Any, Optional

import typer
from typing_extensions import Annotated

from ..contract import (
    AllPagesOption,
    Columns,
    FormatOption,
    MaxPagesOption,
    OutputOption,
    PageSizeOption,
    PageTokenOption,
    ProfileOption,
    collect_pages,
    emit,
    pltr_command,
    resource_argument,
    spinner,
)
from ..services.aip_agents import AipAgentsService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()
sessions_app = typer.Typer(help="Your conversation sessions with an agent.")
versions_app = typer.Typer(help="Published versions of an agent.")

app.add_typer(sessions_app, name="sessions")
app.add_typer(versions_app, name="versions")


def _parameters(agent: Any) -> str:
    """The agent's application variables: ``id (type, access)``, comma-separated."""
    return ", ".join(
        f"{parameter_id} ({parameter.parameter_type.type}, {parameter.access})"
        for parameter_id, parameter in agent.parameters.items()
    )


#: Table/CSV columns for an ``Agent`` model.
AGENT_COLUMNS: Columns = {
    "RID": "rid",
    "Version": "version",
    "Display Name": "metadata.display_name",
    "Description": "metadata.description",
    "Input Placeholder": "metadata.input_placeholder",
    "Suggested Prompts": "metadata.suggested_prompts",
    "Parameters": _parameters,
}

#: Table/CSV columns for ``sessions list`` (one row per ``Session``).
SESSION_LIST_COLUMNS: Columns = {
    "RID": "rid",
    "Title": "metadata.title",
    "Agent Version": "agent_version",
    "Messages": "metadata.message_count",
    "Created": "metadata.created_time",
    "Updated": "metadata.updated_time",
    "Expires": "metadata.estimated_expires_time",
}

#: Table/CSV columns for a ``Session`` model.
SESSION_COLUMNS: Columns = {
    "RID": "rid",
    "Title": "metadata.title",
    "Agent": "agent_rid",
    "Agent Version": "agent_version",
    "Messages": "metadata.message_count",
    "Created": "metadata.created_time",
    "Updated": "metadata.updated_time",
    "Expires": "metadata.estimated_expires_time",
}

#: Table/CSV columns for an ``AgentVersion`` model.
VERSION_COLUMNS: Columns = {
    "Version": "string",
    "Major": "version.major",
    "Minor": "version.minor",
}

AgentRid = Annotated[
    str,
    resource_argument(
        "agent",
        help="Agent RID (ri.aip-agents..agent.<id>; shown in AIP Agent Studio).",
        autocompletion=complete_rid,
    ),
]


@app.command("get")
@pltr_command(sdk="aip_agents.Agent.get", beta=True)
def get_agent(
    agent_rid: AgentRid,
    version: Annotated[
        Optional[str],
        typer.Option(
            "--version",
            "-v",
            help="Agent version (e.g. 1.0; default: the latest published version).",
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get an agent's metadata, parameters and version.

    Examples:

        pltr aip-agents get <AGENT_RID>

        pltr aip-agents get <AGENT_RID> --version 1.0 --format json
    """
    with spinner(f"Fetching agent {agent_rid}..."):
        agent = AipAgentsService(profile=profile).get_agent(agent_rid, version=version)
    cache_rid(agent_rid)
    emit(agent, format=format, output=output, columns=AGENT_COLUMNS, title="Agent")


@sessions_app.command("list")
@pltr_command(sdk="aip_agents.Agent.Session.list", beta=True, paged=True)
def list_sessions(
    agent_rid: AgentRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List your conversation sessions with an agent.

    Only sessions you created through the API are listed, not sessions
    created in AIP Agent Studio. Fetches one page by default; use --all for
    every page, or --page-token with the nextPageToken of an earlier
    response to continue.
    """
    service = AipAgentsService(profile=profile)
    with spinner(f"Listing sessions of agent {agent_rid}..."):
        page = collect_pages(
            lambda token: service.list_sessions(
                agent_rid, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(agent_rid)
    emit(page, format=format, output=output, columns=SESSION_LIST_COLUMNS)


@sessions_app.command("get")
@pltr_command(sdk="aip_agents.Agent.Session.get", beta=True)
def get_session(
    agent_rid: AgentRid,
    session_rid: Annotated[
        str,
        typer.Argument(
            help="Session RID (ri.aip-agents..session.<id>; see 'sessions list').",
            autocompletion=complete_rid,
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a conversation session's metadata."""
    with spinner(f"Fetching session {session_rid}..."):
        session = AipAgentsService(profile=profile).get_session(agent_rid, session_rid)
    cache_rid(agent_rid)
    cache_rid(session_rid)
    emit(
        session, format=format, output=output, columns=SESSION_COLUMNS, title="Session"
    )


@versions_app.command("list")
@pltr_command(sdk="aip_agents.Agent.AgentVersion.list", beta=True, paged=True)
def list_versions(
    agent_rid: AgentRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List an agent's published versions, most recent first.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = AipAgentsService(profile=profile)
    with spinner(f"Listing versions of agent {agent_rid}..."):
        page = collect_pages(
            lambda token: service.list_versions(
                agent_rid, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(agent_rid)
    emit(page, format=format, output=output, columns=VERSION_COLUMNS)
