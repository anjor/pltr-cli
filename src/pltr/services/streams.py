"""
Streams service wrapper for Foundry SDK.
Provides access to streaming dataset and stream operations.
"""

from typing import Any, Dict, Optional
from .base import BaseService


class StreamsService(BaseService):
    """Service wrapper for Foundry Streams operations."""

    def _get_service(self) -> Any:
        """Get the Foundry Streams service."""
        return self.client.streams

    # ===== Dataset Operations =====

    def create_dataset(
        self,
        name: str,
        parent_folder_rid: str,
        schema: Dict[str, Any],
        branch_name: Optional[str] = None,
        compressed: Optional[bool] = None,
        partitions_count: Optional[int] = None,
        stream_type: Optional[str] = None,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a streaming dataset with a stream on the specified branch.

        Args:
            name: Dataset name
            parent_folder_rid: Parent folder RID (e.g., ri.compass.main.folder.xxx)
            schema: Foundry schema for the stream (dict with field definitions)
            branch_name: Branch to create stream on (default: 'master')
            compressed: Enable compression for the stream (default: False)
            partitions_count: Number of partitions (default: 1)
                Generally, each partition can handle ~5 MB/s
            stream_type: Stream type ('HIGH_THROUGHPUT' or 'LOW_LATENCY', default: 'LOW_LATENCY')
            preview: Enable preview mode (default: False)

        Returns:
            Dataset information dictionary containing:
            - rid: Dataset resource identifier
            - name: Dataset name
            - streamRid: Stream resource identifier

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = StreamsService()
            >>> schema = {"fieldSchemaList": [{"name": "value", "type": "STRING"}]}
            >>> dataset = service.create_dataset(
            ...     name="my-stream",
            ...     parent_folder_rid="ri.compass.main.folder.xxx",
            ...     schema=schema
            ... )
        """
        try:
            dataset = self.service.Dataset.create(
                name=name,
                parent_folder_rid=parent_folder_rid,
                schema=schema,
                branch_name=branch_name,
                compressed=compressed,
                partitions_count=partitions_count,
                stream_type=stream_type,
                preview=preview,
            )
            return self._serialize_response(dataset)
        except Exception as e:
            raise RuntimeError(f"Failed to create streaming dataset '{name}': {e}")

    # ===== Stream Operations =====

    def create_stream(
        self,
        dataset_rid: str,
        branch_name: str,
        schema: Dict[str, Any],
        compressed: Optional[bool] = None,
        partitions_count: Optional[int] = None,
        stream_type: Optional[str] = None,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new stream on a branch of an existing streaming dataset.

        Args:
            dataset_rid: Dataset RID (e.g., ri.foundry.main.dataset.xxx)
            branch_name: Branch name to create stream on
            schema: Foundry schema for this stream
            compressed: Enable compression (default: False)
            partitions_count: Number of partitions (default: 1)
            stream_type: Stream type ('HIGH_THROUGHPUT' or 'LOW_LATENCY')
            preview: Enable preview mode (default: False)

        Returns:
            Stream information dictionary containing:
            - streamRid: Stream resource identifier
            - branchName: Branch name
            - schema: Stream schema

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = StreamsService()
            >>> stream = service.create_stream(
            ...     dataset_rid="ri.foundry.main.dataset.xxx",
            ...     branch_name="feature-branch",
            ...     schema={"fieldSchemaList": [{"name": "id", "type": "INTEGER"}]}
            ... )
        """
        try:
            stream = self.service.Dataset.Stream.create(
                dataset_rid=dataset_rid,
                branch_name=branch_name,
                schema=schema,
                compressed=compressed,
                partitions_count=partitions_count,
                stream_type=stream_type,
                preview=preview,
            )
            return self._serialize_response(stream)
        except Exception as e:
            raise RuntimeError(
                f"Failed to create stream on branch '{branch_name}': {e}"
            )

    def get_stream(
        self, dataset_rid: str, stream_branch_name: str, preview: bool = False
    ) -> Dict[str, Any]:
        """
        Get information about a stream.

        Args:
            dataset_rid: Dataset RID
            stream_branch_name: Branch name of the stream
            preview: Enable preview mode (default: False)

        Returns:
            Stream information dictionary

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = StreamsService()
            >>> stream = service.get_stream(
            ...     dataset_rid="ri.foundry.main.dataset.xxx",
            ...     stream_branch_name="master"
            ... )
        """
        try:
            stream = self.service.Dataset.Stream.get(
                dataset_rid=dataset_rid,
                stream_branch_name=stream_branch_name,
                preview=preview,
            )
            return self._serialize_response(stream)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get stream on branch '{stream_branch_name}': {e}"
            )

    def publish_record(
        self,
        dataset_rid: str,
        stream_branch_name: str,
        record: Dict[str, Any],
        view_rid: Optional[str] = None,
        preview: bool = False,
    ) -> None:
        """
        Publish a single record to a stream.

        Args:
            dataset_rid: Dataset RID
            stream_branch_name: Branch name of the stream
            record: Record data as dictionary matching stream schema
            view_rid: Optional view RID for partitioning
            preview: Enable preview mode (default: False)

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = StreamsService()
            >>> service.publish_record(
            ...     dataset_rid="ri.foundry.main.dataset.xxx",
            ...     stream_branch_name="master",
            ...     record={"id": 123, "name": "test", "timestamp": 1234567890}
            ... )
        """
        try:
            self.service.Dataset.Stream.publish_record(
                dataset_rid=dataset_rid,
                stream_branch_name=stream_branch_name,
                record=record,
                view_rid=view_rid,
                preview=preview,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to publish record to stream: {e}")

    def publish_records(
        self,
        dataset_rid: str,
        stream_branch_name: str,
        records: list,
        view_rid: Optional[str] = None,
        preview: bool = False,
    ) -> None:
        """
        Publish multiple records to a stream in a batch.

        Args:
            dataset_rid: Dataset RID
            stream_branch_name: Branch name of the stream
            records: List of record dictionaries matching stream schema
            view_rid: Optional view RID for partitioning
            preview: Enable preview mode (default: False)

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = StreamsService()
            >>> records = [
            ...     {"id": 1, "name": "alice"},
            ...     {"id": 2, "name": "bob"}
            ... ]
            >>> service.publish_records(
            ...     dataset_rid="ri.foundry.main.dataset.xxx",
            ...     stream_branch_name="master",
            ...     records=records
            ... )
        """
        try:
            self.service.Dataset.Stream.publish_records(
                dataset_rid=dataset_rid,
                stream_branch_name=stream_branch_name,
                records=records,
                view_rid=view_rid,
                preview=preview,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to publish {len(records)} records to stream: {e}"
            )

    def reset_stream(
        self, dataset_rid: str, stream_branch_name: str, preview: bool = False
    ) -> Dict[str, Any]:
        """
        Reset a stream, clearing all existing data.

        Args:
            dataset_rid: Dataset RID
            stream_branch_name: Branch name of the stream to reset
            preview: Enable preview mode (default: False)

        Returns:
            Updated stream information

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = StreamsService()
            >>> stream = service.reset_stream(
            ...     dataset_rid="ri.foundry.main.dataset.xxx",
            ...     stream_branch_name="master"
            ... )
        """
        try:
            stream = self.service.Dataset.Stream.reset(
                dataset_rid=dataset_rid,
                stream_branch_name=stream_branch_name,
                preview=preview,
            )
            return self._serialize_response(stream)
        except Exception as e:
            raise RuntimeError(
                f"Failed to reset stream on branch '{stream_branch_name}': {e}"
            )
