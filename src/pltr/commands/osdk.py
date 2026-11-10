"""`pltr osdk`: OSDK packages for apps, from the pltr profile (#220).

``pltr osdk generate`` runs Palantir's ``@osdk/foundry-sdk-generator`` with
the host and token pltr already has, so an agent can build an OSDK app without
creating a Developer Console application first. How the token is kept off
command lines is in :mod:`pltr.services.osdk`.
"""

import json
import os
import re
import shlex
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import typer
from typing_extensions import Annotated

from ..contract import (
    Columns,
    FormatOption,
    ProfileOption,
    emit,
    info,
    pltr_command,
    spinner,
    success,
)
from ..services import osdk as generator
from ..services.ontology import OntologyService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer(
    help=(
        "Generate OSDK TypeScript packages for apps from the pltr profile "
        "(needs Node.js and npm)."
    )
)

#: npm's rules for a new package name: lowercase, URL-safe, optionally scoped.
_NPM_NAME = re.compile(r"(?:@[a-z0-9-][a-z0-9-._]*/)?[a-z0-9-][a-z0-9-._]*")
#: The generator's own check (``isValidSemver`` in 2.87.0).
_SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)
#: One API name per flag (``A,B`` or a name with spaces is a mistake).
_API_NAME = re.compile(r"[^\s,]+")


#: The result's (and the generator's) name for each type list, and pltr's flag.
_FLAGS = {
    "objectTypes": "--object-type",
    "actionTypes": "--action-type",
    "queryTypes": "--query-type",
    "linkTypes": "--link-type",
    "interfaceTypes": "--interface-type",
}


def _types_option(flag: str, help: str) -> Any:
    return typer.Option(flag, help=f"{help} Repeat it for several.", show_default=False)


ObjectTypesOption = Annotated[
    Optional[List[str]],
    _types_option("--object-type", "Object type API name to include."),
]
ActionTypesOption = Annotated[
    Optional[List[str]],
    _types_option(
        "--action-type",
        "Action type API name to include (include the object types its "
        "parameters take).",
    ),
]
QueryTypesOption = Annotated[
    Optional[List[str]],
    _types_option(
        "--query-type",
        "Query (function) API name to include, optionally as name:version.",
    ),
]
LinkTypesOption = Annotated[
    Optional[List[str]],
    _types_option(
        "--link-type",
        "Link type to include, as ObjectType.linkApiName (both object types "
        "must be included); without it objects have no links.",
    ),
]
InterfaceTypesOption = Annotated[
    Optional[List[str]],
    _types_option("--interface-type", "Interface type API name to include."),
]


def _entries(mapping: Mapping[str, str]) -> str:
    """``{"a": "1"}`` as the package.json line ``"a": "1"``."""
    return ", ".join(f"{json.dumps(k)}: {json.dumps(v)}" for k, v in mapping.items())


COLUMNS: Columns = {
    "Package": "packageName",
    "Version": "packageVersion",
    "Path": "packagePath",
    "Dependency": lambda d: _entries(d["dependency"]),
    "Peer dependencies": lambda d: _entries(d["peerDependencies"]),
    "React dependencies": lambda d: _entries(d["reactDependencies"]),
    "Overrides": lambda d: _entries(d["overrides"]),
    "Ontology": "ontologyRid",
    "Generator": "generator",
    "Notes": lambda d: "\n".join(d["notes"]),
}


def _check_options(
    *,
    out: Path,
    package_name: str,
    package_version: str,
    types: Dict[str, List[str]],
    replace: bool,
) -> None:
    """Usage errors pltr can see before running anything."""
    object_types, link_types = types["objectTypes"], types["linkTypes"]
    for key, values in types.items():
        flag = _FLAGS[key]
        for value in values:
            if not _API_NAME.fullmatch(value):
                raise typer.BadParameter(
                    f"{value!r} is not an API name: give one per {flag}, and "
                    f"repeat it for several ({flag} A {flag} B).",
                    param_hint=f"'{flag}'",
                )
    if not any(values for key, values in types.items() if key != "linkTypes"):
        raise typer.BadParameter(
            "give the types to generate: at least one --object-type (or "
            "--action-type, --query-type, --interface-type).",
            param_hint="'--object-type'",
        )
    if len(package_name) > 214 or not _NPM_NAME.fullmatch(package_name):
        raise typer.BadParameter(
            f"{package_name!r} is not a valid npm package name: use lowercase "
            "letters, digits, '-', '.' and '_', optionally with a scope, as in "
            "@app/sdk.",
            param_hint="'--package-name'",
        )
    if not _SEMVER.fullmatch(package_version):
        raise typer.BadParameter(
            f"{package_version!r} is not a semver version such as 0.0.1.",
            param_hint="'--package-version'",
        )
    for link in link_types:
        object_type, dot, name = link.rpartition(".")
        if not dot or not object_type or not name:
            raise typer.BadParameter(
                f"{link!r} is not in the form ObjectType.linkType (for example "
                "Employee.department).",
                param_hint="'--link-type'",
            )
        if object_type not in object_types:
            raise typer.BadParameter(
                f"--link-type {link} needs --object-type {object_type} too.",
                param_hint="'--link-type'",
            )
    if out.exists() and not out.is_dir():
        raise typer.BadParameter(
            f"{out} exists and is not a directory.", param_hint="'--out'"
        )
    conflict = generator.package_conflict(
        out / package_name, package_name, replace=replace
    )
    if conflict:
        raise typer.BadParameter(conflict, param_hint="'--out'")


def _file_spec(package_dir: Path) -> str:
    """The ``file:`` dependency for the package, relative to the current directory."""
    try:
        relative = Path(os.path.relpath(package_dir, Path.cwd())).as_posix()
    except ValueError:  # on another drive (Windows)
        return f"file:{package_dir.as_posix()}"
    return f"file:{relative}" if relative.startswith("..") else f"file:./{relative}"


def _notes(version: str) -> List[str]:
    return [
        "Add the dependency, peerDependencies (and reactDependencies for a "
        'React app) to the app\'s package.json "dependencies", then run npm '
        "install. The file: path is relative to the current directory.",
        f'Add "overrides": {{"@osdk/api": "{version}"}} to the app\'s '
        f"package.json: @osdk/react {version} pulls in a newer @osdk/api than "
        f"@osdk/client {version} uses, and type checking then fails with TS2322.",
        "To change the types later, run the command again with --replace: the "
        "new package replaces this one once it is generated.",
    ]


def _suggest(profile: Optional[str], *argv: str) -> str:
    command = " ".join(shlex.quote(arg) for arg in ("pltr", *argv))
    return f"{command} --profile {shlex.quote(profile)}" if profile else command


@app.command("generate")
@pltr_command(
    sdk="ontologies.Ontology.get",
    no_emit_code=(
        "it runs @osdk/foundry-sdk-generator with Node.js; `pltr ontology get "
        "--emit-code` shows the call that looks up the ontology."
    ),
)
def generate(
    ontology: Annotated[
        str,
        typer.Option(
            "--ontology",
            help=(
                "Ontology API name or RID (ri.ontology.main.ontology.<id>); find "
                "it with 'pltr ontology list'."
            ),
            autocompletion=complete_rid,
            show_default=False,
        ),
    ],
    out: Annotated[
        Path,
        typer.Option(
            "--out",
            help=(
                "Directory for the package: it is written to "
                "<out>/<package-name>, e.g. ./osdk/@app/sdk."
            ),
            show_default=False,
        ),
    ],
    object_types: ObjectTypesOption = None,
    action_types: ActionTypesOption = None,
    query_types: QueryTypesOption = None,
    link_types: LinkTypesOption = None,
    interface_types: InterfaceTypesOption = None,
    package_name: Annotated[
        str,
        typer.Option("--package-name", help="npm name of the generated package."),
    ] = "@app/sdk",
    package_version: Annotated[
        str,
        typer.Option("--package-version", help="Version of the generated package."),
    ] = "0.0.1",
    replace: Annotated[
        bool,
        typer.Option(
            "--replace",
            help=(
                "Generate a package that exists already again (to change its "
                "types, or after the ontology changed). The new package replaces "
                "it only once it is generated, and only a package generated "
                "under this name is ever replaced."
            ),
        ),
    ] = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """
    Generate an OSDK TypeScript package for an app, from the pltr profile.

    Runs Palantir's @osdk/foundry-sdk-generator (the version pltr pins) with
    Node.js 18 or later and npm, using the host and token pltr uses, so no
    Developer Console application is needed. The token reaches the generator
    through an environment variable, never a command line. The first run
    installs the generator into ~/.cache/pltr/osdk-generator.

    The result says how to use the package: the dependency line for the app's
    package.json ("@app/sdk": "file:./osdk/@app/sdk", relative to the current
    directory), the @osdk packages and versions the app needs, and the
    "overrides" entry that keeps @osdk/react and @osdk/client on one
    @osdk/api version.

    Examples:

      pltr osdk generate --ontology my-ontology --object-type Employee --action-type promote-employee --out ./osdk --package-name @hr-app/sdk
    """
    types = {
        "objectTypes": list(object_types or []),
        "actionTypes": list(action_types or []),
        "queryTypes": list(query_types or []),
        "linkTypes": list(link_types or []),
        "interfaceTypes": list(interface_types or []),
    }
    out_dir = out.expanduser().resolve()
    _check_options(
        out=out_dir,
        package_name=package_name,
        package_version=package_version,
        types=types,
        replace=replace,
    )
    tools = generator.find_node_tools()
    with spinner(f"Looking up ontology {ontology}..."):
        ontology_rid = OntologyService(profile=profile).get_ontology(ontology).rid
    foundry_url, token = generator.OsdkService(profile=profile).credentials()
    if generator.generator_installed():
        install_dir = generator.generator_dir()
    else:
        with spinner(f"Installing {generator.GENERATOR_SPEC} (first run only)..."):
            install_dir = generator.ensure_generator(tools)
        info(f"Installed {generator.GENERATOR_SPEC} into {install_dir}")
    with spinner(f"Generating {package_name} with {generator.GENERATOR_SPEC}..."):
        package_dir = generator.generate(
            tools,
            install_dir,
            foundry_url=foundry_url,
            token=token,
            ontology_rid=ontology_rid,
            package_name=package_name,
            package_version=package_version,
            out_dir=out_dir,
            object_types=types["objectTypes"],
            action_types=types["actionTypes"],
            query_types=types["queryTypes"],
            link_types=types["linkTypes"],
            interface_types=types["interfaceTypes"],
            replace=replace,
            suggested_command=_suggest(profile, "context", "ontology", ontology_rid),
        )
    cache_rid(ontology_rid)

    version = generator.GENERATOR_VERSION
    document: Dict[str, Any] = {
        "packageName": package_name,
        "packageVersion": package_version,
        "packagePath": str(package_dir),
        "dependency": {package_name: _file_spec(package_dir)},
        "ontologyRid": ontology_rid,
    }
    document.update({key: values for key, values in types.items() if values})
    document.update(
        {
            "generator": generator.GENERATOR_SPEC,
            "peerDependencies": {"@osdk/client": version},
            "reactDependencies": {
                "@osdk/oauth": generator.OSDK_OAUTH_VERSION,
                "@osdk/react": version,
            },
            "overrides": {"@osdk/api": version},
            "notes": _notes(version),
        }
    )
    emit(document, format=format, columns=COLUMNS, title="OSDK package")
    success(f"Generated {package_name} in {package_dir}")
