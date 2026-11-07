"""Realistic Foundry API JSON bodies for the filesystem area's tests
(project, resource, resource-role, cp).

Shared builders (``folder``, ``resource``, ``space``, ``error``, ``sdk_json``)
live in ``tests/foundry_json.py``. Bodies use the API's field names and value
formats (principal IDs are UUIDs, times are ISO-8601), so the SDK decodes them
into real models.
"""

from typing import Any, Dict, List, Optional

from tests.foundry_json import (
    ORG_A,
    PROJECT_RID,
    SPACE_RID,
    USER_ID,
)

GROUP_ID = "6f2a1b3c-0000-4000-8000-0000000000a2"
DATASET_RID = "ri.foundry.main.dataset.source-data"
TEMPLATE_RID = "ri.compass.main.template.t1"
MARKING_ID = "a7c3e1d2-0000-4000-8000-0000000000b1"
TRANSACTION_RID = "ri.foundry.main.transaction.t1"


def project(
    rid: str = PROJECT_RID, name: str = "Test Project", **overrides: Any
) -> Dict:
    """A ``Project``."""
    body = {
        "rid": rid,
        "displayName": name,
        "description": "Test project description",
        "path": f"/Test Space/{name}",
        "createdBy": USER_ID,
        "updatedBy": USER_ID,
        "createdTime": "2024-01-01T00:00:00Z",
        "updatedTime": "2024-01-02T00:00:00Z",
        "trashStatus": "NOT_TRASHED",
        "spaceRid": SPACE_RID,
        "resourceLevelRoleGrantsAllowed": True,
    }
    body.update(overrides)
    return body


def project_resource(
    rid: str = PROJECT_RID, name: str = "Test Project", space_rid: str = SPACE_RID
) -> Dict:
    """A ``Resource`` that is a project (a child of a space): its
    ``projectRid`` is its own RID."""
    return {
        "rid": rid,
        "displayName": name,
        "path": f"/Test Space/{name}",
        "type": "COMPASS_FOLDER",
        "createdBy": USER_ID,
        "updatedBy": USER_ID,
        "createdTime": "2024-01-01T00:00:00Z",
        "updatedTime": "2024-01-02T00:00:00Z",
        "trashStatus": "NOT_TRASHED",
        "parentFolderRid": space_rid,
        "projectRid": rid,
        "spaceRid": space_rid,
    }


def child_resource(
    rid: str,
    name: str,
    resource_type: str = "FOUNDRY_DATASET",
    parent: str = PROJECT_RID,
    description: Optional[str] = None,
) -> Dict:
    """A ``Resource`` inside a project (its ``projectRid`` is the project)."""
    body = {
        "rid": rid,
        "displayName": name,
        "path": f"/Test Space/Test Project/{name}",
        "type": resource_type,
        "createdBy": USER_ID,
        "updatedBy": USER_ID,
        "createdTime": "2024-01-01T00:00:00Z",
        "updatedTime": "2024-01-02T00:00:00Z",
        "trashStatus": "NOT_TRASHED",
        "parentFolderRid": parent,
        "projectRid": PROJECT_RID,
        "spaceRid": SPACE_RID,
    }
    if description is not None:
        body["description"] = description
    return body


def page(items: List[Any], token: Optional[str] = None) -> Dict:
    """A paged list response."""
    body: Dict[str, Any] = {"data": list(items)}
    if token:
        body["nextPageToken"] = token
    return body


def user_role(role_id: str = "compass:read", principal_id: str = USER_ID) -> Dict:
    """A ``ResourceRole`` granted to a user."""
    return {
        "resourceRolePrincipal": {
            "type": "principalWithId",
            "principalId": principal_id,
            "principalType": "USER",
        },
        "roleId": role_id,
    }


def group_role(role_id: str = "compass:edit", principal_id: str = GROUP_ID) -> Dict:
    """A ``ResourceRole`` granted to a group."""
    return {
        "resourceRolePrincipal": {
            "type": "principalWithId",
            "principalId": principal_id,
            "principalType": "GROUP",
        },
        "roleId": role_id,
    }


def everyone_role(role_id: str = "compass:discover") -> Dict:
    """A ``ResourceRole`` granted to everyone."""
    return {"resourceRolePrincipal": {"type": "everyone"}, "roleId": role_id}


def access_requirements() -> Dict:
    """An ``AccessRequirements`` response: one organization, one marking."""
    return {
        "organizations": [
            {
                "markingId": "org-marking-a",
                "organizationRid": ORG_A,
                "isDirectlyApplied": False,
            }
        ],
        "markings": [{"markingId": MARKING_ID, "isDirectlyApplied": True}],
    }


def current_user(user_id: str = USER_ID) -> Dict:
    """A ``User`` (``admin.User.get_current``)."""
    return {
        "id": user_id,
        "username": "test.user",
        "givenName": "Test",
        "familyName": "User",
        "email": "test.user@example.com",
        "realm": "palantir-internal-realm",
        "organization": ORG_A,
        "status": "ACTIVE",
        "attributes": {},
    }


def dataset(rid: str, name: str, parent_folder_rid: str) -> Dict:
    """A ``Dataset``."""
    return {"rid": rid, "name": name, "parentFolderRid": parent_folder_rid}


def transaction(rid: str = TRANSACTION_RID, status: str = "OPEN") -> Dict:
    """A ``Transaction``."""
    return {
        "rid": rid,
        "transactionType": "SNAPSHOT",
        "status": status,
        "createdTime": "2024-01-01T00:00:00Z",
    }


def dataset_file(path: str, transaction_rid: str = TRANSACTION_RID) -> Dict:
    """A dataset ``File``."""
    return {
        "path": path,
        "transactionRid": transaction_rid,
        "sizeBytes": "4",
        "updatedTime": "2024-01-01T00:00:00Z",
    }
