"""
Dataset service wrapper for Foundry SDK.
"""

from typing import Any, Optional, List, Dict, Union
from pathlib import Path

from .base import BaseService


class DatasetService(BaseService):
    """Service wrapper for Foundry dataset operations."""

    def _get_service(self) -> Any:
        """Get the Foundry datasets service."""
        return self.client.datasets

    # list_datasets method removed - not supported by foundry-platform-sdk v1.27.0

    def get_dataset(self, dataset_rid: str) -> Dict[str, Any]:
        """
        Get information about a specific dataset.

        Args:
            dataset_rid: Dataset Resource Identifier

        Returns:
            Dataset information dictionary
        """
        try:
            # Use the v2 API's Dataset.get method
            dataset = self.service.Dataset.get(dataset_rid)
            return self._format_dataset_info(dataset)
        except Exception as e:
            raise RuntimeError(f"Failed to get dataset {dataset_rid}: {e}")

    def get_schema(self, dataset_rid: str) -> Dict[str, Any]:
        """
        Get dataset schema.

        Args:
            dataset_rid: Dataset Resource Identifier

        Returns:
            Schema information
        """
        try:
            schema = self.service.Dataset.get_schema(dataset_rid)
            return {
                "dataset_rid": dataset_rid,
                "schema": schema,
                "type": str(type(schema)),
                "status": "Schema retrieved successfully",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get schema for dataset {dataset_rid}: {e}")

    def create_dataset(
        self, name: str, parent_folder_rid: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new dataset.

        Args:
            name: Dataset name
            parent_folder_rid: Parent folder RID (optional)

        Returns:
            Created dataset information
        """
        try:
            # Try the v2 API first (Dataset.create)
            dataset = self.service.Dataset.create(
                name=name, parent_folder_rid=parent_folder_rid
            )
            return self._format_dataset_info(dataset)
        except AttributeError:
            # Fallback to service.create_dataset
            try:
                dataset = self.service.create_dataset(
                    name=name, parent_folder_rid=parent_folder_rid
                )
                return self._format_dataset_info(dataset)
            except Exception as e:
                raise RuntimeError(f"Failed to create dataset '{name}': {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to create dataset '{name}': {e}")

    def read_table(self, dataset_rid: str, format: str = "arrow") -> Any:
        """
        Read dataset as a table.

        Args:
            dataset_rid: Dataset Resource Identifier
            format: Output format (arrow, pandas, etc.)

        Returns:
            Table data in specified format
        """
        try:
            # Try the v2 API first (Dataset.read_table)
            return self.service.Dataset.read_table(dataset_rid, format=format)
        except AttributeError:
            # Fallback to service.read_table
            try:
                return self.service.read_table(dataset_rid, format=format)
            except Exception as e:
                raise RuntimeError(f"Failed to read dataset {dataset_rid}: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to read dataset {dataset_rid}: {e}")

    def delete_dataset(self, dataset_rid: str) -> bool:
        """
        Delete a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier

        Returns:
            True if deletion was successful
        """
        try:
            self.service.delete_dataset(dataset_rid)
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to delete dataset {dataset_rid}: {e}")

    def upload_file(
        self,
        dataset_rid: str,
        file_path: Union[str, Path],
        branch: str = "master",
        transaction_rid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier
            file_path: Path to file to upload
            branch: Dataset branch name
            transaction_rid: Transaction RID (optional)

        Returns:
            Upload result information
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # Read file content as bytes
            with open(file_path, "rb") as f:
                file_content = f.read()

            # Use the correct method signature with body parameter
            result = self.service.Dataset.File.upload(
                dataset_rid=dataset_rid,
                file_path=file_path.name,  # Just the filename, not full path
                body=file_content,
                branch_name=branch,
                transaction_rid=transaction_rid,
            )

            return {
                "dataset_rid": dataset_rid,
                "file_path": str(file_path),
                "branch": branch,
                "size_bytes": file_path.stat().st_size,
                "uploaded": True,
                "transaction_rid": getattr(result, "transaction_rid", transaction_rid),
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to upload file {file_path} to dataset {dataset_rid}: {e}"
            )

    def download_file(
        self,
        dataset_rid: str,
        file_path: str,
        output_path: Union[str, Path],
        branch: str = "master",
    ) -> Dict[str, Any]:
        """
        Download a file from a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier
            file_path: Path of file within dataset
            output_path: Local path to save the downloaded file
            branch: Dataset branch name

        Returns:
            Download result information
        """
        output_path = Path(output_path)

        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            file_content = self.service.Dataset.File.read(
                dataset_rid=dataset_rid, file_path=file_path, branch_name=branch
            )

            # Write file content to disk
            with open(output_path, "wb") as f:
                if hasattr(file_content, "read"):
                    # If it's a stream
                    f.write(file_content.read())
                else:
                    # If it's bytes
                    f.write(file_content)

            return {
                "dataset_rid": dataset_rid,
                "file_path": file_path,
                "output_path": str(output_path),
                "branch": branch,
                "size_bytes": output_path.stat().st_size,
                "downloaded": True,
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to download file {file_path} from dataset {dataset_rid}: {e}"
            )

    def list_files(
        self, dataset_rid: str, branch: str = "master"
    ) -> List[Dict[str, Any]]:
        """
        List files in a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier
            branch: Dataset branch name

        Returns:
            List of file information dictionaries
        """
        try:
            files = self.service.Dataset.File.list(
                dataset_rid=dataset_rid, branch_name=branch
            )

            return [
                {
                    "path": file.path,
                    "size_bytes": getattr(file, "size_bytes", None),
                    "last_modified": getattr(file, "last_modified", None),
                    "transaction_rid": getattr(file, "transaction_rid", None),
                }
                for file in files
            ]
        except Exception as e:
            raise RuntimeError(f"Failed to list files in dataset {dataset_rid}: {e}")

    def get_branches(self, dataset_rid: str) -> List[Dict[str, Any]]:
        """
        Get list of branches for a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier

        Returns:
            List of branch information dictionaries
        """
        try:
            branches = self.service.list_branches(dataset_rid=dataset_rid)

            return [
                {
                    "name": branch.name,
                    "transaction_rid": getattr(branch, "transaction_rid", None),
                    "created_time": getattr(branch, "created_time", None),
                    "created_by": getattr(branch, "created_by", None),
                }
                for branch in branches
            ]
        except Exception as e:
            raise RuntimeError(f"Failed to get branches for dataset {dataset_rid}: {e}")

    def create_branch(
        self, dataset_rid: str, branch_name: str, parent_branch: str = "master"
    ) -> Dict[str, Any]:
        """
        Create a new branch for a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier
            branch_name: Name for the new branch
            parent_branch: Parent branch to branch from

        Returns:
            Created branch information
        """
        try:
            branch = self.service.create_branch(
                dataset_rid=dataset_rid,
                branch_name=branch_name,
                parent_branch=parent_branch,
            )

            return {
                "name": branch.name,
                "dataset_rid": dataset_rid,
                "parent_branch": parent_branch,
                "transaction_rid": getattr(branch, "transaction_rid", None),
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to create branch '{branch_name}' for dataset {dataset_rid}: {e}"
            )

    def create_transaction(
        self, dataset_rid: str, branch: str = "master", transaction_type: str = "APPEND"
    ) -> Dict[str, Any]:
        """
        Create a new transaction for a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier
            branch: Dataset branch name
            transaction_type: Transaction type (APPEND, UPDATE, SNAPSHOT, DELETE)

        Returns:
            Transaction information dictionary
        """
        try:
            # Use the v2 API's Dataset.Transaction.create method
            transaction = self.service.Dataset.Transaction.create(
                dataset_rid=dataset_rid,
                transaction_type=transaction_type,
                branch_name=branch,
            )

            return {
                "transaction_rid": getattr(transaction, "rid", None),
                "dataset_rid": dataset_rid,
                "branch": branch,
                "transaction_type": transaction_type,
                "status": getattr(transaction, "status", "OPEN"),
                "created_time": getattr(transaction, "created_time", None),
                "created_by": getattr(transaction, "created_by", None),
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to create transaction for dataset {dataset_rid}: {e}"
            )

    def commit_transaction(
        self, dataset_rid: str, transaction_rid: str
    ) -> Dict[str, Any]:
        """
        Commit an open transaction.

        Args:
            dataset_rid: Dataset Resource Identifier
            transaction_rid: Transaction Resource Identifier

        Returns:
            Transaction commit result
        """
        try:
            # Use the v2 API Dataset.Transaction.commit method
            self.service.Dataset.Transaction.commit(
                dataset_rid=dataset_rid, transaction_rid=transaction_rid
            )

            return {
                "transaction_rid": transaction_rid,
                "dataset_rid": dataset_rid,
                "status": "COMMITTED",
                "committed_time": None,  # Would need to get this from a status call
                "success": True,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to commit transaction {transaction_rid}: {e}")

    def abort_transaction(
        self, dataset_rid: str, transaction_rid: str
    ) -> Dict[str, Any]:
        """
        Abort an open transaction.

        Args:
            dataset_rid: Dataset Resource Identifier
            transaction_rid: Transaction Resource Identifier

        Returns:
            Transaction abort result
        """
        try:
            # Use the v2 API Dataset.Transaction.abort method
            self.service.Dataset.Transaction.abort(
                dataset_rid=dataset_rid, transaction_rid=transaction_rid
            )

            return {
                "transaction_rid": transaction_rid,
                "dataset_rid": dataset_rid,
                "status": "ABORTED",
                "aborted_time": None,  # Would need to get this from a status call
                "success": True,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to abort transaction {transaction_rid}: {e}")

    def get_transaction_status(
        self, dataset_rid: str, transaction_rid: str
    ) -> Dict[str, Any]:
        """
        Get the status of a specific transaction.

        Args:
            dataset_rid: Dataset Resource Identifier
            transaction_rid: Transaction Resource Identifier

        Returns:
            Transaction status information
        """
        try:
            # Use the v2 API Dataset.Transaction.get method
            transaction = self.service.Dataset.Transaction.get(
                dataset_rid=dataset_rid, transaction_rid=transaction_rid
            )

            return {
                "transaction_rid": transaction_rid,
                "dataset_rid": dataset_rid,
                "status": getattr(transaction, "status", None),
                "transaction_type": getattr(transaction, "transaction_type", None),
                "branch": getattr(transaction, "branch", None),
                "created_time": getattr(transaction, "created_time", None),
                "created_by": getattr(transaction, "created_by", None),
                "committed_time": getattr(transaction, "committed_time", None),
                "aborted_time": getattr(transaction, "aborted_time", None),
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to get transaction status {transaction_rid}: {e}"
            )

    def get_transactions(
        self, dataset_rid: str, branch: str = "master"
    ) -> List[Dict[str, Any]]:
        """
        Get list of transactions for a dataset branch.

        Args:
            dataset_rid: Dataset Resource Identifier
            branch: Dataset branch name

        Returns:
            List of transaction information dictionaries
        """
        try:
            # Use the v2 API Dataset.Transaction for transaction listing
            # Note: This method may not exist in all SDK versions
            transactions = self.service.Dataset.Transaction.list(
                dataset_rid=dataset_rid, branch_name=branch
            )

            return [
                {
                    "transaction_rid": getattr(transaction, "rid", None),
                    "status": getattr(transaction, "status", None),
                    "transaction_type": getattr(transaction, "transaction_type", None),
                    "branch": getattr(transaction, "branch", branch),
                    "created_time": getattr(transaction, "created_time", None),
                    "created_by": getattr(transaction, "created_by", None),
                    "committed_time": getattr(transaction, "committed_time", None),
                    "aborted_time": getattr(transaction, "aborted_time", None),
                }
                for transaction in transactions
            ]
        except AttributeError:
            # Method not available in this SDK version
            raise NotImplementedError(
                "Transaction listing is not supported by this SDK version. "
                "This feature may require a newer version of foundry-platform-python."
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to get transactions for dataset {dataset_rid}: {e}"
            )

    def get_views(self, dataset_rid: str) -> List[Dict[str, Any]]:
        """
        Get list of views for a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier

        Returns:
            List of view information dictionaries
        """
        try:
            # Note: This method may not be available in all SDK versions
            views = self.service.list_views(dataset_rid=dataset_rid)

            return [
                {
                    "view_rid": getattr(view, "rid", None),
                    "name": getattr(view, "name", None),
                    "description": getattr(view, "description", None),
                    "created_time": getattr(view, "created_time", None),
                    "created_by": getattr(view, "created_by", None),
                }
                for view in views
            ]
        except AttributeError:
            # Method not available in this SDK version
            raise NotImplementedError(
                "View listing is not supported by this SDK version. "
                "This feature may require a newer version of foundry-platform-python."
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get views for dataset {dataset_rid}: {e}")

    def create_view(
        self, dataset_rid: str, view_name: str, description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new view for a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier
            view_name: Name for the new view
            description: Optional description for the view

        Returns:
            Created view information
        """
        try:
            # Note: This method may not be available in all SDK versions
            view = self.service.create_view(
                dataset_rid=dataset_rid,
                name=view_name,
                description=description,
            )

            return {
                "view_rid": getattr(view, "rid", None),
                "name": view_name,
                "description": description,
                "dataset_rid": dataset_rid,
                "created_time": getattr(view, "created_time", None),
                "created_by": getattr(view, "created_by", None),
            }
        except AttributeError:
            # Method not available in this SDK version
            raise NotImplementedError(
                "View creation is not supported by this SDK version. "
                "This feature may require a newer version of foundry-platform-python."
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to create view '{view_name}' for dataset {dataset_rid}: {e}"
            )

    def _format_dataset_info(self, dataset: Any) -> Dict[str, Any]:
        """
        Format dataset information for consistent output.

        Args:
            dataset: Dataset object from Foundry SDK

        Returns:
            Formatted dataset information dictionary
        """
        # The v2 Dataset object has different attributes
        return {
            "rid": getattr(dataset, "rid", "unknown"),
            "name": getattr(dataset, "name", "Unknown"),
            "description": getattr(dataset, "description", ""),
            "path": getattr(dataset, "path", None),
            "created": getattr(dataset, "created", None),
            "modified": getattr(dataset, "modified", None),
            # Try to get additional attributes that might exist
            "created_time": getattr(dataset, "created_time", None),
            "created_by": getattr(dataset, "created_by", None),
            "last_modified": getattr(dataset, "last_modified", None),
            "size_bytes": getattr(dataset, "size_bytes", None),
            "schema_id": getattr(dataset, "schema_id", None),
            "parent_folder_rid": getattr(dataset, "parent_folder_rid", None),
        }
