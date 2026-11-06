"""Check every foundry-platform-sdk call in pltr against the real SDK (issue #185).

pltr's service tests used to mock the SDK with bare ``Mock()`` objects, which accept any
attribute and any argument. This module is the static guardrail that catches what those
mocks hide. It parses ``src/pltr/services/*.py`` and ``src/pltr/commands/*.py`` and, for
every SDK call:

* resolves the call target (``self.service...``, ``self.client...``, service properties,
  simple local aliases, composed services such as ``self.dataset_service.service...``)
  against a real ``FoundryClient`` built with a dummy token and hostname (no network);
* binds the call's arguments to the real signature with ``inspect.Signature.bind``;
* applies the preview rules: GA methods never get ``preview``; beta methods (those with a
  ``preview`` parameter) always get the literal ``preview=True``.

It also reports direct HTTP calls (``requests``, ``httpx``, ``urllib``,
``BaseService._make_request``) outside the labeled exceptions.

``tests/test_sdk_call_guardrail.py`` runs the check against the ratchet allowlist
``tests/sdk_call_allowlist.txt``; ``scripts/check_sdk_calls.py`` is the command-line
front end. Other tooling can call :func:`collect_sdk_calls` to get one structured
:class:`SdkCall` record per call site. See ``docs/development/sdk-guardrail.md``.

Known limits: values that flow through function parameters, containers or ``**kwargs``
can't be followed, and nothing here checks how responses are used (formatters reading
fields that don't exist). Tests with the ``stub_foundry_http`` fixture cover those.
"""

from __future__ import annotations

import ast
import difflib
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PLTR_SRC = REPO_ROOT / "src" / "pltr"
DEFAULT_ALLOWLIST = REPO_ROOT / "tests" / "sdk_call_allowlist.txt"

#: Sub-packages of ``src/pltr`` that are scanned.
SCANNED_PACKAGES: Tuple[str, ...] = ("services", "commands")

#: Rule code -> one-line explanation. Rule codes are part of the allowlist keys.
RULES: Dict[str, str] = {
    "missing-method": "the SDK has no such namespace, resource or method",
    "unknown-keyword": "a keyword argument the SDK method doesn't accept",
    "too-many-positional": (
        "more positional arguments than the method takes "
        "(usually a keyword-only argument passed positionally)"
    ),
    "missing-required": "a required argument isn't passed",
    "duplicate-argument": "the same parameter is passed twice",
    "bad-arguments": "the arguments don't bind to the signature",
    "preview-on-ga": "preview is passed to a GA method (one without a preview parameter)",
    "beta-without-preview": "a beta method (one with a preview parameter) is called without preview=True",
    "beta-preview-not-literal": "a beta method gets preview=<anything but the literal True>",
    "unchecked-kwargs": "arguments go through **kwargs or *args, so the call can't be checked",
    "uncheckable": "the SDK call target can't be resolved statically",
    "direct-http": "a direct HTTP call outside the labeled exceptions",
}

#: The labeled direct-HTTP exceptions from the roadmap (#181): the only functions
#: allowed to call Foundry endpoints without the SDK. Keys are ``<file>::<Class.method>``.
#: No new exceptions get added; this list can only shrink.
LABELED_HTTP_EXCEPTIONS: Dict[str, str] = {
    "services/base.py::BaseService._make_request": (
        "shared helper used by the labeled exceptions below"
    ),
    "services/dataset.py::DatasetService.apply_schema": "dataset schema apply",
    "services/ontology.py::ObjectTypeService._create_schema_entity": (
        "ontology object-type-create / link-type-create fallback"
    ),
    "services/language_models.py::LanguageModelsService.list_available_models": (
        "language-models list"
    ),
    "services/language_models.py::LanguageModelsService.get_model_enrollment_status": (
        "language-models status"
    ),
    "services/language_models.py::LanguageModelsService.enroll_model": (
        "language-models enroll"
    ),
}

#: Name of the BaseService helper that makes raw HTTP requests.
MAKE_REQUEST = "BaseService._make_request"

_HTTP_LIBRARIES = frozenset({"requests", "httpx", "urllib", "http", "aiohttp"})
_HTTP_VERBS = ("request", "get", "options", "head", "post", "put", "patch", "delete")
#: Calls that make (or set up) an HTTP request, by dotted name.
_HTTP_CALLS = frozenset(
    [f"requests.{name}" for name in _HTTP_VERBS + ("Session", "session")]
    + [f"httpx.{name}" for name in _HTTP_VERBS + ("stream", "Client", "AsyncClient")]
    + [
        "urllib.request.urlopen",
        "http.client.HTTPConnection",
        "http.client.HTTPSConnection",
        "aiohttp.request",
        "aiohttp.ClientSession",
        MAKE_REQUEST,
    ]
)

# Parameters every SDK method has; left out of signatures in messages.
_NOISE_PARAMETERS = frozenset({"request_timeout", "_sdk_internal"})
_PLACEHOLDER = object()

FunctionNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]
# Where a record comes from: (file, class name, method, call or reference node).
_Context = Tuple[str, Optional[str], str, ast.expr]


# --------------------------------------------------------------------------- records


@dataclass(frozen=True)
class Violation:
    """One broken rule at one call site."""

    rule: str
    message: str
    #: The argument a rule is about (``unknown-keyword``, ``missing-required``, ...).
    subject: Optional[str] = None

    @property
    def rule_id(self) -> str:
        """Rule code as used in allowlist keys, e.g. ``unknown-keyword(query)``."""
        return f"{self.rule}({self.subject})" if self.subject else self.rule


@dataclass
class SdkCall:
    """One SDK call (``kind == "sdk"``) or direct HTTP call (``kind == "http"``) in pltr."""

    #: Path relative to ``src/pltr``, POSIX style, e.g. ``services/folder.py``.
    file: str
    #: Class the call is in (``None`` for module-level functions).
    class_name: Optional[str]
    #: Method or function the call is in (nested functions count as their outer one).
    method: str
    line: int
    col: int
    #: SDK path from ``FoundryClient``, e.g. ``filesystem.Folder.get``. For direct HTTP,
    #: the function called, e.g. ``requests.get`` or ``BaseService._make_request``.
    sdk_path: str
    kind: str
    #: Whether ``sdk_path`` exists in the installed SDK (always ``False`` for HTTP).
    resolved: bool
    #: Whether the SDK method is beta (takes ``preview``); ``None`` if unresolved/HTTP.
    beta: Optional[bool]
    #: For direct HTTP in a labeled exception: the command(s) it serves.
    http_label: Optional[str] = None
    #: Compact form of the SDK signature, when resolved.
    signature: Optional[str] = None
    violations: List[Violation] = field(default_factory=list)

    @property
    def function(self) -> str:
        """``Class.method`` (or ``function`` for module-level code)."""
        return f"{self.class_name}.{self.method}" if self.class_name else self.method

    @property
    def location(self) -> str:
        """``src/pltr/<file>:<line>``."""
        return f"src/pltr/{self.file}:{self.line}"

    def to_dict(self) -> Dict[str, Any]:
        """JSON-friendly form."""
        return {
            "file": self.file,
            "class": self.class_name,
            "method": self.method,
            "line": self.line,
            "kind": self.kind,
            "sdkPath": self.sdk_path,
            "resolved": self.resolved,
            "beta": self.beta,
            "httpLabel": self.http_label,
            "signature": self.signature,
            "violations": [
                {"rule": v.rule_id, "message": v.message} for v in self.violations
            ],
        }


@dataclass(frozen=True)
class Finding:
    """A violation with its stable allowlist key."""

    key: str
    call: SdkCall
    violation: Violation


# ------------------------------------------------------------------- symbolic values


@dataclass(frozen=True)
class _SdkRef:
    """An SDK object reached from ``FoundryClient`` through ``path``."""

    path: Tuple[str, ...]
    #: Length of the prefix looked up with ``getattr(obj, "name", default)``. Code
    #: handles that prefix being absent, so a candidate whose optional prefix doesn't
    #: exist is dropped when another candidate exists.
    optional: int = 0


@dataclass(frozen=True)
class _UncheckableRef:
    """An SDK object the checker can't pin down (dynamic attribute, unresolved root)."""

    path: Tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class _ServiceInstance:
    """An instance of a pltr service class (``self`` or a composed service)."""

    cls: str


@dataclass(frozen=True)
class _ServiceClass:
    """A pltr service class itself (calling it makes an instance)."""

    cls: str


@dataclass(frozen=True)
class _HttpRef:
    """An HTTP library module/function (``requests``, ``requests.get``, ...)."""

    name: str


_Value = Union[_SdkRef, _UncheckableRef, _ServiceInstance, _ServiceClass, _HttpRef]


def _dedupe(values: Iterable[_Value]) -> List[_Value]:
    seen: Set[_Value] = set()
    out: List[_Value] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


# ------------------------------------------------------------------- source modules


@dataclass
class _ClassInfo:
    name: str
    module: "_ModuleInfo"
    bases: Tuple[str, ...]
    methods: Dict[str, FunctionNode]
    properties: Set[str]
    #: ``self.<attr> = <expr>`` assignments: attr -> [(function, expr)].
    self_assignments: Dict[str, List[Tuple[FunctionNode, ast.expr]]]


@dataclass
class _ModuleInfo:
    file: str
    tree: ast.Module
    #: Module-level names bound to HTTP libraries: local name -> dotted name.
    imports: Dict[str, str]
    classes: Dict[str, _ClassInfo]
    functions: Dict[str, FunctionNode] = field(default_factory=dict)


def _http_import_bindings(node: Union[ast.Import, ast.ImportFrom]) -> Dict[str, str]:
    """Names an import statement binds to HTTP libraries (local name -> dotted name)."""
    out: Dict[str, str] = {}
    if isinstance(node, ast.Import):
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in _HTTP_LIBRARIES:
                if alias.asname:
                    out[alias.asname] = alias.name
                else:
                    out[top] = top
    elif node.module and node.level == 0:
        if node.module.split(".")[0] in _HTTP_LIBRARIES:
            for alias in node.names:
                out[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return out


def _decorator_names(func: FunctionNode) -> Set[str]:
    names: Set[str] = set()
    for decorator in func.decorator_list:
        if isinstance(decorator, ast.Name):
            names.add(decorator.id)
        elif isinstance(decorator, ast.Attribute):
            names.add(decorator.attr)
    return names


def _parse_module(file: str, source: str) -> _ModuleInfo:
    tree = ast.parse(source, filename=file)
    module = _ModuleInfo(file=file, tree=tree, imports={}, classes={})
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module.imports.update(_http_import_bindings(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            module.functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            info = _ClassInfo(
                name=node.name,
                module=module,
                bases=tuple(
                    base.id if isinstance(base, ast.Name) else ast.unparse(base)
                    for base in node.bases
                ),
                methods={},
                properties=set(),
                self_assignments={},
            )
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    info.methods[item.name] = item
                    if _decorator_names(item) & {"property", "cached_property"}:
                        info.properties.add(item.name)
                    for sub in ast.walk(item):
                        if isinstance(sub, (ast.Assign, ast.AnnAssign)) and sub.value:
                            targets = (
                                sub.targets
                                if isinstance(sub, ast.Assign)
                                else [sub.target]
                            )
                            for target in targets:
                                if (
                                    isinstance(target, ast.Attribute)
                                    and isinstance(target.value, ast.Name)
                                    and target.value.id == "self"
                                ):
                                    info.self_assignments.setdefault(
                                        target.attr, []
                                    ).append((item, sub.value))
            module.classes[node.name] = info
    return module


# ------------------------------------------------------------------------ analysis


def _target_names(target: ast.expr) -> List[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for elt in target.elts for name in _target_names(elt)]
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    return []


class _Scope:
    """Local names of one function (nested functions included, flow-insensitive)."""

    def __init__(
        self,
        analyzer: "_Analyzer",
        module: _ModuleInfo,
        self_cls: Optional[str],
        body: Sequence[ast.AST],
    ) -> None:
        self.analyzer = analyzer
        self.module = module
        self.self_cls = self_cls
        # name -> assigned expressions; None marks an assignment we can't follow.
        self.assignments: Dict[str, List[Optional[ast.expr]]] = {}
        self.imports: Dict[str, str] = {}
        self._cache: Dict[str, List[_Value]] = {}
        self._resolving: Set[str] = set()
        for node in body:
            for sub in ast.walk(node):
                self._collect(sub)

    def _bind(self, name: str, value: Optional[ast.expr]) -> None:
        self.assignments.setdefault(name, []).append(value)

    def _collect(self, node: ast.AST) -> None:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._bind(target.id, node.value)
                else:
                    for name in _target_names(target):
                        self._bind(name, None)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            self._bind(node.target.id, node.value)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            self._bind(node.target.id, None)
        elif isinstance(node, ast.NamedExpr):
            self._bind(node.target.id, node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            for name in _target_names(node.target):
                self._bind(name, None)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            for name in _target_names(node.optional_vars):
                self._bind(name, None)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            self._bind(node.name, None)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            self.imports.update(_http_import_bindings(node))

    def local(self, name: str) -> List[_Value]:
        if name in self._cache:
            return self._cache[name]
        if name in self._resolving:
            return []
        self._resolving.add(name)
        values: List[_Value] = []
        for expr in self.assignments[name]:
            if expr is not None:
                values.extend(self.eval(expr))
        self._resolving.discard(name)
        result = _dedupe(values)
        self._cache[name] = result
        return result

    def eval(self, node: ast.AST) -> List[_Value]:
        """Symbolic value(s) of an expression; [] when it isn't SDK/HTTP related."""
        if isinstance(node, ast.Name):
            name = node.id
            if name == "self" and self.self_cls:
                return [_ServiceInstance(self.self_cls)]
            if name in self.assignments:
                return self.local(name)
            if name in self.imports:
                return [_HttpRef(self.imports[name])]
            if name in self.module.imports:
                return [_HttpRef(self.module.imports[name])]
            if name in self.analyzer.classes:
                return [_ServiceClass(name)]
            return []
        if isinstance(node, ast.Attribute):
            out: List[_Value] = []
            for base in self.eval(node.value):
                out.extend(self.analyzer.attribute(base, node.attr))
            return _dedupe(out)
        if isinstance(node, ast.Call):
            return self.analyzer.call_result(node, self)
        if isinstance(node, ast.IfExp):
            return _dedupe(self.eval(node.body) + self.eval(node.orelse))
        if isinstance(node, ast.BoolOp):
            return _dedupe(v for operand in node.values for v in self.eval(operand))
        if isinstance(node, ast.NamedExpr):
            return self.eval(node.value)
        return []


#: Builtins that only inspect an object; passing an SDK object to them is fine.
_PROBES = frozenset(
    {
        "getattr",
        "hasattr",
        "isinstance",
        "issubclass",
        "callable",
        "type",
        "id",
        "repr",
        "str",
        "bool",
        "print",
    }
)


def _is_probe(func: ast.expr) -> bool:
    if isinstance(func, ast.Name):
        return func.id in _PROBES
    # inspect.signature(...), inspect.isclass(...), ...
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "inspect"
    )


def _escape(node: ast.expr, parents: Mapping[ast.AST, ast.AST]) -> Optional[str]:
    """Where an expression's value goes, if that hides a call from the checker.

    Calls, aliases (``x = self.service.Folder``), attribute storage (``self.x = ...``),
    returns, truthiness/``is None`` tests and probes (``hasattr``, ``inspect.signature``)
    are followed or harmless; passing an SDK object to other code isn't.
    """
    child: ast.AST = node
    parent = parents.get(child)
    # Values flow through `a or b`, `a if c else b`, `(x := a)` and `*a`.
    while isinstance(parent, (ast.BoolOp, ast.NamedExpr, ast.Starred)) or (
        isinstance(parent, ast.IfExp) and child is not parent.test
    ):
        child, parent = parent, parents.get(parent)
    if isinstance(parent, ast.keyword):
        parent = parents.get(parent)
        child = node
    if isinstance(parent, ast.Call):
        if parent.func is child or _is_probe(parent.func):
            return None
        return f"is passed to {ast.unparse(parent.func)}()"
    if isinstance(parent, (ast.Assign, ast.AnnAssign)):
        targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
        simple = all(
            isinstance(t, ast.Name)
            or (
                isinstance(t, ast.Attribute)
                and isinstance(t.value, ast.Name)
                and t.value.id == "self"
            )
            for t in targets
        )
        return (
            None
            if simple
            else f"is stored in {', '.join(ast.unparse(t) for t in targets)}"
        )
    if isinstance(parent, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return "is put in a container"
    if isinstance(parent, ast.Lambda):
        return "is returned from a lambda"
    if isinstance(parent, (ast.Yield, ast.YieldFrom)):
        return "is yielded"
    return None


def _format_signature(sig: inspect.Signature) -> str:
    parts: List[str] = []
    star_done = False
    for param in sig.parameters.values():
        if param.name in _NOISE_PARAMETERS:
            continue
        if param.kind is param.VAR_POSITIONAL:
            parts.append(f"*{param.name}")
            star_done = True
            continue
        if param.kind is param.VAR_KEYWORD:
            parts.append(f"**{param.name}")
            continue
        if param.kind is param.KEYWORD_ONLY and not star_done:
            parts.append("*")
            star_done = True
        if param.default is param.empty:
            parts.append(param.name)
        else:
            parts.append(f"{param.name}={param.default!r}")
    return f"({', '.join(parts)})"


def _public_names(obj: Any) -> List[str]:
    return sorted(
        name
        for name in dir(obj)
        if not name.startswith("_")
        and name not in ("with_raw_response", "with_streaming_response")
    )


class _Analyzer:
    def __init__(
        self,
        modules: Sequence[_ModuleInfo],
        client: Any,
        labeled_http: Mapping[str, str],
    ) -> None:
        self.modules = list(modules)
        self.classes: Dict[str, _ClassInfo] = {}
        for module in self.modules:
            self.classes.update(module.classes)
        self.client = client
        self.labeled_http = dict(labeled_http)
        self._memo: Dict[Tuple[str, ...], List[_Value]] = {}
        self._in_progress: Set[Tuple[str, ...]] = set()
        self._scopes: Dict[Tuple[int, Optional[str]], _Scope] = {}
        self._resolved: Dict[Tuple[str, ...], Tuple[Any, Optional[str]]] = {}

    # ---------------------------------------------------------------- classes

    def mro(self, cls: str) -> List[_ClassInfo]:
        out: List[_ClassInfo] = []
        stack = [cls]
        seen: Set[str] = set()
        while stack:
            name = stack.pop(0)
            if name in seen or name not in self.classes:
                continue
            seen.add(name)
            info = self.classes[name]
            out.append(info)
            stack.extend(info.bases)
        return out

    def is_service(self, cls: str) -> bool:
        """Whether ``cls`` is (or derives from) ``BaseService``."""
        stack = [cls]
        seen: Set[str] = set()
        while stack:
            name = stack.pop()
            if name == "BaseService":
                return True
            if name in seen or name not in self.classes:
                continue
            seen.add(name)
            stack.extend(self.classes[name].bases)
        return False

    def find_method(
        self, cls: str, name: str
    ) -> Optional[Tuple[_ClassInfo, FunctionNode]]:
        for info in self.mro(cls):
            if name in info.methods:
                return info, info.methods[name]
        return None

    def scope(
        self, module: _ModuleInfo, self_cls: Optional[str], func: FunctionNode
    ) -> _Scope:
        key = (id(func), self_cls)
        if key not in self._scopes:
            self._scopes[key] = _Scope(self, module, self_cls, [func])
        return self._scopes[key]

    def _memoized(self, key: Tuple[str, ...], compute: Any) -> List[_Value]:
        if key in self._memo:
            return self._memo[key]
        if key in self._in_progress:
            return []
        self._in_progress.add(key)
        try:
            values = _dedupe(compute())
        finally:
            self._in_progress.discard(key)
        self._memo[key] = values
        return values

    def _return_values(
        self, module: _ModuleInfo, func: FunctionNode, self_cls: Optional[str]
    ) -> List[_Value]:
        scope = self.scope(module, self_cls, func)
        values: List[_Value] = []
        stack: List[ast.AST] = list(func.body)
        while stack:
            node = stack.pop()
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
            ):
                continue
            if isinstance(node, ast.Return) and node.value is not None:
                values.extend(scope.eval(node.value))
            stack.extend(ast.iter_child_nodes(node))
        return values

    def service_root(self, cls: str) -> List[_Value]:
        """What ``self.service`` / ``self._get_service()`` is for a service class."""

        def compute() -> List[_Value]:
            found = self.find_method(cls, "_get_service")
            values: List[_Value] = []
            if found is not None:
                values = [
                    v
                    for v in self._return_values(found[0].module, found[1], cls)
                    if isinstance(v, (_SdkRef, _UncheckableRef))
                ]
            if not values:
                values = [
                    _UncheckableRef(
                        ("<service>",),
                        f"{cls}._get_service() can't be resolved statically",
                    )
                ]
            return values

        return self._memoized(("service", cls), compute)

    def property_values(self, cls: str, prop: str) -> List[_Value]:
        found = self.find_method(cls, prop)
        if found is None:
            return []
        owner, func = found
        return self._memoized(
            ("property", cls, prop),
            lambda: self._return_values(owner.module, func, cls),
        )

    def method_returns(self, cls: str, name: str) -> List[_Value]:
        """SDK objects a method returns (accessors like ``_get_service``)."""
        found = self.find_method(cls, name)
        if found is None:
            return []
        owner, func = found
        return self._memoized(
            ("method", cls, name),
            lambda: [
                v
                for v in self._return_values(owner.module, func, cls)
                if isinstance(v, (_SdkRef, _UncheckableRef))
            ],
        )

    def function_returns(self, module: _ModuleInfo, name: str) -> List[_Value]:
        """SDK objects a module-level function returns."""
        func = module.functions[name]
        return self._memoized(
            ("function", module.file, name),
            lambda: [
                v
                for v in self._return_values(module, func, None)
                if isinstance(v, (_SdkRef, _UncheckableRef))
            ],
        )

    def instance_attribute(self, cls: str, attr: str) -> List[_Value]:
        """Values assigned to ``self.<attr>`` anywhere in the class hierarchy."""

        def compute() -> List[_Value]:
            values: List[_Value] = []
            for info in self.mro(cls):
                for func, expr in info.self_assignments.get(attr, []):
                    values.extend(self.scope(info.module, cls, func).eval(expr))
            return values

        return self._memoized(("attribute", cls, attr), compute)

    # ------------------------------------------------------------ evaluation

    def attribute(self, base: _Value, name: str) -> List[_Value]:
        if isinstance(base, _SdkRef):
            return [_SdkRef(base.path + (name,), base.optional)]
        if isinstance(base, _UncheckableRef):
            return [_UncheckableRef(base.path + (name,), base.reason)]
        if isinstance(base, _HttpRef):
            return [_HttpRef(f"{base.name}.{name}")]
        if isinstance(base, _ServiceInstance):
            cls = base.cls
            if self.is_service(cls):
                if name == "client":
                    return [_SdkRef(())]
                if name == "_make_request":
                    return [_HttpRef(MAKE_REQUEST)]
                if name == "service":
                    found = self.find_method(cls, "service")
                    if found is None or found[0].name == "BaseService":
                        return self.service_root(cls)
            for info in self.mro(cls):
                if name in info.properties:
                    return self.property_values(cls, name)
                if name in info.methods:
                    return []
            return self.instance_attribute(cls, name)
        return []

    def call_result(self, node: ast.Call, scope: _Scope) -> List[_Value]:
        """Value of a call *expression* (not the call record): getattr, constructors..."""
        func = node.func
        if (
            isinstance(func, ast.Name)
            and func.id == "getattr"
            and len(node.args) >= 2
            and not node.keywords
        ):
            bases = scope.eval(node.args[0])
            name_node = node.args[1]
            if isinstance(name_node, ast.Constant) and isinstance(name_node.value, str):
                out: List[_Value] = []
                for base in bases:
                    for value in self.attribute(base, name_node.value):
                        if len(node.args) >= 3 and isinstance(value, _SdkRef):
                            value = _SdkRef(value.path, len(value.path))
                        out.append(value)
                return out
            return [
                _UncheckableRef(
                    base.path + ("<dynamic>",),
                    f"attribute name is computed at runtime: getattr(..., {ast.unparse(name_node)})",
                )
                for base in bases
                if isinstance(base, (_SdkRef, _UncheckableRef))
            ]
        out = []
        for value in scope.eval(func):
            if isinstance(value, _ServiceClass):
                out.append(_ServiceInstance(value.cls))
        if isinstance(func, ast.Attribute):
            # self._get_service(), or another accessor method returning an SDK object.
            for base in scope.eval(func.value):
                if isinstance(base, _ServiceInstance):
                    if func.attr == "_get_service":
                        out.extend(self.service_root(base.cls))
                    else:
                        out.extend(self.method_returns(base.cls, func.attr))
        elif (
            isinstance(func, ast.Name)
            and func.id in scope.module.functions
            and func.id not in scope.assignments
        ):
            out.extend(self.function_returns(scope.module, func.id))
        return out

    # ------------------------------------------------------------ resolution

    def resolve(self, path: Tuple[str, ...]) -> Tuple[Any, Optional[str]]:
        """Follow ``path`` from the client: (object, None) or (None, error message)."""
        if path in self._resolved:
            return self._resolved[path]
        obj = self.client
        result: Tuple[Any, Optional[str]] = (obj, None)
        for index, segment in enumerate(path):
            try:
                obj = getattr(obj, segment)
            except Exception:  # AttributeError, or a lazy import failing
                owner = ".".join(path[:index]) or "FoundryClient"
                names = _public_names(obj)
                close = difflib.get_close_matches(segment, names, n=3)
                message = f"{owner} has no attribute {segment!r}"
                if close:
                    message += f" (closest: {', '.join(close)})"
                elif names:
                    shown = ", ".join(names[:15])
                    message += f" (it has: {shown}{', ...' if len(names) > 15 else ''})"
                result = (None, message)
                break
        else:
            result = (obj, None)
        self._resolved[path] = result
        return result

    # --------------------------------------------------------------- records

    def records(self) -> List[SdkCall]:
        out: List[SdkCall] = []
        for module in self.modules:
            # Module-level statements (outside functions and classes).
            top = [
                node
                for node in module.tree.body
                if not isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                )
            ]
            if top:
                scope = _Scope(self, module, None, top)
                for node in top:
                    out.extend(
                        self._records_in(node, scope, module.file, None, "<module>")
                    )
            for node in module.tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scope = self.scope(module, None, node)
                    out.extend(
                        self._records_in(node, scope, module.file, None, node.name)
                    )
                elif isinstance(node, ast.ClassDef):
                    info = module.classes[node.name]
                    for name, func in info.methods.items():
                        self_cls = (
                            None
                            if "staticmethod" in _decorator_names(func)
                            else info.name
                        )
                        scope = self.scope(module, self_cls, func)
                        out.extend(
                            self._records_in(func, scope, module.file, info.name, name)
                        )
        out.sort(key=lambda r: (r.file, r.line, r.col, r.sdk_path))
        return out

    def _records_in(
        self,
        root: ast.AST,
        scope: _Scope,
        file: str,
        class_name: Optional[str],
        method: str,
    ) -> List[SdkCall]:
        out: List[SdkCall] = []
        parents: Dict[ast.AST, ast.AST] = {}
        for node in ast.walk(root):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(root):
            if isinstance(node, ast.Call):
                values = scope.eval(node.func)
                context = (file, class_name, method, node)
                sdk_refs = [v for v in values if isinstance(v, _SdkRef)]
                for ref in self._viable_candidates(sdk_refs):
                    out.append(self._sdk_record(ref, context))
                for value in values:
                    if isinstance(value, _UncheckableRef):
                        out.append(
                            self._uncheckable_record(value, value.reason, context)
                        )
                    elif isinstance(value, _HttpRef) and value.name in _HTTP_CALLS:
                        out.append(self._http_record(value.name, context))
            elif isinstance(node, (ast.Name, ast.Attribute)) and isinstance(
                node.ctx, ast.Load
            ):
                parent = parents.get(node)
                if isinstance(parent, ast.Attribute) or (
                    isinstance(parent, ast.Call) and parent.func is node
                ):
                    continue  # part of a longer chain, or a call (checked above)
                escape = _escape(node, parents)
                if escape is None:
                    continue
                values = scope.eval(node)
                refs: List[Union[_SdkRef, _UncheckableRef]] = list(
                    self._viable_candidates(
                        [v for v in values if isinstance(v, _SdkRef)]
                    )
                )
                refs.extend(v for v in values if isinstance(v, _UncheckableRef))
                message = (
                    f"SDK object {escape}, so the call that uses it can't be "
                    "checked; call the SDK method directly with explicit arguments"
                )
                for escaped in refs:
                    out.append(
                        self._uncheckable_record(
                            escaped, message, (file, class_name, method, node)
                        )
                    )
        return out

    def _uncheckable_record(
        self,
        ref: Union[_SdkRef, _UncheckableRef],
        message: str,
        context: _Context,
    ) -> SdkCall:
        return self._record(
            context,
            sdk_path=".".join(ref.path),
            kind="sdk",
            violations=[Violation("uncheckable", message)],
        )

    def _viable_candidates(self, refs: List[_SdkRef]) -> List[_SdkRef]:
        """Drop candidates whose optional (getattr-with-default) prefix is absent,
        unless that leaves nothing; then dedupe by path."""
        viable = [
            ref
            for ref in refs
            if ref.optional == 0 or self.resolve(ref.path[: ref.optional])[1] is None
        ]
        chosen = viable or refs
        seen: Set[Tuple[str, ...]] = set()
        out: List[_SdkRef] = []
        for ref in chosen:
            if ref.path not in seen:
                seen.add(ref.path)
                out.append(ref)
        return out

    @staticmethod
    def _record(
        context: _Context, **fields: Any
    ) -> SdkCall:
        file, class_name, method, node = context
        fields.setdefault("resolved", False)
        fields.setdefault("beta", None)
        return SdkCall(
            file=file,
            class_name=class_name,
            method=method,
            line=node.lineno,
            col=node.col_offset,
            **fields,
        )

    def _http_record(
        self, name: str, context: _Context
    ) -> SdkCall:
        file, class_name, method, _ = context
        function = f"{class_name}.{method}" if class_name else method
        label = self.labeled_http.get(f"{file}::{function}")
        violations = []
        if label is None:
            violations.append(
                Violation(
                    "direct-http",
                    f"direct HTTP call {name}() outside the labeled exceptions; "
                    "call Foundry through foundry-platform-sdk instead",
                )
            )
        return self._record(
            context, sdk_path=name, kind="http", http_label=label, violations=violations
        )

    def _sdk_record(
        self, ref: _SdkRef, context: _Context
    ) -> SdkCall:
        target = ".".join(ref.path)
        obj, error = self.resolve(ref.path)
        if error is not None:
            return self._record(
                context,
                sdk_path=target,
                kind="sdk",
                violations=[Violation("missing-method", error)],
            )
        try:
            sig = inspect.signature(obj)
        except (TypeError, ValueError):
            return self._record(
                context,
                sdk_path=target,
                kind="sdk",
                violations=[Violation("missing-method", f"{target} is not a method")],
            )
        call = context[3]
        assert isinstance(call, ast.Call)
        return self._record(
            context,
            sdk_path=target,
            kind="sdk",
            resolved=True,
            beta="preview" in sig.parameters,
            signature=_format_signature(sig),
            violations=check_arguments(call, sig, target),
        )


# ------------------------------------------------------------------ argument rules


def check_arguments(
    call: ast.Call, sig: inspect.Signature, target: str
) -> List[Violation]:
    """Violations of the binding and preview rules for ``call`` against ``sig``."""
    beta = "preview" in sig.parameters
    shown = f"{target}{_format_signature(sig)}"
    star_args = [arg for arg in call.args if isinstance(arg, ast.Starred)]
    star_kwargs = [kw for kw in call.keywords if kw.arg is None]
    positional = [arg for arg in call.args if not isinstance(arg, ast.Starred)]
    # (A repeated keyword is a SyntaxError, so names are unique.)
    keywords = {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}
    complete = not star_args and not star_kwargs
    out: List[Violation] = []

    if not complete:
        spread = [f"*{ast.unparse(a.value)}" for a in star_args] + [
            f"**{ast.unparse(kw.value)}" for kw in star_kwargs
        ]
        out.append(
            Violation(
                "unchecked-kwargs",
                f"arguments passed through {', '.join(spread)} can't be checked "
                f"against {shown}; pass them as explicit keywords",
            )
        )

    if "preview" in keywords:
        if not beta:
            out.append(
                Violation(
                    "preview-on-ga",
                    f"{target} is GA (it has no preview parameter); don't pass preview",
                )
            )
        elif not (
            isinstance(keywords["preview"], ast.Constant)
            and keywords["preview"].value is True
        ):
            out.append(
                Violation(
                    "beta-preview-not-literal",
                    f"{target} is beta; pass the literal preview=True, "
                    f"not preview={ast.unparse(keywords['preview'])}",
                )
            )
    elif beta and not star_kwargs:
        out.append(
            Violation("beta-without-preview", f"{target} is beta; pass preview=True")
        )

    # The SDK's maybe_ignore_preview decorator drops preview= on GA methods (with a
    # warning), so it doesn't take part in binding there.
    names = [name for name in keywords if beta or name != "preview"]
    out.extend(_binding_problems(sig, len(positional), names, complete, shown))
    return out


def _binding_problems(
    sig: inspect.Signature,
    n_positional: int,
    keywords: List[str],
    complete: bool,
    shown: str,
) -> List[Violation]:
    params = list(sig.parameters.values())
    kinds = inspect.Parameter
    has_var_positional = any(p.kind is kinds.VAR_POSITIONAL for p in params)
    has_var_keyword = any(p.kind is kinds.VAR_KEYWORD for p in params)
    positional_params = [
        p
        for p in params
        if p.kind in (kinds.POSITIONAL_ONLY, kinds.POSITIONAL_OR_KEYWORD)
    ]
    out: List[Violation] = []
    if n_positional > len(positional_params) and not has_var_positional:
        out.append(
            Violation(
                "too-many-positional",
                f"{n_positional} positional argument(s) given, but {shown} "
                f"takes {len(positional_params)}",
            )
        )
    bound = {p.name for p in positional_params[:n_positional]}
    for name in keywords:
        param = sig.parameters.get(name)
        if param is None or param.kind in (
            kinds.VAR_POSITIONAL,
            kinds.VAR_KEYWORD,
            kinds.POSITIONAL_ONLY,
        ):
            if not has_var_keyword:
                close = difflib.get_close_matches(name, list(sig.parameters), n=1)
                hint = f" (did you mean {close[0]!r}?)" if close else ""
                out.append(
                    Violation(
                        "unknown-keyword",
                        f"{shown} has no parameter {name!r}{hint}",
                        name,
                    )
                )
        elif name in bound:
            out.append(
                Violation(
                    "duplicate-argument",
                    f"{name!r} is passed both positionally and by keyword to {shown}",
                    name,
                )
            )
        else:
            bound.add(name)
    if not complete:
        return out
    for param in params:
        if (
            param.default is param.empty
            and param.kind not in (kinds.VAR_POSITIONAL, kinds.VAR_KEYWORD)
            and param.name not in bound
        ):
            out.append(
                Violation(
                    "missing-required",
                    f"required argument {param.name!r} isn't passed to {shown}",
                    param.name,
                )
            )
    # Cross-check with inspect's own binder, so the rules can never disagree with it.
    try:
        sig.bind(
            *[_PLACEHOLDER] * n_positional, **{name: _PLACEHOLDER for name in keywords}
        )
    except TypeError as error:
        if not out:
            out.append(Violation("bad-arguments", f"{shown}: {error}"))
    return out


# ------------------------------------------------------------------------ entry points


def make_client() -> Any:
    """A real V2 ``FoundryClient`` with a dummy token and hostname. Makes no requests."""
    from foundry_sdk import FoundryClient, UserTokenAuth

    return FoundryClient(
        auth=UserTokenAuth(token="sdk-call-guardrail"),
        hostname="sdk-call-guardrail.invalid",
    )


def analyze_sources(
    sources: Mapping[str, str],
    client: Any = None,
    labeled_http: Optional[Mapping[str, str]] = None,
) -> List[SdkCall]:
    """Records for in-memory modules: ``{"services/foo.py": "<source>", ...}``."""
    modules = [_parse_module(file, source) for file, source in sorted(sources.items())]
    analyzer = _Analyzer(
        modules,
        make_client() if client is None else client,
        LABELED_HTTP_EXCEPTIONS if labeled_http is None else labeled_http,
    )
    return analyzer.records()


def collect_sdk_calls(
    src_dir: Optional[Path] = None,
    client: Any = None,
    packages: Sequence[str] = SCANNED_PACKAGES,
    labeled_http: Optional[Mapping[str, str]] = None,
) -> List[SdkCall]:
    """One :class:`SdkCall` per SDK call and direct HTTP call in pltr's services/commands.

    ``src_dir`` defaults to this checkout's ``src/pltr``. ``client`` defaults to
    :func:`make_client`. Runs without network access.
    """
    root = Path(src_dir) if src_dir is not None else PLTR_SRC
    sources: Dict[str, str] = {}
    for package in packages:
        for path in sorted((root / package).glob("*.py")):
            if path.name == "__init__.py":
                continue
            sources[path.relative_to(root).as_posix()] = path.read_text(
                encoding="utf-8"
            )
    return analyze_sources(sources, client=client, labeled_http=labeled_http)


def find_violations(calls: Iterable[SdkCall]) -> List[Finding]:
    """Every violation, with its allowlist key.

    Keys are ``<file>::<Class.method>::<sdk path>::<rule>`` and don't contain line
    numbers, so unrelated edits don't change them. Repeats of the same key within one
    method get ``[2]``, ``[3]``, ... in source order.
    """
    counts: Dict[str, int] = {}
    findings: List[Finding] = []
    for call in sorted(calls, key=lambda c: (c.file, c.line, c.col, c.sdk_path)):
        for violation in call.violations:
            base = f"{call.file}::{call.function}::{call.sdk_path}::{violation.rule_id}"
            counts[base] = counts.get(base, 0) + 1
            key = base if counts[base] == 1 else f"{base}[{counts[base]}]"
            findings.append(Finding(key=key, call=call, violation=violation))
    return findings


# ----------------------------------------------------------------------- allowlist

ALLOWLIST_HEADER = """\
# SDK call guardrail: ratchet allowlist of known violations (issue #185).
#
# tests/test_sdk_call_guardrail.py fails on any violation that isn't listed here AND on
# any entry that no longer occurs. When you fix a violation, delete its line.
# Don't add lines to hide new violations; fix the call. See
# docs/development/sdk-guardrail.md.
#
# Format: <file>::<Class.method>::<SDK path or HTTP call>::<rule>[<n>]  # <reason>
# Rewrite (keeps existing reasons): uv run python scripts/check_sdk_calls.py --write-allowlist
"""


def load_allowlist(path: Path = DEFAULT_ALLOWLIST) -> Dict[str, str]:
    """Allowlist entries: key -> reason. A missing file is an empty allowlist."""
    entries: Dict[str, str] = {}
    if not path.exists():
        return entries
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, rest = line.partition(" ")
        reason = rest.strip()
        if reason.startswith("#"):
            reason = reason[1:].strip()
        if key in entries:
            raise ValueError(f"{path}:{lineno}: duplicate allowlist entry {key}")
        entries[key] = reason
    return entries


def default_reason(finding: Finding) -> str:
    """Reason written for a new allowlist entry: the violation message."""
    return " ".join(finding.violation.message.split())


def render_allowlist(findings: Sequence[Finding], reasons: Mapping[str, str]) -> str:
    """Allowlist text for ``findings``, reusing ``reasons`` for existing keys."""
    lines = [ALLOWLIST_HEADER.rstrip("\n")]
    current_file = None
    for finding in sorted(findings, key=lambda f: f.key):
        if finding.call.file != current_file:
            current_file = finding.call.file
            lines.extend(["", f"# src/pltr/{current_file}"])
        reason = reasons.get(finding.key) or default_reason(finding)
        lines.append(f"{finding.key}  # {reason}")
    return "\n".join(lines) + "\n"


def compare_with_allowlist(
    findings: Sequence[Finding], allowlist: Mapping[str, str]
) -> Tuple[List[Finding], List[str]]:
    """(findings not in the allowlist, allowlist keys that no longer occur)."""
    current = {finding.key for finding in findings}
    new = [finding for finding in findings if finding.key not in allowlist]
    stale = sorted(key for key in allowlist if key not in current)
    return new, stale


def unused_labeled_exceptions(
    calls: Iterable[SdkCall], labeled_http: Mapping[str, str] = LABELED_HTTP_EXCEPTIONS
) -> List[str]:
    """Labeled exceptions that no longer make a direct HTTP call."""
    used = {
        f"{c.file}::{c.function}" for c in calls if c.kind == "http" and c.http_label
    }
    return sorted(key for key in labeled_http if key not in used)
