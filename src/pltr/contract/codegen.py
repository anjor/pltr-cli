"""Render a foundry-platform-sdk call as a runnable Python snippet (#192).

``pltr <command> --emit-code`` prints the code for the SDK call the command
would make, with its real argument values, instead of making it. The snippet:

* reads the host and token from ``FOUNDRY_HOST`` and ``FOUNDRY_TOKEN`` (never a
  credential pltr knows);
* looks up Compass paths given for RIDs with ``Resource.get_by_path`` (#193);
* passes every argument by keyword, SDK models as constructors
  (``ontologies_models.EqualsQueryV2(field="name", value="x")``);
* pages the SDK's way: a ``for`` loop over a ``ResourceIterator``, or a loop on
  ``next_page_token`` for a paged response;
* writes binary content to the command's ``--output`` file or to stdout.
"""

from __future__ import annotations

import datetime
import enum
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


class PathValue(str):
    """A Compass path given where a RID goes: the snippet looks it up first."""


class RawExpr(str):
    """A Python expression the snippet uses verbatim (e.g. reading a file),
    with the imports it needs."""

    imports: frozenset = frozenset()

    def __new__(cls, text: str, imports: Sequence[str] = ()) -> "RawExpr":
        expression = super().__new__(cls, text)
        expression.imports = frozenset(imports)
        return expression


#: Arguments that carry credentials: the snippet reads them from the
#: environment instead of holding their values.
SECRET_ARGUMENTS: Dict[str, Tuple[str, str]] = {
    "secrets": ("SECRETS", 'json.loads(os.environ["SECRETS"])'),
    "token": ("MEDIA_SET_TOKEN", 'os.environ["MEDIA_SET_TOKEN"]'),
    "read_token": ("MEDIA_SET_READ_TOKEN", 'os.environ["MEDIA_SET_READ_TOKEN"]'),
}


@dataclass
class Call:
    """One SDK call: its path relative to ``FoundryClient`` and its arguments.

    ``paged`` is ``"iterator"`` (the method returns a ``ResourceIterator``) or
    ``"response"`` (a page model with ``data`` and ``next_page_token``).
    """

    sdk_path: str
    kwargs: Mapping[str, Any]
    paged: Optional[str] = None
    binary: bool = False
    output: Optional[str] = None
    comments: List[str] = field(default_factory=list)


def _model_module_alias(module: str) -> Optional[str]:
    parts = module.split(".")
    if len(parts) == 4 and parts[0] == "foundry_sdk" and parts[3] == "models":
        return f"{parts[2]}_models"
    return None


def render_value(
    value: Any, imports: Set[str], paths: Optional[Mapping[str, str]] = None
) -> str:
    """A Python expression for ``value``; adds the imports it needs."""
    import pydantic

    if isinstance(value, PathValue) and paths is not None and value in paths:
        return paths[value]
    if isinstance(value, RawExpr):
        imports.update(value.imports)
        return str(value)
    if isinstance(value, enum.Enum):
        value = value.value
    if value is None or isinstance(value, (bool, int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, datetime.datetime):
        imports.add("import datetime")
        return f'datetime.datetime.fromisoformat("{value.isoformat()}")'
    if isinstance(value, datetime.date):
        imports.add("import datetime")
        return f'datetime.date.fromisoformat("{value.isoformat()}")'
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(render_value(v, imports, paths) for v in value) + "]"
    if isinstance(value, dict):
        items = (
            f"{render_value(k, imports, paths)}: {render_value(v, imports, paths)}"
            for k, v in value.items()
        )
        return "{" + ", ".join(items) + "}"
    if isinstance(value, pydantic.BaseModel):
        cls = type(value)
        alias = _model_module_alias(cls.__module__)
        if alias is None:
            return render_value(
                value.model_dump(mode="json", by_alias=True), imports, paths
            )
        namespace = cls.__module__.rsplit(".", 1)[0]
        imports.add(f"from {namespace} import models as {alias}")
        parts = [
            f"{name}={render_value(getattr(value, name), imports, paths)}"
            for name in cls.model_fields
            if name in value.model_fields_set
        ]
        # Keys the SDK's model doesn't know (extra="allow") are sent too.
        extra = dict(value.model_extra or {})
        odd = {k: v for k, v in extra.items() if not str(k).isidentifier()}
        parts += [
            f"{key}={render_value(item, imports, paths)}"
            for key, item in extra.items()
            if key not in odd
        ]
        if odd:
            parts.append(f"**{render_value(odd, imports, paths)}")
        return f"{alias}.{cls.__name__}({', '.join(parts)})"
    if isinstance(value, bytes):
        return repr(value)
    return json.dumps(str(value), ensure_ascii=False)


def _path_values(value: Any) -> List[PathValue]:
    if isinstance(value, PathValue):
        return [value]
    if isinstance(value, (list, tuple)):
        return [p for v in value for p in _path_values(v)]
    if isinstance(value, dict):
        return [p for v in value.values() for p in _path_values(v)]
    return []


def _lookup_variables(kwargs: Mapping[str, Any]) -> Dict[str, str]:
    """A variable name for each distinct path, in order of appearance."""
    names: Dict[str, str] = {}
    used: Set[str] = set()
    for name, value in kwargs.items():
        for path in _path_values(value):
            if path in names:
                continue
            candidate = name if value is path and name not in used else None
            index = 1
            while candidate is None or candidate in used:
                candidate = f"{name}_{index}"
                index += 1
            names[path] = candidate
            used.add(candidate)
    return names


def _call_expression(
    sdk_path: str,
    kwargs: Mapping[str, Any],
    imports: Set[str],
    paths: Mapping[str, str],
    indent: str = "",
) -> str:
    if not kwargs:
        return f"client.{sdk_path}()"
    lines = [f"client.{sdk_path}("]
    for name, value in kwargs.items():
        lines.append(f"{indent}    {name}={render_value(value, imports, paths)},")
    lines.append(f"{indent})")
    return "\n".join(lines)


def render_snippet(call: Call) -> str:
    """The whole runnable snippet for ``call``."""
    imports: Set[str] = {"import os"}
    comments = list(call.comments)
    kwargs = dict(call.kwargs)
    for name, (variable, expression) in SECRET_ARGUMENTS.items():
        if name in kwargs:
            kwargs[name] = RawExpr(
                expression, ["import json"] if "json." in expression else []
            )
            comments.append(f"Set {variable} before running: {name} is a secret.")
    if call.paged:
        comments.append(
            "This loops over every page; pltr printed one page (--all for every page)."
        )
    call = Call(call.sdk_path, kwargs, call.paged, call.binary, call.output, comments)
    paths = _lookup_variables(call.kwargs)
    body: List[str] = []
    for path, variable in paths.items():
        lookup = _call_expression(
            "filesystem.Resource.get_by_path", {"path": str(path)}, imports, {}
        )
        body.append(f"{variable} = {lookup}.rid")
    if paths:
        body.append("")

    if call.paged == "response":
        first_token = render_value(call.kwargs.get("page_token"), imports, paths)
        kwargs = {k: v for k, v in call.kwargs.items() if k != "page_token"}
        kwargs["page_token"] = RawExpr("page_token")
        expression = _call_expression(
            call.sdk_path, kwargs, imports, paths, indent="    "
        )
        body += [
            f"page_token = {first_token}",
            "while True:",
            f"    page = {expression}",
            "    for item in page.data:",
            "        print(item)",
            "    page_token = page.next_page_token",
            "    if not page_token:",
            "        break",
        ]
    else:
        expression = _call_expression(call.sdk_path, call.kwargs, imports, paths)
        if call.paged:
            body += [f"for item in {expression}:", "    print(item)"]
        elif call.binary:
            body.append(f"content = {expression}")
            if call.output and call.output != "-":
                target = json.dumps(call.output, ensure_ascii=False)
                body += [
                    f'with open({target}, "wb") as file:',
                    "    file.write(content)",
                ]
            else:
                imports.add("import sys")
                body.append("sys.stdout.buffer.write(content)")
        else:
            body += [f"result = {expression}", "print(result)"]

    stdlib = sorted(i for i in imports if i.startswith("import "))
    third_party = sorted(i for i in imports if i.startswith("from "))
    header = [f"# {comment}" for comment in call.comments]
    lines = (
        header + stdlib + ["", "from foundry_sdk import FoundryClient, UserTokenAuth"]
    )
    lines += third_party
    lines += [
        "",
        "client = FoundryClient(",
        '    auth=UserTokenAuth(token=os.environ["FOUNDRY_TOKEN"]),',
        '    hostname=os.environ["FOUNDRY_HOST"],',
        ")",
        "",
    ]
    return "\n".join(lines + body) + "\n"
