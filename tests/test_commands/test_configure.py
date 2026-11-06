"""
Tests for the configure command's credential storage paths.

Profiles keep their credentials in the system keyring. Where there is no usable
keyring, configure must fail fast with a clear error that points to
environment-variable auth, not a traceback or a hang.
"""

import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from pltr.config.profiles import ProfileManager
from tests.test_auth.fakes import FakeKeyring, broken_keyring

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


def test_configure_stores_credentials_in_the_keyring(config_dir, monkeypatch):
    keyring_fake = FakeKeyring().install(monkeypatch)

    result = CliRunner().invoke(
        app, ["configure", "configure", "--profile", "work", *TOKEN_ARGS]
    )

    assert result.exit_code == 0, result.output
    stored = json.loads(keyring_fake.passwords[("pltr-cli", "work")])
    assert stored == {
        "auth_type": "token",
        "host": "https://work.palantirfoundry.com",
        "token": "secret-token",
    }
    # The first profile becomes the default; profiles.json holds no secrets.
    assert ProfileManager().get_default() == "work"
    assert "secret-token" not in (config_dir / "profiles.json").read_text()


def test_configure_without_a_keyring_fails_fast_with_env_var_guidance(
    config_dir, monkeypatch
):
    broken_keyring(monkeypatch)

    result = CliRunner().invoke(
        app, ["configure", "configure", "--profile", "work", *TOKEN_ARGS]
    )

    assert result.exit_code == 3
    assert "could not read the credentials of profile 'work'" in result.stderr
    assert "set FOUNDRY_HOST and FOUNDRY_TOKEN" in result.stderr
    assert "Traceback" not in result.output
    # Nothing was half-configured
    assert not (config_dir / "profiles.json").exists()


def test_configure_save_failure_fails_with_env_var_guidance(config_dir, monkeypatch):
    keyring_fake = FakeKeyring().install(monkeypatch)

    def cannot_save(*args):
        raise RuntimeError("Keychain is locked")

    monkeypatch.setattr("keyring.set_password", cannot_save)

    result = CliRunner().invoke(
        app, ["configure", "configure", "--profile", "work", *TOKEN_ARGS]
    )

    assert result.exit_code == 3
    assert "could not save the credentials of profile 'work'" in result.stderr
    assert "Keychain is locked" in result.stderr
    assert "FOUNDRY_HOST" in result.stderr
    assert keyring_fake.passwords == {}
    assert not (config_dir / "profiles.json").exists()


def test_delete_without_a_keyring_fails_with_env_var_guidance(config_dir, monkeypatch):
    ProfileManager().add_profile("work")
    broken_keyring(monkeypatch)

    result = CliRunner().invoke(app, ["configure", "delete", "work", "--force"])

    assert result.exit_code == 3
    assert "could not delete the credentials of profile 'work'" in result.stderr
    assert "Traceback" not in result.output
    assert ProfileManager().list_profiles() == ["work"]
