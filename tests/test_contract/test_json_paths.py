"""Compass paths inside JSON arguments (pltr.contract.resolve_json_paths, #218)."""

import copy
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from pltr.contract import resolve_json_documents, resolve_json_paths
from pltr.contract.resources import PathNotFoundError, WrongResourceTypeError
from tests import foundry_json as fj

DS = "ri.foundry.main.dataset.d1"
DS_2 = "ri.foundry.main.dataset.d2"
DS_3 = "ri.foundry.main.dataset.d3"

BUILD_TARGET = {
    "targetRids": "resource",
    "inputRids": "resource",
    "ignoredRids": "resource",
}


def dataset(rid: str, name: str) -> dict:
    """A dataset ``Resource`` at /Space/Project/<name>."""
    return fj.resource(rid, name, "FOUNDRY_DATASET")


def test_rids_only_make_no_request(stub_foundry_http) -> None:
    document = {"type": "manual", "targetRids": [DS, DS_2]}

    assert resolve_json_paths(document, BUILD_TARGET, label="TARGET") == document
    assert stub_foundry_http.requests == []


def test_one_path_is_resolved_with_get_by_path(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=dataset(DS, "sales"))
    document = {"type": "manual", "targetRids": ["/Space/Project/sales"]}
    original = copy.deepcopy(document)

    result = resolve_json_paths(document, BUILD_TARGET, label="TARGET")

    assert result == {"type": "manual", "targetRids": [DS]}
    assert document == original  # the input isn't changed
    [request] = stub_foundry_http.requests
    assert request.url.path == "/api/v2/filesystem/resources/getByPath"
    query = parse_qs(urlsplit(str(request.url)).query)
    assert query["path"] == ["/Space/Project/sales"]


def test_paths_in_several_fields_are_one_batch_call(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json={"data": [dataset(DS, "raw"), dataset(DS_2, "clean")]}
    )
    document = {
        "type": "connecting",
        "inputRids": ["/Space/Project/raw"],
        "targetRids": ["/Space/Project/clean", DS_3],
        "ignoredRids": ["/Space/Project/raw"],
    }

    result = resolve_json_paths(document, BUILD_TARGET, label="TARGET")

    assert result == {
        "type": "connecting",
        "inputRids": [DS],
        "targetRids": [DS_2, DS_3],
        "ignoredRids": [DS],
    }
    [request] = stub_foundry_http.requests
    assert request.url.path == "/api/v2/filesystem/resources/getByPathBatch"
    assert json.loads(request.content) == [
        {"path": "/Space/Project/raw"},
        {"path": "/Space/Project/clean"},
    ]


def test_fields_are_found_at_any_depth(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json={"data": [dataset(DS, "sales"), dataset(DS_2, "orders")]}
    )
    document = {
        "type": "and",
        "triggers": [
            {"type": "datasetUpdated", "datasetRid": "/Space/Project/sales"},
            {
                "type": "or",
                "triggers": [
                    {"type": "jobSucceeded", "datasetRid": "/Space/Project/orders"}
                ],
            },
        ],
    }

    result = resolve_json_paths(document, {"datasetRid": "dataset"}, label="--trigger")

    assert result["triggers"][0]["datasetRid"] == DS
    assert result["triggers"][1]["triggers"][0]["datasetRid"] == DS_2


def test_other_fields_keep_values_that_start_with_a_slash(stub_foundry_http) -> None:
    document = {
        "target": {"type": "manual", "targetRids": [DS]},
        "branchName": "/not/a/rid",
        "description": "/Space/Project/sales",
    }

    assert resolve_json_paths(document, BUILD_TARGET, label="ACTION") == document
    assert stub_foundry_http.requests == []


def test_a_missing_path_is_path_not_found(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        404,
        json=fj.error("PathNotFound", parameters={"path": "/Space/Project/nope"}),
    )

    with pytest.raises(PathNotFoundError) as caught:
        resolve_json_paths(
            {"type": "manual", "targetRids": ["/Space/Project/nope"]},
            BUILD_TARGET,
            label="TARGET",
        )

    assert caught.value.parameters == {"path": "/Space/Project/nope"}


def test_a_path_of_the_wrong_kind_names_the_field(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=fj.resource(fj.FOLDER_RID, "sub"))

    with pytest.raises(WrongResourceTypeError) as caught:
        resolve_json_paths(
            {"type": "project", "projectRids": ["/Space/Project/sub"]},
            {"projectRids": "project"},
            label="--scope-mode",
        )

    assert "projectRids in --scope-mode" in str(caught.value)


def test_a_rid_of_the_wrong_kind_fails_before_any_request(stub_foundry_http) -> None:
    with pytest.raises(WrongResourceTypeError) as caught:
        resolve_json_paths(
            {"type": "datasetUpdated", "datasetRid": fj.FOLDER_RID},
            {"datasetRid": "dataset"},
            label="--trigger",
        )

    assert "datasetRid in --trigger" in str(caught.value)
    assert stub_foundry_http.requests == []


def test_an_unknown_kind_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        resolve_json_paths({}, {"targetRids": "build"}, label="TARGET")


def test_several_documents_share_one_lookup(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=dataset(DS, "sales"))
    action = {"target": {"type": "manual", "targetRids": ["/Space/Project/sales"]}}
    trigger = {"type": "datasetUpdated", "datasetRid": "/Space/Project/sales"}

    result = resolve_json_documents(
        [
            (action, BUILD_TARGET, "ACTION"),
            (trigger, {"datasetRid": "dataset"}, "--trigger"),
            (None, {"projectRids": "project"}, "--scope-mode"),
        ]
    )

    assert result == [
        {"target": {"type": "manual", "targetRids": [DS]}},
        {"type": "datasetUpdated", "datasetRid": DS},
        None,
    ]
    [request] = stub_foundry_http.requests
    assert request.url.path == "/api/v2/filesystem/resources/getByPath"


def test_every_rid_is_checked_before_any_lookup(stub_foundry_http) -> None:
    with pytest.raises(WrongResourceTypeError):
        resolve_json_documents(
            [
                ({"targetRids": ["/Space/Project/sales"]}, BUILD_TARGET, "ACTION"),
                ({"projectRids": [DS]}, {"projectRids": "project"}, "--scope-mode"),
            ]
        )

    assert stub_foundry_http.requests == []
