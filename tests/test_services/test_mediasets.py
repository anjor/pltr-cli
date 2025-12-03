"""
Tests for mediasets service.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from pltr.services.mediasets import MediaSetsService


@pytest.fixture
def mock_mediasets_service():
    """Create a mocked MediaSetsService."""
    with patch("pltr.services.base.AuthManager") as mock_auth:
        # Set up client mock
        mock_client = Mock()
        mock_media_sets = Mock()
        mock_media_set_class = Mock()

        mock_media_sets.MediaSet = mock_media_set_class
        mock_client.media_sets = mock_media_sets
        mock_auth.return_value.get_client.return_value = mock_client

        # Create service
        service = MediaSetsService()
        return service, mock_media_set_class


@pytest.fixture
def sample_thumbnail_response():
    """Create sample thumbnail status response."""
    response = Mock()
    response.status = "COMPLETED"
    response.transformation_id = "transform-12345"
    response.media_item_rid = "ri.mediasets.main.media-item.test"
    return response


@pytest.fixture
def sample_media_reference_response():
    """Create sample media reference response."""
    response = Mock()
    response.reference_id = "ref-12345"
    response.url = "https://example.com/media/test"
    response.expires_at = "2024-01-01T01:00:00Z"
    return response


def test_mediasets_service_initialization():
    """Test MediaSetsService initialization."""
    with patch("pltr.services.base.AuthManager"):
        service = MediaSetsService()
        assert service is not None


def test_mediasets_service_get_service(mock_mediasets_service):
    """Test getting the underlying media_sets service."""
    service, mock_media_set = mock_mediasets_service
    media_sets = service._get_service()
    assert media_sets.MediaSet == mock_media_set


# calculate_thumbnail tests
def test_calculate_thumbnail_success(mock_mediasets_service, sample_thumbnail_response):
    """Test successful thumbnail calculation."""
    service, mock_media_set = mock_mediasets_service
    mock_media_set.calculate.return_value = sample_thumbnail_response

    result = service.calculate_thumbnail(
        media_set_rid="ri.mediasets.main.media-set.test",
        media_item_rid="ri.mediasets.main.media-item.test",
    )

    assert result["status"] == "COMPLETED"
    assert result["transformation_id"] == "transform-12345"
    assert result["media_item_rid"] == "ri.mediasets.main.media-item.test"
    mock_media_set.calculate.assert_called_once_with(
        media_set_rid="ri.mediasets.main.media-set.test",
        media_item_rid="ri.mediasets.main.media-item.test",
        preview=False,
    )


def test_calculate_thumbnail_with_preview(
    mock_mediasets_service, sample_thumbnail_response
):
    """Test thumbnail calculation with preview mode."""
    service, mock_media_set = mock_mediasets_service
    mock_media_set.calculate.return_value = sample_thumbnail_response

    service.calculate_thumbnail(
        media_set_rid="ri.mediasets.main.media-set.test",
        media_item_rid="ri.mediasets.main.media-item.test",
        preview=True,
    )

    mock_media_set.calculate.assert_called_once_with(
        media_set_rid="ri.mediasets.main.media-set.test",
        media_item_rid="ri.mediasets.main.media-item.test",
        preview=True,
    )


def test_calculate_thumbnail_error(mock_mediasets_service):
    """Test thumbnail calculation error handling."""
    service, mock_media_set = mock_mediasets_service
    mock_media_set.calculate.side_effect = Exception("API error")

    with pytest.raises(RuntimeError) as exc_info:
        service.calculate_thumbnail(
            media_set_rid="ri.mediasets.main.media-set.test",
            media_item_rid="ri.mediasets.main.media-item.test",
        )

    assert "Failed to calculate thumbnail" in str(exc_info.value)


# retrieve_thumbnail tests
def test_retrieve_thumbnail_success(mock_mediasets_service, tmp_path):
    """Test successful thumbnail retrieval."""
    service, mock_media_set = mock_mediasets_service

    # Mock response with content
    mock_response = Mock()
    mock_response.content = b"fake webp image data"
    mock_media_set.retrieve.return_value = mock_response

    output_file = tmp_path / "thumbnail.webp"
    result = service.retrieve_thumbnail(
        media_set_rid="ri.mediasets.main.media-set.test",
        media_item_rid="ri.mediasets.main.media-item.test",
        output_path=str(output_file),
    )

    assert result["downloaded"] is True
    assert result["format"] == "image/webp"
    assert result["file_size"] == len(b"fake webp image data")
    assert output_file.exists()
    mock_media_set.retrieve.assert_called_once()


def test_retrieve_thumbnail_streaming(mock_mediasets_service, tmp_path):
    """Test thumbnail retrieval with streaming response."""
    service, mock_media_set = mock_mediasets_service

    # Mock streaming response (no content attribute) using MagicMock for __iter__
    mock_response = MagicMock()
    del mock_response.content  # Remove content attribute to trigger streaming path
    mock_response.__iter__.return_value = iter([b"chunk1", b"chunk2"])
    mock_media_set.retrieve.return_value = mock_response

    output_file = tmp_path / "thumbnail.webp"
    result = service.retrieve_thumbnail(
        media_set_rid="ri.mediasets.main.media-set.test",
        media_item_rid="ri.mediasets.main.media-item.test",
        output_path=str(output_file),
    )

    assert result["downloaded"] is True
    assert output_file.exists()
    assert output_file.read_bytes() == b"chunk1chunk2"


def test_retrieve_thumbnail_empty_content(mock_mediasets_service, tmp_path):
    """Test thumbnail retrieval with empty content raises error."""
    service, mock_media_set = mock_mediasets_service

    # Mock response with empty content
    mock_response = Mock()
    mock_response.content = b""
    mock_media_set.retrieve.return_value = mock_response

    output_file = tmp_path / "thumbnail.webp"
    with pytest.raises(RuntimeError) as exc_info:
        service.retrieve_thumbnail(
            media_set_rid="ri.mediasets.main.media-set.test",
            media_item_rid="ri.mediasets.main.media-item.test",
            output_path=str(output_file),
        )

    assert "Downloaded thumbnail is empty" in str(exc_info.value)
    # Ensure empty file was cleaned up
    assert not output_file.exists()


def test_retrieve_thumbnail_creates_parent_dirs(mock_mediasets_service, tmp_path):
    """Test that retrieve_thumbnail creates parent directories."""
    service, mock_media_set = mock_mediasets_service

    mock_response = Mock()
    mock_response.content = b"fake webp image data"
    mock_media_set.retrieve.return_value = mock_response

    # Use a nested path that doesn't exist
    output_file = tmp_path / "nested" / "dir" / "thumbnail.webp"
    service.retrieve_thumbnail(
        media_set_rid="ri.mediasets.main.media-set.test",
        media_item_rid="ri.mediasets.main.media-item.test",
        output_path=str(output_file),
    )

    assert output_file.exists()
    assert output_file.parent.exists()


def test_retrieve_thumbnail_error(mock_mediasets_service, tmp_path):
    """Test thumbnail retrieval error handling."""
    service, mock_media_set = mock_mediasets_service
    mock_media_set.retrieve.side_effect = Exception("API error")

    with pytest.raises(RuntimeError) as exc_info:
        service.retrieve_thumbnail(
            media_set_rid="ri.mediasets.main.media-set.test",
            media_item_rid="ri.mediasets.main.media-item.test",
            output_path=str(tmp_path / "thumbnail.webp"),
        )

    assert "Failed to retrieve thumbnail" in str(exc_info.value)


# upload_temp_media tests
def test_upload_temp_media_success(
    mock_mediasets_service, tmp_path, sample_media_reference_response
):
    """Test successful temporary media upload."""
    service, mock_media_set = mock_mediasets_service
    mock_media_set.upload_media.return_value = sample_media_reference_response

    # Create test file
    test_file = tmp_path / "test.jpg"
    test_file.write_bytes(b"fake image data")

    result = service.upload_temp_media(file_path=str(test_file))

    assert result["reference_id"] == "ref-12345"
    assert result["url"] == "https://example.com/media/test"
    mock_media_set.upload_media.assert_called_once()


def test_upload_temp_media_with_filename(
    mock_mediasets_service, tmp_path, sample_media_reference_response
):
    """Test temporary upload with custom filename."""
    service, mock_media_set = mock_mediasets_service
    mock_media_set.upload_media.return_value = sample_media_reference_response

    test_file = tmp_path / "test.jpg"
    test_file.write_bytes(b"fake image data")

    service.upload_temp_media(
        file_path=str(test_file),
        filename="custom-name.jpg",
    )

    call_args = mock_media_set.upload_media.call_args
    assert call_args[1]["filename"] == "custom-name.jpg"


def test_upload_temp_media_with_attribution(
    mock_mediasets_service, tmp_path, sample_media_reference_response
):
    """Test temporary upload with attribution."""
    service, mock_media_set = mock_mediasets_service
    mock_media_set.upload_media.return_value = sample_media_reference_response

    test_file = tmp_path / "test.jpg"
    test_file.write_bytes(b"fake image data")

    service.upload_temp_media(
        file_path=str(test_file),
        attribution="Photo by Test User",
    )

    call_args = mock_media_set.upload_media.call_args
    assert call_args[1]["attribution"] == "Photo by Test User"


def test_upload_temp_media_file_not_found(mock_mediasets_service):
    """Test temporary upload with non-existent file."""
    service, mock_media_set = mock_mediasets_service

    with pytest.raises(RuntimeError) as exc_info:
        service.upload_temp_media(file_path="/nonexistent/file.jpg")

    assert "Failed to upload temporary media" in str(exc_info.value)


def test_upload_temp_media_default_filename(
    mock_mediasets_service, tmp_path, sample_media_reference_response
):
    """Test that upload uses file basename as default filename."""
    service, mock_media_set = mock_mediasets_service
    mock_media_set.upload_media.return_value = sample_media_reference_response

    test_file = tmp_path / "my-image.jpg"
    test_file.write_bytes(b"fake image data")

    service.upload_temp_media(file_path=str(test_file))

    call_args = mock_media_set.upload_media.call_args
    assert call_args[1]["filename"] == "my-image.jpg"


def test_upload_temp_media_error(mock_mediasets_service, tmp_path):
    """Test temporary upload error handling."""
    service, mock_media_set = mock_mediasets_service
    mock_media_set.upload_media.side_effect = Exception("API error")

    test_file = tmp_path / "test.jpg"
    test_file.write_bytes(b"fake image data")

    with pytest.raises(RuntimeError) as exc_info:
        service.upload_temp_media(file_path=str(test_file))

    assert "Failed to upload temporary media" in str(exc_info.value)


# _write_response_to_file helper tests
def test_write_response_to_file_with_content(mock_mediasets_service, tmp_path):
    """Test helper method with response.content attribute."""
    service, _ = mock_mediasets_service

    mock_response = Mock()
    mock_response.content = b"test content"

    output_file = tmp_path / "output.bin"
    file_size = service._write_response_to_file(mock_response, output_file)

    assert file_size == len(b"test content")
    assert output_file.read_bytes() == b"test content"


def test_write_response_to_file_streaming(mock_mediasets_service, tmp_path):
    """Test helper method with streaming response."""
    service, _ = mock_mediasets_service

    mock_response = MagicMock()
    del mock_response.content  # Remove content attribute to trigger streaming path
    mock_response.__iter__.return_value = iter([b"chunk1", b"chunk2", b"chunk3"])

    output_file = tmp_path / "output.bin"
    file_size = service._write_response_to_file(mock_response, output_file)

    assert file_size == len(b"chunk1chunk2chunk3")
    assert output_file.read_bytes() == b"chunk1chunk2chunk3"


# _format_thumbnail_status tests
def test_format_thumbnail_status(mock_mediasets_service, sample_thumbnail_response):
    """Test thumbnail status formatting."""
    service, _ = mock_mediasets_service

    result = service._format_thumbnail_status(sample_thumbnail_response)

    assert result["status"] == "COMPLETED"
    assert result["transformation_id"] == "transform-12345"
    assert result["media_item_rid"] == "ri.mediasets.main.media-item.test"


def test_format_thumbnail_status_missing_attrs(mock_mediasets_service):
    """Test thumbnail status formatting with missing attributes."""
    service, _ = mock_mediasets_service

    # Response with no attributes
    mock_response = Mock(spec=[])

    result = service._format_thumbnail_status(mock_response)

    assert result["status"] == "unknown"
    assert result["transformation_id"] is None
    assert result["media_item_rid"] is None
