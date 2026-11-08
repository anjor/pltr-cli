"""Contract-test cases for src/pltr/commands/streams.py (see __init__.py)."""

import json

from tests import foundry_json_streams as st
from tests.test_contract.cases import CONTRACT_RID, resource_rid

_SCHEMA = json.dumps(st.SCHEMA)

SUCCESS = {
    "streams dataset create": [{"json": st.dataset()}],
    "streams stream create": [{"json": st.stream("contract-test")}],
    "streams stream get": [{"json": st.stream("contract-test")}],
    "streams stream publish": [{"status_code": 204}],
    "streams stream publish-batch": [{"status_code": 204}],
    "streams stream reset": [{"json": st.stream("contract-test")}],
}

# --schema/--record/--records take JSON, so the synthesized values won't do.
ARGS = {
    "streams dataset create": [
        "contract-test",
        "--folder",
        CONTRACT_RID,
        "--schema",
        _SCHEMA,
    ],
    "streams stream create": [
        resource_rid("dataset"),
        "--branch",
        "contract-test",
        "--schema",
        _SCHEMA,
    ],
    "streams stream publish": [
        resource_rid("dataset"),
        "--branch",
        "contract-test",
        "--record",
        '{"id": 1}',
    ],
    "streams stream publish-batch": [
        resource_rid("dataset"),
        "--branch",
        "contract-test",
        "--records",
        '[{"id": 1}]',
    ],
}
