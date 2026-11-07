"""Tests for MediaSetsService against a real FoundryClient (only HTTP is faked).

info, read, read_original and upload_media are GA: passing preview= would
make the SDK emit a UserWarning, which the module-level filter turns into a
failure. Every other MediaSet method pltr calls is beta and must send
preview=true.
"""

import pytest
from foundry_sdk import NotFoundError
from foundry_sdk.v2.core.models import MediaReference
from foundry_sdk.v2.media_sets.models import (
    GetMediaItemInfoResponse,
    GetMediaItemRidByPathResponse,
    PutMediaItemResponse,
    TrackedTransformationPendingResponse,
)

from pltr.services.mediasets import MediaSetsService
from tests import foundry_json as fj
from tests import foundry_json_mediasets as ms

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

TRANSACTIONS = f"/api/v2/mediasets/{ms.MEDIA_SET_RID}/transactions"


def only_request(stub):
    [request] = stub.requests
    return request


def test_get_media_item_info_is_ga(stub_foundry_http):
    stub_foundry_http.respond(json=ms.item_info())

    info = MediaSetsService().get_media_item_info(ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID)

    assert isinstance(info, GetMediaItemInfoResponse)
    assert (info.path, info.mime_type, info.size_bytes_long) == (
        "images/photo.png",
        "image/png",
        20,
    )
    assert info.attribution.creator_id == fj.USER_ID
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("GET", ms.ITEM)
    assert dict(request.url.params) == {}


def test_get_media_item_rid_by_path_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=ms.rid_by_path())

    result = MediaSetsService().get_media_item_rid_by_path(
        ms.MEDIA_SET_RID, "images/photo.png", branch_name="dev"
    )

    assert isinstance(result, GetMediaItemRidByPathResponse)
    assert result.media_item_rid == ms.MEDIA_ITEM_RID
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("GET", f"{ms.ITEMS}/getRidByPath")
    assert dict(request.url.params) == {
        "mediaItemPath": "images/photo.png",
        "branchName": "dev",
        "preview": "true",
    }


def test_create_transaction_is_beta_and_returns_the_id(stub_foundry_http):
    stub_foundry_http.respond(json=ms.TRANSACTION_ID)

    transaction_id = MediaSetsService().create_transaction(ms.MEDIA_SET_RID)

    assert transaction_id == ms.TRANSACTION_ID
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("POST", TRANSACTIONS)
    assert dict(request.url.params) == {"preview": "true"}


@pytest.mark.parametrize("action", ["commit", "abort"])
def test_commit_and_abort_are_beta(stub_foundry_http, action):
    stub_foundry_http.respond(204)
    service = MediaSetsService()
    method = getattr(service, f"{action}_transaction")

    assert method(ms.MEDIA_SET_RID, ms.TRANSACTION_ID) is None

    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        f"{TRANSACTIONS}/{ms.TRANSACTION_ID}/{action}",
    )
    assert dict(request.url.params) == {"preview": "true"}


def test_upload_media_is_beta_and_posts_the_bytes(stub_foundry_http):
    stub_foundry_http.respond(json=ms.put_item())

    response = MediaSetsService().upload_media(
        ms.MEDIA_SET_RID,
        b"%PDF-1.7 fake",
        media_item_path="docs/scan.pdf",
        transaction_id=ms.TRANSACTION_ID,
    )

    assert isinstance(response, PutMediaItemResponse)
    assert response.media_item_rid == ms.MEDIA_ITEM_RID
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("POST", ms.ITEMS)
    assert dict(request.url.params) == {
        "mediaItemPath": "docs/scan.pdf",
        "transactionId": ms.TRANSACTION_ID,
        "preview": "true",
    }
    assert request.content == b"%PDF-1.7 fake"


def test_upload_media_without_transaction(stub_foundry_http):
    stub_foundry_http.respond(json=ms.put_item())

    MediaSetsService().upload_media(
        ms.MEDIA_SET_RID, b"x", media_item_path="a.txt", branch_name="dev"
    )

    assert dict(only_request(stub_foundry_http).url.params) == {
        "branchName": "dev",
        "mediaItemPath": "a.txt",
        "preview": "true",
    }


@pytest.mark.parametrize("original, suffix", [(False, "/content"), (True, "/original")])
def test_download_media_streams_the_content(stub_foundry_http, original, suffix):
    stub_foundry_http.respond(content=b"\x89PNG fake image bytes")

    with MediaSetsService().download_media(
        ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, original=original
    ) as response:
        content = b"".join(response.iter_bytes())

    assert content == b"\x89PNG fake image bytes"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("GET", ms.ITEM + suffix)
    assert dict(request.url.params) == {}


def test_download_media_raises_api_errors_before_streaming(stub_foundry_http):
    stub_foundry_http.respond(404, json=fj.error("MediaItemNotFound"))

    with pytest.raises(NotFoundError) as caught:
        MediaSetsService().download_media(ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID)

    assert caught.value.name == "MediaItemNotFound"


def test_get_media_reference_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=ms.media_reference(token="read-token"))

    reference = MediaSetsService().get_media_reference(
        ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID
    )

    assert isinstance(reference, MediaReference)
    item = reference.reference.media_set_view_item
    assert (item.media_item_rid, item.token) == (ms.MEDIA_ITEM_RID, "read-token")
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("GET", f"{ms.ITEM}/reference")
    assert dict(request.url.params) == {"preview": "true"}


def test_calculate_thumbnail_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=ms.thumbnail_status("pending"))

    status = MediaSetsService().calculate_thumbnail(ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID)

    assert isinstance(status, TrackedTransformationPendingResponse)
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{ms.ITEM}/transform/imagery/thumbnail/calculate"
    assert dict(request.url.params) == {"preview": "true"}


def test_retrieve_thumbnail_is_beta_and_streams(stub_foundry_http):
    stub_foundry_http.respond(content=b"RIFF....WEBP")

    with MediaSetsService().retrieve_thumbnail(
        ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID
    ) as response:
        content = b"".join(response.iter_bytes())

    assert content == b"RIFF....WEBP"
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{ms.ITEM}/transform/imagery/thumbnail/retrieve"
    assert dict(request.url.params) == {"preview": "true"}


def test_upload_temp_media_is_ga(stub_foundry_http):
    stub_foundry_http.respond(json=ms.media_reference())

    reference = MediaSetsService().upload_temp_media(
        b"png-bytes", filename="photo.png", attribution="ri.foundry.main.dataset.x"
    )

    assert reference.mime_type == "image/png"
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "PUT",
        "/api/v2/mediasets/media/upload",
    )
    assert dict(request.url.params) == {"filename": "photo.png"}
    assert request.headers["attribution"] == "ri.foundry.main.dataset.x"
    assert request.content == b"png-bytes"


def test_clear_media_item_is_beta(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = MediaSetsService().clear_media_item(
        ms.MEDIA_SET_RID, "images/photo.png", transaction_id=ms.TRANSACTION_ID
    )

    assert result is None
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("DELETE", f"{ms.ITEMS}/clearAtPath")
    assert dict(request.url.params) == {
        "mediaItemPath": "images/photo.png",
        "preview": "true",
        "transactionId": ms.TRANSACTION_ID,
    }
