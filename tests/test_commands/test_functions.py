"""Tests for Functions commands."""

import pytest
from unittest.mock import Mock, patch, mock_open
from typer.testing import CliRunner
from pltr.cli import app


class TestFunctionsCommands:
    """Test Functions CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock FunctionsService."""
        with patch("pltr.commands.functions.FunctionsService") as MockService:
            mock_svc = Mock()
            MockService.return_value = mock_svc
            yield mock_svc

    # ===== Query Get Tests =====

    def test_query_get_success(self, runner, mock_service):
        """Test successful get query command."""
        # Setup
        query_result = {
            "rid": "ri.functions.main.query.abc123",
            "apiName": "myQuery",
            "version": "1.0.0",
            "parameters": {"limit": "integer"},
        }
        mock_service.get_query.return_value = query_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "get",
                "myQuery",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_query.assert_called_once_with(
            "myQuery", preview=False, version=None
        )

    def test_query_get_with_version(self, runner, mock_service):
        """Test get query with specific version."""
        # Setup
        query_result = {
            "rid": "ri.functions.main.query.abc123",
            "apiName": "myQuery",
            "version": "2.0.0",
        }
        mock_service.get_query.return_value = query_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "get",
                "myQuery",
                "--version",
                "2.0.0",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_query.assert_called_once_with(
            "myQuery", preview=False, version="2.0.0"
        )

    def test_query_get_with_preview(self, runner, mock_service):
        """Test get query with preview mode."""
        # Setup
        query_result = {"rid": "ri.functions.main.query.abc123", "apiName": "myQuery"}
        mock_service.get_query.return_value = query_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "get",
                "myQuery",
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_query.assert_called_once_with(
            "myQuery", preview=True, version=None
        )

    def test_query_get_with_profile(self, runner, mock_service):
        """Test get query with profile option."""
        # Setup
        query_result = {"rid": "ri.functions.main.query.abc123", "apiName": "myQuery"}
        mock_service.get_query.return_value = query_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "get",
                "myQuery",
                "--profile",
                "test-profile",
            ],
        )

        # Assert
        assert result.exit_code == 0
        # Verify service was initialized with profile
        from pltr.commands.functions import FunctionsService

        FunctionsService.assert_called_with(profile="test-profile")

    def test_query_get_error(self, runner, mock_service):
        """Test get query command with service error."""
        # Setup
        mock_service.get_query.side_effect = RuntimeError("Query not found")

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "get",
                "invalidQuery",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get query" in result.stdout

    # ===== Query Get-By-RID Tests =====

    def test_query_get_by_rid_success(self, runner, mock_service):
        """Test successful get query by RID command."""
        # Setup
        query_result = {
            "rid": "ri.functions.main.query.abc123",
            "apiName": "myQuery",
            "version": "1.0.0",
        }
        mock_service.get_query_by_rid.return_value = query_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "get-by-rid",
                "ri.functions.main.query.abc123",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_query_by_rid.assert_called_once_with(
            "ri.functions.main.query.abc123", preview=False, version=None
        )

    def test_query_get_by_rid_permission_denied(self, runner, mock_service):
        """Test get query by RID with permission denied error."""
        # Setup
        mock_service.get_query_by_rid.side_effect = RuntimeError("Permission denied")

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "get-by-rid",
                "ri.functions.main.query.abc123",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get query" in result.stdout

    # ===== Query Execute Tests =====

    def test_query_execute_success(self, runner, mock_service):
        """Test successful execute query command."""
        # Setup
        execute_result = {"result": [{"id": 1, "name": "Test"}]}
        mock_service.execute_query.return_value = execute_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "execute",
                "myQuery",
                "--parameters",
                '{"limit": 10}',
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.execute_query.assert_called_once_with(
            "myQuery",
            parameters={"limit": 10},
            preview=False,
            version=None,
        )

    def test_query_execute_with_file_parameters(self, runner, mock_service):
        """Test execute query with parameters from file."""
        # Setup
        execute_result = {"result": [{"id": 1}]}
        mock_service.execute_query.return_value = execute_result

        params_content = '{"limit": 100, "filter": "active"}'

        # Execute with file mock
        with patch("builtins.open", mock_open(read_data=params_content)):
            with patch("pathlib.Path.exists", return_value=True):
                result = runner.invoke(
                    app,
                    [
                        "functions",
                        "query",
                        "execute",
                        "myQuery",
                        "--parameters",
                        "@params.json",
                    ],
                )

        # Assert
        assert result.exit_code == 0
        mock_service.execute_query.assert_called_once_with(
            "myQuery",
            parameters={"limit": 100, "filter": "active"},
            preview=False,
            version=None,
        )

    def test_query_execute_with_version(self, runner, mock_service):
        """Test execute query with specific version."""
        # Setup
        execute_result = {"result": []}
        mock_service.execute_query.return_value = execute_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "execute",
                "myQuery",
                "--version",
                "1.5.0",
                "--parameters",
                "{}",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.execute_query.assert_called_once_with(
            "myQuery",
            parameters={},
            preview=False,
            version="1.5.0",
        )

    def test_query_execute_with_preview(self, runner, mock_service):
        """Test execute query with preview mode."""
        # Setup
        execute_result = {"result": []}
        mock_service.execute_query.return_value = execute_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "execute",
                "myQuery",
                "--preview",
                "--parameters",
                "{}",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.execute_query.assert_called_once_with(
            "myQuery",
            parameters={},
            preview=True,
            version=None,
        )

    def test_query_execute_invalid_json(self, runner, mock_service):
        """Test execute query with invalid JSON parameters."""
        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "execute",
                "myQuery",
                "--parameters",
                "{invalid json}",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Invalid JSON in parameters" in result.stdout

    def test_query_execute_file_not_found(self, runner, mock_service):
        """Test execute query with non-existent parameter file."""
        # Execute with file not found
        with patch("pathlib.Path.exists", return_value=False):
            result = runner.invoke(
                app,
                [
                    "functions",
                    "query",
                    "execute",
                    "myQuery",
                    "--parameters",
                    "@missing.json",
                ],
            )

        # Assert
        assert result.exit_code == 1
        assert "Parameter file not found" in result.stdout

    def test_query_execute_permission_denied(self, runner, mock_service):
        """Test execute query with permission denied error."""
        # Setup
        mock_service.execute_query.side_effect = RuntimeError(
            "ExecuteQueryPermissionDenied"
        )

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "execute",
                "myQuery",
                "--parameters",
                "{}",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to execute query" in result.stdout

    def test_query_execute_no_parameters(self, runner, mock_service):
        """Test execute query without parameters."""
        # Setup
        execute_result = {"result": []}
        mock_service.execute_query.return_value = execute_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "execute",
                "myQuery",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.execute_query.assert_called_once_with(
            "myQuery",
            parameters=None,
            preview=False,
            version=None,
        )

    # ===== Query Execute-By-RID Tests =====

    def test_query_execute_by_rid_success(self, runner, mock_service):
        """Test successful execute query by RID command."""
        # Setup
        execute_result = {"result": [{"id": 1}]}
        mock_service.execute_query_by_rid.return_value = execute_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "execute-by-rid",
                "ri.functions.main.query.abc123",
                "--parameters",
                '{"limit": 10}',
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.execute_query_by_rid.assert_called_once_with(
            "ri.functions.main.query.abc123",
            parameters={"limit": 10},
            preview=False,
            version=None,
        )

    # ===== Value Type Tests =====

    def test_value_type_get_success(self, runner, mock_service):
        """Test successful get value type command."""
        # Setup
        value_type_result = {
            "rid": "ri.functions.main.value-type.xyz",
            "apiName": "MyValueType",
            "definition": {"type": "struct"},
        }
        mock_service.get_value_type.return_value = value_type_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "value-type",
                "get",
                "ri.functions.main.value-type.xyz",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_value_type.assert_called_once_with(
            "ri.functions.main.value-type.xyz", preview=False
        )

    def test_value_type_get_with_preview(self, runner, mock_service):
        """Test get value type with preview mode."""
        # Setup
        value_type_result = {
            "rid": "ri.functions.main.value-type.xyz",
            "apiName": "MyValueType",
        }
        mock_service.get_value_type.return_value = value_type_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "value-type",
                "get",
                "ri.functions.main.value-type.xyz",
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_value_type.assert_called_once_with(
            "ri.functions.main.value-type.xyz", preview=True
        )

    def test_value_type_get_not_found(self, runner, mock_service):
        """Test get value type with not found error."""
        # Setup
        mock_service.get_value_type.side_effect = RuntimeError("ValueTypeNotFound")

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "value-type",
                "get",
                "ri.functions.main.value-type.invalid",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Failed to get value type" in result.stdout

    def test_value_type_get_with_profile(self, runner, mock_service):
        """Test get value type with profile option."""
        # Setup
        value_type_result = {
            "rid": "ri.functions.main.value-type.xyz",
            "apiName": "MyValueType",
        }
        mock_service.get_value_type.return_value = value_type_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "value-type",
                "get",
                "ri.functions.main.value-type.xyz",
                "--profile",
                "test-profile",
            ],
        )

        # Assert
        assert result.exit_code == 0
        # Verify service was initialized with profile
        from pltr.commands.functions import FunctionsService

        FunctionsService.assert_called_with(profile="test-profile")

    # ===== Output Format Tests =====

    def test_query_get_output_csv(self, runner, mock_service):
        """Test query get with CSV output format."""
        # Setup
        query_result = {"rid": "ri.functions.main.query.abc123", "apiName": "myQuery"}
        mock_service.get_query.return_value = query_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "get",
                "myQuery",
                "--format",
                "csv",
            ],
        )

        # Assert
        assert result.exit_code == 0

    def test_query_execute_output_table(self, runner, mock_service):
        """Test query execute with table output format."""
        # Setup
        execute_result = {"result": [{"id": 1, "name": "Test"}]}
        mock_service.execute_query.return_value = execute_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "execute",
                "myQuery",
                "--parameters",
                "{}",
                "--format",
                "table",
            ],
        )

        # Assert
        assert result.exit_code == 0

    # ===== File Output Tests =====

    def test_query_get_with_output_file(self, runner, mock_service):
        """Test query get with output file."""
        # Setup
        query_result = {"rid": "ri.functions.main.query.abc123", "apiName": "myQuery"}
        mock_service.get_query.return_value = query_result

        # Execute
        result = runner.invoke(
            app,
            [
                "functions",
                "query",
                "get",
                "myQuery",
                "--output",
                "output.json",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "saved to output.json" in result.stdout
