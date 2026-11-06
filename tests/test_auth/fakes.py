"""
Fakes for auth tests: Foundry's HTTP layer and the system keyring.

``FakeFoundryHttp`` fakes only the network: real ``FoundryClient`` objects (and
real ``foundry_sdk`` auth objects, including the OAuth token request) run
unchanged on top of a faked ``httpx.Client.send``, and pltr's direct-HTTP calls
run on top of a faked ``requests.request``.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

import httpx
import keyring.errors
import requests

OAUTH_TOKEN_PATH = "/multipass/api/oauth2/token"
OAUTH_ACCESS_TOKEN = "oauth-access-token-123"
GET_CURRENT_USER_PATH = "/api/v2/admin/users/getCurrent"

# An admin.User as the Foundry API returns it.
USER_JSON: Dict[str, Any] = {
    "id": "f5bf3a0a-8a1b-4b8c-9a55-0123456789ab",
    "username": "jane.doe@example.com",
    "givenName": "Jane",
    "familyName": "Doe",
    "email": "jane.doe@example.com",
    "realm": "palantir-internal-realm",
    "organization": "ri.multipass..organization.0a1b2c3d-1111-2222-3333-444455556666",
    "status": "ACTIVE",
    "attributes": {"multipass:email:primary": ["jane.doe@example.com"]},
}


class FakeFoundryHttp:
    """Route faked responses by (method, path); fail on any other request."""

    def __init__(self) -> None:
        self.sdk_requests: List[httpx.Request] = []
        self.direct_requests: List[Dict[str, Any]] = []
        self._routes: Dict[Tuple[str, str], Tuple[int, Any]] = {}

    def route(self, method: str, path: str, status: int = 200, body: Any = None):
        """Answer ``method path`` (any host) with ``status`` and a JSON body."""
        self._routes[(method.upper(), path)] = (status, body)

    def route_oauth_token(self, status: int = 200, body: Any = None) -> None:
        """Answer the OAuth client-credentials token request."""
        if body is None and status == 200:
            body = {
                "access_token": OAUTH_ACCESS_TOKEN,
                "token_type": "bearer",
                "expires_in": 3600,
            }
        self.route("POST", OAUTH_TOKEN_PATH, status, body)

    def _lookup(self, method: str, path: str) -> Tuple[int, Any]:
        key = (method.upper(), path)
        if key not in self._routes:
            raise AssertionError(f"Unexpected request: {method} {path}")
        return self._routes[key]

    def install(self, monkeypatch) -> "FakeFoundryHttp":
        fake = self

        def fake_send(client: Any, request: httpx.Request, **kwargs: Any):
            request.read()
            fake.sdk_requests.append(request)
            status, body = fake._lookup(request.method, request.url.path)
            content = b"" if body is None else json.dumps(body).encode()
            return httpx.Response(
                status,
                request=request,
                content=content,
                headers={"Content-Type": "application/json"},
            )

        def fake_request(method: str, url: str, **kwargs: Any) -> requests.Response:
            fake.direct_requests.append({"method": method, "url": url, **kwargs})
            path = httpx.URL(url).path
            status, body = fake._lookup(method, path)
            response = requests.Response()
            response.status_code = status
            response.reason = "OK" if status < 400 else "Error"
            response.url = url
            response._content = b"" if body is None else json.dumps(body).encode()
            response.headers["Content-Type"] = "application/json"
            return response

        monkeypatch.setattr(httpx.Client, "send", fake_send)
        monkeypatch.setattr(requests, "request", fake_request)
        return self

    def sdk_request(self, path: str) -> httpx.Request:
        """Return the (single) SDK request made to ``path``."""
        matches = [r for r in self.sdk_requests if r.url.path == path]
        assert len(matches) == 1, f"expected one request to {path}: {matches}"
        return matches[0]


class FakeKeyring:
    """In-memory replacement for the keyring module's password functions."""

    def __init__(self) -> None:
        self.passwords: Dict[Tuple[str, str], str] = {}
        self.calls: List[str] = []

    def get_password(self, service: str, username: str) -> Optional[str]:
        self.calls.append("get")
        return self.passwords.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.calls.append("set")
        self.passwords[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.calls.append("delete")
        if (service, username) not in self.passwords:
            raise keyring.errors.PasswordDeleteError("not found")
        del self.passwords[(service, username)]

    def store(self, profile: str, credentials: Dict[str, Any]) -> None:
        self.passwords[("pltr-cli", profile)] = json.dumps(credentials)

    def install(self, monkeypatch) -> "FakeKeyring":
        monkeypatch.setattr(keyring, "get_password", self.get_password)
        monkeypatch.setattr(keyring, "set_password", self.set_password)
        monkeypatch.setattr(keyring, "delete_password", self.delete_password)
        return self


def forbid_keyring(monkeypatch) -> List[str]:
    """Make every keyring entry point fail the test; return the list of attempts."""
    attempts: List[str] = []

    def touched(name: str):
        def fail(*args: Any, **kwargs: Any) -> Any:
            attempts.append(name)
            raise AssertionError(f"keyring.{name} must not be called")

        return fail

    for name in ("get_password", "set_password", "delete_password", "get_keyring"):
        monkeypatch.setattr(keyring, name, touched(name))
    return attempts


def broken_keyring(monkeypatch, error: Optional[Exception] = None) -> None:
    """Make the keyring behave like a machine without a usable backend."""
    failure = error or keyring.errors.NoKeyringError(
        "No recommended backend was available."
    )

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise failure

    for name in ("get_password", "set_password", "delete_password"):
        monkeypatch.setattr(keyring, name, fail)


__all__ = [
    "FakeFoundryHttp",
    "FakeKeyring",
    "GET_CURRENT_USER_PATH",
    "OAUTH_ACCESS_TOKEN",
    "OAUTH_TOKEN_PATH",
    "USER_JSON",
    "broken_keyring",
    "forbid_keyring",
]
