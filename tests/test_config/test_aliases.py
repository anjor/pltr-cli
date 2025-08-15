"""Tests for alias configuration management."""

import tempfile
from pathlib import Path

import pytest

from pltr.config.aliases import AliasManager


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def alias_manager(temp_config_dir, monkeypatch):
    """Create an AliasManager with a temporary config directory."""

    # Mock Settings class to return our temp directory
    class MockSettings:
        def __init__(self):
            self.config_dir = temp_config_dir

    monkeypatch.setattr("pltr.config.aliases.Settings", MockSettings)
    return AliasManager()


class TestAliasManager:
    """Test AliasManager functionality."""

    def test_init_creates_empty_aliases(self, alias_manager):
        """Test that initialization creates empty aliases."""
        assert alias_manager.aliases == {}
        assert not alias_manager.aliases_file.exists()

    def test_add_alias(self, alias_manager):
        """Test adding a new alias."""
        assert alias_manager.add_alias("ds", "dataset get")
        assert alias_manager.aliases["ds"] == "dataset get"
        assert alias_manager.aliases_file.exists()

    def test_add_duplicate_alias(self, alias_manager):
        """Test that adding a duplicate alias returns False."""
        alias_manager.add_alias("ds", "dataset get")
        assert not alias_manager.add_alias("ds", "dataset list")
        assert alias_manager.aliases["ds"] == "dataset get"

    def test_remove_alias(self, alias_manager):
        """Test removing an alias."""
        alias_manager.add_alias("ds", "dataset get")
        assert alias_manager.remove_alias("ds")
        assert "ds" not in alias_manager.aliases

    def test_remove_nonexistent_alias(self, alias_manager):
        """Test removing a non-existent alias returns False."""
        assert not alias_manager.remove_alias("nonexistent")

    def test_edit_alias(self, alias_manager):
        """Test editing an existing alias."""
        alias_manager.add_alias("ds", "dataset get")
        assert alias_manager.edit_alias("ds", "dataset list")
        assert alias_manager.aliases["ds"] == "dataset list"

    def test_edit_nonexistent_alias(self, alias_manager):
        """Test editing a non-existent alias returns False."""
        assert not alias_manager.edit_alias("nonexistent", "command")

    def test_get_alias(self, alias_manager):
        """Test getting an alias."""
        alias_manager.add_alias("ds", "dataset get")
        assert alias_manager.get_alias("ds") == "dataset get"
        assert alias_manager.get_alias("nonexistent") is None

    def test_list_aliases(self, alias_manager):
        """Test listing all aliases."""
        alias_manager.add_alias("ds", "dataset get")
        alias_manager.add_alias("sq", "sql execute")
        aliases = alias_manager.list_aliases()
        assert aliases == {"ds": "dataset get", "sq": "sql execute"}

    def test_resolve_simple_alias(self, alias_manager):
        """Test resolving a simple alias."""
        alias_manager.add_alias("ds", "dataset get")
        assert alias_manager.resolve_alias("ds") == "dataset get"
        assert alias_manager.resolve_alias("other") == "other"

    def test_resolve_nested_alias(self, alias_manager):
        """Test resolving nested aliases."""
        alias_manager.add_alias("ds", "dataset")
        alias_manager.add_alias("dataset", "dataset get")
        assert alias_manager.resolve_alias("ds") == "dataset get"

    def test_resolve_circular_alias(self, alias_manager):
        """Test that circular aliases are detected."""
        alias_manager.aliases = {"a": "b", "b": "c", "c": "a"}
        alias_manager._save_aliases()
        # Should return original command when circular
        assert alias_manager.resolve_alias("a") == "a"

    def test_would_create_cycle(self, alias_manager):
        """Test cycle detection."""
        alias_manager.add_alias("b", "c")
        alias_manager.add_alias("c", "d")
        assert alias_manager._would_create_cycle("a", "b") is False
        assert alias_manager._would_create_cycle("d", "b") is True

    def test_add_alias_prevents_cycle(self, alias_manager):
        """Test that adding an alias that would create a cycle raises an error."""
        alias_manager.add_alias("b", "c")
        alias_manager.add_alias("c", "d")
        with pytest.raises(ValueError, match="circular reference"):
            alias_manager.add_alias("d", "b")

    def test_clear_all(self, alias_manager):
        """Test clearing all aliases."""
        alias_manager.add_alias("ds", "dataset get")
        alias_manager.add_alias("sq", "sql execute")
        count = alias_manager.clear_all()
        assert count == 2
        assert alias_manager.aliases == {}

    def test_import_aliases(self, alias_manager):
        """Test importing aliases."""
        data = {"ds": "dataset get", "sq": "sql execute"}
        count = alias_manager.import_aliases(data)
        assert count == 2
        assert alias_manager.aliases == data

    def test_import_aliases_skip_cycles(self, alias_manager):
        """Test that import skips aliases that would create cycles."""
        alias_manager.add_alias("a", "b")
        # Initial state: a -> b
        # Trying to import: b -> c (safe), c -> a (would create cycle a->b->c->a)
        data = {"b": "c", "c": "a"}
        count = alias_manager.import_aliases(data)
        # b -> c is safe to import
        # c -> a would create cycle, should be skipped
        assert count == 1  # Only "b": "c" should be imported
        assert alias_manager.aliases["a"] == "b"
        assert alias_manager.aliases["b"] == "c"
        assert "c" not in alias_manager.aliases

    def test_export_aliases(self, alias_manager):
        """Test exporting aliases."""
        alias_manager.add_alias("ds", "dataset get")
        alias_manager.add_alias("sq", "sql execute")
        exported = alias_manager.export_aliases()
        assert exported == {"ds": "dataset get", "sq": "sql execute"}

    def test_get_completion_items(self, alias_manager):
        """Test getting completion items."""
        alias_manager.add_alias("ds", "dataset get")
        alias_manager.add_alias("sq", "sql execute")
        items = alias_manager.get_completion_items()
        assert sorted(items) == ["ds", "sq"]

    def test_persistence(self, temp_config_dir, monkeypatch):
        """Test that aliases persist across manager instances."""

        # Mock Settings class to return our temp directory
        class MockSettings:
            def __init__(self):
                self.config_dir = temp_config_dir

        monkeypatch.setattr("pltr.config.aliases.Settings", MockSettings)

        # Create first manager and add aliases
        manager1 = AliasManager()
        manager1.add_alias("ds", "dataset get")

        # Create second manager and check aliases are loaded
        manager2 = AliasManager()
        assert manager2.get_alias("ds") == "dataset get"

    def test_display_aliases(self, alias_manager, capsys):
        """Test displaying aliases."""
        # Test empty aliases
        alias_manager.display_aliases()
        captured = capsys.readouterr()
        assert "No aliases configured" in captured.out

        # Test with aliases
        alias_manager.add_alias("ds", "dataset get")
        alias_manager.display_aliases()
        captured = capsys.readouterr()
        # Rich table output varies, just check key content
        assert "ds" in captured.out or "Command Aliases" in captured.out

    def test_display_specific_alias(self, alias_manager, capsys):
        """Test displaying a specific alias."""
        alias_manager.add_alias("ds", "dataset get")
        alias_manager.display_aliases("ds")
        captured = capsys.readouterr()
        assert "dataset get" in captured.out

        # Test nonexistent alias
        alias_manager.display_aliases("nonexistent")
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_corrupted_aliases_file(self, temp_config_dir, monkeypatch):
        """Test handling of corrupted aliases file."""

        # Mock Settings class to return our temp directory
        class MockSettings:
            def __init__(self):
                self.config_dir = temp_config_dir

        monkeypatch.setattr("pltr.config.aliases.Settings", MockSettings)

        # Create corrupted file
        aliases_file = temp_config_dir / "aliases.json"
        aliases_file.write_text("not valid json")

        # Should handle gracefully and start with empty aliases
        manager = AliasManager()
        assert manager.aliases == {}
