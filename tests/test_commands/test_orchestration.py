"""Tests for `pltr orchestration` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_orchestration as fo

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()
API = "/api/v2/orchestration"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, ["orchestration", *args], **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


def request_body(request):
    return json.loads(request.content)


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


# ------------------------------------------------------------------- help


@pytest.mark.parametrize(
    "group, beta, ga",
    [
        ("builds", {"search"}, {"get", "create", "cancel", "jobs", "get-batch"}),
        ("jobs", {"get", "get-batch"}, set()),
        (
            "schedules",
            {"get", "create", "replace"},
            {"delete", "pause", "unpause", "run", "runs"},
        ),
    ],
)
def test_beta_commands_are_labeled_in_help(group, beta, ga):
    result = invoke(group, "--help")

    lines = result.stdout.splitlines()
    for command in beta | ga:
        line = next(
            line for line in lines if line.lstrip("│ ").startswith(f"{command} ")
        )
        assert ("[beta]" in line) == (command in beta), line


# ------------------------------------------------------------- builds get


def test_get_build_table(stub_foundry_http):
    stub_foundry_http.respond(json=fo.build())

    result = invoke("builds", "get", fo.BUILD_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        fo.BUILD_RID,
        "SUCCEEDED",
        "master",
        fo.JOB_RID,
        fo.SCHEDULE_RID,
        "develop",
        "30 SECONDS",
        "2024-01-01T00:10:00+00:00",
        fj.USER_ID,
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/builds/{fo.BUILD_RID}"
    assert "preview" not in request.url.params


def test_get_build_json_is_the_sdk_serialization(stub_foundry_http):
    stub_foundry_http.respond(json=fo.build())

    result = invoke("builds", "get", fo.BUILD_RID, "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == fo.sdk_json(fo.build())
    assert result.stderr == ""


def test_get_build_csv(stub_foundry_http):
    stub_foundry_http.respond(json=fo.build(finishedTime=None, status="RUNNING"))

    result = invoke("builds", "get", fo.BUILD_RID, "-f", "csv")

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row["RID"] == fo.BUILD_RID
    assert row["Status"] == "RUNNING"
    assert row["Finished"] == ""
    assert row["Abort On Failure"] == "false"


def test_get_build_output_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=fo.build())
    target = tmp_path / "build.json"

    result = invoke("builds", "get", fo.BUILD_RID, "-f", "json", "-o", str(target))

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert json.loads(target.read_text())["rid"] == fo.BUILD_RID


def test_get_build_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("BuildNotFound", parameters={"buildRid": fo.BUILD_RID})
    )

    result = invoke("builds", "get", fo.BUILD_RID, "--format", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == ("not_found", "BuildNotFound")


def test_get_build_invalid_rid_is_a_usage_error(stub_foundry_http):
    result = invoke("builds", "get", "not-a-rid", "--format", "json")

    assert result.exit_code == 2
    assert "not a valid RID" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


# ---------------------------------------------------------- builds create


def test_create_build(stub_foundry_http):
    stub_foundry_http.respond(json=fo.build(status="RUNNING", finishedTime=None))

    result = invoke(
        "builds",
        "create",
        json.dumps(fo.MANUAL_TARGET),
        "--branch",
        "feature",
        "--fallback-branch",
        "develop",
        "--fallback-branch",
        "master",
        "--force",
        "--retry-count",
        "2",
    )

    assert result.exit_code == 0, result.output
    assert f"Started build {fo.BUILD_RID} (RUNNING)" in result.stderr
    assert f"pltr orchestration builds get {fo.BUILD_RID}" in result.stderr
    assert fo.BUILD_RID in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{API}/builds/create")
    assert request_body(request) == {
        "target": fo.MANUAL_TARGET,
        "fallbackBranches": ["develop", "master"],
        "branchName": "feature",
        "forceBuild": True,  # --force means "force build", not "skip a prompt"
        "abortOnFailure": False,
        "notificationsEnabled": True,
        "retryCount": 2,
    }


def test_create_build_defaults(stub_foundry_http):
    stub_foundry_http.respond(json=fo.build())

    result = invoke(
        "builds", "create", json.dumps(fo.MANUAL_TARGET), "--no-notifications"
    )

    assert result.exit_code == 0, result.output
    assert request_body(stub_foundry_http.requests[0]) == {
        "target": fo.MANUAL_TARGET,
        "fallbackBranches": [],
        "forceBuild": False,
        "abortOnFailure": False,
        "notificationsEnabled": False,
    }


def test_create_build_target_from_file(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=fo.build())
    target = {"type": "upstream", "targetRids": [fo.DATASET_RID], "ignoredRids": []}
    path = tmp_path / "target.json"
    path.write_text(json.dumps(target))

    result = invoke("builds", "create", f"@{path}", "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == fo.sdk_json(fo.build())
    assert result.stderr == ""  # success/info messages are suppressed in JSON mode
    assert request_body(stub_foundry_http.requests[0])["target"] == target


def test_create_build_invalid_json_is_a_usage_error(stub_foundry_http):
    result = invoke("builds", "create", "{not json", "--format", "json")

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert "invalid JSON" in error["message"]
    assert stub_foundry_http.requests == []


def test_create_build_invalid_target_is_a_usage_error(stub_foundry_http):
    result = invoke("builds", "create", '{"type": "sideways"}', "--format", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "usage_error"
    assert stub_foundry_http.requests == []


def test_create_build_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403, json=fj.error("CreateBuildPermissionDenied", "PERMISSION_DENIED")
    )

    result = invoke(
        "builds", "create", json.dumps(fo.MANUAL_TARGET), "--format", "json"
    )

    assert result.exit_code == 4
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == (
        "permission_denied",
        "CreateBuildPermissionDenied",
    )


# ---------------------------------------------------------- builds cancel


def test_cancel_build_requires_yes_when_not_interactive(stub_foundry_http):
    result = invoke("builds", "cancel", fo.BUILD_RID, "--format", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub_foundry_http.requests == []


def test_cancel_build_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("builds", "cancel", fo.BUILD_RID, "--yes")

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Requested cancellation of build {fo.BUILD_RID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/builds/{fo.BUILD_RID}/cancel",
    )


def test_cancel_build_json_prints_null(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("builds", "cancel", fo.BUILD_RID, "-y", "-f", "json")

    assert result.exit_code == 0
    assert json.loads(result.stdout) is None
    assert result.stderr == ""


def test_cancel_build_prompts_when_interactive(stub_foundry_http, interactive):
    stub_foundry_http.respond(204)

    result = invoke("builds", "cancel", fo.BUILD_RID, input="y\n")

    assert result.exit_code == 0, result.output
    assert f"Cancel build {fo.BUILD_RID}?" in result.stderr
    assert len(stub_foundry_http.requests) == 1


def test_cancel_build_answering_no_aborts(stub_foundry_http, interactive):
    result = invoke("builds", "cancel", fo.BUILD_RID, input="n\n")

    assert result.exit_code == 1
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------ builds jobs


def test_build_jobs_table(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.job()]})

    result = invoke("builds", "jobs", fo.BUILD_RID)

    assert result.exit_code == 0, result.output
    for expected in (fo.JOB_RID, "SUCCEEDED", fo.DATASET_RID, fo.MEDIA_SET_RID):
        assert expected in result.stdout


def test_build_jobs_json_has_the_paged_shape(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.job()], "nextPageToken": "t2"})

    result = invoke("builds", "jobs", fo.BUILD_RID, "--format", "json")

    assert json.loads(result.stdout) == {
        "data": [fo.sdk_json(fo.job())],
        "nextPageToken": "t2",
    }


def test_build_jobs_csv_outputs_column(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.job()]})

    result = invoke("builds", "jobs", fo.BUILD_RID, "--format", "csv")

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row["Outputs"] == f"{fo.DATASET_RID}, {fo.MEDIA_SET_RID}"
    assert row["Status"] == "SUCCEEDED"


def test_build_jobs_all_pages(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.job()], "nextPageToken": "t2"})
    stub_foundry_http.respond(json={"data": [fo.job(fo.JOB_RID_2)]})

    result = invoke(
        "builds", "jobs", fo.BUILD_RID, "--all", "--page-size", "1", "-f", "json"
    )

    assert [job["rid"] for job in json.loads(result.stdout)["data"]] == [
        fo.JOB_RID,
        fo.JOB_RID_2,
    ]
    assert [dict(r.url.params) for r in stub_foundry_http.requests] == [
        {"pageSize": "1"},
        {"pageSize": "1", "pageToken": "t2"},
    ]


def test_build_jobs_empty(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    result = invoke("builds", "jobs", fo.BUILD_RID)

    assert result.exit_code == 0
    assert "No results." in result.stderr


# ---------------------------------------------------------- builds search


def search_request_body(stub):
    [request] = stub.requests
    assert (request.method, request.url.path) == ("POST", f"{API}/builds/search")
    assert request.url.params["preview"] == "true"
    return request_body(request)


def test_search_builds_single_shortcut(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.build(status="FAILED")]})

    result = invoke("builds", "search", "--status", "failed")

    assert result.exit_code == 0, result.output
    assert "FAILED" in result.stdout
    assert search_request_body(stub_foundry_http) == {
        "where": {"type": "eq", "field": "STATUS", "value": "FAILED"}
    }


def test_search_builds_combines_shortcuts_with_and(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    result = invoke(
        "builds",
        "search",
        "--status",
        "FAILED",
        "--branch",
        "master",
        "--created-by",
        fj.USER_ID,
        "--started-after",
        "2024-01-31T01:00:00+01:00",
        "--finished-before",
        "2024-02-01T00:00:00Z",
        "--order-by",
        "started_time",
        "--order-by",
        "FINISHED_TIME:asc",
        "--page-size",
        "10",
    )

    assert result.exit_code == 0, result.output
    assert search_request_body(stub_foundry_http) == {
        "where": {
            "type": "and",
            "items": [
                {"type": "eq", "field": "STATUS", "value": "FAILED"},
                {"type": "eq", "field": "BRANCH_NAME", "value": "master"},
                {"type": "eq", "field": "CREATED_BY", "value": fj.USER_ID},
                {
                    "type": "gte",
                    "field": "STARTED_TIME",
                    "value": "2024-01-31T00:00:00Z",
                },
                {
                    "type": "lt",
                    "field": "FINISHED_TIME",
                    "value": "2024-02-01T00:00:00Z",
                },
            ],
        },
        "orderBy": {
            "fields": [
                {"field": "STARTED_TIME", "direction": "DESC"},
                {"field": "FINISHED_TIME", "direction": "ASC"},
            ]
        },
        "pageSize": 10,
    }


def test_search_builds_where_json_and_a_shortcut(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json={"data": [fo.build()]})
    where = {
        "type": "or",
        "items": [
            {"type": "eq", "field": "STATUS", "value": "FAILED"},
            {"type": "eq", "field": "STATUS", "value": "CANCELED"},
        ],
    }
    path = tmp_path / "where.json"
    path.write_text(json.dumps(where))

    result = invoke("builds", "search", "--where", f"@{path}", "--branch", "master")

    assert result.exit_code == 0, result.output
    assert search_request_body(stub_foundry_http)["where"] == {
        "type": "and",
        "items": [where, {"type": "eq", "field": "BRANCH_NAME", "value": "master"}],
    }


def test_search_builds_json_output(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.build()], "nextPageToken": "next"})

    result = invoke(
        "builds",
        "search",
        "--where",
        '{"type": "eq", "field": "RID", "value": "%s"}' % fo.BUILD_RID,
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [fo.sdk_json(fo.build())],
        "nextPageToken": "next",
    }
    assert result.stderr == ""


def test_search_builds_all_pages(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.build()], "nextPageToken": "t2"})
    stub_foundry_http.respond(json={"data": [fo.build(fo.BUILD_RID_2)]})

    result = invoke("builds", "search", "--branch", "master", "--all", "-f", "csv")

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [row["RID"] for row in rows] == [fo.BUILD_RID, fo.BUILD_RID_2]
    assert [
        request_body(request).get("pageToken") for request in stub_foundry_http.requests
    ] == [None, "t2"]


def test_search_builds_requires_a_filter(stub_foundry_http):
    result = invoke("builds", "search", "--format", "json")

    assert result.exit_code == 2
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert "the API requires a filter" in error["message"]
    assert stub_foundry_http.requests == []


@pytest.mark.parametrize(
    "args, message",
    [
        (["--started-after", "yesterday"], "not an ISO-8601 timestamp"),
        (["--started-before", "2024-01-31T00:00:00"], "with a time zone"),
        (["--status", "DONE"], "DONE"),
        (["--branch", "master", "--order-by", "CREATED_TIME"], "FIELD[:ASC|DESC]"),
        (["--branch", "master", "--order-by", "STARTED_TIME:UP"], "FIELD[:ASC|DESC]"),
        (["--where", "{bad"], "invalid JSON"),
        (
            ["--where", '{"type": "eq", "field": "COLOR", "value": 1}'],
            "Invalid argument",
        ),
    ],
)
def test_search_builds_bad_input_is_a_usage_error(stub_foundry_http, args, message):
    result = invoke("builds", "search", *args, "--format", "json")

    assert result.exit_code == 2, result.output
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "usage_error"
    assert message in error["message"]
    assert stub_foundry_http.requests == []


def test_search_builds_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403, json=fj.error("SearchBuildsPermissionDenied", "PERMISSION_DENIED")
    )

    result = invoke("builds", "search", "--status", "RUNNING", "-f", "json")

    assert result.exit_code == 4
    assert json_lines(result.stderr)[-1]["errorName"] == "SearchBuildsPermissionDenied"


# ------------------------------------------------------- builds get-batch


def test_get_builds_batch_accepts_spaces_and_commas(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": {
                fo.BUILD_RID: fo.build(),
                fo.BUILD_RID_2: fo.build(fo.BUILD_RID_2, status="FAILED"),
            }
        }
    )

    result = invoke(
        "builds", "get-batch", f"{fo.BUILD_RID},", fo.BUILD_RID_2, "-f", "csv"
    )

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [(row["RID"], row["Status"]) for row in rows] == [
        (fo.BUILD_RID, "SUCCEEDED"),
        (fo.BUILD_RID_2, "FAILED"),
    ]
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{API}/builds/getBatch")
    assert request_body(request) == [
        {"buildRid": fo.BUILD_RID},
        {"buildRid": fo.BUILD_RID_2},
    ]


def test_get_builds_batch_json_is_the_api_response(stub_foundry_http):
    stub_foundry_http.respond(json={"data": {fo.BUILD_RID: fo.build()}})

    result = invoke("builds", "get-batch", fo.BUILD_RID, "--format", "json")

    assert json.loads(result.stdout) == {
        "data": {fo.BUILD_RID: fo.sdk_json(fo.build())}
    }


@pytest.mark.parametrize(
    "rids, message",
    [([",".join([fo.BUILD_RID] * 101)], "at most 100"), ([",, ,"], "no build RIDs")],
)
def test_get_builds_batch_bad_rid_lists(stub_foundry_http, rids, message):
    result = invoke("builds", "get-batch", *rids, "--format", "json")

    assert result.exit_code == 2
    assert message in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


# -------------------------------------------------------------------- jobs


def test_get_job_table_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=fo.job())

    result = invoke("jobs", "get", fo.JOB_RID)

    assert result.exit_code == 0, result.output
    for expected in (fo.JOB_RID, fo.BUILD_RID, "SUCCEEDED", fo.DATASET_RID):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/jobs/{fo.JOB_RID}"
    assert request.url.params["preview"] == "true"


def test_get_job_json(stub_foundry_http):
    stub_foundry_http.respond(json=fo.job())

    result = invoke("jobs", "get", fo.JOB_RID, "-f", "json")

    assert json.loads(result.stdout) == fo.sdk_json(fo.job())


def test_get_jobs_batch(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": {
                fo.JOB_RID: fo.job(),
                fo.JOB_RID_2: fo.job(fo.JOB_RID_2, jobStatus="FAILED"),
            }
        }
    )

    result = invoke("jobs", "get-batch", f"{fo.JOB_RID},{fo.JOB_RID_2}", "-f", "csv")

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [(row["RID"], row["Status"]) for row in rows] == [
        (fo.JOB_RID, "SUCCEEDED"),
        (fo.JOB_RID_2, "FAILED"),
    ]
    [request] = stub_foundry_http.requests
    assert request.url.params["preview"] == "true"
    assert request_body(request) == [{"jobRid": fo.JOB_RID}, {"jobRid": fo.JOB_RID_2}]


def test_get_jobs_batch_too_many(stub_foundry_http):
    result = invoke("jobs", "get-batch", ",".join([fo.JOB_RID] * 501))

    assert result.exit_code == 2
    assert "at most 500" in result.stderr
    assert stub_foundry_http.requests == []


# --------------------------------------------------------- schedules get


def test_get_schedule_table(stub_foundry_http):
    stub_foundry_http.respond(json=fo.schedule())

    result = invoke("schedules", "get", fo.SCHEDULE_RID)

    assert result.exit_code == 0, result.output
    for expected in (
        fo.SCHEDULE_RID,
        "Nightly build",
        "0 2 * * *",
        fo.DATASET_RID,
        '{"type":"user"}',
        fo.SCHEDULE_VERSION_RID,
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.params["preview"] == "true"


def test_get_schedule_json(stub_foundry_http):
    stub_foundry_http.respond(json=fo.schedule())

    result = invoke("schedules", "get", fo.SCHEDULE_RID, "--format", "json")

    assert json.loads(result.stdout) == fo.sdk_json(fo.schedule())
    assert result.stderr == ""


def test_get_schedule_preview_flag_is_a_deprecated_no_op(stub_foundry_http):
    stub_foundry_http.respond(json=fo.schedule())

    result = invoke("schedules", "get", fo.SCHEDULE_RID, "--preview", "-f", "json")

    assert result.exit_code == 0, result.output
    [warning] = json_lines(result.stderr)
    assert warning["type"] == "warning"
    assert "--preview is deprecated" in warning["message"]
    assert stub_foundry_http.requests[0].url.params["preview"] == "true"


def test_get_schedule_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error("ScheduleNotFound", parameters={"scheduleRid": fo.SCHEDULE_RID}),
    )

    result = invoke("schedules", "get", fo.SCHEDULE_RID, "--format", "json")

    assert result.exit_code == 5
    error = json_lines(result.stderr)[-1]
    assert error["errorName"] == "ScheduleNotFound"
    assert error["parameters"] == {"scheduleRid": fo.SCHEDULE_RID}


# ------------------------------------------------------ schedules create


ACTION = {"target": fo.MANUAL_TARGET, "branchName": "master"}
TRIGGER = {"type": "time", "cronExpression": "0 2 * * *", "timeZone": "UTC"}


def test_create_schedule(stub_foundry_http, tmp_path):
    stub_foundry_http.respond(json=fo.schedule())
    trigger_file = tmp_path / "trigger.json"
    trigger_file.write_text(json.dumps(TRIGGER))

    result = invoke(
        "schedules",
        "create",
        json.dumps(ACTION),
        "--name",
        "Nightly build",
        "--description",
        "Builds the dataset every night",
        "--trigger",
        f"@{trigger_file}",
        "--scope-mode",
        json.dumps({"type": "project", "projectRids": [fo.PROJECT_RID]}),
    )

    assert result.exit_code == 0, result.output
    assert f"Created schedule {fo.SCHEDULE_RID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{API}/schedules")
    assert request.url.params["preview"] == "true"
    assert request_body(request) == {
        "action": ACTION,
        "displayName": "Nightly build",
        "description": "Builds the dataset every night",
        "trigger": TRIGGER,
        "scopeMode": {"type": "project", "projectRids": [fo.PROJECT_RID]},
    }


def test_create_schedule_json(stub_foundry_http):
    stub_foundry_http.respond(json=fo.schedule())

    result = invoke("schedules", "create", json.dumps(ACTION), "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == fo.sdk_json(fo.schedule())
    assert request_body(stub_foundry_http.requests[0]) == {"action": ACTION}


@pytest.mark.parametrize(
    "args",
    [
        ["not-json"],
        [json.dumps(ACTION), "--trigger", "{"],
        [json.dumps(ACTION), "--scope-mode", "["],
    ],
)
def test_create_schedule_invalid_json(stub_foundry_http, args):
    result = invoke("schedules", "create", *args, "-f", "json")

    assert result.exit_code == 2
    assert "invalid JSON" in json_lines(result.stderr)[-1]["message"]
    assert stub_foundry_http.requests == []


# ----------------------------------------------------- schedules replace


def test_replace_schedule_requires_yes_when_not_interactive(stub_foundry_http):
    result = invoke(
        "schedules", "replace", fo.SCHEDULE_RID, json.dumps(ACTION), "-f", "json"
    )

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "confirmation_required"
    assert stub_foundry_http.requests == []


def test_replace_schedule_validates_json_before_asking(stub_foundry_http):
    result = invoke("schedules", "replace", fo.SCHEDULE_RID, "{bad", "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "usage_error"


def test_replace_schedule_with_yes(stub_foundry_http):
    stub_foundry_http.respond(json=fo.schedule(displayName="Renamed"))

    result = invoke(
        "schedules",
        "replace",
        fo.SCHEDULE_RID,
        json.dumps(ACTION),
        "--name",
        "Renamed",
        "--trigger",
        json.dumps(TRIGGER),
        "--yes",
    )

    assert result.exit_code == 0, result.output
    assert f"Replaced schedule {fo.SCHEDULE_RID}" in result.stderr
    assert "Renamed" in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "PUT",
        f"{API}/schedules/{fo.SCHEDULE_RID}",
    )
    assert request.url.params["preview"] == "true"
    assert request_body(request) == {
        "action": ACTION,
        "displayName": "Renamed",
        "trigger": TRIGGER,
    }


def test_replace_schedule_prompts_when_interactive(stub_foundry_http, interactive):
    stub_foundry_http.respond(json=fo.schedule())

    result = invoke(
        "schedules", "replace", fo.SCHEDULE_RID, json.dumps(ACTION), input="yes\n"
    )

    assert result.exit_code == 0, result.output
    assert f"Replace the definition of schedule {fo.SCHEDULE_RID}?" in result.stderr


# ------------------------------------------- schedules delete/pause/unpause


def test_delete_schedule_requires_yes_when_not_interactive(stub_foundry_http):
    result = invoke("schedules", "delete", fo.SCHEDULE_RID)

    assert result.exit_code == 2
    assert "Re-run with --yes" in result.stderr
    assert stub_foundry_http.requests == []


def test_delete_schedule_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("schedules", "delete", fo.SCHEDULE_RID, "-y", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "DELETE",
        f"{API}/schedules/{fo.SCHEDULE_RID}",
    )


def test_delete_schedule_answering_no_aborts(stub_foundry_http, interactive):
    result = invoke("schedules", "delete", fo.SCHEDULE_RID, input="n\n")

    assert result.exit_code == 1
    assert stub_foundry_http.requests == []


@pytest.mark.parametrize("action, past", [("pause", "Paused"), ("unpause", "Unpaused")])
def test_pause_and_unpause(stub_foundry_http, action, past):
    stub_foundry_http.respond(204)

    result = invoke("schedules", action, fo.SCHEDULE_RID)

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"{past} schedule {fo.SCHEDULE_RID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/schedules/{fo.SCHEDULE_RID}/{action}",
    )
    assert "preview" not in request.url.params


# ---------------------------------------------------------- schedules run


def test_run_schedule_shows_the_build(stub_foundry_http):
    stub_foundry_http.respond(json=fo.schedule_run())

    result = invoke("schedules", "run", fo.SCHEDULE_RID)

    assert result.exit_code == 0, result.output
    assert f"started build {fo.BUILD_RID}" in result.stderr
    assert fo.SCHEDULE_RUN_RID in result.stdout
    assert fo.BUILD_RID in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/schedules/{fo.SCHEDULE_RID}/run",
    )


def test_run_schedule_json(stub_foundry_http):
    run = fo.schedule_run(result={"type": "ignored"})
    stub_foundry_http.respond(json=run)

    result = invoke("schedules", "run", fo.SCHEDULE_RID, "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == fo.sdk_json(run)
    assert result.stderr == ""


# --------------------------------------------------------- schedules runs


def test_schedule_runs_table_shows_builds_and_errors(stub_foundry_http):
    error_run = fo.schedule_run(
        "ri.scheduler.main.schedule-run.0e4b0f8d-4444-4000-8000-000000000002",
        result={
            "type": "error",
            "errorName": "PERMISSIONDENIED",
            "description": "Missing permission on the target",
        },
    )
    stub_foundry_http.respond(json={"data": [fo.schedule_run(), error_run]})

    result = invoke("schedules", "runs", fo.SCHEDULE_RID, "--format", "csv")

    assert result.exit_code == 0, result.output
    submitted, failed = list(csv.DictReader(io.StringIO(result.stdout)))
    assert (submitted["Result"], submitted["Build"], submitted["Error"]) == (
        "submitted",
        fo.BUILD_RID,
        "",
    )
    assert (failed["Result"], failed["Build"]) == ("error", "")
    assert failed["Error"] == "PERMISSIONDENIED: Missing permission on the target"


def test_schedule_runs_json_and_page_token(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.schedule_run()], "nextPageToken": "n"})

    result = invoke(
        "schedules", "runs", fo.SCHEDULE_RID, "--page-token", "p", "--format", "json"
    )

    assert json.loads(result.stdout) == {
        "data": [fo.sdk_json(fo.schedule_run())],
        "nextPageToken": "n",
    }
    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {"pageToken": "p"}


def test_schedule_runs_table_hints_at_the_next_page(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.schedule_run()], "nextPageToken": "n"})

    result = invoke("schedules", "runs", fo.SCHEDULE_RID)

    assert result.exit_code == 0
    assert "--page-token n" in result.stderr
