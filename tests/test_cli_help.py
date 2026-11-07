"""Help of the root CLI's command groups (`pltr <group> --help`).

`app.add_typer(..., help=...)` in pltr/cli.py would replace a module's own
help (its `@app.callback()` docstring, with RID guidance and examples), so
groups whose module has one register only a `short_help` for the root
listing.
"""

import inspect

import pytest
import typer
from typer.models import DefaultPlaceholder
from typer.testing import CliRunner

from pltr.cli import app

runner = CliRunner()

pytestmark = pytest.mark.usefixtures("isolated_home")


def _groups_with_a_docstring():
    for group in app.registered_groups:
        callback = group.typer_instance.registered_callback
        function = getattr(callback, "callback", None)
        if function is not None and inspect.getdoc(function):
            yield group


GROUPS_WITH_A_DOCSTRING = [group.name for group in _groups_with_a_docstring()]


def _module_help(group) -> str:
    """The help the module itself defines, in Typer's order of precedence:
    the callback's help=, the Typer(help=), the callback's docstring."""
    instance = group.typer_instance
    callback = instance.registered_callback
    for text in (callback.help, instance.info.help):
        if not isinstance(text, DefaultPlaceholder) and text:
            return inspect.cleandoc(text)
    return inspect.getdoc(callback.callback)


def test_groups_with_their_own_help_are_found():
    # (`verify` is a command, so its docstring is its help: see test_verify.py.)
    assert {"dataset", "space", "media-sets", "orchestration"} <= set(
        GROUPS_WITH_A_DOCSTRING
    )


@pytest.mark.parametrize("name", GROUPS_WITH_A_DOCSTRING)
def test_add_typer_does_not_hide_the_module_help(name):
    [group] = [group for group in app.registered_groups if group.name == name]

    assert isinstance(group.help, DefaultPlaceholder), (
        f"cli.py passes help= for '{name}', which hides its module's docstring; "
        "pass short_help= for the root listing instead"
    )
    command = typer.main.get_command(app).commands[name]
    assert command.help == _module_help(group)


def test_group_help_shows_rid_guidance_and_examples_line_by_line():
    result = runner.invoke(app, ["space", "--help"], env={"COLUMNS": "120"})

    assert result.exit_code == 0, result.output
    assert "Spaces are addressed by RID" in result.stdout
    lines = [line.strip() for line in result.stdout.splitlines()]
    # \b keeps the example blocks' line breaks in Typer's rich help
    assert "# List spaces (one page; --all for every page)" in lines
    assert "pltr space list" in lines


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["media-sets", "--help"], "ri.mio.main.media-set.<uuid>"),
        (["dataset", "--help"], "ri.foundry.main.dataset.<id>"),
        (["verify", "--help"], "Reports which one it used."),
        (["admin", "--help"], "Manage users, groups, roles, organizations"),
        (["sql", "--help"], "Execute SQL queries against Foundry datasets"),
        (["cp", "--help"], "SOURCE_RID and TARGET_FOLDER_RID are RIDs"),
    ],
)
def test_help_shows_the_modules_text(args, expected):
    result = runner.invoke(app, args, env={"COLUMNS": "200"})

    assert result.exit_code == 0, result.output
    assert expected in result.stdout


def test_root_listing_keeps_the_one_line_summaries():
    result = runner.invoke(app, ["--help"], env={"COLUMNS": "200"})

    assert result.exit_code == 0, result.output
    rows = {
        line.strip(" │").split(None, 1)[0]: line.strip(" │").split(None, 1)[-1]
        for line in result.stdout.splitlines()
        if line.strip(" │") and not line.lstrip().startswith(("╭", "╰"))
    }
    assert rows["dataset"].strip() == "Manage datasets"
    assert rows["space"].strip() == "Manage spaces"
    assert rows["media-sets"].strip() == "Manage media sets and media content"
    assert rows["cp"].strip() == (
        "Copy a dataset, or a folder with its contents, into another folder."
    )
