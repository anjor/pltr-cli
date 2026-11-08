"""Generate the `pltr api` command specs from the installed foundry-platform-sdk.

The generator introspects the SDK client tree (namespaces -> resources -> nested
resources -> public methods) with `inspect`, type hints, docstrings and the
`core.RequestInfo(...)` call in each method body, and writes declarative spec
modules (plain Python literals) under `src/pltr/commands/api/_specs/`. The runtime
in `src/pltr/commands/api/_runtime.py` turns those specs into click commands lazily.

    uv run python scripts/generate_api_commands.py           # regenerate the specs
    uv run python scripts/generate_api_commands.py --check   # exit 1 if they are stale

The output is deterministic: it does not depend on the Python version, the OS or the
order in which the SDK registers things, so a staleness check can compare bytes.
Run it after every foundry-platform-sdk bump and review the diff (new methods, beta
labels, destructive flags). It fails, with instructions, when a new method needs a
human decision (a destructive-looking name that is not reviewed, or a method the
runtime cannot call such as a server-sent-events stream).
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import datetime
import importlib
import inspect
import json
import re
import sys
import textwrap
import types
import typing
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

from pltr.contract.resources import kind_for_sdk_type

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "src" / "pltr" / "commands" / "api" / "_specs"
SPECS_PACKAGE = "pltr.commands.api._specs"

# ---------------------------------------------------------------------------
# Configuration (reviewed by hand; refresh on every SDK bump)
# ---------------------------------------------------------------------------

# Words in method names that suggest an operation destroys or overwrites data.
# Every SDK method with one of them as a `_`-separated word of its name
# (`delete`, `bulk_delete`, `delete_batch`, `reset_offsets`, ...) must appear
# either in the version's `destructive` set or in its `not_destructive` set, so a
# new method is never classified silently.
DESTRUCTIVE_NAME_SEED = re.compile(
    r"(?:^|_)(?:delete|abort|cancel|disable|remove|revoke|replace|reset|clear"
    r"|undeploy|unregister|purge)(?:_|$)"
)


def looks_destructive(method_name: str) -> bool:
    """Whether a method name has a destructive word (see DESTRUCTIVE_NAME_SEED)."""
    return DESTRUCTIVE_NAME_SEED.search(method_name) is not None


# The shared pltr.contract options that every generated command (or some of
# them) adds. An SDK parameter whose option name collides with one of these is
# exposed as `--api-<name>`. (`--page-size`/`--page-token` of paged methods are
# the SDK's own parameters, provided by the shared paging options.)
RESERVED_OPTION_NAMES = frozenset(
    {"all", "format", "help", "max-pages", "output", "profile", "yes"}
)


@dataclasses.dataclass(frozen=True)
class ApiVersionConfig:
    """Everything the generator needs to know about one SDK client."""

    key: str
    # Import path of the SDK client class, "module:attribute".
    client: str
    # None: namespaces live directly under `pltr api`. A string (e.g. "v3") puts them
    # under `pltr api <cli_group> <namespace> ...`.
    cli_group: Optional[str]
    # Prefix of the generated spec module names (e.g. "v3_" -> _specs/v3_filesystem.py).
    module_prefix: str
    # Explicit, reviewed list of destructive methods ("namespace.Resource.method").
    destructive: frozenset
    # Methods whose names match DESTRUCTIVE_NAME_SEED but that were reviewed and are
    # not destructive.
    not_destructive: frozenset
    # Methods that get no generated command, with the reason (shown by coverage).
    excluded: Mapping[str, str]
    # Paged methods whose API returns a next page token on every page, even when
    # there is nothing more to read yet (clients poll with it), with the reason.
    # Their `--all`/`--max-pages` stop at the first empty page instead of paging
    # forever (spec key `stop_at_empty_page`).
    stop_at_empty_page: Mapping[str, str] = dataclasses.field(default_factory=dict)


V2_DESTRUCTIVE = frozenset(
    {
        # Names with a destructive word (DESTRUCTIVE_NAME_SEED): delete,
        # permanently_delete, remove*, revoke*, replace*, abort, cancel, disable.
        "admin.Enrollment.EnrollmentRoleAssignment.remove",
        "admin.Group.GroupMember.remove",
        "admin.Group.MembershipExpirationPolicy.replace",
        "admin.Group.ProviderInfo.replace",
        "admin.Group.delete",
        "admin.Group.replace",
        "admin.Marking.MarkingMember.remove",
        "admin.Marking.MarkingRoleAssignment.remove",
        "admin.Marking.replace",
        "admin.MarkingCategory.replace",
        "admin.Organization.OrganizationGuestMember.remove",
        "admin.Organization.OrganizationRoleAssignment.remove",
        "admin.Organization.replace",
        "admin.User.ProviderInfo.replace",
        "admin.User.delete",
        "admin.User.revoke_all_tokens",
        "aip_agents.Agent.Session.cancel",
        "aip_agents.Agent.Session.delete",
        "connectivity.Connection.FileImport.delete",
        "connectivity.Connection.FileImport.replace",
        "connectivity.Connection.TableImport.delete",
        "connectivity.Connection.TableImport.replace",
        "data_health.Check.delete",
        "data_health.Check.replace",
        "datasets.Dataset.Branch.delete",
        "datasets.Dataset.File.delete",
        "datasets.Dataset.Transaction.abort",
        "datasets.View.remove_backing_datasets",
        "datasets.View.replace_backing_datasets",
        "filesystem.Folder.replace",
        "filesystem.Project.Reference.remove",
        "filesystem.Project.remove_organizations",
        "filesystem.Project.replace",
        "filesystem.Resource.Role.remove",
        "filesystem.Resource.Tag.remove",
        "filesystem.Resource.delete",
        "filesystem.Resource.permanently_delete",
        "filesystem.Resource.remove_markings",
        "filesystem.Space.delete",
        "filesystem.Space.replace",
        "functions.Execution.cancel",
        "media_sets.MediaSet.abort",
        "models.LiveDeployment.disable",
        "models.LiveDeployment.replace",
        "models.Model.Function.replace",
        "orchestration.Build.cancel",
        "orchestration.Schedule.delete",
        "orchestration.Schedule.replace",
        "sql_queries.SqlQuery.cancel",
        "streams.Dataset.Stream.Subscriber.delete",
        "third_party_applications.ThirdPartyApplication.Website.Version.delete",
        "widgets.WidgetSet.Release.delete",
        # Reviewed additions whose names don't say so.
        # Overwrites stored secret values, which can't be read back.
        "connectivity.Connection.update_secrets",
        # Replaces the dataset's schema on a branch.
        "datasets.Dataset.put_schema",
        # Reviewed first by hand; their names have a destructive word too (reset,
        # clear, undeploy).
        # Soft-deletes the item at a path and every older item at that path.
        "media_sets.MediaSet.clear",
        # Clears the stream's existing records.
        "streams.Dataset.Stream.reset",
        # Moves a subscriber's committed offsets.
        "streams.Dataset.Stream.Subscriber.reset_offsets",
        # Takes the website offline.
        "third_party_applications.ThirdPartyApplication.Website.undeploy",
    }
)

SSE_REASON = (
    "Streams server-sent events (the SDK returns an SseContextManager). Generated "
    "commands print one JSON document, so SSE methods are left out for now."
)

INT_PATH_REASON = (
    "Can't be called through foundry-platform-sdk 1.111.0: the SDK URL-quotes path "
    "parameters with urllib.parse.quote, which raises for this method's integer "
    "path parameter, so no request is ever sent (SDKInternalError). Re-check after "
    "an SDK bump."
)

V2 = ApiVersionConfig(
    key="v2",
    client="foundry_sdk.v2:FoundryClient",
    cli_group=None,
    module_prefix="",
    destructive=V2_DESTRUCTIVE,
    not_destructive=frozenset(),
    excluded={
        "functions.Query.streaming_execute": SSE_REASON,
        "functions.Query.streaming_execute_events": SSE_REASON,
        "media_sets.MediaSet.tile": INT_PATH_REASON,
        "models.ModelStudio.ConfigVersion.get": INT_PATH_REASON,
    },
    stop_at_empty_page={
        "audit.Organization.LogFile.list": (
            "Without an end date the API returns a nextPageToken on every page, to "
            "poll for new log files (see its end_date parameter)."
        ),
    },
)

# Adding V3 means adding an ApiVersionConfig here (for example key="v3",
# client="foundry_sdk.v3:FoundryClient", cli_group="v3", module_prefix="v3_") and a
# client factory for "v3" in the runtime.
API_VERSIONS: Tuple[ApiVersionConfig, ...] = (V2,)

# Parameters the CLI never exposes: `preview` is passed automatically for beta
# methods, the other two are SDK plumbing.
HIDDEN_PARAMETERS = frozenset({"preview", "request_timeout", "_sdk_internal"})

GENERATED_HEADER = (
    "# Generated by scripts/generate_api_commands.py. Do not edit by hand.\n"
    "# Regenerate with: uv run python scripts/generate_api_commands.py\n"
)


class GeneratorError(Exception):
    """A problem that needs a human decision before the specs can be generated."""


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class MethodInfo:
    """One public SDK method and where it lives in the client tree."""

    sdk_path: Tuple[str, ...]  # ("admin", "User", "list")
    function: Any  # the unwrapped function defined in the SDK source
    bound: Any  # the bound (decorated) method on a client instance

    @property
    def dotted(self) -> str:
        return ".".join(self.sdk_path)


@dataclasses.dataclass
class ResourceInfo:
    """A resource client (possibly nested) with its methods and sub-resources."""

    sdk_path: Tuple[str, ...]  # ("admin", "User")
    obj: Any
    methods: List[MethodInfo]
    resources: List["ResourceInfo"]


def load_client(config: ApiVersionConfig) -> Any:
    """Instantiate the SDK client with dummy auth (no network access happens)."""
    from foundry_sdk import UserTokenAuth

    module_name, _, attr = config.client.partition(":")
    client_cls = getattr(importlib.import_module(module_name), attr)
    return client_cls(
        auth=UserTokenAuth(token="generator"), hostname="generator.invalid"
    )


def iter_namespaces(client: Any) -> List[Tuple[str, Any]]:
    """Namespace clients are the client instance's `*Client` attributes."""
    found = []
    for attr, value in vars(client).items():
        cls = type(value)
        if cls.__module__.startswith("foundry_sdk.") and cls.__name__.endswith(
            "Client"
        ):
            found.append((attr, value))
    return sorted(found, key=lambda item: item[0])


def _child_resources(obj: Any) -> List[Tuple[str, Any]]:
    cls = type(obj)
    children = []
    for name, attr in vars(cls).items():
        if not name.startswith("_") and isinstance(attr, cached_property):
            children.append((name, getattr(obj, name)))
    return sorted(children, key=lambda item: item[0])


def _public_methods(obj: Any) -> List[Tuple[str, Any]]:
    cls = type(obj)
    methods = []
    for name, attr in vars(cls).items():
        if not name.startswith("_") and inspect.isfunction(attr):
            methods.append((name, attr))
    return sorted(methods, key=lambda item: item[0])


def walk_resource(obj: Any, sdk_path: Tuple[str, ...]) -> ResourceInfo:
    methods = [
        MethodInfo(
            sdk_path=sdk_path + (name,),
            function=inspect.unwrap(attr),
            bound=getattr(obj, name),
        )
        for name, attr in _public_methods(obj)
    ]
    resources = [
        walk_resource(child, sdk_path + (name,))
        for name, child in _child_resources(obj)
    ]
    return ResourceInfo(
        sdk_path=sdk_path, obj=obj, methods=methods, resources=resources
    )


def discover(config: ApiVersionConfig) -> List[Tuple[str, List[ResourceInfo]]]:
    """Return [(namespace attr, [top-level resources])] for one API version."""
    client = load_client(config)
    namespaces = []
    for ns_attr, ns_obj in iter_namespaces(client):
        resources = [
            walk_resource(child, (ns_attr, name))
            for name, child in _child_resources(ns_obj)
        ]
        namespaces.append((ns_attr, resources))
    return namespaces


def iter_methods(resources: List[ResourceInfo]) -> Iterator[MethodInfo]:
    for resource in resources:
        yield from resource.methods
        yield from iter_methods(resource.resources)


def all_public_methods(config: ApiVersionConfig = V2) -> List[str]:
    """Every public SDK method of one API version, as dotted paths (sorted)."""
    return sorted(
        method.dotted
        for _, resources in discover(config)
        for method in iter_methods(resources)
    )


# ---------------------------------------------------------------------------
# Analysis of one method
# ---------------------------------------------------------------------------


def kebab(name: str) -> str:
    """CamelCase / snake_case -> kebab-case (CbacBanner -> cbac-banner)."""
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "-", name)
    return name.replace("_", "-").lower()


@dataclasses.dataclass
class RequestShape:
    """What the method's `core.RequestInfo(...)` call says about the HTTP request."""

    http_method: str
    resource_path: str
    path: Dict[str, str]  # python parameter -> API name
    query: Dict[str, str]
    header: Dict[str, str]
    body: List[str]  # python parameters that end up in the body
    accept: Optional[str]


def _dict_params(node: ast.AST) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Split a RequestInfo dict literal into {param: api name} and {api name: constant}."""
    params: Dict[str, str] = {}
    constants: Dict[str, str] = {}
    if not isinstance(node, ast.Dict):
        return params, constants
    for key, value in zip(node.keys, node.values):
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            continue
        if isinstance(value, ast.Name):
            params[value.id] = key.value
        elif isinstance(value, ast.Constant) and isinstance(value.value, str):
            constants[key.value] = value.value
    return params, constants


def request_shape(method: MethodInfo) -> RequestShape:
    source = textwrap.dedent(inspect.getsource(method.function))
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "RequestInfo"
        ):
            keywords = {kw.arg: kw.value for kw in node.keywords}
            break
    else:
        raise GeneratorError(f"{method.dotted}: no core.RequestInfo(...) call found")

    http_method = keywords["method"]
    resource_path = keywords["resource_path"]
    if not (
        isinstance(http_method, ast.Constant)
        and isinstance(resource_path, ast.Constant)
    ):
        raise GeneratorError(f"{method.dotted}: non-literal HTTP method or path")
    path, _ = _dict_params(keywords.get("path_params", ast.Dict(keys=[], values=[])))
    query, _ = _dict_params(keywords.get("query_params", ast.Dict(keys=[], values=[])))
    header, header_constants = _dict_params(
        keywords.get("header_params", ast.Dict(keys=[], values=[]))
    )
    body_node = keywords.get("body")
    body = []
    if body_node is not None:
        body = sorted({n.id for n in ast.walk(body_node) if isinstance(n, ast.Name)})
    return RequestShape(
        http_method=str(http_method.value),
        resource_path=str(resource_path.value),
        path=path,
        query=query,
        header=header,
        body=body,
        accept=header_constants.get("Accept"),
    )


@dataclasses.dataclass
class Docstring:
    description: str
    params: Dict[str, str]
    types: Dict[str, str]


_FIELD_RE = re.compile(r"^:(param|type|return|rtype|raises)\b")


def parse_docstring(doc: Optional[str]) -> Docstring:
    """Split an SDK docstring into description, `:param` and `:type` texts."""
    text = inspect.cleandoc(doc or "")
    lines = [line.rstrip() for line in text.splitlines()]
    description: List[str] = []
    fields: List[List[str]] = []
    for line in lines:
        if _FIELD_RE.match(line):
            fields.append([line])
        elif fields:
            fields[-1].append(line)
        else:
            description.append(line)
    params: Dict[str, str] = {}
    types_: Dict[str, str] = {}
    for field in fields:
        match = re.match(r"^:(param|type)\s+(\w+):(.*)$", field[0])
        if not match:
            continue
        kind, name, first = match.groups()
        value = " ".join(part.strip() for part in [first, *field[1:]] if part.strip())
        (params if kind == "param" else types_)[name] = value
    return Docstring(
        description=normalize_text("\n".join(description)),
        params=params,
        types=types_,
    )


def normalize_text(text: str) -> str:
    """Strip trailing spaces, collapse blank-line runs, trim the ends."""
    lines = [line.rstrip() for line in text.strip().splitlines()]
    out: List[str] = []
    for line in lines:
        if not line and out and not out[-1]:
            continue
        out.append(line)
    return "\n".join(out).strip()


def prose_paragraphs(description: str) -> List[str]:
    """Paragraphs other than the `Required scopes: [...]` line."""
    return [
        paragraph
        for paragraph in description.split("\n\n")
        if paragraph.strip() and not paragraph.startswith("Required scopes:")
    ]


def summarize(description: str, limit: int = 100) -> str:
    """First sentence of the first prose paragraph, at most `limit` characters."""
    paragraphs = prose_paragraphs(description)
    if not paragraphs:
        return ""
    paragraph = " ".join(paragraphs[0].split())
    match = re.search(r"(?<=[.!?])\s", paragraph)
    sentence = paragraph[: match.start()] if match else paragraph
    if len(sentence) > limit:
        sentence = sentence[: limit - 3].rstrip() + "..."
    return sentence


def _strip_annotation(annotation: Any) -> Tuple[Any, bool]:
    """Remove Annotated[...] and Optional[...] wrappers; report optionality."""
    optional = False
    while True:
        origin = typing.get_origin(annotation)
        if origin is typing.Annotated:
            annotation = typing.get_args(annotation)[0]
            continue
        if origin is typing.Union or (
            hasattr(types, "UnionType") and origin is getattr(types, "UnionType")
        ):
            args = typing.get_args(annotation)
            non_none = [arg for arg in args if arg is not type(None)]
            if len(non_none) < len(args):
                optional = True
            if len(non_none) == 1:
                annotation = non_none[0]
                continue
        return annotation, optional


_PRIMITIVES = {str: "str", int: "int", float: "float", bool: "bool"}


def _pydantic_datetime_kind(annotation: Any) -> Optional[str]:
    import pydantic

    datetimes = ("AwareDatetime", "NaiveDatetime", "PastDatetime", "FutureDatetime")
    dates = ("PastDate", "FutureDate")
    for name in datetimes:
        if annotation is getattr(pydantic, name, object()):
            return "datetime"
    for name in dates:
        if annotation is getattr(pydantic, name, object()):
            return "date"
    return None


def scalar_type(annotation: Any) -> Optional[Dict[str, Any]]:
    """CLI type for a scalar SDK annotation, or None if it is not a scalar."""
    annotation, _ = _strip_annotation(annotation)
    for py_type, name in _PRIMITIVES.items():
        if annotation is py_type:
            return {"type": name}
    if annotation is datetime.datetime:
        return {"type": "datetime"}
    if annotation is datetime.date:
        return {"type": "date"}
    pydantic_kind = _pydantic_datetime_kind(annotation)
    if pydantic_kind:
        return {"type": pydantic_kind}
    if typing.get_origin(annotation) is typing.Literal:
        values = typing.get_args(annotation)
        if values and all(isinstance(value, str) for value in values):
            return {"type": "choice", "choices": list(values)}
    return None


def parameter_type(annotation: Any) -> Dict[str, Any]:
    """Map an SDK parameter annotation to the CLI type description."""
    stripped, _ = _strip_annotation(annotation)
    if stripped is bytes:
        return {"type": "bytes"}
    scalar = scalar_type(stripped)
    if scalar is not None:
        return scalar
    if typing.get_origin(stripped) in (list, typing.List):
        (item,) = typing.get_args(stripped) or (typing.Any,)
        item_scalar = scalar_type(item)
        if item_scalar is not None and item_scalar["type"] != "bool":
            return {**item_scalar, "multiple": True}
    # Models, unions, dicts, lists of models and Any: JSON validated by the SDK.
    return {"type": "json"}


def response_kind(method: MethodInfo, shape: RequestShape) -> Dict[str, Any]:
    """Classify the method's response: sse, binary, paged (iterator/response)."""
    import pydantic
    from foundry_sdk._core.resource_iterator import ResourceIterator
    from foundry_sdk._core.sse import SseContextManager

    signature = inspect.signature(method.function)
    annotation = signature.return_annotation
    origin = typing.get_origin(annotation)
    if origin is SseContextManager or shape.accept == "text/event-stream":
        return {"sse": True}
    stripped, _ = _strip_annotation(annotation)
    if isinstance(stripped, type) and issubclass(stripped, bytes):
        return {"binary": True}
    has_page_token = "page_token" in signature.parameters
    if origin is ResourceIterator:
        if not has_page_token:
            raise GeneratorError(
                f"{method.dotted} returns a ResourceIterator but takes no page_token; "
                "the runtime can't page it. Decide how to expose it (or exclude it)."
            )
        return {"paged": "iterator"}
    if (
        has_page_token
        and isinstance(stripped, type)
        and issubclass(stripped, pydantic.BaseModel)
        and {"data", "next_page_token"} <= set(stripped.model_fields)
    ):
        return {"paged": "response"}
    return {}


def _schema_name(type_text: Optional[str]) -> Optional[str]:
    if not type_text:
        return None
    text = " ".join(type_text.split())
    match = re.fullmatch(r"Optional\[(.*)\]", text)
    return match.group(1) if match else text


def method_spec(
    method: MethodInfo, config: ApiVersionConfig
) -> Optional[Dict[str, Any]]:
    """Build the spec dict for one method, or None if it is excluded."""
    shape = request_shape(method)
    kind = response_kind(method, shape)
    dotted_in_namespace = method.dotted
    if kind.get("sse"):
        if dotted_in_namespace not in config.excluded:
            raise GeneratorError(
                f"{method.dotted} streams server-sent events, which generated commands "
                "don't support. Add it to the `excluded` mapping of the "
                f"{config.key} config in scripts/generate_api_commands.py with a reason."
            )
        return None
    if dotted_in_namespace in config.excluded:
        return None

    signature = inspect.signature(method.function)
    doc = parse_docstring(method.function.__doc__)
    has_bytes_body = False
    params: List[Dict[str, Any]] = []
    for parameter in list(signature.parameters.values())[1:]:
        name = parameter.name
        if name in HIDDEN_PARAMETERS:
            continue
        if parameter.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            raise GeneratorError(f"{method.dotted}: unsupported parameter kind {name}")
        param: Dict[str, Any] = {"name": name}
        if name in shape.path:
            param["in"] = "path"
            param["api"] = shape.path[name]
        elif name in shape.query:
            param["in"] = "query"
            param["api"] = shape.query[name]
        elif name in shape.header:
            param["in"] = "header"
            param["api"] = shape.header[name]
        elif name in shape.body:
            param["in"] = "body"
        else:
            raise GeneratorError(
                f"{method.dotted}: can't tell where parameter {name!r} is sent"
            )
        param.update(parameter_type(parameter.annotation))
        if param["in"] == "path" and param["type"] not in ("str", "choice"):
            raise GeneratorError(
                f"{method.dotted} has a non-string path parameter {name!r}, which "
                "foundry-platform-sdk 1.111.0 can't URL-quote (the call fails before "
                "sending a request). Check whether the installed SDK still fails; if "
                f"so, add it to the `excluded` mapping of the {config.key} config in "
                "scripts/generate_api_commands.py with INT_PATH_REASON, otherwise "
                "relax this check."
            )
        if param["type"] == "bytes":
            has_bytes_body = True
        if param["type"] == "json" or param["in"] == "path":
            # The SDK type name (e.g. DatasetRid, SearchJsonQueryV2) tells users what
            # to pass and where to look in Foundry's API docs.
            schema = _schema_name(doc.types.get(name))
            if schema:
                param["schema"] = schema
        resource_kind = kind_for_sdk_type(doc.types.get(name))
        if resource_kind and param["type"] == "str":
            # The RID of a Compass resource: the command accepts its path too (#193).
            param["resource"] = resource_kind
        if parameter.default is inspect.Parameter.empty:
            param["required"] = True
        option = kebab(name)
        if param["in"] != "path" and option in RESERVED_OPTION_NAMES:
            param["option"] = f"--api-{option}"
        help_text = doc.params.get(name, "")
        if help_text:
            param["help"] = help_text
        params.append(param)

    if has_bytes_body:
        # Uploads must state their size; compute it from the file when omitted.
        for param in params:
            if param["name"] == "content_length" and param.get("required"):
                del param["required"]
                param["auto"] = "body_length"

    method_name = method.sdk_path[-1]
    destructive = method.dotted in config.destructive
    if looks_destructive(method_name) and not (
        destructive or method.dotted in config.not_destructive
    ):
        raise GeneratorError(
            f"{method.dotted} looks destructive ({method_name!r}). Review it and add it "
            f"to the `destructive` or `not_destructive` set of the {config.key} config "
            "in scripts/generate_api_commands.py."
        )

    http = f"{shape.http_method} {shape.resource_path}"
    description = doc.description
    if not prose_paragraphs(description):
        # Some SDK docstrings only list the required scopes.
        fallback = f"Calls {http} (SDK: client.{method.dotted})."
        description = f"{fallback}\n\n{description}" if description else fallback
    spec: Dict[str, Any] = {
        "name": kebab(method_name),
        "sdk": method_name,
        "summary": summarize(description),
        "help": description,
        "http": http,
    }
    if "preview" in signature.parameters:
        spec["beta"] = True
    if kind.get("paged"):
        spec["paged"] = kind["paged"]
    if method.dotted in config.stop_at_empty_page:
        if not kind.get("paged"):
            raise GeneratorError(
                f"{method.dotted} is listed in the {config.key} `stop_at_empty_page` "
                "config but isn't a paged method. Remove it."
            )
        spec["stop_at_empty_page"] = True
    if kind.get("binary"):
        spec["binary"] = True
    if destructive:
        spec["destructive"] = True
    spec["params"] = params
    return spec


# ---------------------------------------------------------------------------
# Building the spec tree
# ---------------------------------------------------------------------------


def _short_list(prefix: str, items: List[str], limit: int = 100) -> str:
    text = prefix + ", ".join(items)
    if len(text) > limit:
        text = text[: limit - 3].rstrip(", ") + "..."
    return text


def resource_spec(
    resource: ResourceInfo, config: ApiVersionConfig
) -> Optional[Dict[str, Any]]:
    methods = [
        spec
        for spec in (method_spec(method, config) for method in resource.methods)
        if spec is not None
    ]
    children = [
        spec
        for spec in (resource_spec(child, config) for child in resource.resources)
        if spec is not None
    ]
    if not methods and not children:
        return None
    names = [m["name"] for m in methods] + [c["name"] for c in children]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise GeneratorError(
            f"{'.'.join(resource.sdk_path)}: CLI name collision {duplicates}"
        )
    sdk_name = "client." + ".".join(resource.sdk_path)
    spec: Dict[str, Any] = {
        "name": kebab(resource.sdk_path[-1]),
        "sdk": resource.sdk_path[-1],
        "summary": _short_list(sdk_name + ": ", sorted(names)),
        "help": (
            f"Commands for the {resource.sdk_path[-1]} resource "
            f"(SDK: {sdk_name}), one per SDK method."
        ),
        "methods": methods,
    }
    if children:
        spec["resources"] = children
    return spec


def namespace_spec(
    ns_attr: str, resources: List[ResourceInfo], config: ApiVersionConfig
) -> Dict[str, Any]:
    children = [
        spec
        for spec in (resource_spec(resource, config) for resource in resources)
        if spec is not None
    ]
    resource_names = [child["sdk"] for child in children]
    return {
        "name": kebab(ns_attr),
        "sdk": ns_attr,
        "summary": _short_list(f"client.{ns_attr}: ", resource_names),
        "help": (
            f"Commands for the Foundry API `{ns_attr}` namespace "
            f"(SDK: FoundryClient.{ns_attr}). Resources: "
            + ", ".join(resource_names)
            + "."
        ),
        "resources": children,
    }


def check_config(config: ApiVersionConfig, methods: List[str]) -> None:
    """Every configured method must exist, so the lists can't silently rot."""
    known = set(methods)
    for label, entries in (
        ("destructive", config.destructive),
        ("not_destructive", config.not_destructive),
        ("excluded", set(config.excluded)),
        ("stop_at_empty_page", set(config.stop_at_empty_page)),
    ):
        stale = sorted(set(entries) - known)
        if stale:
            raise GeneratorError(
                f"The {config.key} `{label}` config lists methods that the installed SDK "
                f"doesn't have: {stale}. Remove or rename them."
            )


def sdk_version() -> str:
    import foundry_sdk

    return str(foundry_sdk.__version__)


def build_specs() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Return ({module name: namespace spec}, index) for every configured version."""
    modules: Dict[str, Dict[str, Any]] = {}
    index: Dict[str, Any] = {}
    for config in API_VERSIONS:
        namespaces = discover(config)
        check_config(
            config,
            [m.dotted for _, resources in namespaces for m in iter_methods(resources)],
        )
        entries: Dict[str, Any] = {}
        for ns_attr, resources in namespaces:
            spec = namespace_spec(ns_attr, resources, config)
            if not spec["resources"]:
                continue
            module = config.module_prefix + ns_attr
            modules[module] = spec
            entries[spec["name"]] = {
                "module": module,
                "sdk": ns_attr,
                "client": config.key,
                "summary": spec["summary"],
            }
        if config.cli_group is None:
            overlap = sorted(set(entries) & set(index))
            if overlap:
                raise GeneratorError(f"namespace name collision: {overlap}")
            index.update(entries)
        else:
            index[config.cli_group] = {
                "summary": f"Foundry API {config.key} commands",
                "namespaces": entries,
            }
    return modules, index


# ---------------------------------------------------------------------------
# Rendering (deterministic Python literals)
# ---------------------------------------------------------------------------


def _literal(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        # JSON string syntax is valid Python and identical on every version.
        return json.dumps(value, ensure_ascii=True)
    raise TypeError(f"unsupported literal {value!r}")


def _is_flat(value: Any) -> bool:
    if isinstance(value, dict):
        return all(
            not isinstance(v, (dict, list)) or _is_flat_list(v) for v in value.values()
        )
    return False


def _is_flat_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        not isinstance(item, (dict, list)) for item in value
    )


def render(value: Any, indent: int = 0) -> str:
    """Render nested dicts/lists: flat dicts and scalar lists on one line."""
    pad = "    " * indent
    inner = "    " * (indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        if _is_flat(value):
            items = ", ".join(f"{_literal(k)}: {render(v)}" for k, v in value.items())
            return "{" + items + "}"
        lines = [
            f"{inner}{_literal(k)}: {render(v, indent + 1)}," for k, v in value.items()
        ]
        return "{\n" + "\n".join(lines) + f"\n{pad}}}"
    if isinstance(value, list):
        if not value:
            return "[]"
        if _is_flat_list(value):
            return "[" + ", ".join(_literal(item) for item in value) + "]"
        lines = [f"{inner}{render(item, indent + 1)}," for item in value]
        return "[\n" + "\n".join(lines) + f"\n{pad}]"
    return _literal(value)


def render_module(docstring: str, assignments: List[Tuple[str, Any]]) -> str:
    parts = [GENERATED_HEADER, f'"""{docstring}"""\n', "\n# fmt: off\n"]
    for name, value in assignments:
        parts.append(f"{name} = {render(value)}\n")
    return "".join(parts)


def render_files() -> Dict[str, str]:
    """Return {path relative to the repo root: file content} for every spec file."""
    modules, index = build_specs()
    version = sdk_version()
    files: Dict[str, str] = {}
    rel = SPECS_DIR.relative_to(REPO_ROOT).as_posix()
    files[f"{rel}/__init__.py"] = render_module(
        f"Generated `pltr api` index (foundry-platform-sdk {version}).",
        [("SDK_VERSION", version), ("NAMESPACES", index)],
    )
    for module, spec in sorted(modules.items()):
        files[f"{rel}/{module}.py"] = render_module(
            f"Generated specs for `pltr api {spec['name']}`.",
            [("SPEC", spec)],
        )
    return files


def existing_files() -> Dict[str, str]:
    files: Dict[str, str] = {}
    if SPECS_DIR.is_dir():
        for path in sorted(SPECS_DIR.glob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            files[rel] = path.read_text(encoding="utf-8")
    return files


def stale_files(expected: Dict[str, str], actual: Dict[str, str]) -> List[str]:
    """Paths whose content differs, that are missing, or that shouldn't exist."""
    return sorted(
        path
        for path in set(expected) | set(actual)
        if expected.get(path) != actual.get(path)
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Don't write anything; exit 1 if the committed specs are stale.",
    )
    args = parser.parse_args(argv)
    try:
        expected = render_files()
    except GeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    actual = existing_files()
    stale = stale_files(expected, actual)
    if args.check:
        if stale:
            print(
                "The generated `pltr api` specs are stale for foundry-platform-sdk "
                f"{sdk_version()}: {', '.join(stale)}\n"
                "Run: uv run python scripts/generate_api_commands.py",
                file=sys.stderr,
            )
            return 1
        print(f"`pltr api` specs are up to date ({len(expected)} files).")
        return 0
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    for path in stale:
        target = REPO_ROOT / path
        if path in expected:
            with open(target, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(expected[path])
        else:
            target.unlink()
    print(
        f"Wrote {len(stale)} changed file(s); {len(expected)} spec files for "
        f"foundry-platform-sdk {sdk_version()}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
