"""
Connectivity service wrapper for the Foundry SDK connectivity API.

Every method calls a GA endpoint of ``client.connectivity`` (so none passes
``preview``), returns the SDK result unchanged (``Connection``,
``FileImport`` and ``TableImport`` models, one-page ``ResourceIterator``s,
build RIDs) and lets SDK exceptions propagate so the error layer can
classify them.

File and table imports are nested under their connection in the API, so
every import method takes the connection RID as well as the import RID.
The SDK has no endpoint that lists connections.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .base import BaseService


class ConnectivityService(BaseService):
    """Service wrapper for Foundry connectivity operations (``client.connectivity``)."""

    def _get_service(self) -> Any:
        """Get the Foundry connectivity service."""
        return self.client.connectivity

    # ------------------------------------------------------------ connections

    def get_connection(self, connection_rid: str) -> Any:
        """Get a connection (``Connection.get``, GA); returns a ``Connection``."""
        return self.service.Connection.get(connection_rid)

    def create_connection(
        self,
        *,
        display_name: str,
        parent_folder_rid: str,
        configuration: Dict[str, Any],
        worker: Dict[str, Any],
    ) -> Any:
        """Create a connection (``Connection.create``, GA).

        Args:
            display_name: Display name of the connection
            parent_folder_rid: RID of the folder to create it in
            configuration: The API's ``CreateConnectionRequestConnectionConfiguration``
                as JSON (Foundry field names, with its ``type``)
            worker: The API's ``CreateConnectionRequestConnectionWorker`` as JSON

        Returns:
            The created ``Connection`` model
        """
        return self.service.Connection.create(
            configuration=configuration,
            display_name=display_name,
            parent_folder_rid=parent_folder_rid,
            worker=worker,
        )

    def get_connection_configuration(self, connection_rid: str) -> Any:
        """Get a connection's configuration (``Connection.get_configuration``, GA).

        Returns:
            One of the ``ConnectionConfiguration`` models (S3, REST, Snowflake,
            Databricks, SMB or JDBC), told apart by its ``type``
        """
        return self.service.Connection.get_configuration(connection_rid)

    def update_export_settings(
        self, connection_rid: str, export_settings: Dict[str, Any]
    ) -> None:
        """Replace a connection's export settings (``Connection.update_export_settings``, GA).

        Args:
            connection_rid: Connection RID
            export_settings: The API's ``ConnectionExportSettings`` as JSON
                (``exportsEnabled``, ``exportEnabledWithoutMarkingsValidation``)
        """
        self.service.Connection.update_export_settings(
            connection_rid, export_settings=export_settings
        )

    def update_secrets(self, connection_rid: str, secrets: Dict[str, str]) -> None:
        """Set secret values on a connection (``Connection.update_secrets``, GA).

        Secrets not named in ``secrets`` keep their values.
        """
        self.service.Connection.update_secrets(connection_rid, secrets=secrets)

    def upload_custom_jdbc_drivers(
        self, connection_rid: str, jar_path: Union[str, Path]
    ) -> Any:
        """Upload one JDBC driver JAR (``Connection.upload_custom_jdbc_drivers``, GA).

        Returns:
            The updated ``Connection`` model
        """
        path = Path(jar_path)
        return self.service.Connection.upload_custom_jdbc_drivers(
            connection_rid, body=path.read_bytes(), file_name=path.name
        )

    # ----------------------------------------------------------- file imports

    def create_file_import(
        self,
        connection_rid: str,
        *,
        dataset_rid: str,
        display_name: str,
        import_mode: str,
        file_import_filters: List[Dict[str, Any]],
        branch_name: Optional[str] = None,
        subfolder: Optional[str] = None,
    ) -> Any:
        """Create a file import (``Connection.FileImport.create``, GA).

        Args:
            connection_rid: RID of the connection to import from
            dataset_rid: RID of the output dataset (can't be changed later)
            display_name: Display name of the import
            import_mode: ``SNAPSHOT``, ``APPEND`` or ``UPDATE``
            file_import_filters: The API's ``FileImportFilter`` objects as JSON
                (may be empty)
            branch_name: Output dataset branch (default: the API's, usually master)
            subfolder: Folder in the source system to import (default: its root)

        Returns:
            The created ``FileImport`` model
        """
        return self.service.Connection.FileImport.create(
            connection_rid,
            dataset_rid=dataset_rid,
            display_name=display_name,
            file_import_filters=file_import_filters,
            import_mode=import_mode,
            branch_name=branch_name,
            subfolder=subfolder,
        )

    def get_file_import(self, connection_rid: str, file_import_rid: str) -> Any:
        """Get a file import (``Connection.FileImport.get``, GA)."""
        return self.service.Connection.FileImport.get(connection_rid, file_import_rid)

    def list_file_imports(
        self,
        connection_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a connection's file imports (``Connection.FileImport.list``, GA).

        Returns:
            The SDK ``ResourceIterator[FileImport]``; constructing it fetched
            exactly one page (``.data``, ``.next_page_token``).
        """
        return self.service.Connection.FileImport.list(
            connection_rid, page_size=page_size, page_token=page_token
        )

    def execute_file_import(self, connection_rid: str, file_import_rid: str) -> str:
        """Run a file import as a build (``Connection.FileImport.execute``, GA).

        Returns:
            The RID of the build that runs the import
        """
        return self.service.Connection.FileImport.execute(
            connection_rid, file_import_rid
        )

    # ---------------------------------------------------------- table imports

    def create_table_import(
        self,
        connection_rid: str,
        *,
        dataset_rid: str,
        display_name: str,
        import_mode: str,
        config: Dict[str, Any],
        allow_schema_changes: Optional[bool] = None,
        branch_name: Optional[str] = None,
    ) -> Any:
        """Create a table import (``Connection.TableImport.create``, GA).

        Args:
            connection_rid: RID of the connection to import from
            dataset_rid: RID of the output dataset (can't be changed later)
            display_name: Display name of the import
            import_mode: ``SNAPSHOT`` or ``APPEND``
            config: The API's ``CreateTableImportRequestTableImportConfig`` as
                JSON: its ``type`` (``jdbcImportConfig``, ...) and ``query``
            allow_schema_changes: Let runs succeed when the schema changes
            branch_name: Output dataset branch (default: the API's, usually master)

        Returns:
            The created ``TableImport`` model
        """
        return self.service.Connection.TableImport.create(
            connection_rid,
            config=config,
            dataset_rid=dataset_rid,
            display_name=display_name,
            import_mode=import_mode,
            allow_schema_changes=allow_schema_changes,
            branch_name=branch_name,
        )

    def get_table_import(self, connection_rid: str, table_import_rid: str) -> Any:
        """Get a table import (``Connection.TableImport.get``, GA)."""
        return self.service.Connection.TableImport.get(connection_rid, table_import_rid)

    def list_table_imports(
        self,
        connection_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a connection's table imports (``Connection.TableImport.list``, GA).

        Returns:
            The SDK ``ResourceIterator[TableImport]``; constructing it fetched
            exactly one page (``.data``, ``.next_page_token``).
        """
        return self.service.Connection.TableImport.list(
            connection_rid, page_size=page_size, page_token=page_token
        )

    def execute_table_import(self, connection_rid: str, table_import_rid: str) -> str:
        """Run a table import as a build (``Connection.TableImport.execute``, GA).

        Returns:
            The RID of the build that runs the import
        """
        return self.service.Connection.TableImport.execute(
            connection_rid, table_import_rid
        )
