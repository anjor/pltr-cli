"""Realistic Foundry audit API JSON bodies for stub_foundry_http tests."""

from typing import Any, Dict

ORG_RID = "ri.multipass..organization.4d2c1b0a-0000-4000-8000-000000000003"
LOG_FILE_ID = "2024-01-15T00:00:00Z-0001.json.gz"


def log_files(*ids: str, token: str = "") -> Dict[str, Any]:
    """A ``ListLogFilesResponse`` page (a ``LogFile`` has only an ``id``)."""
    body: Dict[str, Any] = {"data": [{"id": log_id} for log_id in ids]}
    if token:
        body["nextPageToken"] = token
    return body
