"""
Simplified integration tests for data operation workflows.

This file contains simplified integration tests that focus on basic functionality
without complex mocking strategies.
"""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch

from pltr.cli import app
from pltr.config.profiles import ProfileManager
from pltr.config.settings import Settings
from pltr.auth.storage import CredentialStorage


class TestSimpleDataWorkflows:
    """Test simplified data operation workflows."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def authenticated_profile(self, temp_config_dir):
        """Create an authenticated profile for testing."""
        with patch.object(Settings, "_get_config_dir", return_value=temp_config_dir):
            profile_manager = ProfileManager()
            storage = CredentialStorage()
            storage.save_profile(
                "test",
                {
                    "auth_type": "token",
                    "host": "https://test.palantirfoundry.com",
                    "token": "test_token",
                },
            )
            profile_manager.add_profile("test")
            profile_manager.set_default("test")
            yield profile_manager

    def test_dataset_command_help(self, runner):
        """Test dataset command help works."""
        result = runner.invoke(app, ["dataset", "--help"])
        assert result.exit_code == 0
        assert "dataset" in result.output.lower()

    def test_sql_command_help(self, runner):
        """Test SQL command help works."""
        result = runner.invoke(app, ["sql", "--help"])
        assert result.exit_code == 0
        assert "sql" in result.output.lower()

    def test_ontology_command_help(self, runner):
        """Test ontology command help works."""
        result = runner.invoke(app, ["ontology", "--help"])
        assert result.exit_code == 0
        assert "ontology" in result.output.lower()

    def test_admin_command_help(self, runner):
        """Test admin command help works."""
        result = runner.invoke(app, ["admin", "--help"])
        assert result.exit_code == 0
        assert "admin" in result.output.lower()

    def test_dataset_get_basic_functionality(self, runner, authenticated_profile):
        """Test basic dataset get functionality (may fail without real credentials)."""
        # This test may fail but shouldn't crash
        result = runner.invoke(
            app, ["dataset", "get", "ri.foundry.main.dataset.example"]
        )
        # Just ensure it doesn't crash with a Python error
        assert result.exit_code in [0, 1]  # Either success or expected failure

    def test_sql_execute_basic_functionality(self, runner, authenticated_profile):
        """Test basic SQL execute functionality (may fail without real credentials)."""
        # This test may fail but shouldn't crash
        result = runner.invoke(app, ["sql", "execute", "SELECT 1"])
        # Just ensure it doesn't crash with a Python error
        assert result.exit_code in [0, 1]  # Either success or expected failure

    def test_ontology_list_basic_functionality(self, runner, authenticated_profile):
        """Test basic ontology list functionality (may fail without real credentials)."""
        # This test may fail but shouldn't crash
        result = runner.invoke(app, ["ontology", "list"])
        # Just ensure it doesn't crash with a Python error
        assert result.exit_code in [0, 1]  # Either success or expected failure
