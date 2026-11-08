"""`--emit-code` prints the SDK code for a command's call instead of making it (#192)."""

import json
from typing import Any, List

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_dataset as dj
from tests.conftest import STUB_HOSTNAME, STUB_TOKEN

pytestmark = pytest.mark.usefixtures("isolated_home")

runner = CliRunner()

DS = dj.DATASET_RID


def emit(*args: str) -> str:
    result = runner.invoke(app, [*args, "--emit-code"])
    assert result.exit_code == 0, result.stderr
    compile(result.stdout, "<emitted>", "exec")
    return result.stdout


def run_snippet(code: str, monkeypatch) -> None:
    monkeypatch.setenv("FOUNDRY_HOST", STUB_HOSTNAME)
    monkeypatch.setenv("FOUNDRY_TOKEN", "snippet-token")
    exec(compile(code, "<emitted>", "exec"), {"__name__": "__main__"})


def same_requests(first: List[Any], second: List[Any]) -> None:
    assert [(r.method, str(r.url), r.content) for r in first] == [
        (r.method, str(r.url), r.content) for r in second
    ]


# ------------------------------------------------------------ activation


def test_nothing_is_called(stub_foundry_http) -> None:
    code = emit("dataset", "get", DS)

    assert stub_foundry_http.requests == []
    assert "client.datasets.Dataset.get(" in code
    assert f'dataset_rid="{DS}"' in code


def test_the_flag_works_anywhere(stub_foundry_http) -> None:
    result = runner.invoke(app, ["--emit-code", "dataset", "get", DS])

    assert result.exit_code == 0, result.stderr
    assert "client.datasets.Dataset.get(" in result.stdout


def test_destructive_commands_neither_ask_nor_run(stub_foundry_http) -> None:
    code = emit("resource", "delete", fj.FOLDER_RID)

    assert "client.filesystem.Resource.delete(" in code
    assert stub_foundry_http.requests == []


def test_no_credentials_in_the_snippet(stub_foundry_http) -> None:
    code = emit("dataset", "get", DS)

    assert STUB_TOKEN not in code
    assert 'os.environ["FOUNDRY_TOKEN"]' in code


# ------------------------------------------------- same request as the command


def test_a_curated_command(stub_foundry_http, monkeypatch) -> None:
    stub_foundry_http.respond_always(json=fj.folder())
    runner.invoke(app, ["folder", "get", fj.FOLDER_RID, "-f", "json"])
    by_command = list(stub_foundry_http.requests)
    stub_foundry_http.requests.clear()

    run_snippet(emit("folder", "get", fj.FOLDER_RID), monkeypatch)

    same_requests(by_command, stub_foundry_http.requests)


def test_a_generated_beta_command(stub_foundry_http, monkeypatch) -> None:
    stub_foundry_http.respond_always(json=fj.folder())
    args = ["api", "filesystem", "folder", "replace", fj.FOLDER_RID]
    args += ["--display-name", "New", "--parent-folder-rid", fj.PARENT_RID]
    runner.invoke(app, [*args, "--yes", "-f", "json"])
    by_command = list(stub_foundry_http.requests)
    stub_foundry_http.requests.clear()

    code = emit(*args)
    run_snippet(code, monkeypatch)

    assert "preview=True" in code
    same_requests(by_command, stub_foundry_http.requests)


def test_a_paged_generated_command(stub_foundry_http, monkeypatch) -> None:
    from tests import foundry_json_admin as aj

    stub_foundry_http.respond_always(json={"data": [aj.user()]})
    runner.invoke(
        app, ["api", "admin", "user", "list", "--page-size", "5", "-f", "json"]
    )
    by_command = list(stub_foundry_http.requests)
    stub_foundry_http.requests.clear()

    code = emit("api", "admin", "user", "list", "--page-size", "5")
    run_snippet(code, monkeypatch)

    assert "for item in client.admin.User.list(" in code
    same_requests(by_command, stub_foundry_http.requests)


def test_a_json_body_becomes_models(stub_foundry_http, monkeypatch) -> None:
    from tests import foundry_json_ontology as oj

    stub_foundry_http.respond_always(json={"data": [], "totalCount": "0"})
    where = json.dumps({"type": "eq", "field": "fullName", "value": "Ada"})
    args = ["api", "ontologies", "ontology-object", "search", oj.ONTOLOGY, "Employee"]
    args += ["--where", where]
    runner.invoke(app, [*args, "-f", "json"])
    by_command = list(stub_foundry_http.requests)
    stub_foundry_http.requests.clear()

    code = emit(*args)
    run_snippet(code, monkeypatch)

    assert "ontologies_models.EqualsQueryV2(" in code
    same_requests(by_command, stub_foundry_http.requests)


def test_a_binary_command_writes_the_output_file(stub_foundry_http) -> None:
    code = emit(
        "api",
        "datasets",
        "dataset",
        "file",
        "content",
        DS,
        "data/a.csv",
        "--output",
        "a.csv",
    )

    assert 'with open("a.csv", "wb") as file:' in code


def test_a_path_is_looked_up_in_the_snippet(stub_foundry_http, monkeypatch) -> None:
    code = emit("dataset", "get", "/Space/Project/sales")

    assert stub_foundry_http.requests == []
    assert "client.filesystem.Resource.get_by_path(" in code
    assert "dataset_rid=dataset_rid" in code
    stub_foundry_http.respond(
        json={
            **fj.resource(DS, "sales", "FOUNDRY_DATASET"),
            "path": "/Space/Project/sales",
        }
    )
    stub_foundry_http.respond(
        json={"rid": DS, "name": "sales", "parentFolderRid": fj.PARENT_RID}
    )
    run_snippet(code, monkeypatch)
    assert [r.url.path for r in stub_foundry_http.requests] == [
        "/api/v2/filesystem/resources/getByPath",
        f"/api/v2/datasets/{DS}",
    ]


# ------------------------------------------------------------ unsupported


def unsupported(*args: str) -> dict:
    result = runner.invoke(app, [*args, "--emit-code", "--format", "json"])
    assert result.exit_code == 2, result.stdout
    assert result.stdout == ""
    return json.loads(result.stderr.strip().splitlines()[-1])


def test_a_command_with_several_calls_says_so(stub_foundry_http) -> None:
    error = unsupported("cp", DS, fj.FOLDER_RID)

    assert error["type"] == "emit_code_unsupported"
    assert "several" in error["message"]
    assert stub_foundry_http.requests == []


def test_a_local_command_says_so(stub_foundry_http) -> None:
    error = unsupported("alias", "list")

    assert error["type"] == "emit_code_unsupported"
    assert "no Foundry call" in error["message"]


# ------------------------------------------------- every command (#192)

from tests.test_contract.test_cli_contract import (  # noqa: E402
    ENTRIES,
    ROOT,
    contract_args,
    contract_env,  # noqa: F401  (fixture)
    option_names,
)


@pytest.mark.parametrize("path", sorted(ENTRIES))
def test_every_command_handles_emit_code(path, contract_env, tmp_path) -> None:  # noqa: F811
    from click.testing import CliRunner as ClickRunner

    args = contract_args(path, tmp_path)
    if "--format" not in option_names(ENTRIES[path].command):
        index = args.index("--format")
        del args[index : index + 2]
    result = ClickRunner().invoke(
        ROOT, [*args, "--emit-code"], env={"PLTR_FORMAT": "json"}
    )

    assert contract_env.requests == [], f"pltr {path} called Foundry"
    assert STUB_TOKEN not in result.stdout
    if result.exit_code == 0:
        compile(result.stdout, f"pltr {path}", "exec")
        assert "client = FoundryClient(" in result.stdout
        return
    lines = result.stderr.strip().splitlines()
    error = json.loads(lines[-1]) if lines else {}
    assert (result.exit_code, error.get("type")) == (2, "emit_code_unsupported"), (
        f"pltr {path}: exit {result.exit_code}: {result.stderr[-500:]}"
    )


def test_root_help_mentions_emit_code() -> None:
    result = runner.invoke(app, ["--help"])

    assert "--emit-code" in result.stdout


# ------------------------------------------------------ review fixes (#192)

CONNECTION = "ri.magritte..source.c1"


def test_secrets_from_a_file_are_not_inlined(stub_foundry_http, tmp_path) -> None:
    secrets = tmp_path / "secrets.json"
    secrets.write_text('{"password": "hunter2-SUPER-SECRET"}')

    code = emit(
        "connectivity",
        "connection",
        "update-secrets",
        CONNECTION,
        "--secrets-file",
        str(secrets),
    )

    assert "hunter2" not in code
    assert 'secrets=json.loads(os.environ["SECRETS"])' in code
    assert "import json" in code


def test_generated_secret_arguments_are_not_inlined(stub_foundry_http) -> None:
    code = emit(
        "api",
        "connectivity",
        "connection",
        "update-secrets",
        CONNECTION,
        "--secrets",
        '{"password": "hunter2"}',
    )

    assert "hunter2" not in code


def test_resource_search_is_refused(stub_foundry_http) -> None:
    error = unsupported("resource", "search", "sales", "--folder-rid", fj.FOLDER_RID)

    assert "search" in error["message"]


def test_a_local_filter_is_noted_in_the_snippet(stub_foundry_http) -> None:
    code = emit(
        "resource", "list", "--folder-rid", fj.FOLDER_RID, "--type", "FOUNDRY_DATASET"
    )

    assert code.startswith("# ")
    assert "--type" in code.splitlines()[0]


def test_extra_model_fields_are_kept(stub_foundry_http, monkeypatch) -> None:
    from tests import foundry_json_ontology as oj

    stub_foundry_http.respond_always(json={"data": [], "totalCount": "0"})
    where = {"type": "eq", "field": "fullName", "value": "Ada", "fuzzy": True}
    args = ["api", "ontologies", "ontology-object", "search", oj.ONTOLOGY, "Employee"]
    args += ["--where", json.dumps(where)]
    runner.invoke(app, [*args, "-f", "json"])
    by_command = list(stub_foundry_http.requests)
    stub_foundry_http.requests.clear()

    run_snippet(emit(*args), monkeypatch)

    same_requests(by_command, stub_foundry_http.requests)


def test_a_page_token_starts_a_response_paged_loop(
    stub_foundry_http, monkeypatch
) -> None:
    from tests import foundry_json_admin as aj

    stub_foundry_http.respond_always(json={"data": [aj.user()]})
    args = ["admin", "user", "search", "jane", "--page-token", "TOKEN123"]
    runner.invoke(app, [*args, "-f", "json"])
    by_command = list(stub_foundry_http.requests)
    stub_foundry_http.requests.clear()

    run_snippet(emit(*args), monkeypatch)

    same_requests(by_command, stub_foundry_http.requests)


def test_paths_in_a_batch_get_are_refused_cleanly(stub_foundry_http) -> None:
    error = unsupported("resource", "batch-get", fj.FOLDER_RID, "/Space/Project/x")

    assert error["type"] == "emit_code_unsupported"
    assert "path" in error["message"]


def test_an_output_path_argument_is_used(stub_foundry_http) -> None:
    code = emit(
        "media-sets",
        "thumbnail-retrieve",
        "ri.mio.main.media-set.m1",
        "ri.mio.main.media-item.i1",
        "thumb.webp",
    )

    assert 'with open("thumb.webp", "wb") as file:' in code


def test_a_paged_snippet_says_it_reads_every_page(stub_foundry_http) -> None:
    code = emit("api", "admin", "user", "list")

    assert "every page" in code.splitlines()[0]


def test_a_binary_snippet_writes_what_the_command_writes(
    stub_foundry_http, monkeypatch, tmp_path
) -> None:
    stub_foundry_http.respond_always(content=b"a,b\n1,2\n")
    by_command_file = tmp_path / "by-command.csv"
    args = ["api", "datasets", "dataset", "file", "content", DS, "data/a.csv"]
    runner.invoke(app, [*args, "--output", str(by_command_file)])
    by_command = list(stub_foundry_http.requests)
    stub_foundry_http.requests.clear()
    by_snippet_file = tmp_path / "by-snippet.csv"

    run_snippet(emit(*args, "--output", str(by_snippet_file)), monkeypatch)

    same_requests(by_command, stub_foundry_http.requests)
    assert by_snippet_file.read_bytes() == by_command_file.read_bytes()
