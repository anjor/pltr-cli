"""
Tests for mediasets CLI commands.
"""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from pltr.commands.mediasets import app
from pltr.auth.base import ProfileNotFoundError, MissingCredentialsError

runner = CliRunner()


@pytest.fixture
def mock_mediasets_service():
    """Mock MediaSetsService for command tests."""
    with patch("pltr.commands.mediasets.MediaSetsService") as mock_service_class:
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        yield mock_service


@pytest.fixture
def sample_media_item():
    """Sample media item for testing."""
    return {
        "media_item_rid": "ri.mediasets.main.media-item.test",
        "filename": "test-image.jpg",
        "size": 12345,
        "content_type": "image/jpeg",
        "created_time": "2024-01-01T00:00:00Z",
        "updated_time": "2024-01-02T00:00:00Z",
    }


@pytest.fixture
def sample_media_reference():
    """Sample media reference for testing."""
    return {
        "reference_id": "ref-12345",
        "url": "https://example.com/media/test",
        "expires_at": "2024-01-01T01:00:00Z",
    }


@pytest.fixture
def sample_thumbnail_status():
    """Sample thumbnail status for testing."""
    return {
        "status": "COMPLETED",
        "transformation_id": "transform-12345",
        "media_item_rid": "ri.mediasets.main.media-item.test",
    }


# Get Media Item Tests
def test_get_media_item_success(mock_mediasets_service, sample_media_item):
    """Test successful media item retrieval."""
    mock_mediasets_service.get_media_set_info.return_value = sample_media_item

    result = runner.invoke(
        app,
        [
            "get",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
        ],
    )

    assert result.exit_code == 0
    mock_mediasets_service.get_media_set_info.assert_called_once()


def test_get_media_item_auth_error(mock_mediasets_service):
    """Test media item retrieval with authentication error."""
    mock_mediasets_service.get_media_set_info.side_effect = ProfileNotFoundError(
        "Profile not found"
    )

    result = runner.invoke(
        app,
        [
            "get",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
        ],
    )

    assert result.exit_code == 1
    assert "Authentication error" in result.output


def test_get_media_item_with_format(mock_mediasets_service, sample_media_item):
    """Test media item retrieval with different formats."""
    mock_mediasets_service.get_media_set_info.return_value = sample_media_item

    result = runner.invoke(
        app,
        [
            "get",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0


# Get By Path Tests
def test_get_by_path_success(mock_mediasets_service):
    """Test successful media item path lookup."""
    mock_mediasets_service.get_media_item_by_path.return_value = {
        "rid": "ri.mediasets.main.media-item.test",
        "path": "/images/test.jpg",
    }

    result = runner.invoke(
        app,
        ["get-by-path", "ri.mediasets.main.media-set.test", "/images/test.jpg"],
    )

    assert result.exit_code == 0
    mock_mediasets_service.get_media_item_by_path.assert_called_once()


# Transaction Tests
def test_create_transaction_success(mock_mediasets_service):
    """Test successful transaction creation."""
    mock_mediasets_service.create_transaction.return_value = "transaction-12345"

    result = runner.invoke(
        app,
        ["create", "ri.mediasets.main.media-set.test"],
    )

    assert result.exit_code == 0
    assert "Successfully created transaction" in result.output
    mock_mediasets_service.create_transaction.assert_called_once()


def test_commit_transaction_success(mock_mediasets_service):
    """Test successful transaction commit."""
    result = runner.invoke(
        app,
        [
            "commit",
            "ri.mediasets.main.media-set.test",
            "transaction-12345",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully committed transaction" in result.output
    mock_mediasets_service.commit_transaction.assert_called_once()


def test_abort_transaction_success(mock_mediasets_service):
    """Test successful transaction abort."""
    result = runner.invoke(
        app,
        [
            "abort",
            "ri.mediasets.main.media-set.test",
            "transaction-12345",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully aborted transaction" in result.output
    mock_mediasets_service.abort_transaction.assert_called_once()


# Upload Tests
def test_upload_media_file_not_found(mock_mediasets_service):
    """Test upload with non-existent file."""
    result = runner.invoke(
        app,
        [
            "upload",
            "ri.mediasets.main.media-set.test",
            "/nonexistent/file.jpg",
            "/images/file.jpg",
            "transaction-12345",
        ],
    )

    assert result.exit_code == 1
    assert "File not found" in result.output


# Download Tests
def test_download_media_success(mock_mediasets_service, tmp_path):
    """Test successful media download."""
    mock_mediasets_service.download_media.return_value = {
        "media_set_rid": "ri.mediasets.main.media-set.test",
        "media_item_rid": "ri.mediasets.main.media-item.test",
        "output_path": str(tmp_path / "downloaded.jpg"),
        "file_size": 12345,
        "downloaded": True,
        "original": False,
    }

    result = runner.invoke(
        app,
        [
            "download",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
            str(tmp_path / "downloaded.jpg"),
        ],
    )

    assert result.exit_code == 0
    assert "Successfully downloaded" in result.output


def test_download_media_file_exists(mock_mediasets_service, tmp_path):
    """Test download when output file already exists."""
    # Create existing file
    existing_file = tmp_path / "existing.jpg"
    existing_file.write_text("existing content")

    result = runner.invoke(
        app,
        [
            "download",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
            str(existing_file),
        ],
    )

    assert result.exit_code == 1
    assert "File already exists" in result.output


# Reference Tests
def test_get_reference_success(mock_mediasets_service, sample_media_reference):
    """Test successful media reference retrieval."""
    mock_mediasets_service.get_media_reference.return_value = sample_media_reference

    result = runner.invoke(
        app,
        [
            "reference",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
        ],
    )

    assert result.exit_code == 0
    mock_mediasets_service.get_media_reference.assert_called_once()


# Thumbnail Calculate Tests
def test_thumbnail_calculate_success(mock_mediasets_service, sample_thumbnail_status):
    """Test successful thumbnail calculation initiation."""
    mock_mediasets_service.calculate_thumbnail.return_value = sample_thumbnail_status

    result = runner.invoke(
        app,
        [
            "thumbnail-calculate",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
        ],
    )

    assert result.exit_code == 0
    mock_mediasets_service.calculate_thumbnail.assert_called_once_with(
        "ri.mediasets.main.media-set.test",
        "ri.mediasets.main.media-item.test",
        preview=False,
    )


def test_thumbnail_calculate_with_format(
    mock_mediasets_service, sample_thumbnail_status
):
    """Test thumbnail calculation with JSON format."""
    mock_mediasets_service.calculate_thumbnail.return_value = sample_thumbnail_status

    result = runner.invoke(
        app,
        [
            "thumbnail-calculate",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0


def test_thumbnail_calculate_auth_error(mock_mediasets_service):
    """Test thumbnail calculation with authentication error."""
    mock_mediasets_service.calculate_thumbnail.side_effect = MissingCredentialsError(
        "Missing credentials"
    )

    result = runner.invoke(
        app,
        [
            "thumbnail-calculate",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
        ],
    )

    assert result.exit_code == 1
    assert "Authentication error" in result.output


# Thumbnail Retrieve Tests
def test_thumbnail_retrieve_success(mock_mediasets_service, tmp_path):
    """Test successful thumbnail retrieval."""
    output_file = tmp_path / "thumbnail.webp"
    mock_mediasets_service.retrieve_thumbnail.return_value = {
        "media_set_rid": "ri.mediasets.main.media-set.test",
        "media_item_rid": "ri.mediasets.main.media-item.test",
        "output_path": str(output_file),
        "file_size": 5000,
        "downloaded": True,
        "format": "image/webp",
    }

    result = runner.invoke(
        app,
        [
            "thumbnail-retrieve",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
            str(output_file),
        ],
    )

    assert result.exit_code == 0
    assert "Successfully downloaded thumbnail" in result.output
    mock_mediasets_service.retrieve_thumbnail.assert_called_once()


def test_thumbnail_retrieve_file_exists(mock_mediasets_service, tmp_path):
    """Test thumbnail retrieval when output file already exists."""
    existing_file = tmp_path / "existing.webp"
    existing_file.write_text("existing content")

    result = runner.invoke(
        app,
        [
            "thumbnail-retrieve",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
            str(existing_file),
        ],
    )

    assert result.exit_code == 1
    assert "File already exists" in result.output


def test_thumbnail_retrieve_with_overwrite(mock_mediasets_service, tmp_path):
    """Test thumbnail retrieval with overwrite flag."""
    existing_file = tmp_path / "existing.webp"
    existing_file.write_text("existing content")

    mock_mediasets_service.retrieve_thumbnail.return_value = {
        "media_set_rid": "ri.mediasets.main.media-set.test",
        "media_item_rid": "ri.mediasets.main.media-item.test",
        "output_path": str(existing_file),
        "file_size": 5000,
        "downloaded": True,
        "format": "image/webp",
    }

    result = runner.invoke(
        app,
        [
            "thumbnail-retrieve",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
            str(existing_file),
            "--overwrite",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully downloaded thumbnail" in result.output


def test_thumbnail_retrieve_auth_error(mock_mediasets_service, tmp_path):
    """Test thumbnail retrieval with authentication error."""
    mock_mediasets_service.retrieve_thumbnail.side_effect = ProfileNotFoundError(
        "Profile not found"
    )

    result = runner.invoke(
        app,
        [
            "thumbnail-retrieve",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
            str(tmp_path / "thumbnail.webp"),
        ],
    )

    assert result.exit_code == 1
    assert "Authentication error" in result.output


# Upload Temp Tests
def test_upload_temp_success(mock_mediasets_service, tmp_path, sample_media_reference):
    """Test successful temporary media upload."""
    # Create a test file
    test_file = tmp_path / "test-image.jpg"
    test_file.write_bytes(b"fake image content")

    mock_mediasets_service.upload_temp_media.return_value = sample_media_reference

    result = runner.invoke(
        app,
        ["upload-temp", str(test_file)],
    )

    assert result.exit_code == 0
    assert "Successfully uploaded temporary media" in result.output
    mock_mediasets_service.upload_temp_media.assert_called_once()


def test_upload_temp_with_filename(
    mock_mediasets_service, tmp_path, sample_media_reference
):
    """Test temporary upload with custom filename."""
    test_file = tmp_path / "test-image.jpg"
    test_file.write_bytes(b"fake image content")

    mock_mediasets_service.upload_temp_media.return_value = sample_media_reference

    result = runner.invoke(
        app,
        ["upload-temp", str(test_file), "--filename", "custom-name.jpg"],
    )

    assert result.exit_code == 0
    call_args = mock_mediasets_service.upload_temp_media.call_args
    assert call_args[1]["filename"] == "custom-name.jpg"


def test_upload_temp_with_attribution(
    mock_mediasets_service, tmp_path, sample_media_reference
):
    """Test temporary upload with attribution."""
    test_file = tmp_path / "test-image.jpg"
    test_file.write_bytes(b"fake image content")

    mock_mediasets_service.upload_temp_media.return_value = sample_media_reference

    result = runner.invoke(
        app,
        ["upload-temp", str(test_file), "--attribution", "Photo by Test User"],
    )

    assert result.exit_code == 0
    call_args = mock_mediasets_service.upload_temp_media.call_args
    assert call_args[1]["attribution"] == "Photo by Test User"


def test_upload_temp_file_not_found(mock_mediasets_service):
    """Test temporary upload with non-existent file."""
    result = runner.invoke(
        app,
        ["upload-temp", "/nonexistent/file.jpg"],
    )

    assert result.exit_code == 1
    assert "File not found" in result.output


def test_upload_temp_auth_error(mock_mediasets_service, tmp_path):
    """Test temporary upload with authentication error."""
    test_file = tmp_path / "test-image.jpg"
    test_file.write_bytes(b"fake image content")

    mock_mediasets_service.upload_temp_media.side_effect = MissingCredentialsError(
        "Missing credentials"
    )

    result = runner.invoke(
        app,
        ["upload-temp", str(test_file)],
    )

    assert result.exit_code == 1
    assert "Authentication error" in result.output


# Error handling tests
def test_command_generic_error(mock_mediasets_service):
    """Test generic error handling in commands."""
    mock_mediasets_service.get_media_set_info.side_effect = Exception(
        "Unexpected error"
    )

    result = runner.invoke(
        app,
        [
            "get",
            "ri.mediasets.main.media-set.test",
            "ri.mediasets.main.media-item.test",
        ],
    )

    assert result.exit_code == 1
    assert "Failed to get media item" in result.output
