"""Tests for OrchestrationService against a real FoundryClient (only HTTP is faked).

Build.search, Job.get, Job.get_batch, Schedule.get, Schedule.create and
Schedule.replace are beta: their requests must carry preview=true. The other
methods are GA: passing preview= would make the SDK emit a UserWarning, which
the module-level filter turns into a failure.
"""

import json

import pydantic
import pytest
from foundry_sdk.v2.orchestration.models import (
    Build,
    GetBuildsBatchResponse,
    GetJobsBatchResponse,
    Job,
    Schedule,
    ScheduleRun,
    SearchBuildsResponse,
)

from pltr.services.orchestration import OrchestrationService
from tests import foundry_json_orchestration as fo

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

API = "/api/v2/orchestration"


def body(request):
    return json.loads(request.content)


# ------------------------------------------------------------------ builds


def test_get_build_is_ga(stub_foundry_http):
    stub_foundry_http.respond(json=fo.build())

    build = OrchestrationService().get_build(fo.BUILD_RID)

    assert isinstance(build, Build)
    assert (build.status, build.job_rids) == ("SUCCEEDED", [fo.JOB_RID])
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", f"{API}/builds/{fo.BUILD_RID}")
    assert "preview" not in request.url.params


def test_create_build_sends_explicit_fields(stub_foundry_http):
    stub_foundry_http.respond(json=fo.build(status="RUNNING", finishedTime=None))

    build = OrchestrationService().create_build(
        target=fo.MANUAL_TARGET,
        fallback_branches=["develop"],
        branch_name="master",
        force_build=True,
        abort_on_failure=False,
        notifications_enabled=True,
        retry_count=2,
    )

    assert build.status == "RUNNING"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{API}/builds/create")
    assert "preview" not in request.url.params
    assert body(request) == {
        "target": fo.MANUAL_TARGET,
        "fallbackBranches": ["develop"],
        "branchName": "master",
        "forceBuild": True,
        "abortOnFailure": False,
        "notificationsEnabled": True,
        "retryCount": 2,
    }


def test_create_build_leaves_out_unset_options(stub_foundry_http):
    stub_foundry_http.respond(json=fo.build())

    OrchestrationService().create_build(target=fo.MANUAL_TARGET, fallback_branches=[])

    assert body(stub_foundry_http.requests[0]) == {
        "target": fo.MANUAL_TARGET,
        "fallbackBranches": [],
    }


def test_create_build_rejects_an_invalid_target_before_sending(stub_foundry_http):
    with pytest.raises(pydantic.ValidationError):
        OrchestrationService().create_build(
            target={"type": "manual"}, fallback_branches=[]
        )
    assert stub_foundry_http.requests == []


def test_cancel_build(stub_foundry_http):
    stub_foundry_http.respond(204)

    assert OrchestrationService().cancel_build(fo.BUILD_RID) is None

    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/builds/{fo.BUILD_RID}/cancel",
    )


def test_get_build_jobs_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.job()], "nextPageToken": "t2"})

    page = OrchestrationService().get_build_jobs(
        fo.BUILD_RID, page_size=5, page_token="t1"
    )

    assert [job.rid for job in page.data] == [fo.JOB_RID]
    assert page.next_page_token == "t2"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/builds/{fo.BUILD_RID}/jobs",
    )
    assert dict(request.url.params) == {"pageSize": "5", "pageToken": "t1"}


def test_search_builds_is_beta_and_sends_the_filter(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.build()], "nextPageToken": "next"})
    where = {"type": "eq", "field": "STATUS", "value": "FAILED"}
    order_by = {"fields": [{"field": "STARTED_TIME", "direction": "DESC"}]}

    response = OrchestrationService().search_builds(
        where=where, order_by=order_by, page_size=10, page_token="tok"
    )

    assert isinstance(response, SearchBuildsResponse)
    assert [build.rid for build in response.data] == [fo.BUILD_RID]
    assert response.next_page_token == "next"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{API}/builds/search")
    assert dict(request.url.params) == {"preview": "true"}
    assert body(request) == {
        "where": where,
        "orderBy": order_by,
        "pageSize": 10,
        "pageToken": "tok",
    }


def test_search_builds_rejects_an_invalid_filter_before_sending(stub_foundry_http):
    with pytest.raises(pydantic.ValidationError):
        OrchestrationService().search_builds(
            where={"type": "eq", "field": "NOT_A_FIELD", "value": "x"}
        )
    assert stub_foundry_http.requests == []


def test_get_builds_batch_sends_build_rid_elements(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": {
                fo.BUILD_RID: fo.build(),
                fo.BUILD_RID_2: fo.build(fo.BUILD_RID_2, status="FAILED"),
            }
        }
    )

    response = OrchestrationService().get_builds_batch([fo.BUILD_RID, fo.BUILD_RID_2])

    assert isinstance(response, GetBuildsBatchResponse)
    assert response.data[fo.BUILD_RID_2].status == "FAILED"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{API}/builds/getBatch")
    assert "preview" not in request.url.params
    assert body(request) == [{"buildRid": fo.BUILD_RID}, {"buildRid": fo.BUILD_RID_2}]


def test_get_builds_batch_limit(stub_foundry_http):
    with pytest.raises(ValueError, match="Maximum batch size is 100 builds"):
        OrchestrationService().get_builds_batch([fo.BUILD_RID] * 101)
    assert stub_foundry_http.requests == []


# -------------------------------------------------------------------- jobs


def test_get_job_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=fo.job())

    job = OrchestrationService().get_job(fo.JOB_RID)

    assert isinstance(job, Job)
    assert job.job_status == "SUCCEEDED"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", f"{API}/jobs/{fo.JOB_RID}")
    assert request.url.params["preview"] == "true"


def test_get_jobs_batch_is_beta_and_sends_job_rid_elements(stub_foundry_http):
    stub_foundry_http.respond(json={"data": {fo.JOB_RID: fo.job()}})

    response = OrchestrationService().get_jobs_batch([fo.JOB_RID])

    assert isinstance(response, GetJobsBatchResponse)
    assert list(response.data) == [fo.JOB_RID]
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{API}/jobs/getBatch")
    assert request.url.params["preview"] == "true"
    assert body(request) == [{"jobRid": fo.JOB_RID}]


def test_get_jobs_batch_limit(stub_foundry_http):
    with pytest.raises(ValueError, match="Maximum batch size is 500 jobs"):
        OrchestrationService().get_jobs_batch([fo.JOB_RID] * 501)
    assert stub_foundry_http.requests == []


# --------------------------------------------------------------- schedules


def test_get_schedule_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=fo.schedule())

    schedule = OrchestrationService().get_schedule(fo.SCHEDULE_RID)

    assert isinstance(schedule, Schedule)
    assert schedule.action.branch_name == "master"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/schedules/{fo.SCHEDULE_RID}",
    )
    assert request.url.params["preview"] == "true"


def test_create_schedule_is_beta_and_sends_explicit_fields(stub_foundry_http):
    stub_foundry_http.respond(json=fo.schedule())
    action = {"target": fo.MANUAL_TARGET, "branchName": "master"}
    trigger = {"type": "time", "cronExpression": "0 2 * * *", "timeZone": "UTC"}
    scope = {"type": "project", "projectRids": [fo.PROJECT_RID]}

    schedule = OrchestrationService().create_schedule(
        action=action,
        display_name="Nightly build",
        description="Builds the dataset every night",
        trigger=trigger,
        scope_mode=scope,
    )

    assert schedule.rid == fo.SCHEDULE_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{API}/schedules")
    assert request.url.params["preview"] == "true"
    assert body(request) == {
        "action": action,
        "displayName": "Nightly build",
        "description": "Builds the dataset every night",
        "trigger": trigger,
        "scopeMode": scope,
    }


def test_create_schedule_with_only_an_action(stub_foundry_http):
    stub_foundry_http.respond(json=fo.schedule())

    OrchestrationService().create_schedule(action={"target": fo.MANUAL_TARGET})

    assert body(stub_foundry_http.requests[0]) == {
        "action": {"target": fo.MANUAL_TARGET}
    }


def test_replace_schedule_is_beta_and_a_put(stub_foundry_http):
    stub_foundry_http.respond(json=fo.schedule(displayName="Renamed"))
    action = {"target": fo.MANUAL_TARGET}

    schedule = OrchestrationService().replace_schedule(
        fo.SCHEDULE_RID, action=action, display_name="Renamed"
    )

    assert schedule.display_name == "Renamed"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "PUT",
        f"{API}/schedules/{fo.SCHEDULE_RID}",
    )
    assert request.url.params["preview"] == "true"
    assert body(request) == {"action": action, "displayName": "Renamed"}


@pytest.mark.parametrize(
    "method, http_method, suffix",
    [
        ("delete_schedule", "DELETE", ""),
        ("pause_schedule", "POST", "/pause"),
        ("unpause_schedule", "POST", "/unpause"),
    ],
)
def test_ga_schedule_actions(stub_foundry_http, method, http_method, suffix):
    stub_foundry_http.respond(204)

    assert getattr(OrchestrationService(), method)(fo.SCHEDULE_RID) is None

    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        http_method,
        f"{API}/schedules/{fo.SCHEDULE_RID}{suffix}",
    )
    assert "preview" not in request.url.params


def test_run_schedule_returns_the_run(stub_foundry_http):
    stub_foundry_http.respond(json=fo.schedule_run())

    run = OrchestrationService().run_schedule(fo.SCHEDULE_RID)

    assert isinstance(run, ScheduleRun)
    assert run.result is not None and run.result.type == "submitted"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{API}/schedules/{fo.SCHEDULE_RID}/run",
    )
    assert "preview" not in request.url.params


def test_get_schedule_runs_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.schedule_run()]})

    page = OrchestrationService().get_schedule_runs(fo.SCHEDULE_RID, page_size=20)

    assert [run.rid for run in page.data] == [fo.SCHEDULE_RUN_RID]
    assert page.next_page_token is None
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/schedules/{fo.SCHEDULE_RID}/runs",
    )
    assert dict(request.url.params) == {"pageSize": "20"}
