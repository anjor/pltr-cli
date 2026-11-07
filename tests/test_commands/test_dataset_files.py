"""Tests for `pltr dataset files` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json
from pathlib import PurePosixPath, PureWindowsPath
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from pltr.commands.dataset import _download_targets
from pltr.contract import PltrError
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


def upload_path(request) -> str:
    """The dataset file path of an upload request (decoded)."""
    prefix = f"{API}/{DATASET}/files/"
    assert request.url.path.startswith(prefix) and request.url.path.endswith("/upload")
    return request.url.path[len(prefix) : -len("/upload")]


# ------------------------------------------------------------------- list


def test_list_files_json(stub):
    files = [dj.file("data/a.csv"), dj.file("data/b.csv", size_bytes="2048")]
    stub.respond(json=dj.page(files, "t2"))

    result = invoke("dataset", "files", "list", DATASET, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dj.sdk_json(dj.page(files, "t2"))
    [request] = stub.requests
    assert request.url.path == f"{API}/{DATASET}/files"
    assert dict(request.url.params) == {}  # default branch, API page size


def test_list_files_csv_columns(stub):
    stub.respond(json=dj.page([dj.file()]))

    result = invoke("dataset", "files", "list", DATASET, "-f", "csv")

    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {
            "Path": "data/sales.csv",
            "Size (bytes)": "1024",
            "Updated": "2024-03-04T05:06:07+00:00",
            "Transaction RID": TRANSACTION,
        }
    ]


def test_list_files_filters_and_paging(stub):
    stub.respond(json=dj.page([dj.file("data/a.csv")], "t2"))
    stub.respond(json=dj.page([dj.file("data/b.csv")]))

    result = invoke(
        "dataset",
        "files",
        "list",
        DATASET,
        "--branch",
        "dev",
        "--path-prefix",
        "data/",
        "--start-transaction-rid",
        TRANSACTION,
        "--end-transaction-rid",
        TRANSACTION,
        "--page-size",
        "1",
        "--all",
    )

    assert result.exit_code == 0, result.output
    assert "data/a.csv" in result.stdout and "data/b.csv" in result.stdout
    first, second = stub.requests
    assert dict(first.url.params) == {
        "branchName": "dev",
        "pathPrefix": "data/",
        "startTransactionRid": TRANSACTION,
        "endTransactionRid": TRANSACTION,
        "pageSize": "1",
    }
    assert second.url.params["pageToken"] == "t2"


# ----------------------------------------------------------------- upload


@pytest.fixture
def local_csv(tmp_path):
    path = tmp_path / "sales.csv"
    path.write_bytes(b"id,region\n1,EMEA\n")
    return path


def test_upload_a_file_to_the_default_branch(stub, local_csv):
    stub.respond(json=dj.file("sales.csv"))

    result = invoke("dataset", "files", "upload", str(local_csv), DATASET, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dj.sdk_json(dj.file("sales.csv"))
    [request] = stub.requests
    assert upload_path(request) == "sales.csv"
    assert dict(request.url.params) == {}
    assert request.content == b"id,region\n1,EMEA\n"


@pytest.mark.parametrize(
    "path_option, expected",
    [("data/2024/sales.csv", "data/2024/sales.csv"), ("/data/", "data/sales.csv")],
)
def test_upload_a_file_to_a_dataset_path(stub, local_csv, path_option, expected):
    stub.respond(json=dj.file(expected))

    result = invoke(
        "dataset", "files", "upload", str(local_csv), DATASET, "--path", path_option
    )

    assert result.exit_code == 0, result.output
    assert f"as {expected}" in result.stderr
    assert upload_path(stub.requests[0]) == expected


def test_upload_a_file_on_a_branch_as_a_snapshot(stub, local_csv):
    stub.respond(json=dj.file("sales.csv"))

    result = invoke(
        "dataset",
        "files",
        "upload",
        str(local_csv),
        DATASET,
        "--branch",
        "dev",
        "--transaction-type",
        "snapshot",
    )

    assert result.exit_code == 0, result.output
    assert dict(stub.requests[0].url.params) == {
        "branchName": "dev",
        "transactionType": "SNAPSHOT",
    }


def test_upload_a_file_into_an_open_transaction(stub, local_csv):
    """Only transactionRid is sent: the API rejects it together with branchName."""
    stub.respond(json=dj.file("sales.csv"))

    result = invoke(
        "dataset",
        "files",
        "upload",
        str(local_csv),
        DATASET,
        "--transaction-rid",
        TRANSACTION,
    )

    assert result.exit_code == 0, result.output
    assert dict(stub.requests[0].url.params) == {"transactionRid": TRANSACTION}
    assert "The transaction is still open" in result.stderr


@pytest.mark.parametrize(
    "options, message",
    [
        (["--branch", "dev", "--transaction-rid", TRANSACTION], "not both"),
        (
            ["--transaction-rid", TRANSACTION, "--transaction-type", "APPEND"],
            "--transaction-type",
        ),
    ],
)
def test_upload_rejects_conflicting_options(stub, local_csv, options, message):
    result = invoke(
        "dataset", "files", "upload", str(local_csv), DATASET, *options, "-f", "json"
    )

    assert result.exit_code == 2
    assert message in json_lines(result.stderr)[-1]["message"]
    assert stub.requests == []


def test_upload_of_a_missing_local_file(stub, tmp_path):
    result = invoke("dataset", "files", "upload", str(tmp_path / "nope.csv"), DATASET)

    assert result.exit_code == 2
    assert "does not exist" in result.stderr
    assert stub.requests == []


def test_upload_error_is_structured(stub, local_csv):
    stub.respond(
        409,
        json=fj.error(
            "OpenTransactionAlreadyExists",
            "CONFLICT",
            parameters={"datasetRid": DATASET, "branchName": "master"},
        ),
    )

    result = invoke("dataset", "files", "upload", str(local_csv), DATASET, "-f", "json")

    assert result.exit_code == 7
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == (
        "conflict",
        "OpenTransactionAlreadyExists",
    )


@pytest.fixture
def local_dir(tmp_path):
    root = tmp_path / "exports"
    (root / "2024").mkdir(parents=True)
    (root / "a.csv").write_bytes(b"a")
    (root / "2024" / "b.csv").write_bytes(b"bb")
    return root


def test_upload_a_directory_in_one_committed_transaction(stub, local_dir):
    stub.respond(json=dj.transaction(transaction_type="UPDATE"))
    stub.respond(json=dj.file("exports/2024/b.csv"))
    stub.respond(json=dj.file("exports/a.csv"))
    stub.respond(json=dj.transaction(status="COMMITTED", closed_time=dj.CLOSED_TIME))

    result = invoke(
        "dataset",
        "files",
        "upload",
        str(local_dir),
        DATASET,
        "--path",
        "exports",
        "--branch",
        "dev",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dj.sdk_json(
        dj.page([dj.file("exports/2024/b.csv"), dj.file("exports/a.csv")])
    )
    start, first, second, commit = stub.requests
    assert (start.method, start.url.path) == ("POST", f"{API}/{DATASET}/transactions")
    assert dict(start.url.params) == {"branchName": "dev"}
    assert json.loads(start.content) == {"transactionType": "UPDATE"}
    assert [upload_path(first), upload_path(second)] == [
        "exports/2024/b.csv",
        "exports/a.csv",
    ]
    for upload in (first, second):
        assert dict(upload.url.params) == {"transactionRid": TRANSACTION}
    assert (first.content, second.content) == (b"bb", b"a")
    assert commit.url.path == f"{API}/{DATASET}/transactions/{TRANSACTION}/commit"


def test_upload_a_directory_with_a_transaction_type(stub, local_dir):
    stub.respond(json=dj.transaction(transaction_type="SNAPSHOT"))
    stub.respond(json=dj.file("2024/b.csv"))
    stub.respond(json=dj.file("a.csv"))
    stub.respond(json=dj.transaction(status="COMMITTED", closed_time=dj.CLOSED_TIME))

    result = invoke(
        "dataset",
        "files",
        "upload",
        str(local_dir),
        DATASET,
        "--transaction-type",
        "SNAPSHOT",
    )

    assert result.exit_code == 0, result.output
    assert "Uploaded 2 files and committed transaction" in result.stderr
    assert json.loads(stub.requests[0].content) == {"transactionType": "SNAPSHOT"}
    assert [upload_path(r) for r in stub.requests[1:3]] == ["2024/b.csv", "a.csv"]


def test_failed_directory_upload_aborts_the_transaction(stub, local_dir):
    stub.respond(json=dj.transaction(transaction_type="UPDATE"))
    stub.respond(json=dj.file("2024/b.csv"))
    stub.respond(500, json=fj.error("UploadFailed", "INTERNAL"))
    stub.respond(json=dj.transaction(status="ABORTED", closed_time=dj.CLOSED_TIME))

    result = invoke("dataset", "files", "upload", str(local_dir), DATASET, "-f", "json")

    assert result.exit_code == 7
    *warnings, error = json_lines(result.stderr)
    assert error["errorName"] == "UploadFailed"
    assert warnings == [
        {
            "type": "warning",
            "message": f"Aborted transaction {TRANSACTION}; the dataset is unchanged.",
        }
    ]
    abort = stub.requests[-1]
    assert abort.url.path == f"{API}/{DATASET}/transactions/{TRANSACTION}/abort"
    assert result.stdout == ""


def test_failed_abort_tells_the_user_how_to_abort(stub, local_dir):
    stub.respond(json=dj.transaction(transaction_type="UPDATE"))
    stub.respond(500, json=fj.error("UploadFailed", "INTERNAL"))
    stub.respond(500, json=fj.error("AbortFailed", "INTERNAL"))

    result = invoke("dataset", "files", "upload", str(local_dir), DATASET)

    assert result.exit_code == 7
    assert f"Couldn't abort transaction {TRANSACTION}" in result.stderr
    assert f"pltr dataset transactions abort {DATASET} {TRANSACTION}" in result.stderr
    assert "UploadFailed" in result.stderr


def test_upload_a_directory_into_an_open_transaction(stub, local_dir):
    stub.respond(json=dj.file("2024/b.csv"))
    stub.respond(json=dj.file("a.csv"))

    result = invoke(
        "dataset",
        "files",
        "upload",
        str(local_dir),
        DATASET,
        "--transaction-rid",
        TRANSACTION,
    )

    assert result.exit_code == 0, result.output
    assert len(stub.requests) == 2  # no create, no commit
    assert all(
        dict(r.url.params) == {"transactionRid": TRANSACTION} for r in stub.requests
    )
    assert "The transaction is still open" in result.stderr


def test_upload_an_empty_directory(stub, tmp_path):
    (tmp_path / "empty").mkdir()

    result = invoke("dataset", "files", "upload", str(tmp_path / "empty"), DATASET)

    assert result.exit_code == 2
    assert "contains no files" in result.stderr
    assert stub.requests == []


# ------------------------------------------------------------------- get


def test_get_file_writes_it_and_prints_its_metadata(stub, tmp_path):
    stub.respond(json=dj.file())
    stub.respond(content=b"id,region\n1,EMEA\n")
    target = tmp_path / "out.csv"

    result = invoke(
        "dataset", "files", "get", DATASET, "data/sales.csv", str(target), "-f", "json"
    )

    assert result.exit_code == 0, result.output
    assert target.read_bytes() == b"id,region\n1,EMEA\n"
    assert json.loads(result.stdout) == dj.sdk_json(dj.file())
    get, content = stub.requests
    assert get.url.path == f"{API}/{DATASET}/files/data/sales.csv"
    assert content.url.path == f"{API}/{DATASET}/files/data/sales.csv/content"


def test_get_file_into_a_directory_keeps_its_name(stub, tmp_path):
    stub.respond(json=dj.file())
    stub.respond(content=b"x")

    result = invoke(
        "dataset",
        "files",
        "get",
        DATASET,
        "data/sales.csv",
        str(tmp_path),
        "--branch",
        "dev",
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "sales.csv").read_bytes() == b"x"
    assert "(1 bytes)" in result.stderr
    assert all(dict(r.url.params) == {"branchName": "dev"} for r in stub.requests)


def test_get_file_to_stdout(stub):
    stub.respond(content=b"id,region\n1,EMEA\n")

    result = invoke("dataset", "files", "get", DATASET, "data/sales.csv", "-")

    assert result.exit_code == 0, result.output
    assert result.stdout_bytes == b"id,region\n1,EMEA\n"
    [content] = stub.requests  # no metadata request
    assert content.url.path.endswith("/content")


def test_get_missing_file_writes_nothing(stub, tmp_path):
    stub.respond(
        404,
        json=fj.error(
            "FileNotFoundOnBranch",
            parameters={"datasetRid": DATASET, "branchName": "master", "path": "x"},
        ),
    )

    downloads = tmp_path / "downloads"
    downloads.mkdir()

    result = invoke("dataset", "files", "get", DATASET, "x", str(downloads / "x"))

    assert result.exit_code == 5
    assert list(downloads.iterdir()) == []


def test_get_folder_recursively(stub, tmp_path):
    files = [dj.file("data/a.csv"), dj.file("data/2024/b.csv")]
    stub.respond(json=dj.page(files[:1], "t2"))
    stub.respond(json=dj.page(files[1:]))
    stub.respond(content=b"a")
    stub.respond(content=b"bb")
    out = tmp_path / "out"

    result = invoke(
        "dataset",
        "files",
        "get",
        DATASET,
        "data",
        str(out),
        "--recursive",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert (out / "a.csv").read_bytes() == b"a"
    assert (out / "2024" / "b.csv").read_bytes() == b"bb"
    assert json.loads(result.stdout) == dj.sdk_json(dj.page(files))
    first_page, second_page, a, b = stub.requests
    assert dict(first_page.url.params) == {"pathPrefix": "data/"}
    assert second_page.url.params["pageToken"] == "t2"
    assert a.url.path == f"{API}/{DATASET}/files/data/a.csv/content"
    assert b.url.path == f"{API}/{DATASET}/files/data/2024/b.csv/content"


def test_get_whole_dataset_recursively(stub, tmp_path):
    stub.respond(json=dj.page([dj.file("top.csv")]))
    stub.respond(content=b"t")

    result = invoke("dataset", "files", "get", DATASET, "/", str(tmp_path), "-r")

    assert result.exit_code == 0, result.output
    assert dict(stub.requests[0].url.params) == {}  # no pathPrefix
    assert (tmp_path / "top.csv").read_bytes() == b"t"


def test_recursive_get_refuses_paths_outside_the_target(stub, tmp_path):
    stub.respond(json=dj.page([dj.file("data/../../escape.csv")]))
    out = tmp_path / "out"

    result = invoke("dataset", "files", "get", DATASET, "data", str(out), "-r")

    assert result.exit_code == 1
    assert "Refusing to download" in result.stderr
    assert len(stub.requests) == 1  # nothing downloaded
    assert not (tmp_path / "escape.csv").exists()


WINDOWS_OUT = PureWindowsPath(r"C:\work\out")
POSIX_OUT = PurePosixPath("/work/out")


def remote_files(*paths: str) -> list:
    return [SimpleNamespace(path=path) for path in paths]


@pytest.mark.parametrize(
    "remote",
    [
        r"data\..\..\..\Users\me\evil.bat",  # "\" separates paths on Windows
        "data/C:/Windows/evil.dll",  # a drive
        "C:evil.dll",  # drive-relative
        "data/evil.csv:stream",  # an alternate data stream
        "data/.. /evil.csv",  # Windows drops the trailing space: ".."
        "data/.../evil.csv",  # Windows drops trailing dots
        "../evil.csv",
        "/etc/evil.csv",
    ],
)
def test_recursive_get_refuses_unsafe_names_on_windows(remote):
    """Simulates Windows: only "/" separated parts were checked (#181 review)."""
    with pytest.raises(PltrError, match="can't be written safely"):
        _download_targets(remote_files(remote), None, WINDOWS_OUT)


def test_recursive_get_keeps_safe_names_on_windows():
    files = remote_files("data/ok.csv", "data/report..v2.csv", "data/2024/b.csv")

    targets = _download_targets(files, "data/", WINDOWS_OUT)

    assert [str(target) for _, target in targets] == [
        r"C:\work\out\ok.csv",
        r"C:\work\out\report..v2.csv",
        r"C:\work\out\2024\b.csv",
    ]


def test_backslashes_and_colons_are_ordinary_characters_elsewhere():
    files = remote_files(r"data\a.csv", "data/10:00.csv", "data/report..v2.csv")

    targets = _download_targets(files, None, POSIX_OUT)

    assert [str(target) for _, target in targets] == [
        r"/work/out/data\a.csv",
        "/work/out/data/10:00.csv",
        "/work/out/data/report..v2.csv",
    ]
    with pytest.raises(PltrError):
        _download_targets(remote_files("data/../../evil.csv"), None, POSIX_OUT)


def test_recursive_get_refuses_a_symlink_out_of_the_target(stub, tmp_path):
    """A target that resolves outside OUTPUT_PATH is refused before anything
    is written, whatever made it point there."""
    out = tmp_path / "out"
    out.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (out / "link").symlink_to(elsewhere, target_is_directory=True)
    stub.respond(json=dj.page([dj.file("data/ok.csv"), dj.file("data/link/x.csv")]))

    result = invoke("dataset", "files", "get", DATASET, "data", str(out), "-r")

    assert result.exit_code == 1
    assert "Refusing to download 'data/link/x.csv'" in result.stderr
    assert "Hint: Download that file on its own" in result.stderr
    assert len(stub.requests) == 1  # the listing; nothing downloaded
    assert list(elsewhere.iterdir()) == []
    assert not (out / "ok.csv").exists()


def test_recursive_get_to_stdout_is_rejected(stub):
    result = invoke("dataset", "files", "get", DATASET, "data", "-", "-r")

    assert result.exit_code == 2
    assert stub.requests == []


# ---------------------------------------------------------------- delete


def test_delete_file_with_yes(stub):
    stub.respond(204)

    result = invoke(
        "dataset", "files", "delete", DATASET, "data/sales.csv", "--yes", "-f", "json"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    [request] = stub.requests
    assert (request.method, request.url.path) == (
        "DELETE",
        f"{API}/{DATASET}/files/data/sales.csv",
    )
    assert dict(request.url.params) == {}


def test_delete_file_in_a_transaction(stub):
    stub.respond(204)

    result = invoke(
        "dataset",
        "files",
        "delete",
        DATASET,
        "a.csv",
        "--transaction-rid",
        TRANSACTION,
        "-y",
    )

    assert result.exit_code == 0, result.output
    assert dict(stub.requests[0].url.params) == {"transactionRid": TRANSACTION}


def test_delete_file_rejects_branch_and_transaction(stub):
    result = invoke(
        "dataset",
        "files",
        "delete",
        DATASET,
        "a.csv",
        "--branch",
        "dev",
        "--transaction-rid",
        TRANSACTION,
        "-y",
    )

    assert result.exit_code == 2
    assert stub.requests == []


def test_delete_file_requires_yes_when_not_interactive(stub):
    result = invoke("dataset", "files", "delete", DATASET, "a.csv")

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub.requests == []


def test_delete_file_answering_no_aborts(stub, interactive):
    result = invoke("dataset", "files", "delete", DATASET, "a.csv", input="n\n")

    assert result.exit_code == 1
    assert "Aborted" in result.stderr
    assert stub.requests == []


# ------------------------------------------------------------------ info


def test_file_info(stub):
    stub.respond(json=dj.file())

    result = invoke(
        "dataset",
        "files",
        "info",
        DATASET,
        "data/sales.csv",
        "--end-transaction-rid",
        TRANSACTION,
    )

    assert result.exit_code == 0, result.output
    for expected in ("data/sales.csv", "1024", TRANSACTION):
        assert expected in result.stdout
    [request] = stub.requests
    assert request.url.path == f"{API}/{DATASET}/files/data/sales.csv"
    assert dict(request.url.params) == {"endTransactionRid": TRANSACTION}


def test_a_leading_slash_in_file_paths_is_dropped(stub, tmp_path):
    """Dataset file paths never start with / (the API rejects them)."""
    stub.respond(json=dj.file())
    stub.respond(json=dj.file())
    stub.respond(content=b"x")
    stub.respond(204)

    info = invoke("dataset", "files", "info", DATASET, "/data/sales.csv")
    get = invoke("dataset", "files", "get", DATASET, "/data/sales.csv", str(tmp_path))
    delete = invoke("dataset", "files", "delete", DATASET, "/data/sales.csv", "-y")

    assert (info.exit_code, get.exit_code, delete.exit_code) == (0, 0, 0)
    file_path = f"{API}/{DATASET}/files/data/sales.csv"
    assert [r.url.path for r in stub.requests] == [
        file_path,
        file_path,
        f"{file_path}/content",
        file_path,
    ]
    assert (tmp_path / "sales.csv").read_bytes() == b"x"
