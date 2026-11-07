"""Tests for AdminService against a real FoundryClient (only HTTP is faked).

Every admin endpoint pltr calls is GA except Role.get, Role.get_batch and
Organization.create, which must carry preview=true. A GA call that still
passes preview= makes the SDK warn, which the module-level filter turns into
a failure.
"""

import json

import pytest
from foundry_sdk.v2.admin.models import (
    GetGroupsBatchResponse,
    GetMarkingsBatchResponse,
    GetRolesBatchResponse,
    GetUserMarkingsResponse,
    GetUsersBatchResponse,
    Group,
    ListAvailableOrganizationRolesResponse,
    Marking,
    Organization,
    Role,
    SearchGroupsResponse,
    SearchUsersResponse,
    User,
)
from foundry_sdk.v2.admin.errors import UserNotFound

from pltr.services.admin import MAX_BATCH_SIZE, AdminService
from tests import foundry_json_admin as aj

pytestmark = pytest.mark.filterwarnings("error::UserWarning")


def only_request(stub):
    [request] = stub.requests
    return request


# ------------------------------------------------------------------- users


def test_list_users_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.user()], "nextPageToken": "next"})

    page = AdminService().list_users(page_size=50, page_token="tok")

    assert [user.username for user in page.data] == ["jane.doe"]
    assert isinstance(page.data[0], User)
    assert page.next_page_token == "next"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("GET", "/api/v2/admin/users")
    assert dict(request.url.params) == {"pageSize": "50", "pageToken": "tok"}


def test_get_user(stub_foundry_http):
    stub_foundry_http.respond(json=aj.user())

    user = AdminService().get_user(aj.USER_ID)

    assert isinstance(user, User)
    assert (user.given_name, user.status) == ("Jane", "ACTIVE")
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "GET",
        f"/api/v2/admin/users/{aj.USER_ID}",
    )
    assert dict(request.url.params) == {}


def test_get_user_not_found_propagates_the_sdk_error(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json={
            "errorCode": "NOT_FOUND",
            "errorName": "UserNotFound",
            "errorInstanceId": "00000000-0000-4000-8000-000000000001",
            "parameters": {"userId": aj.USER_ID},
        },
    )

    with pytest.raises(UserNotFound):
        AdminService().get_user(aj.USER_ID)


def test_current_user_returns_the_model(stub_foundry_http):
    stub_foundry_http.respond(json=aj.user())

    user = AdminService().current_user()

    assert isinstance(user, User)
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "GET",
        "/api/v2/admin/users/getCurrent",
    )


def test_get_current_user_returns_the_sdk_dict(stub_foundry_http):
    """ProjectService reads the current user's "id" from this dict."""
    stub_foundry_http.respond(json=aj.user())

    current = AdminService().get_current_user()

    assert current == aj.user()
    assert current["id"] == aj.USER_ID


def test_search_users_sends_a_query_string_filter(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.user()], "nextPageToken": "next"})

    page = AdminService().search_users("jan", page_size=5, page_token="tok")

    assert isinstance(page, SearchUsersResponse)
    assert [user.id for user in page.data] == [aj.USER_ID]
    assert page.next_page_token == "next"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/admin/users/search",
    )
    assert json.loads(request.content) == {
        "where": {"type": "queryString", "value": "jan"},
        "pageSize": 5,
        "pageToken": "tok",
    }


def test_search_users_omits_unset_paging(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    page = AdminService().search_users("jan")

    assert page.data == [] and page.next_page_token is None
    body = json.loads(only_request(stub_foundry_http).content)
    assert body == {"where": {"type": "queryString", "value": "jan"}}


def test_get_user_markings(stub_foundry_http):
    stub_foundry_http.respond(json={"view": [aj.MARKING_ID, aj.MARKING_ID_2]})

    response = AdminService().get_user_markings(aj.USER_ID)

    assert isinstance(response, GetUserMarkingsResponse)
    assert response.view == [aj.MARKING_ID, aj.MARKING_ID_2]
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "GET",
        f"/api/v2/admin/users/{aj.USER_ID}/getMarkings",
    )


def test_revoke_user_tokens(stub_foundry_http):
    stub_foundry_http.respond(204)

    assert AdminService().revoke_user_tokens(aj.USER_ID) is None

    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        f"/api/v2/admin/users/{aj.USER_ID}/revokeAllTokens",
    )


def test_delete_user(stub_foundry_http):
    stub_foundry_http.respond(204)

    assert AdminService().delete_user(aj.USER_ID) is None

    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "DELETE",
        f"/api/v2/admin/users/{aj.USER_ID}",
    )


def test_get_batch_users_sends_request_elements(stub_foundry_http):
    """The old call sent bare strings, which the SDK rejects."""
    stub_foundry_http.respond(
        json={
            "data": {
                aj.USER_ID: aj.user(),
                aj.USER_ID_2: aj.user(aj.USER_ID_2, "john.roe"),
            }
        }
    )

    response = AdminService().get_batch_users([aj.USER_ID, aj.USER_ID_2])

    assert isinstance(response, GetUsersBatchResponse)
    assert response.data[aj.USER_ID_2].username == "john.roe"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/admin/users/getBatch",
    )
    assert json.loads(request.content) == [
        {"userId": aj.USER_ID},
        {"userId": aj.USER_ID_2},
    ]


def test_get_batch_users_rejects_more_than_500(stub_foundry_http):
    with pytest.raises(ValueError, match="Maximum batch size is 500 users"):
        AdminService().get_batch_users([aj.USER_ID] * (MAX_BATCH_SIZE + 1))
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------------ groups


def test_list_groups_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.group()]})

    page = AdminService().list_groups(page_size=10)

    assert isinstance(page.data[0], Group)
    assert page.next_page_token is None
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("GET", "/api/v2/admin/groups")
    assert dict(request.url.params) == {"pageSize": "10"}


def test_get_group(stub_foundry_http):
    stub_foundry_http.respond(json=aj.group())

    group = AdminService().get_group(aj.GROUP_ID)

    assert isinstance(group, Group)
    assert group.organizations == [aj.ORG_RID]
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "GET",
        f"/api/v2/admin/groups/{aj.GROUP_ID}",
    )


def test_search_groups_sends_a_query_string_filter(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.group()], "nextPageToken": "next"})

    page = AdminService().search_groups("data", page_size=2)

    assert isinstance(page, SearchGroupsResponse)
    assert [group.name for group in page.data] == ["Data Science"]
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/admin/groups/search",
    )
    assert json.loads(request.content) == {
        "where": {"type": "queryString", "value": "data"},
        "pageSize": 2,
    }


def test_create_group_sends_every_required_field(stub_foundry_http):
    stub_foundry_http.respond(json=aj.group())

    group = AdminService().create_group(
        name="Data Science",
        organizations=[aj.ORG_RID],
        attributes={"team": ["ds"]},
        description="Machine learning team",
    )

    assert isinstance(group, Group)
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("POST", "/api/v2/admin/groups")
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {
        "name": "Data Science",
        "organizations": [aj.ORG_RID],
        "attributes": {"team": ["ds"]},
        "description": "Machine learning team",
    }


def test_create_group_without_description_or_attributes(stub_foundry_http):
    stub_foundry_http.respond(json=aj.group(description=None, attributes={}))

    AdminService().create_group(
        name="Data Science", organizations=[aj.ORG_RID], attributes={}
    )

    assert json.loads(only_request(stub_foundry_http).content) == {
        "name": "Data Science",
        "organizations": [aj.ORG_RID],
        "attributes": {},
    }


def test_delete_group(stub_foundry_http):
    stub_foundry_http.respond(204)

    assert AdminService().delete_group(aj.GROUP_ID) is None

    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "DELETE",
        f"/api/v2/admin/groups/{aj.GROUP_ID}",
    )


def test_get_batch_groups_sends_request_elements(stub_foundry_http):
    stub_foundry_http.respond(json={"data": {aj.GROUP_ID: aj.group()}})

    response = AdminService().get_batch_groups([aj.GROUP_ID])

    assert isinstance(response, GetGroupsBatchResponse)
    assert response.data[aj.GROUP_ID].name == "Data Science"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/admin/groups/getBatch",
    )
    assert json.loads(request.content) == [{"groupId": aj.GROUP_ID}]


def test_get_batch_groups_rejects_more_than_500(stub_foundry_http):
    with pytest.raises(ValueError, match="Maximum batch size is 500 groups"):
        AdminService().get_batch_groups([aj.GROUP_ID] * (MAX_BATCH_SIZE + 1))
    assert stub_foundry_http.requests == []


# ---------------------------------------------------------------- markings


def test_list_markings_without_filters(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [aj.marking()], "nextPageToken": "n"})

    page = AdminService().list_markings()

    assert isinstance(page.data[0], Marking)
    assert page.next_page_token == "n"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("GET", "/api/v2/admin/markings")
    assert dict(request.url.params) == {}


def test_list_markings_with_filters_and_paging(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    AdminService().list_markings(
        include_deleted=False, marking_type="CBAC", page_size=100, page_token="t"
    )

    assert dict(only_request(stub_foundry_http).url.params) == {
        "includeDeleted": "false",
        "markingType": "CBAC",
        "pageSize": "100",
        "pageToken": "t",
    }


def test_get_marking(stub_foundry_http):
    stub_foundry_http.respond(json=aj.marking())

    marking = AdminService().get_marking(aj.MARKING_ID)

    assert isinstance(marking, Marking)
    assert (marking.category_id, marking.priority) == (aj.CATEGORY_ID, 10)
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "GET",
        f"/api/v2/admin/markings/{aj.MARKING_ID}",
    )
    assert dict(request.url.params) == {}


def test_get_batch_markings_sends_request_elements(stub_foundry_http):
    stub_foundry_http.respond(json={"data": {aj.MARKING_ID: aj.marking()}})

    response = AdminService().get_batch_markings([aj.MARKING_ID])

    assert isinstance(response, GetMarkingsBatchResponse)
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/admin/markings/getBatch",
    )
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == [{"markingId": aj.MARKING_ID}]


def test_get_batch_markings_rejects_more_than_500(stub_foundry_http):
    with pytest.raises(ValueError, match="Maximum batch size is 500 markings"):
        AdminService().get_batch_markings([aj.MARKING_ID] * (MAX_BATCH_SIZE + 1))
    assert stub_foundry_http.requests == []


def test_create_marking_sends_members_and_role_assignments(stub_foundry_http):
    stub_foundry_http.respond(json=aj.marking())

    marking = AdminService().create_marking(
        name="Project X",
        category_id=aj.CATEGORY_ID,
        initial_members=[aj.GROUP_ID],
        initial_role_assignments=[("ADMINISTER", aj.USER_ID), ("USE", aj.GROUP_ID)],
        description="Data about Project X",
    )

    assert isinstance(marking, Marking)
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("POST", "/api/v2/admin/markings")
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {
        "name": "Project X",
        "categoryId": aj.CATEGORY_ID,
        "initialMembers": [aj.GROUP_ID],
        "initialRoleAssignments": [
            {"role": "ADMINISTER", "principalId": aj.USER_ID},
            {"role": "USE", "principalId": aj.GROUP_ID},
        ],
        "description": "Data about Project X",
    }


def test_replace_marking_with_description_sends_one_request(stub_foundry_http):
    stub_foundry_http.respond(json=aj.marking(name="Renamed", description="New"))

    marking = AdminService().replace_marking(
        aj.MARKING_ID, name="Renamed", description="New"
    )

    assert marking.name == "Renamed"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "PUT",
        f"/api/v2/admin/markings/{aj.MARKING_ID}",
    )
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {"name": "Renamed", "description": "New"}


def test_replace_marking_keeps_the_current_description(stub_foundry_http):
    """Marking.replace clears a description it isn't sent."""
    stub_foundry_http.respond(json=aj.marking())
    stub_foundry_http.respond(json=aj.marking(name="Renamed"))

    AdminService().replace_marking(aj.MARKING_ID, name="Renamed")

    get_request, put_request = stub_foundry_http.requests
    assert get_request.method == "GET"
    assert put_request.method == "PUT"
    assert json.loads(put_request.content) == {
        "name": "Renamed",
        "description": "Data about Project X",
    }


# ----------------------------------------------------------- organizations


def test_get_organization(stub_foundry_http):
    stub_foundry_http.respond(json=aj.organization())

    organization = AdminService().get_organization(aj.ORG_RID)

    assert isinstance(organization, Organization)
    assert organization.marking_id == aj.ORG_MARKING_ID
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "GET",
        f"/api/v2/admin/organizations/{aj.ORG_RID}",
    )


def test_create_organization_is_beta_and_sends_administrators(stub_foundry_http):
    stub_foundry_http.respond(json=aj.organization())

    organization = AdminService().create_organization(
        name="Research",
        enrollment_rid=aj.ENROLLMENT_RID,
        administrators=[aj.USER_ID],
        description="Research department",
        host="research.example.com",
    )

    assert isinstance(organization, Organization)
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/admin/organizations",
    )
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {
        "name": "Research",
        "enrollmentRid": aj.ENROLLMENT_RID,
        "administrators": [aj.USER_ID],
        "description": "Research department",
        "host": "research.example.com",
    }


def test_replace_organization_with_every_field_sends_one_request(
    stub_foundry_http,
):
    stub_foundry_http.respond(json=aj.organization(name="Lab"))

    AdminService().replace_organization(
        aj.ORG_RID, name="Lab", description="New", host="lab.example.com"
    )

    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "PUT",
        f"/api/v2/admin/organizations/{aj.ORG_RID}",
    )
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {
        "name": "Lab",
        "description": "New",
        "host": "lab.example.com",
    }


def test_replace_organization_keeps_the_current_description_and_host(
    stub_foundry_http,
):
    """Organization.replace clears the description and host it isn't sent."""
    stub_foundry_http.respond(json=aj.organization())
    stub_foundry_http.respond(json=aj.organization(name="Lab"))

    organization = AdminService().replace_organization(aj.ORG_RID, name="Lab")

    assert organization.name == "Lab"
    get_request, put_request = stub_foundry_http.requests
    assert (get_request.method, put_request.method) == ("GET", "PUT")
    assert json.loads(put_request.content) == {
        "name": "Lab",
        "description": "Research department",
        "host": "research.example.com",
    }


def test_replace_organization_keeps_only_what_is_not_given(stub_foundry_http):
    stub_foundry_http.respond(json=aj.organization(host=None))
    stub_foundry_http.respond(json=aj.organization(name="Lab"))

    AdminService().replace_organization(aj.ORG_RID, name="Lab", description="New")

    body = json.loads(stub_foundry_http.requests[1].content)
    assert body == {"name": "Lab", "description": "New"}  # no host to keep


def test_list_available_roles_takes_only_the_organization(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": [
                aj.organization_role(),
                aj.organization_role(aj.ROLE_ID_2, "Viewer", isDefault=False),
            ]
        }
    )

    response = AdminService().list_available_roles(aj.ORG_RID)

    assert isinstance(response, ListAvailableOrganizationRolesResponse)
    assert [role.name for role in response.data] == ["Administrator", "Viewer"]
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "GET",
        f"/api/v2/admin/organizations/{aj.ORG_RID}/listAvailableRoles",
    )
    assert dict(request.url.params) == {}


# ------------------------------------------------------------------- roles


def test_get_role_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=aj.role())

    role = AdminService().get_role(aj.ROLE_ID)

    assert isinstance(role, Role)
    assert role.can_assigns == [aj.ROLE_ID_2]
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "GET",
        f"/api/v2/admin/roles/{aj.ROLE_ID}",
    )
    assert dict(request.url.params) == {"preview": "true"}


def test_get_batch_roles_is_beta_and_sends_request_elements(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": {
                aj.ROLE_ID: aj.role(),
                aj.ROLE_ID_2: aj.role(aj.ROLE_ID_2, "Viewer"),
            }
        }
    )

    response = AdminService().get_batch_roles([aj.ROLE_ID, aj.ROLE_ID_2])

    assert isinstance(response, GetRolesBatchResponse)
    assert response.data[aj.ROLE_ID_2].display_name == "Viewer"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/admin/roles/getBatch",
    )
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == [
        {"roleId": aj.ROLE_ID},
        {"roleId": aj.ROLE_ID_2},
    ]


def test_get_batch_roles_rejects_more_than_500(stub_foundry_http):
    with pytest.raises(ValueError, match="Maximum batch size is 500 roles"):
        AdminService().get_batch_roles([aj.ROLE_ID] * (MAX_BATCH_SIZE + 1))
    assert stub_foundry_http.requests == []
