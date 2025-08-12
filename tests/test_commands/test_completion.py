"""Tests for completion commands."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile

from typer.testing import CliRunner

from pltr.commands import completion
from pltr.utils.completion import (
    get_cached_rids,
    cache_rid,
    complete_rid,
    complete_profile,
    complete_output_format,
    complete_sql_query,
)


runner = CliRunner()


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

    def test_show_bash_completion(self):
        """Test showing bash completion script."""
        result = runner.invoke(completion.app, ["show", "--shell", "bash"])
        assert result.exit_code == 0
        assert "_pltr_completion()" in result.output
        assert "COMP_WORDS" in result.output
        assert "complete -o nosort -F _pltr_completion pltr" in result.output

    def test_show_zsh_completion(self):
        """Test showing zsh completion script."""
        result = runner.invoke(completion.app, ["show", "--shell", "zsh"])
        assert result.exit_code == 0
        assert "#compdef pltr" in result.output
        assert "_pltr()" in result.output
        assert "compdef _pltr pltr" in result.output

    def test_show_fish_completion(self):
        """Test showing fish completion script."""
        result = runner.invoke(completion.app, ["show", "--shell", "fish"])
        assert result.exit_code == 0
        assert "function _pltr_completion" in result.output
        assert "complete -c pltr" in result.output

    def test_show_unsupported_shell(self):
        """Test showing completion for unsupported shell."""
        result = runner.invoke(completion.app, ["show", "--shell", "tcsh"])
        assert result.exit_code == 1
        assert "Unsupported shell: tcsh" in result.output

    @patch.dict(os.environ, {"SHELL": "/bin/bash"})
    def test_auto_detect_bash_shell(self):
        """Test auto-detection of bash shell."""
        result = runner.invoke(completion.app, ["show"])
        assert result.exit_code == 0
        assert "_pltr_completion()" in result.output  # Bash script

    @patch.dict(os.environ, {"SHELL": "/usr/bin/zsh"})
    def test_auto_detect_zsh_shell(self):
        """Test auto-detection of zsh shell."""
        result = runner.invoke(completion.app, ["show"])
        assert result.exit_code == 0
        assert "#compdef pltr" in result.output  # Zsh script

    @patch.dict(os.environ, {"SHELL": "/usr/local/bin/fish"})
    def test_auto_detect_fish_shell(self):
        """Test auto-detection of fish shell."""
        result = runner.invoke(completion.app, ["show"])
        assert result.exit_code == 0
        assert "function _pltr_completion" in result.output  # Fish script

    @patch.dict(os.environ, {}, clear=True)
    def test_no_shell_detection(self):
        """Test when shell cannot be detected."""
        result = runner.invoke(completion.app, ["show"])
        assert result.exit_code == 1
        assert "Could not detect shell type" in result.output

    def test_install_with_custom_path(self):
        """Test installing completion with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "completions" / "pltr.bash"
            result = runner.invoke(
                completion.app,
                ["install", "--shell", "bash", "--path", str(custom_path)],
            )
            assert result.exit_code == 0
            assert custom_path.exists()
            assert "_pltr_completion()" in custom_path.read_text()

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
                assert "No completion file found" in result.output

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
                assert "Removed completion file" in result.output


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
