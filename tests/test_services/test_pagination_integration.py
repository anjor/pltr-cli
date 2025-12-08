"""
Integration tests for pagination in BaseService.
"""

from unittest.mock import Mock
from src.pltr.services.base import BaseService
from src.pltr.utils.pagination import PaginationConfig, PaginationResult


class MockIterator:
    """Mock iterator that mimics SDK's ResourceIterator with next_page_token property."""

    def __init__(self, items, next_page_token=None):
        self._items = iter(items)
        self.next_page_token = next_page_token

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._items)


class MockService(BaseService):
    """Mock service for testing BaseService pagination methods."""

    def _get_service(self):
        return Mock()


class TestBaseServicePagination:
    """Tests for BaseService pagination helper methods."""

    def test_paginate_iterator(self):
        """Test _paginate_iterator helper method."""
        service = MockService()

        # Create mock iterator
        mock_iterator = MockIterator(
            [{"id": 1}, {"id": 2}, {"id": 3}], next_page_token=None
        )

        config = PaginationConfig(page_size=10, max_pages=1)
        result = service._paginate_iterator(mock_iterator, config)

        assert isinstance(result, PaginationResult)
        assert len(result.data) == 3
        assert result.data[0]["id"] == 1

    def test_paginate_response(self):
        """Test _paginate_response helper method."""
        service = MockService()

        def fetch_fn(token):
            if token is None:
                return {
                    "data": [{"id": 1}, {"id": 2}],
                    "next_page_token": "token1",
                }
            return {"data": [{"id": 3}], "next_page_token": None}

        config = PaginationConfig(fetch_all=True)
        result = service._paginate_response(fetch_fn, config)

        assert isinstance(result, PaginationResult)
        assert len(result.data) == 3
        assert result.metadata.current_page == 2

    def test_serialize_response_with_pydantic_model(self):
        """Test _serialize_response with Pydantic model."""
        service = MockService()

        # Mock Pydantic model
        mock_model = Mock()
        mock_model.dict.return_value = {"field": "value"}

        result = service._serialize_response(mock_model)
        assert result == {"field": "value"}
        mock_model.dict.assert_called_once()

    def test_serialize_response_with_regular_object(self):
        """Test _serialize_response with regular object."""
        service = MockService()

        # Mock regular object with __dict__
        class MockObject:
            def __init__(self):
                self.field1 = "value1"
                self.field2 = 42
                self._private = "should be excluded"

        obj = MockObject()
        result = service._serialize_response(obj)

        assert "field1" in result
        assert "field2" in result
        assert "_private" not in result
        assert result["field1"] == "value1"
        assert result["field2"] == 42

    def test_serialize_response_with_primitive(self):
        """Test _serialize_response with primitive types."""
        service = MockService()

        # Test with serializable primitive
        result = service._serialize_response({"key": "value"})
        assert result == {"key": "value"}

        # Test with None
        result = service._serialize_response(None)
        assert result == {}

    def test_serialize_response_with_non_serializable(self):
        """Test _serialize_response with non-serializable object."""
        service = MockService()

        class NonSerializable:
            def __init__(self):
                self.func = lambda x: x  # Non-serializable

        obj = NonSerializable()
        result = service._serialize_response(obj)

        # Should convert to string
        assert "func" in result
        assert isinstance(result["func"], str)

    def test_paginate_iterator_with_progress_callback(self):
        """Test iterator pagination with progress tracking."""
        service = MockService()

        mock_iterator = MockIterator(range(1, 21), next_page_token=None)

        progress_calls = []

        def progress_callback(page, items):
            progress_calls.append((page, items))

        config = PaginationConfig(page_size=10, fetch_all=True)
        result = service._paginate_iterator(mock_iterator, config, progress_callback)

        assert len(result.data) == 20
        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 10)
        assert progress_calls[1] == (2, 20)

    def test_paginate_response_with_progress_callback(self):
        """Test response pagination with progress tracking."""
        service = MockService()

        def fetch_fn(token):
            if token is None:
                return {"data": [1, 2], "next_page_token": "t1"}
            elif token == "t1":
                return {"data": [3, 4], "next_page_token": "t2"}
            return {"data": [5], "next_page_token": None}

        progress_calls = []

        def progress_callback(page, items):
            progress_calls.append((page, items))

        config = PaginationConfig(fetch_all=True)
        result = service._paginate_response(fetch_fn, config, progress_callback)

        assert len(result.data) == 5
        assert len(progress_calls) == 3
