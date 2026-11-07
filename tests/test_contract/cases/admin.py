"""Contract-test cases for src/pltr/commands/admin.py (see __init__.py)."""

from tests import foundry_json_admin as aj
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "admin user list": [{"json": {"data": [aj.user()]}}],
    "admin user get": [{"json": aj.user()}],
    "admin user current": [{"json": aj.user()}],
    "admin user search": [{"json": {"data": [aj.user()]}}],
    "admin user markings": [{"json": {"view": [aj.MARKING_ID]}}],
    "admin user revoke-tokens": [{"status_code": 204}],
    "admin user delete": [{"status_code": 204}],
    "admin user batch-get": [{"json": {"data": {aj.USER_ID: aj.user()}}}],
    "admin group list": [{"json": {"data": [aj.group()]}}],
    "admin group get": [{"json": aj.group()}],
    "admin group search": [{"json": {"data": [aj.group()]}}],
    "admin group create": [{"json": aj.group()}],
    "admin group delete": [{"status_code": 204}],
    "admin group batch-get": [{"json": {"data": {aj.GROUP_ID: aj.group()}}}],
    "admin role get": [{"json": aj.role()}],
    "admin role batch-get": [{"json": {"data": {aj.ROLE_ID: aj.role()}}}],
    "admin org get": [{"json": aj.organization(CONTRACT_RID)}],
    "admin org create": [{"json": aj.organization()}],
    # replace reads the organization (to keep its description and host), then
    # replaces it
    "admin org replace": [
        {"json": aj.organization(CONTRACT_RID)},
        {"json": aj.organization(CONTRACT_RID, "contract-test")},
    ],
    "admin org available-roles": [{"json": {"data": [aj.organization_role()]}}],
    "admin marking list": [{"json": {"data": [aj.marking()]}}],
    "admin marking get": [{"json": aj.marking()}],
    "admin marking batch-get": [{"json": {"data": {aj.MARKING_ID: aj.marking()}}}],
    "admin marking create": [{"json": aj.marking()}],
    # replace reads the marking (to keep its description), then replaces it
    "admin marking replace": [
        {"json": aj.marking()},
        {"json": aj.marking(name="contract-test")},
    ],
}

# User and group IDs must be UUIDs, and some commands need options the
# synthesized arguments don't provide.
ARGS = {
    "admin user get": [aj.USER_ID],
    "admin user markings": [aj.USER_ID],
    "admin user revoke-tokens": [aj.USER_ID],
    "admin user delete": [aj.USER_ID],
    "admin user batch-get": [aj.USER_ID],
    "admin group get": [aj.GROUP_ID],
    "admin group delete": [aj.GROUP_ID],
    "admin group batch-get": [aj.GROUP_ID],
    "admin group create": ["Data Science", "--organization", aj.ORG_RID],
    "admin org create": [
        "Research",
        "--enrollment-rid",
        aj.ENROLLMENT_RID,
        "--admin-id",
        aj.USER_ID,
    ],
    "admin marking create": [
        "Project X",
        "--category-id",
        aj.CATEGORY_ID,
        "--role",
        f"ADMINISTER:{aj.USER_ID}",
    ],
}
