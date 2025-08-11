"""
Tests for SQL service.
"""

import pytest
from unittest.mock import Mock, patch
from foundry_sdk.v2.sql_queries.models import (
    RunningQueryStatus,
    SucceededQueryStatus,
    FailedQueryStatus,
    CanceledQueryStatus,
)

from pltr.services.sql import SqlService


class TestSqlService:
    """Test SQL service functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.sql_queries = Mock()
        client.sql_queries.SqlQuery = Mock()
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create SqlService with mocked client."""
        service = SqlService()
        service._client = mock_client
        return service

    def test_execute_query_immediate_success(self, service, mock_client):
        """Test executing query that succeeds immediately."""
        # Setup
        query_id = "test-query-123"
        results_bytes = b'[{"name": "John", "age": 30}]'

        mock_client.sql_queries.SqlQuery.execute.return_value = SucceededQueryStatus(
            query_id=query_id, type="succeeded"
        )
        mock_client.sql_queries.SqlQuery.get_results.return_value = results_bytes

        # Execute
        result = service.execute_query("SELECT * FROM users", format="json")

        # Assert
        assert result["query_id"] == query_id
        assert result["status"] == "succeeded"
        assert result["results"] == [{"name": "John", "age": 30}]

        mock_client.sql_queries.SqlQuery.execute.assert_called_once_with(
            query="SELECT * FROM users", fallback_branch_ids=None
        )
        mock_client.sql_queries.SqlQuery.get_results.assert_called_once_with(query_id)

    def test_execute_query_immediate_failure(self, service, mock_client):
        """Test executing query that fails immediately."""
        # Setup
        error_message = "Syntax error in SQL query"
        mock_client.sql_queries.SqlQuery.execute.return_value = FailedQueryStatus(
            error_message=error_message, type="failed"
        )

        # Execute and assert
        with pytest.raises(
            RuntimeError, match="Query failed: Syntax error in SQL query"
        ):
            service.execute_query("SELECT * FROM nonexistent")

    def test_execute_query_with_waiting(self, service, mock_client):
        """Test executing query that requires waiting."""
        # Setup
        query_id = "test-query-456"
        results_bytes = b'{"count": 42}'

        # First call returns running status
        mock_client.sql_queries.SqlQuery.execute.return_value = RunningQueryStatus(
            query_id=query_id, type="running"
        )

        # Status checks return running then succeeded
        mock_client.sql_queries.SqlQuery.get_status.side_effect = [
            RunningQueryStatus(query_id=query_id, type="running"),
            SucceededQueryStatus(query_id=query_id, type="succeeded"),
        ]

        mock_client.sql_queries.SqlQuery.get_results.return_value = results_bytes

        # Execute with very short timeout to avoid long test runs
        with patch("time.sleep"):  # Mock sleep to speed up test
            result = service.execute_query(
                "SELECT COUNT(*) FROM large_table", timeout=1
            )

        # Assert
        assert result["query_id"] == query_id
        assert result["status"] == "succeeded"
        assert result["results"] == {"result": {"count": 42}}

    def test_execute_query_timeout(self, service, mock_client):
        """Test executing query that times out."""
        # Setup
        query_id = "test-query-timeout"
        mock_client.sql_queries.SqlQuery.execute.return_value = RunningQueryStatus(
            query_id=query_id, type="running"
        )

        # Always return running status
        mock_client.sql_queries.SqlQuery.get_status.return_value = RunningQueryStatus(
            query_id=query_id, type="running"
        )

        # Execute with very short timeout and mock time
        with patch("time.time") as mock_time, patch("time.sleep"):
            # Simulate timeout by making time progress beyond timeout
            mock_time.side_effect = [0, 301]  # Start at 0, then jump to 301 seconds

            with pytest.raises(RuntimeError, match="Query timed out after 300 seconds"):
                service.execute_query("SELECT * FROM slow_table", timeout=300)

    def test_submit_query(self, service, mock_client):
        """Test submitting query without waiting."""
        # Setup
        query_id = "test-query-submit"
        mock_client.sql_queries.SqlQuery.execute.return_value = RunningQueryStatus(
            query_id=query_id, type="running"
        )

        # Execute
        result = service.submit_query("SELECT * FROM users")

        # Assert
        assert result["query_id"] == query_id
        assert result["status"] == "running"

    def test_get_query_status(self, service, mock_client):
        """Test getting query status."""
        # Setup
        query_id = "test-query-status"
        mock_client.sql_queries.SqlQuery.get_status.return_value = SucceededQueryStatus(
            query_id=query_id, type="succeeded"
        )

        # Execute
        result = service.get_query_status(query_id)

        # Assert
        assert result["query_id"] == query_id
        assert result["status"] == "succeeded"

    def test_get_query_results_success(self, service, mock_client):
        """Test getting results from completed query."""
        # Setup
        query_id = "test-query-results"
        results_bytes = b'[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]'

        mock_client.sql_queries.SqlQuery.get_status.return_value = SucceededQueryStatus(
            query_id=query_id, type="succeeded"
        )
        mock_client.sql_queries.SqlQuery.get_results.return_value = results_bytes

        # Execute
        result = service.get_query_results(query_id, format="table")

        # Assert
        assert result == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    def test_get_query_results_failed_query(self, service, mock_client):
        """Test getting results from failed query."""
        # Setup
        query_id = "test-query-failed"
        error_message = "Table not found"
        mock_client.sql_queries.SqlQuery.get_status.return_value = FailedQueryStatus(
            error_message=error_message, type="failed"
        )

        # Execute and assert
        with pytest.raises(RuntimeError, match="Query failed: Table not found"):
            service.get_query_results(query_id)

    def test_get_query_results_running_query(self, service, mock_client):
        """Test getting results from still-running query."""
        # Setup
        query_id = "test-query-running"
        mock_client.sql_queries.SqlQuery.get_status.return_value = RunningQueryStatus(
            query_id=query_id, type="running"
        )

        # Execute and assert
        with pytest.raises(RuntimeError, match="Query is still running"):
            service.get_query_results(query_id)

    def test_cancel_query(self, service, mock_client):
        """Test canceling a query."""
        # Setup
        query_id = "test-query-cancel"
        mock_client.sql_queries.SqlQuery.get_status.return_value = CanceledQueryStatus(
            type="canceled"
        )

        # Execute
        result = service.cancel_query(query_id)

        # Assert
        assert result["status"] == "canceled"
        mock_client.sql_queries.SqlQuery.cancel.assert_called_once_with(query_id)

    def test_wait_for_completion_success(self, service, mock_client):
        """Test waiting for query completion."""
        # Setup
        query_id = "test-query-wait"

        # Return running, then succeeded
        mock_client.sql_queries.SqlQuery.get_status.side_effect = [
            RunningQueryStatus(query_id=query_id, type="running"),
            SucceededQueryStatus(query_id=query_id, type="succeeded"),
        ]

        # Execute with mocked sleep
        with patch("time.sleep"):
            result = service.wait_for_completion(query_id, timeout=60)

        # Assert
        assert result["query_id"] == query_id
        assert result["status"] == "succeeded"

    def test_wait_for_completion_failure(self, service, mock_client):
        """Test waiting for query that fails."""
        # Setup
        query_id = "test-query-wait-fail"
        error_message = "Query execution failed"

        mock_client.sql_queries.SqlQuery.get_status.return_value = FailedQueryStatus(
            error_message=error_message, type="failed"
        )

        # Execute and assert
        with pytest.raises(RuntimeError, match="Query failed: Query execution failed"):
            service.wait_for_completion(query_id, timeout=60)

    def test_format_query_results_json(self, service):
        """Test formatting query results as JSON."""
        results_bytes = b'{"users": [{"name": "Alice"}, {"name": "Bob"}]}'

        result = service._format_query_results(results_bytes, "json")

        assert result == {"users": [{"name": "Alice"}, {"name": "Bob"}]}

    def test_format_query_results_table(self, service):
        """Test formatting query results as table data."""
        results_bytes = b'[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]'

        result = service._format_query_results(results_bytes, "table")

        assert result == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    def test_format_query_results_raw(self, service):
        """Test formatting query results as raw bytes."""
        results_bytes = b"raw binary data"

        result = service._format_query_results(results_bytes, "raw")

        assert result == results_bytes

    def test_format_query_results_text(self, service):
        """Test formatting text query results."""
        results_bytes = b"Simple text result"

        result = service._format_query_results(results_bytes, "table")

        assert result == {"result": "Simple text result"}

    def test_format_query_results_binary(self, service):
        """Test formatting binary query results."""
        # Use actual binary data that will cause UnicodeDecodeError
        results_bytes = (
            b"\xff\xfe\xfd\x00\x01\x02"  # Binary data that can't be decoded as UTF-8
        )

        result = service._format_query_results(results_bytes, "json")

        assert result["type"] == "binary"
        assert result["size_bytes"] == 6
        assert "data" in result

    def test_format_query_results_invalid_json(self, service):
        """Test formatting invalid JSON as text."""
        results_bytes = b"not valid json {"

        result = service._format_query_results(results_bytes, "json")

        assert result == {"text": "not valid json {"}

    def test_execute_query_with_fallback_branches(self, service, mock_client):
        """Test executing query with fallback branch IDs."""
        # Setup
        query_id = "test-query-branches"
        fallback_branches = ["branch1", "branch2"]
        results_bytes = b'{"result": "success"}'

        mock_client.sql_queries.SqlQuery.execute.return_value = SucceededQueryStatus(
            query_id=query_id, type="succeeded"
        )
        mock_client.sql_queries.SqlQuery.get_results.return_value = results_bytes

        # Execute
        result = service.execute_query(
            "SELECT * FROM table", fallback_branch_ids=fallback_branches, format="json"
        )

        # Assert
        mock_client.sql_queries.SqlQuery.execute.assert_called_once_with(
            query="SELECT * FROM table", fallback_branch_ids=fallback_branches
        )
        assert result["results"] == {"result": "success"}

    def test_service_error_handling(self, service, mock_client):
        """Test service handles SDK errors properly."""
        # Setup
        mock_client.sql_queries.SqlQuery.execute.side_effect = Exception("SDK Error")

        # Execute and assert
        with pytest.raises(RuntimeError, match="Failed to execute query: SDK Error"):
            service.execute_query("SELECT 1")

    def test_format_query_status_types(self, service):
        """Test formatting different query status types."""
        # Test running status
        running_status = RunningQueryStatus(query_id="123", type="running")
        result = service._format_query_status(running_status)
        assert result == {"status": "running", "query_id": "123"}

        # Test succeeded status
        succeeded_status = SucceededQueryStatus(query_id="456", type="succeeded")
        result = service._format_query_status(succeeded_status)
        assert result == {"status": "succeeded", "query_id": "456"}

        # Test failed status
        failed_status = FailedQueryStatus(error_message="Error", type="failed")
        result = service._format_query_status(failed_status)
        assert result == {"status": "failed", "error_message": "Error"}

        # Test canceled status
        canceled_status = CanceledQueryStatus(type="canceled")
        result = service._format_query_status(canceled_status)
        assert result == {"status": "canceled"}
