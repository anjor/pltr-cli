"""Realistic Foundry orchestration API JSON bodies for stub_foundry_http tests.

Bodies use the API's field names and value formats (principal IDs are UUIDs,
times are ISO-8601), so the SDK decodes them into real ``Build``, ``Job``,
``Schedule`` and ``ScheduleRun`` models.
"""

import re
from typing import Any, Dict

from tests.foundry_json import USER_ID

BUILD_RID = "ri.foundry.main.build.0b1e7c5a-1111-4000-8000-000000000001"
BUILD_RID_2 = "ri.foundry.main.build.0b1e7c5a-1111-4000-8000-000000000002"
JOB_RID = "ri.foundry.main.job.0c2f8d6b-2222-4000-8000-000000000001"
JOB_RID_2 = "ri.foundry.main.job.0c2f8d6b-2222-4000-8000-000000000002"
SCHEDULE_RID = "ri.scheduler.main.schedule.0d3a9e7c-3333-4000-8000-000000000001"
SCHEDULE_VERSION_RID = (
    "ri.scheduler.main.schedule-version.0d3a9e7c-3333-4000-8000-000000000009"
)
SCHEDULE_RUN_RID = "ri.scheduler.main.schedule-run.0e4b0f8d-4444-4000-8000-000000000001"
DATASET_RID = "ri.foundry.main.dataset.0f5c1a9e-5555-4000-8000-000000000001"
TRANSACTION_RID = "ri.foundry.main.transaction.0a6d2b0f-6666-4000-8000-000000000001"
MEDIA_SET_RID = "ri.mio.main.media-set.0b7e3c1a-7777-4000-8000-000000000001"
PROJECT_RID = "ri.compass.main.folder.0c8f4d2b-8888-4000-8000-000000000001"

MANUAL_TARGET = {"type": "manual", "targetRids": [DATASET_RID]}


def build(rid: str = BUILD_RID, **overrides: Any) -> Dict:
    """A finished ``Build``."""
    body = {
        "rid": rid,
        "branchName": "master",
        "createdTime": "2024-01-01T00:00:00Z",
        "createdBy": USER_ID,
        "fallbackBranches": ["develop"],
        "jobRids": [JOB_RID],
        "retryCount": 1,
        "retryBackoffDuration": {"value": 30, "unit": "SECONDS"},
        "abortOnFailure": False,
        "status": "SUCCEEDED",
        "finishedTime": "2024-01-01T00:10:00Z",
        "scheduleRid": SCHEDULE_RID,
    }
    body.update(overrides)
    return body


def job(rid: str = JOB_RID, **overrides: Any) -> Dict:
    """A finished ``Job`` with a dataset and a media set output."""
    body = {
        "rid": rid,
        "buildRid": BUILD_RID,
        "startedTime": "2024-01-01T00:00:05Z",
        "latestAttemptStartTime": "2024-01-01T00:00:05Z",
        "finishedTime": "2024-01-01T00:09:00Z",
        "jobStatus": "SUCCEEDED",
        "outputs": [
            {
                "type": "datasetJobOutput",
                "datasetRid": DATASET_RID,
                "outputTransactionRid": TRANSACTION_RID,
            },
            {
                "type": "transactionalMediaSetJobOutput",
                "mediaSetRid": MEDIA_SET_RID,
            },
        ],
    }
    body.update(overrides)
    return body


def schedule(rid: str = SCHEDULE_RID, **overrides: Any) -> Dict:
    """A user-scoped ``Schedule`` with a daily time trigger."""
    body = {
        "rid": rid,
        "displayName": "Nightly build",
        "description": "Builds the dataset every night",
        "currentVersionRid": SCHEDULE_VERSION_RID,
        "createdTime": "2024-01-01T00:00:00Z",
        "createdBy": USER_ID,
        "updatedTime": "2024-01-02T00:00:00Z",
        "updatedBy": USER_ID,
        "paused": False,
        "trigger": {"type": "time", "cronExpression": "0 2 * * *", "timeZone": "UTC"},
        "action": {
            "target": MANUAL_TARGET,
            "branchName": "master",
            "fallbackBranches": [],
            "forceBuild": False,
            "abortOnFailure": False,
            "notificationsEnabled": True,
        },
        "scopeMode": {"type": "user"},
    }
    body.update(overrides)
    return body


def schedule_run(
    rid: str = SCHEDULE_RUN_RID, result: Any = None, **overrides: Any
) -> Dict:
    """A ``ScheduleRun``; by default one that submitted ``BUILD_RID``."""
    body = {
        "rid": rid,
        "scheduleRid": SCHEDULE_RID,
        "scheduleVersionRid": SCHEDULE_VERSION_RID,
        "createdTime": "2024-01-03T02:00:00Z",
        "createdBy": USER_ID,
        "result": result or {"type": "submitted", "buildRid": BUILD_RID},
    }
    body.update(overrides)
    return body


_UTC_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def sdk_json(body: Any) -> Any:
    """What pltr's JSON output is for ``body``: the SDK re-serializes times
    in UTC with an explicit offset (``Z`` becomes ``+00:00``)."""
    if isinstance(body, dict):
        return {key: sdk_json(value) for key, value in body.items()}
    if isinstance(body, list):
        return [sdk_json(item) for item in body]
    if isinstance(body, str) and _UTC_TIME.match(body):
        return body[:-1] + "+00:00"
    return body
