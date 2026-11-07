"""Contract-test cases for src/pltr/commands/third_party_applications.py (see __init__.py)."""

from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "third-party-apps get": [{"json": {"rid": CONTRACT_RID}}],
}
