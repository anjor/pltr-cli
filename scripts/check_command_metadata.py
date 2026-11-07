#!/usr/bin/env python3
"""Cross-check curated commands' ``@pltr_command(sdk=...)`` metadata (#188).

    uv run python scripts/check_command_metadata.py          # report
    uv run python scripts/check_command_metadata.py --json   # machine-readable

For every curated command with metadata, the script follows the command
function to the service methods it calls, then to the SDK methods those
call, and compares them with the metadata:

* command function -> service methods: ``FooService(...).method(...)``, a
  local bound to ``FooService(...)`` (also inside lambdas and nested
  functions), bound methods passed around (``service.list_children``), and
  module-level helpers of the command module;
* service method -> service methods: ``self.method(...)`` (including base
  classes), and services held in attributes (``self.datasets.method``);
* service method -> SDK methods: the guardrail's resolver
  (``scripts/sdk_calls.py``), the same records CI checks.

It reports SDK methods a command declares but doesn't reach, SDK methods it
reaches but doesn't declare, labeled direct-HTTP calls reached by a command
without ``http=`` metadata, and calls the static analysis can't follow. It is
a report for a human, not a test: a service may call different SDK methods
depending on its arguments, and some indirections can't be followed
statically. Exit status 1 when there is a mismatch.
"""

from __future__ import annotations

import argparse
import ast
import inspect
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.sdk_calls import PLTR_SRC, SdkCall, collect_sdk_calls  # noqa: E402

#: A function in pltr's source: (file relative to src/pltr, class or None, name).
Function = Tuple[str, Optional[str], str]


@dataclass
class Report:
    path: str
    declared: List[str]
    reached: List[str]
    http: List[str] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)

    @property
    def missing(self) -> List[str]:
        """Reached but not declared."""
        return sorted(set(self.reached) - set(self.declared))

    @property
    def extra(self) -> List[str]:
        """Declared but not reached."""
        return sorted(set(self.declared) - set(self.reached))

    @property
    def ok(self) -> bool:
        return not (self.missing or self.extra)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "declared": self.declared,
            "reached": self.reached,
            "declaredNotReached": self.extra,
            "reachedNotDeclared": self.missing,
            "directHttp": self.http,
            "unresolved": self.unresolved,
            "serviceMethods": self.services,
        }


# ------------------------------------------------------------------ sources


class Source:
    """Parsed modules of src/pltr/{commands,services}: classes, functions, imports."""

    def __init__(self, root: Path = PLTR_SRC) -> None:
        self.modules: Dict[str, ast.Module] = {}
        for package in ("commands", "services"):
            for path in sorted((root / package).glob("*.py")):
                rel = path.relative_to(root).as_posix()
                self.modules[rel] = ast.parse(path.read_text(encoding="utf-8"))
        self.classes: Dict[str, List[Tuple[str, ast.ClassDef]]] = defaultdict(list)
        for file, module in self.modules.items():
            for node in module.body:
                if isinstance(node, ast.ClassDef):
                    self.classes[node.name].append((file, node))

    def imported_classes(self, file: str) -> Dict[str, str]:
        """{class name: services file} for `from ..services.x import Name`."""
        names: Dict[str, str] = {}
        package = file.split("/")[0]
        for node in ast.walk(self.modules[file]):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                target = None
                if "services" in parts and parts[-1] != "services":
                    target = f"services/{parts[parts.index('services') + 1]}.py"
                elif node.level == 1 and package == "services":
                    target = f"services/{parts[0]}.py"  # from .dataset import ...
                if target is not None:
                    for alias in node.names:
                        names[alias.asname or alias.name] = target
        for node in self.modules[file].body:
            if isinstance(node, ast.ClassDef):
                names[node.name] = file
        return names

    def class_node(self, file: str, name: str) -> Optional[ast.ClassDef]:
        for candidate_file, node in self.classes.get(name, []):
            if candidate_file == file:
                return node
        return None

    def method(self, file: str, cls: str, name: str) -> Optional[Function]:
        """Find a method in a class or its bases (by name, across modules)."""
        seen: Set[Tuple[str, str]] = set()
        queue = [(file, cls)]
        while queue:
            current_file, current = queue.pop(0)
            if (current_file, current) in seen:
                continue
            seen.add((current_file, current))
            node = self.class_node(current_file, current)
            if node is None:
                continue
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == name:
                        return (current_file, current, name)
            imports = self.imported_classes(current_file)
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_file = imports.get(base.id, current_file)
                    queue.append((base_file, base.id))
        return None

    def function_node(self, function: Function) -> Optional[ast.AST]:
        file, cls, name = function
        module = self.modules.get(file)
        if module is None:
            return None
        body: Iterable[ast.stmt] = module.body
        if cls is not None:
            node = self.class_node(file, cls)
            if node is None:
                return None
            body = node.body
        for item in body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name == name:
                    return item
        return None

    def attribute_services(self, file: str, cls: str) -> Dict[str, Tuple[str, str]]:
        """{attribute: (file, class)} for `self.attr = FooService(...)` in a class."""
        node = self.class_node(file, cls)
        if node is None:
            return {}
        imports = self.imported_classes(file)
        found: Dict[str, Tuple[str, str]] = {}
        for item in ast.walk(node):
            if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call):
                callee = item.value.func
                if isinstance(callee, ast.Name) and callee.id in imports:
                    for target in item.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"
                        ):
                            found[target.attr] = (imports[callee.id], callee.id)
        return found


# ------------------------------------------------------------------ walking


def _service_class(name: str) -> bool:
    return name.endswith("Service") and name != "BaseService"


def reached_functions(source: Source, start: Function) -> Set[Function]:
    """Every function of pltr's own code reached from a command function."""
    reached: Set[Function] = set()
    queue = [start]
    while queue:
        function = queue.pop()
        if function in reached:
            continue
        reached.add(function)
        node = source.function_node(function)
        if node is None:
            continue
        queue.extend(_callees(source, function, node))
    return reached


def _callees(source: Source, function: Function, node: ast.AST) -> List[Function]:
    file, cls, _ = function
    imports = source.imported_classes(file)
    module_functions = {
        item.name
        for item in source.modules[file].body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    attributes = source.attribute_services(file, cls) if cls else {}
    bound: Dict[str, Tuple[str, str]] = {}
    for item in ast.walk(node):  # locals bound to a service instance
        if isinstance(item, (ast.Assign, ast.AnnAssign)) and isinstance(
            item.value, ast.Call
        ):
            callee = item.value.func
            if isinstance(callee, ast.Name) and _service_class(callee.id):
                targets = (
                    item.targets if isinstance(item, ast.Assign) else [item.target]
                )
                for target in targets:
                    if isinstance(target, ast.Name):
                        bound[target.id] = (imports.get(callee.id, file), callee.id)
    found: List[Function] = []
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            owner = item.value
            target: Optional[Tuple[str, str]] = None
            if isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name):
                if _service_class(owner.func.id):
                    target = (imports.get(owner.func.id, file), owner.func.id)
            elif isinstance(owner, ast.Name):
                if owner.id in bound:
                    target = bound[owner.id]
                elif owner.id == "self" and cls is not None:
                    method = source.method(file, cls, item.attr)
                    if method is not None:
                        found.append(method)
            elif (
                isinstance(owner, ast.Attribute)
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "self"
                and owner.attr in attributes
            ):
                target = attributes[owner.attr]
            if target is not None:
                method = source.method(target[0], target[1], item.attr)
                if method is not None:
                    found.append(method)
        elif isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
            if item.func.id in module_functions and cls is None:
                found.append((file, None, item.func.id))
    return found


# ------------------------------------------------------------------ checking


def _records(calls: Iterable[SdkCall]) -> Dict[Function, List[SdkCall]]:
    by_function: Dict[Function, List[SdkCall]] = defaultdict(list)
    for call in calls:
        by_function[(call.file, call.class_name, call.method)].append(call)
    return by_function


def check(app: Any = None) -> List[Report]:
    """A report per curated command with ``@pltr_command`` metadata."""
    if app is None:
        from pltr.cli import app as pltr_app

        app = pltr_app
    from pltr.contract import iter_commands

    source = Source()
    records = _records(collect_sdk_calls())
    reports = []
    for entry in iter_commands(app):
        if entry.meta is None or entry.path.split()[0] == "api":
            continue
        function = inspect.unwrap(entry.command.callback)  # type: ignore[arg-type]
        module = function.__module__
        if not module.startswith("pltr.commands."):
            continue
        file = module[len("pltr.") :].replace(".", "/") + ".py"
        start: Function = (file, None, function.__name__)
        reached = reached_functions(source, start)
        sdk: Set[str] = set()
        http: Set[str] = set()
        unresolved: Set[str] = set()
        for function_key in reached:
            for call in records.get(function_key, []):
                where = f"{call.function} ({call.location})"
                if call.kind == "http":
                    http.add(f"{call.sdk_path} in {where}")
                elif call.resolved:
                    sdk.add(call.sdk_path)
                else:
                    unresolved.add(f"{call.sdk_path} in {where}")
        reports.append(
            Report(
                path=f"pltr {entry.path}",
                declared=sorted(entry.meta.sdk),
                reached=sorted(sdk),
                http=sorted(http) if not entry.meta.http else [],
                unresolved=sorted(unresolved),
                services=sorted(
                    f"{cls}.{name}"
                    for f, cls, name in reached
                    if cls is not None and f.startswith("services/")
                ),
            )
        )
    return sorted(reports, key=lambda report: report.path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", action="store_true", help="Print JSON reports.")
    parser.add_argument(
        "--all", action="store_true", help="Also list commands that match."
    )
    args = parser.parse_args(argv)
    reports = check()
    problems = [r for r in reports if not r.ok or r.http or r.unresolved]
    if args.json:
        shown = reports if args.all else problems
        print(json.dumps([r.to_dict() for r in shown], indent=2))
    else:
        for report in reports if args.all else problems:
            print(report.path)
            print(f"  declared: {', '.join(report.declared) or '-'}")
            print(f"  reached:  {', '.join(report.reached) or '-'}")
            for label, items in (
                ("declared, not reached", report.extra),
                ("reached, not declared", report.missing),
                ("direct HTTP without http= metadata", report.http),
                ("unresolved (check by hand)", report.unresolved),
            ):
                for item in items:
                    print(f"  {label}: {item}")
        mismatched = sum(1 for r in reports if not r.ok)
        print(
            f"\n{len(reports)} curated commands with metadata: {mismatched} "
            f"mismatched, {sum(1 for r in reports if r.http)} with undeclared "
            f"direct HTTP, {sum(1 for r in reports if r.unresolved)} with "
            "unresolved calls."
        )
    return 1 if any(not r.ok or r.http for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
