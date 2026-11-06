"""`pltr api` loads lazily and plays well with completion and the shell."""

import json
import subprocess
import sys
import textwrap

import typer
from click.shell_completion import BashComplete
from typer.testing import CliRunner

from pltr.cli import app

PROBE = textwrap.dedent(
    """
    import json, sys
    from typer.testing import CliRunner

    def snapshot():
        return {
            "specs": sorted(m for m in sys.modules if m.startswith("pltr.commands.api._specs")),
            "sdk": sorted(m for m in sys.modules if m.startswith("foundry_sdk")),
        }

    from pltr.cli import app
    steps = {"import": snapshot()}
    runner = CliRunner()
    for name, args in [
        ("root_help", ["--help"]),
        ("api_help", ["api", "--help"]),
        ("admin_help", ["api", "admin", "--help"]),
        ("user_list_help", ["api", "admin", "user", "list", "--help"]),
    ]:
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        steps[name] = snapshot()
    print(json.dumps(steps))
    """
)


def test_generated_tree_loads_lazily():
    output = subprocess.run(
        [sys.executable, "-c", PROBE],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    steps = json.loads(output.strip().splitlines()[-1])
    index = "pltr.commands.api._specs"

    # Importing the CLI and `pltr --help` load no generated specs and no extra
    # SDK modules.
    assert steps["import"]["specs"] == []
    assert steps["root_help"]["specs"] == []
    assert steps["root_help"]["sdk"] == steps["import"]["sdk"]
    # `pltr api --help` reads only the tiny index.
    assert steps["api_help"]["specs"] == [index]
    assert steps["api_help"]["sdk"] == steps["import"]["sdk"]
    # `pltr api admin --help` loads only the admin specs, and no SDK modules.
    assert steps["admin_help"]["specs"] == [index, f"{index}.admin"]
    assert steps["admin_help"]["sdk"] == steps["import"]["sdk"]
    assert steps["user_list_help"]["specs"] == [index, f"{index}.admin"]
    assert steps["user_list_help"]["sdk"] == steps["import"]["sdk"]


def test_api_is_listed_in_root_help():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "api" in result.stdout
    assert "Generated commands for every Foundry Platform SDK" in result.stdout


def _completions(args, incomplete):
    command = typer.main.get_command(app)
    completer = BashComplete(command, {}, "pltr", "_PLTR_COMPLETE")
    return [item.value for item in completer.get_completions(args, incomplete)]


def test_shell_completion_reaches_generated_commands():
    assert "api" in _completions([], "ap")
    assert "admin" in _completions(["api"], "ad")
    assert _completions(["api", "admin", "user"], "li") == ["list"]
    options = _completions(["api", "admin", "user", "list"], "--page")
    assert sorted(options) == ["--page-size", "--page-token"]
    assert _completions(["api", "admin", "user", "list", "--include"], "") == [
        "ACTIVE",
        "DELETED",
    ]


def test_interactive_shell_completer_reaches_generated_commands():
    from click_repl._completer import ClickCompleter
    from prompt_toolkit.document import Document

    command = typer.main.get_command(app)
    # `pltr shell` builds this context with make_context("pltr", []), which click
    # 8.2 rejects for a no_args_is_help root (a pre-existing shell bug, unrelated
    # to `pltr api`); resilient parsing builds the same context without that check.
    ctx = command.make_context("pltr", [], resilient_parsing=True)
    completer = ClickCompleter(command, ctx)

    def complete(text):
        return [c.text for c in completer.get_completions(Document(text), None)]

    assert "admin" in complete("api ad")
    assert "list" in complete("api admin user li")
