"""
Tests for the shell command.

`pltr shell` used click-repl, whose `repl()` can't run a command on click 8.2
(it assigns `ctx.protected_args`, a read-only property there), and built its
context with `make_context("pltr", [])`, which click 8.2 rejects for a group
that shows help when called without arguments: `pltr shell` printed an empty
error box. The shell now runs each line as its own `pltr` invocation and
completes with click's completion machinery. CliRunner's stdin isn't a
terminal, so these tests feed commands line by line, as `pltr shell < file`
does.
"""

import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.document import Document
from typer.testing import CliRunner

from pltr.cli import app
from pltr.commands.shell import (
    build_completer,
    get_history_file,
    get_prompt,
    root_command,
    shell_app,
    split_line,
)


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def run_shell(*lines: str, args=()):
    """Run `pltr shell` with these lines on stdin (not a terminal)."""
    return CliRunner().invoke(
        app, ["shell", *args], input="".join(f"{line}\n" for line in lines)
    )


@pytest.fixture(scope="module")
def completer():
    return build_completer(root_command())


def complete(completer, text: str) -> list:
    return [c.text for c in completer.get_completions(Document(text), None)]


class TestShellCommand:
    """Test shell command functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_get_history_file(self, monkeypatch, tmp_path):
        """In pltr's config directory: $XDG_CONFIG_HOME/pltr or ~/.config/pltr."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        assert get_history_file() == tmp_path / "xdg" / "pltr" / "repl_history"

        monkeypatch.delenv("XDG_CONFIG_HOME")
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
        history_file = get_history_file()
        assert isinstance(history_file, Path)
        assert history_file == tmp_path / "home" / ".config" / "pltr" / "repl_history"
        assert history_file.exists()

    @patch("pltr.commands.shell.ProfileManager")
    def test_get_prompt_with_profile(self, mock_profile_manager_class):
        """Test get_prompt function with profile."""
        # Setup mock
        mock_profile_manager = MagicMock()
        mock_profile_manager.get_active_profile.return_value = "test-profile"
        mock_profile_manager_class.return_value = mock_profile_manager

        # Test
        prompt = get_prompt()

        # Assert
        assert prompt == "pltr (test-profile)> "
        mock_profile_manager_class.assert_called_once()
        mock_profile_manager.get_active_profile.assert_called_once()

    @patch("pltr.commands.shell.ProfileManager")
    def test_get_prompt_no_profile(self, mock_profile_manager_class):
        """Test get_prompt function without profile."""
        # Setup mock
        mock_profile_manager = MagicMock()
        mock_profile_manager.get_active_profile.return_value = None
        mock_profile_manager_class.return_value = mock_profile_manager

        # Test
        prompt = get_prompt()

        # Assert
        assert prompt == "pltr> "

    @patch("pltr.commands.shell.ProfileManager")
    def test_get_prompt_exception(self, mock_profile_manager_class):
        """Test get_prompt function when ProfileManager raises exception."""
        # Setup mock to raise exception
        mock_profile_manager_class.side_effect = Exception("Profile error")

        # Test
        prompt = get_prompt()

        # Assert
        assert prompt == "pltr> "

    def test_shell_app_help(self):
        """Test shell app help command."""
        result = self.runner.invoke(shell_app, ["--help"])

        assert result.exit_code == 0
        assert (
            "Start an interactive shell session with tab completion and history"
            in result.stdout
        )

    def test_start_command_help(self):
        """Test start command help."""
        result = self.runner.invoke(shell_app, ["start", "--help"])

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "Start an interactive shell session" in clean_output
        assert "--profile" in clean_output

    def test_shell_callback_no_subcommand(self):
        """Test shell callback when no subcommand is provided."""
        mock_ctx = MagicMock()
        mock_ctx.invoked_subcommand = None

        with patch("pltr.commands.shell.start") as mock_start:
            from pltr.commands.shell import shell_callback

            shell_callback(mock_ctx, profile="test-profile")

            mock_start.assert_called_once_with(profile="test-profile")

    def test_shell_callback_with_subcommand(self):
        """Test shell callback when subcommand is provided."""
        mock_ctx = MagicMock()
        mock_ctx.invoked_subcommand = "start"

        with patch("pltr.commands.shell.start") as mock_start:
            from pltr.commands.shell import shell_callback

            shell_callback(mock_ctx, profile="test-profile")

            mock_start.assert_not_called()

    def test_interactive_alias(self):
        """Test interactive alias command."""
        with patch("pltr.commands.shell.start") as mock_start:
            from pltr.commands.shell import interactive_alias

            interactive_alias(profile="test-profile")

            mock_start.assert_called_once_with(profile="test-profile")


@pytest.mark.usefixtures("isolated_home")
class TestShellSession:
    """Run commands through `pltr shell` (regressions for click 8.2)."""

    def test_shell_without_input_exits_cleanly(self):
        result = run_shell()

        assert result.exit_code == 0, result.output
        assert result.stderr == ""

    def test_runs_commands_until_exit(self):
        result = run_shell("hello", "exit", "hello")

        assert result.exit_code == 0, result.output
        assert result.stdout.count("Hello from pltr!") == 1

    @pytest.mark.parametrize(
        "args", [["shell"], ["shell", "start"], ["shell", "interactive"]]
    )
    def test_every_entry_point_starts_the_session(self, args):
        result = CliRunner().invoke(app, args, input="hello\n")

        assert result.exit_code == 0, result.output
        assert "Hello from pltr!" in result.stdout

    def test_a_failing_command_does_not_end_the_session(self):
        result = run_shell("nosuchcommand", "hello")

        assert result.exit_code == 0, result.output
        assert "No such command 'nosuchcommand'" in result.stderr
        assert "Hello from pltr!" in result.stdout

    def test_errors_are_structured_per_line(self):
        result = run_shell("configure set-default nope --format json", "hello")

        assert result.exit_code == 0, result.output
        error = json.loads(result.stderr.strip().splitlines()[-1])
        assert (error["type"], error["exitCode"]) == ("not_found", 5)
        assert "Hello from pltr!" in result.stdout

    def test_format_does_not_leak_to_the_next_line(self):
        result = run_shell(
            "configure list-profiles --format json", "configure list-profiles"
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {"data": []}
        # The second, table-format command still prints its message
        assert "No profiles configured" in result.stderr

    def test_destructive_commands_never_read_the_next_line_as_an_answer(self):
        result = run_shell(
            'alias add ds "dataset get"',
            "alias remove ds",
            "y",
            "alias list --format json",
        )

        assert result.exit_code == 0, result.output
        assert "Re-run with --yes" in result.stderr
        assert json.loads(result.stdout) == {
            "data": [{"name": "ds", "command": "dataset get"}]
        }

    def test_help_words(self):
        result = run_shell("help", "help configure")

        assert result.exit_code == 0, result.output
        output = strip_ansi_codes(result.stdout)
        assert "Command-line interface for Palantir Foundry APIs" in output
        assert "list-profiles" in output

    def test_aliases_expand(self):
        result = run_shell(
            'alias add hi "hello"',
            'alias add ls "alias list --format json"',
            "hi",
            "ls",
        )

        assert result.exit_code == 0, result.output
        assert "Hello from pltr!" in result.stdout
        document = result.stdout[result.stdout.index("{") :]
        assert {"name": "hi", "command": "hello"} in json.loads(document)["data"]

    def test_nested_shell_is_refused(self):
        result = run_shell("shell", "hello")

        assert "Already in the pltr shell" in result.stderr
        assert "Hello from pltr!" in result.stdout

    def test_comments_and_blank_lines_are_skipped(self):
        result = run_shell("", "# a comment", "   ", "hello")

        assert result.exit_code == 0, result.output
        assert result.stderr == ""
        assert "Hello from pltr!" in result.stdout

    def test_profile_option_sets_pltr_profile(self, monkeypatch):
        # setenv (not a delenv of an unset variable, which records nothing)
        # makes monkeypatch remove the variable the shell sets after the test.
        monkeypatch.setenv("PLTR_PROFILE", "before")

        result = run_shell(args=["--profile", "work"])

        assert result.exit_code == 0, result.output
        assert os.environ["PLTR_PROFILE"] == "work"


class TestShellCompletion:
    """The shell's completer, built on click's completion (reaches `pltr api`)."""

    def test_top_level(self, completer):
        words = complete(completer, "")

        assert {"dataset", "folder", "api", "help", "exit"} <= set(words)
        assert "shell" not in words

    def test_reaches_the_generated_api_tree(self, completer):
        assert "widgets" in complete(completer, "api ")
        assert complete(completer, "api wid") == ["widgets"]
        assert complete(completer, "api widgets widget-set release ") == [
            "delete",
            "get",
            "list",
        ]

    def test_curated_commands_and_option_values(self, completer):
        assert complete(completer, "fo") == ["folder"]
        assert "--format" in complete(completer, "folder get --f")
        assert complete(completer, "folder get --format ") == ["table", "json", "csv"]

    def test_alias_names(self, completer, isolated_home):
        from pltr.config.aliases import AliasManager

        AliasManager().add_alias("dsg", "dataset get")

        assert "dsg" in complete(completer, "ds")
        assert "dsg" not in complete(completer, "folder ")

    def test_help_completes_like_the_command(self, completer):
        assert complete(completer, "help fol") == ["folder"]
        assert "list" in complete(completer, "help folder ")

    def test_paths(self, completer, tmp_path):
        (tmp_path / "commands.txt").write_text("")

        assert complete(completer, f"alias import {tmp_path}/comm") == ["ands.txt"]

    def test_system_commands_and_comments_get_no_completions(self, completer):
        assert complete(completer, "!ls ") == []
        assert complete(completer, "# fo") == []


def test_session_on_a_terminal(monkeypatch, capsys, isolated_home):
    """The prompt_toolkit path: banner on stderr, prompt, history, exit."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from pltr.commands.shell import start

    monkeypatch.setattr("pltr.commands.shell.stdin_is_interactive", lambda: True)
    with create_pipe_input() as pipe:
        pipe.send_text("hello\rhello --token SECRET-1\rexit\r")
        with create_app_session(input=pipe, output=DummyOutput()):
            start(profile=None)

    out, err = capsys.readouterr()
    assert out.count("Hello from pltr!") == 1
    assert "Welcome to pltr interactive shell!" in err
    assert "Goodbye!" in err
    history = isolated_home / ".config" / "pltr" / "repl_history"
    assert "+hello" in history.read_text()
    assert "SECRET" not in history.read_text()  # lines with credentials aren't kept


@pytest.mark.parametrize(
    "line, secret",
    [
        ("configure configure --token abc", True),
        ("configure configure --token=abc --host h", True),
        ("configure configure --auth-type oauth --client-id i --client-secret s", True),
        ("configure configure --client-secret=s", True),
        ("!export FOUNDRY_TOKEN=abc", True),
        ("!FOUNDRY_CLIENT_SECRET=s pltr verify", True),
        ("admin user revoke-all-tokens 0d4b1b8e-5e43-4d1f-9a7f-6b8c2f3e1a90", False),
        ("dataset get ri.foundry.main.dataset.x --format json", False),
        ("api admin user get --token-hint x", False),
    ],
)
def test_lines_holding_credentials(line, secret):
    from pltr.commands.shell import holds_credentials

    assert holds_credentials(line) is secret


def test_history_doesnt_save_lines_with_credentials(tmp_path):
    from pltr.commands.shell import make_history

    path = tmp_path / "repl_history"
    history = make_history(path)
    history.append_string("configure configure --token SECRET-1")
    history.append_string("folder get ri.compass.main.folder.0")

    assert "SECRET" not in path.read_text()
    assert "+folder get ri.compass.main.folder.0" in path.read_text()
    # The line can still be recalled during the session.
    assert "configure configure --token SECRET-1" in history.get_strings()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_history_file_and_directory_are_private(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    history = get_history_file()
    assert history.parent.stat().st_mode & 0o777 == 0o700
    assert history.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_an_existing_history_file_is_made_private(monkeypatch, tmp_path):
    config = tmp_path / "xdg" / "pltr"
    config.mkdir(parents=True)
    old = config / "repl_history"
    old.write_text("\n# earlier\n+folder list ri.compass.main.folder.0\n")
    old.chmod(0o644)  # what FileHistory created
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert get_history_file() == old
    assert old.stat().st_mode & 0o777 == 0o600
    assert old.read_text().endswith("+folder list ri.compass.main.folder.0\n")


def test_split_line_keeps_an_unclosed_quote():
    assert split_line('alias add ds "dataset get') == [
        "alias",
        "add",
        "ds",
        "dataset get",
    ]
    assert split_line("folder list  ri.x ") == ["folder", "list", "ri.x"]


def test_split_line_keeps_windows_paths():
    """On Windows a backslash separates path components; it isn't an escape."""
    line = r"dataset files upload C:\data\flights.csv ri.foundry.main.dataset.x"
    assert split_line(line, windows=True) == [
        "dataset",
        "files",
        "upload",
        r"C:\data\flights.csv",
        "ri.foundry.main.dataset.x",
    ]
    assert split_line(r"x \\server\share\f.csv", windows=True) == [
        "x",
        r"\\server\share\f.csv",
    ]
    # Quotes still group words, and an unclosed one keeps its partial word.
    assert split_line(r'alias import "C:\My Data\a.json"', windows=True) == [
        "alias",
        "import",
        r"C:\My Data\a.json",
    ]
    assert split_line(r"alias import 'C:\My Data\a", windows=True) == [
        "alias",
        "import",
        r"C:\My Data\a",
    ]


def test_split_line_escapes_with_a_backslash_elsewhere():
    assert split_line(r"alias import my\ file.json", windows=False) == [
        "alias",
        "import",
        "my file.json",
    ]


def test_split_line_follows_the_platform(monkeypatch):
    monkeypatch.setattr("pltr.commands.shell.WINDOWS", True)
    assert split_line(r"dataset get C:\x") == ["dataset", "get", r"C:\x"]
    monkeypatch.setattr("pltr.commands.shell.WINDOWS", False)
    assert split_line(r"dataset get C:\x") == ["dataset", "get", "C:x"]


def test_a_windows_path_reaches_the_command_unchanged(monkeypatch, isolated_home):
    """`pltr shell` on Windows mangled C:\\data\\x.json into C:datax.json."""
    monkeypatch.setattr("pltr.commands.shell.WINDOWS", True)

    result = run_shell(r"alias import C:\no\such\aliases.json --format json")

    error = json.loads(result.stderr.strip().splitlines()[-1])
    assert error["type"] == "usage_error"
    assert r"cannot read C:\no\such\aliases.json" in error["message"]


def test_windows_paths_get_path_completion():
    from pltr.commands.shell import _looks_like_path

    for text in (r"C:\data\fl", "C:", r"data\fl", r"\\server\share"):
        assert _looks_like_path(text, windows=True), text
        assert not _looks_like_path(text, windows=False), text
    for text in ("/tmp/x", "./x", "~/x", "data/x"):
        assert _looks_like_path(text, windows=True), text
        assert _looks_like_path(text, windows=False), text
    assert not _looks_like_path("dataset", windows=True)


class TestShellIntegration:
    """Integration tests for shell functionality."""

    def test_shell_command_in_main_cli(self):
        """Test that shell command is properly integrated in main CLI."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "shell" in result.stdout
        # The shell module's own description (pltr/commands/shell.py).
        assert "Start an interactive shell session" in result.stdout

    def test_shell_subcommand_available(self):
        """Test that shell subcommands are available."""
        runner = CliRunner()
        result = runner.invoke(app, ["shell", "--help"])

        assert result.exit_code == 0
        assert "start" in result.stdout
