"""
Tests for dataset transaction management service methods.
"""

import pytest
from unittest.mock import Mock, patch

from pltr.services.dataset import DatasetService


@pytest.fixture
def mock_dataset_service():
    """Create a mocked DatasetService with transaction support."""
    with patch("pltr.services.base.AuthManager") as mock_auth:
        # Set up client mock
        mock_client = Mock()
        mock_datasets = Mock()
        mock_dataset_class = Mock()  # The Dataset class
        mock_transaction_class = Mock()  # The Transaction class
        mock_file_class = Mock()  # The File class
        mock_dataset_class.Transaction = mock_transaction_class
        mock_dataset_class.File = mock_file_class
        mock_datasets.Dataset = mock_dataset_class
        mock_client.datasets = mock_datasets
        mock_auth.return_value.get_client.return_value = mock_client

        # Create service
        service = DatasetService()
        return service, mock_dataset_class


@pytest.fixture
def sample_transaction():
    """Create sample transaction object."""
    transaction = Mock()
    transaction.rid = "ri.foundry.main.transaction.test-transaction"
    transaction.status = "OPEN"
    transaction.transaction_type = "APPEND"
    transaction.branch = "master"
    transaction.created_time = "2024-01-01T00:00:00Z"
    transaction.created_by = "user@example.com"
    transaction.committed_time = None
    transaction.aborted_time = None
    return transaction


def test_create_transaction_success(mock_dataset_service, sample_transaction):
    """Test successful transaction creation."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Dataset.Transaction.create method response
    mock_dataset_class.Transaction.create.return_value = sample_transaction

    result = service.create_transaction(
        dataset_rid="ri.foundry.main.dataset.test",
        branch="master",
        transaction_type="APPEND",
    )

    assert result["transaction_rid"] == "ri.foundry.main.transaction.test-transaction"
    assert result["dataset_rid"] == "ri.foundry.main.dataset.test"
    assert result["branch"] == "master"
    assert result["transaction_type"] == "APPEND"
    assert result["status"] == "OPEN"
    assert result["created_time"] == "2024-01-01T00:00:00Z"
    assert result["created_by"] == "user@example.com"

    mock_dataset_class.Transaction.create.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test",
        transaction_type="APPEND",
        branch_name="master",
    )


def test_create_transaction_with_different_types(
    mock_dataset_service, sample_transaction
):
    """Test transaction creation with different transaction types."""
    service, mock_dataset_class = mock_dataset_service

    # Test each transaction type
    for trans_type in ["APPEND", "UPDATE", "SNAPSHOT", "DELETE"]:
        sample_transaction.transaction_type = trans_type
        mock_dataset_class.Transaction.create.return_value = sample_transaction

        result = service.create_transaction(
            dataset_rid="ri.foundry.main.dataset.test",
            branch="master",
            transaction_type=trans_type,
        )

        assert result["transaction_type"] == trans_type


def test_create_transaction_error(mock_dataset_service):
    """Test transaction creation with error."""
    service, mock_dataset_class = mock_dataset_service

    # Mock error response
    mock_dataset_class.Transaction.create.side_effect = Exception("Creation failed")

    with pytest.raises(RuntimeError, match="Failed to create transaction"):
        service.create_transaction(
            dataset_rid="ri.foundry.main.dataset.test", branch="master"
        )


def test_commit_transaction_success(mock_dataset_service):
    """Test successful transaction commit."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Dataset.commit_transaction method (returns None on success)
    mock_dataset_class.Transaction.commit.return_value = None

    result = service.commit_transaction(
        dataset_rid="ri.foundry.main.dataset.test",
        transaction_rid="ri.foundry.main.transaction.test",
    )

    assert result["transaction_rid"] == "ri.foundry.main.transaction.test"
    assert result["dataset_rid"] == "ri.foundry.main.dataset.test"
    assert result["status"] == "COMMITTED"
    assert result["success"] is True

    mock_dataset_class.Transaction.commit.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test",
        transaction_rid="ri.foundry.main.transaction.test",
    )


def test_commit_transaction_error(mock_dataset_service):
    """Test transaction commit with error."""
    service, mock_dataset_class = mock_dataset_service

    # Mock error response
    mock_dataset_class.Transaction.commit.side_effect = Exception("Commit failed")

    with pytest.raises(RuntimeError, match="Failed to commit transaction"):
        service.commit_transaction(
            dataset_rid="ri.foundry.main.dataset.test",
            transaction_rid="ri.foundry.main.transaction.test",
        )


def test_abort_transaction_success(mock_dataset_service):
    """Test successful transaction abort."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Dataset.abort_transaction method (returns None on success)
    mock_dataset_class.Transaction.abort.return_value = None

    result = service.abort_transaction(
        dataset_rid="ri.foundry.main.dataset.test",
        transaction_rid="ri.foundry.main.transaction.test",
    )

    assert result["transaction_rid"] == "ri.foundry.main.transaction.test"
    assert result["dataset_rid"] == "ri.foundry.main.dataset.test"
    assert result["status"] == "ABORTED"
    assert result["success"] is True

    mock_dataset_class.Transaction.abort.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test",
        transaction_rid="ri.foundry.main.transaction.test",
    )


def test_abort_transaction_error(mock_dataset_service):
    """Test transaction abort with error."""
    service, mock_dataset_class = mock_dataset_service

    # Mock error response
    mock_dataset_class.Transaction.abort.side_effect = Exception("Abort failed")

    with pytest.raises(RuntimeError, match="Failed to abort transaction"):
        service.abort_transaction(
            dataset_rid="ri.foundry.main.dataset.test",
            transaction_rid="ri.foundry.main.transaction.test",
        )


def test_get_transaction_status_success(mock_dataset_service, sample_transaction):
    """Test successful transaction status retrieval."""
    service, mock_dataset_class = mock_dataset_service

    # Mock the Dataset.get_transaction method response
    mock_dataset_class.Transaction.get.return_value = sample_transaction

    result = service.get_transaction_status(
        dataset_rid="ri.foundry.main.dataset.test",
        transaction_rid="ri.foundry.main.transaction.test",
    )

    assert result["transaction_rid"] == "ri.foundry.main.transaction.test"
    assert result["dataset_rid"] == "ri.foundry.main.dataset.test"
    assert result["status"] == "OPEN"
    assert result["transaction_type"] == "APPEND"
    assert result["branch"] == "master"
    assert result["created_time"] == "2024-01-01T00:00:00Z"
    assert result["created_by"] == "user@example.com"

    mock_dataset_class.Transaction.get.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test",
        transaction_rid="ri.foundry.main.transaction.test",
    )


def test_get_transaction_status_committed(mock_dataset_service):
    """Test transaction status for committed transaction."""
    service, mock_dataset_class = mock_dataset_service

    # Create committed transaction
    committed_transaction = Mock()
    committed_transaction.rid = "ri.foundry.main.transaction.committed"
    committed_transaction.status = "COMMITTED"
    committed_transaction.transaction_type = "UPDATE"
    committed_transaction.branch = "master"
    committed_transaction.created_time = "2024-01-01T00:00:00Z"
    committed_transaction.created_by = "user@example.com"
    committed_transaction.committed_time = "2024-01-01T00:10:00Z"
    committed_transaction.aborted_time = None

    mock_dataset_class.Transaction.get.return_value = committed_transaction

    result = service.get_transaction_status(
        dataset_rid="ri.foundry.main.dataset.test",
        transaction_rid="ri.foundry.main.transaction.committed",
    )

    assert result["status"] == "COMMITTED"
    assert result["committed_time"] == "2024-01-01T00:10:00Z"
    assert result["aborted_time"] is None


def test_get_transaction_status_error(mock_dataset_service):
    """Test transaction status retrieval with error."""
    service, mock_dataset_class = mock_dataset_service

    # Mock error response
    mock_dataset_class.Transaction.get.side_effect = Exception("Not found")

    with pytest.raises(RuntimeError, match="Failed to get transaction status"):
        service.get_transaction_status(
            dataset_rid="ri.foundry.main.dataset.test",
            transaction_rid="ri.foundry.main.transaction.test",
        )


def test_get_transactions_success(mock_dataset_service):
    """Test successful transaction list retrieval."""
    service, mock_dataset_class = mock_dataset_service

    # Create list of transactions
    transactions = []
    for i in range(3):
        trans = Mock()
        trans.rid = f"ri.foundry.main.transaction.test-{i}"
        trans.status = ["OPEN", "COMMITTED", "ABORTED"][i]
        trans.transaction_type = ["APPEND", "UPDATE", "DELETE"][i]
        trans.branch = "master"
        trans.created_time = f"2024-01-0{i + 1}T00:00:00Z"
        trans.created_by = f"user{i}@example.com"
        trans.committed_time = "2024-01-02T00:10:00Z" if i == 1 else None
        trans.aborted_time = "2024-01-03T00:10:00Z" if i == 2 else None
        transactions.append(trans)

    mock_dataset_class.Transaction.list.return_value = transactions

    result = service.get_transactions(
        dataset_rid="ri.foundry.main.dataset.test", branch="master"
    )

    assert len(result) == 3
    assert result[0]["transaction_rid"] == "ri.foundry.main.transaction.test-0"
    assert result[0]["status"] == "OPEN"
    assert result[1]["status"] == "COMMITTED"
    assert result[1]["committed_time"] == "2024-01-02T00:10:00Z"
    assert result[2]["status"] == "ABORTED"
    assert result[2]["aborted_time"] == "2024-01-03T00:10:00Z"

    mock_dataset_class.Transaction.list.assert_called_once_with(
        dataset_rid="ri.foundry.main.dataset.test", branch_name="master"
    )


def test_get_transactions_empty(mock_dataset_service):
    """Test transaction list retrieval with no transactions."""
    service, mock_dataset_class = mock_dataset_service

    # Mock empty response
    mock_dataset_class.Transaction.list.return_value = []

    result = service.get_transactions(
        dataset_rid="ri.foundry.main.dataset.test", branch="master"
    )

    assert result == []


def test_get_transactions_not_implemented(mock_dataset_service):
    """Test transaction list when method is not available."""
    service, mock_dataset_class = mock_dataset_service

    # Mock AttributeError to simulate method not available in Dataset class
    mock_dataset_class.Transaction.list.side_effect = AttributeError("Method not found")

    # Also mock the fallback service.list_transactions to raise AttributeError
    service.service.list_transactions.side_effect = AttributeError("Method not found")

    with pytest.raises(
        NotImplementedError, match="Transaction listing is not supported"
    ):
        service.get_transactions(
            dataset_rid="ri.foundry.main.dataset.test", branch="master"
        )


def test_upload_file_with_transaction(mock_dataset_service):
    """Test file upload with transaction."""
    service, mock_dataset_class = mock_dataset_service

    # Create a temporary test file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
        f.write("test,data\n1,2\n")
        temp_file = f.name

    try:
        # Mock the Dataset.File.upload method
        mock_dataset_class.File.upload = Mock(
            return_value=Mock(transaction_rid="ri.foundry.main.transaction.test")
        )

        result = service.upload_file(
            dataset_rid="ri.foundry.main.dataset.test",
            file_path=temp_file,
            branch="master",
            transaction_rid="ri.foundry.main.transaction.test",
        )

        assert result["dataset_rid"] == "ri.foundry.main.dataset.test"
        assert result["branch"] == "master"
        assert result["uploaded"] is True
        assert result["transaction_rid"] == "ri.foundry.main.transaction.test"

        mock_dataset_class.File.upload.assert_called_once()

    finally:
        # Clean up temp file
        import os

        os.unlink(temp_file)


def test_upload_file_without_transaction(mock_dataset_service):
    """Test file upload without transaction (auto-creates transaction)."""
    service, mock_dataset_class = mock_dataset_service

    # Create a temporary test file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
        f.write("test,data\n1,2\n")
        temp_file = f.name

    try:
        # Mock the Dataset.File.upload method
        mock_dataset_class.File.upload = Mock(
            return_value=Mock(transaction_rid="ri.foundry.main.transaction.auto")
        )

        result = service.upload_file(
            dataset_rid="ri.foundry.main.dataset.test",
            file_path=temp_file,
            branch="master",
            transaction_rid=None,
        )

        assert result["dataset_rid"] == "ri.foundry.main.dataset.test"
        assert result["branch"] == "master"
        assert result["uploaded"] is True
        # Transaction RID should be set from the result
        assert "transaction_rid" in result

        mock_dataset_class.File.upload.assert_called_once()

    finally:
        # Clean up temp file
        import os

        os.unlink(temp_file)


def test_upload_file_not_found(mock_dataset_service):
    """Test file upload with non-existent file."""
    service, mock_dataset_class = mock_dataset_service

    with pytest.raises(FileNotFoundError, match="File not found"):
        service.upload_file(
            dataset_rid="ri.foundry.main.dataset.test",
            file_path="/nonexistent/file.csv",
            branch="master",
        )
