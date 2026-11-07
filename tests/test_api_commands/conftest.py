"""Fixtures for the generated `pltr api` commands.

The commands get their client from `pltr.services.base.AuthManager`, like the
services, so `stub_foundry_http` (tests/conftest.py) serves them directly.
"""

from typing import Any, Optional

import pytest
from typer.testing import CliRunner

from pltr.cli import app


@pytest.fixture(autouse=True)
def _isolated(isolated_home):
    """No real home directory; wide tables (COLUMNS=200)."""
    return isolated_home


class Invoker:
    def __init__(self) -> None:
        self.runner = CliRunner()

    def __call__(self, *args: str, input: Optional[Any] = None, env=None):
        return self.runner.invoke(app, ["api", *args], input=input, env=env)


@pytest.fixture
def pltr_api():
    """Run `pltr api ...` through the real root Typer app."""
    return Invoker()
