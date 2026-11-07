"""pltr declares every third-party package it imports.

A package that only arrives as another package's dependency can be missing
from a fresh install: typer >= 0.26 bundles its own click and no longer
installs click, so `pip install pltr-cli` gave "No module named 'click'"
while uv.lock (typer 0.16, which requires click) hid it. The CI job
"fresh-install" installs the built wheel without the lock; this test catches
the cause in the normal test run.
"""

import ast
import re
import sys
from importlib.metadata import requires
from pathlib import Path
from typing import Set

SRC = Path(__file__).resolve().parent.parent / "src" / "pltr"

#: The distribution of each third-party package pltr imports (import name ->
#: name on PyPI). A new import needs an entry here and a dependency in
#: pyproject.toml.
DISTRIBUTIONS = {
    "click": "click",
    "foundry_sdk": "foundry-platform-sdk",
    "httpx": "httpx",
    "keyring": "keyring",
    "prompt_toolkit": "prompt-toolkit",
    "pyarrow": "pyarrow",
    "pydantic": "pydantic",
    "pydantic_core": "pydantic-core",
    "requests": "requests",
    "rich": "rich",
    "typer": "typer",
    "typing_extensions": "typing-extensions",
}


def imported_packages() -> Set[str]:
    """Top-level names of the third-party packages that src/pltr imports."""
    names: Set[str] = set()
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return {
        name for name in names if name not in sys.stdlib_module_names and name != "pltr"
    }


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def declared_dependencies() -> Set[str]:
    """The distributions that the installed pltr-cli requires (without extras)."""
    declared = set()
    for requirement in requires("pltr-cli") or []:
        if "extra ==" in requirement:
            continue
        match = re.match(r"[A-Za-z0-9._-]+", requirement)
        assert match, requirement
        declared.add(normalize(match.group(0)))
    return declared


def test_the_import_scan_finds_pltrs_dependencies():
    imported = imported_packages()

    assert {"click", "typer", "foundry_sdk"} <= imported


def test_every_imported_package_is_known():
    unknown = sorted(imported_packages() - DISTRIBUTIONS.keys())

    assert not unknown, (
        f"src/pltr imports {unknown}: add each to DISTRIBUTIONS and declare its "
        "distribution in pyproject.toml's dependencies"
    )


def test_every_imported_package_is_a_declared_dependency():
    needed = {normalize(DISTRIBUTIONS[name]) for name in imported_packages()}

    missing = sorted(needed - declared_dependencies())

    assert not missing, (
        f"pltr imports packages from {missing} but pyproject.toml doesn't declare "
        "them; a fresh install may not have them"
    )
