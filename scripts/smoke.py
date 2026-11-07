"""Live smoke test: run the real pltr CLI against a Foundry stack.

The maintainer runs this against a real stack (#189); the result table can be
pasted into a PR:

    uv run python scripts/smoke.py --profile dev                 # read-only checks
    uv run python scripts/smoke.py --config smoke.toml --markdown > smoke.md
    uv run python scripts/smoke.py --allow-writes --scratch-folder ri.compass.main.folder.<uuid>
    uv run python scripts/smoke.py --only dataset sql            # some groups only
    uv run python scripts/smoke.py --list                        # every check and its command

Every check runs `pltr` in a subprocess with stdin closed (so nothing can
prompt) and `--format json` (one check uses `--format csv`). Besides the
result, it checks the output contract: the exit code, exactly one JSON
document on stdout, JSON Lines on stderr and, for a failure, the structured
error (`type`, `errorName`, `exitCode`).

Inputs (RIDs, the ontology, the object type, the SQL table, ...) come from a
config file (`--config`, default `./smoke.toml`; see
`scripts/smoke.example.toml`), from `--<input>` flags or from
`--set KEY=VALUE`. Many are found by earlier checks when you leave them out:
the first ontology and object type, an object, a recent build, its jobs and
schedule, ... A check whose input is missing is reported as skipped, not
failed.

Writes are opt-in: `--allow-writes --scratch-folder RID` creates a folder
inside the scratch folder, a dataset and a streaming dataset in it, uploads,
downloads, commits, branches and copies, and moves everything it created to
the trash at the end. Checks that need admin permissions (users, groups,
markings, organizations, audit logs; with --allow-writes also replacing a
space, organization and marking you name with their current values) run only
with --include-admin. Nothing is ever permanently deleted.

See docs/development/live-verification.md.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    TextIO,
    Tuple,
    Union,
)

PASS, FAIL, SKIP = "pass", "fail", "skip"

DEFAULT_CONFIG = "smoke.toml"
DEFAULT_TIMEOUT = 600.0
EXIT_INTERRUPTED = 130

ROOT_FOLDER_RID = "ri.compass.main.folder.0"
# A well-formed folder RID that no stack has.
MISSING_FOLDER_RID = "ri.compass.main.folder.00000000-0000-4000-8000-000000000000"
SMOKE_BRANCH = "pltr-smoke"

# {namespace.key}: a value from the config, the run, an earlier check or a
# DERIVED rule. JSON literals ('{"type": ...}') never match.
PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*(?:\.[A-Za-z0-9_]+)+)\}")

# Credentials pltr reads from the environment (removed for the checks that
# bring their own).
AUTH_VARIABLES = (
    "PLTR_PROFILE",
    "FOUNDRY_HOST",
    "FOUNDRY_HOSTNAME",
    "FOUNDRY_TOKEN",
    "FOUNDRY_CLIENT_ID",
    "FOUNDRY_CLIENT_SECRET",
)

# Files the write checks upload (paths relative to the run's temp directory).
UPLOAD_FILES = {
    "upload/smoke.csv": "id,name,value\n1,alpha,1.5\n2,beta,2.5\n3,gamma,3.5\n",
    "upload/smoke-append.csv": "id,name,value\n4,delta,4.5\n",
    "upload/smoke-txn.csv": "id,name,value\n5,epsilon,5.5\n",
    "upload/smoke-dir/a.csv": "id,name,value\n6,zeta,6.5\n",
    "upload/smoke-dir/b.csv": "id,name,value\n7,eta,7.5\n",
}
UPLOAD_COLUMNS = ["id", "name", "value"]

STREAM_SCHEMA = json.dumps(
    {
        "fields": [
            {
                "name": "id",
                "schema": {"nullable": False, "dataType": {"type": "long"}},
            },
            {
                "name": "value",
                "schema": {"nullable": True, "dataType": {"type": "string"}},
            },
        ],
        "keyFieldNames": ["id"],
    }
)
STREAM_RECORD = json.dumps({"id": 1, "value": "pltr smoke test"})
COUNT_AGGREGATION = json.dumps([{"type": "count", "name": "count"}])


class ConfigError(Exception):
    """Bad configuration or arguments (exit code 2)."""


class Unexpected(Exception):
    """The command succeeded, but its output isn't what the check expects."""


# ---------------------------------------------------------------- inputs


@dataclasses.dataclass(frozen=True)
class Input:
    """An input the user can set in the config file or with a flag."""

    key: str
    help: str


INPUTS: Tuple[Input, ...] = (
    Input(
        "dataset.rid",
        "A dataset you can read that has files and a schema (a tabular "
        "dataset): ri.foundry.main.dataset.<uuid>.",
    ),
    Input("dataset.branch", "A branch of it. Found automatically."),
    Input(
        "dataset.file_path",
        "A file in it to download. Found automatically (the smallest file "
        "on the first page).",
    ),
    Input(
        "sql.table",
        "A dataset to query, by RID or path: the SQL checks run "
        "SELECT * FROM `<table>` LIMIT 10.",
    ),
    Input("sql.query", "A complete SQL query to run instead."),
    Input(
        "ontology.name",
        "Ontology API name or RID. Found automatically (the first one).",
    ),
    Input(
        "ontology.object_type",
        "Object type API name. Found automatically (the first one).",
    ),
    Input(
        "ontology.primary_key",
        "Primary key of an object of that type. Found automatically.",
    ),
    Input(
        "ontology.link_type",
        "Outgoing link type API name of that object type. Found automatically.",
    ),
    Input(
        "ontology.where",
        "Search query (SearchJsonQueryV2 JSON) for object-search. Default: "
        "eq on the object's primary key.",
    ),
    Input(
        "action.name",
        "Action type API name in that ontology: validated, never applied.",
    ),
    Input("action.parameters", "Its parameters as a JSON object."),
    Input(
        "orchestration.build_rid",
        "A build. Found automatically (the most recent one started in the "
        "last 30 days).",
    ),
    Input(
        "orchestration.schedule_rid",
        "A schedule. Found automatically (from the dataset or the build).",
    ),
    Input(
        "filesystem.folder_rid",
        "A folder or project to read. Default: the scratch folder.",
    ),
    Input("functions.query", "Functions query API name (read-only)."),
    Input(
        "functions.parameters",
        "JSON parameters to execute that query with (the execute checks are "
        "skipped without them; {} for none).",
    ),
    Input("media_sets.rid", "Media set RID (ri.mio.main.media-set.<uuid>)."),
    Input("media_sets.item_path", "Path of an item in that media set."),
    Input("aip_agents.agent_rid", "AIP Agent RID."),
    Input("widgets.widget_set_rid", "Widget set RID."),
    Input("third_party_apps.application_rid", "Third-party application RID."),
    Input("connectivity.connection_rid", "Data Connection source RID."),
    Input("data_health.check_rid", "Data health check RID."),
    Input("models.model_rid", "Model RID."),
    Input("streams.dataset_rid", "Streaming dataset RID."),
    Input("streams.branch", "Branch of its stream (usually master)."),
    Input(
        "language_models.anthropic_model",
        "Anthropic model API name: one short message is sent to it.",
    ),
    Input(
        "language_models.embedding_model",
        "OpenAI embedding model API name: one short text is embedded.",
    ),
    Input(
        "admin.organization_rid",
        "Organization RID for the admin checks. Default: yours.",
    ),
    Input(
        "admin.replace_space_rid",
        "--include-admin --allow-writes: a space to replace with its current "
        "values (checks that nothing changes).",
    ),
    Input(
        "admin.replace_organization_rid",
        "--include-admin --allow-writes: an organization to replace with its "
        "current values.",
    ),
    Input(
        "admin.replace_marking_id",
        "--include-admin --allow-writes: a marking to replace with its current values.",
    ),
    Input(
        "writes.scratch_folder",
        "Folder or project the write checks may create things in (--scratch-folder).",
    ),
    Input(
        "writes.space_rid",
        "A space the write checks may create a project in (and move it to the trash).",
    ),
)
INPUT_KEYS = {spec.key: spec for spec in INPUTS}


def _sql_query(table: Any) -> str:
    return f"SELECT * FROM `{str(table).strip('`')}` LIMIT 10"


def _where_primary_key(prop: Any, value: Any) -> str:
    return json.dumps({"type": "eq", "field": prop, "value": value})


# Keys computed from other keys when they aren't set or captured.
DERIVED: Dict[str, Tuple[Tuple[str, ...], Callable[..., Any]]] = {
    "sql.query": (("sql.table",), _sql_query),
    "ontology.where": (
        ("ontology.pk_property", "ontology.primary_key"),
        _where_primary_key,
    ),
    "filesystem.folder_rid": (("writes.scratch_folder",), lambda rid: rid),
}

# Resources the write checks create, and the created folder they live in.
CREATED_RESOURCES: Dict[str, Optional[str]] = {
    "created.folder": None,
    "created.dataset": "created.folder",
    "created.dataset_copy": "created.folder",
    "created.stream_dataset": "created.folder",
    "created.project": None,
}


def _text(value: Any) -> str:
    """A value as a command-line argument."""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, bool)) or value is None:
        return json.dumps(value)
    return str(value)


class Context:
    """Values for the placeholders in the checks' command lines.

    A key's value comes from, in order: the config file and flags
    (``configured``), the run itself (``run.*``), an earlier check's output
    (``captured``), or a rule that derives it from other keys (``DERIVED``).
    """

    def __init__(self, configured: Mapping[str, Any], run: Mapping[str, Any]):
        self.configured = dict(configured)
        self.run = dict(run)
        self.captured: Dict[str, Any] = {}

    def lookup(self, key: str) -> Tuple[bool, Any]:
        for source in (self.configured, self.run, self.captured):
            if key in source:
                return True, source[key]
        rule = DERIVED.get(key)
        if rule is None:
            return False, None
        deps, derive = rule
        values = []
        for dep in deps:
            found, value = self.lookup(dep)
            if not found:
                return False, None
            values.append(value)
        return True, derive(*values)

    def has(self, key: str) -> bool:
        return self.lookup(key)[0]

    def get(self, key: str) -> Any:
        found, value = self.lookup(key)
        if not found:
            raise KeyError(key)
        return value

    def is_configured(self, key: str) -> bool:
        return key in self.configured

    def capture(self, key: str, value: Any) -> None:
        """Remember a value an earlier check found; set values and the first find win."""
        if value is None or value == "" or value == [] or value == {}:
            return
        if key in self.configured or key in self.captured:
            return
        self.captured[key] = value

    def render(self, template: str) -> str:
        return PLACEHOLDER.sub(lambda m: _text(self.get(m.group(1))), template)


# ---------------------------------------------------------------- output paths


_MISSING = object()


def get_path(doc: Any, path: str, default: Any = None) -> Any:
    """Follow a dotted path ("data.0.name") through dicts and lists."""
    current = doc
    for part in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return default
        elif isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
        else:
            return default
    return current


def _data_list(doc: Any) -> List[Any]:
    if not isinstance(doc, dict) or not isinstance(doc.get("data"), list):
        raise Unexpected('the output is not {"data": [...]}')
    return doc["data"]


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _short(text: Any, limit: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


# ---------------------------------------------------------------- validators

Validator = Callable[[Any, Context], Optional[str]]
Capture = Union[str, Callable[[Any], Any]]


def has(*paths: str) -> Validator:
    """The output is a JSON object with these (dotted) paths."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        if not isinstance(doc, dict):
            raise Unexpected(f"the output is not a JSON object: {_short(doc, 60)}")
        missing = [p for p in paths if get_path(doc, p, _MISSING) is _MISSING]
        if missing:
            raise Unexpected(f"no {', '.join(missing)} in the output")
        return None

    return validate


def equals(path: str, template: str) -> Validator:
    """The value at path equals the rendered template (compared as text)."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        expected = ctx.render(template)
        actual = get_path(doc, path, _MISSING)
        if actual is _MISSING:
            raise Unexpected(f"no {path} in the output")
        if _text(actual) != expected:
            raise Unexpected(f"{path} is {_short(actual, 80)!r}, expected {expected!r}")
        return None

    return validate


def one_of(path: str, *allowed: str) -> Validator:
    """The value at path is one of these; it is noted."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        actual = get_path(doc, path, _MISSING)
        if actual not in allowed:
            shown = "nothing" if actual is _MISSING else repr(actual)
            raise Unexpected(f"{path} is {shown}, expected one of {', '.join(allowed)}")
        return f"{path} {actual}"

    return validate


def paged(min_items: int = 0) -> Validator:
    """The API's paged shape: {"data": [...], "nextPageToken"?: "..."}."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        data = _data_list(doc)
        token = doc.get("nextPageToken")
        if token is not None and not isinstance(token, str):
            raise Unexpected("nextPageToken is not a string")
        if len(data) < min_items:
            raise Unexpected(
                f"{_count(len(data), 'item')}, expected at least {min_items}"
            )
        return _count(len(data), "item") + (", more pages" if token else "")

    return validate


def data_map(key_template: str) -> Validator:
    """A batch response {"data": {"<id>": {...}}} that includes this id."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        data = doc.get("data") if isinstance(doc, dict) else None
        if not isinstance(data, dict):
            raise Unexpected('the output is not {"data": {...}}')
        key = ctx.render(key_template)
        if key not in data:
            raise Unexpected(f"{key} is not in the response's data")
        return _count(len(data), "item")

    return validate


def contains(template: str, field: str) -> Validator:
    """Some item of the paged output has item[field] == the rendered template."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        wanted = ctx.render(template)
        if not any(
            isinstance(item, dict) and _text(item.get(field)) == wanted
            for item in _data_list(doc)
        ):
            raise Unexpected(f"no item with {field} {wanted!r} in the output")
        return None

    return validate


def is_null(doc: Any, ctx: Context) -> Optional[str]:
    if doc is not None:
        raise Unexpected(f"expected null, got {_short(doc, 60)}")
    return None


def any_json(doc: Any, ctx: Context) -> Optional[str]:
    return "null" if doc is None else None


def all_items(field: str, template: str) -> Validator:
    """Every item of the paged output has item[field] == the rendered template."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        wanted = ctx.render(template)
        other = [
            item.get(field)
            for item in _data_list(doc)
            if isinstance(item, dict) and _text(item.get(field)) != wanted
        ]
        if other:
            raise Unexpected(f"an item has {field} {other[0]!r}, expected {wanted!r}")
        return None

    return validate


def none_deleted(doc: Any, ctx: Context) -> Optional[str]:
    if any(isinstance(m, dict) and m.get("deleted") for m in _data_list(doc)):
        raise Unexpected("--exclude-deleted listed a deleted marking")
    return None


def note(path: str, label: str) -> Validator:
    """Report the value at path, if any."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        value = get_path(doc, path, _MISSING)
        return None if value is _MISSING else f"{label} {_short(_text(value), 60)}"

    return validate


def describe_verify(doc: Any, ctx: Context) -> Optional[str]:
    user = doc.get("user") or {}
    source = doc.get("authSource") or {}
    via = ", ".join(str(source[k]) for k in ("kind", "authType") if source.get(k))
    return f"user {user.get('username', user.get('id'))} ({via})"


def rows(min_rows: int = 0, max_rows: Optional[int] = None) -> Validator:
    """{"data": [{column: value}, ...]}: query results and dataset previews."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        data = _data_list(doc)
        if not all(isinstance(row, dict) for row in data):
            raise Unexpected("a row is not a JSON object")
        if len(data) < min_rows:
            raise Unexpected(
                f"{_count(len(data), 'row')}, expected at least {min_rows}"
            )
        if max_rows is not None and len(data) > max_rows:
            raise Unexpected(f"{_count(len(data), 'row')}, expected at most {max_rows}")
        columns = len(data[0]) if data else 0
        return f"{_count(len(data), 'row')}, {_count(columns, 'column')}"

    return validate


def csv_table(max_rows: int) -> Validator:
    """CSV with a header row (the document is the parsed rows)."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        header, body = doc[0], doc[1:]
        if not header or not all(header):
            raise Unexpected("the CSV header has an empty column name")
        if any(len(row) != len(header) for row in body):
            raise Unexpected(
                "a CSV row has a different number of fields than the header"
            )
        if len(body) > max_rows:
            raise Unexpected(f"{_count(len(body), 'row')}, expected at most {max_rows}")
        return f"{_count(len(body), 'row')}, {_count(len(header), 'column')}"

    return validate


def preview_columns(doc: Any, ctx: Context) -> Optional[str]:
    """The CSV files the write checks uploaded are read with their columns."""
    data = _data_list(doc)
    if not data:
        raise Unexpected("no rows: the uploaded CSV files weren't read")
    first = data[0]
    if not isinstance(first, dict) or sorted(first) != sorted(UPLOAD_COLUMNS):
        raise Unexpected(f"columns are {sorted(first)}, expected {UPLOAD_COLUMNS}")
    headers = sum(1 for row in data if row.get("id") == "id")
    notes = _count(len(data), "row")
    return notes + (f", {headers} header rows read as data" if headers else "")


def schema_fields(*names: str) -> Validator:
    def validate(doc: Any, ctx: Context) -> Optional[str]:
        fields = get_path(doc, "schema.fieldSchemaList", _MISSING)
        if not isinstance(fields, list):
            raise Unexpected("no schema.fieldSchemaList in the output")
        found = [f.get("name") for f in fields if isinstance(f, dict)]
        if names and found != list(names):
            raise Unexpected(f"fields are {found}, expected {list(names)}")
        return _count(len(found), "field")

    return validate


def objects_with_properties(doc: Any, ctx: Context) -> Optional[str]:
    """Search found objects, with their properties (select [] = every property)."""
    data = _data_list(doc)
    if not data and not ctx.is_configured("ontology.where"):
        raise Unexpected("searching by the object's primary key found nothing")
    if data and not any(not str(k).startswith("__") for k in data[0]):
        raise Unexpected("the objects have no properties (only __ fields)")
    total = doc.get("totalCount")
    return _count(len(data), "object") + (f", totalCount {total}" if total else "")


def same_file(downloaded: str, uploaded: str) -> Validator:
    def validate(doc: Any, ctx: Context) -> Optional[str]:
        got = Path(ctx.render(downloaded))
        if not got.is_file():
            raise Unexpected(f"{got.name} wasn't written")
        if got.read_bytes() != Path(ctx.render(uploaded)).read_bytes():
            raise Unexpected(f"{got.name} differs from the uploaded file")
        return None

    return validate


def same_tree(downloaded: str, uploaded: str) -> Validator:
    def validate(doc: Any, ctx: Context) -> Optional[str]:
        got, want = Path(ctx.render(downloaded)), Path(ctx.render(uploaded))
        expected = sorted(p.relative_to(want) for p in want.rglob("*") if p.is_file())
        written = sorted(p.relative_to(got) for p in got.rglob("*") if p.is_file())
        if written != expected:
            raise Unexpected(
                f"downloaded {[str(p) for p in written]}, expected {[str(p) for p in expected]}"
            )
        for rel in expected:
            if (got / rel).read_bytes() != (want / rel).read_bytes():
                raise Unexpected(f"{rel} differs from the uploaded file")
        return _count(len(written), "file")

    return validate


def downloaded_size(target: str) -> Validator:
    """The downloaded file has the size the API reported (sizeBytes)."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        path = Path(ctx.render(target))
        if not path.is_file():
            raise Unexpected("the file wasn't written")
        size = path.stat().st_size
        reported = doc.get("sizeBytes") if isinstance(doc, dict) else None
        if reported is not None and str(reported) != str(size):
            raise Unexpected(
                f"wrote {size} bytes, the API reported sizeBytes {reported}"
            )
        return f"{size} bytes"

    return validate


def unchanged(before_key: str, *fields: str) -> Validator:
    """The object kept these fields' values (compare with a captured copy)."""

    def validate(doc: Any, ctx: Context) -> Optional[str]:
        before = ctx.get(before_key)
        changed = [
            f
            for f in fields
            if get_path(doc, f, _MISSING) != get_path(before, f, _MISSING)
        ]
        if changed:
            raise Unexpected(
                "changed by the replace: "
                + ", ".join(
                    f"{f} {get_path(before, f)!r} -> {get_path(doc, f)!r}"
                    for f in changed
                )
            )
        return "unchanged: " + ", ".join(fields)

    return validate


# ---------------------------------------------------------------- captures


def smallest_file(doc: Any) -> Any:
    """The path of the smallest file on the page (keeps downloads small)."""
    files = [f for f in _data_list(doc) if isinstance(f, dict) and f.get("path")]

    def size(f: Dict[str, Any]) -> int:
        try:
            return int(f.get("sizeBytes") or 0)
        except (TypeError, ValueError):
            return 0

    return min(files, key=size)["path"] if files else None


def first_model_id(doc: Any) -> Any:
    """language-models list items are the endpoint's own objects."""
    for item in _data_list(doc)[:1]:
        if isinstance(item, dict):
            for field in ("apiName", "id", "rid", "modelRid", "name"):
                if item.get(field):
                    return item[field]
    return None


def whole(doc: Any) -> Any:
    return doc


def extract(doc: Any, how: Capture) -> Any:
    if callable(how):
        try:
            return how(doc)
        except Unexpected:
            return None
    return get_path(doc, how)


# ---------------------------------------------------------------- checks


@dataclasses.dataclass(frozen=True)
class Check:
    """One pltr command line, what it must print, and what it finds for later checks.

    ``argv`` follows ``pltr``; ``--format json`` (or ``output``) and
    ``--profile`` are added. ``{key}`` placeholders are filled from the
    Context; a check whose placeholders can't be filled is skipped.
    """

    id: str
    argv: Tuple[str, ...]
    about: str
    expect: Tuple[Validator, ...] = ()
    capture: Mapping[str, Capture] = dataclasses.field(default_factory=dict)
    exit_codes: Tuple[int, ...] = (0,)
    error_types: Tuple[str, ...] = ()
    output: str = "json"
    write: bool = False
    admin: bool = False
    cleanup: bool = False
    trashes: Tuple[str, ...] = ()
    env: Mapping[str, str] = dataclasses.field(default_factory=dict)
    isolated_auth: bool = False
    needs: Tuple[str, ...] = ()

    @property
    def group(self) -> str:
        return self.id.split(".", 1)[0]

    @property
    def kind(self) -> str:
        if self.write and self.admin:
            return "admin write"
        return "write" if self.write else "admin" if self.admin else "read"

    def placeholders(self) -> List[str]:
        """The keys this check needs, in order of appearance."""
        keys: List[str] = []
        for template in (*self.argv, *self.env.values()):
            keys.extend(PLACEHOLDER.findall(template))
        keys.extend(self.needs)
        return list(dict.fromkeys(keys))


def _check(id: str, argv: str, about: str, **kwargs: Any) -> Check:
    """A check whose argv is written as one shell-quoted string."""
    return Check(id=id, argv=tuple(shlex.split(argv)), about=about, **kwargs)


C = _check
DS = "{dataset.rid}"
ONT = "{ontology.name} {ontology.object_type}"
NEW_DS = "{created.dataset}"

CHECKS: Tuple[Check, ...] = (
    # ------------------------------------------------ authentication, contract
    C(
        "verify",
        "verify",
        "Credentials work; reports the auth source and the current user.",
        expect=(has("authSource.kind", "user.id"), describe_verify),
        capture={
            "auth.host": "authSource.host",
            "user.id": "user.id",
            "user.username": "user.username",
            "admin.organization_rid": "user.organization",
        },
    ),
    C(
        "auth.invalid-token",
        "verify",
        "A rejected token (HTTP 401) exits 3 with auth_error "
        "(environment-variable auth, no profile).",
        isolated_auth=True,
        env={
            "FOUNDRY_HOST": "{auth.host}",
            "FOUNDRY_TOKEN": "pltr-smoke-invalid-token",
        },
        exit_codes=(3,),
        error_types=("auth_error",),
    ),
    C(
        "auth.invalid-oauth-client",
        "verify",
        "Rejected OAuth client credentials (the token request fails) exit 3 "
        "with auth_error.",
        isolated_auth=True,
        env={
            "FOUNDRY_HOST": "{auth.host}",
            "FOUNDRY_CLIENT_ID": "pltr-smoke-invalid-client",
            "FOUNDRY_CLIENT_SECRET": "pltr-smoke-invalid-secret",
        },
        exit_codes=(3,),
        error_types=("auth_error",),
    ),
    C(
        "contract.not-found",
        f"folder get {MISSING_FOLDER_RID}",
        "An API error is one structured JSON error on stderr, with errorName "
        "(404: exit 5; a stack that answers 403: exit 4).",
        exit_codes=(5, 4),
        error_types=("not_found", "permission_denied"),
    ),
    C(
        "contract.invalid-rid",
        "dataset get not-a-rid",
        "An invalid RID is a usage error (exit 2), caught before any request.",
        exit_codes=(2,),
        error_types=("usage_error",),
    ),
    C(
        "contract.needs-yes",
        f"resource delete {MISSING_FOLDER_RID}",
        "A destructive command without --yes and no terminal exits 2 "
        "(confirmation_required) instead of prompting.",
        exit_codes=(2,),
        error_types=("confirmation_required",),
    ),
    # ------------------------------------------------ datasets
    C(
        "dataset.get",
        f"dataset get {DS}",
        "Dataset metadata.",
        expect=(equals("rid", DS), note("name", "name")),
    ),
    C(
        "dataset.branches-list",
        f"dataset branches list {DS}",
        "Branches, one page.",
        expect=(paged(min_items=1),),
        capture={"dataset.branch": "data.0.name"},
    ),
    C(
        "dataset.branches-get",
        f"dataset branches get {DS} {{dataset.branch}}",
        "One branch.",
        expect=(equals("name", "{dataset.branch}"),),
    ),
    C(
        "dataset.files-list",
        f"dataset files list {DS} --page-size 20",
        "Files, one page of 20 (--page-size).",
        expect=(paged(),),
        capture={"dataset.file_path": smallest_file},
    ),
    C(
        "dataset.files-info",
        f"dataset files info {DS} {{dataset.file_path}}",
        "A file's metadata.",
        expect=(equals("path", "{dataset.file_path}"), note("sizeBytes", "sizeBytes")),
    ),
    C(
        "dataset.files-get",
        f"dataset files get {DS} {{dataset.file_path}} {{run.tmp}}/download/dataset-file",
        "Downloads the file (streamed); its size matches sizeBytes.",
        expect=(
            equals("path", "{dataset.file_path}"),
            downloaded_size("{run.tmp}/download/dataset-file"),
        ),
    ),
    C(
        "dataset.transactions-list",
        f"dataset transactions list {DS} --page-size 5",
        "[beta] Transactions of every branch, newest first.",
        expect=(paged(),),
        capture={"dataset.transaction_rid": "data.0.rid"},
    ),
    C(
        "dataset.transactions-status",
        f"dataset transactions status {DS} {{dataset.transaction_rid}}",
        "One transaction.",
        expect=(equals("rid", "{dataset.transaction_rid}"), note("status", "status")),
    ),
    C(
        "dataset.schema-get",
        f"dataset schema get {DS}",
        "The schema (GA Dataset.get_schema).",
        expect=(schema_fields(),),
    ),
    C(
        "dataset.read-json",
        f"dataset preview {DS} --limit 5",
        "Reads rows (Dataset.read_table, Arrow) as JSON.",
        expect=(rows(max_rows=5),),
    ),
    C(
        "dataset.read-csv",
        f"dataset preview {DS} --limit 5",
        "Reads rows as CSV.",
        output="csv",
        expect=(csv_table(max_rows=5),),
    ),
    C(
        "dataset.schedules-list",
        f"dataset schedules list {DS}",
        "Schedules that build the dataset (RIDs).",
        expect=(paged(),),
        capture={"orchestration.schedule_rid": "data.0"},
    ),
    C(
        "dataset.jobs-list",
        f"dataset jobs list {DS} --page-size 5",
        "[beta] Jobs that built the dataset.",
        expect=(paged(),),
    ),
    # ------------------------------------------------ SQL
    C(
        "sql.execute",
        "sql execute {sql.query}",
        "Runs a query and prints its rows (Arrow decoding).",
        expect=(rows(),),
    ),
    C(
        "sql.submit",
        "sql submit {sql.query}",
        "Starts a query without waiting.",
        expect=(one_of("type", "running", "succeeded"),),
        capture={"sql.query_id": "queryId"},
    ),
    C(
        "sql.status",
        "sql status {sql.query_id}",
        "The query's status.",
        expect=(one_of("type", "running", "succeeded"),),
    ),
    C(
        "sql.wait",
        "sql wait {sql.query_id} --timeout 300",
        "Waits for the query, then prints its rows.",
        expect=(rows(),),
        capture={"sql.query_finished": lambda doc: "yes"},
    ),
    C(
        "sql.results",
        "sql results {sql.query_id}",
        "The rows of the finished query.",
        expect=(rows(),),
    ),
    # ------------------------------------------------ ontology objects
    C(
        "ontology.list",
        "ontology list",
        "Ontologies you can see.",
        expect=(paged(min_items=1),),
        capture={"ontology.name": "data.0.apiName"},
    ),
    C(
        "ontology.get",
        "ontology get {ontology.name}",
        "An ontology's metadata.",
        expect=(has("apiName", "rid"),),
    ),
    C(
        "ontology.object-type-list",
        "ontology object-type-list {ontology.name} --page-size 5",
        "Object types, one page.",
        expect=(paged(min_items=1),),
        capture={"ontology.object_type": "data.0.apiName"},
    ),
    C(
        "ontology.object-type-get",
        f"ontology object-type-get {ONT} --include-datasources",
        "An object type, with its datasources (--include-datasources).",
        expect=(
            equals("apiName", "{ontology.object_type}"),
            has("primaryKey"),
            note("datasources", "datasources"),
        ),
        capture={"ontology.pk_property": "primaryKey"},
    ),
    C(
        "ontology.object-list",
        f"ontology object-list {ONT} --page-size 5",
        "Objects, one page.",
        expect=(paged(),),
        capture={"ontology.primary_key": "data.0.__primaryKey"},
    ),
    C(
        "ontology.object-get",
        f"ontology object-get {ONT} {{ontology.primary_key}}",
        "One object by primary key.",
        expect=(equals("__primaryKey", "{ontology.primary_key}"),),
    ),
    C(
        "ontology.object-search",
        f"ontology object-search {ONT} --where {{ontology.where}} --page-size 5",
        "Typed --where search (default: eq on the primary key); select [] "
        "returns every property.",
        expect=(objects_with_properties,),
    ),
    C(
        "ontology.object-aggregate",
        f"ontology object-aggregate {ONT} --aggregation '{COUNT_AGGREGATION}'",
        "Aggregation DSL: a count.",
        expect=(has("data"), note("data.0.metrics.0.value", "count")),
    ),
    C(
        "ontology.object-count",
        f"ontology object-count {ONT}",
        "[beta] Object count (preview=true).",
        expect=(has("count"), note("count", "count")),
    ),
    C(
        "ontology.link-types",
        f"api ontologies ontology object-type list-outgoing-link-types {ONT} --page-size 5",
        "Outgoing link types (generated command; finds a link type).",
        expect=(paged(),),
        capture={"ontology.link_type": "data.0.apiName"},
    ),
    C(
        "ontology.object-linked",
        f"ontology object-linked {ONT} {{ontology.primary_key}} {{ontology.link_type}} --page-size 5",
        "Objects linked to the object.",
        expect=(paged(),),
    ),
    # ------------------------------------------------ ontology actions
    C(
        "action.validate",
        "ontology action-validate {ontology.name} {action.name} {action.parameters}",
        "Validates an action's parameters (VALIDATE_ONLY; nothing is applied).",
        expect=(one_of("validation.result", "VALID", "INVALID"),),
    ),
    # ------------------------------------------------ builds and schedules
    C(
        "orchestration.builds-search",
        "orchestration builds search --started-after {run.since} "
        "--order-by STARTED_TIME:DESC --page-size 5",
        "[beta] Builds started in the last 30 days (time filter, ordering).",
        expect=(paged(),),
        capture={"orchestration.build_rid": "data.0.rid"},
    ),
    C(
        "orchestration.builds-search-mine",
        "orchestration builds search --created-by {user.id} --page-size 5",
        "[beta] --created-by filter: every build found is yours.",
        expect=(paged(), all_items("createdBy", "{user.id}")),
    ),
    C(
        "orchestration.builds-get",
        "orchestration builds get {orchestration.build_rid}",
        "A build.",
        expect=(equals("rid", "{orchestration.build_rid}"), note("status", "status")),
        capture={
            "orchestration.job_rid": "jobRids.0",
            "orchestration.schedule_rid": "scheduleRid",
        },
    ),
    C(
        "orchestration.builds-get-batch",
        "orchestration builds get-batch {orchestration.build_rid}",
        "Builds by RID in one request.",
        expect=(data_map("{orchestration.build_rid}"),),
    ),
    C(
        "orchestration.builds-jobs",
        "orchestration builds jobs {orchestration.build_rid}",
        "The build's jobs.",
        expect=(paged(),),
        capture={"orchestration.job_rid": "data.0.rid"},
    ),
    C(
        "orchestration.jobs-get",
        "orchestration jobs get {orchestration.job_rid}",
        "[beta] A job.",
        expect=(equals("rid", "{orchestration.job_rid}"), note("jobStatus", "status")),
    ),
    C(
        "orchestration.jobs-get-batch",
        "orchestration jobs get-batch {orchestration.job_rid}",
        "[beta] Jobs by RID in one request.",
        expect=(data_map("{orchestration.job_rid}"),),
    ),
    C(
        "orchestration.schedules-get",
        "orchestration schedules get {orchestration.schedule_rid}",
        "[beta] A schedule.",
        expect=(equals("rid", "{orchestration.schedule_rid}"),),
    ),
    C(
        "orchestration.schedules-runs",
        "orchestration schedules runs {orchestration.schedule_rid} --page-size 5",
        "A schedule's recent runs.",
        expect=(paged(),),
    ),
    # ------------------------------------------------ filesystem
    C(
        "filesystem.root-folder-list",
        f"folder list {ROOT_FOLDER_RID} --page-size 5",
        "Children of the root folder.",
        expect=(paged(),),
    ),
    C(
        "filesystem.resource-list-root",
        "resource list --page-size 5",
        "resource list without --folder-rid lists the root folder.",
        expect=(paged(),),
    ),
    C(
        "filesystem.space-list",
        "space list --page-size 5",
        "Spaces you can see.",
        expect=(paged(),),
    ),
    C(
        "filesystem.folder-get",
        "folder get {filesystem.folder_rid}",
        "A folder (the scratch folder unless filesystem.folder_rid is set).",
        expect=(equals("rid", "{filesystem.folder_rid}"),),
    ),
    C(
        "filesystem.folder-list",
        "folder list {filesystem.folder_rid} --page-size 5",
        "Its children.",
        expect=(paged(),),
    ),
    C(
        "filesystem.resource-get",
        "resource get {filesystem.folder_rid}",
        "The same folder as a resource (finds its project and space).",
        expect=(equals("rid", "{filesystem.folder_rid}"), note("type", "type")),
        capture={
            "filesystem.project_rid": "projectRid",
            "filesystem.space_rid": "spaceRid",
        },
    ),
    C(
        "filesystem.project-get",
        "project get {filesystem.project_rid}",
        "Its project.",
        expect=(equals("rid", "{filesystem.project_rid}"),),
    ),
    C(
        "filesystem.space-get",
        "space get {filesystem.space_rid}",
        "[beta] Its space.",
        expect=(equals("rid", "{filesystem.space_rid}"),),
    ),
    C(
        "filesystem.project-list",
        "project list --space-rid {filesystem.space_rid} --page-size 5",
        "Projects in that space (children of a space are its projects).",
        expect=(paged(),),
    ),
    C(
        "filesystem.resource-roles",
        "resource-role list {filesystem.folder_rid} --include-inherited",
        "Role grants on the folder, with inherited ones.",
        expect=(paged(),),
    ),
    C(
        "filesystem.access-requirements",
        "resource access-requirements {filesystem.folder_rid}",
        "Organizations and markings needed to view the folder.",
        expect=(has(),),
    ),
    # ------------------------------------------------ pltr api (one per namespace)
    C(
        "api.admin",
        "api admin user get-current",
        "Generated command (admin), no input.",
        expect=(has("id"),),
    ),
    C(
        "api.filesystem",
        "api filesystem space list --page-size 1 --max-pages 2",
        "Generated command (filesystem); --max-pages follows nextPageToken.",
        expect=(paged(),),
    ),
    C(
        "api.ontologies",
        "api ontologies ontology list",
        "Generated command (ontologies), no input.",
        expect=(paged(),),
    ),
    C(
        "api.aip-agents",
        "api aip-agents agent all-sessions --page-size 5",
        "Generated command (aip-agents, beta), no input.",
        expect=(paged(),),
    ),
    C(
        "api.models",
        "api models model-studio-trainer list",
        "Generated command (models, beta), no input.",
        expect=(any_json,),
    ),
    C(
        "api.datasets",
        f"api datasets dataset get {DS}",
        "Generated command (datasets).",
        expect=(equals("rid", DS),),
    ),
    C(
        "api.sql-queries",
        "api sql-queries sql-query get-status {sql.query_id}",
        "Generated command (sql-queries).",
        expect=(has("type"),),
    ),
    C(
        "api.ontologies-search",
        f"api ontologies ontology-object search {ONT} --page-size 1",
        "Generated command; a left-out required list (select) is sent as [].",
        expect=(has("data"),),
    ),
    C(
        "api.orchestration",
        "api orchestration build get {orchestration.build_rid}",
        "Generated command (orchestration).",
        expect=(equals("rid", "{orchestration.build_rid}"),),
    ),
    C(
        "api.connectivity",
        "api connectivity connection get {connectivity.connection_rid}",
        "Generated command (connectivity).",
        expect=(has(),),
    ),
    C(
        "api.functions",
        "api functions query get {functions.query}",
        "Generated command (functions, beta).",
        expect=(has("apiName"),),
    ),
    C(
        "api.data-health",
        "api data-health check get {data_health.check_rid}",
        "Generated command (data-health, beta).",
        expect=(has("rid"),),
    ),
    C(
        "api.streams",
        "api streams dataset stream get {streams.dataset_rid} {streams.branch}",
        "Generated command (streams).",
        expect=(has("branchName"),),
    ),
    C(
        "api.third-party-applications",
        "api third-party-applications third-party-application get "
        "{third_party_apps.application_rid}",
        "Generated command (third-party-applications, beta).",
        expect=(has("rid"),),
    ),
    C(
        "api.widgets",
        "api widgets widget-set get {widgets.widget_set_rid}",
        "Generated command (widgets, beta).",
        expect=(has("rid"),),
    ),
    C(
        "api.audit",
        "api audit organization log-file list {admin.organization_rid} "
        "--start-date {run.week_ago} --end-date {run.today}",
        "Generated command (audit).",
        admin=True,
        expect=(paged(),),
    ),
    # ------------------------------------------------ other areas (inputs optional)
    C(
        "functions.query-get",
        "functions query get {functions.query}",
        "[beta] A query's definition by API name.",
        expect=(equals("apiName", "{functions.query}"),),
        capture={"functions.query_rid": "rid"},
    ),
    C(
        "functions.query-get-by-rid",
        "functions query get-by-rid {functions.query_rid}",
        "[beta] The same query by RID.",
        expect=(equals("rid", "{functions.query_rid}"),),
    ),
    C(
        "functions.query-execute",
        "functions query execute {functions.query} --parameters {functions.parameters}",
        "[beta] Executes the query.",
        expect=(has(),),
    ),
    C(
        "functions.query-execute-by-rid",
        "functions query execute-by-rid {functions.query_rid} "
        "--parameters {functions.parameters}",
        "[beta] Executes the version the RID resolves to.",
        expect=(has(),),
    ),
    C(
        "media-sets.get-by-path",
        "media-sets get-by-path {media_sets.rid} {media_sets.item_path}",
        "[beta] The item at a path.",
        expect=(has("mediaItemRid"),),
        capture={"media_sets.item_rid": "mediaItemRid"},
    ),
    C(
        "media-sets.get-by-missing-path",
        "media-sets get-by-path {media_sets.rid} pltr-smoke/{run.name}/missing",
        "[beta] A path with no item: exit 0 with a warning, or 5 (notes which).",
        exit_codes=(0, 5),
        error_types=("not_found",),
        expect=(any_json,),
    ),
    C(
        "media-sets.get",
        "media-sets get {media_sets.rid} {media_sets.item_rid}",
        "A media item's metadata.",
        expect=(has("path"),),
    ),
    C(
        "media-sets.reference",
        "media-sets reference {media_sets.rid} {media_sets.item_rid}",
        "[beta] A media item's media reference.",
        expect=(has("mimeType"),),
    ),
    C(
        "aip-agents.get",
        "aip-agents get {aip_agents.agent_rid}",
        "[beta] An agent.",
        expect=(equals("rid", "{aip_agents.agent_rid}"),),
    ),
    C(
        "aip-agents.versions-list",
        "aip-agents versions list {aip_agents.agent_rid}",
        "[beta] Its versions.",
        expect=(paged(),),
    ),
    C(
        "aip-agents.sessions-list",
        "aip-agents sessions list {aip_agents.agent_rid}",
        "[beta] Your sessions with it.",
        expect=(paged(),),
    ),
    C(
        "widgets.get",
        "widgets get {widgets.widget_set_rid}",
        "[beta] A widget set.",
        expect=(equals("rid", "{widgets.widget_set_rid}"),),
    ),
    C(
        "widgets.release-list",
        "widgets release list {widgets.widget_set_rid}",
        "[beta] Its releases.",
        expect=(paged(),),
    ),
    C(
        "third-party-apps.get",
        "third-party-apps get {third_party_apps.application_rid}",
        "[beta] A third-party application.",
        expect=(equals("rid", "{third_party_apps.application_rid}"),),
    ),
    C(
        "connectivity.connection-get",
        "connectivity connection get {connectivity.connection_rid}",
        "A connection.",
        expect=(has("configuration"),),
    ),
    C(
        "connectivity.list-file-imports",
        "connectivity import list-file {connectivity.connection_rid}",
        "Its file imports.",
        expect=(paged(),),
    ),
    C(
        "connectivity.list-table-imports",
        "connectivity import list-table {connectivity.connection_rid}",
        "Its table imports.",
        expect=(paged(),),
    ),
    C(
        "data-health.check-get",
        "data-health check get {data_health.check_rid}",
        "[beta] A check.",
        expect=(equals("rid", "{data_health.check_rid}"),),
    ),
    C(
        "data-health.report-latest",
        "data-health report latest {data_health.check_rid} --limit 5",
        "[beta] The check's latest reports.",
        expect=(paged(),),
        capture={"data_health.report_rid": "data.0.rid"},
    ),
    C(
        "data-health.report-get",
        "data-health report get {data_health.check_rid} {data_health.report_rid}",
        "[beta] One report.",
        expect=(equals("rid", "{data_health.report_rid}"),),
    ),
    C(
        "models.model-get",
        "models model get {models.model_rid}",
        "[beta] A model.",
        expect=(equals("rid", "{models.model_rid}"),),
    ),
    C(
        "models.version-list",
        "models version list {models.model_rid}",
        "[beta] Its versions.",
        expect=(paged(),),
        capture={"models.version_rid": "data.0.rid"},
    ),
    C(
        "models.version-get",
        "models version get {models.model_rid} {models.version_rid}",
        "[beta] One version.",
        expect=(equals("rid", "{models.version_rid}"),),
    ),
    C(
        "streams.stream-get",
        "streams stream get {streams.dataset_rid} --branch {streams.branch}",
        "A stream.",
        expect=(has("branchName"),),
    ),
    C(
        "language-models.list",
        "language-models list",
        "Language models (direct HTTP: not in the SDK).",
        expect=(paged(),),
        capture={"language_models.model_id": first_model_id},
    ),
    C(
        "language-models.status",
        "language-models status {language_models.model_id}",
        "A model's enrollment status (direct HTTP).",
        expect=(has(),),
    ),
    C(
        "language-models.anthropic-messages",
        "language-models anthropic messages {language_models.anthropic_model} "
        "--message 'Reply with the word OK.' --max-tokens 16",
        "[beta] One short message to an Anthropic model.",
        expect=(has("content"),),
    ),
    C(
        "language-models.openai-embeddings",
        "language-models openai embeddings {language_models.embedding_model} "
        "--input 'pltr smoke test'",
        "[beta] Embeds one short text.",
        expect=(has("data"),),
    ),
    # ------------------------------------------------ admin (read-only, --include-admin)
    C(
        "admin.user-search",
        "admin user search {user.username} --page-size 5",
        "User search (queryString prefix) finds you by username.",
        admin=True,
        needs=("user.id",),
        expect=(paged(min_items=1), contains("{user.id}", "id")),
    ),
    C(
        "admin.user-list",
        "admin user list --page-size 5",
        "Users, one page.",
        admin=True,
        expect=(paged(),),
    ),
    C(
        "admin.group-list",
        "admin group list --page-size 5",
        "Groups, one page.",
        admin=True,
        expect=(paged(),),
    ),
    C(
        "admin.marking-list",
        "admin marking list --exclude-deleted --marking-type MANDATORY --page-size 5",
        "Markings with the #189 filters (--exclude-deleted, --marking-type).",
        admin=True,
        expect=(paged(), none_deleted),
    ),
    C(
        "admin.org-get",
        "admin org get {admin.organization_rid}",
        "Your organization (or admin.organization_rid).",
        admin=True,
        expect=(equals("rid", "{admin.organization_rid}"),),
    ),
    C(
        "admin.org-available-roles",
        "admin org available-roles {admin.organization_rid}",
        "Roles assignable in the organization (not paged).",
        admin=True,
        expect=(paged(),),
        capture={"admin.role_id": "data.0.id"},
    ),
    C(
        "admin.role-get",
        "admin role get {admin.role_id}",
        "[beta] A role ID from available-roles works with role get.",
        admin=True,
        expect=(equals("id", "{admin.role_id}"),),
    ),
    C(
        "audit.list",
        "audit list {admin.organization_rid} {run.week_ago}",
        "Audit log files of the last week, no end date (notes the nextPageToken).",
        admin=True,
        expect=(paged(),),
    ),
    # ------------------------------------------------ writes (--allow-writes)
    C(
        "write.folder-create",
        "folder create {run.name} --parent-folder {writes.scratch_folder}",
        "Creates the run's folder in the scratch folder.",
        write=True,
        expect=(equals("displayName", "{run.name}"),),
        capture={"created.folder": "rid"},
    ),
    C(
        "write.folder-get",
        "folder get {created.folder}",
        "Reads it back.",
        write=True,
        needs=("writes.scratch_folder",),
        expect=(equals("parentFolderRid", "{writes.scratch_folder}"),),
    ),
    C(
        "write.dataset-create",
        "dataset create {run.name}-dataset --parent-folder {created.folder}",
        "Creates a dataset in it.",
        write=True,
        expect=(has("rid"),),
        capture={"created.dataset": "rid"},
    ),
    C(
        "write.files-upload",
        f"dataset files upload {{run.tmp}}/upload/smoke.csv {NEW_DS} --path smoke/smoke.csv",
        "Uploads a file (the API opens and commits a transaction).",
        write=True,
        expect=(equals("path", "smoke/smoke.csv"),),
    ),
    C(
        "write.files-upload-append",
        f"dataset files upload {{run.tmp}}/upload/smoke-append.csv {NEW_DS} "
        "--path smoke/smoke-append.csv --transaction-type APPEND",
        "--transaction-type without --branch.",
        write=True,
        expect=(equals("path", "smoke/smoke-append.csv"),),
    ),
    C(
        "write.files-list",
        f"dataset files list {NEW_DS}",
        "Lists the uploaded files.",
        write=True,
        expect=(paged(min_items=2), contains("smoke/smoke.csv", "path")),
    ),
    C(
        "write.files-get",
        f"dataset files get {NEW_DS} smoke/smoke.csv {{run.tmp}}/download/smoke.csv",
        "Downloads a file: same bytes as uploaded.",
        write=True,
        expect=(
            equals("path", "smoke/smoke.csv"),
            same_file("{run.tmp}/download/smoke.csv", "{run.tmp}/upload/smoke.csv"),
        ),
    ),
    C(
        "write.transaction-start",
        f"dataset transactions start {NEW_DS} --type UPDATE",
        "Opens a transaction.",
        write=True,
        expect=(equals("status", "OPEN"),),
        capture={"created.transaction": "rid"},
    ),
    C(
        "write.transaction-upload",
        f"dataset files upload {{run.tmp}}/upload/smoke-txn.csv {NEW_DS} "
        "--transaction-rid {created.transaction} --path smoke/smoke-txn.csv",
        "Uploads into the open transaction.",
        write=True,
        expect=(equals("transactionRid", "{created.transaction}"),),
    ),
    C(
        "write.transaction-commit",
        f"dataset transactions commit {NEW_DS} {{created.transaction}}",
        "Commits it.",
        write=True,
        expect=(equals("status", "COMMITTED"),),
    ),
    C(
        "write.directory-upload",
        f"dataset files upload {{run.tmp}}/upload/smoke-dir {NEW_DS} --path dir",
        "Uploads a directory in one transaction.",
        write=True,
        expect=(paged(min_items=2),),
    ),
    C(
        "write.directory-download",
        f"dataset files get {NEW_DS} dir {{run.tmp}}/download/dir --recursive",
        "Downloads the folder: same files as uploaded.",
        write=True,
        expect=(
            paged(min_items=2),
            same_tree("{run.tmp}/download/dir", "{run.tmp}/upload/smoke-dir"),
        ),
    ),
    C(
        "write.transaction-start-2",
        f"dataset transactions start {NEW_DS}",
        "Opens a second transaction.",
        write=True,
        expect=(equals("status", "OPEN"),),
        capture={"created.transaction_2": "rid"},
    ),
    C(
        "write.transaction-abort",
        f"dataset transactions abort {NEW_DS} {{created.transaction_2}} --yes",
        "Aborts it.",
        write=True,
        expect=(equals("status", "ABORTED"),),
    ),
    C(
        "write.schema-apply",
        f"dataset schema apply {NEW_DS} --yes",
        "Infers and applies a schema (direct HTTP: internal endpoints).",
        write=True,
        expect=(any_json,),
    ),
    C(
        "write.schema-set",
        f"dataset schema set {NEW_DS} --from-csv {{run.tmp}}/upload/smoke.csv "
        "--dataframe-reader CSV --yes",
        "Sets a schema read from a CSV file, for CSV files.",
        write=True,
        expect=(has(),),
    ),
    C(
        "write.schema-get",
        f"dataset schema get {NEW_DS}",
        "Reads the schema back.",
        write=True,
        expect=(schema_fields(*UPLOAD_COLUMNS),),
    ),
    C(
        "write.read-table",
        f"dataset preview {NEW_DS} --limit 20",
        "Foundry reads the uploaded CSV files with that schema.",
        write=True,
        expect=(preview_columns,),
    ),
    C(
        "write.branch-create",
        f"dataset branches create {NEW_DS} {SMOKE_BRANCH}",
        "Creates a branch from master.",
        write=True,
        expect=(equals("name", SMOKE_BRANCH),),
    ),
    C(
        "write.branches-list",
        f"dataset branches list {NEW_DS}",
        "Lists it.",
        write=True,
        expect=(paged(min_items=2), contains(SMOKE_BRANCH, "name")),
    ),
    C(
        "write.branch-delete-needs-yes",
        f"dataset branches delete {NEW_DS} {SMOKE_BRANCH}",
        "Without --yes and no terminal: exit 2, nothing deleted.",
        write=True,
        exit_codes=(2,),
        error_types=("confirmation_required",),
    ),
    C(
        "write.branch-delete",
        f"dataset branches delete {NEW_DS} {SMOKE_BRANCH} --yes",
        "Deletes the branch.",
        write=True,
        expect=(is_null,),
    ),
    C(
        "write.file-delete",
        f"dataset files delete {NEW_DS} smoke/smoke-append.csv --yes",
        "Deletes a file (in a DELETE transaction).",
        write=True,
        expect=(is_null,),
    ),
    C(
        "write.cp",
        f"cp {NEW_DS} {{created.folder}}",
        "Copies the dataset (files and schema) into the folder.",
        write=True,
        expect=(paged(min_items=1),),
        capture={"created.dataset_copy": "data.0.rid"},
    ),
    C(
        "write.trash-copy",
        "resource delete {created.dataset_copy} --yes",
        "Moves the copy to the trash.",
        write=True,
        cleanup=True,
        trashes=("created.dataset_copy",),
        expect=(is_null,),
    ),
    C(
        "write.trash-dataset",
        f"resource delete {NEW_DS} --yes",
        "Moves the dataset to the trash.",
        write=True,
        expect=(is_null,),
    ),
    C(
        "write.dataset-trashed",
        f"resource get {NEW_DS}",
        "It is in the trash.",
        write=True,
        expect=(equals("trashStatus", "DIRECTLY_TRASHED"),),
    ),
    C(
        "write.restore-dataset",
        f"resource restore {NEW_DS}",
        "Restores it.",
        write=True,
        expect=(is_null,),
    ),
    C(
        "write.dataset-restored",
        f"resource get {NEW_DS}",
        "It is out of the trash.",
        write=True,
        expect=(equals("trashStatus", "NOT_TRASHED"),),
    ),
    C(
        "write.stream-create",
        f"streams dataset create {{run.name}}-stream --folder {{created.folder}} "
        f"--schema '{STREAM_SCHEMA}'",
        "[beta] Creates a streaming dataset (StreamSchema format).",
        write=True,
        expect=(has("rid"),),
        capture={"created.stream_dataset": "rid"},
    ),
    C(
        "write.stream-get",
        "streams stream get {created.stream_dataset} --branch master",
        "Reads its stream.",
        write=True,
        expect=(has("branchName"),),
    ),
    C(
        "write.stream-publish",
        f"streams stream publish {{created.stream_dataset}} --branch master "
        f"--record '{STREAM_RECORD}'",
        "Publishes a record (high-scale endpoint).",
        write=True,
        expect=(is_null,),
    ),
    C(
        "write.trash-stream",
        "resource delete {created.stream_dataset} --yes",
        "Moves the streaming dataset to the trash.",
        write=True,
        cleanup=True,
        trashes=("created.stream_dataset",),
        expect=(is_null,),
    ),
    C(
        "write.sql-cancel-finished",
        "sql cancel {sql.query_id} --yes",
        "Canceling a finished query (sql.submit's, after sql.wait) changes nothing.",
        write=True,
        needs=("sql.query_finished",),
        expect=(one_of("type", "succeeded"),),
    ),
    C(
        "write.project-create",
        "project create {run.name} --space-rid {writes.space_rid}",
        "Creates a project (you get compass:manage).",
        write=True,
        expect=(has("rid"),),
        capture={"created.project": "rid"},
    ),
    C(
        "write.project-delete",
        "project delete {created.project} --yes",
        "Moves the project to the trash (Resource.delete accepts project RIDs).",
        write=True,
        cleanup=True,
        trashes=("created.project",),
        expect=(is_null,),
    ),
    C(
        "write.project-trashed",
        "project get {created.project}",
        "It is in the trash.",
        write=True,
        expect=(equals("trashStatus", "DIRECTLY_TRASHED"),),
    ),
    C(
        "write.trash-folder",
        "resource delete {created.folder} --yes",
        "Moves the run's folder, with everything in it, to the trash.",
        write=True,
        cleanup=True,
        trashes=("created.folder",),
        expect=(is_null,),
    ),
    C(
        "write.folder-trashed",
        "folder get {created.folder}",
        "It is in the trash.",
        write=True,
        expect=(equals("trashStatus", "DIRECTLY_TRASHED"),),
    ),
    # ------------------------------------------------ admin writes (no-op replaces)
    C(
        "admin.space-before",
        "space get {admin.replace_space_rid}",
        "[beta] Reads the space to replace.",
        write=True,
        admin=True,
        expect=(has("displayName"),),
        capture={"before.space": whole, "before.space_name": "displayName"},
    ),
    C(
        "admin.space-update-unchanged",
        "space update {admin.replace_space_rid} --name {before.space_name}",
        "[beta] Space.replace with the current values (pltr sends what you don't change).",
        write=True,
        admin=True,
        expect=(has("rid"),),
    ),
    C(
        "admin.space-after",
        "space get {admin.replace_space_rid}",
        "[beta] Nothing changed.",
        write=True,
        admin=True,
        needs=("before.space",),
        expect=(
            unchanged(
                "before.space",
                "displayName",
                "description",
                "defaultRoleSetId",
                "usageAccountRid",
                "organizations",
                "deletionPolicyOrganizations",
            ),
        ),
    ),
    C(
        "admin.org-before",
        "admin org get {admin.replace_organization_rid}",
        "Reads the organization to replace.",
        write=True,
        admin=True,
        expect=(has("name"),),
        capture={"before.organization": whole, "before.organization_name": "name"},
    ),
    C(
        "admin.org-replace-unchanged",
        "admin org replace {admin.replace_organization_rid} "
        "{before.organization_name} --yes",
        "Organization.replace with the current name (description and host kept).",
        write=True,
        admin=True,
        expect=(any_json,),
    ),
    C(
        "admin.org-after",
        "admin org get {admin.replace_organization_rid}",
        "Nothing changed.",
        write=True,
        admin=True,
        needs=("before.organization",),
        expect=(unchanged("before.organization", "name", "description", "host"),),
    ),
    C(
        "admin.marking-before",
        "admin marking get {admin.replace_marking_id}",
        "Reads the marking to replace.",
        write=True,
        admin=True,
        expect=(has("name"),),
        capture={"before.marking": whole, "before.marking_name": "name"},
    ),
    C(
        "admin.marking-replace-unchanged",
        "admin marking replace {admin.replace_marking_id} {before.marking_name} --yes",
        "Marking.replace with the current name (description kept).",
        write=True,
        admin=True,
        expect=(any_json,),
    ),
    C(
        "admin.marking-after",
        "admin marking get {admin.replace_marking_id}",
        "Nothing changed.",
        write=True,
        admin=True,
        needs=("before.marking",),
        expect=(unchanged("before.marking", "name", "description"),),
    ),
)

CHECKS_BY_ID = {check.id: check for check in CHECKS}


def providers(key: str, checks: Iterable[Check] = CHECKS) -> List[Check]:
    """The checks that capture key (directly, or a key it is derived from)."""
    checks = list(checks)
    found = [c for c in checks if key in c.capture]
    if key in DERIVED:
        for dep in DERIVED[key][0]:
            found.extend(c for c in providers(dep, checks) if c not in found)
    return found


def known_keys() -> Set[str]:
    """Every key a config file or --set may give a value."""
    keys: Set[str] = set(INPUT_KEYS) | set(DERIVED)
    for check in CHECKS:
        keys.update(check.placeholders())
        keys.update(check.capture)
    return {k for k in keys if not k.startswith(("run.", "created.", "before."))}


# ---------------------------------------------------------------- running


@dataclasses.dataclass
class RunResult:
    """What one pltr process did."""

    exit_code: int
    stdout: str
    stderr: str
    seconds: float = 0.0
    timed_out: bool = False


# (pltr arguments, environment changes (None = unset), timeout) -> RunResult
Runner = Callable[[Sequence[str], Mapping[str, Optional[str]], float], RunResult]


def _decode(data: Union[str, bytes, None]) -> str:
    if data is None:
        return ""
    return data if isinstance(data, str) else data.decode("utf-8", "replace")


class SubprocessRunner:
    """Run pltr in a subprocess with stdin closed, so nothing can prompt."""

    def __init__(self, command: Sequence[str]):
        self.command = list(command)

    def __call__(
        self,
        argv: Sequence[str],
        env: Mapping[str, Optional[str]],
        timeout: float,
    ) -> RunResult:
        full_env = dict(os.environ)
        for key, value in env.items():
            if value is None:
                full_env.pop(key, None)
            else:
                full_env[key] = value
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [*self.command, *argv],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=full_env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return RunResult(
                exit_code=-1,
                stdout=_decode(exc.stdout),
                stderr=_decode(exc.stderr),
                seconds=time.monotonic() - start,
                timed_out=True,
            )
        return RunResult(
            proc.returncode, proc.stdout, proc.stderr, time.monotonic() - start
        )


@dataclasses.dataclass
class CheckResult:
    check: Check
    status: str
    detail: str = ""
    seconds: Optional[float] = None
    argv: Optional[List[str]] = None
    exit_code: Optional[int] = None
    error: Optional[Dict[str, Any]] = None


def command_line(check: Check, ctx: Context, profile: Optional[str]) -> List[str]:
    """The pltr arguments a check runs with (after ``pltr``)."""
    argv = [ctx.render(part) for part in check.argv]
    argv += ["--format", check.output]
    if profile and not check.isolated_auth:
        argv += ["--profile", profile]
    return argv


_DISPLAY_SAFE = re.compile(r"[\w@%+=:,./<>-]+")


def _display(part: str) -> str:
    return part if _DISPLAY_SAFE.fullmatch(part) else shlex.quote(part)


def _template(text: str) -> str:
    return PLACEHOLDER.sub(r"<\1>", text)


def command_template(check: Check) -> str:
    """The command with <key> for each input, as --list and Markdown show it.

    Environment variables a check sets come first; checks with their own
    credentials run without a profile.
    """
    parts = [_template(part) for part in check.argv] + ["--format", check.output]
    env = [f"{name}={_display(_template(value))}" for name, value in check.env.items()]
    return " ".join([*env, "pltr", *(_display(p) for p in parts)])


def check_env(check: Check, ctx: Context) -> Dict[str, Optional[str]]:
    """Environment changes for a check (None removes a variable)."""
    # PLTR_FORMAT would change nothing (--format is explicit) and PLTR_DEBUG
    # would print tracebacks into the JSON stderr.
    env: Dict[str, Optional[str]] = {"PLTR_FORMAT": None, "PLTR_DEBUG": None}
    if check.isolated_auth:
        # No profile can be found, so pltr uses only the variables below.
        home = os.path.join(_text(ctx.get("run.tmp")), "isolated-home")
        env.update(
            HOME=home,
            USERPROFILE=home,
            XDG_CONFIG_HOME=os.path.join(home, ".config"),
        )
        env.update({var: None for var in AUTH_VARIABLES})
    for key, template in check.env.items():
        env[key] = ctx.render(template)
    return env


def parse_stderr(stderr: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """JSON Lines on stderr: (the objects, the first line that isn't one)."""
    objects: List[Dict[str, Any]] = []
    for line in stderr.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except ValueError:
            return objects, line
        if not isinstance(value, dict) or "type" not in value:
            return objects, line
        objects.append(value)
    return objects, None


def describe_error(error: Mapping[str, Any]) -> str:
    """type, errorName and HTTP status of a structured error, then its message."""
    parts = [str(error.get("type", "error"))]
    if error.get("errorName"):
        parts.append(str(error["errorName"]))
    if error.get("statusCode"):
        parts.append(f"HTTP {error['statusCode']}")
    message = error.get("message")
    return " ".join(parts) + (f": {_short(message)}" if message else "")


def _last_line(text: str) -> str:
    """The last line of stderr; in text mode the last `Error: ...` line."""
    lines = [line for line in text.splitlines() if line.strip()]
    errors = [line for line in lines if line.startswith("Error:")]
    return (errors or lines or [""])[-1]


def _codes(codes: Sequence[int]) -> str:
    return " or ".join(str(c) for c in codes)


def evaluate(check: Check, run: RunResult, ctx: Context) -> CheckResult:
    """Judge one run: exit code, the output contract, then the check's expectations."""

    def result(status: str, detail: str, error: Any = None) -> CheckResult:
        return CheckResult(
            check, status, detail, run.seconds, exit_code=run.exit_code, error=error
        )

    if run.timed_out:
        return result(FAIL, f"no answer within {run.seconds:.0f}s (timed out)")
    json_mode = check.output == "json"
    lines, bad_line = parse_stderr(run.stderr) if json_mode else ([], None)
    errors = [line for line in lines if line.get("type") != "warning"]
    error = errors[-1] if errors else None

    if run.exit_code not in check.exit_codes:
        detail = f"exit {run.exit_code} (expected {_codes(check.exit_codes)})"
        if error is not None:
            detail += ": " + describe_error(error)
        elif _last_line(run.stderr):
            detail += ": " + _short(_last_line(run.stderr))
            if json_mode:
                detail += " [contract: stderr is not a JSON error]"
        else:
            detail += ", nothing on stderr"
        return result(FAIL, detail, error)
    if bad_line is not None:
        return result(
            FAIL, f"contract: stderr is not JSON Lines: {_short(bad_line)}", error
        )

    if run.exit_code != 0:  # an expected failure
        if json_mode:
            if error is None:
                return result(FAIL, "contract: no structured error on stderr")
            if error.get("exitCode") != run.exit_code:
                return result(
                    FAIL,
                    f"contract: the error's exitCode is {error.get('exitCode')!r}, "
                    f"the process exited {run.exit_code}",
                    error,
                )
            if check.error_types and error.get("type") not in check.error_types:
                return result(
                    FAIL,
                    f"error type {error.get('type')!r}, expected "
                    f"{' or '.join(check.error_types)}: {describe_error(error)}",
                    error,
                )
        if run.stdout.strip():
            return result(FAIL, "contract: stdout is not empty after a failure", error)
        return result(
            PASS,
            f"exit {run.exit_code}: "
            + (describe_error(error) if error else _short(_last_line(run.stderr))),
            error,
        )

    if error is not None:
        return result(
            FAIL,
            f"contract: exit 0 but stderr has an error: {describe_error(error)}",
            error,
        )
    if json_mode:
        try:
            doc: Any = json.loads(run.stdout)
        except ValueError as exc:
            shown = _short(run.stdout, 80) if run.stdout.strip() else "nothing"
            return result(
                FAIL,
                f"contract: stdout is not exactly one JSON document ({exc}); got {shown}",
            )
    else:
        doc = list(csv.reader(io.StringIO(run.stdout)))
        if not doc:
            return result(FAIL, "no CSV on stdout")

    notes: List[str] = []
    try:
        for validate in check.expect:
            text = validate(doc, ctx)
            if text:
                notes.append(text)
    except Unexpected as exc:
        return result(FAIL, f"unexpected output: {exc}")
    except KeyError as exc:  # a validator template names a key the check lacks
        return result(FAIL, f"smoke.py bug: {check.id} has no value for {exc}")
    for key, how in check.capture.items():
        ctx.capture(key, extract(doc, how))
    warnings = [line for line in lines if line.get("type") == "warning"]
    if warnings:
        more = f" (+{len(warnings) - 1} more)" if len(warnings) > 1 else ""
        notes.append(f"warning: {_short(warnings[0].get('message', ''), 100)}{more}")
    return result(PASS, "; ".join(notes))


def _sources(key: str) -> Set[str]:
    """The key and, for a DERIVED key, the keys it is derived from."""
    found = {key}
    for dep in DERIVED.get(key, ((), None))[0]:
        found |= _sources(dep)
    return found


def explain_missing(
    key: str,
    ctx: Context,
    done: Mapping[str, CheckResult],
    checks: Sequence[Check],
) -> str:
    """Why a key has no value, for a skipped check."""
    sources = _sources(key)
    states = []
    for provider in providers(key, checks):
        outcome = done.get(provider.id)
        if outcome is None:
            continue  # not selected
        if outcome.status == PASS:
            provided = [k for k in provider.capture if k in sources]
            if any(not ctx.has(k) for k in provided):
                states.append(f"{provider.id} found none")
        else:
            state = "failed" if outcome.status == FAIL else "was skipped"
            states.append(f"{provider.id} {state}")
    if key in DERIVED:
        missing = [d for d in DERIVED[key][0] if not ctx.has(d)]
        if missing and all(d in INPUT_KEYS for d in missing):
            states.append(f"set {key} or {' and '.join(missing)}")
    return f"no input: {key}" + (f" ({'; '.join(states)})" if states else "")


@dataclasses.dataclass
class Options:
    profile: Optional[str] = None
    allow_writes: bool = False
    include_admin: bool = False
    timeout: float = DEFAULT_TIMEOUT


def run_checks(
    checks: Sequence[Check],
    ctx: Context,
    runner: Runner,
    options: Options,
    progress: Optional[Callable[[CheckResult, int, int], None]] = None,
) -> Tuple[List[CheckResult], bool]:
    """Run checks in order; returns (results, interrupted).

    After Ctrl-C only the cleanup checks still run (if their inputs exist),
    so the write pass doesn't leave its resources behind.
    """
    done: Dict[str, CheckResult] = {}
    results: List[CheckResult] = []
    interrupted = False
    for index, check in enumerate(checks, 1):
        if check.write and not options.allow_writes:
            outcome = CheckResult(check, SKIP, "writes are off (--allow-writes)")
        elif check.admin and not options.include_admin:
            outcome = CheckResult(check, SKIP, "admin checks are off (--include-admin)")
        elif interrupted and not check.cleanup:
            outcome = CheckResult(check, SKIP, "interrupted")
        else:
            missing = [key for key in check.placeholders() if not ctx.has(key)]
            if missing:
                outcome = CheckResult(
                    check, SKIP, explain_missing(missing[0], ctx, done, checks)
                )
            else:
                argv = command_line(check, ctx, options.profile)
                try:
                    run = runner(argv, check_env(check, ctx), options.timeout)
                    outcome = evaluate(check, run, ctx)
                except KeyboardInterrupt:
                    interrupted = True
                    outcome = CheckResult(check, FAIL, "interrupted")
                outcome.argv = argv
        done[check.id] = outcome
        results.append(outcome)
        if progress is not None:
            progress(outcome, index, len(checks))
    return results, interrupted


def leftovers(ctx: Context, results: Sequence[CheckResult]) -> List[Tuple[str, str]]:
    """Resources the write checks created and didn't move to the trash."""
    trashed = {key for r in results if r.status == PASS for key in r.check.trashes}
    left = []
    for key, container in CREATED_RESOURCES.items():
        rid = ctx.captured.get(key)
        if rid is None or key in trashed or (container and container in trashed):
            continue
        left.append((key, str(rid)))
    return left


# ---------------------------------------------------------------- selection


def select_checks(
    only: Sequence[str],
    *,
    allow_writes: bool,
    include_admin: bool,
    configured: Mapping[str, Any],
    checks: Sequence[Check] = CHECKS,
) -> Tuple[List[Check], Dict[str, int]]:
    """The checks to run, in order, and how many were left out by each flag.

    ``only`` names groups (``dataset``) or check IDs (``dataset.get``). The
    checks that find the inputs of the selected checks are added (unless
    their flag is off).
    """
    groups = {c.group for c in checks}
    ids = {c.id for c in checks}
    unknown = [token for token in only if token not in groups and token not in ids]
    if unknown:
        raise ConfigError(
            f"--only: unknown group or check {', '.join(unknown)}; groups: "
            + ", ".join(sorted(groups))
        )
    wanted = [c for c in checks if not only or c.group in only or c.id in only]

    def allowed(check: Check) -> bool:
        return (allow_writes or not check.write) and (include_admin or not check.admin)

    not_run = {"write": 0, "admin": 0}
    for check in wanted:
        if check.write and not allow_writes:
            not_run["write"] += 1
        elif check.admin and not include_admin:
            not_run["admin"] += 1

    by_id = {c.id: c for c in checks}
    chosen = {c.id for c in wanted if allowed(c)}
    queue = list(chosen)
    while queue:
        check = by_id[queue.pop()]
        for key in check.placeholders():
            if key in configured:
                continue
            for provider in providers(key, checks):
                if provider.id not in chosen and allowed(provider):
                    chosen.add(provider.id)
                    queue.append(provider.id)
    return [c for c in checks if c.id in chosen], not_run


# ---------------------------------------------------------------- configuration


def _load_toml(path: Path) -> Dict[str, Any]:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:  # Python 3.10
        try:
            import tomli as tomllib  # type: ignore[import-not-found,no-redef]
        except ModuleNotFoundError:
            raise ConfigError(
                f"{path}: reading TOML needs Python 3.11+ or the tomli package "
                "(`uv sync --dev` installs it); or use a JSON config"
            ) from None
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_config(path: Optional[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Read a TOML or JSON config file: (settings, inputs).

    Settings are the top-level ``profile`` and ``pltr``; every table is a
    group of inputs (``[dataset] rid = ...`` is the input ``dataset.rid``).
    Without ``path``, ``./smoke.toml`` is read if it exists.
    """
    if path is None:
        if not Path(DEFAULT_CONFIG).is_file():
            return {}, {}
        path = DEFAULT_CONFIG
    file = Path(path)
    if not file.is_file():
        raise ConfigError(f"config file {path} not found")
    try:
        if file.suffix == ".json":
            data = json.loads(file.read_text(encoding="utf-8"))
        else:
            data = _load_toml(file)
    except ConfigError:
        raise
    except Exception as exc:  # a TOML or JSON syntax error
        raise ConfigError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a table of settings and inputs")
    settings: Dict[str, Any] = {}
    inputs: Dict[str, Any] = {}
    keys = known_keys()
    for name, value in data.items():
        if name in ("profile", "pltr"):
            if not isinstance(value, str):
                raise ConfigError(f"{path}: {name} must be a string")
            settings[name] = value
            continue
        if not isinstance(value, dict):
            raise ConfigError(
                f"{path}: {name!r} must be a table of inputs ([{name}]), "
                "or one of the settings profile, pltr"
            )
        for sub, item in value.items():
            key = f"{name}.{sub}"
            if key not in keys:
                raise ConfigError(
                    f"{path}: unknown input {key}; see scripts/smoke.example.toml"
                )
            if isinstance(item, (dict, list)):
                item = json.dumps(item)  # e.g. action parameters as a TOML table
            if item != "":
                inputs[key] = item
    return settings, inputs


def input_flag(key: str) -> str:
    return "--" + key.replace(".", "-").replace("_", "-")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smoke.py",
        usage="uv run python scripts/smoke.py [--config FILE] [--profile P] "
        "[--allow-writes --scratch-folder RID] [--include-admin] "
        "[--only GROUP ...] [--markdown] [--list] [input flags]",
        description="Run the real pltr CLI against a live Foundry stack and "
        "report pass/fail/skip per check (see "
        "docs/development/live-verification.md).",
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        help=f"TOML or JSON file with inputs (default: ./{DEFAULT_CONFIG} if it "
        "exists; see scripts/smoke.example.toml).",
    )
    parser.add_argument("--profile", help="pltr profile to run every check with.")
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        help="Also run the write checks. Needs --scratch-folder.",
    )
    parser.add_argument(
        "--scratch-folder",
        metavar="RID",
        help="Folder or project the write checks create their folder in "
        "(ri.compass.main.folder.<uuid>). Everything they create is moved to "
        "the trash at the end.",
    )
    parser.add_argument(
        "--include-admin",
        action="store_true",
        help="Also run checks that need admin permissions (users, groups, "
        "markings, organizations, audit logs); with --allow-writes also the "
        "no-op replaces of admin.replace_* inputs. Nothing is ever "
        "permanently deleted.",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="GROUP",
        default=[],
        help="Run only these groups or check IDs (and the checks that find "
        "their inputs). See --list.",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Print the report as Markdown, ready to paste into a PR.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the checks and their commands; run nothing.",
    )
    parser.add_argument(
        "--pltr",
        metavar="COMMAND",
        help="Command that runs pltr (default: this Python's `python -m "
        "pltr`), e.g. 'pltr' for the pltr on PATH.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"Time limit for each command (default: {DEFAULT_TIMEOUT:.0f}).",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Set any input, e.g. --set orchestration.job_rid=ri.foundry.main.job.<uuid>.",
    )
    inputs = parser.add_argument_group(
        "inputs", "Override the config file (dotted names in brackets)."
    )
    for spec in INPUTS:
        if spec.key == "writes.scratch_folder":
            continue  # --scratch-folder
        inputs.add_argument(
            input_flag(spec.key),
            dest=f"input:{spec.key}",
            metavar="VALUE",
            help=f"[{spec.key}] {spec.help}",
        )
    return parser


def gather_inputs(args: argparse.Namespace) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Settings and inputs from the config file, then flags, then --set."""
    settings, inputs = load_config(args.config)
    for name, value in vars(args).items():
        if name.startswith("input:") and value is not None:
            inputs[name[len("input:") :]] = value
    if args.scratch_folder:
        inputs["writes.scratch_folder"] = args.scratch_folder
    keys = known_keys()
    for item in args.set:
        key, sep, value = item.partition("=")
        if not sep or key not in keys:
            raise ConfigError(f"--set {item}: expected KEY=VALUE with a known key")
        inputs[key] = value
    return settings, inputs


def check_write_guard(args: argparse.Namespace, inputs: Mapping[str, Any]) -> None:
    """--allow-writes needs a scratch folder, and it can't be the root folder."""
    scratch = inputs.get("writes.scratch_folder")
    if args.allow_writes and not scratch:
        raise ConfigError(
            "--allow-writes needs --scratch-folder RID (or writes.scratch_folder "
            "in the config): a folder or project the smoke test may create "
            "things in"
        )
    if scratch and (
        scratch == ROOT_FOLDER_RID
        or not str(scratch).startswith("ri.compass.main.folder.")
    ):
        raise ConfigError(
            f"--scratch-folder {scratch}: expected a folder or project RID "
            "(ri.compass.main.folder.<uuid>), not the root folder"
        )


# ---------------------------------------------------------------- reports


@dataclasses.dataclass
class Report:
    results: List[CheckResult]
    not_run: Dict[str, int]
    leftovers: List[Tuple[str, str]]
    pltr_version: str
    profile: Optional[str]
    allow_writes: bool
    include_admin: bool
    started: dt.datetime
    seconds: float
    interrupted: bool = False

    def count(self, status: str) -> int:
        return sum(1 for r in self.results if r.status == status)


def _duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return ""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(int(round(seconds)), 60)
    return f"{minutes}m {rest:02d}s"


def _summary(report: Report) -> str:
    text = (
        f"{report.count(PASS)} passed, {report.count(FAIL)} failed, "
        f"{report.count(SKIP)} skipped in {_duration(report.seconds)}"
    )
    return text + (" (interrupted)" if report.interrupted else "")


def _setup(report: Report) -> str:
    return " | ".join(
        [
            report.pltr_version,
            f"profile {report.profile}" if report.profile else "default credentials",
            f"writes {'on' if report.allow_writes else 'off'}",
            f"admin checks {'on' if report.include_admin else 'off'}",
            report.started.strftime("%Y-%m-%d %H:%M UTC"),
        ]
    )


def _not_run_lines(report: Report) -> List[str]:
    lines = []
    if report.not_run.get("write"):
        lines.append(
            f"Not run: {_count(report.not_run['write'], 'write check')} "
            "(--allow-writes --scratch-folder RID)."
        )
    if report.not_run.get("admin"):
        lines.append(
            f"Not run: {_count(report.not_run['admin'], 'admin check')} (--include-admin)."
        )
    for key, rid in report.leftovers:
        lines.append(
            f"Left behind ({key}): {rid}; move it to the trash with "
            f"`pltr resource delete {rid} --yes`."
        )
    return lines


def render_text(report: Report) -> str:
    out = [f"pltr smoke test: {_summary(report)}", _setup(report), ""]
    width = max([len(r.check.id) for r in report.results] + [5])
    out.append(f"{'RESULT':6}  {'CHECK':{width}}  {'TIME':>7}  DETAILS")
    for r in report.results:
        out.append(
            f"{r.status.upper():6}  {r.check.id:{width}}  "
            f"{_duration(r.seconds):>7}  {r.detail}".rstrip()
        )
    failed = [r for r in report.results if r.status == FAIL and r.argv is not None]
    if failed:
        out += ["", "Failed checks:"]
        for r in failed:
            out.append(f"  {r.check.id}: pltr {shlex.join(r.argv or [])}")
            if r.error:
                out.append(f"    {json.dumps(r.error, sort_keys=True)}")
    extra = _not_run_lines(report)
    if extra:
        out += [""] + extra
    return "\n".join(out)


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _md_code(text: str) -> str:
    fence = "``" if "`" in text else "`"
    pad = " " if fence == "``" else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def render_markdown(report: Report) -> str:
    out = [
        "### pltr live smoke test",
        "",
        f"**{_summary(report)}** ({_setup(report)})",
        "",
        "| Result | Check | Command | Time | Details |",
        "|---|---|---|---|---|",
    ]
    for r in report.results:
        status = {PASS: "PASS", FAIL: "**FAIL**", SKIP: "skip"}[r.status]
        out.append(
            "| "
            + " | ".join(
                [
                    status,
                    _md_code(r.check.id),
                    _md_cell(_md_code(command_template(r.check))),
                    _duration(r.seconds),
                    _md_cell(r.detail),
                ]
            )
            + " |"
        )
    extra = _not_run_lines(report)
    if extra:
        out += [""] + extra
    out += [
        "",
        "Commands show inputs as `<key>`; every check also gets `--profile` "
        "when one is given. Generated by `scripts/smoke.py`.",
    ]
    return "\n".join(out)


def render_plan(checks: Sequence[Check], markdown: bool) -> str:
    """The checks and their commands (--list)."""
    if markdown:
        out = ["| Check | Kind | Command | Verifies |", "|---|---|---|---|"]
        for c in checks:
            out.append(
                f"| {_md_code(c.id)} | {c.kind} | "
                f"{_md_cell(_md_code(command_template(c)))} | {_md_cell(c.about)} |"
            )
        return "\n".join(out)
    width = max(len(c.id) for c in checks)
    lines = []
    for c in checks:
        lines.append(f"{c.id:{width}}  {c.kind:11}  {command_template(c)}")
    return "\n".join(lines)


# ---------------------------------------------------------------- main


def prepare_files(tmp: Path) -> None:
    for relative, content in UPLOAD_FILES.items():
        path = tmp / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (tmp / "download").mkdir(exist_ok=True)


def run_values(tmp: Path, now: dt.datetime) -> Dict[str, str]:
    return {
        "run.name": f"pltr-smoke-{now:%Y%m%d-%H%M%S}",
        "run.tmp": str(tmp),
        "run.since": (now - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run.today": now.strftime("%Y-%m-%d"),
        "run.week_ago": (now - dt.timedelta(days=7)).strftime("%Y-%m-%d"),
    }


def pltr_version(runner: Runner, timeout: float) -> str:
    run = runner(["--version"], {"PLTR_DEBUG": None}, timeout)
    text = run.stdout.strip()
    return text if run.exit_code == 0 and text else "pltr (version unknown)"


def main(
    argv: Optional[Sequence[str]] = None,
    runner: Optional[Runner] = None,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
    now: Optional[dt.datetime] = None,
) -> int:
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    args = build_parser().parse_args(argv)
    try:
        settings, inputs = gather_inputs(args)
        if args.list:
            listed, _ = select_checks(
                args.only, allow_writes=True, include_admin=True, configured={}
            )
            print(render_plan(listed, args.markdown), file=out)
            return 0
        check_write_guard(args, inputs)
        checks, not_run = select_checks(
            args.only,
            allow_writes=args.allow_writes,
            include_admin=args.include_admin,
            configured=inputs,
        )
    except ConfigError as exc:
        print(f"smoke.py: error: {exc}", file=err)
        return 2

    profile = args.profile or settings.get("profile")
    command = shlex.split(args.pltr or settings.get("pltr") or "")
    runner = runner or SubprocessRunner(command or [sys.executable, "-m", "pltr"])
    options = Options(
        profile=profile,
        allow_writes=args.allow_writes,
        include_admin=args.include_admin,
        timeout=args.timeout,
    )
    started = now or dt.datetime.now(dt.timezone.utc)

    def progress(result: CheckResult, index: int, total: int) -> None:
        print(
            f"[{index:>{len(str(total))}}/{total}] {result.status.upper():4} "
            f"{result.check.id} {_duration(result.seconds)}".rstrip(),
            file=err,
            flush=True,
        )

    clock = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="pltr-smoke-") as tmp:
        prepare_files(Path(tmp))
        ctx = Context(inputs, run_values(Path(tmp), started))
        version = pltr_version(runner, args.timeout)
        print(f"Running {len(checks)} checks with {version}...", file=err, flush=True)
        results, interrupted = run_checks(checks, ctx, runner, options, progress)
        left = leftovers(ctx, results)
    report = Report(
        results=results,
        not_run=not_run,
        leftovers=left,
        pltr_version=version,
        profile=profile,
        allow_writes=args.allow_writes,
        include_admin=args.include_admin,
        started=started,
        seconds=time.monotonic() - clock,
        interrupted=interrupted,
    )
    print(render_markdown(report) if args.markdown else render_text(report), file=out)
    if interrupted:
        return EXIT_INTERRUPTED
    return 1 if report.count(FAIL) else 0


if __name__ == "__main__":
    sys.exit(main())
