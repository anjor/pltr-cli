"""Tests for ModelsService against a real FoundryClient (only HTTP is faked).

Model.create, Model.get, Model.Version.get and Model.Version.list are beta:
every request must carry preview=true. The module-level filter turns the
SDK's UserWarning about a stray preview= on a GA call into a failure.
"""

import json

import pytest
from foundry_sdk.v2.models.models import Model, ModelVersion

from pltr.services.models import ModelsService
from tests import foundry_json_models as fm

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

API = "/api/v2/models"


def test_create_model_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=fm.model())

    model = ModelsService().create_model(
        name="fraud-detector", parent_folder_rid=fm.FOLDER_RID
    )

    assert isinstance(model, Model)
    assert model.rid == fm.MODEL_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", API)
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {
        "name": "fraud-detector",
        "parentFolderRid": fm.FOLDER_RID,
    }


def test_get_model_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=fm.model())

    model = ModelsService().get_model(fm.MODEL_RID)

    assert model.rid == fm.MODEL_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", f"{API}/{fm.MODEL_RID}")
    assert dict(request.url.params) == {"preview": "true"}


def test_get_model_version_uses_model_version_get(stub_foundry_http):
    """#182: models.ModelVersion doesn't exist; it's models.Model.Version."""
    stub_foundry_http.respond(json=fm.model_version())

    version = ModelsService().get_model_version(fm.MODEL_RID, fm.VERSION_RID)

    assert isinstance(version, ModelVersion)
    assert version.source is not None and version.source.type == "codeRepository"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/{fm.MODEL_RID}/versions/{fm.VERSION_RID}",
    )
    assert dict(request.url.params) == {"preview": "true"}


def test_list_model_versions_fetches_one_page(stub_foundry_http):
    """#182: models.ModelVersion doesn't exist; it's models.Model.Version."""
    stub_foundry_http.respond(
        json={"data": [fm.model_version()], "nextPageToken": "next"}
    )

    page = ModelsService().list_model_versions(
        fm.MODEL_RID, branch="develop", page_size=10, page_token="tok"
    )

    assert [version.rid for version in page.data] == [fm.VERSION_RID]
    assert page.next_page_token == "next"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "GET",
        f"{API}/{fm.MODEL_RID}/versions",
    )
    assert dict(request.url.params) == {
        "branch": "develop",
        "pageSize": "10",
        "pageToken": "tok",
        "preview": "true",
    }


def test_list_model_versions_defaults(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    page = ModelsService().list_model_versions(fm.MODEL_RID)

    assert page.data == []
    assert dict(stub_foundry_http.requests[0].url.params) == {"preview": "true"}
