"""Write a command's result to stdout (or ``--output``) as table, JSON or CSV.

``emit()`` is the only function commands use to print data. stdout carries
exactly that data; status messages go to stderr (:mod:`pltr.contract.runtime`).

Columns for table and CSV output are a declarative mapping from header to
either an attribute path or a callable::

    FOLDER_COLUMNS: Columns = {
        "RID": "rid",                    # python field name...
        "Display Name": "displayName",   # ...or the API (alias) name
        "Space": "space_rid",
        "Created": "created_time",       # datetimes render as ISO-8601 (UTC)
        "Org": lambda folder: ...,       # or any callable taking the row item
    }

Paths are dot-separated (``"reference.media_set_view_item.media_set_rid"``).
On SDK models every segment must be a declared field (python name or alias),
otherwise :class:`ColumnError` is raised, so a column that reads a field the
model doesn't have fails its test instead of printing an empty value. A field
that exists but is ``None`` renders as an empty cell. On plain dicts (SDK
ontology objects, raw API JSON) a missing key renders empty, because the API
omits null fields.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple, Union

import click

from .runtime import info, success
from .serialize import Page, _is_resource_iterator, to_document, to_jsonable

ColumnSpec = Union[str, Callable[[Any], Any]]
#: Ordered mapping of column header to attribute path or callable.
Columns = Mapping[str, ColumnSpec]


class ColumnError(LookupError):
    """A column path names a field that doesn't exist on the SDK model."""


# ------------------------------------------------------------------ columns


def _model_field(obj: Any, name: str) -> Any:
    fields = type(obj).model_fields
    if name in fields:
        return getattr(obj, name)
    for field_name, field_info in fields.items():
        if field_info.alias == name:
            return getattr(obj, field_name)
    known = ", ".join(sorted(fields))
    raise ColumnError(f"{type(obj).__name__} has no field {name!r} (fields: {known})")


def _get(obj: Any, name: str) -> Any:
    import pydantic

    if isinstance(obj, Mapping):
        return obj.get(name)
    if isinstance(obj, pydantic.BaseModel):
        return _model_field(obj, name)
    try:
        return getattr(obj, name)
    except AttributeError:
        raise ColumnError(f"{type(obj).__name__} has no attribute {name!r}") from None


def column_value(item: Any, spec: ColumnSpec) -> Any:
    """Resolve one column spec against a row item (see module docstring)."""
    if callable(spec):
        return spec(item)
    value = item
    for segment in spec.split("."):
        if value is None:
            return None
        value = _get(value, segment)
    return value


def format_cell(value: Any) -> str:
    """Render a value for a table or CSV cell.

    ``None`` is empty, datetimes are ISO-8601 in UTC (as the SDK serializes
    them), booleans are ``true``/``false`` and nested values are compact JSON.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.isoformat()
    jsonable = to_jsonable(value)
    if jsonable is None:
        return ""
    if isinstance(jsonable, str):
        return jsonable
    if isinstance(jsonable, bool):
        return "true" if jsonable else "false"
    if isinstance(jsonable, (int, float)):
        return str(jsonable)
    return json.dumps(jsonable, separators=(",", ":"), ensure_ascii=False)


def auto_columns(items: List[Any]) -> Columns:
    """Columns for results without curated columns (e.g. generated commands).

    SDK models: every declared field that is set on at least one item, headed
    by its API name. Dicts: every key, in order of first appearance. Anything
    else: a single ``Value`` column.
    """
    import pydantic

    if items and all(isinstance(item, pydantic.BaseModel) for item in items):
        model_type = type(items[0])
        columns: Dict[str, ColumnSpec] = {}
        for name, field_info in model_type.model_fields.items():
            if any(getattr(item, name, None) is not None for item in items):
                columns[field_info.alias or name] = name
        return columns
    if items and all(isinstance(item, Mapping) for item in items):
        keys: Dict[str, Any] = {}
        for item in items:
            for key in item:
                keys.setdefault(str(key), key)
        return {header: _key_getter(key) for header, key in keys.items()}
    return {"Value": _identity}


def _key_getter(key: Any) -> Callable[[Any], Any]:
    def get(item: Any) -> Any:
        return item.get(key)

    return get


def _identity(item: Any) -> Any:
    return item


# --------------------------------------------------------------------- emit


def _rows(
    result: Any, rows: Optional[Callable[[Any], Iterable[Any]]]
) -> Tuple[List[Any], bool, Optional[str]]:
    """Return (row items, is_single_object, next_page_token)."""
    if rows is not None:
        return list(rows(result)), False, None
    if isinstance(result, Page) or _is_resource_iterator(result):
        return list(result.data), False, result.next_page_token
    if isinstance(result, (list, tuple)):
        return list(result), False, None
    return [result], True, None


def _render_table(
    items: List[Any],
    columns: Columns,
    single: bool,
    title: Optional[str],
    console: Any,
) -> None:
    from rich.table import Table
    from rich.text import Text

    if single:
        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", overflow="fold")
        for header, spec in columns.items():
            table.add_row(header, Text(format_cell(column_value(items[0], spec))))
    else:
        table = Table(title=title, show_header=True, header_style="bold cyan")
        for header in columns:
            if "rid" in header.lower():
                table.add_column(header, no_wrap=True, overflow="fold")
            else:
                table.add_column(header, overflow="fold")
        for item in items:
            table.add_row(
                *(
                    Text(format_cell(column_value(item, spec)))
                    for spec in columns.values()
                )
            )
    console.print(table)


def _render_csv(items: List[Any], columns: Columns) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(list(columns))
    for item in items:
        writer.writerow(
            [format_cell(column_value(item, spec)) for spec in columns.values()]
        )
    return buffer.getvalue()


def _write_text(text: str, output: Optional[str]) -> None:
    if output:
        with open(output, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    else:
        click.echo(text, nl=False)


def emit(
    result: Any,
    *,
    format: str,
    output: Optional[str] = None,
    columns: Optional[Columns] = None,
    rows: Optional[Callable[[Any], Iterable[Any]]] = None,
    title: Optional[str] = None,
) -> None:
    """Write ``result`` to stdout, or to the ``output`` file, in ``format``.

    Args:
        result: what the SDK returned: a model, a dict, a list, a
            :class:`Page`, an SDK ``ResourceIterator`` (its current page) or
            ``None`` (a call with no response body).
        format: ``table``, ``json`` or ``csv`` (the command's ``--format``).
        output: file path from ``--output``; stdout when ``None``.
        columns: curated table/CSV columns (see module docstring). Defaults
            to :func:`auto_columns`. Ignored for JSON.
        rows: for table/CSV only, a callable returning the row items when
            they aren't ``result`` itself, e.g. ``lambda r: r.data.values()``
            for a batch response whose ``data`` is a dict.
        title: optional table title.

    JSON prints exactly one document: the SDK's own serialization of
    ``result`` (lists in the paged shape ``{"data": [...],
    "nextPageToken": ...}``, ``None`` as ``null``). A single object renders as
    a vertical Property/Value table; lists render one row per item. When a
    page has more results, a hint with the next ``--page-token`` goes to
    stderr (JSON carries it as ``nextPageToken``).
    """
    fmt = (format or "table").lower()
    if fmt == "json":
        document = json.dumps(to_document(result), indent=2, ensure_ascii=True)
        _write_text(document + "\n", output)
        if output:
            success(f"Wrote JSON output to {output}")
        return

    if result is None and rows is None:
        if output:
            _write_text("", output)
        return

    items, single, next_page_token = _rows(result, rows)
    cols = columns if columns is not None else auto_columns(items)

    if fmt == "csv":
        _write_text(_render_csv(items, cols), output)
        if output:
            success(f"Wrote {len(items)} row(s) to {output}")
    elif not items:
        info("No results.")
        if output:
            _write_text("", output)
    else:
        from rich.console import Console

        if output:
            with open(output, "w", encoding="utf-8") as handle:
                console = Console(file=handle, width=240, highlight=False)
                _render_table(items, cols, single, title, console)
            success(f"Wrote table output to {output}")
        else:
            _render_table(items, cols, single, title, Console(highlight=False))

    if next_page_token:
        info(
            f"More results available. Next page: --page-token {next_page_token} "
            "(or --all to fetch every page)."
        )
