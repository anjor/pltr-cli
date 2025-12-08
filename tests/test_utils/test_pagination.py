"""
Tests for pagination utilities.
"""

from src.pltr.utils.pagination import (
    PaginationConfig,
    PaginationMetadata,
    PaginationResult,
    ResponsePaginationHandler,
    IteratorPaginationHandler,
)


class TestPaginationConfig:
    """Tests for PaginationConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = PaginationConfig()
        assert config.page_size is None
        assert config.max_pages == 1
        assert config.page_token is None
        assert config.fetch_all is False

    def test_should_show_progress_with_max_pages(self):
        """Test progress indication when max_pages > 1."""
        config = PaginationConfig(max_pages=3)
        assert config.should_show_progress() is True

    def test_should_show_progress_with_fetch_all(self):
        """Test no progress when fetch_all is True."""
        config = PaginationConfig(max_pages=3, fetch_all=True)
        assert config.should_show_progress() is False

    def test_should_show_progress_single_page(self):
        """Test no progress for single page."""
        config = PaginationConfig(max_pages=1)
        assert config.should_show_progress() is False

    def test_effective_max_pages_with_fetch_all(self):
        """Test effective_max_pages returns None when fetch_all."""
        config = PaginationConfig(max_pages=5, fetch_all=True)
        assert config.effective_max_pages() is None

    def test_effective_max_pages_without_fetch_all(self):
        """Test effective_max_pages returns max_pages normally."""
        config = PaginationConfig(max_pages=5, fetch_all=False)
        assert config.effective_max_pages() == 5


class TestPaginationMetadata:
    """Tests for PaginationMetadata dataclass."""

    def test_default_values(self):
        """Test default metadata values."""
        metadata = PaginationMetadata()
        assert metadata.current_page == 1
        assert metadata.items_fetched == 0
        assert metadata.next_page_token is None
        assert metadata.has_more is False
        assert metadata.total_pages_fetched == 0

    def test_to_dict_without_token(self):
        """Test dictionary conversion without next_page_token."""
        metadata = PaginationMetadata(
            current_page=2,
            items_fetched=40,
            has_more=False,
            total_pages_fetched=2,
        )
        result = metadata.to_dict()
        assert result == {
            "page": 2,
            "items_count": 40,
            "has_more": False,
            "total_pages_fetched": 2,
        }
        assert "next_page_token" not in result

    def test_to_dict_with_token(self):
        """Test dictionary conversion with next_page_token."""
        metadata = PaginationMetadata(
            current_page=1,
            items_fetched=20,
            next_page_token="abc123",
            has_more=True,
            total_pages_fetched=1,
        )
        result = metadata.to_dict()
        assert result["next_page_token"] == "abc123"
        assert result["has_more"] is True


class TestPaginationResult:
    """Tests for PaginationResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = PaginationResult()
        assert result.data == []
        assert isinstance(result.metadata, PaginationMetadata)

    def test_to_dict(self):
        """Test dictionary conversion."""
        metadata = PaginationMetadata(current_page=1, items_fetched=10)
        result = PaginationResult(data=[1, 2, 3], metadata=metadata)

        result_dict = result.to_dict()
        assert result_dict["data"] == [1, 2, 3]
        assert "pagination" in result_dict
        assert result_dict["pagination"]["items_count"] == 10


class TestResponsePaginationHandler:
    """Tests for ResponsePaginationHandler."""

    def test_single_page_no_next_token(self):
        """Test fetching single page with no next token."""

        def fetch_fn(token):
            return {
                "data": [1, 2, 3],
                "next_page_token": None,
            }

        handler = ResponsePaginationHandler()
        config = PaginationConfig(max_pages=1)
        result = handler.collect_pages(fetch_fn, config)

        assert len(result.data) == 3
        assert result.metadata.current_page == 1
        assert result.metadata.items_fetched == 3
        assert result.metadata.has_more is False
        assert result.metadata.next_page_token is None

    def test_multiple_pages_with_limit(self):
        """Test fetching multiple pages up to max_pages."""
        page_data = {
            None: {"data": [1, 2], "next_page_token": "token1"},
            "token1": {"data": [3, 4], "next_page_token": "token2"},
            "token2": {"data": [5, 6], "next_page_token": None},
        }

        def fetch_fn(token):
            return page_data[token]

        handler = ResponsePaginationHandler()
        config = PaginationConfig(max_pages=2)
        result = handler.collect_pages(fetch_fn, config)

        assert len(result.data) == 4  # Only 2 pages
        assert result.data == [1, 2, 3, 4]
        assert result.metadata.current_page == 2
        assert result.metadata.has_more is True
        assert result.metadata.next_page_token == "token2"

    def test_fetch_all_pages(self):
        """Test fetching all available pages."""
        page_data = {
            None: {"data": [1, 2], "next_page_token": "token1"},
            "token1": {"data": [3, 4], "next_page_token": "token2"},
            "token2": {"data": [5, 6], "next_page_token": None},
        }

        def fetch_fn(token):
            return page_data[token]

        handler = ResponsePaginationHandler()
        config = PaginationConfig(fetch_all=True)
        result = handler.collect_pages(fetch_fn, config)

        assert len(result.data) == 6
        assert result.data == [1, 2, 3, 4, 5, 6]
        assert result.metadata.current_page == 3
        assert result.metadata.has_more is False
        assert result.metadata.next_page_token is None

    def test_progress_callback(self):
        """Test progress callback is called correctly."""

        def fetch_fn(token):
            if token is None:
                return {"data": [1, 2], "next_page_token": "token1"}
            return {"data": [3, 4], "next_page_token": None}

        progress_calls = []

        def progress_callback(page_num, items_count):
            progress_calls.append((page_num, items_count))

        handler = ResponsePaginationHandler()
        config = PaginationConfig(fetch_all=True)
        handler.collect_pages(fetch_fn, config, progress_callback)

        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 2)
        assert progress_calls[1] == (2, 4)

    def test_resume_from_token(self):
        """Test resuming from a page token."""
        page_data = {
            "token1": {"data": [3, 4], "next_page_token": "token2"},
            "token2": {"data": [5, 6], "next_page_token": None},
        }

        def fetch_fn(token):
            return page_data[token]

        handler = ResponsePaginationHandler()
        config = PaginationConfig(page_token="token1", fetch_all=True)
        result = handler.collect_pages(fetch_fn, config)

        assert len(result.data) == 4
        assert result.data == [3, 4, 5, 6]


class TestIteratorPaginationHandler:
    """Tests for IteratorPaginationHandler."""

    def test_single_page_iterator(self):
        """Test iterating single page from iterator."""
        mock_iterator = iter([1, 2, 3, 4, 5])
        mock_iterator.next_page_token = None  # SDK ResourceIterator property

        handler = IteratorPaginationHandler()
        config = PaginationConfig(page_size=10, max_pages=1)
        result = handler.collect_pages(mock_iterator, config)

        assert len(result.data) == 5
        assert result.data == [1, 2, 3, 4, 5]
        assert result.metadata.current_page == 1
        assert result.metadata.items_fetched == 5

    def test_multiple_pages_from_iterator(self):
        """Test paginating iterator results."""
        mock_iterator = iter(range(1, 51))  # 50 items
        mock_iterator.next_page_token = "next_token"

        handler = IteratorPaginationHandler()
        config = PaginationConfig(page_size=20, max_pages=2)
        result = handler.collect_pages(mock_iterator, config)

        assert len(result.data) == 40  # 2 pages * 20 items
        assert result.metadata.current_page == 2
        assert result.metadata.items_fetched == 40

    def test_iterator_with_next_token_property(self):
        """Test extracting next_page_token from iterator."""
        mock_iterator = iter([1, 2, 3])
        mock_iterator.next_page_token = "abc123"

        handler = IteratorPaginationHandler()
        config = PaginationConfig(page_size=10, max_pages=1)
        result = handler.collect_pages(mock_iterator, config)

        assert result.metadata.next_page_token == "abc123"
        assert result.metadata.has_more is True

    def test_iterator_without_next_token_property(self):
        """Test fallback when iterator doesn't have next_page_token."""
        mock_iterator = iter([1, 2, 3])
        # No next_page_token property

        handler = IteratorPaginationHandler()
        config = PaginationConfig(page_size=10, max_pages=1)
        result = handler.collect_pages(mock_iterator, config)

        # Should fall back to trying to peek ahead
        assert result.metadata.items_fetched == 3

    def test_fetch_all_from_iterator(self):
        """Test fetching all items from iterator."""
        mock_iterator = iter(range(1, 101))  # 100 items
        mock_iterator.next_page_token = None

        handler = IteratorPaginationHandler()
        config = PaginationConfig(page_size=20, fetch_all=True)
        result = handler.collect_pages(mock_iterator, config)

        assert len(result.data) == 100
        assert result.metadata.items_fetched == 100
        assert result.metadata.has_more is False

    def test_progress_callback_iterator(self):
        """Test progress callback with iterator."""
        mock_iterator = iter(range(1, 41))  # 40 items
        mock_iterator.next_page_token = None

        progress_calls = []

        def progress_callback(page_num, items_count):
            progress_calls.append((page_num, items_count))

        handler = IteratorPaginationHandler()
        config = PaginationConfig(page_size=20, fetch_all=True)
        handler.collect_pages(mock_iterator, config, progress_callback)

        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 20)
        assert progress_calls[1] == (2, 40)

    def test_partial_last_page(self):
        """Test handling partial last page."""
        mock_iterator = iter(range(1, 26))  # 25 items
        mock_iterator.next_page_token = None

        handler = IteratorPaginationHandler()
        config = PaginationConfig(page_size=20, fetch_all=True)
        result = handler.collect_pages(mock_iterator, config)

        assert len(result.data) == 25
        assert result.metadata.current_page == 2  # page 1 (20 items) + page 2 (5 items)
        assert result.metadata.items_fetched == 25
