"""``--emit-code``: print the SDK code for a command's call instead of making it (#192).

``pltr <command> ... --emit-code`` (the flag works anywhere on the line) runs
the command up to its Foundry call, then prints the foundry-platform-sdk
Python code for that call, with the real argument values, and exits 0. Nothing
is called: the services get a :class:`RecordingClient`, whose first SDK call
stops the command with a :class:`RecordedCall`; ``@pltr_command`` renders it
(:mod:`pltr.contract.codegen`). Destructive commands don't ask (nothing runs),
and Compass paths (#193) become ``get_by_path`` lookups in the snippet.

Commands that make several calls, call Foundry without the SDK (the labeled
direct-HTTP exceptions), or make no Foundry call fail with
``emit_code_unsupported`` (exit 2) rather than print a partial snippet.
"""

from __future__ import annotations

import contextvars
import functools
import inspect
import typing
from typing import Any, Dict, List, Optional, Sequence, Tuple

import click

from .errors import ExitCode, PltrError

EMIT_FLAG = "--emit-code"

_ACTIVE: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "pltr_emit_code", default=False
)

#: Accessors on SDK resource clients that wrap a method without changing it.
_WRAPPERS = ("with_raw_response", "with_streaming_response")


def emit_mode() -> bool:
    """True while a command runs with ``--emit-code``."""
    return _ACTIVE.get()


def set_emit_mode(value: bool) -> contextvars.Token:
    return _ACTIVE.set(value)


def reset_emit_mode(token: contextvars.Token) -> None:
    _ACTIVE.reset(token)


def strip_emit_flag(args: Sequence[str]) -> Tuple[List[str], bool]:
    """Remove ``--emit-code`` from the arguments (before any ``--``)."""
    result: List[str] = []
    found = False
    for index, arg in enumerate(args):
        if arg == "--":
            result.extend(args[index:])
            break
        if arg == EMIT_FLAG:
            found = True
            continue
        result.append(arg)
    return result, found


class EmitUnsupported(PltrError):
    """``--emit-code`` can't show this command as one SDK snippet."""

    error_type = "emit_code_unsupported"
    exit_code = ExitCode.USAGE


class EmitDone(BaseException):
    """Stops a command once its snippet is ready (``code``)."""

    def __init__(self, code: str) -> None:
        super().__init__("emit-code snippet ready")
        self.code = code


class RecordedCall(BaseException):
    """An SDK call made on a :class:`RecordingClient`: the command stops here.

    A ``BaseException`` so that services' ``except Exception`` blocks let it
    through.
    """

    def __init__(self, path: Tuple[str, ...], args: tuple, kwargs: Dict[str, Any]):
        super().__init__(".".join(path))
        self.path = path
        self.args_ = args
        self.kwargs = kwargs


class RecordingClient:
    """Stands in for ``FoundryClient`` in emit mode: records the first call."""

    def __init__(self, path: Tuple[str, ...] = ()) -> None:
        self._path = path

    def __getattr__(self, name: str) -> "RecordingClient":
        if name.startswith("__"):
            raise AttributeError(name)
        return RecordingClient(self._path + (name,))

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise RecordedCall(self._path, args, kwargs)


# ------------------------------------------------------------- SDK lookups


@functools.lru_cache(maxsize=1)
def reference_client() -> Any:
    """A FoundryClient used only to look up method signatures (never called)."""
    from foundry_sdk import FoundryClient, UserTokenAuth

    return FoundryClient(
        auth=UserTokenAuth(token="unused"), hostname="emit-code.invalid"
    )


def sdk_method(sdk_path: str) -> Any:
    """The bound SDK method at ``sdk_path`` (``datasets.Dataset.get``)."""
    target = reference_client()
    for attr in sdk_path.split("."):
        target = getattr(target, attr)
    return target


def paged_kind(method: Any) -> Optional[str]:
    """``"iterator"``, ``"response"`` or None, from the method's return type."""
    import pydantic
    from foundry_sdk._core.resource_iterator import ResourceIterator

    signature = inspect.signature(method)
    annotation = signature.return_annotation
    if typing.get_origin(annotation) is ResourceIterator:
        return "iterator"
    if (
        "page_token" in signature.parameters
        and isinstance(annotation, type)
        and issubclass(annotation, pydantic.BaseModel)
        and {"data", "next_page_token"} <= set(getattr(annotation, "model_fields", {}))
    ):
        return "response"
    return None


def returns_bytes(method: Any) -> bool:
    annotation = inspect.signature(method).return_annotation
    return isinstance(annotation, type) and issubclass(annotation, bytes)


def typed_argument(value: Any, annotation: Any) -> Any:
    """``value`` validated into the parameter's SDK type (dicts become models)."""
    import pydantic

    from .codegen import PathValue, RawExpr

    if annotation is inspect.Parameter.empty or isinstance(value, (PathValue, RawExpr)):
        return value
    if not isinstance(value, (dict, list)):
        return value
    if isinstance(value, list) and any(isinstance(v, PathValue) for v in value):
        return value  # validating would turn the paths into plain strings
    try:
        return pydantic.TypeAdapter(annotation).validate_python(value)
    except Exception:
        return value


def call_from_recording(
    recorded: RecordedCall, *, paged: bool, binary: bool, output: Optional[str]
) -> Any:
    """A :class:`~pltr.contract.codegen.Call` for a recorded SDK call."""
    from .codegen import Call

    path = [part for part in recorded.path if part not in _WRAPPERS]
    sdk_path = ".".join(path)
    method = sdk_method(sdk_path)
    signature = inspect.signature(method)
    bound = signature.bind_partial(*recorded.args_, **recorded.kwargs)
    kwargs: Dict[str, Any] = {}
    for name, value in bound.arguments.items():
        if value is None or name.startswith("_") or name == "request_timeout":
            continue
        kwargs[name] = typed_argument(value, signature.parameters[name].annotation)
    return Call(
        sdk_path,
        kwargs,
        paged=paged_kind(method) if paged else None,
        binary=binary or returns_bytes(method),
        output=output,
    )


def check_supported(meta: Any, command_path: str) -> None:
    """Fail unless ``--emit-code`` can show the command as one SDK call."""
    if meta is not None and meta.no_emit_code:
        raise EmitUnsupported(
            f"--emit-code can't show `{command_path}` as one SDK call: "
            f"{meta.no_emit_code}"
        )
    if meta is None or (not meta.sdk and not meta.http):
        raise EmitUnsupported(
            f"`{command_path}` makes no Foundry call, so --emit-code has no SDK "
            "code to show."
        )
    if meta.http:
        raise EmitUnsupported(
            f"`{command_path}` calls Foundry without foundry-platform-sdk "
            f"({'; '.join(meta.http)}), so --emit-code has no SDK code to show."
        )
    if len(meta.sdk) > 1:
        raise EmitUnsupported(
            f"`{command_path}` makes several calls ({', '.join(meta.sdk)}), so "
            "--emit-code can't show it as one snippet. Write them one by one: "
            "`pltr commands show` lists the SDK methods, and `pltr api ... "
            "--emit-code` shows each.",
        )


def leaf_command(root: click.Group, args: Sequence[str]) -> Optional[click.Command]:
    """The command ``args`` name, found by walking the group tree."""
    command: click.Command = root
    ctx = click.Context(root, info_name="pltr")
    for arg in args:
        if arg.startswith("-"):
            continue
        if not isinstance(command, click.Group):
            break
        sub = command.get_command(ctx, arg)
        if sub is None:
            break
        ctx = click.Context(sub, info_name=arg, parent=ctx)
        command = sub
    return None if command is root else command
