"""Realistic Foundry API JSON bodies for the dataset area's tests.

Bodies use the datasets API's own field names and value formats (RIDs that
match the SDK's RID pattern, ISO-8601 times, ``Long`` values as strings), so
the SDK decodes them into real models (``Dataset``, ``Branch``, ``File``,
``Transaction``, ``View``, ``GetDatasetSchemaResponse``, ``JobDetails``).
"""

from typing import Any, Dict, Iterable, List, Optional

DATASET_RID = "ri.foundry.main.dataset.6b2d1f0e-3a4c-4e5f-8a9b-0c1d2e3f4a5b"
OTHER_DATASET_RID = "ri.foundry.main.dataset.7c3e2a1f-4b5d-4f6a-9b0c-1d2e3f4a5b6c"
VIEW_RID = "ri.foundry.main.dataset.8d4f3b2a-5c6e-4a7b-8c1d-2e3f4a5b6c7d"
FOLDER_RID = "ri.compass.main.folder.9e5a4c3b-6d7f-4b8c-9d2e-3f4a5b6c7d8e"
TRANSACTION_RID = "ri.foundry.main.transaction.0000018b-1f2e-3d4c-5b6a-7980a1b2c3d4"
OTHER_TRANSACTION_RID = (
    "ri.foundry.main.transaction.0000018b-1f2e-3d4c-5b6a-7980a1b2c3d5"
)
BUILD_RID = "ri.foundry.main.build.1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
JOB_RID = "ri.foundry.main.job.2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e"
SCHEDULE_RID = "ri.scheduler.main.schedule.3c4d5e6f-7a8b-4c9d-0e1f-2a3b4c5d6e7f"
VERSION_ID = "4d5e6f7a-8b9c-4d0e-8f1a-2b3c4d5e6f7a"
CREATED_TIME = "2024-03-04T05:06:07Z"
CLOSED_TIME = "2024-03-04T06:07:08Z"

_TIME_KEYS = ("createdTime", "closedTime", "updatedTime")


def dataset(
    rid: str = DATASET_RID, name: str = "sales", parent_folder_rid: str = FOLDER_RID
) -> Dict[str, Any]:
    """A ``Dataset``."""
    return {"rid": rid, "name": name, "parentFolderRid": parent_folder_rid}


def branch(
    name: str = "master", transaction_rid: Optional[str] = TRANSACTION_RID
) -> Dict[str, Any]:
    """A ``Branch`` (``transactionRid`` is left out when ``None``)."""
    body: Dict[str, Any] = {"name": name}
    if transaction_rid is not None:
        body["transactionRid"] = transaction_rid
    return body


def file(
    path: str = "data/sales.csv",
    size_bytes: str = "1024",
    transaction_rid: str = TRANSACTION_RID,
    updated_time: str = CREATED_TIME,
) -> Dict[str, Any]:
    """A ``File`` (``sizeBytes`` is a Long, which the API sends as a string)."""
    return {
        "path": path,
        "transactionRid": transaction_rid,
        "sizeBytes": size_bytes,
        "updatedTime": updated_time,
    }


def transaction(
    rid: str = TRANSACTION_RID,
    transaction_type: str = "APPEND",
    status: str = "OPEN",
    closed_time: Optional[str] = None,
) -> Dict[str, Any]:
    """A ``Transaction`` (``closedTime`` only once committed or aborted)."""
    body: Dict[str, Any] = {
        "rid": rid,
        "transactionType": transaction_type,
        "status": status,
        "createdTime": CREATED_TIME,
    }
    if closed_time is not None:
        body["closedTime"] = closed_time
    return body


def field(name: str, field_type: str, nullable: bool = True, **extra: Any) -> Dict:
    """A ``DatasetFieldSchema``."""
    return {"name": name, "type": field_type, "nullable": nullable, **extra}


DEFAULT_FIELDS = [
    field("id", "LONG", nullable=False),
    field("region", "STRING"),
    field("amount", "DECIMAL", precision=10, scale=2),
    field("tags", "ARRAY", arraySubtype=field("tag", "STRING")),
]


def schema_response(
    fields: Optional[List[Dict[str, Any]]] = None,
    branch_name: str = "master",
    end_transaction_rid: str = TRANSACTION_RID,
    version_id: str = VERSION_ID,
) -> Dict[str, Any]:
    """A ``GetDatasetSchemaResponse`` (``Dataset.get_schema``/``put_schema``)."""
    return {
        "branchName": branch_name,
        "endTransactionRid": end_transaction_rid,
        "schema": {"fieldSchemaList": DEFAULT_FIELDS if fields is None else fields},
        "versionId": version_id,
    }


def backing_dataset(
    dataset_rid: str = DATASET_RID, branch_name: Optional[str] = None
) -> Dict[str, Any]:
    """A ``ViewBackingDataset``."""
    body: Dict[str, Any] = {"datasetRid": dataset_rid, "stopPropagatingMarkingIds": []}
    if branch_name is not None:
        body["branch"] = branch_name
    return body


def view(
    rid: str = VIEW_RID,
    name: str = "sales_view",
    backing: Iterable[Dict[str, Any]] = (),
    primary_key: Optional[Dict[str, Any]] = None,
    branch_name: str = "master",
) -> Dict[str, Any]:
    """A ``View``; ``backing`` defaults to one backing dataset."""
    body: Dict[str, Any] = {
        "viewName": name,
        "datasetRid": rid,
        "parentFolderRid": FOLDER_RID,
        "branch": branch_name,
        "backingDatasets": list(backing) or [backing_dataset()],
    }
    if primary_key is not None:
        body["primaryKey"] = primary_key
    return body


def job(rid: str = JOB_RID) -> Dict[str, Any]:
    """A ``JobDetails`` (the API returns only the job RID)."""
    return {"jobRid": rid}


def page(data: List[Any], next_page_token: Optional[str] = None) -> Dict[str, Any]:
    """One page of a list endpoint."""
    body: Dict[str, Any] = {"data": data}
    if next_page_token is not None:
        body["nextPageToken"] = next_page_token
    return body


def inference_response() -> Dict[str, Any]:
    """The schema-inference endpoint's response (internal API, shape assumed)."""
    return {
        "data": {
            "foundrySchema": {
                "fieldSchemaList": [{"name": "id", "type": "LONG", "nullable": True}],
                "dataFrameReaderClass": "com.palantir.foundry.spark.input.TextDataFrameReader",
                "customMetadata": {"textParserParams": {"parser": "CSV_PARSER"}},
            }
        }
    }


def metadata_response() -> Dict[str, Any]:
    """The foundry-metadata endpoint's response (internal API, shape assumed)."""
    return {"transactionRid": TRANSACTION_RID, "versionId": VERSION_ID}


def arrow_stream(columns: Dict[str, List[Any]]) -> bytes:
    """An Arrow IPC stream, as ``Dataset.read_table(format="ARROW")`` returns."""
    import pyarrow as pa

    table = pa.table(columns)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def sdk_json(body: Any) -> Any:
    """What pltr's JSON output is for ``body``: the SDK re-serializes times
    in UTC with an explicit offset (``Z`` becomes ``+00:00``)."""
    if isinstance(body, list):
        return [sdk_json(item) for item in body]
    if not isinstance(body, dict):
        return body
    result = {}
    for key, value in body.items():
        if key in _TIME_KEYS and isinstance(value, str) and value.endswith("Z"):
            value = value[:-1] + "+00:00"
        result[key] = sdk_json(value)
    return result
