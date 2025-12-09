"""Tests for AIP Agents commands."""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner
from pltr.cli import app
from pltr.utils.pagination import PaginationResult, PaginationMetadata


class TestAipAgentsCommands:
    """Test AIP Agents CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock AipAgentsService."""
        with patch("pltr.commands.aip_agents.AipAgentsService") as MockService:
            mock_svc = Mock()
            MockService.return_value = mock_svc
            yield mock_svc

    def test_get_agent_success(self, runner, mock_service):
        """Test successful get agent command."""
        # Setup
        agent_result = {
            "rid": "ri.foundry.main.agent.abc123",
            "version": "1.0",
            "metadata": {
                "displayName": "Test Agent",
                "description": "A test agent",
            },
        }
        mock_service.get_agent.return_value = agent_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "get",
                "ri.foundry.main.agent.abc123",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_agent.assert_called_once_with(
            "ri.foundry.main.agent.abc123", version=None
        )

    def test_get_agent_with_version(self, runner, mock_service):
        """Test get agent with specific version."""
        # Setup
        agent_result = {
            "rid": "ri.foundry.main.agent.abc123",
            "version": "1.5",
        }
        mock_service.get_agent.return_value = agent_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "get",
                "ri.foundry.main.agent.abc123",
                "--version",
                "1.5",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_agent.assert_called_once_with(
            "ri.foundry.main.agent.abc123", version="1.5"
        )

    def test_get_agent_with_profile(self, runner, mock_service):
        """Test get agent with profile option."""
        # Setup
        agent_result = {
            "rid": "ri.foundry.main.agent.abc123",
            "version": "1.0",
        }
        mock_service.get_agent.return_value = agent_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "get",
                "ri.foundry.main.agent.abc123",
                "--profile",
                "test-profile",
            ],
        )

        # Assert
        assert result.exit_code == 0
        # Verify service was initialized with profile
        from pltr.commands.aip_agents import AipAgentsService

        AipAgentsService.assert_called_with(profile="test-profile")

    def test_get_agent_error(self, runner, mock_service):
        """Test get agent command with service error."""
        # Setup
        mock_service.get_agent.side_effect = RuntimeError("Agent not found")

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "get",
                "ri.foundry.main.agent.invalid",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get agent" in result.stdout

    def test_list_sessions_success(self, runner, mock_service):
        """Test successful list sessions command."""
        # Setup
        sessions_result = PaginationResult(
            data=[
                {
                    "rid": "session1",
                    "agent_rid": "ri.foundry.main.agent.abc123",
                    "metadata": {"title": "Chat 1"},
                },
                {
                    "rid": "session2",
                    "agent_rid": "ri.foundry.main.agent.abc123",
                    "metadata": {"title": "Chat 2"},
                },
            ],
            metadata=PaginationMetadata(items_fetched=2, has_more=False),
        )
        mock_service.list_sessions.return_value = sessions_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "sessions",
                "list",
                "ri.foundry.main.agent.abc123",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_sessions.assert_called_once()

    def test_list_sessions_with_pagination(self, runner, mock_service):
        """Test list sessions with pagination options."""
        # Setup
        sessions_result = PaginationResult(
            data=[],
            metadata=PaginationMetadata(items_fetched=0, has_more=False),
        )
        mock_service.list_sessions.return_value = sessions_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "sessions",
                "list",
                "ri.foundry.main.agent.abc123",
                "--page-size",
                "50",
                "--max-pages",
                "3",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_sessions.assert_called_once()
        # Verify PaginationConfig was created correctly
        call_args = mock_service.list_sessions.call_args
        config = call_args[0][1]  # Second positional argument
        assert config.page_size == 50
        assert config.max_pages == 3

    def test_list_sessions_all(self, runner, mock_service):
        """Test list sessions with --all flag."""
        # Setup
        sessions_result = PaginationResult(
            data=[],
            metadata=PaginationMetadata(items_fetched=0, has_more=False),
        )
        mock_service.list_sessions.return_value = sessions_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "sessions",
                "list",
                "ri.foundry.main.agent.abc123",
                "--all",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_args = mock_service.list_sessions.call_args
        config = call_args[0][1]
        assert config.fetch_all is True

    def test_list_sessions_empty(self, runner, mock_service):
        """Test list sessions when no sessions found."""
        # Setup
        sessions_result = PaginationResult(
            data=[],
            metadata=PaginationMetadata(items_fetched=0, has_more=False),
        )
        mock_service.list_sessions.return_value = sessions_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "sessions",
                "list",
                "ri.foundry.main.agent.abc123",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "No sessions found" in result.stdout

    def test_list_sessions_error(self, runner, mock_service):
        """Test list sessions command with error."""
        # Setup
        mock_service.list_sessions.side_effect = RuntimeError("Failed to list")

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "sessions",
                "list",
                "ri.foundry.main.agent.abc123",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to list sessions" in result.stdout

    def test_get_session_success(self, runner, mock_service):
        """Test successful get session command."""
        # Setup
        session_result = {
            "rid": "ri.foundry.main.session.xyz789",
            "agent_rid": "ri.foundry.main.agent.abc123",
            "agent_version": "1.0",
            "metadata": {"title": "Test Session"},
        }
        mock_service.get_session.return_value = session_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "sessions",
                "get",
                "ri.foundry.main.agent.abc123",
                "ri.foundry.main.session.xyz789",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_session.assert_called_once_with(
            "ri.foundry.main.agent.abc123",
            "ri.foundry.main.session.xyz789",
        )

    def test_get_session_error(self, runner, mock_service):
        """Test get session command with error."""
        # Setup
        mock_service.get_session.side_effect = RuntimeError("Session not found")

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "sessions",
                "get",
                "ri.foundry.main.agent.abc123",
                "ri.foundry.main.session.xyz789",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get session" in result.stdout

    def test_list_versions_success(self, runner, mock_service):
        """Test successful list versions command."""
        # Setup
        versions_result = PaginationResult(
            data=[
                {"string": "1.2", "published": True},
                {"string": "1.1", "published": True},
            ],
            metadata=PaginationMetadata(items_fetched=2, has_more=False),
        )
        mock_service.list_versions.return_value = versions_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "versions",
                "list",
                "ri.foundry.main.agent.abc123",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_versions.assert_called_once()

    def test_list_versions_all(self, runner, mock_service):
        """Test list versions with --all flag."""
        # Setup
        versions_result = PaginationResult(
            data=[],
            metadata=PaginationMetadata(items_fetched=0, has_more=False),
        )
        mock_service.list_versions.return_value = versions_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "versions",
                "list",
                "ri.foundry.main.agent.abc123",
                "--all",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_args = mock_service.list_versions.call_args
        config = call_args[0][1]
        assert config.fetch_all is True

    def test_list_versions_empty(self, runner, mock_service):
        """Test list versions when no versions found."""
        # Setup
        versions_result = PaginationResult(
            data=[],
            metadata=PaginationMetadata(items_fetched=0, has_more=False),
        )
        mock_service.list_versions.return_value = versions_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "versions",
                "list",
                "ri.foundry.main.agent.abc123",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "No versions found" in result.stdout

    def test_list_versions_error(self, runner, mock_service):
        """Test list versions command with error."""
        # Setup
        mock_service.list_versions.side_effect = RuntimeError("Failed to list")

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "versions",
                "list",
                "ri.foundry.main.agent.abc123",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to list versions" in result.stdout

    def test_help_commands(self, runner):
        """Test help output for commands."""
        # Test main help
        result = runner.invoke(app, ["aip-agents", "--help"])
        assert result.exit_code == 0
        assert "AIP Agents" in result.stdout

        # Test sessions help
        result = runner.invoke(app, ["aip-agents", "sessions", "--help"])
        assert result.exit_code == 0
        assert "conversation sessions" in result.stdout.lower()

        # Test versions help
        result = runner.invoke(app, ["aip-agents", "versions", "--help"])
        assert result.exit_code == 0
        assert "versions" in result.stdout.lower()

    def test_get_agent_json_format(self, runner, mock_service):
        """Test get agent with JSON output format."""
        # Setup
        agent_result = {
            "rid": "ri.foundry.main.agent.abc123",
            "version": "1.0",
        }
        mock_service.get_agent.return_value = agent_result

        # Execute
        result = runner.invoke(
            app,
            [
                "aip-agents",
                "get",
                "ri.foundry.main.agent.abc123",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
