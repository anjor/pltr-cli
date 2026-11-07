"""Tests for `pltr cp` against a real FoundryClient (only HTTP is faked).

Dataset steps that go through the dataset area's DatasetService
compatibility methods are patched as in tests/test_services/test_copy.py.
"""

import csv
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from pltr.services.dataset import DatasetService
from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()
SOURCE_DATASET = fs.child_resource(fs.DATASET_RID, "Source Dataset")
SOURCE_FOLDER = fs.child_resource(
    "ri.compass.main.folder.source", "Source", "COMPASS_FOLDER"
)
TARGET = "ri.compass.main.folder.target"
NEW_FOLDER = fj.folder(
    "ri.compass.main.folder.new", "Source-copy", parentFolderRid=TARGET
)
NEW_DATASET_RID = "ri.foundry.main.dataset.new"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


@pytest.fixture
def dataset_compat():
    def fake_download(self, dataset_rid, file_path, output_path, branch="master"):
        Path(output_path).write_bytes(b"data")

    with (
        patch.object(
            DatasetService,
            "create_dataset",
            autospec=True,
            return_value={"rid": NEW_DATASET_RID},
        ),
        patch.object(
            DatasetService, "get_schema", autospec=True, return_value={"schema": None}
        ),
        patch.object(DatasetService, "put_schema", autospec=True),
        patch.object(
            DatasetService,
            "list_files",
            autospec=True,
            return_value=[{"path": "part-0.csv"}],
        ),
        patch.object(
            DatasetService,
            "create_transaction",
            autospec=True,
            return_value={"transaction_rid": fs.TRANSACTION_RID},
        ),
        patch.object(
            DatasetService, "download_file", autospec=True, side_effect=fake_download
        ),
        patch.object(DatasetService, "commit_transaction", autospec=True),
        patch.object(DatasetService, "abort_transaction", autospec=True),
        patch.object(DatasetService, "delete_dataset", autospec=True),
    ):
        yield


def test_cp_dataset_json_prints_the_created_dataset(stub_foundry_http, dataset_compat):
    stub_foundry_http.respond(json=SOURCE_DATASET)
    stub_foundry_http.respond(json=fs.dataset_file("part-0.csv"))

    result = invoke("cp", fs.DATASET_RID, TARGET, "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [
            fs.dataset(NEW_DATASET_RID, "Source Dataset-copy", TARGET),
        ]
    }
    assert result.stderr == ""  # progress messages are suppressed in JSON mode


def test_cp_dataset_table_reports_progress_on_stderr(stub_foundry_http, dataset_compat):
    stub_foundry_http.respond(json=SOURCE_DATASET)
    stub_foundry_http.respond(json=fs.dataset_file("part-0.csv"))

    result = invoke("cp", fs.DATASET_RID, TARGET, "--name-suffix", " (copy)")

    assert result.exit_code == 0, result.output
    for expected in ("FOUNDRY_DATASET", "Source Dataset (copy)", NEW_DATASET_RID):
        assert expected in result.stdout
    assert "Copying dataset 'Source Dataset'" in result.stderr
    assert "Copied 0 folder(s) and 1 dataset(s); 0 skipped, 0 failed" in result.stderr
    assert "Copying" not in result.stdout


def test_cp_folder_recursive(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(json=NEW_FOLDER)
    stub_foundry_http.respond(json=fs.page([]))

    result = invoke("cp", SOURCE_FOLDER["rid"], TARGET, "-r", "-f", "csv")

    assert result.exit_code == 0, result.output
    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {
            "Type": "COMPASS_FOLDER",
            "Name": "Source-copy",
            "RID": NEW_FOLDER["rid"],
            "Parent Folder": TARGET,
        }
    ]


def test_cp_folder_without_recursive_is_a_usage_error(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_FOLDER)

    result = invoke("cp", SOURCE_FOLDER["rid"], TARGET, "--format", "json")

    assert result.exit_code == 2
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert "--recursive" in error["message"]


def test_cp_dry_run_lists_the_sources(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(json=fs.page([SOURCE_DATASET]))

    result = invoke("cp", SOURCE_FOLDER["rid"], TARGET, "-r", "--dry-run", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [fj.sdk_json(SOURCE_FOLDER), fj.sdk_json(SOURCE_DATASET)]
    }
    assert [request.method for request in stub_foundry_http.requests] == ["GET", "GET"]


def test_cp_dry_run_table_says_what_it_would_do(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_DATASET)

    result = invoke("cp", fs.DATASET_RID, TARGET, "--dry-run")

    assert result.exit_code == 0, result.output
    assert "[DRY-RUN] Would copy dataset 'Source Dataset'" in result.stderr
    assert "Would copy 0 folder(s) and 1 dataset(s)" in result.stderr
    assert fs.DATASET_RID in result.stdout


def test_cp_source_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error("ResourceNotFound", parameters={"resourceRid": fs.DATASET_RID}),
    )

    result = invoke("cp", fs.DATASET_RID, TARGET, "--format", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    assert json_lines(result.stderr)[-1]["errorName"] == "ResourceNotFound"


def test_cp_partial_failure_prints_what_was_created_and_fails(stub_foundry_http):
    one = fs.child_resource("ri.compass.main.folder.one", "One", "COMPASS_FOLDER")
    stub_foundry_http.respond(json=SOURCE_FOLDER)
    stub_foundry_http.respond(json=NEW_FOLDER)
    stub_foundry_http.respond(json=fs.page([one]))
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "CreateFolderPermissionDenied",
            "PERMISSION_DENIED",
            {"parentFolderRid": NEW_FOLDER["rid"]},
        ),
    )

    result = invoke("cp", SOURCE_FOLDER["rid"], TARGET, "-r", "--format", "json")

    assert result.exit_code == 4  # the first failure's exit code
    assert json.loads(result.stdout) == {"data": [fj.sdk_json(NEW_FOLDER)]}
    lines = json_lines(result.stderr)
    assert lines[0]["type"] == "warning"
    assert "Failed to copy 'One'" in lines[0]["message"]
    error = lines[-1]
    assert error["type"] == "permission_denied"
    assert error["errorName"] == "CreateFolderPermissionDenied"
    assert error["message"].startswith("1 item(s) could not be copied")


def test_cp_failed_dataset_copy_is_cleaned_up(stub_foundry_http, dataset_compat):
    stub_foundry_http.respond(json=SOURCE_DATASET)
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "UploadFilePermissionDenied",
            "PERMISSION_DENIED",
            {
                "datasetRid": NEW_DATASET_RID,
                "transactionRid": fs.TRANSACTION_RID,
                "path": "part-0.csv",
            },
        ),
    )

    result = invoke("cp", fs.DATASET_RID, TARGET, "--format", "json")

    assert result.exit_code == 4
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert error["errorName"] == "UploadFilePermissionDenied"
    assert error["message"].startswith("Failed to copy the files")
    assert DatasetService.delete_dataset.call_count == 1  # type: ignore[attr-defined]


def test_cp_debug_is_deprecated(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_DATASET)

    result = invoke("cp", fs.DATASET_RID, TARGET, "--dry-run", "--debug", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json_lines(result.stderr) == [
        {
            "type": "warning",
            "message": "--debug is deprecated; set PLTR_DEBUG=1 to see tracebacks.",
        }
    ]
    assert "--debug" not in invoke("cp", "--help").stdout


def test_cp_profile_short_flag(stub_foundry_http):
    stub_foundry_http.respond(json=SOURCE_DATASET)

    result = invoke("cp", fs.DATASET_RID, TARGET, "--dry-run", "-p", "dev")

    assert result.exit_code == 0, result.output
