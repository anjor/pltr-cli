"""
SQL service wrapper for Foundry SQL queries (``client.sql_queries.SqlQuery``).

The endpoints pltr uses (``execute``, ``get_status``, ``get_results`` and
``cancel``) are GA, so they are called without ``preview``. Methods return
SDK models unchanged and let SDK exceptions propagate so the error layer can
classify them. Query results are decoded into a ``pyarrow.Table``: the API
serializes them as an Apache Arrow IPC stream unless the query was executed
with ``serializationFormat`` CSV.
"""

import time
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from foundry_sdk.v2.sql_queries.models import (
    CanceledQueryStatus,
    FailedQueryStatus,
    RunningQueryStatus,
    SucceededQueryStatus,
)

from ..contract import ExitCode, PltrError
from .base import BaseService

if TYPE_CHECKING:
    import pyarrow

#: Seconds between status checks while waiting for a query to finish.
POLL_INTERVAL = 2.0

#: First bytes of an Arrow IPC stream (the continuation marker) and file.
_ARROW_STREAM_MARKER = b"\xff\xff\xff\xff"
_ARROW_FILE_MAGIC = b"ARROW1"


class QueryNotSucceeded(PltrError):
    """A query finished without results: it failed or was canceled.

    Exit code 7, like the API's own ``QueryFailed`` error for the same state.
    """

    error_type = "api_error"
    exit_code = ExitCode.API


def query_id_of(status: Any) -> Optional[str]:
    """The query ID in a ``QueryStatus`` (failed/canceled statuses have none)."""
    if isinstance(status, (RunningQueryStatus, SucceededQueryStatus)):
        return status.query_id
    return None


def check_not_failed(status: Any, query_id: Optional[str] = None) -> Any:
    """Return ``status`` unless the query failed or was canceled.

    Raises:
        QueryNotSucceeded: for a ``FailedQueryStatus`` (with the API's error
            message) or a ``CanceledQueryStatus``.
    """
    label = f"Query {query_id}" if query_id else "The query"
    if isinstance(status, FailedQueryStatus):
        raise QueryNotSucceeded(f"{label} failed: {status.error_message}")
    if isinstance(status, CanceledQueryStatus):
        raise QueryNotSucceeded(f"{label} was canceled.")
    return status


def decode_results(data: Optional[bytes]) -> "pyarrow.Table":
    """Decode the bytes of ``SqlQuery.get_results`` into a ``pyarrow.Table``.

    Handles an Arrow IPC stream (the API's default), an Arrow IPC file and
    CSV (``serializationFormat`` CSV). An empty response is an empty table.

    Raises:
        PltrError: if the bytes can't be decoded.
    """
    import pyarrow as pa
    import pyarrow.csv as pa_csv
    import pyarrow.ipc as pa_ipc

    if not data:
        return pa.table({})
    buffer = pa.py_buffer(data)
    head = bytes(data[:8])
    try:
        if head.startswith(_ARROW_STREAM_MARKER):
            return pa_ipc.open_stream(buffer).read_all()
        if head.startswith(_ARROW_FILE_MAGIC):
            return pa_ipc.open_file(buffer).read_all()
        return pa_csv.read_csv(pa.BufferReader(buffer))
    except (pa.ArrowException, ValueError) as exc:
        raise PltrError(
            f"Could not decode the query results ({len(data)} bytes): {exc}"
        ) from exc


class SqlService(BaseService):
    """Service wrapper for Foundry SQL queries (``client.sql_queries``)."""

    def _get_service(self) -> Any:
        """Get the Foundry SQL query client."""
        return self.client.sql_queries.SqlQuery

    def submit_query(
        self, query: str, *, fallback_branch_ids: Optional[List[str]] = None
    ) -> Any:
        """Start a query (``SqlQuery.execute``, GA); returns its ``QueryStatus``.

        The status is ``RunningQueryStatus`` or ``SucceededQueryStatus`` (both
        carry the query ID), or ``FailedQueryStatus``/``CanceledQueryStatus``.
        """
        return self.service.execute(
            query=query, fallback_branch_ids=fallback_branch_ids
        )

    def get_query_status(self, query_id: str) -> Any:
        """Get a query's ``QueryStatus`` (``SqlQuery.get_status``, GA)."""
        return self.service.get_status(query_id)

    def cancel_query(self, query_id: str) -> None:
        """Cancel a query (``SqlQuery.cancel``, GA); a no-op if it has finished."""
        self.service.cancel(query_id)

    def get_query_results(self, query_id: str) -> "pyarrow.Table":
        """Get a finished query's results (``SqlQuery.get_results``, GA).

        The API long-polls: while the query is still running the request waits
        up to a minute, then fails with ``QueryRunning``. A failed or canceled
        query fails with ``QueryFailed``/``QueryCanceled``.
        """
        return decode_results(self.service.get_results(query_id))

    def wait_for_query(
        self, query_id: str, *, timeout: float, status: Any = None
    ) -> Any:
        """Poll ``SqlQuery.get_status`` (GA) until the query has finished.

        Args:
            query_id: The query to wait for.
            timeout: Seconds to wait while the query is running.
            status: The query's current status, if already known (saves one
                ``get_status`` call).

        Returns:
            The ``SucceededQueryStatus``.

        Raises:
            QueryNotSucceeded: the query failed or was canceled.
            PltrError: (``timeout``, exit code 7) the query was still running
                after ``timeout`` seconds; it keeps running.
        """
        deadline = time.monotonic() + timeout
        if status is None:
            status = self.service.get_status(query_id)
        while isinstance(status, RunningQueryStatus):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PltrError(
                    f"Query {query_id} is still running after {timeout:g} seconds.",
                    error_type="timeout",
                    exit_code=ExitCode.API,
                    hint=(
                        f"It keeps running: wait again with 'pltr sql wait {query_id}', "
                        f"or stop it with 'pltr sql cancel {query_id}'."
                    ),
                )
            time.sleep(min(POLL_INTERVAL, remaining))
            status = self.service.get_status(query_id)
        return check_not_failed(status, query_id)

    def execute_query(
        self,
        query: str,
        *,
        fallback_branch_ids: Optional[List[str]] = None,
        timeout: float = 300,
    ) -> Tuple[str, "pyarrow.Table"]:
        """Run a query, wait for it and return ``(query ID, results table)``.

        Calls ``SqlQuery.execute``, then ``get_status`` while the query runs,
        then ``get_results`` (all GA).

        Raises:
            QueryNotSucceeded: the query failed or was canceled.
            PltrError: (``timeout``) the query didn't finish within ``timeout``.
        """
        status = self.submit_query(query, fallback_branch_ids=fallback_branch_ids)
        query_id = query_id_of(check_not_failed(status))
        if query_id is None:  # not a status type this SDK version knows
            raise PltrError(f"Unexpected query status: {status!r}")
        self.wait_for_query(query_id, timeout=timeout, status=status)
        return query_id, self.get_query_results(query_id)
