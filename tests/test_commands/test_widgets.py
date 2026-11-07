"""Tests for `pltr widgets` against a real FoundryClient (only HTTP is faked).

Every Widgets endpoint is beta, so every request carries preview=true and
every command's help starts with [beta]. (These tests replace Mock-based ones
that asserted calls to `DevModeSettings.get/disable/pause`, which don't exist
in the SDK; the `widgets dev-mode` group was removed.)
"""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_widgets as wj

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()
RELEASES = f"/api/v2/widgets/widgetSets/{wj.WIDGET_SET_RID}/releases"


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


@pytest.fixture
def interactive(monkeypatch):
    """Pretend stdin is a terminal so confirmation prompts are allowed."""
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)


# ------------------------------------------------------------------- help


@pytest.mark.parametrize(
    "group, commands",
    [
        (["widgets"], ["get"]),
        (["widgets", "release"], ["list", "get", "delete"]),
        (["widgets", "repository"], ["get"]),
    ],
)
def test_every_command_is_labeled_beta(group, commands):
    result = invoke(*group, "--help")

    assert result.exit_code == 0
    for command in commands:
        line = next(
            line for line in result.stdout.splitlines() if f" {command} " in line
        )
        assert "[beta]" in line, line


def test_dev_mode_group_was_removed():
    result = invoke("widgets", "dev-mode", "get")

    assert result.exit_code == 2
    assert "No such command 'dev-mode'" in result.stderr


# --------------------------------------------------------------------- get


def test_get_widget_set_table(stub_foundry_http):
    stub_foundry_http.respond(json=wj.widget_set())

    result = invoke("widgets", "get", wj.WIDGET_SET_RID)

    assert result.exit_code == 0, result.output
    assert wj.WIDGET_SET_RID in result.stdout
    assert wj.REPOSITORY_RID in result.stdout
    assert "Publish Repository" in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/widgets/widgetSets/{wj.WIDGET_SET_RID}"
    assert request.url.params["preview"] == "true"


def test_get_widget_set_json_is_the_sdk_serialization(stub_foundry_http):
    stub_foundry_http.respond(json=wj.widget_set())

    result = invoke("widgets", "get", wj.WIDGET_SET_RID, "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == wj.widget_set()
    assert result.stderr == ""


def test_get_widget_set_without_publish_repository_omits_it(stub_foundry_http):
    body = {"rid": wj.WIDGET_SET_RID}
    stub_foundry_http.respond(json=body)

    result = invoke("widgets", "get", wj.WIDGET_SET_RID, "-f", "csv")

    assert result.exit_code == 0, result.output
    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row == {"RID": wj.WIDGET_SET_RID, "Publish Repository": ""}


def test_get_widget_set_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "WidgetSetNotFound", parameters={"widgetSetRid": wj.WIDGET_SET_RID}
        ),
    )

    result = invoke("widgets", "get", wj.WIDGET_SET_RID, "-f", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == ("not_found", "WidgetSetNotFound")
    assert error["parameters"] == {"widgetSetRid": wj.WIDGET_SET_RID}


def test_get_widget_set_rejects_an_invalid_rid(stub_foundry_http):
    result = invoke("widgets", "get", "not-a-rid", "-f", "json")

    assert result.exit_code == 2
    assert json_lines(result.stderr)[-1]["type"] == "usage_error"
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------ release list


def test_list_releases_json_keeps_the_paged_shape(stub_foundry_http):
    body = {"data": [wj.release("1.2.0"), wj.release("1.1.0")], "nextPageToken": "t2"}
    stub_foundry_http.respond(json=body)

    result = invoke("widgets", "release", "list", wj.WIDGET_SET_RID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == body
    [request] = stub_foundry_http.requests
    assert request.url.path == RELEASES
    assert dict(request.url.params) == {"preview": "true"}


def test_list_releases_csv(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [wj.release("1.2.0")]})

    result = invoke("widgets", "release", "list", wj.WIDGET_SET_RID, "-f", "csv")

    assert result.exit_code == 0, result.output
    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row == {
        "Version": "1.2.0",
        "Description": "Release 1.2.0",
        "Widget Set": wj.WIDGET_SET_RID,
        "Repository": wj.REPOSITORY_RID,
        "Repository Version": "1.2.0",
    }


def test_list_releases_table_hints_at_the_next_page(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [wj.release()], "nextPageToken": "t2"})

    result = invoke("widgets", "release", "list", wj.WIDGET_SET_RID)

    assert result.exit_code == 0, result.output
    assert "1.2.0" in result.stdout
    assert "--page-token t2" in result.stderr


def test_list_releases_all_pages_with_branch(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [wj.release("1.2.0")], "nextPageToken": "t2"}
    )
    stub_foundry_http.respond(json={"data": [wj.release("1.1.0")]})

    result = invoke(
        "widgets",
        "release",
        "list",
        wj.WIDGET_SET_RID,
        "--branch",
        "dev",
        "--page-size",
        "1",
        "--all",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert [r["version"] for r in json.loads(result.stdout)["data"]] == [
        "1.2.0",
        "1.1.0",
    ]
    assert [dict(r.url.params) for r in stub_foundry_http.requests] == [
        {"branch": "dev", "pageSize": "1", "preview": "true"},
        {"branch": "dev", "pageSize": "1", "pageToken": "t2", "preview": "true"},
    ]


def test_list_releases_resumes_from_a_page_token(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    result = invoke(
        "widgets", "release", "list", wj.WIDGET_SET_RID, "--page-token", "t2"
    )

    assert result.exit_code == 0, result.output
    assert "No results." in result.stderr
    [request] = stub_foundry_http.requests
    assert request.url.params["pageToken"] == "t2"


# ------------------------------------------------------------- release get


def test_get_release_table(stub_foundry_http):
    stub_foundry_http.respond(json=wj.release("1.2.0"))

    result = invoke("widgets", "release", "get", wj.WIDGET_SET_RID, "1.2.0")

    assert result.exit_code == 0, result.output
    for expected in ("1.2.0", "Release 1.2.0", wj.WIDGET_SET_RID, wj.REPOSITORY_RID):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{RELEASES}/1.2.0"
    assert request.url.params["preview"] == "true"


def test_get_release_json(stub_foundry_http):
    stub_foundry_http.respond(json=wj.release("1.2.0"))

    result = invoke(
        "widgets", "release", "get", wj.WIDGET_SET_RID, "1.2.0", "-f", "json"
    )

    assert json.loads(result.stdout) == wj.release("1.2.0")


def test_get_release_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "ReleaseNotFound",
            parameters={"widgetSetRid": wj.WIDGET_SET_RID, "releaseVersion": "9.9.9"},
        ),
    )

    result = invoke("widgets", "release", "get", wj.WIDGET_SET_RID, "9.9.9")

    assert result.exit_code == 5
    assert result.stdout == ""
    assert "ReleaseNotFound" in result.stderr


# ---------------------------------------------------------- release delete


def test_delete_release_refuses_without_yes_when_not_interactive(stub_foundry_http):
    result = invoke(
        "widgets", "release", "delete", wj.WIDGET_SET_RID, "1.2.0", "-f", "json"
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "confirmation_required"
    assert "--yes" in error["message"]
    assert stub_foundry_http.requests == []


def test_delete_release_with_yes(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke("widgets", "release", "delete", wj.WIDGET_SET_RID, "1.2.0", "-y")

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert f"Deleted release 1.2.0 of widget set {wj.WIDGET_SET_RID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert request.method == "DELETE"
    assert request.url.path == f"{RELEASES}/1.2.0"
    assert request.url.params["preview"] == "true"


def test_delete_release_json_prints_null(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = invoke(
        "widgets",
        "release",
        "delete",
        wj.WIDGET_SET_RID,
        "1.2.0",
        "--yes",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    assert result.stderr == ""


def test_delete_release_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "DeleteReleasePermissionDenied",
            "PERMISSION_DENIED",
            parameters={"widgetSetRid": wj.WIDGET_SET_RID, "releaseVersion": "1.2.0"},
        ),
    )

    result = invoke(
        "widgets", "release", "delete", wj.WIDGET_SET_RID, "1.2.0", "-y", "-f", "json"
    )

    assert result.exit_code == 4
    assert result.stdout == ""
    error = json_lines(result.stderr)[-1]
    assert error["type"] == "permission_denied"
    assert error["errorName"] == "DeleteReleasePermissionDenied"
    assert error["statusCode"] == 403


def test_delete_release_prompts_on_stderr(stub_foundry_http, interactive):
    stub_foundry_http.respond(204)

    result = invoke(
        "widgets", "release", "delete", wj.WIDGET_SET_RID, "1.2.0", input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert f"Delete release 1.2.0 of widget set {wj.WIDGET_SET_RID}?" in result.stderr
    assert result.stdout == ""
    assert len(stub_foundry_http.requests) == 1


def test_delete_release_answering_no_aborts(stub_foundry_http, interactive):
    result = invoke(
        "widgets", "release", "delete", wj.WIDGET_SET_RID, "1.2.0", input="n\n"
    )

    assert result.exit_code == 1
    assert "Aborted" in result.stderr
    assert stub_foundry_http.requests == []


# ---------------------------------------------------------- repository get


def test_get_repository_csv(stub_foundry_http):
    stub_foundry_http.respond(json=wj.repository())

    result = invoke("widgets", "repository", "get", wj.REPOSITORY_RID, "-f", "csv")

    assert result.exit_code == 0, result.output
    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row == {"RID": wj.REPOSITORY_RID, "Widget Set": wj.WIDGET_SET_RID}
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/widgets/repositories/{wj.REPOSITORY_RID}"
    assert request.url.params["preview"] == "true"


def test_get_repository_json(stub_foundry_http):
    stub_foundry_http.respond(json=wj.repository())

    result = invoke("widgets", "repository", "get", wj.REPOSITORY_RID, "-f", "json")

    assert json.loads(result.stdout) == wj.repository()


def test_get_repository_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "RepositoryNotFound", parameters={"repositoryRid": wj.REPOSITORY_RID}
        ),
    )

    result = invoke("widgets", "repository", "get", wj.REPOSITORY_RID, "-f", "json")

    assert result.exit_code == 5
    error = json_lines(result.stderr)[-1]
    assert (error["type"], error["errorName"]) == ("not_found", "RepositoryNotFound")
