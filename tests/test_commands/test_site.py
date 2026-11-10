"""`pltr site`: deploy a built site to Foundry website hosting (#221).

Real FoundryClient, only HTTP faked. Every endpoint is GA, so no request may
carry `preview` (a stray one raises the SDK's UserWarning, an error here).
"""

import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from pltr.services.third_party_applications import ThirdPartyApplicationsService
from tests import foundry_json as fj

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()

APP = (
    "ri.third-party-applications.main.application.292db3b2-b653-4de6-971c-7e97a7b881d6"
)
WEBSITE = f"/api/v2/thirdPartyApplications/{APP}/website"
HOST = "my-app.apps.region.example.com"


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)


@pytest.fixture
def dist(tmp_path) -> Path:
    folder = tmp_path / "web" / "dist"
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_text("<title>My App</title>")
    (folder / "assets" / "index-abc.js").write_text("console.log(1)")
    return folder


def website(version: str = "1.2.3", subdomains: Any = (HOST,)) -> Dict[str, Any]:
    return {"deployedVersion": version, "subdomains": list(subdomains)}


def version_not_found(version: str = "1.2.3") -> Dict[str, Any]:
    return {
        "status_code": 404,
        "json": fj.error(
            "VersionNotFound",
            parameters={"thirdPartyApplicationRid": APP, "versionVersion": version},
        ),
    }


def scanning(version: str = "1.2.3") -> Dict[str, Any]:
    return {
        "status_code": 400,
        "json": fj.error(
            "ScanningInProgress", "INVALID_ARGUMENT", parameters={"version": version}
        ),
    }


def queue(stub, *responses: Dict[str, Any]) -> None:
    for response in responses:
        stub.respond(**response)


def happy_path(stub, version: str = "1.2.3", subdomains: Any = (HOST,)) -> None:
    queue(
        stub,
        version_not_found(version),
        {"json": {"version": version}},
        {"json": website(version, subdomains)},
    )


def deploy(dist: Path, *args: str, **kwargs: Any):
    return runner.invoke(
        app, ["site", "deploy", str(dist), "--application", APP, *args], **kwargs
    )


def calls(stub) -> List[str]:
    return [
        f"{r.method} {r.url.path.replace(WEBSITE, '<website>')}" for r in stub.requests
    ]


def error_of(result: Any) -> Dict[str, Any]:
    assert result.stdout == ""
    return json.loads(result.stderr.strip().splitlines()[-1])


def json_lines(stderr: str) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


# -------------------------------------------------------------- the service


def test_service_calls_are_ga(stub_foundry_http):
    service = ThirdPartyApplicationsService()
    queue(
        stub_foundry_http,
        version_not_found(),
        {"json": {"version": "1.2.3"}},
        {"json": website()},
        {"json": {"data": [{"version": "1.2.3"}]}},
    )

    assert service.website_version_exists(APP, "1.2.3") is False
    assert service.upload_website_version(APP, b"zip", "1.2.3").version == "1.2.3"
    assert service.deploy_website(APP, "1.2.3", timeout=0).subdomains == [HOST]
    assert [v.version for v in service.list_website_versions(APP).data] == ["1.2.3"]

    get, upload, deploy_, list_ = stub_foundry_http.requests
    assert (get.method, get.url.path) == ("GET", f"{WEBSITE}/versions/1.2.3")
    assert (upload.method, upload.url.path) == ("POST", f"{WEBSITE}/versions/upload")
    assert dict(upload.url.params) == {"version": "1.2.3"}
    assert upload.headers["content-type"] == "application/octet-stream"
    assert upload.content == b"zip"
    assert (deploy_.method, deploy_.url.path) == ("POST", f"{WEBSITE}/deploy")
    assert json.loads(deploy_.content) == {"version": "1.2.3"}
    assert (list_.method, list_.url.path) == ("GET", f"{WEBSITE}/versions")
    for request in stub_foundry_http.requests:
        assert "preview" not in request.url.params


def test_an_existing_version_is_found(stub_foundry_http):
    stub_foundry_http.respond(json={"version": "1.2.3"})

    assert ThirdPartyApplicationsService().website_version_exists(APP, "1.2.3")


# ------------------------------------------------------------ site deploy


def test_deploy_zips_uploads_and_deploys(stub_foundry_http, dist):
    happy_path(stub_foundry_http)

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {
        "thirdPartyApplicationRid": APP,
        "version": "1.2.3",
        "deployed": True,
        "deployedVersion": "1.2.3",
        "subdomains": [HOST],
        "url": f"https://{HOST}",
    }
    assert calls(stub_foundry_http) == [
        "GET <website>/versions/1.2.3",
        "POST <website>/versions/upload",
        "POST <website>/deploy",
    ]
    upload = stub_foundry_http.requests[1]
    archive = zipfile.ZipFile(io.BytesIO(upload.content))
    assert sorted(archive.namelist()) == [
        "assets/",
        "assets/index-abc.js",
        "index.html",
    ]
    assert archive.read("index.html") == b"<title>My App</title>"
    assert json_lines(result.stderr) == []


def test_deploy_in_table_mode_shows_the_url(stub_foundry_http, dist):
    happy_path(stub_foundry_http)

    result = deploy(dist, "--version", "1.2.3", "--yes")

    assert result.exit_code == 0, result.stderr
    assert f"https://{HOST}" in result.stdout
    assert "Deployed version 1.2.3" in result.stderr


def test_deploy_needs_yes_without_a_terminal(stub_foundry_http, dist):
    queue(stub_foundry_http, version_not_found())

    result = deploy(dist, "--version", "1.2.3", "--format", "json")

    assert result.exit_code == 2
    error = error_of(result)
    assert error["type"] == "confirmation_required"
    assert "replaces the live version" in error["message"]
    # Only the read-only version check ran: nothing was uploaded.
    assert calls(stub_foundry_http) == ["GET <website>/versions/1.2.3"]


def test_an_existing_version_is_reported_before_asking(stub_foundry_http, dist):
    """Nobody should approve a deploy that then fails as a conflict."""
    stub_foundry_http.respond(json={"version": "1.2.3"})

    result = deploy(dist, "--version", "1.2.3", "--format", "json")

    assert result.exit_code == 7
    assert error_of(result)["type"] == "conflict"
    assert calls(stub_foundry_http) == ["GET <website>/versions/1.2.3"]


def test_deploy_asks_on_a_terminal(stub_foundry_http, dist, monkeypatch):
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)
    happy_path(stub_foundry_http)

    result = deploy(dist, "--version", "1.2.3", input="y\n")

    assert result.exit_code == 0, result.stderr
    assert "[y/N]" in result.stderr
    assert len(stub_foundry_http.requests) == 3


def test_no_at_the_prompt_changes_nothing(stub_foundry_http, dist, monkeypatch):
    monkeypatch.setattr("pltr.contract.options.stdin_is_interactive", lambda: True)
    queue(stub_foundry_http, version_not_found())

    result = deploy(dist, "--version", "1.2.3", input="n\n")

    assert result.exit_code == 1
    assert calls(stub_foundry_http) == ["GET <website>/versions/1.2.3"]


def test_upload_only_uploads_without_asking(stub_foundry_http, dist):
    queue(stub_foundry_http, version_not_found(), {"json": {"version": "1.2.3"}})

    result = deploy(dist, "--version", "1.2.3", "--upload-only", "--format", "json")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {
        "thirdPartyApplicationRid": APP,
        "version": "1.2.3",
        "deployed": False,
    }
    assert calls(stub_foundry_http) == [
        "GET <website>/versions/1.2.3",
        "POST <website>/versions/upload",
    ]


def test_upload_only_says_how_to_deploy(stub_foundry_http, dist):
    queue(stub_foundry_http, version_not_found(), {"json": {"version": "1.2.3"}})

    result = deploy(dist, "--version", "1.2.3", "--upload-only")

    assert result.exit_code == 0, result.stderr
    assert f"pltr site rollback 1.2.3 --application {APP}" in result.stderr


# ---------------------------------------------------------------- versions


def test_no_version_flag_is_a_usage_error(stub_foundry_http, dist):
    result = deploy(dist, "--yes", "--format", "json")

    assert result.exit_code == 2
    error = error_of(result)
    assert error["type"] == "usage_error"
    assert "--auto-version" in error["message"]
    assert stub_foundry_http.requests == []


def test_version_and_auto_version_together(stub_foundry_http, dist):
    result = deploy(
        dist, "--version", "1.2.3", "--auto-version", "package-json", "--yes"
    )

    assert result.exit_code == 2
    assert "not both" in result.stderr
    assert stub_foundry_http.requests == []


@pytest.mark.parametrize("version", ["1.2", "v1.2.3", "latest"])
def test_a_version_that_isnt_semver(stub_foundry_http, dist, version):
    result = deploy(dist, "--version", version, "--yes", "--format", "json")

    assert result.exit_code == 2
    assert "semantic version" in error_of(result)["message"]
    assert stub_foundry_http.requests == []


def test_auto_version_from_package_json(stub_foundry_http, dist):
    (dist.parent / "package.json").write_text(json.dumps({"version": "0.4.0"}))
    happy_path(stub_foundry_http, "0.4.0")

    result = deploy(dist, "--auto-version", "package-json", "--yes", "--format", "json")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["version"] == "0.4.0"
    assert stub_foundry_http.requests[1].url.params["version"] == "0.4.0"


def test_auto_version_from_git_describe(stub_foundry_http, dist, monkeypatch):
    from pltr.services import site

    monkeypatch.setattr(
        site, "version_from_git_describe", lambda folder: ("2.1.0", "v2.1.0")
    )
    happy_path(stub_foundry_http, "2.1.0")

    result = deploy(dist, "--auto-version", "git-describe", "--yes")

    assert result.exit_code == 0, result.stderr
    assert "Version 2.1.0 (git describe: v2.1.0)" in result.stderr
    assert stub_foundry_http.requests[1].url.params["version"] == "2.1.0"


def test_an_existing_version_is_a_conflict_before_any_upload(stub_foundry_http, dist):
    stub_foundry_http.respond(json={"version": "1.2.3"})

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 7
    error = error_of(result)
    assert error["type"] == "conflict"
    assert "already exists" in error["message"]
    assert "pltr site rollback" in error["hint"]
    assert error["suggestedCommand"] == f"pltr site versions --application {APP}"
    assert error["parameters"] == {"thirdPartyApplicationRid": APP, "version": "1.2.3"}
    assert calls(stub_foundry_http) == ["GET <website>/versions/1.2.3"]


def test_a_version_uploaded_meanwhile_is_the_apis_conflict(stub_foundry_http, dist):
    queue(
        stub_foundry_http,
        version_not_found(),
        {
            "status_code": 409,
            "json": fj.error(
                "VersionAlreadyExists", "CONFLICT", parameters={"version": "1.2.3"}
            ),
        },
    )

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 7
    error = error_of(result)
    assert (error["type"], error["errorName"]) == ("conflict", "VersionAlreadyExists")


def test_other_errors_of_the_version_check_pass_through(stub_foundry_http, dist):
    stub_foundry_http.respond(404, json=fj.error("WebsiteNotFound"))

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 5
    assert error_of(result)["errorName"] == "WebsiteNotFound"
    assert len(stub_foundry_http.requests) == 1


# ------------------------------------------------------------ the folder


def test_a_folder_without_index_html_is_refused(stub_foundry_http, tmp_path):
    (tmp_path / "out").mkdir()

    result = deploy(tmp_path / "out", "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 2
    assert "index.html" in error_of(result)["message"]
    assert stub_foundry_http.requests == []


def test_a_missing_folder_is_refused(stub_foundry_http, tmp_path):
    result = deploy(tmp_path / "dist", "--version", "1.2.3", "--yes")

    assert result.exit_code == 2
    assert "doesn't exist" in result.stderr
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------ the RID


def test_a_rid_of_another_kind_is_refused(stub_foundry_http, dist):
    result = runner.invoke(
        app,
        [
            "site",
            "deploy",
            str(dist),
            "--application",
            "ri.foundry.main.dataset.x",
            "--version",
            "1.2.3",
            "--yes",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 2
    assert error_of(result)["type"] == "wrong_resource_type"
    assert stub_foundry_http.requests == []


def test_a_value_that_isnt_a_rid_is_refused(stub_foundry_http, dist):
    result = runner.invoke(
        app,
        ["site", "deploy", str(dist), "--application", "my-app", "--version", "1.2.3"],
    )

    assert result.exit_code == 2
    assert "third-party application RID" in result.stderr
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------- the URL


def test_no_subdomain_yet(stub_foundry_http, dist):
    happy_path(stub_foundry_http, subdomains=())

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 0, result.stderr
    document = json.loads(result.stdout)
    assert document["subdomains"] == []
    assert "url" not in document
    [warning] = json_lines(result.stderr)
    assert warning["type"] == "warning"
    assert "no subdomain" in warning["message"]
    assert "approved" in warning["message"]


def test_a_subdomain_without_a_domain_gives_no_url(stub_foundry_http, dist):
    happy_path(stub_foundry_http, subdomains=("my-app",))

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 0, result.stderr
    document = json.loads(result.stdout)
    assert document["subdomains"] == ["my-app"]
    assert "url" not in document
    [warning] = json_lines(result.stderr)
    assert "can't build the site's URL" in warning["message"]


# ------------------------------------------------------- scanning, failures


def test_deploy_retries_while_the_upload_is_scanned(stub_foundry_http, dist):
    queue(
        stub_foundry_http,
        version_not_found(),
        {"json": {"version": "1.2.3"}},
        scanning(),
        scanning(),
        {"json": website()},
    )

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 0, result.stderr
    assert calls(stub_foundry_http).count("POST <website>/deploy") == 3
    assert json.loads(result.stdout)["deployedVersion"] == "1.2.3"


def test_still_scanning_at_the_timeout(stub_foundry_http, dist):
    queue(stub_foundry_http, version_not_found(), {"json": {"version": "1.2.3"}})
    stub_foundry_http.respond_always(**scanning())

    result = deploy(
        dist, "--version", "1.2.3", "--timeout", "0", "--yes", "--format", "json"
    )

    assert result.exit_code == 9
    error = error_of(result)
    assert error["type"] == "wait_timeout"
    assert "uploaded" in error["message"]
    assert error["parameters"] == {"thirdPartyApplicationRid": APP, "version": "1.2.3"}
    assert (
        error["suggestedCommand"]
        == f"pltr site rollback 1.2.3 --application {APP} --yes"
    )


def test_a_failed_deploy_says_the_version_was_uploaded(stub_foundry_http, dist):
    queue(
        stub_foundry_http,
        version_not_found(),
        {"json": {"version": "1.2.3"}},
        {
            "status_code": 403,
            "json": fj.error(
                "DeployWebsitePermissionDenied",
                "PERMISSION_DENIED",
                parameters={"thirdPartyApplicationRid": APP},
            ),
        },
    )

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 4
    error = error_of(result)
    assert error["errorName"] == "DeployWebsitePermissionDenied"
    assert "Uploaded version 1.2.3, but deploying it failed" in error["message"]
    assert f"pltr site rollback 1.2.3 --application {APP}" in error["message"]


@pytest.mark.parametrize("name", ["SiteAssetHasVulnerabilities", "ScanningErrored"])
def test_a_version_foundry_wont_deploy_needs_a_new_upload(
    stub_foundry_http, dist, name
):
    """Rolling back to that version would fail the same way: don't suggest it."""
    queue(
        stub_foundry_http,
        version_not_found(),
        {"json": {"version": "1.2.3"}},
        {
            "status_code": 400,
            "json": fj.error(name, "INVALID_ARGUMENT", parameters={"version": "1.2.3"}),
        },
    )

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 6
    error = error_of(result)
    assert error["errorName"] == name
    assert "new version" in error["message"]
    assert "rollback" not in error["message"]


def test_an_unreadable_deploy_response_may_have_deployed(stub_foundry_http, dist):
    """The deploy request may have gone through: don't claim it failed."""
    queue(
        stub_foundry_http,
        version_not_found(),
        {"json": {"version": "1.2.3"}},
        {"json": {"subdomains": "not-a-list"}},
    )

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 7
    error = error_of(result)
    assert error["type"] == "invalid_response"
    assert "may have been deployed" in error["message"]
    assert "website get" in error["message"]


def test_too_many_versions_says_how_to_delete_one(stub_foundry_http, dist):
    queue(
        stub_foundry_http,
        version_not_found(),
        {
            "status_code": 400,
            "json": fj.error(
                "VersionLimitExceeded",
                "INVALID_ARGUMENT",
                parameters={"versionLimit": 50},
            ),
        },
    )

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 6
    error = error_of(result)
    assert error["errorName"] == "VersionLimitExceeded"
    assert "website version delete" in error["message"]


def test_a_server_error_while_scanning_is_retried(stub_foundry_http, dist):
    queue(
        stub_foundry_http,
        version_not_found(),
        {"json": {"version": "1.2.3"}},
        scanning(),
        {"status_code": 503, "json": fj.error("ServiceUnavailable", "INTERNAL")},
        {"json": website()},
    )

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 0, result.stderr
    assert calls(stub_foundry_http).count("POST <website>/deploy") == 3


def test_a_different_deployed_version_warns(stub_foundry_http, dist):
    happy_path(stub_foundry_http)
    stub_foundry_http._queued[-1] = (200, {"json": website("1.0.0")})

    result = deploy(dist, "--version", "1.2.3", "--yes", "--format", "json")

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["deployedVersion"] == "1.0.0"
    [warning] = json_lines(result.stderr)
    assert "1.0.0" in warning["message"] and "1.2.3" in warning["message"]


def test_suggested_commands_keep_the_profile(stub_foundry_http, dist):
    stub_foundry_http.respond(json={"version": "1.2.3"})
    conflict = deploy(
        dist, "--version", "1.2.3", "--profile", "dev", "--yes", "--format", "json"
    )
    queue(stub_foundry_http, version_not_found(), {"json": {"version": "1.2.3"}})
    stub_foundry_http.respond_always(**scanning())
    timeout = deploy(
        dist,
        *("--version", "1.2.3", "--timeout", "0", "--profile", "dev", "--yes"),
        "--format",
        "json",
    )

    conflict_error = error_of(conflict)
    assert conflict_error["suggestedCommand"].endswith("--profile dev")
    assert "--profile dev`" in conflict_error["hint"]
    assert error_of(timeout)["suggestedCommand"] == (
        f"pltr site rollback 1.2.3 --application {APP} --yes --profile dev"
    )


def test_emit_code_is_unsupported(stub_foundry_http, dist):
    result = deploy(dist, "--version", "1.2.3", "--yes", "--emit-code")

    assert result.exit_code == 2
    assert "several calls" in result.stderr
    assert stub_foundry_http.requests == []


# -------------------------------------------------- versions and rollback


def test_versions_lists_the_uploaded_versions(stub_foundry_http):
    body = {"data": [{"version": "0.1.0"}, {"version": "0.2.0"}]}
    stub_foundry_http.respond(json=body)

    result = runner.invoke(
        app, ["site", "versions", "--application", APP, "--format", "json"]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == body
    assert calls(stub_foundry_http) == ["GET <website>/versions"]


def test_versions_pages(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [{"version": "0.1.0"}], "nextPageToken": "t2"}
    )
    stub_foundry_http.respond(json={"data": [{"version": "0.2.0"}]})

    result = runner.invoke(
        app, ["site", "versions", "--application", APP, "--all", "--page-size", "1"]
    )

    assert result.exit_code == 0, result.stderr
    assert "0.1.0" in result.stdout and "0.2.0" in result.stdout
    second = stub_foundry_http.requests[1]
    assert dict(second.url.params) == {"pageSize": "1", "pageToken": "t2"}


def test_rollback_deploys_an_uploaded_version(stub_foundry_http):
    stub_foundry_http.respond(json=website("0.1.0"))

    result = runner.invoke(
        app,
        [
            "site",
            "rollback",
            "0.1.0",
            "--application",
            APP,
            "--yes",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {
        "thirdPartyApplicationRid": APP,
        "version": "0.1.0",
        "deployed": True,
        "deployedVersion": "0.1.0",
        "subdomains": [HOST],
        "url": f"https://{HOST}",
    }
    [request] = stub_foundry_http.requests
    assert json.loads(request.content) == {"version": "0.1.0"}


def test_rollback_needs_yes(stub_foundry_http):
    result = runner.invoke(
        app, ["site", "rollback", "0.1.0", "--application", APP, "--format", "json"]
    )

    assert result.exit_code == 2
    assert error_of(result)["type"] == "confirmation_required"
    assert stub_foundry_http.requests == []


def test_rollback_checks_the_version(stub_foundry_http):
    result = runner.invoke(
        app, ["site", "rollback", "0.1", "--application", APP, "--yes"]
    )

    assert result.exit_code == 2
    assert "semantic version" in result.stderr
    assert stub_foundry_http.requests == []


def test_rollback_emit_code_shows_the_deploy_call(stub_foundry_http):
    result = runner.invoke(
        app,
        ["site", "rollback", "0.1.0", "--application", APP, "--emit-code"],
    )

    assert result.exit_code == 0, result.stderr
    assert "Website.deploy(" in result.stdout
    assert stub_foundry_http.requests == []
