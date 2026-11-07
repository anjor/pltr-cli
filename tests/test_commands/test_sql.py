"""Tests for `pltr sql` against a real FoundryClient (only HTTP is faked)."""

import csv
import datetime
import decimal
import io
import json

import pyarrow as pa
import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_sql as sj

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()

ROWS = [{"n": 1, "msg": "hi"}, {"n": 2, "msg": "there"}]


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


def endpoints(stub) -> list:
    return [
        (request.method, request.url.path.rsplit("/", 1)[-1])
        for request in stub.requests
    ]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


def queue_execute(stub, table=None):
    stub.respond(json=sj.running())
    stub.respond(json=sj.succeeded())
    stub.respond(**sj.results(table))


# -------------------------------------------------------------------- help


def test_sql_commands_are_ga_and_hide_the_deprecated_preview_flags():
    result = invoke("sql", "--help")
    assert "[beta]" not in result.stdout

    help_text = invoke("sql", "execute", "--help").stdout
    assert "--preview" not in help_text
    assert "--fallback-branches" in help_text


# ----------------------------------------------------------------- execute


def test_execute_table(stub_foundry_http):
    queue_execute(stub_foundry_http)

    result = invoke("sql", "execute", sj.QUERY)

    assert result.exit_code == 0, result.output
    for expected in ("n", "msg", "hi", "there"):
        assert expected in result.stdout
    assert f"Query ID: {sj.QUERY_ID}" in result.stderr
    assert sj.QUERY_ID not in result.stdout
    assert endpoints(stub_foundry_http) == [
        ("POST", "execute"),
        ("GET", "getStatus"),
        ("GET", "getResults"),
    ]
    assert all("preview" not in r.url.params for r in stub_foundry_http.requests)


def test_execute_json_is_a_data_document_of_row_objects(stub_foundry_http):
    queue_execute(stub_foundry_http)

    result = invoke("sql", "execute", sj.QUERY, "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": ROWS}
    assert result.stderr == ""


def test_execute_csv(stub_foundry_http):
    queue_execute(stub_foundry_http)

    result = invoke("sql", "execute", sj.QUERY, "-f", "csv")

    assert result.stdout.splitlines()[0] == "n,msg"
    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {"n": "1", "msg": "hi"},
        {"n": "2", "msg": "there"},
    ]


def test_execute_sends_fallback_branches(stub_foundry_http):
    queue_execute(stub_foundry_http)

    result = invoke(
        "sql", "execute", sj.QUERY, "--fallback-branches", "dev, master", "-f", "json"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(stub_foundry_http.requests[0].content) == {
        "query": sj.QUERY,
        "fallbackBranchIds": ["dev", "master"],
    }


def test_execute_rejects_empty_fallback_branches(stub_foundry_http):
    result = invoke("sql", "execute", sj.QUERY, "--fallback-branches", " , ")

    assert result.exit_code == 2
    assert "give at least one branch name" in result.stderr
    assert stub_foundry_http.requests == []


def test_execute_output_file(stub_foundry_http, tmp_path):
    queue_execute(stub_foundry_http)
    target = tmp_path / "rows.csv"

    result = invoke("sql", "execute", sj.QUERY, "-f", "csv", "-o", str(target))

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Wrote 2 row(s) to {target}" in result.stderr
    assert target.read_text().splitlines() == ["n,msg", "1,hi", "2,there"]


def test_execute_converts_arrow_types_to_json(stub_foundry_http):
    table = pa.table(
        {
            "id": pa.array([1, 2], pa.int64()),
            "price": pa.array([decimal.Decimal("1.50"), None], pa.decimal128(10, 2)),
            "at": pa.array(
                [
                    datetime.datetime(
                        2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc
                    ),
                    None,
                ],
                pa.timestamp("us", tz="UTC"),
            ),
            "day": pa.array([datetime.date(2024, 1, 2), None], pa.date32()),
            "raw": pa.array([b"\xff\x00", None], pa.binary()),
            "tags": pa.array([["x", "y"], []], pa.list_(pa.string())),
            "ratio": pa.array([float("nan"), 0.5], pa.float64()),
        }
    )
    queue_execute(stub_foundry_http, table)

    result = invoke("sql", "execute", sj.QUERY, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [
            {
                "id": 1,
                "price": "1.50",
                "at": "2024-01-02T03:04:05Z",
                "day": "2024-01-02",
                "raw": "/wA=",  # base64
                "tags": ["x", "y"],
                "ratio": None,  # NaN isn't JSON
            },
            {
                "id": 2,
                "price": None,
                "at": None,
                "day": None,
                "raw": None,
                "tags": [],
                "ratio": 0.5,
            },
        ]
    }


def test_execute_table_renders_binary_and_null_cells(stub_foundry_http):
    table = pa.table(
        {"raw": pa.array([b"\xff\x00", None], pa.binary()), "s": ["a", None]}
    )
    queue_execute(stub_foundry_http, table)

    result = invoke("sql", "execute", sj.QUERY, "-f", "csv")

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == ["raw,s", "/wA=,a", ","]


def test_execute_renames_duplicate_columns(stub_foundry_http):
    table = pa.Table.from_arrays(
        [pa.array([1]), pa.array([2]), pa.array([3])], names=["id", "id", "id"]
    )
    queue_execute(stub_foundry_http, table)

    result = invoke("sql", "execute", sj.QUERY, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": [{"id": 1, "id_2": 2, "id_3": 3}]}
    [warning] = json_lines(result.stderr)
    assert warning["type"] == "warning"
    assert "id -> id_2, id -> id_3" in warning["message"]


def test_execute_empty_result(stub_foundry_http):
    queue_execute(stub_foundry_http, pa.table({"n": pa.array([], pa.int64())}))
    result = invoke("sql", "execute", sj.QUERY)
    assert (result.exit_code, result.stdout) == (0, "")
    assert "No results." in result.stderr

    queue_execute(stub_foundry_http, pa.table({"n": pa.array([], pa.int64())}))
    result = invoke("sql", "execute", sj.QUERY, "-f", "csv")
    assert result.stdout == "n\n"

    queue_execute(stub_foundry_http, pa.table({"n": pa.array([], pa.int64())}))
    result = invoke("sql", "execute", sj.QUERY, "-f", "json")
    assert json.loads(result.stdout) == {"data": []}


def test_execute_failed_query(stub_foundry_http):
    stub_foundry_http.respond(json=sj.running())
    stub_foundry_http.respond(json=sj.failed("Column 'nope' does not exist"))

    result = invoke("sql", "execute", sj.QUERY, "-f", "json")

    assert result.exit_code == 7
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert error == {
        "type": "api_error",
        "message": f"Query {sj.QUERY_ID} failed: Column 'nope' does not exist",
        "exitCode": 7,
    }


def test_execute_parse_error_is_a_validation_error(stub_foundry_http):
    stub_foundry_http.respond(
        400,
        json=fj.error(
            "QueryParseError", "INVALID_ARGUMENT", parameters={"errorMessage": "bad"}
        ),
    )

    result = invoke("sql", "execute", "SELEC 1", "-f", "json")

    assert result.exit_code == 6
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == (
        "validation_error",
        "QueryParseError",
    )


def test_execute_timeout(stub_foundry_http, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    monkeypatch.setattr(
        "time.sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds)
    )
    stub_foundry_http.respond_always(json=sj.running())

    result = invoke("sql", "execute", sj.QUERY, "--timeout", "3")

    assert result.exit_code == 7
    assert f"Query {sj.QUERY_ID} is still running after 3 seconds" in result.stderr
    assert f"pltr sql wait {sj.QUERY_ID}" in result.stderr


@pytest.mark.parametrize("flag", ["--preview", "--no-preview"])
def test_execute_preview_flags_are_deprecated_no_ops(stub_foundry_http, flag):
    queue_execute(stub_foundry_http)

    result = invoke("sql", "execute", sj.QUERY, flag, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": ROWS}
    [warning] = json_lines(result.stderr)
    assert warning["type"] == "warning"
    assert "--preview/--no-preview is deprecated" in warning["message"]


# ------------------------------------------------------------------ submit


def test_submit_json(stub_foundry_http):
    stub_foundry_http.respond(json=sj.running())

    result = invoke("sql", "submit", sj.QUERY, "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == sj.running()
    assert result.stderr == ""
    assert endpoints(stub_foundry_http) == [("POST", "execute")]


def test_submit_table_prints_query_id_and_next_step(stub_foundry_http):
    stub_foundry_http.respond(json=sj.running())

    result = invoke("sql", "submit", sj.QUERY)

    assert result.exit_code == 0, result.output
    assert sj.QUERY_ID in result.stdout
    assert "running" in result.stdout
    assert f"pltr sql wait {sj.QUERY_ID}" in result.stderr


def test_submit_csv(stub_foundry_http):
    stub_foundry_http.respond(json=sj.succeeded())

    result = invoke("sql", "submit", sj.QUERY, "-f", "csv")

    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {"Query ID": sj.QUERY_ID, "Status": "succeeded"}
    ]


def test_submit_fails_when_the_query_fails_at_once(stub_foundry_http):
    stub_foundry_http.respond(json=sj.failed("Dataset not found"))

    result = invoke("sql", "submit", sj.QUERY, "-f", "json")

    assert result.exit_code == 7
    assert result.stdout == ""
    assert json_lines(result.stderr)[-1]["message"] == (
        "The query failed: Dataset not found"
    )


# ------------------------------------------------------------------ status


def test_status_json(stub_foundry_http):
    stub_foundry_http.respond(json=sj.running())

    result = invoke("sql", "status", sj.QUERY_ID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == sj.running()
    [request] = stub_foundry_http.requests
    assert request.url.raw_path.decode() == (
        f"/api/v2/sqlQueries/{sj.QUERY_ID_IN_PATH}/getStatus"
    )


def test_status_of_a_failed_query_shows_the_error_and_the_given_id(
    stub_foundry_http,
):
    stub_foundry_http.respond(json=sj.failed("Out of memory"))

    result = invoke("sql", "status", sj.QUERY_ID, "-f", "csv")

    assert result.exit_code == 0
    assert list(csv.DictReader(io.StringIO(result.stdout))) == [
        {"Query ID": sj.QUERY_ID, "Status": "failed", "Error": "Out of memory"}
    ]


def test_status_of_a_canceled_query_json_is_the_api_body(stub_foundry_http):
    stub_foundry_http.respond(json=sj.canceled())

    result = invoke("sql", "status", sj.QUERY_ID, "-f", "json")

    assert json.loads(result.stdout) == {"type": "canceled"}


# ----------------------------------------------------------------- results


def test_results_json(stub_foundry_http):
    stub_foundry_http.respond(**sj.results())

    result = invoke("sql", "results", sj.QUERY_ID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": ROWS}
    assert endpoints(stub_foundry_http) == [("GET", "getResults")]


def test_results_of_a_running_query(stub_foundry_http):
    stub_foundry_http.respond(400, json=fj.error("QueryRunning", "INVALID_ARGUMENT"))

    result = invoke("sql", "results", sj.QUERY_ID, "-f", "json")

    assert result.exit_code == 6
    assert result.stdout == ""
    assert json_lines(result.stderr)[-1]["errorName"] == "QueryRunning"


def test_results_of_a_failed_query(stub_foundry_http):
    stub_foundry_http.respond(
        500,
        json=fj.error("QueryFailed", "INTERNAL", parameters={"errorMessage": "boom"}),
    )

    result = invoke("sql", "results", sj.QUERY_ID)

    assert result.exit_code == 7
    assert "QueryFailed" in result.stderr
    assert "errorMessage=boom" in result.stderr


# ------------------------------------------------------------------ cancel


def test_cancel_requires_yes_when_not_interactive(stub_foundry_http):
    result = invoke("sql", "cancel", sj.QUERY_ID, "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub_foundry_http.requests == []


def test_cancel_with_yes_prints_the_new_status(stub_foundry_http):
    stub_foundry_http.respond(204)
    stub_foundry_http.respond(json=sj.canceled())

    result = invoke("sql", "cancel", sj.QUERY_ID, "--yes")

    assert result.exit_code == 0, result.output
    assert f"Canceled query {sj.QUERY_ID}" in result.stderr
    assert "canceled" in result.stdout
    assert endpoints(stub_foundry_http) == [("POST", "cancel"), ("GET", "getStatus")]


def test_cancel_of_a_finished_query(stub_foundry_http):
    stub_foundry_http.respond(204)
    stub_foundry_http.respond(json=sj.succeeded())

    result = invoke("sql", "cancel", sj.QUERY_ID, "-y", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == sj.succeeded()


def test_cancel_prompts_when_interactive(stub_foundry_http, interactive):
    stub_foundry_http.respond(204)
    stub_foundry_http.respond(json=sj.canceled())

    result = invoke("sql", "cancel", sj.QUERY_ID, input="y\n")

    assert result.exit_code == 0, result.output
    assert f"Cancel SQL query {sj.QUERY_ID}?" in result.stderr
    assert len(stub_foundry_http.requests) == 2


def test_cancel_answering_no_aborts(stub_foundry_http, interactive):
    result = invoke("sql", "cancel", sj.QUERY_ID, input="n\n")

    assert result.exit_code == 1
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------------ export


@pytest.mark.parametrize(
    "name, expected",
    [
        ("rows.csv", "n,msg\n1,hi\n2,there\n"),
        ("rows.json", json.dumps({"data": ROWS}, indent=2) + "\n"),
    ],
)
def test_export_format_follows_the_extension(
    stub_foundry_http, tmp_path, name, expected
):
    queue_execute(stub_foundry_http)
    target = tmp_path / name

    result = invoke("sql", "export", sj.QUERY, str(target))

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert target.read_text() == expected
    assert f"Query ID: {sj.QUERY_ID}" in result.stderr


def test_export_unknown_extension_writes_a_table(stub_foundry_http, tmp_path):
    queue_execute(stub_foundry_http)
    target = tmp_path / "rows.txt"

    result = invoke("sql", "export", sj.QUERY, str(target))

    assert result.exit_code == 0, result.output
    # Tables are written as UTF-8 (box drawing); Windows reads cp1252 by default.
    assert "there" in target.read_text(encoding="utf-8")
    assert f"Wrote table output to {target}" in result.stderr


def test_export_explicit_format_wins_over_the_extension(stub_foundry_http, tmp_path):
    queue_execute(stub_foundry_http)
    target = tmp_path / "rows.csv"

    result = invoke("sql", "export", sj.QUERY, str(target), "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(target.read_text()) == {"data": ROWS}
    assert result.stdout == ""


def test_export_extension_wins_over_pltr_format(
    stub_foundry_http, tmp_path, monkeypatch
):
    monkeypatch.setenv("PLTR_FORMAT", "json")
    queue_execute(stub_foundry_http)
    target = tmp_path / "rows.csv"

    result = invoke("sql", "export", sj.QUERY, str(target))

    assert result.exit_code == 0, result.output
    assert target.read_text().startswith("n,msg\n")
    assert result.stdout == ""
    assert result.stderr == ""  # JSON mode: informational messages suppressed


def test_export_error_leaves_stdout_empty(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(
        403, json=fj.error("ExecuteSqlQueryPermissionDenied", "PERMISSION_DENIED")
    )
    target = tmp_path / "rows.csv"

    result = invoke("sql", "export", sj.QUERY, str(target), "-f", "json")

    assert result.exit_code == 4
    assert result.stdout == ""
    assert not target.exists()


# -------------------------------------------------------------------- wait


def test_wait_polls_then_prints_rows(stub_foundry_http):
    stub_foundry_http.respond(json=sj.running())
    stub_foundry_http.respond(json=sj.succeeded())
    stub_foundry_http.respond(**sj.results())

    result = invoke("sql", "wait", sj.QUERY_ID, "--timeout", "30")

    assert result.exit_code == 0, result.output
    assert "there" in result.stdout
    assert f"Query {sj.QUERY_ID} succeeded" in result.stderr
    assert endpoints(stub_foundry_http) == [
        ("GET", "getStatus"),
        ("GET", "getStatus"),
        ("GET", "getResults"),
    ]


def test_wait_csv_output_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=sj.succeeded())
    stub_foundry_http.respond(**sj.results())
    target = tmp_path / "rows.csv"

    result = invoke("sql", "wait", sj.QUERY_ID, "-f", "csv", "-o", str(target))

    assert result.exit_code == 0, result.output
    assert target.read_text() == "n,msg\n1,hi\n2,there\n"


def test_wait_for_a_canceled_query_fails(stub_foundry_http):
    stub_foundry_http.respond(json=sj.canceled())

    result = invoke("sql", "wait", sj.QUERY_ID, "-f", "json")

    assert result.exit_code == 7
    assert json_lines(result.stderr)[-1]["message"] == (
        f"Query {sj.QUERY_ID} was canceled."
    )
    assert len(stub_foundry_http.requests) == 1
