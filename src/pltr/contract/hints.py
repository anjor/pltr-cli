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

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

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

PROVIDERS: List[Provider] = []


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
