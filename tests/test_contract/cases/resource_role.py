"""Contract-test cases for src/pltr/commands/resource_role.py (see __init__.py)."""

from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "resource-role grant": [{"status_code": 204}],
    "resource-role revoke": [{"status_code": 204}],
    "resource-role list": [
        {"json": fs.page([fs.user_role(), fs.everyone_role()], token="next")}
    ],
}

ARGS = {
    # --principal-id (a UUID) or --everyone is required, and --role
    "resource-role grant": [
        CONTRACT_RID,
        "--principal-id",
        fj.USER_ID,
        "--role",
        "compass:read",
    ],
    "resource-role revoke": [
        CONTRACT_RID,
        "--principal-id",
        fj.USER_ID,
        "--role",
        "compass:read",
    ],
}
