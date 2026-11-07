"""Contract-test cases for src/pltr/commands/widgets.py (see __init__.py)."""

from tests import foundry_json_widgets as wj
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "widgets get": [{"json": wj.widget_set(CONTRACT_RID)}],
    "widgets release list": [
        {"json": {"data": [wj.release(widget_set_rid=CONTRACT_RID)]}}
    ],
    "widgets release get": [{"json": wj.release(widget_set_rid=CONTRACT_RID)}],
    "widgets release delete": [{"status_code": 204}],
    "widgets repository get": [{"json": wj.repository(CONTRACT_RID)}],
}
