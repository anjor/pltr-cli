"""Realistic Foundry API JSON bodies for the Widgets API (``client.widgets``).

Bodies use the API's own field names, so the SDK decodes them into real
``foundry_sdk.v2.widgets.models`` models.
"""

from typing import Any, Dict

WIDGET_SET_RID = "ri.widgetregistry..widget-set.0b9a3c1e-5d2f-4e8a-9b7c-1a2b3c4d5e6f"
REPOSITORY_RID = "ri.stemma.main.repository.7f3e2d1c-0b9a-4c8d-8e7f-6a5b4c3d2e1f"


def widget_set(rid: str = WIDGET_SET_RID, **overrides: Any) -> Dict[str, Any]:
    """A ``WidgetSet``."""
    body: Dict[str, Any] = {"rid": rid, "publishRepositoryRid": REPOSITORY_RID}
    body.update(overrides)
    return body


def release(
    version: str = "1.2.0", widget_set_rid: str = WIDGET_SET_RID, **overrides: Any
) -> Dict[str, Any]:
    """A ``Release`` of a widget set."""
    body: Dict[str, Any] = {
        "widgetSetRid": widget_set_rid,
        "version": version,
        "locator": {"repositoryRid": REPOSITORY_RID, "repositoryVersion": version},
        "description": f"Release {version}",
    }
    body.update(overrides)
    return body


def repository(rid: str = REPOSITORY_RID, **overrides: Any) -> Dict[str, Any]:
    """A widget ``Repository``."""
    body: Dict[str, Any] = {"rid": rid, "widgetSetRid": WIDGET_SET_RID}
    body.update(overrides)
    return body
