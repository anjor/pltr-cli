"""Builds from Compass paths: `builds create --dataset`, and paths inside
the JSON of orchestration and data-health commands (#218)."""

import json
from typing import Any, Dict, List

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_data_health as dh
from tests import foundry_json_orchestration as fo
from tests.conftest import STUB_HOSTNAME

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()

DS = fo.DATASET_RID
DS_2 = "ri.foundry.main.dataset.0f5c1a9e-5555-4000-8000-000000000002"
SALES = "/Space/Project/sales"
ORDERS = "/Space/Project/orders"
GET_BY_PATH = "/api/v2/filesystem/resources/getByPath"
GET_BY_PATH_BATCH = "/api/v2/filesystem/resources/getByPathBatch"
CREATE = "/api/v2/orchestration/builds/create"


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)


def dataset(rid: str, name: str) -> Dict[str, Any]:
    """A dataset ``Resource`` at /Space/Project/<name>."""
    return fj.resource(rid, name, "FOUNDRY_DATASET")


def run(*args: str) -> Any:
    return runner.invoke(app, ["orchestration", "builds", "create", *args])


def run_json(*args: str) -> Any:
    return run(*args, "--format", "json")


def error_of(result: Any) -> Dict[str, Any]:
    assert result.stdout == ""
    return json.loads(result.stderr.strip().splitlines()[-1])


def paths(stub) -> List[str]:
    return [request.url.path for request in stub.requests]


def body(request: Any) -> Dict[str, Any]:
    return json.loads(request.content)


# ------------------------------------------------------- builds create --dataset


def test_dataset_rid_means_a_manual_target(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=fo.build())

    result = run_json("--dataset", DS, "--branch", "master", "--force")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == fo.sdk_json(fo.build())
    [request] = stub_foundry_http.requests
    assert request.url.path == CREATE
    assert body(request) == {
        "target": {"type": "manual", "targetRids": [DS]},
        "fallbackBranches": [],
        "branchName": "master",
        "forceBuild": True,
        "abortOnFailure": False,
        "notificationsEnabled": True,
    }


def test_dataset_paths_and_rids_keep_their_order(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=dataset(DS, "sales"))
    stub_foundry_http.respond(json=fo.build())

    result = run_json("--dataset", SALES, "--dataset", DS_2)

    assert result.exit_code == 0, result.stderr
    assert paths(stub_foundry_http) == [GET_BY_PATH, CREATE]
    assert body(stub_foundry_http.requests[1])["target"] == {
        "type": "manual",
        "targetRids": [DS, DS_2],
    }


def test_several_dataset_paths_are_one_lookup(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json={"data": [dataset(DS, "sales"), dataset(DS_2, "orders")]}
    )
    stub_foundry_http.respond(json=fo.build())

    result = run_json("--dataset", SALES, "--dataset", ORDERS)

    assert result.exit_code == 0, result.stderr
    assert paths(stub_foundry_http) == [GET_BY_PATH_BATCH, CREATE]
    assert body(stub_foundry_http.requests[1])["target"]["targetRids"] == [DS, DS_2]


def test_dataset_path_with_wait(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=dataset(DS, "sales"))
    stub_foundry_http.respond(json=fo.build(status="RUNNING", finishedTime=None))
    stub_foundry_http.respond(json=fo.build(status="SUCCEEDED"))

    result = run_json("--dataset", SALES, "--branch", "master", "--wait")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "SUCCEEDED"
    assert paths(stub_foundry_http) == [
        GET_BY_PATH,
        CREATE,
        f"/api/v2/orchestration/builds/{fo.BUILD_RID}",
    ]


def test_text_mode_reports_the_resolved_path(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=dataset(DS, "sales"))
    stub_foundry_http.respond(json=fo.build())

    result = run("--dataset", SALES)

    assert result.exit_code == 0, result.stderr
    assert f"Resolved '{SALES}' to {DS} (FOUNDRY_DATASET)" in result.stderr


def test_a_missing_dataset_path_is_path_not_found(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        404, json=fj.error("PathNotFound", parameters={"path": SALES})
    )

    result = run_json("--dataset", SALES)

    assert result.exit_code == 5
    error = error_of(result)
    assert error["type"] == "path_not_found"
    assert error["parameters"] == {"path": SALES}
    assert paths(stub_foundry_http) == [GET_BY_PATH]


def test_a_folder_given_as_a_dataset_is_refused(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=fj.resource(fj.FOLDER_RID, "sales"))

    result = run_json("--dataset", SALES)

    assert result.exit_code == 2
    error = error_of(result)
    assert error["type"] == "wrong_resource_type"
    assert "--dataset" in error["message"]
    assert paths(stub_foundry_http) == [GET_BY_PATH]


def test_target_and_dataset_together_are_a_usage_error(stub_foundry_http) -> None:
    result = run_json(json.dumps(fo.MANUAL_TARGET), "--dataset", SALES)

    assert result.exit_code == 2
    error = error_of(result)
    assert error["type"] == "usage_error"
    assert "TARGET" in error["message"] and "--dataset" in error["message"]
    assert stub_foundry_http.requests == []  # not even the path lookup


def test_dataset_before_target_is_the_same_usage_error(stub_foundry_http) -> None:
    result = run_json("--dataset", SALES, json.dumps(fo.MANUAL_TARGET))

    assert result.exit_code == 2
    assert error_of(result)["type"] == "usage_error"
    assert stub_foundry_http.requests == []


def test_neither_target_nor_dataset_is_a_usage_error(stub_foundry_http) -> None:
    result = run_json("--branch", "master")

    assert result.exit_code == 2
    error = error_of(result)
    assert error["type"] == "usage_error"
    assert "TARGET" in error["message"] and "--dataset" in error["message"]
    assert stub_foundry_http.requests == []


def test_neither_in_text_mode_is_click_usage_error(stub_foundry_http) -> None:
    result = run()

    assert result.exit_code == 2
    assert "--dataset" in result.stderr
    assert stub_foundry_http.requests == []


@pytest.mark.parametrize("value", [SALES, DS])
def test_a_bare_rid_or_path_as_target_points_at_dataset(
    stub_foundry_http, value: str
) -> None:
    result = run_json(value, "--branch", "master")

    assert result.exit_code == 2
    error = error_of(result)
    assert error["type"] == "usage_error"
    assert "--dataset" in error["message"]
    assert stub_foundry_http.requests == []


def test_help_shows_both_forms() -> None:
    result = run("--help")

    assert result.exit_code == 0
    assert "--dataset" in result.stdout
    assert "Compass path" in result.stdout


# --------------------------------------------- builds create: paths in TARGET


def test_a_path_in_target_rids_is_resolved(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=dataset(DS, "sales"))
    stub_foundry_http.respond(json=fo.build())
    target = {"type": "manual", "targetRids": [SALES]}

    result = run_json(json.dumps(target), "--branch", "master")

    assert result.exit_code == 0, result.stderr
    assert paths(stub_foundry_http) == [GET_BY_PATH, CREATE]
    assert body(stub_foundry_http.requests[1])["target"] == {
        "type": "manual",
        "targetRids": [DS],
    }


def test_paths_in_a_connecting_target(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json={"data": [dataset(DS, "sales"), dataset(DS_2, "orders")]}
    )
    stub_foundry_http.respond(json=fo.build())
    target = {
        "type": "connecting",
        "inputRids": [SALES],
        "targetRids": [ORDERS],
        "ignoredRids": [],
    }

    result = run_json(json.dumps(target))

    assert result.exit_code == 0, result.stderr
    assert paths(stub_foundry_http) == [GET_BY_PATH_BATCH, CREATE]
    assert body(stub_foundry_http.requests[1])["target"] == {
        "type": "connecting",
        "inputRids": [DS],
        "targetRids": [DS_2],
        "ignoredRids": [],
    }


def test_a_path_in_ignored_rids_of_an_upstream_target(
    stub_foundry_http, tmp_path
) -> None:
    stub_foundry_http.respond(json=dataset(DS_2, "orders"))
    stub_foundry_http.respond(json=fo.build())
    target_file = tmp_path / "target.json"
    target_file.write_text(
        json.dumps({"type": "upstream", "targetRids": [DS], "ignoredRids": [ORDERS]})
    )

    result = run_json(f"@{target_file}")

    assert result.exit_code == 0, result.stderr
    assert body(stub_foundry_http.requests[1])["target"] == {
        "type": "upstream",
        "targetRids": [DS],
        "ignoredRids": [DS_2],
    }


def test_a_missing_path_in_target_starts_no_build(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        404, json=fj.error("PathNotFound", parameters={"path": SALES})
    )
    target = {"type": "manual", "targetRids": [SALES]}

    result = run_json(json.dumps(target))

    assert result.exit_code == 5
    error = error_of(result)
    assert error["type"] == "path_not_found"
    assert error["parameters"] == {"path": SALES}
    assert paths(stub_foundry_http) == [GET_BY_PATH]


def test_a_target_of_rids_makes_no_lookup(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=fo.build())

    result = run_json(json.dumps(fo.MANUAL_TARGET))

    assert result.exit_code == 0, result.stderr
    assert paths(stub_foundry_http) == [CREATE]


# ------------------------------------------------------------- --emit-code


def emit(*args: str) -> str:
    result = runner.invoke(
        app, ["orchestration", "builds", "create", *args, "--emit-code"]
    )
    assert result.exit_code == 0, result.stderr
    compile(result.stdout, "<emitted>", "exec")
    return result.stdout


def run_snippet(code: str, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_HOST", STUB_HOSTNAME)
    monkeypatch.setenv("FOUNDRY_TOKEN", "snippet-token")
    exec(compile(code, "<emitted>", "exec"), {"__name__": "__main__"})


@pytest.mark.parametrize(
    "args",
    [
        ["--dataset", SALES],
        [json.dumps({"type": "manual", "targetRids": [SALES]})],
    ],
    ids=["dataset-option", "target-json"],
)
def test_emit_code_looks_the_path_up(stub_foundry_http, monkeypatch, args) -> None:
    code = emit(*args, "--branch", "master")

    assert stub_foundry_http.requests == []
    assert "client.filesystem.Resource.get_by_path(" in code
    assert f'"{SALES}"' in code
    stub_foundry_http.respond(json=dataset(DS, "sales"))
    stub_foundry_http.respond(json=fo.build())
    run_snippet(code, monkeypatch)
    assert paths(stub_foundry_http) == [GET_BY_PATH, CREATE]
    assert body(stub_foundry_http.requests[1])["target"] == {
        "type": "manual",
        "targetRids": [DS],
    }


# --------------------------------------------------------------- schedules


SCHEDULES = "/api/v2/orchestration/schedules"


def test_schedule_create_resolves_paths_in_action_trigger_and_scope(
    stub_foundry_http,
) -> None:
    project = fj.resource(fj.PROJECT_RID, "Project")
    project["path"] = "/Space/Project"
    stub_foundry_http.respond(json=dataset(DS, "sales"))  # ACTION
    stub_foundry_http.respond(json=dataset(DS_2, "orders"))  # --trigger
    stub_foundry_http.respond(json=project)  # --scope-mode
    stub_foundry_http.respond(json=fo.schedule())

    result = runner.invoke(
        app,
        [
            "orchestration",
            "schedules",
            "create",
            json.dumps({"target": {"type": "manual", "targetRids": [SALES]}}),
            "--trigger",
            json.dumps(
                {"type": "datasetUpdated", "datasetRid": ORDERS, "branchName": "master"}
            ),
            "--scope-mode",
            json.dumps({"type": "project", "projectRids": ["/Space/Project"]}),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert paths(stub_foundry_http) == [
        GET_BY_PATH,
        GET_BY_PATH,
        GET_BY_PATH,
        SCHEDULES,
    ]
    sent = body(stub_foundry_http.requests[-1])
    assert sent["action"]["target"]["targetRids"] == [DS]
    assert sent["trigger"]["datasetRid"] == DS_2
    assert sent["scopeMode"]["projectRids"] == [fj.PROJECT_RID]


def test_schedule_scope_refuses_a_folder_that_is_not_a_project(
    stub_foundry_http,
) -> None:
    stub_foundry_http.respond(json=fj.resource(fj.FOLDER_RID, "sub"))

    result = runner.invoke(
        app,
        [
            "orchestration",
            "schedules",
            "create",
            json.dumps({"target": fo.MANUAL_TARGET}),
            "--scope-mode",
            json.dumps({"type": "project", "projectRids": ["/Space/Project/sub"]}),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 2
    error = error_of(result)
    assert error["type"] == "wrong_resource_type"
    assert "projectRids in --scope-mode" in error["message"]
    assert paths(stub_foundry_http) == [GET_BY_PATH]


def test_schedule_replace_resolves_a_path_in_action(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=dataset(DS, "sales"))
    stub_foundry_http.respond(json=fo.schedule())

    result = runner.invoke(
        app,
        [
            "orchestration",
            "schedules",
            "replace",
            fo.SCHEDULE_RID,
            json.dumps({"target": {"type": "manual", "targetRids": [SALES]}}),
            "--yes",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stderr
    sent = body(stub_foundry_http.requests[-1])
    assert sent["action"]["target"]["targetRids"] == [DS]


# ------------------------------------------------------------- data health


def test_data_health_check_create_resolves_the_subject_path(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=dataset(dh.DATASET_RID, "sales"))
    stub_foundry_http.respond(json=dh.check())
    config = dict(
        dh.BUILD_STATUS_CONFIG, subject={"datasetRid": SALES, "branchId": "master"}
    )

    result = runner.invoke(
        app,
        ["data-health", "check", "create", json.dumps(config), "--format", "json"],
    )

    assert result.exit_code == 0, result.stderr
    assert paths(stub_foundry_http)[0] == GET_BY_PATH
    sent = body(stub_foundry_http.requests[-1])
    assert sent["config"]["subject"] == {
        "datasetRid": dh.DATASET_RID,
        "branchId": "master",
    }
