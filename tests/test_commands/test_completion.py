"""Tests for the completion commands and the completion protocol they rely on.

The scripts `pltr completion show/install` write call the `pltr` executable
with Typer's completion protocol (`_PLTR_COMPLETE=complete_bash`, ...), the
protocol the `pltr` entry point (a Typer app) answers. (The old scripts sent
click's `bash_complete` protocol, which the entry point rejects with "Shell
complete not supported.", so completion never worked; the tests that pinned
those scripts' text are replaced by tests that run their protocol against
the real app, and by an end-to-end bash test.)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from pltr.cli import app as pltr_app
from pltr.commands import completion
from pltr.utils.completion import (
    cache_rid,
    complete_output_format,
    complete_profile,
    complete_rid,
    complete_sql_query,
    get_cached_rids,
)

runner = CliRunner()


def show_script(shell: str) -> str:
    result = runner.invoke(pltr_app, ["completion", "show", "--shell", shell])
    assert result.exit_code == 0, result.output
    return result.stdout


def complete_with_script_protocol(shell: str, env: dict) -> str:
    """Ask the real app for completions the way the shell's script does."""
    match = re.search(r"_PLTR_COMPLETE=(\w+)", show_script(shell))
    assert match is not None
    result = runner.invoke(
        pltr_app, [], env={"_PLTR_COMPLETE": match.group(1), **env}, prog_name="pltr"
    )
    assert result.exit_code == 0, result.output
    return result.stdout


class TestCompletionCommands:
    """Test completion CLI commands."""

    def test_completion_help(self):
        """Test completion help display."""
        result = runner.invoke(completion.app, ["--help"])
        assert result.exit_code == 0
        assert "Manage shell completions" in result.output
        assert "install" in result.output
        assert "show" in result.output
        assert "uninstall" in result.output

    @pytest.mark.parametrize(
        "shell, expected",
        [
            ("bash", "complete -o default -F _pltr_completion pltr"),
            ("zsh", "#compdef pltr"),
            ("fish", "complete --command pltr"),
        ],
    )
    def test_show_prints_the_bare_script(self, shell, expected):
        result = runner.invoke(pltr_app, ["completion", "show", "--shell", shell])

        assert result.exit_code == 0, result.output
        assert expected in result.stdout
        assert f"_PLTR_COMPLETE=complete_{shell}" in result.stdout
        assert "_complete pltr" not in result.stdout  # click's protocol
        assert "Completion Script" not in result.stdout  # no Rich panel
        assert result.stderr == ""

    def test_zsh_script_completes_on_the_first_tab_when_autoloaded(self):
        script = show_script("zsh")

        assert "if [[ $zsh_eval_context[-1] == loadautofunc ]]; then" in script
        assert '  _pltr_completion "$@"' in script
        assert "  compdef _pltr_completion pltr" in script
        assert script.rstrip().endswith("fi")

    def test_show_unsupported_shell_is_a_usage_error(self):
        result = runner.invoke(pltr_app, ["completion", "show", "--shell", "tcsh"])

        assert result.exit_code == 2
        assert result.stdout == ""

    @pytest.mark.parametrize(
        "shell_path, expected",
        [
            ("/bin/bash", "_PLTR_COMPLETE=complete_bash"),
            ("/usr/bin/zsh", "_PLTR_COMPLETE=complete_zsh"),
            ("/usr/local/bin/fish", "_PLTR_COMPLETE=complete_fish"),
        ],
    )
    def test_show_detects_the_shell(self, shell_path, expected):
        with patch.dict(os.environ, {"SHELL": shell_path}):
            result = runner.invoke(completion.app, ["show"])

        assert result.exit_code == 0, result.output
        assert expected in result.stdout

    @patch.dict(os.environ, {}, clear=True)
    def test_no_shell_detection(self):
        """Test when shell cannot be detected."""
        result = runner.invoke(completion.app, ["show"])
        assert result.exit_code == 2
        assert "could not detect your shell" in result.stderr

    def test_no_shell_detection_json_error(self, monkeypatch):
        monkeypatch.delenv("SHELL", raising=False)
        monkeypatch.setenv("PLTR_FORMAT", "json")

        result = runner.invoke(pltr_app, ["completion", "show"])

        assert result.exit_code == 2
        error = json.loads(result.stderr.strip().splitlines()[-1])
        assert error["type"] == "usage_error"
        assert "could not detect your shell" in error["message"]

    def test_install_with_custom_path(self):
        """Test installing completion with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "completions" / "pltr.bash"
            result = runner.invoke(
                completion.app,
                ["install", "--shell", "bash", "--path", str(custom_path)],
            )
            assert result.exit_code == 0, result.output
            assert custom_path.read_text() == show_script("bash")
            assert result.stdout == ""
            assert f"Completion file written to: {custom_path}" in result.stderr
            assert "source ~/.bashrc" in result.stderr

    def test_install_detected_shell_to_the_default_path(self, isolated_home):
        with patch.dict(os.environ, {"SHELL": "/usr/bin/zsh"}):
            result = runner.invoke(pltr_app, ["completion", "install"])

        assert result.exit_code == 0, result.output
        target = isolated_home / ".zfunc" / "_pltr"
        assert target.read_text() == show_script("zsh")
        assert "Detected shell: zsh" in result.stderr
        assert f"fpath=({target.parent} $fpath)" in result.stderr

    def test_uninstall_nonexistent(self):
        """Test uninstalling when no completion file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock get_default_completion_path to return a temp path
            mock_path = Path(tmpdir) / "pltr.bash"
            with patch.object(
                completion, "get_default_completion_path", return_value=mock_path
            ):
                result = runner.invoke(completion.app, ["uninstall", "--shell", "bash"])
                assert result.exit_code == 0
                assert "No completion file found" in result.stderr

    def test_uninstall_existing(self):
        """Test uninstalling existing completion file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mock completion file
            mock_path = Path(tmpdir) / "pltr.bash"
            mock_path.write_text("# completion script")

            with patch.object(
                completion, "get_default_completion_path", return_value=mock_path
            ):
                result = runner.invoke(completion.app, ["uninstall", "--shell", "bash"])
                assert result.exit_code == 0
                assert not mock_path.exists()
                assert "Removed completion file" in result.stderr


class TestCompletionProtocol:
    """The scripts' protocol, run against the real app (including `pltr api`)."""

    def test_bash(self):
        out = complete_with_script_protocol(
            "bash", {"COMP_WORDS": "pltr api wid", "COMP_CWORD": "2"}
        )
        assert out.split() == ["widgets"]

    def test_bash_option_values(self):
        out = complete_with_script_protocol(
            "bash", {"COMP_WORDS": "pltr folder get --format ", "COMP_CWORD": "4"}
        )
        assert out.split() == ["table", "json", "csv"]

    def test_zsh(self):
        out = complete_with_script_protocol(
            "zsh", {"_TYPER_COMPLETE_ARGS": "pltr api widgets widget-set "}
        )
        assert "get" in out and "release" in out

    def test_fish(self):
        out = complete_with_script_protocol(
            "fish",
            {
                "_TYPER_COMPLETE_ARGS": "pltr api wid",
                "_TYPER_COMPLETE_FISH_ACTION": "get-args",
            },
        )
        assert out.split()[0] == "widgets"

    def test_clicks_protocol_is_not_what_the_entry_point_answers(self):
        """Why the old scripts never completed anything."""
        result = runner.invoke(
            pltr_app,
            [],
            env={
                "_PLTR_COMPLETE": "bash_complete",
                "COMP_WORDS": "pltr fo",
                "COMP_CWORD": "1",
            },
            prog_name="pltr",
        )
        assert result.exit_code == 1
        assert "Shell complete not supported" in result.stderr


PLTR_EXECUTABLE = Path(sys.executable).parent / "pltr"


@pytest.mark.skipif(
    shutil.which("bash") is None or not PLTR_EXECUTABLE.exists(),
    reason="needs bash and the pltr console script",
)
def test_bash_script_completes_with_the_installed_executable(tmp_path):
    """Source the generated script in a real bash and complete with `pltr`."""
    script = tmp_path / "pltr.bash"
    script.write_text(show_script("bash"))
    program = "\n".join(
        [
            f"source {script}",
            "COMP_WORDS=(pltr api wid)",
            "COMP_CWORD=2",
            "_pltr_completion pltr",
            "printf '%s\\n' \"${COMPREPLY[@]}\"",
        ]
    )
    env = dict(
        os.environ,
        PATH=f"{PLTR_EXECUTABLE.parent}{os.pathsep}{os.environ.get('PATH', '')}",
        HOME=str(tmp_path),
        XDG_CONFIG_HOME=str(tmp_path / ".config"),
    )

    out = subprocess.run(
        ["bash", "-c", program], env=env, capture_output=True, text=True, timeout=120
    )

    assert out.stdout.split() == ["widgets"], out.stderr


class TestCompletionFunctions:
    """Test completion helper functions."""

    def test_cache_and_get_rids(self):
        """Test RID caching and retrieval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock home directory
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                # Initially should return example RIDs
                rids = get_cached_rids()
                assert len(rids) > 0
                assert any("dataset" in rid for rid in rids)

                # Cache a new RID
                test_rid = "ri.foundry.main.dataset.test-123"
                cache_rid(test_rid)

                # Should now include the cached RID
                rids = get_cached_rids()
                assert test_rid in rids

    def test_complete_rid(self):
        """Test RID completion."""
        with patch("pltr.utils.completion.get_cached_rids") as mock_get:
            mock_get.return_value = [
                "ri.foundry.main.dataset.abc123",
                "ri.foundry.main.dataset.def456",
                "ri.foundry.main.folder.xyz789",
            ]

            # Complete with prefix
            results = complete_rid("ri.foundry.main.dataset.")
            assert len(results) == 2
            assert all("dataset" in r for r in results)

            # Complete with partial
            results = complete_rid("ri.foundry.main.d")
            assert len(results) == 2

    def test_complete_profile(self):
        """Test profile name completion."""
        mock_profiles = ["default", "production", "development"]

        with patch("pltr.utils.completion.ProfileManager") as MockManager:
            mock_manager = MagicMock()
            mock_manager.list_profiles.return_value = mock_profiles
            MockManager.return_value = mock_manager

            # Complete all
            results = complete_profile("")
            assert len(results) == 3

            # Complete with prefix
            results = complete_profile("de")
            assert len(results) == 2
            assert "default" in results
            assert "development" in results

    def test_complete_output_format(self):
        """Test output format completion."""
        # Complete all
        results = complete_output_format("")
        assert len(results) == 3
        assert "table" in results
        assert "json" in results
        assert "csv" in results

        # Complete with prefix
        results = complete_output_format("j")
        assert len(results) == 1
        assert results[0] == "json"

    def test_complete_sql_query(self):
        """Test SQL query template completion."""
        # Complete SELECT
        results = complete_sql_query("SEL")
        assert any("SELECT * FROM " in r for r in results)
        assert any("SELECT COUNT(*) FROM " in r for r in results)

        # Complete JOIN (only matches templates that start with "JOIN")
        results = complete_sql_query("JOIN")
        assert "JOIN " in results
        # LEFT JOIN and INNER JOIN don't start with "JOIN", so they won't match

        # Complete LEFT
        results = complete_sql_query("LEFT")
        assert "LEFT JOIN " in results

        # Case insensitive
        results = complete_sql_query("sel")
        assert any("SELECT" in r for r in results)

    def test_shell_detection(self):
        """Test shell type detection from environment."""
        # Test bash detection
        with patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            shell = completion.get_shell_from_env()
            assert shell == "bash"

        # Test zsh detection
        with patch.dict(os.environ, {"SHELL": "/usr/bin/zsh"}):
            shell = completion.get_shell_from_env()
            assert shell == "zsh"

        # Test fish detection
        with patch.dict(os.environ, {"SHELL": "/usr/local/bin/fish"}):
            shell = completion.get_shell_from_env()
            assert shell == "fish"

        # Test unknown shell
        with patch.dict(os.environ, {"SHELL": "/bin/sh"}):
            shell = completion.get_shell_from_env()
            assert shell is None

    def test_default_completion_paths(self):
        """Test default paths for completion files."""
        # Bash path
        bash_path = completion.get_default_completion_path("bash")
        assert "bash" in str(bash_path) or "completion" in str(bash_path)

        # Zsh path
        zsh_path = completion.get_default_completion_path("zsh")
        assert ".zfunc" in str(zsh_path) or "_pltr" in str(zsh_path)

        # Fish path
        fish_path = completion.get_default_completion_path("fish")
        assert "fish" in str(fish_path) and "completions" in str(fish_path)
