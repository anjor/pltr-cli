"""Path resolution in the shared command layer (@pltr_command, #193)."""

import json
from typing import Any, Dict, List, Optional

import click
import typer
from click.testing import CliRunner
from typing_extensions import Annotated

from pltr.contract import (
    FormatOption,
    PltrRootGroup,
    ProfileOption,
    pltr_command,
)
from pltr.contract.resources import (
    PATH_HELP,
    ResourceRef,
    resource_argument,
    resource_option,
)
from tests import foundry_json as fj

runner = CliRunner()

DATASET_RID = "ri.foundry.main.dataset.d1"
OTHER_RID = "ri.foundry.main.dataset.d2"
FOLDER_RID = "ri.compass.main.folder.f1"


def resource_json(rid: str, path: str, resource_type: str = "FOUNDRY_DATASET"):
    return {
        "rid": rid,
        "displayName": path.rsplit("/", 1)[-1],
        "path": path,
        "type": resource_type,
        "createdBy": fj.USER_ID,
        "updatedBy": fj.USER_ID,
        "createdTime": "2024-01-01T00:00:00Z",
        "updatedTime": "2024-01-02T00:00:00Z",
        "trashStatus": "NOT_TRASHED",
        "parentFolderRid": fj.PARENT_RID,
        "projectRid": fj.PROJECT_RID,
        "spaceRid": fj.SPACE_RID,
    }


def make_app() -> typer.Typer:
    app = typer.Typer(cls=PltrRootGroup, no_args_is_help=True)
    things = typer.Typer()
    app.add_typer(things, name="things")

    @things.command("get")
    @pltr_command(sdk="datasets.Dataset.get")
    def get_thing(
        dataset_rid: Annotated[str, resource_argument("dataset", help="Dataset RID.")],
        profile: ProfileOption = None,
        format: FormatOption = "table",
    ):
        """Get a thing."""
        typer.echo(json.dumps({"dataset_rid": dataset_rid}))

    @things.command("copy")
    @pltr_command(sdk="filesystem.Resource.get")
    def copy_thing(
        source: Annotated[
            str, resource_argument("dataset-or-folder", help="What to copy.")
        ],
        target: Annotated[
            str, resource_option("--target", "-t", kind="folder", help="Where to.")
        ],
        note: Annotated[Optional[str], typer.Option("--note")] = None,
        profile: ProfileOption = None,
        format: FormatOption = "table",
    ):
        """Copy a thing."""
        typer.echo(json.dumps({"source": source, "target": target, "note": note}))

    @things.command("batch")
    @pltr_command(sdk="filesystem.Resource.get_batch")
    def batch_things(
        rids: Annotated[List[str], resource_argument("resource", help="RIDs.")],
        profile: ProfileOption = None,
        format: FormatOption = "table",
    ):
        """Get several things."""
        typer.echo(json.dumps({"rids": list(rids)}))

    return app


APP = typer.main.get_command(make_app())


@click.command("plain")
@click.argument("dataset_rid", type=ResourceRef("dataset"))
@click.option("--profile", default=None)
@click.option("--format", "format", default="table")
@pltr_command(sdk="datasets.Dataset.get")
def plain(dataset_rid: str, profile: Optional[str], format: str) -> None:
    click.echo(json.dumps({"dataset_rid": dataset_rid}))


def invoke(*args: str) -> Any:
    return runner.invoke(APP, list(args))


def stdout_json(result: Any) -> Dict[str, Any]:
    assert result.exit_code == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


# --------------------------------------------------------------- behaviour


def test_a_rid_is_passed_through_without_any_request(stub_foundry_http) -> None:
    result = invoke("things", "get", DATASET_RID)

    assert stdout_json(result) == {"dataset_rid": DATASET_RID}
    assert stub_foundry_http.requests == []


def test_a_path_reaches_the_command_as_its_rid(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=resource_json(DATASET_RID, "/S/P/a"))

    result = invoke("things", "get", "/S/P/a")

    assert stdout_json(result) == {"dataset_rid": DATASET_RID}
    assert f"Resolved '/S/P/a' to {DATASET_RID}" in result.stderr
    (request,) = stub_foundry_http.requests
    assert request.url.path == "/api/v2/filesystem/resources/getByPath"


def test_json_mode_resolves_silently(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=resource_json(DATASET_RID, "/S/P/a"))

    result = invoke("things", "get", "/S/P/a", "--format", "json")

    assert stdout_json(result) == {"dataset_rid": DATASET_RID}
    assert result.stderr == ""


def test_the_profile_option_picks_the_client(stub_foundry_http) -> None:
    from pltr.services import base

    stub_foundry_http.respond(json=resource_json(DATASET_RID, "/S/P/a"))

    result = invoke("things", "get", "/S/P/a", "--profile", "work")

    assert result.exit_code == 0, result.stderr
    base.AuthManager.return_value.get_client.assert_called_with("work")


def test_paths_in_two_parameters_are_one_batch_call(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json={
            "data": [
                resource_json(DATASET_RID, "/S/P/a"),
                resource_json(FOLDER_RID, "/S/P/f", "COMPASS_FOLDER"),
            ]
        }
    )

    result = invoke("things", "copy", "/S/P/a", "--target", "/S/P/f")

    assert stdout_json(result) == {
        "source": DATASET_RID,
        "target": FOLDER_RID,
        "note": None,
    }
    (request,) = stub_foundry_http.requests
    assert request.url.path == "/api/v2/filesystem/resources/getByPathBatch"


def test_the_same_path_twice_is_resolved_once(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json=resource_json(FOLDER_RID, "/S/P/f", "COMPASS_FOLDER")
    )

    result = invoke("things", "copy", "/S/P/f", "--target", "/S/P/f")

    assert stdout_json(result)["source"] == FOLDER_RID
    assert stdout_json(result)["target"] == FOLDER_RID
    assert len(stub_foundry_http.requests) == 1


def test_mixed_rids_and_paths_keep_their_order(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=resource_json(OTHER_RID, "/S/P/b"))

    result = invoke("things", "batch", DATASET_RID, "/S/P/b", FOLDER_RID)

    assert stdout_json(result) == {"rids": [DATASET_RID, OTHER_RID, FOLDER_RID]}
    assert len(stub_foundry_http.requests) == 1


def test_a_missing_path_is_a_structured_error(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        404, json=fj.error("PathNotFound", parameters={"path": "/S/P/x"})
    )

    result = invoke("things", "get", "/S/P/x", "--format", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json.loads(result.stderr.strip().splitlines()[-1])
    assert error["type"] == "path_not_found"
    assert error["parameters"] == {"path": "/S/P/x"}


def test_a_path_of_the_wrong_kind_is_a_usage_error(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json=resource_json(FOLDER_RID, "/S/P/f", "COMPASS_FOLDER")
    )

    result = invoke("things", "get", "/S/P/f", "--format", "json")

    assert result.exit_code == 2
    error = json.loads(result.stderr.strip().splitlines()[-1])
    assert error["type"] == "wrong_resource_type"
    assert "DATASET_RID" in error["message"]
    assert error["parameters"]["resourceType"] == "COMPASS_FOLDER"


def test_an_option_is_named_by_its_flag_on_a_kind_mismatch(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json={
            "data": [
                resource_json(DATASET_RID, "/S/P/a"),
                resource_json(OTHER_RID, "/S/P/b"),
            ]
        }
    )

    result = invoke("things", "copy", "/S/P/a", "--target", "/S/P/b")

    assert result.exit_code == 2
    assert "--target" in result.stderr


def test_a_click_command_resolves_paths_too(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=resource_json(DATASET_RID, "/S/P/a"))

    result = runner.invoke(plain, ["/S/P/a"])

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {"dataset_rid": DATASET_RID}


# -------------------------------------------------------------------- help


def test_helpers_add_the_path_sentence_and_the_type() -> None:
    command = APP.commands["things"].commands["copy"]  # type: ignore[attr-defined]
    params = {param.name: param for param in command.params}
    assert isinstance(params["source"].type, ResourceRef)
    assert params["source"].type.kind.name == "dataset-or-folder"
    assert isinstance(params["target"].type, ResourceRef)
    assert params["target"].help.endswith(PATH_HELP)
    assert not isinstance(params["note"].type, ResourceRef)
