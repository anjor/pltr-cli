"""Realistic Foundry data health API JSON bodies for stub_foundry_http tests.

Bodies use the API's field names and value formats (principal IDs are UUIDs,
times are ISO-8601), so the SDK decodes them into real ``Check`` and
``CheckReport`` models.
"""

from typing import Any, Dict

from tests.foundry_json import USER_ID
from tests.foundry_json_orchestration import sdk_json

__all__ = ["check", "check_report", "sdk_json"]

CHECK_RID = "ri.data-health.main.check.1a2b3c4d-1111-4000-8000-000000000001"
CHECK_GROUP_RID = "ri.data-health.main.check-group.1a2b3c4d-2222-4000-8000-000000000001"
REPORT_RID = "ri.data-health.main.check-report.1a2b3c4d-3333-4000-8000-000000000001"
REPORT_RID_2 = "ri.data-health.main.check-report.1a2b3c4d-3333-4000-8000-000000000002"
DATASET_RID = "ri.foundry.main.dataset.1a2b3c4d-4444-4000-8000-000000000001"

#: A ``buildStatus`` check configuration (create shape, with its subject).
BUILD_STATUS_CONFIG = {
    "type": "buildStatus",
    "subject": {"datasetRid": DATASET_RID, "branchId": "master"},
    "statusCheckConfig": {"severity": "MODERATE"},
}

#: The same check's configuration in the replace shape (no subject).
REPLACE_BUILD_STATUS_CONFIG = {
    "type": "buildStatus",
    "statusCheckConfig": {"severity": "CRITICAL"},
}


def check(rid: str = CHECK_RID, **overrides: Any) -> Dict:
    """A ``buildStatus`` ``Check``."""
    body = {
        "rid": rid,
        "groups": [CHECK_GROUP_RID],
        "config": BUILD_STATUS_CONFIG,
        "intent": "Monitor production builds",
        "createdBy": USER_ID,
        "updatedTime": "2024-01-02T00:00:00Z",
    }
    body.update(overrides)
    return body


def check_report(
    rid: str = REPORT_RID,
    status: str = "FAILED",
    message: Any = "The latest build failed",
    **overrides: Any,
) -> Dict:
    """A ``CheckReport`` with a snapshot of :func:`check`."""
    result: Dict[str, Any] = {"status": status}
    if message is not None:
        result["message"] = message
    body = {
        "rid": rid,
        "check": check(),
        "result": result,
        "createdTime": "2024-01-03T00:00:00Z",
    }
    body.update(overrides)
    return body
