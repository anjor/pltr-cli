"""
Dataset service wrapper for Foundry SDK.
"""

from typing import Any, Optional, List, Dict, Union
from pathlib import Path
import csv

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

    def apply_schema(self, dataset_rid: str, branch: str = "master") -> Dict[str, Any]:
        """
        Apply/infer schema for a dataset using both schema inference and metadata APIs.

        This method performs two sequential API calls:
        1. Schema inference to infer the dataset schema
        2. Schema application to apply the inferred schema to the dataset

        Args:
            dataset_rid: Dataset Resource Identifier
            branch: Dataset branch name (default: "master")

        Returns:
            Schema application result including transaction and version information
        """
        try:
            # Step 1: Call schema inference API to infer the schema
            inference_endpoint = f"/foundry-schema-inference/api/datasets/{dataset_rid}/branches/{branch}/schema"
            inference_response = self._make_request(
                "POST", inference_endpoint, json_data={}
            )

            # Parse the inference response
            inference_result = (
                inference_response.json() if inference_response.text else {}
            )

            # Extract the foundry schema from the inference result
            foundry_schema = inference_result.get("data", {}).get("foundrySchema")
            if not foundry_schema:
                raise RuntimeError(
                    "Schema inference failed: No foundrySchema found in response"
                )

            # Step 2: Call foundry-metadata API to apply the schema
            metadata_endpoint = f"/foundry-metadata/api/schemas/datasets/{dataset_rid}/branches/{branch}"
            metadata_response = self._make_request(
                "POST", metadata_endpoint, json_data=foundry_schema
            )

            # Parse the metadata response
            metadata_result = metadata_response.json() if metadata_response.text else {}

            return {
                "dataset_rid": dataset_rid,
                "branch": branch,
                "status": "Schema applied successfully",
                "inference_result": inference_result,
                "application_result": metadata_result,
                "transaction_rid": metadata_result.get("transactionRid"),
                "version_id": metadata_result.get("versionId"),
            }
        except Exception as e:
            raise RuntimeError(f"Failed to apply schema for dataset {dataset_rid}: {e}")

    def put_schema(
        self,
        dataset_rid: str,
        schema: Any,
        branch: str = "master",
        transaction_rid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Set or update dataset schema.

        Args:
            dataset_rid: Dataset Resource Identifier
            schema: DatasetSchema object with field definitions
            branch: Dataset branch name
            transaction_rid: Optional transaction RID

        Returns:
            Schema update result
        """
        try:
            from foundry_sdk.v2.core.models import DatasetSchema

            # Ensure schema is a DatasetSchema object
            if not isinstance(schema, DatasetSchema):
                raise ValueError("Schema must be a DatasetSchema object")

            result = self.service.Dataset.put_schema(
                dataset_rid=dataset_rid,
                schema=schema,
                branch_name=branch,
                end_transaction_rid=transaction_rid,
            )

            return {
                "dataset_rid": dataset_rid,
                "branch": branch,
                "transaction_rid": transaction_rid,
                "status": "Schema updated successfully",
                "schema": result,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to set schema for dataset {dataset_rid}: {e}")

    def infer_schema_from_csv(
        self, csv_path: Union[str, Path], sample_rows: int = 100
    ) -> Any:
        """
        Infer schema from a CSV file by analyzing headers and sample data.

        Args:
            csv_path: Path to CSV file
            sample_rows: Number of rows to sample for type inference

        Returns:
            DatasetSchema object with inferred field types
        """
        from foundry_sdk.v2.core.models import DatasetSchema, DatasetFieldSchema

        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        def infer_type(values: List[str]) -> tuple[str, bool]:
            """
            Infer type from a list of values.
            Returns (type_name, nullable)
            """
            # Remove empty strings and track if nullable
            non_empty = [v for v in values if v.strip()]
            nullable = len(non_empty) < len(values) or len(non_empty) == 0

            if not non_empty:
                return ("STRING", True)

            # Check for boolean
            bool_values = {"true", "false", "yes", "no", "1", "0"}
            if all(v.lower() in bool_values for v in non_empty):
                return ("BOOLEAN", nullable)

            # Check for integer
            try:
                for v in non_empty:
                    int(v)
                return ("INTEGER", nullable)
            except ValueError:
                pass

            # Check for double
            try:
                for v in non_empty:
                    float(v)
                return ("DOUBLE", nullable)
            except ValueError:
                pass

            # Check for date patterns
            date_patterns = [
                r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD
                r"^\d{2}/\d{2}/\d{4}$",  # MM/DD/YYYY
                r"^\d{2}-\d{2}-\d{4}$",  # DD-MM-YYYY
            ]
            import re

            for pattern in date_patterns:
                if all(re.match(pattern, v) for v in non_empty[:10]):  # Check first 10
                    return ("DATE", nullable)

            # Check for timestamp patterns
            if all(
                "-" in v and ":" in v and len(v) > 10 for v in non_empty[:10]
            ):  # Basic timestamp check
                return ("TIMESTAMP", nullable)

            # Default to string
            return ("STRING", nullable)

        # Read CSV and analyze
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

            if not headers:
                raise ValueError("CSV file has no headers")

            # Collect sample values for each column
            column_values: Dict[str, List[str]] = {col: [] for col in headers}
            for i, row in enumerate(reader):
                if i >= sample_rows:
                    break
                for col in headers:
                    column_values[col].append(row.get(col, ""))

        # Infer types for each column
        fields = []
        for col in headers:
            values = column_values[col]
            field_type, nullable = infer_type(values)

            # Clean column name (remove special characters for field name)
            clean_name = col.strip().replace(" ", "_").replace("-", "_")

            fields.append(
                DatasetFieldSchema(name=clean_name, type=field_type, nullable=nullable)
            )

        return DatasetSchema(field_schema_list=fields)

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
            # Try to extract more detailed error information
            error_msg = str(e).strip()
            error_type = type(e).__name__

            # Check for common HTTP/API errors
            if hasattr(e, "response") and hasattr(e.response, "status_code"):
                status_code = e.response.status_code
                if hasattr(e.response, "text"):
                    response_text = e.response.text[:500]  # Limit to 500 chars
                    error_details = f"HTTP {status_code}: {response_text}"
                else:
                    error_details = f"HTTP {status_code}"
                error_msg = f"{error_details} ({error_type}: {error_msg})"
            elif hasattr(e, "status_code"):
                error_msg = f"HTTP {e.status_code}: {error_msg}"
            elif hasattr(e, "message"):
                error_msg = f"{error_type}: {e.message}"
            else:
                if error_msg:
                    error_msg = f"{error_type}: {error_msg}"
                else:
                    error_msg = f"{error_type} (no additional details available)"

            # Add context about what might have gone wrong
            context_hints = []
            error_lower = error_msg.lower()

            if (
                "permission" in error_lower
                or "forbidden" in error_lower
                or "401" in error_msg
                or "403" in error_msg
            ):
                context_hints.append(
                    "Check your authentication credentials and dataset permissions"
                )
            if "not found" in error_lower or "404" in error_msg:
                context_hints.append(
                    "Verify the dataset RID and transaction RID are correct"
                )
            if "transaction" in error_lower:
                context_hints.append(
                    "Check if the transaction is still open and not expired"
                )
            if "schema" in error_lower or "validation" in error_lower:
                context_hints.append(
                    "The file might not match the expected dataset schema"
                )
            if (
                "invalidparametercombination" in error_lower
                or "invalid parameter" in error_lower
            ):
                context_hints.append(
                    "The combination of parameters (dataset RID, transaction RID, branch) may be invalid"
                )
                context_hints.append(
                    "Try without --transaction-rid, or verify the transaction belongs to this dataset"
                )
            if (
                "opentransactionalreadyexists" in error_lower
                or "transaction already exists" in error_lower
            ):
                context_hints.append(
                    "There's already an open transaction for this dataset"
                )
                context_hints.append(
                    "Use the existing transaction with --transaction-rid, or commit/abort it first"
                )
                context_hints.append(
                    "List transactions with: pltr dataset transactions list "
                    + dataset_rid
                )

            # Try to get more detailed error information from the exception
            if hasattr(e, "__dict__"):
                for attr in ["detail", "details", "error_message", "description"]:
                    if hasattr(e, attr):
                        detail = getattr(e, attr)
                        if detail and str(detail).strip():
                            error_msg += f" - {detail}"
                            break

            full_error = f"Failed to upload file {file_path.name} to dataset {dataset_rid}: {error_msg}"
            if context_hints:
                full_error += f". Suggestions: {'; '.join(context_hints)}"

            raise RuntimeError(full_error)

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

    def get_schedules(self, dataset_rid: str) -> List[Dict[str, Any]]:
        """
        Get schedules that target a specific dataset.

        Args:
            dataset_rid: Dataset Resource Identifier

        Returns:
            List of schedule information dictionaries
        """
        try:
            schedules = self.service.Dataset.get_schedules(dataset_rid=dataset_rid)

            return [
                {
                    "schedule_rid": getattr(schedule, "rid", None),
                    "name": getattr(schedule, "name", None),
                    "description": getattr(schedule, "description", None),
                    "enabled": getattr(schedule, "enabled", None),
                    "created_time": getattr(schedule, "created_time", None),
                }
                for schedule in schedules
            ]
        except Exception as e:
            raise RuntimeError(
                f"Failed to get schedules for dataset {dataset_rid}: {e}"
            )

    def get_jobs(
        self, dataset_rid: str, branch: str = "master"
    ) -> List[Dict[str, Any]]:
        """
        Get jobs for a specific dataset.

        Args:
            dataset_rid: Dataset Resource Identifier
            branch: Dataset branch name

        Returns:
            List of job information dictionaries
        """
        try:
            jobs = self.service.Dataset.jobs(
                dataset_rid=dataset_rid, branch_name=branch
            )

            return [
                {
                    "job_rid": getattr(job, "rid", None),
                    "name": getattr(job, "name", None),
                    "status": getattr(job, "status", None),
                    "created_time": getattr(job, "created_time", None),
                    "started_time": getattr(job, "started_time", None),
                    "completed_time": getattr(job, "completed_time", None),
                }
                for job in jobs
            ]
        except Exception as e:
            raise RuntimeError(f"Failed to get jobs for dataset {dataset_rid}: {e}")

    def delete_branch(self, dataset_rid: str, branch_name: str) -> Dict[str, Any]:
        """
        Delete a branch from a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier
            branch_name: Branch name to delete

        Returns:
            Deletion result information
        """
        try:
            self.service.Dataset.Branch.delete(
                dataset_rid=dataset_rid, branch_name=branch_name
            )

            return {
                "dataset_rid": dataset_rid,
                "branch_name": branch_name,
                "status": "deleted",
                "success": True,
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to delete branch '{branch_name}' from dataset {dataset_rid}: {e}"
            )

    def get_branch(self, dataset_rid: str, branch_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific branch.

        Args:
            dataset_rid: Dataset Resource Identifier
            branch_name: Branch name

        Returns:
            Branch information dictionary
        """
        try:
            branch = self.service.Dataset.Branch.get(
                dataset_rid=dataset_rid, branch_name=branch_name
            )

            return {
                "name": branch_name,
                "dataset_rid": dataset_rid,
                "transaction_rid": getattr(branch, "transaction_rid", None),
                "created_time": getattr(branch, "created_time", None),
                "created_by": getattr(branch, "created_by", None),
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to get branch '{branch_name}' from dataset {dataset_rid}: {e}"
            )

    def get_branch_transactions(
        self, dataset_rid: str, branch_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get transaction history for a specific branch.

        Args:
            dataset_rid: Dataset Resource Identifier
            branch_name: Branch name

        Returns:
            List of transaction information dictionaries
        """
        try:
            transactions = self.service.Dataset.Branch.transactions(
                dataset_rid=dataset_rid, branch_name=branch_name
            )

            return [
                {
                    "transaction_rid": getattr(transaction, "rid", None),
                    "status": getattr(transaction, "status", None),
                    "transaction_type": getattr(transaction, "transaction_type", None),
                    "branch": branch_name,
                    "created_time": getattr(transaction, "created_time", None),
                    "created_by": getattr(transaction, "created_by", None),
                    "committed_time": getattr(transaction, "committed_time", None),
                    "aborted_time": getattr(transaction, "aborted_time", None),
                }
                for transaction in transactions
            ]
        except Exception as e:
            raise RuntimeError(
                f"Failed to get transaction history for branch '{branch_name}' in dataset {dataset_rid}: {e}"
            )

    def delete_file(
        self, dataset_rid: str, file_path: str, branch: str = "master"
    ) -> Dict[str, Any]:
        """
        Delete a file from a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier
            file_path: Path of file within dataset to delete
            branch: Dataset branch name

        Returns:
            Deletion result information
        """
        try:
            self.service.Dataset.File.delete(
                dataset_rid=dataset_rid, file_path=file_path, branch_name=branch
            )

            return {
                "dataset_rid": dataset_rid,
                "file_path": file_path,
                "branch": branch,
                "status": "deleted",
                "success": True,
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to delete file {file_path} from dataset {dataset_rid}: {e}"
            )

    def get_file_info(
        self, dataset_rid: str, file_path: str, branch: str = "master"
    ) -> Dict[str, Any]:
        """
        Get metadata about a file in a dataset.

        Args:
            dataset_rid: Dataset Resource Identifier
            file_path: Path of file within dataset
            branch: Dataset branch name

        Returns:
            File metadata information
        """
        try:
            file_info = self.service.Dataset.File.get(
                dataset_rid=dataset_rid, file_path=file_path, branch_name=branch
            )

            return {
                "path": file_path,
                "dataset_rid": dataset_rid,
                "branch": branch,
                "size_bytes": getattr(file_info, "size_bytes", None),
                "last_modified": getattr(file_info, "last_modified", None),
                "transaction_rid": getattr(file_info, "transaction_rid", None),
                "created_time": getattr(file_info, "created_time", None),
                "content_type": getattr(file_info, "content_type", None),
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to get file info for {file_path} in dataset {dataset_rid}: {e}"
            )

    def get_transaction_build(
        self, dataset_rid: str, transaction_rid: str
    ) -> Dict[str, Any]:
        """
        Get build information for a transaction.

        Args:
            dataset_rid: Dataset Resource Identifier
            transaction_rid: Transaction Resource Identifier

        Returns:
            Build information dictionary
        """
        try:
            build = self.service.Dataset.Transaction.build(
                dataset_rid=dataset_rid, transaction_rid=transaction_rid
            )

            return {
                "transaction_rid": transaction_rid,
                "dataset_rid": dataset_rid,
                "build_rid": getattr(build, "rid", None),
                "status": getattr(build, "status", None),
                "started_time": getattr(build, "started_time", None),
                "completed_time": getattr(build, "completed_time", None),
                "duration_ms": getattr(build, "duration_ms", None),
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to get build for transaction {transaction_rid}: {e}"
            )

    def get_view(self, view_rid: str, branch: str = "master") -> Dict[str, Any]:
        """
        Get detailed information about a view.

        Args:
            view_rid: View Resource Identifier
            branch: Branch name

        Returns:
            View information dictionary
        """
        try:
            view = self.service.Dataset.View.get(
                dataset_rid=view_rid, branch_name=branch
            )

            return {
                "view_rid": view_rid,
                "name": getattr(view, "name", None),
                "description": getattr(view, "description", None),
                "branch": branch,
                "created_time": getattr(view, "created_time", None),
                "created_by": getattr(view, "created_by", None),
                "backing_datasets": getattr(view, "backing_datasets", []),
                "primary_key": getattr(view, "primary_key", None),
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get view {view_rid}: {e}")

    def add_backing_datasets(
        self, view_rid: str, dataset_rids: List[str]
    ) -> Dict[str, Any]:
        """
        Add backing datasets to a view.

        Args:
            view_rid: View Resource Identifier
            dataset_rids: List of dataset RIDs to add as backing datasets

        Returns:
            Operation result
        """
        try:
            result = self.service.Dataset.View.add_backing_datasets(
                dataset_rid=view_rid, backing_datasets=dataset_rids
            )

            return {
                "view_rid": view_rid,
                "added_datasets": dataset_rids,
                "success": True,
                "result": result,
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to add backing datasets to view {view_rid}: {e}"
            )

    def remove_backing_datasets(
        self, view_rid: str, dataset_rids: List[str]
    ) -> Dict[str, Any]:
        """
        Remove backing datasets from a view.

        Args:
            view_rid: View Resource Identifier
            dataset_rids: List of dataset RIDs to remove as backing datasets

        Returns:
            Operation result
        """
        try:
            result = self.service.Dataset.View.remove_backing_datasets(
                dataset_rid=view_rid, backing_datasets=dataset_rids
            )

            return {
                "view_rid": view_rid,
                "removed_datasets": dataset_rids,
                "success": True,
                "result": result,
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to remove backing datasets from view {view_rid}: {e}"
            )

    def replace_backing_datasets(
        self, view_rid: str, dataset_rids: List[str]
    ) -> Dict[str, Any]:
        """
        Replace all backing datasets in a view.

        Args:
            view_rid: View Resource Identifier
            dataset_rids: List of dataset RIDs to set as backing datasets

        Returns:
            Operation result
        """
        try:
            result = self.service.Dataset.View.replace_backing_datasets(
                dataset_rid=view_rid, backing_datasets=dataset_rids
            )

            return {
                "view_rid": view_rid,
                "new_datasets": dataset_rids,
                "success": True,
                "result": result,
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to replace backing datasets in view {view_rid}: {e}"
            )

    def add_primary_key(self, view_rid: str, key_fields: List[str]) -> Dict[str, Any]:
        """
        Add a primary key to a view.

        Args:
            view_rid: View Resource Identifier
            key_fields: List of field names to use as primary key

        Returns:
            Operation result
        """
        try:
            result = self.service.Dataset.View.add_primary_key(
                dataset_rid=view_rid, primary_key=key_fields
            )

            return {
                "view_rid": view_rid,
                "primary_key_fields": key_fields,
                "success": True,
                "result": result,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to add primary key to view {view_rid}: {e}")

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
