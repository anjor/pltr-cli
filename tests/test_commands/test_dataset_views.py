"""Tests for `pltr dataset views`, `schedules` and `jobs` (real SDK, fake HTTP)."""

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
OTHER = dj.OTHER_DATASET_RID
VIEW = dj.VIEW_RID
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


def backing(rid: str, branch: str = "") -> dict:
    return dj.backing_dataset(rid, branch or None)


# ----------------------------------------------------------------- create


def test_create_view(stub):
    view = dj.view(backing=[backing(DATASET), backing(OTHER, "dev")])
    stub.respond(json=view)

    result = invoke(
        "dataset",
        "views",
        "create",
        "sales_view",
        "--parent-folder",
        dj.FOLDER_RID,
        "--backing-dataset",
        DATASET,
        "--backing-dataset",
        f"{OTHER}@dev",
        "--branch",
        "master",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == view
    [request] = stub.requests
    assert (request.method, request.url.path) == ("POST", f"{API}/views")
    assert json.loads(request.content) == {
        "backingDatasets": [backing(DATASET), backing(OTHER, "dev")],
        "parentFolderRid": dj.FOLDER_RID,
        "viewName": "sales_view",
        "branch": "master",
    }


def test_create_view_table(stub):
    stub.respond(json=dj.view(backing=[backing(DATASET), backing(OTHER, "dev")]))

    result = invoke(
        "dataset",
        "views",
        "create",
        "sales_view",
        "--parent-folder",
        dj.FOLDER_RID,
        "--backing-dataset",
        DATASET,
    )

    assert result.exit_code == 0, result.output
    assert f"Created view 'sales_view' ({VIEW})" in result.stderr
    assert f"{DATASET}, {OTHER}@dev" in result.stdout


def test_create_view_needs_a_backing_dataset(stub):
    result = invoke(
        "dataset",
        "views",
        "create",
        "v",
        "--parent-folder",
        dj.FOLDER_RID,
        "-f",
        "json",
    )

    assert result.exit_code == 2
    assert stub.requests == []


def test_create_view_rejects_a_malformed_backing_dataset(stub):
    result = invoke(
        "dataset",
        "views",
        "create",
        "v",
        "--parent-folder",
        dj.FOLDER_RID,
        "--backing-dataset",
        f"{DATASET}@",
    )

    assert result.exit_code == 2
    assert "DATASET_RID@BRANCH" in result.stderr
    assert stub.requests == []


def test_create_view_description_was_removed(stub):
    result = invoke(
        "dataset",
        "views",
        "create",
        "v",
        "--parent-folder",
        dj.FOLDER_RID,
        "--backing-dataset",
        DATASET,
        "--description",
        "text",
        "-f",
        "json",
    )

    assert result.exit_code == 2
    assert "no description" in json_lines(result.stderr)[-1]["message"]
    assert stub.requests == []
    help_text = invoke("dataset", "views", "create", "--help").stdout
    assert "--description" not in help_text  # hidden


# -------------------------------------------------------------------- get


def test_get_view(stub):
    key = {
        "columns": ["id"],
        "resolution": {
            "type": "duplicate",
            "deletionColumn": "is_deleted",
            "resolutionStrategy": {"type": "latestWins", "columns": ["updated_at"]},
        },
    }
    stub.respond(json=dj.view(primary_key=key))

    result = invoke("dataset", "views", "get", VIEW, "--branch", "dev", "-f", "csv")

    assert result.exit_code == 0, result.output
    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {
            "View Name": "sales_view",
            "RID": VIEW,
            "Parent Folder": dj.FOLDER_RID,
            "Branch": "master",
            "Backing Datasets": DATASET,
            "Primary Key": "id (duplicates resolved by latest updated_at; "
            "deletion column is_deleted)",
        }
    ]
    [request] = stub.requests
    assert request.url.path == f"{API}/views/{VIEW}"
    assert dict(request.url.params) == {"branch": "dev"}


def test_get_view_unique_key_and_json(stub):
    view = dj.view(primary_key={"columns": ["id"], "resolution": {"type": "unique"}})
    stub.respond(json=view)
    stub.respond(json=view)

    table = invoke("dataset", "views", "get", VIEW)
    as_json = invoke("dataset", "views", "get", VIEW, "-f", "json")

    assert "id (unique)" in table.stdout
    assert json.loads(as_json.stdout) == view


def test_get_view_not_found(stub):
    stub.respond(
        404,
        json=fj.error(
            "ViewNotFound", parameters={"viewDatasetRid": VIEW, "branch": "master"}
        ),
    )

    result = invoke("dataset", "views", "get", VIEW, "-f", "json")

    assert result.exit_code == 5
    assert json_lines(result.stderr)[-1]["errorName"] == "ViewNotFound"


# ------------------------------------------------------ backing datasets


def test_add_datasets(stub):
    stub.respond(json=dj.view(backing=[backing(DATASET), backing(OTHER)]))

    result = invoke("dataset", "views", "add-datasets", VIEW, OTHER, "-f", "json")

    assert result.exit_code == 0, result.output
    [request] = stub.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/views/{VIEW}/addBackingDatasets",
    )
    assert json.loads(request.content) == {"backingDatasets": [backing(OTHER)]}


@pytest.mark.parametrize(
    "command, method, endpoint",
    [
        ("remove-datasets", "POST", "removeBackingDatasets"),
        ("replace-datasets", "PUT", "replaceBackingDatasets"),
    ],
)
def test_destructive_backing_dataset_changes(stub, command, method, endpoint):
    stub.respond(json=dj.view())

    result = invoke(
        "dataset",
        "views",
        command,
        VIEW,
        DATASET,
        f"{OTHER}@dev",
        "--branch",
        "master",
        "--yes",
    )

    assert result.exit_code == 0, result.output
    [request] = stub.requests
    assert (request.method, request.url.path) == (
        method,
        f"{API}/views/{VIEW}/{endpoint}",
    )
    assert json.loads(request.content) == {
        "branch": "master",
        "backingDatasets": [backing(DATASET), backing(OTHER, "dev")],
    }


@pytest.mark.parametrize("command", ["remove-datasets", "replace-datasets"])
def test_backing_dataset_removal_needs_confirmation(stub, command):
    result = invoke("dataset", "views", command, VIEW, DATASET, "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub.requests == []


def test_replace_datasets_prompts_when_interactive(stub, interactive):
    stub.respond(json=dj.view())

    result = invoke("dataset", "views", "replace-datasets", VIEW, DATASET, input="y\n")

    assert result.exit_code == 0, result.output
    assert f"Replace the backing datasets of view {VIEW}" in result.stderr
    assert len(stub.requests) == 1


# ------------------------------------------------------------ primary key


def test_add_unique_primary_key(stub):
    view = dj.view(primary_key={"columns": ["id"], "resolution": {"type": "unique"}})
    stub.respond(json=view)

    result = invoke("dataset", "views", "add-primary-key", VIEW, "id", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == view
    [request] = stub.requests
    assert request.url.path == f"{API}/views/{VIEW}/addPrimaryKey"
    assert json.loads(request.content) == {
        "primaryKey": {"columns": ["id"], "resolution": {"type": "unique"}}
    }


def test_add_latest_wins_primary_key(stub):
    stub.respond(json=dj.view())

    result = invoke(
        "dataset",
        "views",
        "add-primary-key",
        VIEW,
        "id",
        "region",
        "--latest-wins",
        "updated_at",
        "--latest-wins",
        "version",
        "--deletion-column",
        "is_deleted",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(stub.requests[0].content)["primaryKey"] == {
        "columns": ["id", "region"],
        "resolution": {
            "type": "duplicate",
            "deletionColumn": "is_deleted",
            "resolutionStrategy": {
                "type": "latestWins",
                "columns": ["updated_at", "version"],
            },
        },
    }


def test_deletion_column_needs_latest_wins(stub):
    result = invoke(
        "dataset", "views", "add-primary-key", VIEW, "id", "--deletion-column", "d"
    )

    assert result.exit_code == 2
    assert "--latest-wins" in result.stderr
    assert stub.requests == []


# -------------------------------------------------------------- schedules


def test_schedules_list_shows_rids(stub):
    stub.respond(json=dj.page([dj.SCHEDULE_RID], "t2"))

    table = invoke("dataset", "schedules", "list", DATASET)
    stub.respond(json=dj.page([dj.SCHEDULE_RID], "t2"))
    as_json = invoke("dataset", "schedules", "list", DATASET, "-f", "json")

    assert table.exit_code == 0, table.output
    assert dj.SCHEDULE_RID in table.stdout
    assert "--page-token t2" in table.stderr
    assert json.loads(as_json.stdout) == dj.page([dj.SCHEDULE_RID], "t2")
    request = stub.requests[0]
    assert request.url.path == f"{API}/{DATASET}/getSchedules"
    assert "preview" not in request.url.params  # GA


def test_schedules_list_branch_and_csv(stub):
    stub.respond(json=dj.page([dj.SCHEDULE_RID]))

    result = invoke(
        "dataset", "schedules", "list", DATASET, "--branch", "dev", "-f", "csv"
    )

    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {"Schedule RID": dj.SCHEDULE_RID}
    ]
    assert dict(stub.requests[0].url.params) == {"branchName": "dev"}


# ------------------------------------------------------------------- jobs


def test_jobs_list_is_beta_newest_started_first(stub):
    stub.respond(json=dj.page([dj.job()]))

    result = invoke("dataset", "jobs", "list", DATASET, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dj.page([dj.job()])
    [request] = stub.requests
    assert (request.method, request.url.path) == ("POST", f"{API}/{DATASET}/jobs")
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {
        "orderBy": [{"sortType": "BY_STARTED_TIME", "sortDirection": "DESCENDING"}]
    }


def test_jobs_list_options(stub):
    stub.respond(json=dj.page([dj.job()], "t2"))
    stub.respond(json=dj.page([dj.job("ri.foundry.main.job.second")]))

    result = invoke(
        "dataset",
        "jobs",
        "list",
        DATASET,
        "--branch",
        "dev",
        "--order-by",
        "finished",
        "--ascending",
        "--page-size",
        "1",
        "--all",
        "-f",
        "csv",
    )

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [row["Job RID"] for row in rows] == [
        dj.JOB_RID,
        "ri.foundry.main.job.second",
    ]
    first, second = stub.requests
    assert dict(first.url.params) == {
        "branchName": "dev",
        "pageSize": "1",
        "preview": "true",
    }
    assert second.url.params["pageToken"] == "t2"
    assert json.loads(first.content) == {
        "orderBy": [{"sortType": "BY_FINISHED_TIME", "sortDirection": "ASCENDING"}]
    }
