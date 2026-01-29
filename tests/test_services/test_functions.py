"""Tests for Functions service."""

import pytest
from unittest.mock import Mock, patch
from pltr.services.functions import FunctionsService


class TestFunctionsService:
    """Test Functions service functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.functions = Mock()
        client.functions.Query = Mock()
        client.functions.ValueType = Mock()
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create FunctionsService with mocked client."""
        with patch("pltr.services.base.AuthManager") as mock_auth:
            mock_auth.return_value.get_client.return_value = mock_client
            service = FunctionsService()
            return service

    # ===== Query Get Tests =====

    def test_get_query(self, service, mock_client):
        """Test getting a query by API name."""
        # Setup
        query_api_name = "myQuery"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": "ri.functions.main.query.abc123",
            "apiName": query_api_name,
            "version": "1.0.0",
            "parameters": {"limit": "integer"},
        }
        mock_client.functions.Query.get.return_value = mock_response

        # Execute
        result = service.get_query(query_api_name)

        # Assert
        mock_client.functions.Query.get.assert_called_once_with(
            query_api_name, preview=False, version=None
        )
        assert result["apiName"] == query_api_name
        assert result["version"] == "1.0.0"

    def test_get_query_with_version(self, service, mock_client):
        """Test getting a specific query version."""
        # Setup
        query_api_name = "myQuery"
        version = "2.0.0"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": "ri.functions.main.query.abc123",
            "apiName": query_api_name,
            "version": version,
        }
        mock_client.functions.Query.get.return_value = mock_response

        # Execute
        result = service.get_query(query_api_name, version=version)

        # Assert
        mock_client.functions.Query.get.assert_called_once_with(
            query_api_name, preview=False, version=version
        )
        assert result["version"] == version

    def test_get_query_with_preview(self, service, mock_client):
        """Test getting a query with preview mode."""
        # Setup
        query_api_name = "myQuery"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": "ri.functions.main.query.abc123",
            "apiName": query_api_name,
        }
        mock_client.functions.Query.get.return_value = mock_response

        # Execute
        service.get_query(query_api_name, preview=True)

        # Assert
        mock_client.functions.Query.get.assert_called_once_with(
            query_api_name, preview=True, version=None
        )

    def test_get_query_error(self, service, mock_client):
        """Test error handling in get_query."""
        # Setup
        query_api_name = "invalidQuery"
        mock_client.functions.Query.get.side_effect = Exception("Query not found")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to get query 'invalidQuery'"):
            service.get_query(query_api_name)

    # ===== Query Get-By-RID Tests =====

    def test_get_query_by_rid(self, service, mock_client):
        """Test getting a query by RID."""
        # Setup
        query_rid = "ri.functions.main.query.abc123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": query_rid,
            "apiName": "myQuery",
            "version": "1.0.0",
        }
        mock_client.functions.Query.get_by_rid.return_value = mock_response

        # Execute
        result = service.get_query_by_rid(query_rid)

        # Assert
        mock_client.functions.Query.get_by_rid.assert_called_once_with(
            query_rid, preview=False, version=None
        )
        assert result["rid"] == query_rid

    def test_get_query_by_rid_error(self, service, mock_client):
        """Test error handling in get_query_by_rid."""
        # Setup
        query_rid = "ri.functions.main.query.invalid"
        mock_client.functions.Query.get_by_rid.side_effect = Exception(
            "Query not found"
        )

        # Execute & Assert
        with pytest.raises(RuntimeError, match=f"Failed to get query {query_rid}"):
            service.get_query_by_rid(query_rid)

    # ===== Query Execute Tests =====

    def test_execute_query(self, service, mock_client):
        """Test executing a query by API name."""
        # Setup
        query_api_name = "myQuery"
        parameters = {"limit": 10, "filter": "active"}
        mock_response = Mock()
        mock_response.dict.return_value = {"result": [{"id": 1, "name": "Test"}]}
        mock_client.functions.Query.execute.return_value = mock_response

        # Execute
        result = service.execute_query(query_api_name, parameters=parameters)

        # Assert
        mock_client.functions.Query.execute.assert_called_once_with(
            query_api_name,
            parameters=parameters,
            preview=False,
            version=None,
        )
        assert "result" in result

    def test_execute_query_no_parameters(self, service, mock_client):
        """Test executing a query without parameters."""
        # Setup
        query_api_name = "myQuery"
        mock_response = Mock()
        mock_response.dict.return_value = {"result": []}
        mock_client.functions.Query.execute.return_value = mock_response

        # Execute
        service.execute_query(query_api_name)

        # Assert
        mock_client.functions.Query.execute.assert_called_once_with(
            query_api_name,
            parameters={},
            preview=False,
            version=None,
        )

    def test_execute_query_with_version(self, service, mock_client):
        """Test executing a specific query version."""
        # Setup
        query_api_name = "myQuery"
        version = "1.5.0"
        parameters = {"limit": 100}
        mock_response = Mock()
        mock_response.dict.return_value = {"result": []}
        mock_client.functions.Query.execute.return_value = mock_response

        # Execute
        service.execute_query(query_api_name, parameters=parameters, version=version)

        # Assert
        mock_client.functions.Query.execute.assert_called_once_with(
            query_api_name,
            parameters=parameters,
            preview=False,
            version=version,
        )

    def test_execute_query_with_preview(self, service, mock_client):
        """Test executing a query with preview mode."""
        # Setup
        query_api_name = "myQuery"
        mock_response = Mock()
        mock_response.dict.return_value = {"result": []}
        mock_client.functions.Query.execute.return_value = mock_response

        # Execute
        service.execute_query(query_api_name, preview=True)

        # Assert
        mock_client.functions.Query.execute.assert_called_once_with(
            query_api_name,
            parameters={},
            preview=True,
            version=None,
        )

    def test_execute_query_error(self, service, mock_client):
        """Test error handling in execute_query."""
        # Setup
        query_api_name = "myQuery"
        mock_client.functions.Query.execute.side_effect = Exception("Permission denied")

        # Execute & Assert
        with pytest.raises(
            RuntimeError, match=f"Failed to execute query '{query_api_name}'"
        ):
            service.execute_query(query_api_name)

    # ===== Query Execute-By-RID Tests =====

    def test_execute_query_by_rid(self, service, mock_client):
        """Test executing a query by RID."""
        # Setup
        query_rid = "ri.functions.main.query.abc123"
        parameters = {"limit": 10}
        mock_response = Mock()
        mock_response.dict.return_value = {"result": [{"id": 1}]}
        mock_client.functions.Query.execute_by_rid.return_value = mock_response

        # Execute
        service.execute_query_by_rid(query_rid, parameters=parameters)

        # Assert
        mock_client.functions.Query.execute_by_rid.assert_called_once_with(
            query_rid,
            parameters=parameters,
            preview=False,
            version=None,
        )

    def test_execute_query_by_rid_error(self, service, mock_client):
        """Test error handling in execute_query_by_rid."""
        # Setup
        query_rid = "ri.functions.main.query.invalid"
        mock_client.functions.Query.execute_by_rid.side_effect = Exception(
            "Query not found"
        )

        # Execute & Assert
        with pytest.raises(RuntimeError, match=f"Failed to execute query {query_rid}"):
            service.execute_query_by_rid(query_rid)

    # ===== Value Type Tests =====

    def test_get_value_type(self, service, mock_client):
        """Test getting a value type."""
        # Setup
        value_type_rid = "ri.functions.main.value-type.xyz"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": value_type_rid,
            "apiName": "MyValueType",
            "definition": {"type": "struct"},
        }
        mock_client.functions.ValueType.get.return_value = mock_response

        # Execute
        result = service.get_value_type(value_type_rid)

        # Assert
        mock_client.functions.ValueType.get.assert_called_once_with(
            value_type_rid, preview=False
        )
        assert result["rid"] == value_type_rid
        assert result["apiName"] == "MyValueType"

    def test_get_value_type_with_preview(self, service, mock_client):
        """Test getting a value type with preview mode."""
        # Setup
        value_type_rid = "ri.functions.main.value-type.xyz"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": value_type_rid,
            "apiName": "MyValueType",
        }
        mock_client.functions.ValueType.get.return_value = mock_response

        # Execute
        service.get_value_type(value_type_rid, preview=True)

        # Assert
        mock_client.functions.ValueType.get.assert_called_once_with(
            value_type_rid, preview=True
        )

    def test_get_value_type_error(self, service, mock_client):
        """Test error handling in get_value_type."""
        # Setup
        value_type_rid = "ri.functions.main.value-type.invalid"
        mock_client.functions.ValueType.get.side_effect = Exception(
            "ValueType not found"
        )

        # Execute & Assert
        with pytest.raises(
            RuntimeError, match=f"Failed to get value type {value_type_rid}"
        ):
            service.get_value_type(value_type_rid)

    # ===== Response Serialization Tests =====

    def test_response_serialization(self, service, mock_client):
        """Test that responses are properly serialized."""
        # Setup
        query_api_name = "myQuery"
        mock_response = Mock()
        # Simulate a Pydantic model with dict() method
        mock_response.dict.return_value = {
            "rid": "ri.functions.main.query.abc123",
            "apiName": query_api_name,
        }
        mock_client.functions.Query.get.return_value = mock_response

        # Execute
        result = service.get_query(query_api_name)

        # Assert
        assert isinstance(result, dict)
        assert result["apiName"] == query_api_name
        # Verify dict() was called for serialization
        mock_response.dict.assert_called_once()
