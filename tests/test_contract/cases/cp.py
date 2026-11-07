"""Contract-test cases for src/pltr/commands/cp.py (see __init__.py)."""

from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    # copy an empty folder: read the source, create the copy, list the
    # source's children (dataset copies are covered by tests/test_services/
    # test_copy.py and tests/test_commands/test_cp.py)
    "cp": [
        {"json": fs.child_resource(CONTRACT_RID, "Source", "COMPASS_FOLDER")},
        {"json": fj.folder("ri.compass.main.folder.copy", "Source-copy")},
        {"json": fs.page([])},
    ],
}

ARGS = {
    "cp": [CONTRACT_RID, CONTRACT_RID, "--recursive"],
}
