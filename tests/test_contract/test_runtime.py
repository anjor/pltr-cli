"""Tests for the output mode, stderr messages and warning routing."""

import io
import json
import os
import subprocess
import sys
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
    ensure_utf8_output,
    format_from_args,
    set_output_format,
)

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


# ------------------------------------------------------- redirected output


class Stream(io.TextIOWrapper):
    """A text stream in some encoding, on a terminal or not."""

    def __init__(self, encoding: str, tty: bool = False):
        super().__init__(io.BytesIO(), encoding=encoding)
        self.tty = tty

    def isatty(self):
        return self.tty


def test_redirected_output_becomes_utf8(monkeypatch):
    """Windows redirects stdout in cp1252, which can't encode most text."""
    out, err = Stream("cp1252"), Stream("cp1252")
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)

    ensure_utf8_output()

    for stream in (out, err):
        assert stream.encoding == "utf-8"
        stream.write("数据")
        stream.flush()
        assert stream.buffer.getvalue() == "数据".encode("utf-8")


def test_terminals_and_utf8_streams_are_left_alone(monkeypatch):
    terminal, utf8 = Stream("cp1252", tty=True), Stream("UTF8")
    monkeypatch.setattr(sys, "stdout", terminal)
    monkeypatch.setattr(sys, "stderr", utf8)

    ensure_utf8_output()

    assert terminal.encoding == "cp1252"
    assert utf8.encoding == "UTF8"


def test_streams_that_cant_be_reconfigured_are_left_alone(monkeypatch):
    plain = io.StringIO()  # no reconfigure(), like some test runners' captures
    monkeypatch.setattr(sys, "stdout", plain)
    ensure_utf8_output()
    assert sys.stdout is plain


def test_csv_and_tables_of_any_text_to_a_cp1252_pipe(tmp_path):
    """`PYTHONIOENCODING=cp1252 pltr alias list --format csv > out.csv` crashed
    with UnicodeEncodeError (what a Windows redirect does)."""
    config = tmp_path / "config" / "pltr"
    config.mkdir(parents=True)
    (config / "aliases.json").write_text(
        json.dumps({"数据": "dataset get"}), encoding="utf-8"
    )
    env = dict(
        os.environ,
        HOME=str(tmp_path),
        USERPROFILE=str(tmp_path),
        XDG_CONFIG_HOME=str(tmp_path / "config"),
        PYTHONIOENCODING="cp1252",
        COLUMNS="120",
    )
    env.pop("PLTR_FORMAT", None)
    for fmt in ("csv", "table"):
        result = subprocess.run(
            [sys.executable, "-m", "pltr", "alias", "list", "--format", fmt],
            capture_output=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
        assert "数据" in result.stdout.decode("utf-8"), fmt
