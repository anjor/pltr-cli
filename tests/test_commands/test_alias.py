"""Tests for alias management commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from pltr.commands.alias import app


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_alias_manager(temp_config_dir):
    """Mock AliasManager for testing."""
    with patch("pltr.commands.alias.AliasManager") as mock:
        manager = MagicMock()
        manager.aliases = {}
        # Create proper mock methods that can be asserted
        manager.get_alias = MagicMock(
            side_effect=lambda name: manager.aliases.get(name)
        )
        manager.list_aliases = MagicMock(side_effect=lambda: manager.aliases.copy())
        manager.add_alias = MagicMock(return_value=True)
        manager.edit_alias = MagicMock(return_value=True)
        manager.remove_alias = MagicMock(return_value=True)
        manager.clear_all = MagicMock(return_value=0)
        manager.import_aliases = MagicMock(return_value=0)
        manager.export_aliases = MagicMock(return_value={})
        manager.resolve_alias = MagicMock(side_effect=lambda x: x)
        manager.display_aliases = MagicMock()
        mock.return_value = manager
        yield manager


class TestAliasCommands:
    """Test alias command functionality."""

    def test_add_command(self, runner, mock_alias_manager):
        """Test adding a new alias."""
        mock_alias_manager.add_alias.return_value = True
        mock_alias_manager.get_alias.return_value = None

        result = runner.invoke(app, ["add", "ds", "dataset get"])
        assert result.exit_code == 0
        assert "Created alias" in result.stdout
        mock_alias_manager.add_alias.assert_called_once_with("ds", "dataset get")

    def test_add_existing_alias(self, runner, mock_alias_manager):
        """Test adding an existing alias without force."""
        mock_alias_manager.get_alias.return_value = "existing command"

        result = runner.invoke(app, ["add", "ds", "dataset get"])
        assert result.exit_code == 1
        assert "already exists" in result.stdout

    def test_add_with_force(self, runner, mock_alias_manager):
        """Test adding an existing alias with force."""
        mock_alias_manager.get_alias.return_value = "existing command"
        mock_alias_manager.edit_alias.return_value = True

        result = runner.invoke(app, ["add", "ds", "dataset get", "--force"])
        assert result.exit_code == 0
        assert "Updated alias" in result.stdout
        mock_alias_manager.edit_alias.assert_called_once_with("ds", "dataset get")

    def test_add_reserved_name(self, runner, mock_alias_manager):
        """Test that reserved command names cannot be used as aliases."""
        result = runner.invoke(app, ["add", "configure", "some command"])
        assert result.exit_code == 1
        assert "reserved command name" in result.stdout

    def test_add_circular_reference(self, runner, mock_alias_manager):
        """Test handling circular reference errors."""
        mock_alias_manager.get_alias.return_value = None
        mock_alias_manager.add_alias.side_effect = ValueError("circular reference")

        result = runner.invoke(app, ["add", "a", "b"])
        assert result.exit_code == 1
        assert "circular reference" in result.stdout

    def test_remove_command(self, runner, mock_alias_manager):
        """Test removing an alias."""
        mock_alias_manager.get_alias.return_value = "dataset get"
        mock_alias_manager.remove_alias.return_value = True

        result = runner.invoke(app, ["remove", "ds", "--no-confirm"])
        assert result.exit_code == 0
        assert "Removed alias" in result.stdout
        mock_alias_manager.remove_alias.assert_called_once_with("ds")

    def test_remove_nonexistent(self, runner, mock_alias_manager):
        """Test removing a non-existent alias."""
        mock_alias_manager.get_alias.return_value = None

        result = runner.invoke(app, ["remove", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_remove_with_confirmation(self, runner, mock_alias_manager):
        """Test remove command with confirmation prompt."""
        mock_alias_manager.get_alias.return_value = "dataset get"
        mock_alias_manager.remove_alias.return_value = True

        # Simulate user confirming
        result = runner.invoke(app, ["remove", "ds"], input="y\n")
        assert result.exit_code == 0
        assert "Removed alias" in result.stdout

        # Simulate user cancelling
        result = runner.invoke(app, ["remove", "ds"], input="n\n")
        assert result.exit_code == 0
        assert "cancelled" in result.stdout

    def test_edit_command(self, runner, mock_alias_manager):
        """Test editing an alias."""
        mock_alias_manager.get_alias.return_value = "old command"
        mock_alias_manager.edit_alias.return_value = True

        result = runner.invoke(app, ["edit", "ds", "new command"])
        assert result.exit_code == 0
        assert "Updated alias" in result.stdout
        mock_alias_manager.edit_alias.assert_called_once_with("ds", "new command")

    def test_edit_nonexistent(self, runner, mock_alias_manager):
        """Test editing a non-existent alias."""
        mock_alias_manager.get_alias.return_value = None

        result = runner.invoke(app, ["edit", "nonexistent", "command"])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_list_command(self, runner, mock_alias_manager):
        """Test listing aliases."""
        mock_alias_manager.display_aliases = MagicMock()

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        mock_alias_manager.display_aliases.assert_called_once_with()

    def test_show_command(self, runner, mock_alias_manager):
        """Test showing a specific alias."""
        mock_alias_manager.display_aliases = MagicMock()

        result = runner.invoke(app, ["show", "ds"])
        assert result.exit_code == 0
        mock_alias_manager.display_aliases.assert_called_once_with("ds")

    def test_clear_command(self, runner, mock_alias_manager):
        """Test clearing all aliases."""
        mock_alias_manager.list_aliases.return_value = {"ds": "dataset", "sq": "sql"}
        mock_alias_manager.clear_all.return_value = 2

        result = runner.invoke(app, ["clear", "--no-confirm"])
        assert result.exit_code == 0
        assert "Cleared 2 aliases" in result.stdout
        mock_alias_manager.clear_all.assert_called_once()

    def test_clear_empty(self, runner, mock_alias_manager):
        """Test clearing when no aliases exist."""
        mock_alias_manager.list_aliases.return_value = {}

        result = runner.invoke(app, ["clear"])
        assert result.exit_code == 0
        assert "No aliases to clear" in result.stdout

    def test_export_command(self, runner, mock_alias_manager):
        """Test exporting aliases to stdout."""
        mock_alias_manager.export_aliases.return_value = {
            "ds": "dataset get",
            "sq": "sql execute",
        }

        result = runner.invoke(app, ["export"])
        assert result.exit_code == 0
        exported = json.loads(result.stdout)
        assert exported == {"ds": "dataset get", "sq": "sql execute"}

    def test_export_to_file(self, runner, mock_alias_manager, tmp_path):
        """Test exporting aliases to a file."""
        mock_alias_manager.export_aliases.return_value = {"ds": "dataset get"}
        output_file = tmp_path / "aliases.json"

        result = runner.invoke(app, ["export", "--output", str(output_file)])
        assert result.exit_code == 0
        assert "Exported 1 aliases" in result.stdout

        with open(output_file) as f:
            data = json.load(f)
        assert data == {"ds": "dataset get"}

    def test_export_empty(self, runner, mock_alias_manager):
        """Test exporting when no aliases exist."""
        mock_alias_manager.export_aliases.return_value = {}

        result = runner.invoke(app, ["export"])
        assert result.exit_code == 0
        assert "No aliases to export" in result.stdout

    def test_import_command(self, runner, mock_alias_manager, tmp_path):
        """Test importing aliases from a file."""
        import_file = tmp_path / "aliases.json"
        import_data = {"ds": "dataset get", "sq": "sql execute"}
        import_file.write_text(json.dumps(import_data))

        mock_alias_manager.list_aliases.return_value = {}
        mock_alias_manager.import_aliases.return_value = 2

        result = runner.invoke(app, ["import", str(import_file)])
        assert result.exit_code == 0
        assert "Imported 2 aliases" in result.stdout
        mock_alias_manager.import_aliases.assert_called_once_with(import_data)

    def test_import_merge(self, runner, mock_alias_manager, tmp_path):
        """Test importing aliases with merge option."""
        import_file = tmp_path / "aliases.json"
        import_data = {"new": "command"}
        import_file.write_text(json.dumps(import_data))

        mock_alias_manager.list_aliases.return_value = {"existing": "command"}
        mock_alias_manager.import_aliases.return_value = 1

        result = runner.invoke(app, ["import", str(import_file), "--merge"])
        assert result.exit_code == 0
        assert "Imported 1 aliases" in result.stdout
        # Should not clear existing aliases
        mock_alias_manager.clear_all.assert_not_called()

    def test_import_replace(self, runner, mock_alias_manager, tmp_path):
        """Test importing aliases with replace (default) option."""
        import_file = tmp_path / "aliases.json"
        import_data = {"new": "command"}
        import_file.write_text(json.dumps(import_data))

        mock_alias_manager.list_aliases.return_value = {"existing": "command"}
        mock_alias_manager.import_aliases.return_value = 1

        result = runner.invoke(app, ["import", str(import_file)], input="y\n")
        assert result.exit_code == 0
        assert "Imported 1 aliases" in result.stdout
        mock_alias_manager.clear_all.assert_called_once()

    def test_import_invalid_file(self, runner, mock_alias_manager, tmp_path):
        """Test importing from invalid file."""
        import_file = tmp_path / "invalid.json"
        import_file.write_text("not valid json")

        result = runner.invoke(app, ["import", str(import_file)])
        assert result.exit_code == 1
        assert "Error reading file" in result.stdout

    def test_import_invalid_format(self, runner, mock_alias_manager, tmp_path):
        """Test importing invalid format."""
        import_file = tmp_path / "aliases.json"
        import_file.write_text('"not an object"')

        result = runner.invoke(app, ["import", str(import_file)])
        assert result.exit_code == 1
        assert "Invalid format" in result.stdout

    def test_resolve_command(self, runner, mock_alias_manager):
        """Test resolving an alias."""
        mock_alias_manager.resolve_alias.return_value = "dataset get"
        mock_alias_manager.list_aliases.return_value = {"ds": "dataset get"}

        result = runner.invoke(app, ["resolve", "ds"])
        assert result.exit_code == 0
        assert "dataset get" in result.stdout

    def test_resolve_not_alias(self, runner, mock_alias_manager):
        """Test resolving a non-alias."""
        mock_alias_manager.resolve_alias.return_value = "command"
        mock_alias_manager.list_aliases.return_value = {}

        result = runner.invoke(app, ["resolve", "command"])
        assert result.exit_code == 0
        assert "is not an alias" in result.stdout

    def test_resolve_circular(self, runner, mock_alias_manager):
        """Test resolving a circular alias."""
        mock_alias_manager.resolve_alias.return_value = "a"
        mock_alias_manager.list_aliases.return_value = {"a": "b", "b": "a"}

        result = runner.invoke(app, ["resolve", "a"])
        assert result.exit_code == 0
        assert "circular references" in result.stdout
