"""Tests for CopyService against a real FoundryClient (only HTTP is faked).

Every step goes through the SDK: the resource and folder side
(``Resource.get``, ``Folder.create``, ``Folder.children``) and the dataset side
(``Dataset.create``, ``File.list``, ``Transaction.create``, ``File.content``,
``File.upload``, ``Transaction.commit``/``abort``, ``Dataset.get_schema``,
``Dataset.put_schema``, and ``Resource.delete`` to clean up a failed copy).
"""

import json
import re

import pytest
from foundry_sdk import PermissionDeniedError
from foundry_sdk.v2.datasets.models import Dataset
from foundry_sdk.v2.filesystem.models import Folder, Resource

from pltr.contract import PltrError
from pltr.services.copy import CopyService, dataframe_reader_for
from tests import foundry_json as fj
from tests import foundry_json_dataset as dj
from tests import foundry_json_filesystem as fs

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

API = "/api/v2/datasets"
SOURCE_DATASET = fs.child_resource(fs.DATASET_RID, "Source Dataset")
SOURCE_FOLDER = fs.child_resource(
    "ri.compass.main.folder.source", "Source", "COMPASS_FOLDER"
)
TARGET = "ri.compass.main.folder.target"
#: The target folder, a sibling of SOURCE_FOLDER (a folder copy reads it to
#: check that it isn't inside the source).
TARGET_FOLDER = fs.child_resource(TARGET, "Target", "COMPASS_FOLDER")
NEW_DATASET_RID = "ri.foundry.main.dataset.new"
NEW_DATASET = fs.dataset(NEW_DATASET_RID, "Source Dataset-copy", TARGET)
SCHEMA = dj.schema_response()
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


def calls(stub):
    return [(request.method, request.url.path) for request in stub.requests]


def queue_files_copy(stub, paths=("data/part-0.csv",)):
    """Queue the responses of a dataset copy up to the commit of its files."""
    stub.respond(json=SOURCE_DATASET)  # Resource.get
    stub.respond(json=NEW_DATASET)  # Dataset.create
    stub.respond(json=fs.page([fs.dataset_file(path) for path in paths]))
    stub.respond(json=fs.transaction())  # Transaction.create
    for path in paths:
        stub.respond(content=b"col\n1\n")  # File.content
        stub.respond(json=fs.dataset_file(path))  # File.upload
    stub.respond(json=fs.transaction(status="COMMITTED"))


FILES_COPY_CALLS = [
    ("GET", f"/api/v2/filesystem/resources/{fs.DATASET_RID}"),
    ("POST", API),
    ("GET", f"{API}/{fs.DATASET_RID}/files"),
    ("POST", f"{API}/{NEW_DATASET_RID}/transactions"),
    ("GET", f"{API}/{fs.DATASET_RID}/files/data/part-0.csv/content"),
    ("POST", f"{API}/{NEW_DATASET_RID}/files/data/part-0.csv/upload"),
    ("POST", f"{API}/{NEW_DATASET_RID}/transactions/{fs.TRANSACTION_RID}/commit"),
]
SCHEMA_COPY_CALLS = [
    ("GET", f"{API}/{fs.DATASET_RID}/getSchema"),
    ("PUT", f"{API}/{NEW_DATASET_RID}/putSchema"),
]
TRASH_CALL = ("DELETE", f"/api/v2/filesystem/resources/{NEW_DATASET_RID}")


# ------------------------------------------------------------------ datasets


def test_copy_dataset_dry_run_creates_nothing(stub_foundry_http):
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
    assert requests_summary(stub_foundry_http) == [
        ("GET", f"/api/v2/filesystem/resources/{fs.DATASET_RID}", None)
    ]


def test_copy_dataset_copies_files_then_the_schema(stub_foundry_http, capsys):
    queue_files_copy(stub_foundry_http)
    stub_foundry_http.respond(json=SCHEMA)  # Dataset.get_schema
    stub_foundry_http.respond(json=SCHEMA)  # Dataset.put_schema

    result = CopyService(branch="dev").copy_resource(fs.DATASET_RID, TARGET)

    [created] = result.items
    assert isinstance(created, Dataset)  # the model Dataset.create returned
    assert (created.rid, created.name, created.parent_folder_rid) == (
        NEW_DATASET_RID,
        "Source Dataset-copy",
        TARGET,
    )
    assert (result.stats.datasets, result.failures) == (1, [])
    # A schema applies to a committed transaction, so it is copied last.
    assert calls(stub_foundry_http) == FILES_COPY_CALLS + SCHEMA_COPY_CALLS
    _, create, listing, start, content, upload, _, get_schema, put_schema = (
        stub_foundry_http.requests
    )
    assert json.loads(create.content) == {
        "name": "Source Dataset-copy",
        "parentFolderRid": TARGET,
    }
    assert dict(listing.url.params) == {"branchName": "dev"}
    assert dict(start.url.params) == {"branchName": "dev"}
    assert json.loads(start.content) == {"transactionType": "SNAPSHOT"}
    assert dict(content.url.params) == {"branchName": "dev"}
    # transaction or branch, never both (InvalidParameterCombination)
    assert dict(upload.url.params) == {"transactionRid": fs.TRANSACTION_RID}
    assert upload.content == b"col\n1\n"
    assert dict(get_schema.url.params) == {"branchName": "dev"}
    assert json.loads(put_schema.content) == {
        "branchName": "dev",
        "endTransactionRid": fs.TRANSACTION_RID,
        "schema": SCHEMA["schema"],
        "dataframeReader": "CSV",  # every copied file is a .csv file
    }
    err = capsys.readouterr().err
    assert f"Committed transaction {fs.TRANSACTION_RID}" in err
    assert "Copied dataset schema (CSV reader)" in err


def test_copy_dataset_reads_every_page_of_files(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_DATASET)
    stub_foundry_http.respond(json=NEW_DATASET)
    stub_foundry_http.respond(json=fs.page([fs.dataset_file("a.parquet")], "p2"))
    stub_foundry_http.respond(json=fs.page([fs.dataset_file("b.parquet")]))
    stub_foundry_http.respond(json=fs.transaction())
    for path in ("a.parquet", "b.parquet"):
        stub_foundry_http.respond(content=b"PAR1")
        stub_foundry_http.respond(json=fs.dataset_file(path))
    stub_foundry_http.respond(json=fs.transaction(status="COMMITTED"))
    stub_foundry_http.respond(json=SCHEMA)
    stub_foundry_http.respond(json=SCHEMA)

    CopyService().copy_resource(fs.DATASET_RID, TARGET)

    requests = stub_foundry_http.requests
    listings = [
        dict(request.url.params)
        for request in requests
        if request.url.path == f"{API}/{fs.DATASET_RID}/files"
    ]
    assert listings == [
        {"branchName": "master"},
        {"branchName": "master", "pageToken": "p2"},
    ]
    uploads = [r.url.path for r in requests if r.url.path.endswith("/upload")]
    assert uploads == [
        f"{API}/{NEW_DATASET_RID}/files/a.parquet/upload",
        f"{API}/{NEW_DATASET_RID}/files/b.parquet/upload",
    ]
    # Parquet files: the API's default reader, so none is sent.
    assert "dataframeReader" not in json.loads(requests[-1].content)


def test_copy_dataset_without_a_source_schema(stub_foundry_http, capsys):
    queue_files_copy(stub_foundry_http)
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "SchemaNotFound",
            parameters={"datasetRid": fs.DATASET_RID, "branchName": "master"},
        ),
    )

    result = CopyService().copy_resource(fs.DATASET_RID, TARGET)

    assert [item.rid for item in result.items] == [NEW_DATASET_RID]
    assert result.failures == []
    assert calls(stub_foundry_http) == FILES_COPY_CALLS + SCHEMA_COPY_CALLS[:1]
    assert "Source dataset has no schema to copy" in capsys.readouterr().err


def test_copy_dataset_with_no_schema_option(stub_foundry_http):
    queue_files_copy(stub_foundry_http)

    CopyService(copy_schema=False).copy_resource(fs.DATASET_RID, TARGET)

    assert calls(stub_foundry_http) == FILES_COPY_CALLS


def test_copy_dataset_without_files_commits_nothing(stub_foundry_http, capsys):
    stub_foundry_http.respond(json=SOURCE_DATASET)
    stub_foundry_http.respond(json=NEW_DATASET)
    stub_foundry_http.respond(json=fs.page([]))

    result = CopyService().copy_resource(fs.DATASET_RID, TARGET)

    assert [item.rid for item in result.items] == [NEW_DATASET_RID]
    # No transaction, so no schema either (a schema needs a committed one).
    assert calls(stub_foundry_http) == FILES_COPY_CALLS[:3]
    err = capsys.readouterr().err
    assert "has no files on branch 'master'" in err
    assert "no schema to copy either" in err


def test_failed_file_copy_is_rolled_back_trashed_and_raised(stub_foundry_http, capsys):
    stub_foundry_http.respond(json=SOURCE_DATASET)
    stub_foundry_http.respond(json=NEW_DATASET)
    stub_foundry_http.respond(json=fs.page([fs.dataset_file("data/part-0.csv")]))
    stub_foundry_http.respond(json=fs.transaction())
    stub_foundry_http.respond(content=b"col\n1\n")
    stub_foundry_http.respond(403, json=UPLOAD_DENIED)
    stub_foundry_http.respond(json=fs.transaction(status="ABORTED"))  # abort
    stub_foundry_http.respond(204)  # Resource.delete

    with pytest.raises(RuntimeError, match="Failed to copy the files") as excinfo:
        CopyService().copy_resource(fs.DATASET_RID, TARGET)

    # the SDK error is the cause, so the error layer can classify it
    cause = excinfo.value.__cause__
    assert isinstance(cause, PermissionDeniedError)
    assert cause.name == "UploadFilePermissionDenied"
    assert calls(stub_foundry_http) == FILES_COPY_CALLS[:6] + [
        ("POST", f"{API}/{NEW_DATASET_RID}/transactions/{fs.TRANSACTION_RID}/abort"),
        TRASH_CALL,
    ]
    err = capsys.readouterr().err
    assert "Removing the partly copied dataset" in err
    assert f"Moved dataset {NEW_DATASET_RID} to the trash" in err


def test_failed_schema_copy_trashes_the_copy_and_raises(stub_foundry_http, capsys):
    queue_files_copy(stub_foundry_http)
    stub_foundry_http.respond(json=SCHEMA)
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "PutDatasetSchemaPermissionDenied",
            "PERMISSION_DENIED",
            {"datasetRid": NEW_DATASET_RID},
        ),
    )
    stub_foundry_http.respond(204)  # Resource.delete

    with pytest.raises(RuntimeError, match="Failed to copy the schema") as excinfo:
        CopyService().copy_resource(fs.DATASET_RID, TARGET)

    cause = excinfo.value.__cause__
    assert isinstance(cause, PermissionDeniedError)
    assert cause.name == "PutDatasetSchemaPermissionDenied"
    assert calls(stub_foundry_http) == (
        FILES_COPY_CALLS + SCHEMA_COPY_CALLS + [TRASH_CALL]
    )
    assert "Removing the partly copied dataset" in capsys.readouterr().err


def test_failed_cleanup_is_reported_and_the_copy_error_raised(
    stub_foundry_http, capsys
):
    stub_foundry_http.respond(json=SOURCE_DATASET)
    stub_foundry_http.respond(json=NEW_DATASET)
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "ListFilesPermissionDenied",
            "PERMISSION_DENIED",
            {"datasetRid": fs.DATASET_RID},
        ),
    )
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "DeleteResourcePermissionDenied",
            "PERMISSION_DENIED",
            {"resourceRid": NEW_DATASET_RID},
        ),
    )

    with pytest.raises(RuntimeError, match="Failed to copy the files") as excinfo:
        CopyService().copy_resource(fs.DATASET_RID, TARGET)

    assert excinfo.value.__cause__.name == "ListFilesPermissionDenied"
    assert calls(stub_foundry_http)[-1] == TRASH_CALL
    err = capsys.readouterr().err
    assert f"Could not remove dataset {NEW_DATASET_RID}" in err
    assert "DeleteResourcePermissionDenied" in err


@pytest.mark.parametrize(
    ("paths", "reader"),
    [
        (["a.csv", "dir/B.CSV"], "CSV"),
        (["a.avro"], "AVRO"),
        (["spark/part-0.snappy.parquet"], None),
        (["a.csv", "b.parquet"], None),  # mixed: the API's default
        (["a.csv", "_SUCCESS"], None),
        ([], None),
    ],
)
def test_dataframe_reader_for(paths, reader):
    assert dataframe_reader_for(paths) == reader


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
    stub_foundry_http.respond(json=TARGET_FOLDER)
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
        ("GET", f"/api/v2/filesystem/resources/{TARGET}", None),
        ("POST", "/api/v2/filesystem/folders", None),
        ("GET", children_path(SOURCE_FOLDER["rid"]), None),
        ("GET", children_path(SOURCE_FOLDER["rid"]), "p2"),
        ("POST", "/api/v2/filesystem/folders", None),
        ("GET", children_path(sub["rid"]), None),
    ]
    first_create = json.loads(stub_foundry_http.requests[2].content)
    assert first_create == {"displayName": "Source-copy", "parentFolderRid": TARGET}
    nested_create = json.loads(stub_foundry_http.requests[5].content)
    assert nested_create["parentFolderRid"] == "ri.compass.main.folder.new"


def test_copy_folder_skips_unsupported_children(stub_foundry_http, capsys):
    analysis = fs.child_resource("ri.contour.main.analysis.a", "A", "CONTOUR_ANALYSIS")
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(json=TARGET_FOLDER)
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
    stub.respond(json=TARGET_FOLDER)
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
    assert len(stub_foundry_http.requests) == 5  # nothing after the failure


def test_listing_failure_after_creating_the_folder_is_recorded(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(json=TARGET_FOLDER)
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


def test_copy_folder_dry_run_lists_the_sources(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(json=TARGET_FOLDER)
    stub_foundry_http.respond(json=fs.page([SOURCE_DATASET]))

    result = CopyService(dry_run=True).copy_resource(
        SOURCE_FOLDER["rid"], TARGET, recursive=True
    )

    assert [item.rid for item in result.items] == [
        SOURCE_FOLDER["rid"],
        fs.DATASET_RID,
    ]
    assert all(isinstance(item, Resource) for item in result.items)
    # Nothing is created: only the source, the target and the children are read.
    assert [request.method for request in stub_foundry_http.requests] == [
        "GET",
        "GET",
        "GET",
    ]


def test_copy_folder_with_a_dataset(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(json=TARGET_FOLDER)
    stub_foundry_http.respond(
        json=fj.folder("ri.compass.main.folder.new", "Source-copy")
    )
    stub_foundry_http.respond(json=fs.page([SOURCE_DATASET]))
    stub_foundry_http.respond(
        json=fs.dataset(
            NEW_DATASET_RID, "Source Dataset-copy", "ri.compass.main.folder.new"
        )
    )
    stub_foundry_http.respond(json=fs.page([fs.dataset_file("data/part-0.csv")]))
    stub_foundry_http.respond(json=fs.transaction())
    stub_foundry_http.respond(content=b"col\n1\n")
    stub_foundry_http.respond(json=fs.dataset_file("data/part-0.csv"))
    stub_foundry_http.respond(json=fs.transaction(status="COMMITTED"))
    stub_foundry_http.respond(json=SCHEMA)
    stub_foundry_http.respond(json=SCHEMA)

    result = CopyService().copy_resource(SOURCE_FOLDER["rid"], TARGET, recursive=True)

    assert [type(item) for item in result.items] == [Folder, Dataset]
    assert result.stats.as_dict() == {
        "folders_copied": 1,
        "datasets_copied": 1,
        "skipped": 0,
        "errors": 0,
    }
    create_dataset = stub_foundry_http.requests[4]
    assert json.loads(create_dataset.content) == {
        "name": "Source Dataset-copy",
        "parentFolderRid": "ri.compass.main.folder.new",
    }
    assert calls(stub_foundry_http)[-1] == SCHEMA_COPY_CALLS[-1]


# --------------------------------------------------- a folder into itself


@pytest.mark.parametrize("dry_run", [False, True])
def test_copy_folder_into_itself_is_refused(stub_foundry_http, dry_run):
    stub_foundry_http.respond(json=SOURCE_FOLDER)

    with pytest.raises(PltrError, match="into itself") as excinfo:
        CopyService(dry_run=dry_run).copy_resource(
            SOURCE_FOLDER["rid"], SOURCE_FOLDER["rid"], recursive=True
        )

    assert excinfo.value.error_type == "usage_error"
    assert excinfo.value.exit_code == 2
    assert SOURCE_FOLDER["parentFolderRid"] in excinfo.value.hint
    assert len(stub_foundry_http.requests) == 1  # nothing created


@pytest.mark.parametrize("dry_run", [False, True])
def test_copy_folder_into_a_folder_inside_it_is_refused(stub_foundry_http, dry_run):
    inside = fs.child_resource(TARGET, "Deeper", "COMPASS_FOLDER")
    inside["path"] = SOURCE_FOLDER["path"] + "/Sub/Deeper"
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(json=inside)

    with pytest.raises(PltrError, match="is inside it") as excinfo:
        CopyService(dry_run=dry_run).copy_resource(
            SOURCE_FOLDER["rid"], TARGET, recursive=True
        )

    assert excinfo.value.error_type == "usage_error"
    assert inside["path"] in excinfo.value.message
    assert [request.method for request in stub_foundry_http.requests] == [
        "GET",
        "GET",
    ]


def test_copy_folder_next_to_a_similar_name_is_allowed(stub_foundry_http):
    """'/.../Source-old' starts with '/.../Source' but isn't inside it."""
    sibling = fs.child_resource(TARGET, "Source-old", "COMPASS_FOLDER")
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(json=sibling)
    stub_foundry_http.respond(json=fj.folder("ri.compass.main.folder.new", "Copy"))
    stub_foundry_http.respond(json=fs.page([]))

    result = CopyService().copy_resource(SOURCE_FOLDER["rid"], TARGET, recursive=True)

    assert [item.rid for item in result.items] == ["ri.compass.main.folder.new"]


class FakeCompass:
    """Folders only, with real paths: ``Resource.get``, ``Folder.create`` and
    ``Folder.children`` (a replacement for ``stub.next_response``)."""

    ROOT = "/Test Space/Test Project"

    def __init__(self) -> None:
        self.folders: dict = {}
        self.created: list = []

    def add(self, rid: str, name: str, parent: str = fs.PROJECT_RID) -> None:
        parent_path = self.folders[parent]["path"] if parent in self.folders else None
        self.folders[rid] = {
            "name": name,
            "parent": parent,
            "path": f"{parent_path or self.ROOT}/{name}",
            "children": [],
        }
        if parent in self.folders:
            self.folders[parent]["children"].append(rid)

    def resource(self, rid: str) -> dict:
        folder = self.folders[rid]
        body = fs.child_resource(
            rid, folder["name"], "COMPASS_FOLDER", parent=folder["parent"]
        )
        body["path"] = folder["path"]
        return body

    def __call__(self, request):
        path = request.url.path
        if request.method == "GET" and path.startswith("/api/v2/filesystem/resources/"):
            return 200, {"json": self.resource(path.rsplit("/", 1)[1])}
        if request.method == "POST" and path == "/api/v2/filesystem/folders":
            assert len(self.created) < 10, "runaway copy"
            body = json.loads(request.content)
            rid = f"ri.compass.main.folder.copy-{len(self.created)}"
            self.add(rid, body["displayName"], body["parentFolderRid"])
            self.created.append(rid)
            folder = fj.folder(
                rid, body["displayName"], parentFolderRid=body["parentFolderRid"]
            )
            return 200, {"json": folder}
        match = re.fullmatch(r"/api/v2/filesystem/folders/([^/]+)/children", path)
        if request.method == "GET" and match:
            children = self.folders[match.group(1)]["children"]
            return 200, {"json": fs.page([self.resource(c) for c in children])}
        raise AssertionError(f"unexpected {request.method} {request.url}")


def test_a_copy_never_copies_what_it_created(stub_foundry_http, monkeypatch, capsys):
    """Without the up-front check, copying a folder into itself used to create
    folders without end (the review's repro); now it stops at one level."""
    compass = FakeCompass()
    compass.add(SOURCE_FOLDER["rid"], "Source")
    monkeypatch.setattr(stub_foundry_http, "next_response", compass)
    monkeypatch.setattr(CopyService, "_check_target_outside", lambda *args: None)

    result = CopyService().copy_resource(
        SOURCE_FOLDER["rid"], SOURCE_FOLDER["rid"], recursive=True
    )

    assert compass.created == ["ri.compass.main.folder.copy-0"]
    assert result.stats.as_dict() == {
        "folders_copied": 1,
        "datasets_copied": 0,
        "skipped": 1,
        "errors": 0,
    }
    assert "this copy created it" in capsys.readouterr().err


def test_a_subfolder_target_missed_by_the_check_is_bounded(
    stub_foundry_http, monkeypatch
):
    compass = FakeCompass()
    compass.add(SOURCE_FOLDER["rid"], "Source")
    compass.add(TARGET, "Sub", parent=SOURCE_FOLDER["rid"])
    monkeypatch.setattr(stub_foundry_http, "next_response", compass)
    monkeypatch.setattr(CopyService, "_check_target_outside", lambda *args: None)

    result = CopyService().copy_resource(SOURCE_FOLDER["rid"], TARGET, recursive=True)

    # Source-copy in Sub, then Sub-copy in Source-copy; Sub's listing then
    # holds Source-copy, which is skipped.
    assert len(compass.created) == 2
    assert (result.stats.folders, result.stats.skipped) == (2, 1)


def test_the_check_reads_real_paths(stub_foundry_http, monkeypatch):
    compass = FakeCompass()
    compass.add(SOURCE_FOLDER["rid"], "Source")
    compass.add("ri.compass.main.folder.sub", "Sub", parent=SOURCE_FOLDER["rid"])
    compass.add(TARGET, "Deeper", parent="ri.compass.main.folder.sub")
    monkeypatch.setattr(stub_foundry_http, "next_response", compass)

    with pytest.raises(PltrError, match="Source/Sub/Deeper"):
        CopyService().copy_resource(SOURCE_FOLDER["rid"], TARGET, recursive=True)

    assert compass.created == []


def test_source_errors_propagate(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error("ResourceNotFound", parameters={"resourceRid": fs.DATASET_RID}),
    )

    with pytest.raises(Exception) as excinfo:
        CopyService().copy_resource(fs.DATASET_RID, TARGET)

    assert getattr(excinfo.value, "name", None) == "ResourceNotFound"
