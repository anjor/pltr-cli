"""Contract-test cases for src/pltr/commands/cp.py (see __init__.py)."""

from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs
from tests.test_contract.cases import CONTRACT_RID

#: The folder the success case copies into (cp refuses to copy a folder into
#: itself, so it can't be CONTRACT_RID).
TARGET_RID = "ri.compass.main.folder.contract-target"

SUCCESS = {
    # copy an empty folder: read the source, read the target (it must not be
    # inside the source), create the copy, list the source's children
    # (dataset copies are covered by tests/test_services/test_copy.py and
    # tests/test_commands/test_cp.py)
    "cp": [
        {"json": fs.child_resource(CONTRACT_RID, "Source", "COMPASS_FOLDER")},
        {"json": fs.child_resource(TARGET_RID, "Target", "COMPASS_FOLDER")},
        {"json": fj.folder("ri.compass.main.folder.copy", "Source-copy")},
        {"json": fs.page([])},
    ],
}

ARGS = {
    "cp": [CONTRACT_RID, TARGET_RID, "--recursive"],
}
