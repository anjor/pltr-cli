"""scripts/smoke.py, the live smoke test: its logic, with a fake runner.

No network: a fake runner stands in for the pltr subprocess. The last test
parses every check's command line against the real CLI, so a check can't
drift from the commands it runs.
"""

import datetime as dt
import io
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import click
import pytest
import typer

from scripts import smoke
from scripts.smoke import FAIL, PASS, SKIP, RunResult

REPO = Path(__file__).resolve().parents[1]
DATASET = "ri.foundry.main.dataset.11111111-1111-4111-8111-111111111111"
SCRATCH = "ri.compass.main.folder.22222222-2222-4222-8222-222222222222"
NOW = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.timezone.utc)

Response = Union[RunResult, Callable[[List[str], Dict[str, Optional[str]]], RunResult]]


def ok(doc: Any, stderr: str = "") -> RunResult:
    return RunResult(0, json.dumps(doc) + "\n", stderr, 0.1)


def api_error(
    exit_code: int, error_type: str, name: Optional[str] = None, status: int = 0
) -> RunResult:
    error: Dict[str, Any] = {
        "type": error_type,
        "message": f"{name or error_type}: something went wrong",
        "exitCode": exit_code,
    }
    if name:
        error["errorName"] = name
    if status:
        error["statusCode"] = status
    return RunResult(exit_code, "", json.dumps(error) + "\n", 0.1)


class FakeRunner:
    """Answers pltr command lines by their longest matching command-path prefix."""

    def __init__(self, routes: Dict[str, Response], default: Optional[Response] = None):
        self.routes = dict(routes)
        self.routes.setdefault("--version", RunResult(0, "pltr 0.16.0\n", "", 0.1))
        self.default = default
        self.calls: List[List[str]] = []
        self.envs: List[Dict[str, Optional[str]]] = []

    def __call__(self, argv: Sequence[str], env, timeout: float) -> RunResult:
        argv = list(argv)
        self.calls.append(argv)
        self.envs.append(dict(env))
        line = " ".join(argv)
        matches = [
            key for key in self.routes if line == key or line.startswith(key + " ")
        ]
        response = self.routes[max(matches, key=len)] if matches else self.default
        if response is None:
            raise AssertionError(f"unexpected command: pltr {line}")
        return response(argv, dict(env)) if callable(response) else response

    def ran(self, prefix: str) -> List[List[str]]:
        return [c for c in self.calls if " ".join(c).startswith(prefix)]


def run_main(args: Sequence[str], runner: FakeRunner):
    out, err = io.StringIO(), io.StringIO()
    code = smoke.main(list(args), runner=runner, stdout=out, stderr=err, now=NOW)
    return code, out.getvalue(), err.getvalue()


def results_by_id(text: str) -> Dict[str, str]:
    """RESULT and DETAILS per check from the text report."""
    found = {}
    for line in text.splitlines():
        match = re.match(
            r"^(PASS|FAIL|SKIP)\s+(\S+)\s+(?:(?:\d+\.\ds|\d+m \d+s)\s+)?(.*)$", line
        )
        if match:
            found[match.group(2)] = f"{match.group(1)} {match.group(3)}".strip()
    return found


@pytest.fixture(autouse=True)
def _no_local_config(monkeypatch, tmp_path):
    """Run from an empty directory, so a developer's ./smoke.toml isn't read."""
    monkeypatch.chdir(tmp_path)


# ------------------------------------------------------------------ config


def test_toml_tables_become_dotted_inputs(tmp_path):
    config = tmp_path / "smoke.toml"
    config.write_text(
        'profile = "dev"\n'
        'pltr = "pltr"\n'
        "[dataset]\n"
        f'rid = "{DATASET}"\n'
        'branch = ""\n'
        "[action]\n"
        'name = "promote"\n'
        'parameters = { employee = "EMP1", level = 3 }\n'
        "[ontology]\n"
        "primary_key = 42\n"
    )
    settings, inputs = smoke.load_config(str(config))
    assert settings == {"profile": "dev", "pltr": "pltr"}
    assert inputs == {
        "dataset.rid": DATASET,  # the empty branch is left out
        "action.name": "promote",
        "action.parameters": '{"employee": "EMP1", "level": 3}',
        "ontology.primary_key": 42,
    }


def test_json_config_has_the_same_structure(tmp_path):
    config = tmp_path / "inputs.json"
    config.write_text(json.dumps({"profile": "dev", "sql": {"table": DATASET}}))
    assert smoke.load_config(str(config)) == (
        {"profile": "dev"},
        {"sql.table": DATASET},
    )


def test_default_config_is_smoke_toml_in_the_working_directory(tmp_path):
    assert smoke.load_config(None) == ({}, {})
    (tmp_path / "smoke.toml").write_text(f'[dataset]\nrid = "{DATASET}"\n')
    assert smoke.load_config(None) == ({}, {"dataset.rid": DATASET})


@pytest.mark.parametrize(
    "content, message",
    [
        ('[dataset]\nrdi = "x"\n', "unknown input dataset.rdi"),
        ('dataset = "x"\n', "must be a table of inputs"),
        ("profile = 3\n", "profile must be a string"),
        ("[dataset\n", "smoke.toml"),  # TOML syntax error
    ],
)
def test_bad_config_is_a_config_error(tmp_path, content, message):
    (tmp_path / "smoke.toml").write_text(content)
    with pytest.raises(smoke.ConfigError, match=re.escape(message)):
        smoke.load_config("smoke.toml")


def test_config_errors_exit_2_before_running_anything():
    runner = FakeRunner({})
    code, out, err = run_main(["--config", "missing.toml"], runner)
    assert code == 2 and "config file missing.toml not found" in err
    assert runner.calls == []


def test_toml_needs_tomllib_or_tomli(tmp_path, monkeypatch):
    (tmp_path / "smoke.toml").write_text("[dataset]\n")
    monkeypatch.setitem(sys.modules, "tomllib", None)
    monkeypatch.setitem(sys.modules, "tomli", None)
    with pytest.raises(smoke.ConfigError, match="use a JSON config"):
        smoke.load_config("smoke.toml")


def test_flags_and_set_override_the_config(tmp_path):
    (tmp_path / "smoke.toml").write_text(
        f'[dataset]\nrid = "from-config"\n[sql]\ntable = "{DATASET}"\n'
    )
    args = smoke.build_parser().parse_args(
        [
            "--dataset-rid",
            "from-flag",
            "--set",
            "sql.table=from-set",
            "--set",
            "orchestration.job_rid=ri.foundry.main.job.1",
            "--scratch-folder",
            SCRATCH,
        ]
    )
    _, inputs = smoke.gather_inputs(args)
    assert inputs["dataset.rid"] == "from-flag"
    assert inputs["sql.table"] == "from-set"
    assert inputs["orchestration.job_rid"] == "ri.foundry.main.job.1"
    assert inputs["writes.scratch_folder"] == SCRATCH


@pytest.mark.parametrize("item", ["nokey", "dataset.rdi=x", "created.folder=x"])
def test_set_takes_known_keys_only(item):
    args = smoke.build_parser().parse_args(["--set", item])
    with pytest.raises(smoke.ConfigError, match="--set"):
        smoke.gather_inputs(args)


def test_example_config_documents_every_input():
    """scripts/smoke.example.toml, uncommented, parses and covers INPUTS."""
    example = REPO / "scripts" / "smoke.example.toml"
    text = re.sub(r"(?m)^# ([a-z_]+ = )", r"\1", example.read_text())
    uncommented = Path("uncommented.toml")
    uncommented.write_text(text)
    settings, inputs = smoke.load_config(str(uncommented))
    assert set(settings) == {"profile", "pltr"}
    assert set(smoke.INPUT_KEYS) <= set(inputs), set(smoke.INPUT_KEYS) - set(inputs)


# ------------------------------------------------------------------ the check table


def test_check_ids_are_unique_and_grouped():
    ids = [check.id for check in smoke.CHECKS]
    assert len(ids) == len(set(ids))
    for check in smoke.CHECKS:
        assert re.fullmatch(r"[a-z-]+(\.[a-z0-9-]+)?", check.id), check.id


def test_every_placeholder_can_get_a_value():
    """Each key is an input, found by a check, derived, or set by the run."""
    run_keys = set(smoke.run_values(Path("/tmp"), NOW))
    for check in smoke.CHECKS:
        for key in check.placeholders():
            assert (
                key in smoke.INPUT_KEYS
                or key in run_keys
                or key in smoke.DERIVED
                or smoke.providers(key)
            ), f"{check.id}: nothing gives {key} a value"


def test_checks_that_find_an_input_run_before_the_checks_that_use_it():
    position = {check.id: i for i, check in enumerate(smoke.CHECKS)}
    for check in smoke.CHECKS:
        for key in check.placeholders():
            for provider in smoke.providers(key):
                assert position[provider.id] < position[check.id], (
                    f"{provider.id} finds {key} but runs after {check.id}"
                )


def test_write_checks_only_act_on_what_the_run_created():
    """Writes never target an existing resource you named or one that was found.

    The scratch folder and the space are only ever parents (--parent-folder,
    --space-rid); the admin replaces are the only exception, and they replace
    objects with their own values, behind --include-admin.
    """
    allowed = re.compile(r"(run|created|before)\..*|sql\.query_id")
    for check in smoke.CHECKS:
        if not check.write:
            continue
        arguments = [k for part in check.argv for k in smoke.PLACEHOLDER.findall(part)]
        assert not check.env, check.id
        for key in arguments:
            if key.startswith("admin.replace_"):
                assert check.admin, check.id
                continue
            if key in ("writes.scratch_folder", "writes.space_rid"):
                option = check.argv[check.argv.index("{" + key + "}") - 1]
                assert option in ("--parent-folder", "--space-rid"), check.id
                continue
            assert allowed.fullmatch(key), f"{check.id} writes with {key}"


def test_nothing_is_ever_permanently_deleted():
    for check in smoke.CHECKS:
        assert "permanently-delete" not in check.argv, check.id
        assert "permanently-delete" not in smoke.command_template(check)


def test_every_resource_the_write_pass_creates_is_trashed_by_a_cleanup_check():
    trashed = {key for c in smoke.CHECKS if c.cleanup for key in c.trashes}
    for key, container in smoke.CREATED_RESOURCES.items():
        assert key in trashed or container in trashed, key
    for check in smoke.CHECKS:
        if check.cleanup:
            assert check.write and check.trashes, check.id


# ------------------------------------------------------------------ skip vs fail


def test_a_check_without_its_input_is_skipped_not_failed():
    runner = FakeRunner({})
    code, out, _ = run_main(["--only", "dataset"], runner)
    found = results_by_id(out)
    assert code == 0
    assert found["dataset.get"] == "SKIP no input: dataset.rid"
    assert all(status.startswith("SKIP") for status in found.values())
    assert runner.calls == [["--version"]]


def test_derived_inputs_say_what_to_set():
    code, out, _ = run_main(["--only", "sql.execute"], FakeRunner({}))
    assert results_by_id(out)["sql.execute"] == (
        "SKIP no input: sql.query (set sql.query or sql.table)"
    )
    assert code == 0


def test_a_failed_check_skips_the_checks_that_need_what_it_finds():
    runner = FakeRunner(
        {"ontology list": api_error(4, "permission_denied", "OntologyListDenied", 403)}
    )
    code, out, _ = run_main(["--only", "ontology"], runner)
    found = results_by_id(out)
    assert code == 1
    assert found["ontology.list"].startswith(
        "FAIL exit 4 (expected 0): permission_denied"
    )
    assert (
        found["ontology.get"] == "SKIP no input: ontology.name (ontology.list failed)"
    )
    assert found["ontology.object-get"] == (
        "SKIP no input: ontology.name (ontology.list failed)"
    )


def test_a_check_that_finds_nothing_is_named_in_the_skip_reason():
    runner = FakeRunner(
        {
            "ontology list": ok({"data": [{"apiName": "ont", "rid": "ri.o"}]}),
            "ontology get": ok({"apiName": "ont", "rid": "ri.o"}),
            "ontology object-type-list": ok({"data": [{"apiName": "Emp"}]}),
            "ontology object-type-get": ok({"apiName": "Emp", "primaryKey": "id"}),
            "ontology object-list": ok({"data": []}),
            "ontology object-aggregate": ok({"data": []}),
            "ontology object-count": ok({"count": 0}),
            "api ontologies": ok({"data": []}),
        }
    )
    code, out, _ = run_main(["--only", "ontology"], runner)
    found = results_by_id(out)
    assert code == 0
    assert found["ontology.object-get"] == (
        "SKIP no input: ontology.primary_key (ontology.object-list found none)"
    )
    assert found["ontology.object-search"] == (
        "SKIP no input: ontology.where (ontology.object-list found none; "
        "set ontology.where or ontology.primary_key)"
    )
    assert found["ontology.object-linked"].startswith(
        "SKIP no input: ontology.primary_key"
    )


def test_captured_values_fill_later_command_lines_and_set_values_win():
    runner = FakeRunner(
        {
            "verify": ok(
                {
                    "authSource": {"kind": "profile", "authType": "token", "host": "h"},
                    "user": {"id": "u-1", "username": "jane", "organization": "ri.org"},
                }
            ),
            "orchestration builds search": ok(
                {"data": [{"rid": "ri.b.found", "createdBy": "u-1"}]}
            ),
        },
        default=ok({}),
    )
    run_main(
        [
            "--only",
            "orchestration.builds-search-mine",
            "orchestration.builds-get",
            "--orchestration-build-rid",
            "ri.b.set",
        ],
        runner,
    )
    assert runner.ran("orchestration builds search --created-by u-1")
    assert runner.ran("orchestration builds get ri.b.set")
    assert not runner.ran("orchestration builds get ri.b.found")


def test_only_pulls_in_the_checks_that_find_inputs():
    checks, _ = smoke.select_checks(
        ["ontology.object-get"], allow_writes=False, include_admin=False, configured={}
    )
    assert [c.id for c in checks] == [
        "ontology.list",
        "ontology.object-type-list",
        "ontology.object-list",
        "ontology.object-get",
    ]
    configured = {"ontology.name": "o", "ontology.object_type": "T"}
    checks, _ = smoke.select_checks(
        ["ontology.object-get"],
        allow_writes=False,
        include_admin=False,
        configured=configured,
    )
    assert [c.id for c in checks] == ["ontology.object-list", "ontology.object-get"]


def test_unknown_only_group_is_a_usage_error():
    code, _, err = run_main(["--only", "datasets"], FakeRunner({}))
    assert code == 2 and "unknown group or check datasets" in err


# ------------------------------------------------------------------ evaluating a run


def evaluate(check_id: str, run: RunResult, **inputs: Any) -> smoke.CheckResult:
    ctx = smoke.Context(
        {k.replace("__", "."): v for k, v in inputs.items()},
        smoke.run_values(Path("/nonexistent"), NOW),
    )
    return smoke.evaluate(smoke.CHECKS_BY_ID[check_id], run, ctx)


def test_failure_detail_has_the_structured_error():
    run = api_error(5, "not_found", "DatasetNotFound", 404)
    result = evaluate("dataset.get", run, dataset__rid=DATASET)
    assert result.status == FAIL
    assert result.detail == (
        "exit 5 (expected 0): not_found DatasetNotFound HTTP 404: "
        "DatasetNotFound: something went wrong"
    )
    assert result.error and result.error["errorName"] == "DatasetNotFound"
    # The errorCode pltr reports is shown too (it is derived for typed errors).
    error = dict(json.loads(run.stderr), errorCode="NOT_FOUND")
    assert smoke.describe_error(error).startswith(
        "not_found DatasetNotFound HTTP 404 NOT_FOUND: "
    )


@pytest.mark.parametrize(
    "run, problem",
    [
        (
            RunResult(0, '{"rid": "x"}\n{"rid": "y"}\n', ""),
            "not exactly one JSON document",
        ),
        (RunResult(0, "", ""), "not exactly one JSON document"),
        (RunResult(0, "Dataset: x\n", ""), "not exactly one JSON document"),
        (RunResult(0, "{}", "Fetching dataset...\n"), "stderr is not JSON Lines"),
        (
            RunResult(
                0, "{}", '{"type": "auth_error", "message": "m", "exitCode": 3}\n'
            ),
            "exit 0 but stderr has an error",
        ),
        (
            RunResult(1, "", "Traceback (most recent call last):\n"),
            "stderr is not a JSON error",
        ),
        (RunResult(1, "", ""), "nothing on stderr"),
    ],
)
def test_contract_violations_fail(run, problem):
    result = evaluate("dataset.get", run, dataset__rid=DATASET)
    assert result.status == FAIL
    assert problem in result.detail


def test_an_expected_failure_passes_with_the_error_noted():
    run = api_error(2, "confirmation_required")
    result = evaluate("contract.needs-yes", run)
    assert result.status == PASS
    assert result.detail.startswith("exit 2: confirmation_required")


@pytest.mark.parametrize(
    "run, problem",
    [
        (
            api_error(2, "usage_error"),
            "error type 'usage_error', expected confirmation_required",
        ),
        (
            RunResult(2, "null\n", api_error(2, "confirmation_required").stderr),
            "stdout is not empty",
        ),
        (
            RunResult(
                2,
                "",
                '{"type": "confirmation_required", "message": "m", "exitCode": 1}\n',
            ),
            "the error's exitCode is 1, the process exited 2",
        ),
        (RunResult(2, "", ""), "no structured error on stderr"),
        (ok(None), "exit 0 (expected 2)"),
    ],
)
def test_an_expected_failure_must_follow_the_error_contract(run, problem):
    result = evaluate("contract.needs-yes", run)
    assert result.status == FAIL
    assert problem in result.detail


def test_unexpected_output_fails_with_what_is_wrong():
    result = evaluate("dataset.get", ok({"rid": "ri.other"}), dataset__rid=DATASET)
    assert result.status == FAIL
    assert (
        result.detail == f"unexpected output: rid is 'ri.other', expected '{DATASET}'"
    )
    result = evaluate("dataset.branches-list", ok([1, 2]), dataset__rid=DATASET)
    assert result.detail == 'unexpected output: the output is not {"data": [...]}'


def test_a_timeout_fails():
    run = RunResult(-1, "", "", 600.0, timed_out=True)
    result = evaluate("dataset.get", run, dataset__rid=DATASET)
    assert result.status == FAIL and "timed out" in result.detail


def test_warnings_and_notes_are_reported():
    warning = '{"type": "warning", "message": "--preview is deprecated"}\n'
    doc = {"data": [{"name": "master"}], "nextPageToken": "t"}
    result = evaluate("dataset.branches-list", ok(doc, warning), dataset__rid=DATASET)
    assert result.status == PASS
    assert result.detail == "1 item, more pages; warning: --preview is deprecated"


def test_csv_output_is_parsed_as_a_table():
    good = RunResult(0, "id,name\n1,a\n2,b\n", "")
    result = evaluate("dataset.read-csv", good, dataset__rid=DATASET)
    assert (result.status, result.detail) == (PASS, "2 rows, 2 columns")
    ragged = RunResult(0, "id,name\n1\n", "")
    assert evaluate("dataset.read-csv", ragged, dataset__rid=DATASET).status == FAIL
    text_error = RunResult(7, "", "Error: Read failed\nHint: retry\n")
    result = evaluate("dataset.read-csv", text_error, dataset__rid=DATASET)
    assert result.detail == "exit 7 (expected 0): Error: Read failed"


def test_object_search_by_primary_key_must_find_the_object():
    inputs = dict(
        ontology__name="o",
        ontology__object_type="T",
        ontology__pk_property="id",
        ontology__primary_key="1",
    )
    found = ok({"data": [{"__primaryKey": "1", "name": "a"}], "totalCount": "1"})
    assert evaluate("ontology.object-search", found, **inputs).detail == (
        "1 object, totalCount 1"
    )
    empty = evaluate("ontology.object-search", ok({"data": []}), **inputs)
    assert empty.status == FAIL and "found nothing" in empty.detail
    # A where clause you set may legitimately match nothing.
    inputs["ontology__where"] = '{"type": "isNull", "field": "x"}'
    assert evaluate("ontology.object-search", ok({"data": []}), **inputs).status == PASS


def test_the_derived_search_keeps_the_primary_keys_json_type():
    ctx = smoke.Context(
        {"ontology.pk_property": "id"}, smoke.run_values(Path("/tmp"), NOW)
    )
    ctx.capture("ontology.primary_key", 42)
    assert json.loads(ctx.get("ontology.where")) == {
        "type": "eq",
        "field": "id",
        "value": 42,
    }
    check = smoke.CHECKS_BY_ID["ontology.object-get"]
    ctx.capture("ontology.name", "o")
    ctx.capture("ontology.object_type", "T")
    assert smoke.command_line(check, ctx, "dev") == [
        "ontology", "object-get", "o", "T", "42", "--format", "json", "--profile", "dev"
    ]  # fmt: skip


def test_auth_checks_bring_their_own_credentials():
    ctx = smoke.Context({}, smoke.run_values(Path("/run"), NOW))
    ctx.capture("auth.host", "foundry.example.com")
    check = smoke.CHECKS_BY_ID["auth.invalid-token"]
    env = smoke.check_env(check, ctx)
    assert env["FOUNDRY_HOST"] == "foundry.example.com"
    assert env["FOUNDRY_TOKEN"] == "pltr-smoke-invalid-token"
    assert env["PLTR_PROFILE"] is None and env["FOUNDRY_CLIENT_ID"] is None
    assert env["XDG_CONFIG_HOME"].startswith("/run/isolated-home")
    assert "--profile" not in smoke.command_line(check, ctx, "dev")
    # Every other check runs with the profile and without PLTR_DEBUG.
    other = smoke.CHECKS_BY_ID["verify"]
    assert smoke.command_line(other, ctx, "dev")[-2:] == ["--profile", "dev"]
    assert smoke.check_env(other, ctx) == {"PLTR_FORMAT": None, "PLTR_DEBUG": None}


# ------------------------------------------------------------------ write-pass guard


def test_allow_writes_needs_a_scratch_folder():
    runner = FakeRunner({})
    code, _, err = run_main(["--allow-writes"], runner)
    assert code == 2 and "--allow-writes needs --scratch-folder" in err
    assert runner.calls == []


@pytest.mark.parametrize(
    "folder", [smoke.ROOT_FOLDER_RID, "ri.foundry.main.dataset.1", "my-folder"]
)
def test_scratch_folder_must_be_a_folder_rid(folder):
    runner = FakeRunner({})
    code, _, err = run_main(["--allow-writes", "--scratch-folder", folder], runner)
    assert code == 2 and "expected a folder or project RID" in err
    assert runner.calls == []


def test_without_allow_writes_no_write_command_runs():
    runner = FakeRunner({}, default=ok({}))
    code, out, _ = run_main(["--scratch-folder", SCRATCH, "--only", "write"], runner)
    assert runner.calls == [["--version"]]
    writes = sum(1 for c in smoke.CHECKS if c.write and not c.admin)
    assert (
        f"Not run: {writes} write checks (--allow-writes --scratch-folder RID)." in out
    )
    assert code == 0


def test_run_checks_refuses_writes_and_admin_checks_that_are_off():
    """Defense in depth: even a hand-made selection can't run them."""
    runner = FakeRunner({}, default=ok({}))
    ctx = smoke.Context({}, smoke.run_values(Path("/tmp"), NOW))
    checks = [smoke.CHECKS_BY_ID["contract.needs-yes"]]
    checks += [
        smoke.CHECKS_BY_ID["write.trash-folder"],
        smoke.CHECKS_BY_ID["admin.user-list"],
    ]
    ctx.capture("created.folder", SCRATCH)
    results, _ = smoke.run_checks(checks, ctx, runner, smoke.Options())
    assert [r.detail for r in results[1:]] == [
        "writes are off (--allow-writes)",
        "admin checks are off (--include-admin)",
    ]
    assert len(runner.calls) == 1


def test_admin_checks_need_include_admin():
    runner = FakeRunner({}, default=ok({"data": []}))
    code, out, _ = run_main(["--only", "admin"], runner)
    admin_reads = sum(1 for c in smoke.CHECKS if c.group == "admin" and not c.write)
    assert f"Not run: {admin_reads} admin checks (--include-admin)." in out
    assert not runner.ran("admin")


# ------------------------------------------------------------------ the write pass


def write_pass_routes(**overrides: Response) -> Dict[str, Response]:
    folder = "ri.compass.main.folder.33333333-3333-4333-8333-333333333333"
    routes: Dict[str, Response] = {
        "folder create": ok(
            {"rid": folder, "displayName": "pltr-smoke-20261107-120000"}
        ),
        "folder get": ok({"rid": folder, "parentFolderRid": SCRATCH}),
        "dataset create": ok({"rid": DATASET}),
        "resource delete": ok(None),
    }
    routes.update(overrides)
    return routes


def test_cleanup_runs_after_a_failure_and_leftovers_are_reported():
    runner = FakeRunner(
        write_pass_routes(
            **{
                "dataset create": api_error(
                    4, "permission_denied", "CreateDenied", 403
                ),
                "resource delete": api_error(7, "server_error", "Internal", 500),
            }
        ),
        default=api_error(5, "not_found", "Missing", 404),
    )
    code, out, _ = run_main(
        ["--allow-writes", "--scratch-folder", SCRATCH, "--only", "write"], runner
    )
    found = results_by_id(out)
    assert code == 1
    assert found["write.files-upload"].startswith("SKIP no input: created.dataset")
    assert found["write.trash-folder"].startswith("FAIL exit 7")
    assert "Left behind (created.folder): ri.compass.main.folder.3333" in out
    deletes = runner.ran("resource delete")
    assert deletes and all("--yes" in call for call in deletes)


def test_ctrl_c_stops_the_run_but_still_cleans_up():
    def interrupt(argv, env):
        raise KeyboardInterrupt

    runner = FakeRunner(
        write_pass_routes(**{"dataset files upload": interrupt}), default=ok(None)
    )
    code, out, _ = run_main(
        ["--allow-writes", "--scratch-folder", SCRATCH, "--only", "write"], runner
    )
    found = results_by_id(out)
    assert code == smoke.EXIT_INTERRUPTED
    assert found["write.files-upload"] == "FAIL interrupted"
    assert found["write.files-list"] == "SKIP interrupted"
    assert found["write.trash-folder"].startswith("PASS")
    assert runner.ran("resource delete ri.compass.main.folder.3333")
    assert "(interrupted)" in out


# ------------------------------------------------------------------ reports


def sample_report() -> smoke.Report:
    def result(check_id, status, detail="", seconds=None, argv=None, error=None):
        return smoke.CheckResult(
            smoke.CHECKS_BY_ID[check_id], status, detail, seconds, argv, error=error
        )

    error = {"type": "not_found", "errorName": "DatasetNotFound", "exitCode": 5}
    return smoke.Report(
        results=[
            result("verify", PASS, "user jane (profile, token)", 1.25),
            result(
                "dataset.get",
                FAIL,
                "exit 5 (expected 0): not_found DatasetNotFound | x",
                2.0,
                ["dataset", "get", DATASET, "--format", "json"],
                error,
            ),
            result(
                "sql.execute", SKIP, "no input: sql.query (set sql.query or sql.table)"
            ),
        ],
        not_run={"write": 3, "admin": 0},
        leftovers=[],
        pltr_version="pltr 0.16.0",
        profile="dev",
        allow_writes=False,
        include_admin=False,
        started=NOW,
        seconds=75.0,
        found={
            "ontology.name": "hr",
            "orchestration.build_rid": "ri.foundry.main.build.1",
        },
    )


def test_text_report():
    text = smoke.render_text(sample_report())
    assert (
        text.splitlines()[0]
        == "pltr smoke test: 1 passed, 1 failed, 1 skipped in 1m 15s"
    )
    assert "pltr 0.16.0 | profile dev | writes off | admin checks off" in text
    assert re.search(r"^PASS\s+verify\s+1\.2s\s+user jane", text, re.M)
    assert re.search(r"^SKIP\s+sql\.execute\s+no input: sql\.query", text, re.M)
    # Failures repeat the real command line and the whole structured error.
    assert f"  dataset.get: pltr dataset get {DATASET} --format json" in text
    assert '"errorName": "DatasetNotFound"' in text
    assert "Not run: 3 write checks (--allow-writes --scratch-folder RID)." in text
    # What the checks found, to compare RID formats or pin a run with --set.
    assert "Found by the checks:\n  ontology.name = hr\n" in text
    assert "  orchestration.build_rid = ri.foundry.main.build.1" in text


def test_markdown_report_is_a_table_without_input_values():
    text = smoke.render_markdown(sample_report())
    lines = text.splitlines()
    assert lines[0] == "### pltr live smoke test"
    assert "**1 passed, 1 failed, 1 skipped in 1m 15s**" in text
    header = lines.index("| Result | Check | Command | Time | Details |")
    assert lines[header + 1] == "|---|---|---|---|---|"
    assert (
        "| **FAIL** | `dataset.get` | `pltr dataset get <dataset.rid> --format json` "
        "| 2.0s | exit 5 (expected 0): not_found DatasetNotFound \\| x |"
    ) in lines
    assert (
        "| skip | `sql.execute` | `pltr sql execute <sql.query> --format json` |  |"
        in text
    )
    assert DATASET not in text and "ri.foundry.main.build.1" not in text
    rows = [line for line in lines if line.startswith("|")]
    assert all(len(re.findall(r"(?<!\\)\|", line)) == 6 for line in rows), rows


def test_main_prints_the_report_on_stdout_and_progress_on_stderr():
    runner = FakeRunner({"verify": api_error(3, "auth_error")})
    code, out, err = run_main(["--only", "verify", "--markdown"], runner)
    assert code == 1
    assert out.startswith("### pltr live smoke test")
    assert "[1/1] FAIL verify" in err and "Running 1 checks with pltr 0.16.0" in err


def test_list_shows_every_check_with_its_command():
    runner = FakeRunner({})
    code, out, _ = run_main(["--list"], runner)
    assert code == 0 and runner.calls == []
    assert len(out.splitlines()) == len(smoke.CHECKS)
    assert "pltr dataset get <dataset.rid> --format json" in out
    code, out, _ = run_main(["--list", "--markdown", "--only", "sql"], runner)
    assert out.splitlines()[0] == "| Check | Kind | Command | Verifies |"
    assert "`sql.submit`" in out and "`dataset.get`" not in out


# ------------------------------------------------------------------ the real CLI


def sample_value(key: str, run: Dict[str, str]) -> str:
    if key in run:
        return run[key]
    if key.endswith(("parameters", "where")):
        return "{}"
    if key == "admin.replace_marking_id" or key.endswith(("user.id", "role_id")):
        return "00000000-0000-4000-8000-000000000003"
    if key.endswith(("rid", "_rid", "folder", "dataset", "project", "dataset_copy")):
        return "ri.foundry.main.dataset.00000000-0000-4000-8000-000000000004"
    return "sample"


def resolve(argv: List[str]):
    """The click command a pltr command line runs, and its own arguments."""
    from pltr.cli import app

    command: click.Command = typer.main.get_command(app)
    ctx = click.Context(command, info_name="pltr")
    args = list(argv)
    # A group that runs itself (pltr verify) takes options, not a subcommand.
    while isinstance(command, click.Group) and args and not args[0].startswith("-"):
        name, sub, args = command.resolve_command(ctx, args)
        assert sub is not None, f"no command {name!r} in {argv}"
        command = sub
        ctx = click.Context(command, info_name=name, parent=ctx)
    return command, ctx, args


@pytest.mark.parametrize("check", smoke.CHECKS, ids=lambda check: check.id)
def test_every_check_parses_against_the_real_cli(check, tmp_path):
    """The command line is accepted as is: commands, options, choices, files."""
    smoke.prepare_files(tmp_path)
    run = smoke.run_values(tmp_path, NOW)
    ctx_values = smoke.Context({}, run)
    for key in check.placeholders():
        if not ctx_values.has(key):
            ctx_values.capture(key, sample_value(key, run))
    argv = smoke.command_line(check, ctx_values, "dev")
    command, ctx, args = resolve(argv)
    command.parse_args(ctx, args)  # raises click.UsageError for a bad command line
    if check.exit_codes == (0,) and "--yes" in {
        opt for p in command.params if isinstance(p, click.Option) for opt in p.opts
    }:
        assert "--yes" in argv, f"{check.id} would stop at the confirmation"


# ------------------------------------------------------------------ the docs


def test_live_verification_doc_names_real_checks_and_counts():
    """docs/development/live-verification.md cites checks that exist."""
    doc = (REPO / "docs" / "development" / "live-verification.md").read_text()
    groups = {check.group for check in smoke.CHECKS}
    ids = set(smoke.CHECKS_BY_ID)
    keys = smoke.known_keys()
    for name in re.findall(r"`([a-z-]+\.[a-z0-9_*-]+)`", doc):
        if name.split(".")[0] not in groups or name in keys:
            continue
        if name.endswith("*"):
            assert any(i.startswith(name[:-1]) for i in ids | keys), name
        else:
            assert name in ids, f"the doc cites {name}, which isn't a check"
    rows = re.findall(r"^\| `([a-z-]+)` \| (\d+) \|", doc, re.M)
    assert rows
    for group, count in rows:
        actual = sum(
            1 for c in smoke.CHECKS if c.group == group and c.kind != "admin write"
        )
        assert int(count) == actual, f"the doc says {group} has {count} checks"
