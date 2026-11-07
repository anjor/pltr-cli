"""
Streams service wrapper for the Foundry SDK (``client.streams``).

``Dataset.create``, ``Dataset.Stream.create`` and ``Dataset.Stream.reset``
are beta endpoints and are always called with ``preview=True``;
``Dataset.Stream.get``, ``publish_record`` and ``publish_records`` are GA.
Methods return SDK models unchanged and let SDK exceptions propagate so the
error layer can classify them.

Schemas are Foundry stream schemas (``StreamSchema``), for example::

    {"fields": [{"name": "id", "schema": {"nullable": false,
                                          "dataType": {"type": "long"}}}],
     "keyFieldNames": ["id"]}
"""

from typing import Any, Dict, List, Optional

from .base import BaseService


class StreamsService(BaseService):
    """Service wrapper for Foundry streaming datasets and streams."""

    def _get_service(self) -> Any:
        """Get the Foundry streams namespace."""
        return self.client.streams

    def create_dataset(
        self,
        *,
        name: str,
        parent_folder_rid: str,
        schema: Dict[str, Any],
        branch_name: Optional[str] = None,
        compressed: Optional[bool] = None,
        partitions_count: Optional[int] = None,
        stream_type: Optional[str] = None,
    ) -> Any:
        """Create a streaming dataset with a stream on ``branch_name``.

        ``Dataset.create`` (beta); returns a ``streams.models.Dataset``
        (``rid``, ``name``, ``parent_folder_rid``).
        """
        return self.service.Dataset.create(
            name=name,
            parent_folder_rid=parent_folder_rid,
            schema=schema,
            branch_name=branch_name,
            compressed=compressed,
            partitions_count=partitions_count,
            stream_type=stream_type,
            preview=True,
        )

    def create_stream(
        self,
        dataset_rid: str,
        *,
        branch_name: str,
        schema: Dict[str, Any],
        compressed: Optional[bool] = None,
        partitions_count: Optional[int] = None,
        stream_type: Optional[str] = None,
    ) -> Any:
        """Create a branch of a streaming dataset with a new stream on it.

        ``Dataset.Stream.create`` (beta); returns a ``Stream`` model.
        """
        return self.service.Dataset.Stream.create(
            dataset_rid,
            branch_name=branch_name,
            schema=schema,
            compressed=compressed,
            partitions_count=partitions_count,
            stream_type=stream_type,
            preview=True,
        )

    def get_stream(self, dataset_rid: str, branch_name: str) -> Any:
        """Get the stream on a branch (``Dataset.Stream.get``, GA); a ``Stream``."""
        return self.service.Dataset.Stream.get(dataset_rid, branch_name)

    def publish_record(
        self,
        dataset_rid: str,
        branch_name: str,
        record: Dict[str, Any],
        *,
        view_rid: Optional[str] = None,
    ) -> None:
        """Publish one record (``Dataset.Stream.publish_record``, GA)."""
        self.service.Dataset.Stream.publish_record(
            dataset_rid, branch_name, record=record, view_rid=view_rid
        )

    def publish_records(
        self,
        dataset_rid: str,
        branch_name: str,
        records: List[Dict[str, Any]],
        *,
        view_rid: Optional[str] = None,
    ) -> None:
        """Publish a batch of records (``Dataset.Stream.publish_records``, GA).

        The API rejects the whole batch if any record doesn't match the schema.
        """
        self.service.Dataset.Stream.publish_records(
            dataset_rid, branch_name, records=records, view_rid=view_rid
        )

    def reset_stream(
        self,
        dataset_rid: str,
        branch_name: str,
        *,
        schema: Optional[Dict[str, Any]] = None,
        compressed: Optional[bool] = None,
        partitions_count: Optional[int] = None,
        stream_type: Optional[str] = None,
    ) -> Any:
        """Reset the stream on a branch, deleting its records.

        ``Dataset.Stream.reset`` (beta). Settings left as ``None`` keep the
        current stream's value. Returns the new ``Stream`` (it has a new view
        RID).
        """
        return self.service.Dataset.Stream.reset(
            dataset_rid,
            branch_name,
            schema=schema,
            compressed=compressed,
            partitions_count=partitions_count,
            stream_type=stream_type,
            preview=True,
        )
