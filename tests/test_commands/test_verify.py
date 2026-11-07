"""
Tests for the verify command.

verify calls admin.User.get_current() through a real FoundryClient built by
AuthManager; only the network and the keyring are faked. Errors follow the
shared contract (pltr.contract): structured JSON errors, documented exit
codes, status lines on stderr. (These tests replace ones that mocked
`requests` for the old /multipass/api/me call; the error `type` values now
use the contract's names, e.g. `auth_error` instead of `auth`.)
"""

import csv
import io
import json
from typing import Any, Dict

import pytest
from typer.testing import CliRunner

from pltr.auth.manager import AuthManager
from pltr.cli import app
from pltr.config.profiles import ProfileManager
from tests.conftest import STUB_HOSTNAME, STUB_TOKEN
from tests.test_auth.fakes import (
    GET_CURRENT_USER_PATH,
    OAUTH_ACCESS_TOKEN,
    OAUTH_TOKEN_PATH,
    USER_JSON,
    FakeFoundryHttp,
    FakeKeyring,
)
from tests.test_contract.cases.verify import SUCCESS as CONTRACT_SUCCESS
from tests.test_contract.test_cli_contract import (
    ERROR_INSTANCE_ID,
    SCENARIOS,
    error_problems,
    stderr_json_lines,
)

PROFILE_HOST = "work.palantirfoundry.com"
ENV_HOST = "env.palantirfoundry.com"

pytestmark = pytest.mark.filterwarnings("error::UserWarning")


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    for name in (
        "PLTR_PROFILE",
        "PLTR_FORMAT",
        "FOUNDRY_HOST",
        "FOUNDRY_HOSTNAME",
        "FOUNDRY_TOKEN",
        "FOUNDRY_CLIENT_ID",
        "FOUNDRY_CLIENT_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


@pytest.fixture
def fake_http(monkeypatch) -> FakeFoundryHttp:
    return FakeFoundryHttp().install(monkeypatch)


@pytest.fixture
def fake_keyring(monkeypatch) -> FakeKeyring:
    return FakeKeyring().install(monkeypatch)


def add_profile(fake_keyring: FakeKeyring, name: str, credentials: Dict[str, Any]):
    fake_keyring.store(name, credentials)
    manager = ProfileManager()
    manager.add_profile(name)
    manager.set_default(name)


def token_profile(token: str = "work-token") -> Dict[str, Any]:
    return {"auth_type": "token", "host": f"https://{PROFILE_HOST}", "token": token}


def env_token(monkeypatch):
    monkeypatch.setenv("FOUNDRY_HOST", ENV_HOST)
    monkeypatch.setenv("FOUNDRY_TOKEN", "env-token")


def api_error(name: str, code: str) -> Dict[str, Any]:
    return {
        "errorCode": code,
        "errorName": name,
        "errorInstanceId": "4f5c1b0e-0000-4000-8000-000000000001",
        "parameters": {},
    }


def invoke(*args: str):
    return CliRunner().invoke(app, ["verify", *args])


def last_error(result) -> Dict[str, Any]:
    return json.loads(result.stderr.strip().splitlines()[-1])


class TestVerifySuccess:
    def test_default_token_profile_table(self, fake_keyring, fake_http):
        add_profile(fake_keyring, "work", token_profile())
        fake_http.route("GET", GET_CURRENT_USER_PATH, body=USER_JSON)

        result = invoke()

        assert result.exit_code == 0, result.output
        request = fake_http.sdk_request(GET_CURRENT_USER_PATH)
        assert request.method == "GET"
        assert request.url.host == PROFILE_HOST
        assert request.headers["Authorization"] == "Bearer work-token"
        assert "preview" not in request.url.params
        # Only the SDK call: no direct HTTP (the old /multipass/api/me call)
        assert fake_http.direct_requests == []
        assert "Authentication verified" in result.stdout
        assert "jane.doe@example.com" in result.stdout
        assert "profile 'work' (default profile)" in result.stdout
        assert "palantir-internal-realm" in result.stdout
        assert (
            f"Verifying profile 'work' (default profile) against https://{PROFILE_HOST}"
            in result.stderr
        )
        assert "Authentication successful" in result.stderr
        assert "Authentication successful" not in result.stdout

    def test_json_output_with_environment_token(self, fake_http, monkeypatch):
        env_token(monkeypatch)
        fake_http.route("GET", GET_CURRENT_USER_PATH, body=USER_JSON)

        result = invoke("--format", "json")

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {
            "authSource": {
                "kind": "environment",
                "authType": "token",
                "host": ENV_HOST,
                "variables": ["FOUNDRY_HOST", "FOUNDRY_TOKEN"],
            },
            "user": USER_JSON,
        }
        # JSON mode: no informational output on stderr
        assert result.stderr == ""
        request = fake_http.sdk_request(GET_CURRENT_USER_PATH)
        assert request.headers["Authorization"] == "Bearer env-token"

    def test_json_output_with_oauth_profile_option(self, fake_keyring, fake_http):
        fake_keyring.store(
            "svc",
            {
                "auth_type": "oauth",
                "host": PROFILE_HOST,
                "client_id": "svc-client",
                "client_secret": "svc-secret",
            },
        )
        fake_http.route_oauth_token()
        fake_http.route("GET", GET_CURRENT_USER_PATH, body=USER_JSON)

        result = invoke("--profile", "svc", "--format", "json")

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["authSource"] == {
            "kind": "profile",
            "profile": "svc",
            "selectedBy": "--profile",
            "authType": "oauth",
            "host": PROFILE_HOST,
        }
        fake_http.sdk_request(OAUTH_TOKEN_PATH)
        request = fake_http.sdk_request(GET_CURRENT_USER_PATH)
        assert request.headers["Authorization"] == f"Bearer {OAUTH_ACCESS_TOKEN}"

    def test_pltr_format_sets_the_default_format(self, fake_http, monkeypatch):
        env_token(monkeypatch)
        monkeypatch.setenv("PLTR_FORMAT", "json")
        fake_http.route("GET", GET_CURRENT_USER_PATH, body=USER_JSON)

        result = invoke()

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["user"]["username"] == USER_JSON["username"]

    def test_format_option_beats_pltr_format(self, fake_http, monkeypatch):
        env_token(monkeypatch)
        monkeypatch.setenv("PLTR_FORMAT", "json")
        fake_http.route("GET", GET_CURRENT_USER_PATH, body=USER_JSON)

        result = invoke("--format", "csv")

        assert result.exit_code == 0, result.output
        assert result.stdout.startswith("Auth source,")

    def test_csv_output(self, fake_http, monkeypatch):
        env_token(monkeypatch)
        fake_http.route("GET", GET_CURRENT_USER_PATH, body=USER_JSON)

        result = invoke("--format", "csv")

        assert result.exit_code == 0, result.output
        (row,) = list(csv.DictReader(io.StringIO(result.stdout)))
        assert row == {
            "Auth source": "environment variables FOUNDRY_HOST and FOUNDRY_TOKEN",
            "Auth type": "token",
            "Host": ENV_HOST,
            "Username": USER_JSON["username"],
            "Name": "Jane Doe",
            "Email": USER_JSON["email"],
            "User ID": USER_JSON["id"],
            "Organization": USER_JSON["organization"],
            "Realm": USER_JSON["realm"],
            "Status": "ACTIVE",
        }

    def test_output_file(self, fake_http, monkeypatch, tmp_path):
        env_token(monkeypatch)
        fake_http.route("GET", GET_CURRENT_USER_PATH, body=USER_JSON)
        target = tmp_path / "whoami.json"

        result = invoke("--format", "json", "--output", str(target))

        assert result.exit_code == 0, result.output
        assert result.stdout == ""
        assert json.loads(target.read_text())["user"]["id"] == USER_JSON["id"]


class TestVerifyFailure:
    def test_rejected_token_exits_3_with_structured_error(self, fake_http, monkeypatch):
        env_token(monkeypatch)
        fake_http.route(
            "GET",
            GET_CURRENT_USER_PATH,
            status=401,
            body=api_error("InvalidToken", "UNAUTHORIZED"),
        )

        result = invoke("--format", "json")

        assert result.exit_code == 3
        assert result.stdout == ""
        error = last_error(result)
        assert error["type"] == "auth_error"
        assert error["exitCode"] == 3
        assert error["statusCode"] == 401
        assert error["errorCode"] == "UNAUTHORIZED"
        assert error["errorName"] == "InvalidToken"
        assert error["message"] == (
            "Foundry rejected the credentials from environment variables "
            "FOUNDRY_HOST and FOUNDRY_TOKEN: InvalidToken"
        )

    def test_permission_denied_exits_4(self, fake_http, monkeypatch):
        env_token(monkeypatch)
        fake_http.route(
            "GET",
            GET_CURRENT_USER_PATH,
            status=403,
            body=api_error("GetCurrentUserPermissionDenied", "PERMISSION_DENIED"),
        )

        result = invoke()

        assert result.exit_code == 4
        assert "\nError: Foundry accepted the credentials" in result.stderr
        assert "api:admin-read" in result.stderr
        assert result.stdout == ""

    def test_permission_denied_json_error(self, fake_http, monkeypatch):
        env_token(monkeypatch)
        fake_http.route(
            "GET",
            GET_CURRENT_USER_PATH,
            status=403,
            body=api_error("GetCurrentUserPermissionDenied", "PERMISSION_DENIED"),
        )

        result = invoke("--format", "json")

        error = last_error(result)
        assert error["type"] == "permission_denied"
        assert error["exitCode"] == 4
        assert error["statusCode"] == 403
        assert error["errorName"] == "GetCurrentUserPermissionDenied"
        assert "api:admin-read" in error["message"]

    def test_rejected_oauth_client_credentials_exit_3(self, fake_http, monkeypatch):
        monkeypatch.setenv("FOUNDRY_HOST", ENV_HOST)
        monkeypatch.setenv("FOUNDRY_CLIENT_ID", "env-client")
        monkeypatch.setenv("FOUNDRY_CLIENT_SECRET", "wrong-secret")
        fake_http.route_oauth_token(status=401, body={"error": "invalid_client"})

        result = invoke()

        assert result.exit_code == 3
        assert "OAuth token request" in result.stderr
        assert "HTTP 401" in result.stderr
        assert "invalid_client" in result.stderr
        assert "Traceback" not in result.output

    def test_rejected_oauth_client_credentials_json(self, fake_http, monkeypatch):
        monkeypatch.setenv("FOUNDRY_HOST", ENV_HOST)
        monkeypatch.setenv("FOUNDRY_CLIENT_ID", "env-client")
        monkeypatch.setenv("FOUNDRY_CLIENT_SECRET", "wrong-secret")
        fake_http.route_oauth_token(status=401, body={"error": "invalid_client"})

        result = invoke("-f", "json")

        error = last_error(result)
        assert (error["type"], error["exitCode"]) == ("auth_error", 3)
        assert error["statusCode"] == 401
        assert "FOUNDRY_CLIENT_ID" in error["message"]

    def test_nothing_configured_exits_3(self, fake_http):
        result = invoke("--format", "json")

        assert result.exit_code == 3
        assert result.stdout == ""
        error = last_error(result)
        assert error["type"] == "auth_error"
        assert "FOUNDRY_HOST and FOUNDRY_TOKEN" in error["message"]
        assert fake_http.sdk_requests == []

    def test_missing_profile_exits_3(self, fake_keyring, fake_http):
        result = invoke("--profile", "nope")

        assert result.exit_code == 3
        assert "Profile 'nope' not found" in result.stderr
        assert "pltr configure configure --profile nope" in result.stderr

    def test_unknown_format_is_a_usage_error(self, fake_http, monkeypatch):
        env_token(monkeypatch)

        result = invoke("--format", "yaml")

        assert result.exit_code == 2
        assert fake_http.sdk_requests == []

    def test_invalid_pltr_format_is_a_usage_error_as_for_every_command(
        self, fake_http, monkeypatch
    ):
        env_token(monkeypatch)
        monkeypatch.setenv("PLTR_FORMAT", "yaml")

        result = invoke()

        assert result.exit_code == 2
        assert "PLTR_FORMAT" in result.stderr
        assert fake_http.sdk_requests == []

    def test_unreachable_host_exits_7(self, monkeypatch):
        import httpx

        env_token(monkeypatch)

        def refuse(client, request, **kwargs):
            raise httpx.ConnectError("connection refused", request=request)

        monkeypatch.setattr(httpx.Client, "send", refuse)

        result = invoke("--format", "json")

        assert result.exit_code == 7
        error = last_error(result)
        assert error["type"] == "network_error"
        assert f"Could not reach https://{ENV_HOST}" in error["message"]


class TestVerifyIsACommand:
    """verify is a plain command, not a group: its usage has no COMMAND, and an
    extra argument is a usage error ("No such command" before)."""

    def test_registered_as_a_command(self):
        import click
        import typer

        command = typer.main.get_command(app).commands["verify"]

        assert not isinstance(command, click.Group)
        assert command.short_help == "Verify authentication"

    def test_help_usage_has_no_subcommand(self):
        result = invoke("--help")

        assert result.exit_code == 0, result.output
        assert "Usage: pltr verify [OPTIONS]" in result.stdout
        assert "COMMAND" not in result.stdout
        assert "Reports which one it used." in result.stdout

    def test_an_extra_argument_is_a_json_usage_error(self, fake_http, monkeypatch):
        env_token(monkeypatch)

        result = invoke("foo", "--format", "json")

        assert result.exit_code == 2
        assert result.stdout == ""
        error = last_error(result)
        assert error["type"] == "usage_error"
        assert "unexpected extra argument (foo)" in error["message"]
        assert fake_http.sdk_requests == []


class TestVerifyFollowsTheCliContract:
    """The contract test's own checks (tests/test_contract/test_cli_contract.py).

    The shared stub_foundry_http fixture fakes AuthManager with an auth
    context that has no `source`, which verify reports, so here the real
    AuthManager resolves FOUNDRY_HOST/FOUNDRY_TOKEN and only HTTP is faked.
    """

    @pytest.fixture
    def contract_env(self, stub_foundry_http, isolated_home, monkeypatch):
        monkeypatch.setattr("pltr.services.base.AuthManager", AuthManager)
        monkeypatch.setenv("FOUNDRY_HOST", STUB_HOSTNAME)
        monkeypatch.setenv("FOUNDRY_TOKEN", STUB_TOKEN)
        return stub_foundry_http

    @pytest.mark.parametrize("status, code, name, error_type, exit_code", SCENARIOS)
    def test_api_errors_are_structured(
        self, contract_env, status, code, name, error_type, exit_code
    ):
        contract_env.respond_always(
            status,
            json={
                "errorCode": code,
                "errorName": name,
                "errorInstanceId": ERROR_INSTANCE_ID,
                "parameters": {},
            },
        )

        result = invoke("--format", "json")

        assert not error_problems(result, status, name, error_type, exit_code)
        [request] = contract_env.requests
        assert request.url.path == GET_CURRENT_USER_PATH
        assert request.headers["Authorization"] == f"Bearer {STUB_TOKEN}"

    def test_success_prints_exactly_one_json_document(self, contract_env):
        for response in CONTRACT_SUCCESS["verify"]:
            contract_env.respond(**response)

        result = invoke("--format", "json")

        assert result.exit_code == 0, result.stderr
        assert json.loads(result.stdout)["authSource"]["host"] == STUB_HOSTNAME
        assert all(line.get("type") == "warning" for line in stderr_json_lines(result))
