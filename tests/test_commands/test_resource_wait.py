"""`pltr resource wait`: poll until a resource exists (#219)."""

import itertools
import json
from typing import Any, Dict, List

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_filesystem as fs

# Every Resource endpoint is GA: a stray preview= would raise a UserWarning.
pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()

RID = fs.DATASET_RID
PATH = "/Test Space/Test Project/orders clean"
DATASET = fs.child_resource(RID, "orders clean")
BY_PATH = "/api/v2/filesystem/resources/getByPath"
BY_RID = f"/api/v2/filesystem/resources/{RID}"
PATH_NOT_FOUND = {
    "status_code": 404,
    "json": fj.error("PathNotFound", parameters={"path": PATH}),
}
RESOURCE_NOT_FOUND = {
    "status_code": 404,
    "json": fj.error("ResourceNotFound", parameters={"resourceRid": RID}),
}


@pytest.fixture(autouse=True)
def sleeps(monkeypatch) -> List[float]:
    """Record the poll intervals instead of sleeping."""
    slept: List[float] = []
    monkeypatch.setattr("time.sleep", slept.append)
    return slept


@pytest.fixture
def fast_clock(monkeypatch) -> None:
    """Every reading of the clock is 1000 s after the previous one."""
    clock = itertools.count(step=1000)
    monkeypatch.setattr("time.monotonic", lambda: next(clock))


def run(*args: str) -> Any:
    return runner.invoke(app, ["resource", "wait", *args, "--format", "json"])


def error_of(result: Any) -> Dict[str, Any]:
    assert result.stdout == ""
    return json.loads(result.stderr.strip().splitlines()[-1])


def paths(stub) -> List[str]:
    return [request.url.path for request in stub.requests]


# ----------------------------------------------------------------- success


def test_waits_until_something_exists_at_the_path(stub_foundry_http) -> None:
    stub_foundry_http.respond(**PATH_NOT_FOUND)
    stub_foundry_http.respond(**PATH_NOT_FOUND)
    stub_foundry_http.respond(json=DATASET)

    result = run(PATH)

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == fj.sdk_json(DATASET)
    assert paths(stub_foundry_http) == [BY_PATH] * 3
    assert all(
        dict(request.url.params) == {"path": PATH}
        for request in stub_foundry_http.requests
    )
    # Nothing was started, so there is no {"type": "started"} line.
    assert result.stderr == ""


def test_waits_until_a_rid_exists(stub_foundry_http) -> None:
    stub_foundry_http.respond(**RESOURCE_NOT_FOUND)
    stub_foundry_http.respond(json=DATASET)

    result = run(RID)

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["rid"] == RID
    assert paths(stub_foundry_http) == [BY_RID, BY_RID]
    assert all(r.method == "GET" for r in stub_foundry_http.requests)


def test_an_existing_resource_is_printed_at_once(stub_foundry_http, sleeps) -> None:
    stub_foundry_http.respond(json=DATASET)

    result = run(PATH)

    assert result.exit_code == 0, result.stderr
    assert len(stub_foundry_http.requests) == 1
    assert sleeps == []


def test_text_mode_prints_the_resource_and_says_it_was_found(
    stub_foundry_http,
) -> None:
    stub_foundry_http.respond(**PATH_NOT_FOUND)
    stub_foundry_http.respond(json=DATASET)

    result = runner.invoke(app, ["resource", "wait", PATH])

    assert result.exit_code == 0, result.stderr
    assert RID in result.stdout and "FOUNDRY_DATASET" in result.stdout
    assert RID in result.stderr


def test_polls_with_backoff_up_to_ten_seconds(stub_foundry_http, sleeps) -> None:
    for _ in range(7):
        stub_foundry_http.respond(**PATH_NOT_FOUND)
    stub_foundry_http.respond(json=DATASET)

    result = run(PATH)

    assert result.exit_code == 0, result.stderr
    assert sleeps == [2.0, 3.0, 4.5, 6.75, 10.0, 10.0, 10.0]


def test_transient_errors_while_polling_are_retried(stub_foundry_http) -> None:
    # A 500: the SDK retries 429 and 503 itself, so they wouldn't test pltr.
    stub_foundry_http.respond(**PATH_NOT_FOUND)
    stub_foundry_http.respond(
        status_code=500, json=fj.error("InternalServerError", "INTERNAL")
    )
    stub_foundry_http.respond(json=DATASET)

    result = run(PATH)

    assert result.exit_code == 0, result.stderr
    assert len(stub_foundry_http.requests) == 3


def test_a_resource_not_found_answer_to_a_path_also_means_not_yet(
    stub_foundry_http,
) -> None:
    stub_foundry_http.respond(**RESOURCE_NOT_FOUND)
    stub_foundry_http.respond(json=DATASET)

    result = run(PATH)

    assert result.exit_code == 0, result.stderr
    assert paths(stub_foundry_http) == [BY_PATH, BY_PATH]


def test_a_trashed_resource_counts_but_warns(stub_foundry_http) -> None:
    stub_foundry_http.respond(json={**DATASET, "trashStatus": "DIRECTLY_TRASHED"})

    result = run(PATH)

    assert result.exit_code == 0, result.stderr
    [line] = [json.loads(line) for line in result.stderr.splitlines()]
    assert line["type"] == "warning"
    assert "trash" in line["message"]


# ----------------------------------------------------------------- timeout


def test_a_path_still_missing_at_the_timeout_exits_9(
    stub_foundry_http, fast_clock
) -> None:
    stub_foundry_http.respond_always(**PATH_NOT_FOUND)

    result = run(PATH, "--timeout", "30")

    assert result.exit_code == 9
    error = error_of(result)
    assert error["type"] == "wait_timeout"
    assert error["exitCode"] == 9
    assert error["parameters"] == {"path": PATH}
    assert PATH in error["message"]
    assert error["suggestedCommand"] == (f"pltr resource wait '{PATH}' --timeout 30")


def test_a_rid_still_missing_at_the_timeout_exits_9(
    stub_foundry_http, fast_clock
) -> None:
    stub_foundry_http.respond_always(**RESOURCE_NOT_FOUND)

    result = run(RID)

    assert result.exit_code == 9
    error = error_of(result)
    assert error["parameters"] == {"resourceRid": RID}
    assert error["suggestedCommand"] == f"pltr resource wait {RID}"
    # A resource gets its RID when it's created: a RID never found is
    # usually a wrong one, not a slow push.
    assert "git push" not in error["hint"]
    assert "check the RID" in error["hint"]


@pytest.mark.parametrize(
    "given, shown", [("1234567", "1234567"), ("2.5", "2.5"), ("90.0", "90")]
)
def test_the_timeout_is_shown_as_given(
    stub_foundry_http, fast_clock, given, shown
) -> None:
    stub_foundry_http.respond_always(**PATH_NOT_FOUND)

    error = error_of(run(PATH, "--timeout", given))

    assert error["suggestedCommand"].endswith(f"--timeout {shown}")
    assert f"after {shown} seconds" in error["message"]


def test_timeout_zero_checks_once(stub_foundry_http, sleeps) -> None:
    stub_foundry_http.respond(**PATH_NOT_FOUND)

    result = run(PATH, "--timeout", "0")

    assert result.exit_code == 9
    assert len(stub_foundry_http.requests) == 1
    assert sleeps == []


def test_the_suggested_command_keeps_the_profile(stub_foundry_http, fast_clock) -> None:
    stub_foundry_http.respond_always(**PATH_NOT_FOUND)

    result = run(PATH, "--profile", "dev")

    assert error_of(result)["suggestedCommand"] == (
        f"pltr resource wait '{PATH}' --profile dev"
    )


# ------------------------------------------------- errors that fail at once


@pytest.mark.parametrize(
    "status, error_name, error_type, exit_code",
    [
        (401, "Unauthorized", "auth_error", 3),
        (403, "GetByPathPermissionDenied", "permission_denied", 4),
        # a 404 that doesn't say the resource doesn't exist
        (404, "SomethingElseNotFound", "not_found", 5),
        (400, "InvalidPath", "validation_error", 6),
    ],
)
def test_other_errors_fail_at_once(
    stub_foundry_http, status, error_name, error_type, exit_code
) -> None:
    stub_foundry_http.respond_always(
        status, json=fj.error(error_name, parameters={"path": PATH})
    )

    result = run(PATH)

    assert result.exit_code == exit_code, result.stderr
    assert error_of(result)["type"] == error_type
    assert len(stub_foundry_http.requests) == 1


def test_a_not_found_without_a_foundry_body_fails_at_once(stub_foundry_http) -> None:
    """A 404 without an error body: the endpoint isn't on this stack."""
    stub_foundry_http.respond_always(404, content=b"")

    result = run(RID)

    assert result.exit_code == 5
    assert error_of(result)["type"] == "api_not_found"
    assert len(stub_foundry_http.requests) == 1


def test_a_space_fails_at_once(stub_foundry_http) -> None:
    stub_foundry_http.respond_always(
        400,
        json=fj.error(
            "GetSpaceResourceNotSupported",
            "INVALID_ARGUMENT",
            parameters={"spaceRid": fj.SPACE_RID},
        ),
    )

    result = run(fj.SPACE_RID)

    assert result.exit_code == 6
    assert error_of(result)["errorName"] == "GetSpaceResourceNotSupported"
    assert len(stub_foundry_http.requests) == 1


def test_an_error_after_polling_started_fails_at_once(stub_foundry_http) -> None:
    stub_foundry_http.respond(**PATH_NOT_FOUND)
    stub_foundry_http.respond(status_code=401, json=fj.error("Unauthorized"))

    result = run(PATH)

    assert result.exit_code == 3
    assert len(stub_foundry_http.requests) == 2


@pytest.mark.parametrize(
    "rid, what",
    [
        ("ri.foundry.main.build.0d6f6c63-2a2e-4c7e-9b1a-3c3c3c3c3c3c", "build"),
        ("ri.foundry.main.job.0d6f6c63-2a2e-4c7e-9b1a-3c3c3c3c3c3c", "job"),
        ("ri.foundry.main.transaction.0d6f6c63-2a2e-4c7e-9b1a-3c3c", "transaction"),
        ("ri.scheduler.main.schedule.0d6f6c63-2a2e-4c7e-9b1a-3c3c", "schedule"),
    ],
)
def test_a_rid_that_is_never_a_compass_resource_is_refused(
    stub_foundry_http, rid, what
) -> None:
    """The API answers ResourceNotFound for these, like "not yet": refuse
    them instead of polling until --timeout."""
    result = run(rid)

    assert result.exit_code == 2
    error = error_of(result)
    assert error["type"] == "wrong_resource_type"
    assert what in error["message"]
    assert stub_foundry_http.requests == []


def test_a_build_rid_suggests_builds_wait(stub_foundry_http) -> None:
    build = "ri.foundry.main.build.0d6f6c63-2a2e-4c7e-9b1a-3c3c3c3c3c3c"

    result = run(build)

    assert error_of(result)["suggestedCommand"] == (
        f"pltr orchestration builds wait {build}"
    )


def test_something_that_is_neither_a_rid_nor_a_path_is_a_usage_error(
    stub_foundry_http,
) -> None:
    result = run("not-a-rid")

    assert result.exit_code == 2
    assert error_of(result)["type"] == "usage_error"
    assert stub_foundry_http.requests == []


def test_a_negative_timeout_is_a_usage_error(stub_foundry_http) -> None:
    result = run(PATH, "--timeout", "-1")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_emit_code_is_unsupported(stub_foundry_http) -> None:
    result = runner.invoke(
        app, ["resource", "wait", PATH, "--emit-code", "--format", "json"]
    )

    assert result.exit_code == 2
    error = error_of(result)
    assert error["type"] == "emit_code_unsupported"
    assert "resource get-by-path" in error["message"]
    assert stub_foundry_http.requests == []


def test_the_manifest_says_it_takes_a_path() -> None:
    result = runner.invoke(
        app, ["commands", "show", "resource wait", "--format", "json"]
    )

    assert result.exit_code == 0, result.stderr
    command = json.loads(result.stdout)
    [argument] = command["arguments"]
    assert argument["acceptsPath"] is True
    assert argument["resourceKind"] == "resource"
    # A resource has no RID before it exists: the path is the usual input.
    assert argument["name"] == "resource"
    assert argument["help"].startswith("Compass path")


# ------------------------------------------------------------- the skill


def push_loop() -> str:
    """The skill's push -> wait -> build -> assert example (#219)."""
    from pathlib import Path

    skill = Path(__file__).resolve().parents[2] / "claude_skill" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    start = text.index("**After a git push to a code repository**")
    return text[start : text.index("\n## ", start)]


def test_the_skill_builds_the_branch_that_was_pushed() -> None:
    """Without --branch the build runs the default branch's (old) code."""
    loop = push_loop()
    [build] = [line for line in loop.splitlines() if "builds create" in line]
    assert "--branch" in build
    assert "--wait" in build


def test_the_skill_asserts_the_change_not_just_fresh_rows() -> None:
    """--min-rows/--updated-within pass for a build of the old code too."""
    loop = push_loop()
    [check] = [line for line in loop.splitlines() if "pltr assert dataset" in line]
    assert "--schema" in check
    assert "BuildTargetsMissingJobSpecs" in loop
