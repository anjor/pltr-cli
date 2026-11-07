"""Contract-test cases for src/pltr/commands/functions.py (see __init__.py)."""

from tests import foundry_json_functions as ff
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "functions query get": [{"json": ff.query()}],
    "functions query get-by-rid": [{"json": ff.query()}],
    "functions query execute": [{"json": {"value": [{"name": "Acme"}]}}],
    # resolves the RID, then executes the version it found
    "functions query execute-by-rid": [
        {"json": ff.query()},
        {"json": {"value": 42}},
    ],
    "functions value-type get": [{"json": ff.value_type(CONTRACT_RID)}],
}
