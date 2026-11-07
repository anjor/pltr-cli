"""Tests for ResourceRoleService against a real FoundryClient (only HTTP is faked).

The previous Mock()-based tests asserted calls to ``filesystem.ResourceRole``,
which doesn't exist in the SDK (#182); these assert the real
``Resource.Role.add/remove/list`` requests instead. Every endpoint is GA, so a
stray ``preview=`` would raise a UserWarning (turned into a failure here).
"""

import json

import pytest
from foundry_sdk import NotFoundError
from foundry_sdk.v2.filesystem.models import Everyone, PrincipalWithId, ResourceRole

from pltr.services.resource_role import ResourceRoleService, role_identifier
from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

RID = fs.DATASET_RID
ROLES_PATH = f"/api/v2/filesystem/resources/{RID}/roles"


def test_grant_role_to_a_principal_posts_a_role_identifier(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = ResourceRoleService().grant_role(
        RID, "compass:read", principal_id=fj.USER_ID
    )

    assert result is None
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{ROLES_PATH}/add")
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {
        "roles": [
            {
                "resourceRolePrincipal": {
                    "type": "principalIdOnly",
                    "principalId": fj.USER_ID,
                },
                "roleId": "compass:read",
            }
        ]
    }


def test_grant_role_to_everyone(stub_foundry_http):
    stub_foundry_http.respond(204)

    ResourceRoleService().grant_role(RID, "compass:discover")

    body = json.loads(stub_foundry_http.requests[0].content)
    assert body == {
        "roles": [
            {
                "resourceRolePrincipal": {"type": "everyone"},
                "roleId": "compass:discover",
            }
        ]
    }


def test_revoke_role_posts_to_remove(stub_foundry_http):
    stub_foundry_http.respond(204)

    ResourceRoleService().revoke_role(RID, "compass:edit", principal_id=fs.GROUP_ID)

    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{ROLES_PATH}/remove")
    assert json.loads(request.content)["roles"][0] == {
        "resourceRolePrincipal": {
            "type": "principalIdOnly",
            "principalId": fs.GROUP_ID,
        },
        "roleId": "compass:edit",
    }


def test_list_roles_fetches_one_page_and_decodes_principals(stub_foundry_http):
    stub_foundry_http.respond(
        json=fs.page(
            [fs.user_role(), fs.group_role(), fs.everyone_role()], token="page-2"
        )
    )

    page = ResourceRoleService().list_roles(
        RID, include_inherited=True, page_size=3, page_token="page-1"
    )

    assert all(isinstance(role, ResourceRole) for role in page.data)
    user, group, everyone = page.data
    assert isinstance(user.resource_role_principal, PrincipalWithId)
    assert user.resource_role_principal.principal_type == "USER"
    assert group.resource_role_principal.principal_id == fs.GROUP_ID
    assert isinstance(everyone.resource_role_principal, Everyone)
    assert everyone.role_id == "compass:discover"
    assert page.next_page_token == "page-2"
    [request] = stub_foundry_http.requests  # constructing the iterator = one page
    assert (request.method, request.url.path) == ("GET", ROLES_PATH)
    assert dict(request.url.params) == {
        "includeInherited": "true",
        "pageSize": "3",
        "pageToken": "page-1",
    }


def test_list_roles_sends_no_optional_parameters_by_default(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([]))

    ResourceRoleService().list_roles(RID)

    assert dict(stub_foundry_http.requests[0].url.params) == {}


def test_role_identifier_validates_the_principal_id():
    with pytest.raises(ValueError):  # pydantic: a principal ID is a UUID
        role_identifier("compass:read", "john.doe")


def test_sdk_errors_propagate_unchanged(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("ResourceNotFound", parameters={"resourceRid": RID})
    )

    with pytest.raises(NotFoundError) as excinfo:
        ResourceRoleService().list_roles(RID)

    assert excinfo.value.name == "ResourceNotFound"
