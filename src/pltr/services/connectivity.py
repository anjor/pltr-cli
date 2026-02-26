"""
Connectivity service wrapper for Foundry SDK.
"""

from typing import Any, Optional, Dict, List

from .base import BaseService


class ConnectivityService(BaseService):
    """Service wrapper for Foundry connectivity operations."""

    def _get_service(self) -> Any:
        """Get the Foundry client for connectivity operations."""
        return self.client

    @property
    def connections_service(self) -> Any:
        """Get the connections service from the client."""
        legacy_connections = getattr(self.client, "connections", None)
        if legacy_connections is not None:
            return legacy_connections

        connectivity = getattr(self.client, "connectivity", None)
        if connectivity is None:
            raise RuntimeError("Connectivity service is not available on the client")
        return connectivity

    @property
    def file_imports_service(self) -> Any:
        """Get the file imports service from the client."""
        return self.client.file_imports

    @property
    def table_imports_service(self) -> Any:
        """Get the table imports service from the client."""
        return self.client.table_imports

    def list_connections(self) -> List[Dict[str, Any]]:
        """
        List available connections.

        Returns:
            List of connection information dictionaries
        """
        try:
            connection_client = self.connections_service.Connection
            if hasattr(connection_client, "list"):
                connections = connection_client.list()
            else:
                connections = self._list_connections_from_filesystem()
            return [self._format_connection_info(conn) for conn in connections]
        except Exception as e:
            raise RuntimeError(f"Failed to list connections: {e}")

    def get_connection(self, connection_rid: str) -> Dict[str, Any]:
        """
        Get information about a specific connection.

        Args:
            connection_rid: Connection Resource Identifier

        Returns:
            Connection information dictionary
        """
        try:
            connection = self.connections_service.Connection.get(connection_rid)
            return self._format_connection_info(connection)
        except Exception as e:
            raise RuntimeError(f"Failed to get connection {connection_rid}: {e}")

    def create_connection(
        self,
        display_name: str,
        parent_folder_rid: str,
        configuration: Dict[str, Any],
        worker: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new connection.

        Args:
            display_name: Display name for the connection
            parent_folder_rid: Parent folder Resource Identifier
            configuration: Connection configuration dictionary
            worker: Worker configuration dictionary

        Returns:
            Created connection information dictionary
        """
        try:
            connection = self.connections_service.Connection.create(
                configuration=configuration,
                display_name=display_name,
                parent_folder_rid=parent_folder_rid,
                worker=worker,
            )
            return self._format_connection_info(connection)
        except Exception as e:
            raise RuntimeError(f"Failed to create connection '{display_name}': {e}")

    def get_connection_configuration(self, connection_rid: str) -> Dict[str, Any]:
        """
        Get connection configuration.

        Args:
            connection_rid: Connection Resource Identifier

        Returns:
            Connection configuration dictionary
        """
        try:
            config = self.connections_service.Connection.get_configuration(
                connection_rid
            )
            return {"connection_rid": connection_rid, "configuration": config}
        except Exception as e:
            raise RuntimeError(
                f"Failed to get configuration for connection {connection_rid}: {e}"
            )

    def update_export_settings(
        self, connection_rid: str, export_settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update connection export settings.

        Args:
            connection_rid: Connection Resource Identifier
            export_settings: Export settings dictionary

        Returns:
            Status dictionary
        """
        try:
            self.connections_service.Connection.update_export_settings(
                connection_rid=connection_rid,
                export_settings=export_settings,
            )
            return {
                "connection_rid": connection_rid,
                "status": "export settings updated",
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to update export settings for connection {connection_rid}: {e}"
            )

    def update_secrets(
        self, connection_rid: str, secrets: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Update connection secrets.

        Args:
            connection_rid: Connection Resource Identifier
            secrets: Dictionary mapping secret names to values

        Returns:
            Status dictionary
        """
        try:
            self.connections_service.Connection.update_secrets(
                connection_rid=connection_rid,
                secrets=secrets,
            )
            return {"connection_rid": connection_rid, "status": "secrets updated"}
        except Exception as e:
            raise RuntimeError(
                f"Failed to update secrets for connection {connection_rid}: {e}"
            )

    def upload_custom_jdbc_drivers(
        self, connection_rid: str, file_path: str
    ) -> Dict[str, Any]:
        """
        Upload custom JDBC drivers to a connection.

        Args:
            connection_rid: Connection Resource Identifier
            file_path: Path to the JAR file

        Returns:
            Updated connection information dictionary
        """
        from pathlib import Path

        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path_obj.suffix.lower() == ".jar":
            raise ValueError(f"File must be a JAR file: {file_path}")

        try:
            with open(file_path_obj, "rb") as f:
                file_content = f.read()

            connection = self.connections_service.Connection.upload_custom_jdbc_drivers(
                connection_rid=connection_rid,
                body=file_content,
                file_name=file_path_obj.name,
            )
            return self._format_connection_info(connection)
        except Exception as e:
            raise RuntimeError(
                f"Failed to upload JDBC driver to connection {connection_rid}: {e}"
            )

    def create_file_import(
        self,
        connection_rid: str,
        source_path: str,
        target_dataset_rid: str,
        import_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a file import via connection.

        Args:
            connection_rid: Connection Resource Identifier
            source_path: Path to source file in the connection
            target_dataset_rid: Target dataset RID
            import_config: Optional import configuration

        Returns:
            File import information dictionary
        """
        try:
            config = import_config or {}
            file_import = self.file_imports_service.FileImport.create(
                connection_rid=connection_rid,
                source_path=source_path,
                target_dataset_rid=target_dataset_rid,
                **config,
            )
            return self._format_import_info(file_import)
        except Exception as e:
            raise RuntimeError(
                f"Failed to create file import from {connection_rid}:{source_path}: {e}"
            )

    def get_file_import(self, import_rid: str) -> Dict[str, Any]:
        """
        Get information about a specific file import.

        Args:
            import_rid: File import Resource Identifier

        Returns:
            File import information dictionary
        """
        try:
            file_import = self.file_imports_service.FileImport.get(import_rid)
            return self._format_import_info(file_import)
        except Exception as e:
            raise RuntimeError(f"Failed to get file import {import_rid}: {e}")

    def execute_file_import(self, import_rid: str) -> Dict[str, Any]:
        """
        Execute a file import.

        Args:
            import_rid: File import Resource Identifier

        Returns:
            Execution result information
        """
        try:
            result = self.file_imports_service.FileImport.execute(import_rid)
            return self._format_execution_result(result)
        except Exception as e:
            raise RuntimeError(f"Failed to execute file import {import_rid}: {e}")

    def create_table_import(
        self,
        connection_rid: str,
        source_table: str,
        target_dataset_rid: str,
        import_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a table import via connection.

        Args:
            connection_rid: Connection Resource Identifier
            source_table: Source table name in the connection
            target_dataset_rid: Target dataset RID
            import_config: Optional import configuration

        Returns:
            Table import information dictionary
        """
        try:
            config = import_config or {}
            table_import = self.table_imports_service.TableImport.create(
                connection_rid=connection_rid,
                source_table=source_table,
                target_dataset_rid=target_dataset_rid,
                **config,
            )
            return self._format_import_info(table_import)
        except Exception as e:
            raise RuntimeError(
                f"Failed to create table import from {connection_rid}:{source_table}: {e}"
            )

    def get_table_import(self, import_rid: str) -> Dict[str, Any]:
        """
        Get information about a specific table import.

        Args:
            import_rid: Table import Resource Identifier

        Returns:
            Table import information dictionary
        """
        try:
            table_import = self.table_imports_service.TableImport.get(import_rid)
            return self._format_import_info(table_import)
        except Exception as e:
            raise RuntimeError(f"Failed to get table import {import_rid}: {e}")

    def execute_table_import(self, import_rid: str) -> Dict[str, Any]:
        """
        Execute a table import.

        Args:
            import_rid: Table import Resource Identifier

        Returns:
            Execution result information
        """
        try:
            result = self.table_imports_service.TableImport.execute(import_rid)
            return self._format_execution_result(result)
        except Exception as e:
            raise RuntimeError(f"Failed to execute table import {import_rid}: {e}")

    def list_file_imports(
        self, connection_rid: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List file imports, optionally filtered by connection.

        Args:
            connection_rid: Optional connection RID to filter by

        Returns:
            List of file import information dictionaries
        """
        try:
            if connection_rid:
                imports = self.file_imports_service.FileImport.list(
                    connection_rid=connection_rid
                )
            else:
                imports = self.file_imports_service.FileImport.list()
            return [self._format_import_info(imp) for imp in imports]
        except Exception as e:
            raise RuntimeError(f"Failed to list file imports: {e}")

    def list_table_imports(
        self, connection_rid: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List table imports, optionally filtered by connection.

        Args:
            connection_rid: Optional connection RID to filter by

        Returns:
            List of table import information dictionaries
        """
        try:
            if connection_rid:
                imports = self.table_imports_service.TableImport.list(
                    connection_rid=connection_rid
                )
            else:
                imports = self.table_imports_service.TableImport.list()
            return [self._format_import_info(imp) for imp in imports]
        except Exception as e:
            raise RuntimeError(f"Failed to list table imports: {e}")

    def _format_connection_info(self, connection: Any) -> Dict[str, Any]:
        """
        Format connection information for display.

        Args:
            connection: Connection object from SDK

        Returns:
            Formatted connection dictionary
        """
        try:
            if isinstance(connection, dict):
                return {
                    "rid": connection.get("rid", "N/A"),
                    "display_name": connection.get("display_name", "N/A"),
                    "description": connection.get("description", ""),
                    "connection_type": connection.get("connection_type", "N/A"),
                    "status": connection.get("status", "N/A"),
                    "created_time": connection.get("created_time", "N/A"),
                    "modified_time": connection.get("modified_time", "N/A"),
                }

            return {
                "rid": getattr(connection, "rid", "N/A"),
                "display_name": getattr(connection, "display_name", "N/A"),
                "description": getattr(connection, "description", ""),
                "connection_type": getattr(connection, "connection_type", "N/A"),
                "status": getattr(connection, "status", "N/A"),
                "created_time": getattr(connection, "created_time", "N/A"),
                "modified_time": getattr(connection, "modified_time", "N/A"),
            }
        except Exception:
            return {"raw": str(connection)}

    def _list_connections_from_filesystem(self) -> List[Dict[str, Any]]:
        """
        Discover connection resources from filesystem when SDK list() is unavailable.
        """
        filesystem = getattr(self.client, "filesystem", None)
        if filesystem is None or not hasattr(filesystem, "Folder"):
            raise RuntimeError(
                "Connection.list() is unavailable and filesystem fallback is not supported"
            )

        folder_client = filesystem.Folder
        root_folder_rid = "ri.compass.main.folder.0"
        pending_folders = [root_folder_rid]
        visited_folders = set()
        discovered_connections: List[Dict[str, Any]] = []
        max_folders = 1000

        while pending_folders and len(visited_folders) < max_folders:
            folder_rid = pending_folders.pop(0)
            if folder_rid in visited_folders:
                continue
            visited_folders.add(folder_rid)

            try:
                children = folder_client.children(folder_rid, preview=True)
            except Exception:
                continue

            for child in children:
                child_rid = getattr(child, "rid", None)
                if not child_rid:
                    continue

                child_type = str(getattr(child, "type", "") or "").lower()
                if self._looks_like_connection_resource(child_rid, child_type):
                    discovered_connections.append(
                        {
                            "rid": child_rid,
                            "display_name": getattr(child, "display_name", "N/A"),
                            "description": getattr(child, "description", ""),
                            "connection_type": child_type or "connection",
                            "status": getattr(child, "status", "N/A"),
                            "created_time": getattr(child, "created_time", "N/A"),
                            "modified_time": getattr(child, "modified_time", "N/A"),
                        }
                    )
                    continue

                if child_type in {"folder", "compass_folder", "project", "space"}:
                    pending_folders.append(child_rid)

        return discovered_connections

    @staticmethod
    def _looks_like_connection_resource(resource_rid: str, resource_type: str) -> bool:
        """Best-effort detection for connection resources from filesystem entries."""
        return "connection" in resource_type or ".connection." in resource_rid

    def _format_import_info(self, import_obj: Any) -> Dict[str, Any]:
        """
        Format import information for display.

        Args:
            import_obj: Import object from SDK

        Returns:
            Formatted import dictionary
        """
        try:
            return {
                "rid": getattr(import_obj, "rid", "N/A"),
                "display_name": getattr(import_obj, "display_name", "N/A"),
                "connection_rid": getattr(import_obj, "connection_rid", "N/A"),
                "target_dataset_rid": getattr(import_obj, "target_dataset_rid", "N/A"),
                "status": getattr(import_obj, "status", "N/A"),
                "import_type": getattr(import_obj, "import_type", "N/A"),
                "source": getattr(import_obj, "source", "N/A"),
                "created_time": getattr(import_obj, "created_time", "N/A"),
                "modified_time": getattr(import_obj, "modified_time", "N/A"),
            }
        except Exception:
            return {"raw": str(import_obj)}

    def _format_execution_result(self, result: Any) -> Dict[str, Any]:
        """
        Format execution result for display.

        Args:
            result: Execution result object from SDK

        Returns:
            Formatted result dictionary
        """
        try:
            return {
                "execution_rid": getattr(result, "execution_rid", "N/A"),
                "status": getattr(result, "status", "N/A"),
                "started_time": getattr(result, "started_time", "N/A"),
                "completed_time": getattr(result, "completed_time", ""),
                "records_processed": getattr(result, "records_processed", 0),
                "errors": getattr(result, "errors", []),
            }
        except Exception:
            return {"raw": str(result)}
