"""`--wait` on commands that start asynchronous work (#195)."""

import json
from typing import Any, Dict

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json_orchestration as oj

pytestmark = pytest.mark.usefixtures("isolated_home")

runner = CliRunner()

BUILD = oj.BUILD_RID
TARGET = json.dumps(oj.MANUAL_TARGET)
CONNECTION = "ri.magritte..source.c1"
FILE_IMPORT = "ri.magritte..file-import.f1"


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)


def run(*args: str) -> Any:
    return runner.invoke(app, [*args, "--format", "json"])


def error_of(result: Any) -> Dict[str, Any]:
    assert result.stdout == ""
    return json.loads(result.stderr.strip().splitlines()[-1])


def running() -> Dict[str, Any]:
    return oj.build(status="RUNNING", finishedTime=None)


# ------------------------------------------------------------------ builds


def test_build_create_waits_until_the_build_succeeds(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=running())
    stub_foundry_http.respond(json=running())
    stub_foundry_http.respond(json=oj.build(status="SUCCEEDED"))

    result = run("orchestration", "builds", "create", TARGET, "--wait")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "SUCCEEDED"
    paths = [r.url.path for r in stub_foundry_http.requests]
    assert paths == [
        "/api/v2/orchestration/builds/create",
        f"/api/v2/orchestration/builds/{BUILD}",
        f"/api/v2/orchestration/builds/{BUILD}",
    ]


def test_a_failed_build_names_its_failed_jobs(stub_foundry_http) -> None:
    failed_job = oj.job("ri.foundry.main.job.failed", jobStatus="FAILED")
    stub_foundry_http.respond(json=running())
    stub_foundry_http.respond(json=oj.build(status="FAILED"))
    stub_foundry_http.respond(json={"data": [failed_job, oj.job()]})

    result = run("orchestration", "builds", "create", TARGET, "--wait")

    assert result.exit_code == 8
    error = error_of(result)
    assert error["type"] == "work_failed"
    assert "ri.foundry.main.job.failed" in error["message"]
    assert error["parameters"]["buildRid"] == BUILD
    assert error["parameters"]["status"] == "FAILED"
    (job,) = error["parameters"]["failedJobs"]
    assert job["rid"] == "ri.foundry.main.job.failed"
    assert job["outputs"][0]["datasetRid"] == oj.DATASET_RID
    assert error["suggestedCommand"] == f"pltr orchestration builds jobs {BUILD}"


def test_a_build_still_running_at_the_timeout(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=running())

    result = run(
        "orchestration", "builds", "create", TARGET, "--wait", "--timeout", "0"
    )

    assert result.exit_code == 9
    error = error_of(result)
    assert error["type"] == "wait_timeout"
    assert error["parameters"] == {"buildRid": BUILD, "status": "RUNNING"}
    assert error["suggestedCommand"] == f"pltr orchestration builds wait {BUILD}"


def test_builds_wait_resumes_waiting(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=running())
    stub_foundry_http.respond(json=oj.build(status="CANCELED"))
    stub_foundry_http.respond(json={"data": []})

    result = run("orchestration", "builds", "wait", BUILD)

    assert result.exit_code == 8
    assert error_of(result)["parameters"]["status"] == "CANCELED"


def test_build_create_without_wait_returns_at_once(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=running())

    result = run("orchestration", "builds", "create", TARGET)

    assert result.exit_code == 0
    assert len(stub_foundry_http.requests) == 1


# --------------------------------------------------------------- schedules


def test_schedule_run_waits_for_its_build(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=oj.schedule_run())
    stub_foundry_http.respond(json=oj.build(status="SUCCEEDED"))

    result = run("orchestration", "schedules", "run", oj.SCHEDULE_RID, "--wait")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "SUCCEEDED"


def test_a_schedule_run_error_fails(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json=oj.schedule_run(
            result={
                "type": "error",
                "errorName": "CYCLICDEPENDENCY",
                "description": "nope",
            }
        )
    )

    result = run("orchestration", "schedules", "run", oj.SCHEDULE_RID, "--wait")

    assert result.exit_code == 8
    assert "CYCLICDEPENDENCY" in error_of(result)["message"]


def test_an_ignored_schedule_run_succeeds_with_nothing_to_wait_for(
    stub_foundry_http,
) -> None:
    stub_foundry_http.respond(json=oj.schedule_run(result={"type": "ignored"}))

    result = run("orchestration", "schedules", "run", oj.SCHEDULE_RID, "--wait")

    assert result.exit_code == 0
    assert json.loads(result.stdout)["result"]["type"] == "ignored"


# ----------------------------------------------------------------- imports


def test_an_import_waits_for_its_build(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=BUILD)
    stub_foundry_http.respond(json=oj.build(status="SUCCEEDED"))

    result = run(
        "connectivity", "import", "execute-file", CONNECTION, FILE_IMPORT, "--wait"
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["rid"] == BUILD


# --------------------------------------------------------------------- SQL


def test_sql_submit_waits_for_the_query(stub_foundry_http) -> None:
    stub_foundry_http.respond(json={"type": "running", "queryId": "q-1"})
    stub_foundry_http.respond(json={"type": "succeeded", "queryId": "q-1"})

    result = run("sql", "submit", "SELECT 1", "--wait")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {"type": "succeeded", "queryId": "q-1"}


def test_sql_wait_timeout_and_failure_use_the_wait_exit_codes(
    stub_foundry_http, monkeypatch
) -> None:
    import itertools

    clock = itertools.count(step=1000)  # every reading is 1000 s later
    monkeypatch.setattr("time.monotonic", lambda: next(clock))
    stub_foundry_http.respond(json={"type": "running", "queryId": "q-1"})
    timed_out = run("sql", "wait", "q-1", "--timeout", "1")
    stub_foundry_http.respond(json={"type": "failed", "errorMessage": "bad SQL"})
    failed = run("sql", "wait", "q-1")

    assert (timed_out.exit_code, error_of(timed_out)["type"]) == (9, "wait_timeout")
    assert (failed.exit_code, error_of(failed)["type"]) == (8, "work_failed")


# ------------------------------------------------------ review fixes (#195)

TABLE_IMPORT = "ri.magritte..table-import.t1"


def pending_run() -> Dict[str, Any]:
    body = oj.schedule_run()
    del body["result"]  # the service is still triggering the schedule
    return body


def test_a_pending_schedule_run_is_waited_for(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=pending_run())
    stub_foundry_http.respond(json={"data": [pending_run()]})
    stub_foundry_http.respond(json={"data": [oj.schedule_run()]})
    stub_foundry_http.respond(json=oj.build(status="SUCCEEDED"))

    result = run("orchestration", "schedules", "run", oj.SCHEDULE_RID, "--wait")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "SUCCEEDED"


def test_a_schedule_run_whose_build_fails(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=oj.schedule_run())
    stub_foundry_http.respond(json=oj.build(status="FAILED"))
    stub_foundry_http.respond(json={"data": []})

    result = run("orchestration", "schedules", "run", oj.SCHEDULE_RID, "--wait")

    assert result.exit_code == 8


def test_a_schedule_run_that_times_out(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=oj.schedule_run())
    stub_foundry_http.respond(json=running())

    result = run(
        "orchestration",
        "schedules",
        "run",
        oj.SCHEDULE_RID,
        "--wait",
        "--timeout",
        "0",
    )

    assert result.exit_code == 9


@pytest.mark.parametrize(
    "command, import_rid",
    [("execute-file", FILE_IMPORT), ("execute-table", TABLE_IMPORT)],
)
@pytest.mark.parametrize("final, code", [("SUCCEEDED", 0), ("FAILED", 8), (None, 9)])
def test_imports_wait_for_their_build(
    stub_foundry_http, command, import_rid, final, code
) -> None:
    stub_foundry_http.respond(json=BUILD)
    args = ["connectivity", "import", command, CONNECTION, import_rid, "--wait"]
    if final is None:
        stub_foundry_http.respond(json=running())
        args += ["--timeout", "0"]
    else:
        stub_foundry_http.respond(json=oj.build(status=final))
        stub_foundry_http.respond(json={"data": []})

    assert run(*args).exit_code == code


def test_sql_submit_wait_failure_and_timeout(stub_foundry_http, monkeypatch) -> None:
    import itertools

    stub_foundry_http.respond(json={"type": "running", "queryId": "q-1"})
    stub_foundry_http.respond(json={"type": "failed", "errorMessage": "bad SQL"})
    failed = run("sql", "submit", "SELECT 1", "--wait")
    clock = itertools.count(step=1000)
    monkeypatch.setattr("time.monotonic", lambda: next(clock))
    stub_foundry_http.respond(json={"type": "running", "queryId": "q-2"})
    timed_out = run("sql", "submit", "SELECT 1", "--wait", "--timeout", "1")

    assert failed.exit_code == 8
    assert timed_out.exit_code == 9


def test_transient_errors_while_waiting_are_retried(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=running())
    stub_foundry_http.respond(503, json={})
    stub_foundry_http.respond(json=oj.build(status="SUCCEEDED"))

    result = run("orchestration", "builds", "create", TARGET, "--wait")

    assert result.exit_code == 0, result.stderr


def test_an_error_while_waiting_names_the_started_build(stub_foundry_http) -> None:
    from tests import foundry_json as fj

    stub_foundry_http.respond(json=running())
    stub_foundry_http.respond(403, json=fj.error("Nope", "PERMISSION_DENIED"))

    result = run("orchestration", "builds", "create", TARGET, "--wait")

    error = error_of(result)
    assert result.exit_code == 4
    assert BUILD in error["hint"]
    assert error["suggestedCommand"] == f"pltr orchestration builds wait {BUILD}"


def test_failed_jobs_that_cant_be_listed_still_fail_the_build(
    stub_foundry_http,
) -> None:
    from tests import foundry_json as fj

    stub_foundry_http.respond(json=oj.build(status="FAILED"))
    stub_foundry_http.respond(403, json=fj.error("Nope", "PERMISSION_DENIED"))

    result = run("orchestration", "builds", "wait", BUILD)

    assert result.exit_code == 8
    assert error_of(result)["parameters"]["failedJobs"] == []


def test_json_mode_says_when_the_work_starts(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=running())
    stub_foundry_http.respond(json=oj.build(status="SUCCEEDED"))

    result = run("orchestration", "builds", "create", TARGET, "--wait")

    first = json.loads(result.stderr.strip().splitlines()[0])
    assert first == {
        "type": "started",
        "message": f"Started build {BUILD}; waiting for it.",
        "buildRid": BUILD,
    }


def test_wait_commands_refuse_emit_code(stub_foundry_http) -> None:
    for args in (
        ["orchestration", "builds", "create", TARGET, "--wait"],
        ["orchestration", "builds", "wait", BUILD],
    ):
        result = runner.invoke(app, [*args, "--emit-code", "--format", "json"])
        assert result.exit_code == 2, args
        assert error_of(result)["type"] == "emit_code_unsupported"


def test_wait_until_clamps_its_last_sleep_to_the_deadline(monkeypatch) -> None:
    from pltr.services import waiting

    now = [0.0]
    sleeps = []
    monkeypatch.setattr(waiting.time, "monotonic", lambda: now[0])

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(waiting.time, "sleep", sleep)
    with pytest.raises(RuntimeError):
        waiting.wait_until(
            lambda: "running",
            lambda value: False,
            timeout=5,
            on_timeout=lambda latest: RuntimeError("timed out"),
        )
    assert sleeps == [2.0, 3.0]


def test_wait_until_keeps_polling_through_a_network_error(monkeypatch) -> None:
    from foundry_sdk import _errors as sdk

    from pltr.services import waiting

    monkeypatch.setattr(waiting.time, "sleep", lambda seconds: None)
    answers = iter([sdk.ConnectionError("down"), "done"])

    def fetch() -> str:
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    value = waiting.wait_until(
        fetch,
        lambda v: v == "done",
        timeout=60,
        on_timeout=lambda latest: RuntimeError("timed out"),
        current="running",
    )

    assert value == "done"
