"""
Headless authentication (#190, #144).

- Precedence: --profile, then PLTR_PROFILE, then the default profile, then the
  FOUNDRY_* environment variables. An environment variable never overrides
  (or completes) a stored profile.
- Environment-variable auth needs no configuration directory and never
  touches the keyring.
- Direct-HTTP calls use the same auth object as the SDK client, so token,
  OAuth and environment-variable auth all send the right bearer token.
- A missing, broken or hanging keyring gives a clear error that points to the
  environment variables.
- Credentials lose surrounding whitespace (a trailing CR/LF); whitespace or
  control characters inside one are an auth error that never shows the value.

Only the network and the keyring are faked: AuthManager, FoundryClient and the
foundry_sdk auth objects (including the OAuth token request) are real.
"""

import json
import threading
import time
from typing import Any, Dict
from urllib.parse import parse_qs

import foundry_sdk
import keyring.errors
import pytest
import requests
from typer.testing import CliRunner

from pltr.auth.base import (
    InvalidCredentialsError,
    KeyringUnavailableError,
    MissingCredentialsError,
    ProfileNotFoundError,
)
from pltr.auth.manager import AuthManager, AuthSource
from pltr.auth.storage import DEFAULT_KEYRING_TIMEOUT, keyring_timeout
from pltr.cli import app
from pltr.config.profiles import ProfileManager
from pltr.services.base import BaseService
from pltr.services.language_models import LanguageModelsService

from .fakes import (
    GET_CURRENT_USER_PATH,
    OAUTH_ACCESS_TOKEN,
    OAUTH_TOKEN_PATH,
    USER_JSON,
    FakeFoundryHttp,
    FakeKeyring,
    broken_keyring,
    forbid_keyring,
)

ENV_VARS = [
    "PLTR_PROFILE",
    "FOUNDRY_HOST",
    "FOUNDRY_HOSTNAME",
    "FOUNDRY_TOKEN",
    "FOUNDRY_CLIENT_ID",
    "FOUNDRY_CLIENT_SECRET",
    "PLTR_KEYRING_TIMEOUT",
    "PLTR_FORMAT",
]

PROFILE_HOST = "profile.palantirfoundry.com"
ENV_HOST = "env.palantirfoundry.com"


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """No auth variables set; pltr's config directory doesn't exist yet."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path / "xdg-config" / "pltr"


@pytest.fixture
def fake_http(monkeypatch) -> FakeFoundryHttp:
    return FakeFoundryHttp().install(monkeypatch)


@pytest.fixture
def fake_keyring(monkeypatch) -> FakeKeyring:
    return FakeKeyring().install(monkeypatch)


@pytest.fixture
def no_keyring(monkeypatch):
    """Fail the test if anything touches the keyring or builds credential storage."""
    attempts = forbid_keyring(monkeypatch)

    def no_storage(*args: Any, **kwargs: Any) -> Any:
        attempts.append("CredentialStorage")
        raise AssertionError("CredentialStorage must not be created")

    monkeypatch.setattr("pltr.auth.manager.CredentialStorage", no_storage)
    return attempts


def token_profile(token: str, host: str = f"https://{PROFILE_HOST}") -> Dict[str, Any]:
    return {"auth_type": "token", "host": host, "token": token}


def oauth_profile(host: str = f"https://{PROFILE_HOST}") -> Dict[str, Any]:
    return {
        "auth_type": "oauth",
        "host": host,
        "client_id": "profile-client-id",
        "client_secret": "profile-client-secret",
    }


def add_profiles(keyring_fake: FakeKeyring, profiles: Dict[str, Dict], default=None):
    manager = ProfileManager()
    for name, credentials in profiles.items():
        keyring_fake.store(name, credentials)
        manager.add_profile(name)
    if default:
        manager.set_default(default)


def set_env_token(monkeypatch, token: str = "env-token", host: str = ENV_HOST):
    monkeypatch.setenv("FOUNDRY_HOST", host)
    monkeypatch.setenv("FOUNDRY_TOKEN", token)


def set_env_oauth(monkeypatch, host: str = ENV_HOST):
    monkeypatch.setenv("FOUNDRY_HOST", host)
    monkeypatch.setenv("FOUNDRY_CLIENT_ID", "env-client-id")
    monkeypatch.setenv("FOUNDRY_CLIENT_SECRET", "env-client-secret")


class DirectHttpService(BaseService):
    """A service using only BaseService's client and direct-HTTP helper."""

    def _get_service(self) -> Any:
        return self.client.admin


# ---------------------------------------------------------------------------
# Precedence
# ---------------------------------------------------------------------------


class TestPrecedence:
    """Each level beats the next; environment variables come last."""

    def test_profile_option_beats_pltr_profile(
        self, config_dir, fake_keyring, monkeypatch
    ):
        add_profiles(
            fake_keyring,
            {
                "flag": token_profile("flag-token"),
                "env-selected": token_profile("pltr-profile-token"),
                "default": token_profile("default-token"),
            },
            default="default",
        )
        monkeypatch.setenv("PLTR_PROFILE", "env-selected")
        set_env_token(monkeypatch)

        context = AuthManager().get_auth_context("flag")

        assert context.source == AuthSource(
            kind="profile",
            profile="flag",
            selected_by="--profile",
            auth_type="token",
            host=PROFILE_HOST,
        )
        assert context.get_token() == "flag-token"

    def test_pltr_profile_beats_default_profile(
        self, config_dir, fake_keyring, monkeypatch
    ):
        add_profiles(
            fake_keyring,
            {
                "env-selected": token_profile("pltr-profile-token"),
                "default": token_profile("default-token"),
            },
            default="default",
        )
        monkeypatch.setenv("PLTR_PROFILE", "env-selected")
        set_env_token(monkeypatch)

        context = AuthManager().get_auth_context()

        assert context.source.profile == "env-selected"
        assert context.source.selected_by == "PLTR_PROFILE"
        assert context.get_token() == "pltr-profile-token"

    def test_default_profile_beats_environment_variables(
        self, config_dir, fake_keyring, monkeypatch
    ):
        add_profiles(
            fake_keyring, {"work": token_profile("default-token")}, default="work"
        )
        set_env_token(monkeypatch)

        context = AuthManager().get_auth_context()

        assert context.source.kind == "profile"
        assert context.source.profile == "work"
        assert context.source.selected_by == "default"
        assert context.get_token() == "default-token"
        assert context.host == PROFILE_HOST

    def test_environment_variables_used_when_no_profile_is_selected(
        self, config_dir, no_keyring, monkeypatch
    ):
        set_env_token(monkeypatch, host=f"https://{ENV_HOST}/")

        context = AuthManager().get_auth_context()

        assert context.source == AuthSource(
            kind="environment",
            auth_type="token",
            host=ENV_HOST,
            variables=("FOUNDRY_HOST", "FOUNDRY_TOKEN"),
        )
        assert context.get_token() == "env-token"
        assert context.base_url == f"https://{ENV_HOST}"
        assert no_keyring == []

    def test_environment_never_fills_gaps_in_a_stored_profile(
        self, config_dir, fake_keyring, monkeypatch
    ):
        add_profiles(
            fake_keyring,
            {"broken": {"auth_type": "token", "host": f"https://{PROFILE_HOST}"}},
            default="broken",
        )
        set_env_token(monkeypatch)

        with pytest.raises(MissingCredentialsError, match="Token not found"):
            AuthManager().get_client()

    def test_pltr_profile_naming_a_missing_profile_does_not_fall_back(
        self, config_dir, fake_keyring, monkeypatch
    ):
        add_profiles(
            fake_keyring, {"work": token_profile("default-token")}, default="work"
        )
        monkeypatch.setenv("PLTR_PROFILE", "typo")
        set_env_token(monkeypatch)

        with pytest.raises(ProfileNotFoundError) as excinfo:
            AuthManager().get_client()

        message = str(excinfo.value)
        assert "Profile 'typo' not found (selected by PLTR_PROFILE)" in message
        assert "pltr configure configure --profile typo" in message

    def test_resolve_auth_source_reads_no_secrets(
        self, config_dir, fake_keyring, monkeypatch
    ):
        add_profiles(
            fake_keyring, {"work": token_profile("default-token")}, default="work"
        )
        set_env_token(monkeypatch)
        fake_keyring.calls.clear()

        source = AuthManager().resolve_auth_source()

        assert source == AuthSource(
            kind="profile", profile="work", selected_by="default"
        )
        assert fake_keyring.calls == []

    def test_get_current_profile_reports_pltr_profile(self, config_dir, monkeypatch):
        monkeypatch.setenv("PLTR_PROFILE", "staging")

        assert AuthManager().get_current_profile() == "staging"

    def test_get_current_profile_is_none_for_environment_auth(
        self, config_dir, monkeypatch
    ):
        set_env_token(monkeypatch)

        assert AuthManager().get_current_profile() is None


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------


class TestEnvironmentVariables:
    def test_oauth_client_credentials(self, config_dir, no_keyring, monkeypatch):
        set_env_oauth(monkeypatch)

        context = AuthManager().get_auth_context()

        assert context.source.auth_type == "oauth"
        assert context.source.variables == (
            "FOUNDRY_HOST",
            "FOUNDRY_CLIENT_ID",
            "FOUNDRY_CLIENT_SECRET",
        )
        assert context.source.describe() == (
            "environment variables FOUNDRY_HOST, FOUNDRY_CLIENT_ID and "
            "FOUNDRY_CLIENT_SECRET"
        )
        assert context.source.to_dict() == {
            "kind": "environment",
            "authType": "oauth",
            "host": ENV_HOST,
            "variables": [
                "FOUNDRY_HOST",
                "FOUNDRY_CLIENT_ID",
                "FOUNDRY_CLIENT_SECRET",
            ],
        }
        assert isinstance(context.auth, foundry_sdk.ConfidentialClientAuth)

    def test_token_wins_over_client_credentials(self, config_dir, monkeypatch):
        set_env_oauth(monkeypatch)
        monkeypatch.setenv("FOUNDRY_TOKEN", "env-token")

        source = AuthManager().resolve_auth_source()

        assert source.auth_type == "token"
        assert source.variables == ("FOUNDRY_HOST", "FOUNDRY_TOKEN")

    def test_foundry_hostname_is_accepted(self, config_dir, monkeypatch):
        monkeypatch.setenv("FOUNDRY_HOSTNAME", ENV_HOST)
        monkeypatch.setenv("FOUNDRY_TOKEN", "env-token")

        source = AuthManager().resolve_auth_source()

        assert source.host == ENV_HOST
        assert source.variables == ("FOUNDRY_HOSTNAME", "FOUNDRY_TOKEN")

    @pytest.mark.parametrize(
        "host",
        [
            ENV_HOST,
            f"{ENV_HOST}/",
            f"https://{ENV_HOST}",
            f"https://{ENV_HOST}/",
            f"  https://{ENV_HOST}  ",
        ],
    )
    def test_hosts_are_normalised_like_profiles(
        self, config_dir, fake_keyring, fake_http, monkeypatch, host
    ):
        set_env_token(monkeypatch, host=host)
        fake_http.route("GET", "/api/v2/some/endpoint", body={})

        DirectHttpService()._make_request("GET", "/api/v2/some/endpoint")
        env_url = fake_http.direct_requests[-1]["url"]

        # The same host stored in a profile ends up at the same URL.
        monkeypatch.delenv("FOUNDRY_HOST")
        monkeypatch.delenv("FOUNDRY_TOKEN")
        add_profiles(fake_keyring, {"p": token_profile("t", host=host)}, default="p")
        DirectHttpService()._make_request("GET", "/api/v2/some/endpoint")

        assert env_url == f"https://{ENV_HOST}/api/v2/some/endpoint"
        assert fake_http.direct_requests[-1]["url"] == env_url

    @pytest.mark.parametrize(
        "variables, message",
        [
            ({"FOUNDRY_TOKEN": "t"}, "FOUNDRY_TOKEN is set but FOUNDRY_HOST is not"),
            (
                {"FOUNDRY_CLIENT_ID": "i", "FOUNDRY_CLIENT_SECRET": "s"},
                "FOUNDRY_CLIENT_ID and FOUNDRY_CLIENT_SECRET are set but "
                "FOUNDRY_HOST is not",
            ),
            (
                {"FOUNDRY_HOST": ENV_HOST},
                "FOUNDRY_HOST is set but no credentials are",
            ),
            (
                {"FOUNDRY_HOST": ENV_HOST, "FOUNDRY_CLIENT_ID": "i"},
                "FOUNDRY_CLIENT_ID is set but FOUNDRY_CLIENT_SECRET is not",
            ),
            (
                {"FOUNDRY_HOST": ENV_HOST, "FOUNDRY_CLIENT_SECRET": "s"},
                "FOUNDRY_CLIENT_SECRET is set but FOUNDRY_CLIENT_ID is not",
            ),
            (
                {"FOUNDRY_HOST": "https://", "FOUNDRY_TOKEN": "t"},
                "does not contain a host name",
            ),
        ],
    )
    def test_incomplete_variables_name_what_is_missing(
        self, config_dir, monkeypatch, variables, message
    ):
        for name, value in variables.items():
            monkeypatch.setenv(name, value)

        with pytest.raises(MissingCredentialsError, match=message):
            AuthManager().get_client()

    def test_nothing_configured(self, config_dir, no_keyring):
        with pytest.raises(ProfileNotFoundError) as excinfo:
            AuthManager().get_client()

        message = str(excinfo.value)
        assert "pltr configure configure" in message
        assert "FOUNDRY_HOST and FOUNDRY_TOKEN" in message
        assert "FOUNDRY_CLIENT_ID and FOUNDRY_CLIENT_SECRET" in message


# ---------------------------------------------------------------------------
# Commands with environment variables only: no config dir, no keyring
# ---------------------------------------------------------------------------


class TestHeadlessCommands:
    @pytest.mark.filterwarnings("error::UserWarning")
    def test_sdk_command_with_env_token(
        self, config_dir, no_keyring, fake_http, monkeypatch
    ):
        set_env_token(monkeypatch)
        fake_http.route("GET", GET_CURRENT_USER_PATH, body=USER_JSON)

        result = CliRunner().invoke(app, ["verify", "--format", "json"])

        assert result.exit_code == 0, result.output
        request = fake_http.sdk_request(GET_CURRENT_USER_PATH)
        assert request.url.host == ENV_HOST
        assert request.headers["Authorization"] == "Bearer env-token"
        assert no_keyring == []
        assert not config_dir.exists()

    @pytest.mark.filterwarnings("error::UserWarning")
    def test_direct_http_command_with_env_oauth(
        self, config_dir, no_keyring, fake_http, monkeypatch
    ):
        set_env_oauth(monkeypatch)
        fake_http.route_oauth_token()
        # `language-models enroll` is one of the labeled direct-HTTP commands
        endpoint = LanguageModelsService._MODEL_ENROLL_ENDPOINTS[0].format(
            model_id="claude"
        )
        fake_http.route(
            "POST",
            endpoint,
            body={"rid": "ri.language-model.main.model.claude", "status": "ENROLLED"},
        )

        result = CliRunner().invoke(app, ["language-models", "enroll", "claude"])

        assert result.exit_code == 0, result.output
        (direct,) = fake_http.direct_requests
        assert direct["url"] == f"https://{ENV_HOST}{endpoint}"
        assert direct["headers"]["Authorization"] == f"Bearer {OAUTH_ACCESS_TOKEN}"
        token_request = fake_http.sdk_request(OAUTH_TOKEN_PATH)
        form = parse_qs(token_request.content.decode())
        assert form["grant_type"] == ["client_credentials"]
        assert form["client_id"] == ["env-client-id"]
        assert no_keyring == []
        assert not config_dir.exists()


# ---------------------------------------------------------------------------
# Direct-HTTP calls use the SDK client's auth
# ---------------------------------------------------------------------------


class TestDirectHttpAuth:
    @pytest.mark.filterwarnings("error::UserWarning")
    def test_token_profile(self, config_dir, fake_keyring, fake_http):
        add_profiles(fake_keyring, {"p": token_profile("profile-token")}, default="p")
        fake_http.route("POST", "/foundry-schema-inference/api/x", body={"ok": True})

        response = DirectHttpService()._make_request(
            "POST", "/foundry-schema-inference/api/x", json_data={"a": 1}
        )

        (direct,) = fake_http.direct_requests
        assert direct["method"] == "POST"
        assert direct["url"] == f"https://{PROFILE_HOST}/foundry-schema-inference/api/x"
        assert direct["headers"]["Authorization"] == "Bearer profile-token"
        assert direct["json"] == {"a": 1}
        assert response.json() == {"ok": True}

    @pytest.mark.filterwarnings("error::UserWarning")
    def test_oauth_profile_sends_the_oauth_access_token(
        self, config_dir, fake_keyring, fake_http
    ):
        add_profiles(fake_keyring, {"p": oauth_profile()}, default="p")
        fake_http.route_oauth_token()
        fake_http.route("GET", "/api/v2/llm/x", body={})

        DirectHttpService(profile="p")._make_request("GET", "/api/v2/llm/x")

        (direct,) = fake_http.direct_requests
        assert direct["headers"]["Authorization"] == f"Bearer {OAUTH_ACCESS_TOKEN}"
        assert "None" not in direct["headers"]["Authorization"]
        token_request = fake_http.sdk_request(OAUTH_TOKEN_PATH)
        assert token_request.url.host == PROFILE_HOST
        form = parse_qs(token_request.content.decode())
        assert form["client_id"] == ["profile-client-id"]

    @pytest.mark.filterwarnings("error::UserWarning")
    def test_env_token(self, config_dir, no_keyring, fake_http, monkeypatch):
        set_env_token(monkeypatch)
        fake_http.route("GET", "/api/v2/llm/x", body={})

        DirectHttpService()._make_request("GET", "/api/v2/llm/x")

        (direct,) = fake_http.direct_requests
        assert direct["url"] == f"https://{ENV_HOST}/api/v2/llm/x"
        assert direct["headers"]["Authorization"] == "Bearer env-token"

    @pytest.mark.filterwarnings("error::UserWarning")
    def test_env_oauth(self, config_dir, no_keyring, fake_http, monkeypatch):
        set_env_oauth(monkeypatch)
        fake_http.route_oauth_token()
        fake_http.route("GET", "/api/v2/llm/x", body={})

        DirectHttpService()._make_request("GET", "/api/v2/llm/x")

        (direct,) = fake_http.direct_requests
        assert direct["headers"]["Authorization"] == f"Bearer {OAUTH_ACCESS_TOKEN}"

    @pytest.mark.filterwarnings("error::UserWarning")
    def test_sdk_client_and_direct_calls_share_one_oauth_token(
        self, config_dir, no_keyring, fake_http, monkeypatch
    ):
        set_env_oauth(monkeypatch)
        fake_http.route_oauth_token()
        fake_http.route("GET", GET_CURRENT_USER_PATH, body=USER_JSON)
        fake_http.route("GET", "/api/v2/llm/x", body={})
        service = DirectHttpService()

        service.client.admin.User.get_current()
        service._make_request("GET", "/api/v2/llm/x")

        token_requests = [
            r for r in fake_http.sdk_requests if r.url.path == OAUTH_TOKEN_PATH
        ]
        assert len(token_requests) == 1
        sdk_call = fake_http.sdk_request(GET_CURRENT_USER_PATH)
        (direct,) = fake_http.direct_requests
        assert (
            sdk_call.headers["Authorization"]
            == direct["headers"]["Authorization"]
            == f"Bearer {OAUTH_ACCESS_TOKEN}"
        )

    def test_http_errors_still_raise_requests_http_error(
        self, config_dir, fake_http, monkeypatch
    ):
        set_env_token(monkeypatch)
        fake_http.route("GET", "/api/v2/llm/x", status=404, body={"errorCode": "X"})

        with pytest.raises(requests.HTTPError):
            DirectHttpService()._make_request("GET", "/api/v2/llm/x")

    def test_rejected_oauth_credentials_raise_an_auth_error(
        self, config_dir, fake_http, monkeypatch
    ):
        set_env_oauth(monkeypatch)
        fake_http.route_oauth_token(status=401, body={"error": "invalid_client"})

        with pytest.raises(InvalidCredentialsError, match="HTTP 401"):
            DirectHttpService()._make_request("GET", "/api/v2/llm/x")
        assert fake_http.direct_requests == []


# ---------------------------------------------------------------------------
# Keyring failures
# ---------------------------------------------------------------------------


class TestKeyringFailures:
    def test_missing_backend_gives_a_clear_error(self, config_dir, monkeypatch):
        add_profiles(FakeKeyring(), {"work": token_profile("t")}, default="work")
        broken_keyring(monkeypatch)
        set_env_token(monkeypatch)

        with pytest.raises(KeyringUnavailableError) as excinfo:
            AuthManager().get_client()

        message = str(excinfo.value)
        assert "could not read the credentials of profile 'work'" in message
        assert "No recommended backend was available." in message
        assert "FOUNDRY_HOST and FOUNDRY_TOKEN" in message
        assert "'work' is the default profile" in message
        assert str(config_dir / "profiles.json") in message
        assert isinstance(
            excinfo.value.__cause__.__cause__, keyring.errors.KeyringError
        )

    def test_missing_backend_in_a_command_exits_3_without_traceback(
        self, config_dir, monkeypatch
    ):
        add_profiles(FakeKeyring(), {"work": token_profile("t")}, default="work")
        broken_keyring(monkeypatch)

        result = CliRunner().invoke(app, ["verify"])

        assert result.exit_code == 3
        assert "FOUNDRY_HOST and FOUNDRY_TOKEN" in result.stderr
        assert "Traceback" not in result.output
        assert result.stdout == ""

    def test_hanging_keyring_times_out(self, config_dir, monkeypatch):
        add_profiles(FakeKeyring(), {"work": token_profile("t")}, default="work")
        release = threading.Event()

        def hang(*args: Any) -> None:
            release.wait(10)

        monkeypatch.setattr(keyring, "get_password", hang)
        monkeypatch.setenv("PLTR_KEYRING_TIMEOUT", "0.2")

        started = time.monotonic()
        try:
            with pytest.raises(
                KeyringUnavailableError, match="did not answer within 0.2 seconds"
            ):
                AuthManager().get_client()
        finally:
            release.set()
        assert time.monotonic() - started < 5

    @pytest.mark.parametrize(
        "value, expected",
        [
            (None, DEFAULT_KEYRING_TIMEOUT),
            ("", DEFAULT_KEYRING_TIMEOUT),
            ("5", 5.0),
            ("0.5", 0.5),
            ("0", None),
            ("-1", None),
            ("soon", DEFAULT_KEYRING_TIMEOUT),
        ],
    )
    def test_keyring_timeout_setting(self, monkeypatch, value, expected):
        if value is None:
            monkeypatch.delenv("PLTR_KEYRING_TIMEOUT", raising=False)
        else:
            monkeypatch.setenv("PLTR_KEYRING_TIMEOUT", value)

        assert keyring_timeout() == expected


# ---------------------------------------------------------------------------
# Credentials with whitespace or control characters
# ---------------------------------------------------------------------------

#: A secret that must never appear in an error message.
SECRET = "PltrTestSecret123"


class TestCredentialWhitespace:
    """`--token "$(cat token.txt)"` on a file with Windows line endings stores
    the token with a trailing CR. Surrounding whitespace is stripped wherever
    credentials are read; whitespace or control characters inside one are an
    auth error that says where the credential came from, never its value."""

    @pytest.mark.filterwarnings("error::UserWarning")
    def test_stored_token_with_a_trailing_line_break_works(
        self, config_dir, fake_keyring, fake_http
    ):
        add_profiles(fake_keyring, {"p": token_profile(" profile-token\r\n")}, "p")
        fake_http.route("GET", GET_CURRENT_USER_PATH, body=USER_JSON)

        result = CliRunner().invoke(app, ["verify", "--format", "json"])

        assert result.exit_code == 0, result.output
        request = fake_http.sdk_request(GET_CURRENT_USER_PATH)
        assert request.headers["Authorization"] == "Bearer profile-token"

    @pytest.mark.filterwarnings("error::UserWarning")
    def test_stored_oauth_credentials_with_line_breaks_work(
        self, config_dir, fake_keyring, fake_http
    ):
        profile = {
            **oauth_profile(),
            "client_id": "profile-client-id\r",
            "client_secret": "profile-client-secret\r\n",
        }
        add_profiles(fake_keyring, {"p": profile}, default="p")
        fake_http.route_oauth_token()
        fake_http.route("GET", "/api/v2/llm/x", body={})

        DirectHttpService()._make_request("GET", "/api/v2/llm/x")

        form = parse_qs(fake_http.sdk_request(OAUTH_TOKEN_PATH).content.decode())
        assert form["client_id"] == ["profile-client-id"]
        assert form["client_secret"] == ["profile-client-secret"]

    @pytest.mark.parametrize(
        "field, label",
        [
            ("token", "token"),
            ("client_id", "OAuth client ID"),
            ("client_secret", "OAuth client secret"),
        ],
    )
    @pytest.mark.parametrize("inner", ["\r\n", " ", "\t", "\x1b"])
    def test_stored_credential_with_inner_whitespace_is_rejected(
        self, config_dir, fake_keyring, field, label, inner
    ):
        profile = token_profile("t") if field == "token" else oauth_profile()
        profile[field] = f"{SECRET}{inner}{SECRET}"
        add_profiles(fake_keyring, {"work": profile}, default="work")

        with pytest.raises(InvalidCredentialsError) as excinfo:
            AuthManager().get_client()

        message = str(excinfo.value)
        assert f"The {label} stored in profile 'work'" in message
        assert "whitespace or control characters" in message
        assert "pltr configure configure --profile work" in message
        assert SECRET not in message

    @pytest.mark.filterwarnings("error::UserWarning")
    def test_env_token_with_a_trailing_line_break_works(
        self, config_dir, no_keyring, fake_http, monkeypatch
    ):
        set_env_token(monkeypatch, token="env-token\r\n")
        fake_http.route("GET", GET_CURRENT_USER_PATH, body=USER_JSON)

        result = CliRunner().invoke(app, ["verify", "--format", "json"])

        assert result.exit_code == 0, result.output
        request = fake_http.sdk_request(GET_CURRENT_USER_PATH)
        assert request.headers["Authorization"] == "Bearer env-token"

    @pytest.mark.parametrize(
        "variable", ["FOUNDRY_TOKEN", "FOUNDRY_CLIENT_ID", "FOUNDRY_CLIENT_SECRET"]
    )
    @pytest.mark.parametrize("inner", ["\r\n", " ", "\x1b"])
    def test_env_credential_with_inner_whitespace_is_rejected(
        self, config_dir, no_keyring, monkeypatch, variable, inner
    ):
        if variable == "FOUNDRY_TOKEN":
            set_env_token(monkeypatch)
        else:
            set_env_oauth(monkeypatch)
        monkeypatch.setenv(variable, f"{SECRET}{inner}{SECRET}")

        with pytest.raises(InvalidCredentialsError) as excinfo:
            AuthManager().get_client()

        message = str(excinfo.value)
        assert f"{variable} contains whitespace or control characters" in message
        assert SECRET not in message

    def test_an_unused_variable_is_not_checked(self, config_dir, monkeypatch):
        # FOUNDRY_TOKEN wins over client credentials, which are then ignored.
        set_env_token(monkeypatch)
        monkeypatch.setenv("FOUNDRY_CLIENT_SECRET", "not used\n at all")

        assert AuthManager().get_auth_context().source.auth_type == "token"

    def test_a_command_fails_with_an_auth_error_without_the_value(
        self, config_dir, fake_keyring, fake_http
    ):
        add_profiles(fake_keyring, {"p": token_profile(f"{SECRET}\n{SECRET}")}, "p")

        result = CliRunner().invoke(
            app, ["folder", "get", "ri.compass.main.folder.x", "--format", "json"]
        )

        assert result.exit_code == 3, result.output
        assert result.stdout == ""
        error = json.loads(result.stderr.strip().splitlines()[-1])
        assert error["type"] == "auth_error"
        assert "The token stored in profile 'p'" in error["message"]
        assert SECRET not in result.stderr
        assert fake_http.sdk_requests == []
