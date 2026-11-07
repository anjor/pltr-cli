"""Tests for `pltr media-sets` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json
from typing import Iterator, List

import httpx
import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_mediasets as ms

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()

PNG = b"\x89PNG\r\n\x1a\n fake image bytes"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, ["media-sets", *args], **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


def only_request(stub):
    [request] = stub.requests
    return request


class ChunkedStream(httpx.SyncByteStream):
    """A response body sent in chunks; ``fail`` drops the connection after them."""

    def __init__(self, chunks: List[bytes], fail: bool = False):
        self.chunks = chunks
        self.fail = fail

    def __iter__(self) -> Iterator[bytes]:
        yield from self.chunks
        if self.fail:
            raise httpx.ReadError("connection reset by peer")


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


# -------------------------------------------------------------------- help


def test_beta_commands_are_labeled_in_help():
    lines = invoke("--help").stdout.splitlines()

    def line_for(command):
        # The command's row in the Commands panel, not an example line in
        # the group's description.
        return next(
            line for line in lines if line.strip("│ ").startswith(f"{command} ")
        )

    for command in (
        "get-by-path",
        "create",
        "commit",
        "abort",
        "upload",
        "reference",
        "thumbnail-calculate",
        "thumbnail-retrieve",
        "clear",
    ):
        assert "[beta]" in line_for(command), command
    for command in ("get", "download", "upload-temp"):
        assert "[beta]" not in line_for(command), command


def test_help_explains_the_rid_formats():
    help_text = invoke("get", "--help").stdout
    assert "ri.mio.main.media-set.<uuid>" in help_text
    assert "ri.mio.main.media-item.<uuid>" in help_text


# --------------------------------------------------------------------- get


def test_get_table_shows_real_fields_and_the_given_item_rid(stub_foundry_http):
    stub_foundry_http.respond(json=ms.item_info())

    result = invoke("get", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        ms.MEDIA_ITEM_RID,
        "images/photo.png",
        "image/png",
        "image/heic",
        ms.VIEW_RID,
        "1700000000000",
        fj.USER_ID,
        "2024-01-02T03:04:05",
    ):
        assert expected in result.stdout, expected
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("GET", ms.ITEM)
    assert dict(request.url.params) == {}  # GA


def test_get_csv(stub_foundry_http):
    stub_foundry_http.respond(json=ms.item_info())

    result = invoke("get", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, "-f", "csv")

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row == {
        "Media Item RID": ms.MEDIA_ITEM_RID,
        "Path": "images/photo.png",
        "MIME Type": "image/png",
        "Size (bytes)": "20",
        "Originally Uploaded MIME Type": "image/heic",
        "View RID": ms.VIEW_RID,
        "Logical Timestamp": "1700000000000",
        "Created By": fj.USER_ID,
        "Created": "2024-01-02T03:04:05+00:00",
    }


def test_get_json_is_the_sdk_serialization(stub_foundry_http):
    stub_foundry_http.respond(json=ms.item_info())

    result = invoke("get", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "viewRid": ms.VIEW_RID,
        "path": "images/photo.png",
        "logicalTimestamp": "1700000000000",  # SDK Long: a string in JSON
        "attribution": {
            "creatorId": fj.USER_ID,
            "creationTimestamp": "2024-01-02T03:04:05+00:00",
        },
        "mimeType": "image/png",
        "originallyUploadedFileMimeType": "image/heic",
        "sizeBytes": 20,
        "sizeBytesLong": "20",
    }
    assert result.stderr == ""


def test_get_without_optional_fields(stub_foundry_http):
    stub_foundry_http.respond(
        json={"viewRid": ms.VIEW_RID, "logicalTimestamp": 1, "sizeBytesLong": 3}
    )

    result = invoke("get", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, "-f", "csv")

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert (row["Path"], row["Created By"], row["Size (bytes)"]) == ("", "", "3")


def test_get_not_found(stub_foundry_http):
    stub_foundry_http.respond(404, json=fj.error("MediaItemNotFound"))

    result = invoke("get", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, "-f", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    assert json_lines(result.stderr)[-1]["errorName"] == "MediaItemNotFound"


# ------------------------------------------------------------- get-by-path


def test_get_by_path(stub_foundry_http):
    stub_foundry_http.respond(json=ms.rid_by_path())

    result = invoke(
        "get-by-path",
        ms.MEDIA_SET_RID,
        "images/photo.png",
        "--branch",
        "dev",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"mediaItemRid": ms.MEDIA_ITEM_RID}
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{ms.ITEMS}/getRidByPath"
    assert dict(request.url.params) == {
        "mediaItemPath": "images/photo.png",
        "branchName": "dev",
        "preview": "true",
    }


def test_get_by_path_table(stub_foundry_http):
    stub_foundry_http.respond(json=ms.rid_by_path())

    result = invoke("get-by-path", ms.MEDIA_SET_RID, "images/photo.png")

    assert result.exit_code == 0, result.output
    assert "images/photo.png" in result.stdout
    assert ms.MEDIA_ITEM_RID in result.stdout


def test_get_by_path_without_an_item_warns(stub_foundry_http):
    stub_foundry_http.respond(json=ms.rid_by_path(None))

    result = invoke("get-by-path", ms.MEDIA_SET_RID, "nothing/here", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {}
    assert json_lines(result.stderr) == [
        {"type": "warning", "message": "No media item at path 'nothing/here'."}
    ]


def test_get_by_path_preview_is_a_deprecated_no_op(stub_foundry_http):
    stub_foundry_http.respond(json=ms.rid_by_path())

    result = invoke("get-by-path", ms.MEDIA_SET_RID, "a", "--preview")

    assert result.exit_code == 0, result.output
    assert "--preview is deprecated" in result.stderr


def test_ga_commands_keep_preview_as_a_deprecated_no_op(stub_foundry_http, tmp_path):
    """0.16.0 had --preview on get/download/upload-temp; it stays hidden for one
    release and is never sent to these GA endpoints."""
    stub_foundry_http.respond(json=ms.item_info())
    result = invoke("get", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, "--preview")
    assert result.exit_code == 0, result.output
    assert "--preview is deprecated" in result.stderr
    assert "preview" not in dict(only_request(stub_foundry_http).url.params)

    for command in ("download", "upload-temp"):
        help_text = invoke(command, "--help").stdout
        assert "--preview" not in help_text, command


# ------------------------------------------------------------ transactions


def test_create_prints_the_transaction_id(stub_foundry_http):
    stub_foundry_http.respond(json=ms.TRANSACTION_ID)

    result = invoke("create", ms.MEDIA_SET_RID, "--branch", "dev", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == ms.TRANSACTION_ID
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "POST",
        f"/api/v2/mediasets/{ms.MEDIA_SET_RID}/transactions",
    )
    assert dict(request.url.params) == {"branchName": "dev", "preview": "true"}


def test_create_table(stub_foundry_http):
    stub_foundry_http.respond(json=ms.TRANSACTION_ID)

    result = invoke("create", ms.MEDIA_SET_RID)

    assert result.exit_code == 0, result.output
    assert ms.TRANSACTION_ID in result.stdout
    assert f"Created transaction {ms.TRANSACTION_ID}" in result.stderr
    assert "pltr media-sets upload" in result.stderr


def test_commit_does_not_ask(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("commit", ms.MEDIA_SET_RID, ms.TRANSACTION_ID)

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Committed transaction {ms.TRANSACTION_ID}" in result.stderr
    request = only_request(stub_foundry_http)
    assert request.url.path.endswith(f"/transactions/{ms.TRANSACTION_ID}/commit")
    assert request.url.params["preview"] == "true"


def test_commit_yes_is_a_deprecated_no_op(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("commit", ms.MEDIA_SET_RID, ms.TRANSACTION_ID, "-y", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    [warning] = json_lines(result.stderr)
    assert "--yes has no effect on 'media-sets commit'" in warning["message"]


def test_commit_invalid_transaction_id_is_a_usage_error(stub_foundry_http):
    result = invoke("commit", ms.MEDIA_SET_RID, "not-a-uuid", "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "usage_error"
    assert stub_foundry_http.requests == []


def test_abort_requires_yes_when_not_interactive(stub_foundry_http):
    result = invoke("abort", ms.MEDIA_SET_RID, ms.TRANSACTION_ID, "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub_foundry_http.requests == []


def test_abort_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("abort", ms.MEDIA_SET_RID, ms.TRANSACTION_ID, "--yes", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    request = only_request(stub_foundry_http)
    assert request.url.path.endswith(f"/transactions/{ms.TRANSACTION_ID}/abort")
    assert request.url.params["preview"] == "true"


def test_abort_prompts_when_interactive(stub_foundry_http, interactive):
    stub_foundry_http.respond(204)

    result = invoke("abort", ms.MEDIA_SET_RID, ms.TRANSACTION_ID, input="y\n")

    assert result.exit_code == 0, result.output
    assert "items uploaded in it will be deleted" in result.stderr
    assert len(stub_foundry_http.requests) == 1


def test_abort_answering_no(stub_foundry_http, interactive):
    result = invoke("abort", ms.MEDIA_SET_RID, ms.TRANSACTION_ID, input="n\n")

    assert result.exit_code == 1
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------------ upload


def test_upload_in_a_transaction(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=ms.put_item())
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-1.7 fake")

    result = invoke(
        "upload",
        ms.MEDIA_SET_RID,
        str(source),
        "docs/scan.pdf",
        ms.TRANSACTION_ID,
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == ms.put_item()
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("POST", ms.ITEMS)
    assert dict(request.url.params) == {
        "mediaItemPath": "docs/scan.pdf",
        "transactionId": ms.TRANSACTION_ID,
        "preview": "true",
    }
    assert request.content == b"%PDF-1.7 fake"


def test_upload_table_and_commit_hint(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=ms.put_item())
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"x")

    result = invoke(
        "upload", ms.MEDIA_SET_RID, str(source), "docs/scan.pdf", ms.TRANSACTION_ID
    )

    assert result.exit_code == 0, result.output
    for expected in (ms.MEDIA_ITEM_RID, ms.VIEW_RID, "docs/scan.pdf"):
        assert expected in result.stdout
    assert (
        f"pltr media-sets commit {ms.MEDIA_SET_RID} {ms.TRANSACTION_ID}"
        in result.stderr
    )


def test_upload_without_transaction(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=ms.put_item())
    source = tmp_path / "a.txt"
    source.write_bytes(b"hello")

    result = invoke("upload", ms.MEDIA_SET_RID, str(source), "a.txt", "--branch", "dev")

    assert result.exit_code == 0, result.output
    assert dict(only_request(stub_foundry_http).url.params) == {
        "branchName": "dev",
        "mediaItemPath": "a.txt",
        "preview": "true",
    }
    assert "commit" not in result.stderr


def test_upload_missing_file(stub_foundry_http, tmp_path):
    result = invoke("upload", ms.MEDIA_SET_RID, str(tmp_path / "nope.pdf"), "a.pdf")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


# ---------------------------------------------------------------- download


def test_download_to_a_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(content=PNG)
    target = tmp_path / "nested" / "photo.png"

    result = invoke("download", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, str(target))

    assert result.exit_code == 0, result.output
    assert target.read_bytes() == PNG
    assert result.stdout == ""
    assert f"Wrote {len(PNG)} bytes to {target}" in result.stderr
    assert list(target.parent.iterdir()) == [target]
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("GET", f"{ms.ITEM}/content")
    assert dict(request.url.params) == {}  # GA


def test_download_original_json_mode_keeps_stdout_empty(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(content=PNG)
    target = tmp_path / "photo.heic"

    result = invoke(
        "download",
        ms.MEDIA_SET_RID,
        ms.MEDIA_ITEM_RID,
        str(target),
        "--original",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert (result.stdout, result.stderr) == ("", "")
    assert target.read_bytes() == PNG
    assert only_request(stub_foundry_http).url.path == f"{ms.ITEM}/original"


def test_download_to_stdout(stub_foundry_http):
    stub_foundry_http.respond(content=PNG)

    result = invoke("download", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, "-")

    assert result.exit_code == 0, result.output
    assert result.stdout_bytes == PNG  # the content and nothing else
    assert "Wrote" not in result.stderr


def test_download_streams_large_content_in_chunks(stub_foundry_http, tmp_path):
    content = bytes(range(256)) * 4096  # 1 MiB
    stub_foundry_http.respond(
        stream=ChunkedStream([content[:300_000], content[300_000:]])
    )
    target = tmp_path / "out" / "video.bin"

    result = invoke("download", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, str(target))

    assert result.exit_code == 0, result.output
    assert target.read_bytes() == content


def test_download_interrupted_mid_stream_leaves_no_partial_file(
    stub_foundry_http, tmp_path
):
    stub_foundry_http.respond(stream=ChunkedStream([b"partial"], fail=True))
    out = tmp_path / "out"
    target = out / "photo.png"

    result = invoke(
        "download", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, str(target), "-f", "json"
    )

    assert result.exit_code == 7
    assert result.stdout == ""
    assert json_lines(result.stderr)[-1]["type"] == "network_error"
    assert list(out.iterdir()) == []


def test_download_keeps_an_existing_file_without_overwrite(stub_foundry_http, tmp_path):
    target = tmp_path / "photo.png"
    target.write_bytes(b"old")

    result = invoke("download", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, str(target))

    assert result.exit_code == 2
    assert "pass --overwrite" in result.stderr
    assert target.read_bytes() == b"old"
    assert stub_foundry_http.requests == []


def test_download_overwrite(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(content=PNG)
    target = tmp_path / "photo.png"
    target.write_bytes(b"old")

    result = invoke(
        "download", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, str(target), "--overwrite"
    )

    assert result.exit_code == 0, result.output
    assert target.read_bytes() == PNG


def test_download_overwrite_interrupted_mid_stream_keeps_the_old_file(
    stub_foundry_http, tmp_path
):
    stub_foundry_http.respond(stream=ChunkedStream([b"partial"], fail=True))
    out = tmp_path / "out"
    out.mkdir()
    target = out / "photo.png"
    target.write_bytes(b"old")

    result = invoke(
        "download", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, str(target), "--overwrite"
    )

    assert result.exit_code == 7
    assert target.read_bytes() == b"old"
    assert list(out.iterdir()) == [target]  # no temporary file left


def test_api_error_keeps_the_existing_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(
        403, json=fj.error("MediaSetPermissionDenied", "PERMISSION_DENIED")
    )
    out = tmp_path / "out"
    out.mkdir()
    target = out / "photo.png"
    target.write_bytes(b"old")

    result = invoke(
        "download",
        ms.MEDIA_SET_RID,
        ms.MEDIA_ITEM_RID,
        str(target),
        "--overwrite",
        "-f",
        "json",
    )

    assert result.exit_code == 4
    assert result.stdout == ""
    assert json_lines(result.stderr)[-1]["type"] == "permission_denied"
    assert target.read_bytes() == b"old"  # the API error comes before writing
    assert list(out.iterdir()) == [target]


def test_download_output_path_cannot_be_a_directory(stub_foundry_http, tmp_path):
    result = invoke("download", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, str(tmp_path))

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


# --------------------------------------------------------------- reference


def test_reference_table_reads_the_nested_media_set_view_item(stub_foundry_http):
    stub_foundry_http.respond(json=ms.media_reference(token="read-token"))

    result = invoke("reference", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, "-f", "csv")

    assert result.exit_code == 0, result.output
    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {
            "MIME Type": "image/png",
            "Media Set RID": ms.MEDIA_SET_RID,
            "Media Set View RID": ms.VIEW_RID,
            "Media Item RID": ms.MEDIA_ITEM_RID,
            "Token": "read-token",
        }
    ]
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{ms.ITEM}/reference"
    assert request.url.params["preview"] == "true"


def test_reference_json(stub_foundry_http):
    stub_foundry_http.respond(json=ms.media_reference())

    result = invoke("reference", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, "-f", "json")

    assert json.loads(result.stdout) == ms.media_reference()


# -------------------------------------------------------------- thumbnails


def test_thumbnail_calculate(stub_foundry_http):
    stub_foundry_http.respond(json=ms.thumbnail_status("pending"))

    result = invoke(
        "thumbnail-calculate", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, "-f", "csv"
    )

    assert result.exit_code == 0, result.output
    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {"Media Item RID": ms.MEDIA_ITEM_RID, "Status": "pending"}
    ]
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{ms.ITEM}/transform/imagery/thumbnail/calculate"
    assert request.url.params["preview"] == "true"


def test_thumbnail_calculate_successful_points_to_retrieve(stub_foundry_http):
    stub_foundry_http.respond(json=ms.thumbnail_status("successful"))

    result = invoke("thumbnail-calculate", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID)

    assert "successful" in result.stdout
    assert "pltr media-sets thumbnail-retrieve" in result.stderr


def test_thumbnail_calculate_json(stub_foundry_http):
    stub_foundry_http.respond(json=ms.thumbnail_status("failed"))

    result = invoke(
        "thumbnail-calculate", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, "-f", "json"
    )

    assert json.loads(result.stdout) == {"type": "failed"}


def test_thumbnail_retrieve(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(content=b"RIFF....WEBP")
    target = tmp_path / "thumb.webp"

    result = invoke(
        "thumbnail-retrieve", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, str(target)
    )

    assert result.exit_code == 0, result.output
    assert target.read_bytes() == b"RIFF....WEBP"
    assert result.stdout == ""
    request = only_request(stub_foundry_http)
    assert request.url.path == f"{ms.ITEM}/transform/imagery/thumbnail/retrieve"
    assert request.url.params["preview"] == "true"


def test_thumbnail_retrieve_to_stdout(stub_foundry_http):
    stub_foundry_http.respond(content=b"RIFF....WEBP")

    result = invoke("thumbnail-retrieve", ms.MEDIA_SET_RID, ms.MEDIA_ITEM_RID, "-")

    assert result.stdout_bytes == b"RIFF....WEBP"


def test_empty_thumbnail_is_an_error_and_writes_no_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(content=b"")
    out = tmp_path / "out"
    target = out / "thumb.webp"

    result = invoke(
        "thumbnail-retrieve",
        ms.MEDIA_SET_RID,
        ms.MEDIA_ITEM_RID,
        str(target),
        "-f",
        "json",
    )

    assert result.exit_code == 7
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["message"]) == (
        "api_error",
        "The thumbnail is empty; it may not be calculated yet.",
    )
    assert list(out.iterdir()) == []


# ------------------------------------------------------------- upload-temp


def test_upload_temp(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=ms.media_reference())
    source = tmp_path / "photo.png"
    source.write_bytes(b"png-bytes")

    result = invoke("upload-temp", str(source), "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == ms.media_reference()
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == (
        "PUT",
        "/api/v2/mediasets/media/upload",
    )
    assert dict(request.url.params) == {"filename": "photo.png"}  # GA: no preview
    assert request.content == b"png-bytes"


def test_upload_temp_filename_and_attribution(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=ms.media_reference())
    source = tmp_path / "photo.png"
    source.write_bytes(b"png-bytes")

    result = invoke(
        "upload-temp",
        str(source),
        "--filename",
        "renamed.png",
        "--attribution",
        "team-x",
    )

    assert result.exit_code == 0, result.output
    request = only_request(stub_foundry_http)
    assert request.url.params["filename"] == "renamed.png"
    assert request.headers["attribution"] == "team-x"
    assert ms.MEDIA_ITEM_RID in result.stdout
    assert "deleted after an hour" in result.stderr


# ------------------------------------------------------------------- clear


def test_clear_requires_yes_when_not_interactive(stub_foundry_http):
    result = invoke("clear", ms.MEDIA_SET_RID, "images/photo.png")

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub_foundry_http.requests == []


def test_clear_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "clear",
        ms.MEDIA_SET_RID,
        "images/photo.png",
        "--transaction-id",
        ms.TRANSACTION_ID,
        "--yes",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    request = only_request(stub_foundry_http)
    assert (request.method, request.url.path) == ("DELETE", f"{ms.ITEMS}/clearAtPath")
    assert dict(request.url.params) == {
        "mediaItemPath": "images/photo.png",
        "preview": "true",
        "transactionId": ms.TRANSACTION_ID,
    }


def test_clear_prompts_when_interactive(stub_foundry_http, interactive):
    stub_foundry_http.respond(204)

    result = invoke(
        "clear", ms.MEDIA_SET_RID, "images/photo.png", "--branch", "dev", input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert "Clear the media item at 'images/photo.png'" in result.stderr
    assert "Cleared the media item" in result.stderr
    assert only_request(stub_foundry_http).url.params["branchName"] == "dev"
