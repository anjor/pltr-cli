"""Contract-test cases for src/pltr/commands/ontology.py (see __init__.py)."""

import json

from tests import foundry_json_ontology as fo
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "ontology list": [{"json": {"data": [fo.ontology()]}}],
    "ontology get": [{"json": fo.ontology(CONTRACT_RID)}],
    "ontology object-type-list": [
        {"json": fo.page([fo.object_type()], "next")},
    ],
    "ontology object-type-get": [{"json": fo.object_type(datasources=True)}],
    "ontology object-list": [
        {"json": fo.page([fo.employee()], "next", totalCount="2")},
    ],
    "ontology object-get": [{"json": fo.employee()}],
    "ontology object-search": [
        {"json": fo.search_response([fo.employee()], "next", total_count=2)},
    ],
    "ontology object-aggregate": [{"json": fo.aggregate_response()}],
    "ontology object-count": [{"json": fo.count_response()}],
    "ontology object-linked": [{"json": fo.page([fo.employee("EMP002")])}],
    "ontology action-apply": [
        {"json": fo.apply_response(edits=fo.object_edits())},
    ],
    "ontology action-validate": [{"json": fo.validate_response()}],
    "ontology action-apply-batch": [{"json": fo.batch_response(fo.object_edits(2))}],
    "ontology query-execute": [{"json": fo.query_response([{"employeeId": "EMP001"}])}],
}

_PARAMETERS = json.dumps({"employee": "EMP001"})

ARGS = {
    # --aggregation isn't click-required (a deprecated positional can stand
    # in for it), so it isn't synthesized
    "ontology object-aggregate": [
        fo.ONTOLOGY,
        "Employee",
        "--aggregation",
        '[{"type": "count"}]',
        "--group-by",
        "department",
    ],
    # PARAMETERS / REQUESTS must be JSON
    "ontology action-apply": [fo.ONTOLOGY, "transferEmployee", _PARAMETERS],
    "ontology action-validate": [fo.ONTOLOGY, "transferEmployee", _PARAMETERS],
    "ontology action-apply-batch": [
        fo.ONTOLOGY,
        "transferEmployee",
        json.dumps([{"parameters": {"employee": "EMP001"}}]),
    ],
}
