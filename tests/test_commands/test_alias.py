"""Tests for `pltr alias ...` with the real AliasManager (aliases.json in a temp home).

The alias commands follow the shared contract: data on stdout, messages on
stderr, structured errors (an unknown alias is `not_found`, exit 5; bad
arguments are usage errors, exit 2), and removing aliases needs --yes when
stdin is not a terminal (CliRunner's isn't). (These tests replace ones that
expected messages on stdout and exit code 1 for every error.)
"""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from pltr.commands.alias import reserved_names
from pltr.config.aliases import AliasManager

pytestmark = pytest.mark.usefixtures("isolated_home")


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


def invoke(*args: str, **kwargs):
    return CliRunner().invoke(app, ["alias", *args], **kwargs)


def last_json_line(stderr: str) -> dict:
    return json.loads(stderr.strip().splitlines()[-1])


def aliases() -> dict:
    return AliasManager().list_aliases()


def add(name: str, command: str) -> None:
    assert AliasManager().add_alias(name, command)


# -------------------------------------------------------------------- add


def test_add(isolated_home):
    result = invoke("add", "ds", "dataset get")

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Created alias: ds → dataset get" in result.stderr
    assert aliases() == {"ds": "dataset get"}
    assert (isolated_home / ".config" / "pltr" / "aliases.json").exists()


def test_add_json_prints_null():
    result = invoke("add", "ds", "dataset get", "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    assert result.stderr == ""


def test_add_existing_alias_needs_force():
    add("ds", "dataset get")

    result = invoke("add", "ds", "dataset list", "--format", "json")

    assert result.exit_code == 2
    error = last_json_line(result.stderr)
    assert error["type"] == "usage_error"
    assert "alias 'ds' already exists" in error["message"]
    assert "--force" in error["message"]
    assert aliases() == {"ds": "dataset get"}


def test_add_with_force_replaces():
    add("ds", "dataset get")

    result = invoke("add", "ds", "dataset list", "-f")

    assert result.exit_code == 0, result.output
    assert "Updated alias: ds → dataset list" in result.stderr
    assert aliases() == {"ds": "dataset list"}


@pytest.mark.parametrize("name", ["configure", "folder", "api", "help", "--version"])
def test_add_rejects_pltr_command_names(name):
    result = invoke("add", "--format", "json", "--", name, "some command")

    assert result.exit_code == 2
    error = last_json_line(result.stderr)
    assert error["type"] == "usage_error"
    assert "is a pltr command name" in error["message"]
    assert aliases() == {}


def test_reserved_names_are_every_top_level_command():
    names = reserved_names()

    for command in ("dataset", "folder", "space", "api", "verify", "alias", "shell"):
        assert command in names
    assert "ds" not in names


def test_add_rejects_a_circular_reference():
    add("a", "b")
    add("b", "c")

    result = invoke("add", "c", "a", "--format", "json")

    assert result.exit_code == 2
    assert "circular reference" in last_json_line(result.stderr)["message"]
    assert "c" not in aliases()


# ----------------------------------------------------------------- remove


def test_remove_needs_yes_without_a_terminal():
    add("ds", "dataset get")

    result = invoke("remove", "ds", "--format", "json")

    assert result.exit_code == 2
    error = last_json_line(result.stderr)
    assert error["type"] == "confirmation_required"
    assert "Remove alias 'ds' (ds → dataset get)?" in error["message"]
    assert aliases() == {"ds": "dataset get"}


def test_remove_with_yes():
    add("ds", "dataset get")

    result = invoke("remove", "ds", "-y")

    assert result.exit_code == 0, result.output
    assert "Removed alias 'ds'" in result.stderr
    assert aliases() == {}


def test_remove_no_confirm_is_a_deprecated_alias_for_yes():
    add("ds", "dataset get")

    result = invoke("remove", "ds", "--no-confirm", "--format", "json")

    assert result.exit_code == 0, result.output
    [warning] = [json.loads(line) for line in result.stderr.splitlines()]
    assert warning["type"] == "warning"
    assert "--no-confirm is deprecated" in warning["message"]
    assert aliases() == {}


def test_remove_confirm_still_asks():
    add("ds", "dataset get")

    result = invoke("remove", "ds", "--confirm")

    assert result.exit_code == 2
    assert "--confirm is deprecated" in result.stderr
    assert aliases() == {"ds": "dataset get"}


def test_remove_prompts_on_stderr_when_interactive(interactive):
    add("ds", "dataset get")

    result = invoke("remove", "ds", input="y\n")

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Remove alias 'ds' (ds → dataset get)? [y/N]" in result.stderr
    assert aliases() == {}


def test_remove_answering_no_aborts(interactive):
    add("ds", "dataset get")

    result = invoke("remove", "ds", input="n\n")

    assert result.exit_code == 1
    assert "Aborted" in result.stderr
    assert aliases() == {"ds": "dataset get"}


def test_remove_unknown_alias_is_not_found():
    result = invoke("remove", "nope", "--yes", "--format", "json")

    assert result.exit_code == 5
    error = last_json_line(result.stderr)
    assert (error["type"], error["message"]) == ("not_found", "Alias 'nope' not found.")


# ------------------------------------------------------------------- edit


def test_edit():
    add("ds", "dataset get")

    result = invoke("edit", "ds", "dataset list")

    assert result.exit_code == 0, result.output
    assert "Updated alias: ds → dataset list" in result.stderr
    assert aliases() == {"ds": "dataset list"}


def test_edit_unknown_alias_is_not_found():
    result = invoke("edit", "nope", "command")

    assert result.exit_code == 5
    assert "Alias 'nope' not found." in result.stderr


def test_edit_rejects_a_circular_reference():
    add("a", "b")
    add("b", "dataset get")

    result = invoke("edit", "b", "a", "--format", "json")

    assert result.exit_code == 2
    assert "circular reference" in last_json_line(result.stderr)["message"]
    assert aliases()["b"] == "dataset get"


# ------------------------------------------------------------- list, show


def test_list_table_json_and_csv():
    add("sq", "sql execute")
    add("ds", "dataset get")

    table = invoke("list")
    as_json = invoke("list", "--format", "json")
    as_csv = invoke("list", "--format", "csv")

    assert table.exit_code == 0, table.output
    assert "dataset get" in table.stdout and "sql execute" in table.stdout
    assert json.loads(as_json.stdout) == {
        "data": [
            {"name": "ds", "command": "dataset get"},
            {"name": "sq", "command": "sql execute"},
        ]
    }
    assert list(csv.DictReader(io.StringIO(as_csv.stdout))) == [
        {"Alias": "ds", "Command": "dataset get"},
        {"Alias": "sq", "Command": "sql execute"},
    ]


def test_list_when_empty():
    table = invoke("list")
    as_json = invoke("list", "-f", "json")

    assert table.exit_code == 0
    assert table.stdout == ""
    assert "No results." in table.stderr
    assert "pltr alias add" in table.stderr
    assert json.loads(as_json.stdout) == {"data": []}


def test_show():
    add("ds", "dataset get")

    table = invoke("show", "ds")
    as_json = invoke("show", "ds", "-f", "json")

    assert table.exit_code == 0, table.output
    assert "dataset get" in table.stdout
    assert json.loads(as_json.stdout) == {"name": "ds", "command": "dataset get"}


def test_show_unknown_alias_is_not_found():
    result = invoke("show", "nope", "--format", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    assert last_json_line(result.stderr)["type"] == "not_found"


# ------------------------------------------------------------------ clear


def test_clear_with_yes():
    add("ds", "dataset")
    add("sq", "sql")

    result = invoke("clear", "--yes")

    assert result.exit_code == 0, result.output
    assert "Cleared 2 aliases" in result.stderr
    assert aliases() == {}


def test_clear_needs_yes_without_a_terminal():
    add("ds", "dataset")

    result = invoke("clear")

    assert result.exit_code == 2
    assert "Remove all 1 aliases?" in result.stderr
    assert aliases() == {"ds": "dataset"}


def test_clear_no_confirm_still_works_with_a_warning():
    add("ds", "dataset")

    result = invoke("clear", "--no-confirm")

    assert result.exit_code == 0, result.output
    assert "--no-confirm is deprecated" in result.stderr
    assert aliases() == {}


def test_clear_with_nothing_to_clear():
    result = invoke("clear")

    assert result.exit_code == 0
    assert "No aliases to clear" in result.stderr


# --------------------------------------------------------- export, import


def test_export_to_stdout():
    add("sq", "sql execute")
    add("ds", "dataset get")

    result = invoke("export")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"ds": "dataset get", "sq": "sql execute"}
    assert list(json.loads(result.stdout)) == ["ds", "sq"]  # sorted


def test_export_to_a_file(tmp_path):
    add("ds", "dataset get")
    target = tmp_path / "aliases.json"

    result = invoke("export", "--output", str(target))

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Wrote JSON output to {target}" in result.stderr
    assert json.loads(target.read_text()) == {"ds": "dataset get"}


def test_export_with_no_aliases_prints_an_empty_object():
    result = invoke("export")

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {}
    assert "No aliases to export" in result.stderr


def test_export_and_import_round_trip(tmp_path):
    add("ds", "dataset get")
    add("sq", "sql execute")
    target = tmp_path / "aliases.json"
    invoke("export", "-o", str(target))
    invoke("clear", "--yes")

    result = invoke("import", str(target))

    assert result.exit_code == 0, result.output
    assert "Imported 2 aliases" in result.stderr
    assert aliases() == {"ds": "dataset get", "sq": "sql execute"}


def test_import_replacing_existing_aliases_needs_yes(tmp_path):
    add("old", "folder get")
    source = tmp_path / "aliases.json"
    source.write_text(json.dumps({"ds": "dataset get"}))

    refused = invoke("import", str(source), "--format", "json")
    replaced = invoke("import", str(source), "--yes")

    assert refused.exit_code == 2
    assert last_json_line(refused.stderr)["type"] == "confirmation_required"
    assert replaced.exit_code == 0, replaced.output
    assert aliases() == {"ds": "dataset get"}


def test_import_merge_keeps_existing_aliases(tmp_path):
    add("old", "folder get")
    add("ds", "dataset list")
    source = tmp_path / "aliases.json"
    source.write_text(json.dumps({"ds": "dataset get", "sq": "sql execute"}))

    result = invoke("import", str(source), "--merge")

    assert result.exit_code == 0, result.output
    assert aliases() == {"old": "folder get", "ds": "dataset get", "sq": "sql execute"}


def test_import_skips_circular_aliases_with_a_warning(tmp_path):
    source = tmp_path / "aliases.json"
    source.write_text(json.dumps({"a": "a", "ds": "dataset get"}))

    result = invoke("import", str(source))

    assert result.exit_code == 0, result.output
    assert "Skipped 1 alias(es)" in result.stderr
    assert aliases() == {"ds": "dataset get"}


@pytest.mark.parametrize(
    "content, message",
    [
        ("{not json", "invalid JSON"),
        ('["ds", "dataset get"]', "expected a JSON object"),
        ('{"ds": 1}', "expected a JSON object"),
        ('{"folder": "dataset get"}', "'folder' is a pltr command name"),
    ],
)
def test_import_rejects_bad_files(tmp_path, content, message):
    add("ds", "dataset get")
    source = tmp_path / "aliases.json"
    source.write_text(content)

    result = invoke("import", str(source), "--yes", "--format", "json")

    assert result.exit_code == 2
    error = last_json_line(result.stderr)
    assert error["type"] == "usage_error"
    assert message in error["message"]
    assert aliases() == {"ds": "dataset get"}  # nothing changed


def test_import_missing_file_is_a_usage_error(tmp_path):
    result = invoke("import", str(tmp_path / "missing.json"))

    assert result.exit_code == 2
    assert "cannot read" in result.stderr


# ---------------------------------------------------------------- resolve


def test_resolve_follows_nested_aliases():
    add("a", "b")
    add("b", "dataset get")

    table = invoke("resolve", "a")
    as_json = invoke("resolve", "a", "--format", "json")

    assert table.exit_code == 0, table.output
    assert "dataset get" in table.stdout
    assert json.loads(as_json.stdout) == {"name": "a", "command": "dataset get"}


def test_resolve_something_that_is_not_an_alias_is_not_found():
    result = invoke("resolve", "dataset", "--format", "json")

    assert result.exit_code == 5
    assert last_json_line(result.stderr)["message"] == "Alias 'dataset' not found."


def test_resolve_reports_a_circular_alias_file(isolated_home):
    config = isolated_home / ".config" / "pltr"
    config.mkdir(parents=True, exist_ok=True)
    (config / "aliases.json").write_text(json.dumps({"a": "b", "b": "a"}))

    result = invoke("resolve", "a", "--format", "json")

    assert result.exit_code == 1
    assert "refers back to itself" in last_json_line(result.stderr)["message"]
