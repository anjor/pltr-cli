"""Tests for pltr.contract serialization (the JSON contract)."""

import datetime
import enum
import json

from foundry_sdk.v2.filesystem.models import Folder, GetFoldersBatchResponse

from pltr.contract import Page, collect_pages, to_document, to_jsonable
from tests import foundry_json as fj


def folder_model(**overrides) -> Folder:
    return Folder.model_validate(fj.folder(**overrides))


def test_sdk_model_uses_api_names_and_json_safe_values():
    assert to_jsonable(folder_model()) == fj.sdk_json(fj.folder())


def test_sdk_model_matches_model_dump_json_mode():
    model = folder_model()
    assert to_jsonable(model) == model.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )


def test_null_fields_are_omitted():
    body = fj.folder()
    del body["description"]
    assert "description" not in to_jsonable(Folder.model_validate(body))


def test_nested_models_in_dicts_and_lists():
    response = GetFoldersBatchResponse.model_validate(
        {"data": {fj.FOLDER_RID: fj.folder()}}
    )
    assert to_jsonable(response) == {"data": {fj.FOLDER_RID: fj.sdk_json(fj.folder())}}
    assert to_jsonable([folder_model()]) == [fj.sdk_json(fj.folder())]
    assert to_jsonable({"items": (folder_model(),)}) == {
        "items": [fj.sdk_json(fj.folder())]
    }


def test_plain_dicts_keep_their_keys_and_nulls():
    ontology_object = {"__apiName": "Employee", "__primaryKey": "E1", "manager": None}
    assert to_jsonable(ontology_object) == ontology_object


def test_primitives_datetimes_enums_and_non_finite_floats():
    class Color(enum.Enum):
        RED = "red"

    assert to_jsonable(None) is None
    assert to_jsonable("x") == "x"
    assert to_jsonable(3) == 3
    assert to_jsonable(True) is True
    assert to_jsonable(float("nan")) is None
    assert to_jsonable({"v": [float("inf"), 1.5]}) == {"v": [None, 1.5]}
    assert to_jsonable(Color.RED) == "red"
    when = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    assert json.dumps(to_jsonable({"t": when})) == '{"t": "2024-01-01T00:00:00Z"}'


def test_objects_with_to_dict_and_unknown_objects():
    class HasToDict:
        def to_dict(self):
            return {"a": 1}

    class Unknown:
        def __str__(self):
            return "unknown-object"

    assert to_jsonable(HasToDict()) == {"a": 1}
    assert to_jsonable([Unknown()]) == ["unknown-object"]


def test_page_is_the_api_paged_shape():
    assert to_jsonable(Page([folder_model()], "tok")) == {
        "data": [fj.sdk_json(fj.folder())],
        "nextPageToken": "tok",
    }
    assert to_jsonable(Page([])) == {"data": []}


def test_resource_iterator_serializes_its_current_page(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": [fj.resource("ri.compass.main.folder.c", "C")],
            "nextPageToken": "n",
        }
    )
    iterator = stub_foundry_http.client.filesystem.Folder.children(fj.PARENT_RID)

    assert to_jsonable(iterator) == {
        "data": [fj.sdk_json(fj.resource("ri.compass.main.folder.c", "C"))],
        "nextPageToken": "n",
    }
    assert len(stub_foundry_http.requests) == 1


def test_to_document_wraps_lists_in_the_paged_shape():
    assert to_document([1, 2]) == {"data": [1, 2]}
    assert to_document((1,)) == {"data": [1]}
    assert to_document({"a": 1}) == {"a": 1}
    assert to_document(None) is None


class FakePage:
    def __init__(self, data, next_page_token):
        self.data = data
        self.next_page_token = next_page_token


def fake_fetch(pages):
    """A fetch_page that serves `pages` keyed by the token it is asked for."""
    calls = []

    def fetch(token):
        calls.append(token)
        return pages[token]

    return fetch, calls


PAGES = {
    None: FakePage([1, 2], "t2"),
    "t2": FakePage([3], "t3"),
    "t3": FakePage([4], None),
}


def test_collect_pages_defaults_to_one_page():
    fetch, calls = fake_fetch(PAGES)
    page = collect_pages(fetch)
    assert (page.data, page.next_page_token, calls) == ([1, 2], "t2", [None])


def test_collect_pages_max_pages_and_resume_token():
    fetch, calls = fake_fetch(PAGES)
    page = collect_pages(fetch, page_token="t2", max_pages=5)
    assert (page.data, page.next_page_token, calls) == ([3, 4], None, ["t2", "t3"])


def test_collect_pages_all_pages_overrides_max_pages():
    fetch, calls = fake_fetch(PAGES)
    page = collect_pages(fetch, max_pages=1, all_pages=True)
    assert (page.data, page.next_page_token) == ([1, 2, 3, 4], None)
    assert calls == [None, "t2", "t3"]


def test_collect_pages_with_sdk_iterators(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fj.space()], "nextPageToken": "t2"})
    stub_foundry_http.respond(json={"data": [fj.space("ri.compass.main.folder.s2")]})
    spaces = stub_foundry_http.client.filesystem.Space

    page = collect_pages(lambda token: spaces.list(page_token=token), all_pages=True)

    assert [space.rid for space in page.data] == [
        fj.SPACE_RID,
        "ri.compass.main.folder.s2",
    ]
    assert page.next_page_token is None
    assert len(stub_foundry_http.requests) == 2  # no extra requests
