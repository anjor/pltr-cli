"""Tests for the shared options, the confirmation rule and JSON input."""

import json
from typing import Optional

import click
import pytest
import typer
from click.testing import CliRunner as ClickRunner
from typer.testing import CliRunner
from typing_extensions import Annotated

from pltr.contract import (
    AllPagesOption,
    ConfirmAliasOption,
    ForceAliasOption,
    FormatOption,
    MaxPagesOption,
    OutputOption,
    PageSizeOption,
    PageTokenOption,
    PltrRootGroup,
    PreviewNoopOption,
    ProfileOption,
    YesOption,
    click_format_option,
    click_output_option,
    click_page_options,
    click_profile_option,
    click_yes_option,
    confirm_destructive,
    emit,
    format_option,
    load_json_input,
    output_option,
    pltr_command,
    profile_option,
)

runner = CliRunner()


def lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


def make_app() -> typer.Typer:
    app = typer.Typer(cls=PltrRootGroup)

    @app.command("show")
    @pltr_command(sdk="filesystem.Folder.get")
    def show(
        profile: ProfileOption = None,
        format: FormatOption = "table",
        output: OutputOption = None,
        preview: PreviewNoopOption = False,
        page_size: PageSizeOption = None,
        page_token: PageTokenOption = None,
        max_pages: MaxPagesOption = 1,
        all_pages: AllPagesOption = False,
    ):
        emit(
            {
                "profile": profile,
                "pageSize": page_size,
                "pageToken": page_token,
                "maxPages": max_pages,
                "all": all_pages,
            },
            format=format,
            output=output,
        )

    @app.command("drop")
    @pltr_command(sdk="filesystem.Space.delete", beta=True, destructive=True)
    def drop(
        yes: YesOption = False,
        confirm: ConfirmAliasOption = False,
        force: ForceAliasOption = False,
        format: FormatOption = "table",
    ):
        """Drop it."""
        confirm_destructive("Drop it?", yes=yes)
        emit({"dropped": True}, format=format)

    return app


APP = make_app()


# --------------------------------------------------------------- --format


def test_format_choices_are_case_insensitive():
    result = runner.invoke(APP, ["show", "--format", "JSON"])
    assert json.loads(result.stdout)["maxPages"] == 1


def test_invalid_format_is_a_usage_error():
    result = runner.invoke(APP, ["show", "--format", "xml"])
    assert result.exit_code == 2
    assert "Invalid value for '--format'" in result.stderr


def test_format_env_var(monkeypatch):
    monkeypatch.setenv("PLTR_FORMAT", "json")
    assert json.loads(runner.invoke(APP, ["show"]).stdout)["all"] is False


def test_paging_and_profile_options():
    result = runner.invoke(
        APP,
        [
            "show",
            "-f",
            "json",
            "--profile",
            "p",
            "--page-size",
            "5",
            "--page-token",
            "t",
            "--max-pages",
            "3",
            "--all",
        ],
    )
    assert json.loads(result.stdout) == {
        "profile": "p",
        "pageSize": 5,
        "pageToken": "t",
        "maxPages": 3,
        "all": True,
    }


def test_page_size_must_be_positive():
    assert runner.invoke(APP, ["show", "--page-size", "0"]).exit_code == 2


def test_option_factories_can_drop_the_short_flag():
    app = typer.Typer(cls=PltrRootGroup)

    @app.command("x")
    @pltr_command(sdk="filesystem.Folder.get")
    def x(
        folder: Annotated[str, typer.Option("--folder", "-f")] = "",
        org: Annotated[str, typer.Option("--org", "-o")] = "",
        principal: Annotated[str, typer.Option("--principal", "-p")] = "",
        profile: Annotated[Optional[str], profile_option(short=False)] = None,
        format: Annotated[str, format_option(short=False)] = "table",
        output: Annotated[Optional[str], output_option(short=False)] = None,
    ):
        emit({"folder": folder, "org": org, "profile": profile}, format=format)

    @app.command("other")
    def other():
        pass

    result = runner.invoke(
        app,
        ["x", "-f", "F", "-o", "O", "-p", "P", "--profile", "dev", "--format", "json"],
    )
    assert json.loads(result.stdout) == {"folder": "F", "org": "O", "profile": "dev"}
    with_env = runner.invoke(app, ["x"], env={"PLTR_FORMAT": "json"})
    assert json.loads(with_env.stdout)["profile"] is None


def test_hidden_options_are_not_in_help():
    help_text = runner.invoke(APP, ["drop", "--help"]).stdout
    assert "--yes" in help_text
    for hidden in ("--confirm", "--force", "--preview"):
        assert hidden not in help_text


def test_preview_is_a_deprecated_no_op():
    result = runner.invoke(APP, ["show", "--preview", "-f", "json"])
    assert result.exit_code == 0
    [warning] = lines(result.stderr)
    assert warning["type"] == "warning"
    assert "--preview is deprecated and has no effect" in warning["message"]


def test_preview_warning_in_text_mode():
    result = runner.invoke(APP, ["show", "--preview"])
    assert result.stderr.startswith("Warning: --preview is deprecated")


# ---------------------------------------------------------- confirmation


@pytest.fixture
def interactive(monkeypatch):
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


def test_yes_skips_the_prompt():
    for flag in ("--yes", "-y"):
        result = runner.invoke(APP, ["drop", flag, "-f", "json"])
        assert result.exit_code == 0 and json.loads(result.stdout) == {"dropped": True}


@pytest.mark.parametrize("alias", ["--confirm", "--force"])
def test_deprecated_aliases_skip_the_prompt_and_warn(alias):
    result = runner.invoke(APP, ["drop", alias, "-f", "json"])
    assert result.exit_code == 0
    assert lines(result.stderr) == [
        {
            "type": "warning",
            "message": f"{alias} is deprecated and will be removed in a future "
            "release; use --yes.",
        }
    ]


def test_non_interactive_without_yes_is_exit_2():
    result = runner.invoke(APP, ["drop", "-f", "json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    [error] = lines(result.stderr)
    assert error == {
        "type": "confirmation_required",
        "message": "Drop it? Confirmation is required, but stdin is not a terminal. "
        "Re-run with --yes to proceed.",
        "exitCode": 2,
    }


def test_prompt_goes_to_stderr_and_yes_proceeds(interactive):
    result = runner.invoke(APP, ["drop", "-f", "json"], input="y\n")
    assert result.exit_code == 0
    assert result.stderr == "Drop it? [y/N]: "
    assert json.loads(result.stdout) == {"dropped": True}  # nothing else on stdout


def test_answering_no_is_exit_1(interactive):
    result = runner.invoke(APP, ["drop", "-f", "json"], input="n\n")
    assert result.exit_code == 1
    assert result.stdout == ""
    prompt, error = result.stderr.split("]: ")
    assert prompt == "Drop it? [y/N"
    assert lines(error) == [
        {"type": "aborted", "message": "Aborted; nothing was changed.", "exitCode": 1}
    ]


@pytest.mark.parametrize("answer", ["", "\n", "maybe\n"])
def test_anything_but_yes_aborts(interactive, answer):
    result = runner.invoke(APP, ["drop"], input=answer)
    assert result.exit_code == 1
    assert "Aborted" in result.stderr


def run_in_shell_session(group: click.Group, *invocations: list) -> list:
    """Run commands under one long-lived parent context, as `pltr shell` does."""
    session = click.Context(group, info_name="pltr")
    exit_codes = []
    for args in invocations:
        name, *rest = args
        command = group.get_command(session, name)
        try:
            with command.make_context(name, rest, parent=session) as ctx:
                command.invoke(ctx)
            exit_codes.append(0)
        except click.exceptions.Exit as exc:
            exit_codes.append(exc.exit_code)
    return exit_codes


def test_yes_alias_does_not_leak_to_the_next_command_in_a_shell_session(capsys):
    group = typer.main.get_command(APP)
    assert run_in_shell_session(group, ["drop", "--confirm"], ["drop"]) == [0, 2]
    assert "Confirmation is required" in capsys.readouterr().err


def test_confirm_destructive_outside_a_command():
    confirm_destructive("ok?", yes=True)  # no context needed
    from pltr.contract import ConfirmationRequired

    with pytest.raises(ConfirmationRequired):
        confirm_destructive("ok?")


# ------------------------------------------------------------- JSON input


def test_load_json_input_inline_and_file(tmp_path):
    assert load_json_input('{"a": 1}', param_hint="--where") == {"a": 1}
    path = tmp_path / "where.json"
    path.write_text("[1, 2]")
    assert load_json_input(f"@{path}", param_hint="--where") == [1, 2]


def test_load_json_input_errors_are_usage_errors(tmp_path):
    with pytest.raises(click.BadParameter, match="invalid JSON"):
        load_json_input("{nope", param_hint="--where")
    with pytest.raises(click.BadParameter, match="cannot read"):
        load_json_input(f"@{tmp_path / 'missing.json'}", param_hint="--where")


def test_load_json_input_from_stdin():
    @click.command()
    @click.option("--where")
    def show(where):
        click.echo(json.dumps(load_json_input(where, param_hint="'--where'")))

    result = ClickRunner().invoke(show, ["--where", "@-"], input='{"a": [1]}')
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"a": [1]}
    with_bom = ClickRunner().invoke(
        show, ["--where", "@-"], input=b'\xef\xbb\xbf{"a": [2]}'
    )
    assert with_bom.exit_code == 0, with_bom.output
    assert json.loads(with_bom.stdout) == {"a": [2]}


@pytest.mark.parametrize(
    "encoding",
    [
        "utf-8-sig",  # PowerShell 5: Out-File -Encoding utf8, Set-Content -Encoding utf8
        "utf-16",  # PowerShell 5: `>` and Out-File (UTF-16 LE with a BOM)
        "utf-16-le",
        "utf-32",
    ],
)
def test_load_json_input_reads_what_windows_tools_write(tmp_path, encoding):
    path = tmp_path / "where.json"
    path.write_bytes('{"name": "Zoë"}\r\n'.encode(encoding))
    assert load_json_input(f"@{path}", param_hint="--where") == {"name": "Zoë"}


def test_load_json_input_inline_byte_order_mark():
    assert load_json_input('\ufeff{"a": 1}', param_hint="--where") == {"a": 1}


def test_load_json_input_text_in_another_encoding_is_a_usage_error(tmp_path):
    path = tmp_path / "where.json"
    path.write_bytes('{"name": "Zoë"}'.encode("cp1252"))
    with pytest.raises(click.BadParameter, match="isn't UTF-8, UTF-16 or UTF-32"):
        load_json_input(f"@{path}", param_hint="--where")


def test_invalid_json_input_in_a_command():
    app = typer.Typer(cls=PltrRootGroup)

    @app.command("q")
    @pltr_command(sdk="ontologies.OntologyObject.search")
    def q(where: str = typer.Option(...), format: FormatOption = "table"):
        emit(load_json_input(where, param_hint="'--where'"), format=format)

    @app.command("other")
    def other():
        pass

    as_json = runner.invoke(app, ["q", "--where", "{", "-f", "json"])
    as_text = runner.invoke(app, ["q", "--where", "{"])

    assert as_json.exit_code == 2
    assert lines(as_json.stderr)[-1]["type"] == "usage_error"
    assert (
        "Invalid value for '--where': invalid JSON"
        in lines(as_json.stderr)[-1]["message"]
    )
    assert as_text.exit_code == 2
    assert "Invalid value for '--where'" in as_text.stderr  # click's own rendering


# ------------------------------------------------- plain click commands


@click.command("ls")
@click_profile_option
@click_format_option
@click_output_option
@click_yes_option
@click_page_options
@pltr_command(sdk="filesystem.Space.list", paged=True)
def click_ls(profile, format, output, yes, page_size, page_token, max_pages, all_pages):
    """List things."""
    if page_token == "boom":
        raise click.UsageError("bad token")
    emit(
        {
            "profile": profile,
            "yes": yes,
            "pageSize": page_size,
            "pageToken": page_token,
            "maxPages": max_pages,
            "all": all_pages,
        },
        format=format,
        output=output,
    )


def test_click_option_decorators():
    result = ClickRunner().invoke(
        click_ls,
        [
            "--profile",
            "p",
            "-y",
            "--page-size",
            "2",
            "--page-token",
            "t",
            "--all",
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "profile": "p",
        "yes": True,
        "pageSize": 2,
        "pageToken": "t",
        "maxPages": 1,
        "all": True,
    }


def test_click_command_errors_are_structured():
    result = ClickRunner().invoke(
        click_ls, ["--page-token", "boom", "--format", "json"]
    )
    assert result.exit_code == 2
    assert lines(result.stderr) == [
        {"type": "usage_error", "message": "bad token", "exitCode": 2}
    ]


def test_click_format_option_reads_the_env_var(monkeypatch):
    monkeypatch.setenv("PLTR_FORMAT", "json")
    result = ClickRunner().invoke(click_ls, [])
    assert json.loads(result.stdout)["maxPages"] == 1
