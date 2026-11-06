"""Build `pltr api` click commands from the generated specs, lazily.

`pltr api` lists namespaces from the tiny generated index (`_specs/__init__.py`).
A namespace's spec module is imported only when that namespace is used, and
resource groups and method commands are built only when they are reached, so
`pltr --help` and the curated commands don't pay for the generated tree.

At call time every command resolves its SDK method by attribute path on the
client returned by `AuthManager().get_client(profile)`, so it works against a newer
installed SDK too: `preview=True` is passed only if the installed method still
accepts `preview`, and a method or parameter that no longer exists fails with a
clear error instead of a traceback.
"""

from __future__ import annotations

import functools
import importlib
import inspect
import os
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import click

from . import _adapter as adapter

SPECS_PACKAGE = "pltr.commands.api._specs"


def _index() -> Any:
    return importlib.import_module(SPECS_PACKAGE)


def generated_sdk_version() -> str:
    return str(_index().SDK_VERSION)


def installed_sdk_version() -> str:
    try:
        from importlib.metadata import version

        return version("foundry-platform-sdk")
    except Exception:
        import foundry_sdk

        return str(getattr(foundry_sdk, "__version__", "unknown"))


# ---------------------------------------------------------------------------
# JSON-mode usage errors
# ---------------------------------------------------------------------------


def json_requested(args: Sequence[str]) -> bool:
    """Whether the invocation asks for JSON (`--format json` or PLTR_FORMAT)."""
    args = list(args)
    for position, arg in enumerate(args):
        if arg == "--":
            break
        if arg == "--format" and position + 1 < len(args):
            return adapter.is_json(args[position + 1])
        if arg.startswith("--format="):
            return adapter.is_json(arg.split("=", 1)[1])
    return adapter.is_json(os.environ.get("PLTR_FORMAT"))


class _JsonUsageErrorsMixin:
    """Report click usage errors as JSON when JSON output was requested."""

    def parse_args(self, ctx: click.Context, args: List[str]) -> List[str]:
        original = list(args)  # click's parser consumes `args` in place
        try:
            return super().parse_args(ctx, args)  # type: ignore[misc]
        except click.UsageError as exc:
            if json_requested(original):
                adapter.fail_usage(exc)
            raise

    def resolve_command(self, ctx: click.Context, args: List[str]) -> Any:
        original = list(args)
        try:
            return super().resolve_command(ctx, args)  # type: ignore[misc]
        except click.UsageError as exc:
            if json_requested(original):
                adapter.fail_usage(exc)
            raise


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


class SpecGroup(_JsonUsageErrorsMixin, click.Group):
    """A namespace or resource group whose children are built on first use."""

    def __init__(
        self,
        name: str,
        *,
        loader: Callable[[], Dict[str, Any]],
        context: Dict[str, Any],
        summary: str,
    ) -> None:
        super().__init__(name=name, short_help=summary, no_args_is_help=True)
        self._loader = loader
        self._context = context
        self._spec: Optional[Dict[str, Any]] = None
        self._built: Dict[str, click.Command] = {}

    @property
    def spec(self) -> Dict[str, Any]:
        if self._spec is None:
            self._spec = self._loader()
            self.help = self._spec.get("help", "")
        return self._spec

    def _children(self) -> Dict[str, Tuple[str, Dict[str, Any]]]:
        spec = self.spec
        children: Dict[str, Tuple[str, Dict[str, Any]]] = {}
        for method in spec.get("methods", []):
            children[method["name"]] = ("method", method)
        for resource in spec.get("resources", []):
            children[resource["name"]] = ("resource", resource)
        return children

    def list_commands(self, ctx: click.Context) -> List[str]:
        return sorted(self._children())

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        if cmd_name in self._built:
            return self._built[cmd_name]
        child = self._children().get(cmd_name)
        if child is None:
            return None
        kind, spec = child
        context = dict(self._context)
        context["cli_path"] = self._context["cli_path"] + (spec["name"],)
        context["sdk_path"] = self._context["sdk_path"] + (spec["sdk"],)
        command: click.Command
        if kind == "resource":
            command = SpecGroup(
                spec["name"],
                loader=functools.partial(dict, spec),
                context=context,
                summary=spec.get("summary", ""),
            )
        else:
            command = build_method_command(spec, context)
        self._built[cmd_name] = command
        return command

    def format_help_text(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        self.spec  # load the help text
        super().format_help_text(ctx, formatter)


def _load_namespace(module: str) -> Dict[str, Any]:
    spec: Dict[str, Any] = importlib.import_module(f"{SPECS_PACKAGE}.{module}").SPEC
    return spec


def namespace_group(
    name: str, entry: Dict[str, Any], cli_prefix: Tuple[str, ...]
) -> SpecGroup:
    """A namespace group; its spec module is imported on first use."""
    return SpecGroup(
        name,
        loader=functools.partial(_load_namespace, entry["module"]),
        context={
            "cli_path": cli_prefix + (name,),
            "sdk_path": (entry["sdk"],),
            "client": entry["client"],
        },
        summary=entry.get("summary", ""),
    )


class IndexGroup(_JsonUsageErrorsMixin, click.Group):
    """A group of namespaces read from the generated index (e.g. a future `v3`)."""

    def __init__(
        self,
        name: str,
        entries: Dict[str, Any],
        cli_path: Tuple[str, ...],
        summary: str,
    ):
        super().__init__(
            name=name, short_help=summary, help=summary, no_args_is_help=True
        )
        self._entries = entries
        self._cli_path = cli_path
        self._built: Dict[str, click.Command] = {}

    def list_commands(self, ctx: click.Context) -> List[str]:
        return sorted(self._entries)

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        return index_child(self._entries, cmd_name, self._cli_path, self._built)


def index_child(
    entries: Dict[str, Any],
    name: str,
    cli_path: Tuple[str, ...],
    cache: Dict[str, click.Command],
) -> Optional[click.Command]:
    if name in cache:
        return cache[name]
    entry = entries.get(name)
    if entry is None:
        return None
    command: click.Command
    if "module" in entry:
        command = namespace_group(name, entry, cli_path)
    else:
        command = IndexGroup(
            name,
            entry.get("namespaces", {}),
            cli_path + (name,),
            entry.get("summary", ""),
        )
    cache[name] = command
    return command


# ---------------------------------------------------------------------------
# Method commands
# ---------------------------------------------------------------------------

_TYPE_HINTS = {
    "datetime": "ISO-8601 date-time with a time zone, e.g. 2026-01-31T12:00:00Z.",
    "date": "ISO-8601 date, e.g. 2026-01-31.",
    "bytes": "Path of the file to send as the request body, or - to read stdin.",
}
_METAVARS = {
    "str": "TEXT",
    "int": "INTEGER",
    "float": "FLOAT",
    "datetime": "DATETIME",
    "date": "DATE",
    "json": "JSON",
    "bytes": "FILE",
}


def option_name(param: Dict[str, Any]) -> str:
    return str(param.get("option") or "--" + param["name"].replace("_", "-"))


def _click_type(param: Dict[str, Any]) -> Any:
    kind = param["type"]
    if kind == "int":
        return click.INT
    if kind == "float":
        return click.FLOAT
    if kind == "choice":
        return click.Choice(param["choices"])
    return click.STRING


def _sentence(text: str) -> str:
    text = text.strip()
    if text and text[-1] not in ".!?:)":
        text += "."
    return text


def _option_help(param: Dict[str, Any]) -> str:
    parts = [_sentence(param.get("help", ""))]
    kind = param["type"]
    if kind == "json":
        schema = param.get("schema")
        label = f"JSON ({schema})" if schema else "JSON"
        parts.append(f"{label}: inline, @file.json, or @- for stdin.")
    elif kind in _TYPE_HINTS:
        parts.append(_TYPE_HINTS[kind])
    if param.get("multiple"):
        parts.append("Repeat the option to pass several values.")
    if param.get("auto") == "body_length":
        parts.append("Defaults to the size of --body.")
    return " ".join(part for part in parts if part)


def _argument_help(param: Dict[str, Any]) -> str:
    text = _sentence(param.get("help", "")) or f"Path parameter {param['api']}."
    schema = param.get("schema")
    if schema:
        text += f" Type: {schema}."
    return text


def sdk_parameter(param: Dict[str, Any]) -> click.Parameter:
    """The click argument/option for one SDK parameter."""
    name = param["name"]
    if param["in"] == "path":
        return click.Argument([name], type=_click_type(param), required=True)
    required = bool(param.get("required"))
    declaration = option_name(param)
    help_text = _option_help(param)
    if param["type"] == "bool":
        return click.Option(
            [f"{declaration}/--no-{declaration[2:]}", name],
            default=None,
            required=required,
            help=help_text,
        )
    return click.Option(
        [declaration, name],
        type=_click_type(param),
        required=required,
        multiple=bool(param.get("multiple")),
        metavar=None if param["type"] == "choice" else _METAVARS[param["type"]],
        help=help_text,
    )


def pltr_options(spec: Dict[str, Any]) -> List[click.Option]:
    """The options pltr adds to every generated command."""
    options = [
        click.Option(
            ["--profile", "pltr_profile"],
            help="Auth profile to use (default: the active profile).",
        ),
        click.Option(
            ["--format", "pltr_format"],
            type=click.Choice(adapter.FORMATS, case_sensitive=False),
            default="table",
            show_default=True,
            envvar="PLTR_FORMAT",
            help=(
                "Output format; json is the SDK's own serialization. Can be set "
                "with PLTR_FORMAT."
            ),
        ),
    ]
    if spec.get("binary"):
        options.append(
            click.Option(
                ["--output-file", "--output", "-o", "pltr_output"],
                type=click.Path(dir_okay=False, allow_dash=True),
                help=(
                    "Write the binary response to FILE (- for stdout). Without it the "
                    "response goes to stdout, unless stdout is a terminal."
                ),
            )
        )
    else:
        options.append(
            click.Option(
                ["--output", "-o", "pltr_output"],
                type=click.Path(dir_okay=False),
                help="Write the output to FILE instead of stdout.",
            )
        )
    if spec.get("paged"):
        options.append(
            click.Option(
                ["--all", "pltr_all"],
                is_flag=True,
                help=(
                    'Fetch every page and print them as one {"data": [...]} result. '
                    "Without it one page is printed, with its nextPageToken."
                ),
            )
        )
    if spec.get("destructive"):
        options.append(
            click.Option(
                ["--yes", "-y", "pltr_yes"],
                is_flag=True,
                help=(
                    "Don't ask for confirmation. Required when stdin is not a terminal."
                ),
            )
        )
    return options


def _preformat(text: str) -> str:
    """Prepare an SDK docstring for click's help formatter.

    Markdown headings become their own paragraphs, and paragraphs that hold
    indented code, JSON, lists or tables keep their layout (click's \\b marker);
    other paragraphs are rewrapped.
    """
    text = re.sub(r"(?m)^(#+ .*)$", r"\n\1\n", text)
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        lines = paragraph.splitlines()
        keep = len(lines) > 1 and any(
            re.match(r"(\s|[-*] |\d+\. |[{}|]|```)", line) for line in lines
        )
        paragraphs.append("\b\n" + paragraph if keep else paragraph)
    return "\n\n".join(paragraphs)


def _epilog(spec: Dict[str, Any], context: Dict[str, Any]) -> str:
    lines = [
        f"SDK method: FoundryClient.{'.'.join(context['sdk_path'])}",
        f"HTTP: {spec['http']}",
    ]
    if spec.get("beta"):
        lines.append("Beta: pltr passes preview=True for you.")
    if spec.get("paged"):
        lines.append("Paged: prints one page by default; --all fetches every page.")
    if spec.get("binary"):
        lines.append("Binary response: written to --output-file or to stdout.")
    if spec.get("destructive"):
        lines.append("Destructive: asks for confirmation; --yes skips it.")
    return "\b\n" + "\n".join(lines)


class ApiCommand(_JsonUsageErrorsMixin, click.Command):
    """A generated command; documents its positional arguments too.

    `spec` is the generated method spec and `sdk_method` the dotted SDK path
    (e.g. "admin.User.list"), for coverage reports and the command manifest.
    """

    def __init__(
        self,
        *args: Any,
        argument_help: Dict[str, str],
        spec: Dict[str, Any],
        sdk_method: str,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.argument_help = argument_help
        self.spec = spec
        self.sdk_method = sdk_method

    def format_options(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        rows = [
            (param.human_readable_name, self.argument_help.get(param.name or "", ""))
            for param in self.get_params(ctx)
            if isinstance(param, click.Argument)
        ]
        if rows:
            with formatter.section("Arguments"):
                formatter.write_dl(rows)
        super().format_options(ctx, formatter)


def build_method_command(
    spec: Dict[str, Any], context: Dict[str, Any]
) -> click.Command:
    params: List[click.Parameter] = [sdk_parameter(p) for p in spec["params"]]
    params.extend(pltr_options(spec))
    beta = "[beta] " if spec.get("beta") else ""
    description = spec.get("help") or (
        f"Call FoundryClient.{'.'.join(context['sdk_path'])} ({spec['http']})."
    )
    argument_help = {
        p["name"]: _argument_help(p) for p in spec["params"] if p["in"] == "path"
    }

    def callback(**values: Any) -> None:
        run_method(spec, context, values)

    return ApiCommand(
        spec["name"],
        params=params,
        callback=callback,
        help=beta + _preformat(description),
        short_help=beta + (spec.get("summary") or description.splitlines()[0]),
        epilog=_epilog(spec, context),
        argument_help=argument_help,
        spec=spec,
        sdk_method=".".join(context["sdk_path"]),
    )


# ---------------------------------------------------------------------------
# Running a method
# ---------------------------------------------------------------------------


def get_client(client_key: str, profile: Optional[str]) -> Any:
    """The authenticated SDK client for a generated command."""
    if client_key != "v2":
        raise adapter.unavailable(
            f"pltr has no client factory for the {client_key} API yet."
        )
    from pltr.auth.manager import AuthManager

    return AuthManager().get_client(profile)


@functools.lru_cache(maxsize=None)
def _signature(function: Any) -> inspect.Signature:
    return inspect.signature(function)


def method_signature(method: Any) -> inspect.Signature:
    """Signature of a bound SDK method (cached per underlying function)."""
    function = getattr(method, "__func__", method)
    signature = _signature(function)
    if hasattr(method, "__func__"):
        parameters = list(signature.parameters.values())[1:]
        signature = signature.replace(parameters=parameters)
    return signature


def accepts_preview(method: Any) -> bool:
    """Beta methods take `preview`; pass it only if the installed method does."""
    return "preview" in method_signature(method).parameters


def resolve(client: Any, context: Dict[str, Any]) -> Tuple[Any, Any]:
    """Return (resource client, bound method) for the command's SDK path."""
    obj = client
    parent = client
    for attr in context["sdk_path"]:
        parent = obj
        try:
            obj = getattr(obj, attr)
        except AttributeError:
            raise adapter.unavailable(
                f"`pltr {' '.join(context['cli_path'])}` calls "
                f"FoundryClient.{'.'.join(context['sdk_path'])}, which is not "
                f"available in foundry-platform-sdk {installed_sdk_version()} "
                f"(the generated commands were built from {generated_sdk_version()}). "
                "Install pltr in its own environment (uv tool install pltr-cli) to get "
                "the SDK version it was tested with."
            ) from None
    return parent, obj


def _read_text_argument(value: str, label: str) -> str:
    if not value.startswith("@"):
        return value
    path = value[1:]
    try:
        if path == "-":
            return click.get_text_stream("stdin").read()
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise adapter.usage_error(f"{label}: can't read {path}: {exc}") from exc


def parse_json(value: str, label: str) -> Any:
    import json

    text = _read_text_argument(value, label)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise adapter.usage_error(f"{label}: invalid JSON ({exc})") from exc


def read_bytes(value: str, label: str) -> bytes:
    try:
        if value == "-":
            return click.get_binary_stream("stdin").read()
        with open(value, "rb") as handle:
            return handle.read()
    except OSError as exc:
        raise adapter.usage_error(f"{label}: can't read {value}: {exc}") from exc


def build_kwargs(spec: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
    """Convert parsed CLI values into SDK keyword arguments (None = not given)."""
    kwargs: Dict[str, Any] = {}
    body_length: Optional[int] = None
    for param in spec["params"]:
        name = param["name"]
        value = values.get(name)
        if param.get("multiple"):
            if value:
                kwargs[name] = list(value)
            continue
        if value is None:
            continue
        label = name.upper() if param["in"] == "path" else option_name(param)
        if param["type"] == "json":
            kwargs[name] = parse_json(value, label)
        elif param["type"] == "bytes":
            kwargs[name] = read_bytes(value, label)
            body_length = len(kwargs[name])
        else:
            kwargs[name] = value
    for param in spec["params"]:
        if (
            param.get("auto") == "body_length"
            and param["name"] not in kwargs
            and body_length is not None
        ):
            kwargs[param["name"]] = body_length
    return kwargs


def check_parameters(
    method: Any, kwargs: Dict[str, Any], context: Dict[str, Any]
) -> None:
    accepted = method_signature(method).parameters
    unknown = sorted(name for name in kwargs if name not in accepted)
    if unknown:
        raise adapter.unavailable(
            f"FoundryClient.{'.'.join(context['sdk_path'])} in foundry-platform-sdk "
            f"{installed_sdk_version()} doesn't accept {', '.join(unknown)} (the "
            f"generated commands were built from {generated_sdk_version()})."
        )


def confirmation_message(
    spec: Dict[str, Any], context: Dict[str, Any], kwargs: Dict[str, Any]
) -> str:
    http_method, _, path = spec["http"].partition(" ")
    for param in spec["params"]:
        if param["in"] == "path" and param["name"] in kwargs:
            path = path.replace("{" + param["api"] + "}", str(kwargs[param["name"]]))
    return (
        f"{http_method} {path} (FoundryClient.{'.'.join(context['sdk_path'])}) is "
        "destructive. Continue?"
    )


def run_method(
    spec: Dict[str, Any], context: Dict[str, Any], values: Dict[str, Any]
) -> None:
    fmt = str(values.pop("pltr_format", "table")).lower()
    output = values.pop("pltr_output", None)
    fetch_all = bool(values.pop("pltr_all", False))
    yes = bool(values.pop("pltr_yes", False))
    profile = values.pop("pltr_profile", None)
    try:
        kwargs = build_kwargs(spec, values)
        destructive = bool(spec.get("destructive"))
        if destructive and not yes and not adapter.stdin_is_terminal():
            adapter.confirm("", yes=False, fmt=fmt)  # raises the usage error
        if spec.get("binary") and not output and adapter.stdout_is_terminal():
            raise adapter.usage_error(
                "This command returns binary data. Pass --output-file FILE, or "
                "redirect stdout to a file or pipe."
            )
        client = get_client(context.get("client", "v2"), profile)
        resource, method = resolve(client, context)
        check_parameters(method, kwargs, context)
        if accepts_preview(method):
            kwargs["preview"] = True
        if destructive:
            adapter.confirm(
                confirmation_message(spec, context, kwargs), yes=yes, fmt=fmt
            )
        if spec.get("binary"):
            run_binary(resource, method, context, kwargs, output, fmt)
        elif spec.get("paged"):
            run_paged(spec, resource, method, context, kwargs, fetch_all, output, fmt)
        else:
            result = method(**kwargs)
            annotation = method_signature(method).return_annotation
            if annotation is inspect.Signature.empty:
                annotation = None
            document = (
                None if result is None else adapter.to_jsonable(result, annotation)
            )
            adapter.emit_result(document, fmt=fmt, output=output)
    except click.exceptions.Exit:
        raise
    except Exception as exc:
        adapter.fail(exc, fmt=fmt)


def run_binary(
    resource: Any,
    method: Any,
    context: Dict[str, Any],
    kwargs: Dict[str, Any],
    output: Optional[str],
    fmt: str,
) -> None:
    name = context["sdk_path"][-1]
    streaming = getattr(getattr(resource, "with_streaming_response", None), name, None)
    if streaming is not None:
        with streaming(**kwargs) as response:
            written = adapter.emit_binary(response.iter_bytes(), output_file=output)
    else:
        data = method(**kwargs)
        written = adapter.emit_binary([bytes(data or b"")], output_file=output)
    if output and output != "-":
        adapter.info(f"Wrote {written} bytes to {output}", fmt=fmt)


def _page_fetcher(
    spec: Dict[str, Any], resource: Any, method: Any, name: str
) -> Callable[..., Dict[str, Any]]:
    """A function returning one page as a JSON-safe dict in the API's shape."""
    raw = None
    if spec.get("paged") == "iterator":
        raw = getattr(getattr(resource, "with_raw_response", None), name, None)

    def fetch(**kwargs: Any) -> Dict[str, Any]:
        if raw is not None:
            return adapter.to_jsonable(raw(**kwargs).decode())
        result = method(**kwargs)
        if (
            hasattr(result, "next_page_token")
            and hasattr(result, "data")
            and not hasattr(result, "model_dump")
        ):
            page: Dict[str, Any] = {"data": adapter.to_jsonable(list(result.data))}
            if result.next_page_token:
                page["nextPageToken"] = result.next_page_token
            return page
        return adapter.to_jsonable(result)

    return fetch


def run_paged(
    spec: Dict[str, Any],
    resource: Any,
    method: Any,
    context: Dict[str, Any],
    kwargs: Dict[str, Any],
    fetch_all: bool,
    output: Optional[str],
    fmt: str,
) -> None:
    fetch = _page_fetcher(spec, resource, method, context["sdk_path"][-1])
    page = fetch(**kwargs)
    if not fetch_all:
        adapter.emit_result(page, fmt=fmt, output=output)
        return
    data = list(page.get("data") or [])
    seen = set()
    token = page.get("nextPageToken")
    while token:
        if token in seen:
            raise adapter.ApiCommandError(
                f"The API returned the page token {token!r} twice; stopping.",
                exit_code=7,
                error_type="api_error",
            )
        seen.add(token)
        kwargs["page_token"] = token
        page = fetch(**kwargs)
        data.extend(page.get("data") or [])
        token = page.get("nextPageToken")
    adapter.emit_result({"data": data}, fmt=fmt, output=output)
