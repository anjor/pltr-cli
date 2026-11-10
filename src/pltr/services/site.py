"""Local steps of ``pltr site deploy`` (#221): no Foundry calls here.

Checks the build folder, zips it the way Foundry website hosting expects
(the folder's contents at the root of the zip, ``index.html`` among them),
works out the version (``--version``, the nearest ``package.json`` or
``git describe``) and turns the API's subdomains into a URL. Every check
raises ``typer.BadParameter`` (a usage error, exit 2) before any call.
"""

import io
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path
from typing import FrozenSet, Iterable, Iterator, Optional, Tuple

import typer

#: Semantic Versioning 2.0.0 (semver.org's regular expression).
SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)

#: A third-party application RID (the only kind that has a website).
APPLICATION_RID = re.compile(
    r"ri\.third-party-applications\.[a-z0-9-]*\.application\..+"
)

#: Files or folders that mark a project folder rather than its build output.
PROJECT_MARKERS = ("package.json", "node_modules")

#: Describes HEAD by its nearest version-looking tag (v1..., 1...); --dirty
#: marks uncommitted changes to tracked files (untracked files, such as a
#: gitignored dist/, don't count).
GIT_DESCRIBE = [
    "git",
    "describe",
    "--tags",
    "--dirty",
    "--match",
    "v[0-9]*",
    "--match",
    "[0-9]*",
]

BUILD_HINT = (
    "build the site first (npm run build) and pass its output folder (Vite: dist)"
)


def check_version(value: str, *, param_hint: str = "'--version'") -> str:
    """Return ``value`` if it is a semantic version, else a usage error."""
    if SEMVER.fullmatch(value):
        return value
    if value[:1] in ("v", "V") and SEMVER.fullmatch(value[1:]):
        raise typer.BadParameter(
            f"{value!r} isn't a semantic version: pass it without the leading "
            f"'v' ({value[1:]}).",
            param_hint=param_hint,
        )
    raise typer.BadParameter(
        f"{value!r} isn't a semantic version: use MAJOR.MINOR.PATCH, such as "
        "0.1.0 or 1.2.3.",
        param_hint=param_hint,
    )


def check_application_rid(rid: str) -> str:
    """Return ``rid`` if it names a third-party application, else a usage error."""
    if APPLICATION_RID.fullmatch(rid):
        return rid
    raise typer.BadParameter(
        f"{rid!r} isn't a third-party application RID "
        "(ri.third-party-applications.main.application.<id>): find it in "
        "Developer Console, on the application's overview.",
        param_hint="'--application'",
    )


def check_site_folder(folder: Path) -> Path:
    """Return the build folder, resolved, if it can be deployed as it is."""
    hint = "'DIST_DIR'"
    if not folder.exists():
        raise typer.BadParameter(
            f"Folder {str(folder)!r} doesn't exist: {BUILD_HINT}.", param_hint=hint
        )
    if not folder.is_dir():
        raise typer.BadParameter(
            f"{str(folder)!r} is not a folder: pass the site's build output "
            "folder (Vite: dist); pltr zips it for you.",
            param_hint=hint,
        )
    markers = [name for name in PROJECT_MARKERS if (folder / name).exists()]
    if markers:
        raise typer.BadParameter(
            f"{str(folder)!r} looks like the project folder (it has "
            f"{markers[0]}), not its build output: {BUILD_HINT}.",
            param_hint=hint,
        )
    if not (folder / "index.html").is_file():
        nested = sorted(p.parent.name for p in folder.glob("*/index.html"))
        where = (
            f" (there is one in {', '.join(nested)}/: pass that folder)"
            if nested
            else ""
        )
        raise typer.BadParameter(
            f"{str(folder)!r} has no index.html at its root{where}. Foundry "
            f"serves index.html from the root of the upload: {BUILD_HINT}.",
            param_hint=hint,
        )
    return folder.resolve()


#: Folders never uploaded: a .git folder in a build output would publish the
#: repository's history.
SKIPPED_FOLDERS = (".git",)


def _site_entries(folder: Path) -> Iterator[Tuple[str, str, bool]]:
    """``(name in the zip, path, is a folder)`` for everything in ``folder``.

    Links are followed, as ``zip -r`` does; a broken link or a link back to a
    folder it is in is a usage error. Hidden files (``.well-known``) are kept;
    ``.git`` folders are left out.
    """
    hint = "'DIST_DIR'"

    def walk(directory: str, prefix: str, ancestors: FrozenSet[str]) -> Iterator:
        for entry in sorted(os.scandir(directory), key=lambda e: e.name):
            name = prefix + entry.name
            if entry.is_dir(follow_symlinks=True):
                if entry.name in SKIPPED_FOLDERS:
                    continue
                real = os.path.realpath(entry.path)
                if real in ancestors:
                    raise typer.BadParameter(
                        f"{name} links back to a folder it is in (a loop): "
                        "remove the link.",
                        param_hint=hint,
                    )
                yield name + "/", entry.path, True
                yield from walk(entry.path, name + "/", ancestors | {real})
            elif entry.is_file(follow_symlinks=True):
                yield name, entry.path, False
            elif entry.is_symlink():
                raise typer.BadParameter(
                    f"{name} is a broken link: fix or remove it.", param_hint=hint
                )

    yield from walk(str(folder), "", frozenset({os.path.realpath(folder)}))


def zip_site(folder: Path) -> Tuple[bytes, int]:
    """Zip the folder's contents (not the folder itself); return the bytes and
    the number of files. Folders get their own entries, as ``zip -r`` makes,
    and files dated before 1980 (reproducible builds) are dated 1980."""
    buffer = io.BytesIO()
    count = 0
    with zipfile.ZipFile(
        buffer, "w", compression=zipfile.ZIP_DEFLATED, strict_timestamps=False
    ) as archive:
        for name, path, is_folder in _site_entries(folder):
            archive.write(path, name)
            count += 0 if is_folder else 1
    return buffer.getvalue(), count


def _parents(start: Path) -> Iterable[Path]:
    return [start, *start.parents]


def version_from_package_json(folder: Path) -> Tuple[str, Path]:
    """The ``version`` of the nearest ``package.json`` at or above the build
    folder's parent, and that file."""
    hint = "'--auto-version'"
    start = folder.resolve().parent
    for directory in _parents(start):
        candidate = directory / "package.json"
        if candidate.is_file():
            break
    else:
        raise typer.BadParameter(
            f"No package.json at or above {str(start)!r}: pass --version.",
            param_hint=hint,
        )
    try:
        data = json.loads(candidate.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(
            f"{str(candidate)!r} isn't valid JSON ({exc}).", param_hint=hint
        ) from None
    version = data.get("version") if isinstance(data, dict) else None
    if not isinstance(version, str):
        raise typer.BadParameter(
            f'{str(candidate)!r} has no "version": add one, or pass --version.',
            param_hint=hint,
        )
    check_version(version, param_hint=f'"version" in {candidate}')
    return version, candidate


def version_from_git_describe(folder: Path) -> Tuple[str, str]:
    """The version ``git describe --tags --dirty`` gives for the build folder's
    repository, and git's own output.

    Only tags that look like versions count (``v1...``, ``1...``), so a
    ``release-2026`` or ``@scope/app@1.0.0`` tag is passed over. A leading
    ``v`` is dropped. On a tag that is the tag (``v1.2.3`` -> ``1.2.3``);
    commits after it make a semver pre-release (``1.2.3-4-gabc1234``), as
    ``@osdk/cli site deploy`` does. A tree with uncommitted changes to tracked
    files, or a version tag that isn't a semantic version, is a usage error:
    the version would not say what was built.
    """
    hint = "'--auto-version'"
    start = folder.resolve().parent
    try:
        completed = subprocess.run(
            GIT_DESCRIBE,
            cwd=start,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        raise typer.BadParameter(
            "git isn't installed (or isn't on PATH): pass --version.", param_hint=hint
        ) from None
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise typer.BadParameter(
            f"pltr couldn't run git in {str(start)!r} ({exc}): pass --version.",
            param_hint=hint,
        ) from None
    if completed.returncode != 0:
        lines = (completed.stderr or completed.stdout or "").strip().splitlines()
        reason = lines[-1] if lines else f"exit code {completed.returncode}"
        raise typer.BadParameter(
            f"`git describe --tags` failed in {str(start)!r}: {reason}. Tag the "
            "commit you built (git tag v0.1.0), or pass --version.",
            param_hint=hint,
        )
    described = completed.stdout.strip()
    if described.endswith("-dirty"):
        raise typer.BadParameter(
            f"git describe gave {described!r}: tracked files have uncommitted "
            "changes, so the version wouldn't say what was built. Commit them, "
            "or pass --version.",
            param_hint=hint,
        )
    version = described[1:] if described[:1] in ("v", "V") else described
    if not SEMVER.fullmatch(version):
        raise typer.BadParameter(
            f"git describe gave {described!r}, and {version!r} isn't a semantic "
            "version: tag the commit vMAJOR.MINOR.PATCH (git tag v0.1.0), or "
            "pass --version.",
            param_hint=hint,
        )
    return version, described


def site_url(subdomain: str) -> Optional[str]:
    """``https://<subdomain>`` when the API gave a full hostname, else None.

    Foundry returns each subdomain as the whole hostname the site is served
    from (``<name>.apps.<region>.<domain>``, checked on a live stack); pltr
    doesn't guess a domain for a bare name.
    """
    if "." not in subdomain or not re.fullmatch(r"[A-Za-z0-9.-]+", subdomain):
        return None
    return f"https://{subdomain}"
