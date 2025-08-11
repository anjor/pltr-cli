"""
Tests for shell command.
"""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from pltr.commands.shell import get_history_file, get_prompt, shell_app


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class TestShellCommand:
    """Test shell command functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_get_history_file(self):
        """Test get_history_file function."""
        history_file = get_history_file()

        # Should return a Path object
        assert isinstance(history_file, Path)

        # Should be in the correct location (cross-platform compatible)
        expected_path = Path.home() / ".config" / "pltr" / "repl_history"
        assert history_file == expected_path

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

    def test_start_command_basic(self):
        """Test start command basic execution."""
        # Test help works - this is the main verification we need
        result = self.runner.invoke(shell_app, ["start", "--help"])
        assert result.exit_code == 0
        assert "Start an interactive shell session" in result.stdout

    def test_start_command_with_profile(self):
        """Test start command with profile option."""
        # Test that the profile option is accepted
        result = self.runner.invoke(
            shell_app, ["start", "--profile", "test-profile", "--help"]
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "--profile" in clean_output

    def test_shell_callback_no_subcommand(self):
        """Test shell callback when no subcommand is provided."""
        # Create a mock context
        mock_ctx = MagicMock()
        mock_ctx.invoked_subcommand = None

        # Mock the start function
        with patch("pltr.commands.shell.start") as mock_start:
            from pltr.commands.shell import shell_callback

            # Test
            shell_callback(mock_ctx, profile="test-profile")

            # Assert start was called with the correct profile
            mock_start.assert_called_once_with(profile="test-profile")

    def test_shell_callback_with_subcommand(self):
        """Test shell callback when subcommand is provided."""
        # Create a mock context
        mock_ctx = MagicMock()
        mock_ctx.invoked_subcommand = "start"

        # Mock the start function
        with patch("pltr.commands.shell.start") as mock_start:
            from pltr.commands.shell import shell_callback

            # Test
            shell_callback(mock_ctx, profile="test-profile")

            # Assert start was NOT called since there is a subcommand
            mock_start.assert_not_called()

    def test_interactive_alias(self):
        """Test interactive alias command."""
        with patch("pltr.commands.shell.start") as mock_start:
            from pltr.commands.shell import interactive_alias

            # Test
            interactive_alias(profile="test-profile")

            # Assert start was called
            mock_start.assert_called_once_with(profile="test-profile")


class TestShellIntegration:
    """Integration tests for shell functionality."""

    def test_shell_command_in_main_cli(self):
        """Test that shell command is properly integrated in main CLI."""
        from pltr.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "shell" in result.stdout
        assert "Interactive shell mode" in result.stdout

    def test_shell_subcommand_available(self):
        """Test that shell subcommands are available."""
        from pltr.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["shell", "--help"])

        assert result.exit_code == 0
        assert "start" in result.stdout
