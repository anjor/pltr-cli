"""Realistic Foundry API JSON bodies for stub_foundry_http tests.

Bodies use the API's own field names and value formats (principal IDs are
UUIDs, times are ISO-8601), so the SDK decodes them into real models.
"""

from typing import Any, Dict

USER_ID = "6f2a1b3c-0000-4000-8000-000000000001"
PARENT_RID = "ri.compass.main.folder.parent"
FOLDER_RID = "ri.compass.main.folder.test-folder"
PROJECT_RID = "ri.compass.main.folder.project"
SPACE_RID = "ri.compass.main.folder.space-1"
ENROLLMENT_RID = "ri.control-plane.main.enrollment.e1"
ORG_A = "ri.multipass..organization.org-a"
ORG_B = "ri.multipass..organization.org-b"
USAGE_ACCOUNT_RID = "ri.resource-policy-manager.main.usage-account.u1"
ERROR_INSTANCE_ID = "00000000-0000-4000-8000-0000000000e1"


def folder(rid: str = FOLDER_RID, name: str = "Test Folder", **overrides: Any) -> Dict:
    """A ``Folder``."""
    body = {
        "rid": rid,
        "displayName": name,
        "description": "Test folder description",
        "path": f"/Space/Project/{name}",
        "type": "FOLDER",
        "createdBy": USER_ID,
        "updatedBy": USER_ID,
        "createdTime": "2024-01-01T00:00:00Z",
        "updatedTime": "2024-01-02T00:00:00Z",
        "trashStatus": "NOT_TRASHED",
        "parentFolderRid": PARENT_RID,
        "projectRid": PROJECT_RID,
        "spaceRid": SPACE_RID,
    }
    body.update(overrides)
    return body


def resource(rid: str, name: str, resource_type: str = "COMPASS_FOLDER") -> Dict:
    """A ``Resource`` (an entry of ``Folder.children``)."""
    return {
        "rid": rid,
        "displayName": name,
        "path": f"/Space/Project/{name}",
        "type": resource_type,
        "createdBy": USER_ID,
        "updatedBy": USER_ID,
        "createdTime": "2024-01-01T00:00:00Z",
        "updatedTime": "2024-01-02T00:00:00Z",
        "trashStatus": "NOT_TRASHED",
        "parentFolderRid": PARENT_RID,
        "projectRid": PROJECT_RID,
        "spaceRid": SPACE_RID,
    }


def space(rid: str = SPACE_RID, name: str = "Test Space", **overrides: Any) -> Dict:
    """A ``Space``."""
    body = {
        "rid": rid,
        "displayName": name,
        "description": "Test description",
        "path": f"/{name}",
        "fileSystemId": "default-fs",
        "usageAccountRid": USAGE_ACCOUNT_RID,
        "organizations": [ORG_A],
        "deletionPolicyOrganizations": [ORG_A],
        "defaultRoleSetId": "role-set-1",
    }
    body.update(overrides)
    return body


def error(
    error_name: str,
    error_code: str = "NOT_FOUND",
    parameters: Any = None,
    instance_id: str = ERROR_INSTANCE_ID,
) -> Dict:
    """A Foundry error response body."""
    return {
        "errorCode": error_code,
        "errorName": error_name,
        "errorInstanceId": instance_id,
        "parameters": parameters or {},
    }


def sdk_json(body: Dict) -> Dict:
    """What pltr's JSON output is for ``body``: the SDK re-serializes times
    in UTC with an explicit offset (``Z`` becomes ``+00:00``)."""
    result = dict(body)
    for key in ("createdTime", "updatedTime"):
        if isinstance(result.get(key), str) and result[key].endswith("Z"):
            result[key] = result[key][:-1] + "+00:00"
    return result
