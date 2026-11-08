"""`pltr assert`: checks that pass or fail by exit code (#195).

Each command runs its checks, prints one result
(``{"passed": ..., "target": ..., "checks": [...]}``) and exits 0 when every
check passed, 8 (``assertion_failed``, with an error line on stderr) when one
didn't. Use them after ``--wait`` to verify what a build or import produced.
"""

import datetime
import json
import re
from typing import Any, Dict, List, Optional

import typer
from typing_extensions import Annotated

from ..contract import (
    Columns,
    ExitCode,
    FormatOption,
    OutputOption,
    PltrError,
    ProfileOption,
    emit,
    pltr_command,
    resource_argument,
    spinner,
    to_jsonable,
)
from ..services.dataset import DatasetService
from ..services.ontology import OntologyObjectService
from ..services.orchestration import OrchestrationService

app = typer.Typer(
    help=(
        "Check a dataset, build or object type; exit 0 if every check passes, "
        "8 if one fails."
    )
)

CHECK_COLUMNS: Columns = {
    "Check": "check",
    "Passed": "passed",
    "Expected": "expected",
    "Actual": "actual",
}


class AssertionFailed(PltrError):
    """At least one `pltr assert` check failed (exit 8)."""

    error_type = "assertion_failed"
    exit_code = ExitCode.FAILED


def _report(
    target: str, checks: List[Dict[str, Any]], format: str, output: Optional[str]
) -> None:
    passed = all(check["passed"] for check in checks)
    emit(
        {"passed": passed, "target": target, "checks": checks},
        format=format,
        output=output,
        columns=CHECK_COLUMNS,
        rows=lambda result: result["checks"],
        title=f"Checks on {target}",
    )
    if not passed:
        failed = ", ".join(c["check"] for c in checks if not c["passed"])
        raise AssertionFailed(f"Failed on {target}: {failed}.")


# ----------------------------------------------------------------- dataset

_DURATION = re.compile(r"(\d+)\s*([smhd])")
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(text: str) -> datetime.timedelta:
    """``90s``, ``30m``, ``1h``, ``2d`` (or combined, ``1h30m``)."""
    compact = text.strip().lower()
    parts = _DURATION.findall(compact)
    if not parts or "".join(f"{n}{u}" for n, u in parts) != compact.replace(" ", ""):
        raise typer.BadParameter(
            f"{text!r} is not a duration such as 90s, 30m, 1h or 2d",
            param_hint="'--updated-within'",
        )
    return datetime.timedelta(seconds=sum(int(n) * _UNITS[u] for n, u in parts))


def _schema_fields(document: Any) -> Dict[str, str]:
    """Column name -> type, from an API schema or a ``schema get`` response."""
    if isinstance(document, dict) and "schema" in document:
        document = document["schema"]
    fields = (document or {}).get("fieldSchemaList") or []
    return {str(f["name"]): str(f.get("type", "")).upper() for f in fields}


def _load_expected_schema(path: str) -> Dict[str, str]:
    try:
        with open(path, encoding="utf-8") as handle:
            return _schema_fields(json.load(handle))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise typer.BadParameter(
            f"can't read a dataset schema from {path}: {exc}",
            param_hint="'--schema'",
        ) from exc


def _latest_commit(service: DatasetService, dataset_rid: str, branch: str) -> Any:
    for transaction in service.list_branch_transactions(dataset_rid, branch):
        if transaction.status == "COMMITTED":
            return transaction
    return None


@app.command("dataset")
@pltr_command(
    sdk=(
        "datasets.Dataset.read_table",
        "datasets.Dataset.get_schema",
        "datasets.Dataset.Branch.transactions",
    ),
    beta=True,
)
def assert_dataset(
    dataset_rid: Annotated[
        str, resource_argument("dataset", help="Dataset RID to check.")
    ],
    min_rows: Annotated[
        Optional[int],
        typer.Option(
            "--min-rows",
            min=1,
            help=(
                "At least this many rows. Reads at most this many rows "
                "(Dataset.read_table with a row limit), so it stays cheap."
            ),
        ),
    ] = None,
    schema: Annotated[
        Optional[str],
        typer.Option(
            "--schema",
            help=(
                "File with the expected schema: the output of `pltr dataset "
                'schema get --format json`, or {"fieldSchemaList": [...]}. '
                "Same column names and types; order doesn't matter."
            ),
        ),
    ] = None,
    updated_within: Annotated[
        Optional[str],
        typer.Option(
            "--updated-within",
            help="The latest committed transaction is this recent: 90s, 30m, 1h, 2d.",
        ),
    ] = None,
    branch: Annotated[
        Optional[str],
        typer.Option(
            "--branch",
            help="Branch to check (default: the dataset's default branch; "
            "--updated-within uses master).",
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """[beta] Check a dataset's rows, schema and freshness.

    Give at least one of --min-rows, --schema and --updated-within.

    \b
      pltr assert dataset /Space/Project/sales --min-rows 1 --updated-within 1h
      pltr assert dataset ri.foundry.main.dataset.abc --schema expected.json
    """
    if min_rows is None and schema is None and updated_within is None:
        raise typer.BadParameter(
            "give at least one check: --min-rows, --schema or --updated-within"
        )
    expected_schema = _load_expected_schema(schema) if schema else None
    window = parse_duration(updated_within) if updated_within else None
    service = DatasetService(profile=profile)
    checks: List[Dict[str, Any]] = []
    with spinner(f"Checking dataset {dataset_rid}..."):
        if min_rows is not None:
            rows = service.preview_table(dataset_rid, limit=min_rows, branch=branch)
            checks.append(
                {
                    "check": "min-rows",
                    "passed": rows.num_rows >= min_rows,
                    "expected": min_rows,
                    "actual": rows.num_rows,
                }
            )
        if expected_schema is not None:
            response = service.get_dataset_schema(dataset_rid, branch=branch)
            actual = _schema_fields(to_jsonable(response))
            missing = sorted(set(expected_schema) - set(actual))
            unexpected = sorted(set(actual) - set(expected_schema))
            mismatches = [
                {
                    "column": name,
                    "expected": expected_schema[name],
                    "actual": actual[name],
                }
                for name in sorted(set(expected_schema) & set(actual))
                if expected_schema[name] != actual[name]
            ]
            checks.append(
                {
                    "check": "schema",
                    "passed": not (missing or unexpected or mismatches),
                    "missing": missing,
                    "unexpected": unexpected,
                    "typeMismatches": mismatches,
                }
            )
        if window is not None:
            commit = _latest_commit(service, dataset_rid, branch or "master")
            closed = getattr(commit, "closed_time", None)
            now = datetime.datetime.now(datetime.timezone.utc)
            checks.append(
                {
                    "check": "updated-within",
                    "passed": closed is not None and now - closed <= window,
                    "expected": updated_within,
                    "actual": closed.isoformat() if closed else None,
                    "transactionRid": getattr(commit, "rid", None),
                }
            )
    _report(dataset_rid, checks, format, output)


# ------------------------------------------------------------- build, objects


@app.command("build")
@pltr_command(
    sdk="orchestration.Build.get",
    no_emit_code=(
        "it checks the build locally; `pltr orchestration builds get "
        "--emit-code` shows the call."
    ),
)
def assert_build(
    build_rid: Annotated[str, typer.Argument(help="Build RID.")],
    succeeded: Annotated[
        bool, typer.Option("--succeeded", help="The build has SUCCEEDED.")
    ] = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Check that a build succeeded (a running build fails the check)."""
    if not succeeded:
        raise typer.BadParameter("give the check: --succeeded")
    with spinner(f"Checking build {build_rid}..."):
        build = OrchestrationService(profile=profile).get_build(build_rid)
    checks = [
        {
            "check": "succeeded",
            "passed": build.status == "SUCCEEDED",
            "expected": "SUCCEEDED",
            "actual": build.status,
        }
    ]
    _report(build_rid, checks, format, output)


@app.command("objects")
@pltr_command(
    sdk="ontologies.OntologyObject.count",
    beta=True,
    no_emit_code=(
        "it checks the count locally; `pltr ontology object-count "
        "--emit-code` shows the call."
    ),
)
def assert_objects(
    ontology: Annotated[str, typer.Argument(help="Ontology RID or API name.")],
    object_type: Annotated[str, typer.Argument(help="Object type API name.")],
    min_count: Annotated[
        int,
        typer.Option("--min-count", min=0, help="At least this many objects."),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """[beta] Check that an object type has at least --min-count objects."""
    with spinner(f"Counting {object_type} objects..."):
        response = OntologyObjectService(profile=profile).count_objects(
            ontology, object_type
        )
    count = int(response.count or 0)
    checks = [
        {
            "check": "min-count",
            "passed": count >= min_count,
            "expected": min_count,
            "actual": count,
        }
    ]
    _report(f"{ontology} {object_type}", checks, format, output)
