"""
Data health commands: checks and check reports (Foundry data health API).

Every data health endpoint is beta, so every command is labeled [beta].
"""

from typing import Optional

import typer
from typing_extensions import Annotated

from ..contract import (
    Columns,
    ForceAliasOption,
    FormatOption,
    OutputOption,
    PreviewNoopOption,
    ProfileOption,
    YesOption,
    confirm_destructive,
    emit,
    load_json_input,
    pltr_command,
    spinner,
    success,
)
from ..services.data_health import DataHealthService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer(help="Manage data health checks and reports")
check_app = typer.Typer(help="Create, inspect, replace and delete checks")
report_app = typer.Typer(help="Inspect the reports (results) of checks")
app.add_typer(check_app, name="check")
app.add_typer(report_app, name="report")

#: Table/CSV columns for a ``Check``.
CHECK_COLUMNS: Columns = {
    "RID": "rid",
    "Type": "config.type",
    "Intent": "intent",
    "Groups": lambda check: ", ".join(check.groups),
    "Created By": "created_by",
    "Updated": "updated_time",
    "Config": "config",
}

#: Table/CSV columns for a ``CheckReport``.
REPORT_COLUMNS: Columns = {
    "RID": "rid",
    "Status": "result.status",
    "Message": "result.message",
    "Created": "created_time",
    "Check": "check.rid",
    "Check Type": "check.config.type",
}

#: Table/CSV columns for lists of check reports (one row per ``CheckReport``).
REPORT_LIST_COLUMNS: Columns = {
    "RID": "rid",
    "Status": "result.status",
    "Message": "result.message",
    "Created": "created_time",
}

CheckRid = Annotated[
    str,
    typer.Argument(
        help="Check RID (ri.data-health.main.check.<id>).",
        autocompletion=complete_rid,
    ),
]
IntentOption = Annotated[
    Optional[str],
    typer.Option("--intent", "-i", help="Why the check was set up."),
]


@check_app.command("get")
@pltr_command(sdk="data_health.Check.get", beta=True)
def get_check(
    check_rid: CheckRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Get a check: its type, configuration and intent.

    Examples:

    \b
        pltr data-health check get ri.data-health.main.check.abc123
        pltr data-health check get ri.data-health.main.check.abc123 --format json
    """
    with spinner(f"Fetching check {check_rid}..."):
        check = DataHealthService(profile=profile).get_check(check_rid)
    cache_rid(check_rid)
    emit(check, format=format, output=output, columns=CHECK_COLUMNS, title="Check")


@check_app.command("create")
@pltr_command(sdk="data_health.Check.create", beta=True)
def create_check(
    config: Annotated[
        str,
        typer.Argument(
            help="Check configuration as JSON or @file.json (see below).",
            show_default=False,
        ),
    ],
    intent: IntentOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Create a check.

    CONFIG is the check configuration in the API's JSON shape. Its 'type'
    picks the kind of check, and 'subject' says what it checks (a dataset
    and branch, or a schedule). Types: allowedColumnValues,
    approximateUniquePercentage, buildDuration, buildStatus, columnType,
    dateColumnRange, jobDuration, jobStatus, nullPercentage,
    numericColumnMean, numericColumnMedian, numericColumnRange, primaryKey,
    scheduleDuration, scheduleStatus, schemaComparison, timeSinceLastUpdated,
    totalColumnCount.

    Examples:

    \b
        # Alert when a dataset's build on master fails
        pltr data-health check create '{
            "type": "buildStatus",
            "subject": {
                "datasetRid": "ri.foundry.main.dataset.abc123",
                "branchId": "master"
            },
            "statusCheckConfig": {"severity": "MODERATE"}
        }' --intent "Monitor production builds"
    \b
        # Create from a JSON file
        pltr data-health check create @check-config.json --format json
    """
    config_json = load_json_input(config, param_hint="CONFIG")
    with spinner("Creating check..."):
        check = DataHealthService(profile=profile).create_check(
            config=config_json, intent=intent
        )
    cache_rid(check.rid)
    success(f"Created check {check.rid}")
    emit(check, format=format, output=output, columns=CHECK_COLUMNS, title="Check")


@check_app.command("replace")
@pltr_command(sdk="data_health.Check.replace", beta=True, destructive=True)
def replace_check(
    check_rid: CheckRid,
    config: Annotated[
        str,
        typer.Argument(
            help="New check configuration as JSON or @file.json.",
            show_default=False,
        ),
    ],
    intent: IntentOption = None,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Replace a check's configuration.

    CONFIG has the shape of the create configuration without 'subject': a
    check's type and subject can't be changed. The new configuration and
    --intent replace the old ones.

    Examples:

    \b
        pltr data-health check replace ri.data-health.main.check.abc123 \\
            '{"type": "buildStatus", "statusCheckConfig": {"severity": "CRITICAL"}}' \\
            --intent "Page on failed builds"
    """
    config_json = load_json_input(config, param_hint="CONFIG")
    confirm_destructive(f"Replace the configuration of check {check_rid}?", yes=yes)
    with spinner(f"Replacing check {check_rid}..."):
        check = DataHealthService(profile=profile).replace_check(
            check_rid, config=config_json, intent=intent
        )
    success(f"Replaced check {check_rid}")
    emit(check, format=format, output=output, columns=CHECK_COLUMNS, title="Check")


@check_app.command("delete")
@pltr_command(sdk="data_health.Check.delete", beta=True, destructive=True)
def delete_check(
    check_rid: CheckRid,
    yes: YesOption = False,
    force: ForceAliasOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    preview: PreviewNoopOption = False,
):
    """Delete a check.

    Asks for confirmation; --yes skips it (required when stdin is not a
    terminal).
    """
    confirm_destructive(f"Delete check {check_rid}?", yes=yes)
    with spinner(f"Deleting check {check_rid}..."):
        DataHealthService(profile=profile).delete_check(check_rid)
    success(f"Deleted check {check_rid}")
    emit(None, format=format)


@report_app.command("get")
@pltr_command(sdk="data_health.Check.CheckReport.get", beta=True)
def get_report(
    check_rid: CheckRid,
    check_report_rid: Annotated[
        str,
        typer.Argument(
            help=(
                "Check report RID (find it with 'pltr data-health report "
                "latest <CHECK_RID>')."
            ),
            autocompletion=complete_rid,
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Get one report of a check: its result status and message.

    A report is addressed by its check's RID and its own RID. Statuses:
    PASSED, FAILED, WARNING, ERROR, NOT_APPLICABLE, NOT_COMPUTABLE.

    Examples:

    \b
        pltr data-health report get ri.data-health.main.check.abc123 \\
            ri.data-health.main.check-report.def456
    """
    with spinner(f"Fetching check report {check_report_rid}..."):
        report = DataHealthService(profile=profile).get_check_report(
            check_rid, check_report_rid
        )
    cache_rid(check_rid)
    emit(
        report,
        format=format,
        output=output,
        columns=REPORT_COLUMNS,
        title="Check Report",
    )


@report_app.command("latest")
@pltr_command(sdk="data_health.Check.CheckReport.get_latest", beta=True)
def latest_reports(
    check_rid: CheckRid,
    limit: Annotated[
        Optional[int],
        typer.Option(
            "--limit",
            min=1,
            max=100,
            help="Maximum number of reports (the API's default is 10).",
            show_default=False,
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """List a check's most recent reports.

    JSON output is the API's response: {"data": [...]}.

    Examples:

    \b
        pltr data-health report latest ri.data-health.main.check.abc123
        pltr data-health report latest ri.data-health.main.check.abc123 \\
            --limit 50 --format json
    """
    with spinner(f"Fetching the latest reports of check {check_rid}..."):
        response = DataHealthService(profile=profile).get_latest_check_reports(
            check_rid, limit=limit
        )
    cache_rid(check_rid)
    emit(
        response,
        format=format,
        output=output,
        columns=REPORT_LIST_COLUMNS,
        rows=lambda reports: reports.data,
    )
