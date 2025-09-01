"""
Tests for orchestration CLI commands.
"""

import pytest
import json
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from pltr.commands.orchestration import app
from pltr.auth.base import ProfileNotFoundError, MissingCredentialsError

runner = CliRunner()


@pytest.fixture
def mock_orchestration_service():
    """Mock OrchestrationService for command tests."""
    with patch(
        "pltr.commands.orchestration.OrchestrationService"
    ) as mock_service_class:
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        yield mock_service


@pytest.fixture
def sample_build():
    """Sample build for testing."""
    return {
        "rid": "ri.orchestration.main.build.test",
        "status": "COMPLETED",
        "created_by": "user@example.com",
        "created_time": "2024-01-01T00:00:00Z",
        "started_time": "2024-01-01T00:01:00Z",
        "finished_time": "2024-01-01T00:10:00Z",
        "branch_name": "main",
        "commit_hash": "abc123",
    }


@pytest.fixture
def sample_job():
    """Sample job for testing."""
    return {
        "rid": "ri.orchestration.main.job.test",
        "status": "RUNNING",
        "job_type": "TRANSFORM",
        "build_rid": "ri.orchestration.main.build.test",
        "created_time": "2024-01-01T00:00:00Z",
        "started_time": "2024-01-01T00:01:00Z",
    }


@pytest.fixture
def sample_schedule():
    """Sample schedule for testing."""
    return {
        "rid": "ri.orchestration.main.schedule.test",
        "display_name": "Test Schedule",
        "description": "Test schedule description",
        "paused": False,
        "created_by": "user@example.com",
        "created_time": "2024-01-01T00:00:00Z",
        "modified_by": "user@example.com",
        "modified_time": "2024-01-02T00:00:00Z",
    }


# Build Command Tests
def test_get_build_success(mock_orchestration_service, sample_build):
    """Test successful build retrieval."""
    mock_orchestration_service.get_build.return_value = sample_build

    result = runner.invoke(app, ["builds", "get", "ri.orchestration.main.build.test"])

    assert result.exit_code == 0
    mock_orchestration_service.get_build.assert_called_once_with(
        "ri.orchestration.main.build.test"
    )


def test_get_build_with_format(mock_orchestration_service, sample_build):
    """Test build retrieval with different formats."""
    mock_orchestration_service.get_build.return_value = sample_build

    # Test JSON format
    result = runner.invoke(
        app, ["builds", "get", "ri.orchestration.main.build.test", "--format", "json"]
    )
    assert result.exit_code == 0

    # Test CSV format
    result = runner.invoke(
        app, ["builds", "get", "ri.orchestration.main.build.test", "--format", "csv"]
    )
    assert result.exit_code == 0


def test_get_build_with_profile(mock_orchestration_service, sample_build):
    """Test build retrieval with specific profile."""
    mock_orchestration_service.get_build.return_value = sample_build

    result = runner.invoke(
        app,
        [
            "builds",
            "get",
            "ri.orchestration.main.build.test",
            "--profile",
            "test-profile",
        ],
    )

    assert result.exit_code == 0


def test_get_build_auth_error(mock_orchestration_service):
    """Test build retrieval with authentication error."""
    mock_orchestration_service.get_build.side_effect = ProfileNotFoundError(
        "Profile not found"
    )

    result = runner.invoke(app, ["builds", "get", "ri.orchestration.main.build.test"])

    assert result.exit_code == 1
    assert "Authentication error" in result.output


def test_create_build_success(mock_orchestration_service, sample_build):
    """Test successful build creation."""
    mock_orchestration_service.create_build.return_value = sample_build

    target = {"dataset_rid": "ri.foundry.main.dataset.test"}
    result = runner.invoke(
        app, ["builds", "create", json.dumps(target), "--branch", "feature", "--force"]
    )

    assert result.exit_code == 0
    assert "Successfully created build" in result.output

    # Check service was called with correct parameters
    mock_orchestration_service.create_build.assert_called_once()
    call_args = mock_orchestration_service.create_build.call_args[1]
    assert call_args["branch_name"] == "feature"
    assert call_args["force_build"] is True


def test_create_build_invalid_json(mock_orchestration_service):
    """Test build creation with invalid JSON."""
    result = runner.invoke(app, ["builds", "create", "invalid-json"])

    assert result.exit_code == 1
    assert "Invalid JSON format" in result.output


def test_cancel_build_success(mock_orchestration_service):
    """Test successful build cancellation."""
    result = runner.invoke(
        app, ["builds", "cancel", "ri.orchestration.main.build.test"]
    )

    assert result.exit_code == 0
    assert "Successfully cancelled build" in result.output
    mock_orchestration_service.cancel_build.assert_called_once_with(
        "ri.orchestration.main.build.test"
    )


def test_get_build_jobs_success(mock_orchestration_service, sample_job):
    """Test successful retrieval of build jobs."""
    mock_orchestration_service.get_build_jobs.return_value = {
        "jobs": [sample_job],
        "next_page_token": None,
    }

    result = runner.invoke(app, ["builds", "jobs", "ri.orchestration.main.build.test"])

    assert result.exit_code == 0
    mock_orchestration_service.get_build_jobs.assert_called_once()


def test_get_build_jobs_empty(mock_orchestration_service):
    """Test build jobs retrieval with no jobs."""
    mock_orchestration_service.get_build_jobs.return_value = {
        "jobs": [],
        "next_page_token": None,
    }

    result = runner.invoke(app, ["builds", "jobs", "ri.orchestration.main.build.test"])

    assert result.exit_code == 0
    assert "No jobs found" in result.output


def test_search_builds_success(mock_orchestration_service, sample_build):
    """Test successful build search."""
    mock_orchestration_service.search_builds.return_value = {
        "builds": [sample_build],
        "next_page_token": None,
    }

    result = runner.invoke(app, ["builds", "search"])

    assert result.exit_code == 0
    mock_orchestration_service.search_builds.assert_called_once()


# Job Command Tests
def test_get_job_success(mock_orchestration_service, sample_job):
    """Test successful job retrieval."""
    mock_orchestration_service.get_job.return_value = sample_job

    result = runner.invoke(app, ["jobs", "get", "ri.orchestration.main.job.test"])

    assert result.exit_code == 0
    mock_orchestration_service.get_job.assert_called_once_with(
        "ri.orchestration.main.job.test"
    )


def test_get_job_with_format(mock_orchestration_service, sample_job):
    """Test job retrieval with different formats."""
    mock_orchestration_service.get_job.return_value = sample_job

    result = runner.invoke(
        app, ["jobs", "get", "ri.orchestration.main.job.test", "--format", "json"]
    )

    assert result.exit_code == 0


def test_get_jobs_batch_success(mock_orchestration_service, sample_job):
    """Test successful batch job retrieval."""
    mock_orchestration_service.get_jobs_batch.return_value = {"jobs": [sample_job]}

    result = runner.invoke(app, ["jobs", "get-batch", "rid1,rid2,rid3"])

    assert result.exit_code == 0
    mock_orchestration_service.get_jobs_batch.assert_called_once()
    call_args = mock_orchestration_service.get_jobs_batch.call_args[0][0]
    assert len(call_args) == 3
    assert "rid1" in call_args


def test_get_jobs_batch_too_many(mock_orchestration_service):
    """Test batch job retrieval with too many RIDs."""
    # Create 501 RIDs
    rids = ",".join([f"rid{i}" for i in range(501)])

    result = runner.invoke(app, ["jobs", "get-batch", rids])

    assert result.exit_code == 1
    assert "Maximum batch size is 500" in result.output


# Schedule Command Tests
def test_get_schedule_success(mock_orchestration_service, sample_schedule):
    """Test successful schedule retrieval."""
    mock_orchestration_service.get_schedule.return_value = sample_schedule

    result = runner.invoke(
        app, ["schedules", "get", "ri.orchestration.main.schedule.test"]
    )

    assert result.exit_code == 0
    mock_orchestration_service.get_schedule.assert_called_once()


def test_get_schedule_with_preview(mock_orchestration_service, sample_schedule):
    """Test schedule retrieval with preview mode."""
    mock_orchestration_service.get_schedule.return_value = sample_schedule

    result = runner.invoke(
        app, ["schedules", "get", "ri.orchestration.main.schedule.test", "--preview"]
    )

    assert result.exit_code == 0
    call_args = mock_orchestration_service.get_schedule.call_args[1]
    assert call_args["preview"] is True


def test_create_schedule_success(mock_orchestration_service, sample_schedule):
    """Test successful schedule creation."""
    mock_orchestration_service.create_schedule.return_value = sample_schedule

    action = {"type": "BUILD", "target": "dataset-rid"}
    result = runner.invoke(
        app,
        [
            "schedules",
            "create",
            json.dumps(action),
            "--name",
            "Test Schedule",
            "--description",
            "Test description",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully created schedule" in result.output

    # Check service was called with correct parameters
    mock_orchestration_service.create_schedule.assert_called_once()
    call_args = mock_orchestration_service.create_schedule.call_args[1]
    assert call_args["display_name"] == "Test Schedule"
    assert call_args["description"] == "Test description"


def test_create_schedule_with_trigger(mock_orchestration_service, sample_schedule):
    """Test schedule creation with trigger."""
    mock_orchestration_service.create_schedule.return_value = sample_schedule

    action = {"type": "BUILD", "target": "dataset-rid"}
    trigger = {"type": "CRON", "expression": "0 0 * * *"}

    result = runner.invoke(
        app,
        ["schedules", "create", json.dumps(action), "--trigger", json.dumps(trigger)],
    )

    assert result.exit_code == 0

    # Check trigger was parsed and passed
    call_args = mock_orchestration_service.create_schedule.call_args[1]
    assert call_args["trigger"] == trigger


def test_create_schedule_invalid_json(mock_orchestration_service):
    """Test schedule creation with invalid JSON."""
    result = runner.invoke(app, ["schedules", "create", "invalid-json"])

    assert result.exit_code == 1
    assert "Invalid JSON format" in result.output


def test_delete_schedule_with_confirmation(mock_orchestration_service):
    """Test schedule deletion with confirmation."""
    # Use --yes flag to skip confirmation
    result = runner.invoke(
        app, ["schedules", "delete", "ri.orchestration.main.schedule.test", "--yes"]
    )

    assert result.exit_code == 0
    assert "Successfully deleted schedule" in result.output
    mock_orchestration_service.delete_schedule.assert_called_once_with(
        "ri.orchestration.main.schedule.test"
    )


def test_delete_schedule_without_confirmation(mock_orchestration_service):
    """Test schedule deletion without confirmation (should abort)."""
    result = runner.invoke(
        app,
        ["schedules", "delete", "ri.orchestration.main.schedule.test"],
        input="n\n",  # Say no to confirmation
    )

    assert result.exit_code == 1
    mock_orchestration_service.delete_schedule.assert_not_called()


def test_pause_schedule_success(mock_orchestration_service):
    """Test successful schedule pausing."""
    result = runner.invoke(
        app, ["schedules", "pause", "ri.orchestration.main.schedule.test"]
    )

    assert result.exit_code == 0
    assert "Successfully paused schedule" in result.output
    mock_orchestration_service.pause_schedule.assert_called_once_with(
        "ri.orchestration.main.schedule.test"
    )


def test_unpause_schedule_success(mock_orchestration_service):
    """Test successful schedule unpausing."""
    result = runner.invoke(
        app, ["schedules", "unpause", "ri.orchestration.main.schedule.test"]
    )

    assert result.exit_code == 0
    assert "Successfully unpaused schedule" in result.output
    mock_orchestration_service.unpause_schedule.assert_called_once_with(
        "ri.orchestration.main.schedule.test"
    )


def test_run_schedule_success(mock_orchestration_service):
    """Test successful schedule execution."""
    result = runner.invoke(
        app, ["schedules", "run", "ri.orchestration.main.schedule.test"]
    )

    assert result.exit_code == 0
    assert "Successfully triggered schedule" in result.output
    mock_orchestration_service.run_schedule.assert_called_once_with(
        "ri.orchestration.main.schedule.test"
    )


def test_replace_schedule_success(mock_orchestration_service, sample_schedule):
    """Test successful schedule replacement."""
    mock_orchestration_service.replace_schedule.return_value = sample_schedule

    action = {"type": "BUILD", "target": "new-dataset-rid"}
    result = runner.invoke(
        app,
        [
            "schedules",
            "replace",
            "ri.orchestration.main.schedule.test",
            json.dumps(action),
            "--name",
            "Updated Schedule",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully replaced schedule" in result.output

    # Check service was called with correct parameters
    mock_orchestration_service.replace_schedule.assert_called_once()
    call_args = mock_orchestration_service.replace_schedule.call_args[1]
    assert call_args["schedule_rid"] == "ri.orchestration.main.schedule.test"
    assert call_args["display_name"] == "Updated Schedule"


# Error handling tests
def test_command_generic_error(mock_orchestration_service):
    """Test generic error handling in commands."""
    mock_orchestration_service.get_build.side_effect = Exception("Unexpected error")

    result = runner.invoke(app, ["builds", "get", "ri.orchestration.main.build.test"])

    assert result.exit_code == 1
    assert "Failed to get build" in result.output


def test_command_auth_missing_credentials(mock_orchestration_service):
    """Test handling of missing credentials error."""
    mock_orchestration_service.get_job.side_effect = MissingCredentialsError(
        "Missing credentials"
    )

    result = runner.invoke(app, ["jobs", "get", "ri.orchestration.main.job.test"])

    assert result.exit_code == 1
    assert "Authentication error" in result.output
