"""Contract-test cases for src/pltr/commands/project.py (see __init__.py)."""

from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    # no --owner-id: reads the current user, then creates the project
    "project create": [{"json": fs.current_user()}, {"json": fs.project()}],
    "project get": [{"json": fs.project(CONTRACT_RID)}],
    # no --space-rid: every page of the spaces, then of each space's children
    "project list": [
        {"json": fs.page([fj.space()])},
        {"json": fs.page([fs.project_resource()])},
    ],
    # update reads the project, then replaces it
    "project update": [
        {"json": fs.project(CONTRACT_RID)},
        {"json": fs.project(CONTRACT_RID, "Renamed")},
    ],
    # delete checks that the RID is a project, then moves it to the trash
    "project delete": [{"json": fs.project(CONTRACT_RID)}, {"status_code": 204}],
    "project add-orgs": [{"status_code": 204}],
    "project remove-orgs": [{"status_code": 204}],
    "project list-orgs": [{"json": fs.page([fj.ORG_A], token="next")}],
    "project create-from-template": [{"json": fs.project()}],
}

ARGS = {
    # needs at least one field to change
    "project update": [CONTRACT_RID, "--name", "Renamed"],
}
