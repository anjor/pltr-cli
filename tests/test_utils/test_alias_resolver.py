"""Tests for alias resolution utilities."""

import sys
from unittest.mock import MagicMock, patch


from pltr.utils.alias_resolver import resolve_command_aliases, inject_alias_resolution


class TestAliasResolver:
    """Test alias resolution functionality."""

    def test_resolve_empty_args(self):
        """Test resolving empty arguments."""
        assert resolve_command_aliases([]) == []

    def test_resolve_no_alias(self):
        """Test resolving when no alias exists."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            manager = MagicMock()
            manager.resolve_alias.return_value = "dataset"
            mock_manager.return_value = manager

            args = ["dataset", "get", "rid"]
            result = resolve_command_aliases(args)
            assert result == args
            manager.resolve_alias.assert_called_once_with("dataset")

    def test_resolve_simple_alias(self):
        """Test resolving a simple alias."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            manager = MagicMock()
            manager.resolve_alias.return_value = "dataset get"
            mock_manager.return_value = manager

            args = ["ds", "rid"]
            result = resolve_command_aliases(args)
            assert result == ["dataset", "get", "rid"]

    def test_resolve_complex_alias(self):
        """Test resolving an alias with multiple parts."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            manager = MagicMock()
            manager.resolve_alias.return_value = "sql execute --format json"
            mock_manager.return_value = manager

            args = ["sq", "SELECT * FROM table"]
            result = resolve_command_aliases(args)
            assert result == [
                "sql",
                "execute",
                "--format",
                "json",
                "SELECT * FROM table",
            ]

    def test_resolve_alias_with_quotes(self):
        """Test resolving an alias containing quoted arguments."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            manager = MagicMock()
            manager.resolve_alias.return_value = 'dataset create "My Dataset"'
            mock_manager.return_value = manager

            args = ["dc", "--parent", "folder-rid"]
            result = resolve_command_aliases(args)
            assert result == [
                "dataset",
                "create",
                "My Dataset",
                "--parent",
                "folder-rid",
            ]

    def test_skip_alias_command(self):
        """Test that 'alias' command itself is not resolved."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            args = ["alias", "add", "ds", "dataset"]
            result = resolve_command_aliases(args)
            assert result == args
            mock_manager.return_value.resolve_alias.assert_not_called()

    def test_skip_help_command(self):
        """Test that help commands are not resolved."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            args = ["--help"]
            result = resolve_command_aliases(args)
            assert result == args
            mock_manager.return_value.resolve_alias.assert_not_called()

            args = ["-h"]
            result = resolve_command_aliases(args)
            assert result == args

    def test_skip_version_command(self):
        """Test that version command is not resolved."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            args = ["--version"]
            result = resolve_command_aliases(args)
            assert result == args
            mock_manager.return_value.resolve_alias.assert_not_called()

    def test_skip_completion_command(self):
        """Test that completion command is not resolved."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            args = ["completion", "install"]
            result = resolve_command_aliases(args)
            assert result == args
            mock_manager.return_value.resolve_alias.assert_not_called()

    def test_invalid_alias_syntax(self):
        """Test handling of invalid alias syntax."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            manager = MagicMock()
            # Return an alias with invalid shell syntax
            manager.resolve_alias.return_value = 'invalid "unclosed quote'
            mock_manager.return_value = manager

            args = ["bad", "arg"]
            result = resolve_command_aliases(args)
            # Should return original args when parsing fails
            assert result == args

    def test_resolve_from_sys_argv(self):
        """Test resolving from sys.argv when no args provided."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            manager = MagicMock()
            manager.resolve_alias.return_value = "dataset get"
            mock_manager.return_value = manager

            original_argv = sys.argv
            try:
                sys.argv = ["pltr", "ds", "rid"]
                result = resolve_command_aliases()
                assert result == ["dataset", "get", "rid"]
            finally:
                sys.argv = original_argv

    def test_inject_alias_resolution(self):
        """Test injecting alias resolution into sys.argv."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            manager = MagicMock()
            manager.resolve_alias.return_value = "dataset get"
            mock_manager.return_value = manager

            original_argv = sys.argv
            try:
                sys.argv = ["pltr", "ds", "rid"]
                inject_alias_resolution()
                assert sys.argv == ["pltr", "dataset", "get", "rid"]
            finally:
                sys.argv = original_argv

    def test_nested_alias_resolution(self):
        """Test that nested aliases are fully resolved."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            manager = MagicMock()
            # The manager should handle nested resolution internally
            manager.resolve_alias.return_value = "sql execute --format table"
            mock_manager.return_value = manager

            args = ["query", "SELECT 1"]
            result = resolve_command_aliases(args)
            assert result == ["sql", "execute", "--format", "table", "SELECT 1"]

    def test_alias_with_empty_resolution(self):
        """Test alias that resolves to same value (no change)."""
        with patch("pltr.utils.alias_resolver.AliasManager") as mock_manager:
            manager = MagicMock()
            manager.resolve_alias.return_value = "normalcommand"
            mock_manager.return_value = manager

            args = ["normalcommand", "arg1", "arg2"]
            result = resolve_command_aliases(args)
            assert result == args
