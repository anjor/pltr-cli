"""Contract-test cases for src/pltr/commands/resource.py (see __init__.py)."""

from tests import foundry_json_filesystem as fs
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "resource get": [{"json": fs.child_resource(CONTRACT_RID, "Data")}],
    "resource get-by-path": [{"json": fs.child_resource(fs.DATASET_RID, "Data")}],
    "resource list": [
        {"json": fs.page([fs.child_resource(fs.DATASET_RID, "Data")], token="next")}
    ],
    # the synthesized query is "contract-test"; a dataset (not a folder) matches
    # it, so the scan reads only the start folder
    "resource search": [
        {"json": fs.page([fs.child_resource(fs.DATASET_RID, "contract-test data")])}
    ],
    "resource batch-get": [
        {"json": {"data": {CONTRACT_RID: fs.child_resource(CONTRACT_RID, "Data")}}}
    ],
    "resource batch-get-by-path": [
        {"json": {"data": [fs.child_resource(fs.DATASET_RID, "contract-test")]}}
    ],
    "resource delete": [{"status_code": 204}],
    "resource restore": [{"status_code": 204}],
    "resource permanently-delete": [{"status_code": 204}],
    "resource add-markings": [{"status_code": 204}],
    "resource remove-markings": [{"status_code": 204}],
    "resource list-markings": [{"json": fs.page([fs.MARKING_ID])}],
    "resource access-requirements": [{"json": fs.access_requirements()}],
}
