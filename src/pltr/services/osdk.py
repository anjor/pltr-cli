"""OSDK package generation for ``pltr osdk generate`` (#220).

pltr doesn't generate OSDK code itself: it runs Palantir's
``@osdk/foundry-sdk-generator``, pinned to :data:`GENERATOR_VERSION`, with
Node.js, and the host and token of the pltr profile. No Developer Console
application is needed.

The generator's own command line takes the token only as ``--authToken``,
where anyone who can list processes can read it, so pltr never runs that
command line. Instead:

1. ``npm ci`` installs the generator and every dependency, exactly as locked
   in the package-lock.json pltr ships (:data:`LOCK_DIR`), into pltr's cache,
   ``~/.cache/pltr/osdk-generator/<version>``, once, without install scripts.
2. ``node osdk_generate.mjs`` (:data:`HELPER`, shipped with pltr) imports the
   generator's library entry point from there and calls its exported
   ``cli(argv)`` in its own process, adding ``--authToken`` in memory. The
   token reaches the helper only in the :data:`TOKEN_ENV_VAR` environment
   variable, which only the same user (and root) can read, and the helper
   deletes it before the generator runs.

No subprocess inherits ``FOUNDRY_TOKEN`` or ``FOUNDRY_CLIENT_SECRET``, and
only the helper gets the token. The token is never written to disk or to a
log, and it is redacted from any generator output pltr shows.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..contract import ExitCode, PltrError, WorkFailed
from .base import BaseService

#: The generator pltr runs.
GENERATOR_PACKAGE = "@osdk/foundry-sdk-generator"
#: The generator version pltr runs: the one proven end to end (#220). Bump it
#: here; ``@osdk/client``, ``@osdk/react`` and ``@osdk/api`` are released with
#: the same version numbers, so they follow it.
GENERATOR_VERSION = "2.87.0"
GENERATOR_SPEC = f"{GENERATOR_PACKAGE}@{GENERATOR_VERSION}"
#: ``@osdk/oauth`` has its own version numbers; this one worked with 2.87.0.
OSDK_OAUTH_VERSION = "1.14.0"

#: The generator declares no ``engines``; its dependencies need Node.js 18
#: (``find-up`` 7, ``eventsource-parser`` 3: ``engines.node >=18``).
MIN_NODE_VERSION = (18, 0, 0)
#: npm 8 came with Node.js 16; older npm can't be trusted with ``--prefix``.
MIN_NPM_VERSION = (8, 0, 0)

#: The environment variable the helper reads the token from (the helper
#: names it too).
TOKEN_ENV_VAR = "PLTR_OSDK_TOKEN"
#: pltr's helper script, shipped in the wheel next to this module.
HELPER = Path(__file__).with_name("osdk_generate.mjs")
#: The generator's package.json and package-lock.json, shipped in the wheel:
#: ``npm ci`` installs exactly this tree, so none of the generator's
#: dependencies (which run in the process that holds the token) can change
#: under pltr. To bump the generator, change GENERATOR_VERSION and the
#: dependency in package.json, then in that directory run
#: ``npm install --package-lock-only --ignore-scripts``.
LOCK_DIR = Path(__file__).with_name("osdk_generator")
#: Written last into an install: the digest of the lockfile it installed.
INSTALL_MARKER = ".pltr-installed"

#: Credentials npm's environment never gets.
_SECRET_ENV_VARS = (TOKEN_ENV_VAR, "FOUNDRY_TOKEN", "FOUNDRY_CLIENT_SECRET")
#: Seconds before pltr gives up on ``npm install`` or the generator.
INSTALL_TIMEOUT = 600
GENERATE_TIMEOUT = 600

NODE_HINT = (
    "Install Node.js 18 or later with npm (https://nodejs.org, or `nvm install "
    "--lts`) and make sure `node` and `npm` are on PATH."
)

#: The generator's flags in its messages, and pltr's.
_FLAG_NAMES = {
    "--objectTypes": "--object-type",
    "--actionTypes": "--action-type",
    "--queryTypes": "--query-type",
    "--linkTypes": "--link-type",
    "--interfaceTypes": "--interface-type",
}

_VERSION = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


class MissingDependency(PltrError):
    """Node.js or npm is missing or too old."""

    error_type = "missing_dependency"
    exit_code = ExitCode.USAGE


@dataclass(frozen=True)
class NodeTools:
    """The Node.js and npm executables pltr runs, and their versions."""

    node: str
    npm: str
    node_version: str
    npm_version: str


def _version_text(version: Tuple[int, ...]) -> str:
    return ".".join(str(part) for part in version)


def _tool_version(
    tool: str, label: str, minimum: Tuple[int, int, int]
) -> Tuple[str, str]:
    """The executable for ``tool`` and its version; MissingDependency if unusable."""
    required = f">={_version_text(minimum)}"
    executable = shutil.which(tool)
    if executable is None:
        raise MissingDependency(
            f"{label} is not installed (no `{tool}` on PATH): pltr osdk generate "
            f"runs {GENERATOR_SPEC} with it.",
            parameters={"tool": tool, "required": required},
            hint=NODE_HINT,
        )
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            env=_clean_env(),
            timeout=60,
        )
        output = result.stdout.strip()
        match = _VERSION.search(output) if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError) as exc:
        output, match = str(exc), None
    if match is None:
        raise MissingDependency(
            f"Could not run `{executable} --version` to check {label}: "
            f"{output or 'no output'}",
            parameters={"tool": tool, "required": required},
            hint=NODE_HINT,
        )
    version = tuple(int(part) for part in match.groups())
    found = _version_text(version)
    if version < minimum:
        raise MissingDependency(
            f"{label} {found} is too old: pltr osdk generate needs {label} "
            f"{_version_text(minimum)} or later.",
            parameters={"tool": tool, "required": required, "found": found},
            hint=NODE_HINT,
        )
    return executable, found


def find_node_tools() -> NodeTools:
    """Check that Node.js and npm are installed and new enough.

    Raises:
        MissingDependency: ``missing_dependency`` (exit 2), with the tool, the
            version found and the version required in ``parameters``
    """
    node, node_version = _tool_version("node", "Node.js", MIN_NODE_VERSION)
    npm, npm_version = _tool_version("npm", "npm", MIN_NPM_VERSION)
    return NodeTools(node, npm, node_version, npm_version)


# ------------------------------------------------------------------ install


def generator_dir() -> Path:
    """Where pltr installs the pinned generator (``~/.cache/pltr/...``)."""
    return Path.home() / ".cache" / "pltr" / "osdk-generator" / GENERATOR_VERSION


def _lock_digest() -> str:
    """SHA-256 of the shipped package.json and lockfile: what an install holds."""
    digest = hashlib.sha256()
    for name in ("package.json", "package-lock.json"):
        digest.update((LOCK_DIR / name).read_bytes())
    return digest.hexdigest()


def _has_generator(directory: Path) -> bool:
    manifest = directory / "node_modules" / "@osdk" / "foundry-sdk-generator"
    try:
        data = json.loads((manifest / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("version") == GENERATOR_VERSION


def _installed(directory: Path) -> bool:
    """A complete install of the shipped lockfile (its marker is written last)."""
    try:
        marker = (directory / INSTALL_MARKER).read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return marker == _lock_digest() and _has_generator(directory)


def generator_installed() -> bool:
    """Whether the pinned generator is in :func:`generator_dir` already."""
    return _installed(generator_dir())


def _clean_env() -> Dict[str, str]:
    """pltr's environment without Foundry credentials, for every subprocess.

    The helper gets the token on top of this, in :data:`TOKEN_ENV_VAR`.
    """
    return {k: v for k, v in os.environ.items() if k not in _SECRET_ENV_VARS}


def _run(
    args: Sequence[str],
    *,
    env: Dict[str, str],
    timeout: int,
    step: str,
    cwd: Optional[Path] = None,
) -> "subprocess.CompletedProcess[str]":
    try:
        return subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            env=env,
            cwd=cwd,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise PltrError(
            f"The OSDK {step} step didn't finish within {timeout} seconds.",
            error_type="timeout",
            exit_code=ExitCode.API,
            parameters={"step": step},
        ) from None


def _tail(text: str, lines: int = 20) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def ensure_generator(tools: NodeTools) -> Path:
    """Install the pinned generator into :func:`generator_dir`, once.

    npm installs into a staging directory next to it, which is moved into
    place only when the install is complete, so an interrupted or failed
    install leaves nothing behind. npm runs without Foundry credentials and
    without install scripts.

    Raises:
        WorkFailed: ``npm install`` failed (``parameters.step`` is ``install``)
    """
    target = generator_dir()
    if _installed(target):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{GENERATOR_VERSION}-", dir=str(target.parent))
    )
    try:
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(LOCK_DIR / name, staging / name)
        result = _run(
            [
                tools.npm,
                "ci",
                "--prefix",
                str(staging),
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
                "--loglevel=error",
            ],
            env=_clean_env(),
            timeout=INSTALL_TIMEOUT,
            step="install",
            cwd=staging,
        )
        if result.returncode != 0 or not _has_generator(staging):
            output = _tail(result.stderr) or _tail(result.stdout) or "no output"
            raise WorkFailed(
                f"npm couldn't install {GENERATOR_SPEC} (exit code "
                f"{result.returncode}):\n{output}",
                parameters={"step": "install", "exitCode": result.returncode},
                hint=(
                    "Check that npm can reach its registry (proxy, .npmrc), "
                    f"then run the command again. `npm view {GENERATOR_SPEC}` "
                    "tests the connection."
                ),
            )
        (staging / INSTALL_MARKER).write_text(_lock_digest(), encoding="utf-8")
        if target.exists() and not _installed(target):
            shutil.rmtree(target, ignore_errors=True)  # an old or broken install
        try:
            os.replace(staging, target)
        except OSError as exc:
            if _installed(target):  # another pltr finished first
                return target
            raise WorkFailed(
                f"Couldn't move the installed generator into {target}: {exc}",
                parameters={"step": "install"},
                hint=f"Delete {target} and run the command again.",
            ) from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target


# ----------------------------------------------------------------- generate


def _redact(text: str, token: str) -> str:
    return text.replace(token, "<redacted>") if token else text


def _pltr_flags(text: str) -> str:
    for theirs, ours in _FLAG_NAMES.items():
        text = text.replace(theirs, ours)
    return text


def _generator_errors(stdout: str) -> List[Dict[str, Any]]:
    """The ERROR entries of the generator's log (JSON Lines on its stdout)."""
    errors: List[Dict[str, Any]] = []
    for line in stdout.splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("level") != "ERROR":
            continue
        error: Dict[str, Any] = {"message": _pltr_flags(str(entry.get("message")))}
        for key in ("params", "unsafeParams"):
            details = entry.get(key)
            if isinstance(details, dict):
                error.update(details)
        stacktrace = entry.get("stacktrace")
        if isinstance(stacktrace, str) and stacktrace.strip():
            first_line = stacktrace.strip().splitlines()[0]
            if str(entry.get("message")) not in first_line:  # it adds something
                error["error"] = _pltr_flags(first_line)
        errors.append(error)
    return errors


def _describe(error: Dict[str, Any]) -> str:
    details = ", ".join(
        f"{key}={json.dumps(value)}" for key, value in error.items() if key != "message"
    )
    return f"{error['message']} ({details})" if details else error["message"]


#: Generator errors about the types asked for (names, or types they need).
_TYPE_ERRORS = re.compile(
    r"Unable to find|unloaded (object|interface) type|Link types were specified|"
    r"Unable to load link type|Invalid link type format"
)
#: Node failing to load part of the installed generator.
_BROKEN_INSTALL = re.compile(r"ERR_MODULE_NOT_FOUND|Cannot find (module|package)")


def _generation_failed(
    result: "subprocess.CompletedProcess[str]",
    token: str,
    suggested_command: Optional[str],
) -> WorkFailed:
    errors = _generator_errors(result.stdout)
    if errors:
        detail = "\n".join(f"- {_describe(error)}" for error in errors)
    else:
        detail = _tail(result.stderr) or _tail(result.stdout) or "no output"
    message = (
        f"{GENERATOR_SPEC} failed (exit code {result.returncode}):\n"
        f"{_pltr_flags(detail)}"
    )
    parameters: Dict[str, Any] = {"step": "generate", "exitCode": result.returncode}
    if errors:
        parameters["errors"] = errors
    redacted = json.loads(_redact(json.dumps(parameters), token))
    hint: Optional[str] = None
    if any(_TYPE_ERRORS.search(error["message"]) for error in errors):
        hint = (
            "Check the API names of the object, link, action and query types "
            "with `pltr context ontology <ontology> --types <ObjectType>` (it "
            "lists each type's links and the actions and queries): actions "
            "and queries also need the object types their parameters use."
        )
    else:
        suggested_command = None
        if _BROKEN_INSTALL.search(result.stderr):
            hint = (
                f"The generator's install in {generator_dir()} looks incomplete: "
                "delete that directory and run the command again."
            )
    return WorkFailed(
        _redact(message, token),
        parameters=redacted,
        hint=hint,
        suggested_command=suggested_command,
    )


def _is_generated_package(directory: Path, package_name: str) -> bool:
    """A package the generator made as ``package_name``.

    Its ``package.json`` has that name, the generator's ``"osdk"`` section,
    and ``@osdk/client`` as a peer dependency (an app lists it under
    ``dependencies``).
    """
    try:
        data = json.loads((directory / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict) or data.get("name") != package_name:
        return False
    peers = data.get("peerDependencies")
    return (
        isinstance(data.get("osdk"), dict)
        and isinstance(peers, dict)
        and "@osdk/client" in peers
    )


def package_conflict(
    package_dir: Path, package_name: str, *, replace: bool
) -> Optional[str]:
    """Why the package can't be written to ``package_dir``, or None if it can.

    The generator refuses a non-empty directory. ``--replace`` regenerates a
    package it made before (and nothing else), unless pltr runs inside it.
    """
    if package_dir.is_symlink():
        return (
            f"{package_dir} is a symbolic link, so pltr won't write the package "
            "there: pick another --out."
        )
    if not package_dir.exists():
        return None
    if not package_dir.is_dir():
        return f"{package_dir} exists and is not a directory."
    if not any(package_dir.iterdir()):
        return None
    if not _is_generated_package(package_dir, package_name):
        return (
            f"{package_dir} is not empty and is not an OSDK package generated as "
            f"{package_name}, so pltr won't replace it: pick another --out or "
            "--package-name."
        )
    if not replace:
        return (
            f"{package_dir} already holds {package_name}: pass --replace to "
            "generate it again (the new package replaces it once it is generated)."
        )
    cwd = Path.cwd().resolve()
    if cwd == package_dir.resolve() or package_dir.resolve() in cwd.parents:
        return (
            f"{package_dir} contains the current directory, so pltr won't replace "
            "it: run the command from the app's root."
        )
    return None


def _swap_in(generated: Path, package_dir: Path) -> None:
    """Move the new package to ``package_dir``, keeping the old one until it's there.

    The old package is moved aside next to it, and deleted only once the new
    one is in place, so a failure leaves it as it was: a file held open (a
    dev server on Windows) can't leave half a package behind.

    Raises:
        WorkFailed: a move failed (``parameters.step`` is ``replace``)
    """
    package_dir.parent.mkdir(parents=True, exist_ok=True)
    aside: Optional[Path] = None
    try:
        if package_dir.exists():
            aside = Path(
                tempfile.mkdtemp(prefix=".pltr-osdk-previous-", dir=package_dir.parent)
            )
            os.replace(package_dir, aside / "package")
        os.replace(generated, package_dir)
    except OSError as exc:
        status = "The existing package is unchanged."
        if aside is not None and (aside / "package").exists():
            try:
                os.replace(aside / "package", package_dir)
            except OSError:
                status = f"The previous package is in {aside / 'package'}."
                aside = None  # keep it
        if aside is not None:
            shutil.rmtree(aside, ignore_errors=True)
        raise WorkFailed(
            f"Couldn't move the new package into {package_dir}: {exc}. {status}",
            parameters={"step": "replace"},
            hint=(
                "Close programs that may hold its files open (a dev server, an "
                "editor), then run the command again."
            ),
        ) from exc
    if aside is not None:
        shutil.rmtree(aside, ignore_errors=True)


def generate(
    tools: NodeTools,
    install_dir: Path,
    *,
    foundry_url: str,
    token: str,
    ontology_rid: str,
    package_name: str,
    package_version: str,
    out_dir: Path,
    object_types: Sequence[str],
    action_types: Sequence[str],
    query_types: Sequence[str],
    link_types: Sequence[str],
    interface_types: Sequence[str],
    replace: bool = False,
    suggested_command: Optional[str] = None,
) -> Path:
    """Run the generator through pltr's helper; returns the package directory.

    The token goes to the helper in :data:`TOKEN_ENV_VAR` only; every other
    argument is on its command line, as ``--name=value`` (a value can't be
    read as a flag). The generator writes into a staging directory inside
    ``out_dir``; the package is moved to ``out_dir/package_name`` only once it
    is complete, so a failure leaves an existing package as it was. With
    ``replace`` the existing package (see :func:`package_conflict`) is
    replaced; without it, pltr refuses to touch one. ``suggested_command``
    goes on the error when the generator rejected the types asked for.

    Raises:
        PltrError: ``usage_error`` when :func:`package_conflict` objects
        WorkFailed: the generator failed, or wrote no ``package.json``
            (``parameters.step`` is ``generate``; its logged errors are in
            ``parameters.errors``), or the package couldn't be moved into
            place (``replace``)
    """
    package_dir = out_dir / package_name
    conflict = package_conflict(package_dir, package_name, replace=replace)
    if conflict:
        raise PltrError(conflict, error_type="usage_error", exit_code=ExitCode.USAGE)
    # The directories pltr creates for --out, removed again if nothing is generated.
    created = [p for p in (out_dir, *out_dir.parents) if not p.exists()]
    out_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".pltr-osdk-", dir=str(out_dir)))
    generated_ok = False
    try:
        args = [
            tools.node,
            str(HELPER),
            str(install_dir),
            "generatePackage",
            f"--foundryHostname={foundry_url}",
            f"--ontology={ontology_rid}",
            f"--packageName={package_name}",
            f"--packageVersion={package_version}",
            f"--outputDir={staging}",
        ]
        for flag, values in (
            ("objectTypes", object_types),
            ("actionTypes", action_types),
            ("queryTypes", query_types),
            ("linkTypes", link_types),
            ("interfaceTypes", interface_types),
        ):
            args += [f"--{flag}={value}" for value in values]
        env = _clean_env()
        env[TOKEN_ENV_VAR] = token
        # The generator reports this in its User-Agent (npm sets it for scripts).
        env["npm_package_version"] = GENERATOR_VERSION
        result = _run(args, env=env, timeout=GENERATE_TIMEOUT, step="generate")
        if result.returncode != 0:
            raise _generation_failed(result, token, suggested_command)
        generated = staging / package_name
        if not (generated / "package.json").is_file():
            raise WorkFailed(
                f"{GENERATOR_SPEC} finished but wrote no package.json for "
                f"{package_name}.",
                parameters={"step": "generate", "exitCode": result.returncode},
            )
        _swap_in(generated, package_dir)
        generated_ok = True
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if not generated_ok:
            for directory in created:  # innermost first
                try:
                    directory.rmdir()
                except OSError:
                    break
    return package_dir


class OsdkService(BaseService):
    """The Foundry URL and token the generator uses: the pltr profile's."""

    def _get_service(self) -> Any:
        return self.client.ontologies

    def credentials(self) -> Tuple[str, str]:
        """``(https://<host>, token)`` from the same credentials as every command.

        For OAuth client credentials the token is the client's access token.
        """
        context = self.auth_manager.get_auth_context(self.profile)
        return context.base_url, context.get_token()
