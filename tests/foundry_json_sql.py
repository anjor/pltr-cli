"""Realistic Foundry SQL query API bodies for stub_foundry_http tests.

``QueryStatus`` bodies use the API's field names; query results are Apache
Arrow IPC stream bytes, as ``GET /v2/sqlQueries/{id}/getResults`` returns
them by default.
"""

import io
from typing import Any, Dict, Mapping, Union

#: An opaque query ID. Real IDs aren't URL-safe; this one needs encoding too.
QUERY_ID = "AAEC/query+0001="
#: The same ID as it appears (percent-encoded) in a request path.
QUERY_ID_IN_PATH = "AAEC%2Fquery%2B0001%3D"
DATASET_RID = "ri.foundry.main.dataset.1b2c3d4e-0000-4000-8000-000000000001"
QUERY = f"SELECT n, msg FROM `{DATASET_RID}`"


def running(query_id: str = QUERY_ID) -> Dict[str, Any]:
    """A ``RunningQueryStatus``."""
    return {"type": "running", "queryId": query_id}


def succeeded(query_id: str = QUERY_ID) -> Dict[str, Any]:
    """A ``SucceededQueryStatus``."""
    return {"type": "succeeded", "queryId": query_id}


def failed(message: str = "Column 'nope' does not exist") -> Dict[str, Any]:
    """A ``FailedQueryStatus``."""
    return {"type": "failed", "errorMessage": message}


def canceled() -> Dict[str, Any]:
    """A ``CanceledQueryStatus``."""
    return {"type": "canceled"}


def arrow_stream(table: Union[Mapping[str, Any], Any]) -> bytes:
    """Arrow IPC stream bytes for a ``pyarrow.Table`` or a column mapping."""
    import pyarrow as pa
    import pyarrow.ipc as ipc

    if isinstance(table, Mapping):
        table = pa.table(dict(table))
    buffer = io.BytesIO()
    with ipc.new_stream(buffer, table.schema) as writer:
        writer.write_table(table)
    return buffer.getvalue()


def results(table: Union[Mapping[str, Any], Any, None] = None) -> Dict[str, Any]:
    """``stub.respond`` kwargs for a getResults response (Arrow IPC stream)."""
    if table is None:
        table = {"n": [1, 2], "msg": ["hi", "there"]}
    return {
        "content": arrow_stream(table),
        "headers": {"Content-Type": "application/octet-stream"},
    }
