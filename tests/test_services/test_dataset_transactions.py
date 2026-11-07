"""Transaction and upload tests for DatasetService (real FoundryClient, fake HTTP).

Transaction.create/get/commit/abort and File.upload are GA (no preview);
Dataset.transactions and Transaction.build are beta (preview=true).
"""

import json

import pytest
from foundry_sdk.v2.datasets.models import File, Transaction

from pltr.services.dataset import DatasetService
from tests import foundry_json as fj
from tests import foundry_json_dataset as dj

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

API = "/api/v2/datasets"
DATASET = dj.DATASET_RID
TRANSACTION = dj.TRANSACTION_RID


def only_request(stub):
    [request] = stub.requests
    return request


@pytest.mark.parametrize("transaction_type", ["APPEND", "UPDATE", "SNAPSHOT", "DELETE"])
def test_start_transaction(stub_foundry_http, transaction_type):
    stub_foundry_http.respond(json=dj.transaction(transaction_type=transaction_type))

    transaction = DatasetService().start_transaction(
        DATASET, transaction_type=transaction_type, branch="dev"
    )

    assert isinstance(transaction, Transaction)
    assert (transaction.transaction_type, transaction.status) == (
        transaction_type,
        "OPEN",
    )
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/{DATASET}/transactions",
    )
    assert dict(request.url.params) == {"branchName": "dev"}
    assert json.loads(request.content) == {"transactionType": transaction_type}


def test_start_transaction_on_the_default_branch(stub_foundry_http):
    stub_foundry_http.respond(json=dj.transaction())

    DatasetService().start_transaction(DATASET)

    request = only_request(stub_foundry_http)
    assert dict(request.url.params) == {}  # no branchName: the API's default branch
    assert json.loads(request.content) == {"transactionType": "APPEND"}


def test_start_transaction_conflict_propagates(stub_foundry_http):
    from foundry_sdk.v2.datasets.errors import OpenTransactionAlreadyExists

    stub_foundry_http.respond(
        409,
        json=fj.error(
            "OpenTransactionAlreadyExists",
            "CONFLICT",
            parameters={"datasetRid": DATASET, "branchName": "master"},
        ),
    )

    with pytest.raises(OpenTransactionAlreadyExists):
        DatasetService().start_transaction(DATASET)


def test_get_transaction(stub_foundry_http):
    stub_foundry_http.respond(
        json=dj.transaction(status="COMMITTED", closed_time=dj.CLOSED_TIME)
    )

    transaction = DatasetService().get_transaction(DATASET, TRANSACTION)

    assert transaction.status == "COMMITTED"
    assert transaction.closed_time is not None
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/{DATASET}/transactions/{TRANSACTION}",
    )


@pytest.mark.parametrize(
    "action, status", [("commit", "COMMITTED"), ("abort", "ABORTED")]
)
def test_commit_and_abort(stub_foundry_http, action, status):
    stub_foundry_http.respond(
        json=dj.transaction(status=status, closed_time=dj.CLOSED_TIME)
    )

    transaction = getattr(DatasetService(), f"{action}_transaction")(
        DATASET, TRANSACTION
    )

    assert transaction.status == status
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/{DATASET}/transactions/{TRANSACTION}/{action}",
    )
    assert "preview" not in request.url.params


def test_list_transactions_is_beta(stub_foundry_http):
    stub_foundry_http.respond(
        json=dj.page([dj.transaction(), dj.transaction(dj.OTHER_TRANSACTION_RID)], "t2")
    )

    page = DatasetService().list_transactions(DATASET, page_size=2, page_token="t1")

    assert [t.rid for t in page.data] == [TRANSACTION, dj.OTHER_TRANSACTION_RID]
    assert page.next_page_token == "t2"
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{API}/{DATASET}/transactions"
    assert dict(request.url.params) == {
        "pageSize": "2",
        "pageToken": "t1",
        "preview": "true",
    }


def test_get_transaction_build_returns_the_build_rid(stub_foundry_http):
    stub_foundry_http.respond(json=dj.BUILD_RID)

    assert DatasetService().get_transaction_build(DATASET, TRANSACTION) == dj.BUILD_RID

    request = only_request(stub_foundry_http)
    assert request.url.path == f"{API}/{DATASET}/transactions/{TRANSACTION}/build"
    assert dict(request.url.params) == {"preview": "true"}


def test_get_transaction_build_without_a_build(stub_foundry_http):
    stub_foundry_http.respond(204)

    assert DatasetService().get_transaction_build(DATASET, TRANSACTION) is None


# ------------------------------------------------------------- uploads


@pytest.fixture
def local_csv(tmp_path):
    path = tmp_path / "sales.csv"
    path.write_bytes(b"id,region\n1,EMEA\n")
    return path


def test_upload_into_an_open_transaction_sends_no_branch(stub_foundry_http, local_csv):
    """The API rejects branchName together with transactionRid
    (InvalidParameterCombination); the old service sent both."""
    stub_foundry_http.respond(json=dj.file("data/sales.csv"))

    file = DatasetService().upload_file(
        DATASET, local_csv, "data/sales.csv", transaction_rid=TRANSACTION
    )

    assert isinstance(file, File)
    request = only_request(stub_foundry_http)
    assert request.method == "POST"
    assert request.url.raw_path.decode() == (
        f"{API}/{DATASET}/files/data%2Fsales.csv/upload?transactionRid={TRANSACTION}"
    )
    assert request.headers["Content-Type"] == "application/octet-stream"
    assert request.content == b"id,region\n1,EMEA\n"


def test_upload_on_a_branch_with_a_transaction_type(stub_foundry_http, local_csv):
    stub_foundry_http.respond(json=dj.file("sales.csv"))

    DatasetService().upload_file(
        DATASET, local_csv, "sales.csv", branch="dev", transaction_type="SNAPSHOT"
    )

    params = only_request(stub_foundry_http).url.params
    assert dict(params) == {"branchName": "dev", "transactionType": "SNAPSHOT"}


def test_upload_on_the_default_branch_sends_no_parameters(stub_foundry_http, local_csv):
    stub_foundry_http.respond(json=dj.file("sales.csv"))

    DatasetService().upload_file(DATASET, local_csv, "sales.csv")

    assert dict(only_request(stub_foundry_http).url.params) == {}


def test_upload_rejects_branch_and_transaction(stub_foundry_http, local_csv):
    with pytest.raises(ValueError, match="not both"):
        DatasetService().upload_file(
            DATASET, local_csv, "sales.csv", branch="dev", transaction_rid=TRANSACTION
        )
    assert stub_foundry_http.requests == []


def test_upload_of_a_missing_file(stub_foundry_http, tmp_path):
    with pytest.raises(FileNotFoundError):
        DatasetService().upload_file(DATASET, tmp_path / "missing.csv", "missing.csv")
    assert stub_foundry_http.requests == []
