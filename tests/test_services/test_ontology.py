"""Tests for the ontology services against a real FoundryClient (only HTTP is faked).

Every ontology endpoint pltr uses is GA except ``OntologyObject.count``: a
stray ``preview=`` on a GA call would make the SDK emit a UserWarning, which
the module-level filter turns into a failure.
"""

import json

import pytest
from foundry_sdk.v2.ontologies.models import (
    AggregateObjectsResponseV2,
    CountObjectsResponseV2,
    ExecuteQueryResponse,
    ListOntologiesV2Response,
    ObjectTypeV2,
    OntologyV2,
    SearchObjectsResponseV2,
    SyncApplyActionResponseV2,
)

from pltr.contract import PltrError
from pltr.services.ontology import (
    ActionService,
    ObjectTypeService,
    OntologyObjectService,
    OntologyService,
    QueryService,
)
from tests import foundry_json as fj
from tests import foundry_json_ontology as fo

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

API = "/api/v2/ontologies"
OBJECTS = f"{API}/{fo.ONTOLOGY}/objects/Employee"


def body(request) -> dict:
    return json.loads(request.content)


def params(request) -> list:
    """Query parameters as (name, value) pairs (repeated names kept)."""
    return list(request.url.params.multi_items())


# --------------------------------------------------------------- ontologies


def test_list_ontologies(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.ontology()]})

    response = OntologyService().list_ontologies()

    assert isinstance(response, ListOntologiesV2Response)
    assert [o.api_name for o in response.data] == [fo.ONTOLOGY]
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", API)
    assert params(request) == []


def test_get_ontology_by_api_name(stub_foundry_http):
    stub_foundry_http.respond(json=fo.ontology())

    ontology = OntologyService().get_ontology(fo.ONTOLOGY)

    assert isinstance(ontology, OntologyV2)
    assert ontology.rid == fo.ONTOLOGY_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", f"{API}/{fo.ONTOLOGY}")


def test_get_ontology_not_found_propagates_the_sdk_error(stub_foundry_http):
    from foundry_sdk import NotFoundError

    stub_foundry_http.respond(
        404, json=fj.error("OntologyNotFound", parameters={"ontologyRid": "x"})
    )

    with pytest.raises(NotFoundError):
        OntologyService().get_ontology(fo.ONTOLOGY_RID)


# ------------------------------------------------------------- object types


def test_list_object_types_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([fo.object_type()], "page-2"))

    page = ObjectTypeService().list_object_types(
        fo.ONTOLOGY, include_datasources=True, page_size=5, page_token="page-1"
    )

    assert [ot.api_name for ot in page.data] == ["Employee"]
    assert page.next_page_token == "page-2"
    [request] = stub_foundry_http.requests  # constructing the iterator = one page
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/{fo.ONTOLOGY}/objectTypes",
    )
    assert dict(request.url.params) == {
        "includeDatasources": "true",
        "pageSize": "5",
        "pageToken": "page-1",
    }


def test_get_object_type(stub_foundry_http):
    stub_foundry_http.respond(json=fo.object_type(datasources=True))

    object_type = ObjectTypeService().get_object_type(
        fo.ONTOLOGY, "Employee", include_datasources=True
    )

    assert isinstance(object_type, ObjectTypeV2)
    assert object_type.primary_key == "employeeId"
    assert object_type.datasources[0].definition.dataset_rid == fo.DATASET_RID
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/{fo.ONTOLOGY}/objectTypes/Employee"
    assert dict(request.url.params) == {"includeDatasources": "true"}


def test_get_object_type_sends_no_optional_parameters_by_default(stub_foundry_http):
    stub_foundry_http.respond(json=fo.object_type())

    ObjectTypeService().get_object_type(fo.ONTOLOGY, "Employee")

    assert params(stub_foundry_http.requests[0]) == []


# ---------------------------------------- object/link type create (direct HTTP)

ENCODED_RID = fo.ONTOLOGY_RID  # RIDs have no characters that need URL-encoding


def create_employee_type(**kwargs):
    return ObjectTypeService().create_object_type(
        ontology_rid=fo.ONTOLOGY_RID,
        api_name="TMAircraft",
        display_name="TM Aircraft",
        primary_key="msn",
        backing_dataset=fo.DATASET_RID,
        **kwargs,
    )


def test_create_object_type_posts_to_the_first_endpoint(stub_foundry_http):
    created = {"apiName": "TMAircraft", "rid": fo.OBJECT_TYPE_RID}
    stub_foundry_http.respond(json=created)

    result = create_employee_type()

    assert result == created  # the response body, nothing added
    [request] = stub_foundry_http.requests
    assert request.method == "POST"
    assert str(request.url) == (
        f"https://test.palantirfoundry.com/v2/ontologies/{ENCODED_RID}/objectTypes"
    )
    assert request.headers["Authorization"] == "Bearer test-token"
    assert body(request) == {
        "apiName": "TMAircraft",
        "displayName": "TM Aircraft",
        "primaryKey": "msn",
        "backingDatasetRid": fo.DATASET_RID,
    }


def test_create_object_type_sends_the_description(stub_foundry_http):
    stub_foundry_http.respond(json={"apiName": "TMAircraft"})

    create_employee_type(description="Aircraft entity")

    assert body(stub_foundry_http.requests[0])["description"] == "Aircraft entity"


@pytest.mark.parametrize("status", [404, 405])
def test_create_object_type_falls_back_when_an_endpoint_is_missing(
    stub_foundry_http, status
):
    stub_foundry_http.respond(status, json=fj.error("NotFound"))
    stub_foundry_http.respond(204)  # created, empty body

    assert create_employee_type() is None

    first, second = stub_foundry_http.requests
    assert first.url.path == f"/v2/ontologies/{ENCODED_RID}/objectTypes"
    assert second.url.path == f"/v1/ontologies/{ENCODED_RID}/objectTypes"


def test_create_object_type_other_errors_fail_at_once(stub_foundry_http):
    import requests

    stub_foundry_http.respond(
        403, json=fj.error("PermissionDenied", error_code="PERMISSION_DENIED")
    )

    with pytest.raises(
        RuntimeError, match="Failed to create object type TMAircraft"
    ) as e:
        create_employee_type()

    assert isinstance(e.value.__cause__, requests.HTTPError)
    assert e.value.__cause__.response.status_code == 403
    assert len(stub_foundry_http.requests) == 1


def test_create_object_type_when_no_endpoint_exists(stub_foundry_http):
    import requests

    stub_foundry_http.respond_always(404, json=fj.error("NotFound"))

    with pytest.raises(RuntimeError, match="none of the schema endpoints") as e:
        create_employee_type()

    assert isinstance(e.value.__cause__, requests.HTTPError)
    assert [r.url.path for r in stub_foundry_http.requests] == [
        f"/v2/ontologies/{ENCODED_RID}/objectTypes",
        f"/v1/ontologies/{ENCODED_RID}/objectTypes",
        f"/ontology-manager/api/ontologies/{ENCODED_RID}/objectTypes",
    ]
    assert "/ontology-manager/api/ontologies" in str(e.value)


def test_create_object_type_non_json_response_is_an_api_error(stub_foundry_http):
    stub_foundry_http.respond(200, content=b"<html>not the API</html>")

    with pytest.raises(PltrError, match="not JSON") as e:
        create_employee_type()

    assert e.value.error_type == "api_error"
    assert e.value.exit_code == 7


def test_create_link_type_modern_payload(stub_foundry_http):
    stub_foundry_http.respond(json={"apiName": "aircraftLease"})

    result = ObjectTypeService().create_link_type(
        ontology_rid=fo.ONTOLOGY_RID,
        api_name="aircraftLease",
        from_object_type="TMAircraft",
        to_object_type="TMLeaseAgreement",
        reverse_api_name="leaseAircraft",
    )

    assert result == {"apiName": "aircraftLease"}
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/v2/ontologies/{ENCODED_RID}/linkTypes"
    assert body(request) == {
        "apiName": "aircraftLease",
        "fromObjectTypeApiName": "TMAircraft",
        "toObjectTypeApiName": "TMLeaseAgreement",
        "reverseApiName": "leaseAircraft",
    }


def test_create_link_type_fallback_uses_the_legacy_payload(stub_foundry_http):
    stub_foundry_http.respond(404, json=fj.error("NotFound"))
    stub_foundry_http.respond(json={"apiName": "aircraftLease"})

    ObjectTypeService().create_link_type(
        ontology_rid=fo.ONTOLOGY_RID,
        api_name="aircraftLease",
        from_object_type="TMAircraft",
        to_object_type="TMLeaseAgreement",
        display_name="Aircraft lease",
        description="Leases of an aircraft",
        reverse_api_name="leaseAircraft",
    )

    legacy = stub_foundry_http.requests[1]
    assert legacy.url.path == f"/v1/ontologies/{ENCODED_RID}/linkTypes"
    assert body(legacy) == {
        "apiName": "aircraftLease",
        "linkTypeApiNameAtoB": "aircraftLease",
        "aSideObjectTypeApiName": "TMAircraft",
        "bSideObjectTypeApiName": "TMLeaseAgreement",
        "displayName": "Aircraft lease",
        "description": "Leases of an aircraft",
        "linkTypeApiNameBtoA": "leaseAircraft",
    }


# ------------------------------------------------------------------ objects


def test_list_objects_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([fo.employee()], "page-2", totalCount="3"))

    page = OntologyObjectService().list_objects(
        fo.ONTOLOGY,
        "Employee",
        select=["fullName", "salary"],
        branch="feature",
        load_ontology_defined_derived_properties=False,
        page_size=20,
        page_token="page-1",
    )

    assert page.data == [fo.employee()]  # objects are plain dicts
    assert page.next_page_token == "page-2"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", OBJECTS)
    assert params(request) == [
        ("branch", "feature"),
        ("loadOntologyDefinedDerivedProperties", "false"),
        ("pageSize", "20"),
        ("pageToken", "page-1"),
        ("select", "fullName"),
        ("select", "salary"),
    ]


def test_get_object(stub_foundry_http):
    stub_foundry_http.respond(json=fo.employee())

    obj = OntologyObjectService().get_object(
        fo.ONTOLOGY,
        "Employee",
        "EMP001",
        select=["fullName"],
        scenario_rid=fo.SCENARIO_RID,
        transaction_id="txn-1",
        load_ontology_defined_derived_properties=True,
    )

    assert obj == fo.employee()
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", f"{OBJECTS}/EMP001")
    assert params(request) == [
        ("loadOntologyDefinedDerivedProperties", "true"),
        ("scenarioRid", fo.SCENARIO_RID),
        ("select", "fullName"),
        ("transactionId", "txn-1"),
    ]


def test_get_object_url_encodes_the_primary_key(stub_foundry_http):
    stub_foundry_http.respond(json=fo.employee("a/b c"))

    OntologyObjectService().get_object(fo.ONTOLOGY, "Employee", "a/b c")

    assert (
        stub_foundry_http.requests[0]
        .url.raw_path.decode()
        .endswith("/objects/Employee/a%2Fb%20c")
    )


def test_search_objects_always_sends_select(stub_foundry_http):
    stub_foundry_http.respond(json=fo.search_response([fo.employee()]))

    response = OntologyObjectService().search_objects(fo.ONTOLOGY, "Employee")

    assert isinstance(response, SearchObjectsResponseV2)
    assert response.data == [fo.employee()]
    assert response.total_count == 1
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{OBJECTS}/search")
    assert body(request) == {"select": []}  # no where: every object
    assert params(request) == []


def test_search_objects_sends_the_typed_query(stub_foundry_http):
    stub_foundry_http.respond(
        json=fo.search_response([fo.employee()], token="next", total_count=9)
    )
    where = {
        "type": "and",
        "value": [
            {"type": "eq", "field": "department", "value": "Engineering"},
            {"type": "gte", "field": "salary", "value": 100000},
        ],
    }

    response = OntologyObjectService().search_objects(
        fo.ONTOLOGY,
        "Employee",
        where=where,
        select=["fullName"],
        order_by={"fields": [{"field": "salary", "direction": "desc"}]},
        branch="feature",
        default_load_level="extractMainValue",
        load_ontology_defined_derived_properties=False,
        page_size=50,
        page_token="tok",
    )

    assert response.next_page_token == "next"
    [request] = stub_foundry_http.requests
    assert params(request) == [("branch", "feature")]
    assert body(request) == {
        "where": where,
        "orderBy": {"fields": [{"field": "salary", "direction": "desc"}]},
        "pageSize": 50,
        "pageToken": "tok",
        "select": ["fullName"],
        "defaultLoadLevel": {"type": "extractMainValue"},
        "loadOntologyDefinedDerivedProperties": False,
    }


def test_aggregate_objects(stub_foundry_http):
    stub_foundry_http.respond(json=fo.aggregate_response())
    aggregation = [
        {"type": "count", "name": "employees"},
        {"type": "avg", "field": "salary", "name": "avgSalary"},
    ]

    response = OntologyObjectService().aggregate_objects(
        fo.ONTOLOGY,
        "Employee",
        aggregation=aggregation,
        group_by=[{"type": "exact", "field": "department"}],
        where={"type": "isNull", "field": "terminationDate", "value": True},
        accuracy="ALLOW_APPROXIMATE",
        branch="feature",
    )

    assert isinstance(response, AggregateObjectsResponseV2)
    assert response.data[0].group == {"department": "Engineering"}
    assert response.data[0].metrics[1].value == 125000.5
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{OBJECTS}/aggregate")
    assert params(request) == [("branch", "feature")]
    assert body(request) == {
        "aggregation": aggregation,
        "where": {"type": "isNull", "field": "terminationDate", "value": True},
        "groupBy": [{"type": "exact", "field": "department"}],
        "accuracy": "ALLOW_APPROXIMATE",
    }


def test_aggregate_objects_without_groups_sends_an_empty_group_by(stub_foundry_http):
    stub_foundry_http.respond(json=fo.aggregate_response([]))

    OntologyObjectService().aggregate_objects(
        fo.ONTOLOGY, "Employee", aggregation=[{"type": "count"}]
    )

    assert body(stub_foundry_http.requests[0]) == {
        "aggregation": [{"type": "count"}],
        "groupBy": [],
    }


def test_count_objects_is_beta_and_returns_the_response(stub_foundry_http):
    stub_foundry_http.respond(json=fo.count_response(42))

    response = OntologyObjectService().count_objects(
        fo.ONTOLOGY, "Employee", branch="feature"
    )

    assert isinstance(response, CountObjectsResponseV2)
    assert response.count == 42
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{OBJECTS}/count")
    assert request.url.params["preview"] == "true"
    assert request.url.params["branch"] == "feature"


def test_list_linked_objects_returns_linked_object_properties(stub_foundry_http):
    linked = fo.employee("EMP002", "Jane Roe")
    stub_foundry_http.respond(json=fo.page([linked], "page-2"))

    page = OntologyObjectService().list_linked_objects(
        fo.ONTOLOGY,
        "Employee",
        "EMP001",
        "manages",
        select=["fullName"],
        page_size=10,
    )

    assert page.data == [linked]
    assert page.next_page_token == "page-2"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"{OBJECTS}/EMP001/links/manages",
    )
    assert params(request) == [("pageSize", "10"), ("select", "fullName")]


# ------------------------------------------------------------------ actions

ACTIONS = f"{API}/{fo.ONTOLOGY}/actions/transferEmployee"
PARAMETERS = {"employee": "EMP001", "newDepartment": "Sales"}


def test_apply_action_passes_parameters_by_keyword(stub_foundry_http):
    stub_foundry_http.respond(json=fo.apply_response())

    response = ActionService().apply_action(fo.ONTOLOGY, "transferEmployee", PARAMETERS)

    assert isinstance(response, SyncApplyActionResponseV2)
    assert response.operation_id == fo.OPERATION_ID
    assert response.validation.result == "VALID"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{ACTIONS}/apply")
    assert body(request) == {"parameters": PARAMETERS}  # no options by default
    assert params(request) == []
    assert "attribution" not in request.headers


def test_apply_action_options(stub_foundry_http):
    stub_foundry_http.respond(json=fo.apply_response(edits=fo.object_edits()))

    response = ActionService().apply_action(
        fo.ONTOLOGY,
        "transferEmployee",
        PARAMETERS,
        return_edits="ALL",
        attribution="pltr-tests",
        scenario_rid=fo.SCENARIO_RID,
    )

    assert response.edits.modified_objects_count == 1
    [request] = stub_foundry_http.requests
    assert body(request) == {
        "parameters": PARAMETERS,
        "options": {"returnEdits": "ALL"},
    }
    assert params(request) == [("scenarioRid", fo.SCENARIO_RID)]
    assert request.headers["attribution"] == "pltr-tests"


def test_apply_action_keeps_null_parameter_values(stub_foundry_http):
    stub_foundry_http.respond(json=fo.apply_response())

    ActionService().apply_action(
        fo.ONTOLOGY, "transferEmployee", {"employee": "EMP001", "manager": None}
    )

    assert body(stub_foundry_http.requests[0])["parameters"] == {
        "employee": "EMP001",
        "manager": None,
    }


def test_validate_action_applies_in_validate_only_mode(stub_foundry_http):
    stub_foundry_http.respond(
        json=fo.validate_response("INVALID", invalid_parameter="employee")
    )

    response = ActionService().validate_action(
        fo.ONTOLOGY, "transferEmployee", PARAMETERS
    )

    assert response.validation.result == "INVALID"
    assert response.validation.parameters["employee"].result == "INVALID"
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{ACTIONS}/apply"
    assert body(request) == {
        "parameters": PARAMETERS,
        "options": {"mode": "VALIDATE_ONLY"},
    }


def test_apply_batch_actions_passes_requests_by_keyword(stub_foundry_http):
    stub_foundry_http.respond(json=fo.batch_response(fo.object_edits(2)))
    requests = [
        {"parameters": {"employee": "EMP001"}},
        {"parameters": {"employee": "EMP002"}},
    ]

    response = ActionService().apply_batch_actions(
        fo.ONTOLOGY,
        "transferEmployee",
        requests,
        return_edits="ALL",
        scenario_rid=fo.SCENARIO_RID,
    )

    assert response.edits.modified_objects_count == 2
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{ACTIONS}/applyBatch")
    assert body(request) == {"requests": requests, "options": {"returnEdits": "ALL"}}
    assert params(request) == [("scenarioRid", fo.SCENARIO_RID)]


def test_apply_batch_actions_leaves_the_size_limit_to_foundry(stub_foundry_http):
    # Foundry allows more than 20 for some actions; pltr doesn't cap the batch.
    stub_foundry_http.respond(json=fo.batch_response())
    requests = [{"parameters": {"employee": f"EMP{i}"}} for i in range(25)]

    ActionService().apply_batch_actions(fo.ONTOLOGY, "transferEmployee", requests)

    assert len(body(stub_foundry_http.requests[0])["requests"]) == 25


# ------------------------------------------------------------------ queries


def test_execute_query(stub_foundry_http):
    stub_foundry_http.respond(json=fo.query_response([{"employeeId": "EMP001"}]))

    response = QueryService().execute_query(
        fo.ONTOLOGY, "employeesByDepartment", {"department": "Engineering"}
    )

    assert isinstance(response, ExecuteQueryResponse)
    assert response.value == [{"employeeId": "EMP001"}]
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/{fo.ONTOLOGY}/queries/employeesByDepartment/execute",
    )
    assert body(request) == {"parameters": {"department": "Engineering"}}


def test_execute_query_without_parameters_sends_an_empty_object(stub_foundry_http):
    stub_foundry_http.respond(json=fo.query_response(3))

    assert QueryService().execute_query(fo.ONTOLOGY, "headCount").value == 3
    assert body(stub_foundry_http.requests[0]) == {"parameters": {}}
