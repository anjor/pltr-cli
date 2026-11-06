"""Contract-test cases for src/pltr/commands/space.py (see __init__.py)."""

from tests import foundry_json as fj
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "space create": [{"json": fj.space()}],
    "space get": [{"json": fj.space(CONTRACT_RID)}],
    "space list": [{"json": {"data": [fj.space()]}}],
    # update reads the space, then replaces it
    "space update": [
        {"json": fj.space(CONTRACT_RID)},
        {"json": fj.space(CONTRACT_RID)},
    ],
    "space delete": [{"status_code": 204}],
}

ARGS = {
    # needs at least one field to change
    "space update": [CONTRACT_RID, "--name", "Renamed"],
}
