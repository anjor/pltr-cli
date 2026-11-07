"""Contract-test cases for src/pltr/commands/mediasets.py (see __init__.py)."""

from tests import foundry_json_mediasets as ms
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "media-sets get": [{"json": ms.item_info()}],
    "media-sets get-by-path": [{"json": ms.rid_by_path()}],
    "media-sets create": [{"json": ms.TRANSACTION_ID}],
    "media-sets commit": [{"status_code": 204}],
    "media-sets abort": [{"status_code": 204}],
    "media-sets upload": [{"json": ms.put_item()}],
    "media-sets reference": [{"json": ms.media_reference()}],
    "media-sets thumbnail-calculate": [{"json": ms.thumbnail_status()}],
    "media-sets upload-temp": [{"json": ms.media_reference()}],
    "media-sets clear": [{"status_code": 204}],
}

ARGS = {
    # Transaction IDs are UUIDs.
    "media-sets commit": [CONTRACT_RID, ms.TRANSACTION_ID],
    "media-sets abort": [CONTRACT_RID, ms.TRANSACTION_ID],
    # A synthesized OUTPUT_PATH is an existing file, which needs --overwrite;
    # "-" streams the content to stdout instead.
    "media-sets download": [CONTRACT_RID, CONTRACT_RID, "-"],
    "media-sets thumbnail-retrieve": [CONTRACT_RID, CONTRACT_RID, "-"],
}

_BINARY = (
    "binary content: writes the bytes to OUTPUT_PATH, or raw to stdout with '-', "
    "never a JSON document; tests/test_commands/test_mediasets.py covers the "
    "success path"
)

SUCCESS_EXEMPT = {
    "media-sets download": _BINARY,
    "media-sets thumbnail-retrieve": _BINARY,
}
