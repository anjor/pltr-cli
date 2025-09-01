"""
Tests for orchestration service.
"""

import pytest
from unittest.mock import Mock, patch

from pltr.services.orchestration import OrchestrationService


@pytest.fixture
def mock_orchestration_service():
    """Create a mocked OrchestrationService."""
    with patch("pltr.services.base.AuthManager") as mock_auth:
        # Set up client mock
        mock_client = Mock()
        mock_orchestration = Mock()

        # Mock the Build, Job, and Schedule classes
        mock_build_class = Mock()
        mock_job_class = Mock()
        mock_schedule_class = Mock()

        mock_orchestration.Build = mock_build_class
        mock_orchestration.Job = mock_job_class
        mock_orchestration.Schedule = mock_schedule_class

        mock_client.orchestration = mock_orchestration
        mock_auth.return_value.get_client.return_value = mock_client

        # Create service
        service = OrchestrationService()
        return service, mock_build_class, mock_job_class, mock_schedule_class


@pytest.fixture
def sample_build():
    """Create sample build object."""
    build = Mock()
    build.rid = "ri.orchestration.main.build.test-build"
    build.status = "COMPLETED"
    build.created_time = "2024-01-01T00:00:00Z"
    build.started_time = "2024-01-01T00:01:00Z"
    build.finished_time = "2024-01-01T00:10:00Z"
    build.created_by = "user@example.com"
    build.branch_name = "main"
    build.commit_hash = "abc123"
    return build


@pytest.fixture
def sample_job():
    """Create sample job object."""
    job = Mock()
    job.rid = "ri.orchestration.main.job.test-job"
    job.status = "RUNNING"
    job.created_time = "2024-01-01T00:00:00Z"
    job.started_time = "2024-01-01T00:01:00Z"
    job.finished_time = None
    job.job_type = "TRANSFORM"
    job.build_rid = "ri.orchestration.main.build.test-build"
    return job


@pytest.fixture
def sample_schedule():
    """Create sample schedule object."""
    schedule = Mock()
    schedule.rid = "ri.orchestration.main.schedule.test-schedule"
    schedule.display_name = "Test Schedule"
    schedule.description = "Test schedule description"
    schedule.paused = False
    schedule.created_time = "2024-01-01T00:00:00Z"
    schedule.created_by = "user@example.com"
    schedule.modified_time = "2024-01-02T00:00:00Z"
    schedule.modified_by = "user@example.com"
    schedule.trigger = Mock()
    schedule.action = Mock()
    return schedule


def test_orchestration_service_initialization():
    """Test OrchestrationService initialization."""
    with patch("pltr.services.base.AuthManager"):
        service = OrchestrationService()
        assert service is not None


def test_orchestration_service_get_service(mock_orchestration_service):
    """Test getting the underlying orchestration service."""
    service, mock_build, mock_job, mock_schedule = mock_orchestration_service
    orchestration = service._get_service()
    assert orchestration.Build == mock_build
    assert orchestration.Job == mock_job
    assert orchestration.Schedule == mock_schedule


# Build tests
def test_get_build_success(mock_orchestration_service, sample_build):
    """Test successful build retrieval."""
    service, mock_build_class, _, _ = mock_orchestration_service

    mock_build_class.get.return_value = sample_build

    result = service.get_build("ri.orchestration.main.build.test-build")

    assert result["rid"] == "ri.orchestration.main.build.test-build"
    assert result["status"] == "COMPLETED"
    assert result["created_by"] == "user@example.com"
    assert result["branch_name"] == "main"
    mock_build_class.get.assert_called_once_with(
        "ri.orchestration.main.build.test-build"
    )


def test_get_build_error(mock_orchestration_service):
    """Test build retrieval with error."""
    service, mock_build_class, _, _ = mock_orchestration_service

    mock_build_class.get.side_effect = Exception("API Error")

    with pytest.raises(RuntimeError) as exc_info:
        service.get_build("ri.orchestration.main.build.test-build")

    assert "Failed to get build" in str(exc_info.value)


def test_create_build_success(mock_orchestration_service, sample_build):
    """Test successful build creation."""
    service, mock_build_class, _, _ = mock_orchestration_service

    mock_build_class.create.return_value = sample_build

    target = {"dataset_rid": "ri.foundry.main.dataset.test"}
    result = service.create_build(
        target=target, branch_name="feature-branch", force_build=True
    )

    assert result["rid"] == "ri.orchestration.main.build.test-build"
    assert result["status"] == "COMPLETED"

    # Check that create was called with correct arguments
    call_args = mock_build_class.create.call_args[1]
    assert call_args["target"] == target
    assert call_args["branch_name"] == "feature-branch"
    assert call_args["force_build"] is True


def test_cancel_build_success(mock_orchestration_service):
    """Test successful build cancellation."""
    service, mock_build_class, _, _ = mock_orchestration_service

    service.cancel_build("ri.orchestration.main.build.test-build")

    mock_build_class.cancel.assert_called_once_with(
        "ri.orchestration.main.build.test-build"
    )


def test_get_build_jobs_success(mock_orchestration_service, sample_job):
    """Test successful retrieval of build jobs."""
    service, mock_build_class, _, _ = mock_orchestration_service

    # Mock response with jobs
    mock_response = Mock()
    mock_response.data = [sample_job]
    mock_response.next_page_token = "next-token"
    mock_build_class.jobs.return_value = mock_response

    result = service.get_build_jobs(
        "ri.orchestration.main.build.test-build", page_size=10
    )

    assert len(result["jobs"]) == 1
    assert result["jobs"][0]["rid"] == "ri.orchestration.main.job.test-job"
    assert result["next_page_token"] == "next-token"

    mock_build_class.jobs.assert_called_once()


def test_search_builds_success(mock_orchestration_service, sample_build):
    """Test successful build search."""
    service, mock_build_class, _, _ = mock_orchestration_service

    # Mock response with builds
    mock_response = Mock()
    mock_response.data = [sample_build]
    mock_response.next_page_token = "next-token"
    mock_build_class.search.return_value = mock_response

    result = service.search_builds(page_size=10)

    assert len(result["builds"]) == 1
    assert result["builds"][0]["rid"] == "ri.orchestration.main.build.test-build"
    assert result["next_page_token"] == "next-token"


# Job tests
def test_get_job_success(mock_orchestration_service, sample_job):
    """Test successful job retrieval."""
    service, _, mock_job_class, _ = mock_orchestration_service

    mock_job_class.get.return_value = sample_job

    result = service.get_job("ri.orchestration.main.job.test-job")

    assert result["rid"] == "ri.orchestration.main.job.test-job"
    assert result["status"] == "RUNNING"
    assert result["job_type"] == "TRANSFORM"
    mock_job_class.get.assert_called_once_with("ri.orchestration.main.job.test-job")


def test_get_job_error(mock_orchestration_service):
    """Test job retrieval with error."""
    service, _, mock_job_class, _ = mock_orchestration_service

    mock_job_class.get.side_effect = Exception("API Error")

    with pytest.raises(RuntimeError) as exc_info:
        service.get_job("ri.orchestration.main.job.test-job")

    assert "Failed to get job" in str(exc_info.value)


def test_get_jobs_batch_success(mock_orchestration_service, sample_job):
    """Test successful batch job retrieval."""
    service, _, mock_job_class, _ = mock_orchestration_service

    # Mock batch response
    mock_response = Mock()
    mock_item = Mock()
    mock_item.data = sample_job
    mock_response.data = [mock_item]
    mock_job_class.get_batch.return_value = mock_response

    job_rids = ["rid1", "rid2"]
    result = service.get_jobs_batch(job_rids)

    assert len(result["jobs"]) == 1
    assert result["jobs"][0]["rid"] == "ri.orchestration.main.job.test-job"

    # Check that batch request was formatted correctly
    call_args = mock_job_class.get_batch.call_args[0][0]
    assert len(call_args) == 2
    assert call_args[0]["rid"] == "rid1"
    assert call_args[1]["rid"] == "rid2"


def test_get_jobs_batch_too_many(mock_orchestration_service):
    """Test batch job retrieval with too many jobs."""
    service, _, _, _ = mock_orchestration_service

    job_rids = ["rid" + str(i) for i in range(501)]  # 501 jobs

    with pytest.raises(RuntimeError) as exc_info:
        service.get_jobs_batch(job_rids)

    assert "Maximum batch size is 500" in str(exc_info.value)


# Schedule tests
def test_get_schedule_success(mock_orchestration_service, sample_schedule):
    """Test successful schedule retrieval."""
    service, _, _, mock_schedule_class = mock_orchestration_service

    mock_schedule_class.get.return_value = sample_schedule

    result = service.get_schedule("ri.orchestration.main.schedule.test-schedule")

    assert result["rid"] == "ri.orchestration.main.schedule.test-schedule"
    assert result["display_name"] == "Test Schedule"
    assert result["paused"] is False
    mock_schedule_class.get.assert_called_once()


def test_get_schedule_with_preview(mock_orchestration_service, sample_schedule):
    """Test schedule retrieval with preview mode."""
    service, _, _, mock_schedule_class = mock_orchestration_service

    mock_schedule_class.get.return_value = sample_schedule

    result = service.get_schedule(
        "ri.orchestration.main.schedule.test-schedule", preview=True
    )

    assert result["rid"] == "ri.orchestration.main.schedule.test-schedule"

    # Check preview parameter was passed
    call_args = mock_schedule_class.get.call_args[1]
    assert call_args["preview"] is True


def test_create_schedule_success(mock_orchestration_service, sample_schedule):
    """Test successful schedule creation."""
    service, _, _, mock_schedule_class = mock_orchestration_service

    mock_schedule_class.create.return_value = sample_schedule

    action = {"type": "BUILD", "target": "dataset-rid"}
    trigger = {"type": "CRON", "expression": "0 0 * * *"}

    result = service.create_schedule(
        action=action,
        display_name="Test Schedule",
        description="Test description",
        trigger=trigger,
    )

    assert result["rid"] == "ri.orchestration.main.schedule.test-schedule"
    assert result["display_name"] == "Test Schedule"

    # Check create parameters
    call_args = mock_schedule_class.create.call_args[1]
    assert call_args["action"] == action
    assert call_args["display_name"] == "Test Schedule"
    assert call_args["trigger"] == trigger


def test_delete_schedule_success(mock_orchestration_service):
    """Test successful schedule deletion."""
    service, _, _, mock_schedule_class = mock_orchestration_service

    service.delete_schedule("ri.orchestration.main.schedule.test-schedule")

    mock_schedule_class.delete.assert_called_once_with(
        "ri.orchestration.main.schedule.test-schedule"
    )


def test_pause_schedule_success(mock_orchestration_service):
    """Test successful schedule pausing."""
    service, _, _, mock_schedule_class = mock_orchestration_service

    service.pause_schedule("ri.orchestration.main.schedule.test-schedule")

    mock_schedule_class.pause.assert_called_once_with(
        "ri.orchestration.main.schedule.test-schedule"
    )


def test_unpause_schedule_success(mock_orchestration_service):
    """Test successful schedule unpausing."""
    service, _, _, mock_schedule_class = mock_orchestration_service

    service.unpause_schedule("ri.orchestration.main.schedule.test-schedule")

    mock_schedule_class.unpause.assert_called_once_with(
        "ri.orchestration.main.schedule.test-schedule"
    )


def test_run_schedule_success(mock_orchestration_service):
    """Test successful schedule execution."""
    service, _, _, mock_schedule_class = mock_orchestration_service

    service.run_schedule("ri.orchestration.main.schedule.test-schedule")

    mock_schedule_class.run.assert_called_once_with(
        "ri.orchestration.main.schedule.test-schedule"
    )


def test_replace_schedule_success(mock_orchestration_service, sample_schedule):
    """Test successful schedule replacement."""
    service, _, _, mock_schedule_class = mock_orchestration_service

    mock_schedule_class.replace.return_value = sample_schedule

    action = {"type": "BUILD", "target": "new-dataset-rid"}

    result = service.replace_schedule(
        schedule_rid="ri.orchestration.main.schedule.test-schedule",
        action=action,
        display_name="Updated Schedule",
    )

    assert result["rid"] == "ri.orchestration.main.schedule.test-schedule"

    # Check replace parameters
    call_args = mock_schedule_class.replace.call_args[1]
    assert call_args["schedule_rid"] == "ri.orchestration.main.schedule.test-schedule"
    assert call_args["action"] == action
    assert call_args["display_name"] == "Updated Schedule"


# Formatting method tests
def test_format_build_info(mock_orchestration_service, sample_build):
    """Test build info formatting."""
    service, _, _, _ = mock_orchestration_service

    result = service._format_build_info(sample_build)

    assert result["rid"] == "ri.orchestration.main.build.test-build"
    assert result["status"] == "COMPLETED"
    assert result["created_by"] == "user@example.com"
    assert result["branch_name"] == "main"
    assert result["commit_hash"] == "abc123"


def test_format_job_info(mock_orchestration_service, sample_job):
    """Test job info formatting."""
    service, _, _, _ = mock_orchestration_service

    result = service._format_job_info(sample_job)

    assert result["rid"] == "ri.orchestration.main.job.test-job"
    assert result["status"] == "RUNNING"
    assert result["job_type"] == "TRANSFORM"
    assert result["build_rid"] == "ri.orchestration.main.build.test-build"


def test_format_schedule_info(mock_orchestration_service, sample_schedule):
    """Test schedule info formatting."""
    service, _, _, _ = mock_orchestration_service

    result = service._format_schedule_info(sample_schedule)

    assert result["rid"] == "ri.orchestration.main.schedule.test-schedule"
    assert result["display_name"] == "Test Schedule"
    assert result["description"] == "Test schedule description"
    assert result["paused"] is False
    assert "trigger" in result
    assert "action" in result
