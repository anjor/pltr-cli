"""Tests for Streams commands."""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner
from pltr.cli import app


class TestStreamsCommands:
    """Test Streams CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock StreamsService."""
        with patch("pltr.commands.streams.StreamsService") as MockService:
            mock_svc = Mock()
            MockService.return_value = mock_svc
            yield mock_svc

    # ===== Dataset Create Tests =====

    def test_dataset_create_success(self, runner, mock_service):
        """Test successful dataset creation."""
        # Setup
        dataset_result = {
            "rid": "ri.foundry.main.dataset.abc123",
            "name": "test-stream",
            "streamRid": "ri.foundry.main.stream.xyz789",
        }
        mock_service.create_dataset.return_value = dataset_result

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "dataset",
                "create",
                "test-stream",
                "--folder",
                "ri.compass.main.folder.123",
                "--schema",
                '{"fieldSchemaList": [{"name": "value", "type": "STRING"}]}',
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Created streaming dataset" in result.output
        mock_service.create_dataset.assert_called_once()

    def test_dataset_create_with_options(self, runner, mock_service):
        """Test dataset creation with all options."""
        # Setup
        dataset_result = {
            "rid": "ri.foundry.main.dataset.abc123",
            "name": "high-throughput-stream",
        }
        mock_service.create_dataset.return_value = dataset_result

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "dataset",
                "create",
                "high-throughput-stream",
                "--folder",
                "ri.compass.main.folder.123",
                "--schema",
                '{"fieldSchemaList": []}',
                "--branch",
                "develop",
                "--compressed",
                "--partitions",
                "5",
                "--type",
                "HIGH_THROUGHPUT",
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_kwargs = mock_service.create_dataset.call_args[1]
        assert call_kwargs["branch_name"] == "develop"
        assert call_kwargs["compressed"] is True
        assert call_kwargs["partitions_count"] == 5
        assert call_kwargs["stream_type"] == "HIGH_THROUGHPUT"
        assert call_kwargs["preview"] is True

    def test_dataset_create_invalid_schema(self, runner, mock_service):
        """Test dataset creation with invalid JSON schema."""
        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "dataset",
                "create",
                "test-stream",
                "--folder",
                "ri.compass.main.folder.123",
                "--schema",
                "invalid-json",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error parsing schema" in result.output

    def test_dataset_create_error(self, runner, mock_service):
        """Test dataset creation with service error."""
        # Setup
        mock_service.create_dataset.side_effect = Exception("Permission denied")

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "dataset",
                "create",
                "test-stream",
                "--folder",
                "ri.compass.main.folder.123",
                "--schema",
                "{}",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error:" in result.output

    # ===== Stream Create Tests =====

    def test_stream_create_success(self, runner, mock_service):
        """Test successful stream creation."""
        # Setup
        stream_result = {
            "streamRid": "ri.foundry.main.stream.xyz789",
            "branchName": "feature-branch",
        }
        mock_service.create_stream.return_value = stream_result

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "create",
                "ri.foundry.main.dataset.123",
                "--branch",
                "feature-branch",
                "--schema",
                '{"fieldSchemaList": []}',
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Created stream" in result.output
        mock_service.create_stream.assert_called_once()

    def test_stream_create_with_options(self, runner, mock_service):
        """Test stream creation with all options."""
        # Setup
        stream_result = {"streamRid": "ri.foundry.main.stream.xyz789"}
        mock_service.create_stream.return_value = stream_result

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "create",
                "ri.foundry.main.dataset.123",
                "--branch",
                "production",
                "--schema",
                "{}",
                "--compressed",
                "--partitions",
                "10",
                "--type",
                "LOW_LATENCY",
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_kwargs = mock_service.create_stream.call_args[1]
        assert call_kwargs["branch_name"] == "production"
        assert call_kwargs["compressed"] is True
        assert call_kwargs["partitions_count"] == 10
        assert call_kwargs["stream_type"] == "LOW_LATENCY"

    def test_stream_create_error(self, runner, mock_service):
        """Test stream creation with service error."""
        # Setup
        mock_service.create_stream.side_effect = Exception("Branch already exists")

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "create",
                "ri.foundry.main.dataset.123",
                "--branch",
                "main",
                "--schema",
                "{}",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error:" in result.output

    # ===== Stream Get Tests =====

    def test_stream_get_success(self, runner, mock_service):
        """Test successful get stream."""
        # Setup
        stream_result = {
            "streamRid": "ri.foundry.main.stream.xyz789",
            "branchName": "master",
            "schema": {"fieldSchemaList": []},
        }
        mock_service.get_stream.return_value = stream_result

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "get",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.get_stream.assert_called_once_with(
            dataset_rid="ri.foundry.main.dataset.123",
            stream_branch_name="master",
            preview=False,
        )

    def test_stream_get_with_preview(self, runner, mock_service):
        """Test get stream with preview mode."""
        # Setup
        stream_result = {"streamRid": "ri.foundry.main.stream.xyz789"}
        mock_service.get_stream.return_value = stream_result

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "get",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_kwargs = mock_service.get_stream.call_args[1]
        assert call_kwargs["preview"] is True

    def test_stream_get_error(self, runner, mock_service):
        """Test get stream with service error."""
        # Setup
        mock_service.get_stream.side_effect = Exception("Stream not found")

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "get",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error:" in result.output

    # ===== Publish Record Tests =====

    def test_publish_record_success(self, runner, mock_service):
        """Test successful record publishing."""
        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "publish",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
                "--record",
                '{"id": 123, "name": "test"}',
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Record published successfully" in result.output
        mock_service.publish_record.assert_called_once()

    def test_publish_record_with_view(self, runner, mock_service):
        """Test publishing record with view RID."""
        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "publish",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
                "--record",
                "{}",
                "--view",
                "ri.foundry.main.view.abc",
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_kwargs = mock_service.publish_record.call_args[1]
        assert call_kwargs["view_rid"] == "ri.foundry.main.view.abc"
        assert call_kwargs["preview"] is True

    def test_publish_record_invalid_json(self, runner, mock_service):
        """Test publishing record with invalid JSON."""
        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "publish",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
                "--record",
                "invalid-json",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error parsing record" in result.output

    def test_publish_record_error(self, runner, mock_service):
        """Test publishing record with service error."""
        # Setup
        mock_service.publish_record.side_effect = Exception("Schema mismatch")

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "publish",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
                "--record",
                "{}",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error:" in result.output

    # ===== Publish Batch Tests =====

    def test_publish_batch_success(self, runner, mock_service):
        """Test successful batch record publishing."""
        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "publish-batch",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
                "--records",
                '[{"id": 1}, {"id": 2}]',
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Published 2 records successfully" in result.output
        mock_service.publish_records.assert_called_once()

    def test_publish_batch_invalid_json(self, runner, mock_service):
        """Test batch publishing with invalid JSON."""
        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "publish-batch",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
                "--records",
                "not-a-list",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error parsing records" in result.output

    def test_publish_batch_not_array(self, runner, mock_service):
        """Test batch publishing with non-array JSON."""
        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "publish-batch",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
                "--records",
                '{"id": 1}',
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "must be a JSON array" in result.output

    # ===== Reset Stream Tests =====

    def test_reset_stream_with_confirm(self, runner, mock_service):
        """Test stream reset with confirmation flag."""
        # Setup
        stream_result = {
            "streamRid": "ri.foundry.main.stream.xyz789",
            "branchName": "master",
        }
        mock_service.reset_stream.return_value = stream_result

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "reset",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
                "--confirm",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "Stream reset successfully" in result.output
        mock_service.reset_stream.assert_called_once()

    def test_reset_stream_cancelled(self, runner, mock_service):
        """Test stream reset cancelled by user."""
        # Execute (simulate user saying 'no' to confirmation)
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "reset",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
            ],
            input="n\n",
        )

        # Assert
        assert result.exit_code == 0
        assert "Operation cancelled" in result.output
        mock_service.reset_stream.assert_not_called()

    def test_reset_stream_confirmed(self, runner, mock_service):
        """Test stream reset with user confirmation."""
        # Setup
        stream_result = {"streamRid": "ri.foundry.main.stream.xyz789"}
        mock_service.reset_stream.return_value = stream_result

        # Execute (simulate user saying 'yes' to confirmation)
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "reset",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
            ],
            input="y\n",
        )

        # Assert
        assert result.exit_code == 0
        assert "Stream reset successfully" in result.output
        mock_service.reset_stream.assert_called_once()

    def test_reset_stream_error(self, runner, mock_service):
        """Test stream reset with service error."""
        # Setup
        mock_service.reset_stream.side_effect = Exception("Reset failed")

        # Execute
        result = runner.invoke(
            app,
            [
                "streams",
                "stream",
                "reset",
                "ri.foundry.main.dataset.123",
                "--branch",
                "master",
                "--confirm",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Error:" in result.output
