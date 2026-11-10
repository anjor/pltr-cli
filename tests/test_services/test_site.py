"""Local helpers of `pltr site deploy` (#221): the build folder, the zip, the version."""

import io
import json
import os
import subprocess
import zipfile
from pathlib import Path

import click
import pytest

from pltr.services import site


def build_folder(root: Path) -> Path:
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<title>App</title>")
    (dist / "assets" / "index-abc.js").write_text("console.log(1)")
    (dist / "favicon.svg").write_text("<svg/>")
    return dist


# ------------------------------------------------------------------ versions


@pytest.mark.parametrize(
    "value",
    ["0.1.0", "1.2.3", "10.20.30", "1.2.3-rc.1", "1.2.3-4-gabc1234", "1.0.0+build.5"],
)
def test_semantic_versions_pass(value):
    assert site.check_version(value) == value


@pytest.mark.parametrize(
    "value", ["1.2", "1", "01.2.3", "1.2.3.4", "latest", "", "1.2.3-", "1.2.3-01"]
)
def test_other_versions_are_usage_errors(value):
    with pytest.raises(click.BadParameter, match="semantic version"):
        site.check_version(value)


def test_a_leading_v_is_explained():
    with pytest.raises(click.BadParameter, match="without the leading 'v'"):
        site.check_version("v1.2.3")


# --------------------------------------------------------------- the folder


def test_a_build_folder_passes(tmp_path):
    dist = build_folder(tmp_path)

    assert site.check_site_folder(dist) == dist.resolve()


def test_a_missing_folder(tmp_path):
    with pytest.raises(click.BadParameter, match="doesn't exist"):
        site.check_site_folder(tmp_path / "dist")


def test_a_file_is_not_a_folder(tmp_path):
    (tmp_path / "site.zip").write_bytes(b"PK")

    with pytest.raises(click.BadParameter, match="not a folder"):
        site.check_site_folder(tmp_path / "site.zip")


def test_a_folder_without_index_html(tmp_path):
    (tmp_path / "dist").mkdir()

    with pytest.raises(click.BadParameter, match="no index.html at its root"):
        site.check_site_folder(tmp_path / "dist")


def test_an_index_html_one_level_down_is_named(tmp_path):
    (tmp_path / "out" / "app").mkdir(parents=True)
    (tmp_path / "out" / "app" / "index.html").write_text("x")

    with pytest.raises(click.BadParameter, match="app"):
        site.check_site_folder(tmp_path / "out")


@pytest.mark.parametrize("marker", ["package.json", "node_modules"])
def test_the_project_folder_is_refused(tmp_path, marker):
    """A Vite project has index.html at its root too; zipping it would upload
    the sources and node_modules."""
    (tmp_path / "index.html").write_text("x")
    if marker == "package.json":
        (tmp_path / marker).write_text("{}")
    else:
        (tmp_path / marker).mkdir()

    with pytest.raises(click.BadParameter, match="project folder"):
        site.check_site_folder(tmp_path)


# ------------------------------------------------------------------- the zip


def test_the_zip_has_the_folder_contents_at_its_root(tmp_path):
    dist = build_folder(tmp_path)

    body, count = site.zip_site(dist)

    archive = zipfile.ZipFile(io.BytesIO(body))
    assert sorted(archive.namelist()) == [
        "assets/",
        "assets/index-abc.js",
        "favicon.svg",
        "index.html",
    ]
    assert count == 3
    assert archive.read("index.html") == b"<title>App</title>"
    assert archive.getinfo("index.html").compress_type == zipfile.ZIP_DEFLATED


def link(path: Path, target: Path) -> None:
    try:
        path.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links aren't available here")


def test_linked_folders_and_files_are_followed(tmp_path):
    """Like `zip -r`: a linked folder's files go up, not a dropped link."""
    dist = build_folder(tmp_path)
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "lib.js").write_text("lib")
    link(dist / "lib", shared)
    link(dist / "robots.txt", tmp_path / "robots-source.txt")
    (tmp_path / "robots-source.txt").write_text("User-agent: *")

    body, count = site.zip_site(dist)

    archive = zipfile.ZipFile(io.BytesIO(body))
    assert archive.read("lib/lib.js") == b"lib"
    assert archive.read("robots.txt") == b"User-agent: *"
    assert count == 5


def test_a_broken_link_is_a_usage_error(tmp_path):
    dist = build_folder(tmp_path)
    link(dist / "gone.js", tmp_path / "missing.js")

    with pytest.raises(click.BadParameter, match="gone.js"):
        site.zip_site(dist)


def test_a_link_loop_is_a_usage_error(tmp_path):
    dist = build_folder(tmp_path)
    link(dist / "assets" / "up", dist)

    with pytest.raises(click.BadParameter, match="loop"):
        site.zip_site(dist)


def test_files_older_than_1980_are_zipped(tmp_path):
    """Reproducible builds (SOURCE_DATE_EPOCH=0, Nix) date files 1970."""
    dist = build_folder(tmp_path)
    os.utime(dist / "index.html", (0, 0))

    body, _ = site.zip_site(dist)

    assert zipfile.ZipFile(io.BytesIO(body)).read("index.html")


def test_git_folders_are_left_out_and_other_hidden_files_kept(tmp_path):
    dist = build_folder(tmp_path)
    (dist / ".git").mkdir()
    (dist / ".git" / "config").write_text("[core]")
    (dist / ".well-known").mkdir()
    (dist / ".well-known" / "security.txt").write_text("Contact: x")

    body, _ = site.zip_site(dist)

    names = zipfile.ZipFile(io.BytesIO(body)).namelist()
    assert not [name for name in names if name.startswith(".git/")]
    assert ".well-known/security.txt" in names


# ---------------------------------------------------------- auto-versioning


def test_package_json_search_starts_above_the_build_folder(tmp_path):
    """A package.json copied into the build output isn't the project's."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "package.json").write_text(json.dumps({"version": "9.9.9"}))
    (tmp_path / "package.json").write_text(json.dumps({"version": "0.3.0"}))

    assert site.version_from_package_json(dist)[0] == "0.3.0"


def test_package_json_next_to_the_build_folder(tmp_path):
    dist = build_folder(tmp_path)
    (tmp_path / "package.json").write_text(json.dumps({"version": "0.3.0"}))

    version, found = site.version_from_package_json(dist)

    assert (version, found) == ("0.3.0", tmp_path / "package.json")


def test_package_json_further_up(tmp_path):
    dist = build_folder(tmp_path / "apps" / "web")
    (tmp_path / "package.json").write_text(json.dumps({"version": "2.0.0"}))

    assert site.version_from_package_json(dist)[0] == "2.0.0"


def test_the_nearest_package_json_wins_even_without_a_version(tmp_path):
    dist = build_folder(tmp_path / "web")
    (tmp_path / "package.json").write_text(json.dumps({"version": "2.0.0"}))
    (tmp_path / "web" / "package.json").write_text(json.dumps({"name": "web"}))

    with pytest.raises(click.BadParameter, match='no "version"'):
        site.version_from_package_json(dist)


def test_a_package_json_version_that_isnt_semver(tmp_path):
    dist = build_folder(tmp_path)
    (tmp_path / "package.json").write_text(json.dumps({"version": "1.0"}))

    with pytest.raises(click.BadParameter, match="semantic version"):
        site.version_from_package_json(dist)


def test_a_package_json_that_isnt_json(tmp_path):
    dist = build_folder(tmp_path)
    (tmp_path / "package.json").write_text("{")

    with pytest.raises(click.BadParameter, match="isn't valid JSON"):
        site.version_from_package_json(dist)


def test_no_package_json(tmp_path, monkeypatch):
    dist = build_folder(tmp_path)
    monkeypatch.setattr(site, "_parents", lambda start: [start])

    with pytest.raises(click.BadParameter, match="No package.json"):
        site.version_from_package_json(dist)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=pltr",
            "-c",
            "user.email=pltr@example.com",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "tag.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path, isolated_home) -> Path:
    """A git repository with one commit and a gitignored build folder."""
    root = tmp_path / "app"
    root.mkdir()
    git(root, "init", "-q")
    (root / ".gitignore").write_text("dist/\n")
    (root / "README.md").write_text("app\n")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "first")
    build_folder(root)
    return root


def test_git_describe_on_a_tag(repo):
    git(repo, "tag", "v1.4.0")

    assert site.version_from_git_describe(repo / "dist") == ("1.4.0", "v1.4.0")


def test_git_describe_after_a_tag_is_a_prerelease(repo):
    """Like @osdk/cli: `v1.4.0-2-g<sha>` becomes `1.4.0-2-g<sha>`."""
    git(repo, "tag", "1.4.0")
    for n in range(2):
        (repo / "README.md").write_text(f"app {n}\n")
        git(repo, "commit", "-q", "-am", f"change {n}")
    sha = git(repo, "rev-parse", "--short=7", "HEAD")

    version, described = site.version_from_git_describe(repo / "dist")

    assert version == f"1.4.0-2-g{sha}"
    assert described == version


def test_git_describe_refuses_a_dirty_tree(repo):
    git(repo, "tag", "v1.4.0")
    (repo / "README.md").write_text("changed\n")

    with pytest.raises(click.BadParameter, match="uncommitted changes"):
        site.version_from_git_describe(repo / "dist")


def test_git_describe_refuses_a_version_tag_that_isnt_semver(repo):
    git(repo, "tag", "v1.2")

    with pytest.raises(click.BadParameter, match="'v1.2'"):
        site.version_from_git_describe(repo / "dist")


def test_git_describe_skips_tags_that_dont_look_like_versions(repo):
    """Only v<digit>... and <digit>... tags count, like a release tag."""
    git(repo, "tag", "v1.0.0")
    (repo / "README.md").write_text("later\n")
    git(repo, "commit", "-q", "-am", "later")
    git(repo, "tag", "release-2026")
    git(repo, "tag", "@scope/app@2.0.0")
    sha = git(repo, "rev-parse", "--short=7", "HEAD")

    assert site.version_from_git_describe(repo / "dist")[0] == f"1.0.0-1-g{sha}"


def test_git_describe_that_cant_run(tmp_path, monkeypatch):
    dist = build_folder(tmp_path)

    def refused(*args, **kwargs):
        raise PermissionError("git")

    monkeypatch.setattr(site.subprocess, "run", refused)

    with pytest.raises(click.BadParameter, match="couldn't run git"):
        site.version_from_git_describe(dist)


def test_git_describe_that_hangs(tmp_path, monkeypatch):
    dist = build_folder(tmp_path)

    def hangs(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 60)

    monkeypatch.setattr(site.subprocess, "run", hangs)

    with pytest.raises(click.BadParameter, match="couldn't run git"):
        site.version_from_git_describe(dist)


def test_git_describe_without_tags(repo):
    with pytest.raises(click.BadParameter, match="git describe --tags"):
        site.version_from_git_describe(repo / "dist")


def test_git_describe_outside_a_repository(tmp_path):
    dist = build_folder(tmp_path)
    # GIT_CEILING_DIRECTORIES stops git from finding a repository above tmp_path.
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
        with pytest.raises(click.BadParameter, match="git describe --tags"):
            site.version_from_git_describe(dist)


def test_git_describe_without_git(tmp_path, monkeypatch):
    dist = build_folder(tmp_path)

    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(site.subprocess, "run", no_git)

    with pytest.raises(click.BadParameter, match="git isn't installed"):
        site.version_from_git_describe(dist)


# ----------------------------------------------------------------- the URL


def test_a_hostname_subdomain_is_a_url():
    assert (
        site.site_url("my-app.apps.region.example.com")
        == "https://my-app.apps.region.example.com"
    )


@pytest.mark.parametrize("subdomain", ["my-app", "", "https://x.example.com/a"])
def test_no_url_without_a_full_hostname(subdomain):
    assert site.site_url(subdomain) is None


# ------------------------------------------------------------ the RID


@pytest.mark.parametrize(
    "rid",
    [
        "ri.third-party-applications.main.application.292db3b2-b653-4de6-971c-7e97a7b881d6",
        "ri.third-party-applications..application.x",
    ],
)
def test_application_rids_pass(rid):
    assert site.check_application_rid(rid) == rid


@pytest.mark.parametrize(
    "rid",
    ["my-app", "ri.foundry.main.dataset.x", "ri.third-party-applications.main.x.y"],
)
def test_other_rids_are_usage_errors(rid):
    with pytest.raises(click.BadParameter, match="third-party application RID"):
        site.check_application_rid(rid)
