"""
Simple integration tests to verify basic CLI functionality.
"""

import pytest
from typer.testing import CliRunner

from pltr.cli import app


class TestSimpleIntegration:
    """Test basic CLI functionality."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    def test_help_command_works(self, runner):
        """Test that help command works."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "pltr" in result.output.lower() or "foundry" in result.output.lower()

    def test_configure_help_works(self, runner):
        """Test that configure help works."""
        result = runner.invoke(app, ["configure", "--help"])
        assert result.exit_code == 0
        assert "configure" in result.output.lower()

    def test_dataset_help_works(self, runner):
        """Test that dataset help works."""
        result = runner.invoke(app, ["dataset", "--help"])
        assert result.exit_code == 0
        assert "dataset" in result.output.lower()

    def test_sql_help_works(self, runner):
        """Test that sql help works."""
        result = runner.invoke(app, ["sql", "--help"])
        assert result.exit_code == 0
        assert "sql" in result.output.lower()

    def test_ontology_help_works(self, runner):
        """Test that ontology help works."""
        result = runner.invoke(app, ["ontology", "--help"])
        assert result.exit_code == 0
        assert "ontology" in result.output.lower()

    def test_admin_help_works(self, runner):
        """Test that admin help works."""
        result = runner.invoke(app, ["admin", "--help"])
        assert result.exit_code == 0
        assert "admin" in result.output.lower()
