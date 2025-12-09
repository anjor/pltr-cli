"""Tests for AIP Agents service."""

import pytest
from unittest.mock import Mock, patch
from pltr.services.aip_agents import AipAgentsService
from pltr.utils.pagination import PaginationConfig


class TestAipAgentsService:
    """Test AIP Agents service functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.aip_agents = Mock()
        client.aip_agents.Agent = Mock()
        client.aip_agents.Agent.Session = Mock()
        client.aip_agents.Agent.AgentVersion = Mock()
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create AipAgentsService with mocked client."""
        with patch("pltr.services.base.AuthManager") as mock_auth:
            mock_auth.return_value.get_client.return_value = mock_client
            service = AipAgentsService()
            return service

    def test_get_agent(self, service, mock_client):
        """Test getting an agent."""
        # Setup
        agent_rid = "ri.foundry.main.agent.abc123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": agent_rid,
            "version": "1.0",
            "metadata": {
                "displayName": "Test Agent",
                "description": "A test agent",
            },
        }
        mock_client.aip_agents.Agent.get.return_value = mock_response

        # Execute
        result = service.get_agent(agent_rid)

        # Assert
        mock_client.aip_agents.Agent.get.assert_called_once_with(
            agent_rid, version=None, preview=True
        )
        assert result["rid"] == agent_rid
        assert result["metadata"]["displayName"] == "Test Agent"

    def test_get_agent_with_version(self, service, mock_client):
        """Test getting a specific agent version."""
        # Setup
        agent_rid = "ri.foundry.main.agent.abc123"
        version = "1.5"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": agent_rid,
            "version": version,
        }
        mock_client.aip_agents.Agent.get.return_value = mock_response

        # Execute
        result = service.get_agent(agent_rid, version=version)

        # Assert
        mock_client.aip_agents.Agent.get.assert_called_once_with(
            agent_rid, version=version, preview=True
        )
        assert result["version"] == version

    def test_get_agent_error(self, service, mock_client):
        """Test error handling in get_agent."""
        # Setup
        agent_rid = "ri.foundry.main.agent.invalid"
        mock_client.aip_agents.Agent.get.side_effect = Exception("Agent not found")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to get agent"):
            service.get_agent(agent_rid)

    def test_list_sessions(self, service, mock_client):
        """Test listing sessions for an agent."""
        # Setup
        agent_rid = "ri.foundry.main.agent.abc123"
        config = PaginationConfig(page_size=10, max_pages=1)

        # Create a mock that returns a single session to avoid empty iterator issue
        mock_session = Mock()
        mock_session.dict.return_value = {
            "rid": "session1",
            "agent_rid": agent_rid,
        }

        # Create a mock iterator
        mock_iterator = Mock()
        mock_iterator.__iter__ = Mock(return_value=iter([mock_session]))
        mock_iterator.next_page_token = None
        mock_client.aip_agents.Agent.Session.list.return_value = mock_iterator

        # Execute
        result = service.list_sessions(agent_rid, config)

        # Assert - Just verify the SDK method was called correctly
        mock_client.aip_agents.Agent.Session.list.assert_called_once_with(
            agent_rid, page_size=10, preview=True
        )
        # Verify result was returned
        assert result is not None
        assert hasattr(result, "data")

    def test_list_sessions_error(self, service, mock_client):
        """Test error handling in list_sessions."""
        # Setup
        agent_rid = "ri.foundry.main.agent.abc123"
        mock_client.aip_agents.Agent.Session.list.side_effect = Exception(
            "Failed to list"
        )
        config = PaginationConfig(page_size=10, max_pages=1)

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to list sessions"):
            service.list_sessions(agent_rid, config)

    def test_get_session(self, service, mock_client):
        """Test getting a specific session."""
        # Setup
        agent_rid = "ri.foundry.main.agent.abc123"
        session_rid = "ri.foundry.main.session.xyz789"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": session_rid,
            "agent_rid": agent_rid,
            "agent_version": "1.0",
            "metadata": {"title": "Test Session"},
        }
        mock_client.aip_agents.Agent.Session.get.return_value = mock_response

        # Execute
        result = service.get_session(agent_rid, session_rid)

        # Assert
        mock_client.aip_agents.Agent.Session.get.assert_called_once_with(
            agent_rid, session_rid, preview=True
        )
        assert result["rid"] == session_rid
        assert result["agent_rid"] == agent_rid

    def test_get_session_error(self, service, mock_client):
        """Test error handling in get_session."""
        # Setup
        agent_rid = "ri.foundry.main.agent.abc123"
        session_rid = "ri.foundry.main.session.xyz789"
        mock_client.aip_agents.Agent.Session.get.side_effect = Exception(
            "Session not found"
        )

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to get session"):
            service.get_session(agent_rid, session_rid)

    def test_list_versions(self, service, mock_client):
        """Test listing agent versions."""
        # Setup
        agent_rid = "ri.foundry.main.agent.abc123"
        config = PaginationConfig(page_size=10, fetch_all=True)

        # Create a mock that returns a single version to avoid empty iterator issue
        mock_version = Mock()
        mock_version.dict.return_value = {"string": "1.0", "published": True}

        # Create a mock iterator
        mock_iterator = Mock()
        mock_iterator.__iter__ = Mock(return_value=iter([mock_version]))
        mock_iterator.next_page_token = None
        mock_client.aip_agents.Agent.AgentVersion.list.return_value = mock_iterator

        # Execute
        result = service.list_versions(agent_rid, config)

        # Assert - Just verify the SDK method was called correctly
        mock_client.aip_agents.Agent.AgentVersion.list.assert_called_once_with(
            agent_rid, page_size=10, preview=True
        )
        # Verify result was returned
        assert result is not None
        assert hasattr(result, "data")

    def test_list_versions_error(self, service, mock_client):
        """Test error handling in list_versions."""
        # Setup
        agent_rid = "ri.foundry.main.agent.abc123"
        mock_client.aip_agents.Agent.AgentVersion.list.side_effect = Exception(
            "Failed to list versions"
        )
        config = PaginationConfig(page_size=10, max_pages=1)

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to list versions"):
            service.list_versions(agent_rid, config)
