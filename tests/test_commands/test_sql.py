"""
Tests for SQL commands.
"""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from pltr.commands.sql import app
from pltr.services.sql import SqlService


class TestSqlCommands:
    """Test SQL CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock SQL service."""
        return Mock(spec=SqlService)

    def test_execute_command_success(self, runner, mock_service):
        """Test successful query execution command."""
        # Setup
        query_result = {
            "query_id": "test-123",
            "status": "succeeded",
            "results": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}],
        }
        mock_service.execute_query.return_value = query_result

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                app, ["execute", "SELECT name, age FROM users", "--format", "json"]
            )

        # Assert
        assert result.exit_code == 0
        mock_service.execute_query.assert_called_once_with(
            query="SELECT name, age FROM users",
            fallback_branch_ids=None,
            timeout=300,
            format="json",
        )

    def test_execute_command_with_options(self, runner, mock_service):
        """Test execute command with all options."""
        # Setup
        query_result = {
            "query_id": "test-456",
            "status": "succeeded",
            "results": {"count": 100},
        }
        mock_service.execute_query.return_value = query_result

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                app,
                [
                    "execute",
                    "SELECT COUNT(*) as count FROM users",
                    "--profile",
                    "production",
                    "--format",
                    "table",
                    "--timeout",
                    "600",
                    "--fallback-branches",
                    "branch1,branch2",
                ],
            )

        # Assert
        assert result.exit_code == 0
        mock_service_class.assert_called_once_with(profile="production")
        mock_service.execute_query.assert_called_once_with(
            query="SELECT COUNT(*) as count FROM users",
            fallback_branch_ids=["branch1", "branch2"],
            timeout=600,
            format="table",
        )

    def test_execute_command_with_output_file(self, runner, mock_service):
        """Test execute command with file output."""
        # Setup
        query_result = {
            "query_id": "test-789",
            "status": "succeeded",
            "results": [{"id": 1, "value": "test"}],
        }
        mock_service.execute_query.return_value = query_result

        with (
            patch("pltr.commands.sql.SqlService") as mock_service_class,
            patch("pltr.commands.sql.OutputFormatter") as mock_formatter_class,
        ):
            mock_service_class.return_value = mock_service
            mock_formatter = Mock()
            mock_formatter_class.return_value = mock_formatter

            result = runner.invoke(
                app,
                [
                    "execute",
                    "SELECT id, value FROM test_table",
                    "--output",
                    "/tmp/results.json",
                    "--format",
                    "json",
                ],
            )

        # Assert
        assert result.exit_code == 0
        mock_formatter.save_to_file.assert_called_once()

    def test_execute_command_error(self, runner, mock_service):
        """Test execute command with service error."""
        # Setup
        mock_service.execute_query.side_effect = RuntimeError("Query execution failed")

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["execute", "INVALID SQL"])

        # Assert
        assert result.exit_code == 1
        assert "Failed to execute query" in result.stdout

    def test_submit_command_success(self, runner, mock_service):
        """Test submit command success."""
        # Setup
        submit_result = {"query_id": "submitted-123", "status": "running"}
        mock_service.submit_query.return_value = submit_result

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["submit", "SELECT * FROM large_table"])

        # Assert
        assert result.exit_code == 0
        assert "Query submitted successfully" in result.stdout
        assert "submitted-123" in result.stdout
        mock_service.submit_query.assert_called_once_with(
            query="SELECT * FROM large_table", fallback_branch_ids=None
        )

    def test_submit_command_immediate_success(self, runner, mock_service):
        """Test submit command with immediate completion."""
        # Setup
        submit_result = {"query_id": "immediate-456", "status": "succeeded"}
        mock_service.submit_query.return_value = submit_result

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["submit", "SELECT 1"])

        # Assert
        assert result.exit_code == 0
        assert "Query completed immediately" in result.stdout

    def test_status_command_running(self, runner, mock_service):
        """Test status command for running query."""
        # Setup
        status_result = {"query_id": "running-789", "status": "running"}
        mock_service.get_query_status.return_value = status_result

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["status", "running-789"])

        # Assert
        assert result.exit_code == 0
        assert "Status: running" in result.stdout
        assert "Query is still executing" in result.stdout

    def test_status_command_succeeded(self, runner, mock_service):
        """Test status command for succeeded query."""
        # Setup
        status_result = {"query_id": "succeeded-101", "status": "succeeded"}
        mock_service.get_query_status.return_value = status_result

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["status", "succeeded-101"])

        # Assert
        assert result.exit_code == 0
        assert "Status: succeeded" in result.stdout
        assert "pltr sql results" in result.stdout

    def test_status_command_failed(self, runner, mock_service):
        """Test status command for failed query."""
        # Setup
        status_result = {
            "query_id": "failed-202",
            "status": "failed",
            "error_message": "Syntax error in query",
        }
        mock_service.get_query_status.return_value = status_result

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["status", "failed-202"])

        # Assert
        assert result.exit_code == 0
        assert "Status: failed" in result.stdout
        assert "Syntax error in query" in result.stdout

    def test_results_command_success(self, runner, mock_service):
        """Test results command success."""
        # Setup
        results_data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        mock_service.get_query_results.return_value = results_data

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                app, ["results", "completed-303", "--format", "json"]
            )

        # Assert
        assert result.exit_code == 0
        mock_service.get_query_results.assert_called_once_with(
            "completed-303", format="json"
        )

    def test_results_command_with_file_output(self, runner, mock_service):
        """Test results command with file output."""
        # Setup
        results_data = {"total_count": 150}
        mock_service.get_query_results.return_value = results_data

        with (
            patch("pltr.commands.sql.SqlService") as mock_service_class,
            patch("pltr.commands.sql.OutputFormatter") as mock_formatter_class,
        ):
            mock_service_class.return_value = mock_service
            mock_formatter = Mock()
            mock_formatter_class.return_value = mock_formatter

            result = runner.invoke(
                app,
                [
                    "results",
                    "export-404",
                    "--output",
                    "/tmp/query_results.csv",
                    "--format",
                    "csv",
                ],
            )

        # Assert
        assert result.exit_code == 0
        mock_formatter.save_to_file.assert_called_once()

    def test_cancel_command_success(self, runner, mock_service):
        """Test cancel command success."""
        # Setup
        cancel_result = {"query_id": "cancel-505", "status": "canceled"}
        mock_service.cancel_query.return_value = cancel_result

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["cancel", "cancel-505"])

        # Assert
        assert result.exit_code == 0
        assert "Query has been canceled successfully" in result.stdout
        mock_service.cancel_query.assert_called_once_with("cancel-505")

    def test_export_command_success(self, runner, mock_service):
        """Test export command success."""
        # Setup
        export_result = {
            "query_id": "export-606",
            "status": "succeeded",
            "results": [{"metric": "users", "count": 1000}],
        }
        mock_service.execute_query.return_value = export_result

        with (
            patch("pltr.commands.sql.SqlService") as mock_service_class,
            patch("pltr.commands.sql.OutputFormatter") as mock_formatter_class,
        ):
            mock_service_class.return_value = mock_service
            mock_formatter = Mock()
            mock_formatter_class.return_value = mock_formatter

            result = runner.invoke(
                app,
                [
                    "export",
                    "SELECT metric, COUNT(*) as count FROM analytics GROUP BY metric",
                    "/tmp/analytics.json",
                    "--format",
                    "json",
                ],
            )

        # Assert
        assert result.exit_code == 0
        assert "Query executed and results saved" in result.stdout
        mock_service.execute_query.assert_called_once()
        mock_formatter.save_to_file.assert_called_once()

    def test_export_command_auto_format_detection(self, runner, mock_service):
        """Test export command with auto format detection."""
        # Setup
        export_result = {
            "query_id": "auto-707",
            "status": "succeeded",
            "results": [{"data": "test"}],
        }
        mock_service.execute_query.return_value = export_result

        with (
            patch("pltr.commands.sql.SqlService") as mock_service_class,
            patch("pltr.commands.sql.OutputFormatter") as mock_formatter_class,
        ):
            mock_service_class.return_value = mock_service
            mock_formatter = Mock()
            mock_formatter_class.return_value = mock_formatter

            # Test .csv extension
            result = runner.invoke(
                app, ["export", "SELECT * FROM table", "/tmp/output.csv"]
            )

            # Assert CSV format was detected
            assert result.exit_code == 0
            mock_formatter.save_to_file.assert_called_once()
            # Check that CSV format was used (through service call)
            args, kwargs = mock_service.execute_query.call_args
            assert kwargs["format"] == "table"  # table format for CSV output

    def test_wait_command_success(self, runner, mock_service):
        """Test wait command success."""
        # Setup
        wait_result = {"query_id": "wait-808", "status": "succeeded"}
        mock_service.wait_for_completion.return_value = wait_result
        results_data = {"final": "result"}
        mock_service.get_query_results.return_value = results_data

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                app, ["wait", "wait-808", "--timeout", "120", "--format", "json"]
            )

        # Assert
        assert result.exit_code == 0
        assert "Status: succeeded" in result.stdout
        mock_service.wait_for_completion.assert_called_once_with("wait-808", 120)
        mock_service.get_query_results.assert_called_once()

    def test_wait_command_no_results(self, runner, mock_service):
        """Test wait command without retrieving results."""
        # Setup
        wait_result = {"query_id": "wait-909", "status": "succeeded"}
        mock_service.wait_for_completion.return_value = wait_result

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                app,
                [
                    "wait",
                    "wait-909",
                    "--format",
                    "table",  # table format, no output file = no results fetch
                ],
            )

        # Assert
        assert result.exit_code == 0
        assert "pltr sql results" in result.stdout
        mock_service.get_query_results.assert_not_called()

    def test_command_error_handling(self, runner, mock_service):
        """Test error handling in commands."""
        # Setup
        mock_service.execute_query.side_effect = RuntimeError(
            "Database connection failed"
        )

        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["execute", "SELECT 1"])

        # Assert
        assert result.exit_code == 1
        assert "Failed to execute query" in result.stdout
        assert "Database connection failed" in result.stdout

    def test_service_initialization_with_profile(self, runner, mock_service):
        """Test service initialization with custom profile."""
        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service
            mock_service.execute_query.return_value = {
                "query_id": "profile-test",
                "status": "succeeded",
                "results": [],
            }

            result = runner.invoke(
                app, ["execute", "SELECT 1", "--profile", "custom-profile"]
            )

        # Assert
        assert result.exit_code == 0
        mock_service_class.assert_called_once_with(profile="custom-profile")

    def test_fallback_branches_parsing(self, runner, mock_service):
        """Test parsing of fallback branches parameter."""
        with patch("pltr.commands.sql.SqlService") as mock_service_class:
            mock_service_class.return_value = mock_service
            mock_service.submit_query.return_value = {
                "query_id": "branches-test",
                "status": "running",
            }

            result = runner.invoke(
                app,
                [
                    "submit",
                    "SELECT * FROM versioned_table",
                    "--fallback-branches",
                    "main,feature/new-data,hotfix",
                ],
            )

        # Assert
        assert result.exit_code == 0
        mock_service.submit_query.assert_called_once_with(
            query="SELECT * FROM versioned_table",
            fallback_branch_ids=["main", "feature/new-data", "hotfix"],
        )

    def test_help_commands(self, runner):
        """Test help output for commands."""
        # Test main SQL help
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Execute SQL queries" in result.stdout

        # Test execute command help
        result = runner.invoke(app, ["execute", "--help"])
        assert result.exit_code == 0
        assert "SQL query to execute" in result.stdout
