"""
Orchestration service wrapper for Foundry SDK v2 API.
Provides operations for managing builds, jobs, and schedules.
"""

from typing import Any, Optional, Dict, List

from .base import BaseService


class OrchestrationService(BaseService):
    """Service wrapper for Foundry orchestration operations using v2 API."""

    def _get_service(self) -> Any:
        """Get the Foundry orchestration service."""
        return self.client.orchestration

    # Build operations
    def get_build(self, build_rid: str) -> Dict[str, Any]:
        """
        Get information about a specific build.

        Args:
            build_rid: Build Resource Identifier

        Returns:
            Build information dictionary
        """
        try:
            build = self.service.Build.get(build_rid)
            return self._format_build_info(build)
        except Exception as e:
            raise RuntimeError(f"Failed to get build {build_rid}: {e}")

    def create_build(
        self,
        target: Dict[str, Any],
        fallback_branches: Optional[Dict[str, Any]] = None,
        abort_on_failure: Optional[bool] = None,
        branch_name: Optional[str] = None,
        force_build: Optional[bool] = None,
        notifications_enabled: Optional[bool] = None,
        retry_backoff_duration: Optional[int] = None,
        retry_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a new build.

        Args:
            target: Build target configuration
            fallback_branches: Fallback branches configuration
            abort_on_failure: Whether to abort on failure
            branch_name: Branch name for the build
            force_build: Force build even if no changes
            notifications_enabled: Enable notifications
            retry_backoff_duration: Retry backoff duration in milliseconds
            retry_count: Number of retries

        Returns:
            Created build information
        """
        try:
            kwargs: Dict[str, Any] = {
                "target": target,
                "fallback_branches": fallback_branches or [],
            }

            # Add optional parameters if provided
            if abort_on_failure is not None:
                kwargs["abort_on_failure"] = abort_on_failure
            if branch_name is not None:
                kwargs["branch_name"] = branch_name
            if force_build is not None:
                kwargs["force_build"] = force_build
            if notifications_enabled is not None:
                kwargs["notifications_enabled"] = notifications_enabled
            if retry_backoff_duration is not None:
                kwargs["retry_backoff_duration"] = retry_backoff_duration
            if retry_count is not None:
                kwargs["retry_count"] = retry_count

            build = self.service.Build.create(**kwargs)
            return self._format_build_info(build)
        except Exception as e:
            raise RuntimeError(f"Failed to create build: {e}")

    def cancel_build(self, build_rid: str) -> None:
        """
        Cancel a build.

        Args:
            build_rid: Build Resource Identifier
        """
        try:
            self.service.Build.cancel(build_rid)
        except Exception as e:
            raise RuntimeError(f"Failed to cancel build {build_rid}: {e}")

    def get_build_jobs(
        self,
        build_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get jobs in a build.

        Args:
            build_rid: Build Resource Identifier
            page_size: Number of results per page
            page_token: Token for pagination

        Returns:
            Jobs list with pagination info
        """
        try:
            kwargs: Dict[str, Any] = {"build_rid": build_rid}
            if page_size is not None:
                kwargs["page_size"] = page_size
            if page_token is not None:
                kwargs["page_token"] = page_token

            response = self.service.Build.jobs(**kwargs)
            return self._format_jobs_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get jobs for build {build_rid}: {e}")

    def search_builds(
        self,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
        **search_params,
    ) -> Dict[str, Any]:
        """
        Search for builds.

        Args:
            page_size: Number of results per page
            page_token: Token for pagination
            **search_params: Additional search parameters

        Returns:
            Search results with pagination info
        """
        try:
            kwargs: Dict[str, Any] = {}
            if page_size is not None:
                kwargs["page_size"] = page_size
            if page_token is not None:
                kwargs["page_token"] = page_token
            kwargs.update(search_params)

            response = self.service.Build.search(**kwargs)
            return self._format_builds_search_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to search builds: {e}")

    # Job operations
    def get_job(self, job_rid: str) -> Dict[str, Any]:
        """
        Get information about a specific job.

        Args:
            job_rid: Job Resource Identifier

        Returns:
            Job information dictionary
        """
        try:
            job = self.service.Job.get(job_rid)
            return self._format_job_info(job)
        except Exception as e:
            raise RuntimeError(f"Failed to get job {job_rid}: {e}")

    def get_jobs_batch(self, job_rids: List[str]) -> Dict[str, Any]:
        """
        Get multiple jobs in batch.

        Args:
            job_rids: List of Job Resource Identifiers (max 500)

        Returns:
            Batch response with job information
        """
        try:
            if len(job_rids) > 500:
                raise ValueError("Maximum batch size is 500 jobs")

            body = [{"rid": rid} for rid in job_rids]
            response = self.service.Job.get_batch(body)
            return self._format_jobs_batch_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to get jobs batch: {e}")

    # Schedule operations
    def get_schedule(
        self, schedule_rid: str, preview: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Get information about a specific schedule.

        Args:
            schedule_rid: Schedule Resource Identifier
            preview: Enable preview mode

        Returns:
            Schedule information dictionary
        """
        try:
            kwargs: Dict[str, Any] = {"schedule_rid": schedule_rid}
            if preview is not None:
                kwargs["preview"] = preview

            schedule = self.service.Schedule.get(**kwargs)
            return self._format_schedule_info(schedule)
        except Exception as e:
            raise RuntimeError(f"Failed to get schedule {schedule_rid}: {e}")

    def create_schedule(
        self,
        action: Dict[str, Any],
        description: Optional[str] = None,
        display_name: Optional[str] = None,
        trigger: Optional[Dict[str, Any]] = None,
        scope_mode: Optional[str] = None,
        preview: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Create a new schedule.

        Args:
            action: Schedule action configuration
            description: Schedule description
            display_name: Display name for the schedule
            trigger: Trigger configuration
            scope_mode: Scope mode for the schedule
            preview: Enable preview mode

        Returns:
            Created schedule information
        """
        try:
            kwargs: Dict[str, Any] = {"action": action}

            if description is not None:
                kwargs["description"] = description
            if display_name is not None:
                kwargs["display_name"] = display_name
            if trigger is not None:
                kwargs["trigger"] = trigger
            if scope_mode is not None:
                kwargs["scope_mode"] = scope_mode
            if preview is not None:
                kwargs["preview"] = preview

            schedule = self.service.Schedule.create(**kwargs)
            return self._format_schedule_info(schedule)
        except Exception as e:
            raise RuntimeError(f"Failed to create schedule: {e}")

    def delete_schedule(self, schedule_rid: str) -> None:
        """
        Delete a schedule.

        Args:
            schedule_rid: Schedule Resource Identifier
        """
        try:
            self.service.Schedule.delete(schedule_rid)
        except Exception as e:
            raise RuntimeError(f"Failed to delete schedule {schedule_rid}: {e}")

    def pause_schedule(self, schedule_rid: str) -> None:
        """
        Pause a schedule.

        Args:
            schedule_rid: Schedule Resource Identifier
        """
        try:
            self.service.Schedule.pause(schedule_rid)
        except Exception as e:
            raise RuntimeError(f"Failed to pause schedule {schedule_rid}: {e}")

    def unpause_schedule(self, schedule_rid: str) -> None:
        """
        Unpause a schedule.

        Args:
            schedule_rid: Schedule Resource Identifier
        """
        try:
            self.service.Schedule.unpause(schedule_rid)
        except Exception as e:
            raise RuntimeError(f"Failed to unpause schedule {schedule_rid}: {e}")

    def run_schedule(self, schedule_rid: str) -> None:
        """
        Execute a schedule immediately.

        Args:
            schedule_rid: Schedule Resource Identifier
        """
        try:
            self.service.Schedule.run(schedule_rid)
        except Exception as e:
            raise RuntimeError(f"Failed to run schedule {schedule_rid}: {e}")

    def replace_schedule(
        self,
        schedule_rid: str,
        action: Dict[str, Any],
        description: Optional[str] = None,
        display_name: Optional[str] = None,
        trigger: Optional[Dict[str, Any]] = None,
        scope_mode: Optional[str] = None,
        preview: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Replace an existing schedule.

        Args:
            schedule_rid: Schedule Resource Identifier
            action: Schedule action configuration
            description: Schedule description
            display_name: Display name for the schedule
            trigger: Trigger configuration
            scope_mode: Scope mode for the schedule
            preview: Enable preview mode

        Returns:
            Updated schedule information
        """
        try:
            kwargs: Dict[str, Any] = {
                "schedule_rid": schedule_rid,
                "action": action,
            }

            if description is not None:
                kwargs["description"] = description
            if display_name is not None:
                kwargs["display_name"] = display_name
            if trigger is not None:
                kwargs["trigger"] = trigger
            if scope_mode is not None:
                kwargs["scope_mode"] = scope_mode
            if preview is not None:
                kwargs["preview"] = preview

            schedule = self.service.Schedule.replace(**kwargs)
            return self._format_schedule_info(schedule)
        except Exception as e:
            raise RuntimeError(f"Failed to replace schedule {schedule_rid}: {e}")

    # Formatting methods
    def _format_build_info(self, build: Any) -> Dict[str, Any]:
        """Format build information for consistent output."""
        info = {}

        # Extract available attributes
        for attr in [
            "rid",
            "status",
            "created_time",
            "started_time",
            "finished_time",
            "created_by",
            "branch_name",
            "commit_hash",
        ]:
            if hasattr(build, attr):
                info[attr] = getattr(build, attr)

        return info

    def _format_job_info(self, job: Any) -> Dict[str, Any]:
        """Format job information for consistent output."""
        info = {}

        # Extract available attributes
        for attr in [
            "rid",
            "status",
            "created_time",
            "started_time",
            "finished_time",
            "job_type",
            "build_rid",
        ]:
            if hasattr(job, attr):
                info[attr] = getattr(job, attr)

        return info

    def _format_schedule_info(self, schedule: Any) -> Dict[str, Any]:
        """Format schedule information for consistent output."""
        info = {}

        # Extract available attributes
        for attr in [
            "rid",
            "display_name",
            "description",
            "paused",
            "created_time",
            "created_by",
            "modified_time",
            "modified_by",
        ]:
            if hasattr(schedule, attr):
                info[attr] = getattr(schedule, attr)

        # Handle nested objects
        if hasattr(schedule, "trigger"):
            info["trigger"] = str(schedule.trigger)
        if hasattr(schedule, "action"):
            info["action"] = str(schedule.action)

        return info

    def _format_jobs_response(self, response: Any) -> Dict[str, Any]:
        """Format jobs list response."""
        result: Dict[str, Any] = {"jobs": []}

        if hasattr(response, "data"):
            result["jobs"] = [self._format_job_info(job) for job in response.data]

        if hasattr(response, "next_page_token"):
            result["next_page_token"] = response.next_page_token

        return result

    def _format_builds_search_response(self, response: Any) -> Dict[str, Any]:
        """Format builds search response."""
        result: Dict[str, Any] = {"builds": []}

        if hasattr(response, "data"):
            result["builds"] = [
                self._format_build_info(build) for build in response.data
            ]

        if hasattr(response, "next_page_token"):
            result["next_page_token"] = response.next_page_token

        return result

    def _format_jobs_batch_response(self, response: Any) -> Dict[str, Any]:
        """Format jobs batch response."""
        result: Dict[str, Any] = {"jobs": []}

        if hasattr(response, "data"):
            for item in response.data:
                if hasattr(item, "data"):
                    result["jobs"].append(self._format_job_info(item.data))

        return result
