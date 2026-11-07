"""Contract-test cases for src/pltr/commands/verify.py (see __init__.py)."""

from tests.test_auth.fakes import USER_JSON

# verify follows the contract (tests/test_commands/test_verify.py runs this
# test's own 404/400/success checks on it), but it reports which credentials
# it used, and the shared stub_foundry_http fixture fakes
# AuthManager.get_auth_context() with an object that has no `source` (only
# `base_url` and `get_token`). Under that fixture verify fails before its
# request with exit code 1. Delete this entry once the fixture's fake context
# also has `source`, `host` and `client`.
NOT_CONVERTED = {
    "verify",
}

SUCCESS = {
    "verify": [{"json": USER_JSON}],
}
