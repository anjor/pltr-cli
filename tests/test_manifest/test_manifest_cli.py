"""`pltr commands list/search/show` through the real root command."""

import csv
import io
import json
import subprocess
import sys
import textwrap

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from pltr.contract.serialize import to_document
from pltr.manifest import SUMMARY_KEYS

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated(isolated_home):
    """No real home directory; wide tables (COLUMNS=200)."""
    return isolated_home


def pltr(*args):
    return runner.invoke(app, list(args))


def last_error(result):
    return json.loads(result.stderr.strip().splitlines()[-1])


# --------------------------------------------------------------------- list


def test_list_json_prints_the_manifest(manifest):
    result = pltr("commands", "list", "--format", "json")
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == to_document(manifest)
    assert result.stderr == ""
    again = pltr("commands", "list", "--format", "json")
    assert again.stdout == result.stdout  # deterministic


def test_list_under_a_path(manifest):
    result = pltr("commands", "list", "api", "admin", "user", "--format", "json")
    assert result.exit_code == 0, result.stderr
    document = json.loads(result.stdout)
    paths = [entry["path"] for entry in document["commands"]]
    assert "pltr api admin user list" in paths
    assert all(path.startswith("pltr api admin user ") for path in paths)
    assert [g["path"] for g in document["groups"]][0] == "pltr api admin user"
    assert document["sdkVersion"] == manifest["sdkVersion"]
    # A quoted path with the program name works too.
    quoted = pltr("commands", "list", "pltr api admin user", "--format", "json")
    assert quoted.stdout == result.stdout


def test_list_unknown_path_is_a_usage_error():
    result = pltr("commands", "list", "datasett", "--format", "json")
    assert result.exit_code == 2
    assert result.stdout == ""
    error = last_error(result)
    assert error["type"] == "usage_error" and error["exitCode"] == 2
    assert "no commands under 'pltr datasett'" in error["message"]
    assert "pltr dataset" in error["message"]  # a suggestion


def test_list_table_and_csv():
    table = pltr("commands", "list", "folder")
    assert table.exit_code == 0, table.stderr
    assert "pltr folder get" in table.stdout
    assert "paged" in table.stdout  # folder list's label
    rows = list(
        csv.DictReader(
            io.StringIO(pltr("commands", "list", "folder", "-f", "csv").stdout)
        )
    )
    assert [row["Command"] for row in rows] == [
        "pltr folder batch-get",
        "pltr folder create",
        "pltr folder get",
        "pltr folder list",
    ]
    assert rows[3]["Labels"] == "paged"
    assert rows[2]["Description"] == "Get a folder's metadata."


# ------------------------------------------------------------------- search


def test_search_json():
    result = pltr("commands", "search", "dataset", "get", "--format", "json")
    assert result.exit_code == 0, result.stderr
    document = json.loads(result.stdout)
    assert list(document) == ["data", "totalCount"]
    assert len(document["data"]) == 10  # the default --limit
    assert document["totalCount"] > 10
    first = document["data"][0]
    assert first["path"] == "pltr dataset get"
    assert set(first) <= set(SUMMARY_KEYS)
    assert "help" not in first and "options" not in first
    assert result.stderr == ""


def test_search_limit_and_hint():
    result = pltr("commands", "search", "delete", "user", "--limit", "2")
    assert result.exit_code == 0, result.stderr
    assert "pltr admin user delete" in result.stdout
    assert "Showing 2 of" in result.stderr  # stdout stays data only
    json_result = pltr("commands", "search", "delete user", "-n", "2", "-f", "json")
    assert [e["path"] for e in json.loads(json_result.stdout)["data"]] == [
        "pltr admin user delete",
        "pltr api admin user delete",
    ]


def test_search_without_matches():
    result = pltr("commands", "search", "zzzzqqqq", "--format", "json")
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"data": [], "totalCount": 0}
    table = pltr("commands", "search", "zzzzqqqq")
    assert table.exit_code == 0
    assert "No results." in table.stderr


def test_search_needs_text():
    result = pltr("commands", "search", "--format", "json")
    assert result.exit_code == 2
    assert last_error(result)["type"] == "usage_error"


# --------------------------------------------------------------------- show


@pytest.mark.parametrize(
    "args",
    [
        ["folder", "get"],
        ["folder get"],
        ["pltr folder get"],
        ["pltr", "folder", "get"],
    ],
)
def test_show_accepts_a_path_in_any_form(entries, args):
    result = pltr("commands", "show", *args, "--format", "json")
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == entries["pltr folder get"]


def test_show_table():
    result = pltr("commands", "show", "space", "delete")
    assert result.exit_code == 0, result.stderr
    for text in (
        "pltr space delete SPACE_RID [OPTIONS]",
        "beta, destructive",
        "filesystem.Space.delete",
        "--yes, -y",
    ):
        assert text in result.stdout


def test_show_unknown_command_suggests_close_ones():
    result = pltr("commands", "show", "dataset", "gett", "--format", "json")
    assert result.exit_code == 2
    assert result.stdout == ""
    error = last_error(result)
    assert error["type"] == "usage_error"
    assert "no command 'pltr dataset gett'" in error["message"]
    assert "Did you mean: pltr dataset get" in error["message"]


def test_show_a_group_is_a_usage_error():
    result = pltr("commands", "show", "api", "datasets", "--format", "json")
    assert result.exit_code == 2
    message = last_error(result)["message"]
    assert "'pltr api datasets' is a group of commands" in message
    assert "pltr commands list api datasets" in message


# ------------------------------------------------------------------ startup

PROBE = textwrap.dedent(
    """
    import json, sys
    from typer.testing import CliRunner
    from pltr.cli import app

    runner = CliRunner()
    for args in (["--help"], ["commands", "--help"], ["commands", "search", "--help"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
    print(json.dumps(sorted(m for m in sys.modules if m.startswith("pltr.commands.api._specs"))))
    """
)


def test_help_doesnt_build_the_manifest():
    """`pltr --help` and `pltr commands --help` load none of the generated specs."""
    output = subprocess.run(
        [sys.executable, "-c", PROBE], check=True, capture_output=True, text=True
    ).stdout
    assert json.loads(output.strip().splitlines()[-1]) == []


def test_commands_group_is_listed_in_root_help():
    result = pltr("--help")
    assert result.exit_code == 0
    assert "commands" in result.stdout
    assert "Find commands" in result.stdout
