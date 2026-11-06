"""Tests for the output mode, stderr messages and warning routing."""

import json
import warnings

import click
import pytest
import typer
from typer.testing import CliRunner

from pltr.contract import (
    FormatOption,
    PltrRootGroup,
    capture_warnings,
    info,
    output_format,
    pltr_command,
    spinner,
    success,
    warn,
)
from pltr.contract.runtime import (
    begin_invocation,
    format_from_args,
    set_output_format,
)
from pltr.utils.formatting import OutputFormatter
from pltr.utils.progress import SpinnerProgressTracker

runner = CliRunner()


@pytest.fixture(autouse=True)
def restore_fallback_format():
    yield
    set_output_format("table")


# ------------------------------------------------------------ format lookup


@pytest.mark.parametrize(
    "args, expected",
    [
        (["x", "--format", "json"], "json"),
        (["x", "--format=csv"], "csv"),
        (["x", "-f", "JSON"], "json"),
        (["x", "-fjson"], "json"),
        (["x", "--format", "xml"], None),
        (["x", "--", "--format", "json"], None),
        (["x"], None),
    ],
)
def test_format_from_args(args, expected):
    assert format_from_args(args) == expected


def test_begin_invocation_uses_args_then_env(monkeypatch):
    begin_invocation(["--format", "csv"])
    assert output_format() == "csv"
    monkeypatch.setenv("PLTR_FORMAT", "json")
    begin_invocation([])
    assert output_format() == "json"


def make_app() -> typer.Typer:
    app = typer.Typer(cls=PltrRootGroup)

    @app.command("with-format")
    @pltr_command(sdk="filesystem.Folder.get")
    def with_format(format: FormatOption = "table"):
        typer.echo(output_format())

    @app.command("without-format")
    def without_format():
        typer.echo(output_format())

    return app


def test_running_command_format_wins_and_does_not_leak():
    app = make_app()
    assert runner.invoke(app, ["with-format", "-f", "json"]).stdout == "json\n"
    # The next invocation (directly through the sub-command) starts clean.
    assert runner.invoke(app, ["without-format"]).stdout == "table\n"
    assert output_format() == "table"


def test_pltr_format_env_var_is_the_default(monkeypatch):
    monkeypatch.setenv("PLTR_FORMAT", "csv")
    app = make_app()
    assert runner.invoke(app, ["with-format"]).stdout == "csv\n"
    assert runner.invoke(app, ["without-format"]).stdout == "csv\n"


# ---------------------------------------------------------- stderr messages


def test_messages_go_to_stderr(capsys):
    info("hello")
    success("done")
    warn("careful")
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "hello\ndone\nWarning: careful\n"


def test_json_mode_suppresses_info_and_makes_warnings_json(capsys):
    set_output_format("json")
    info("hello")
    success("done")
    warn("careful")
    out, err = capsys.readouterr()
    assert out == ""
    assert [json.loads(line) for line in err.splitlines()] == [
        {"type": "warning", "message": "careful"}
    ]


def test_long_messages_are_not_wrapped(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "40")
    rid = "ri.compass.main.folder." + "x" * 60
    info(f"Fetched {rid}")
    assert f"Fetched {rid}\n" == capsys.readouterr().err


def test_spinner_writes_nothing_when_stderr_is_not_a_terminal(capsys):
    with spinner("working"):
        pass
    with SpinnerProgressTracker().track_spinner("working"):
        pass
    assert capsys.readouterr() == ("", "")


# ---------------------------------------------------------- python warnings


def test_capture_warnings_text_mode(capsys):
    with capture_warnings():
        warnings.warn("The preview argument is not required", UserWarning)
    assert capsys.readouterr().err == (
        "Warning: UserWarning: The preview argument is not required\n"
    )


def test_capture_warnings_json_mode(capsys):
    set_output_format("json")
    with capture_warnings():
        warnings.warn("deprecated thing", DeprecationWarning)
    assert json.loads(capsys.readouterr().err) == {
        "type": "warning",
        "message": "DeprecationWarning: deprecated thing",
    }


@pytest.mark.filterwarnings("error::UserWarning")
def test_capture_warnings_keeps_error_filters():
    with pytest.raises(UserWarning), capture_warnings():
        warnings.warn("escalated", UserWarning)


def test_sdk_warning_inside_a_command_becomes_a_json_line():
    app = typer.Typer(cls=PltrRootGroup)

    @app.command("warns")
    @pltr_command(sdk="filesystem.Folder.get")
    def warns(format: FormatOption = "table"):
        warnings.warn("SDK says hi", UserWarning)
        typer.echo("{}")

    @app.command("other")
    def other():
        pass

    result = runner.invoke(app, ["warns", "-f", "json"])

    assert result.exit_code == 0
    assert result.stdout == "{}\n"
    assert json.loads(result.stderr) == {
        "type": "warning",
        "message": "UserWarning: SDK says hi",
    }


# ------------------------------------------------- legacy OutputFormatter


def test_legacy_print_methods_go_to_stderr(capsys):
    formatter = OutputFormatter()
    formatter.print_success("ok")
    formatter.print_info("note")
    formatter.print_warning("hmm")
    formatter.print_error("bad")
    out, err = capsys.readouterr()
    assert out == ""
    for text in ("ok", "note", "hmm", "bad"):
        assert text in err


def test_legacy_print_methods_in_json_mode(capsys):
    set_output_format("json")
    formatter = OutputFormatter()
    formatter.print_success("ok")
    formatter.print_info("note")
    formatter.print_warning("hmm")
    formatter.print_error("bad")
    out, err = capsys.readouterr()
    assert out == ""
    assert [json.loads(line) for line in err.splitlines()] == [
        {"type": "warning", "message": "hmm"},
        {"type": "error", "message": "bad"},
    ]


def test_legacy_data_output_stays_on_stdout(capsys):
    OutputFormatter().format_output([{"a": 1}], "json")
    out, err = capsys.readouterr()
    assert json.loads(out) == [{"a": 1}] and err == ""


def test_format_does_not_leak_to_the_next_command_in_a_shell_session(capsys):
    """`pltr shell` runs commands under one long-lived parent context."""
    group = typer.main.get_command(make_app())
    session = click.Context(group, info_name="pltr")
    for name, args in (("with-format", ["-f", "json"]), ("without-format", [])):
        command = group.get_command(session, name)
        with command.make_context(name, args, parent=session) as ctx:
            command.invoke(ctx)
    assert capsys.readouterr().out == "json\ntable\n"


def test_click_context_without_format_option_uses_fallback():
    set_output_format("csv")
    with click.Context(click.Command("x")):
        assert output_format() == "csv"
