"""Tests for CopyService."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pltr.services.copy import CopyService


def _setup_service_mocks():
    """Patch dependent services and return their mocks."""
    dataset_patch = patch("pltr.services.copy.DatasetService")
    folder_patch = patch("pltr.services.copy.FolderService")
    resource_patch = patch("pltr.services.copy.ResourceService")
    return dataset_patch, folder_patch, resource_patch


def test_copy_dataset_dry_run_skips_creation():
    """Dry runs should not call dataset creation but should report stats."""
    dataset_patch, folder_patch, resource_patch = _setup_service_mocks()
    with (
        dataset_patch as MockDatasetService,
        folder_patch,
        resource_patch as MockResourceService,
    ):
        dataset_instance = MockDatasetService.return_value
        resource_instance = MockResourceService.return_value
        resource_instance.get_resource.return_value = {
            "rid": "ri.foundry.main.dataset.source",
            "display_name": "Source Dataset",
            "type": "FOUNDRY_DATASET",
        }

        console = Mock()
        service = CopyService(dry_run=True, console=console)
        summary = service.copy_resource(
            "ri.foundry.main.dataset.source", "ri.compass.main.folder.dest"
        )

        dataset_instance.create_dataset.assert_not_called()
        assert summary["datasets_copied"] == 1
        assert summary["folders_copied"] == 0


def test_copy_dataset_copies_files_and_schema():
    """Copying a dataset should duplicate schema and files."""
    dataset_patch, folder_patch, resource_patch = _setup_service_mocks()
    with (
        dataset_patch as MockDatasetService,
        folder_patch,
        resource_patch as MockResourceService,
        patch.object(CopyService, "_upload_dataset_file") as mock_upload,
    ):
        dataset_instance = MockDatasetService.return_value
        resource_instance = MockResourceService.return_value

        resource_instance.get_resource.return_value = {
            "rid": "ri.foundry.main.dataset.source",
            "display_name": "Source Dataset",
            "type": "FOUNDRY_DATASET",
        }
        dataset_instance.create_dataset.return_value = {
            "rid": "ri.foundry.main.dataset.new"
        }
        dataset_instance.get_schema.return_value = {"schema": {"fields": []}}
        dataset_instance.list_files.return_value = [{"path": "/foo/bar.csv"}]
        dataset_instance.create_transaction.return_value = {
            "transaction_rid": "ri.foundry.main.transaction.txn"
        }
        dataset_instance.service = Mock()
        dataset_instance.download_file = Mock()

        console = Mock()
        service = CopyService(console=console)
        summary = service.copy_resource(
            "ri.foundry.main.dataset.source", "ri.compass.main.folder.dest"
        )

        dataset_instance.create_dataset.assert_called_once_with(
            "Source Dataset-copy", "ri.compass.main.folder.dest"
        )
        dataset_instance.put_schema.assert_called_once_with(
            "ri.foundry.main.dataset.new", {"fields": []}
        )
        dataset_instance.list_files.assert_called_once_with(
            "ri.foundry.main.dataset.source", branch="master"
        )
        dataset_instance.create_transaction.assert_called_once_with(
            "ri.foundry.main.dataset.new", branch="master", transaction_type="SNAPSHOT"
        )
        dataset_instance.download_file.assert_called_once()
        mock_upload.assert_called_once()
        dataset_instance.commit_transaction.assert_called_once_with(
            "ri.foundry.main.dataset.new", "ri.foundry.main.transaction.txn"
        )
        assert summary["datasets_copied"] == 1
        assert summary["errors"] == 0


def test_copy_folder_requires_recursive_flag():
    """Copying a folder without --recursive should error."""
    dataset_patch, folder_patch, resource_patch = _setup_service_mocks()
    with dataset_patch, folder_patch, resource_patch as MockResourceService:
        resource_instance = MockResourceService.return_value
        resource_instance.get_resource.return_value = {
            "rid": "ri.compass.main.folder.source",
            "display_name": "Source Folder",
            "type": "FOLDER",
        }

        service = CopyService(console=Mock())
        with pytest.raises(RuntimeError, match="--recursive"):
            service.copy_resource(
                "ri.compass.main.folder.source",
                "ri.compass.main.folder.dest",
                recursive=False,
            )


def test_upload_dataset_file_normalizes_remote_path(tmp_path: Path):
    """Uploading files should strip the leading slash from dataset paths."""
    service = CopyService.__new__(CopyService)
    service.branch = "master"
    service.dataset_service = Mock()
    service.dataset_service.service = Mock()
    service.dataset_service.service.Dataset = Mock()
    service.dataset_service.service.Dataset.File = Mock()

    local_file = tmp_path / "foo" / "bar.csv"
    local_file.parent.mkdir(parents=True)
    local_file.write_bytes(b"data")

    service._upload_dataset_file(
        "ri.foundry.main.dataset.dest", "/foo/bar.csv", local_file, "txn"
    )

    upload_kwargs = service.dataset_service.service.Dataset.File.upload.call_args.kwargs
    assert upload_kwargs["file_path"] == "foo/bar.csv"
    assert "branch_name" not in upload_kwargs


def test_upload_dataset_file_adds_branch_when_no_transaction(tmp_path: Path):
    """Uploads without a transaction should include branch parameter."""
    service = CopyService.__new__(CopyService)
    service.branch = "feature"
    service.dataset_service = Mock()
    service.dataset_service.service = Mock()
    service.dataset_service.service.Dataset = Mock()
    service.dataset_service.service.Dataset.File = Mock()

    local_file = tmp_path / "baz.csv"
    local_file.write_bytes(b"hello")

    service._upload_dataset_file(
        "ri.foundry.main.dataset.dest", "/baz.csv", local_file, None
    )

    upload_kwargs = service.dataset_service.service.Dataset.File.upload.call_args.kwargs
    assert upload_kwargs["branch_name"] == "feature"
