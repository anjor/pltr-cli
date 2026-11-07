"""Fixtures for the command manifest, `pltr commands` and the skill reference."""

import importlib.util
import sys
from pathlib import Path

import pytest

from pltr.manifest import build_manifest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load_script(name: str, filename: str):
    """Import a script from scripts/ without touching sys.path."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def manifest():
    """The manifest of the real CLI (built once: it walks the whole tree)."""
    return build_manifest()


@pytest.fixture(scope="session")
def entries(manifest):
    """{path: command entry} of the real CLI."""
    return {entry["path"]: entry for entry in manifest["commands"]}


@pytest.fixture(scope="session")
def generator():
    return load_script("pltr_generate_skill_reference", "generate_skill_reference.py")
