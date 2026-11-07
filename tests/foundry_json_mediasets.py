"""Realistic Foundry media sets API bodies for stub_foundry_http tests."""

from typing import Any, Dict, Optional

from tests.foundry_json import USER_ID

MEDIA_SET_RID = "ri.mio.main.media-set.6b57b513-6e54-4f04-b779-2a3a3f9e6f45"
MEDIA_ITEM_RID = "ri.mio.main.media-item.001ec98b-1620-4814-9e17-8e9c4e536225"
VIEW_RID = "ri.mio.main.view.2b4ebd9e-2b2c-4e4e-8d3c-0b0e2d2bf0a1"
TRANSACTION_ID = "3f2a9c1e-5b7d-4e8a-9c0f-1a2b3c4d5e6f"

ITEMS = f"/api/v2/mediasets/{MEDIA_SET_RID}/items"
ITEM = f"{ITEMS}/{MEDIA_ITEM_RID}"


def item_info(**overrides: Any) -> Dict[str, Any]:
    """A ``GetMediaItemInfoResponse`` (it doesn't include the item's RID)."""
    body: Dict[str, Any] = {
        "viewRid": VIEW_RID,
        "path": "images/photo.png",
        "logicalTimestamp": 1700000000000,
        "attribution": {
            "creatorId": USER_ID,
            "creationTimestamp": "2024-01-02T03:04:05Z",
        },
        "mimeType": "image/png",
        "originallyUploadedFileMimeType": "image/heic",
        "sizeBytes": 20,
        "sizeBytesLong": 20,
    }
    body.update(overrides)
    return body


def media_reference(token: Optional[str] = None) -> Dict[str, Any]:
    """A ``MediaReference``."""
    item = {
        "mediaSetRid": MEDIA_SET_RID,
        "mediaSetViewRid": VIEW_RID,
        "mediaItemRid": MEDIA_ITEM_RID,
    }
    if token is not None:
        item["token"] = token
    return {
        "mimeType": "image/png",
        "reference": {"type": "mediaSetViewItem", "mediaSetViewItem": item},
    }


def put_item() -> Dict[str, Any]:
    """A ``PutMediaItemResponse`` (``MediaSet.upload``)."""
    return {"mediaItemRid": MEDIA_ITEM_RID, "mediaSetViewRid": VIEW_RID}


def rid_by_path(rid: Optional[str] = MEDIA_ITEM_RID) -> Dict[str, Any]:
    """A ``GetMediaItemRidByPathResponse``."""
    return {} if rid is None else {"mediaItemRid": rid}


def thumbnail_status(state: str = "pending") -> Dict[str, Any]:
    """A ``TrackedTransformation{Pending,Successful,Failed}Response``."""
    return {"type": state}
