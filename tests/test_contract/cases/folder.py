"""Contract-test cases for src/pltr/commands/folder.py (see __init__.py)."""

from tests import foundry_json as fj
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "folder create": [{"json": fj.folder()}],
    "folder get": [{"json": fj.folder(CONTRACT_RID)}],
    "folder list": [
        {
            "json": {
                "data": [fj.resource("ri.compass.main.folder.child", "Child")],
                "nextPageToken": "next",
            }
        }
    ],
    "folder batch-get": [{"json": {"data": {CONTRACT_RID: fj.folder(CONTRACT_RID)}}}],
}
