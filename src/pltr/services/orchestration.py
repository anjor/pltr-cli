"""
Orchestration service wrapper for the Foundry SDK (builds, jobs and schedules).

``Build.search``, ``Job.get``, ``Job.get_batch``, ``Schedule.get``,
``Schedule.create`` and ``Schedule.replace`` are beta endpoints and are always
called with ``preview=True``; the other methods are GA. Methods return SDK
models (or SDK iterators) unchanged and let SDK exceptions propagate so the
error layer can classify them.
"""

from typing import Any, Dict, List, Optional

from .base import BaseService

#: Maximum number of builds ``Build.get_batch`` accepts in one request.
MAX_BUILDS_BATCH = 100

#: Maximum number of jobs ``Job.get_batch`` accepts in one request.
MAX_JOBS_BATCH = 500


class OrchestrationService(BaseService):
    """Service wrapper for Foundry orchestration (``client.orchestration``)."""

    def _get_service(self) -> Any:
        """Get the Foundry orchestration service."""
        return self.client.orchestration

    # ------------------------------------------------------------------ builds

    def get_build(self, build_rid: str) -> Any:
        """Get a build (``Build.get``, GA); returns a ``Build`` model."""
        return self.service.Build.get(build_rid)

    def create_build(
        self,
        *,
        target: Dict[str, Any],
        fallback_branches: List[str],
        branch_name: Optional[str] = None,
        force_build: Optional[bool] = None,
        abort_on_failure: Optional[bool] = None,
        notifications_enabled: Optional[bool] = None,
        retry_count: Optional[int] = None,
    ) -> Any:
        """Start a build (``Build.create``, GA); returns the new ``Build``.

        Args:
            target: The build target in the API's JSON shape, e.g.
                ``{"type": "manual", "targetRids": [...]}`` (``manual``,
                ``upstream`` or ``connecting``). The SDK validates it.
            fallback_branches: Branches to read inputs from when an input
                doesn't exist on ``branch_name`` (may be empty).
        """
        return self.service.Build.create(
            target=target,
            fallback_branches=fallback_branches,
            branch_name=branch_name,
            force_build=force_build,
            abort_on_failure=abort_on_failure,
            notifications_enabled=notifications_enabled,
            retry_count=retry_count,
        )

    def wait_for_build(
        self, build_rid: str, *, timeout: float, build: Any = None
    ) -> Any:
        """Poll ``Build.get`` (GA) until the build finishes; return it if it succeeded.

        Args:
            build: The build's latest state, if already known.

        Raises:
            WorkFailed: (exit 8) the build failed or was canceled; its
                ``parameters`` name the failed jobs (from ``Build.jobs``) and
                their outputs. The public API has no job error messages.
            WaitTimedOut: (exit 9) still running after ``timeout`` seconds.
        """
        from ..contract import WaitTimedOut, WorkFailed, to_jsonable
        from .waiting import wait_until

        def timed_out(latest: Any) -> Exception:
            return WaitTimedOut(
                f"Build {build_rid} is still running after {timeout:g} seconds.",
                hint="It keeps running: wait again, or cancel it.",
                suggested_command=f"pltr orchestration builds wait {build_rid}",
                parameters={"buildRid": build_rid, "status": "RUNNING"},
            )

        build = wait_until(
            lambda: self.get_build(build_rid),
            lambda b: b.status != "RUNNING",
            timeout=timeout,
            on_timeout=timed_out,
            current=build,
        )
        if build.status == "SUCCEEDED":
            return build
        try:
            failed = [
                job
                for job in self.service.Build.jobs(build_rid)
                if job.job_status == "FAILED"
            ]
        except Exception:
            failed = []  # only detail: the build's own status decides
        names = ", ".join(job.rid for job in failed)
        detail = f": {len(failed)} job(s) failed ({names})" if failed else ""
        raise WorkFailed(
            f"Build {build_rid} {str(build.status).lower()}{detail}.",
            hint=(
                "The API doesn't return job error messages: open the build in "
                "Foundry for the logs."
            ),
            suggested_command=f"pltr orchestration builds jobs {build_rid}",
            parameters={
                "buildRid": build_rid,
                "status": build.status,
                "failedJobs": [
                    {"rid": job.rid, "outputs": to_jsonable(job.outputs)}
                    for job in failed
                ],
            },
        )

    def wait_for_schedule_run(
        self, schedule_rid: str, run: Any, *, timeout: float
    ) -> Any:
        """Poll ``Schedule.runs`` (GA) until ``run`` has a result (#195).

        A run's ``result`` is empty while the service is still triggering the
        schedule.
        """
        from ..contract import WaitTimedOut
        from .waiting import wait_until

        def latest() -> Any:
            for candidate in self.service.Schedule.runs(schedule_rid, page_size=50):
                if candidate.rid == run.rid:
                    return candidate
            return run

        return wait_until(
            latest,
            lambda current: current.result is not None,
            timeout=timeout,
            on_timeout=lambda _: WaitTimedOut(
                f"Schedule run {run.rid} hasn't started anything after "
                f"{timeout:g} seconds.",
                suggested_command=f"pltr orchestration schedules runs {schedule_rid}",
                parameters={"scheduleRid": schedule_rid, "scheduleRunRid": run.rid},
            ),
            current=run,
        )

    def cancel_build(self, build_rid: str) -> None:
        """Request cancellation of a build's unfinished jobs (``Build.cancel``, GA)."""
        self.service.Build.cancel(build_rid)

    def get_build_jobs(
        self,
        build_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a build's jobs (``Build.jobs``, GA).

        Returns:
            The SDK ``ResourceIterator[Job]``; constructing it fetched one
            page (``.data``, ``.next_page_token``).
        """
        return self.service.Build.jobs(
            build_rid, page_size=page_size, page_token=page_token
        )

    def search_builds(
        self,
        *,
        where: Dict[str, Any],
        order_by: Optional[Dict[str, Any]] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """Search builds, one page (``Build.search``, beta).

        Args:
            where: A ``SearchBuildsFilter`` in the API's JSON shape, e.g.
                ``{"type": "eq", "field": "STATUS", "value": "FAILED"}``.
            order_by: A ``SearchBuildsOrderBy``, e.g.
                ``{"fields": [{"field": "STARTED_TIME", "direction": "DESC"}]}``.

        Returns:
            ``SearchBuildsResponse`` (``.data``, ``.next_page_token``).
        """
        return self.service.Build.search(
            where=where,
            order_by=order_by,
            page_size=page_size,
            page_token=page_token,
            preview=True,
        )

    def get_builds_batch(self, build_rids: List[str]) -> Any:
        """Get up to 100 builds in one request (``Build.get_batch``, GA).

        Returns:
            ``GetBuildsBatchResponse``; its ``data`` maps build RID to ``Build``.
        """
        if len(build_rids) > MAX_BUILDS_BATCH:
            raise ValueError(f"Maximum batch size is {MAX_BUILDS_BATCH} builds")
        from foundry_sdk.v2.orchestration.models import GetBuildsBatchRequestElement

        return self.service.Build.get_batch(
            body=[GetBuildsBatchRequestElement(build_rid=rid) for rid in build_rids]
        )

    # -------------------------------------------------------------------- jobs

    def get_job(self, job_rid: str) -> Any:
        """Get a job (``Job.get``, beta); returns a ``Job`` model."""
        return self.service.Job.get(job_rid, preview=True)

    def get_jobs_batch(self, job_rids: List[str]) -> Any:
        """Get up to 500 jobs in one request (``Job.get_batch``, beta).

        Returns:
            ``GetJobsBatchResponse``; its ``data`` maps job RID to ``Job``.
        """
        if len(job_rids) > MAX_JOBS_BATCH:
            raise ValueError(f"Maximum batch size is {MAX_JOBS_BATCH} jobs")
        from foundry_sdk.v2.orchestration.models import GetJobsBatchRequestElement

        return self.service.Job.get_batch(
            body=[GetJobsBatchRequestElement(job_rid=rid) for rid in job_rids],
            preview=True,
        )

    # --------------------------------------------------------------- schedules

    def get_schedule(self, schedule_rid: str) -> Any:
        """Get a schedule (``Schedule.get``, beta); returns a ``Schedule``."""
        return self.service.Schedule.get(schedule_rid, preview=True)

    def create_schedule(
        self,
        *,
        action: Dict[str, Any],
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        trigger: Optional[Dict[str, Any]] = None,
        scope_mode: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Create a schedule (``Schedule.create``, beta); returns the ``Schedule``.

        ``action``, ``trigger`` and ``scope_mode`` are in the API's JSON shape;
        the SDK validates them.
        """
        return self.service.Schedule.create(
            action=action,
            display_name=display_name,
            description=description,
            trigger=trigger,
            scope_mode=scope_mode,
            preview=True,
        )

    def replace_schedule(
        self,
        schedule_rid: str,
        *,
        action: Dict[str, Any],
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        trigger: Optional[Dict[str, Any]] = None,
        scope_mode: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Replace a schedule's definition (``Schedule.replace``, beta).

        This is a full replacement (HTTP PUT): only the fields passed here are
        sent. Returns the updated ``Schedule``.
        """
        return self.service.Schedule.replace(
            schedule_rid,
            action=action,
            display_name=display_name,
            description=description,
            trigger=trigger,
            scope_mode=scope_mode,
            preview=True,
        )

    def delete_schedule(self, schedule_rid: str) -> None:
        """Delete a schedule (``Schedule.delete``, GA)."""
        self.service.Schedule.delete(schedule_rid)

    def pause_schedule(self, schedule_rid: str) -> None:
        """Pause a schedule (``Schedule.pause``, GA)."""
        self.service.Schedule.pause(schedule_rid)

    def unpause_schedule(self, schedule_rid: str) -> None:
        """Unpause a schedule (``Schedule.unpause``, GA)."""
        self.service.Schedule.unpause(schedule_rid)

    def run_schedule(self, schedule_rid: str) -> Any:
        """Run a schedule now (``Schedule.run``, GA); returns the ``ScheduleRun``."""
        return self.service.Schedule.run(schedule_rid)

    def get_schedule_runs(
        self,
        schedule_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a schedule's most recent runs (``Schedule.runs``, GA).

        Returns:
            The SDK ``ResourceIterator[ScheduleRun]``; constructing it fetched
            one page (``.data``, ``.next_page_token``).
        """
        return self.service.Schedule.runs(
            schedule_rid, page_size=page_size, page_token=page_token
        )
