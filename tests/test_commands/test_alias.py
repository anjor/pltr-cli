"""Tests for alias management commands using real AliasManager."""

import json
import tempfile
from pathlib import Path

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
def setup_alias_env(temp_config_dir, monkeypatch):
    """Set up environment for alias testing."""

    # Mock Settings class to return our temp directory
    class MockSettings:
        def __init__(self):
            self.config_dir = temp_config_dir

    # Patch the Settings import in config.aliases module
    monkeypatch.setattr("pltr.config.aliases.Settings", MockSettings)

    return temp_config_dir


class TestAliasCommandsReal:
    """Test alias commands with real AliasManager."""

    def test_add_command(self, runner, setup_alias_env):
        """Test adding a new alias."""
        result = runner.invoke(app, ["add", "ds", "dataset get"])
        assert result.exit_code == 0
        assert "Created alias" in result.stdout

        # Verify it was actually added
        result = runner.invoke(app, ["show", "ds"])
        assert result.exit_code == 0
        assert "dataset get" in result.stdout

    def test_add_existing_alias(self, runner, setup_alias_env):
        """Test adding an existing alias without force."""
        # First add an alias
        runner.invoke(app, ["add", "ds", "dataset get"])

        # Try to add it again
        result = runner.invoke(app, ["add", "ds", "dataset list"])
        assert result.exit_code == 1
        assert "already exists" in result.stdout

    def test_add_with_force(self, runner, setup_alias_env):
        """Test adding an existing alias with force."""
        # First add an alias
        runner.invoke(app, ["add", "ds", "dataset get"])

        # Overwrite with force
        result = runner.invoke(app, ["add", "ds", "dataset list", "--force"])
        assert result.exit_code == 0
        assert "Updated alias" in result.stdout

        # Verify it was updated
        result = runner.invoke(app, ["show", "ds"])
        assert "dataset list" in result.stdout

    def test_add_reserved_name(self, runner, setup_alias_env):
        """Test that reserved command names cannot be used as aliases."""
        result = runner.invoke(app, ["add", "configure", "some command"])
        assert result.exit_code == 1
        assert "reserved command name" in result.stdout

    def test_remove_command(self, runner, setup_alias_env):
        """Test removing an alias."""
        # First add an alias
        runner.invoke(app, ["add", "ds", "dataset get"])

        # Remove it
        result = runner.invoke(app, ["remove", "ds", "--no-confirm"])
        assert result.exit_code == 0
        assert "Removed alias" in result.stdout

        # Verify it's gone
        result = runner.invoke(app, ["show", "ds"])
        assert "not found" in result.stdout

    def test_remove_nonexistent(self, runner, setup_alias_env):
        """Test removing a non-existent alias."""
        result = runner.invoke(app, ["remove", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_edit_command(self, runner, setup_alias_env):
        """Test editing an alias."""
        # First add an alias
        runner.invoke(app, ["add", "ds", "dataset get"])

        # Edit it
        result = runner.invoke(app, ["edit", "ds", "dataset list"])
        assert result.exit_code == 0
        assert "Updated alias" in result.stdout

        # Verify it was updated
        result = runner.invoke(app, ["show", "ds"])
        assert "dataset list" in result.stdout

    def test_edit_nonexistent(self, runner, setup_alias_env):
        """Test editing a non-existent alias."""
        result = runner.invoke(app, ["edit", "nonexistent", "command"])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_list_command(self, runner, setup_alias_env):
        """Test listing aliases."""
        # Add some aliases
        runner.invoke(app, ["add", "ds", "dataset get"])
        runner.invoke(app, ["add", "sq", "sql execute"])

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "ds" in result.stdout
        assert "sq" in result.stdout

    def test_clear_command(self, runner, setup_alias_env):
        """Test clearing all aliases."""
        # Add some aliases
        runner.invoke(app, ["add", "ds", "dataset"])
        runner.invoke(app, ["add", "sq", "sql"])

        result = runner.invoke(app, ["clear", "--no-confirm"])
        assert result.exit_code == 0
        assert "Cleared 2 aliases" in result.stdout

        # Verify they're gone
        result = runner.invoke(app, ["list"])
        assert "No aliases" in result.stdout

    def test_export_command(self, runner, setup_alias_env):
        """Test exporting aliases to stdout."""
        # Add some aliases
        runner.invoke(app, ["add", "ds", "dataset get"])
        runner.invoke(app, ["add", "sq", "sql execute"])

        result = runner.invoke(app, ["export"])
        assert result.exit_code == 0
        exported = json.loads(result.stdout)
        assert exported == {"ds": "dataset get", "sq": "sql execute"}

    def test_export_to_file(self, runner, setup_alias_env, tmp_path):
        """Test exporting aliases to a file."""
        # Add an alias
        runner.invoke(app, ["add", "ds", "dataset get"])

        output_file = tmp_path / "aliases.json"
        result = runner.invoke(app, ["export", "--output", str(output_file)])
        assert result.exit_code == 0
        assert "Exported 1 aliases" in result.stdout

        with open(output_file) as f:
            data = json.load(f)
        assert data == {"ds": "dataset get"}

    def test_import_command(self, runner, setup_alias_env, tmp_path):
        """Test importing aliases from a file."""
        # Create import file
        import_file = tmp_path / "aliases.json"
        import_data = {"ds": "dataset get", "sq": "sql execute"}
        import_file.write_text(json.dumps(import_data))

        result = runner.invoke(app, ["import", str(import_file)])
        assert result.exit_code == 0
        assert "Imported 2 aliases" in result.stdout

        # Verify they were imported
        result = runner.invoke(app, ["list"])
        assert "ds" in result.stdout
        assert "sq" in result.stdout

    def test_resolve_command(self, runner, setup_alias_env):
        """Test resolving an alias."""
        # Add an alias
        runner.invoke(app, ["add", "ds", "dataset get"])

        result = runner.invoke(app, ["resolve", "ds"])
        assert result.exit_code == 0
        assert "dataset get" in result.stdout

    def test_resolve_not_alias(self, runner, setup_alias_env):
        """Test resolving a non-alias."""
        result = runner.invoke(app, ["resolve", "command"])
        assert result.exit_code == 0
        assert "is not an alias" in result.stdout

    def test_circular_reference_prevention(self, runner, setup_alias_env):
        """Test that circular references are prevented."""
        # Create a chain
        runner.invoke(app, ["add", "a", "b"])
        runner.invoke(app, ["add", "b", "c"])

        # Try to create a cycle
        result = runner.invoke(app, ["add", "c", "a"])
        assert result.exit_code == 1
        assert "circular reference" in result.stdout

    def test_nested_aliases(self, runner, setup_alias_env):
        """Test nested alias resolution."""
        # Create nested aliases
        runner.invoke(app, ["add", "a", "b"])
        runner.invoke(app, ["add", "b", "dataset get"])

        result = runner.invoke(app, ["resolve", "a"])
        assert result.exit_code == 0
        assert "dataset get" in result.stdout
