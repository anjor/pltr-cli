"""Contract-test cases for src/pltr/commands/models.py (see __init__.py)."""

from tests import foundry_json_models as fm
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "models model create": [{"json": fm.model()}],
    "models model get": [{"json": fm.model(CONTRACT_RID)}],
    "models version get": [{"json": fm.model_version(CONTRACT_RID)}],
    "models version list": [
        {"json": {"data": [fm.model_version()], "nextPageToken": "next"}}
    ],
}
