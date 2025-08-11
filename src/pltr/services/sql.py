"""
SQL service wrapper for Foundry SDK SQL queries.
Provides a high-level interface for executing SQL queries against Foundry datasets.
"""

import time
from typing import Any, Dict, List, Optional, Union
import json

from foundry_sdk.v2.sql_queries.models import (
    RunningQueryStatus,
    SucceededQueryStatus,
    FailedQueryStatus,
    CanceledQueryStatus,
)

from .base import BaseService


class SqlService(BaseService):
    """Service wrapper for Foundry SQL query operations."""

    def _get_service(self) -> Any:
        """Get the Foundry SQL queries service."""
        return self.client.sql_queries.SqlQuery

    def execute_query(
        self,
        query: str,
        fallback_branch_ids: Optional[List[str]] = None,
        timeout: int = 300,
        format: str = "table",
    ) -> Dict[str, Any]:
        """
        Execute a SQL query and wait for completion.

        Args:
            query: SQL query string
            fallback_branch_ids: Optional list of branch IDs for fallback
            timeout: Maximum time to wait for query completion (seconds)
            format: Output format for results ('table', 'json', 'raw')

        Returns:
            Dictionary containing query results and metadata

        Raises:
            RuntimeError: If query execution fails or times out
        """
        try:
            # Submit the query
            status = self.service.execute(
                query=query, fallback_branch_ids=fallback_branch_ids
            )

            # If the query completed immediately
            if isinstance(status, SucceededQueryStatus):
                return self._format_completed_query(status.query_id, format)
            elif isinstance(status, FailedQueryStatus):
                raise RuntimeError(f"Query failed: {status.error_message}")
            elif isinstance(status, CanceledQueryStatus):
                raise RuntimeError("Query was canceled")
            elif isinstance(status, RunningQueryStatus):
                # Wait for completion
                return self._wait_for_query_completion(status.query_id, timeout, format)
            else:
                raise RuntimeError(f"Unknown query status type: {type(status)}")

        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Failed to execute query: {e}")

    def submit_query(
        self, query: str, fallback_branch_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Submit a SQL query without waiting for completion.

        Args:
            query: SQL query string
            fallback_branch_ids: Optional list of branch IDs for fallback

        Returns:
            Dictionary containing query ID and initial status

        Raises:
            RuntimeError: If query submission fails
        """
        try:
            status = self.service.execute(
                query=query, fallback_branch_ids=fallback_branch_ids
            )
            return self._format_query_status(status)
        except Exception as e:
            raise RuntimeError(f"Failed to submit query: {e}")

    def get_query_status(self, query_id: str) -> Dict[str, Any]:
        """
        Get the status of a submitted query.

        Args:
            query_id: Query identifier

        Returns:
            Dictionary containing query status information

        Raises:
            RuntimeError: If status check fails
        """
        try:
            status = self.service.get_status(query_id)
            return self._format_query_status(status)
        except Exception as e:
            raise RuntimeError(f"Failed to get query status: {e}")

    def get_query_results(self, query_id: str, format: str = "table") -> Dict[str, Any]:
        """
        Get the results of a completed query.

        Args:
            query_id: Query identifier
            format: Output format ('table', 'json', 'raw')

        Returns:
            Dictionary containing query results

        Raises:
            RuntimeError: If results retrieval fails
        """
        try:
            # First check if the query has completed successfully
            status = self.service.get_status(query_id)
            if not isinstance(status, SucceededQueryStatus):
                status_info = self._format_query_status(status)
                if isinstance(status, FailedQueryStatus):
                    raise RuntimeError(f"Query failed: {status.error_message}")
                elif isinstance(status, CanceledQueryStatus):
                    raise RuntimeError("Query was canceled")
                elif isinstance(status, RunningQueryStatus):
                    raise RuntimeError("Query is still running")
                else:
                    raise RuntimeError(f"Query status: {status_info['status']}")

            # Get the results
            results_bytes = self.service.get_results(query_id)
            return self._format_query_results(results_bytes, format)

        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Failed to get query results: {e}")

    def cancel_query(self, query_id: str) -> Dict[str, Any]:
        """
        Cancel a running query.

        Args:
            query_id: Query identifier

        Returns:
            Dictionary containing cancellation status

        Raises:
            RuntimeError: If cancellation fails
        """
        try:
            self.service.cancel(query_id)
            # Get updated status after cancellation
            status = self.service.get_status(query_id)
            return self._format_query_status(status)
        except Exception as e:
            raise RuntimeError(f"Failed to cancel query: {e}")

    def wait_for_completion(
        self, query_id: str, timeout: int = 300, poll_interval: int = 2
    ) -> Dict[str, Any]:
        """
        Wait for a query to complete.

        Args:
            query_id: Query identifier
            timeout: Maximum time to wait (seconds)
            poll_interval: Time between status checks (seconds)

        Returns:
            Dictionary containing final query status

        Raises:
            RuntimeError: If query fails or times out
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                status = self.service.get_status(query_id)

                if isinstance(status, SucceededQueryStatus):
                    return self._format_query_status(status)
                elif isinstance(status, FailedQueryStatus):
                    raise RuntimeError(f"Query failed: {status.error_message}")
                elif isinstance(status, CanceledQueryStatus):
                    raise RuntimeError("Query was canceled")
                elif isinstance(status, RunningQueryStatus):
                    # Still running, continue waiting
                    time.sleep(poll_interval)
                    continue
                else:
                    raise RuntimeError(f"Unknown status type: {type(status)}")

            except Exception as e:
                if isinstance(e, RuntimeError):
                    raise
                raise RuntimeError(f"Error checking query status: {e}")

        # Timeout reached
        raise RuntimeError(f"Query timed out after {timeout} seconds")

    def _wait_for_query_completion(
        self, query_id: str, timeout: int, format: str
    ) -> Dict[str, Any]:
        """
        Wait for query completion and return formatted results.

        Args:
            query_id: Query identifier
            timeout: Maximum wait time
            format: Result format

        Returns:
            Dictionary with query results
        """
        # Wait for completion
        self.wait_for_completion(query_id, timeout)

        # Get results
        return self._format_completed_query(query_id, format)

    def _format_completed_query(self, query_id: str, format: str) -> Dict[str, Any]:
        """
        Format a completed query's results.

        Args:
            query_id: Query identifier
            format: Result format

        Returns:
            Formatted query results
        """
        results_bytes = self.service.get_results(query_id)
        results = self._format_query_results(results_bytes, format)

        return {
            "query_id": query_id,
            "status": "succeeded",
            "results": results,
        }

    def _format_query_status(
        self,
        status: Union[
            RunningQueryStatus,
            SucceededQueryStatus,
            FailedQueryStatus,
            CanceledQueryStatus,
        ],
    ) -> Dict[str, Any]:
        """
        Format query status for consistent output.

        Args:
            status: Query status object

        Returns:
            Formatted status dictionary
        """
        base_info: Dict[str, Any] = {"status": status.type}

        if isinstance(status, (RunningQueryStatus, SucceededQueryStatus)):
            base_info["query_id"] = status.query_id
        elif isinstance(status, FailedQueryStatus):
            base_info["error_message"] = status.error_message

        return base_info

    def _format_query_results(self, results_bytes: bytes, format: str) -> Any:
        """
        Format query results based on the requested format.

        Args:
            results_bytes: Raw results from the API
            format: Desired output format

        Returns:
            Formatted results
        """
        if format == "raw":
            return results_bytes

        # Try to decode as text first
        try:
            results_text = results_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # If it's binary data, return as base64 or hex
            return {
                "type": "binary",
                "size_bytes": len(results_bytes),
                "data": results_bytes.hex()[:200] + "..."
                if len(results_bytes) > 100
                else results_bytes.hex(),
            }

        if format == "json":
            try:
                # Try to parse as JSON
                return json.loads(results_text)
            except json.JSONDecodeError:
                # Return as text if not valid JSON
                return {"text": results_text}

        elif format == "table":
            # For table format, we'll return structured data
            # that the formatter can convert to a table
            try:
                # Try parsing as JSON first for structured data
                data = json.loads(results_text)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    # List of dictionaries - perfect for table format
                    return data
                else:
                    return {"result": data}
            except json.JSONDecodeError:
                # Return as text data
                lines = results_text.strip().split("\n")
                if len(lines) == 1:
                    return {"result": lines[0]}
                else:
                    return {"results": lines}

        # Default: return as text
        return {"text": results_text}
