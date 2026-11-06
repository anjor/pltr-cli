"""Fixtures for the generated `pltr api` commands (on top of `stub_foundry_http`)."""

import json
from typing import Any, List, Optional
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from pltr.cli import app


@pytest.fixture
def api_stub(stub_foundry_http, monkeypatch):
    """`stub_foundry_http`, also served to `pltr api` via AuthManager().get_client()."""
    auth_manager = Mock()
    auth_manager.return_value.get_client.return_value = stub_foundry_http.client
    monkeypatch.setattr("pltr.auth.manager.AuthManager", auth_manager)
    monkeypatch.delenv("PLTR_FORMAT", raising=False)
    stub_foundry_http.auth_manager = auth_manager
    return stub_foundry_http


class Invoker:
    def __init__(self) -> None:
        self.runner = CliRunner()

    def __call__(self, *args: str, input: Optional[Any] = None, env=None):
        return self.runner.invoke(app, ["api", *args], input=input, env=env)


@pytest.fixture
def pltr_api():
    """Run `pltr api ...` through the real root Typer app."""
    return Invoker()


def stderr_json(result) -> Any:
    """The structured error: the last stderr line, parsed."""
    lines: List[str] = [line for line in result.stderr.splitlines() if line.strip()]
    assert lines, "expected a JSON error on stderr"
    return json.loads(lines[-1])
