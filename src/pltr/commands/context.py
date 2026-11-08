"""`pltr context`: compact summaries of a dataset, folder or ontology (#194).

Context packs are written for a model to read before it writes code against a
resource: short Markdown by default, the same content as JSON with
``--format json``. Nulls, internal IDs and fields agents don't use are left
out, and the output is capped: when something is cut, the pack says so and
how to narrow it. ``--fixture-dir`` also writes the samples to files for
tests (a few rows, never an export).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import typer
from typing_extensions import Annotated

from ..contract import (
    FormatOption,
    OutputOption,
    ProfileOption,
    emit,
    pltr_command,
    resource_argument,
    spinner,
    to_jsonable,
    warn,
)
from ..contract.errors import classify_error
from ..contract.output import _write_text, table_rows
from ..services.dataset import DatasetService
from ..services.ontology import OntologyObjectService, OntologyService
from ..services.orchestration import OrchestrationService
from ..services.resource import ResourceService
from .assertions import type_text

app = typer.Typer(
    help=(
        "Compact summaries of a dataset, folder or ontology for writing code "
        "against it (Markdown, or --format json); --fixture-dir writes samples "
        "for tests."
    )
)

RowsOption = Annotated[
    int,
    typer.Option(
        "--rows", min=1, max=1000, help="Sample rows or objects (at most 1000)."
    ),
]
FixtureDirOption = Annotated[
    Optional[Path],
    typer.Option(
        "--fixture-dir",
        help=(
            "Also write the samples to this directory for tests. They are real "
            "Foundry data: keep them out of git unless you may share them."
        ),
    ),
]

#: Sample values longer than this are cut in Markdown.
VALUE_LIMIT = 40
#: Columns shown in Markdown sample rows unless --columns picks them.
SAMPLE_COLUMNS = 12
#: Rows of `context folder` at most.
FOLDER_LIMIT = 500
#: Object types described in full without --types.
SUMMARY_LIMIT = 200

FIXTURE_WARNING = (
    "Fixtures contain real Foundry data, which may carry markings: add the "
    "fixture directory to .gitignore unless you may share it."
)


def _cell(value: Any, limit: Optional[int] = None) -> str:
    if value is None:
        return ""
    value = to_jsonable(value)
    text = value if isinstance(value, str) else json.dumps(value)
    text = " ".join(str(text).split()).replace("|", "\\|")
    if limit is None or len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _table(
    headers: Sequence[str], rows: List[Sequence[Any]], limit: Optional[int] = None
) -> List[str]:
    """A Markdown table; ``limit`` cuts long cells (sample values only)."""
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(v, limit) for v in row) + " |" for row in rows]
    return lines


def _write(
    fmt: str,
    document: Dict[str, Any],
    markdown: List[str],
    output: Optional[str],
    rows: List[Dict[str, Any]],
) -> None:
    """table: the Markdown pack; json: the document; csv: its main list."""
    if fmt == "json":
        emit(document, format="json", output=output)
    elif fmt == "csv":
        emit(rows, format="csv", output=output)
    else:
        _write_text("\n".join(markdown).rstrip() + "\n", output)


def _unavailable(section: str, exc: Exception) -> str:
    info = classify_error(exc)
    return f"{section} unavailable ({info.type}): {info.message}"


# ----------------------------------------------------------------- dataset


@app.command("dataset")
@pltr_command(
    sdk=(
        "filesystem.Resource.get",
        "datasets.Dataset.get_schema",
        "datasets.Dataset.read_table",
        "datasets.Dataset.get_schedules",
        "datasets.Dataset.jobs",
        "orchestration.Job.get",
    ),
    beta=True,
)
def dataset_context(
    dataset_rid: Annotated[
        str, resource_argument("dataset", help="Dataset RID to describe.")
    ],
    rows: RowsOption = 5,
    columns: Annotated[
        Optional[str],
        typer.Option(
            "--columns",
            help="Comma-separated columns for the sample rows (default: the first 12).",
        ),
    ] = None,
    branch: Annotated[
        Optional[str], typer.Option("--branch", help="Branch (default: the default).")
    ] = None,
    fixture_dir: FixtureDirOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """[beta] What a dataset holds: columns, sample rows, schedules, latest job.

    \b
      pltr context dataset /Space/Project/sales
      pltr context dataset ri.foundry.main.dataset.abc --format json
      pltr context dataset /Space/Project/sales --rows 20 --fixture-dir tests/fixtures
    """
    fmt = format
    datasets = DatasetService(profile=profile)
    notes: List[str] = []
    with spinner(f"Describing dataset {dataset_rid}..."):
        resource = ResourceService(profile=profile).get_resource(dataset_rid)
        schema = datasets.get_dataset_schema(dataset_rid, branch=branch)
        schema_json = to_jsonable(schema)
        fields = (schema_json.get("schema") or {}).get("fieldSchemaList") or []
        table = datasets.preview_table(dataset_rid, limit=rows, branch=branch)
        try:
            schedules = [
                str(s) for s in datasets.list_schedules(dataset_rid, branch=branch)
            ]
        except Exception as exc:
            schedules = []
            notes.append(_unavailable("schedules", exc))
        latest_job: Optional[Dict[str, Any]] = None
        try:
            job_details = next(iter(datasets.list_jobs(dataset_rid, page_size=1)), None)
            if job_details is not None:
                job = OrchestrationService(profile=profile).get_job(job_details.job_rid)
                latest_job = {"rid": job.rid, "status": job.job_status}
        except Exception as exc:
            notes.append(_unavailable("jobs", exc))

    column_list = [
        {
            "name": f["name"],
            "type": type_text(f),
            "nullable": bool(f.get("nullable", True)),
        }
        for f in fields
    ]
    _, all_rows = table_rows(table)
    names = [c["name"] for c in column_list] or list(all_rows[0] if all_rows else [])
    picked = (
        [c.strip() for c in columns.split(",")] if columns else names[:SAMPLE_COLUMNS]
    )
    sample = [
        {name: row.get(name) for name in picked if name in row} for row in all_rows
    ]
    if not columns and len(names) > SAMPLE_COLUMNS:
        notes.append(
            f"Sample rows show {SAMPLE_COLUMNS} of {len(names)} columns: pick others "
            "with --columns a,b,c."
        )
    document: Dict[str, Any] = {
        "rid": resource.rid,
        "name": resource.display_name,
        "path": resource.path,
        "branch": schema_json.get("branchName") or branch,
        "columns": column_list,
        "sampleRows": sample,
        "schedules": schedules,
        "latestJob": latest_job,
        "notes": notes,
    }
    document = {k: v for k, v in document.items() if v not in (None, [], "")}

    markdown = [f"# Dataset {resource.display_name}", ""]
    markdown += [f"- RID: {resource.rid}", f"- Path: {resource.path}"]
    if document.get("branch"):
        markdown.append(f"- Branch: {document['branch']}")
    markdown += ["", f"## Columns ({len(column_list)})", ""]
    markdown += _table(
        ["Column", "Type", "Nullable"],
        [[c["name"], c["type"], "yes" if c["nullable"] else "no"] for c in column_list],
    )
    markdown += ["", f"## Sample rows ({len(sample)} of at most {rows})", ""]
    if sample:
        shown = [n for n in picked if n in sample[0]]
        markdown += _table(
            shown, [[r.get(n) for n in shown] for r in sample], limit=VALUE_LIMIT
        )
    else:
        markdown.append("(no rows)")
    markdown += ["", f"## Schedules ({len(schedules)})", ""]
    markdown += [f"- {s}" for s in schedules] or ["(none)"]
    markdown += ["", "## Latest job", ""]
    markdown.append(
        f"- {latest_job['rid']}: {latest_job['status']}" if latest_job else "(none)"
    )
    if notes:
        markdown += ["", "## Notes", ""] + [f"- {n}" for n in notes]

    if fixture_dir is not None:
        _write_dataset_fixtures(fixture_dir, resource.display_name, table, schema_json)
    _write(fmt, document, markdown, output, column_list)


def _write_dataset_fixtures(
    directory: Path, name: str, table: Any, schema_json: Dict[str, Any]
) -> None:
    import pyarrow.parquet

    directory.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name) or "dataset"
    pyarrow.parquet.write_table(table, directory / f"{safe}.parquet")
    schema = schema_json.get("schema") or {"fieldSchemaList": []}
    (directory / f"{safe}.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    warn(
        f"Wrote {safe}.parquet and {safe}.schema.json to {directory}. {FIXTURE_WARNING}"
    )


# ------------------------------------------------------------------ folder


@app.command("folder")
@pltr_command(
    sdk="filesystem.Folder.children",
    no_emit_code=(
        "it walks the folder tree level by level; `pltr folder list "
        "--emit-code` shows one listing call."
    ),
)
def folder_context(
    folder_rid: Annotated[
        str, resource_argument("folder", help="Folder or project RID to describe.")
    ],
    depth: Annotated[
        int,
        typer.Option("--depth", min=1, max=10, help="Levels of subfolders to list."),
    ] = 1,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """The resources under a folder or project: type, path and RID.

    \b
      pltr context folder /Space/Project --depth 2
    """
    fmt = format
    service = ResourceService(profile=profile)
    found: List[Dict[str, Any]] = []
    truncated = False
    level = [folder_rid]
    with spinner(f"Listing {folder_rid}..."):
        for _ in range(depth):
            subfolders: List[str] = []
            for parent in level:
                for child in service.list_children(parent):
                    if len(found) >= FOLDER_LIMIT:
                        truncated = True
                        break
                    found.append(
                        {
                            "type": child.type,
                            "name": child.display_name,
                            "path": child.path,
                            "rid": child.rid,
                        }
                    )
                    if child.type == "COMPASS_FOLDER":
                        subfolders.append(child.rid)
            level = subfolders
            if not level or truncated:
                break
    notes = (
        [
            f"Stopped at {FOLDER_LIMIT} resources: describe a subfolder, or lower --depth."
        ]
        if truncated
        else []
    )
    document = {"folder": folder_rid, "resources": found, "notes": notes}
    document = {k: v for k, v in document.items() if v != []}
    markdown = [
        f"# Folder {folder_rid}",
        "",
        f"{len(found)} resources (depth {depth}).",
        "",
    ]
    markdown += _table(
        ["Type", "Path", "RID"], [[r["type"], r["path"], r["rid"]] for r in found]
    )
    if notes:
        markdown += [""] + [f"- {n}" for n in notes]
    _write(fmt, document, markdown, output, found)


# ---------------------------------------------------------------- ontology


def ontology_type(data_type: Any) -> str:
    """A compact ontology data type: ``string``, ``array<string>``, ``object<Employee>``."""
    if not isinstance(data_type, dict):
        return str(data_type)
    kind = str(data_type.get("type", ""))
    for key in ("subType", "itemType", "elementType"):
        if isinstance(data_type.get(key), dict):
            return f"{kind}<{ontology_type(data_type[key])}>"
    target = data_type.get("objectTypeApiName") or data_type.get("objectApiName")
    return f"{kind}<{target}>" if target else kind


def _mentions(document: Any, types: Sequence[str]) -> bool:
    text = json.dumps(document)
    return any(f'"{name}"' in text for name in types)


@app.command("ontology")
@pltr_command(
    sdk=("ontologies.Ontology.get_full_metadata", "ontologies.OntologyObject.list"),
    beta=True,
)
def ontology_context(
    ontology: Annotated[str, typer.Argument(help="Ontology RID or API name.")],
    types: Annotated[
        Optional[str],
        typer.Option(
            "--types",
            help="Comma-separated object types to describe in full (default: a summary).",
        ),
    ] = None,
    rows: RowsOption = 5,
    fixture_dir: FixtureDirOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """[beta] Object types (keys, properties, links), and their actions and queries.

    Without --types: a summary of every object type. With --types: each
    type's primary key, properties and link types, and the action and query
    types that involve them, with their parameters. One API call
    (Ontology.get_full_metadata).

    \b
      pltr context ontology my-ontology
      pltr context ontology my-ontology --types Employee,Department --format json
    """
    fmt = format
    wanted = [t.strip() for t in types.split(",") if t.strip()] if types else []
    if fixture_dir is not None and not wanted:
        raise typer.BadParameter(
            "--fixture-dir needs --types", param_hint="'--fixture-dir'"
        )
    with spinner(f"Reading ontology {ontology}..."):
        metadata = to_jsonable(
            OntologyService(profile=profile).get_full_metadata(ontology)
        )
    object_types: Dict[str, Any] = metadata.get("objectTypes") or {}
    unknown = [t for t in wanted if t not in object_types]
    if unknown:
        raise typer.BadParameter(
            f"no object type {', '.join(unknown)} in {ontology}; "
            f"`pltr context ontology {ontology}` lists them",
            param_hint="'--types'",
        )
    name = (metadata.get("ontology") or {}).get("apiName", ontology)
    markdown = [f"# Ontology {name}", ""]
    document: Dict[str, Any] = {"ontology": name}
    notes: List[str] = []

    if not wanted:
        summary = []
        for api_name in sorted(object_types)[:SUMMARY_LIMIT]:
            entry = object_types[api_name]
            obj = entry.get("objectType") or {}
            summary.append(
                {
                    "apiName": api_name,
                    "primaryKey": obj.get("primaryKey"),
                    "properties": len(obj.get("properties") or {}),
                    "linkTypes": len(entry.get("linkTypes") or []),
                }
            )
        if len(object_types) > SUMMARY_LIMIT:
            notes.append(
                f"Showing {SUMMARY_LIMIT} of {len(object_types)} object types."
            )
        notes.append("Describe some in full with --types A,B.")
        actions = sorted(metadata.get("actionTypes") or {})
        queries = sorted(metadata.get("queryTypes") or {})
        document.update(objectTypes=summary, actionTypes=actions, queryTypes=queries)
        markdown += [f"## Object types ({len(object_types)})", ""]
        markdown += _table(
            ["Object type", "Primary key", "Properties", "Links"],
            [
                [s["apiName"], s["primaryKey"], s["properties"], s["linkTypes"]]
                for s in summary
            ],
        )
        markdown += ["", f"## Action types ({len(actions)})", ""]
        markdown += [", ".join(actions) or "(none)"]
        markdown += ["", f"## Query types ({len(queries)})", ""]
        markdown += [", ".join(queries) or "(none)"]
    else:
        described = []
        for api_name in wanted:
            entry = object_types[api_name]
            obj = entry.get("objectType") or {}
            properties = [
                {"name": p, "type": ontology_type(spec.get("dataType"))}
                for p, spec in (obj.get("properties") or {}).items()
            ]
            links = [
                {
                    "apiName": link.get("apiName"),
                    "objectType": link.get("objectTypeApiName"),
                    "cardinality": link.get("cardinality"),
                }
                for link in entry.get("linkTypes") or []
            ]
            described.append(
                {
                    "apiName": api_name,
                    "primaryKey": obj.get("primaryKey"),
                    "titleProperty": obj.get("titleProperty"),
                    "properties": properties,
                    "linkTypes": links,
                }
            )
            markdown += [f"## {api_name}", ""]
            markdown.append(f"- Primary key: {obj.get('primaryKey')}")
            markdown += ["", "| Property | Type |", "|---|---|"]
            markdown += [f"| {p['name']} | {p['type']} |" for p in properties]
            markdown += ["", "Links:"]
            markdown += [
                f"- {link['apiName']} -> {link['objectType']} ({link['cardinality']})"
                for link in links
            ] or ["- (none)"]
            markdown.append("")

        def parameters(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
            return [
                {
                    "name": param,
                    "type": ontology_type(value.get("dataType")),
                    "required": bool(value.get("required")),
                }
                for param, value in (spec.get("parameters") or {}).items()
            ]

        actions = [
            {"apiName": key, "parameters": parameters(spec)}
            for key, spec in sorted((metadata.get("actionTypes") or {}).items())
            if _mentions(spec, wanted)
        ]
        queries = [
            {"apiName": key, "parameters": parameters(spec)}
            for key, spec in sorted((metadata.get("queryTypes") or {}).items())
            if _mentions(spec, wanted)
        ]
        document.update(objectTypes=described, actionTypes=actions, queryTypes=queries)
        for title, items in (("Action types", actions), ("Query types", queries)):
            markdown += [f"## {title} involving {', '.join(wanted)} ({len(items)})", ""]
            for item in items:
                markdown += [f"### {item['apiName']}", ""]
                markdown += [
                    f"- {p['name']}: {p['type']}{' (required)' if p['required'] else ''}"
                    for p in item["parameters"]
                ] or ["- (no parameters)"]
                markdown.append("")
        if fixture_dir is not None:
            _write_object_fixtures(fixture_dir, ontology, wanted, rows, profile)
    if notes:
        document["notes"] = notes
        markdown += ["", "## Notes", ""] + [f"- {n}" for n in notes]
    main = document.get("objectTypes") or []
    flat = [{k: v for k, v in item.items() if not isinstance(v, list)} for item in main]
    _write(fmt, document, markdown, output, flat)


def _write_object_fixtures(
    directory: Path, ontology: str, types: List[str], rows: int, profile: Optional[str]
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    service = OntologyObjectService(profile=profile)
    for object_type in types:
        page = service.list_objects(ontology, object_type, page_size=rows)
        objects = to_jsonable(list(page.data)[:rows])
        (directory / f"{object_type}.json").write_text(
            json.dumps(objects, indent=2) + "\n"
        )
    warn(f"Wrote {len(types)} object fixture file(s) to {directory}. {FIXTURE_WARNING}")
