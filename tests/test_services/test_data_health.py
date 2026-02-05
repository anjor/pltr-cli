"""Tests for DataHealth service."""

import pytest
from unittest.mock import Mock, patch
from pltr.services.data_health import DataHealthService


class TestDataHealthService:
    """Test DataHealth service functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.data_health = Mock()
        client.data_health.Check = Mock()
        client.data_health.CheckReport = Mock()
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create DataHealthService with mocked client."""
        with patch("pltr.services.base.AuthManager") as mock_auth:
            mock_auth.return_value.get_client.return_value = mock_client
            service = DataHealthService()
            return service

    # ===== Check Creation Tests =====

    def test_create_check(self, service, mock_client):
        """Test creating a check."""
        # Setup
        config = {
            "type": "buildStatus",
            "subject": {
                "datasetRid": "ri.foundry.main.dataset.xxx",
                "branchId": "master"
            },
            "statusCheckConfig": {"severity": "WARNING"}
        }
        intent = "Monitor build health"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": "ri.data-health.main.check.abc123",
            "config": config,
            "intent": intent,
            "groups": [],
        }
        mock_client.data_health.Check.create.return_value = mock_response

        # Execute
        result = service.create_check(config=config, intent=intent)

        # Assert
        mock_client.data_health.Check.create.assert_called_once_with(
            config=config,
            intent=intent,
            preview=False,
        )
        assert result["rid"] == "ri.data-health.main.check.abc123"
        assert result["config"] == config
        assert result["intent"] == intent

    def test_create_check_with_preview(self, service, mock_client):
        """Test creating a check with preview mode."""
        # Setup
        config = {"type": "buildStatus", "subject": {}, "statusCheckConfig": {}}
        mock_response = Mock()
        mock_response.dict.return_value = {"rid": "ri.data-health.main.check.abc123"}
        mock_client.data_health.Check.create.return_value = mock_response

        # Execute
        service.create_check(config=config, preview=True)

        # Assert
        mock_client.data_health.Check.create.assert_called_once_with(
            config=config,
            intent=None,
            preview=True,
        )

    def test_create_check_error(self, service, mock_client):
        """Test error handling in create_check."""
        # Setup
        mock_client.data_health.Check.create.side_effect = Exception("Permission denied")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to create check"):
            service.create_check(config={"type": "buildStatus"})

    # ===== Get Check Tests =====

    def test_get_check(self, service, mock_client):
        """Test getting check information."""
        # Setup
        check_rid = "ri.data-health.main.check.abc123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": check_rid,
            "config": {"type": "buildStatus"},
            "groups": [],
        }
        mock_client.data_health.Check.get.return_value = mock_response

        # Execute
        result = service.get_check(check_rid=check_rid)

        # Assert
        mock_client.data_health.Check.get.assert_called_once_with(
            check_rid=check_rid,
            preview=False,
        )
        assert result["rid"] == check_rid

    def test_get_check_error(self, service, mock_client):
        """Test error handling in get_check."""
        # Setup
        check_rid = "ri.data-health.main.check.notfound"
        mock_client.data_health.Check.get.side_effect = Exception("Not found")

        # Execute & Assert
        with pytest.raises(RuntimeError, match=f"Failed to get check '{check_rid}'"):
            service.get_check(check_rid=check_rid)

    # ===== Replace Check Tests =====

    def test_replace_check(self, service, mock_client):
        """Test replacing/updating a check."""
        # Setup
        check_rid = "ri.data-health.main.check.abc123"
        config = {
            "type": "buildStatus",
            "subject": {"datasetRid": "ri.foundry.main.dataset.xxx", "branchId": "master"},
            "statusCheckConfig": {"severity": "ERROR"}
        }
        intent = "Updated threshold"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": check_rid,
            "config": config,
            "intent": intent,
        }
        mock_client.data_health.Check.replace.return_value = mock_response

        # Execute
        result = service.replace_check(
            check_rid=check_rid,
            config=config,
            intent=intent,
        )

        # Assert
        mock_client.data_health.Check.replace.assert_called_once_with(
            check_rid=check_rid,
            config=config,
            intent=intent,
            preview=False,
        )
        assert result["rid"] == check_rid
        assert result["intent"] == intent

    def test_replace_check_error(self, service, mock_client):
        """Test error handling in replace_check."""
        # Setup
        check_rid = "ri.data-health.main.check.abc123"
        mock_client.data_health.Check.replace.side_effect = Exception("Not found")

        # Execute & Assert
        with pytest.raises(RuntimeError, match=f"Failed to replace check '{check_rid}'"):
            service.replace_check(check_rid=check_rid, config={"type": "buildStatus"})

    # ===== Delete Check Tests =====

    def test_delete_check(self, service, mock_client):
        """Test deleting a check."""
        # Setup
        check_rid = "ri.data-health.main.check.abc123"
        mock_client.data_health.Check.delete.return_value = None

        # Execute
        service.delete_check(check_rid=check_rid)

        # Assert
        mock_client.data_health.Check.delete.assert_called_once_with(
            check_rid=check_rid,
            preview=False,
        )

    def test_delete_check_with_preview(self, service, mock_client):
        """Test deleting a check with preview mode."""
        # Setup
        check_rid = "ri.data-health.main.check.abc123"
        mock_client.data_health.Check.delete.return_value = None

        # Execute
        service.delete_check(check_rid=check_rid, preview=True)

        # Assert
        mock_client.data_health.Check.delete.assert_called_once_with(
            check_rid=check_rid,
            preview=True,
        )

    def test_delete_check_error(self, service, mock_client):
        """Test error handling in delete_check."""
        # Setup
        check_rid = "ri.data-health.main.check.abc123"
        mock_client.data_health.Check.delete.side_effect = Exception("Permission denied")

        # Execute & Assert
        with pytest.raises(RuntimeError, match=f"Failed to delete check '{check_rid}'"):
            service.delete_check(check_rid=check_rid)

    # ===== Get CheckReport Tests =====

    def test_get_check_report(self, service, mock_client):
        """Test getting check report information."""
        # Setup
        check_report_rid = "ri.data-health.main.check-report.abc123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": check_report_rid,
            "check": {"rid": "ri.data-health.main.check.xxx", "config": {}},
            "result": {"status": "PASSED", "message": "Check passed"},
            "createdTime": "2024-01-15T10:30:00Z",
        }
        mock_client.data_health.CheckReport.get.return_value = mock_response

        # Execute
        result = service.get_check_report(check_report_rid=check_report_rid)

        # Assert
        mock_client.data_health.CheckReport.get.assert_called_once_with(
            check_report_rid=check_report_rid,
            preview=False,
        )
        assert result["rid"] == check_report_rid
        assert result["result"]["status"] == "PASSED"

    def test_get_check_report_error(self, service, mock_client):
        """Test error handling in get_check_report."""
        # Setup
        check_report_rid = "ri.data-health.main.check-report.notfound"
        mock_client.data_health.CheckReport.get.side_effect = Exception("Not found")

        # Execute & Assert
        with pytest.raises(RuntimeError, match=f"Failed to get check report '{check_report_rid}'"):
            service.get_check_report(check_report_rid=check_report_rid)
