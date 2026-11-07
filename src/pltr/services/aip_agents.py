"""
AIP Agents service wrapper for the Foundry SDK (``client.aip_agents``).

Every AIP Agents endpoint is beta, so every call passes the literal
``preview=True``. Methods return SDK models (or SDK iterators) unchanged and
let SDK exceptions propagate so the error layer can classify them.
"""

from typing import Any, Optional

from .base import BaseService


class AipAgentsService(BaseService):
    """Service wrapper for Foundry AIP Agents operations."""

    def _get_service(self) -> Any:
        """Get the Foundry AIP Agents service."""
        return self.client.aip_agents

    def get_agent(self, agent_rid: str, version: Optional[str] = None) -> Any:
        """Get an agent (``Agent.get``, beta); returns an ``Agent`` model.

        Args:
            agent_rid: Agent RID (``ri.aip-agents..agent.<id>``).
            version: Agent version (``"<major>.<minor>"``); the latest
                published version when omitted.
        """
        return self.service.Agent.get(agent_rid, version=version, preview=True)

    def list_sessions(
        self,
        agent_rid: str,
        *,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of your sessions with an agent (``Agent.Session.list``, beta).

        Only sessions created through the API by the calling user are listed,
        not sessions created in AIP Agent Studio.

        Returns:
            The SDK ``ResourceIterator[Session]``; constructing it fetched one
            page (``.data``, ``.next_page_token``).
        """
        return self.service.Agent.Session.list(
            agent_rid, page_size=page_size, page_token=page_token, preview=True
        )

    def get_session(self, agent_rid: str, session_rid: str) -> Any:
        """Get a session (``Agent.Session.get``, beta); returns a ``Session`` model."""
        return self.service.Agent.Session.get(agent_rid, session_rid, preview=True)

    def list_versions(
        self,
        agent_rid: str,
        *,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of an agent's versions (``Agent.AgentVersion.list``, beta).

        Versions are returned most recent first.

        Returns:
            The SDK ``ResourceIterator[AgentVersion]``; constructing it fetched
            one page (``.data``, ``.next_page_token``).
        """
        return self.service.Agent.AgentVersion.list(
            agent_rid, page_size=page_size, page_token=page_token, preview=True
        )
