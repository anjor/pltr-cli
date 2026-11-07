"""Realistic Foundry streams API bodies for stub_foundry_http tests."""

from typing import Any, Dict

DATASET_RID = "ri.foundry.main.dataset.5c1d2e3f-0000-4000-8000-000000000002"
FOLDER_RID = "ri.compass.main.folder.8a9b0c1d-0000-4000-8000-000000000003"
VIEW_RID = "ri.foundry-streaming.main.view.0d1e2f3a-0000-4000-8000-000000000004"

#: A ``StreamSchema`` in the API's JSON shape.
SCHEMA: Dict[str, Any] = {
    "fields": [
        {"name": "id", "schema": {"nullable": False, "dataType": {"type": "long"}}},
        {
            "name": "value",
            "schema": {"nullable": True, "dataType": {"type": "string"}},
        },
    ],
    "keyFieldNames": ["id"],
}


def dataset(rid: str = DATASET_RID, name: str = "sensor-data") -> Dict[str, Any]:
    """A ``streams.models.Dataset``."""
    return {"rid": rid, "name": name, "parentFolderRid": FOLDER_RID}


def stream(branch: str = "master", **overrides: Any) -> Dict[str, Any]:
    """A ``Stream``."""
    body: Dict[str, Any] = {
        "branchName": branch,
        "schema": SCHEMA,
        "viewRid": VIEW_RID,
        "partitionsCount": 1,
        "streamType": "LOW_LATENCY",
        "compressed": False,
    }
    body.update(overrides)
    return body


def stream_not_found(branch: str = "master") -> Dict[str, Any]:
    """A ``StreamNotFound`` error body (404)."""
    return {
        "errorCode": "NOT_FOUND",
        "errorName": "StreamNotFound",
        "errorInstanceId": "00000000-0000-4000-8000-0000000000e2",
        "parameters": {"datasetRid": DATASET_RID, "streamBranchName": branch},
    }
