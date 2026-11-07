"""Tests for Compass path resolution (pltr.contract.resources, #193)."""

import json
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlsplit

import click
import pytest

from pltr.contract import ExitCode, PltrError, classify_error
from pltr.contract.resources import (
    KINDS,
    PathNotFoundError,
    ResourceRef,
    WrongResourceTypeError,
    check_kind,
    is_path,
    kind_for_sdk_type,
    resolve_paths,
)
from tests import foundry_json as fj

DATASET_RID = "ri.foundry.main.dataset.d1"
OTHER_DATASET_RID = "ri.foundry.main.dataset.d2"
FOLDER_RID = "ri.compass.main.folder.f1"
PROJECT_RID = "ri.compass.main.folder.p1"


def resource_json(
    rid: str,
    path: str,
    resource_type: str = "FOUNDRY_DATASET",
    project_rid: str = PROJECT_RID,
    trash_status: str = "NOT_TRASHED",
) -> Dict[str, Any]:
    """A ``Resource`` at ``path``."""
    return {
        "rid": rid,
        "displayName": path.rstrip("/").rsplit("/", 1)[-1],
        "path": path,
        "type": resource_type,
        "createdBy": fj.USER_ID,
        "updatedBy": fj.USER_ID,
        "createdTime": "2024-01-01T00:00:00Z",
        "updatedTime": "2024-01-02T00:00:00Z",
        "trashStatus": trash_status,
        "parentFolderRid": fj.PARENT_RID,
        "projectRid": project_rid,
        "spaceRid": fj.SPACE_RID,
    }


def query(request: Any) -> Dict[str, Any]:
    return {k: v[0] for k, v in parse_qs(urlsplit(str(request.url)).query).items()}


# ------------------------------------------------------------------ basics


@pytest.mark.parametrize(
    "value, expected",
    [
        ("/Space/Project/data", True),
        ("/", True),
        ("ri.foundry.main.dataset.d1", False),
        ("Space/Project", False),
        ("", False),
    ],
)
def test_is_path_means_a_leading_slash(value: str, expected: bool) -> None:
    assert is_path(value) is expected


@pytest.mark.parametrize(
    "type_text, kind",
    [
        ("DatasetRid", "dataset"),
        ("Optional[DatasetRid]", "dataset"),
        ("List[FolderRid]", "folder"),
        ("Optional[List[ResourceRid]]", "resource"),
        ("ProjectRid", "project"),
        ("MediaSetRid", "media-set"),
        ("ConnectionRid", "connection"),
        ("ModelRid", "model"),
        ("AgentRid", "agent"),
        ("ThirdPartyApplicationRid", "third-party-application"),
        ("RepositoryRid", "repository"),
        ("SpaceRid", None),
        ("TransactionRid", None),
        ("BuildRid", None),
        ("str", None),
        (None, None),
    ],
)
def test_kind_for_sdk_type_maps_compass_rid_types(
    type_text: Optional[str], kind: Optional[str]
) -> None:
    assert kind_for_sdk_type(type_text) == kind


def test_resource_ref_passes_values_through() -> None:
    ref = ResourceRef("dataset")
    assert ref.kind is KINDS["dataset"]
    assert ref.convert("/a/b", None, None) == "/a/b"
    assert ref.convert(DATASET_RID, None, None) == DATASET_RID


def test_resource_ref_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        ResourceRef("spaceship")


def test_pltr_error_parameters_reach_the_json_error() -> None:
    info = classify_error(
        PltrError("x", error_type="t", exit_code=2, parameters={"path": "/a"})
    )
    assert info.to_json()["parameters"] == {"path": "/a"}


# ------------------------------------------------------------- resolution


def test_one_path_is_resolved_with_get_by_path(stub_foundry_http) -> None:
    path = "/My Space/Projekt Ü/Sales data"
    stub_foundry_http.respond(json=resource_json(DATASET_RID, path))

    resolved = resolve_paths(stub_foundry_http.client, [path])

    assert resolved[path].rid == DATASET_RID
    (request,) = stub_foundry_http.requests
    assert request.method == "GET"
    assert request.url.path == "/api/v2/filesystem/resources/getByPath"
    assert query(request) == {"path": path}


def test_several_paths_are_resolved_in_one_batch_call(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json={
            "data": [
                resource_json(OTHER_DATASET_RID, "/S/P/b"),
                resource_json(DATASET_RID, "/S/P/a"),
            ]
        }
    )

    resolved = resolve_paths(stub_foundry_http.client, ["/S/P/a", "/S/P/b", "/S/P/a"])

    assert resolved["/S/P/a"].rid == DATASET_RID
    assert resolved["/S/P/b"].rid == OTHER_DATASET_RID
    (request,) = stub_foundry_http.requests
    assert request.method == "POST"
    assert request.url.path == "/api/v2/filesystem/resources/getByPathBatch"
    assert json.loads(request.content) == [{"path": "/S/P/a"}, {"path": "/S/P/b"}]


def test_a_repeated_single_path_is_one_get_by_path_call(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=resource_json(DATASET_RID, "/S/P/a"))

    resolved = resolve_paths(stub_foundry_http.client, ["/S/P/a", "/S/P/a"])

    assert resolved["/S/P/a"].rid == DATASET_RID
    assert len(stub_foundry_http.requests) == 1


def test_batch_matches_paths_despite_trailing_or_missing_slashes(
    stub_foundry_http,
) -> None:
    stub_foundry_http.respond(
        json={
            "data": [
                resource_json(FOLDER_RID, "/S/P/folder", "COMPASS_FOLDER"),
                resource_json(DATASET_RID, "/S/P/a"),
            ]
        }
    )

    resolved = resolve_paths(stub_foundry_http.client, ["/S/P/folder/", "/S/P/a"])

    assert resolved["/S/P/folder/"].rid == FOLDER_RID
    assert resolved["/S/P/a"].rid == DATASET_RID


def test_paths_missing_from_a_batch_are_path_not_found(stub_foundry_http) -> None:
    stub_foundry_http.respond(json={"data": [resource_json(DATASET_RID, "/S/P/a")]})

    with pytest.raises(PathNotFoundError) as caught:
        resolve_paths(stub_foundry_http.client, ["/S/P/a", "/S/P/x", "/S/P/y"])

    info = classify_error(caught.value)
    assert info.type == "path_not_found"
    assert info.exit_code == ExitCode.NOT_FOUND
    assert "/S/P/x" in info.message and "/S/P/y" in info.message
    assert info.to_json()["parameters"] == {"paths": ["/S/P/x", "/S/P/y"]}


def test_a_single_missing_path_is_path_not_found(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        404, json=fj.error("PathNotFound", parameters={"path": "/S/P/x"})
    )

    with pytest.raises(PathNotFoundError) as caught:
        resolve_paths(stub_foundry_http.client, ["/S/P/x"])

    info = classify_error(caught.value)
    assert info.type == "path_not_found"
    assert info.exit_code == ExitCode.NOT_FOUND
    assert info.to_json()["parameters"] == {"path": "/S/P/x"}
    assert "/S/P/x" in info.message


def test_other_api_errors_keep_their_classification_with_the_path(
    stub_foundry_http,
) -> None:
    stub_foundry_http.respond(
        400,
        json=fj.error(
            "GetSpaceResourceNotSupported",
            "INVALID_ARGUMENT",
            parameters={"spaceRid": fj.SPACE_RID},
        ),
    )

    with pytest.raises(Exception) as caught:
        resolve_paths(stub_foundry_http.client, ["/My Space"])

    info = classify_error(caught.value)
    assert info.type == "validation_error"
    assert "/My Space" in info.message
    assert "GetSpaceResourceNotSupported" in info.message


def test_a_trashed_resource_resolves_with_a_warning(stub_foundry_http, capsys) -> None:
    stub_foundry_http.respond(
        json=resource_json(DATASET_RID, "/S/P/a", trash_status="DIRECTLY_TRASHED")
    )

    resolved = resolve_paths(stub_foundry_http.client, ["/S/P/a"])

    assert resolved["/S/P/a"].rid == DATASET_RID
    stderr = capsys.readouterr().err
    assert "'/S/P/a' is in the trash" in stderr
    assert DATASET_RID in stderr


# ------------------------------------------------------------ kind checks


def _resource(stub_foundry_http, body: Dict[str, Any]) -> Any:
    stub_foundry_http.respond(json=body)
    return resolve_paths(stub_foundry_http.client, [body["path"]])[body["path"]]


def test_check_kind_accepts_the_right_type(stub_foundry_http) -> None:
    found = _resource(stub_foundry_http, resource_json(DATASET_RID, "/S/P/a"))
    check_kind("/S/P/a", found, KINDS["dataset"], "DATASET_RID")
    check_kind("/S/P/a", found, KINDS["resource"], "RESOURCE_RID")


def test_check_kind_names_both_types_on_a_mismatch(stub_foundry_http) -> None:
    found = _resource(
        stub_foundry_http, resource_json(FOLDER_RID, "/S/P/f", "COMPASS_FOLDER")
    )

    with pytest.raises(WrongResourceTypeError) as caught:
        check_kind("/S/P/f", found, KINDS["dataset"], "DATASET_RID")

    info = classify_error(caught.value)
    assert info.type == "wrong_resource_type"
    assert info.exit_code == ExitCode.USAGE
    assert "COMPASS_FOLDER" in info.message
    assert "FOUNDRY_DATASET" in info.message
    assert "DATASET_RID" in info.message
    assert info.to_json()["parameters"] == {
        "path": "/S/P/f",
        "rid": FOLDER_RID,
        "resourceType": "COMPASS_FOLDER",
        "expectedTypes": ["FOUNDRY_DATASET"],
    }


def test_project_kind_accepts_a_project(stub_foundry_http) -> None:
    found = _resource(
        stub_foundry_http,
        resource_json(PROJECT_RID, "/S/P", "COMPASS_FOLDER", project_rid=PROJECT_RID),
    )
    check_kind("/S/P", found, KINDS["project"], "PROJECT_RID")


def test_project_kind_rejects_a_folder_inside_a_project(stub_foundry_http) -> None:
    found = _resource(
        stub_foundry_http, resource_json(FOLDER_RID, "/S/P/f", "COMPASS_FOLDER")
    )

    with pytest.raises(WrongResourceTypeError) as caught:
        check_kind("/S/P/f", found, KINDS["project"], "PROJECT_RID")

    assert "not a project" in str(caught.value)


def test_folder_kind_accepts_a_project(stub_foundry_http) -> None:
    found = _resource(
        stub_foundry_http,
        resource_json(PROJECT_RID, "/S/P", "COMPASS_FOLDER", project_rid=PROJECT_RID),
    )
    check_kind("/S/P", found, KINDS["folder"], "--parent-folder")


def test_click_param_type_name_is_resource() -> None:
    assert isinstance(ResourceRef("folder"), click.ParamType)
    assert ResourceRef("folder").name == "resource"


def test_batch_api_errors_name_the_paths(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        403,
        json=fj.error("ApiUsageDenied", "PERMISSION_DENIED"),
    )

    with pytest.raises(Exception) as caught:
        resolve_paths(stub_foundry_http.client, ["/S/P/a", "/S/P/b"])

    info = classify_error(caught.value)
    assert info.type == "permission_denied"
    assert "Could not resolve the paths '/S/P/a', '/S/P/b'" in info.message


@pytest.mark.parametrize(
    "value",
    ["C:/Program Files/Git/Space/Project/data", "D:\\Space\\Project\\data"],
)
def test_a_windows_rewritten_path_is_a_usage_error_with_advice(value: str) -> None:
    with pytest.raises(click.BadParameter) as caught:
        ResourceRef("dataset").convert(value, None, None)

    message = caught.value.format_message()
    assert "MSYS_NO_PATHCONV=1" in message
    assert "Git Bash" in message
