"""Tests for SpaceService against a real FoundryClient (only HTTP is faked).

Space.create/get/replace/delete are beta: every request must carry
preview=true. Space.list is GA: passing preview= would make the SDK emit a
UserWarning, which the module-level filter turns into a failure.
"""

import json

import pytest
from foundry_sdk.v2.filesystem.models import Space

from pltr.services.space import SpaceService
from tests.foundry_json import ENROLLMENT_RID, ORG_A, ORG_B, SPACE_RID
from tests.foundry_json import USAGE_ACCOUNT_RID as USAGE_ACCOUNT
from tests.foundry_json import space as space_json

pytestmark = pytest.mark.filterwarnings("error::UserWarning")


def test_create_space_sends_required_fields_with_preview(stub_foundry_http):
    stub_foundry_http.respond(json=space_json())

    space = SpaceService().create_space(
        display_name="Test Space",
        enrollment_rid=ENROLLMENT_RID,
        organizations=[ORG_A, ORG_B],
        deletion_policy_organizations=[ORG_A],
        description="Test description",
    )

    assert isinstance(space, Space)
    assert space.rid == SPACE_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", "/api/v2/filesystem/spaces")
    assert request.url.params["preview"] == "true"
    assert json.loads(request.content) == {
        "displayName": "Test Space",
        "enrollmentRid": ENROLLMENT_RID,
        "organizations": [ORG_A, ORG_B],
        "deletionPolicyOrganizations": [ORG_A],
        "description": "Test description",
    }


def test_create_space_optional_fields(stub_foundry_http):
    stub_foundry_http.respond(json=space_json())

    SpaceService().create_space(
        display_name="Test Space",
        enrollment_rid=ENROLLMENT_RID,
        organizations=[ORG_A],
        deletion_policy_organizations=[ORG_A],
        default_role_set_id="role-set-2",
        file_system_id="fs-2",
        usage_account_rid=USAGE_ACCOUNT,
    )

    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["defaultRoleSetId"] == "role-set-2"
    assert body["fileSystemId"] == "fs-2"
    assert body["usageAccountRid"] == USAGE_ACCOUNT
    assert "description" not in body


def test_get_space_uses_preview(stub_foundry_http):
    stub_foundry_http.respond(json=space_json())

    space = SpaceService().get_space(SPACE_RID)

    assert space.organizations == [ORG_A]
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"/api/v2/filesystem/spaces/{SPACE_RID}",
    )
    assert request.url.params["preview"] == "true"


def test_list_spaces_fetches_one_page_without_preview(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [space_json(), space_json("ri.compass.main.folder.s2", "Two")]}
    )

    page = SpaceService().list_spaces(page_size=10, page_token="tok")

    assert [space.display_name for space in page.data] == ["Test Space", "Two"]
    assert page.next_page_token is None
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", "/api/v2/filesystem/spaces")
    assert dict(request.url.params) == {"pageSize": "10", "pageToken": "tok"}


def test_update_space_keeps_fields_it_does_not_change(stub_foundry_http):
    """Space.replace resets omitted fields, so current values are sent back."""
    stub_foundry_http.respond(json=space_json())
    stub_foundry_http.respond(json=space_json(name="Renamed"))

    space = SpaceService().update_space(SPACE_RID, display_name="Renamed")

    assert space.display_name == "Renamed"
    get_request, put_request = stub_foundry_http.requests
    assert (get_request.method, get_request.url.params["preview"]) == ("GET", "true")
    assert (put_request.method, put_request.url.path) == (
        "PUT",
        f"/api/v2/filesystem/spaces/{SPACE_RID}",
    )
    assert put_request.url.params["preview"] == "true"
    assert json.loads(put_request.content) == {
        "displayName": "Renamed",
        "description": "Test description",
        "defaultRoleSetId": "role-set-1",
        "usageAccountRid": USAGE_ACCOUNT,
    }


def test_update_space_description_only(stub_foundry_http):
    stub_foundry_http.respond(json=space_json())
    stub_foundry_http.respond(json=space_json(description="New"))

    SpaceService().update_space(SPACE_RID, description="New")

    body = json.loads(stub_foundry_http.requests[1].content)
    assert body["displayName"] == "Test Space"
    assert body["description"] == "New"


def test_update_space_requires_a_field(stub_foundry_http):
    with pytest.raises(ValueError, match="At least one field"):
        SpaceService().update_space(SPACE_RID)
    assert stub_foundry_http.requests == []


def test_delete_space_uses_preview(stub_foundry_http):
    stub_foundry_http.respond(204)

    assert SpaceService().delete_space(SPACE_RID) is None

    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "DELETE",
        f"/api/v2/filesystem/spaces/{SPACE_RID}",
    )
    assert request.url.params["preview"] == "true"
