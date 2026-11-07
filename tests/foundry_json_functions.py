"""Realistic Foundry Functions API JSON bodies for stub_foundry_http tests.

Bodies use the API's field names and value formats, so the SDK decodes them
into real ``Query``, ``ExecuteQueryResponse`` and ``ValueType`` models.
"""

from typing import Any, Dict

from tests.foundry_json_orchestration import sdk_json

__all__ = ["query", "value_type", "sdk_json"]

QUERY_API_NAME = "getTopCustomers"
QUERY_RID = "ri.function-registry.main.function.2b3c4d5e-1111-4000-8000-000000000001"
VALUE_TYPE_RID = (
    "ri.ontology-metadata.main.value-type.2b3c4d5e-2222-4000-8000-000000000001"
)
VALUE_TYPE_VERSION_ID = "2b3c4d5e-3333-4000-8000-000000000001"


def query(
    api_name: str = QUERY_API_NAME, version: str = "1.2.0", **overrides: Any
) -> Dict:
    """A ``Query`` with a required and an optional parameter."""
    body = {
        "apiName": api_name,
        "displayName": "Get top customers",
        "description": "The customers with the highest revenue",
        "parameters": {
            "limit": {
                "description": "How many customers to return",
                "dataType": {"type": "integer"},
                "required": True,
            },
            "region": {"dataType": {"type": "string"}, "required": False},
        },
        "output": {"type": "array", "subType": {"type": "string"}},
        "rid": QUERY_RID,
        "version": version,
    }
    body.update(overrides)
    return body


def value_type(rid: str = VALUE_TYPE_RID, **overrides: Any) -> Dict:
    """A string ``ValueType`` with a regex constraint."""
    body = {
        "rid": rid,
        "version": "1.0.0",
        "versionId": VALUE_TYPE_VERSION_ID,
        "apiName": "emailAddress",
        "displayName": "Email address",
        "description": "An email address",
        "baseType": {"type": "string"},
        "constraints": [
            {"type": "regex", "pattern": "^[^@]+@[^@]+$", "partialMatch": False}
        ],
    }
    body.update(overrides)
    return body
