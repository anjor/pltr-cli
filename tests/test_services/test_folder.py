"""Tests for FolderService against a real FoundryClient (only HTTP is faked).

Every Folder endpoint pltr uses is GA, so any `preview=` argument would make
the SDK emit a UserWarning; the module-level filter turns that into a failure.
"""

import json

import pytest
from foundry_sdk import NotFoundError
from foundry_sdk.v2.filesystem.models import Folder, GetFoldersBatchResponse

from pltr.services.folder import FolderService
from tests.foundry_json import FOLDER_RID, PARENT_RID, USER_ID
from tests.foundry_json import folder as folder_json
from tests.foundry_json import resource as resource_json

pytestmark = pytest.mark.filterwarnings("error::UserWarning")


def test_create_folder_posts_display_name_and_parent(stub_foundry_http):
    stub_foundry_http.respond(json=folder_json())

    folder = FolderService().create_folder(
        display_name="Test Folder", parent_folder_rid=PARENT_RID
    )

    assert isinstance(folder, Folder)
    assert folder.rid == FOLDER_RID
    assert folder.created_by == USER_ID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", "/api/v2/filesystem/folders")
    assert "preview" not in request.url.params
    assert json.loads(request.content) == {
        "displayName": "Test Folder",
        "parentFolderRid": PARENT_RID,
    }


def test_get_folder(stub_foundry_http):
    stub_foundry_http.respond(json=folder_json())

    folder = FolderService().get_folder(FOLDER_RID)

    assert folder.display_name == "Test Folder"
    assert folder.created_time.year == 2024
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"/api/v2/filesystem/folders/{FOLDER_RID}",
    )
    assert "preview" not in request.url.params


def test_list_children_fetches_exactly_one_page(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": [
                resource_json(
                    "ri.compass.main.folder.child", "Child", "COMPASS_FOLDER"
                ),
                resource_json(
                    "ri.foundry.main.dataset.child", "Data", "FOUNDRY_DATASET"
                ),
            ],
            "nextPageToken": "page-2",
        }
    )

    page = FolderService().list_children(PARENT_RID, page_size=2, page_token="page-1")

    assert [child.type for child in page.data] == ["COMPASS_FOLDER", "FOUNDRY_DATASET"]
    assert page.next_page_token == "page-2"
    [request] = stub_foundry_http.requests  # constructing the iterator = one page
    assert (request.method, request.url.path) == (
        "GET",
        f"/api/v2/filesystem/folders/{PARENT_RID}/children",
    )
    assert dict(request.url.params) == {"pageSize": "2", "pageToken": "page-1"}


def test_get_folders_batch_sends_folder_rid_elements(stub_foundry_http):
    other = "ri.compass.main.folder.other"
    stub_foundry_http.respond(
        json={"data": {FOLDER_RID: folder_json(), other: folder_json(other, "Other")}}
    )

    response = FolderService().get_folders_batch([FOLDER_RID, other])

    assert isinstance(response, GetFoldersBatchResponse)
    assert sorted(response.data) == sorted([FOLDER_RID, other])
    assert response.data[other].display_name == "Other"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/filesystem/folders/getBatch",
    )
    assert json.loads(request.content) == [
        {"folderRid": FOLDER_RID},
        {"folderRid": other},
    ]


def test_get_folders_batch_rejects_more_than_1000(stub_foundry_http):
    rids = [f"ri.compass.main.folder.f{i}" for i in range(1001)]

    with pytest.raises(ValueError, match="Maximum batch size is 1000 folders"):
        FolderService().get_folders_batch(rids)

    assert stub_foundry_http.requests == []


def test_sdk_errors_propagate_unchanged(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json={
            "errorCode": "NOT_FOUND",
            "errorName": "FolderNotFound",
            "errorInstanceId": "00000000-0000-0000-0000-000000000000",
            "parameters": {"folderRid": FOLDER_RID},
        },
    )

    with pytest.raises(NotFoundError) as excinfo:
        FolderService().get_folder(FOLDER_RID)

    assert excinfo.value.name == "FolderNotFound"
    assert excinfo.value.parameters == {"folderRid": FOLDER_RID}
