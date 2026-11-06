"""Tests for @pltr_command, command metadata, the tree walker and the root group."""

import functools
import json

import click
import pytest
import typer
from click.testing import CliRunner as ClickRunner
from typer.testing import CliRunner
from typing_extensions import Annotated

from pltr.contract import (
    CommandMeta,
    FormatOption,
    PltrRootGroup,
    beta_help,
    get_command_meta,
    iter_commands,
    pltr_command,
)

runner = CliRunner()


def lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


def passthrough(func):
    """Some other decorator that uses functools.wraps."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def make_app() -> typer.Typer:
    app = typer.Typer(cls=PltrRootGroup, no_args_is_help=True)
    things = typer.Typer()
    app.add_typer(things, name="things")

    @things.command("get")
    @pltr_command(sdk="filesystem.Space.get", beta=True)
    def get_thing(
        thing_rid: Annotated[str, typer.Argument(help="Thing RID")],
        count: Annotated[int, typer.Option("--count", min=1)] = 1,
        format: FormatOption = "table",
    ):
        """Get a thing.

        More details.
        """
        typer.echo(json.dumps({"rid": thing_rid, "count": count}))

    @things.command("list", help="Explicit help text.")
    @passthrough
    @pltr_command(
        sdk=("filesystem.Space.list", "filesystem.Folder.children"), paged=True
    )
    def list_things(format: FormatOption = "table"):
        typer.echo("[]")

    @things.command("hidden", hidden=True)
    @pltr_command(http="POST /api/v1/things")
    def hidden_thing():
        """Hidden."""

    @app.command("crash")
    def crash(format: FormatOption = "table"):
        """Not decorated: the root group still renders its errors."""
        raise RuntimeError("legacy failure")

    verify = typer.Typer()
    app.add_typer(verify, name="check")

    @verify.callback(invoke_without_command=True)
    @pltr_command(sdk="admin.User.get_current")
    def check():
        """A runnable group."""

    return app


APP = make_app()


# ------------------------------------------------------------- metadata


def test_metadata_survives_typer_wrapping():
    entries = {entry.path: entry for entry in iter_commands(APP)}
    assert entries["things get"].meta == CommandMeta(
        sdk=("filesystem.Space.get",), beta=True
    )
    assert entries["things list"].meta == CommandMeta(
        sdk=("filesystem.Space.list", "filesystem.Folder.children"), paged=True
    )
    assert entries["things hidden"].meta.http == ("POST /api/v1/things",)
    assert entries["things hidden"].command.hidden
    assert entries["crash"].meta is None
    assert entries["check"].meta.sdk == ("admin.User.get_current",)  # runnable group


def test_metadata_on_plain_click_commands():
    @click.command()
    @pltr_command(sdk="filesystem.Folder.get", destructive=True)
    def cmd():
        """Do it."""

    assert get_command_meta(cmd) == CommandMeta(
        sdk=("filesystem.Folder.get",), destructive=True
    )
    group = click.Group("root", commands={"do": cmd})
    assert [(e.path, e.meta.destructive) for e in iter_commands(group)] == [
        ("do", True)
    ]


def test_to_dict():
    assert CommandMeta(sdk=("a.B.c",), paged=True).to_dict() == {
        "sdk": ["a.B.c"],
        "http": [],
        "beta": False,
        "destructive": False,
        "paged": True,
    }


@pytest.mark.parametrize(
    "kwargs", [{"sdk": "get"}, {"sdk": "filesystem Folder get"}, {"http": "/no/method"}]
)
def test_invalid_metadata_is_rejected(kwargs):
    with pytest.raises(ValueError, match="Invalid command metadata"):
        pltr_command(**kwargs)


def test_typer_introspection_still_works():
    result = runner.invoke(APP, ["things", "get", "ri.a.b.c.d", "--count", "2"])
    assert json.loads(result.stdout) == {"rid": "ri.a.b.c.d", "count": 2}
    assert runner.invoke(APP, ["things", "get", "x", "--count", "0"]).exit_code == 2


# ------------------------------------------------------------- beta label


def test_beta_help_label():
    assert beta_help("Get a thing.") == "[beta] Get a thing."
    assert (
        beta_help("\n    Get a thing.\n\n    More.\n") == "[beta] Get a thing.\n\nMore."
    )
    assert beta_help("[beta] Already.") == "[beta] Already."
    assert beta_help(None) == "[beta]"


def test_beta_commands_show_the_label_in_help():
    group_help = runner.invoke(APP, ["things", "--help"]).stdout
    assert "[beta] Get a thing." in group_help
    command_help = runner.invoke(APP, ["things", "get", "--help"]).stdout
    assert "[beta] Get a thing." in command_help
    assert "More details." in command_help


# ------------------------------------------------- parse-time usage errors


def test_missing_argument_is_json_in_json_mode():
    result = runner.invoke(APP, ["things", "get", "--format", "json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert lines(result.stderr) == [
        {
            "type": "usage_error",
            "message": "Missing argument 'THING_RID'.",
            "exitCode": 2,
        }
    ]


def test_missing_argument_with_pltr_format_env(monkeypatch):
    monkeypatch.setenv("PLTR_FORMAT", "json")
    result = runner.invoke(APP, ["things", "get"])
    assert lines(result.stderr)[-1]["type"] == "usage_error"


def test_unknown_option_is_json_in_json_mode():
    result = runner.invoke(APP, ["things", "get", "x", "--nope", "-f", "json"])
    assert result.exit_code == 2
    assert lines(result.stderr)[-1]["message"] == "No such option: --nope"


def test_unknown_command_is_json_in_json_mode():
    result = runner.invoke(APP, ["things", "nope", "--format", "json"])
    assert result.exit_code == 2
    assert "No such command 'nope'" in lines(result.stderr)[-1]["message"]


def test_usage_errors_keep_clicks_rendering_in_text_mode():
    result = runner.invoke(APP, ["things", "get"])
    assert result.exit_code == 2
    assert "Missing argument 'THING_RID'" in result.stderr
    assert "Usage:" in result.stderr


def test_no_args_is_help_is_not_an_error():
    result = runner.invoke(APP, [])
    assert "Usage:" in result.stdout + result.stderr
    assert "usage_error" not in result.stderr


# ------------------------------------------------ errors from commands


def test_undecorated_command_errors_are_rendered_by_the_root():
    as_json = runner.invoke(APP, ["crash", "-f", "json"])
    as_text = runner.invoke(APP, ["crash"])
    assert as_json.exit_code == as_text.exit_code == 1
    assert lines(as_json.stderr) == [
        {"type": "unexpected_error", "message": "legacy failure", "exitCode": 1}
    ]
    assert as_text.stderr.startswith("Error: legacy failure")


def test_pltr_debug_shows_the_traceback(monkeypatch):
    monkeypatch.setenv("PLTR_DEBUG", "1")
    result = runner.invoke(APP, ["crash"])
    assert isinstance(result.exception, RuntimeError)


def test_typer_exit_and_abort_pass_through():
    app = typer.Typer(cls=PltrRootGroup)

    @app.command("exit")
    @pltr_command(sdk="filesystem.Folder.get")
    def do_exit(format: FormatOption = "table"):
        raise typer.Exit(3)

    @app.command("abort")
    @pltr_command(sdk="filesystem.Folder.get")
    def do_abort(format: FormatOption = "table"):
        raise click.Abort()

    exited = runner.invoke(app, ["exit", "-f", "json"])
    aborted = runner.invoke(app, ["abort"])
    assert (exited.exit_code, exited.stderr) == (3, "")
    assert aborted.exit_code == 1 and "Aborted" in aborted.stderr


def test_decorator_works_for_click_commands_without_the_root_group():
    @click.command()
    @click.option("--format", "format", default="table")
    @pltr_command(sdk="filesystem.Folder.get")
    def cmd(format):
        raise KeyError("missing")

    result = ClickRunner().invoke(cmd, ["--format", "json"])
    assert result.exit_code == 1
    assert lines(result.stderr) == [
        {"type": "unexpected_error", "message": "KeyError: 'missing'", "exitCode": 1}
    ]


def test_real_cli_root_uses_the_root_group():
    from pltr.cli import app

    assert isinstance(typer.main.get_command(app), PltrRootGroup)
