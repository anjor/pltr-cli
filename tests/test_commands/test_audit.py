"""
Tests for audit log commands.
"""

import pytest
from unittest.mock import Mock, patch
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
        """Test successful list audit logs command."""
        # Setup
        logs_result = [
            {
                "id": "audit-log-1",
                "timestamp": "2024-01-15T10:30:00Z",
                "user": "user123",
                "action": "DATASET_READ",
                "resource": "ri.foundry.main.dataset.abc",
            },
            {
                "id": "audit-log-2",
                "timestamp": "2024-01-15T11:00:00Z",
                "user": "user456",
                "action": "DATASET_WRITE",
                "resource": "ri.foundry.main.dataset.def",
            },
        ]
        mock_service.list_audit_logs.return_value = logs_result

        result = runner.invoke(
            app,
            ["audit", "list", "--format", "json"],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_audit_logs.assert_called_once_with(
            start_time=None,
            end_time=None,
            user_id=None,
            preview=False,
        )

    def test_list_command_with_filters(self, runner, mock_service) -> None:
        """Test list command with time and user filters."""
        # Setup
        logs_result = [
            {
                "id": "audit-log-1",
                "timestamp": "2024-01-15T10:30:00Z",
                "user": "user123",
                "action": "DATASET_READ",
            },
        ]
        mock_service.list_audit_logs.return_value = logs_result

        result = runner.invoke(
            app,
            [
                "audit",
                "list",
                "--start-time",
                "2024-01-01T00:00:00Z",
                "--end-time",
                "2024-01-31T23:59:59Z",
                "--user-id",
                "user123",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_audit_logs.assert_called_once_with(
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-01-31T23:59:59Z",
            user_id="user123",
            preview=False,
        )

    def test_list_command_empty_result(self, runner, mock_service) -> None:
        """Test list command with no results."""
        # Setup
        mock_service.list_audit_logs.return_value = []

        result = runner.invoke(
            app,
            ["audit", "list"],
        )

        # Assert
        assert result.exit_code == 0
        assert "No audit logs found" in result.stdout

    def test_list_command_with_preview(self, runner, mock_service) -> None:
        """Test list command with preview flag."""
        # Setup
        mock_service.list_audit_logs.return_value = []

        result = runner.invoke(
            app,
            ["audit", "list", "--preview"],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.list_audit_logs.assert_called_once_with(
            start_time=None,
            end_time=None,
            user_id=None,
            preview=True,
        )

    def test_list_command_error(self, runner, mock_service) -> None:
        """Test list command with service error."""
        # Setup
        mock_service.list_audit_logs.side_effect = RuntimeError(
            "Failed to fetch audit logs"
        )

        result = runner.invoke(
            app,
            ["audit", "list"],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to list audit logs" in result.stdout

    # ===== Get Command Tests =====

    def test_get_command_success(self, runner, mock_service) -> None:
        """Test successful get audit log command."""
        # Setup
        log_result = {
            "id": "audit-log-123",
            "timestamp": "2024-01-15T10:30:00Z",
            "user": "user123",
            "action": "DATASET_READ",
            "resource": "ri.foundry.main.dataset.abc",
            "details": {"ip_address": "10.0.0.1"},
        }
        mock_service.get_audit_log.return_value = log_result

        result = runner.invoke(
            app,
            ["audit", "get", "audit-log-123", "--format", "json"],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_audit_log.assert_called_once_with(
            "audit-log-123", preview=False
        )

    def test_get_command_with_profile(self, runner, mock_service) -> None:
        """Test get command with custom profile."""
        # Setup
        log_result = {"id": "audit-log-456"}
        mock_service.get_audit_log.return_value = log_result

        result = runner.invoke(
            app,
            ["audit", "get", "audit-log-456", "--profile", "production"],
        )

        # Assert
        assert result.exit_code == 0

    def test_get_command_error(self, runner, mock_service) -> None:
        """Test get command with service error."""
        # Setup
        mock_service.get_audit_log.side_effect = RuntimeError("Audit log not found")

        result = runner.invoke(
            app,
            ["audit", "get", "invalid-log-id"],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get audit log" in result.stdout

    # ===== Export Command Tests =====

    def test_export_command_success(self, runner, mock_service) -> None:
        """Test successful export audit logs command."""
        # Setup
        export_result = {
            "id": "export-123",
            "status": "PENDING",
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-31T23:59:59Z",
        }
        mock_service.export_audit_logs.return_value = export_result

        result = runner.invoke(
            app,
            [
                "audit",
                "export",
                "2024-01-01T00:00:00Z",
                "2024-01-31T23:59:59Z",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.export_audit_logs.assert_called_once_with(
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-01-31T23:59:59Z",
            format="json",
            preview=False,
        )

    def test_export_command_with_csv_format(self, runner, mock_service) -> None:
        """Test export command with CSV export format."""
        # Setup
        export_result = {"id": "export-456", "status": "PENDING"}
        mock_service.export_audit_logs.return_value = export_result

        result = runner.invoke(
            app,
            [
                "audit",
                "export",
                "2024-01-01T00:00:00Z",
                "2024-01-31T23:59:59Z",
                "--export-format",
                "csv",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.export_audit_logs.assert_called_once_with(
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-01-31T23:59:59Z",
            format="csv",
            preview=False,
        )

    def test_export_command_error(self, runner, mock_service) -> None:
        """Test export command with service error."""
        # Setup
        mock_service.export_audit_logs.side_effect = RuntimeError("Export failed")

        result = runner.invoke(
            app,
            ["audit", "export", "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z"],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to export audit logs" in result.stdout

    # ===== Export Status Command Tests =====

    def test_export_status_command_success(self, runner, mock_service) -> None:
        """Test successful export status command."""
        # Setup
        status_result = {
            "id": "export-123",
            "status": "COMPLETED",
            "download_url": "https://foundry.example.com/export/123/download",
        }
        mock_service.get_export_status.return_value = status_result

        result = runner.invoke(
            app,
            ["audit", "export-status", "export-123", "--format", "json"],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_export_status.assert_called_once_with(
            "export-123", preview=False
        )

    def test_export_status_command_pending(self, runner, mock_service) -> None:
        """Test export status command with pending status."""
        # Setup
        status_result = {
            "id": "export-456",
            "status": "IN_PROGRESS",
            "progress": 50,
        }
        mock_service.get_export_status.return_value = status_result

        result = runner.invoke(
            app,
            ["audit", "export-status", "export-456"],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_export_status.assert_called_once()

    def test_export_status_command_error(self, runner, mock_service) -> None:
        """Test export status command with service error."""
        # Setup
        mock_service.get_export_status.side_effect = RuntimeError("Export not found")

        result = runner.invoke(
            app,
            ["audit", "export-status", "invalid-export-id"],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get export status" in result.stdout

    # ===== Help Command Tests =====

    def test_help_command(self, runner) -> None:
        """Test help output for commands."""
        # Test main help
        result = runner.invoke(app, ["audit", "--help"])
        assert result.exit_code == 0
        assert "audit" in result.stdout.lower()
        assert (
            "compliance" in result.stdout.lower() or "security" in result.stdout.lower()
        )

        # Test list command help
        result = runner.invoke(app, ["audit", "list", "--help"])
        assert result.exit_code == 0
        assert "start-time" in result.stdout.lower()

        # Test get command help
        result = runner.invoke(app, ["audit", "get", "--help"])
        assert result.exit_code == 0
        assert "log" in result.stdout.lower()

        # Test export command help
        result = runner.invoke(app, ["audit", "export", "--help"])
        assert result.exit_code == 0
        assert "export" in result.stdout.lower()

    # ===== File Output Tests =====

    def test_list_command_with_file_output(self, runner, mock_service) -> None:
        """Test list command with file output."""
        # Setup
        logs_result = [{"id": "audit-log-1", "action": "DATASET_READ"}]
        mock_service.list_audit_logs.return_value = logs_result

        with patch("pltr.commands.audit.formatter") as mock_formatter:
            result = runner.invoke(
                app,
                [
                    "audit",
                    "list",
                    "--output",
                    "/tmp/audit_logs.json",
                    "--format",
                    "json",
                ],
            )

            # Assert
            assert result.exit_code == 0
            mock_formatter.save_to_file.assert_called_once_with(
                logs_result, "/tmp/audit_logs.json", "json"
            )
            mock_formatter.print_success.assert_called()

    def test_get_command_with_file_output(self, runner, mock_service) -> None:
        """Test get command with file output."""
        # Setup
        log_result = {"id": "audit-log-123", "action": "DATASET_READ"}
        mock_service.get_audit_log.return_value = log_result

        with patch("pltr.commands.audit.formatter") as mock_formatter:
            result = runner.invoke(
                app,
                [
                    "audit",
                    "get",
                    "audit-log-123",
                    "--output",
                    "/tmp/audit_log.json",
                    "--format",
                    "json",
                ],
            )

            # Assert
            assert result.exit_code == 0
            mock_formatter.save_to_file.assert_called_once_with(
                log_result, "/tmp/audit_log.json", "json"
            )
