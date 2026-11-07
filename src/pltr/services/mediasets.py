"""
MediaSets service wrapper for the Foundry SDK (``client.media_sets``).

Beta endpoints, always called with ``preview=True``: ``MediaSet.get_rid_by_path``,
``create``, ``commit``, ``abort``, ``upload``, ``reference``, ``calculate``,
``retrieve`` and ``clear``. GA endpoints, called without ``preview``:
``MediaSet.info``, ``read``, ``read_original`` and ``upload_media``.

Methods return SDK models unchanged and let SDK exceptions propagate so the
error layer can classify them. Media content is streamed: the download
methods return the SDK's streaming context manager, whose response yields
the content with ``iter_bytes()`` instead of holding it in memory.
"""

from typing import Any, Optional

from .base import BaseService


class MediaSetsService(BaseService):
    """Service wrapper for Foundry media sets (``client.media_sets``)."""

    def _get_service(self) -> Any:
        """Get the Foundry media sets namespace."""
        return self.client.media_sets

    def get_media_item_info(self, media_set_rid: str, media_item_rid: str) -> Any:
        """Get a media item's metadata (``MediaSet.info``, GA).

        Returns a ``GetMediaItemInfoResponse``; it doesn't repeat the item RID.
        """
        return self.service.MediaSet.info(media_set_rid, media_item_rid)

    def get_media_item_rid_by_path(
        self,
        media_set_rid: str,
        media_item_path: str,
        *,
        branch_name: Optional[str] = None,
    ) -> Any:
        """Look up the RID of the item at a path (``MediaSet.get_rid_by_path``, beta).

        Returns a ``GetMediaItemRidByPathResponse`` (``media_item_rid``).
        """
        return self.service.MediaSet.get_rid_by_path(
            media_set_rid,
            media_item_path=media_item_path,
            branch_name=branch_name,
            preview=True,
        )

    def create_transaction(
        self, media_set_rid: str, *, branch_name: Optional[str] = None
    ) -> str:
        """Open a transaction (``MediaSet.create``, beta); returns its ID."""
        return self.service.MediaSet.create(
            media_set_rid, branch_name=branch_name, preview=True
        )

    def commit_transaction(self, media_set_rid: str, transaction_id: str) -> None:
        """Commit a transaction (``MediaSet.commit``, beta)."""
        self.service.MediaSet.commit(media_set_rid, transaction_id, preview=True)

    def abort_transaction(self, media_set_rid: str, transaction_id: str) -> None:
        """Abort a transaction, deleting its uploads (``MediaSet.abort``, beta)."""
        self.service.MediaSet.abort(media_set_rid, transaction_id, preview=True)

    def upload_media(
        self,
        media_set_rid: str,
        body: bytes,
        *,
        media_item_path: Optional[str] = None,
        transaction_id: Optional[str] = None,
        branch_name: Optional[str] = None,
    ) -> Any:
        """Upload a media item (``MediaSet.upload``, beta).

        Transactional media sets need ``transaction_id``. Returns a
        ``PutMediaItemResponse`` (``media_item_rid``, ``media_set_view_rid``).
        """
        return self.service.MediaSet.upload(
            media_set_rid,
            body,
            branch_name=branch_name,
            media_item_path=media_item_path,
            transaction_id=transaction_id,
            preview=True,
        )

    def download_media(
        self, media_set_rid: str, media_item_rid: str, *, original: bool = False
    ) -> Any:
        """Request a media item's content as a stream.

        ``MediaSet.read`` (GA), or ``MediaSet.read_original`` (GA) for the file
        as originally uploaded. API errors are raised here, before any content
        is read. Returns the SDK's streaming context manager::

            with service.download_media(set_rid, item_rid) as response:
                for chunk in response.iter_bytes(): ...
        """
        streaming = self.service.MediaSet.with_streaming_response
        if original:
            return streaming.read_original(media_set_rid, media_item_rid)
        return streaming.read(media_set_rid, media_item_rid)

    def get_media_reference(self, media_set_rid: str, media_item_rid: str) -> Any:
        """Get a media item's ``MediaReference`` (``MediaSet.reference``, beta)."""
        return self.service.MediaSet.reference(
            media_set_rid, media_item_rid, preview=True
        )

    def calculate_thumbnail(self, media_set_rid: str, media_item_rid: str) -> Any:
        """Start calculating an image's thumbnail (``MediaSet.calculate``, beta).

        Returns a ``TrackedTransformation{Pending,Failed,Successful}Response``
        (only ``type``).
        """
        return self.service.MediaSet.calculate(
            media_set_rid, media_item_rid, preview=True
        )

    def retrieve_thumbnail(self, media_set_rid: str, media_item_rid: str) -> Any:
        """Request a calculated thumbnail (200px wide webp) as a stream.

        ``MediaSet.retrieve`` (beta). Returns the SDK's streaming context
        manager, like :meth:`download_media`.
        """
        streaming = self.service.MediaSet.with_streaming_response
        return streaming.retrieve(media_set_rid, media_item_rid, preview=True)

    def upload_temp_media(
        self, body: bytes, *, filename: str, attribution: Optional[str] = None
    ) -> Any:
        """Upload temporary media (``MediaSet.upload_media``, GA).

        The item is deleted after an hour unless it is persisted. Returns a
        ``MediaReference``.
        """
        return self.service.MediaSet.upload_media(
            body, filename=filename, attribution=attribution
        )

    def clear_media_item(
        self,
        media_set_rid: str,
        media_item_path: str,
        *,
        branch_name: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> None:
        """Clear (soft-delete) the item at a path (``MediaSet.clear``, beta).

        The item and all older items at that path become unretrievable.
        Transactional media sets need ``transaction_id``.
        """
        self.service.MediaSet.clear(
            media_set_rid,
            media_item_path=media_item_path,
            branch_name=branch_name,
            transaction_id=transaction_id,
            preview=True,
        )
