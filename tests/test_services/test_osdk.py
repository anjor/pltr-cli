"""`pltr osdk generate`'s Node.js side, with the subprocesses faked (#220).

The token must reach the generator only through the helper's environment:
never on a command line (anyone can list processes), never in npm's
environment, never in an error message.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from pltr.contract import ExitCode, PltrError
from pltr.services import osdk
from tests.osdk_fakes import (
    NODE,
    NPM,
    FakeNode,
    generated_package_json,
    generator_log,
)

TOKEN = "s3cr3t-osdk-token-value"
FOUNDRY_URL = "https://stack.example.com"
ONTOLOGY_RID = "ri.ontology.main.ontology.0b1c"


@pytest.fixture
def fake_node(monkeypatch) -> FakeNode:
    return FakeNode().apply(monkeypatch)


def _option(call, name: str) -> str:
    """The value of ``--name=value`` in a recorded call."""
    (value,) = [a.split("=", 1)[1] for a in call.args if a.startswith(f"--{name}=")]
    return value


def _existing_package(out_dir: Path, name: str = "@app/sdk") -> Path:
    """A package the generator made earlier, with a file the new one lacks."""
    package = out_dir / name
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps(generated_package_json(name)))
    (package / "stale.js").write_text("// from the last generation")
    return package


def _generate(tools, install_dir, out_dir, **overrides):
    kwargs = dict(
        foundry_url=FOUNDRY_URL,
        token=TOKEN,
        ontology_rid=ONTOLOGY_RID,
        package_name="@app/sdk",
        package_version="0.0.1",
        out_dir=out_dir,
        object_types=["Employee", "Department"],
        action_types=["promote-employee"],
        query_types=["employeeStats"],
        link_types=["Employee.department"],
        interface_types=[],
    )
    kwargs.update(overrides)
    return osdk.generate(tools, install_dir, **kwargs)


# ------------------------------------------------------------------ pinning


def test_the_generator_is_pinned_to_the_version_proven_end_to_end():
    assert osdk.GENERATOR_PACKAGE == "@osdk/foundry-sdk-generator"
    assert osdk.GENERATOR_VERSION == "2.87.0"
    assert osdk.GENERATOR_SPEC == "@osdk/foundry-sdk-generator@2.87.0"


def test_the_helper_ships_with_pltr_and_reads_the_token_variable():
    helper = osdk.HELPER.read_text(encoding="utf-8")
    assert osdk.HELPER.name == "osdk_generate.mjs"
    assert f'"{osdk.TOKEN_ENV_VAR}"' in helper
    # It deletes the variable before the generator runs, and refuses a token
    # given on its own command line.
    assert "delete process.env[TOKEN_ENV_VAR]" in helper
    assert "--authToken" in helper


# --------------------------------------------------------------- node + npm


def test_find_node_tools_reports_the_versions(fake_node):
    tools = osdk.find_node_tools()

    assert (tools.node, tools.npm) == (NODE, NPM)
    assert (tools.node_version, tools.npm_version) == ("26.13.0", "11.6.2")


def test_missing_node_is_a_missing_dependency(monkeypatch):
    FakeNode(node_version=None).apply(monkeypatch)

    with pytest.raises(PltrError) as caught:
        osdk.find_node_tools()

    error = caught.value
    assert error.error_type == "missing_dependency"
    assert error.exit_code == ExitCode.USAGE
    assert error.parameters == {"tool": "node", "required": ">=18.0.0"}
    assert "Node.js 18" in (error.hint or "")


def test_old_node_is_a_missing_dependency(monkeypatch):
    FakeNode(node_version="v16.20.2").apply(monkeypatch)

    with pytest.raises(PltrError) as caught:
        osdk.find_node_tools()

    error = caught.value
    assert error.error_type == "missing_dependency"
    assert error.parameters == {
        "tool": "node",
        "required": ">=18.0.0",
        "found": "16.20.2",
    }
    assert "16.20.2" in error.message


def test_missing_npm_is_a_missing_dependency(monkeypatch):
    FakeNode(npm_version=None).apply(monkeypatch)

    with pytest.raises(PltrError) as caught:
        osdk.find_node_tools()

    assert caught.value.error_type == "missing_dependency"
    assert caught.value.parameters == {"tool": "npm", "required": ">=8.0.0"}


def test_old_npm_is_a_missing_dependency(monkeypatch):
    FakeNode(npm_version="6.14.18").apply(monkeypatch)

    with pytest.raises(PltrError) as caught:
        osdk.find_node_tools()

    assert caught.value.parameters == {
        "tool": "npm",
        "required": ">=8.0.0",
        "found": "6.14.18",
    }


def test_a_node_that_does_not_run_is_a_missing_dependency(monkeypatch):
    fake = FakeNode().apply(monkeypatch)

    def broken(args, **kwargs):
        fake.calls.append(args)
        raise OSError("Exec format error")

    monkeypatch.setattr(subprocess, "run", broken)

    with pytest.raises(PltrError) as caught:
        osdk.find_node_tools()

    assert caught.value.error_type == "missing_dependency"
    assert "Exec format error" in caught.value.message


# ------------------------------------------------------------------ install


def test_ensure_generator_installs_the_pinned_version_once(fake_node, monkeypatch):
    monkeypatch.setenv("FOUNDRY_TOKEN", TOKEN)
    tools = osdk.find_node_tools()

    install_dir = osdk.ensure_generator(tools)
    again = osdk.ensure_generator(tools)

    assert install_dir == again == osdk.generator_dir()
    assert install_dir == Path.home() / ".cache" / "pltr" / "osdk-generator" / "2.87.0"
    manifest = install_dir / "node_modules" / "@osdk" / "foundry-sdk-generator"
    assert json.loads((manifest / "package.json").read_text())["version"] == "2.87.0"
    (install,) = fake_node.installs
    # npm ci installs exactly the tree in the lockfile pltr ships, without
    # running install scripts.
    assert install.args[:2] == [NPM, "ci"]
    assert "--ignore-scripts" in install.args
    shipped = osdk.HELPER.parent / "osdk_generator"
    assert install.files == {
        "package.json": (shipped / "package.json").read_text(encoding="utf-8"),
        "package-lock.json": (shipped / "package-lock.json").read_text(
            encoding="utf-8"
        ),
    }
    # npm never gets a Foundry credential, in argv or in its environment.
    assert install.env is not None
    assert osdk.TOKEN_ENV_VAR not in install.env
    assert "FOUNDRY_TOKEN" not in install.env
    assert all(TOKEN not in value for value in install.env.values())
    assert all(TOKEN not in arg for arg in install.args)
    # It installed into a staging directory and moved it into place.
    assert install.cwd != str(install_dir)
    assert not [p for p in install_dir.parent.iterdir() if p.name != "2.87.0"]


def test_the_shipped_lockfile_pins_the_generator_and_every_dependency():
    """Bump GENERATOR_VERSION and the lockfile together (see the module docstring)."""
    shipped = osdk.HELPER.parent / "osdk_generator"
    manifest = json.loads((shipped / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((shipped / "package-lock.json").read_text(encoding="utf-8"))

    assert manifest["dependencies"] == {osdk.GENERATOR_PACKAGE: osdk.GENERATOR_VERSION}
    packages = lock["packages"]
    assert packages[""]["dependencies"] == manifest["dependencies"]
    generator = packages[f"node_modules/{osdk.GENERATOR_PACKAGE}"]
    assert generator["version"] == osdk.GENERATOR_VERSION
    for name, package in packages.items():
        if not name:
            continue
        assert package.get("integrity", "").startswith("sha512-"), name
        assert package["resolved"].startswith("https://registry.npmjs.org/"), name
        # Install scripts never run (--ignore-scripts); only optional,
        # platform-specific packages may have one.
        assert not package.get("hasInstallScript") or package.get("optional"), name


@pytest.mark.parametrize("stale", ["another version", "another lockfile", "no marker"])
def test_an_install_that_does_not_match_the_lockfile_is_replaced(stale, fake_node):
    tools = osdk.find_node_tools()
    target = osdk.ensure_generator(tools)
    manifest = (
        target / "node_modules" / "@osdk" / "foundry-sdk-generator" / "package.json"
    )
    marker = target / ".pltr-installed"
    if stale == "another version":
        manifest.write_text(json.dumps({"version": "2.80.0"}))
    elif stale == "another lockfile":
        marker.write_text("0" * 64)
    else:
        marker.unlink()
    assert not osdk.generator_installed()

    osdk.ensure_generator(tools)

    assert len(fake_node.installs) == 2
    assert osdk.generator_installed()
    assert json.loads(manifest.read_text())["version"] == "2.87.0"


def test_an_install_another_pltr_finished_first_is_used(fake_node, monkeypatch):
    tools = osdk.find_node_tools()
    real_replace = os.replace

    def racing_replace(src, dst):
        if Path(dst) == osdk.generator_dir():
            # Another pltr moved its install into place a moment earlier.
            real_replace(src, Path(str(dst)))
            raise OSError(66, "Directory not empty", str(dst))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", racing_replace)

    assert osdk.ensure_generator(tools) == osdk.generator_dir()
    assert osdk.generator_installed()


def test_a_failed_install_is_work_failed_and_leaves_nothing(monkeypatch):
    fake = FakeNode(
        install_returncode=1,
        install_stderr="npm error code ENOTFOUND\nnpm error network request failed\n",
    ).apply(monkeypatch)

    with pytest.raises(PltrError) as caught:
        osdk.ensure_generator(osdk.find_node_tools())

    error = caught.value
    assert error.error_type == "work_failed"
    assert error.exit_code == ExitCode.FAILED
    assert "ENOTFOUND" in error.message
    assert error.parameters["step"] == "install"
    assert error.parameters["exitCode"] == 1
    assert len(fake.installs) == 1
    assert not osdk.generator_dir().parent.exists() or not list(
        osdk.generator_dir().parent.iterdir()
    )


# ----------------------------------------------------------------- generate


def test_generate_passes_the_token_only_in_the_helpers_environment(fake_node, tmp_path):
    tools = osdk.find_node_tools()
    install_dir = osdk.ensure_generator(tools)

    package_dir = _generate(tools, install_dir, tmp_path / "osdk")

    assert package_dir == tmp_path / "osdk" / "@app" / "sdk"
    assert (package_dir / "package.json").is_file()
    (call,) = fake_node.generations
    assert call.args[:4] == [
        NODE,
        str(osdk.HELPER),
        str(install_dir),
        "generatePackage",
    ]
    # The generator writes into a staging directory inside --out, which is
    # moved into place and removed.
    staging = Path(_option(call, "outputDir"))
    assert staging.parent == tmp_path / "osdk"
    assert staging.name.startswith(".pltr-osdk-")
    assert [p.name for p in (tmp_path / "osdk").iterdir()] == ["@app"]
    assert call.args[4:] == [
        f"--foundryHostname={FOUNDRY_URL}",
        f"--ontology={ONTOLOGY_RID}",
        "--packageName=@app/sdk",
        "--packageVersion=0.0.1",
        f"--outputDir={staging}",
        "--objectTypes=Employee",
        "--objectTypes=Department",
        "--actionTypes=promote-employee",
        "--queryTypes=employeeStats",
        "--linkTypes=Employee.department",
    ]
    for each in fake_node.calls:
        assert all(TOKEN not in arg for arg in each.args), each.args
        assert all("authToken" not in arg for arg in each.args), each.args
    assert call.env is not None
    assert call.env[osdk.TOKEN_ENV_VAR] == TOKEN
    assert call.env["npm_package_version"] == "2.87.0"
    assert call.kwargs["stdin"] == subprocess.DEVNULL
    assert call.kwargs["capture_output"] is True


def test_replace_swaps_in_the_new_package_after_it_is_generated(fake_node, tmp_path):
    old = _existing_package(tmp_path / "osdk")
    tools = osdk.find_node_tools()

    package_dir = _generate(
        tools, osdk.ensure_generator(tools), tmp_path / "osdk", replace=True
    )

    assert package_dir == old
    assert not (old / "stale.js").exists()
    assert json.loads((old / "package.json").read_text())["version"] == "0.0.1"
    assert [p.name for p in (tmp_path / "osdk").iterdir()] == ["@app"]


def test_a_failed_regeneration_keeps_the_existing_package(monkeypatch, tmp_path):
    FakeNode(generate_returncode=1, generate_stderr="boom").apply(monkeypatch)
    old = _existing_package(tmp_path / "osdk")
    tools = osdk.find_node_tools()

    with pytest.raises(PltrError):
        _generate(tools, osdk.ensure_generator(tools), tmp_path / "osdk", replace=True)

    assert (old / "stale.js").exists()
    assert [p.name for p in (tmp_path / "osdk").iterdir()] == ["@app"]


@pytest.mark.parametrize("failing_move", ["old-aside", "new-in"])
def test_a_failed_swap_keeps_the_existing_package(
    failing_move, fake_node, tmp_path, monkeypatch
):
    """E.g. Windows: a file of the old package is open in a dev server."""
    old = _existing_package(tmp_path / "osdk")
    old_manifest = (old / "package.json").read_text()
    tools = osdk.find_node_tools()
    install_dir = osdk.ensure_generator(tools)
    real_replace = os.replace

    def replace(src, dst):
        moving_old = Path(src) == old
        moving_new = Path(dst) == old and Path(src).parent.parent.name.startswith(
            ".pltr-osdk-"
        )  # <out>/.pltr-osdk-xxx/@app/sdk, not the old package moving back
        if (failing_move == "old-aside" and moving_old) or (
            failing_move == "new-in" and moving_new
        ):
            raise PermissionError(13, "Access is denied", str(src))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", replace)

    with pytest.raises(PltrError) as caught:
        _generate(tools, install_dir, tmp_path / "osdk", replace=True)

    assert caught.value.error_type == "work_failed"
    assert "Access is denied" in caught.value.message
    assert caught.value.parameters["step"] == "replace"
    assert (old / "stale.js").exists()
    assert (old / "package.json").read_text() == old_manifest
    assert [p.name for p in (tmp_path / "osdk").iterdir()] == ["@app"]


def test_generate_never_overwrites_without_replace(fake_node, tmp_path):
    old = _existing_package(tmp_path / "osdk")
    tools = osdk.find_node_tools()

    with pytest.raises(PltrError) as caught:
        _generate(tools, osdk.ensure_generator(tools), tmp_path / "osdk")

    assert caught.value.error_type == "usage_error"
    assert (old / "stale.js").exists()
    assert fake_node.generations == []


def test_package_conflict(tmp_path, monkeypatch):
    target = tmp_path / "osdk" / "@app" / "sdk"
    conflict = osdk.package_conflict

    assert conflict(target, "@app/sdk", replace=False) is None  # doesn't exist
    target.mkdir(parents=True)
    assert conflict(target, "@app/sdk", replace=False) is None  # empty
    _existing_package(tmp_path / "other")
    generated = tmp_path / "other" / "@app" / "sdk"
    assert "--replace" in (conflict(generated, "@app/sdk", replace=False) or "")
    assert conflict(generated, "@app/sdk", replace=True) is None
    # --replace only ever deletes a package the generator made with this name.
    assert "not an OSDK package" in (
        conflict(generated, "@app/other", replace=True) or ""
    )
    app = tmp_path / "orders-app"
    app.mkdir()
    (app / "package.json").write_text(
        json.dumps({"name": "orders-app", "dependencies": {"@osdk/client": "2.87.0"}})
    )
    assert "not an OSDK package" in (conflict(app, "orders-app", replace=True) or "")
    # A hand-written library with an OSDK peer dependency isn't generated.
    library = generated_package_json("orders-app")
    del library["osdk"]
    (app / "package.json").write_text(json.dumps(library))
    assert "not an OSDK package" in (conflict(app, "orders-app", replace=True) or "")
    (app / "package.json").unlink()
    (app / "index.html").write_text("<html></html>")
    assert "not an OSDK package" in (conflict(app, "orders-app", replace=True) or "")
    # A symlink is refused before anything runs (it would be replaced, not
    # what it points to).
    link = tmp_path / "linked" / "@app" / "sdk"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(generated, target_is_directory=True)
    except OSError:  # no symlinks without privileges on Windows
        pass
    else:
        assert "symbolic link" in (conflict(link, "@app/sdk", replace=True) or "")
    # Nor the directory pltr runs in, or one that contains it.
    (generated / "src").mkdir()
    monkeypatch.chdir(generated / "src")
    assert "current directory" in (conflict(generated, "@app/sdk", replace=True) or "")
    file = tmp_path / "file"
    file.write_text("x")
    assert "not a directory" in (conflict(file, "x", replace=True) or "")


def test_no_subprocess_inherits_foundry_credentials(fake_node, tmp_path, monkeypatch):
    """Only the helper gets a credential: the token, in PLTR_OSDK_TOKEN."""
    monkeypatch.setenv("FOUNDRY_TOKEN", "env-token-value")
    monkeypatch.setenv("FOUNDRY_CLIENT_SECRET", "env-client-secret")
    tools = osdk.find_node_tools()

    _generate(tools, osdk.ensure_generator(tools), tmp_path / "osdk")

    assert len(fake_node.calls) == 4  # node and npm --version, install, helper
    for call in fake_node.calls:
        assert call.env is not None, f"{call.args} inherits pltr's environment"
        assert "FOUNDRY_TOKEN" not in call.env
        assert "FOUNDRY_CLIENT_SECRET" not in call.env
        values = "\n".join(call.env.values())
        assert "env-token-value" not in values
        assert "env-client-secret" not in values
    for call in fake_node.calls[:3]:
        assert osdk.TOKEN_ENV_VAR not in (call.env or {})
    (generation,) = fake_node.generations
    assert generation.env is not None
    assert generation.env[osdk.TOKEN_ENV_VAR] == TOKEN


def test_generate_failure_shows_the_generators_errors_without_the_token(
    monkeypatch, tmp_path
):
    fake = FakeNode(
        generate_returncode=1,
        generate_stdout="\n".join(
            [
                generator_log("INFO", "OSDK generation..."),
                generator_log(
                    "ERROR",
                    "Encountered 2 errors loading or validating ontology metadata",
                ),
                generator_log(
                    "ERROR",
                    "Unable to find the following object types",
                    unsafe_params={"objectTypeApiNames": ["Nope"]},
                    # Repeats the message: left out.
                    stacktrace="GeneratorError: Unable to find the following "
                    "object types\n    at validate (index.js:1:1)",
                ),
                generator_log(
                    "ERROR",
                    "Unable to load action because it takes an unloaded object "
                    "type as a parameter. Make sure to specify it as an "
                    "argument with --objectTypes <objectTypeApiName>.",
                    unsafe_params={"objectType": "Employee"},
                ),
            ]
        ),
        generate_stderr=f"request failed: Authorization: Bearer {TOKEN}\n",
    ).apply(monkeypatch)
    tools = osdk.find_node_tools()
    install_dir = osdk.ensure_generator(tools)

    with pytest.raises(PltrError) as caught:
        _generate(tools, install_dir, tmp_path / "osdk", object_types=["Nope"])

    error = caught.value
    assert error.error_type == "work_failed"
    assert error.exit_code == ExitCode.FAILED
    assert "Unable to find the following object types" in error.message
    assert "Nope" in error.message
    # The generator's flag names become pltr's.
    assert "--object-type <objectTypeApiName>" in error.message
    assert "--objectTypes" not in error.message
    assert error.parameters["step"] == "generate"
    assert error.parameters["exitCode"] == 1
    assert {
        "message": "Unable to find the following object types",
        "objectTypeApiNames": ["Nope"],
    } in error.parameters["errors"]
    assert "pltr context ontology" in (error.hint or "")
    rendered = json.dumps([error.message, error.parameters, error.hint])
    assert TOKEN not in rendered
    assert len(fake.generations) == 1


def test_generate_failure_without_a_log_shows_stderr(monkeypatch, tmp_path):
    FakeNode(
        generate_returncode=1,
        generate_stderr=f"Error: Cannot find module x\n  token={TOKEN}\n",
    ).apply(monkeypatch)
    tools = osdk.find_node_tools()
    install_dir = osdk.ensure_generator(tools)

    with pytest.raises(PltrError) as caught:
        _generate(tools, install_dir, tmp_path / "osdk")

    assert "Cannot find module x" in caught.value.message
    assert TOKEN not in caught.value.message
    assert "<redacted>" in caught.value.message
    # A module missing from the install: reinstall, not "check the API names".
    assert str(osdk.generator_dir()) in (caught.value.hint or "")
    assert "pltr context" not in (caught.value.hint or "")


def test_an_unrecognised_failure_has_no_hint(monkeypatch, tmp_path):
    FakeNode(generate_returncode=1, generate_stderr="boom").apply(monkeypatch)
    tools = osdk.find_node_tools()

    with pytest.raises(PltrError) as caught:
        _generate(tools, osdk.ensure_generator(tools), tmp_path / "osdk")

    assert caught.value.hint is None
    assert caught.value.suggested_command is None


def test_a_stack_trace_that_adds_detail_is_kept(monkeypatch, tmp_path):
    FakeNode(
        generate_returncode=1,
        generate_stdout=generator_log(
            "ERROR",
            "Rendering OSDK failed.",
            stacktrace="Error: outDir /x is not empty\n    at render (index.js:1:1)",
        ),
    ).apply(monkeypatch)
    tools = osdk.find_node_tools()

    with pytest.raises(PltrError) as caught:
        _generate(tools, osdk.ensure_generator(tools), tmp_path / "osdk")

    assert caught.value.parameters["errors"] == [
        {"message": "Rendering OSDK failed.", "error": "Error: outDir /x is not empty"}
    ]


def test_a_failed_first_generation_leaves_no_out_directory(monkeypatch, tmp_path):
    FakeNode(generate_returncode=1, generate_stderr="boom").apply(monkeypatch)
    tools = osdk.find_node_tools()

    with pytest.raises(PltrError):
        _generate(tools, osdk.ensure_generator(tools), tmp_path / "new" / "osdk")

    assert not (tmp_path / "new").exists()


def test_a_generator_that_writes_no_package_failed(monkeypatch, tmp_path):
    FakeNode(write_package=False).apply(monkeypatch)
    tools = osdk.find_node_tools()

    with pytest.raises(PltrError) as caught:
        _generate(tools, osdk.ensure_generator(tools), tmp_path / "osdk")

    assert caught.value.error_type == "work_failed"
    assert "package.json" in caught.value.message


def test_a_generator_that_hangs_times_out(monkeypatch, tmp_path):
    fake = FakeNode().apply(monkeypatch)
    tools = osdk.find_node_tools()
    install_dir = osdk.ensure_generator(tools)

    def hang(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", hang)

    with pytest.raises(PltrError) as caught:
        _generate(tools, install_dir, tmp_path / "osdk")

    assert caught.value.error_type == "timeout"
    assert caught.value.exit_code == ExitCode.API
    assert len(fake.installs) == 1


# -------------------------------------------------------------- credentials


@pytest.mark.parametrize(
    "host",
    ["stack.example.com", "https://stack.example.com", " https://stack.example.com/ "],
)
def test_credentials_give_an_https_url(host, isolated_home, monkeypatch):
    monkeypatch.setenv("FOUNDRY_HOST", host)
    monkeypatch.setenv("FOUNDRY_TOKEN", TOKEN)

    foundry_url, token = osdk.OsdkService().credentials()

    assert (foundry_url, token) == ("https://stack.example.com", TOKEN)
