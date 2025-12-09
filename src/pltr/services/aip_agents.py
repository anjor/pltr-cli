"""
AIP Agents service wrapper for Foundry SDK.
Provides access to AIP Agent operations including agent details, sessions, and versions.
"""

from typing import Any, Dict, Optional
from .base import BaseService
from ..utils.pagination import PaginationConfig, PaginationResult


class AipAgentsService(BaseService):
    """Service wrapper for Foundry AIP Agents operations."""

    def _get_service(self) -> Any:
        """Get the Foundry AIP agents service."""
        return self.client.aip_agents

    # ===== Agent Operations =====

    def get_agent(
        self, agent_rid: str, version: Optional[str] = None, preview: bool = True
    ) -> Dict[str, Any]:
        """
        Get details for an AIP Agent.

        Args:
            agent_rid: Agent Resource Identifier
                Format: ri.foundry.main.agent.<id>
            version: Optional agent version string (e.g., "1.0")
                If not specified, returns latest published version
            preview: Enable preview mode (default: True)

        Returns:
            Agent information dictionary containing:
            - rid: Agent resource identifier
            - version: Agent version
            - metadata: Agent metadata (displayName, description, etc.)
            - parameters: Application variables/parameters

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = AipAgentsService()
            >>> agent = service.get_agent("ri.foundry.main.agent.abc123")
            >>> print(agent['metadata']['displayName'])
        """
        try:
            agent = self.service.Agent.get(agent_rid, version=version, preview=preview)
            return self._serialize_response(agent)
        except Exception as e:
            raise RuntimeError(f"Failed to get agent {agent_rid}: {e}")

    # ===== Session Operations =====

    def list_sessions(
        self, agent_rid: str, config: PaginationConfig, preview: bool = True
    ) -> PaginationResult:
        """
        List all conversation sessions for an agent created by the calling user.

        Note: Only lists sessions created by this client, not sessions created
        in AIP Agent Studio.

        Args:
            agent_rid: Agent Resource Identifier
            config: Pagination configuration
            preview: Enable preview mode (default: True)

        Returns:
            PaginationResult with sessions and metadata

        Example:
            >>> config = PaginationConfig(page_size=20, max_pages=2)
            >>> result = service.list_sessions(agent_rid, config)
            >>> print(f"Found {result.metadata.items_fetched} sessions")
        """
        try:
            iterator = self.service.Agent.Session.list(
                agent_rid, page_size=config.page_size, preview=preview
            )
            return self._paginate_iterator(iterator, config)
        except Exception as e:
            raise RuntimeError(f"Failed to list sessions for agent {agent_rid}: {e}")

    def get_session(
        self, agent_rid: str, session_rid: str, preview: bool = True
    ) -> Dict[str, Any]:
        """
        Get details of a specific conversation session.

        Args:
            agent_rid: Agent Resource Identifier
            session_rid: Session Resource Identifier
            preview: Enable preview mode (default: True)

        Returns:
            Session information dictionary containing:
            - rid: Session resource identifier
            - agent_rid: Associated agent RID
            - agent_version: Agent version used in session
            - metadata: Session metadata (e.g., title)

        Raises:
            RuntimeError: If the operation fails
        """
        try:
            session = self.service.Agent.Session.get(
                agent_rid, session_rid, preview=preview
            )
            return self._serialize_response(session)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get session {session_rid} for agent {agent_rid}: {e}"
            )

    # ===== Version Operations =====

    def list_versions(
        self, agent_rid: str, config: PaginationConfig, preview: bool = True
    ) -> PaginationResult:
        """
        List all versions for an AIP Agent.

        Versions are returned in descending order (most recent first).

        Args:
            agent_rid: Agent Resource Identifier
            config: Pagination configuration
            preview: Enable preview mode (default: True)

        Returns:
            PaginationResult with agent versions and metadata

        Example:
            >>> config = PaginationConfig(page_size=10, fetch_all=True)
            >>> result = service.list_versions(agent_rid, config)
            >>> for version in result.data:
            ...     print(f"Version {version['string']}")
        """
        try:
            iterator = self.service.Agent.AgentVersion.list(
                agent_rid, page_size=config.page_size, preview=preview
            )
            return self._paginate_iterator(iterator, config)
        except Exception as e:
            raise RuntimeError(f"Failed to list versions for agent {agent_rid}: {e}")
