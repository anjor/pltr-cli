"""Contract-test cases for src/pltr/commands/aip_agents.py (see __init__.py)."""

from tests import foundry_json_aip_agents as aj
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "aip-agents get": [{"json": aj.agent(CONTRACT_RID)}],
    "aip-agents sessions list": [{"json": {"data": [aj.session()]}}],
    "aip-agents sessions get": [{"json": aj.session(CONTRACT_RID)}],
    "aip-agents versions list": [{"json": {"data": [aj.agent_version()]}}],
}
