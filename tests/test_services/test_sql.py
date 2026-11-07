"""Tests for SqlService against a real FoundryClient (only HTTP is faked).

Every SqlQuery endpoint pltr uses is GA: passing preview= would make the SDK
emit a UserWarning, which the module-level filter turns into a failure.
"""

import io
import json

import pyarrow as pa
import pyarrow.ipc as ipc
import pytest
from foundry_sdk.v2.sql_queries.errors import QueryFailed, QueryRunning
from foundry_sdk.v2.sql_queries.models import RunningQueryStatus, SucceededQueryStatus

from pltr.contract import PltrError
from pltr.services.sql import (
    QueryNotSucceeded,
    SqlService,
    check_not_failed,
    decode_results,
    query_id_of,
)
from tests import foundry_json as fj
from tests import foundry_json_sql as sj

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

BASE = "/api/v2/sqlQueries"


@pytest.fixture
def no_sleep(monkeypatch):
    """Record the waits instead of sleeping."""
    sleeps = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    return sleeps


def raw_path(request) -> str:
    return request.url.raw_path.decode().split("?")[0]


# ------------------------------------------------------------------ submit


def test_submit_query_posts_query_and_fallback_branches(stub_foundry_http):
    stub_foundry_http.respond(json=sj.running())

    status = SqlService().submit_query(sj.QUERY, fallback_branch_ids=["dev", "master"])

    assert isinstance(status, RunningQueryStatus)
    assert status.query_id == sj.QUERY_ID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{BASE}/execute")
    assert dict(request.url.params) == {}  # GA: no preview
    assert json.loads(request.content) == {
        "query": sj.QUERY,
        "fallbackBranchIds": ["dev", "master"],
    }


def test_submit_query_leaves_out_unset_fields(stub_foundry_http):
    stub_foundry_http.respond(json=sj.succeeded())

    status = SqlService().submit_query(sj.QUERY)

    assert isinstance(status, SucceededQueryStatus)
    assert json.loads(stub_foundry_http.requests[0].content) == {"query": sj.QUERY}


# ------------------------------------------------------------ status/cancel


def test_get_query_status_encodes_the_query_id(stub_foundry_http):
    stub_foundry_http.respond(json=sj.failed("boom"))

    status = SqlService().get_query_status(sj.QUERY_ID)

    assert (status.type, status.error_message) == ("failed", "boom")
    [request] = stub_foundry_http.requests
    assert request.method == "GET"
    assert raw_path(request) == f"{BASE}/{sj.QUERY_ID_IN_PATH}/getStatus"
    assert "preview" not in request.url.params


def test_cancel_query(stub_foundry_http):
    stub_foundry_http.respond(204)

    assert SqlService().cancel_query(sj.QUERY_ID) is None

    [request] = stub_foundry_http.requests
    assert request.method == "POST"
    assert raw_path(request) == f"{BASE}/{sj.QUERY_ID_IN_PATH}/cancel"
    assert "preview" not in request.url.params


# ----------------------------------------------------------------- results


def test_get_query_results_decodes_arrow(stub_foundry_http):
    stub_foundry_http.respond(**sj.results())

    table = SqlService().get_query_results(sj.QUERY_ID)

    assert table.to_pylist() == [{"n": 1, "msg": "hi"}, {"n": 2, "msg": "there"}]
    [request] = stub_foundry_http.requests
    assert request.method == "GET"
    assert raw_path(request) == f"{BASE}/{sj.QUERY_ID_IN_PATH}/getResults"
    assert request.headers["Accept"] == "application/octet-stream"


def test_get_query_results_empty_body_is_an_empty_table(stub_foundry_http):
    stub_foundry_http.respond(content=b"")

    table = SqlService().get_query_results(sj.QUERY_ID)

    assert (table.num_rows, table.column_names) == (0, [])


def test_get_query_results_of_a_failed_query_raises_the_sdk_error(stub_foundry_http):
    stub_foundry_http.respond(
        500,
        json=fj.error(
            "QueryFailed", "INTERNAL", parameters={"errorMessage": "Out of memory"}
        ),
    )

    with pytest.raises(QueryFailed) as caught:
        SqlService().get_query_results(sj.QUERY_ID)

    assert caught.value.parameters["errorMessage"] == "Out of memory"


def test_get_query_results_of_a_running_query_raises_query_running(
    stub_foundry_http,
):
    stub_foundry_http.respond(
        400, json=fj.error("QueryRunning", "INVALID_ARGUMENT", parameters={})
    )

    with pytest.raises(QueryRunning):
        SqlService().get_query_results(sj.QUERY_ID)


# ------------------------------------------------------------ decode_results


def test_decode_results_arrow_stream_keeps_types_and_nulls():
    source = pa.table({"n": pa.array([1, None], pa.int64()), "s": ["a", None]})

    table = decode_results(sj.arrow_stream(source))

    assert table.equals(source)


def test_decode_results_arrow_file():
    source = pa.table({"n": [1, 2]})
    buffer = io.BytesIO()
    with ipc.new_file(buffer, source.schema) as writer:
        writer.write_table(source)

    assert decode_results(buffer.getvalue()).to_pylist() == [{"n": 1}, {"n": 2}]


def test_decode_results_csv_serialization():
    table = decode_results(b"name,count\nAlice,10\nBob,20\n")

    assert table.to_pylist() == [
        {"name": "Alice", "count": 10},
        {"name": "Bob", "count": 20},
    ]


@pytest.mark.parametrize("data", [None, b""])
def test_decode_results_nothing(data):
    assert decode_results(data).num_rows == 0


def test_decode_results_malformed_arrow_raises():
    with pytest.raises(PltrError, match="Could not decode the query results"):
        decode_results(b"\xff\xff\xff\xffgarbage")


# ---------------------------------------------------------------- statuses


def test_query_id_of_and_check_not_failed():
    running = RunningQueryStatus(queryId="q1", type="running")
    assert query_id_of(running) == "q1"
    assert check_not_failed(running) is running


@pytest.mark.parametrize(
    "body, message",
    [
        (sj.failed("syntax error"), "Query q1 failed: syntax error"),
        (sj.canceled(), "Query q1 was canceled."),
    ],
)
def test_wait_for_query_fails_for_failed_or_canceled(
    stub_foundry_http, no_sleep, body, message
):
    stub_foundry_http.respond(json=body)

    with pytest.raises(QueryNotSucceeded) as caught:
        SqlService().wait_for_query("q1", timeout=60)

    assert caught.value.message == message
    assert caught.value.exit_code == 7


def test_wait_for_query_polls_until_succeeded(stub_foundry_http, no_sleep):
    stub_foundry_http.respond(json=sj.running())
    stub_foundry_http.respond(json=sj.running())
    stub_foundry_http.respond(json=sj.succeeded())

    status = SqlService().wait_for_query(sj.QUERY_ID, timeout=60)

    assert isinstance(status, SucceededQueryStatus)
    assert len(stub_foundry_http.requests) == 3
    assert no_sleep == [2.0, 2.0]


def test_wait_for_query_uses_a_known_status_first(stub_foundry_http, no_sleep):
    status = SqlService().wait_for_query(
        "q1", timeout=60, status=SucceededQueryStatus(queryId="q1", type="succeeded")
    )

    assert status.query_id == "q1"
    assert stub_foundry_http.requests == []


def test_wait_for_query_times_out(stub_foundry_http, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    def sleep(seconds):
        clock[0] += seconds

    monkeypatch.setattr("time.sleep", sleep)
    stub_foundry_http.respond_always(json=sj.running())

    with pytest.raises(PltrError) as caught:
        SqlService().wait_for_query(sj.QUERY_ID, timeout=5)

    error = caught.value
    assert (error.error_type, error.exit_code) == ("timeout", 7)
    assert "still running after 5 seconds" in error.message
    assert f"pltr sql cancel {sj.QUERY_ID}" in error.hint
    # polled at t=0, 2, 4 and 5 (the last sleep is cut to the deadline)
    assert len(stub_foundry_http.requests) == 4


# ----------------------------------------------------------------- execute


def test_execute_query_runs_waits_and_fetches_results(stub_foundry_http, no_sleep):
    stub_foundry_http.respond(json=sj.running())
    stub_foundry_http.respond(json=sj.succeeded())
    stub_foundry_http.respond(**sj.results())

    query_id, table = SqlService().execute_query(sj.QUERY, timeout=60)

    assert query_id == sj.QUERY_ID
    assert table.num_rows == 2
    assert [
        (r.method, r.url.path.rsplit("/", 1)[-1]) for r in stub_foundry_http.requests
    ] == [
        ("POST", "execute"),
        ("GET", "getStatus"),
        ("GET", "getResults"),
    ]


def test_execute_query_that_succeeds_at_once_skips_polling(stub_foundry_http):
    stub_foundry_http.respond(json=sj.succeeded())
    stub_foundry_http.respond(**sj.results())

    query_id, table = SqlService().execute_query(sj.QUERY)

    assert (query_id, table.num_rows) == (sj.QUERY_ID, 2)
    assert len(stub_foundry_http.requests) == 2


def test_execute_query_that_fails_at_once(stub_foundry_http):
    stub_foundry_http.respond(json=sj.failed("Table not found"))

    with pytest.raises(QueryNotSucceeded, match="The query failed: Table not found"):
        SqlService().execute_query(sj.QUERY)

    assert len(stub_foundry_http.requests) == 1
