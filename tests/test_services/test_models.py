"""Tests for Models service."""

import pytest
from unittest.mock import Mock, patch
from pltr.services.models import ModelsService


class TestModelsService:
    """Test Models service functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.models = Mock()
        client.models.Model = Mock()
        client.models.ModelVersion = Mock()
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create ModelsService with mocked client."""
        with patch("pltr.services.base.AuthManager") as mock_auth:
            mock_auth.return_value.get_client.return_value = mock_client
            service = ModelsService()
            return service

    # ===== Model Creation Tests =====

    def test_create_model(self, service, mock_client):
        """Test creating a model."""
        # Setup
        name = "fraud-detector"
        parent_folder_rid = "ri.compass.main.folder.123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": "ri.foundry.main.model.abc123",
            "name": name,
            "parentFolderRid": parent_folder_rid,
        }
        mock_client.models.Model.create.return_value = mock_response

        # Execute
        result = service.create_model(name=name, parent_folder_rid=parent_folder_rid)

        # Assert
        mock_client.models.Model.create.assert_called_once_with(
            name=name,
            parent_folder_rid=parent_folder_rid,
            preview=False,
        )
        assert result["name"] == name
        assert result["rid"] == "ri.foundry.main.model.abc123"
        assert result["parentFolderRid"] == parent_folder_rid

    def test_create_model_with_preview(self, service, mock_client):
        """Test creating a model with preview mode."""
        # Setup
        name = "test-model"
        parent_folder_rid = "ri.compass.main.folder.123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": "ri.foundry.main.model.abc123",
            "name": name,
        }
        mock_client.models.Model.create.return_value = mock_response

        # Execute
        service.create_model(
            name=name,
            parent_folder_rid=parent_folder_rid,
            preview=True,
        )

        # Assert
        mock_client.models.Model.create.assert_called_once_with(
            name=name,
            parent_folder_rid=parent_folder_rid,
            preview=True,
        )

    def test_create_model_error(self, service, mock_client):
        """Test error handling in create_model."""
        # Setup
        mock_client.models.Model.create.side_effect = Exception("Permission denied")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to create model"):
            service.create_model(
                name="test",
                parent_folder_rid="ri.compass.main.folder.123",
            )

    # ===== Get Model Tests =====

    def test_get_model(self, service, mock_client):
        """Test getting model information."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "rid": model_rid,
            "name": "fraud-detector",
            "parentFolderRid": "ri.compass.main.folder.123",
        }
        mock_client.models.Model.get.return_value = mock_response

        # Execute
        result = service.get_model(model_rid=model_rid)

        # Assert
        mock_client.models.Model.get.assert_called_once_with(
            model_rid=model_rid, preview=False
        )
        assert result["rid"] == model_rid
        assert "name" in result

    def test_get_model_with_preview(self, service, mock_client):
        """Test getting model with preview mode."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        mock_response = Mock()
        mock_response.dict.return_value = {"rid": model_rid}
        mock_client.models.Model.get.return_value = mock_response

        # Execute
        service.get_model(model_rid=model_rid, preview=True)

        # Assert
        mock_client.models.Model.get.assert_called_once_with(
            model_rid=model_rid, preview=True
        )

    def test_get_model_error(self, service, mock_client):
        """Test error handling in get_model."""
        # Setup
        mock_client.models.Model.get.side_effect = Exception("Model not found")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to get model"):
            service.get_model(model_rid="ri.foundry.main.model.abc123")

    # ===== Get Model Version Tests =====

    def test_get_model_version(self, service, mock_client):
        """Test getting model version information."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        version_rid = "v1.0.0"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "modelRid": model_rid,
            "versionRid": version_rid,
            "createdTime": "2024-01-01T00:00:00Z",
        }
        mock_client.models.ModelVersion.get.return_value = mock_response

        # Execute
        result = service.get_model_version(
            model_rid=model_rid, model_version_rid=version_rid
        )

        # Assert
        mock_client.models.ModelVersion.get.assert_called_once_with(
            model_rid=model_rid,
            model_version_rid=version_rid,
            preview=False,
        )
        assert result["modelRid"] == model_rid
        assert result["versionRid"] == version_rid

    def test_get_model_version_with_preview(self, service, mock_client):
        """Test getting model version with preview mode."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        version_rid = "v1.0.0"
        mock_response = Mock()
        mock_response.dict.return_value = {"versionRid": version_rid}
        mock_client.models.ModelVersion.get.return_value = mock_response

        # Execute
        service.get_model_version(
            model_rid=model_rid,
            model_version_rid=version_rid,
            preview=True,
        )

        # Assert
        mock_client.models.ModelVersion.get.assert_called_once_with(
            model_rid=model_rid,
            model_version_rid=version_rid,
            preview=True,
        )

    def test_get_model_version_error(self, service, mock_client):
        """Test error handling in get_model_version."""
        # Setup
        mock_client.models.ModelVersion.get.side_effect = Exception("Version not found")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to get model version"):
            service.get_model_version(
                model_rid="ri.foundry.main.model.abc123",
                model_version_rid="v1.0.0",
            )

    # ===== List Model Versions Tests =====

    def test_list_model_versions(self, service, mock_client):
        """Test listing model versions."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [
                {"versionRid": "v1.0.0"},
                {"versionRid": "v1.1.0"},
            ],
            "nextPageToken": None,
        }
        mock_client.models.ModelVersion.list.return_value = mock_response

        # Execute
        result = service.list_model_versions(model_rid=model_rid)

        # Assert
        mock_client.models.ModelVersion.list.assert_called_once_with(
            model_rid=model_rid,
            page_size=None,
            page_token=None,
            preview=False,
        )
        assert len(result["data"]) == 2
        assert result["nextPageToken"] is None

    def test_list_model_versions_with_pagination(self, service, mock_client):
        """Test listing model versions with pagination."""
        # Setup
        model_rid = "ri.foundry.main.model.abc123"
        page_size = 50
        page_token = "token123"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [{"versionRid": "v1.0.0"}],
            "nextPageToken": "token456",
        }
        mock_client.models.ModelVersion.list.return_value = mock_response

        # Execute
        result = service.list_model_versions(
            model_rid=model_rid,
            page_size=page_size,
            page_token=page_token,
            preview=True,
        )

        # Assert
        mock_client.models.ModelVersion.list.assert_called_once_with(
            model_rid=model_rid,
            page_size=page_size,
            page_token=page_token,
            preview=True,
        )
        assert "data" in result
        assert result["nextPageToken"] == "token456"

    def test_list_model_versions_error(self, service, mock_client):
        """Test error handling in list_model_versions."""
        # Setup
        mock_client.models.ModelVersion.list.side_effect = Exception("List failed")

        # Execute & Assert
        with pytest.raises(RuntimeError, match="Failed to list model versions"):
            service.list_model_versions(model_rid="ri.foundry.main.model.abc123")
