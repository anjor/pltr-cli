"""The command manifest: coverage, determinism and the shape of each entry."""

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click
import pytest
import typer
from typing_extensions import Annotated

from pltr import __version__
from pltr.cli import app
from pltr.commands.api import _specs
from pltr.contract import (
    FormatOption,
    resource_argument,
    resource_option,
    YesOption,
    get_command_meta,
    iter_commands,
    pltr_command,
)
from pltr.contract.serialize import to_document
from pltr.manifest import LOCAL_GROUPS, build_manifest
from tests.test_contract.cases import load_cases

#: Keys of a command entry, in order, for a command with metadata.
ENTRY_KEYS = [
    "path",
    "usage",
    "description",
    "beta",
    "destructive",
    "paged",
    "generated",
    "local",
    "hidden",
    "outputFormats",
    "sdkMethods",
    "arguments",
    "options",
    "help",
]


def option(entry, name):
    return next(o for o in entry["options"] if o["name"] == name)


# ------------------------------------------------------------- the document


def test_top_level_document(manifest):
    assert list(manifest) == ["pltrVersion", "sdkVersion", "groups", "commands"]
    assert manifest["pltrVersion"] == __version__
    # The locked SDK version the `pltr api` tree was generated from, not the
    # installed one, so the manifest doesn't change with an SDK patch install.
    assert manifest["sdkVersion"] == _specs.SDK_VERSION


def test_manifest_covers_every_command(manifest):
    expected = sorted(f"pltr {e.path}" for e in iter_commands(app))
    paths = [entry["path"] for entry in manifest["commands"]]
    assert sorted(paths) == expected
    assert len(paths) == len(set(paths))
    assert sum(1 for e in manifest["commands"] if e["generated"]) == 390
    assert {"pltr commands list", "pltr commands search", "pltr commands show"} <= set(
        paths
    )


def test_commands_and_groups_are_sorted_by_path(manifest):
    for key in ("commands", "groups"):
        paths = [entry["path"].split() for entry in manifest[key]]
        assert paths == sorted(paths), key


def test_manifest_is_deterministic(manifest):
    again = build_manifest()
    assert again == manifest
    assert json.dumps(again, sort_keys=False) == json.dumps(manifest, sort_keys=False)


def test_manifest_doesnt_depend_on_the_environment(manifest, tmp_path):
    """Another process, home, terminal width, locale and hash seed: same bytes."""
    env = dict(os.environ)
    env.update(
        HOME=str(tmp_path),
        XDG_CONFIG_HOME=str(tmp_path / "config"),
        COLUMNS="37",
        LINES="5",
        TERM="dumb",
        LANG="C",
        LC_ALL="C",
        PYTHONHASHSEED="12345",
        PLTR_FORMAT="csv",
    )
    output = subprocess.run(
        [sys.executable, "-m", "pltr", "commands", "list", "--format", "json"],
        check=True,
        capture_output=True,
        env=env,
    ).stdout
    expected = json.dumps(to_document(manifest), indent=2, ensure_ascii=True) + "\n"
    # Windows writes text-mode stdout with CRLF line endings.
    assert output.decode("ascii").replace("\r\n", "\n") == expected


def test_manifest_holds_no_local_paths(manifest):
    text = json.dumps(manifest)
    assert str(Path.home()) not in text
    assert str(Path(__file__).resolve().parents[2]) not in text


def test_groups(manifest):
    groups = {group["path"]: group for group in manifest["groups"]}
    assert groups["pltr dataset"]["description"] == "Manage datasets"
    assert groups["pltr api"]["description"].startswith("Generated commands")
    assert "pltr api admin user" in groups
    assert "pltr commands" in groups
    # Commands are not groups: `pltr verify` is a plain command; `pltr shell`
    # is both a group and runnable on its own.
    assert "pltr verify" not in groups
    assert "pltr shell" in groups
    for group in manifest["groups"]:
        assert set(group) <= {"path", "description", "help"}


# ------------------------------------------------------- entries (real CLI)


def test_curated_entry(entries):
    entry = entries["pltr folder get"]
    assert list(entry) == ENTRY_KEYS
    assert entry["usage"] == "pltr folder get FOLDER_RID [OPTIONS]"
    assert entry["description"] == "Get a folder's metadata."
    assert entry["sdkMethods"] == ["filesystem.Folder.get"]
    assert entry["outputFormats"] == ["table", "json", "csv"]
    assert (entry["beta"], entry["destructive"], entry["paged"]) == (False,) * 3
    assert (entry["generated"], entry["local"], entry["hidden"]) == (False,) * 3
    assert entry["arguments"] == [
        {
            "name": "folder_rid",
            "type": "string",
            "required": True,
            "multiple": False,
            "help": "Folder RID (ri.compass.main.folder.<id>).",
        }
    ]
    assert [o["flags"] for o in entry["options"]] == [
        ["--profile", "-p"],
        ["--format", "-f"],
        ["--output", "-o"],
    ]
    assert option(entry, "format") == {
        "name": "format",
        "flags": ["--format", "-f"],
        "type": "choice",
        "required": False,
        "multiple": False,
        "choices": ["table", "json", "csv"],
        "default": "table",
        "envvar": "PLTR_FORMAT",
        "help": "Output format: table, json or csv.",
    }
    assert option(entry, "output")["type"] == "path"


def test_generated_entry(entries):
    entry = entries["pltr api admin user list"]
    assert list(entry) == ENTRY_KEYS
    assert entry["generated"] is True
    assert entry["sdkMethods"] == ["admin.User.list"]
    assert entry["paged"] is True and entry["beta"] is False
    assert entry["description"] == "Lists all Users."
    assert entry["help"].startswith("Lists all Users.\n\nThis is a paged endpoint.")
    assert "\b" not in entry["help"]
    assert option(entry, "include") == {
        "name": "include",
        "flags": ["--include"],
        "type": "choice",
        "required": False,
        "multiple": False,
        "choices": ["ACTIVE", "DELETED"],
    }
    flags = {flag for o in entry["options"] for flag in o["flags"]}
    assert {"--page-size", "--page-token", "--max-pages", "--all"} <= flags


def test_generated_arguments_keep_their_help(entries):
    entry = entries["pltr api datasets dataset branch list"]
    assert entry["arguments"][0]["name"] == "dataset_rid"
    assert entry["arguments"][0]["help"].endswith("Type: DatasetRid.")


def test_generated_json_options_are_typed(entries):
    entry = entries["pltr api admin user search"]
    where = option(entry, "where")
    assert where["type"] == "json" and where["required"] is True
    assert entry["usage"] == "pltr api admin user search --where JSON [OPTIONS]"


def test_beta_entry(entries):
    entry = entries["pltr space get"]
    assert entry["beta"] is True
    assert entry["description"].startswith("[beta] ")
    assert entry["help"].startswith("[beta] ")


def test_destructive_entry(entries):
    entry = entries["pltr space delete"]
    assert entry["destructive"] is True
    assert option(entry, "yes")["flags"] == ["--yes", "-y"]
    assert option(entry, "yes")["type"] == "flag"
    assert "default" not in option(entry, "yes")
    generated = entries["pltr api admin user delete"]
    assert generated["destructive"] is True and generated["generated"] is True


def test_paged_entry(entries):
    entry = entries["pltr folder list"]
    assert entry["paged"] is True
    assert option(entry, "max_pages")["default"] == 1
    assert option(entry, "all_pages")["flags"] == ["--all"]
    assert option(entry, "page_size")["type"] == "integer"


def test_binary_generated_entry(entries):
    entry = entries["pltr api datasets dataset file content"]
    assert entry["outputFormats"] == ["binary"]


@pytest.mark.parametrize(
    "path",
    [
        "pltr audit get",
        "pltr media-sets download",
        "pltr media-sets thumbnail-retrieve",
    ],
)
def test_binary_curated_entries(entries, path):
    """They have --format (it only shapes errors) but print raw bytes."""
    entry = entries[path]
    assert entry["outputFormats"] == ["binary"], path
    assert any(o["name"] == "format" for o in entry["options"])


def test_binary_follows_the_metadata(manifest):
    commands = {f"pltr {e.path}": e for e in iter_commands(app)}
    for entry in manifest["commands"]:
        meta = commands[entry["path"]].meta
        binary = entry.get("outputFormats") == ["binary"]
        assert binary == bool(meta and meta.binary), entry["path"]


def test_local_entries(entries):
    entry = entries["pltr commands search"]
    assert entry["local"] is True and entry["sdkMethods"] == []
    assert option(entry, "limit")["default"] == 10
    assert entries["pltr alias list"]["local"] is True
    assert entries["pltr folder get"]["local"] is False


def test_local_commands_match_the_contract_cases(manifest):
    """`local` agrees with the contract test's list of commands with no API call."""
    local = {e["path"] for e in manifest["commands"] if e["local"]}
    cases = {f"pltr {path}" for path in load_cases().local}
    assert local == cases
    assert {path.split()[1] for path in local} <= LOCAL_GROUPS


def test_entries_follow_the_recorded_metadata(manifest):
    """Every entry matches its command's @pltr_command metadata, if any."""
    commands = {f"pltr {e.path}": e for e in iter_commands(app)}
    for entry in manifest["commands"]:
        meta = commands[entry["path"]].meta
        if meta is None:
            # Not converted yet: unknown, so absent rather than false.
            for key in ("beta", "destructive", "paged", "sdkMethods"):
                assert key not in entry, (entry["path"], key)
            continue
        assert entry["beta"] == meta.beta, entry["path"]
        assert entry["destructive"] == meta.destructive, entry["path"]
        assert entry["paged"] == meta.paged, entry["path"]
        assert entry["sdkMethods"] == list(meta.sdk), entry["path"]
        if meta.http:  # the labeled direct-HTTP exceptions
            assert entry["httpEndpoints"] == list(meta.http), entry["path"]
        else:
            assert "httpEndpoints" not in entry, entry["path"]


def test_hidden_commands_are_included_and_marked(entries):
    assert entries["pltr shell interactive"]["hidden"] is True
    assert entries["pltr shell start"]["hidden"] is False


# ---------------------------------------------------- entries (synthetic CLI)


def synthetic_app() -> typer.Typer:
    test_app = typer.Typer()

    @test_app.command("http")
    @pltr_command(http="GET /v2/languageModels")
    def http_command(format: FormatOption = "table"):
        """[A labeled exception] Call a Foundry endpoint without the SDK."""

    @test_app.command("legacy")
    def legacy_command(
        rid: str = typer.Argument(..., help="A RID."),
        format: str = typer.Option("table", "--format", help="table, json, csv"),
    ):
        """A command without metadata and with a free-text --format."""

    @test_app.command("plain")
    def plain_command(names: Optional[List[str]] = typer.Argument(None)):
        """A command without metadata and without --format.

        More help.
        """

    @test_app.command("bytes")
    @pltr_command(sdk="datasets.Dataset.File.content", binary=True)
    def bytes_command(format: FormatOption = "table"):
        """Write a file's content (--format only shapes errors)."""

    @test_app.command("types")
    @pltr_command(sdk="filesystem.Folder.get", destructive=True)
    def types_command(
        count: int = typer.Option(1, "--count"),
        ratio: float = typer.Option(0.5, "--ratio"),
        flag: bool = typer.Option(False, "--flag"),
        on: bool = typer.Option(True, "--on/--off"),
        choice: str = typer.Option(
            "a", "--choice", click_type=click.Choice(["a", "b"])
        ),
        path: Optional[Path] = typer.Option(None, "--path"),
        when: Optional[datetime] = typer.Option(None, "--when"),
        uid: Optional[uuid.UUID] = typer.Option(None, "--uid"),
        many: Optional[List[str]] = typer.Option(None, "--many"),
        confirm: bool = typer.Option(False, "--confirm", hidden=True),
        envy: Optional[str] = typer.Option(None, "--envy", envvar="ENVY"),
        body: Optional[str] = typer.Option(None, "--body", metavar="JSON"),
        name: str = typer.Option(..., "--name"),
        yes: YesOption = False,
    ):
        """Every kind of option."""

    @test_app.command("paths")
    @pltr_command(sdk="datasets.Dataset.create")
    def paths_command(
        dataset_rid: Annotated[str, resource_argument("dataset", help="Dataset RID.")],
        parent: Annotated[
            str, resource_option("--parent", kind="folder", help="Folder.")
        ],
        label: Optional[str] = typer.Option(None, "--label"),
    ):
        """Arguments and options that take a RID or a Compass path."""

    return test_app


@pytest.fixture(scope="module")
def synthetic():
    return {e["path"]: e for e in build_manifest(synthetic_app())["commands"]}


def test_direct_http_entry(synthetic):
    entry = synthetic["pltr http"]
    assert entry["sdkMethods"] == []
    assert entry["httpEndpoints"] == ["GET /v2/languageModels"]
    assert entry["local"] is False
    keys = ENTRY_KEYS[:11] + ["httpEndpoints"] + ENTRY_KEYS[11:]
    assert list(entry) == keys


def test_binary_metadata_entry(synthetic):
    assert synthetic["pltr bytes"]["outputFormats"] == ["binary"]
    assert synthetic["pltr http"]["outputFormats"] == ["table", "json", "csv"]


def test_entry_without_metadata(synthetic):
    entry = synthetic["pltr legacy"]
    assert list(entry) == [
        "path",
        "usage",
        "description",
        "generated",
        "local",
        "hidden",
        "arguments",
        "options",
        "help",
    ]
    assert entry["local"] is False  # unknown: not one of the local groups
    # A free-text --format: which formats it accepts is unknown.
    assert "outputFormats" not in entry
    plain = synthetic["pltr plain"]
    assert plain["outputFormats"] == []  # no --format: prints text
    assert plain["description"] == "A command without metadata and without --format."
    assert plain["help"].endswith("More help.")
    assert plain["usage"] == "pltr plain [NAMES...]"
    assert plain["arguments"][0]["multiple"] is True
    assert plain["arguments"][0]["required"] is False


def test_option_types_defaults_and_hidden_aliases(synthetic):
    entry = synthetic["pltr types"]
    options = {o["name"]: o for o in entry["options"]}
    assert "confirm" not in options  # hidden deprecated alias
    assert {name: o["type"] for name, o in options.items()} == {
        "count": "integer",
        "ratio": "number",
        "flag": "flag",
        "on": "flag",
        "choice": "choice",
        "path": "path",
        "when": "datetime",
        "uid": "uuid",
        "many": "string",
        "envy": "string",
        "body": "json",
        "name": "string",
        "yes": "flag",
    }
    assert options["count"]["default"] == 1
    assert options["ratio"]["default"] == 0.5
    assert "default" not in options["flag"]  # off by default
    assert options["on"]["default"] is True
    assert options["on"]["flags"] == ["--on", "--off"]
    assert options["choice"]["choices"] == ["a", "b"]
    assert options["many"]["multiple"] is True and "default" not in options["many"]
    assert options["envy"]["envvar"] == "ENVY"
    assert options["name"]["required"] is True
    assert entry["usage"] == "pltr types --name TEXT [OPTIONS]"
    assert entry["destructive"] is True


def test_metadata_reader_sees_the_synthetic_commands():
    root = typer.main.get_command(synthetic_app())
    assert isinstance(root, click.Group)
    ctx = click.Context(root)
    assert get_command_meta(root.get_command(ctx, "legacy")) is None
    assert get_command_meta(root.get_command(ctx, "http")) is not None


def test_resource_parameters_accept_paths(synthetic):
    entry = synthetic["pltr paths"]
    (argument,) = entry["arguments"]
    options = {o["name"]: o for o in entry["options"]}
    assert argument["acceptsPath"] is True
    assert argument["resourceKind"] == "dataset"
    assert argument["type"] == "string"
    assert options["parent"]["acceptsPath"] is True
    assert options["parent"]["resourceKind"] == "folder"
    assert "acceptsPath" not in options["label"]
    assert "resourceKind" not in options["label"]
    assert entry["usage"] == "pltr paths DATASET_RID --parent RID|PATH [OPTIONS]"
