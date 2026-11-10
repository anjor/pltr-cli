"""`pltr osdk generate`: an OSDK package from the pltr profile (#220).

Node.js and npm are faked (tests/osdk_fakes.py) except in the helper test at
the end, which runs pltr's real helper script with Node against a fake
generator package.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

import httpx
import pytest
from typer.testing import CliRunner

from pltr.cli import app
from pltr.services import osdk
from tests import foundry_json_ontology as oj
from tests.osdk_fakes import FakeNode, generated_package_json, generator_log

pytestmark = pytest.mark.usefixtures("isolated_home")

runner = CliRunner()

TOKEN = "s3cr3t-osdk-token-value"


@pytest.fixture
def secret_token(stub_foundry_http) -> str:
    """The stub's credentials, with a token no test argument can contain."""
    import pltr.services.base as base

    base.AuthManager.return_value.get_auth_context.return_value.get_token = (
        lambda: TOKEN
    )
    return TOKEN


@pytest.fixture
def fake_node(monkeypatch) -> FakeNode:
    return FakeNode().apply(monkeypatch)


@pytest.fixture
def app_dir(tmp_path, monkeypatch) -> Path:
    """Run from an app's root, as an agent would."""
    root = tmp_path / "orders-app"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def generate(*args: str, format: str = "json") -> Any:
    return runner.invoke(
        app, ["osdk", "generate", *args, "--format", format], catch_exceptions=False
    )


def last_error(result: Any) -> Dict[str, Any]:
    return json.loads(result.stderr.strip().splitlines()[-1])


BASIC = ("--ontology", oj.ONTOLOGY_RID, "--object-type", "Employee", "--out", "osdk")


# ------------------------------------------------------------------ success


def test_generates_a_package_and_says_how_to_use_it(
    stub_foundry_http, secret_token, fake_node, app_dir
):
    stub_foundry_http.respond(json=oj.ontology())

    result = generate(
        *BASIC,
        "--object-type",
        "Department",
        "--action-type",
        "promote-employee",
        "--package-name",
        "@orders/sdk",
    )

    assert result.exit_code == 0, result.stderr
    package_dir = app_dir / "osdk" / "@orders" / "sdk"
    assert json.loads(result.stdout) == {
        "packageName": "@orders/sdk",
        "packageVersion": "0.0.1",
        "packagePath": str(package_dir),
        "dependency": {"@orders/sdk": "file:./osdk/@orders/sdk"},
        "ontologyRid": oj.ONTOLOGY_RID,
        "objectTypes": ["Employee", "Department"],
        "actionTypes": ["promote-employee"],
        "generator": "@osdk/foundry-sdk-generator@2.87.0",
        "peerDependencies": {"@osdk/client": "2.87.0"},
        "reactDependencies": {"@osdk/oauth": "1.14.0", "@osdk/react": "2.87.0"},
        "overrides": {"@osdk/api": "2.87.0"},
        "notes": [
            "Add the dependency, peerDependencies (and reactDependencies for a "
            'React app) to the app\'s package.json "dependencies", then run '
            "npm install. The file: path is relative to the current directory.",
            'Add "overrides": {"@osdk/api": "2.87.0"} to the app\'s '
            "package.json: @osdk/react 2.87.0 pulls in a newer @osdk/api than "
            "@osdk/client 2.87.0 uses, and type checking then fails with TS2322.",
            "To change the types later, run the command again with --replace: "
            "the new package replaces this one once it is generated.",
        ],
    }
    (request,) = stub_foundry_http.requests
    assert request.method == "GET"
    assert request.url.path == f"/api/v2/ontologies/{oj.ONTOLOGY_RID}"
    (call,) = fake_node.generations
    assert f"--ontology={oj.ONTOLOGY_RID}" in call.args
    assert f"--outputDir={app_dir / 'osdk'}{os.sep}.pltr-osdk-" in " ".join(call.args)
    assert "--foundryHostname=https://test.palantirfoundry.com" in call.args
    assert (package_dir / "package.json").is_file()


def test_an_ontology_api_name_is_resolved_to_its_rid(
    stub_foundry_http, secret_token, fake_node, app_dir
):
    stub_foundry_http.respond(json=oj.ontology(api_name="hr"))

    result = generate("--ontology", "hr", "--object-type", "Employee", "--out", "osdk")

    assert result.exit_code == 0, result.stderr
    (request,) = stub_foundry_http.requests
    assert request.url.path == "/api/v2/ontologies/hr"
    (call,) = fake_node.generations
    assert f"--ontology={oj.ONTOLOGY_RID}" in call.args
    assert json.loads(result.stdout)["ontologyRid"] == oj.ONTOLOGY_RID


def test_the_token_is_never_on_a_command_line_or_in_the_output(
    stub_foundry_http, secret_token, fake_node, app_dir
):
    stub_foundry_http.respond(json=oj.ontology())

    result = generate(*BASIC)

    assert result.exit_code == 0, result.stderr
    assert [c.args[1] for c in fake_node.calls] == [
        "--version",
        "--version",
        "ci",
        str(osdk.HELPER),
    ]
    for call in fake_node.calls:
        assert all(TOKEN not in arg for arg in call.args), call.args
        assert all("authToken" not in arg for arg in call.args), call.args
    (generation,) = fake_node.generations
    assert generation.env is not None
    assert generation.env[osdk.TOKEN_ENV_VAR] == TOKEN
    (install,) = fake_node.installs
    assert install.env is not None
    assert all(TOKEN not in value for value in install.env.values())
    assert TOKEN not in result.stdout + result.stderr


def test_the_hostname_is_normalised_to_https(
    isolated_home, fake_node, app_dir, monkeypatch
):
    """With the real auth layer: a host given with a scheme and a slash."""
    monkeypatch.setenv("FOUNDRY_HOST", "https://stack.example.com/")
    monkeypatch.setenv("FOUNDRY_TOKEN", TOKEN)
    sent = []

    def send(self, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json=oj.ontology(), request=request)

    monkeypatch.setattr(httpx.Client, "send", send)

    result = generate(*BASIC)

    assert result.exit_code == 0, result.stderr
    assert [str(r.url.host) for r in sent] == ["stack.example.com"]
    (call,) = fake_node.generations
    assert "--foundryHostname=https://stack.example.com" in call.args
    assert call.env is not None and call.env[osdk.TOKEN_ENV_VAR] == TOKEN


def test_every_kind_of_type_is_passed_through(
    stub_foundry_http, secret_token, fake_node, app_dir
):
    stub_foundry_http.respond(json=oj.ontology())

    result = generate(
        *BASIC,
        "--object-type",
        "Department",
        "--link-type",
        "Employee.department",
        "--action-type",
        "promote-employee",
        "--query-type",
        "employeeStats:1.0.0",
        "--interface-type",
        "Person",
        "--package-version",
        "1.2.3-beta.1",
    )

    assert result.exit_code == 0, result.stderr
    (call,) = fake_node.generations
    start = call.args.index("--packageVersion=1.2.3-beta.1")
    assert call.args[start + 1].startswith(f"--outputDir={app_dir / 'osdk'}")
    assert call.args[start + 2 :] == [
        "--objectTypes=Employee",
        "--objectTypes=Department",
        "--actionTypes=promote-employee",
        "--queryTypes=employeeStats:1.0.0",
        "--linkTypes=Employee.department",
        "--interfaceTypes=Person",
    ]
    document = json.loads(result.stdout)
    assert document["linkTypes"] == ["Employee.department"]
    assert document["queryTypes"] == ["employeeStats:1.0.0"]
    assert document["interfaceTypes"] == ["Person"]


def test_a_package_outside_the_current_directory_gets_a_relative_path(
    stub_foundry_http, secret_token, fake_node, app_dir, tmp_path
):
    stub_foundry_http.respond(json=oj.ontology())

    result = generate(
        "--ontology",
        oj.ONTOLOGY_RID,
        "--object-type",
        "Employee",
        "--out",
        str(tmp_path / "shared" / "osdk"),
    )

    assert result.exit_code == 0, result.stderr
    document = json.loads(result.stdout)
    assert document["dependency"] == {"@app/sdk": "file:../shared/osdk/@app/sdk"}
    assert document["packagePath"] == str(tmp_path / "shared" / "osdk" / "@app" / "sdk")


def test_table_output_shows_the_dependency_line(
    stub_foundry_http, secret_token, fake_node, app_dir
):
    stub_foundry_http.respond(json=oj.ontology())

    result = generate(*BASIC, format="table")

    assert result.exit_code == 0, result.stderr
    assert '"@app/sdk": "file:./osdk/@app/sdk"' in result.stdout
    assert "@osdk/client" in result.stdout
    assert "Generated @app/sdk" in result.stderr


# -------------------------------------------------------------- node + npm


def test_missing_node_fails_before_any_call(stub_foundry_http, monkeypatch, app_dir):
    FakeNode(node_version=None).apply(monkeypatch)

    result = generate(*BASIC)

    assert result.exit_code == 2
    assert result.stdout == ""
    error = last_error(result)
    assert error["type"] == "missing_dependency"
    assert error["exitCode"] == 2
    assert error["parameters"] == {"tool": "node", "required": ">=18.0.0"}
    assert "Node.js 18" in error["hint"]
    assert stub_foundry_http.requests == []


def test_old_node_fails_with_the_version_found(stub_foundry_http, monkeypatch, app_dir):
    FakeNode(node_version="v16.20.2").apply(monkeypatch)

    result = generate(*BASIC)

    assert result.exit_code == 2
    error = last_error(result)
    assert error["type"] == "missing_dependency"
    assert error["parameters"]["found"] == "16.20.2"
    assert stub_foundry_http.requests == []


def test_old_node_in_text_mode_prints_a_hint(stub_foundry_http, monkeypatch, app_dir):
    FakeNode(node_version="v16.20.2").apply(monkeypatch)

    result = generate(*BASIC, format="table")

    assert result.exit_code == 2
    assert "Node.js 16.20.2 is too old" in result.stderr
    assert "Hint:" in result.stderr


# ------------------------------------------------------------------ failure


def test_a_generator_failure_exits_8_with_its_errors(
    stub_foundry_http, secret_token, monkeypatch, app_dir
):
    FakeNode(
        generate_returncode=1,
        generate_stdout=generator_log(
            "ERROR",
            "Unable to find the following object types",
            unsafe_params={"objectTypeApiNames": ["Employe"]},
        ),
    ).apply(monkeypatch)
    stub_foundry_http.respond(json=oj.ontology())

    result = generate("--ontology", "hr", "--object-type", "Employe", "--out", "osdk")

    assert result.exit_code == 8
    assert result.stdout == ""
    error = last_error(result)
    assert error["type"] == "work_failed"
    assert "Employe" in error["message"]
    assert error["parameters"]["step"] == "generate"
    assert "pltr context ontology" in error["hint"]
    assert error["suggestedCommand"] == f"pltr context ontology {oj.ONTOLOGY_RID}"


def test_other_generator_failures_get_no_api_name_advice(
    stub_foundry_http, secret_token, monkeypatch, app_dir
):
    FakeNode(
        generate_returncode=1,
        generate_stdout=generator_log(
            "ERROR", "Failed generating bundles", stacktrace="Error: rollup crashed"
        ),
    ).apply(monkeypatch)
    stub_foundry_http.respond(json=oj.ontology())

    result = generate(*BASIC)

    assert result.exit_code == 8
    error = last_error(result)
    assert "rollup crashed" in error["message"]
    assert "hint" not in error
    assert "suggestedCommand" not in error


def test_an_unknown_ontology_is_not_found(stub_foundry_http, fake_node, app_dir):
    stub_foundry_http.respond(
        404,
        json={
            "errorCode": "NOT_FOUND",
            "errorName": "OntologyNotFound",
            "errorInstanceId": "00000000-0000-4000-8000-000000000001",
            "parameters": {"ontologyRid": "nope"},
        },
    )

    result = generate(
        "--ontology", "nope", "--object-type", "Employee", "--out", "osdk"
    )

    assert result.exit_code == 5
    assert last_error(result)["errorName"] == "OntologyNotFound"
    assert fake_node.installs == [] and fake_node.generations == []


# ------------------------------------------------------------- usage errors


@pytest.mark.parametrize(
    "args, message",
    [
        (["--ontology", "hr", "--out", "osdk"], "--object-type"),
        ([*BASIC, "--package-name", "My SDK"], "npm package name"),
        ([*BASIC, "--package-name", "@App/sdk"], "npm package name"),
        ([*BASIC, "--package-name", "@app/s~dk"], "npm package name"),
        ([*BASIC, "--package-version", "1.0"], "semver"),
        # The generator's own semver check rejects a leading zero.
        ([*BASIC, "--package-version", "1.2.3-01"], "semver"),
        ([*BASIC, "--link-type", "department"], "ObjectType.linkType"),
        ([*BASIC, "--link-type", "Department.employees"], "--object-type Department"),
        (["--ontology", "hr", "--object-type", "", "--out", "osdk"], "API name"),
        (["--ontology", "hr", "--object-type", "A,B", "--out", "osdk"], "repeat"),
        ([*BASIC, "--action-type", "promote employee"], "API name"),
    ],
)
def test_bad_options_are_usage_errors(
    args, message, stub_foundry_http, fake_node, app_dir
):
    result = generate(*args)

    assert result.exit_code == 2, result.stderr
    error = last_error(result)
    assert error["type"] == "usage_error"
    assert message in error["message"]
    assert stub_foundry_http.requests == []
    assert fake_node.calls == []


def test_out_must_not_be_a_file(stub_foundry_http, fake_node, app_dir):
    (app_dir / "osdk").write_text("not a directory")

    result = generate(*BASIC)

    assert result.exit_code == 2
    assert "not a directory" in last_error(result)["message"]


def _old_package(app_dir: Path) -> Path:
    package = app_dir / "osdk" / "@app" / "sdk"
    package.mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps(generated_package_json("@app/sdk"))
    )
    (package / "stale.js").write_text("// from the last generation")
    return package


def test_an_existing_package_needs_replace(stub_foundry_http, fake_node, app_dir):
    old = _old_package(app_dir)

    result = generate(*BASIC)

    assert result.exit_code == 2
    error = last_error(result)
    assert error["type"] == "usage_error"
    assert "--replace" in error["message"]
    assert stub_foundry_http.requests == [] and fake_node.calls == []
    assert (old / "stale.js").exists()


def test_replace_regenerates_an_existing_package(
    stub_foundry_http, secret_token, fake_node, app_dir
):
    old = _old_package(app_dir)
    stub_foundry_http.respond(json=oj.ontology())

    result = generate(*BASIC, "--replace")

    assert result.exit_code == 0, result.stderr
    assert not (old / "stale.js").exists()
    assert json.loads((old / "package.json").read_text())["version"] == "0.0.1"
    assert [p.name for p in (app_dir / "osdk").iterdir()] == ["@app"]


def test_replace_never_deletes_a_directory_it_did_not_generate(
    stub_foundry_http, fake_node, app_dir
):
    """--out .. with the app's own name would point at the app itself."""
    (app_dir / "package.json").write_text(
        json.dumps({"name": "orders-app", "dependencies": {"@osdk/client": "2.87.0"}})
    )

    result = generate(
        "--ontology",
        "hr",
        "--object-type",
        "Employee",
        "--out",
        "..",
        "--package-name",
        "orders-app",
        "--replace",
    )

    assert result.exit_code == 2
    assert "not an OSDK package" in last_error(result)["message"]
    assert (app_dir / "package.json").exists()
    assert fake_node.calls == []


def test_emit_code_is_unsupported(stub_foundry_http, fake_node, app_dir):
    result = runner.invoke(
        app, ["osdk", "generate", *BASIC, "--emit-code", "--format", "json"]
    )

    assert result.exit_code == 2
    assert last_error(result)["type"] == "emit_code_unsupported"
    assert stub_foundry_http.requests == []
    assert fake_node.calls == []


# -------------------------------------------------- the real helper script

FAKE_GENERATOR = """
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export async function cli(args) {
  const option = (name) =>
    args.find((a) => a.startsWith(`--${name}=`)).slice(name.length + 3);
  const out = join(option("outputDir"), option("packageName"));
  mkdirSync(out, { recursive: true });
  writeFileSync(join(out, "package.json"), JSON.stringify({ name: option("packageName") }));
  writeFileSync(
    process.env.FAKE_GENERATOR_RECORD,
    JSON.stringify({
      args,
      argv: process.argv,
      tokenInEnv: process.env.PLTR_OSDK_TOKEN ?? null,
    }),
  );
}
"""


def _real_node() -> Any:
    try:
        return osdk.find_node_tools()
    except Exception:
        return None


@pytest.mark.skipif(
    shutil.which("node") is None or _real_node() is None,
    reason="needs Node.js 18+ and npm",
)
def test_the_helper_hands_the_token_to_the_generator_in_memory(tmp_path, monkeypatch):
    """pltr's real helper, run by Node, against a fake generator package."""
    install_dir = tmp_path / "install"
    package = install_dir / "node_modules" / "@osdk" / "foundry-sdk-generator"
    package.mkdir(parents=True)
    (install_dir / "package.json").write_text("{}")
    (package / "package.json").write_text(
        json.dumps(
            {
                "name": "@osdk/foundry-sdk-generator",
                "version": "2.87.0",
                "type": "module",
                "exports": {".": {"import": "./index.js", "default": "./index.js"}},
            }
        )
    )
    (package / "index.js").write_text(FAKE_GENERATOR)
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_GENERATOR_RECORD", str(record))
    seen = []
    real_run = subprocess.run

    def spy(args, **kwargs):
        seen.append(list(args))
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)

    package_dir = osdk.generate(
        osdk.find_node_tools(),
        install_dir,
        foundry_url="https://stack.example.com",
        token=TOKEN,
        ontology_rid="ri.ontology.main.ontology.0b1c",
        package_name="@app/sdk",
        package_version="0.0.1",
        out_dir=tmp_path / "osdk",
        object_types=["Employee"],
        action_types=[],
        query_types=[],
        link_types=[],
        interface_types=[],
    )

    assert package_dir == tmp_path / "osdk" / "@app" / "sdk"
    recorded = json.loads(record.read_text())
    # The generator got the token, last, as --authToken=...
    assert recorded["args"][-1] == f"--authToken={TOKEN}"
    assert recorded["args"][2:4] == [
        "generatePackage",
        "--foundryHostname=https://stack.example.com",
    ]
    # ...but no process had it on its command line, and the variable is gone.
    assert all(TOKEN not in arg for arg in recorded["argv"])
    assert all(TOKEN not in arg for args in seen for arg in args)
    assert recorded["tokenInEnv"] is None
    assert TOKEN not in os.environ.get(osdk.TOKEN_ENV_VAR, "")


@pytest.mark.skipif(
    shutil.which("node") is None or _real_node() is None,
    reason="needs Node.js 18+ and npm",
)
def test_the_helper_refuses_a_token_on_its_command_line(tmp_path):
    result = subprocess.run(
        [
            shutil.which("node") or "node",
            str(osdk.HELPER),
            str(tmp_path),
            "generatePackage",
            "--authToken=x",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, osdk.TOKEN_ENV_VAR: "x"},
    )

    assert result.returncode == 2
    assert "PLTR_OSDK_TOKEN" in result.stderr
