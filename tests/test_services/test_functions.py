"""Tests for FunctionsService against a real FoundryClient (only HTTP is faked).

Query.get, Query.get_by_rid, Query.execute and ValueType.get are beta: every
request must carry preview=true. The module-level filter turns the SDK's
UserWarning about a stray preview= on a GA call into a failure.
"""

import json

import pydantic
import pytest
from foundry_sdk.v2.functions.models import ExecuteQueryResponse, Query, ValueType

from pltr.services.functions import FunctionsService
from tests import foundry_json_functions as ff

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

API = "/api/v2/functions"


def test_get_query_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=ff.query())

    query = FunctionsService().get_query(ff.QUERY_API_NAME)

    assert isinstance(query, Query)
    assert (query.api_name, query.version) == (ff.QUERY_API_NAME, "1.2.0")
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/queries/{ff.QUERY_API_NAME}",
    )
    assert dict(request.url.params) == {"preview": "true"}


def test_get_query_version_options(stub_foundry_http):
    stub_foundry_http.respond(json=ff.query())

    FunctionsService().get_query(
        ff.QUERY_API_NAME,
        version="1.0.0",
        include_prerelease=True,
        latest_version_resolution="PUBLISH_TIME",
    )

    assert dict(stub_foundry_http.requests[0].url.params) == {
        "version": "1.0.0",
        "includePrerelease": "true",
        "latestVersionResolution": "PUBLISH_TIME",
        "preview": "true",
    }


def test_get_query_rejects_an_unknown_resolution(stub_foundry_http):
    with pytest.raises(pydantic.ValidationError):
        FunctionsService().get_query(
            ff.QUERY_API_NAME, latest_version_resolution="NEWEST"
        )
    assert stub_foundry_http.requests == []


def test_get_query_by_rid_passes_the_rid_as_a_query_parameter(stub_foundry_http):
    """#182: the RID used to be passed positionally; rid is keyword-only."""
    stub_foundry_http.respond(json=ff.query())

    query = FunctionsService().get_query_by_rid(
        ff.QUERY_RID, version="1.2.0", include_prerelease=True
    )

    assert query.rid == ff.QUERY_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", f"{API}/queries/getByRid")
    assert dict(request.url.params) == {
        "rid": ff.QUERY_RID,
        "version": "1.2.0",
        "includePrerelease": "true",
        "preview": "true",
    }


def test_execute_query_is_beta_and_sends_parameters(stub_foundry_http):
    stub_foundry_http.respond(json={"value": ["Acme", "Globex"]})

    response = FunctionsService().execute_query(
        ff.QUERY_API_NAME,
        parameters={"limit": 2, "region": None},
        version="1.2.0",
        include_prerelease=True,
        latest_version_resolution="SEMANTIC_VERSION",
    )

    assert isinstance(response, ExecuteQueryResponse)
    assert response.value == ["Acme", "Globex"]
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/queries/{ff.QUERY_API_NAME}/execute",
    )
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {
        "parameters": {"limit": 2, "region": None},
        "version": "1.2.0",
        "includePrerelease": True,
        "latestVersionResolution": "SEMANTIC_VERSION",
    }


def test_execute_query_with_no_options(stub_foundry_http):
    stub_foundry_http.respond(json={"value": 7})

    response = FunctionsService().execute_query(ff.QUERY_API_NAME, parameters={})

    assert response.value == 7
    assert json.loads(stub_foundry_http.requests[0].content) == {"parameters": {}}


def test_execute_query_by_rid_resolves_then_executes_that_version(stub_foundry_http):
    """#182: Query.execute_by_rid doesn't exist; resolve the RID, then execute."""
    stub_foundry_http.respond(json=ff.query(version="2.0.0"))
    stub_foundry_http.respond(json={"value": ["Acme"]})

    response = FunctionsService().execute_query_by_rid(
        ff.QUERY_RID, parameters={"limit": 1}, include_prerelease=True
    )

    assert response.value == ["Acme"]
    get_request, execute_request = stub_foundry_http.requests
    assert (get_request.method, get_request.url.path) == (
        "GET",
        f"{API}/queries/getByRid",
    )
    assert dict(get_request.url.params) == {
        "rid": ff.QUERY_RID,
        "includePrerelease": "true",
        "preview": "true",
    }
    assert (execute_request.method, execute_request.url.path) == (
        "POST",
        f"{API}/queries/{ff.QUERY_API_NAME}/execute",
    )
    assert dict(execute_request.url.params) == {"preview": "true"}
    assert json.loads(execute_request.content) == {
        "parameters": {"limit": 1},
        "version": "2.0.0",
    }


def test_execute_query_by_rid_with_a_version(stub_foundry_http):
    stub_foundry_http.respond(json=ff.query(version="1.0.0"))
    stub_foundry_http.respond(json={"value": None})

    FunctionsService().execute_query_by_rid(
        ff.QUERY_RID, parameters={}, version="1.0.0"
    )

    get_request, execute_request = stub_foundry_http.requests
    assert get_request.url.params["version"] == "1.0.0"
    assert json.loads(execute_request.content)["version"] == "1.0.0"


def test_get_value_type_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=ff.value_type())

    value_type = FunctionsService().get_value_type(ff.VALUE_TYPE_RID)

    assert isinstance(value_type, ValueType)
    assert value_type.api_name == "emailAddress"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/valueTypes/{ff.VALUE_TYPE_RID}",
    )
    assert dict(request.url.params) == {"preview": "true"}
