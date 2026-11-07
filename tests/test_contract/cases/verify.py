"""Contract-test cases for src/pltr/commands/verify.py (see __init__.py)."""

from tests.test_auth.fakes import USER_JSON

SUCCESS = {
    "verify": [{"json": USER_JSON}],
}
