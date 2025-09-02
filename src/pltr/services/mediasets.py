"""
MediaSets service wrapper for Foundry SDK v2 API.
Provides operations for managing media sets and media content.
"""

from typing import Any, Optional, Dict
from pathlib import Path

from .base import BaseService


class MediaSetsService(BaseService):
    """Service wrapper for Foundry MediaSets operations using v2 API."""

    def _get_service(self) -> Any:
        """Get the Foundry MediaSets service."""
        return self.client.media_sets

    def get_media_set_info(
        self, media_set_rid: str, media_item_rid: str, preview: bool = False
    ) -> Dict[str, Any]:
        """
        Get information about a specific media item in a media set.

        Args:
            media_set_rid: Media Set Resource Identifier
            media_item_rid: Media Item Resource Identifier
            preview: Enable preview mode

        Returns:
            Media item information dictionary
        """
        try:
            response = self.service.MediaSet.info(
                media_set_rid=media_set_rid,
                media_item_rid=media_item_rid,
                preview=preview,
            )
            return self._format_media_item_info(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get media item info: {e}")

    def get_media_item_by_path(
        self,
        media_set_rid: str,
        media_item_path: str,
        branch_name: Optional[str] = None,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Get media item RID by its path within the media set.

        Args:
            media_set_rid: Media Set Resource Identifier
            media_item_path: Path to the media item within the media set
            branch_name: Branch name (optional)
            preview: Enable preview mode

        Returns:
            Response containing media item RID
        """
        try:
            response = self.service.MediaSet.get_rid_by_path(
                media_set_rid=media_set_rid,
                media_item_path=media_item_path,
                branch_name=branch_name,
                preview=preview,
            )
            return {"rid": response.rid, "path": media_item_path}
        except Exception as e:
            raise RuntimeError(f"Failed to get media item by path: {e}")

    def create_transaction(
        self,
        media_set_rid: str,
        branch_name: Optional[str] = None,
        preview: bool = False,
    ) -> str:
        """
        Create a new transaction for uploading to a media set.

        Args:
            media_set_rid: Media Set Resource Identifier
            branch_name: Branch name (optional)
            preview: Enable preview mode

        Returns:
            Transaction ID
        """
        try:
            response = self.service.MediaSet.create(
                media_set_rid=media_set_rid,
                branch_name=branch_name,
                preview=preview,
            )
            return response.transaction_id
        except Exception as e:
            raise RuntimeError(f"Failed to create transaction: {e}")

    def commit_transaction(
        self,
        media_set_rid: str,
        transaction_id: str,
        preview: bool = False,
    ) -> None:
        """
        Commit an open transaction, making uploaded items available.

        Args:
            media_set_rid: Media Set Resource Identifier
            transaction_id: Transaction ID to commit
            preview: Enable preview mode
        """
        try:
            self.service.MediaSet.commit(
                media_set_rid=media_set_rid,
                transaction_id=transaction_id,
                preview=preview,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to commit transaction: {e}")

    def abort_transaction(
        self,
        media_set_rid: str,
        transaction_id: str,
        preview: bool = False,
    ) -> None:
        """
        Abort an open transaction, deleting any uploaded items.

        Args:
            media_set_rid: Media Set Resource Identifier
            transaction_id: Transaction ID to abort
            preview: Enable preview mode
        """
        try:
            self.service.MediaSet.abort(
                media_set_rid=media_set_rid,
                transaction_id=transaction_id,
                preview=preview,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to abort transaction: {e}")

    def upload_media(
        self,
        media_set_rid: str,
        file_path: str,
        media_item_path: str,
        transaction_id: str,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload a media file to a media set within a transaction.

        Args:
            media_set_rid: Media Set Resource Identifier
            file_path: Local path to the file to upload
            media_item_path: Path within the media set where file should be stored
            transaction_id: Transaction ID for the upload
            preview: Enable preview mode

        Returns:
            Upload response information
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            with open(file_path_obj, "rb") as file:
                self.service.MediaSet.upload(
                    media_set_rid=media_set_rid,
                    media_item_path=media_item_path,
                    body=file,
                    transaction_id=transaction_id,
                    preview=preview,
                )

            return {
                "media_set_rid": media_set_rid,
                "media_item_path": media_item_path,
                "transaction_id": transaction_id,
                "file_size": file_path_obj.stat().st_size,
                "uploaded": True,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to upload media: {e}")

    def download_media(
        self,
        media_set_rid: str,
        media_item_rid: str,
        output_path: str,
        original: bool = False,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Download a media item from a media set.

        Args:
            media_set_rid: Media Set Resource Identifier
            media_item_rid: Media Item Resource Identifier
            output_path: Local path where file should be saved
            original: Whether to download original version (vs processed)
            preview: Enable preview mode

        Returns:
            Download response information
        """
        try:
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            if original:
                response = self.service.MediaSet.read_original(
                    media_set_rid=media_set_rid,
                    media_item_rid=media_item_rid,
                    preview=preview,
                )
            else:
                response = self.service.MediaSet.read(
                    media_set_rid=media_set_rid,
                    media_item_rid=media_item_rid,
                    preview=preview,
                )

            with open(output_path_obj, "wb") as file:
                if hasattr(response, "content"):
                    file.write(response.content)
                else:
                    # Handle streaming response
                    for chunk in response:
                        file.write(chunk)

            file_size = output_path_obj.stat().st_size
            return {
                "media_set_rid": media_set_rid,
                "media_item_rid": media_item_rid,
                "output_path": str(output_path_obj),
                "file_size": file_size,
                "downloaded": True,
                "original": original,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to download media: {e}")

    def get_media_reference(
        self,
        media_set_rid: str,
        media_item_rid: str,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Get a reference to a media item (e.g., for embedding).

        Args:
            media_set_rid: Media Set Resource Identifier
            media_item_rid: Media Item Resource Identifier
            preview: Enable preview mode

        Returns:
            Media reference information
        """
        try:
            response = self.service.MediaSet.reference(
                media_set_rid=media_set_rid,
                media_item_rid=media_item_rid,
                preview=preview,
            )
            return self._format_media_reference(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get media reference: {e}")

    def _format_media_item_info(self, info_response: Any) -> Dict[str, Any]:
        """Format media item info response for display."""
        return {
            "media_item_rid": getattr(info_response, "rid", "unknown"),
            "filename": getattr(info_response, "filename", "unknown"),
            "size": getattr(info_response, "size", 0),
            "content_type": getattr(info_response, "content_type", "unknown"),
            "created_time": getattr(info_response, "created_time", None),
            "updated_time": getattr(info_response, "updated_time", None),
        }

    def _format_media_reference(self, reference_response: Any) -> Dict[str, Any]:
        """Format media reference response for display."""
        return {
            "reference_id": getattr(reference_response, "reference_id", "unknown"),
            "url": getattr(reference_response, "url", "unknown"),
            "expires_at": getattr(reference_response, "expires_at", None),
        }
