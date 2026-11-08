"""Contract-test cases for src/pltr/commands/assertions.py (see __init__.py)."""

from tests import foundry_json_dataset as dj
from tests import foundry_json_orchestration as fo
from tests.test_contract.cases import CONTRACT_RID, resource_rid

SUCCESS = {
    "assert dataset": [{"content": dj.arrow_stream({"id": [1]})}],
    "assert build": [{"json": fo.build(CONTRACT_RID)}],
    "assert objects": [{"json": {"count": 1}}],
}

ARGS = {
    # Each command needs its check.
    "assert dataset": [resource_rid("dataset"), "--min-rows", "1"],
    "assert build": [CONTRACT_RID, "--succeeded"],
    "assert objects": ["contract-test", "Employee", "--min-count", "0"],
}
