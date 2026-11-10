"""A fake Node.js toolchain for `pltr osdk generate` tests (#220).

``FakeNode.apply(monkeypatch)`` replaces ``shutil.which`` and
``subprocess.run``: ``node``/``npm --version`` answer with the configured
versions, ``npm install`` writes the generator's ``package.json`` where npm
would, and running pltr's helper writes the generated package's
``package.json`` into ``--outputDir``. Every call is recorded in ``calls``
(argv, environment, working directory), so tests can check where the token
went.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

GENERATOR_PACKAGE = "@osdk/foundry-sdk-generator"
NODE = "/fake/bin/node"
NPM = "/fake/bin/npm"


@dataclass
class Call:
    args: List[str]
    env: Optional[Dict[str, str]]
    cwd: Optional[str]
    kwargs: Dict[str, Any]
    #: For an install: the files in its directory when npm ran.
    files: Dict[str, str] = field(default_factory=dict)

    @property
    def is_install(self) -> bool:
        return self.args[0] == NPM and self.args[1] in ("ci", "install")

    @property
    def is_generate(self) -> bool:
        return len(self.args) > 1 and self.args[1].endswith("osdk_generate.mjs")


@dataclass
class FakeNode:
    node_version: Optional[str] = "v26.13.0"  # None: node isn't on PATH
    npm_version: Optional[str] = "11.6.2"  # None: npm isn't on PATH
    generator_version: str = "2.87.0"
    install_returncode: int = 0
    install_stderr: str = ""
    generate_returncode: int = 0
    generate_stdout: str = ""
    generate_stderr: str = ""
    #: Write the generated package (False: the generator "succeeds" but writes nothing).
    write_package: bool = True
    calls: List[Call] = field(default_factory=list)

    def apply(self, monkeypatch: Any) -> "FakeNode":
        monkeypatch.setattr(shutil, "which", self.which)
        monkeypatch.setattr(subprocess, "run", self.run)
        return self

    def which(self, name: str, *args: Any, **kwargs: Any) -> Optional[str]:
        if name == "node":
            return NODE if self.node_version is not None else None
        if name == "npm":
            return NPM if self.npm_version is not None else None
        return None

    @property
    def installs(self) -> List[Call]:
        return [call for call in self.calls if call.is_install]

    @property
    def generations(self) -> List[Call]:
        return [call for call in self.calls if call.is_generate]

    def run(self, args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
        args = [str(arg) for arg in args]
        cwd = kwargs.get("cwd")
        call = Call(args, kwargs.get("env"), str(cwd) if cwd else None, kwargs)
        self.calls.append(call)
        if args[1:] == ["--version"]:
            version = self.node_version if args[0] == NODE else self.npm_version
            return subprocess.CompletedProcess(args, 0, f"{version}\n", "")
        if call.is_install:
            return self._install(args, call)
        if call.is_generate:
            return self._generate(args)
        raise AssertionError(f"unexpected subprocess: {args}")

    def _install(self, args: List[str], call: Call) -> subprocess.CompletedProcess:
        prefix = Path(args[args.index("--prefix") + 1]) if "--prefix" in args else None
        prefix = prefix or Path(call.cwd or ".")
        call.files = {p.name: p.read_text() for p in prefix.iterdir() if p.is_file()}
        if self.install_returncode == 0:
            package = prefix / "node_modules" / "@osdk" / "foundry-sdk-generator"
            package.mkdir(parents=True)
            (package / "package.json").write_text(
                json.dumps(
                    {"name": GENERATOR_PACKAGE, "version": self.generator_version}
                )
            )
        return subprocess.CompletedProcess(
            args, self.install_returncode, "", self.install_stderr
        )

    def _generate(self, args: List[str]) -> subprocess.CompletedProcess:
        options = dict(
            arg[2:].split("=", 1) for arg in args if arg.startswith("--") and "=" in arg
        )
        if self.generate_returncode == 0 and self.write_package:
            package = Path(options["outputDir"]) / options["packageName"]
            package.mkdir(parents=True, exist_ok=True)
            (package / "package.json").write_text(
                json.dumps(
                    generated_package_json(
                        options["packageName"], options["packageVersion"]
                    )
                )
            )
        return subprocess.CompletedProcess(
            args,
            self.generate_returncode,
            self.generate_stdout,
            self.generate_stderr,
        )


def generated_package_json(name: str, version: str = "0.0.1") -> Dict[str, Any]:
    """The package.json the generator writes (2.87.0), as in a real package."""
    return {
        "name": name,
        "version": version,
        "main": "./cjs/index.js",
        "types": "./cjs/index.d.ts",
        "osdk": {},
        "exports": {
            ".": {
                "script": {
                    "types": "./dist/bundle/index.d.mts",
                    "default": "./dist/bundle/index.mjs",
                },
                "require": {"types": "./cjs/index.d.ts", "default": "./cjs/index.js"},
                "import": {"types": "./esm/index.d.ts", "default": "./esm/index.js"},
                "types": "./cjs/index.d.ts",
                "default": "./cjs/index.js",
            }
        },
        "dependencies": {},
        "peerDependencies": {"@osdk/client": "^2.87.0"},
        "type": "commonjs",
    }


def generator_log(
    level: str,
    message: str,
    unsafe_params: Optional[Dict[str, Any]] = None,
    stacktrace: Optional[str] = None,
) -> str:
    """One line of the generator's log (its ``SlsLogger``, on stdout).

    A ``GeneratorError``'s details (the API names it couldn't find) are in
    ``unsafeParams``.
    """
    entry: Dict[str, Any] = {
        "type": "service.1",
        "level": level,
        "time": "2026-11-10T12:00:00.000Z",
        "origin": "@osdk/foundry-sdk-generator",
        "thread": "main",
        "message": message,
        "params": {},
    }
    if unsafe_params:
        entry["unsafeParams"] = unsafe_params
    else:
        entry["safe"] = True
    if stacktrace:
        entry["stacktrace"] = stacktrace
    return json.dumps(entry)
