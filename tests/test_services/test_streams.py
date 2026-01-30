"""Tests for Streams service."""

import pytest
from unittest.mock import Mock, patch
from pltr.services.streams import StreamsService


class TestStreamsService:
    """Test Streams service functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.streams = Mock()
        client.streams.Dataset = Mock()
        client.streams.Dataset.Stream = Mock()
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create StreamsService with mocked client."""
        with patch("pltr.services.base.AuthManager") as mock_auth:
            mock_auth.return_value.get_client.return_value = mock_client
            service = StreamsService()
            return service

    # ===== Dataset Creation Tests =====

    def test_create_dataset(self, service, mock_client):
        """Test creating a streaming dataset."""
        # Setup
        name = "test-stream"
        parent_folder_rid = "ri.compass.main.folder.123"
        schema = {"fieldSchemaList": [{"name": "value", "type": "STRING"}]}
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": "ri.foundry.main.dataset.abc123",
            "name": name,
            "streamRid": "ri.foundry.main.stream.xyz789",
        }
        mock_client.streams.Dataset.create.return_value = mock_response

        # Execute
        result = service.create_dataset(
            name=name, parent_folder_rid=parent_folder_rid, schema=schema
        )

        # Assert
        mock_client.streams.Dataset.create.assert_called_once_with(
            name=name,
            parent_folder_rid=parent_folder_rid,
            schema=schema,
            branch_name=None,
            compressed=None,
            partitions_count=None,
            stream_type=None,
            preview=False,
        )
        assert result["name"] == name
        assert "rid" in result
        assert "streamRid" in result

    def test_create_dataset_with_options(self, service, mock_client):
        """Test creating a dataset with all options."""
        # Setup
        name = "high-throughput-stream"
        parent_folder_rid = "ri.compass.main.folder.123"
        schema = {"fieldSchemaList": [{"name": "id", "type": "INTEGER"}]}
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": "ri.foundry.main.dataset.abc123",
            "name": name,
        }
        mock_client.streams.Dataset.create.return_value = mock_response

        # Execute
        service.create_dataset(
            name=name,
            parent_folder_rid=parent_folder_rid,
            schema=schema,
            branch_name="develop",
            compressed=True,
            partitions_count=5,
            stream_type="HIGH_THROUGHPUT",
            preview=True,
        )

        # Assert
        mock_client.streams.Dataset.create.assert_called_once_with(
            name=name,
            parent_folder_rid=parent_folder_rid,
            schema=schema,
            branch_name="develop",
            compressed=True,
            partitions_count=5,
            stream_type="HIGH_THROUGHPUT",
            preview=True,
        )

    def test_create_dataset_error(self, service, mock_client):
        """Test error handling in create_dataset."""
        # Setup
        mock_client.streams.Dataset.create.side_effect = Exception("Permission denied")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to create streaming dataset"):
            service.create_dataset(
                name="test",
                parent_folder_rid="ri.compass.main.folder.123",
                schema={},
            )

    # ===== Stream Creation Tests =====

    def test_create_stream(self, service, mock_client):
        """Test creating a stream on a branch."""
        # Setup
        dataset_rid = "ri.foundry.main.dataset.123"
        branch_name = "feature-branch"
        schema = {"fieldSchemaList": [{"name": "value", "type": "STRING"}]}
        mock_response = Mock()
        mock_response.dict.return_value = {
            "streamRid": "ri.foundry.main.stream.xyz789",
            "branchName": branch_name,
        }
        mock_client.streams.Dataset.Stream.create.return_value = mock_response

        # Execute
        result = service.create_stream(
            dataset_rid=dataset_rid, branch_name=branch_name, schema=schema
        )

        # Assert
        mock_client.streams.Dataset.Stream.create.assert_called_once_with(
            dataset_rid=dataset_rid,
            branch_name=branch_name,
            schema=schema,
            compressed=None,
            partitions_count=None,
            stream_type=None,
            preview=False,
        )
        assert result["branchName"] == branch_name
        assert "streamRid" in result

    def test_create_stream_error(self, service, mock_client):
        """Test error handling in create_stream."""
        # Setup
        mock_client.streams.Dataset.Stream.create.side_effect = Exception(
            "Branch already exists"
        )

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to create stream"):
            service.create_stream(
                dataset_rid="ri.foundry.main.dataset.123",
                branch_name="main",
                schema={},
            )

    # ===== Get Stream Tests =====

    def test_get_stream(self, service, mock_client):
        """Test getting stream information."""
        # Setup
        dataset_rid = "ri.foundry.main.dataset.123"
        branch_name = "master"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "streamRid": "ri.foundry.main.stream.xyz789",
            "branchName": branch_name,
            "schema": {"fieldSchemaList": []},
        }
        mock_client.streams.Dataset.Stream.get.return_value = mock_response

        # Execute
        result = service.get_stream(
            dataset_rid=dataset_rid, stream_branch_name=branch_name
        )

        # Assert
        mock_client.streams.Dataset.Stream.get.assert_called_once_with(
            dataset_rid=dataset_rid, stream_branch_name=branch_name, preview=False
        )
        assert result["branchName"] == branch_name
        assert "streamRid" in result

    def test_get_stream_with_preview(self, service, mock_client):
        """Test getting stream with preview mode."""
        # Setup
        dataset_rid = "ri.foundry.main.dataset.123"
        branch_name = "master"
        mock_response = Mock()
        mock_response.dict.return_value = {"streamRid": "ri.foundry.main.stream.xyz789"}
        mock_client.streams.Dataset.Stream.get.return_value = mock_response

        # Execute
        service.get_stream(
            dataset_rid=dataset_rid, stream_branch_name=branch_name, preview=True
        )

        # Assert
        mock_client.streams.Dataset.Stream.get.assert_called_once_with(
            dataset_rid=dataset_rid, stream_branch_name=branch_name, preview=True
        )

    def test_get_stream_error(self, service, mock_client):
        """Test error handling in get_stream."""
        # Setup
        mock_client.streams.Dataset.Stream.get.side_effect = Exception(
            "Stream not found"
        )

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to get stream"):
            service.get_stream(
                dataset_rid="ri.foundry.main.dataset.123", stream_branch_name="master"
            )

    # ===== Publish Record Tests =====

    def test_publish_record(self, service, mock_client):
        """Test publishing a single record."""
        # Setup
        dataset_rid = "ri.foundry.main.dataset.123"
        branch_name = "master"
        record = {"id": 123, "name": "test"}

        # Execute
        service.publish_record(
            dataset_rid=dataset_rid, stream_branch_name=branch_name, record=record
        )

        # Assert
        mock_client.streams.Dataset.Stream.publish_record.assert_called_once_with(
            dataset_rid=dataset_rid,
            stream_branch_name=branch_name,
            record=record,
            view_rid=None,
            preview=False,
        )

    def test_publish_record_with_view(self, service, mock_client):
        """Test publishing record with view RID."""
        # Setup
        dataset_rid = "ri.foundry.main.dataset.123"
        branch_name = "master"
        record = {"id": 123}
        view_rid = "ri.foundry.main.view.abc"

        # Execute
        service.publish_record(
            dataset_rid=dataset_rid,
            stream_branch_name=branch_name,
            record=record,
            view_rid=view_rid,
            preview=True,
        )

        # Assert
        mock_client.streams.Dataset.Stream.publish_record.assert_called_once_with(
            dataset_rid=dataset_rid,
            stream_branch_name=branch_name,
            record=record,
            view_rid=view_rid,
            preview=True,
        )

    def test_publish_record_error(self, service, mock_client):
        """Test error handling in publish_record."""
        # Setup
        mock_client.streams.Dataset.Stream.publish_record.side_effect = Exception(
            "Schema mismatch"
        )

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to publish record"):
            service.publish_record(
                dataset_rid="ri.foundry.main.dataset.123",
                stream_branch_name="master",
                record={},
            )

    # ===== Publish Records (Batch) Tests =====

    def test_publish_records(self, service, mock_client):
        """Test publishing multiple records."""
        # Setup
        dataset_rid = "ri.foundry.main.dataset.123"
        branch_name = "master"
        records = [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]

        # Execute
        service.publish_records(
            dataset_rid=dataset_rid, stream_branch_name=branch_name, records=records
        )

        # Assert
        mock_client.streams.Dataset.Stream.publish_records.assert_called_once_with(
            dataset_rid=dataset_rid,
            stream_branch_name=branch_name,
            records=records,
            view_rid=None,
            preview=False,
        )

    def test_publish_records_error(self, service, mock_client):
        """Test error handling in publish_records."""
        # Setup
        mock_client.streams.Dataset.Stream.publish_records.side_effect = Exception(
            "Batch failed"
        )

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to publish 2 records"):
            service.publish_records(
                dataset_rid="ri.foundry.main.dataset.123",
                stream_branch_name="master",
                records=[{}, {}],
            )

    # ===== Reset Stream Tests =====

    def test_reset_stream(self, service, mock_client):
        """Test resetting a stream."""
        # Setup
        dataset_rid = "ri.foundry.main.dataset.123"
        branch_name = "master"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "streamRid": "ri.foundry.main.stream.xyz789",
            "branchName": branch_name,
        }
        mock_client.streams.Dataset.Stream.reset.return_value = mock_response

        # Execute
        result = service.reset_stream(
            dataset_rid=dataset_rid, stream_branch_name=branch_name
        )

        # Assert
        mock_client.streams.Dataset.Stream.reset.assert_called_once_with(
            dataset_rid=dataset_rid, stream_branch_name=branch_name, preview=False
        )
        assert result["branchName"] == branch_name

    def test_reset_stream_with_preview(self, service, mock_client):
        """Test resetting stream with preview mode."""
        # Setup
        dataset_rid = "ri.foundry.main.dataset.123"
        branch_name = "master"
        mock_response = Mock()
        mock_response.dict.return_value = {}
        mock_client.streams.Dataset.Stream.reset.return_value = mock_response

        # Execute
        service.reset_stream(
            dataset_rid=dataset_rid, stream_branch_name=branch_name, preview=True
        )

        # Assert
        mock_client.streams.Dataset.Stream.reset.assert_called_once_with(
            dataset_rid=dataset_rid, stream_branch_name=branch_name, preview=True
        )

    def test_reset_stream_error(self, service, mock_client):
        """Test error handling in reset_stream."""
        # Setup
        mock_client.streams.Dataset.Stream.reset.side_effect = Exception("Reset failed")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to reset stream"):
            service.reset_stream(
                dataset_rid="ri.foundry.main.dataset.123", stream_branch_name="master"
            )
