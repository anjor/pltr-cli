"""Tests for ProjectService against a real FoundryClient (only HTTP is faked).

Replaces the Mock()-based tests, which asserted ``preview=True`` on GA calls
(#184), a call to the nonexistent ``Project.delete`` (#182), the
signature-sniffing ``Project.create`` call, and organization fields
(``display_name``, ``description``) that ``Project.organizations`` doesn't
return (it returns organization RIDs). ``Project.replace`` is the only beta
endpoint: it must get ``preview=true``; any other ``preview=`` raises a
UserWarning, which fails these tests.
"""

import json

import pytest
from foundry_sdk import NotFoundError
from foundry_sdk.v2.filesystem.models import Project

from pltr.services.project import OWNER_ROLE_ID, ProjectService, is_project
from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

PROJECT_PATH = f"/api/v2/filesystem/projects/{fj.PROJECT_RID}"


def children_path(folder_rid: str) -> str:
    return f"/api/v2/filesystem/folders/{folder_rid}/children"


# ------------------------------------------------------------------ create


def test_create_project_makes_the_current_user_owner(stub_foundry_http):
    stub_foundry_http.respond(json=fs.current_user())
    stub_foundry_http.respond(json=fs.project())

    project = ProjectService().create_project(
        display_name="Test Project", space_rid=fj.SPACE_RID
    )

    assert isinstance(project, Project)
    assert project.rid == fj.PROJECT_RID
    user_request, create_request = stub_foundry_http.requests
    assert (user_request.method, user_request.url.path) == (
        "GET",
        "/api/v2/admin/users/getCurrent",
    )
    assert (create_request.method, create_request.url.path) == (
        "POST",
        "/api/v2/filesystem/projects/create",
    )
    assert dict(create_request.url.params) == {}
    assert json.loads(create_request.content) == {
        "displayName": "Test Project",
        "spaceRid": fj.SPACE_RID,
        "roleGrants": {
            OWNER_ROLE_ID: [
                {
                    "principalId": fj.USER_ID,
                    "principalType": "USER",
                    "type": "principalWithId",
                }
            ]
        },
        "defaultRoles": [],
        "organizationRids": [],
    }


def test_create_project_with_every_option(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())

    ProjectService().create_project(
        display_name="Test Project",
        space_rid=fj.SPACE_RID,
        owner_id=fs.GROUP_ID,
        owner_type="GROUP",
        owner_role="custom:owner",
        description="About",
        organization_rids=[fj.ORG_A, fj.ORG_B],
        default_roles=["compass:read"],
    )

    [request] = stub_foundry_http.requests  # no current-user lookup
    assert json.loads(request.content) == {
        "displayName": "Test Project",
        "description": "About",
        "spaceRid": fj.SPACE_RID,
        "roleGrants": {
            "custom:owner": [
                {
                    "principalId": fs.GROUP_ID,
                    "principalType": "GROUP",
                    "type": "principalWithId",
                }
            ]
        },
        "defaultRoles": ["compass:read"],
        "organizationRids": [fj.ORG_A, fj.ORG_B],
    }


# -------------------------------------------------------------------- get


def test_get_project(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())

    project = ProjectService().get_project(fj.PROJECT_RID)

    assert project.display_name == "Test Project"
    assert project.resource_level_role_grants_allowed is True
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", PROJECT_PATH)
    assert dict(request.url.params) == {}


def test_get_project_not_found_propagates(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("ProjectNotFound", parameters={"projectRid": fj.PROJECT_RID})
    )

    with pytest.raises(NotFoundError) as excinfo:
        ProjectService().get_project(fj.PROJECT_RID)

    assert excinfo.value.name == "ProjectNotFound"


# ------------------------------------------------------------------- list


def test_is_project_compares_the_rid_with_project_rid():
    from foundry_sdk.v2.filesystem.models import Resource

    assert is_project(Resource.model_validate(fs.project_resource()))
    assert not is_project(
        Resource.model_validate(fs.child_resource(fs.DATASET_RID, "Data"))
    )


def test_list_projects_in_a_space_reads_one_page_and_keeps_projects(
    stub_foundry_http,
):
    other = fs.project_resource("ri.compass.main.folder.p2", "Second")
    not_a_project = fs.child_resource("ri.compass.main.folder.f", "F", "COMPASS_FOLDER")
    stub_foundry_http.respond(
        json=fs.page([fs.project_resource(), not_a_project, other], token="p2")
    )

    page = ProjectService().list_projects(fj.SPACE_RID, page_size=3, page_token="p1")

    assert [item.rid for item in page.data] == [fj.PROJECT_RID, other["rid"]]
    assert page.next_page_token == "p2"
    [request] = stub_foundry_http.requests
    assert request.url.path == children_path(fj.SPACE_RID)
    assert dict(request.url.params) == {"pageSize": "3", "pageToken": "p1"}


def test_list_all_projects_reads_every_page_of_every_space(stub_foundry_http):
    space_b = "ri.compass.main.folder.space-2"
    p2 = fs.project_resource("ri.compass.main.folder.p2", "P2", space_rid=space_b)
    stub_foundry_http.respond(json=fs.page([fj.space()], token="spaces-2"))
    stub_foundry_http.respond(json=fs.page([fs.project_resource()]))
    stub_foundry_http.respond(json=fs.page([fj.space(space_b, "B")]))
    stub_foundry_http.respond(json=fs.page([p2], token="children-2"))
    stub_foundry_http.respond(json=fs.page([fs.project_resource()]))  # duplicate

    projects = ProjectService().list_all_projects(page_size=50)

    assert [item.rid for item in projects] == [fj.PROJECT_RID, p2["rid"]]
    assert [
        (request.url.path, request.url.params.get("pageToken"))
        for request in stub_foundry_http.requests
    ] == [
        ("/api/v2/filesystem/spaces", None),
        (children_path(fj.SPACE_RID), None),
        ("/api/v2/filesystem/spaces", "spaces-2"),
        (children_path(space_b), None),
        (children_path(space_b), "children-2"),
    ]
    assert all(r.url.params["pageSize"] == "50" for r in stub_foundry_http.requests)


# ----------------------------------------------------------------- update


def test_update_project_keeps_the_description(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project(description="Keep me"))
    stub_foundry_http.respond(json=fs.project(name="Renamed"))

    project = ProjectService().update_project(fj.PROJECT_RID, display_name="Renamed")

    assert project.display_name == "Renamed"
    get_request, replace_request = stub_foundry_http.requests
    assert (get_request.method, get_request.url.path) == ("GET", PROJECT_PATH)
    assert "preview" not in get_request.url.params  # Project.get is GA
    assert (replace_request.method, replace_request.url.path) == ("PUT", PROJECT_PATH)
    assert replace_request.url.params["preview"] == "true"  # Project.replace is beta
    assert json.loads(replace_request.content) == {
        "displayName": "Renamed",
        "description": "Keep me",
    }


def test_update_project_description_only_keeps_the_name(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())
    stub_foundry_http.respond(json=fs.project())

    ProjectService().update_project(fj.PROJECT_RID, description="New text")

    body = json.loads(stub_foundry_http.requests[1].content)
    assert body == {"displayName": "Test Project", "description": "New text"}


def test_update_project_needs_a_field(stub_foundry_http):
    with pytest.raises(ValueError, match="At least one field"):
        ProjectService().update_project(fj.PROJECT_RID)
    assert stub_foundry_http.requests == []


# ----------------------------------------------------------------- delete


def test_delete_project_checks_the_project_then_trashes_it(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())
    stub_foundry_http.respond(204)

    project = ProjectService().delete_project(fj.PROJECT_RID)

    assert project.display_name == "Test Project"
    get_request, delete_request = stub_foundry_http.requests
    assert (get_request.method, get_request.url.path) == ("GET", PROJECT_PATH)
    assert (delete_request.method, delete_request.url.path) == (
        "DELETE",
        f"/api/v2/filesystem/resources/{fj.PROJECT_RID}",
    )
    assert dict(delete_request.url.params) == {}


def test_delete_project_does_not_trash_something_else(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("ProjectNotFound", parameters={"projectRid": fs.DATASET_RID})
    )

    with pytest.raises(NotFoundError):
        ProjectService().delete_project(fs.DATASET_RID)

    assert len(stub_foundry_http.requests) == 1  # no DELETE


# ---------------------------------------------------------- organizations


@pytest.mark.parametrize(
    "method, suffix",
    [
        ("add_organizations", "addOrganizations"),
        ("remove_organizations", "removeOrganizations"),
    ],
)
def test_organization_changes(stub_foundry_http, method, suffix):
    stub_foundry_http.respond(204)

    assert getattr(ProjectService(), method)(fj.PROJECT_RID, [fj.ORG_A]) is None

    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{PROJECT_PATH}/{suffix}")
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {"organizationRids": [fj.ORG_A]}


def test_list_organizations_returns_rids(stub_foundry_http):
    stub_foundry_http.respond(json=fs.page([fj.ORG_A, fj.ORG_B], token="p2"))

    page = ProjectService().list_organizations(fj.PROJECT_RID, page_size=2)

    assert page.data == [fj.ORG_A, fj.ORG_B]
    assert page.next_page_token == "p2"
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{PROJECT_PATH}/organizations"
    assert dict(request.url.params) == {"pageSize": "2"}


# --------------------------------------------------------------- template


def test_create_project_from_template_minimal(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())

    project = ProjectService().create_project_from_template(
        template_rid=fs.TEMPLATE_RID, variable_values={"name": "X"}
    )

    assert project.rid == fj.PROJECT_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/filesystem/projects/createFromTemplate",
    )
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {
        "templateRid": fs.TEMPLATE_RID,
        "variableValues": {"name": "X"},
    }


def test_create_project_from_template_with_every_option(stub_foundry_http):
    stub_foundry_http.respond(json=fs.project())

    ProjectService().create_project_from_template(
        template_rid=fs.TEMPLATE_RID,
        variable_values={},
        default_roles=["compass:read"],
        organization_rids=[fj.ORG_A],
        project_description="About",
    )

    assert json.loads(stub_foundry_http.requests[0].content) == {
        "templateRid": fs.TEMPLATE_RID,
        "variableValues": {},
        "defaultRoles": ["compass:read"],
        "organizationRids": [fj.ORG_A],
        "projectDescription": "About",
    }
