"""Contract-test cases for src/pltr/commands/context.py (see __init__.py)."""

from tests import foundry_json as fj
from tests import foundry_json_dataset as dj
from tests import foundry_json_ontology as oj
from tests import foundry_json_orchestration as orj
from tests.test_contract.cases import resource_rid

SUCCESS = {
    "context dataset": [
        {"json": fj.resource(resource_rid("dataset"), "sales", "FOUNDRY_DATASET")},
        {"json": dj.schema_response()},
        {"content": dj.arrow_stream({"id": [1]})},
        {"json": {"data": []}},
        {"json": {"data": [{"jobRid": orj.JOB_RID}]}},
        {"json": orj.job()},
    ],
    "context folder": [{"json": {"data": [fj.resource(fj.FOLDER_RID, "Raw")]}}],
    "context ontology": [
        {
            "json": {
                "ontology": oj.ontology(),
                "objectTypes": {},
                "actionTypes": {},
                "actionTypesFullMetadata": {},
                "queryTypes": {},
                "interfaceTypes": {},
                "sharedPropertyTypes": {},
                "valueTypes": {},
            }
        }
    ],
}
