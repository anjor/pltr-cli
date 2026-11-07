"""Realistic Foundry admin API JSON bodies for stub_foundry_http tests.

Bodies use the API's own field names and value formats, so the SDK decodes
them into real admin models: user, group and other principal IDs are UUIDs,
organizations are addressed by RID (``ri.multipass..organization.<uuid>``),
times are ISO-8601 and 64-bit integers (``Marking.priority``) are strings, as
the SDK serializes them.
"""

from typing import Any, Dict

USER_ID = "8f6e2a3b-1c4d-4e5f-9a0b-1c2d3e4f5a6b"
USER_ID_2 = "0d1e2f3a-4b5c-4d6e-8f70-8192a3b4c5d6"
GROUP_ID = "3c4d5e6f-7a8b-4c9d-8e0f-1a2b3c4d5e6f"
GROUP_ID_2 = "4d5e6f7a-8b9c-4d0e-9f1a-2b3c4d5e6f70"
ORG_RID = "ri.multipass..organization.5e6f7a8b-9c0d-4e1f-8a2b-3c4d5e6f7a8b"
ORG_RID_2 = "ri.multipass..organization.6a7b8c9d-0e1f-4a2b-9c3d-4e5f6a7b8c9d"
ORG_MARKING_ID = "9c0d1e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f"
ENROLLMENT_RID = "ri.control-plane..enrollment.6f7a8b9c-0d1e-4f2a-9b3c-4d5e6f7a8b9c"
MARKING_ID = "7a8b9c0d-1e2f-4a3b-8c4d-5e6f7a8b9c0d"
MARKING_ID_2 = "1f2a3b4c-5d6e-4f7a-8b9c-0d1e2f3a4b5c"
CATEGORY_ID = "8b9c0d1e-2f3a-4b4c-9d5e-6f7a8b9c0d1e"
ROLE_ID = "organization-administrator"
ROLE_ID_2 = "organization-viewer"
ROLE_SET_ID = "organization-roles"
REALM = "palantir-internal-realm"


def user(user_id: str = USER_ID, username: str = "jane.doe", **overrides: Any) -> Dict:
    """An admin ``User``."""
    body: Dict[str, Any] = {
        "id": user_id,
        "username": username,
        "givenName": "Jane",
        "familyName": "Doe",
        "email": f"{username}@example.com",
        "realm": REALM,
        "organization": ORG_RID,
        "status": "ACTIVE",
        "attributes": {"multipass:email:primary": [f"{username}@example.com"]},
    }
    body.update(overrides)
    return body


def group(
    group_id: str = GROUP_ID, name: str = "Data Science", **overrides: Any
) -> Dict:
    """An admin ``Group``."""
    body: Dict[str, Any] = {
        "id": group_id,
        "name": name,
        "description": "Machine learning team",
        "realm": REALM,
        "organizations": [ORG_RID],
        "attributes": {"team": ["ds"]},
    }
    body.update(overrides)
    return body


def marking(
    marking_id: str = MARKING_ID, name: str = "Project X", **overrides: Any
) -> Dict:
    """An admin ``Marking``."""
    body: Dict[str, Any] = {
        "id": marking_id,
        "categoryId": CATEGORY_ID,
        "name": name,
        "description": "Data about Project X",
        "organization": ORG_RID,
        "priority": "10",
        "prominence": "COMMON",
        "deleted": False,
        "createdTime": "2024-01-01T00:00:00Z",
        "createdBy": USER_ID,
    }
    body.update(overrides)
    return body


def organization(rid: str = ORG_RID, name: str = "Research", **overrides: Any) -> Dict:
    """An admin ``Organization``."""
    body: Dict[str, Any] = {
        "rid": rid,
        "name": name,
        "description": "Research department",
        "markingId": ORG_MARKING_ID,
        "host": "research.example.com",
    }
    body.update(overrides)
    return body


def role(
    role_id: str = ROLE_ID, display_name: str = "Administrator", **overrides: Any
) -> Dict:
    """An admin ``Role`` (``Role.get``/``Role.get_batch``)."""
    body: Dict[str, Any] = {
        "id": role_id,
        "displayName": display_name,
        "description": "Manages the organization",
        "operations": ["organization:edit", "organization:manage-members"],
        "canAssigns": [ROLE_ID_2],
    }
    body.update(overrides)
    return body


def organization_role(
    role_id: str = ROLE_ID, name: str = "Administrator", **overrides: Any
) -> Dict:
    """A core ``Role`` (an entry of ``Organization.list_available_roles``)."""
    body: Dict[str, Any] = {
        "id": role_id,
        "roleSetId": ROLE_SET_ID,
        "name": name,
        "description": "Manages the organization",
        "isDefault": True,
        "type": "ORGANIZATION",
        "operations": ["organization:edit"],
    }
    body.update(overrides)
    return body
