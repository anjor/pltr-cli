"""
Tests for connectivity commands.
"""

from unittest.mock import Mock, patch
from typer.testing import CliRunner

from pltr.commands.connectivity import app
from pltr.auth.base import ProfileNotFoundError


class TestConnectivityCommands:
    """Test cases for connectivity commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_list_connections_success(self, mock_service_class):
        """Test successful connection listing command."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.list_connections.return_value = [
            {
                "rid": "ri.conn.main.connection.123",
                "display_name": "Test Connection",
                "connection_type": "JDBC",
                "status": "ACTIVE",
            }
        ]

        result = self.runner.invoke(app, ["connection", "list"])

        assert result.exit_code == 0
        mock_service.list_connections.assert_called_once()

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_list_connections_empty(self, mock_service_class):
        """Test connection listing with no results."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.list_connections.return_value = []

        result = self.runner.invoke(app, ["connection", "list"])

        assert result.exit_code == 0
        assert "No connections found" in result.stdout

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_list_connections_with_profile(self, mock_service_class):
        """Test connection listing with specific profile."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.list_connections.return_value = []

        result = self.runner.invoke(app, ["connection", "list", "--profile", "test"])

        assert result.exit_code == 0
        mock_service_class.assert_called_once_with(profile="test")

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_list_connections_auth_error(self, mock_service_class):
        """Test connection listing with authentication error."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.list_connections.side_effect = ProfileNotFoundError(
            "Profile not found"
        )

        result = self.runner.invoke(app, ["connection", "list"])

        assert result.exit_code == 1
        assert "Authentication error" in result.stdout

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_list_connections_general_error(self, mock_service_class):
        """Test connection listing with general error."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.list_connections.side_effect = Exception("API Error")

        result = self.runner.invoke(app, ["connection", "list"])

        assert result.exit_code == 1
        assert "Error listing connections" in result.stdout

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_get_connection_success(self, mock_service_class):
        """Test successful connection get command."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_connection.return_value = {
            "rid": "ri.conn.main.connection.123",
            "display_name": "Test Connection",
            "connection_type": "JDBC",
            "status": "ACTIVE",
        }

        result = self.runner.invoke(
            app, ["connection", "get", "ri.conn.main.connection.123"]
        )

        assert result.exit_code == 0
        mock_service.get_connection.assert_called_once_with(
            "ri.conn.main.connection.123"
        )

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_get_connection_error(self, mock_service_class):
        """Test connection get with error."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_connection.side_effect = Exception("Connection not found")

        result = self.runner.invoke(
            app, ["connection", "get", "ri.conn.main.connection.123"]
        )

        assert result.exit_code == 1
        assert "Error getting connection" in result.stdout

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_import_file_success(self, mock_service_class):
        """Test successful file import command."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.create_file_import.return_value = {
            "rid": "ri.import.main.file.123",
            "display_name": "Test Import",
            "status": "CREATED",
        }

        result = self.runner.invoke(
            app,
            [
                "import",
                "file",
                "ri.conn.main.connection.123",
                "/path/to/file.csv",
                "ri.foundry.main.dataset.456",
            ],
        )

        assert result.exit_code == 0
        mock_service.create_file_import.assert_called_once_with(
            connection_rid="ri.conn.main.connection.123",
            source_path="/path/to/file.csv",
            target_dataset_rid="ri.foundry.main.dataset.456",
            import_config=None,
        )

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_import_file_with_config(self, mock_service_class):
        """Test file import command with configuration."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.create_file_import.return_value = {
            "rid": "ri.import.main.file.123",
            "display_name": "Test Import",
            "status": "CREATED",
        }

        config = '{"format": "CSV", "delimiter": ","}'
        result = self.runner.invoke(
            app,
            [
                "import",
                "file",
                "ri.conn.main.connection.123",
                "/path/to/file.csv",
                "ri.foundry.main.dataset.456",
                "--config",
                config,
            ],
        )

        assert result.exit_code == 0
        expected_config = {"format": "CSV", "delimiter": ","}
        mock_service.create_file_import.assert_called_once_with(
            connection_rid="ri.conn.main.connection.123",
            source_path="/path/to/file.csv",
            target_dataset_rid="ri.foundry.main.dataset.456",
            import_config=expected_config,
        )

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_import_file_with_execution(self, mock_service_class):
        """Test file import command with immediate execution."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.create_file_import.return_value = {
            "rid": "ri.import.main.file.123",
            "display_name": "Test Import",
            "status": "CREATED",
        }
        mock_service.execute_file_import.return_value = {
            "execution_rid": "ri.execution.main.123",
            "status": "RUNNING",
        }

        result = self.runner.invoke(
            app,
            [
                "import",
                "file",
                "ri.conn.main.connection.123",
                "/path/to/file.csv",
                "ri.foundry.main.dataset.456",
                "--execute",
            ],
        )

        assert result.exit_code == 0
        mock_service.create_file_import.assert_called_once()
        mock_service.execute_file_import.assert_called_once_with(
            "ri.import.main.file.123"
        )
        assert "File import executed" in result.stdout

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_import_file_invalid_config(self, mock_service_class):
        """Test file import command with invalid JSON configuration."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        result = self.runner.invoke(
            app,
            [
                "import",
                "file",
                "ri.conn.main.connection.123",
                "/path/to/file.csv",
                "ri.foundry.main.dataset.456",
                "--config",
                "invalid-json",
            ],
        )

        assert result.exit_code == 1
        assert "Invalid JSON configuration" in result.stdout

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_import_table_success(self, mock_service_class):
        """Test successful table import command."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.create_table_import.return_value = {
            "rid": "ri.import.main.table.123",
            "display_name": "Test Table Import",
            "status": "CREATED",
        }

        result = self.runner.invoke(
            app,
            [
                "import",
                "table",
                "ri.conn.main.connection.123",
                "my_table",
                "ri.foundry.main.dataset.456",
            ],
        )

        assert result.exit_code == 0
        mock_service.create_table_import.assert_called_once_with(
            connection_rid="ri.conn.main.connection.123",
            source_table="my_table",
            target_dataset_rid="ri.foundry.main.dataset.456",
            import_config=None,
        )

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_import_table_with_execution(self, mock_service_class):
        """Test table import command with immediate execution."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.create_table_import.return_value = {
            "rid": "ri.import.main.table.123",
            "display_name": "Test Table Import",
            "status": "CREATED",
        }
        mock_service.execute_table_import.return_value = {
            "execution_rid": "ri.execution.main.123",
            "status": "RUNNING",
        }

        result = self.runner.invoke(
            app,
            [
                "import",
                "table",
                "ri.conn.main.connection.123",
                "my_table",
                "ri.foundry.main.dataset.456",
                "--execute",
            ],
        )

        assert result.exit_code == 0
        mock_service.create_table_import.assert_called_once()
        mock_service.execute_table_import.assert_called_once_with(
            "ri.import.main.table.123"
        )
        assert "Table import executed" in result.stdout

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_list_file_imports_success(self, mock_service_class):
        """Test successful file imports listing command."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.list_file_imports.return_value = [
            {
                "rid": "ri.import.main.file.123",
                "display_name": "Test Import",
                "status": "CREATED",
            }
        ]

        result = self.runner.invoke(app, ["import", "list-file"])

        assert result.exit_code == 0
        mock_service.list_file_imports.assert_called_once_with(connection_rid=None)

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_list_file_imports_filtered(self, mock_service_class):
        """Test file imports listing with connection filter."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.list_file_imports.return_value = []

        result = self.runner.invoke(
            app, ["import", "list-file", "--connection", "ri.conn.main.connection.123"]
        )

        assert result.exit_code == 0
        mock_service.list_file_imports.assert_called_once_with(
            connection_rid="ri.conn.main.connection.123"
        )

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_list_file_imports_empty(self, mock_service_class):
        """Test file imports listing with no results."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.list_file_imports.return_value = []

        result = self.runner.invoke(app, ["import", "list-file"])

        assert result.exit_code == 0
        assert "No file imports found" in result.stdout

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_list_table_imports_success(self, mock_service_class):
        """Test successful table imports listing command."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.list_table_imports.return_value = [
            {
                "rid": "ri.import.main.table.123",
                "display_name": "Test Table Import",
                "status": "CREATED",
            }
        ]

        result = self.runner.invoke(app, ["import", "list-table"])

        assert result.exit_code == 0
        mock_service.list_table_imports.assert_called_once_with(connection_rid=None)

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_get_file_import_success(self, mock_service_class):
        """Test successful file import get command."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_file_import.return_value = {
            "rid": "ri.import.main.file.123",
            "display_name": "Test Import",
            "status": "CREATED",
        }

        result = self.runner.invoke(
            app, ["import", "get-file", "ri.import.main.file.123"]
        )

        assert result.exit_code == 0
        mock_service.get_file_import.assert_called_once_with("ri.import.main.file.123")

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_get_table_import_success(self, mock_service_class):
        """Test successful table import get command."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_table_import.return_value = {
            "rid": "ri.import.main.table.123",
            "display_name": "Test Table Import",
            "status": "CREATED",
        }

        result = self.runner.invoke(
            app, ["import", "get-table", "ri.import.main.table.123"]
        )

        assert result.exit_code == 0
        mock_service.get_table_import.assert_called_once_with(
            "ri.import.main.table.123"
        )

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_import_file_execution_missing_rid(self, mock_service_class):
        """Test file import execution when RID is missing."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.create_file_import.return_value = {
            "display_name": "Test Import",
            "status": "CREATED",
            # Missing RID
        }

        result = self.runner.invoke(
            app,
            [
                "import",
                "file",
                "ri.conn.main.connection.123",
                "/path/to/file.csv",
                "ri.foundry.main.dataset.456",
                "--execute",
            ],
        )

        assert result.exit_code == 0
        mock_service.create_file_import.assert_called_once()
        # Should not call execute when RID is missing
        mock_service.execute_file_import.assert_not_called()
        assert "Warning: Could not execute" in result.stdout

    @patch("pltr.commands.connectivity.ConnectivityService")
    def test_import_error_handling(self, mock_service_class):
        """Test import command error handling."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.create_file_import.side_effect = Exception("Import failed")

        result = self.runner.invoke(
            app,
            [
                "import",
                "file",
                "ri.conn.main.connection.123",
                "/path/to/file.csv",
                "ri.foundry.main.dataset.456",
            ],
        )

        assert result.exit_code == 1
        assert "Error creating file import" in result.stdout
