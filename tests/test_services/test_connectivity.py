"""
Tests for connectivity service wrapper.
"""

import pytest
from unittest.mock import Mock, patch

from pltr.services.connectivity import ConnectivityService


class TestConnectivityService:
    """Test cases for ConnectivityService."""

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def setup_method(self, method, mock_client):
        """Set up test fixtures."""
        self.mock_client = mock_client
        self.service = ConnectivityService(profile="test")

    def test_init_with_profile(self):
        """Test service initialization with profile."""
        service = ConnectivityService(profile="test-profile")
        assert service.profile == "test-profile"

    def test_init_without_profile(self):
        """Test service initialization without profile."""
        service = ConnectivityService()
        assert service.profile is None

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_get_service(self, mock_client):
        """Test _get_service returns client."""
        service = ConnectivityService(profile="test")
        result = service._get_service()
        assert result == mock_client

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_connections_service(self, mock_client):
        """Test connections_service property."""
        service = ConnectivityService(profile="test")
        result = service.connections_service
        assert result == mock_client.connections

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_file_imports_service(self, mock_client):
        """Test file_imports_service property."""
        service = ConnectivityService(profile="test")
        result = service.file_imports_service
        assert result == mock_client.file_imports

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_table_imports_service(self, mock_client):
        """Test table_imports_service property."""
        service = ConnectivityService(profile="test")
        result = service.table_imports_service
        assert result == mock_client.table_imports

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_list_connections_success(self, mock_client):
        """Test successful connection listing."""
        mock_connection = Mock()
        mock_connection.rid = "ri.conn.main.connection.123"
        mock_connection.display_name = "Test Connection"
        mock_connection.description = "Test Description"
        mock_connection.connection_type = "JDBC"
        mock_connection.status = "ACTIVE"
        mock_connection.created_time = "2023-01-01T00:00:00Z"
        mock_connection.modified_time = "2023-01-01T00:00:00Z"

        mock_client.connections.Connection.list.return_value = [mock_connection]

        service = ConnectivityService(profile="test")
        result = service.list_connections()

        assert len(result) == 1
        assert result[0]["rid"] == "ri.conn.main.connection.123"
        assert result[0]["display_name"] == "Test Connection"
        assert result[0]["connection_type"] == "JDBC"

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_list_connections_error(self, mock_client):
        """Test connection listing error handling."""
        mock_client.connections.Connection.list.side_effect = Exception("API Error")

        service = ConnectivityService(profile="test")
        with pytest.raises(RuntimeError, match="Failed to list connections"):
            service.list_connections()

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_get_connection_success(self, mock_client):
        """Test successful connection retrieval."""
        mock_connection = Mock()
        mock_connection.rid = "ri.conn.main.connection.123"
        mock_connection.display_name = "Test Connection"
        mock_connection.description = "Test Description"
        mock_connection.connection_type = "JDBC"
        mock_connection.status = "ACTIVE"

        mock_client.connections.Connection.get.return_value = mock_connection

        service = ConnectivityService(profile="test")
        result = service.get_connection("ri.conn.main.connection.123")

        assert result["rid"] == "ri.conn.main.connection.123"
        assert result["display_name"] == "Test Connection"
        mock_client.connections.Connection.get.assert_called_once_with(
            "ri.conn.main.connection.123"
        )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_get_connection_error(self, mock_client):
        """Test connection retrieval error handling."""
        mock_client.connections.Connection.get.side_effect = Exception("Not found")

        service = ConnectivityService(profile="test")
        with pytest.raises(RuntimeError, match="Failed to get connection"):
            service.get_connection("ri.conn.main.connection.123")

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_create_file_import_success(self, mock_client):
        """Test successful file import creation."""
        mock_import = Mock()
        mock_import.rid = "ri.import.main.file.123"
        mock_import.display_name = "Test File Import"
        mock_import.connection_rid = "ri.conn.main.connection.123"
        mock_import.target_dataset_rid = "ri.foundry.main.dataset.456"
        mock_import.status = "CREATED"

        mock_client.file_imports.FileImport.create.return_value = mock_import

        service = ConnectivityService(profile="test")
        result = service.create_file_import(
            connection_rid="ri.conn.main.connection.123",
            source_path="/path/to/file.csv",
            target_dataset_rid="ri.foundry.main.dataset.456",
        )

        assert result["rid"] == "ri.import.main.file.123"
        assert result["connection_rid"] == "ri.conn.main.connection.123"
        mock_client.file_imports.FileImport.create.assert_called_once()

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_create_file_import_with_config(self, mock_client):
        """Test file import creation with configuration."""
        mock_import = Mock()
        mock_import.rid = "ri.import.main.file.123"

        mock_client.file_imports.FileImport.create.return_value = mock_import

        service = ConnectivityService(profile="test")
        config = {"format": "CSV", "delimiter": ","}

        service.create_file_import(
            connection_rid="ri.conn.main.connection.123",
            source_path="/path/to/file.csv",
            target_dataset_rid="ri.foundry.main.dataset.456",
            import_config=config,
        )

        mock_client.file_imports.FileImport.create.assert_called_once_with(
            connection_rid="ri.conn.main.connection.123",
            source_path="/path/to/file.csv",
            target_dataset_rid="ri.foundry.main.dataset.456",
            format="CSV",
            delimiter=",",
        )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_create_file_import_error(self, mock_client):
        """Test file import creation error handling."""
        mock_client.file_imports.FileImport.create.side_effect = Exception(
            "Creation failed"
        )

        service = ConnectivityService(profile="test")
        with pytest.raises(RuntimeError, match="Failed to create file import"):
            service.create_file_import(
                connection_rid="ri.conn.main.connection.123",
                source_path="/path/to/file.csv",
                target_dataset_rid="ri.foundry.main.dataset.456",
            )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_execute_file_import_success(self, mock_client):
        """Test successful file import execution."""
        mock_result = Mock()
        mock_result.execution_rid = "ri.execution.main.123"
        mock_result.status = "RUNNING"
        mock_result.started_time = "2023-01-01T00:00:00Z"
        mock_result.records_processed = 0
        mock_result.errors = []

        mock_client.file_imports.FileImport.execute.return_value = mock_result

        service = ConnectivityService(profile="test")
        result = service.execute_file_import("ri.import.main.file.123")

        assert result["execution_rid"] == "ri.execution.main.123"
        assert result["status"] == "RUNNING"
        mock_client.file_imports.FileImport.execute.assert_called_once_with(
            "ri.import.main.file.123"
        )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_create_table_import_success(self, mock_client):
        """Test successful table import creation."""
        mock_import = Mock()
        mock_import.rid = "ri.import.main.table.123"
        mock_import.display_name = "Test Table Import"
        mock_import.connection_rid = "ri.conn.main.connection.123"
        mock_import.target_dataset_rid = "ri.foundry.main.dataset.456"
        mock_import.status = "CREATED"

        mock_client.table_imports.TableImport.create.return_value = mock_import

        service = ConnectivityService(profile="test")
        result = service.create_table_import(
            connection_rid="ri.conn.main.connection.123",
            source_table="my_table",
            target_dataset_rid="ri.foundry.main.dataset.456",
        )

        assert result["rid"] == "ri.import.main.table.123"
        assert result["connection_rid"] == "ri.conn.main.connection.123"
        mock_client.table_imports.TableImport.create.assert_called_once()

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_list_file_imports_success(self, mock_client):
        """Test successful file imports listing."""
        mock_import = Mock()
        mock_import.rid = "ri.import.main.file.123"
        mock_import.display_name = "Test Import"

        mock_client.file_imports.FileImport.list.return_value = [mock_import]

        service = ConnectivityService(profile="test")
        result = service.list_file_imports()

        assert len(result) == 1
        assert result[0]["rid"] == "ri.import.main.file.123"
        mock_client.file_imports.FileImport.list.assert_called_once_with()

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_list_file_imports_filtered(self, mock_client):
        """Test file imports listing with connection filter."""
        mock_import = Mock()
        mock_import.rid = "ri.import.main.file.123"

        mock_client.file_imports.FileImport.list.return_value = [mock_import]

        service = ConnectivityService(profile="test")
        result = service.list_file_imports(connection_rid="ri.conn.main.connection.123")

        assert len(result) == 1
        mock_client.file_imports.FileImport.list.assert_called_once_with(
            connection_rid="ri.conn.main.connection.123"
        )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_format_connection_info_complete(self, mock_client):
        """Test connection info formatting with complete data."""
        mock_connection = Mock()
        mock_connection.rid = "ri.conn.main.connection.123"
        mock_connection.display_name = "Test Connection"
        mock_connection.description = "Test Description"
        mock_connection.connection_type = "JDBC"
        mock_connection.status = "ACTIVE"
        mock_connection.created_time = "2023-01-01T00:00:00Z"
        mock_connection.modified_time = "2023-01-01T00:00:00Z"

        service = ConnectivityService(profile="test")
        result = service._format_connection_info(mock_connection)

        expected = {
            "rid": "ri.conn.main.connection.123",
            "display_name": "Test Connection",
            "description": "Test Description",
            "connection_type": "JDBC",
            "status": "ACTIVE",
            "created_time": "2023-01-01T00:00:00Z",
            "modified_time": "2023-01-01T00:00:00Z",
        }
        assert result == expected

    @patch("pltr.services.connectivity.ConnectivityService.client")
    @patch("pltr.services.connectivity.getattr")
    def test_format_connection_info_error(self, mock_getattr, mock_client):
        """Test connection info formatting error fallback."""
        mock_connection = Mock()
        # Make getattr raise an exception
        mock_getattr.side_effect = Exception("Getattr failed")

        service = ConnectivityService(profile="test")
        result = service._format_connection_info(mock_connection)

        # Should fallback to raw format when exception occurs
        assert "raw" in result
        assert str(mock_connection) in result["raw"]

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_format_import_info_complete(self, mock_client):
        """Test import info formatting with complete data."""
        mock_import = Mock()
        mock_import.rid = "ri.import.main.file.123"
        mock_import.display_name = "Test Import"
        mock_import.connection_rid = "ri.conn.main.connection.123"
        mock_import.target_dataset_rid = "ri.foundry.main.dataset.456"
        mock_import.status = "CREATED"
        mock_import.import_type = "FILE"
        mock_import.source = "/path/to/file.csv"
        mock_import.created_time = "2023-01-01T00:00:00Z"
        mock_import.modified_time = "2023-01-01T00:00:00Z"

        service = ConnectivityService(profile="test")
        result = service._format_import_info(mock_import)

        expected = {
            "rid": "ri.import.main.file.123",
            "display_name": "Test Import",
            "connection_rid": "ri.conn.main.connection.123",
            "target_dataset_rid": "ri.foundry.main.dataset.456",
            "status": "CREATED",
            "import_type": "FILE",
            "source": "/path/to/file.csv",
            "created_time": "2023-01-01T00:00:00Z",
            "modified_time": "2023-01-01T00:00:00Z",
        }
        assert result == expected

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_format_execution_result_complete(self, mock_client):
        """Test execution result formatting with complete data."""
        mock_result = Mock()
        mock_result.execution_rid = "ri.execution.main.123"
        mock_result.status = "COMPLETED"
        mock_result.started_time = "2023-01-01T00:00:00Z"
        mock_result.completed_time = "2023-01-01T01:00:00Z"
        mock_result.records_processed = 1000
        mock_result.errors = []

        service = ConnectivityService(profile="test")
        result = service._format_execution_result(mock_result)

        expected = {
            "execution_rid": "ri.execution.main.123",
            "status": "COMPLETED",
            "started_time": "2023-01-01T00:00:00Z",
            "completed_time": "2023-01-01T01:00:00Z",
            "records_processed": 1000,
            "errors": [],
        }
        assert result == expected

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_create_connection_success(self, mock_client):
        """Test successful connection creation."""
        mock_connection = Mock()
        mock_connection.rid = "ri.conn.main.connection.123"
        mock_connection.display_name = "New Connection"
        mock_connection.description = "Description"
        mock_connection.connection_type = "JDBC"
        mock_connection.status = "ACTIVE"
        mock_connection.created_time = "2023-01-01T00:00:00Z"
        mock_connection.modified_time = "2023-01-01T00:00:00Z"

        mock_client.connections.Connection.create.return_value = mock_connection

        service = ConnectivityService(profile="test")
        result = service.create_connection(
            display_name="New Connection",
            parent_folder_rid="ri.folder.main.123",
            configuration={"host": "localhost"},
            worker={"type": "direct"},
        )

        assert result["rid"] == "ri.conn.main.connection.123"
        assert result["display_name"] == "New Connection"
        mock_client.connections.Connection.create.assert_called_once_with(
            configuration={"host": "localhost"},
            display_name="New Connection",
            parent_folder_rid="ri.folder.main.123",
            worker={"type": "direct"},
        )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_create_connection_error(self, mock_client):
        """Test connection creation error handling."""
        mock_client.connections.Connection.create.side_effect = Exception(
            "Creation failed"
        )

        service = ConnectivityService(profile="test")
        with pytest.raises(RuntimeError, match="Failed to create connection"):
            service.create_connection(
                display_name="New Connection",
                parent_folder_rid="ri.folder.main.123",
                configuration={"host": "localhost"},
                worker={"type": "direct"},
            )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_get_connection_configuration_success(self, mock_client):
        """Test successful connection configuration retrieval."""
        mock_config = {"host": "localhost", "port": 5432}
        mock_client.connections.Connection.get_configuration.return_value = mock_config

        service = ConnectivityService(profile="test")
        result = service.get_connection_configuration("ri.conn.main.connection.123")

        assert result["connection_rid"] == "ri.conn.main.connection.123"
        assert result["configuration"] == mock_config
        mock_client.connections.Connection.get_configuration.assert_called_once_with(
            "ri.conn.main.connection.123"
        )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_get_connection_configuration_error(self, mock_client):
        """Test connection configuration retrieval error handling."""
        mock_client.connections.Connection.get_configuration.side_effect = Exception(
            "Not found"
        )

        service = ConnectivityService(profile="test")
        with pytest.raises(RuntimeError, match="Failed to get configuration"):
            service.get_connection_configuration("ri.conn.main.connection.123")

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_update_export_settings_success(self, mock_client):
        """Test successful export settings update."""
        mock_client.connections.Connection.update_export_settings.return_value = None

        service = ConnectivityService(profile="test")
        result = service.update_export_settings(
            "ri.conn.main.connection.123",
            {"exportsEnabled": True},
        )

        assert result["connection_rid"] == "ri.conn.main.connection.123"
        assert result["status"] == "export settings updated"
        mock_client.connections.Connection.update_export_settings.assert_called_once_with(
            connection_rid="ri.conn.main.connection.123",
            export_settings={"exportsEnabled": True},
        )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_update_export_settings_error(self, mock_client):
        """Test export settings update error handling."""
        mock_client.connections.Connection.update_export_settings.side_effect = (
            Exception("Update failed")
        )

        service = ConnectivityService(profile="test")
        with pytest.raises(RuntimeError, match="Failed to update export settings"):
            service.update_export_settings(
                "ri.conn.main.connection.123",
                {"exportsEnabled": True},
            )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_update_secrets_success(self, mock_client):
        """Test successful secrets update."""
        mock_client.connections.Connection.update_secrets.return_value = None

        service = ConnectivityService(profile="test")
        result = service.update_secrets(
            "ri.conn.main.connection.123",
            {"password": "newpass"},
        )

        assert result["connection_rid"] == "ri.conn.main.connection.123"
        assert result["status"] == "secrets updated"
        mock_client.connections.Connection.update_secrets.assert_called_once_with(
            connection_rid="ri.conn.main.connection.123",
            secrets={"password": "newpass"},
        )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_update_secrets_error(self, mock_client):
        """Test secrets update error handling."""
        mock_client.connections.Connection.update_secrets.side_effect = Exception(
            "Update failed"
        )

        service = ConnectivityService(profile="test")
        with pytest.raises(RuntimeError, match="Failed to update secrets"):
            service.update_secrets(
                "ri.conn.main.connection.123",
                {"password": "newpass"},
            )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_upload_custom_jdbc_drivers_success(self, mock_client, tmp_path):
        """Test successful JDBC driver upload."""
        # Create a temporary JAR file
        jar_file = tmp_path / "driver.jar"
        jar_file.write_bytes(b"fake jar content")

        mock_connection = Mock()
        mock_connection.rid = "ri.conn.main.connection.123"
        mock_connection.display_name = "Test Connection"
        mock_connection.description = ""
        mock_connection.connection_type = "JDBC"
        mock_connection.status = "ACTIVE"
        mock_connection.created_time = "2023-01-01T00:00:00Z"
        mock_connection.modified_time = "2023-01-01T00:00:00Z"

        mock_client.connections.Connection.upload_custom_jdbc_drivers.return_value = (
            mock_connection
        )

        service = ConnectivityService(profile="test")
        result = service.upload_custom_jdbc_drivers(
            "ri.conn.main.connection.123",
            str(jar_file),
        )

        assert result["rid"] == "ri.conn.main.connection.123"
        mock_client.connections.Connection.upload_custom_jdbc_drivers.assert_called_once()

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_upload_custom_jdbc_drivers_file_not_found(self, mock_client):
        """Test JDBC driver upload with non-existent file."""
        service = ConnectivityService(profile="test")
        with pytest.raises(FileNotFoundError, match="File not found"):
            service.upload_custom_jdbc_drivers(
                "ri.conn.main.connection.123",
                "/nonexistent/path/driver.jar",
            )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_upload_custom_jdbc_drivers_invalid_extension(self, mock_client, tmp_path):
        """Test JDBC driver upload with non-JAR file."""
        # Create a temporary non-JAR file
        txt_file = tmp_path / "file.txt"
        txt_file.write_text("not a jar file")

        service = ConnectivityService(profile="test")
        with pytest.raises(ValueError, match="File must be a JAR file"):
            service.upload_custom_jdbc_drivers(
                "ri.conn.main.connection.123",
                str(txt_file),
            )

    @patch("pltr.services.connectivity.ConnectivityService.client")
    def test_upload_custom_jdbc_drivers_api_error(self, mock_client, tmp_path):
        """Test JDBC driver upload API error handling."""
        # Create a temporary JAR file
        jar_file = tmp_path / "driver.jar"
        jar_file.write_bytes(b"fake jar content")

        mock_client.connections.Connection.upload_custom_jdbc_drivers.side_effect = (
            Exception("Upload failed")
        )

        service = ConnectivityService(profile="test")
        with pytest.raises(RuntimeError, match="Failed to upload JDBC driver"):
            service.upload_custom_jdbc_drivers(
                "ri.conn.main.connection.123",
                str(jar_file),
            )
