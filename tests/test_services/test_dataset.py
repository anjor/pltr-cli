"""Tests for DatasetService against a real FoundryClient (only HTTP is faked).

Beta endpoints (Dataset.transactions, Dataset.jobs, Branch.transactions,
Transaction.build) must send preview=true. Every other call is GA: passing
preview= would make the SDK emit a UserWarning, which the module-level
filter turns into a failure. Transactions and uploads are covered in
test_dataset_transactions.py.
"""

import base64
import json

import pytest
from foundry_sdk.v2.core.models import DatasetSchema
from foundry_sdk.v2.datasets.models import (
    Branch,
    Dataset,
    File,
    GetDatasetSchemaResponse,
    JobDetails,
    View,
)

from pltr.contract import PltrError
from pltr.services.dataset import DatasetService, decode_arrow_rows
from tests import foundry_json as fj
from tests import foundry_json_dataset as dj

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

API = "/api/v2/datasets"
DATASET = dj.DATASET_RID


def only_request(stub):
    [request] = stub.requests
    return request


# ------------------------------------------------------------ datasets


def test_get_dataset_returns_the_model(stub_foundry_http):
    stub_foundry_http.respond(json=dj.dataset())

    dataset = DatasetService().get_dataset(DATASET)

    assert isinstance(dataset, Dataset)
    assert (dataset.rid, dataset.name, dataset.parent_folder_rid) == (
        DATASET,
        "sales",
        dj.FOLDER_RID,
    )
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("GET", f"{API}/{DATASET}")
    assert "preview" not in request.url.params


def test_get_dataset_propagates_sdk_errors(stub_foundry_http):
    from foundry_sdk.v2.datasets.errors import DatasetNotFound

    stub_foundry_http.respond(
        404, json=fj.error("DatasetNotFound", parameters={"datasetRid": DATASET})
    )

    with pytest.raises(DatasetNotFound):
        DatasetService().get_dataset(DATASET)


def test_create_sends_name_and_parent_folder(stub_foundry_http):
    stub_foundry_http.respond(json=dj.dataset())

    dataset = DatasetService().create("sales", parent_folder_rid=dj.FOLDER_RID)

    assert isinstance(dataset, Dataset)
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("POST", API)
    assert json.loads(request.content) == {
        "name": "sales",
        "parentFolderRid": dj.FOLDER_RID,
    }


def test_read_table_sends_every_option(stub_foundry_http):
    body = dj.arrow_stream({"id": [1]})
    stub_foundry_http.respond(content=body)

    table = DatasetService().read_table(
        DATASET,
        format="CSV",
        branch="dev",
        columns=["id", "region"],
        row_limit=5,
        start_transaction_rid=dj.TRANSACTION_RID,
        end_transaction_rid=dj.OTHER_TRANSACTION_RID,
    )

    assert bytes(table) == body
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{API}/{DATASET}/readTable"
    params = request.url.params
    assert params["format"] == "CSV"
    assert params["branchName"] == "dev"
    assert params.get_list("columns") == ["id", "region"]
    assert params["rowLimit"] == "5"
    assert params["startTransactionRid"] == dj.TRANSACTION_RID
    assert params["endTransactionRid"] == dj.OTHER_TRANSACTION_RID


def test_preview_rows_reads_arrow_and_decodes_rows(stub_foundry_http):
    stub_foundry_http.respond(
        content=dj.arrow_stream({"id": [1, 2], "region": ["EMEA", None]})
    )

    columns, rows = DatasetService().preview_rows(DATASET, limit=2, columns=["id"])

    assert columns == ["id", "region"]
    assert rows == [{"id": 1, "region": "EMEA"}, {"id": 2, "region": None}]
    params = only_request(stub_foundry_http).url.params
    assert dict(params) == {"format": "ARROW", "columns": "id", "rowLimit": "2"}


def test_decode_arrow_rows_base64_encodes_binary_values():
    columns, rows = decode_arrow_rows(
        dj.arrow_stream({"blob": [b"\xff\x00"], "nested": [[b"ok"]]})
    )

    assert columns == ["blob", "nested"]
    assert rows == [
        {
            "blob": base64.b64encode(b"\xff\x00").decode(),
            "nested": [base64.b64encode(b"ok").decode()],
        }
    ]


def test_decode_arrow_rows_of_an_empty_response():
    assert decode_arrow_rows(None) == ([], [])
    assert decode_arrow_rows(b"") == ([], [])


# -------------------------------------------------------------- schema


def test_get_dataset_schema_decodes_the_response(stub_foundry_http):
    stub_foundry_http.respond(json=dj.schema_response())

    response = DatasetService().get_dataset_schema(
        DATASET, branch="dev", version_id=dj.VERSION_ID
    )

    assert isinstance(response, GetDatasetSchemaResponse)
    assert [f.name for f in response.schema_.field_schema_list] == [
        "id",
        "region",
        "amount",
        "tags",
    ]
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("GET", f"{API}/{DATASET}/getSchema")
    assert dict(request.url.params) == {"branchName": "dev", "versionId": dj.VERSION_ID}


def test_put_schema_accepts_the_api_json_form(stub_foundry_http):
    stub_foundry_http.respond(json=dj.schema_response())
    schema = {"fieldSchemaList": [dj.field("id", "LONG", nullable=False)]}

    response = DatasetService().put_schema(
        DATASET,
        schema,
        branch="dev",
        transaction_rid=dj.TRANSACTION_RID,
        dataframe_reader="CSV",
    )

    assert isinstance(response, GetDatasetSchemaResponse)
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("PUT", f"{API}/{DATASET}/putSchema")
    assert json.loads(request.content) == {
        "schema": schema,
        "branchName": "dev",
        "endTransactionRid": dj.TRANSACTION_RID,
        "dataframeReader": "CSV",
    }


def test_put_schema_accepts_a_model_and_omits_unset_options(stub_foundry_http):
    stub_foundry_http.respond(json=dj.schema_response())
    schema = DatasetSchema.model_validate({"fieldSchemaList": [dj.field("id", "LONG")]})

    DatasetService().put_schema(DATASET, schema)

    assert json.loads(only_request(stub_foundry_http).content) == {
        "schema": {"fieldSchemaList": [dj.field("id", "LONG")]}
    }


def test_infer_schema_from_csv(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text(
        "id,unit price,is-active,day,seen at,name,empty\n"
        "1,2.5,true,2024-01-02,2024-01-02 03:04:05,a,\n"
        "2,,false,2024-01-03,2024-01-03 03:04:05,b,\n"
        "3,4\n",  # short row: missing values count as empty
        encoding="utf-8",
    )

    schema = DatasetService.__new__(DatasetService).infer_schema_from_csv(path)

    assert [(f.name, f.type, f.nullable) for f in schema.field_schema_list] == [
        ("id", "INTEGER", False),
        ("unit_price", "DOUBLE", True),
        ("is_active", "BOOLEAN", True),
        ("day", "DATE", True),
        ("seen_at", "TIMESTAMP", True),
        ("name", "STRING", True),
        ("empty", "STRING", True),
    ]


def test_infer_schema_from_csv_without_header(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="no header row"):
        DatasetService.__new__(DatasetService).infer_schema_from_csv(path)


def test_apply_schema_infers_then_applies_over_direct_http(stub_foundry_http):
    stub_foundry_http.respond(json=dj.inference_response())
    stub_foundry_http.respond(json=dj.metadata_response())

    result = DatasetService().apply_schema(DATASET, "feature/x")

    assert result == dj.metadata_response()
    infer, apply = stub_foundry_http.requests
    assert infer.method == apply.method == "POST"
    # the branch is percent-encoded into the path
    assert infer.url.raw_path.decode() == (
        f"/foundry-schema-inference/api/datasets/{DATASET}/branches/feature%2Fx/schema"
    )
    assert json.loads(infer.content) == {}
    assert apply.url.raw_path.decode() == (
        f"/foundry-metadata/api/schemas/datasets/{DATASET}/branches/feature%2Fx"
    )
    assert json.loads(apply.content) == dj.inference_response()["data"]["foundrySchema"]
    assert apply.headers["Authorization"] == "Bearer test-token"


def test_apply_schema_without_an_inferred_schema_is_an_api_error(stub_foundry_http):
    stub_foundry_http.respond(json={"data": {}})

    with pytest.raises(PltrError) as excinfo:
        DatasetService().apply_schema(DATASET)

    assert excinfo.value.error_type == "api_error"
    assert excinfo.value.exit_code == 7
    assert len(stub_foundry_http.requests) == 1  # nothing was applied


def test_apply_schema_http_errors_propagate(stub_foundry_http):
    import requests

    stub_foundry_http.respond(404, json=fj.error("DatasetNotFound"))

    with pytest.raises(requests.HTTPError):
        DatasetService().apply_schema(DATASET)


def test_apply_schema_with_an_empty_metadata_response(stub_foundry_http):
    stub_foundry_http.respond(json=dj.inference_response())
    stub_foundry_http.respond(204)

    assert DatasetService().apply_schema(DATASET) is None


# ------------------------------------------------------------ branches


def test_list_branches_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(json=dj.page([dj.branch(), dj.branch("dev", None)], "t2"))

    page = DatasetService().list_branches(DATASET, page_size=2, page_token="t1")

    assert [b.name for b in page.data] == ["master", "dev"]
    assert isinstance(page.data[0], Branch)
    assert page.next_page_token == "t2"
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{API}/{DATASET}/branches"
    assert dict(request.url.params) == {"pageSize": "2", "pageToken": "t1"}


def test_get_branch(stub_foundry_http):
    stub_foundry_http.respond(json=dj.branch("dev"))

    branch = DatasetService().get_branch(DATASET, "dev")

    assert (branch.name, branch.transaction_rid) == ("dev", dj.TRANSACTION_RID)
    assert only_request(stub_foundry_http).url.path == f"{API}/{DATASET}/branches/dev"


def test_create_branch_sends_name_and_transaction(stub_foundry_http):
    stub_foundry_http.respond(json=dj.branch("dev"))

    DatasetService().create_branch(DATASET, "dev", transaction_rid=dj.TRANSACTION_RID)

    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("POST", f"{API}/{DATASET}/branches")
    assert json.loads(request.content) == {
        "name": "dev",
        "transactionRid": dj.TRANSACTION_RID,
    }


def test_create_branch_without_transaction(stub_foundry_http):
    stub_foundry_http.respond(json=dj.branch("empty", None))

    DatasetService().create_branch(DATASET, "empty")

    assert json.loads(only_request(stub_foundry_http).content) == {"name": "empty"}


def test_delete_branch(stub_foundry_http):
    stub_foundry_http.respond(204)

    assert DatasetService().delete_branch(DATASET, "dev") is None

    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "DELETE",
        f"{API}/{DATASET}/branches/dev",
    )


def test_list_branch_transactions_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=dj.page([dj.transaction()]))

    page = DatasetService().list_branch_transactions(DATASET, "dev", page_size=5)

    assert page.data[0].rid == dj.TRANSACTION_RID
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{API}/{DATASET}/branches/dev/transactions"
    assert dict(request.url.params) == {"pageSize": "5", "preview": "true"}


# --------------------------------------------------------------- files


def test_list_dataset_files_sends_every_filter(stub_foundry_http):
    stub_foundry_http.respond(json=dj.page([dj.file()], "next"))

    page = DatasetService().list_dataset_files(
        DATASET,
        branch="dev",
        path_prefix="data/",
        start_transaction_rid=dj.TRANSACTION_RID,
        end_transaction_rid=dj.TRANSACTION_RID,
        page_size=10,
    )

    assert isinstance(page.data[0], File)
    assert page.data[0].size_bytes == 1024
    assert page.next_page_token == "next"
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{API}/{DATASET}/files"
    assert dict(request.url.params) == {
        "branchName": "dev",
        "pathPrefix": "data/",
        "startTransactionRid": dj.TRANSACTION_RID,
        "endTransactionRid": dj.TRANSACTION_RID,
        "pageSize": "10",
    }


def test_get_file_encodes_the_file_path(stub_foundry_http):
    stub_foundry_http.respond(json=dj.file("data/sales 2024.csv"))

    file = DatasetService().get_file(DATASET, "data/sales 2024.csv", branch="dev")

    assert file.path == "data/sales 2024.csv"
    request = only_request(stub_foundry_http)
    assert request.url.raw_path.decode() == (
        f"{API}/{DATASET}/files/data%2Fsales%202024.csv?branchName=dev"
    )


def test_download_file_streams_content_to_disk(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(content=b"id,region\n1,EMEA\n")
    target = tmp_path / "nested" / "sales.csv"

    written = DatasetService().download_file(
        DATASET, "data/sales.csv", target, end_transaction_rid=dj.TRANSACTION_RID
    )

    assert written == 17
    assert target.read_bytes() == b"id,region\n1,EMEA\n"
    assert [p.name for p in target.parent.iterdir()] == ["sales.csv"]  # no temp file
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{API}/{DATASET}/files/data/sales.csv/content"
    assert dict(request.url.params) == {"endTransactionRid": dj.TRANSACTION_RID}


def test_failed_download_keeps_an_existing_file(stub_foundry_http, tmp_path):
    from foundry_sdk.v2.datasets.errors import FileNotFoundOnBranch

    target = tmp_path / "sales.csv"
    target.write_text("previous")
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "FileNotFoundOnBranch",
            parameters={
                "datasetRid": DATASET,
                "branchName": "master",
                "path": "data/sales.csv",
            },
        ),
    )

    with pytest.raises(FileNotFoundOnBranch):
        DatasetService().download_file(DATASET, "data/sales.csv", target)

    assert target.read_text() == "previous"
    assert [p.name for p in tmp_path.iterdir()] == ["sales.csv"]


def test_interrupted_download_leaves_no_partial_file(
    stub_foundry_http, tmp_path, monkeypatch
):
    from foundry_sdk._core.api_client import StreamedApiResponse

    def broken_stream(self, chunk_size=None):
        yield b"first chunk"
        raise ConnectionError("connection reset")

    monkeypatch.setattr(StreamedApiResponse, "iter_bytes", broken_stream)
    stub_foundry_http.respond(content=b"irrelevant")
    target = tmp_path / "sales.csv"

    with pytest.raises(ConnectionError):
        DatasetService().download_file(DATASET, "data/sales.csv", target)

    assert list(tmp_path.iterdir()) == []


def test_delete_file_on_a_branch(stub_foundry_http):
    stub_foundry_http.respond(204)

    DatasetService().delete_file(DATASET, "data/sales.csv", branch="dev")

    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "DELETE",
        f"{API}/{DATASET}/files/data/sales.csv",
    )
    assert dict(request.url.params) == {"branchName": "dev"}


def test_delete_file_in_a_transaction(stub_foundry_http):
    stub_foundry_http.respond(204)

    DatasetService().delete_file(
        DATASET, "data/sales.csv", transaction_rid=dj.TRANSACTION_RID
    )

    params = only_request(stub_foundry_http).url.params
    assert dict(params) == {"transactionRid": dj.TRANSACTION_RID}


def test_delete_file_rejects_branch_and_transaction(stub_foundry_http):
    with pytest.raises(ValueError, match="not both"):
        DatasetService().delete_file(
            DATASET, "a.csv", branch="dev", transaction_rid=dj.TRANSACTION_RID
        )
    assert stub_foundry_http.requests == []


# --------------------------------------------------------------- views


def test_create_view_builds_backing_datasets(stub_foundry_http):
    stub_foundry_http.respond(json=dj.view())

    view = DatasetService().create_view(
        "sales_view",
        parent_folder_rid=dj.FOLDER_RID,
        backing_datasets=[(DATASET, None), (dj.OTHER_DATASET_RID, "dev")],
        branch="master",
    )

    assert isinstance(view, View)
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("POST", f"{API}/views")
    assert json.loads(request.content) == {
        "backingDatasets": [
            {"datasetRid": DATASET, "stopPropagatingMarkingIds": []},
            {
                "datasetRid": dj.OTHER_DATASET_RID,
                "branch": "dev",
                "stopPropagatingMarkingIds": [],
            },
        ],
        "parentFolderRid": dj.FOLDER_RID,
        "viewName": "sales_view",
        "branch": "master",
    }


def test_get_view(stub_foundry_http):
    stub_foundry_http.respond(json=dj.view())

    view = DatasetService().get_view(dj.VIEW_RID, branch="dev")

    assert view.backing_datasets[0].dataset_rid == DATASET
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{API}/views/{dj.VIEW_RID}"
    assert dict(request.url.params) == {"branch": "dev"}


@pytest.mark.parametrize(
    "method, http_method, endpoint",
    [
        ("add_backing_datasets", "POST", "addBackingDatasets"),
        ("remove_backing_datasets", "POST", "removeBackingDatasets"),
        ("replace_backing_datasets", "PUT", "replaceBackingDatasets"),
    ],
)
def test_backing_dataset_changes(stub_foundry_http, method, http_method, endpoint):
    stub_foundry_http.respond(json=dj.view())

    view = getattr(DatasetService(), method)(
        dj.VIEW_RID, [(DATASET, None)], branch="dev"
    )

    assert isinstance(view, View)
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        http_method,
        f"{API}/views/{dj.VIEW_RID}/{endpoint}",
    )
    assert json.loads(request.content) == {
        "branch": "dev",
        "backingDatasets": [{"datasetRid": DATASET, "stopPropagatingMarkingIds": []}],
    }


def test_add_unique_primary_key(stub_foundry_http):
    stub_foundry_http.respond(json=dj.view())

    DatasetService().add_primary_key(dj.VIEW_RID, ["id"])

    request = only_request(stub_foundry_http)
    assert request.url.path == f"{API}/views/{dj.VIEW_RID}/addPrimaryKey"
    assert json.loads(request.content) == {
        "primaryKey": {"columns": ["id"], "resolution": {"type": "unique"}}
    }


def test_add_latest_wins_primary_key(stub_foundry_http):
    stub_foundry_http.respond(json=dj.view())

    DatasetService().add_primary_key(
        dj.VIEW_RID,
        ["id", "region"],
        latest_wins_columns=["updated_at"],
        deletion_column="is_deleted",
        branch="dev",
    )

    assert json.loads(only_request(stub_foundry_http).content) == {
        "branch": "dev",
        "primaryKey": {
            "columns": ["id", "region"],
            "resolution": {
                "type": "duplicate",
                "deletionColumn": "is_deleted",
                "resolutionStrategy": {"type": "latestWins", "columns": ["updated_at"]},
            },
        },
    }


def test_unique_primary_key_takes_no_deletion_column(stub_foundry_http):
    with pytest.raises(ValueError, match="deletion_column"):
        DatasetService().add_primary_key(dj.VIEW_RID, ["id"], deletion_column="d")


# ---------------------------------------------------- schedules and jobs


def test_list_schedules_returns_schedule_rids(stub_foundry_http):
    stub_foundry_http.respond(json=dj.page([dj.SCHEDULE_RID], "t2"))

    page = DatasetService().list_schedules(DATASET, branch="dev", page_size=1)

    assert page.data == [dj.SCHEDULE_RID]
    assert page.next_page_token == "t2"
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{API}/{DATASET}/getSchedules"
    assert dict(request.url.params) == {"branchName": "dev", "pageSize": "1"}


def test_list_jobs_is_beta_and_sends_the_sort(stub_foundry_http):
    stub_foundry_http.respond(json=dj.page([dj.job()]))

    page = DatasetService().list_jobs(
        DATASET, branch="dev", order_by="BY_FINISHED_TIME", descending=False
    )

    assert isinstance(page.data[0], JobDetails)
    assert page.data[0].job_rid == dj.JOB_RID
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("POST", f"{API}/{DATASET}/jobs")
    assert dict(request.url.params) == {"branchName": "dev", "preview": "true"}
    assert json.loads(request.content) == {
        "orderBy": [{"sortType": "BY_FINISHED_TIME", "sortDirection": "ASCENDING"}]
    }


def test_list_jobs_defaults_to_newest_started_first(stub_foundry_http):
    stub_foundry_http.respond(json=dj.page([]))

    DatasetService().list_jobs(DATASET)

    assert json.loads(only_request(stub_foundry_http).content) == {
        "orderBy": [{"sortType": "BY_STARTED_TIME", "sortDirection": "DESCENDING"}]
    }


# ------------------------------------------- compat for services/copy.py
#
# CopyService (services/copy.py) reads these dict results; keep them
# working until cp migrates to the model-returning methods.


def test_compat_create_dataset_returns_the_sdk_dict(stub_foundry_http):
    stub_foundry_http.respond(json=dj.dataset())

    result = DatasetService().create_dataset("sales", dj.FOLDER_RID)

    assert result == dj.dataset()
    assert result["rid"] == DATASET  # what CopyService reads


def test_compat_get_schema_round_trips_into_put_schema(stub_foundry_http):
    stub_foundry_http.respond(json=dj.schema_response())
    stub_foundry_http.respond(json=dj.schema_response())
    service = DatasetService()

    schema = service.get_schema(DATASET).get("schema")  # what CopyService does
    service.put_schema(dj.OTHER_DATASET_RID, schema)

    _, put = stub_foundry_http.requests
    assert put.url.path == f"{API}/{dj.OTHER_DATASET_RID}/putSchema"
    assert json.loads(put.content)["schema"] == dj.schema_response()["schema"]


def test_compat_list_files_reads_every_page(stub_foundry_http):
    stub_foundry_http.respond(json=dj.page([dj.file("a.csv")], "t2"))
    stub_foundry_http.respond(json=dj.page([dj.file("b.csv")]))

    files = DatasetService().list_files(DATASET, branch="master")

    assert [f.get("path") for f in files] == ["a.csv", "b.csv"]
    first, second = stub_foundry_http.requests
    assert dict(first.url.params) == {"branchName": "master"}
    assert dict(second.url.params) == {"branchName": "master", "pageToken": "t2"}


def test_compat_create_transaction_has_a_rid_key(stub_foundry_http):
    stub_foundry_http.respond(json=dj.transaction(transaction_type="SNAPSHOT"))

    result = DatasetService().create_transaction(
        DATASET, branch="master", transaction_type="SNAPSHOT"
    )

    assert result.get("transaction_rid") or result.get("rid") == dj.TRANSACTION_RID
    request = only_request(stub_foundry_http)
    assert json.loads(request.content) == {"transactionType": "SNAPSHOT"}
    assert dict(request.url.params) == {"branchName": "master"}


def test_compat_delete_dataset_moves_it_to_the_trash(stub_foundry_http):
    stub_foundry_http.respond(204)

    DatasetService().delete_dataset(DATASET)

    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "DELETE",
        f"/api/v2/filesystem/resources/{DATASET}",
    )
    assert "preview" not in request.url.params


def test_cp_copies_a_dataset_through_the_compat_methods(stub_foundry_http):
    """`pltr cp` end to end over the real compat methods (not patched)."""
    from pltr.services.copy import CopyService

    copy_rid = dj.OTHER_DATASET_RID
    stub_foundry_http.respond(json=fj.resource(DATASET, "sales", "FOUNDRY_DATASET"))
    stub_foundry_http.respond(json=dj.dataset(copy_rid, "sales-copy"))
    stub_foundry_http.respond(json=dj.schema_response())  # get_schema
    stub_foundry_http.respond(json=dj.schema_response())  # put_schema
    stub_foundry_http.respond(json=dj.page([dj.file("data/a.csv")]))
    stub_foundry_http.respond(json=dj.transaction(transaction_type="SNAPSHOT"))
    stub_foundry_http.respond(content=b"id\n1\n")  # File.content
    stub_foundry_http.respond(json=dj.file("data/a.csv"))  # File.upload
    stub_foundry_http.respond(
        json=dj.transaction(status="COMMITTED", closed_time=dj.CLOSED_TIME)
    )

    result = CopyService().copy_resource(DATASET, dj.FOLDER_RID)

    assert [item.rid for item in result.items] == [copy_rid]
    assert [(r.method, r.url.path) for r in stub_foundry_http.requests] == [
        ("GET", f"/api/v2/filesystem/resources/{DATASET}"),
        ("POST", API),
        ("GET", f"{API}/{DATASET}/getSchema"),
        ("PUT", f"{API}/{copy_rid}/putSchema"),
        ("GET", f"{API}/{DATASET}/files"),
        ("POST", f"{API}/{copy_rid}/transactions"),
        ("GET", f"{API}/{DATASET}/files/data/a.csv/content"),
        ("POST", f"{API}/{copy_rid}/files/data/a.csv/upload"),
        ("POST", f"{API}/{copy_rid}/transactions/{dj.TRANSACTION_RID}/commit"),
    ]
    requests = stub_foundry_http.requests
    assert json.loads(requests[1].content) == {
        "name": "sales-copy",
        "parentFolderRid": dj.FOLDER_RID,
    }
    assert json.loads(requests[3].content)["schema"] == dj.schema_response()["schema"]
    assert json.loads(requests[5].content) == {"transactionType": "SNAPSHOT"}
    assert dict(requests[7].url.params) == {"transactionRid": dj.TRANSACTION_RID}
    assert requests[7].content == b"id\n1\n"
