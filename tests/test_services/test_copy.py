"""Tests for CopyService against a real FoundryClient (only HTTP is faked).

The resource and folder side (``Resource.get``, ``Folder.create``,
``Folder.children``) and the file upload (``Dataset.File.upload``) go through
``stub_foundry_http``. The other dataset steps go through ``DatasetService``
methods that the dataset area keeps as dict-returning compatibility wrappers
while it is converted (create_dataset, get_schema, put_schema, list_files,
create_transaction, download_file, commit_transaction, abort_transaction,
delete_dataset). Those methods are patched with ``autospec`` here, so the tests
pin the interface copy relies on without depending on how the dataset area
implements it.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from foundry_sdk import PermissionDeniedError
from foundry_sdk.v2.datasets.models import Dataset
from foundry_sdk.v2.filesystem.models import Folder, Resource

from pltr.contract import PltrError
from pltr.services.copy import CopyService
from pltr.services.dataset import DatasetService
from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

SOURCE_DATASET = fs.child_resource(fs.DATASET_RID, "Source Dataset")
SOURCE_FOLDER = fs.child_resource(
    "ri.compass.main.folder.source", "Source", "COMPASS_FOLDER"
)
TARGET = "ri.compass.main.folder.target"
NEW_DATASET_RID = "ri.foundry.main.dataset.new"
UPLOAD_DENIED = fj.error(
    "UploadFilePermissionDenied",
    "PERMISSION_DENIED",
    {
        "datasetRid": NEW_DATASET_RID,
        "transactionRid": fs.TRANSACTION_RID,
        "path": "data/part-0.csv",
    },
)


def children_path(folder_rid: str) -> str:
    return f"/api/v2/filesystem/folders/{folder_rid}/children"


def requests_summary(stub):
    return [
        (request.method, request.url.path, request.url.params.get("pageToken"))
        for request in stub.requests
    ]


@pytest.fixture
def dataset_compat():
    """Patch the DatasetService compatibility methods copy relies on."""

    def fake_download(self, dataset_rid, file_path, output_path, branch="master"):
        Path(output_path).write_bytes(b"col\n1\n")
        return {"downloaded": True}

    patches = {
        "create_dataset": {"return_value": {"rid": NEW_DATASET_RID}},
        "get_schema": {"return_value": {"schema": None}},
        "put_schema": {},
        "list_files": {"return_value": [{"path": "/data/part-0.csv"}]},
        "create_transaction": {"return_value": {"transaction_rid": fs.TRANSACTION_RID}},
        "download_file": {"side_effect": fake_download},
        "commit_transaction": {},
        "abort_transaction": {},
        "delete_dataset": {},
    }
    mocks = {}
    started = []
    for name, kwargs in patches.items():
        patcher = patch.object(DatasetService, name, autospec=True, **kwargs)
        mocks[name] = patcher.start()
        started.append(patcher)
    yield mocks
    for patcher in started:
        patcher.stop()


# ------------------------------------------------------------------ datasets


def test_copy_dataset_dry_run_creates_nothing(stub_foundry_http, dataset_compat):
    stub_foundry_http.respond(json=SOURCE_DATASET)

    result = CopyService(dry_run=True).copy_resource(fs.DATASET_RID, TARGET)

    assert [type(item) for item in result.items] == [Resource]
    assert result.items[0].rid == fs.DATASET_RID
    assert result.stats.as_dict() == {
        "folders_copied": 0,
        "datasets_copied": 1,
        "skipped": 0,
        "errors": 0,
    }
    dataset_compat["create_dataset"].assert_not_called()
    assert requests_summary(stub_foundry_http) == [
        ("GET", f"/api/v2/filesystem/resources/{fs.DATASET_RID}", None)
    ]


def test_copy_dataset_copies_files_into_a_snapshot(stub_foundry_http, dataset_compat):
    stub_foundry_http.respond(json=SOURCE_DATASET)
    stub_foundry_http.respond(json=fs.dataset_file("data/part-0.csv"))  # upload

    result = CopyService(branch="dev").copy_resource(fs.DATASET_RID, TARGET)

    [created] = result.items
    assert isinstance(created, Dataset)
    assert (created.rid, created.name, created.parent_folder_rid) == (
        NEW_DATASET_RID,
        "Source Dataset-copy",
        TARGET,
    )
    assert (result.stats.datasets, result.failures) == (1, [])
    # autospec: args[0] is the DatasetService instance
    create_dataset = dataset_compat["create_dataset"]
    create_dataset.assert_called_once()
    assert create_dataset.call_args.args[1:] == ("Source Dataset-copy", TARGET)
    dataset_compat["list_files"].assert_called_once()
    assert dataset_compat["list_files"].call_args.kwargs == {"branch": "dev"}
    assert dataset_compat["create_transaction"].call_args.kwargs == {
        "branch": "dev",
        "transaction_type": "SNAPSHOT",
    }
    dataset_compat["commit_transaction"].assert_called_once()
    dataset_compat["delete_dataset"].assert_not_called()

    _, upload = stub_foundry_http.requests
    assert (upload.method, upload.url.path) == (
        "POST",
        f"/api/v2/datasets/{NEW_DATASET_RID}/files/data/part-0.csv/upload",
    )
    # transaction or branch, never both (InvalidParameterCombination)
    assert dict(upload.url.params) == {"transactionRid": fs.TRANSACTION_RID}
    assert upload.content == b"col\n1\n"


def test_copy_dataset_copies_the_schema_when_there_is_one(
    stub_foundry_http, dataset_compat
):
    dataset_compat["get_schema"].return_value = {"schema": {"fieldSchemaList": []}}
    stub_foundry_http.respond(json=SOURCE_DATASET)
    stub_foundry_http.respond(json=fs.dataset_file("data/part-0.csv"))

    CopyService().copy_resource(fs.DATASET_RID, TARGET)

    put_schema = dataset_compat["put_schema"]
    assert put_schema.call_args.args[1:] == (NEW_DATASET_RID, {"fieldSchemaList": []})


def test_copy_dataset_without_schema(stub_foundry_http, dataset_compat):
    stub_foundry_http.respond(json=SOURCE_DATASET)
    stub_foundry_http.respond(json=fs.dataset_file("data/part-0.csv"))

    CopyService(copy_schema=False).copy_resource(fs.DATASET_RID, TARGET)

    dataset_compat["get_schema"].assert_not_called()


def test_failed_dataset_copy_is_cleaned_up_and_raised(
    stub_foundry_http, dataset_compat, capsys
):
    stub_foundry_http.respond(json=SOURCE_DATASET)
    stub_foundry_http.respond(403, json=UPLOAD_DENIED)

    with pytest.raises(RuntimeError, match="Failed to copy the files") as excinfo:
        CopyService().copy_resource(fs.DATASET_RID, TARGET)

    # the SDK error is the cause, so the error layer can classify it
    cause = excinfo.value.__cause__
    assert isinstance(cause, PermissionDeniedError)
    assert cause.name == "UploadFilePermissionDenied"
    dataset_compat["abort_transaction"].assert_called_once()
    dataset_compat["commit_transaction"].assert_not_called()
    dataset_compat["delete_dataset"].assert_called_once()
    assert dataset_compat["delete_dataset"].call_args.args[1] == NEW_DATASET_RID
    assert "Removing the partly copied dataset" in capsys.readouterr().err


def test_upload_without_a_transaction_names_the_branch(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=fs.dataset_file("baz.csv"))
    local = tmp_path / "baz.csv"
    local.write_bytes(b"hello")

    CopyService(branch="feature")._upload_dataset_file(
        NEW_DATASET_RID, "/baz.csv", local, None
    )

    [request] = stub_foundry_http.requests
    assert (
        request.url.path == f"/api/v2/datasets/{NEW_DATASET_RID}/files/baz.csv/upload"
    )
    assert dict(request.url.params) == {"branchName": "feature"}
    assert request.content == b"hello"


@pytest.mark.parametrize("path", ["../escape.csv", "/a/../../b.csv"])
def test_sanitize_local_path_rejects_traversal(stub_foundry_http, path):
    with pytest.raises(ValueError):
        CopyService()._sanitize_local_path(path)


def test_derive_name_does_not_repeat_the_suffix(stub_foundry_http):
    service = CopyService(name_suffix="-copy")

    assert service._derive_name("Data") == "Data-copy"
    assert service._derive_name("Data-copy") == "Data-copy"
    assert CopyService(name_suffix="")._derive_name("Data") == "Data"


# ------------------------------------------------------------------ folders


def test_copy_folder_requires_recursive(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_FOLDER)

    with pytest.raises(PltrError, match="--recursive") as excinfo:
        CopyService().copy_resource(SOURCE_FOLDER["rid"], TARGET)

    assert excinfo.value.error_type == "usage_error"
    assert len(stub_foundry_http.requests) == 1


def test_copy_rejects_other_resource_types(stub_foundry_http):
    stub_foundry_http.respond(
        json=fs.child_resource("ri.contour.main.analysis.a", "A", "CONTOUR_ANALYSIS")
    )

    with pytest.raises(PltrError, match="CONTOUR_ANALYSIS"):
        CopyService().copy_resource(
            "ri.contour.main.analysis.a", TARGET, recursive=True
        )


def test_copy_folder_recursively_reads_every_page(stub_foundry_http):
    sub = fs.child_resource("ri.compass.main.folder.sub", "Sub", "COMPASS_FOLDER")
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(
        json=fj.folder("ri.compass.main.folder.new", "Source-copy")
    )
    stub_foundry_http.respond(json=fs.page([sub], token="p2"))
    stub_foundry_http.respond(json=fs.page([]))
    stub_foundry_http.respond(
        json=fj.folder("ri.compass.main.folder.new-sub", "Sub-copy")
    )
    stub_foundry_http.respond(json=fs.page([]))

    result = CopyService().copy_resource(SOURCE_FOLDER["rid"], TARGET, recursive=True)

    assert [type(item) for item in result.items] == [Folder, Folder]
    assert [item.rid for item in result.items] == [
        "ri.compass.main.folder.new",
        "ri.compass.main.folder.new-sub",
    ]
    assert result.stats.folders == 2
    assert requests_summary(stub_foundry_http) == [
        ("GET", f"/api/v2/filesystem/resources/{SOURCE_FOLDER['rid']}", None),
        ("POST", "/api/v2/filesystem/folders", None),
        ("GET", children_path(SOURCE_FOLDER["rid"]), None),
        ("GET", children_path(SOURCE_FOLDER["rid"]), "p2"),
        ("POST", "/api/v2/filesystem/folders", None),
        ("GET", children_path(sub["rid"]), None),
    ]
    first_create = json.loads(stub_foundry_http.requests[1].content)
    assert first_create == {"displayName": "Source-copy", "parentFolderRid": TARGET}
    nested_create = json.loads(stub_foundry_http.requests[4].content)
    assert nested_create["parentFolderRid"] == "ri.compass.main.folder.new"


def test_copy_folder_skips_unsupported_children(stub_foundry_http, capsys):
    analysis = fs.child_resource("ri.contour.main.analysis.a", "A", "CONTOUR_ANALYSIS")
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(
        json=fj.folder("ri.compass.main.folder.new", "Source-copy")
    )
    stub_foundry_http.respond(json=fs.page([analysis]))

    result = CopyService().copy_resource(SOURCE_FOLDER["rid"], TARGET, recursive=True)

    assert (result.stats.skipped, result.failures) == (1, [])
    assert "Skipped A (ri.contour.main.analysis.a)" in capsys.readouterr().err


def _two_subfolders(stub):
    first = fs.child_resource("ri.compass.main.folder.one", "One", "COMPASS_FOLDER")
    second = fs.child_resource("ri.compass.main.folder.two", "Two", "COMPASS_FOLDER")
    stub.respond(json=SOURCE_FOLDER)
    stub.respond(json=fj.folder("ri.compass.main.folder.new", "Source-copy"))
    stub.respond(json=fs.page([first, second]))
    stub.respond(
        403,
        json=fj.error(
            "CreateFolderPermissionDenied",
            "PERMISSION_DENIED",
            {"parentFolderRid": "ri.compass.main.folder.new"},
        ),
    )


def test_child_failures_are_recorded_and_the_copy_goes_on(stub_foundry_http, capsys):
    _two_subfolders(stub_foundry_http)
    stub_foundry_http.respond(
        json=fj.folder("ri.compass.main.folder.new-two", "Two-copy")
    )
    stub_foundry_http.respond(json=fs.page([]))

    result = CopyService().copy_resource(SOURCE_FOLDER["rid"], TARGET, recursive=True)

    assert [item.rid for item in result.items] == [
        "ri.compass.main.folder.new",
        "ri.compass.main.folder.new-two",
    ]
    assert result.stats.errors == 1
    [failure] = result.failures
    assert failure.name == "CreateFolderPermissionDenied"
    assert "Failed to copy 'One'" in capsys.readouterr().err


def test_fail_fast_stops_at_the_first_failure(stub_foundry_http):
    _two_subfolders(stub_foundry_http)

    result = CopyService(fail_fast=True).copy_resource(
        SOURCE_FOLDER["rid"], TARGET, recursive=True
    )

    assert [item.rid for item in result.items] == ["ri.compass.main.folder.new"]
    assert result.stats.errors == 1  # counted once, not once per level
    assert len(result.failures) == 1
    assert len(stub_foundry_http.requests) == 4  # nothing after the failure


def test_listing_failure_after_creating_the_folder_is_recorded(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(
        json=fj.folder("ri.compass.main.folder.new", "Source-copy")
    )
    stub_foundry_http.respond(
        404,
        json=fj.error("FolderNotFound", parameters={"folderRid": SOURCE_FOLDER["rid"]}),
    )

    result = CopyService().copy_resource(SOURCE_FOLDER["rid"], TARGET, recursive=True)

    assert [item.rid for item in result.items] == ["ri.compass.main.folder.new"]
    assert [failure.name for failure in result.failures] == ["FolderNotFound"]


def test_copy_folder_dry_run_lists_the_sources(stub_foundry_http, dataset_compat):
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(json=fs.page([SOURCE_DATASET]))

    result = CopyService(dry_run=True).copy_resource(
        SOURCE_FOLDER["rid"], TARGET, recursive=True
    )

    assert [item.rid for item in result.items] == [
        SOURCE_FOLDER["rid"],
        fs.DATASET_RID,
    ]
    assert all(isinstance(item, Resource) for item in result.items)
    assert [request.method for request in stub_foundry_http.requests] == ["GET", "GET"]
    dataset_compat["create_dataset"].assert_not_called()


def test_source_errors_propagate(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error("ResourceNotFound", parameters={"resourceRid": fs.DATASET_RID}),
    )

    with pytest.raises(Exception) as excinfo:
        CopyService().copy_resource(fs.DATASET_RID, TARGET)

    assert getattr(excinfo.value, "name", None) == "ResourceNotFound"
