"""Contract-test cases for src/pltr/commands/data_health.py (see __init__.py)."""

import json

from tests import foundry_json_data_health as fd
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "data-health check create": [{"json": fd.check()}],
    "data-health check get": [{"json": fd.check(CONTRACT_RID)}],
    "data-health check replace": [{"json": fd.check(CONTRACT_RID)}],
    "data-health check delete": [{"status_code": 204}],
    "data-health report get": [{"json": fd.check_report(CONTRACT_RID)}],
    "data-health report latest": [{"json": {"data": [fd.check_report()]}}],
}

ARGS = {
    # CONFIG is JSON in the API's shape
    "data-health check create": [json.dumps(fd.BUILD_STATUS_CONFIG)],
    "data-health check replace": [
        CONTRACT_RID,
        json.dumps(fd.REPLACE_BUILD_STATUS_CONFIG),
    ],
}
