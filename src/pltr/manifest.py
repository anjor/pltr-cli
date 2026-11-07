"""The command manifest: every pltr command as data, plus search over it.

The manifest is one JSON document that describes every command, curated and
generated (``pltr api``), so agents can find the right command without
loading every ``--help`` page. ``pltr commands list --format json`` prints it::

    {
      "pltrVersion": "0.17.0",
      "sdkVersion": "1.111.0",
      "groups": [{"path": "pltr folder", "description": "Manage folders", ...}],
      "commands": [
        {
          "path": "pltr folder get",
          "usage": "pltr folder get FOLDER_RID [OPTIONS]",
          "description": "Get a folder's metadata.",
          "beta": false, "destructive": false, "paged": false,
          "generated": false, "local": false, "hidden": false,
          "outputFormats": ["table", "json", "csv"],
          "sdkMethods": ["filesystem.Folder.get"],
          "arguments": [{"name": "folder_rid", "type": "string", ...}],
          "options": [{"name": "profile", "flags": ["--profile", "-p"], ...}],
          "help": "Get a folder's metadata."
        }
      ]
    }

It is read from the live click tree (:func:`pltr.contract.iter_commands`) and
the ``@pltr_command`` metadata, so it can't drift from the CLI. It is
deterministic: sorted, no timestamps, and nothing in it depends on the
terminal, the OS, the environment or the installed SDK patch version.
``sdkVersion`` is the foundry-platform-sdk version the ``pltr api`` tree was
generated from (the locked version), not the installed one.

Keys follow the Foundry API style of pltr's JSON output: camelCase, and keys
that don't apply are left out. A command without ``@pltr_command`` metadata
has no ``beta``, ``destructive``, ``paged`` or ``sdkMethods`` keys (unknown,
not false).

This module imports nothing heavy at import time: ``pltr --help`` imports it
through ``pltr.commands.manifest``.
"""

from __future__ import annotations

import difflib
import enum
import inspect
import re
from typing import (
    Any,
    Dict,
    FrozenSet,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import click
import typer

from .contract import CommandEntry, CommandMeta, iter_commands

PROGRAM = "pltr"

#: Top-level groups whose commands never call Foundry (profiles, aliases,
#: shell completion, the REPL, the manifest itself). This decides ``local``
#: for commands without ``@pltr_command`` metadata; a command with metadata
#: is local when it declares neither SDK methods nor HTTP endpoints.
LOCAL_GROUPS: FrozenSet[str] = frozenset(
    {"alias", "commands", "completion", "configure", "hello", "shell"}
)

#: ``outputFormats`` of a command that writes raw bytes (file content, Arrow,
#: Parquet, images) to stdout or ``--output``.
BINARY_FORMAT = "binary"

#: Keys of a command entry kept in search results (``pltr commands search``).
SUMMARY_KEYS: Tuple[str, ...] = (
    "path",
    "usage",
    "description",
    "beta",
    "destructive",
    "paged",
    "generated",
    "local",
    "sdkMethods",
    "httpEndpoints",
)

Root = Union[typer.Typer, click.Command]


# ------------------------------------------------------------------ building


def build_manifest(root: Optional[Root] = None) -> Dict[str, Any]:
    """Build the manifest document for ``root`` (default: the ``pltr`` CLI).

    Walks the whole tree, so every lazily loaded group (``pltr api``) is
    loaded. The result is plain JSON data.
    """
    if root is None:
        from .cli import app  # imported here: pltr.cli imports this module

        root = app
    command = typer.main.get_command(root) if isinstance(root, typer.Typer) else root
    commands = [command_entry(entry) for entry in iter_commands(command)]
    groups = [group_entry(path, group) for path, group in iter_groups(command)]
    return {
        "pltrVersion": pltr_version(),
        "sdkVersion": sdk_version(),
        "groups": sorted(groups, key=_path_key),
        "commands": sorted(commands, key=_path_key),
    }


def pltr_version() -> str:
    from . import __version__

    return __version__


def sdk_version() -> str:
    """The foundry-platform-sdk version the ``pltr api`` tree was generated from.

    It comes from the generated spec index (the locked SDK version), so it
    doesn't change when a newer SDK patch release is installed.
    """
    from .commands.api import _runtime

    return _runtime.generated_sdk_version()


def _path_key(entry: Mapping[str, Any]) -> Tuple[str, ...]:
    return tuple(entry["path"].split())


def iter_groups(root: click.Command) -> Iterator[Tuple[str, click.Group]]:
    """Yield ``(path, group)`` for every group with subcommands, below the root.

    The path has no program name (``"dataset branches"``), as in
    :func:`pltr.contract.iter_commands`, and groups are walked the same way.
    """

    def walk(
        command: click.Command, ctx: click.Context, prefix: Tuple[str, ...]
    ) -> Iterator[Tuple[str, click.Group]]:
        if not isinstance(command, click.Group):
            return
        names = command.list_commands(ctx)
        if prefix and names:
            yield " ".join(prefix), command
        for name in names:
            sub = command.get_command(ctx, name)
            if sub is not None:
                sub_ctx = click.Context(sub, info_name=name, parent=ctx)
                yield from walk(sub, sub_ctx, prefix + (name,))

    yield from walk(root, click.Context(root, info_name=PROGRAM), ())


def group_entry(path: str, group: click.Group) -> Dict[str, Any]:
    """A group's entry: its path, one-line description and full help."""
    entry: Dict[str, Any] = {
        "path": f"{PROGRAM} {path}",
        "description": summary(group),
    }
    help_text = clean_help(group.help)
    if help_text:
        entry["help"] = help_text
    return entry


def command_entry(entry: CommandEntry) -> Dict[str, Any]:
    """One command's manifest entry (see the module docstring for the shape)."""
    command, meta = entry.command, entry.meta
    segments = entry.path.split()
    path = " ".join((PROGRAM, *segments))
    arguments = [
        argument_entry(command, param)
        for param in command.params
        if isinstance(param, click.Argument) and not getattr(param, "hidden", False)
    ]
    options = [
        option_entry(param)
        for param in command.params
        if isinstance(param, click.Option) and not param.hidden
    ]
    document: Dict[str, Any] = {
        "path": path,
        "usage": usage(path, arguments, options),
        "description": summary(command),
    }
    if meta is not None:
        document["beta"] = meta.beta
        document["destructive"] = meta.destructive
        document["paged"] = meta.paged
    document["generated"] = bool(segments) and segments[0] == "api"
    document["local"] = is_local(segments, meta)
    document["hidden"] = bool(command.hidden)
    formats = output_formats(command, meta)
    if formats is not None:
        document["outputFormats"] = formats
    if meta is not None:
        document["sdkMethods"] = list(meta.sdk)
        if meta.http:
            document["httpEndpoints"] = list(meta.http)
    document["arguments"] = arguments
    document["options"] = options
    document["help"] = clean_help(command.help)
    return document


def is_local(segments: Sequence[str], meta: Optional[CommandMeta]) -> bool:
    """Whether a command makes no Foundry call (see :data:`LOCAL_GROUPS`)."""
    if meta is not None:
        return not meta.sdk and not meta.http
    return bool(segments) and segments[0] in LOCAL_GROUPS


def output_formats(
    command: click.Command, meta: Optional[CommandMeta] = None
) -> Optional[List[str]]:
    """The formats a command prints its data in; ``None`` when unknown.

    ``["binary"]`` for commands that write raw bytes (``meta.binary``; their
    ``--format`` only shapes errors), the choices of a validated ``--format``
    option, ``[]`` for a command without ``--format`` (it prints text), and
    ``None`` for a free-text ``--format`` (a command not yet converted to the
    output contract).
    """
    if meta is not None and meta.binary:
        return [BINARY_FORMAT]
    option = next(
        (
            param
            for param in command.params
            if isinstance(param, click.Option) and "--format" in param.opts
        ),
        None,
    )
    if option is None:
        return []
    if isinstance(option.type, click.Choice):
        return [str(choice) for choice in option.type.choices]
    return None


def _argument_help(command: click.Command, param: click.Argument) -> str:
    text = getattr(param, "help", None)
    if not text:
        # Generated commands keep their arguments' help on the command.
        text = getattr(command, "argument_help", {}).get(param.name or "", "")
    return one_line(text)


def argument_entry(command: click.Command, param: click.Argument) -> Dict[str, Any]:
    """A positional argument: name, type, required, multiple, help, ..."""
    entry: Dict[str, Any] = {
        "name": param.name,
        "type": type_name(param),
        "required": bool(param.required),
        "multiple": param.nargs == -1 or bool(param.multiple),
    }
    _add_details(entry, param)
    help_text = _argument_help(command, param)
    if help_text:
        entry["help"] = help_text
    return entry


def option_entry(param: click.Option) -> Dict[str, Any]:
    """An option: name, flags, type, required, multiple, help, ..."""
    entry: Dict[str, Any] = {
        "name": param.name,
        "flags": [*param.opts, *param.secondary_opts],
        "type": type_name(param),
        "required": bool(param.required),
        "multiple": bool(param.multiple),
    }
    _add_details(entry, param)
    help_text = one_line(param.help)
    if help_text:
        entry["help"] = help_text
    return entry


def _add_details(entry: Dict[str, Any], param: click.Parameter) -> None:
    if isinstance(param.type, click.Choice):
        entry["choices"] = [str(choice) for choice in param.type.choices]
    default = default_value(param)
    if default is not None:
        entry["default"] = default
    if param.envvar:
        envvar = param.envvar
        entry["envvar"] = envvar if isinstance(envvar, str) else list(envvar)


#: Types of string options, by the metavar the shared and generated options use.
_METAVAR_TYPES = {
    "JSON": "json",
    "DATETIME": "datetime",
    "DATE": "date",
    "FILE": "path",
}


def type_name(param: click.Parameter) -> str:
    """The parameter's type: ``string``, ``integer``, ``number``, ``boolean``,
    ``flag`` (an option that takes no value), ``choice``, ``path``, ``json``,
    ``date``, ``datetime`` or ``uuid``."""
    if isinstance(param, click.Option) and param.is_flag:
        return "flag"
    kind = param.type
    if isinstance(kind, click.Choice):
        return "choice"
    if isinstance(kind, click.types.BoolParamType):
        return "boolean"
    if isinstance(kind, click.types.IntParamType):
        return "integer"
    if isinstance(kind, click.types.FloatParamType):
        return "number"
    if isinstance(kind, (click.Path, click.File)):
        return "path"
    if isinstance(kind, click.DateTime):
        return "datetime"
    if isinstance(kind, click.types.UUIDParameterType):
        return "uuid"
    return _METAVAR_TYPES.get(getattr(param, "metavar", None) or "", "string")


def default_value(param: click.Parameter) -> Any:
    """The parameter's default as JSON data, or None when there is none to show.

    Dynamic (callable) defaults, empty lists and the ``false`` of an
    off-by-default flag are left out.
    """
    value = param.default
    if value is None or callable(value):
        return None
    if isinstance(param, click.Option) and param.is_flag and value is False:
        return None
    if isinstance(value, (list, tuple)) and not value:
        return None
    return _jsonable(value)


def _jsonable(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        value = value.value
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


# ------------------------------------------------------------------- text

_USAGE_METAVARS = {
    "string": "TEXT",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "path": "PATH",
    "json": "JSON",
    "date": "DATE",
    "datetime": "DATETIME",
    "uuid": "UUID",
}


def long_flag(option: Mapping[str, Any]) -> str:
    """The option's first long flag (``--name``), else its first flag."""
    flags = option["flags"]
    return next((flag for flag in flags if flag.startswith("--")), flags[0])


def metavar(option: Mapping[str, Any]) -> str:
    """How an option's value is shown in usage lines: TEXT, JSON, A|B, ..."""
    if option["type"] == "choice":
        choices = option.get("choices", [])
        return "|".join(choices) if 0 < len(choices) <= 4 else "CHOICE"
    return _USAGE_METAVARS.get(option["type"], "VALUE")


def usage(
    path: str,
    arguments: Sequence[Mapping[str, Any]],
    options: Sequence[Mapping[str, Any]],
) -> str:
    """A usage line: the path, the arguments, the required options, [OPTIONS].

    For example ``pltr folder create NAME --parent-folder TEXT [OPTIONS]``.
    """
    parts = [path]
    for argument in arguments:
        token = str(argument["name"]).upper() + ("..." if argument["multiple"] else "")
        parts.append(token if argument["required"] else f"[{token}]")
    for option in options:
        if option["required"]:
            flag = long_flag(option)
            parts.append(
                flag if option["type"] == "flag" else f"{flag} {metavar(option)}"
            )
    if any(not option["required"] for option in options):
        parts.append("[OPTIONS]")
    return " ".join(parts)


def clean_help(text: Optional[str]) -> str:
    """Help text as a user reads it: no click markers, dedented, trimmed.

    Drops click's ``\\b`` (no-rewrap) marker lines and everything after the
    ``\\f`` truncation marker, and collapses runs of blank lines.
    """
    if not text:
        return ""
    text = inspect.cleandoc(text.split("\f", 1)[0])
    lines = [line.rstrip() for line in text.splitlines() if line.strip() != "\b"]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def one_line(text: Optional[str]) -> str:
    """Collapse whitespace (for option and argument help)."""
    return " ".join((text or "").split())


def summary(command: click.Command) -> str:
    """One-line description: the short help, else the help's first paragraph."""
    text = clean_help(command.short_help or command.help)
    return one_line(text.split("\n\n", 1)[0])


# ----------------------------------------------------------------- lookups


def normalize_path(words: Sequence[str]) -> Tuple[str, ...]:
    """Command path words from CLI arguments.

    Accepts separate words (``dataset get``), one quoted path
    (``"dataset get"``) and a leading program name (``"pltr dataset get"``).
    """
    tokens = " ".join(words).split()
    if tokens and tokens[0] == PROGRAM:
        tokens = tokens[1:]
    return tuple(tokens)


def find_command(
    manifest: Mapping[str, Any], words: Sequence[str]
) -> Optional[Dict[str, Any]]:
    """The command entry for a path (see :func:`normalize_path`), if any."""
    path = " ".join((PROGRAM, *normalize_path(words)))
    for entry in manifest["commands"]:
        if entry["path"] == path:
            return entry
    return None


def find_group(
    manifest: Mapping[str, Any], words: Sequence[str]
) -> Optional[Dict[str, Any]]:
    """The group entry for a path, if any."""
    path = " ".join((PROGRAM, *normalize_path(words)))
    for entry in manifest["groups"]:
        if entry["path"] == path:
            return entry
    return None


def filter_manifest(
    manifest: Mapping[str, Any], words: Sequence[str]
) -> Dict[str, Any]:
    """The manifest restricted to the groups and commands at or below a path."""
    prefix = normalize_path(words)

    def below(entry: Mapping[str, Any]) -> bool:
        return tuple(entry["path"].split()[1:])[: len(prefix)] == prefix

    return {
        **manifest,
        "groups": [entry for entry in manifest["groups"] if below(entry)],
        "commands": [entry for entry in manifest["commands"] if below(entry)],
    }


def suggest(manifest: Mapping[str, Any], path: str, limit: int = 3) -> List[str]:
    """Command or group paths close to a mistyped path, best first.

    Close spellings (``pltr dataset gett``) come first, then search results.
    """
    tokens = normalize_path([path])
    target = " ".join((PROGRAM, *tokens))
    paths = [entry["path"] for entry in (*manifest["groups"], *manifest["commands"])]
    found = difflib.get_close_matches(target, paths, n=limit, cutoff=0.75)
    for entry in search(manifest["commands"], " ".join(tokens)):
        if len(found) >= limit:
            break
        if entry["path"] not in found:
            found.append(entry["path"])
    return found


def summary_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    """The keys of a command entry that search results show."""
    return {key: entry[key] for key in SUMMARY_KEYS if key in entry}


# ------------------------------------------------------------------ search

#: Words that carry no meaning in a search (they match every help text).
STOP_WORDS: FrozenSet[str] = frozenset(
    "a an and are as at be by can do does for from how i in into is it its me "
    "my of on or that the this to use using what which with pltr".split()
)

#: Verbs agents use for what commands call something else (`run` -> `execute`).
SYNONYMS: Dict[str, Tuple[str, ...]] = {
    "run": ("execute", "start", "trigger", "submit"),
    "execute": ("run",),
    "start": ("create", "run"),
    "delete": ("remove", "trash"),
    "remove": ("delete", "revoke"),
    "revoke": ("remove",),
    "grant": ("add",),
    "show": ("get", "describe"),
    "get": ("show", "read", "fetch"),
    "fetch": ("get", "read"),
    "read": ("get", "content"),
    "download": ("content", "read", "get"),
    "upload": ("put", "write"),
    "find": ("search", "lookup"),
    "search": ("find",),
    "lookup": ("get", "search"),
    "create": ("add", "new"),
    "add": ("create",),
    "new": ("create",),
    "update": ("replace", "edit", "set", "modify"),
    "edit": ("update", "replace"),
    "change": ("update", "replace"),
    "stop": ("cancel", "abort", "pause"),
    "kill": ("cancel", "abort"),
    "permission": ("role", "grant"),
    "access": ("role", "permission"),
}

#: How much a query word counts when it matches a word of each field.
FIELD_WEIGHTS: Dict[str, float] = {
    "path": 10.0,  # the command's own words: `dataset branches list`
    "sdk": 6.0,  # SDK method paths: datasets.Dataset.Branch.list
    "http": 6.0,  # direct-HTTP endpoints of the labeled exceptions
    "description": 4.0,
    "parameters": 2.0,  # argument names and option flags
    "help": 1.0,
}

#: Curated commands are the polished path, so their word matches count more
#: than a generated command's: they rank first when both match as well.
CURATED_BOOST = 1.25
#: The query names the command's path (in any order: `list dataset branches`).
EXACT_PATH_BONUS = 30.0
#: The query names the end of the path (`dataset get` for `api datasets dataset get`).
PATH_END_BONUS = 12.0
#: Every query word is a word of the command's path.
PATH_BONUS = 6.0
#: The query is the command's SDK method (`datasets.Dataset.Branch.list`) ...
EXACT_SDK_BONUS = 30.0
#: ... or part of it (`Dataset.Branch.list`).
SDK_SUBSTRING_BONUS = 6.0

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_WORD = re.compile(r"[a-z0-9]+")


def words(text: str) -> List[str]:
    """Lower-case words, splitting camelCase, snake_case, kebab-case and dots."""
    return _WORD.findall(_CAMEL_BOUNDARY.sub(" ", text).lower())


def _stem(word: str) -> str:
    """A crude singular form, so `datasets` matches `dataset`."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ches", "shes", "sses", "xes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


class _Term:
    """A query word with its singular form and synonyms."""

    __slots__ = ("word", "stem", "synonyms")

    def __init__(self, word: str) -> None:
        self.word = word
        self.stem = _stem(word)
        self.synonyms = SYNONYMS.get(word, SYNONYMS.get(self.stem, ()))


class _Field:
    __slots__ = ("words", "stems")

    def __init__(self, items: Sequence[str]) -> None:
        self.words: Set[str] = set(items)
        self.stems: Set[str] = {_stem(word) for word in items}

    def match(self, term: _Term) -> float:
        """How well a query word matches this field: 1 (exact) down to 0."""
        if term.word in self.words:
            return 1.0
        if term.stem in self.stems:
            return 0.9
        if any(synonym in self.stems for synonym in term.synonyms):
            return 0.8
        if len(term.word) >= 3 and any(w.startswith(term.word) for w in self.words):
            return 0.6
        if len(term.word) >= 4 and any(term.word in w for w in self.words):
            return 0.3
        return 0.0


def _key_words(items: Sequence[str]) -> List[str]:
    """Stems of the words that aren't stop words (for path matching)."""
    return [_stem(word) for word in items if word not in STOP_WORDS]


class _Indexed:
    __slots__ = ("entry", "path_words", "path_key", "fields", "sdk_paths")

    def __init__(self, entry: Mapping[str, Any]) -> None:
        self.entry = entry
        self.path_words = words(entry["path"])[1:]  # without "pltr"
        self.path_key = _key_words(self.path_words)
        parameters: List[str] = []
        for argument in entry.get("arguments", []):
            parameters += words(argument["name"])
        for option in entry.get("options", []):
            for flag in option["flags"]:
                parameters += words(flag)
        sdk_methods = entry.get("sdkMethods", [])
        endpoints = entry.get("httpEndpoints", [])
        self.sdk_paths = [path.lower() for path in sdk_methods]
        self.fields = {
            "path": _Field(self.path_words),
            "sdk": _Field([word for path in sdk_methods for word in words(path)]),
            "http": _Field([word for path in endpoints for word in words(path)]),
            "description": _Field(words(entry.get("description", ""))),
            "parameters": _Field(parameters),
            "help": _Field(words(entry.get("help", ""))),
        }


_CLIENT_PREFIX = re.compile(r"^\s*foundryclient\.", re.IGNORECASE)


def query_terms(query: str) -> List[str]:
    """The query's words without stop words (all words if only stop words).

    A leading ``FoundryClient.`` (an SDK method path) is dropped.
    """
    all_words = words(_CLIENT_PREFIX.sub("", query))
    terms = [word for word in all_words if word not in STOP_WORDS]
    return terms or [word for word in all_words if word != PROGRAM]


def _sdk_query(raw: str) -> Optional[str]:
    """The query as an SDK method path (`Dataset.Branch.list`), if it is one."""
    text = _CLIENT_PREFIX.sub("", raw).strip().lower()
    return text if re.fullmatch(r"[a-z_]\w*(\.[a-z_]\w*)+", text) else None


def score(entry: Mapping[str, Any], query: str) -> float:
    """How well a command matches a query (0: not at all); see :func:`search`."""
    return _score(_Indexed(entry), [_Term(t) for t in query_terms(query)], query)


def _score(item: _Indexed, terms: Sequence[_Term], raw: str) -> float:
    matched = 0
    total = 0.0
    for term in terms:
        best = max(
            FIELD_WEIGHTS[name] * field.match(term)
            for name, field in item.fields.items()
        )
        if best > 0:
            matched += 1
            total += best
    if not matched:
        return 0.0
    # Words the command doesn't match at all lower its score.
    total *= 0.5 + 0.5 * matched / len(terms)
    if not item.entry.get("generated"):
        total *= CURATED_BOOST
    key = set(_key_words([term.word for term in terms]))
    path = item.path_key
    if key and key == set(path):
        total += EXACT_PATH_BONUS
    elif len(key) > 1 and key == set(path[-len(key) :]):
        total += PATH_END_BONUS
    elif len(key) > 1 and key <= set(path):
        total += PATH_BONUS
    sdk_query = _sdk_query(raw)
    if sdk_query:
        if sdk_query in item.sdk_paths:
            total += EXACT_SDK_BONUS
        elif any(sdk_query in path for path in item.sdk_paths):
            total += SDK_SUBSTRING_BONUS
    return total


def search(
    commands: Sequence[Mapping[str, Any]],
    query: str,
    *,
    include_hidden: bool = False,
) -> List[Mapping[str, Any]]:
    """Rank commands for a free-text query; returns every match, best first.

    Each query word is matched against the command's path, SDK methods,
    direct-HTTP endpoints, description, parameter names and help, in
    decreasing weight, allowing plurals, a few verb synonyms (`run` finds
    `execute`) and prefixes. A command scores the sum of its best match per
    word, less for words it doesn't match at all, and more for curated
    commands than for generated `pltr api` ones. The query naming the
    command's path, the end of its path (in any order) or its SDK method
    (`Dataset.Branch.list`) adds a bonus. Ties go to curated commands, then
    the shorter path. Hidden commands are left out unless ``include_hidden``.
    """
    terms = [_Term(word) for word in query_terms(query)]
    if not terms:
        return []
    ranked = []
    for entry in commands:
        if entry.get("hidden") and not include_hidden:
            continue
        item = _Indexed(entry)
        relevance = _score(item, terms, query)
        if relevance > 0:
            key = (
                -round(relevance, 6),
                bool(entry.get("generated")),
                len(item.path_words),
                entry["path"],
            )
            ranked.append((key, entry))
    ranked.sort(key=lambda pair: pair[0])
    return [entry for _, entry in ranked]
