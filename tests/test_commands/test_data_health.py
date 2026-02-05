"""Tests for DataHealth commands."""

import pytest
import json
from unittest.mock import Mock, patch
from typer.testing import CliRunner
from pltr.cli import app


class TestDataHealthCommands:
    """Test DataHealth CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock DataHealthService."""
        with patch("pltr.commands.data_health.DataHealthService") as MockService:
            mock_svc = Mock()
            MockService.return_value = mock_svc
            yield mock_svc

    # ===== Check Get Tests =====

    def test_check_get_success(self, runner, mock_service):
        """Test successful check retrieval."""
        # Setup
        check_rid = "ri.data-health.main.check.abc123"
        response = {
            "rid": check_rid,
            "config": {"type": "buildStatus"},
            "groups": [],
            "intent": "Monitor builds",
        }
        mock_service.get_check.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "check",
                "get",
                check_rid,
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_check.assert_called_once_with(
            check_rid=check_rid,
            preview=False,
        )

    def test_check_get_with_preview(self, runner, mock_service):
        """Test check retrieval with preview mode."""
        # Setup
        check_rid = "ri.data-health.main.check.abc123"
        response = {"rid": check_rid, "config": {}, "groups": []}
        mock_service.get_check.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "check",
                "get",
                check_rid,
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_check.assert_called_once_with(
            check_rid=check_rid,
            preview=True,
        )

    def test_check_get_error(self, runner, mock_service):
        """Test check retrieval error handling."""
        # Setup
        mock_service.get_check.side_effect = Exception("Not found")

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "check",
                "get",
                "ri.data-health.main.check.notfound",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error" in result.output

    # ===== Check Create Tests =====

    def test_check_create_success(self, runner, mock_service):
        """Test successful check creation."""
        # Setup
        config = {
            "type": "buildStatus",
            "subject": {
                "datasetRid": "ri.foundry.main.dataset.xxx",
                "branchId": "master"
            },
            "statusCheckConfig": {"severity": "WARNING"}
        }
        response = {
            "rid": "ri.data-health.main.check.abc123",
            "config": config,
            "groups": [],
        }
        mock_service.create_check.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "check",
                "create",
                json.dumps(config),
                "--intent",
                "Monitor builds",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.create_check.assert_called_once_with(
            config=config,
            intent="Monitor builds",
            preview=False,
        )
        assert "Created check" in result.output

    def test_check_create_invalid_json(self, runner, mock_service):
        """Test check creation with invalid JSON."""
        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "check",
                "create",
                "not valid json",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Invalid JSON" in result.output

    def test_check_create_error(self, runner, mock_service):
        """Test check creation error handling."""
        # Setup
        mock_service.create_check.side_effect = Exception("Permission denied")

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "check",
                "create",
                '{"type": "buildStatus"}',
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error" in result.output

    # ===== Check Replace Tests =====

    def test_check_replace_success(self, runner, mock_service):
        """Test successful check replacement."""
        # Setup
        check_rid = "ri.data-health.main.check.abc123"
        config = {"type": "buildStatus", "statusCheckConfig": {"severity": "ERROR"}}
        response = {
            "rid": check_rid,
            "config": config,
            "intent": "Updated threshold",
        }
        mock_service.replace_check.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "check",
                "replace",
                check_rid,
                json.dumps(config),
                "--intent",
                "Updated threshold",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.replace_check.assert_called_once_with(
            check_rid=check_rid,
            config=config,
            intent="Updated threshold",
            preview=False,
        )
        assert "Updated check" in result.output

    def test_check_replace_error(self, runner, mock_service):
        """Test check replacement error handling."""
        # Setup
        mock_service.replace_check.side_effect = Exception("Not found")

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "check",
                "replace",
                "ri.data-health.main.check.abc123",
                '{"type": "buildStatus"}',
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error" in result.output

    # ===== Check Delete Tests =====

    def test_check_delete_success(self, runner, mock_service):
        """Test successful check deletion."""
        # Setup
        check_rid = "ri.data-health.main.check.abc123"
        mock_service.delete_check.return_value = None

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "check",
                "delete",
                check_rid,
                "--force",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.delete_check.assert_called_once_with(
            check_rid=check_rid,
            preview=False,
        )
        assert "Deleted check" in result.output

    def test_check_delete_cancelled(self, runner, mock_service):
        """Test check deletion cancellation."""
        # Execute - input 'n' for confirmation
        result = runner.invoke(
            app,
            [
                "data-health",
                "check",
                "delete",
                "ri.data-health.main.check.abc123",
            ],
            input="n\n",
        )

        # Assert
        assert result.exit_code == 0
        assert "Cancelled" in result.output
        mock_service.delete_check.assert_not_called()

    def test_check_delete_error(self, runner, mock_service):
        """Test check deletion error handling."""
        # Setup
        mock_service.delete_check.side_effect = Exception("Permission denied")

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "check",
                "delete",
                "ri.data-health.main.check.abc123",
                "--force",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error" in result.output

    # ===== Report Get Tests =====

    def test_report_get_success(self, runner, mock_service):
        """Test successful report retrieval."""
        # Setup
        report_rid = "ri.data-health.main.check-report.abc123"
        response = {
            "rid": report_rid,
            "check": {"rid": "ri.data-health.main.check.xxx", "config": {}},
            "result": {"status": "PASSED", "message": "Check passed"},
            "createdTime": "2024-01-15T10:30:00Z",
        }
        mock_service.get_check_report.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "report",
                "get",
                report_rid,
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_check_report.assert_called_once_with(
            check_report_rid=report_rid,
            preview=False,
        )
        assert "PASSED" in result.output

    def test_report_get_failed_status(self, runner, mock_service):
        """Test report retrieval with failed status."""
        # Setup
        report_rid = "ri.data-health.main.check-report.abc123"
        response = {
            "rid": report_rid,
            "check": {"rid": "ri.data-health.main.check.xxx", "config": {}},
            "result": {"status": "FAILED", "message": "Build failed"},
            "createdTime": "2024-01-15T10:30:00Z",
        }
        mock_service.get_check_report.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "report",
                "get",
                report_rid,
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "FAILED" in result.output

    def test_report_get_error(self, runner, mock_service):
        """Test report retrieval error handling."""
        # Setup
        mock_service.get_check_report.side_effect = Exception("Not found")

        # Execute
        result = runner.invoke(
            app,
            [
                "data-health",
                "report",
                "get",
                "ri.data-health.main.check-report.notfound",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error" in result.output
