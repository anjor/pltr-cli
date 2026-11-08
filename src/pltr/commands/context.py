"""`pltr context`: compact summaries of a dataset, folder or ontology (#194).

Context packs are written for a model to read before it writes code against a
resource: Markdown by default (``--format table``), the same content as JSON
with ``--format json``, and the main list as CSV with ``--format csv``. Nulls,
internal IDs and fields agents don't use are left out. Every list is capped
and long values are cut; the pack says what it cut and how to narrow it, and
a Markdown pack is never longer than :data:`MARKDOWN_BUDGET` bytes.
``--fixture-dir`` also writes the samples to files for tests (a few rows,
never an export).
"""

import difflib
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
        "--rows",
        min=1,
        max=1000,
        help=(
            "Sample rows or objects to fetch (at most 1000). The pack shows at "
            "most 10; --fixture-dir writes all of them."
        ),
    ),
]
FixtureDirOption = Annotated[
    Optional[Path],
    typer.Option(
        "--fixture-dir",
        help=(
            "Also write the samples to this directory for tests (never over "
            "an existing file). They are real Foundry data: keep them out of "
            "git unless you may share them."
        ),
    ),
]

#: A Markdown pack is cut at this many bytes (with a note).
MARKDOWN_BUDGET = 15_000
#: Sample values (Markdown) are cut at this many characters.
VALUE_LIMIT = 40
#: Sample values (JSON) are cut at this many characters.
JSON_VALUE_LIMIT = 200
#: Types longer than this are cut (STRUCTs); `dataset schema get` has them all.
TYPE_LIMIT = 60
#: Columns shown in sample rows unless --columns picks them.
SAMPLE_COLUMNS = 12
#: Sample rows shown in a pack.
PACK_ROWS = 10
#: Columns, properties, folder rows, object types, actions, queries listed.
COLUMN_LIMIT = 300
PROPERTY_LIMIT = 150
FOLDER_LIMIT = 200
SUMMARY_LIMIT = 200
ACTION_LIMIT = 50

FIXTURE_WARNING = (
    "Fixtures contain real Foundry data, which may carry markings: add the "
    "fixture directory to .gitignore unless you may share it."
)


def _cut(text: str, limit: Optional[int]) -> str:
    if limit is None or len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _cell(value: Any, limit: Optional[int] = None) -> str:
    if value is None:
        return ""
    value = to_jsonable(value)
    text = value if isinstance(value, str) else json.dumps(value)
    return _cut(" ".join(str(text).split()), limit).replace("|", "\\|")


def _table(
    headers: Sequence[str], rows: List[Sequence[Any]], limit: Optional[int] = None
) -> List[str]:
    """A Markdown table; ``limit`` cuts long cells (sample values only)."""
    head = " | ".join(_cell(h) for h in headers)
    lines = [f"| {head} |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(v, limit) for v in row) + " |" for row in rows]
    return lines


def _budget(markdown: List[str], hint: str) -> str:
    """The Markdown pack, cut at :data:`MARKDOWN_BUDGET` bytes with a note."""
    text = "\n".join(markdown).rstrip() + "\n"
    if len(text.encode()) <= MARKDOWN_BUDGET:
        return text
    kept: List[str] = []
    size = 0
    for line in markdown:
        size += len(line.encode()) + 1
        if size > MARKDOWN_BUDGET - 300:
            break
        kept.append(line)
    kept += ["", f"(Cut at {MARKDOWN_BUDGET // 1000} KB: {hint})"]
    return "\n".join(kept) + "\n"


def _write(
    fmt: str,
    document: Dict[str, Any],
    markdown: List[str],
    output: Optional[str],
    rows: List[Dict[str, Any]],
    hint: str,
) -> None:
    """table: the Markdown pack; json: the document; csv: its main list."""
    if fmt == "json":
        emit(document, format="json", output=output)
    elif fmt == "csv":
        columns = {key: key for key in rows[0]} if rows else None
        emit(rows, format="csv", output=output, columns=columns)
    else:
        _write_text(_budget(markdown, hint), output)


def _unavailable(section: str, exc: Exception) -> str:
    info = classify_error(exc)
    return f"{section} unavailable ({info.type}): {info.message}"


def _check_new(directory: Path, names: List[str]) -> None:
    existing = [n for n in names if (directory / n).exists()]
    if existing:
        raise typer.BadParameter(
            f"{', '.join(existing)} already exist in {directory}: pltr never "
            "overwrites fixtures. Remove them or pick another directory.",
            param_hint="'--fixture-dir'",
        )


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
    datasets = DatasetService(profile=profile)
    notes: List[str] = []
    fields: List[Dict[str, Any]] = []
    schema_json: Dict[str, Any] = {}
    table: Any = None
    with spinner(f"Describing dataset {dataset_rid}..."):
        resource = ResourceService(profile=profile).get_resource(dataset_rid)
        safe = (
            "".join(
                c if c.isalnum() or c in "-_." else "_" for c in resource.display_name
            )
            or "dataset"
        )
        if fixture_dir is not None:
            _check_new(fixture_dir, [f"{safe}.parquet", f"{safe}.schema.json"])
        try:
            schema_json = to_jsonable(
                datasets.get_dataset_schema(dataset_rid, branch=branch)
            )
            fields = (schema_json.get("schema") or {}).get("fieldSchemaList") or []
        except Exception as exc:
            notes.append(
                _unavailable("schema", exc)
                + " (a files-only or not-yet-built dataset has none: "
                f"`pltr dataset files list {dataset_rid}`)"
            )
        try:
            table = datasets.preview_table(dataset_rid, limit=rows, branch=branch)
        except Exception as exc:
            notes.append(_unavailable("rows", exc))
        try:
            schedules = [
                str(s) for s in datasets.list_schedules(dataset_rid, branch=branch)
            ]
        except Exception as exc:
            schedules = []
            notes.append(_unavailable("schedules", exc))
        latest_job: Optional[Dict[str, Any]] = None
        try:
            job_details = next(
                iter(datasets.list_jobs(dataset_rid, branch=branch, page_size=1)), None
            )
            if job_details is not None:
                job = OrchestrationService(profile=profile).get_job(job_details.job_rid)
                latest_job = {"rid": job.rid, "status": job.job_status}
        except Exception as exc:
            notes.append(_unavailable("jobs", exc))

    column_list = [
        {
            "name": f["name"],
            "type": _cut(type_text(f), TYPE_LIMIT),
            "nullable": bool(f.get("nullable", True)),
        }
        for f in fields
    ]
    if any(len(type_text(f)) > TYPE_LIMIT for f in fields):
        notes.append(
            f"Long types are cut at {TYPE_LIMIT} characters: `pltr dataset schema "
            f"get {dataset_rid}` has them in full."
        )
    if len(column_list) > COLUMN_LIMIT:
        notes.append(
            f"Listing {COLUMN_LIMIT} of {len(column_list)} columns: `pltr dataset "
            f"schema get {dataset_rid}` has them all."
        )
    all_rows = table_rows(table)[1] if table is not None and table.num_columns else []
    names = [c["name"] for c in column_list] or list(all_rows[0] if all_rows else [])
    if columns:
        picked = [c.strip() for c in columns.split(",") if c.strip()]
        unknown = [c for c in picked if names and c not in names]
        if unknown:
            hints = []
            for name in unknown:
                close = difflib.get_close_matches(name, names, 1)
                hints.append(f"{name} (did you mean {close[0]}?)" if close else name)
            raise typer.BadParameter(
                f"no column {', '.join(hints)}", param_hint="'--columns'"
            )
    else:
        picked = names[:SAMPLE_COLUMNS]
        if len(names) > SAMPLE_COLUMNS:
            notes.append(
                f"Sample rows show {SAMPLE_COLUMNS} of {len(names)} columns: pick "
                "others with --columns a,b,c."
            )
    shown_rows = all_rows[:PACK_ROWS]
    if len(all_rows) > PACK_ROWS:
        notes.append(
            f"The pack shows {PACK_ROWS} of {len(all_rows)} sample rows"
            + ("; the fixture has all of them." if fixture_dir else ".")
        )
    sample = [{n: row.get(n) for n in picked if n in row} for row in shown_rows]
    cut_values = False
    for row in sample:
        for key, value in row.items():
            text = to_jsonable(value)
            if isinstance(text, str) and len(text) > JSON_VALUE_LIMIT:
                row[key] = _cut(text, JSON_VALUE_LIMIT)
                cut_values = True
    if cut_values:
        notes.append(
            f"Sample values longer than {JSON_VALUE_LIMIT} characters are cut."
        )

    document: Dict[str, Any] = {
        "rid": resource.rid,
        "name": resource.display_name,
        "path": resource.path,
        "branch": schema_json.get("branchName") or branch,
        "columns": column_list[:COLUMN_LIMIT],
        "sampleRows": sample,
        "schedules": schedules,
        "latestJob": latest_job,
        "notes": notes,
    }
    document = {k: v for k, v in document.items() if v is not None}

    markdown = [f"# Dataset {resource.display_name}", ""]
    markdown += [f"- RID: {resource.rid}", f"- Path: {resource.path}"]
    if document.get("branch"):
        markdown.append(f"- Branch: {document['branch']}")
    if notes:
        markdown += ["", "## Notes", ""] + [f"- {n}" for n in notes]
    markdown += ["", f"## Columns ({len(column_list)})", ""]
    markdown += _table(
        ["Column", "Type", "Nullable"],
        [
            [c["name"], c["type"], "yes" if c["nullable"] else "no"]
            for c in column_list[:COLUMN_LIMIT]
        ],
    )
    markdown += ["", f"## Sample rows ({len(sample)})", ""]
    if sample:
        shown = [n for n in picked if n in sample[0]]
        markdown += _table(
            shown, [[r.get(n) for n in shown] for r in sample], limit=VALUE_LIMIT
        )
    else:
        markdown.append("(no rows)")
    markdown += ["", f"## Schedules ({len(schedules)})", ""]
    markdown += [f"- {s}" for s in schedules[:ACTION_LIMIT]] or ["(none)"]
    markdown += ["", "## Latest job", ""]
    markdown.append(
        f"- {latest_job['rid']}: {latest_job['status']}" if latest_job else "(none)"
    )

    if fixture_dir is not None:
        _write_dataset_fixtures(fixture_dir, safe, table, schema_json)
    _write(
        format,
        document,
        markdown,
        output,
        column_list[:COLUMN_LIMIT],
        f"`pltr dataset schema get {dataset_rid}` has every column",
    )


def _write_dataset_fixtures(
    directory: Path, safe: str, table: Any, schema_json: Dict[str, Any]
) -> None:
    import pyarrow.parquet

    warn(f"Writing fixtures for {safe} to {directory}. {FIXTURE_WARNING}")
    directory.mkdir(parents=True, exist_ok=True)
    schema = schema_json.get("schema") or {"fieldSchemaList": []}
    (directory / f"{safe}.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    if table is None or not table.num_columns:
        warn(f"No rows to sample: wrote only {safe}.schema.json.")
        return
    pyarrow.parquet.write_table(table, directory / f"{safe}.parquet")


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
                if truncated:
                    break
            level = subfolders
            if not level or truncated:
                break
    notes = (
        [
            f"Stopped at {FOLDER_LIMIT} resources: describe a subfolder, or "
            "lower --depth."
        ]
        if truncated
        else []
    )
    document = {"folder": folder_rid, "resources": found, "notes": notes}
    markdown = [
        f"# Folder {folder_rid}",
        "",
        f"{len(found)} resources (depth {depth}).",
        "",
    ]
    if notes:
        markdown += [f"- {n}" for n in notes] + [""]
    markdown += _table(
        ["Type", "Path", "RID"], [[r["type"], r["path"], r["rid"]] for r in found]
    )
    _write(format, document, markdown, output, found, "describe a subfolder")


# ---------------------------------------------------------------- ontology


def ontology_type(data_type: Any) -> str:
    """A compact ontology data type: ``string``, ``array<string>``, ``object<Employee>``."""
    if not isinstance(data_type, dict):
        return str(data_type)
    kind = str(data_type.get("type", ""))
    for key in ("subType", "itemType", "elementType"):
        if isinstance(data_type.get(key), dict):
            return f"{kind}<{ontology_type(data_type[key])}>"
    target = (
        data_type.get("objectTypeApiName")
        or data_type.get("objectApiName")
        or data_type.get("interfaceTypeApiName")
    )
    return f"{kind}<{target}>" if target else kind


#: Keys that name an object type in action and query definitions.
_TYPE_KEYS = (
    "objectTypeApiName",
    "objectApiName",
    "aSideObjectTypeApiName",
    "bSideObjectTypeApiName",
)


def _referenced_types(value: Any) -> set:
    """Every object type an action or query definition refers to."""
    found: set = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _TYPE_KEYS and isinstance(item, str):
                found.add(item)
            else:
                found |= _referenced_types(item)
    elif isinstance(value, list):
        for item in value:
            found |= _referenced_types(item)
    return found


def _parameters(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "name": param,
            "type": ontology_type(value.get("dataType")),
            "required": bool(value.get("required")),
        }
        for param, value in (spec.get("parameters") or {}).items()
    ]


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
    types that refer to them, with their parameters. One API call
    (Ontology.get_full_metadata); --fixture-dir also lists --rows objects of
    each type.

    \b
      pltr context ontology my-ontology
      pltr context ontology my-ontology --types Employee,Department --format json
    """
    wanted = [t.strip() for t in types.split(",") if t.strip()] if types else []
    if fixture_dir is not None and not wanted:
        raise typer.BadParameter(
            "--fixture-dir needs --types", param_hint="'--fixture-dir'"
        )
    if fixture_dir is not None:
        _check_new(fixture_dir, [f"{t}.json" for t in wanted])
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
    body: List[str] = []
    document: Dict[str, Any] = {"ontology": name}
    notes: List[str] = []
    all_actions = metadata.get("actionTypes") or {}
    all_queries = metadata.get("queryTypes") or {}

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
                f"Showing {SUMMARY_LIMIT} of {len(object_types)} object types: "
                f"`pltr ontology object-type-list {ontology}` lists them all."
            )
        actions = sorted(all_actions)
        queries = sorted(all_queries)
        for label, items in (("action", actions), ("query", queries)):
            if len(items) > SUMMARY_LIMIT:
                notes.append(f"Showing {SUMMARY_LIMIT} of {len(items)} {label} types.")
        notes.append("Describe object types in full with --types A,B.")
        document.update(
            objectTypes=summary,
            actionTypes=actions[:SUMMARY_LIMIT],
            queryTypes=queries[:SUMMARY_LIMIT],
        )
        body += [f"## Object types ({len(object_types)})", ""]
        body += _table(
            ["Object type", "Primary key", "Properties", "Links"],
            [
                [s["apiName"], s["primaryKey"], s["properties"], s["linkTypes"]]
                for s in summary
            ],
        )
        body += ["", f"## Action types ({len(actions)})", ""]
        body += [", ".join(actions[:SUMMARY_LIMIT]) or "(none)"]
        body += ["", f"## Query types ({len(queries)})", ""]
        body += [", ".join(queries[:SUMMARY_LIMIT]) or "(none)"]
    else:
        described = []
        for api_name in wanted:
            entry = object_types[api_name]
            obj = entry.get("objectType") or {}
            all_properties = list((obj.get("properties") or {}).items())
            properties = [
                {"name": p, "type": ontology_type(spec.get("dataType"))}
                for p, spec in all_properties[:PROPERTY_LIMIT]
            ]
            if len(all_properties) > PROPERTY_LIMIT:
                notes.append(
                    f"{api_name}: showing {PROPERTY_LIMIT} of {len(all_properties)} "
                    f"properties (`pltr ontology object-type-get {ontology} "
                    f"{api_name}` has them all)."
                )
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
            body += [f"## {api_name}", ""]
            body.append(f"- Primary key: {obj.get('primaryKey')}")
            body += ["", "| Property | Type |", "|---|---|"]
            body += [f"| {p['name']} | {p['type']} |" for p in properties]
            body += ["", "Links:"]
            body += [
                f"- {link['apiName']} -> {link['objectType']} ({link['cardinality']})"
                for link in links
            ] or ["- (none)"]
            body.append("")

        def involving(specs: Dict[str, Any], label: str) -> List[Dict[str, Any]]:
            matched = [
                {"apiName": spec.get("apiName", key), "parameters": _parameters(spec)}
                for key, spec in sorted(specs.items())
                if _referenced_types(spec) & set(wanted)
            ]
            if len(matched) > ACTION_LIMIT:
                notes.append(
                    f"Showing {ACTION_LIMIT} of {len(matched)} {label} types: "
                    "narrow --types."
                )
            return matched[:ACTION_LIMIT]

        actions = involving(all_actions, "action")
        queries = involving(all_queries, "query")
        document.update(objectTypes=described, actionTypes=actions, queryTypes=queries)
        for title, items in (("Action types", actions), ("Query types", queries)):
            body += [f"## {title} involving {', '.join(wanted)} ({len(items)})", ""]
            for item in items:
                body += [f"### {item['apiName']}", ""]
                body += [
                    f"- {p['name']}: {p['type']}{' (required)' if p['required'] else ''}"
                    for p in item["parameters"]
                ] or ["- (no parameters)"]
                body.append("")
        if fixture_dir is not None:
            _write_object_fixtures(fixture_dir, ontology, wanted, rows, profile)
    document["notes"] = notes
    markdown = [f"# Ontology {name}", ""]
    if notes:
        markdown += ["## Notes", ""] + [f"- {n}" for n in notes] + [""]
    markdown += body
    main = document.get("objectTypes") or []
    flat = [{k: v for k, v in item.items() if not isinstance(v, list)} for item in main]
    _write(format, document, markdown, output, flat, "narrow with --types")


def _write_object_fixtures(
    directory: Path, ontology: str, types: List[str], rows: int, profile: Optional[str]
) -> None:
    warn(
        f"Writing object fixtures for {', '.join(types)} to {directory}. "
        f"{FIXTURE_WARNING}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    service = OntologyObjectService(profile=profile)
    for object_type in types:
        page = service.list_objects(ontology, object_type, page_size=rows)
        objects = to_jsonable(list(page.data)[:rows])
        (directory / f"{object_type}.json").write_text(
            json.dumps(objects, indent=2) + "\n"
        )
