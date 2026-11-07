"""
Pytest configuration and fixtures for pltr tests.
"""

import pytest
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from typing import Any, Dict, Generator, List, Optional, Tuple

import httpx
import requests
import requests.adapters
import requests.structures
from foundry_sdk import FoundryClient, UserTokenAuth

from pltr.auth.manager import AuthSource
from pltr.auth.storage import CredentialStorage
from pltr.config.settings import Settings
from pltr.config.profiles import ProfileManager


STUB_HOSTNAME = "test.palantirfoundry.com"
STUB_TOKEN = "test-token"


@pytest.fixture(autouse=True)
def _clean_output_environment(monkeypatch):
    """Keep the caller's PLTR_FORMAT / PLTR_DEBUG from changing test results."""
    monkeypatch.delenv("PLTR_FORMAT", raising=False)
    monkeypatch.delenv("PLTR_DEBUG", raising=False)


@pytest.fixture(autouse=True)
def _plain_terminal_output(monkeypatch):
    """Render help and usage errors as plain text, as on a developer's machine.

    On GitHub Actions (GITHUB_ACTIONS), or with FORCE_COLOR / PY_COLORS set,
    Typer forces Rich's terminal mode, so help text and usage errors carry ANSI
    codes and assertions on their text fail. _TYPER_FORCE_DISABLE_TERMINAL is
    Typer's own switch; subprocesses (`python -m pltr`) inherit it.
    """
    for name in ("FORCE_COLOR", "PY_COLORS", "TTY_COMPATIBLE", "TTY_INTERACTIVE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("_TYPER_FORCE_DISABLE_TERMINAL", "1")
    monkeypatch.setattr("typer.rich_utils.FORCE_TERMINAL", False)


@pytest.fixture(autouse=True)
def _private_home(monkeypatch, tmp_path_factory):
    """Keep every test away from the real home directory.

    Commands write a RID completion cache (~/.cache/pltr) after successful
    calls; without this, tests that don't ask for `isolated_home` write it to
    the developer's (or CI runner's) real home. Tests that set HOME themselves
    still win, because their monkeypatching runs after this fixture's.
    """
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


@pytest.fixture
def isolated_home(monkeypatch, tmp_path) -> Path:
    """Point the home and config directories at a temporary directory.

    Commands write a RID completion cache (~/.cache/pltr) and read profiles
    from ~/.config/pltr; this keeps CLI tests away from the real ones. Also
    widens Rich's console so tables aren't folded at 80 columns.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("COLUMNS", "200")
    return home


@dataclass
class StubFoundryHttp:
    """A real foundry_sdk FoundryClient whose network layer returns canned responses."""

    client: Any
    requests: List[httpx.Request] = field(default_factory=list)
    _queued: List[Tuple[int, Dict[str, Any]]] = field(default_factory=list)
    _default: Optional[Tuple[int, Dict[str, Any]]] = None

    def respond(self, status_code: int = 200, **response_kwargs: Any) -> None:
        """Queue the response for the next request (kwargs go to httpx.Response)."""
        self._queued.append((status_code, response_kwargs))

    def respond_always(self, status_code: int = 200, **response_kwargs: Any) -> None:
        """Answer every request that has no queued response with this response.

        Queued responses (``respond``) are still used first.
        """
        self._default = (status_code, response_kwargs)

    def next_response(self, request: httpx.Request) -> Tuple[int, Dict[str, Any]]:
        """Pop the queued response, else the default one, else fail the test."""
        if self._queued:
            return self._queued.pop(0)
        if self._default is not None:
            return self._default
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")


@pytest.fixture
def stub_foundry_http(monkeypatch) -> StubFoundryHttp:
    """Give services a real FoundryClient, faking only HTTP.

    Unlike Mock()-based clients, calls to SDK methods or keyword arguments that
    don't exist fail, SDK argument validation runs, responses are decoded into
    real SDK models, and SDK warnings (e.g. about `preview`) surface.

    Requests made with the ``requests`` library (the labeled direct-HTTP
    commands) are answered from the same queue and recorded in
    ``stub.requests`` as ``httpx.Request`` objects too, so no test can reach
    the network through either client.
    """
    stub = StubFoundryHttp(
        client=FoundryClient(
            auth=UserTokenAuth(token=STUB_TOKEN), hostname=STUB_HOSTNAME
        )
    )

    def fake_send(self, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        request.read()
        stub.requests.append(request)
        status_code, response_kwargs = stub.next_response(request)
        return httpx.Response(status_code, request=request, **response_kwargs)

    def fake_requests_send(
        self, prepared: requests.PreparedRequest, **kwargs: Any
    ) -> requests.Response:
        body = prepared.body
        content = body.encode() if isinstance(body, str) else (body or b"")
        request = httpx.Request(
            prepared.method or "GET",
            prepared.url or "",
            headers=dict(prepared.headers),
            content=content,
        )
        stub.requests.append(request)
        status_code, response_kwargs = stub.next_response(request)
        canned = httpx.Response(status_code, request=request, **response_kwargs)
        response = requests.Response()
        response.status_code = status_code
        response._content = canned.content
        response.headers = requests.structures.CaseInsensitiveDict(canned.headers)
        response.url = prepared.url or ""
        response.reason = canned.reason_phrase
        response.encoding = "utf-8"
        response.request = prepared
        return response

    monkeypatch.setattr(httpx.Client, "send", fake_send)
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake_requests_send)
    auth_manager = Mock()
    auth_manager.return_value.get_client.return_value = stub.client
    # For direct-HTTP code (BaseService._make_request: host and token) and for
    # `pltr verify` (which reports the auth source and uses the context's
    # client): a context shaped like pltr.auth.manager.AuthContext.
    auth_manager.return_value.get_auth_context.return_value = SimpleNamespace(
        base_url=f"https://{STUB_HOSTNAME}",
        host=STUB_HOSTNAME,
        get_token=lambda: STUB_TOKEN,
        client=stub.client,
        source=AuthSource(
            kind="environment",
            auth_type="token",
            host=STUB_HOSTNAME,
            variables=("FOUNDRY_HOST", "FOUNDRY_TOKEN"),
        ),
    )
    monkeypatch.setattr("pltr.services.base.AuthManager", auth_manager)
    return stub


@pytest.fixture
def temp_config_dir() -> Generator[Path, None, None]:
    """Create a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_keyring():
    """Mock keyring for credential storage tests."""
    with (
        patch("keyring.set_password") as mock_set,
        patch("keyring.get_password") as mock_get,
        patch("keyring.delete_password") as mock_delete,
    ):
        # Set up mock storage
        storage = {}

        def set_password(service, username, password):
            storage[f"{service}:{username}"] = password

        def get_password(service, username):
            return storage.get(f"{service}:{username}")

        def delete_password(service, username):
            key = f"{service}:{username}"
            if key in storage:
                del storage[key]

        mock_set.side_effect = set_password
        mock_get.side_effect = get_password
        mock_delete.side_effect = delete_password

        yield {
            "set": mock_set,
            "get": mock_get,
            "delete": mock_delete,
            "storage": storage,
        }


@pytest.fixture
def mock_settings(temp_config_dir):
    """Mock settings with temporary directory."""
    with patch.object(Settings, "_get_config_dir", return_value=temp_config_dir):
        settings = Settings()
        yield settings


@pytest.fixture
def mock_credential_storage(mock_keyring):
    """Mock credential storage with keyring mocked."""
    storage = CredentialStorage()
    yield storage


@pytest.fixture
def mock_profile_manager(temp_config_dir):
    """Mock profile manager with temporary directory."""
    with patch.object(Settings, "_get_config_dir", return_value=temp_config_dir):
        manager = ProfileManager()
        yield manager


@pytest.fixture
def sample_token_credentials():
    """Sample token-based credentials."""
    return {
        "auth_type": "token",
        "host": "https://test.palantirfoundry.com",
        "token": "test_token_12345",
    }


@pytest.fixture
def sample_oauth_credentials():
    """Sample OAuth credentials."""
    return {
        "auth_type": "oauth",
        "host": "https://test.palantirfoundry.com",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "scopes": ["api:read"],
    }


@pytest.fixture
def mock_requests():
    """Mock requests for HTTP calls."""
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # Default successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "username": "test.user@example.com",
            "id": "12345-abcde",
            "organization": {"rid": "ri.organization.main"},
        }

        mock_get.return_value = mock_response
        mock_post.return_value = mock_response

        yield {"get": mock_get, "post": mock_post, "response": mock_response}
