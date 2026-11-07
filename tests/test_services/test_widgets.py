"""Tests for WidgetsService against a real FoundryClient (only HTTP is faked).

Every Widgets endpoint is beta: each request must carry preview=true. The
module-level filter turns the SDK's UserWarning (sent when preview= is
passed to a GA method) into a failure.
"""

import pytest
from foundry_sdk.v2.widgets.models import Release, Repository, WidgetSet

from pltr.services.widgets import WidgetsService
from tests import foundry_json as fj
from tests import foundry_json_widgets as wj

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

WIDGET_SETS = "/api/v2/widgets/widgetSets"


def test_get_widget_set(stub_foundry_http):
    stub_foundry_http.respond(json=wj.widget_set())

    widget_set = WidgetsService().get_widget_set(wj.WIDGET_SET_RID)

    assert isinstance(widget_set, WidgetSet)
    assert widget_set.publish_repository_rid == wj.REPOSITORY_RID
    [request] = stub_foundry_http.requests
    assert request.method == "GET"
    assert request.url.path == f"{WIDGET_SETS}/{wj.WIDGET_SET_RID}"
    assert dict(request.url.params) == {"preview": "true"}


def test_list_releases_fetches_one_page(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [wj.release("1.2.0"), wj.release("1.1.0")], "nextPageToken": "t2"}
    )

    page = WidgetsService().list_releases(wj.WIDGET_SET_RID, page_size=2)

    assert [release.version for release in page.data] == ["1.2.0", "1.1.0"]
    assert all(isinstance(release, Release) for release in page.data)
    assert page.next_page_token == "t2"
    [request] = stub_foundry_http.requests  # constructing the iterator: one page
    assert request.url.path == f"{WIDGET_SETS}/{wj.WIDGET_SET_RID}/releases"
    assert dict(request.url.params) == {"pageSize": "2", "preview": "true"}


def test_list_releases_passes_branch_and_page_token(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    WidgetsService().list_releases(wj.WIDGET_SET_RID, branch="dev", page_token="t2")

    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {
        "branch": "dev",
        "pageToken": "t2",
        "preview": "true",
    }


def test_get_release(stub_foundry_http):
    stub_foundry_http.respond(json=wj.release("1.2.0"))

    release = WidgetsService().get_release(wj.WIDGET_SET_RID, "1.2.0")

    assert isinstance(release, Release)
    assert release.locator.repository_rid == wj.REPOSITORY_RID
    [request] = stub_foundry_http.requests
    assert request.method == "GET"
    assert request.url.path == f"{WIDGET_SETS}/{wj.WIDGET_SET_RID}/releases/1.2.0"
    assert request.url.params["preview"] == "true"


def test_delete_release(stub_foundry_http):
    stub_foundry_http.respond(204)

    assert WidgetsService().delete_release(wj.WIDGET_SET_RID, "1.2.0") is None

    [request] = stub_foundry_http.requests
    assert request.method == "DELETE"
    assert request.url.path == f"{WIDGET_SETS}/{wj.WIDGET_SET_RID}/releases/1.2.0"
    assert request.url.params["preview"] == "true"


def test_get_repository(stub_foundry_http):
    stub_foundry_http.respond(json=wj.repository())

    repository = WidgetsService().get_repository(wj.REPOSITORY_RID)

    assert isinstance(repository, Repository)
    assert repository.widget_set_rid == wj.WIDGET_SET_RID
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/widgets/repositories/{wj.REPOSITORY_RID}"
    assert request.url.params["preview"] == "true"


def test_sdk_errors_propagate_unwrapped(stub_foundry_http):
    from foundry_sdk.v2.widgets.errors import WidgetSetNotFound

    stub_foundry_http.respond(
        404,
        json=fj.error(
            "WidgetSetNotFound", parameters={"widgetSetRid": wj.WIDGET_SET_RID}
        ),
    )

    with pytest.raises(WidgetSetNotFound):
        WidgetsService().get_widget_set(wj.WIDGET_SET_RID)
