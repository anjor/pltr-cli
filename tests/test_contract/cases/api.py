"""Contract-test cases for the generated `pltr api` tree (src/pltr/commands/api/).

Every generated command follows the contract (nothing is NOT_CONVERTED). The
generic argument synthesizer can't satisfy the SDK's own argument validation
(user IDs are UUIDs, JSON options need a valid model, `--body` needs a file),
so ARGS gives every generated command arguments the SDK accepts: path
parameters and required options get the smallest value their SDK type allows,
derived from the type's JSON schema and checked with pydantic. The commands
then reach the stubbed API and must render its 404/400 errors.
"""

import importlib
import inspect
import json
import re
from functools import lru_cache
from typing import Any, Dict, Iterator, List, Optional, Tuple

import pydantic
from foundry_sdk import FoundryClient, UserTokenAuth

from pltr.commands.api import _specs
from pltr.commands.api._runtime import is_shared_paging_parameter, option_name
from tests.test_contract.cases import CONTRACT_RID, resource_rid

SUCCESS_EXEMPT = {
    "api": "generated tree: tests/test_api_commands covers the success path per namespace",
}

_UUID = "00000000-0000-4000-8000-000000000001"
_DATETIME = "2024-01-01T00:00:00Z"
_DATE = "2024-01-01"
_STRINGS = (CONTRACT_RID, "contract-test", _UUID, _DATETIME, _DATE, "contracttest")


def _walk(node: Dict[str, Any], cli: Tuple[str, ...], sdk: Tuple[str, ...]) -> Iterator:
    for method in node.get("methods", []):
        yield cli + (method["name"],), sdk + (method["sdk"],), method
    for resource in node.get("resources", []):
        yield from _walk(resource, cli + (resource["name"],), sdk + (resource["sdk"],))


def _generated_methods() -> Iterator[Tuple[str, Tuple[str, ...], Dict[str, Any]]]:
    for name, entry in sorted(_specs.NAMESPACES.items()):
        spec = importlib.import_module(f"{_specs.__name__}.{entry['module']}").SPEC
        for cli, sdk, method in _walk(spec, ("api", name), (entry["sdk"],)):
            yield " ".join(cli), sdk, method


@lru_cache(maxsize=None)
def _adapter(annotation: Any) -> pydantic.TypeAdapter:
    return pydantic.TypeAdapter(annotation)


def _accepts(annotation: Any, value: Any) -> bool:
    try:
        _adapter(annotation).validate_python(value)
        return True
    except (pydantic.ValidationError, TypeError, ValueError):
        return False


def _string(schema: Dict[str, Any]) -> str:
    if schema.get("format") == "date-time":
        return _DATETIME
    if schema.get("format") == "date":
        return _DATE
    if schema.get("format") == "uuid":
        return _UUID
    pattern = schema.get("pattern")
    for candidate in _STRINGS:
        if pattern is None or re.search(pattern, candidate):
            return candidate
    return _STRINGS[0]


class _TooDeep(Exception):
    """A (recursive) schema needs more nesting than allowed."""


def _minimal(schema: Dict[str, Any], defs: Dict[str, Any], depth_left: int = 12) -> Any:
    """The smallest JSON value a (pydantic-generated) JSON schema accepts.

    Union members are tried shallowest first, so a recursive member (a `not`
    filter wrapping another filter) loses to a flat one.
    """
    if depth_left <= 0:
        raise _TooDeep
    if "$ref" in schema:
        return _minimal(defs[schema["$ref"].split("/")[-1]], defs, depth_left - 1)
    if "const" in schema:
        return schema["const"]
    if schema.get("enum"):
        return schema["enum"][0]
    for key in ("oneOf", "anyOf", "allOf"):
        members = [m for m in schema.get(key, []) if m.get("type") != "null"]
        if members:
            for limit in sorted({min(4, depth_left - 1), depth_left - 1}):
                for member in members:
                    try:
                        return _minimal(member, defs, limit)
                    except _TooDeep:
                        continue
            raise _TooDeep
    kind = schema.get("type")
    if kind == "object":
        properties = schema.get("properties", {})
        value = {
            name: _minimal(properties.get(name, {}), defs, depth_left - 1)
            for name in schema.get("required", [])
        }
        for name, prop in properties.items():  # union discriminators
            if "const" in prop:
                value.setdefault(name, prop["const"])
        return value
    if kind == "array":
        count = schema.get("minItems", 0)
        if not count:
            return []
        return [_minimal(schema.get("items", {}), defs, depth_left - 1)] * count
    if kind == "string":
        return _string(schema)
    if kind in ("integer", "number"):
        return max(1, schema.get("minimum", 1), schema.get("exclusiveMinimum", 0) + 1)
    if kind == "boolean":
        return True
    return {}


def _sample(annotation: Any) -> Any:
    """A value the SDK accepts for `annotation` (tries each union member)."""
    schema = _adapter(annotation).json_schema()
    defs = schema.get("$defs", {})
    candidates: List[Any] = []
    for member in schema.get("oneOf") or schema.get("anyOf") or [schema]:
        try:
            candidates.append(_minimal(member, defs))
        except _TooDeep:
            continue
    candidates += list(_STRINGS) + [1, True, {}, []]
    for candidate in candidates:
        if _accepts(annotation, candidate):
            return candidate
    raise LookupError(f"no sample value for {annotation!r}")


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value)


def _arguments(spec: Dict[str, Any], method: Any) -> List[str]:
    parameters = inspect.signature(method).parameters
    positional: List[str] = []
    options: List[str] = []
    for param in spec["params"]:
        if is_shared_paging_parameter(spec, param) or param.get("auto"):
            continue
        annotation = parameters[param["name"]].annotation
        if param.get("resource") and not param.get("multiple"):
            value = resource_rid(param["resource"])
            if param["in"] == "path":
                positional.append(value)
            elif param.get("required"):
                options += [option_name(param), value]
            continue
        if param["in"] == "path":
            positional.append(_text(_sample(annotation)))
            continue
        if param.get("multiple"):
            # Left out, a required list is sent as []; give one item if [] is invalid.
            if param.get("required") and not _accepts(annotation, []):
                (item,) = _sample(annotation)[:1] or [_STRINGS[0]]
                options += [option_name(param), _text(item)]
            continue
        if not param.get("required"):
            continue
        if param["type"] == "bool":
            options.append(option_name(param))
        elif param["type"] == "bytes":
            options += [option_name(param), "-"]  # an empty body from stdin
        elif param["type"] == "choice":
            options += [option_name(param), param["choices"][0]]
        elif param["type"] == "json":
            options += [option_name(param), json.dumps(_sample(annotation))]
        else:
            options += [option_name(param), _text(_sample(annotation))]
    return positional + options


def _build_args() -> Dict[str, List[str]]:
    client = FoundryClient(auth=UserTokenAuth(token="x"), hostname="example.com")
    args: Dict[str, List[str]] = {}
    for path, sdk_path, spec in _generated_methods():
        target: Optional[Any] = client
        for attr in sdk_path:
            target = getattr(target, attr)
        args[path] = _arguments(spec, target)
    return args


ARGS = _build_args()
