"""The RID completion cache (~/.cache/pltr/recent_rids.json) is best-effort.

Commands call cache_rid after their API call succeeded and before printing
the result. A cache that can't be written (a read-only or missing home
directory, as in some containers and agent sandboxes) must not turn a
successful command, possibly a write, into a failure that invites a retry.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from pltr.utils.completion import cache_rid, get_cached_rids
from tests import foundry_json as fj

runner = CliRunner()

PARENT = "ri.compass.main.folder.00000000-0000-0000-0000-000000000002"
RID = "ri.foundry.main.dataset.00000000-0000-0000-0000-000000000003"


@pytest.fixture
def unusable_home(isolated_home, monkeypatch) -> Path:
    """A home directory below a regular file: creating ~/.cache fails on every OS."""
    blocker = isolated_home / "a-file"
    blocker.write_text("")
    home = blocker / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def cache_file(home: Path) -> Path:
    return home / ".cache" / "pltr" / "recent_rids.json"


def test_a_successful_write_succeeds_when_the_cache_cant_be_written(
    stub_foundry_http, unusable_home
):
    stub_foundry_http.respond(json=fj.folder())

    result = runner.invoke(
        app,
        ["folder", "create", "Reports", "--parent-folder", PARENT, "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    assert [request.method for request in stub_foundry_http.requests] == ["POST"]
    assert json.loads(result.stdout)["rid"] == fj.FOLDER_RID
    assert result.stderr == ""


def test_cache_rid_ignores_a_cache_directory_it_cant_create(unusable_home):
    cache_rid(RID)

    assert not cache_file(unusable_home).exists()


def test_cache_rid_ignores_a_missing_home_directory(monkeypatch):
    def no_home() -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", staticmethod(no_home))

    cache_rid(RID)
    assert RID not in get_cached_rids()


@pytest.mark.parametrize("content", ['{"rids": "not a list"}', "[1, 2]", "{not json"])
def test_cache_rid_replaces_a_corrupted_cache(isolated_home, content):
    path = cache_file(isolated_home)
    path.parent.mkdir(parents=True)
    path.write_text(content)

    cache_rid(RID)

    assert json.loads(path.read_text()) == {"rids": [RID]}


def test_cache_rid_puts_new_rids_first_without_duplicates(isolated_home):
    cache_rid("ri.a")
    cache_rid("ri.b")
    cache_rid("ri.a")

    assert get_cached_rids() == ["ri.b", "ri.a"]


def test_get_cached_rids_without_a_usable_cache_returns_examples(unusable_home):
    rids = get_cached_rids()

    assert rids and all(rid.startswith("ri.") for rid in rids)
