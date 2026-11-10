"""
Orchestration commands: builds, jobs and schedules (Foundry orchestration API).
"""

import shlex
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import click
import typer
from typing_extensions import Annotated

from ..contract import (
    AllPagesOption,
    Columns,
    FormatOption,
    MaxPagesOption,
    OutputOption,
    PageSizeOption,
    PageTokenOption,
    PreviewNoopOption,
    ProfileOption,
    WaitOption,
    WaitTimeoutOption,
    WorkFailed,
    YesOption,
    collect_pages,
    confirm_destructive,
    emit,
    info,
    load_json_input,
    pltr_command,
    resolve_json_paths,
    resource_option,
    spinner,
    success,
)
from ..contract.hints import note_started
from ..services.orchestration import (
    MAX_BUILDS_BATCH,
    MAX_JOBS_BATCH,
    OrchestrationService,
)
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()
builds_app = typer.Typer()
jobs_app = typer.Typer()
schedules_app = typer.Typer()


# ------------------------------------------------------------------ columns


def _join(values: List[str]) -> str:
    return ", ".join(values)


def _retry_backoff(build: Any) -> str:
    duration = build.retry_backoff_duration
    return f"{duration.value} {duration.unit}"


def _job_outputs(job: Any) -> str:
    """The dataset or media set RID written by each of a job's outputs."""
    rids = []
    for output in job.outputs:
        if output.type == "datasetJobOutput":
            rids.append(output.dataset_rid)
        elif output.type == "transactionalMediaSetJobOutput":
            rids.append(output.media_set_rid)
        else:  # an output kind added in a newer SDK
            rids.append(output.type)
    return _join(rids)


def _run_build(run: Any) -> Optional[str]:
    """The build a schedule run submitted, if it submitted one."""
    result = run.result
    if result is not None and result.type == "submitted":
        return result.build_rid
    return None


def _run_error(run: Any) -> Optional[str]:
    result = run.result
    if result is not None and result.type == "error":
        return f"{result.error_name}: {result.description}"
    return None


#: Table/CSV columns for a ``Build``.
BUILD_COLUMNS: Columns = {
    "RID": "rid",
    "Status": "status",
    "Branch": "branch_name",
    "Created": "created_time",
    "Created By": "created_by",
    "Finished": "finished_time",
    "Schedule": "schedule_rid",
    "Jobs": lambda build: _join(build.job_rids),
    "Fallback Branches": lambda build: _join(build.fallback_branches),
    "Abort On Failure": "abort_on_failure",
    "Retry Count": "retry_count",
    "Retry Backoff": _retry_backoff,
}

#: Table/CSV columns for lists of builds (one row per ``Build``).
BUILD_LIST_COLUMNS: Columns = {
    "RID": "rid",
    "Status": "status",
    "Branch": "branch_name",
    "Created": "created_time",
    "Finished": "finished_time",
}

#: Table/CSV columns for a ``Job``.
JOB_COLUMNS: Columns = {
    "RID": "rid",
    "Status": "job_status",
    "Build": "build_rid",
    "Started": "started_time",
    "Latest Attempt Started": "latest_attempt_start_time",
    "Finished": "finished_time",
    "Outputs": _job_outputs,
}

#: Table/CSV columns for lists of jobs (one row per ``Job``).
JOB_LIST_COLUMNS: Columns = {
    "RID": "rid",
    "Status": "job_status",
    "Started": "started_time",
    "Finished": "finished_time",
    "Outputs": _job_outputs,
}

#: Table/CSV columns for a ``Schedule``.
SCHEDULE_COLUMNS: Columns = {
    "RID": "rid",
    "Display Name": "display_name",
    "Description": "description",
    "Paused": "paused",
    "Trigger": "trigger",
    "Target": "action.target",
    "Branch": "action.branch_name",
    "Scope Mode": "scope_mode",
    "Current Version": "current_version_rid",
    "Created": "created_time",
    "Created By": "created_by",
    "Updated": "updated_time",
    "Updated By": "updated_by",
}

#: Table/CSV columns for a ``ScheduleRun``.
SCHEDULE_RUN_COLUMNS: Columns = {
    "RID": "rid",
    "Schedule": "schedule_rid",
    "Schedule Version": "schedule_version_rid",
    "Created": "created_time",
    "Created By": "created_by",
    "Result": "result.type",
    "Build": _run_build,
    "Error": _run_error,
}

#: Table/CSV columns for lists of schedule runs (one row per ``ScheduleRun``).
SCHEDULE_RUN_LIST_COLUMNS: Columns = {
    "RID": "rid",
    "Created": "created_time",
    "Result": "result.type",
    "Build": _run_build,
    "Error": _run_error,
}


# ------------------------------------------------------------- arguments

BuildRid = Annotated[
    str,
    typer.Argument(
        help="Build RID (ri.foundry.main.build.<id>).",
        autocompletion=complete_rid,
    ),
]
JobRid = Annotated[
    str,
    typer.Argument(
        help="Job RID (ri.foundry.main.job.<id>).", autocompletion=complete_rid
    ),
]
ScheduleRid = Annotated[
    str,
    typer.Argument(
        help="Schedule RID (ri.scheduler.main.schedule.<id>).",
        autocompletion=complete_rid,
    ),
]
ScheduleNameOption = Annotated[
    Optional[str],
    typer.Option("--name", help="Display name of the schedule."),
]
ScheduleDescriptionOption = Annotated[
    Optional[str],
    typer.Option("--description", help="Description of the schedule."),
]
TriggerOption = Annotated[
    Optional[str],
    typer.Option(
        "--trigger",
        help=(
            "When the schedule runs, as JSON or @file.json in the API's shape "
            "(a datasetRid or mediaSetRid can be a Compass path), "
            'e.g. \'{"type": "time", "cronExpression": "0 6 * * *", '
            '"timeZone": "UTC"}\'.'
        ),
    ),
]
ScopeModeOption = Annotated[
    Optional[str],
    typer.Option(
        "--scope-mode",
        help=(
            "Whose permissions the schedule's builds use, as JSON or @file.json "
            "(projectRids can be Compass paths): "
            '\'{"type": "project", "projectRids": ["<project RID>"]}\' or '
            '\'{"type": "user"}\'.'
        ),
    ),
]


#: RID fields of a build target (manual, upstream, connecting) that take
#: Compass paths too (#218). The SDK types them ``BuildableRid``, which is
#: open-ended (datasets, media sets, restricted views, ...), so the API
#: checks the resource type.
BUILD_TARGET_PATHS = {
    "targetRids": "resource",
    "inputRids": "resource",
    "ignoredRids": "resource",
}
#: RID fields of a schedule trigger that take paths (``ScheduleSucceeded``'s
#: ``scheduleRid`` names a schedule, not a Compass resource).
TRIGGER_PATHS = {"datasetRid": "dataset", "mediaSetRid": "media-set"}
#: RID fields of a schedule's project scope that take paths.
SCOPE_MODE_PATHS = {"projectRids": "project"}


def _one_build_target(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    """Exactly one of TARGET and --dataset (#218).

    Runs as a callback of both, so the check happens while the command line
    is parsed, before any path is resolved: whichever is processed second
    sees the other in ``ctx.params``.
    """
    # Typer turns an empty list option into None before calling this and
    # converts what it returns again: give back the empty tuple click had.
    unchanged = () if value is None and getattr(param, "multiple", False) else value
    other = "datasets" if param.name == "target" else "target"
    if ctx.resilient_parsing or other not in ctx.params:
        return unchanged
    target = value if param.name == "target" else ctx.params[other]
    datasets = value if param.name == "datasets" else ctx.params[other]
    if target is not None and datasets:
        raise click.UsageError(
            "Give TARGET or --dataset, not both: --dataset builds exactly those "
            "datasets (a manual target); use TARGET's JSON for an upstream or "
            "connecting build.",
            ctx=ctx,
        )
    if target is None and not datasets:
        raise click.UsageError(
            "Give what to build: --dataset <RID or path> (repeatable), or TARGET "
            "as build target JSON.",
            ctx=ctx,
        )
    return unchanged


def _split_rids(values: List[str]) -> List[str]:
    """RIDs given space- and/or comma-separated."""
    return [rid.strip() for value in values for rid in value.split(",") if rid.strip()]


def _optional_json(value: Optional[str], param_hint: str) -> Any:
    return None if value is None else load_json_input(value, param_hint=param_hint)


def _schedule_json(
    action: str,
    trigger: Optional[str],
    scope_mode: Optional[str],
    profile: Optional[str],
) -> Tuple[Any, Any, Any]:
    """A schedule's ACTION, --trigger and --scope-mode JSON, with the Compass
    paths in their RID fields resolved (#218)."""
    action_json = load_json_input(action, param_hint="ACTION")
    trigger_json = _optional_json(trigger, "'--trigger'")
    scope_json = _optional_json(scope_mode, "'--scope-mode'")
    return (
        resolve_json_paths(
            action_json, BUILD_TARGET_PATHS, label="ACTION", profile=profile
        ),
        resolve_json_paths(
            trigger_json, TRIGGER_PATHS, label="--trigger", profile=profile
        ),
        resolve_json_paths(
            scope_json, SCOPE_MODE_PATHS, label="--scope-mode", profile=profile
        ),
    )


# ------------------------------------------------------------------ builds


@builds_app.command("get")
@pltr_command(sdk="orchestration.Build.get")
def get_build(
    build_rid: BuildRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a build: its status, branch, jobs and timing."""
    with spinner(f"Fetching build {build_rid}..."):
        build = OrchestrationService(profile=profile).get_build(build_rid)
    cache_rid(build_rid)
    emit(build, format=format, output=output, columns=BUILD_COLUMNS, title="Build")


@builds_app.command("create")
@pltr_command(
    sdk=(
        "orchestration.Build.create",
        "orchestration.Build.get",
        "orchestration.Build.jobs",
    ),
    waits=True,
)
def create_build(
    target: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "What to build, as JSON or @file.json, with Compass paths "
                "allowed in its RID fields (see the examples below); leave it "
                "out when you use --dataset."
            ),
            show_default=False,
            callback=_one_build_target,
        ),
    ] = None,
    datasets: Annotated[
        Optional[List[str]],
        resource_option(
            "--dataset",
            kind="dataset",
            help=(
                "Dataset RID to build, instead of TARGET (repeat for several): "
                "builds exactly these datasets, like a manual target."
            ),
            show_default=False,
            callback=_one_build_target,
        ),
    ] = None,
    branch_name: Annotated[
        Optional[str],
        typer.Option("--branch", help="Branch to build on."),
    ] = None,
    fallback_branches: Annotated[
        Optional[List[str]],
        typer.Option(
            "--fallback-branch",
            help=(
                "Branch to read an input from when it doesn't exist on --branch "
                "(repeat for several, in order)."
            ),
        ),
    ] = None,
    force_build: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Build even if the outputs are already up to date.",
        ),
    ] = False,
    abort_on_failure: Annotated[
        bool,
        typer.Option(
            "--abort-on-failure", help="Stop the other jobs when one job fails."
        ),
    ] = False,
    notifications: Annotated[
        bool,
        typer.Option(
            "--notifications/--no-notifications",
            help="Send build notifications.",
        ),
    ] = True,
    retry_count: Annotated[
        Optional[int],
        typer.Option(
            "--retry-count", min=0, help="Number of retry attempts for failed jobs."
        ),
    ] = None,
    wait: WaitOption = False,
    timeout: WaitTimeoutOption = 600,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Start a build of datasets (or other build targets).

    To build datasets, name them with --dataset (a RID or a Compass path,
    repeatable). Otherwise TARGET is a JSON object (inline or @file.json) in
    the API's shape, with a 'type' that picks the build strategy:

    \b
    manual: build exactly these targets
      {"type": "manual", "targetRids": ["ri.foundry.main.dataset.abc"]}
    upstream: build the targets and everything upstream of them
      {"type": "upstream", "targetRids": ["ri.foundry.main.dataset.abc"],
       "ignoredRids": []}
    connecting: build everything between the inputs and the targets
      {"type": "connecting", "inputRids": ["ri.foundry.main.dataset.in"],
       "targetRids": ["ri.foundry.main.dataset.out"], "ignoredRids": []}

    In targetRids, inputRids and ignoredRids a Compass path
    (/Space/Project/name) works too: pltr looks it up and sends the RID.

    Follow the build with 'pltr orchestration builds get <build RID>' and
    its jobs with 'pltr orchestration builds jobs <build RID>', or add
    --wait.

    Examples:

    \b
      pltr orchestration builds create --dataset /Space/Project/sales \\
        --branch master --wait
      pltr orchestration builds create \\
        '{"type": "upstream", "targetRids": ["/Space/Project/sales"], "ignoredRids": []}'
      pltr orchestration builds create @target.json --force --format json
    """
    if datasets:
        target_json: Any = {"type": "manual", "targetRids": list(datasets)}
    else:
        assert target is not None  # _one_build_target
        if target.startswith(("/", "ri.")):  # a path or RID, not JSON
            raise typer.BadParameter(
                "TARGET is build target JSON; to build a dataset by RID or "
                f"path, use --dataset {shlex.quote(target)}",
                param_hint="TARGET",
            )
        target_json = resolve_json_paths(
            load_json_input(target, param_hint="TARGET"),
            BUILD_TARGET_PATHS,
            label="TARGET",
            profile=profile,
        )
    with spinner("Starting build..."):
        build = OrchestrationService(profile=profile).create_build(
            target=target_json,
            fallback_branches=list(fallback_branches or []),
            branch_name=branch_name,
            force_build=force_build,
            abort_on_failure=abort_on_failure,
            notifications_enabled=notifications,
            retry_count=retry_count,
        )
    cache_rid(build.rid)
    success(f"Started build {build.rid} ({build.status})")
    if wait:
        build = wait_for_build_rid(
            build.rid, timeout=timeout, build=build, profile=profile
        )
    else:
        info(f"Check its status with: pltr orchestration builds get {build.rid}")
    emit(build, format=format, output=output, columns=BUILD_COLUMNS, title="Build")


def wait_for_build_rid(
    build_rid: str,
    *,
    timeout: float,
    build: Any = None,
    profile: Optional[str],
    announce: bool = True,
) -> Any:
    """Wait for a build (--wait); return it once it succeeded."""
    note_started(
        f"build {build_rid}",
        f"pltr orchestration builds wait {build_rid}",
        announce=announce,
        buildRid=build_rid,
    )
    with spinner(f"Waiting for build {build_rid}..."):
        build = OrchestrationService(profile=profile).wait_for_build(
            build_rid, timeout=timeout, build=build
        )
    success(f"Build {build_rid} succeeded")
    return build


@builds_app.command("wait")
@pltr_command(sdk=("orchestration.Build.get", "orchestration.Build.jobs"), waits=True)
def wait_for_build(
    build_rid: BuildRid,
    timeout: WaitTimeoutOption = 600,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Wait for a build to finish, then print it.

    Exits 8 if the build failed or was canceled (the error names the failed
    jobs), and 9 if it is still running after --timeout seconds (it keeps
    running: run this again).
    """
    build = wait_for_build_rid(
        build_rid, timeout=timeout, profile=profile, announce=False
    )
    emit(build, format=format, output=output, columns=BUILD_COLUMNS, title="Build")


@builds_app.command("cancel")
@pltr_command(sdk="orchestration.Build.cancel", destructive=True)
def cancel_build(
    build_rid: BuildRid,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Cancel a build's unfinished jobs.

    Cancellation is asynchronous: the build's status changes shortly after the
    request is acknowledged. A build that has already finished is unchanged.
    """
    confirm_destructive(f"Cancel build {build_rid}?", yes=yes)
    with spinner(f"Cancelling build {build_rid}..."):
        OrchestrationService(profile=profile).cancel_build(build_rid)
    success(f"Requested cancellation of build {build_rid}")
    emit(None, format=format)


@builds_app.command("jobs")
@pltr_command(sdk="orchestration.Build.jobs", paged=True)
def get_build_jobs(
    build_rid: BuildRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the jobs of a build, with their status and outputs.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = OrchestrationService(profile=profile)
    with spinner(f"Fetching jobs of build {build_rid}..."):
        page = collect_pages(
            lambda token: service.get_build_jobs(
                build_rid, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(build_rid)
    emit(page, format=format, output=output, columns=JOB_LIST_COLUMNS)


_STATUSES = ("RUNNING", "SUCCEEDED", "FAILED", "CANCELED")
_ORDER_FIELDS = ("STARTED_TIME", "FINISHED_TIME")


def _timestamp(value: str, param_hint: str) -> str:
    """Validate an ISO-8601 timestamp with a time zone; return it in UTC."""
    text = value.strip()
    if text[-1:] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:
        raise typer.BadParameter(
            f"{value!r} is not an ISO-8601 timestamp with a time zone, "
            "e.g. 2024-01-31T00:00:00Z",
            param_hint=param_hint,
        )
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _order_by(values: List[str]) -> Optional[Dict[str, Any]]:
    """Turn ``FIELD[:ASC|DESC]`` values into a ``SearchBuildsOrderBy``."""
    if not values:
        return None
    fields = []
    for value in values:
        name, _, direction = value.partition(":")
        field = name.strip().upper().replace("-", "_")
        direction = (direction.strip() or "DESC").upper()
        if field not in _ORDER_FIELDS or direction not in ("ASC", "DESC"):
            raise typer.BadParameter(
                f"{value!r}: expected FIELD[:ASC|DESC] with FIELD one of "
                f"{', '.join(_ORDER_FIELDS)}",
                param_hint="'--order-by'",
            )
        fields.append({"field": field, "direction": direction})
    return {"fields": fields}


@builds_app.command("search")
@pltr_command(sdk="orchestration.Build.search", beta=True, paged=True)
def search_builds(
    where: Annotated[
        Optional[str],
        typer.Option(
            "--where",
            help=(
                "Filter as JSON or @file.json in the API's SearchBuildsFilter "
                "shape (eq, gte, lt, and, or, not; see below)."
            ),
        ),
    ] = None,
    status: Annotated[
        Optional[str],
        typer.Option(
            "--status",
            help="Only builds with this status.",
            click_type=click.Choice(_STATUSES, case_sensitive=False),
        ),
    ] = None,
    branch: Annotated[
        Optional[str], typer.Option("--branch", help="Only builds on this branch.")
    ] = None,
    created_by: Annotated[
        Optional[str],
        typer.Option("--created-by", help="Only builds started by this user ID."),
    ] = None,
    started_after: Annotated[
        Optional[str],
        typer.Option(
            "--started-after",
            help=(
                "Only builds started at or after this time "
                "(ISO-8601 with a time zone, e.g. 2024-01-31T00:00:00Z)."
            ),
        ),
    ] = None,
    started_before: Annotated[
        Optional[str],
        typer.Option("--started-before", help="Only builds started before this time."),
    ] = None,
    finished_after: Annotated[
        Optional[str],
        typer.Option(
            "--finished-after", help="Only builds finished at or after this time."
        ),
    ] = None,
    finished_before: Annotated[
        Optional[str],
        typer.Option(
            "--finished-before", help="Only builds finished before this time."
        ),
    ] = None,
    order_by: Annotated[
        Optional[List[str]],
        typer.Option(
            "--order-by",
            help=(
                "Sort by STARTED_TIME or FINISHED_TIME, optionally with :ASC or "
                ":DESC (default DESC); repeat to sort by both."
            ),
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """Search builds by status, branch, creator and start/finish time.

    Pass at least one filter. The filter options are combined with AND, and
    with --where if given. --where takes the API's SearchBuildsFilter: 'eq'
    on STATUS, BRANCH_NAME, CREATED_BY or RID; 'gte'/'lt' on STARTED_TIME or
    FINISHED_TIME; 'and'/'or' with "items"; 'not' with "value".

    Fetches one page by default (the API's page size is 100); use --all for
    every page, or --page-token with the nextPageToken of an earlier response
    to continue.

    Examples:

    \b
      # Failed builds on master, most recently started first
      pltr orchestration builds search --status FAILED --branch master \\
        --order-by STARTED_TIME:DESC
    \b
      # Builds started since a given time
      pltr orchestration builds search --started-after 2024-01-31T00:00:00Z
    \b
      # The same filter as --where JSON
      pltr orchestration builds search --where \\
        '{"type": "gte", "field": "STARTED_TIME", "value": "2024-01-31T00:00:00Z"}'
    """
    filters: List[Dict[str, Any]] = []
    if where is not None:
        filters.append(load_json_input(where, param_hint="'--where'"))
    for field, value in (
        ("STATUS", status.upper() if status else None),
        ("BRANCH_NAME", branch),
        ("CREATED_BY", created_by),
    ):
        if value is not None:
            filters.append({"type": "eq", "field": field, "value": value})
    for filter_type, field, value, hint in (
        ("gte", "STARTED_TIME", started_after, "'--started-after'"),
        ("lt", "STARTED_TIME", started_before, "'--started-before'"),
        ("gte", "FINISHED_TIME", finished_after, "'--finished-after'"),
        ("lt", "FINISHED_TIME", finished_before, "'--finished-before'"),
    ):
        if value is not None:
            filters.append(
                {"type": filter_type, "field": field, "value": _timestamp(value, hint)}
            )
    if not filters:
        raise typer.BadParameter(
            "pass --where or at least one of --status, --branch, --created-by, "
            "--started-after, --started-before, --finished-after, --finished-before "
            "(the API requires a filter)"
        )
    where_filter = (
        filters[0] if len(filters) == 1 else {"type": "and", "items": filters}
    )
    sort = _order_by(list(order_by or []))

    service = OrchestrationService(profile=profile)
    with spinner("Searching builds..."):
        page = collect_pages(
            lambda token: service.search_builds(
                where=where_filter,
                order_by=sort,
                page_size=page_size,
                page_token=token,
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    emit(page, format=format, output=output, columns=BUILD_LIST_COLUMNS)


@builds_app.command("get-batch")
@pltr_command(sdk="orchestration.Build.get_batch")
def get_builds_batch(
    build_rids: Annotated[
        List[str],
        typer.Argument(
            help=(
                f"Build RIDs, separated by spaces or commas (at most "
                f"{MAX_BUILDS_BATCH})."
            )
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get several builds in one request.

    JSON output is the API's response: {"data": {"<build RID>": {...}}}.
    """
    rids = _split_rids(build_rids)
    if not rids:
        raise typer.BadParameter("no build RIDs given", param_hint="BUILD_RIDS")
    if len(rids) > MAX_BUILDS_BATCH:
        raise typer.BadParameter(
            f"at most {MAX_BUILDS_BATCH} build RIDs per request, got {len(rids)}",
            param_hint="BUILD_RIDS",
        )
    with spinner(f"Fetching {len(rids)} builds..."):
        response = OrchestrationService(profile=profile).get_builds_batch(rids)
    emit(
        response,
        format=format,
        output=output,
        columns=BUILD_LIST_COLUMNS,
        rows=lambda batch: list(batch.data.values()),
    )


# -------------------------------------------------------------------- jobs


@jobs_app.command("get")
@pltr_command(sdk="orchestration.Job.get", beta=True)
def get_job(
    job_rid: JobRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a job: its status, build, outputs and timing."""
    with spinner(f"Fetching job {job_rid}..."):
        job = OrchestrationService(profile=profile).get_job(job_rid)
    cache_rid(job_rid)
    emit(job, format=format, output=output, columns=JOB_COLUMNS, title="Job")


@jobs_app.command("get-batch")
@pltr_command(sdk="orchestration.Job.get_batch", beta=True)
def get_jobs_batch(
    job_rids: Annotated[
        List[str],
        typer.Argument(
            help=(
                f"Job RIDs, separated by spaces or commas (at most {MAX_JOBS_BATCH})."
            )
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get several jobs in one request.

    JSON output is the API's response: {"data": {"<job RID>": {...}}}.
    """
    rids = _split_rids(job_rids)
    if not rids:
        raise typer.BadParameter("no job RIDs given", param_hint="JOB_RIDS")
    if len(rids) > MAX_JOBS_BATCH:
        raise typer.BadParameter(
            f"at most {MAX_JOBS_BATCH} job RIDs per request, got {len(rids)}",
            param_hint="JOB_RIDS",
        )
    with spinner(f"Fetching {len(rids)} jobs..."):
        response = OrchestrationService(profile=profile).get_jobs_batch(rids)
    emit(
        response,
        format=format,
        output=output,
        columns=JOB_COLUMNS,
        rows=lambda batch: list(batch.data.values()),
    )


# --------------------------------------------------------------- schedules


@schedules_app.command("get")
@pltr_command(sdk="orchestration.Schedule.get", beta=True)
def get_schedule(
    schedule_rid: ScheduleRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Get a schedule: its trigger, build target, scope and paused state."""
    with spinner(f"Fetching schedule {schedule_rid}..."):
        schedule = OrchestrationService(profile=profile).get_schedule(schedule_rid)
    cache_rid(schedule_rid)
    emit(
        schedule,
        format=format,
        output=output,
        columns=SCHEDULE_COLUMNS,
        title="Schedule",
    )


_ACTION_HELP = (
    "What the schedule builds, as JSON or @file.json in the API's shape "
    "(Compass paths work in the target's RID fields), e.g. "
    '\'{"target": {"type": "manual", "targetRids": ["<dataset RID>"]}, '
    '"branchName": "master"}\'.'
)


@schedules_app.command("create")
@pltr_command(sdk="orchestration.Schedule.create", beta=True)
def create_schedule(
    action: Annotated[str, typer.Argument(help=_ACTION_HELP, show_default=False)],
    display_name: ScheduleNameOption = None,
    description: ScheduleDescriptionOption = None,
    trigger: TriggerOption = None,
    scope_mode: ScopeModeOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Create a schedule.

    ACTION says what to build (a build target plus build options such as
    branchName, fallbackBranches, forceBuild, abortOnFailure, retryCount and
    notificationsEnabled). --trigger says when. In user-scoped mode the
    outputs to build are found from what the user can access, so they can
    change with the user's permissions; Foundry recommends a project-scoped
    schedule (--scope-mode).

    Examples:

    \b
      pltr orchestration schedules create \\
        '{"target": {"type": "manual", "targetRids": ["ri.foundry.main.dataset.abc"]}}' \\
        --name "Nightly build" \\
        --trigger '{"type": "time", "cronExpression": "0 2 * * *", "timeZone": "UTC"}'
    """
    action_json, trigger_json, scope_json = _schedule_json(
        action, trigger, scope_mode, profile
    )
    with spinner("Creating schedule..."):
        schedule = OrchestrationService(profile=profile).create_schedule(
            action=action_json,
            display_name=display_name,
            description=description,
            trigger=trigger_json,
            scope_mode=scope_json,
        )
    cache_rid(schedule.rid)
    success(f"Created schedule {schedule.rid}")
    emit(
        schedule,
        format=format,
        output=output,
        columns=SCHEDULE_COLUMNS,
        title="Schedule",
    )


@schedules_app.command("replace")
@pltr_command(sdk="orchestration.Schedule.replace", beta=True, destructive=True)
def replace_schedule(
    schedule_rid: ScheduleRid,
    action: Annotated[str, typer.Argument(help=_ACTION_HELP, show_default=False)],
    display_name: ScheduleNameOption = None,
    description: ScheduleDescriptionOption = None,
    trigger: TriggerOption = None,
    scope_mode: ScopeModeOption = None,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Replace a schedule's definition with a new one.

    This is a full replacement, not a patch: only what you pass is sent, so
    pass every field you want the schedule to keep (name, description,
    trigger, scope mode). Read the current definition first with
    'pltr orchestration schedules get <RID> --format json'.
    """
    action_json, trigger_json, scope_json = _schedule_json(
        action, trigger, scope_mode, profile
    )
    confirm_destructive(f"Replace the definition of schedule {schedule_rid}?", yes=yes)
    with spinner(f"Replacing schedule {schedule_rid}..."):
        schedule = OrchestrationService(profile=profile).replace_schedule(
            schedule_rid,
            action=action_json,
            display_name=display_name,
            description=description,
            trigger=trigger_json,
            scope_mode=scope_json,
        )
    success(f"Replaced schedule {schedule_rid}")
    emit(
        schedule,
        format=format,
        output=output,
        columns=SCHEDULE_COLUMNS,
        title="Schedule",
    )


@schedules_app.command("delete")
@pltr_command(sdk="orchestration.Schedule.delete", destructive=True)
def delete_schedule(
    schedule_rid: ScheduleRid,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Delete a schedule."""
    confirm_destructive(f"Delete schedule {schedule_rid}?", yes=yes)
    with spinner(f"Deleting schedule {schedule_rid}..."):
        OrchestrationService(profile=profile).delete_schedule(schedule_rid)
    success(f"Deleted schedule {schedule_rid}")
    emit(None, format=format)


@schedules_app.command("pause")
@pltr_command(sdk="orchestration.Schedule.pause")
def pause_schedule(
    schedule_rid: ScheduleRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Pause a schedule: its trigger no longer starts builds."""
    with spinner(f"Pausing schedule {schedule_rid}..."):
        OrchestrationService(profile=profile).pause_schedule(schedule_rid)
    success(f"Paused schedule {schedule_rid}")
    emit(None, format=format)


@schedules_app.command("unpause")
@pltr_command(sdk="orchestration.Schedule.unpause")
def unpause_schedule(
    schedule_rid: ScheduleRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Unpause a schedule."""
    with spinner(f"Unpausing schedule {schedule_rid}..."):
        OrchestrationService(profile=profile).unpause_schedule(schedule_rid)
    success(f"Unpaused schedule {schedule_rid}")
    emit(None, format=format)


@schedules_app.command("run")
@pltr_command(
    sdk=(
        "orchestration.Schedule.run",
        "orchestration.Schedule.runs",
        "orchestration.Build.get",
        "orchestration.Build.jobs",
    ),
    waits=True,
)
def run_schedule(
    schedule_rid: ScheduleRid,
    wait: WaitOption = False,
    timeout: WaitTimeoutOption = 600,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Run a schedule now, and show the run (with the build it started)."""
    with spinner(f"Running schedule {schedule_rid}..."):
        run = OrchestrationService(profile=profile).run_schedule(schedule_rid)
    deadline = time.monotonic() + timeout
    if wait and run.result is None:
        # The service is still triggering the schedule: wait for the result.
        note_started(
            f"schedule run {run.rid}",
            f"pltr orchestration schedules runs {schedule_rid}",
            scheduleRunRid=run.rid,
        )
        with spinner(f"Waiting for schedule run {run.rid}..."):
            run = OrchestrationService(profile=profile).wait_for_schedule_run(
                schedule_rid, run, timeout=timeout
            )
    build_rid = _run_build(run)
    error = getattr(run.result, "error_name", None)
    if wait and error is not None:
        raise WorkFailed(
            f"Schedule {schedule_rid} didn't start a build: {error}: "
            f"{getattr(run.result, 'description', '')}".rstrip(": "),
            parameters={"scheduleRid": schedule_rid, "scheduleRunRid": run.rid},
        )
    if build_rid is not None:
        cache_rid(build_rid)
        success(f"Schedule {schedule_rid} started build {build_rid}")
        if wait:
            remaining = max(0.0, deadline - time.monotonic())
            build = wait_for_build_rid(build_rid, timeout=remaining, profile=profile)
            emit(
                build,
                format=format,
                output=output,
                columns=BUILD_COLUMNS,
                title="Build",
            )
            return
        info(f"Check its status with: pltr orchestration builds get {build_rid}")
    else:
        success(f"Ran schedule {schedule_rid}")
    emit(
        run,
        format=format,
        output=output,
        columns=SCHEDULE_RUN_COLUMNS,
        title="Schedule Run",
    )


@schedules_app.command("runs")
@pltr_command(sdk="orchestration.Schedule.runs", paged=True)
def get_schedule_runs(
    schedule_rid: ScheduleRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List a schedule's most recent runs and the builds they started.

    Fetches one page by default (the API's page size is 100); use --all for
    every page, or --page-token with the nextPageToken of an earlier response
    to continue.
    """
    service = OrchestrationService(profile=profile)
    with spinner(f"Fetching runs of schedule {schedule_rid}..."):
        page = collect_pages(
            lambda token: service.get_schedule_runs(
                schedule_rid, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(schedule_rid)
    emit(page, format=format, output=output, columns=SCHEDULE_RUN_LIST_COLUMNS)


# --------------------------------------------------------------------- app

app.add_typer(builds_app, name="builds", help="Start, inspect and cancel builds")
app.add_typer(jobs_app, name="jobs", help="Inspect the jobs of builds")
app.add_typer(schedules_app, name="schedules", help="Inspect, run and manage schedules")


@app.callback()
def main():
    """
    Builds, jobs and schedules (Foundry orchestration API).

    Everything is addressed by RID: builds
    (ri.foundry.main.build.<id>), jobs (ri.foundry.main.job.<id>) and
    schedules (ri.scheduler.main.schedule.<id>). Commands labeled [beta] call
    beta Foundry endpoints.

    Examples:

    \b
        # Start a build of a dataset (RID or path) and follow it
        pltr orchestration builds create --dataset /Space/Project/sales
        pltr orchestration builds get <BUILD_RID>
        pltr orchestration builds jobs <BUILD_RID>
    \b
        # Find recent failed builds
        pltr orchestration builds search --status FAILED --order-by STARTED_TIME
    \b
        # Inspect a schedule and its runs, or run it now
        pltr orchestration schedules get <SCHEDULE_RID>
        pltr orchestration schedules runs <SCHEDULE_RID>
        pltr orchestration schedules run <SCHEDULE_RID>
    """
