"""Contract-test cases for src/pltr/commands/orchestration.py (see __init__.py)."""

import json

from tests import foundry_json_orchestration as fo
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "orchestration builds get": [{"json": fo.build(CONTRACT_RID)}],
    "orchestration builds create": [{"json": fo.build()}],
    "orchestration builds cancel": [{"status_code": 204}],
    "orchestration builds jobs": [
        {"json": {"data": [fo.job()], "nextPageToken": "next"}}
    ],
    "orchestration builds search": [{"json": {"data": [fo.build()]}}],
    "orchestration builds get-batch": [
        {"json": {"data": {CONTRACT_RID: fo.build(CONTRACT_RID)}}}
    ],
    "orchestration jobs get": [{"json": fo.job(CONTRACT_RID)}],
    "orchestration jobs get-batch": [
        {"json": {"data": {CONTRACT_RID: fo.job(CONTRACT_RID)}}}
    ],
    "orchestration schedules get": [{"json": fo.schedule(CONTRACT_RID)}],
    "orchestration schedules create": [{"json": fo.schedule()}],
    "orchestration schedules replace": [{"json": fo.schedule(CONTRACT_RID)}],
    "orchestration schedules delete": [{"status_code": 204}],
    "orchestration schedules pause": [{"status_code": 204}],
    "orchestration schedules unpause": [{"status_code": 204}],
    "orchestration schedules run": [{"json": fo.schedule_run()}],
    "orchestration schedules runs": [{"json": {"data": [fo.schedule_run()]}}],
}

ARGS = {
    # TARGET / ACTION are JSON in the API's shape
    "orchestration builds create": [json.dumps(fo.MANUAL_TARGET)],
    "orchestration schedules create": [json.dumps({"target": fo.MANUAL_TARGET})],
    "orchestration schedules replace": [
        CONTRACT_RID,
        json.dumps({"target": fo.MANUAL_TARGET}),
    ],
    # the API requires a filter
    "orchestration builds search": ["--status", "FAILED"],
}
