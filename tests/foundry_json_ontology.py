"""Realistic Foundry API JSON bodies for the ontology area (stub_foundry_http tests).

Bodies use the API's own field names and value formats (camelCase, RIDs that
match the SDK's RID pattern), so the SDK decodes them into real models.
"""

from typing import Any, Dict, List, Optional

ONTOLOGY_RID = "ri.ontology.main.ontology.c61d9ab5-2919-4127-a0a1-ac64c0ce6367"
ONTOLOGY = "hr-ontology"  # the ontology's API name
OBJECT_TYPE_RID = "ri.ontology.main.object-type.0381eda6-69bb-4cb7-8ba0-c6158e094a04"
DATASOURCE_RID = "ri.ontology.main.datasource.5b1fda76-0b6c-4ae8-8a0d-2b2ff5c5c2a6"
DATASET_RID = "ri.foundry.main.dataset.e4b7c3a2-1d0f-4f5e-9a8b-7c6d5e4f3a2b"
OPERATION_ID = "ri.actions.main.action.7a3b6e5c-1f2d-4c8e-9b0a-6d5e4c3b2a19"
SCENARIO_RID = "ri.ontology.main.scenario.2c4e6a8b-0d1f-4a3c-8e5b-7d9f1b3d5f7a"


def ontology(
    rid: str = ONTOLOGY_RID,
    api_name: str = ONTOLOGY,
    display_name: str = "HR Ontology",
) -> Dict[str, Any]:
    """An ``OntologyV2``."""
    return {
        "apiName": api_name,
        "displayName": display_name,
        "description": "People and departments",
        "rid": rid,
    }


def _property(name: str, data_type: str) -> Dict[str, Any]:
    return {
        "displayName": name.title(),
        "dataType": {"type": data_type},
        "rid": f"ri.ontology.main.property.{name.lower()}-0b1c",
        "visibility": "NORMAL",
    }


def object_type(
    api_name: str = "Employee",
    *,
    datasources: bool = False,
    **overrides: Any,
) -> Dict[str, Any]:
    """An ``ObjectTypeV2``, optionally with its datasources."""
    body: Dict[str, Any] = {
        "apiName": api_name,
        "displayName": api_name,
        "pluralDisplayName": f"{api_name}s",
        "status": "ACTIVE",
        "description": f"A {api_name.lower()} of the company",
        "icon": {"type": "blueprint", "name": "person", "color": "#4C90F0"},
        "primaryKey": "employeeId",
        "titleProperty": "fullName",
        "visibility": "NORMAL",
        "rid": OBJECT_TYPE_RID,
        "properties": {
            "employeeId": _property("employeeId", "string"),
            "fullName": _property("fullName", "string"),
            "salary": _property("salary", "double"),
        },
    }
    if datasources:
        body["datasources"] = [
            {
                "rid": DATASOURCE_RID,
                "definition": {
                    "type": "dataset",
                    "datasetRid": DATASET_RID,
                    "propertyMapping": {
                        "employeeId": {"type": "column", "column": "employee_id"}
                    },
                },
            }
        ]
    body.update(overrides)
    return body


def employee(
    primary_key: str = "EMP001",
    name: str = "Jane Doe",
    department: str = "Engineering",
    salary: float = 120000,
) -> Dict[str, Any]:
    """An ontology object as the API returns it: a dict of property values."""
    return {
        "__rid": f"ri.phonograph2-objects.main.object.{primary_key.lower()}",
        "__primaryKey": primary_key,
        "__apiName": "Employee",
        "employeeId": primary_key,
        "fullName": name,
        "department": department,
        "salary": salary,
    }


def page(items: List[Any], token: Optional[str] = None, **extra: Any) -> Dict[str, Any]:
    """A paged list response (``{"data": [...], "nextPageToken": ...}``)."""
    body: Dict[str, Any] = {"data": list(items)}
    if token:
        body["nextPageToken"] = token
    body.update(extra)
    return body


def search_response(
    items: List[Any], token: Optional[str] = None, total_count: Optional[int] = None
) -> Dict[str, Any]:
    """A ``SearchObjectsResponseV2``.

    ``totalCount`` is a Foundry ``Long``, a string on the wire (and in the
    SDK's JSON serialization).
    """
    total = len(items) if total_count is None else total_count
    return page(items, token, totalCount=str(total))


def aggregate_response(
    groups: Optional[List[Dict[str, Any]]] = None, accuracy: str = "ACCURATE"
) -> Dict[str, Any]:
    """An ``AggregateObjectsResponseV2`` (head count and average salary per department)."""
    if groups is None:
        groups = [
            {
                "group": {"department": "Engineering"},
                "metrics": [
                    {"name": "employees", "value": 12},
                    {"name": "avgSalary", "value": 125000.5},
                ],
            },
            {
                "group": {"department": "Sales"},
                "metrics": [
                    {"name": "employees", "value": 7},
                    {"name": "avgSalary", "value": 98000.0},
                ],
            },
        ]
    return {"accuracy": accuracy, "data": groups}


def count_response(count: int = 42) -> Dict[str, Any]:
    """A ``CountObjectsResponseV2``."""
    return {"count": count}


def validation(result: str = "VALID", invalid_parameter: Optional[str] = None) -> Dict:
    """A ``ValidateActionResponseV2``."""
    parameters: Dict[str, Any] = {
        "employee": {"result": "VALID", "evaluatedConstraints": [], "required": True},
        "newDepartment": {
            "result": "VALID",
            "evaluatedConstraints": [],
            "required": True,
        },
    }
    criteria: List[Dict[str, Any]] = [{"result": "VALID"}]
    if invalid_parameter:
        parameters[invalid_parameter] = {
            "result": "INVALID",
            "evaluatedConstraints": [{"type": "range", "gte": 1}],
            "required": True,
        }
    if result == "INVALID" and not invalid_parameter:
        criteria = [
            {
                "result": "INVALID",
                "configuredFailureMessage": "Only managers may do this",
            }
        ]
    return {"result": result, "submissionCriteria": criteria, "parameters": parameters}


def object_edits(modified: int = 1) -> Dict[str, Any]:
    """An ``ObjectEdits`` (the ``edits`` of an apply response)."""
    return {
        "type": "edits",
        "edits": [
            {
                "type": "modifyObject",
                "primaryKey": f"EMP00{i + 1}",
                "objectType": "Employee",
            }
            for i in range(modified)
        ],
        "addedObjectCount": 0,
        "modifiedObjectsCount": modified,
        "deletedObjectsCount": 0,
        "addedLinksCount": 0,
        "deletedLinksCount": 0,
    }


def apply_response(
    *, with_validation: bool = True, edits: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """A ``SyncApplyActionResponseV2``."""
    body: Dict[str, Any] = {"operationId": OPERATION_ID}
    if with_validation:
        body["validation"] = validation()
    if edits is not None:
        body["edits"] = edits
    return body


def validate_response(result: str = "VALID", **kwargs: Any) -> Dict[str, Any]:
    """A ``SyncApplyActionResponseV2`` of a VALIDATE_ONLY apply."""
    return {"validation": validation(result, **kwargs)}


def batch_response(edits: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A ``BatchApplyActionResponseV2``."""
    return {} if edits is None else {"edits": edits}


def query_response(value: Any) -> Dict[str, Any]:
    """An ``ExecuteQueryResponse``."""
    return {"value": value}
