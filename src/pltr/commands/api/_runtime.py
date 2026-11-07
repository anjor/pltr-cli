"""Build `pltr api` click commands from the generated specs, lazily.

`pltr api` lists namespaces from the tiny generated index (`_specs/__init__.py`).
A namespace's spec module is imported only when that namespace is used, and
resource groups and method commands are built only when they are reached, so
`pltr --help` and the curated commands don't pay for the generated tree.

Every command talks to the user through `pltr.contract` like the curated
commands: the shared options (`--profile`, `--format`, `--output`, `--yes`,
the paging options), `@pltr_command` metadata and error handling, `emit` and
`confirm_destructive`.

At call time every command resolves its SDK method by attribute path on the
client the services use, so it works against a newer installed SDK too:
`preview=True` is passed only if the installed method still accepts
`preview`, and a method or parameter that no longer exists fails with a clear
error instead of a traceback.
"""

from __future__ import annotations

import functools
import importlib
import inspect
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

import click

from pltr.contract import (
    BETA_LABEL,
    PltrError,
    check_binary_output,
    click_format_option,
    click_output_option,
    click_page_options,
    click_profile_option,
    click_yes_option,
    collect_pages,
    confirm_destructive,
    emit,
    emit_bytes,
    load_json_input,
    pltr_command,
    spinner,
    success,
)

SPECS_PACKAGE = "pltr.commands.api._specs"

#: SDK parameters that the shared paging options (`click_page_options`)
#: provide for paged commands.
PAGING_PARAMETERS = ("page_size", "page_token")


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
# Groups
# ---------------------------------------------------------------------------


class SpecGroup(click.Group):
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
        _ = self.spec  # loading the spec sets self.help
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


class IndexGroup(click.Group):
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


def param_dest(param: Dict[str, Any]) -> str:
    """The click parameter name of an SDK parameter.

    Its python name, unless the generator renamed its option because it
    collides with a shared option (`format` -> `--api-format` / `api_format`).
    """
    if param.get("option"):
        return str(param["option"])[2:].replace("-", "_")
    return str(param["name"])


def is_shared_paging_parameter(spec: Dict[str, Any], param: Dict[str, Any]) -> bool:
    return bool(spec.get("paged")) and param["name"] in PAGING_PARAMETERS


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
        if param.get("required"):
            parts.append("The API requires this list; leave it out to send [].")
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
    dest = param_dest(param)
    if param["in"] == "path":
        return click.Argument([dest], type=_click_type(param), required=True)
    # A repeatable option can't express an empty list, which many required list
    # parameters accept (e.g. `select`: all properties), so it is never required;
    # leaving it out sends [].
    required = bool(param.get("required")) and not param.get("multiple")
    declaration = option_name(param)
    help_text = _option_help(param)
    if param["type"] == "bool":
        return click.Option(
            [f"{declaration}/--no-{declaration[2:]}", dest],
            default=None,
            required=required,
            help=help_text,
        )
    return click.Option(
        [declaration, dest],
        type=_click_type(param),
        required=required,
        multiple=bool(param.get("multiple")),
        metavar=None if param["type"] == "choice" else _METAVARS[param["type"]],
        help=help_text,
    )


def shared_options(spec: Dict[str, Any]) -> List[click.Parameter]:
    """The shared `pltr.contract` options of a generated command, in help order.

    `--profile`, `--format`, `--output`, plus `--yes` for destructive and the
    paging options for paged commands. They come from the contract's click
    decorators, applied to a placeholder to collect the options they declare.
    """
    decorators: List[Callable[[Any], Any]] = [
        click_profile_option,
        click_format_option,
        click_output_option,
    ]
    if spec.get("destructive"):
        decorators.append(click_yes_option)
    if spec.get("paged"):
        decorators.append(click_page_options)

    def placeholder() -> None:
        """Collects the options the decorators declare."""

    target: Any = placeholder
    for decorate in reversed(decorators):
        target = decorate(target)
    # click's decorators record their parameters in reverse declaration order.
    return list(reversed(target.__click_params__))


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
        lines.append(
            "Paged: prints one page (the API's response) by default; --max-pages "
            "and --all fetch more."
        )
    if spec.get("stop_at_empty_page"):
        lines.append(
            "The API returns a next page token on every page (to poll for new "
            "items): --max-pages and --all stop at the first empty page."
        )
    if spec.get("binary"):
        lines.append("Binary response: written to --output FILE or to stdout.")
    if spec.get("destructive"):
        lines.append("Destructive: asks for confirmation; --yes skips it.")
    return "\b\n" + "\n".join(lines)


class ApiCommand(click.Command):
    """A generated command; documents its positional arguments too.

    `spec` is the generated method spec and `sdk_method` the dotted SDK path
    (e.g. "admin.User.list"). The command's `pltr.contract` CommandMeta (read
    with `get_command_meta`) carries the same SDK path and the beta,
    destructive and paged flags.
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
    sdk_method = ".".join(context["sdk_path"])
    params: List[click.Parameter] = [
        sdk_parameter(p)
        for p in spec["params"]
        if not is_shared_paging_parameter(spec, p)
    ]
    params.extend(shared_options(spec))
    description = spec.get("help") or f"Calls FoundryClient.{sdk_method}."
    summary = spec.get("summary") or description.splitlines()[0]
    help_text = _preformat(description)
    if spec.get("beta"):
        help_text = f"{BETA_LABEL} {help_text}"
        summary = f"{BETA_LABEL} {summary}"
    argument_help = {
        param_dest(p): _argument_help(p) for p in spec["params"] if p["in"] == "path"
    }

    def run(**values: Any) -> None:
        run_method(spec, context, values)

    callback = pltr_command(
        sdk=sdk_method,
        beta=bool(spec.get("beta")),
        destructive=bool(spec.get("destructive")),
        paged=bool(spec.get("paged")),
    )(run)
    return ApiCommand(
        spec["name"],
        params=params,
        callback=callback,
        help=help_text,
        short_help=summary,
        epilog=_epilog(spec, context),
        argument_help=argument_help,
        spec=spec,
        sdk_method=sdk_method,
    )


# ---------------------------------------------------------------------------
# Running a method
# ---------------------------------------------------------------------------


def get_client(client_key: str, profile: Optional[str]) -> Any:
    """The authenticated SDK client for a generated command.

    Generated commands get their client exactly like the curated services do,
    through the AuthManager of `pltr.services.base` (env-var or profile auth;
    `stub_foundry_http` replaces it in tests).
    """
    if client_key != "v2":
        raise PltrError(f"pltr has no client for the {client_key} API yet.")
    from pltr.services import base

    return base.AuthManager().get_client(profile)


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


def _sdk_mismatch(message: str) -> PltrError:
    return PltrError(
        f"{message} (the generated commands were built from foundry-platform-sdk "
        f"{generated_sdk_version()}).",
        hint=(
            "Install pltr in its own environment (uv tool install pltr-cli or "
            "pipx install pltr-cli) to get the SDK version it was tested with."
        ),
    )


def resolve(client: Any, context: Dict[str, Any]) -> Tuple[Any, Any]:
    """Return (resource client, bound method) for the command's SDK path."""
    obj = client
    parent = client
    for attr in context["sdk_path"]:
        parent = obj
        try:
            obj = getattr(obj, attr)
        except AttributeError:
            raise _sdk_mismatch(
                f"`pltr {' '.join(context['cli_path'])}` calls "
                f"FoundryClient.{'.'.join(context['sdk_path'])}, which is not "
                f"available in foundry-platform-sdk {installed_sdk_version()}"
            ) from None
    return parent, obj


def read_bytes(value: str, label: str) -> bytes:
    try:
        if value == "-":
            return click.get_binary_stream("stdin").read()
        with open(value, "rb") as handle:
            return handle.read()
    except OSError as exc:
        raise click.BadParameter(
            f"cannot read {value}: {exc.strerror or exc}", param_hint=f"'{label}'"
        ) from exc


def build_kwargs(spec: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
    """Convert parsed CLI values into SDK keyword arguments (None = not given)."""
    kwargs: Dict[str, Any] = {}
    body_length: Optional[int] = None
    for param in spec["params"]:
        if is_shared_paging_parameter(spec, param):
            continue
        name = param["name"]
        value = values.get(param_dest(param))
        if param.get("multiple"):
            if value:
                kwargs[name] = list(value)
            elif param.get("required"):
                kwargs[name] = []
            continue
        if value is None:
            continue
        label = name.upper() if param["in"] == "path" else option_name(param)
        if param["type"] == "json":
            kwargs[name] = load_json_input(value, param_hint=f"'{label}'")
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
        raise _sdk_mismatch(
            f"FoundryClient.{'.'.join(context['sdk_path'])} in foundry-platform-sdk "
            f"{installed_sdk_version()} doesn't accept {', '.join(unknown)}"
        )


def request_label(spec: Dict[str, Any], kwargs: Dict[str, Any]) -> str:
    """The endpoint with its path parameters filled in, e.g. `GET /v2/...`."""
    http_method, _, path = spec["http"].partition(" ")
    for param in spec["params"]:
        if param["in"] == "path" and param["name"] in kwargs:
            path = path.replace("{" + param["api"] + "}", str(kwargs[param["name"]]))
    return f"{http_method} {path}"


def run_method(
    spec: Dict[str, Any], context: Dict[str, Any], values: Dict[str, Any]
) -> None:
    """The body of every generated command (errors are handled by @pltr_command)."""
    fmt = values.pop("format")
    output = values.pop("output", None)
    profile = values.pop("profile", None)
    yes = bool(values.pop("yes", False))
    paging = {
        key: values.pop(key, None)
        for key in ("page_size", "page_token", "max_pages", "all_pages")
    }
    kwargs = build_kwargs(spec, values)
    if spec.get("paged") and paging["page_size"] is not None:
        if not any(p["name"] == "page_size" for p in spec["params"]):
            raise click.BadParameter(
                "this endpoint doesn't take a page size", param_hint="'--page-size'"
            )
        kwargs["page_size"] = paging["page_size"]
    if spec.get("binary"):
        check_binary_output(output)  # before downloading anything

    client = get_client(context.get("client", "v2"), profile)
    resource, method = resolve(client, context)
    check_parameters(method, kwargs, context)
    if accepts_preview(method):
        kwargs["preview"] = True
    label = request_label(spec, kwargs)
    if spec.get("destructive"):
        confirm_destructive(
            f"Run {label} (FoundryClient.{'.'.join(context['sdk_path'])})?", yes=yes
        )

    if spec.get("binary"):
        run_binary(resource, method, context, kwargs, output, label)
    elif spec.get("paged"):
        run_paged(spec, resource, method, context, kwargs, paging, fmt, output, label)
    else:
        with spinner(label):
            result = method(**kwargs)
        if result is None:
            success("Done (the API returned no content).")
        emit(result, format=fmt, output=output)


def run_binary(
    resource: Any,
    method: Any,
    context: Dict[str, Any],
    kwargs: Dict[str, Any],
    output: Optional[str],
    label: str,
) -> None:
    """Stream a binary response to --output or stdout (never held in memory)."""
    name = context["sdk_path"][-1]
    streaming = getattr(getattr(resource, "with_streaming_response", None), name, None)
    if streaming is not None:
        with spinner(label), streaming(**kwargs) as response:
            emit_bytes(response.iter_bytes(), output=output)
    else:
        with spinner(label):
            data = method(**kwargs)
        emit_bytes(bytes(data or b""), output=output)


def run_paged(
    spec: Dict[str, Any],
    resource: Any,
    method: Any,
    context: Dict[str, Any],
    kwargs: Dict[str, Any],
    paging: Dict[str, Any],
    fmt: str,
    output: Optional[str],
    label: str,
) -> None:
    """One page as the API returns it, or several merged by `collect_pages`.

    Methods that return an SDK ResourceIterator are called through the SDK's
    `with_raw_response`, which decodes the API's own page response (with
    fields such as `totalCount`); methods that return a paged response model
    already give it.
    """
    raw = None
    if spec.get("paged") == "iterator":
        raw = getattr(
            getattr(resource, "with_raw_response", None), context["sdk_path"][-1], None
        )

    def fetch_page(token: Optional[str]) -> Any:
        call = dict(kwargs)
        if token is not None:
            call["page_token"] = token
        with spinner(label):
            if raw is not None:
                return raw(**call).decode()
            return method(**call)

    max_pages = paging["max_pages"] or 1
    if paging["all_pages"] or max_pages > 1:
        page = collect_pages(
            fetch_page,
            page_token=paging["page_token"],
            max_pages=max_pages,
            all_pages=bool(paging["all_pages"]),
            stop_at_empty_page=bool(spec.get("stop_at_empty_page")),
        )
        emit(page, format=fmt, output=output)
    else:
        emit(fetch_page(paging["page_token"]), format=fmt, output=output)
