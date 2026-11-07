"""Tests for ResourceService against a real FoundryClient (only HTTP is faked).

Replaces the Mock()-based tests, which asserted calls to the nonexistent
``Resource.get_metadata`` (#182), passed ``preview=True`` to GA endpoints
(#184) and read batch responses through a ``resources`` attribute the SDK
models don't have (the field is ``data``). Every Resource endpoint pltr uses
is GA: a stray ``preview=`` would raise a UserWarning (a failure here).
"""

import json

import pytest
from foundry_sdk import NotFoundError
from foundry_sdk.v2.filesystem.models import (
    AccessRequirements,
    GetByPathResourcesBatchResponse,
    GetResourcesBatchResponse,
    Marking,
    Organization,
    Resource,
)

from pltr.services.resource import (
    ResourceService,
    normalize_resource_type,
    resource_matches,
)
from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

RID = fs.DATASET_RID
RESOURCE_PATH = f"/api/v2/filesystem/resources/{RID}"


def children_path(folder_rid: str) -> str:
    return f"/api/v2/filesystem/folders/{folder_rid}/children"


DATA = fs.child_resource(RID, "Sales Data", description="Quarterly sales")
SUBFOLDER = fs.child_resource("ri.compass.main.folder.sub", "Archive", "COMPASS_FOLDER")


# ------------------------------------------------------------------ reads


def test_get_resource(stub_foundry_http):
    stub_foundry_http.respond(json=DATA)

    resource = ResourceService().get_resource(RID)

    assert isinstance(resource, Resource)
    assert (resource.rid, resource.type) == (RID, "FOUNDRY_DATASET")
    assert resource.project_rid == fj.PROJECT_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", RESOURCE_PATH)
    assert dict(request.url.params) == {}


def test_get_resource_by_path_sends_the_path_as_query(stub_foundry_http):
    stub_foundry_http.respond(json=DATA)

    resource = ResourceService().get_resource_by_path("/Test Space/Test Project/Sales")

    assert resource.display_name == "Sales Data"
    [request] = stub_foundry_http.requests
    assert request.url.path == "/api/v2/filesystem/resources/getByPath"
    assert dict(request.url.params) == {"path": "/Test Space/Test Project/Sales"}


def test_list_children_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([DATA, SUBFOLDER], token="p2"))

    page = ResourceService().list_children(fj.PROJECT_RID, page_size=2, page_token="p1")

    assert [item.rid for item in page.data] == [RID, SUBFOLDER["rid"]]
    assert page.next_page_token == "p2"
    [request] = stub_foundry_http.requests
    assert request.url.path == children_path(fj.PROJECT_RID)
    assert dict(request.url.params) == {"pageSize": "2", "pageToken": "p1"}


def test_list_children_filters_by_type_locally(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([DATA, SUBFOLDER], token="p2"))

    page = ResourceService().list_children(
        fj.PROJECT_RID, resource_type="COMPASS_FOLDER"
    )

    assert [item.rid for item in page.data] == [SUBFOLDER["rid"]]
    assert page.next_page_token == "p2"
    assert dict(stub_foundry_http.requests[0].url.params) == {}  # no type filter


def test_get_resources_batch_reads_data_map(stub_foundry_http):
    other = "ri.foundry.main.dataset.other"
    stub_foundry_http.respond(
        json={"data": {RID: DATA, other: fs.child_resource(other, "Other")}}
    )

    response = ResourceService().get_resources_batch([RID, other])

    assert isinstance(response, GetResourcesBatchResponse)
    assert response.data[other].display_name == "Other"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/filesystem/resources/getBatch",
    )
    assert json.loads(request.content) == [{"resourceRid": RID}, {"resourceRid": other}]


def test_get_resources_by_path_batch_reads_data_list(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [DATA]})

    response = ResourceService().get_resources_by_path_batch(["/a/b", "/a/c"])

    assert isinstance(response, GetByPathResourcesBatchResponse)
    assert [item.rid for item in response.data] == [RID]
    [request] = stub_foundry_http.requests
    assert request.url.path == "/api/v2/filesystem/resources/getByPathBatch"
    assert json.loads(request.content) == [{"path": "/a/b"}, {"path": "/a/c"}]


@pytest.mark.parametrize(
    "method", ["get_resources_batch", "get_resources_by_path_batch"]
)
def test_batches_reject_more_than_1000(stub_foundry_http, method):
    values = [f"ri.foundry.main.dataset.d{i}" for i in range(1001)]

    with pytest.raises(ValueError, match="Maximum batch size is 1000"):
        getattr(ResourceService(), method)(values)

    assert stub_foundry_http.requests == []


def test_list_markings_returns_marking_ids(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([fs.MARKING_ID, "m-2"], token="p2"))

    page = ResourceService().list_markings(RID, page_size=2)

    assert page.data == [fs.MARKING_ID, "m-2"]
    assert page.next_page_token == "p2"
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{RESOURCE_PATH}/markings"
    assert dict(request.url.params) == {"pageSize": "2"}


def test_get_access_requirements(stub_foundry_http):
    stub_foundry_http.respond(json=fs.access_requirements())

    requirements = ResourceService().get_access_requirements(RID)

    assert isinstance(requirements, AccessRequirements)
    [organization] = requirements.organizations
    assert isinstance(organization, Organization)
    assert organization.organization_rid == fj.ORG_A
    [marking] = requirements.markings
    assert isinstance(marking, Marking)
    assert marking.is_directly_applied is True
    assert stub_foundry_http.requests[0].url.path == (
        f"{RESOURCE_PATH}/getAccessRequirements"
    )


# ------------------------------------------------------------------ writes


@pytest.mark.parametrize(
    "method, http_method, suffix",
    [
        ("delete_resource", "DELETE", ""),
        ("restore_resource", "POST", "/restore"),
        ("permanently_delete_resource", "POST", "/permanentlyDelete"),
    ],
)
def test_trash_operations(stub_foundry_http, method, http_method, suffix):
    stub_foundry_http.respond(204)

    assert getattr(ResourceService(), method)(RID) is None

    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (http_method, RESOURCE_PATH + suffix)
    assert dict(request.url.params) == {}


@pytest.mark.parametrize(
    "method, suffix",
    [("add_markings", "/addMarkings"), ("remove_markings", "/removeMarkings")],
)
def test_marking_operations(stub_foundry_http, method, suffix):
    stub_foundry_http.respond(204)

    getattr(ResourceService(), method)(RID, [fs.MARKING_ID, "m-2"])

    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", RESOURCE_PATH + suffix)
    assert json.loads(request.content) == {"markingIds": [fs.MARKING_ID, "m-2"]}


def test_sdk_errors_propagate_unchanged(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("ResourceNotFound", parameters={"resourceRid": RID})
    )

    with pytest.raises(NotFoundError) as excinfo:
        ResourceService().get_resource(RID)

    assert excinfo.value.name == "ResourceNotFound"


# ------------------------------------------------------------------ search


def test_search_scans_folders_breadth_first(stub_foundry_http):
    nested = fs.child_resource(
        "ri.foundry.main.dataset.nested", "old sales", parent=SUBFOLDER["rid"]
    )
    stub_foundry_http.respond(json=fs.page([DATA, SUBFOLDER], token="p2"))
    stub_foundry_http.respond(json=fs.page([]))  # second page of the start folder
    stub_foundry_http.respond(json=fs.page([nested]))

    result = ResourceService().search_resources("SALES", folder_rid=fj.PROJECT_RID)

    assert [item.rid for item in result.matches] == [RID, nested["rid"]]
    assert (result.folders_scanned, result.truncated) == (2, False)
    first, second, third = stub_foundry_http.requests
    assert first.url.path == second.url.path == children_path(fj.PROJECT_RID)
    assert second.url.params["pageToken"] == "p2"
    assert third.url.path == children_path(SUBFOLDER["rid"])


def test_search_starts_at_the_given_folder(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([]))

    result = ResourceService().search_resources("anything", fj.PROJECT_RID)

    assert result.matches == []
    [request] = stub_foundry_http.requests
    assert request.url.path == children_path(fj.PROJECT_RID)


def test_search_type_filter_still_descends_into_folders(stub_foundry_http):
    folder_named_sales = fs.child_resource(
        "ri.compass.main.folder.sales", "Sales", "COMPASS_FOLDER"
    )
    stub_foundry_http.respond(json=fs.page([folder_named_sales]))
    stub_foundry_http.respond(json=fs.page([DATA]))

    result = ResourceService().search_resources(
        "sales", folder_rid=fj.PROJECT_RID, resource_type="FOUNDRY_DATASET"
    )

    assert [item.rid for item in result.matches] == [RID]


def test_search_limit_stops_early(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([DATA, SUBFOLDER]))

    result = ResourceService().search_resources("a", folder_rid=fj.PROJECT_RID, limit=1)

    assert [item.rid for item in result.matches] == [RID]
    assert len(stub_foundry_http.requests) == 1  # never descends into Archive


def test_search_stops_at_max_folders(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([SUBFOLDER]))

    result = ResourceService().search_resources(
        "nothing-matches", folder_rid=fj.PROJECT_RID, max_folders=1
    )

    assert result.matches == []
    assert (result.folders_scanned, result.truncated) == (1, True)
    assert len(stub_foundry_http.requests) == 1


def test_search_rejects_an_empty_query(stub_foundry_http):
    with pytest.raises(ValueError, match="empty"):
        ResourceService().search_resources("  ", fj.PROJECT_RID)
    assert stub_foundry_http.requests == []


def test_resource_matches_reads_real_fields():
    resource = Resource.model_validate(DATA)

    assert resource_matches(resource, "quarterly")  # description
    assert resource_matches(resource, "test project")  # path
    assert resource_matches(resource, "foundry_dataset")  # type
    assert not resource_matches(resource, "missing")


@pytest.mark.parametrize(
    "given, expected",
    [
        ("FOUNDRY_DATASET", "FOUNDRY_DATASET"),
        ("compass_folder", "COMPASS_FOLDER"),
        ("dataset", "FOUNDRY_DATASET"),
        ("Folder", "COMPASS_FOLDER"),
        ("mio-media-set", "MIO_MEDIA_SET"),
    ],
)
def test_normalize_resource_type(given, expected):
    assert normalize_resource_type(given) == expected


def test_normalize_resource_type_rejects_unknown_types():
    with pytest.raises(ValueError):
        normalize_resource_type("spreadsheet")
