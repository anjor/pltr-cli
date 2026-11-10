"""Curated commands accept Compass paths wherever they take a resource RID (#193)."""

import json
import re
from typing import Dict, List, Tuple

import click
import pytest
from typer.testing import CliRunner

from pltr.cli import app
from pltr.contract import iter_commands
from pltr.contract.resources import ResourceRef
from tests import foundry_json as fj

pytestmark = pytest.mark.usefixtures("isolated_home")

runner = CliRunner()


def curated_parameters() -> Dict[Tuple[str, str], click.Parameter]:
    """Every argument and option of every curated command, by (path, name)."""
    found: Dict[Tuple[str, str], click.Parameter] = {}
    for entry in iter_commands(app):
        if entry.path.split()[0] == "api":
            continue
        for param in entry.command.params:
            found[(entry.path, str(param.name))] = param
    return found


PARAMETERS = curated_parameters()

#: Parameters that take a Compass resource RID, and the kind they must be.
EXPECTED: List[Tuple[str, str, str]] = [
    ("dataset get", "dataset_rid", "dataset"),
    ("dataset create", "parent_folder", "folder"),
    ("dataset preview", "dataset_rid", "dataset"),
    ("dataset files upload", "dataset_rid", "dataset"),
    ("dataset schema get", "dataset_rid", "dataset"),
    ("dataset views get", "view_rid", "dataset"),
    ("dataset views create", "parent_folder", "folder"),
    ("folder get", "folder_rid", "folder"),
    ("folder list", "folder_rid", "folder"),
    ("folder batch-get", "folder_rids", "folder"),
    ("folder create", "parent_folder", "folder"),
    ("project get", "project_rid", "project"),
    ("project delete", "project_rid", "project"),
    ("resource get", "resource_rid", "resource"),
    ("resource batch-get", "resource_rids", "resource"),
    ("resource delete", "resource_rid", "resource"),
    ("resource list", "folder_rid", "folder"),
    ("resource search", "folder_rid", "folder"),
    ("resource-role grant", "resource_rid", "resource"),
    ("cp", "source_rid", "dataset-or-folder"),
    ("cp", "target_folder_rid", "folder"),
    ("media-sets get", "media_set_rid", "media-set"),
    ("media-sets upload", "media_set_rid", "media-set"),
    ("connectivity connection get", "connection_rid", "connection"),
    ("connectivity connection create", "parent_folder_rid", "folder"),
    ("connectivity import file", "dataset_rid", "dataset"),
    ("connectivity import table", "connection_rid", "connection"),
    ("streams dataset create", "parent_folder_rid", "folder"),
    ("streams stream get", "dataset_rid", "dataset"),
    ("models model create", "folder", "folder"),
    ("models model get", "model_rid", "model"),
    ("models version list", "model_rid", "model"),
    ("aip-agents get", "agent_rid", "agent"),
    ("aip-agents sessions list", "agent_rid", "agent"),
    ("third-party-apps get", "application_rid", "third-party-application"),
    ("widgets repository get", "repository_rid", "repository"),
    ("ontology object-type-create", "backing_dataset", "dataset"),
    ("orchestration builds create", "datasets", "dataset"),
]


@pytest.mark.parametrize("path, name, kind", EXPECTED)
def test_resource_parameters_accept_paths(path: str, name: str, kind: str) -> None:
    param = PARAMETERS[(path, name)]
    assert isinstance(param.type, ResourceRef), f"pltr {path} {name}"
    assert param.type.kind.name == kind
    assert "Compass path" in (getattr(param, "help", None) or "")


#: Names of parameters that hold a Compass resource RID.
RESOURCE_RID_NAME = re.compile(
    r"^(?:.*_)?(?:dataset|folder|project|media_set|connection|model|agent|"
    r"resource|view|application|repository)_rids?$|^parent_folder$"
)

#: Parameters whose names look like resource RIDs but don't take one, and why.
_AT_BRANCH = "values are DATASET_RID or DATASET_RID@BRANCH; a path may itself contain @"
_STREAM_VIEW = "a stream view RID (ViewRid), not a Compass resource"
NOT_RESOURCES: Dict[Tuple[str, str], str] = {
    ("dataset views create", "backing_dataset_rids"): _AT_BRANCH,
    ("dataset views add-datasets", "dataset_rids"): _AT_BRANCH,
    ("dataset views remove-datasets", "dataset_rids"): _AT_BRANCH,
    ("dataset views replace-datasets", "dataset_rids"): _AT_BRANCH,
    ("streams stream publish", "view_rid"): _STREAM_VIEW,
    ("streams stream publish-batch", "view_rid"): _STREAM_VIEW,
}


def test_every_resource_rid_parameter_accepts_paths() -> None:
    missing = sorted(
        f"pltr {path} {name}"
        for (path, name), param in PARAMETERS.items()
        if RESOURCE_RID_NAME.match(name)
        and (path, name) not in NOT_RESOURCES
        and not isinstance(param.type, ResourceRef)
    )
    assert not missing, "These take a resource RID but no path: " + ", ".join(missing)


def test_spaces_take_rids_only() -> None:
    """The API can't look up a space by path."""
    assert not isinstance(PARAMETERS[("space get", "space_rid")].type, ResourceRef)
    assert not isinstance(PARAMETERS[("project create", "space_rid")].type, ResourceRef)


# --------------------------------------------------------------- behaviour

DATASET_RID = "ri.foundry.main.dataset.d1"


def resource_json(rid: str, path: str, resource_type: str, project_rid=None):
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
        "projectRid": project_rid or fj.PROJECT_RID,
        "spaceRid": fj.SPACE_RID,
    }


def test_folder_create_in_a_project_given_by_path(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json=resource_json(
            fj.PROJECT_RID, "/Space/Project", "COMPASS_FOLDER", fj.PROJECT_RID
        )
    )
    stub_foundry_http.respond(json=fj.folder())

    result = runner.invoke(
        app,
        ["folder", "create", "New", "--parent-folder", "/Space/Project", "-f", "json"],
    )

    assert result.exit_code == 0, result.stderr
    lookup, create = stub_foundry_http.requests
    assert lookup.url.path == "/api/v2/filesystem/resources/getByPath"
    assert json.loads(create.content)["parentFolderRid"] == fj.PROJECT_RID


def test_resource_batch_get_mixes_rids_and_paths(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json=resource_json(DATASET_RID, "/Space/Project/sales", "FOUNDRY_DATASET")
    )
    stub_foundry_http.respond(json={"data": {}})

    result = runner.invoke(
        app,
        ["resource", "batch-get", fj.FOLDER_RID, "/Space/Project/sales", "-f", "json"],
    )

    assert result.exit_code == 0, result.stderr
    _, batch = stub_foundry_http.requests
    assert json.loads(batch.content) == [
        {"resourceRid": fj.FOLDER_RID},
        {"resourceRid": DATASET_RID},
    ]


def test_project_get_refuses_a_folder_path(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json=resource_json(fj.FOLDER_RID, "/Space/Project/sub", "COMPASS_FOLDER")
    )

    result = runner.invoke(app, ["project", "get", "/Space/Project/sub", "-f", "json"])

    assert result.exit_code == 2
    error = json.loads(result.stderr.strip().splitlines()[-1])
    assert error["type"] == "wrong_resource_type"
    assert "not a project" in error["message"]
    assert len(stub_foundry_http.requests) == 1
