"""Tests for `pltr dataset transactions` against a real FoundryClient (fake HTTP)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_dataset as dj

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

runner = CliRunner()
DATASET = dj.DATASET_RID
TRANSACTION = dj.TRANSACTION_RID
API = "/api/v2/datasets"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


@pytest.fixture
def stub(stub_foundry_http, isolated_home):
    return stub_foundry_http


@pytest.fixture
def interactive(monkeypatch):
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


def test_start_defaults_to_append_on_the_default_branch(stub):
    stub.respond(json=dj.transaction())

    result = invoke("dataset", "transactions", "start", DATASET)

    assert result.exit_code == 0, result.output
    assert TRANSACTION in result.stdout
    assert f"Opened APPEND transaction {TRANSACTION}" in result.stderr
    assert f"--transaction-rid {TRANSACTION}" in result.stderr  # next steps
    [request] = stub.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/{DATASET}/transactions",
    )
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {"transactionType": "APPEND"}


def test_start_with_type_and_branch_json(stub):
    stub.respond(json=dj.transaction(transaction_type="SNAPSHOT"))

    result = invoke(
        "dataset",
        "transactions",
        "start",
        DATASET,
        "--type",
        "snapshot",
        "--branch",
        "dev",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dj.sdk_json(
        dj.transaction(transaction_type="SNAPSHOT")
    )
    assert result.stderr == ""  # next steps are informational: not in JSON mode
    [request] = stub.requests
    assert dict(request.url.params) == {"branchName": "dev"}
    assert json.loads(request.content) == {"transactionType": "SNAPSHOT"}


def test_start_rejects_an_unknown_type(stub):
    result = invoke("dataset", "transactions", "start", DATASET, "--type", "MERGE")

    assert result.exit_code == 2
    assert stub.requests == []


def test_start_when_a_transaction_is_already_open(stub):
    stub.respond(
        409,
        json=fj.error(
            "OpenTransactionAlreadyExists",
            "CONFLICT",
            parameters={"datasetRid": DATASET, "branchName": "master"},
        ),
    )

    result = invoke("dataset", "transactions", "start", DATASET, "-f", "json")

    assert result.exit_code == 7
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"], error["statusCode"]) == (
        "conflict",
        "OpenTransactionAlreadyExists",
        409,
    )


def test_commit(stub):
    committed = dj.transaction(status="COMMITTED", closed_time=dj.CLOSED_TIME)
    stub.respond(json=committed)

    result = invoke(
        "dataset", "transactions", "commit", DATASET, TRANSACTION, "-f", "json"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dj.sdk_json(committed)
    [request] = stub.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/{DATASET}/transactions/{TRANSACTION}/commit",
    )


def test_commit_of_a_closed_transaction(stub):
    stub.respond(
        400,
        json=fj.error(
            "TransactionNotOpen",
            "INVALID_ARGUMENT",
            parameters={
                "datasetRid": DATASET,
                "transactionRid": TRANSACTION,
                "transactionStatus": "COMMITTED",
            },
        ),
    )

    result = invoke("dataset", "transactions", "commit", DATASET, TRANSACTION)

    assert result.exit_code == 6
    assert "TransactionNotOpen" in result.stderr


def test_abort_with_yes(stub):
    aborted = dj.transaction(status="ABORTED", closed_time=dj.CLOSED_TIME)
    stub.respond(json=aborted)

    result = invoke(
        "dataset", "transactions", "abort", DATASET, TRANSACTION, "--yes", "-f", "csv"
    )

    assert result.exit_code == 0, result.output
    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {
            "RID": TRANSACTION,
            "Type": "APPEND",
            "Status": "ABORTED",
            "Created": "2024-03-04T05:06:07+00:00",
            "Closed": "2024-03-04T06:07:08+00:00",
        }
    ]
    [request] = stub.requests
    assert request.url.path == f"{API}/{DATASET}/transactions/{TRANSACTION}/abort"


def test_abort_requires_yes_when_not_interactive(stub):
    result = invoke(
        "dataset", "transactions", "abort", DATASET, TRANSACTION, "-f", "json"
    )

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub.requests == []


def test_abort_prompts_when_interactive(stub, interactive):
    stub.respond(json=dj.transaction(status="ABORTED", closed_time=dj.CLOSED_TIME))

    result = invoke(
        "dataset", "transactions", "abort", DATASET, TRANSACTION, input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert f"Abort transaction {TRANSACTION}" in result.stderr
    assert len(stub.requests) == 1


def test_status(stub):
    stub.respond(json=dj.transaction(status="COMMITTED", closed_time=dj.CLOSED_TIME))

    result = invoke("dataset", "transactions", "status", DATASET, TRANSACTION)

    assert result.exit_code == 0, result.output
    for expected in (TRANSACTION, "COMMITTED", "APPEND", "2024-03-04T06:07:08+00:00"):
        assert expected in result.stdout
    [request] = stub.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/{DATASET}/transactions/{TRANSACTION}",
    )


def test_list_is_beta_and_paged(stub):
    first = dj.page([dj.transaction()], "t2")
    stub.respond(json=first)

    result = invoke("dataset", "transactions", "list", DATASET, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dj.sdk_json(first)
    [request] = stub.requests
    assert request.url.path == f"{API}/{DATASET}/transactions"
    assert dict(request.url.params) == {"preview": "true"}


def test_list_all_pages(stub):
    stub.respond(json=dj.page([dj.transaction()], "t2"))
    stub.respond(json=dj.page([dj.transaction(dj.OTHER_TRANSACTION_RID)]))

    result = invoke("dataset", "transactions", "list", DATASET, "--all", "-f", "csv")

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [row["RID"] for row in rows] == [TRANSACTION, dj.OTHER_TRANSACTION_RID]
    assert stub.requests[1].url.params["pageToken"] == "t2"


def test_list_one_branch(stub):
    stub.respond(json=dj.page([dj.transaction()]))

    result = invoke(
        "dataset",
        "transactions",
        "list",
        DATASET,
        "--branch",
        "dev",
        "--page-size",
        "5",
    )

    assert result.exit_code == 0, result.output
    [request] = stub.requests
    assert request.url.path == f"{API}/{DATASET}/branches/dev/transactions"
    assert dict(request.url.params) == {"pageSize": "5", "preview": "true"}


def test_build(stub):
    stub.respond(json=dj.BUILD_RID)

    table = invoke("dataset", "transactions", "build", DATASET, TRANSACTION)
    stub.respond(json=dj.BUILD_RID)
    as_json = invoke(
        "dataset", "transactions", "build", DATASET, TRANSACTION, "-f", "json"
    )

    assert table.exit_code == 0, table.output
    assert dj.BUILD_RID in table.stdout
    assert json.loads(as_json.stdout) == dj.BUILD_RID
    request = stub.requests[0]
    assert request.url.path == f"{API}/{DATASET}/transactions/{TRANSACTION}/build"
    assert dict(request.url.params) == {"preview": "true"}


def test_build_of_a_transaction_without_a_build(stub):
    stub.respond(204)
    table = invoke("dataset", "transactions", "build", DATASET, TRANSACTION)
    stub.respond(204)
    as_json = invoke(
        "dataset", "transactions", "build", DATASET, TRANSACTION, "-f", "json"
    )

    assert table.exit_code == 0
    assert table.stdout == ""
    assert "No build produced" in table.stderr
    assert json.loads(as_json.stdout) is None
