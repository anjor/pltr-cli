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

import difflib
import itertools
import re
import shlex
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import click

from .errors import ErrorInfo


@dataclass(frozen=True)
class Recovery:
    """What to do about an error."""

    hint: str
    suggested_command: Optional[str] = None


#: ``provider(info, api_error, ctx)``: ``api_error`` is the Foundry API error
#: in the exception chain (or None), ``ctx`` the running command's click
#: context (or None).
Provider = Callable[[ErrorInfo, Any, Optional[click.Context]], Optional[Recovery]]

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


def _q(value: Any) -> str:
    return shlex.quote(str(value))


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
    info: ErrorInfo, api_error: Any, ctx: Optional[click.Context]
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
        candidate = datasets.Branch.get(dataset, branch).transaction_rid
        if candidate and datasets.Transaction.get(dataset, candidate).status == "OPEN":
            transaction = candidate
    except Exception:
        transaction = None
    if transaction:
        return Recovery(
            f"Branch {branch} of {dataset} already has an open transaction, "
            f"{transaction}: commit it or abort it first.",
            f"pltr dataset transactions abort {_q(dataset)} {_q(transaction)}",
        )
    return Recovery(
        f"Branch {branch} of {dataset} already has an open transaction: commit "
        "it or abort it first.",
        f"pltr dataset transactions list {_q(dataset)} --branch {_q(branch)}",
    )


_GRANT = (
    "Grant it to the OAuth client in Developer Console, or use a token that has it."
)


def missing_scope(
    info: ErrorInfo, api_error: Any, ctx: Optional[click.Context]
) -> Optional[Recovery]:
    """403 ``ApiUsageDenied``: name the scope the endpoint needs."""
    if info.error_name != "ApiUsageDenied":
        return None
    scope = _parameters(info).get("missingScope")
    if isinstance(scope, str) and scope:
        return Recovery(f"The token or OAuth client lacks the scope {scope}. {_GRANT}")
    scopes = _command_scopes(ctx)
    if not scopes:
        return None
    noun = "scope" if len(scopes) == 1 else "scopes"
    return Recovery(
        f"This command needs the {noun} {', '.join(scopes)}, which the token or "
        f"OAuth client may lack. {_GRANT}"
    )


def _words(camel: str) -> str:
    return " ".join(re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", camel)).lower()


def permission_denied(
    info: ErrorInfo, api_error: Any, ctx: Optional[click.Context]
) -> Optional[Recovery]:
    """403 ``<Operation>PermissionDenied``: name the operation and the resource."""
    from .resources import rid_resource_type

    name = info.error_name or ""
    if info.type != "permission_denied" or not name.endswith("PermissionDenied"):
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
        f"pltr resource-role list {_q(rid)}" if rid_resource_type(rid) else None,
    )


def rejected_token(
    info: ErrorInfo, api_error: Any, ctx: Optional[click.Context]
) -> Optional[Recovery]:
    """401 with a token: say how to give pltr a new one."""
    from pltr.services import base

    if info.type != "auth_error" or info.status_code != 401:
        return None
    source = base.AuthManager().get_auth_context(_profile(ctx)).source
    if source.auth_type != "token":
        return None
    if source.kind == "environment":
        return Recovery(
            "Foundry rejected FOUNDRY_TOKEN: it has expired or been revoked. "
            "Set a new token.",
            "export FOUNDRY_TOKEN=<new-token>",
        )
    if not source.profile:
        return None
    command = (
        f"pltr configure configure --profile {_q(source.profile)} --auth-type token"
    )
    if source.host:
        command += f" --host {_q(source.host)}"
    return Recovery(
        f"Foundry rejected the token of profile {source.profile}: it has expired "
        "or been revoked. Store a new one.",
        f"{command} --token <new-token>",
    )


#: Most names read from a list endpoint to find the closest ones.
NAME_LIMIT = 2000


def closest_names(wanted: str, names: List[str], limit: int = 3) -> List[str]:
    """The names closest to ``wanted``: same name in another case first."""
    exact = [name for name in names if name.lower() == wanted.lower()]
    lowered: Dict[str, str] = {}
    for name in names:
        lowered.setdefault(name.lower(), name)
    close = difflib.get_close_matches(wanted.lower(), list(lowered), limit, 0.6)
    result = exact + [lowered[c] for c in close if lowered[c] not in exact]
    return result[:limit]


def _api_names(items: Any) -> List[str]:
    return [str(item.api_name) for item in itertools.islice(items, NAME_LIMIT)]


_ONTOLOGY_ERRORS = (
    "ObjectTypeNotFound",
    "PropertiesNotFound",
    "ActionTypeNotFound",
    "LinkTypeNotFound",
)


def ontology_names(
    info: ErrorInfo, api_error: Any, ctx: Optional[click.Context]
) -> Optional[Recovery]:
    """An object type, property, action type or link type that doesn't exist:
    list the closest API names (they are case-sensitive)."""
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
        names = list(ontologies.ObjectType.get(ontology, object_type).properties)
        pairs = [
            f"{prop!r} -> {', '.join(closest_names(str(prop), names)) or 'none'}"
            for prop in properties
        ]
        return Recovery(
            "Property API names are case-sensitive. Closest: " + "; ".join(pairs) + ".",
            f"pltr ontology object-type-get {_q(ontology)} {_q(object_type)}",
        )
    if name == "ObjectTypeNotFound":
        wanted, label = parameters.get("objectType"), "object type"
        listing = f"pltr ontology object-type-list {_q(ontology)}"
        items: Callable[[], Any] = lambda: ontologies.ObjectType.list(  # noqa: E731
            ontology, page_size=500
        )
    elif name == "ActionTypeNotFound":
        wanted, label = parameters.get("actionType"), "action type"
        listing = f"pltr api ontologies ontology action-type list {_q(ontology)}"
        items = lambda: ontologies.ActionType.list(ontology, page_size=500)  # noqa: E731
    else:
        wanted, label = parameters.get("linkType"), "link type"
        if not object_type:
            return None
        listing = (
            "pltr api ontologies ontology object-type list-outgoing-link-types "
            f"{_q(ontology)} {_q(object_type)}"
        )
        items = lambda: ontologies.ObjectType.list_outgoing_link_types(  # noqa: E731
            ontology, object_type, page_size=500
        )
    if not wanted:
        return None
    close = closest_names(str(wanted), _api_names(items()))
    if not close:
        return Recovery(
            f"No {label} in {ontology} has an API name close to {wanted!r}.", listing
        )
    return Recovery(
        f"{label.capitalize()} API names are case-sensitive. Closest to "
        f"{wanted!r}: {', '.join(close)}.",
        listing,
    )


PROVIDERS: List[Provider] = [
    ontology_names,
    open_transaction,
    missing_scope,
    permission_denied,
    rejected_token,
]


def api_error_in(exc: BaseException) -> Any:
    """The first Foundry API error (``PalantirRPCException``) in the chain."""
    from foundry_sdk import _errors as sdk

    from .errors import _chain

    for candidate in _chain(exc):
        if isinstance(candidate, sdk.PalantirRPCException):
            return candidate
    return None


def add_recovery(info: ErrorInfo, exc: BaseException) -> None:
    """Give ``info`` the hint and suggested command of the first provider that
    knows the failure; keep it unchanged if none does (or one fails)."""
    try:
        api_error = api_error_in(exc)
    except Exception:
        api_error = None
    ctx = click.get_current_context(silent=True)
    for provider in PROVIDERS:
        try:
            recovery = provider(info, api_error, ctx)
        except Exception:
            continue
        if recovery is not None:
            info.hint = recovery.hint
            info.generic_hint = False
            info.suggested_command = recovery.suggested_command
            return
