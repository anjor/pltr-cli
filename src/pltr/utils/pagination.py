"""
Pagination utilities for handling large result sets.

This module provides a unified interface for pagination across different
SDK patterns used by the Foundry platform.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class PaginationConfig:
    """
    Configuration for pagination behavior.

    Attributes:
        page_size: Number of items per page (None = use service default)
        max_pages: Maximum number of pages to fetch (None = fetch all)
        page_token: Token to resume from a specific page
        fetch_all: If True, overrides max_pages to fetch all available pages
    """

    page_size: Optional[int] = None
    max_pages: Optional[int] = 1  # Default: fetch single page
    page_token: Optional[str] = None
    fetch_all: bool = False

    def should_show_progress(self) -> bool:
        """
        Determine if progress tracking should be shown.

        Returns:
            True if fetching multiple pages with known max_pages
        """
        return self.max_pages is not None and self.max_pages > 1 and not self.fetch_all

    def effective_max_pages(self) -> Optional[int]:
        """
        Get the effective maximum pages to fetch.

        Returns:
            None if fetch_all is True, otherwise max_pages value
        """
        return None if self.fetch_all else self.max_pages


@dataclass
class PaginationMetadata:
    """
    Metadata about pagination state.

    Attributes:
        current_page: Current page number (1-indexed)
        items_fetched: Total number of items fetched
        next_page_token: Token for fetching the next page (if available)
        has_more: Whether more pages are available
        total_pages_fetched: Total number of pages fetched so far
    """

    current_page: int = 1
    items_fetched: int = 0
    next_page_token: Optional[str] = None
    has_more: bool = False
    total_pages_fetched: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert metadata to dictionary for JSON serialization.

        Returns:
            Dictionary representation of metadata
        """
        result: Dict[str, Any] = {
            "page": self.current_page,
            "items_count": self.items_fetched,
            "has_more": self.has_more,
            "total_pages_fetched": self.total_pages_fetched,
        }
        if self.next_page_token:
            result["next_page_token"] = self.next_page_token
        return result


@dataclass
class PaginationResult:
    """
    Wrapper for paginated results with metadata.

    Attributes:
        data: List of items fetched
        metadata: Pagination metadata
    """

    data: List[Any] = field(default_factory=list)
    metadata: PaginationMetadata = field(default_factory=PaginationMetadata)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert result to dictionary for JSON serialization.

        Returns:
            Dictionary with data and pagination metadata
        """
        return {
            "data": self.data,
            "pagination": self.metadata.to_dict(),
        }


class ResponsePaginationHandler:
    """
    Handler for SDK Pattern B: Response-based pagination.

    This handler works with SDK methods that return response objects
    with explicit `.data` and `.next_page_token` attributes.

    Example SDK methods:
        - admin.User.list()
        - orchestration.Build.search()
    """

    def collect_pages(
        self,
        fetch_fn: Callable[[Optional[str]], Dict[str, Any]],
        config: PaginationConfig,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> PaginationResult:
        """
        Collect pages using a fetch function.

        Args:
            fetch_fn: Function that accepts a page_token and returns a dict
                     with 'data' and 'next_page_token' keys
            config: Pagination configuration
            progress_callback: Optional callback(page_num, items_count)

        Returns:
            PaginationResult with collected items and metadata

        Example:
            >>> def fetch(token):
            ...     response = service.list(page_token=token)
            ...     return {"data": response.data, "next_page_token": response.next_page_token}
            >>> handler = ResponsePaginationHandler()
            >>> result = handler.collect_pages(fetch, config)
        """
        all_items: List[Any] = []
        page_num = 0
        current_token = config.page_token
        max_pages = config.effective_max_pages()

        while True:
            try:
                # Fetch the current page
                response = fetch_fn(current_token)
                page_data = response.get("data", [])
                next_token = response.get("next_page_token")

                # Add items from this page
                all_items.extend(page_data)
                page_num += 1

                # Update progress
                if progress_callback:
                    progress_callback(page_num, len(all_items))

                # Check if we should continue
                has_more = next_token is not None
                should_stop = (
                    not has_more  # No more pages
                    or (
                        max_pages is not None and page_num >= max_pages
                    )  # Reached max pages
                )

                if should_stop:
                    metadata = PaginationMetadata(
                        current_page=page_num,
                        items_fetched=len(all_items),
                        next_page_token=next_token,
                        has_more=has_more,
                        total_pages_fetched=page_num,
                    )
                    return PaginationResult(data=all_items, metadata=metadata)

                # Continue to next page
                current_token = next_token

            except Exception as e:
                # Error occurred while fetching - return partial results
                # Include the error information in metadata for user awareness
                if all_items:
                    # We have partial results - return what we got so far
                    import sys

                    print(
                        f"\nWarning: Error fetching page {page_num + 1}: {e}",
                        file=sys.stderr,
                    )
                    print(
                        f"Returning partial results ({len(all_items)} items from {page_num} pages)",
                        file=sys.stderr,
                    )

                    metadata = PaginationMetadata(
                        current_page=page_num,
                        items_fetched=len(all_items),
                        next_page_token=current_token,  # Token for retry
                        has_more=True,  # Assume more pages exist
                        total_pages_fetched=page_num,
                    )
                    return PaginationResult(data=all_items, metadata=metadata)
                else:
                    # No data fetched yet - re-raise the error
                    raise


class IteratorPaginationHandler:
    """
    Handler for SDK Pattern A: Iterator-based pagination.

    This handler works with SDK methods that return ResourceIterator instances
    that automatically paginate internally and expose next_page_token.

    Example SDK methods:
        - ontology.OntologyObject.list()
        - Dataset.File.list()

    Note: The SDK's ResourceIterator exposes .next_page_token and .data properties
    which we leverage for proper pagination support.
    """

    def collect_pages(
        self,
        iterator: Any,  # ResourceIterator from SDK
        config: PaginationConfig,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> PaginationResult:
        """
        Collect pages from a ResourceIterator using SDK's pagination.

        Args:
            iterator: ResourceIterator instance from SDK (has .next_page_token property)
            config: Pagination configuration
            progress_callback: Optional callback(page_num, items_count)

        Returns:
            PaginationResult with collected items and metadata

        Note:
            This leverages the SDK's ResourceIterator.next_page_token property
            for proper token-based pagination and resume capability.
        """
        all_items: List[Any] = []
        page_num = 0
        max_pages = config.effective_max_pages()
        next_token = None
        has_more = False

        try:
            # Collect items from the iterator
            for item in iterator:
                all_items.append(item)

                # Check if we've completed a "page" worth of items
                page_size = config.page_size or 20  # Default page size
                if len(all_items) % page_size == 0:
                    page_num += 1

                    # Update progress
                    if progress_callback:
                        progress_callback(page_num, len(all_items))

                    # Check if we should stop
                    if max_pages is not None and page_num >= max_pages:
                        # Capture next_page_token BEFORE breaking while iterator state is known
                        if hasattr(iterator, "next_page_token"):
                            next_token = iterator.next_page_token
                            has_more = next_token is not None
                        break

            # Calculate final page number if items don't align with page_size
            if len(all_items) % page_size != 0:
                page_num += 1
                if progress_callback:
                    progress_callback(page_num, len(all_items))

            # If we didn't break early (exhausted iterator), check for next_page_token
            if next_token is None and hasattr(iterator, "next_page_token"):
                next_token = iterator.next_page_token
                has_more = next_token is not None

        except Exception as e:
            # Error occurred during iteration - return partial results
            if all_items:
                # We have partial results
                import sys

                print(
                    f"\nWarning: Error during iteration: {e}",
                    file=sys.stderr,
                )
                print(
                    f"Returning partial results ({len(all_items)} items)",
                    file=sys.stderr,
                )

                # Try to get next_page_token if available
                if hasattr(iterator, "next_page_token"):
                    next_token = iterator.next_page_token
                    has_more = next_token is not None
            else:
                # No data fetched yet - re-raise the error
                raise

        metadata = PaginationMetadata(
            current_page=page_num,
            items_fetched=len(all_items),
            next_page_token=next_token,
            has_more=has_more,
            total_pages_fetched=page_num,
        )

        return PaginationResult(data=all_items, metadata=metadata)
