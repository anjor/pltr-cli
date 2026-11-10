"""Recovery hints: tell the agent how to recover from an error (#197).

:func:`pltr.contract.errors.fail` classifies an exception into an
:class:`~pltr.contract.errors.ErrorInfo`, then :func:`add_recovery` asks each
provider in :data:`PROVIDERS`, in order, whether it knows this failure. The
first :class:`Recovery` it gets becomes the error's ``hint`` (in JSON and text
mode) and ``suggestedCommand``.

Providers are best effort: a provider may make a Foundry call to make its hint
specific (the names closest to a misspelled object type, the RID of the open
transaction), and if anything goes wrong in one, the error is reported without
its hint. Hints are short and specific; a provider returns nothing rather than
a vague hint.
"""

from __future__ import annotations

import contextvars
import difflib
import itertools
import re
import shlex
import warnings
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import click

from .errors import ErrorInfo


@dataclass(frozen=True)
class Recovery:
    """What to do about an error."""

    hint: str
    suggested_command: Optional[str] = None


#: ``provider(info, exc, ctx)``: ``exc`` is the exception being reported,
#: ``ctx`` the running command's click context (or None).
Provider = Callable[
    [ErrorInfo, BaseException, Optional[click.Context]], Optional[Recovery]
]

#: Seconds each Foundry call a provider makes may take.
HINT_TIMEOUT = 10

# ------------------------------------------------------------------ helpers


def _param(ctx: Optional[click.Context], name: str) -> Optional[str]:
    """A string parameter of the running command (or a parent group)."""
    while ctx is not None:
        if name in ctx.params:
            value = ctx.params[name]
            return value if isinstance(value, str) and value else None
        ctx = ctx.parent
    return None


def _profile(ctx: Optional[click.Context]) -> Optional[str]:
    return _param(ctx, "profile")


def _client(ctx: Optional[click.Context]) -> Any:
    """The SDK client of the running command's profile."""
    from pltr.services import base

    return base.AuthManager().get_client(_profile(ctx))


def suggest(ctx: Optional[click.Context], *argv: Any) -> str:
    """A pltr command line: quoted arguments, plus the command's ``--profile``."""
    command = " ".join(shlex.quote(str(arg)) for arg in argv)
    profile = _profile(ctx)
    return f"{command} --profile {shlex.quote(profile)}" if profile else command


def _parameters(info: ErrorInfo) -> Dict[str, Any]:
    return info.parameters if isinstance(info.parameters, dict) else {}


_SCOPES = re.compile(r"Required scopes: \[([^\]]*)\]")


def _scopes_in(text: str) -> List[str]:
    match = _SCOPES.search(text or "")
    if not match:
        return []
    return [scope.strip() for scope in match.group(1).split(",") if scope.strip()]


def _method_spec(sdk_path: str) -> Optional[Dict[str, Any]]:
    """The generated ``pltr api`` spec of an SDK method (``datasets.Dataset.get``)."""
    import importlib

    from pltr.commands.api import _runtime

    namespace, *resources, method = sdk_path.split(".")
    entry = next(
        (e for e in _runtime._index().NAMESPACES.values() if e.get("sdk") == namespace),
        None,
    )
    if entry is None:
        return None
    node: Dict[str, Any] = importlib.import_module(
        f"{_runtime.SPECS_PACKAGE}.{entry['module']}"
    ).SPEC
    for name in resources:
        node = next(r for r in node.get("resources", []) if r["sdk"] == name)
    return next((m for m in node.get("methods", []) if m["sdk"] == method), None)


def _command_scopes(ctx: Optional[click.Context]) -> List[str]:
    """The OAuth scopes the running command's SDK methods need (from their docs)."""
    from .command import get_command_meta

    if ctx is None:
        return []
    spec = getattr(ctx.command, "spec", None)
    if isinstance(spec, dict):  # a generated `pltr api` command
        return _scopes_in(spec.get("help", ""))
    meta = get_command_meta(ctx.command)
    scopes: List[str] = []
    for sdk_path in meta.sdk if meta else ():
        method = _method_spec(sdk_path)
        for scope in _scopes_in(method.get("help", "") if method else ""):
            if scope not in scopes:
                scopes.append(scope)
    return scopes


# ---------------------------------------------------------------- providers


def open_transaction(
    info: ErrorInfo, exc: BaseException, ctx: Optional[click.Context]
) -> Optional[Recovery]:
    """409 ``OpenTransactionAlreadyExists``: name the transaction to abort."""
    if info.error_name != "OpenTransactionAlreadyExists":
        return None
    parameters = _parameters(info)
    dataset, branch = parameters.get("datasetRid"), parameters.get("branchName")
    if not dataset or not branch:
        return None
    transaction = None
    try:
        datasets = _client(ctx).datasets.Dataset
        candidate = datasets.Branch.get(
            dataset, branch, request_timeout=HINT_TIMEOUT
        ).transaction_rid
        if (
            candidate
            and datasets.Transaction.get(
                dataset, candidate, request_timeout=HINT_TIMEOUT
            ).status
            == "OPEN"
        ):
            transaction = candidate
    except Exception:
        transaction = None
    if transaction:
        return Recovery(
            f"Branch {branch} of {dataset} already has an open transaction, "
            f"{transaction}: commit it or abort it first.",
            suggest(
                ctx, "pltr", "dataset", "transactions", "abort", dataset, transaction
            ),
        )
    return Recovery(
        f"Branch {branch} of {dataset} already has an open transaction: commit "
        "it or abort it first.",
        suggest(
            ctx, "pltr", "dataset", "transactions", "list", dataset, "--branch", branch
        ),
    )


_GRANT = (
    "Grant it to the OAuth client in Developer Console, or use a token that has it."
)


def missing_scope(
    info: ErrorInfo, exc: BaseException, ctx: Optional[click.Context]
) -> Optional[Recovery]:
    """403 ``ApiUsageDenied``: name the scope the endpoint needs."""
    if info.error_name != "ApiUsageDenied":
        return None
    from .errors import _chain
    from .resources import PathResolutionError

    scope = _parameters(info).get("missingScope")
    if isinstance(scope, str) and scope:
        return Recovery(f"The token or OAuth client lacks the scope {scope}. {_GRANT}")
    if any(isinstance(e, PathResolutionError) for e in _chain(exc)):
        # The failed call looked up a Compass path (#193), not the command's own.
        method = _method_spec("filesystem.Resource.get_by_path")
        scopes = _scopes_in(method.get("help", "") if method else "")
        subject = "Looking up a Compass path"
    else:
        scopes = _command_scopes(ctx)
        subject = "This command"
    if not scopes:
        return None
    noun = "scope" if len(scopes) == 1 else "scopes"
    return Recovery(
        f"{subject} needs the {noun} {', '.join(scopes)}, which the token or "
        f"OAuth client may lack. {_GRANT}"
    )


def _words(camel: str) -> str:
    return " ".join(re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", camel)).lower()


def permission_denied(
    info: ErrorInfo, exc: BaseException, ctx: Optional[click.Context]
) -> Optional[Recovery]:
    """403 ``<Operation>PermissionDenied``: name the operation and the resource."""
    from .resources import rid_resource_type

    name = info.error_name or ""
    # Typed SDK errors only: a namespaced name such as Default:PermissionDenied
    # says nothing about the operation.
    if info.type != "permission_denied" or not re.fullmatch(
        r"[A-Z][A-Za-z0-9]*PermissionDenied", name
    ):
        return None
    operation = _words(name[: -len("PermissionDenied")])
    rids = [
        value
        for value in _parameters(info).values()
        if isinstance(value, str) and value.startswith("ri.")
    ]
    if not operation or not rids:
        return None
    rid = next((r for r in rids if rid_resource_type(r)), rids[0])
    return Recovery(
        f"Your account isn't allowed to {operation} on {rid}. Ask someone who "
        "manages it for a role that allows this.",
        (
            suggest(ctx, "pltr", "resource-role", "list", rid, "--include-inherited")
            if rid_resource_type(rid)
            else None
        ),
    )


def rejected_token(
    info: ErrorInfo, exc: BaseException, ctx: Optional[click.Context]
) -> Optional[Recovery]:
    """401 with a token: say how to give pltr a new one."""
    from pltr.services import base

    if info.type != "auth_error" or info.status_code != 401:
        return None
    source = base.AuthManager().get_auth_context(_profile(ctx)).source
    if source.auth_type != "token":
        return None
    where = f"Foundry at {source.host}" if source.host else "Foundry"
    if source.kind == "environment":
        return Recovery(
            f"{where} rejected FOUNDRY_TOKEN (invalid, expired or revoked). "
            "Set a new token.",
            "export FOUNDRY_TOKEN=<new-token>",
        )
    if not source.profile:
        return None
    argv = ["pltr", "configure", "configure", "--profile", source.profile]
    argv += ["--auth-type", "token"]
    if source.host:
        argv += ["--host", source.host]
    # No --token: configure asks for it, so it stays out of shell history.
    return Recovery(
        f"{where} rejected the token of profile {source.profile} (invalid, "
        "expired or revoked). Store a new one.",
        " ".join(shlex.quote(arg) for arg in argv),
    )


#: Most names read from a list endpoint to find the closest ones.
NAME_LIMIT = 2000


def closest_names(wanted: str, names: List[str], limit: int = 3) -> List[str]:
    """The names closest to ``wanted``, compared ignoring case; never ``wanted``
    itself in another case (Foundry resolves API names ignoring case, so such a
    name isn't the problem)."""
    lowered: Dict[str, str] = {}
    for name in names:
        lowered.setdefault(name.lower(), name)
    lowered.pop(wanted.lower(), None)
    close = difflib.get_close_matches(wanted.lower(), list(lowered), limit, 0.6)
    return [lowered[c] for c in close]


def _has_name(wanted: str, names: List[str]) -> bool:
    return any(name.lower() == wanted.lower() for name in names)


def _api_names(items: Any) -> List[str]:
    return [str(item.api_name) for item in itertools.islice(items, NAME_LIMIT)]


_ONTOLOGY_ERRORS = (
    "ObjectTypeNotFound",
    "PropertiesNotFound",
    "ActionTypeNotFound",
    "LinkTypeNotFound",
)


def ontology_names(
    info: ErrorInfo, exc: BaseException, ctx: Optional[click.Context]
) -> Optional[Recovery]:
    """An object type, property, action type or link type that doesn't exist:
    list the closest API names."""
    name = info.error_name
    ontology = _param(ctx, "ontology")
    if name not in _ONTOLOGY_ERRORS or ontology is None:
        return None
    parameters = _parameters(info)
    object_type = parameters.get("objectType")
    ontologies = _client(ctx).ontologies.Ontology
    if name == "PropertiesNotFound":
        properties = parameters.get("properties") or []
        if not object_type or not properties:
            return None
        names = list(
            ontologies.ObjectType.get(
                ontology, object_type, request_timeout=HINT_TIMEOUT
            ).properties
        )
        properties = [p for p in properties if not _has_name(str(p), names)]
        if not properties:
            return None
        pairs = [
            f"{prop!r} -> {', '.join(closest_names(str(prop), names)) or 'none'}"
            for prop in properties
        ]
        return Recovery(
            "Closest property API names: " + "; ".join(pairs) + ".",
            suggest(ctx, "pltr", "ontology", "object-type-get", ontology, object_type),
        )
    if name == "ObjectTypeNotFound":
        wanted, label = parameters.get("objectType"), "object type"
        listing = suggest(ctx, "pltr", "ontology", "object-type-list", ontology)
        items: Callable[[], Any] = lambda: ontologies.ObjectType.list(  # noqa: E731
            ontology, page_size=500, request_timeout=HINT_TIMEOUT
        )
    elif name == "ActionTypeNotFound":
        wanted, label = parameters.get("actionType"), "action type"
        listing = suggest(
            ctx,
            "pltr",
            "api",
            "ontologies",
            "ontology",
            "action-type",
            "list",
            ontology,
        )
        items = lambda: ontologies.ActionType.list(  # noqa: E731
            ontology, page_size=500, request_timeout=HINT_TIMEOUT
        )
    else:
        wanted, label = parameters.get("linkType"), "link type"
        if not object_type:
            return None
        listing = suggest(
            ctx,
            "pltr",
            "api",
            "ontologies",
            "ontology",
            "object-type",
            "list-outgoing-link-types",
            ontology,
            object_type,
        )
        items = lambda: ontologies.ObjectType.list_outgoing_link_types(  # noqa: E731
            ontology, object_type, page_size=500, request_timeout=HINT_TIMEOUT
        )
    if not wanted:
        return None
    names = _api_names(items())
    if _has_name(str(wanted), names):
        return None  # the name exists: something else is wrong
    close = closest_names(str(wanted), names)
    if not close:
        return Recovery(
            f"No {label} in {ontology} has an API name close to {wanted!r}.", listing
        )
    return Recovery(
        f"Closest {label} API names to {wanted!r}: {', '.join(close)}.", listing
    )


#: Work a --wait command started: (what, resume command).
_STARTED: contextvars.ContextVar[Optional[tuple]] = contextvars.ContextVar(
    "pltr_started_work", default=None
)


def note_started(
    subject: str, resume: str, *, announce: bool = True, **ids: str
) -> None:
    """Record work a --wait command started (``subject``: "build ri...").

    In JSON mode it is announced at once as a ``{"type": "started", ...}``
    stderr line with ``ids``, so an agent whose tool call is cut off still
    knows the RID. An error while waiting then says the work keeps running and
    suggests ``resume`` (see :func:`started_work`).
    """
    from .runtime import is_json, write_json_line

    _STARTED.set((subject, resume))
    if announce and is_json():
        write_json_line(
            {"type": "started", "message": f"Started {subject}; waiting for it.", **ids}
        )


def clear_started() -> None:
    _STARTED.set(None)


def _long_flag(param: click.Parameter) -> str:
    return next((opt for opt in param.opts if opt.startswith("--")), param.opts[0])


def _flag_option(ctx: Optional[click.Context], name: str) -> Optional[click.Option]:
    """The running command's boolean flag option called ``name``, if it has one."""
    for param in ctx.command.params if ctx is not None else ():
        if param.name == name and isinstance(param, click.Option) and param.is_flag:
            return param
    return None


def rerun_with_flag(ctx: click.Context, flag: click.Option) -> str:
    """The running command again, with ``flag`` turned on.

    Rebuilt from the parsed parameters (the values as typed, before any path
    was resolved): arguments in order, then the options that differ from
    their defaults, then the flag, then ``--profile`` (:func:`suggest`).
    Hidden options (deprecated aliases) are left out.
    """
    names: List[str] = []
    parent: Optional[click.Context] = ctx
    while parent is not None and parent.parent is not None:
        names.insert(0, str(parent.info_name))
        parent = parent.parent
    positional: List[Any] = []
    options: List[Any] = []
    for param in ctx.command.params:
        value = ctx.params.get(str(param.name))
        if param.name == "profile" or not param.expose_value:
            continue
        if isinstance(param, click.Argument):
            if isinstance(value, (list, tuple)):
                positional += list(value)
            elif value is not None:
                positional.append(value)
            continue
        if not isinstance(param, click.Option) or param.hidden:
            continue
        if value is None or value == () or value == param.default:
            continue
        if param.is_flag and param.secondary_opts and value is False:
            options.append(param.secondary_opts[0])
        elif param.is_flag:
            options.append(_long_flag(param))
        elif param.multiple:
            for item in value:
                options += [_long_flag(param), item]
        else:
            options += [_long_flag(param), value]
    return suggest(ctx, "pltr", *names, *positional, *options, _long_flag(flag))


_UP_TO_DATE = (
    "Nothing to build: every target is already up to date, so no build was started."
)


def build_targets_up_to_date(
    info: ErrorInfo, exc: BaseException, ctx: Optional[click.Context]
) -> Optional[Recovery]:
    """400 ``BuildTargetsUpToDate``: nothing was built; the force flag rebuilds.

    The suggested command is the same command with ``--force`` (or the
    generated command's ``--force-build``).
    """
    if info.error_name != "BuildTargetsUpToDate":
        return None
    flag = _flag_option(ctx, "force_build")
    if ctx is None or flag is None or ctx.params.get("force_build"):
        return Recovery(_UP_TO_DATE)
    return Recovery(
        f"{_UP_TO_DATE} Add {_long_flag(flag)} to rebuild anyway.",
        rerun_with_flag(ctx, flag),
    )


def started_work(
    info: ErrorInfo, exc: BaseException, ctx: Optional[click.Context]
) -> Optional[Recovery]:
    """An error while waiting for work pltr started: it keeps running."""
    started = _STARTED.get()
    if started is None or info.type in ("work_failed", "wait_timeout"):
        return None
    subject, resume = started
    return Recovery(
        f"The {subject} was started and keeps running: this error came while "
        "waiting for it.",
        resume,
    )


PROVIDERS: List[Provider] = [
    started_work,
    ontology_names,
    open_transaction,
    build_targets_up_to_date,
    missing_scope,
    permission_denied,
    rejected_token,
]


def add_recovery(info: ErrorInfo, exc: BaseException) -> None:
    """Give ``info`` the hint and suggested command of the first provider that
    knows the failure; keep it unchanged if none does (or one fails)."""
    ctx = click.get_current_context(silent=True)
    for provider in PROVIDERS:
        try:
            # A lookup's SDK warnings (e.g. an error body it can't decode)
            # would print before the error: the hint is best effort.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                recovery = provider(info, exc, ctx)
        except Exception:
            continue
        if recovery is not None:
            info.hint = recovery.hint
            info.generic_hint = False
            info.suggested_command = recovery.suggested_command
            return
