"""Compass paths wherever a RID is accepted (#193).

The Foundry API addresses Compass resources (folders, projects, datasets,
media sets, ...) by RID. pltr also accepts a resource's path, such as
``/Space/Project/data/employees``, in every argument or option that takes the
RID of a Compass resource, and resolves it to the RID before the command
runs. The API stays RID-based: paths are a convenience pltr resolves.

* A parameter takes a path when its click type is :class:`ResourceRef`
  (``ResourceRef("dataset")``). The ``pltr api`` generator marks parameters by
  their SDK type (``DatasetRid`` -> ``dataset``, :data:`SDK_RID_KINDS`).
* A value starting with ``/`` is a path, one starting with ``ri.`` a RID;
  anything else is passed through unchanged.
* :func:`resolve_paths` makes one ``Resource.get_by_path`` call for one path,
  and one ``Resource.get_by_path_batch`` call (per 1000 paths) for several.
* :func:`check_kind` checks the resolved resource's type against the
  parameter's :class:`ResourceKind`: a folder path given for a dataset fails
  with a ``wrong_resource_type`` error that names both types.

Spaces and the root folder can't be looked up by path (the API refuses
them), so ``SpaceRid`` parameters take RIDs only.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

import click

from .errors import ExitCode, PltrError
from .runtime import warn

#: Help sentence added to every parameter that accepts a path.
PATH_HELP = "A Compass path such as /Space/Project/name works too."

#: Most paths ``Resource.get_by_path_batch`` takes in one request.
MAX_BATCH_SIZE = 1000


@dataclass(frozen=True)
class ResourceKind:
    """What a resource parameter takes.

    Attributes:
        name: the kind's name in the manifest (``dataset``, ``media-set``).
        label: how messages name it (``a dataset``).
        resource_types: the API ``ResourceType`` values it accepts; ``None``
            accepts any Compass resource.
        project_only: only a project (a folder that is its own project).
    """

    name: str
    label: str
    resource_types: Optional[FrozenSet[str]] = None
    project_only: bool = False

    def accepts(self, resource: Any) -> bool:
        if self.resource_types is not None and resource.type not in (
            self.resource_types
        ):
            return False
        if self.project_only:
            return bool(resource.rid == resource.project_rid)
        return True


_KIND_LIST = (
    ResourceKind("resource", "any Compass resource"),
    ResourceKind("folder", "a folder or project", frozenset({"COMPASS_FOLDER"})),
    ResourceKind(
        "project", "a project", frozenset({"COMPASS_FOLDER"}), project_only=True
    ),
    ResourceKind("dataset", "a dataset", frozenset({"FOUNDRY_DATASET"})),
    ResourceKind(
        "dataset-or-folder",
        "a dataset or folder",
        frozenset({"FOUNDRY_DATASET", "COMPASS_FOLDER"}),
    ),
    ResourceKind("media-set", "a media set", frozenset({"MIO_MEDIA_SET"})),
    ResourceKind(
        "connection", "a Data Connection source", frozenset({"MAGRITTE_SOURCE"})
    ),
    ResourceKind("model", "a model", frozenset({"MODELS_MODEL"})),
    ResourceKind("agent", "an AIP agent", frozenset({"AIP_AGENTS_AGENT"})),
    ResourceKind(
        "third-party-application",
        "a third-party application",
        frozenset({"THIRD_PARTY_APPLICATIONS_APPLICATION"}),
    ),
    ResourceKind("repository", "a code repository", frozenset({"STEMMA_REPOSITORY"})),
)

#: Every kind, by name.
KINDS: Dict[str, ResourceKind] = {kind.name: kind for kind in _KIND_LIST}

#: SDK RID types of Compass resources, and the kind of parameter they make.
SDK_RID_KINDS: Dict[str, str] = {
    "ResourceRid": "resource",
    "FolderRid": "folder",
    "ProjectRid": "project",
    "DatasetRid": "dataset",
    "MediaSetRid": "media-set",
    "ConnectionRid": "connection",
    "ModelRid": "model",
    "AgentRid": "agent",
    "ThirdPartyApplicationRid": "third-party-application",
    "RepositoryRid": "repository",
}

_WRAPPER = re.compile(r"(?:Optional|List)\[(.*)\]")


def kind_for_sdk_type(type_text: Optional[str]) -> Optional[str]:
    """The kind of an SDK parameter type (``Optional[DatasetRid]`` -> ``dataset``).

    ``None`` for types that aren't Compass resource RIDs.
    """
    if not type_text:
        return None
    text = "".join(type_text.split())
    match = _WRAPPER.fullmatch(text)
    while match:
        text = match.group(1)
        match = _WRAPPER.fullmatch(text)
    return SDK_RID_KINDS.get(text)


class ResourceRef(click.ParamType):
    """Click type of a parameter that takes a resource RID or a Compass path.

    It passes values through unchanged: ``@pltr_command`` resolves the paths
    (:func:`resolve_resource_paths`) once all parameters are parsed, unless
    ``resolve`` is False: then the command looks them up itself (``pltr
    resource wait`` polls a path that doesn't exist yet, #219).
    """

    name = "resource"

    #: A Windows path: what Git Bash (MSYS) makes of a leading-slash argument.
    _WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")

    def __init__(self, kind: str, *, resolve: bool = True) -> None:
        if kind not in KINDS:
            raise ValueError(f"Unknown resource kind: {kind!r}")
        self.kind = KINDS[kind]
        self.resolve = resolve

    def convert(
        self, value: Any, param: Optional[click.Parameter], ctx: Optional[click.Context]
    ) -> Any:
        if isinstance(value, str) and self._WINDOWS_PATH.match(value):
            self.fail(
                f"{value!r} is a Windows path, not a RID or a Compass path. Git "
                "Bash (MSYS) rewrites arguments that start with / into Windows "
                "paths: run the command with MSYS_NO_PATHCONV=1, or start the "
                "Compass path with two slashes (//Space/Project/name).",
                param,
                ctx,
            )
        return value

    def __repr__(self) -> str:
        return f"ResourceRef({self.kind.name!r})"


#: The ``ResourceType`` a RID names, by its service and type
#: (``ri.<service>.<instance>.<type>.<locator>``). Only formats pltr is sure
#: of: a RID of another format is left to the API.
RID_RESOURCE_TYPES: Dict[tuple, str] = {
    ("foundry", "dataset"): "FOUNDRY_DATASET",
    ("compass", "folder"): "COMPASS_FOLDER",
    ("mio", "media-set"): "MIO_MEDIA_SET",
    ("magritte", "source"): "MAGRITTE_SOURCE",
    ("aip-agents", "agent"): "AIP_AGENTS_AGENT",
    ("third-party-applications", "application"): (
        "THIRD_PARTY_APPLICATIONS_APPLICATION"
    ),
    ("stemma", "repository"): "STEMMA_REPOSITORY",
}

_RID = re.compile(r"ri\.([a-z0-9-]+)\.[a-z0-9-]*\.([a-z0-9-]+)\..+")


def rid_service_and_type(value: Any) -> Optional[Tuple[str, str]]:
    """The service and type of a RID (``ri.<service>.<instance>.<type>.<id>``)."""
    if not isinstance(value, str):
        return None
    match = _RID.fullmatch(value)
    return (match.group(1), match.group(2)) if match else None


def rid_resource_type(value: Any) -> Optional[str]:
    """The ``ResourceType`` a RID names, when pltr knows its format."""
    parts = rid_service_and_type(value)
    return RID_RESOURCE_TYPES.get(parts) if parts else None


def is_path(value: Any) -> bool:
    """True when ``value`` is a Compass path (it starts with ``/``)."""
    return isinstance(value, str) and value.startswith("/")


# ------------------------------------------------------------------- errors

PATH_NOT_FOUND_HINT = (
    "A path is the resource's full Compass path, starting with its space: "
    "/Space/Project/folder/name. Find projects with `pltr project list` and "
    "browse them with `pltr folder list`. Spaces and the root folder can't be "
    "looked up by path."
)


class PathNotFoundError(PltrError):
    """No resource (that the account can see) at one or more paths."""

    error_type = "path_not_found"
    exit_code = ExitCode.NOT_FOUND

    def __init__(self, paths: Sequence[str]) -> None:
        self.paths = list(paths)
        quoted = ", ".join(repr(path) for path in self.paths)
        if len(self.paths) == 1:
            message = f"No resource at {quoted} that your account can see."
            parameters: Dict[str, Any] = {"path": self.paths[0]}
        else:
            message = f"No resources at {quoted} that your account can see."
            parameters = {"paths": self.paths}
        super().__init__(message, hint=PATH_NOT_FOUND_HINT, parameters=parameters)


class WrongResourceTypeError(PltrError):
    """A RID or path names a resource of the wrong kind for its parameter."""

    error_type = "wrong_resource_type"
    exit_code = ExitCode.USAGE

    def __init__(
        self,
        given: str,
        rid: str,
        actual: str,
        kind: ResourceKind,
        label: str,
        *,
        from_path: bool,
        profile: Optional[str] = None,
    ) -> None:
        expected = sorted(kind.resource_types or ())
        if from_path and kind.project_only and actual in expected:
            message = (
                f"{given!r} is a folder ({rid}), not a project, but {label} "
                "takes a project."
            )
        elif from_path:
            message = (
                f"{given!r} is a {actual} ({rid}), but {label} takes "
                f"{kind.label} ({', '.join(expected)})."
            )
        else:
            message = (
                f"{rid} is a {actual}, but {label} takes {kind.label} "
                f"({', '.join(expected)})."
            )
        parameters: Dict[str, Any] = {"path": given} if from_path else {}
        parameters.update(rid=rid, resourceType=actual, expectedTypes=expected)
        hint = suggested = None
        if actual == "COMPASS_FOLDER" and actual not in expected:
            hint = f"That is a folder: look in it for {kind.label}."
            suggested = f"pltr folder list {shlex.quote(given)}"
            if profile:
                suggested += f" --profile {shlex.quote(profile)}"
        super().__init__(
            message, parameters=parameters, hint=hint, suggested_command=suggested
        )


class PathResolutionError(Exception):
    """Context for an API error raised while resolving a path.

    Deliberately not a :class:`PltrError`: the API error in its cause decides
    the error type and exit code, and this message prefixes it.
    """


# --------------------------------------------------------------- resolution


def _normalize(path: str) -> str:
    return "/" + path.strip("/")


def _resolve_one(resource_client: Any, path: str) -> Any:
    from foundry_sdk import _errors as sdk

    try:
        return resource_client.get_by_path(path=path)
    except sdk.NotFoundError as exc:
        raise PathNotFoundError([path]) from exc
    except sdk.PalantirRPCException as exc:
        raise PathResolutionError(f"Could not resolve the path {path!r}") from exc


def _resolve_batch(resource_client: Any, paths: List[str]) -> Dict[str, Any]:
    from foundry_sdk import _errors as sdk
    from foundry_sdk.v2.filesystem.models import (
        GetByPathResourcesBatchRequestElement,
    )

    returned: Dict[str, Any] = {}
    for start in range(0, len(paths), MAX_BATCH_SIZE):
        chunk = paths[start : start + MAX_BATCH_SIZE]
        try:
            response = resource_client.get_by_path_batch(
                body=[
                    GetByPathResourcesBatchRequestElement(path=path) for path in chunk
                ]
            )
        except sdk.PalantirRPCException as exc:
            quoted = ", ".join(repr(path) for path in chunk)
            raise PathResolutionError(f"Could not resolve the paths {quoted}") from exc
        for resource in response.data:
            returned.setdefault(_normalize(resource.path), resource)
    found: Dict[str, Any] = {}
    missing: List[str] = []
    for path in paths:
        resource = returned.get(_normalize(path))
        if resource is None:
            missing.append(path)
        else:
            found[path] = resource
    if missing:
        raise PathNotFoundError(missing)
    return found


def resolve_paths(client: Any, paths: Sequence[str]) -> Dict[str, Any]:
    """Resolve Compass paths to ``Resource`` models, one API call per path at most.

    One path: ``Resource.get_by_path``. Several: ``Resource.get_by_path_batch``
    (one request per 1000 paths). Repeated paths are resolved once. Raises
    :class:`PathNotFoundError` for paths with no visible resource; other API
    errors keep their own classification, prefixed with the path. Warns about
    paths whose resource is in the trash.
    """
    unique = list(dict.fromkeys(paths))
    if not unique:
        return {}
    resource_client = client.filesystem.Resource
    if len(unique) == 1:
        found = {unique[0]: _resolve_one(resource_client, unique[0])}
    else:
        found = _resolve_batch(resource_client, unique)
    for path, resource in found.items():
        trash_status = getattr(resource, "trash_status", None)
        if trash_status not in (None, "NOT_TRASHED"):
            warn(f"{path!r} is in the trash ({resource.rid}, {trash_status}).")
    return found


def check_kind(
    path: str,
    resource: Any,
    kind: ResourceKind,
    label: str,
    profile: Optional[str] = None,
) -> None:
    """Fail unless ``resource`` (resolved from ``path``) is of ``kind``.

    ``label`` names the parameter in the message (``DATASET_RID``,
    ``--parent-folder``).
    """
    if not kind.accepts(resource):
        raise WrongResourceTypeError(
            path,
            resource.rid,
            str(resource.type),
            kind,
            label,
            from_path=True,
            profile=profile,
        )


def check_rid_kind(
    rid: str, kind: ResourceKind, label: str, profile: Optional[str] = None
) -> None:
    """Fail, before any API call, when ``rid`` names a resource of another kind.

    Only RIDs whose format pltr knows (:data:`RID_RESOURCE_TYPES`) are checked.
    A folder RID given for a project passes: the RID can't tell them apart.
    """
    actual = rid_resource_type(rid)
    if actual is None or kind.resource_types is None:
        return
    if actual not in kind.resource_types:
        raise WrongResourceTypeError(
            rid, rid, actual, kind, label, from_path=False, profile=profile
        )


# ----------------------------------------------------------- command layer


def _parameter_label(param: click.Parameter) -> str:
    """How messages name a parameter: ``DATASET_RID`` or ``--parent-folder``."""
    if isinstance(param, click.Option):
        return next((opt for opt in param.opts if opt.startswith("--")), param.opts[0])
    return param.human_readable_name


def _values(value: Any) -> List[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def resolve_resource_paths(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Replace the Compass paths in a command's resource parameters with RIDs.

    Called by ``@pltr_command`` before the command body runs, with the
    keyword arguments the command is called with. The command's
    :class:`ResourceRef` parameters are read from the current click context.
    Without a path among their values nothing happens (no client, no
    request); otherwise every path is resolved in one call
    (:func:`resolve_paths`), checked against its parameter's kind, reported
    on stderr (text mode only) and replaced by its RID.
    """
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return kwargs
    params = [
        param
        for param in ctx.command.params
        if isinstance(param.type, ResourceRef) and param.name in kwargs
    ]
    profile = kwargs.get("profile", ctx.params.get("profile"))
    for param in params:
        assert isinstance(param.type, ResourceRef)
        for value in _values(kwargs[str(param.name)]):
            if isinstance(value, str) and not is_path(value):
                check_rid_kind(value, param.type.kind, _parameter_label(param), profile)
    # resolve=False: the command looks its paths up itself.
    targets = [param for param in params if getattr(param.type, "resolve", True)]
    wanted = [
        (value, param)
        for param in targets
        for value in _values(kwargs[str(param.name)])
        if is_path(value)
    ]
    if not wanted:
        return kwargs

    from .emit import emit_mode

    if emit_mode():
        # Nothing is called: the snippet looks the paths up (#192).
        from .codegen import PathValue

        def mark(value: Any) -> Any:
            return PathValue(value) if is_path(value) else value

        marked = dict(kwargs)
        for param in targets:
            name = str(param.name)
            value = marked[name]
            if isinstance(value, (list, tuple)):
                marked[name] = type(value)(mark(item) for item in value)
            else:
                marked[name] = mark(value)
        return marked

    rids = _look_up(
        [
            (path, param.type.kind, _parameter_label(param))
            for path, param in wanted
            if isinstance(param.type, ResourceRef)
        ],
        profile,
    )

    def substitute(value: Any) -> Any:
        return rids[value] if is_path(value) else value

    result = dict(kwargs)
    for param in targets:
        name = str(param.name)
        value = result[name]
        if isinstance(value, (list, tuple)):
            result[name] = type(value)(substitute(item) for item in value)
        else:
            result[name] = substitute(value)
    return result


def _look_up(
    wanted: Sequence[Tuple[str, ResourceKind, str]], profile: Optional[str]
) -> Dict[str, str]:
    """Resolve ``(path, kind, label)`` triples in one call; return path -> RID.

    Checks each resolved resource against its kind and reports it on stderr
    (text mode only).
    """
    from pltr.services import base

    from .runtime import info

    client = base.AuthManager().get_client(profile)
    resolved = resolve_paths(client, [path for path, _, _ in wanted])
    for path, kind, label in wanted:
        check_kind(path, resolved[path], kind, label, profile)
    for path, resource in resolved.items():
        info(f"Resolved {path!r} to {resource.rid} ({resource.type})")
    return {path: resource.rid for path, resource in resolved.items()}


# ------------------------------------------------- paths inside JSON (#218)


def resolve_json_paths(
    document: Any,
    fields: Mapping[str, str],
    *,
    label: str,
    profile: Optional[str] = None,
) -> Any:
    """Replace Compass paths in a JSON argument's RID fields with their RIDs.

    ``fields`` maps the JSON keys that hold resource RIDs in the SDK's
    model (``targetRids``, ``datasetRid``) to the kind of resource each
    takes (:data:`KINDS`; ``resource`` for any). Wherever such a key appears
    in ``document``, at any depth, a value that starts with ``/`` (the value
    itself, or an item of a list) is a path: all of them are resolved in one
    call (:func:`resolve_paths`), checked against their field's kind,
    reported on stderr (text mode only) and replaced by their RIDs. RIDs of a
    known wrong kind fail before any call. Other keys are left alone,
    whatever their values. ``label`` names the argument in messages
    (``TARGET``, ``--trigger``), after the field: ``targetRids in TARGET``.

    Returns a new document (``document`` itself when it holds no path) and
    makes no call when there is no path. With ``--emit-code`` the paths are
    marked for the snippet to look up instead. For a command with several
    JSON arguments, use :func:`resolve_json_documents`.
    """
    return resolve_json_documents([(document, fields, label)], profile=profile)[0]


def resolve_json_documents(
    documents: Sequence[Tuple[Any, Mapping[str, str], str]],
    *,
    profile: Optional[str] = None,
) -> List[Any]:
    """:func:`resolve_json_paths` for several JSON arguments at once.

    ``documents`` holds ``(document, fields, label)`` triples. Every RID is
    checked before any call, and the paths of all the documents are
    resolved in one call (a path given twice is looked up once). Returns
    the documents in the same order.
    """
    wanted: List[Tuple[str, ResourceKind, str]] = []
    prepared: List[Tuple[Any, Dict[str, ResourceKind]]] = []
    for document, fields, label in documents:
        for name in fields.values():
            if name not in KINDS:
                raise ValueError(f"Unknown resource kind: {name!r}")
        kinds = {key: KINDS[name] for key, name in fields.items()}
        _collect_paths(document, kinds, label, profile, wanted)
        prepared.append((document, kinds))
    if not wanted:
        return [document for document, _ in prepared]

    from .emit import emit_mode

    if emit_mode():
        # Nothing is called: the snippet looks the paths up (#192).
        from .codegen import PathValue

        return [_replace_paths(doc, kinds, PathValue) for doc, kinds in prepared]
    rids = _look_up(wanted, profile)
    return [
        _replace_paths(doc, kinds, lambda path: rids[path]) for doc, kinds in prepared
    ]


def _collect_paths(
    node: Any,
    kinds: Mapping[str, ResourceKind],
    label: str,
    profile: Optional[str],
    wanted: List[Tuple[str, ResourceKind, str]],
) -> None:
    """Add the paths in ``node``'s RID fields to ``wanted``; check its RIDs."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in kinds and isinstance(value, (str, list)):
                where = f"{key} in {label}"
                for item in _values(value):
                    if is_path(item):
                        wanted.append((item, kinds[key], where))
                    elif isinstance(item, str):
                        check_rid_kind(item, kinds[key], where, profile)
            else:
                _collect_paths(value, kinds, label, profile, wanted)
    elif isinstance(node, list):
        for item in node:
            _collect_paths(item, kinds, label, profile, wanted)


def _replace_paths(node: Any, kinds: Mapping[str, Any], replace: Any) -> Any:
    """A copy of ``node`` with ``replace(path)`` for each path in a RID field."""

    def swap(value: Any) -> Any:
        return replace(value) if is_path(value) else value

    if isinstance(node, dict):
        copied = {}
        for key, value in node.items():
            if key in kinds and isinstance(value, str):
                copied[key] = swap(value)
            elif key in kinds and isinstance(value, list):
                copied[key] = [swap(item) for item in value]
            else:
                copied[key] = _replace_paths(value, kinds, replace)
        return copied
    if isinstance(node, list):
        return [_replace_paths(item, kinds, replace) for item in node]
    return node


def _with_path_help(text: str) -> str:
    text = text.rstrip()
    return f"{text} {PATH_HELP}" if text else PATH_HELP


def resource_argument(
    kind: str, *, help: str, resolve: bool = True, **kwargs: Any
) -> Any:
    """A ``typer.Argument`` that takes a resource RID or a Compass path.

    Use it in ``Annotated[str, resource_argument("dataset", help="...")]``.
    The help gets :data:`PATH_HELP` appended. With ``resolve=False`` the
    command gets a path as given and looks it up itself (a RID of a known
    wrong kind is still refused); ``--emit-code`` then can't render the path,
    so such a command declares ``no_emit_code``.
    """
    import typer

    return typer.Argument(
        help=_with_path_help(help),
        click_type=ResourceRef(kind, resolve=resolve),
        **kwargs,
    )


def resource_option(*flags: str, kind: str, help: str, **kwargs: Any) -> Any:
    """A ``typer.Option`` that takes a resource RID or a Compass path.

    Use it in ``Annotated[str, resource_option("--parent-folder", kind="folder",
    help="...")]``. The help gets :data:`PATH_HELP` appended.
    """
    import typer

    return typer.Option(
        *flags, help=_with_path_help(help), click_type=ResourceRef(kind), **kwargs
    )
