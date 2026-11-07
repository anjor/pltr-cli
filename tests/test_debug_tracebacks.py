"""PLTR_DEBUG=1 tracebacks must not print credentials.

typer's Rich tracebacks show every frame's local variables unless the app
turns that off, and those locals hold the bearer token, the Authorization
header and the OAuth client secret. pltr's error hints ask people to share
PLTR_DEBUG=1 output, so the root app sets pretty_exceptions_show_locals=False.

These tests run the real entry point in a subprocess: typer installs its
traceback hook in Typer.__call__, which typer.testing.CliRunner bypasses.
"""

import os
import socket
import subprocess
import sys
from typing import List

import pytest

from pltr.cli import app

TOKEN = "PltrTestTokenNeverPrint123"
CLIENT_SECRET = "PltrTestClientSecretNeverPrint456"
FOLDER_RID = "ri.compass.main.folder.00000000-0000-0000-0000-000000000001"


def unused_port() -> str:
    """A localhost port nothing listens on, so connections are refused."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return f"127.0.0.1:{sock.getsockname()[1]}"


def run_with_debug(args: List[str], **variables: str) -> subprocess.CompletedProcess:
    """Run `python -m pltr <args>` with PLTR_DEBUG=1 and only these FOUNDRY_* set."""
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("FOUNDRY_", "PLTR_")) and "proxy" not in name.lower()
    }
    env.update(PLTR_DEBUG="1", NO_PROXY="*", no_proxy="*", COLUMNS="200", **variables)
    return subprocess.run(
        [sys.executable, "-m", "pltr", *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )


def assert_traceback_without(result: subprocess.CompletedProcess, secret: str) -> None:
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    # The command really failed with a debug traceback, so locals had a chance
    # to be printed.
    assert "Traceback" in result.stderr, output
    assert secret not in output


def test_the_root_app_hides_traceback_locals():
    assert app.pretty_exceptions_show_locals is False


@pytest.mark.usefixtures("isolated_home")
def test_token_from_the_environment_is_not_printed():
    # FOUNDRY_HOST is missing, so reading the environment fails before any request.
    result = run_with_debug(
        ["folder", "get", FOLDER_RID, "--format", "json"], FOUNDRY_TOKEN=TOKEN
    )

    assert_traceback_without(result, TOKEN)


@pytest.mark.usefixtures("isolated_home")
def test_bearer_header_is_not_printed_when_a_direct_http_request_fails():
    # language-models list calls Foundry with `requests`; the Authorization
    # header is a local of the frame that sends it.
    result = run_with_debug(
        ["language-models", "list"], FOUNDRY_HOST=unused_port(), FOUNDRY_TOKEN=TOKEN
    )

    assert_traceback_without(result, TOKEN)


@pytest.mark.usefixtures("isolated_home")
def test_oauth_client_secret_is_not_printed_when_the_token_request_fails():
    result = run_with_debug(
        ["folder", "get", FOLDER_RID],
        FOUNDRY_HOST=unused_port(),
        FOUNDRY_CLIENT_ID="pltr-test-client",
        FOUNDRY_CLIENT_SECRET=CLIENT_SECRET,
    )

    assert_traceback_without(result, CLIENT_SECRET)
