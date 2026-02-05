"""
Tests for audit log file commands.
"""

from datetime import date
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from pltr.cli import app


class TestAuditCommands:
    """Test audit CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock AuditService."""
        with patch("pltr.commands.audit.AuditService") as MockService:
            mock_svc = Mock()
            MockService.return_value = mock_svc
            yield mock_svc

    # ===== List Command Tests =====

    def test_list_command_success(self, runner, mock_service) -> None:
        """Test successful list audit log files command."""
        # Setup
        logs_result = [
            {
                "fileId": "2024-01-15",
                "date": "2024-01-15",
                "size": 1024,
            },
            {
                "fileId": "2024-01-16",
                "date": "2024-01-16",
                "size": 2048,
            },
        ]
        mock_service.list_log_files.return_value = logs_result

        result = runner.invoke(
            app,
            [
                "audit",
                "list",
                "ri.multipass..organization.abc123",
                "2024-01-01",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_log_files.assert_called_once_with(
            organization_rid="ri.multipass..organization.abc123",
            start_date=date(2024, 1, 1),
            end_date=None,
            page_size=None,
            preview=False,
        )

    def test_list_command_with_end_date(self, runner, mock_service) -> None:
        """Test list command with end date filter."""
        # Setup
        mock_service.list_log_files.return_value = [{"fileId": "2024-01-15"}]

        result = runner.invoke(
            app,
            [
                "audit",
                "list",
                "ri.multipass..organization.abc123",
                "2024-01-01",
                "--end-date",
                "2024-01-31",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_log_files.assert_called_once_with(
            organization_rid="ri.multipass..organization.abc123",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            page_size=None,
            preview=False,
        )

    def test_list_command_empty_result(self, runner, mock_service) -> None:
        """Test list command with no results."""
        # Setup
        mock_service.list_log_files.return_value = []

        result = runner.invoke(
            app,
            [
                "audit",
                "list",
                "ri.multipass..organization.abc123",
                "2024-01-01",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "No audit log files found" in result.stdout

    def test_list_command_with_preview(self, runner, mock_service) -> None:
        """Test list command with preview flag."""
        # Setup
        mock_service.list_log_files.return_value = []

        result = runner.invoke(
            app,
            [
                "audit",
                "list",
                "ri.multipass..organization.abc123",
                "2024-01-01",
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_log_files.assert_called_once_with(
            organization_rid="ri.multipass..organization.abc123",
            start_date=date(2024, 1, 1),
            end_date=None,
            page_size=None,
            preview=True,
        )

    def test_list_command_with_page_size(self, runner, mock_service) -> None:
        """Test list command with page size."""
        # Setup
        mock_service.list_log_files.return_value = [{"fileId": "2024-01-15"}]

        result = runner.invoke(
            app,
            [
                "audit",
                "list",
                "ri.multipass..organization.abc123",
                "2024-01-01",
                "--page-size",
                "50",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_log_files.assert_called_once_with(
            organization_rid="ri.multipass..organization.abc123",
            start_date=date(2024, 1, 1),
            end_date=None,
            page_size=50,
            preview=False,
        )

    def test_list_command_invalid_date(self, runner, mock_service) -> None:
        """Test list command with invalid date format."""
        result = runner.invoke(
            app,
            [
                "audit",
                "list",
                "ri.multipass..organization.abc123",
                "not-a-date",
            ],
        )

        # Assert
        assert result.exit_code != 0
        assert "Invalid date format" in result.stdout

    def test_list_command_error(self, runner, mock_service) -> None:
        """Test list command with service error."""
        # Setup
        mock_service.list_log_files.side_effect = RuntimeError(
            "Failed to fetch audit logs"
        )

        result = runner.invoke(
            app,
            [
                "audit",
                "list",
                "ri.multipass..organization.abc123",
                "2024-01-01",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to list audit log files" in result.stdout

    # ===== Get Command Tests =====

    def test_get_command_success_text_output(self, runner, mock_service) -> None:
        """Test successful get log file command with text content."""
        # Setup - return UTF-8 text content
        mock_service.get_log_file_content.return_value = b'{"event": "test"}\n'

        result = runner.invoke(
            app,
            [
                "audit",
                "get",
                "ri.multipass..organization.abc123",
                "2024-01-15",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_log_file_content.assert_called_once_with(
            organization_rid="ri.multipass..organization.abc123",
            log_file_id="2024-01-15",
            preview=False,
        )
        assert '{"event": "test"}' in result.stdout

    def test_get_command_with_file_output(self, runner, mock_service, tmp_path) -> None:
        """Test get command with file output."""
        # Setup
        mock_service.get_log_file_content.return_value = b"binary content here"
        output_file = tmp_path / "audit.log"

        result = runner.invoke(
            app,
            [
                "audit",
                "get",
                "ri.multipass..organization.abc123",
                "2024-01-15",
                "--output",
                str(output_file),
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert output_file.read_bytes() == b"binary content here"
        assert "saved to" in result.stdout

    def test_get_command_binary_content_no_output(self, runner, mock_service) -> None:
        """Test get command with binary content but no output file."""
        # Setup - return non-UTF-8 binary content
        mock_service.get_log_file_content.return_value = b"\x80\x81\x82\xff"

        result = runner.invoke(
            app,
            [
                "audit",
                "get",
                "ri.multipass..organization.abc123",
                "2024-01-15",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "binary content" in result.stdout.lower()

    def test_get_command_with_profile(self, runner, mock_service) -> None:
        """Test get command with custom profile."""
        # Setup
        mock_service.get_log_file_content.return_value = b"log content"

        result = runner.invoke(
            app,
            [
                "audit",
                "get",
                "ri.multipass..organization.abc123",
                "2024-01-15",
                "--profile",
                "production",
            ],
        )

        # Assert
        assert result.exit_code == 0

    def test_get_command_error(self, runner, mock_service) -> None:
        """Test get command with service error."""
        # Setup
        mock_service.get_log_file_content.side_effect = RuntimeError("Log not found")

        result = runner.invoke(
            app,
            [
                "audit",
                "get",
                "ri.multipass..organization.abc123",
                "invalid-log-id",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get audit log file" in result.stdout

    # ===== Help Command Tests =====

    def test_help_command(self, runner) -> None:
        """Test help output for commands."""
        # Test main help
        result = runner.invoke(app, ["audit", "--help"])
        assert result.exit_code == 0
        assert "audit" in result.stdout.lower()

        # Test list command help
        result = runner.invoke(app, ["audit", "list", "--help"])
        assert result.exit_code == 0
        assert (
            "ORGANIZATION_RID" in result.stdout
            or "organization" in result.stdout.lower()
        )

        # Test get command help
        result = runner.invoke(app, ["audit", "get", "--help"])
        assert result.exit_code == 0
        assert "LOG_FILE_ID" in result.stdout or "log" in result.stdout.lower()

    # ===== File Output Tests =====

    def test_list_command_with_file_output(
        self, runner, mock_service, tmp_path
    ) -> None:
        """Test list command with file output."""
        # Setup
        logs_result = [{"fileId": "2024-01-15", "size": 1024}]
        mock_service.list_log_files.return_value = logs_result
        output_file = tmp_path / "audit_logs.json"

        with patch("pltr.commands.audit.formatter") as mock_formatter:
            result = runner.invoke(
                app,
                [
                    "audit",
                    "list",
                    "ri.multipass..organization.abc123",
                    "2024-01-01",
                    "--output",
                    str(output_file),
                    "--format",
                    "json",
                ],
            )

            # Assert
            assert result.exit_code == 0
            mock_formatter.save_to_file.assert_called_once_with(
                logs_result, str(output_file), "json"
            )
