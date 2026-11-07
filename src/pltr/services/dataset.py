"""
Dataset service wrapper for the Foundry SDK datasets API (``client.datasets``).

Methods return SDK models, SDK iterators (constructing one fetches exactly one
page) or bytes unchanged, and let SDK exceptions propagate so the error layer
can classify them. Beta endpoints (``Dataset.transactions``,
``Dataset.jobs``, ``Branch.transactions`` and ``Transaction.build``) are
called with a literal ``preview=True``; GA endpoints never get ``preview``.

``apply_schema`` is a labeled direct-HTTP exception: schema inference has no
public API, so it calls Foundry's schema-inference and foundry-metadata
endpoints through ``BaseService._make_request``.
"""

import csv
import re
from contextlib import contextmanager
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from urllib.parse import quote

from ..contract import ExitCode, PltrError, write_bytes_atomically
from .base import BaseService

#: Types of a dataset transaction.
TRANSACTION_TYPES = ("APPEND", "UPDATE", "SNAPSHOT", "DELETE")

#: Readers Foundry can use to read a dataset's files with a schema.
DATAFRAME_READERS = ("AVRO", "CSV", "PARQUET", "DATASOURCE")

#: Sort keys of ``Dataset.jobs``.
JOB_SORT_TYPES = ("BY_STARTED_TIME", "BY_FINISHED_TIME")

#: The schema-inference and foundry-metadata endpoints ``apply_schema`` calls.
SCHEMA_INFERENCE_ENDPOINT = (
    "/foundry-schema-inference/api/datasets/{datasetRid}/branches/{branchName}/schema"
)
SCHEMA_METADATA_ENDPOINT = (
    "/foundry-metadata/api/schemas/datasets/{datasetRid}/branches/{branchName}"
)

#: A backing dataset of a view: (dataset RID, branch or None for the view's).
BackingDataset = Tuple[str, Optional[str]]


class DatasetService(BaseService):
    """Service wrapper for Foundry dataset operations (``client.datasets``)."""

    def _get_service(self) -> Any:
        """Get the Foundry datasets service."""
        return self.client.datasets

    # ----------------------------------------------------------- datasets

    def get_dataset(self, dataset_rid: str) -> Any:
        """Get a dataset (``Dataset.get``, GA); returns a ``Dataset`` model."""
        return self.service.Dataset.get(dataset_rid)

    def create(self, name: str, parent_folder_rid: str) -> Any:
        """Create an empty dataset (``Dataset.create``, GA).

        Args:
            name: Name of the new dataset
            parent_folder_rid: RID of the project or folder to create it in

        Returns:
            The created ``Dataset`` model
        """
        return self.service.Dataset.create(
            name=name, parent_folder_rid=parent_folder_rid
        )

    def read_table(
        self,
        dataset_rid: str,
        *,
        format: str = "ARROW",
        branch: Optional[str] = None,
        columns: Optional[List[str]] = None,
        row_limit: Optional[int] = None,
        start_transaction_rid: Optional[str] = None,
        end_transaction_rid: Optional[str] = None,
    ) -> Any:
        """Read a dataset's rows (``Dataset.read_table``, GA).

        Args:
            format: ``ARROW`` (an Arrow IPC stream) or ``CSV``

        Returns:
            The SDK's ``TableResponse`` (bytes; ``to_pyarrow()`` decodes an
            Arrow stream), or ``None`` for an empty response body.
        """
        return self.service.Dataset.read_table(
            dataset_rid,
            format=format,
            branch_name=branch,
            columns=columns,
            row_limit=row_limit,
            start_transaction_rid=start_transaction_rid,
            end_transaction_rid=end_transaction_rid,
        )

    def preview_table(
        self,
        dataset_rid: str,
        *,
        limit: int = 10,
        branch: Optional[str] = None,
        columns: Optional[List[str]] = None,
    ) -> Any:
        """Read up to ``limit`` rows (``Dataset.read_table`` in Arrow format).

        Returns:
            A ``pyarrow.Table`` (one without columns for an empty response);
            ``pltr.contract.table_rows`` turns it into JSON-safe rows.
        """
        response = self.read_table(
            dataset_rid,
            format="ARROW",
            branch=branch,
            columns=columns,
            row_limit=limit,
        )
        return arrow_table(response)

    # ------------------------------------------------------------- schema

    def get_dataset_schema(
        self,
        dataset_rid: str,
        *,
        branch: Optional[str] = None,
        end_transaction_rid: Optional[str] = None,
        version_id: Optional[str] = None,
    ) -> Any:
        """Get a dataset's schema (``Dataset.get_schema``, GA).

        Returns:
            ``GetDatasetSchemaResponse`` (``branch_name``,
            ``end_transaction_rid``, ``schema_``, ``version_id``)
        """
        return self.service.Dataset.get_schema(
            dataset_rid,
            branch_name=branch,
            end_transaction_rid=end_transaction_rid,
            version_id=version_id,
        )

    def put_schema(
        self,
        dataset_rid: str,
        schema: Union[Any, Mapping[str, Any]],
        *,
        branch: Optional[str] = None,
        transaction_rid: Optional[str] = None,
        dataframe_reader: Optional[str] = None,
    ) -> Any:
        """Replace a dataset's schema (``Dataset.put_schema``, GA).

        Args:
            schema: a ``DatasetSchema`` model, or its JSON form
                (``{"fieldSchemaList": [...]}``)
            branch: branch name (default: the dataset's default branch)
            transaction_rid: end transaction the schema applies to (default:
                the latest committed transaction)
            dataframe_reader: ``AVRO``, ``CSV``, ``PARQUET`` (the API's
                default) or ``DATASOURCE``

        Returns:
            ``GetDatasetSchemaResponse`` for the new schema
        """
        from foundry_sdk.v2.core.models import DatasetSchema

        if not isinstance(schema, DatasetSchema):
            schema = DatasetSchema.model_validate(schema)
        return self.service.Dataset.put_schema(
            dataset_rid,
            schema=schema,
            branch_name=branch,
            end_transaction_rid=transaction_rid,
            dataframe_reader=dataframe_reader,
        )

    def apply_schema(self, dataset_rid: str, branch: str = "master") -> Any:
        """Infer a dataset's schema from its files and apply it to a branch.

        Labeled direct-HTTP exception (no public API infers schemas): POSTs to
        the schema-inference endpoint, then sends the inferred
        ``foundrySchema`` to the foundry-metadata endpoint.

        Returns:
            The foundry-metadata response body (parsed JSON), or ``None`` when
            the response has no body.

        Raises:
            requests.HTTPError: An endpoint returned an error status
            PltrError: The inference response contains no schema
        """
        path_params = {
            "datasetRid": quote(dataset_rid, safe=""),
            "branchName": quote(branch, safe=""),
        }
        inference = self._make_request(
            "POST",
            SCHEMA_INFERENCE_ENDPOINT.format(**path_params),
            json_data={},
        )
        inferred = inference.json() if inference.content else None
        data = inferred.get("data") if isinstance(inferred, dict) else None
        foundry_schema = data.get("foundrySchema") if isinstance(data, dict) else None
        if not foundry_schema:
            raise PltrError(
                f"Schema inference for dataset {dataset_rid} on branch '{branch}' "
                "returned no schema (no data.foundrySchema in the response).",
                error_type="api_error",
                exit_code=ExitCode.API,
                hint="Check that the branch has committed files in a format "
                "Foundry can infer a schema from (for example CSV).",
            )
        applied = self._make_request(
            "POST",
            SCHEMA_METADATA_ENDPOINT.format(**path_params),
            json_data=foundry_schema,
        )
        return applied.json() if applied.content else None

    # ----------------------------------------------------------- branches

    def list_branches(
        self,
        dataset_rid: str,
        *,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a dataset's branches (``Branch.list``, GA).

        Returns:
            The SDK ``ResourceIterator[Branch]``; constructing it fetched one
            page (``.data``, ``.next_page_token``).
        """
        return self.service.Dataset.Branch.list(
            dataset_rid, page_size=page_size, page_token=page_token
        )

    def get_branch(self, dataset_rid: str, branch_name: str) -> Any:
        """Get a branch (``Branch.get``, GA); returns a ``Branch`` model."""
        return self.service.Dataset.Branch.get(dataset_rid, branch_name)

    def create_branch(
        self,
        dataset_rid: str,
        branch_name: str,
        *,
        transaction_rid: Optional[str] = None,
    ) -> Any:
        """Create a branch (``Branch.create``, GA); returns a ``Branch`` model.

        Args:
            transaction_rid: the committed transaction the new branch points
                to; without it the branch has no transactions
        """
        return self.service.Dataset.Branch.create(
            dataset_rid, name=branch_name, transaction_rid=transaction_rid
        )

    def delete_branch(self, dataset_rid: str, branch_name: str) -> None:
        """Delete a branch (``Branch.delete``, GA)."""
        self.service.Dataset.Branch.delete(dataset_rid, branch_name)

    def list_branch_transactions(
        self,
        dataset_rid: str,
        branch_name: str,
        *,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a branch's transactions, newest first.

        ``Branch.transactions`` is beta (``preview=True``).

        Returns:
            The SDK ``ResourceIterator[Transaction]`` (one page fetched)
        """
        return self.service.Dataset.Branch.transactions(
            dataset_rid,
            branch_name,
            page_size=page_size,
            page_token=page_token,
            preview=True,
        )

    # -------------------------------------------------------------- files

    def list_dataset_files(
        self,
        dataset_rid: str,
        *,
        branch: Optional[str] = None,
        path_prefix: Optional[str] = None,
        start_transaction_rid: Optional[str] = None,
        end_transaction_rid: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a dataset's files (``File.list``, GA).

        Returns:
            The SDK ``ResourceIterator[File]``; constructing it fetched one
            page. Iterating it fetches the remaining pages too.
        """
        return self.service.Dataset.File.list(
            dataset_rid,
            branch_name=branch,
            path_prefix=path_prefix,
            start_transaction_rid=start_transaction_rid,
            end_transaction_rid=end_transaction_rid,
            page_size=page_size,
            page_token=page_token,
        )

    def get_file(
        self,
        dataset_rid: str,
        file_path: str,
        *,
        branch: Optional[str] = None,
        start_transaction_rid: Optional[str] = None,
        end_transaction_rid: Optional[str] = None,
    ) -> Any:
        """Get a file's metadata (``File.get``, GA); returns a ``File`` model."""
        return self.service.Dataset.File.get(
            dataset_rid,
            file_path,
            branch_name=branch,
            start_transaction_rid=start_transaction_rid,
            end_transaction_rid=end_transaction_rid,
        )

    def upload_file(
        self,
        dataset_rid: str,
        local_path: Union[str, Path],
        dataset_path: str,
        *,
        branch: Optional[str] = None,
        transaction_rid: Optional[str] = None,
        transaction_type: Optional[str] = None,
    ) -> Any:
        """Upload one local file (``File.upload``, GA).

        The API takes the whole file in one request, so the file is read into
        memory. Pass either ``branch`` (the upload opens and commits its own
        transaction of ``transaction_type``, UPDATE by default) or
        ``transaction_rid`` (an open transaction), not both: the API rejects
        the combination.

        Returns:
            The uploaded ``File`` model
        """
        if branch is not None and transaction_rid is not None:
            raise ValueError("Pass either branch or transaction_rid, not both")
        body = Path(local_path).read_bytes()
        return self.service.Dataset.File.upload(
            dataset_rid,
            dataset_path,
            body,
            branch_name=branch,
            transaction_rid=transaction_rid,
            transaction_type=transaction_type,
        )

    @contextmanager
    def open_file_content(
        self,
        dataset_rid: str,
        file_path: str,
        *,
        branch: Optional[str] = None,
        start_transaction_rid: Optional[str] = None,
        end_transaction_rid: Optional[str] = None,
    ) -> Iterator[Iterator[bytes]]:
        """Stream a file's content (``File.content``, GA).

        A context manager that yields the content as an iterator of byte
        chunks, so large files are never held in memory; the connection
        stays open until the block ends. API errors are raised on entry.
        """
        with self.service.Dataset.File.with_streaming_response.content(
            dataset_rid,
            file_path,
            branch_name=branch,
            start_transaction_rid=start_transaction_rid,
            end_transaction_rid=end_transaction_rid,
        ) as response:
            yield response.iter_bytes()

    def download_file(
        self,
        dataset_rid: str,
        file_path: str,
        output_path: Union[str, Path],
        *,
        branch: Optional[str] = None,
        start_transaction_rid: Optional[str] = None,
        end_transaction_rid: Optional[str] = None,
    ) -> int:
        """Stream a file's content to ``output_path`` (``File.content``, GA).

        The content is streamed to a temporary file next to ``output_path``
        and moved into place when complete, so a failed download never
        leaves a partial file (or clobbers an existing one). Parent
        directories are created.

        Returns:
            Number of bytes written
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with self.open_file_content(
            dataset_rid,
            file_path,
            branch=branch,
            start_transaction_rid=start_transaction_rid,
            end_transaction_rid=end_transaction_rid,
        ) as chunks:
            return write_bytes_atomically(output, chunks)

    def delete_file(
        self,
        dataset_rid: str,
        file_path: str,
        *,
        branch: Optional[str] = None,
        transaction_rid: Optional[str] = None,
    ) -> None:
        """Delete a file (``File.delete``, GA).

        Pass either ``branch`` (the delete opens and commits its own DELETE
        transaction) or ``transaction_rid`` (an open DELETE transaction).
        """
        if branch is not None and transaction_rid is not None:
            raise ValueError("Pass either branch or transaction_rid, not both")
        self.service.Dataset.File.delete(
            dataset_rid,
            file_path,
            branch_name=branch,
            transaction_rid=transaction_rid,
        )

    # ------------------------------------------------------- transactions

    def start_transaction(
        self,
        dataset_rid: str,
        *,
        transaction_type: str = "APPEND",
        branch: Optional[str] = None,
    ) -> Any:
        """Open a transaction (``Transaction.create``, GA).

        Returns:
            The new ``Transaction`` model (status ``OPEN``)
        """
        return self.service.Dataset.Transaction.create(
            dataset_rid, transaction_type=transaction_type, branch_name=branch
        )

    def get_transaction(self, dataset_rid: str, transaction_rid: str) -> Any:
        """Get a transaction (``Transaction.get``, GA); returns a ``Transaction``."""
        return self.service.Dataset.Transaction.get(dataset_rid, transaction_rid)

    def commit_transaction(self, dataset_rid: str, transaction_rid: str) -> Any:
        """Commit an open transaction (``Transaction.commit``, GA).

        Returns:
            The committed ``Transaction`` model
        """
        return self.service.Dataset.Transaction.commit(dataset_rid, transaction_rid)

    def abort_transaction(self, dataset_rid: str, transaction_rid: str) -> Any:
        """Abort an open transaction (``Transaction.abort``, GA).

        Returns:
            The aborted ``Transaction`` model
        """
        return self.service.Dataset.Transaction.abort(dataset_rid, transaction_rid)

    def list_transactions(
        self,
        dataset_rid: str,
        *,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a dataset's transactions, newest first.

        ``Dataset.transactions`` is beta (``preview=True``).

        Returns:
            The SDK ``ResourceIterator[Transaction]`` (one page fetched)
        """
        return self.service.Dataset.transactions(
            dataset_rid, page_size=page_size, page_token=page_token, preview=True
        )

    def get_transaction_build(
        self, dataset_rid: str, transaction_rid: str
    ) -> Optional[str]:
        """The RID of the build that computed a transaction, if any.

        ``Transaction.build`` is beta (``preview=True``). Returns ``None``
        when no build produced the transaction (for example an upload).
        """
        return self.service.Dataset.Transaction.build(
            dataset_rid, transaction_rid, preview=True
        )

    # -------------------------------------------------------------- views

    def create_view(
        self,
        view_name: str,
        *,
        parent_folder_rid: str,
        backing_datasets: Sequence[BackingDataset],
        branch: Optional[str] = None,
    ) -> Any:
        """Create a view (``View.create``, GA); returns a ``View`` model.

        Args:
            backing_datasets: ``(dataset RID, branch or None)`` pairs; a
                ``None`` branch means the view's branch
            branch: the view's branch (default: master on most enrollments)
        """
        return self.service.View.create(
            backing_datasets=_view_backing_datasets(backing_datasets),
            parent_folder_rid=parent_folder_rid,
            view_name=view_name,
            branch=branch,
        )

    def get_view(self, view_rid: str, *, branch: Optional[str] = None) -> Any:
        """Get a view (``View.get``, GA); returns a ``View`` model."""
        return self.service.View.get(view_rid, branch=branch)

    def add_backing_datasets(
        self,
        view_rid: str,
        backing_datasets: Sequence[BackingDataset],
        *,
        branch: Optional[str] = None,
    ) -> Any:
        """Add backing datasets to a view (``View.add_backing_datasets``, GA).

        Returns:
            The updated ``View`` model
        """
        return self.service.View.add_backing_datasets(
            view_rid,
            backing_datasets=_view_backing_datasets(backing_datasets),
            branch=branch,
        )

    def remove_backing_datasets(
        self,
        view_rid: str,
        backing_datasets: Sequence[BackingDataset],
        *,
        branch: Optional[str] = None,
    ) -> Any:
        """Remove backing datasets from a view (``View.remove_backing_datasets``).

        GA. Returns the updated ``View`` model.
        """
        return self.service.View.remove_backing_datasets(
            view_rid,
            backing_datasets=_view_backing_datasets(backing_datasets),
            branch=branch,
        )

    def replace_backing_datasets(
        self,
        view_rid: str,
        backing_datasets: Sequence[BackingDataset],
        *,
        branch: Optional[str] = None,
    ) -> Any:
        """Replace a view's backing datasets (``View.replace_backing_datasets``).

        GA. Returns the updated ``View`` model.
        """
        return self.service.View.replace_backing_datasets(
            view_rid,
            backing_datasets=_view_backing_datasets(backing_datasets),
            branch=branch,
        )

    def add_primary_key(
        self,
        view_rid: str,
        columns: List[str],
        *,
        latest_wins_columns: Optional[List[str]] = None,
        deletion_column: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Any:
        """Add a primary key to a view that has none (``View.add_primary_key``).

        GA. Without ``latest_wins_columns`` the key values are declared
        unique. With them, duplicates are allowed and resolved by keeping the
        row with the highest values of those columns (compared in order);
        ``deletion_column`` names a boolean column marking deleted rows.

        Returns:
            The updated ``View`` model
        """
        from foundry_sdk.v2.datasets.models import (
            PrimaryKeyLatestWinsResolutionStrategy,
            PrimaryKeyResolutionDuplicate,
            PrimaryKeyResolutionUnique,
            ViewPrimaryKey,
        )

        resolution: Any
        if latest_wins_columns:
            resolution = PrimaryKeyResolutionDuplicate(
                deletion_column=deletion_column,
                resolution_strategy=PrimaryKeyLatestWinsResolutionStrategy(
                    columns=list(latest_wins_columns)
                ),
            )
        else:
            if deletion_column is not None:
                raise ValueError("deletion_column needs latest_wins_columns")
            resolution = PrimaryKeyResolutionUnique()
        return self.service.View.add_primary_key(
            view_rid,
            primary_key=ViewPrimaryKey(columns=list(columns), resolution=resolution),
            branch=branch,
        )

    # ---------------------------------------------------- schedules, jobs

    def list_schedules(
        self,
        dataset_rid: str,
        *,
        branch: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of the schedules targeting a dataset.

        ``Dataset.get_schedules`` is GA and returns schedule RIDs only.

        Returns:
            The SDK ``ResourceIterator[str]`` (one page fetched)
        """
        return self.service.Dataset.get_schedules(
            dataset_rid,
            branch_name=branch,
            page_size=page_size,
            page_token=page_token,
        )

    def list_jobs(
        self,
        dataset_rid: str,
        *,
        branch: Optional[str] = None,
        order_by: str = "BY_STARTED_TIME",
        descending: bool = True,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a dataset's jobs (``Dataset.jobs``, beta).

        Args:
            order_by: ``BY_STARTED_TIME`` or ``BY_FINISHED_TIME``

        Returns:
            The SDK ``ResourceIterator[JobDetails]`` (one page fetched);
            ``JobDetails`` carries only the job RID.
        """
        from foundry_sdk.v2.datasets.models import GetDatasetJobsSort

        sort = GetDatasetJobsSort(
            sort_type=order_by,  # type: ignore[arg-type]
            sort_direction="DESCENDING" if descending else "ASCENDING",
        )
        return self.service.Dataset.jobs(
            dataset_rid,
            order_by=[sort],
            branch_name=branch,
            page_size=page_size,
            page_token=page_token,
            preview=True,
        )

    # ------------------------------------------------- local schema helper

    def infer_schema_from_csv(
        self, csv_path: Union[str, Path], sample_rows: int = 100
    ) -> Any:
        """Infer a ``DatasetSchema`` from a local CSV file.

        Reads the header and the first ``sample_rows`` rows and picks the
        narrowest type that fits every non-empty value (BOOLEAN, INTEGER,
        DOUBLE, DATE, TIMESTAMP, else STRING). Column names have spaces and
        hyphens replaced by underscores. No API call is made.
        """
        from foundry_sdk.v2.core.models import DatasetFieldSchema, DatasetSchema

        csv_path = Path(csv_path)
        with open(csv_path, "r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames
            if not headers:
                raise ValueError(f"CSV file {csv_path} has no header row")
            values: Dict[str, List[str]] = {column: [] for column in headers}
            for index, row in enumerate(reader):
                if index >= sample_rows:
                    break
                for column in headers:
                    values[column].append(row.get(column) or "")

        fields = []
        for column in headers:
            field_type, nullable = _infer_csv_type(values[column])
            name = column.strip().replace(" ", "_").replace("-", "_")
            fields.append(
                DatasetFieldSchema(name=name, type=field_type, nullable=nullable)  # type: ignore[arg-type]
            )
        return DatasetSchema(field_schema_list=fields)


# ------------------------------------------------------------------ helpers


def _view_backing_datasets(backing_datasets: Sequence[BackingDataset]) -> List[Any]:
    """``ViewBackingDataset`` models for ``(dataset RID, branch)`` pairs.

    No markings are excluded from propagation (``stopPropagatingMarkingIds``
    is empty): the view inherits every marking of its backing datasets.
    """
    from foundry_sdk.v2.datasets.models import ViewBackingDataset

    return [
        ViewBackingDataset(
            dataset_rid=dataset_rid, branch=branch, stop_propagating_marking_ids=[]
        )
        for dataset_rid, branch in backing_datasets
    ]


def arrow_table(response: Any) -> Any:
    """The ``pyarrow.Table`` of a ``read_table`` Arrow response.

    ``response`` is the SDK's ``TableResponse`` (or raw Arrow IPC stream
    bytes); ``None`` or an empty body gives a table without columns.
    """
    import pyarrow as pa

    if not response:
        return pa.table({})
    if hasattr(response, "to_pyarrow"):
        return response.to_pyarrow()
    return pa.ipc.open_stream(bytes(response)).read_all()


_DATE_PATTERNS = (
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),  # YYYY-MM-DD
    re.compile(r"^\d{2}/\d{2}/\d{4}$"),  # MM/DD/YYYY
    re.compile(r"^\d{2}-\d{2}-\d{4}$"),  # DD-MM-YYYY
)
_BOOLEAN_VALUES = {"true", "false", "yes", "no", "1", "0"}


def _infer_csv_type(values: List[str]) -> Tuple[str, bool]:
    """Return (field type, nullable) for a CSV column's sample values."""
    non_empty = [value for value in values if value.strip()]
    nullable = len(non_empty) < len(values) or not non_empty
    if not non_empty:
        return "STRING", True
    if all(value.lower() in _BOOLEAN_VALUES for value in non_empty):
        return "BOOLEAN", nullable
    if _all_parse(non_empty, int):
        return "INTEGER", nullable
    if _all_parse(non_empty, float):
        return "DOUBLE", nullable
    sample = non_empty[:10]
    for pattern in _DATE_PATTERNS:
        if all(pattern.match(value) for value in sample):
            return "DATE", nullable
    if all("-" in value and ":" in value and len(value) > 10 for value in sample):
        return "TIMESTAMP", nullable
    return "STRING", nullable


def _all_parse(values: List[str], kind: Any) -> bool:
    try:
        for value in values:
            kind(value)
    except ValueError:
        return False
    return True
