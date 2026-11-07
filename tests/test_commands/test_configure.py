"""
Tests for the profile commands (`pltr configure ...`).

Profiles keep their credentials in the system keyring. Where there is no
usable keyring, configure must fail fast with a clear error that points to
environment-variable auth, not a traceback or a hang. Nothing is ever
prompted when stdin is not a terminal (CliRunner's stdin isn't one): missing
values are a usage error (exit 2), and replacing or deleting a profile needs
--yes. Prompts, when stdin is a terminal, go to stderr.
"""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from pltr.config.profiles import ProfileManager
from tests.test_auth.fakes import FakeKeyring, broken_keyring, forbid_keyring

TOKEN_ARGS = [
    "--auth-type",
    "token",
    "--host",
    "https://work.palantirfoundry.com",
    "--token",
    "secret-token",
]


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("PLTR_PROFILE", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    return tmp_path / "xdg-config" / "pltr"


@pytest.fixture
def keyring_fake(monkeypatch) -> FakeKeyring:
    return FakeKeyring().install(monkeypatch)


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal; hidden prompts read the next input line."""
    monkeypatch.setattr("pltr.commands.configure.stdin_is_interactive", lambda: True)
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)

    def getpass(prompt="", stream=None):
        import sys

        return sys.stdin.readline().rstrip("\n")

    monkeypatch.setattr("rich.console.getpass", getpass)


def invoke(*args: str, **kwargs):
    return CliRunner().invoke(app, ["configure", *args], **kwargs)


def stored(keyring_fake: FakeKeyring, profile: str) -> dict:
    return json.loads(keyring_fake.passwords[("pltr-cli", profile)])


def add_profile(keyring_fake: FakeKeyring, name: str) -> None:
    keyring_fake.store(name, {"auth_type": "token", "host": "h", "token": "t"})
    ProfileManager().add_profile(name)


def last_json_line(stderr: str) -> dict:
    return json.loads(stderr.strip().splitlines()[-1])


# -------------------------------------------------------------- configure


def test_configure_stores_credentials_in_the_keyring(config_dir, keyring_fake):
    result = invoke("configure", "--profile", "work", *TOKEN_ARGS)

    assert result.exit_code == 0, result.output
    assert stored(keyring_fake, "work") == {
        "auth_type": "token",
        "host": "https://work.palantirfoundry.com",
        "token": "secret-token",
    }
    # The first profile becomes the default; profiles.json holds no secrets.
    assert ProfileManager().get_default() == "work"
    assert "secret-token" not in (config_dir / "profiles.json").read_text()
    assert result.stdout == ""
    assert "Profile 'work' configured successfully and set as default" in result.stderr


def test_configure_json_prints_null(config_dir, keyring_fake):
    result = invoke("configure", "-p", "work", *TOKEN_ARGS, "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    assert result.stderr == ""


def test_configure_implies_the_auth_type_from_the_credentials(config_dir, keyring_fake):
    token = invoke("configure", "-p", "a", "--host", "h", "--token", "t")
    oauth = invoke(
        "configure",
        "-p",
        "b",
        "--host",
        "h",
        "--client-id",
        "cid",
        "--client-secret",
        "secret",
    )

    assert (token.exit_code, oauth.exit_code) == (0, 0), token.output + oauth.output
    assert stored(keyring_fake, "a")["auth_type"] == "token"
    assert stored(keyring_fake, "b") == {
        "auth_type": "oauth",
        "host": "h",
        "client_id": "cid",
        "client_secret": "secret",
    }
    # Only the first profile becomes the default
    assert ProfileManager().get_default() == "a"


def test_configure_without_a_terminal_requires_every_value(config_dir, monkeypatch):
    attempts = forbid_keyring(monkeypatch)

    result = invoke("configure", "--profile", "work", "--host", "h", "-f", "json")

    assert result.exit_code == 2
    assert result.stdout == ""
    error = last_json_line(result.stderr)
    assert error["type"] == "usage_error"
    assert "missing --token (or --client-id and --client-secret)" in error["message"]
    assert "stdin is not a terminal" in error["message"]
    assert attempts == []  # failed before touching the keyring


def test_configure_without_a_terminal_names_the_missing_oauth_values(config_dir):
    result = invoke("configure", "--auth-type", "oauth", "--client-id", "cid")

    assert result.exit_code == 2
    assert "missing --host, --client-secret" in result.stderr


def test_configure_rejects_an_unknown_auth_type(config_dir):
    result = invoke("configure", "--auth-type", "password", "--host", "h", "-f", "json")

    assert result.exit_code == 2
    error = last_json_line(result.stderr)
    assert error["type"] == "usage_error"
    assert "'password' is not one of 'token', 'oauth'" in error["message"]


def test_configure_rejects_credentials_of_the_other_auth_type(config_dir):
    result = invoke(
        "configure", "--auth-type", "token", "--client-id", "x", "-f", "json"
    )

    assert result.exit_code == 2
    error = last_json_line(result.stderr)
    assert (
        "--client-id and --client-secret are for --auth-type oauth"
        in (error["message"])
    )


def test_replacing_a_profile_needs_yes_without_a_terminal(config_dir, keyring_fake):
    add_profile(keyring_fake, "work")

    refused = invoke("configure", "-p", "work", *TOKEN_ARGS, "-f", "json")
    replaced = invoke("configure", "-p", "work", *TOKEN_ARGS, "--yes")

    assert refused.exit_code == 2
    error = last_json_line(refused.stderr)
    assert error["type"] == "confirmation_required"
    assert "Profile 'work' already exists" in error["message"]
    assert replaced.exit_code == 0, replaced.output
    assert stored(keyring_fake, "work")["token"] == "secret-token"


def test_configure_prompts_on_stderr_for_missing_values(
    config_dir, keyring_fake, interactive
):
    result = invoke(
        "configure",
        "--profile",
        "work",
        input="token\nhttps://work.palantirfoundry.com\nsecret-token\n",
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Authentication type [token/oauth]" in result.stderr
    assert "Foundry host" in result.stderr
    assert "Bearer token" in result.stderr
    assert stored(keyring_fake, "work") == {
        "auth_type": "token",
        "host": "https://work.palantirfoundry.com",
        "token": "secret-token",
    }


def test_configure_asks_before_replacing_a_profile(
    config_dir, keyring_fake, interactive
):
    add_profile(keyring_fake, "work")

    result = invoke("configure", "-p", "work", *TOKEN_ARGS, input="n\n")

    assert result.exit_code == 1
    assert "Profile 'work' already exists. Replace its credentials? [y/N]" in (
        result.stderr
    )
    assert "Aborted" in result.stderr
    assert stored(keyring_fake, "work")["token"] == "t"  # unchanged


def test_configure_without_a_keyring_fails_fast_with_env_var_guidance(
    config_dir, monkeypatch
):
    broken_keyring(monkeypatch)

    result = invoke("configure", "--profile", "work", *TOKEN_ARGS)

    assert result.exit_code == 3
    assert "could not read the credentials of profile 'work'" in result.stderr
    assert "set FOUNDRY_HOST and FOUNDRY_TOKEN" in result.stderr
    assert "Traceback" not in result.output
    # Nothing was half-configured
    assert not (config_dir / "profiles.json").exists()


def test_configure_without_a_keyring_json_error(config_dir, monkeypatch):
    broken_keyring(monkeypatch)

    result = invoke("configure", "--profile", "work", *TOKEN_ARGS, "-f", "json")

    assert result.exit_code == 3
    error = last_json_line(result.stderr)
    assert (error["type"], error["exitCode"]) == ("auth_error", 3)


def test_configure_save_failure_fails_with_env_var_guidance(config_dir, monkeypatch):
    keyring_fake = FakeKeyring().install(monkeypatch)

    def cannot_save(*args):
        raise RuntimeError("Keychain is locked")

    monkeypatch.setattr("keyring.set_password", cannot_save)

    result = invoke("configure", "--profile", "work", *TOKEN_ARGS)

    assert result.exit_code == 3
    assert "could not save the credentials of profile 'work'" in result.stderr
    assert "Keychain is locked" in result.stderr
    assert "FOUNDRY_HOST" in result.stderr
    assert keyring_fake.passwords == {}
    assert not (config_dir / "profiles.json").exists()


# ---------------------------------------------------------- list-profiles


def test_list_profiles_table_json_and_csv(config_dir, keyring_fake):
    add_profile(keyring_fake, "work")
    add_profile(keyring_fake, "staging")
    ProfileManager().set_default("work")

    table = invoke("list-profiles")
    as_json = invoke("list-profiles", "--format", "json")
    as_csv = invoke("list-profiles", "--format", "csv")

    assert table.exit_code == 0, table.output
    assert "work" in table.stdout and "staging" in table.stdout
    assert json.loads(as_json.stdout) == {
        "data": [
            {"name": "work", "default": True},
            {"name": "staging", "default": False},
        ]
    }
    assert list(csv.DictReader(io.StringIO(as_csv.stdout))) == [
        {"Profile": "work", "Default": "true"},
        {"Profile": "staging", "Default": "false"},
    ]
    assert keyring_fake.calls == []  # the list never touches the keyring


def test_list_profiles_when_none_is_configured(config_dir):
    table = invoke("list-profiles")
    as_json = invoke("list-profiles", "-f", "json")

    assert table.exit_code == 0
    assert table.stdout == ""
    assert "No profiles configured" in table.stderr
    assert "FOUNDRY_HOST and FOUNDRY_TOKEN" in table.stderr
    assert json.loads(as_json.stdout) == {"data": []}
    assert as_json.stderr == ""


# ------------------------------------------------------------ set-default


def test_set_default(config_dir, keyring_fake):
    add_profile(keyring_fake, "work")
    add_profile(keyring_fake, "staging")

    result = invoke("set-default", "staging")

    assert result.exit_code == 0, result.output
    assert ProfileManager().get_default() == "staging"
    assert "Profile 'staging' set as default" in result.stderr


def test_set_default_unknown_profile_is_not_found(config_dir, keyring_fake):
    add_profile(keyring_fake, "work")

    result = invoke("set-default", "nope", "--format", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = last_json_line(result.stderr)
    assert error["type"] == "not_found"
    assert error["message"] == "Profile 'nope' not found. Configured profiles: work."


# ----------------------------------------------------------------- delete


def test_delete_needs_yes_without_a_terminal(config_dir, keyring_fake):
    add_profile(keyring_fake, "work")

    result = invoke("delete", "work", "--format", "json")

    assert result.exit_code == 2
    assert last_json_line(result.stderr)["type"] == "confirmation_required"
    assert ProfileManager().list_profiles() == ["work"]
    assert ("pltr-cli", "work") in keyring_fake.passwords


def test_delete_with_yes_removes_credentials_and_profile(config_dir, keyring_fake):
    add_profile(keyring_fake, "work")
    add_profile(keyring_fake, "staging")
    ProfileManager().set_default("work")

    result = invoke("delete", "work", "-y")

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Deleted profile 'work'" in result.stderr
    assert "The default profile is now 'staging'" in result.stderr
    assert ProfileManager().list_profiles() == ["staging"]
    assert ("pltr-cli", "work") not in keyring_fake.passwords


def test_delete_short_f_is_now_format(config_dir, keyring_fake):
    add_profile(keyring_fake, "work")

    result = invoke("delete", "work", "--yes", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    assert result.stderr == ""


def test_delete_force_is_a_deprecated_alias_for_yes(config_dir, keyring_fake):
    add_profile(keyring_fake, "work")

    result = invoke("delete", "work", "--force")

    assert result.exit_code == 0, result.output
    assert "--force is deprecated" in result.stderr
    assert ProfileManager().list_profiles() == []


def test_delete_asks_when_interactive(config_dir, keyring_fake, interactive):
    add_profile(keyring_fake, "work")

    result = invoke("delete", "work", input="y\n")

    assert result.exit_code == 0, result.output
    assert "Delete profile 'work' and its credentials? [y/N]" in result.stderr
    assert ProfileManager().list_profiles() == []


def test_delete_removes_a_profile_whose_credentials_are_gone(config_dir, keyring_fake):
    ProfileManager().add_profile("orphan")  # in profiles.json, not in the keyring

    result = invoke("delete", "orphan", "--yes")

    assert result.exit_code == 0, result.output
    assert "held no credentials for profile 'orphan'" in result.stderr
    assert ProfileManager().list_profiles() == []


def test_delete_unknown_profile_is_not_found(config_dir, keyring_fake):
    result = invoke("delete", "nope", "--yes")

    assert result.exit_code == 5
    assert "Profile 'nope' not found. None is configured." in result.stderr


def test_delete_without_a_keyring_fails_with_env_var_guidance(config_dir, monkeypatch):
    ProfileManager().add_profile("work")
    broken_keyring(monkeypatch)

    result = invoke("delete", "work", "--yes")

    assert result.exit_code == 3
    assert "could not delete the credentials of profile 'work'" in result.stderr
    assert "Traceback" not in result.output
    assert ProfileManager().list_profiles() == ["work"]
