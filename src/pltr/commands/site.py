"""`pltr site`: host a built web app on Foundry (#221).

A third-party application created in Developer Console can host a static
site (an OSDK React app, say). ``pltr site deploy`` zips the build folder,
uploads it as a new website version and deploys it, in one command, through
the public API (``ThirdPartyApplication.Website``, GA). ``pltr site
versions`` lists the uploaded versions and ``pltr site rollback`` deploys one
of them again.

The deploy commands print a pltr document, not one API response:
``thirdPartyApplicationRid``, ``version``, ``deployed``, and after a deploy
the ``Website``'s ``deployedVersion`` and ``subdomains`` plus ``url``
(``https://`` + the first subdomain, when the API gives a full hostname).
"""

import shlex
from pathlib import Path
from typing import Any, Dict, Optional

import click
import typer
from typing_extensions import Annotated

from ..contract import (
    AllPagesOption,
    Columns,
    ExitCode,
    FormatOption,
    MaxPagesOption,
    OutputOption,
    PageSizeOption,
    PageTokenOption,
    PltrError,
    ProfileOption,
    YesOption,
    collect_pages,
    confirm_destructive,
    emit,
    info,
    pltr_command,
    resource_option,
    spinner,
    success,
    warn,
)
from ..services import site as bundle
from ..services.third_party_applications import (
    ThirdPartyApplicationsService,
    foundry_error_name,
)
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer(
    help=(
        "Host a built web app on Foundry: zip, upload and deploy it as a "
        "third-party application's website.\n\n"
        "Before the first deploy, in Developer Console: turn on website hosting "
        "for the application and request a subdomain (it must be approved). "
        "Visitors also need the domain on Control Panel's network ingress "
        "allowlist, and sign-in needs https://<domain>/auth/callback registered "
        "as a redirect URL of the application."
    )
)

ApplicationOption = Annotated[
    str,
    resource_option(
        "--application",
        kind="third-party-application",
        help=(
            "RID of the third-party application whose website to use "
            "(ri.third-party-applications.main.application.<id>; shown in "
            "Developer Console)."
        ),
        autocompletion=complete_rid,
        show_default=False,
    ),
]

TimeoutOption = Annotated[
    float,
    typer.Option(
        "--timeout",
        min=0,
        help=(
            "Seconds to keep retrying the deploy while Foundry scans the upload "
            "for vulnerabilities (exit 9 after that; the version stays uploaded)."
        ),
    ),
]

#: Table/CSV columns of the document `site deploy`/`site rollback` print.
SITE_COLUMNS: Columns = {
    "Application": "thirdPartyApplicationRid",
    "Version": "version",
    "Deployed": "deployed",
    "Deployed Version": "deployedVersion",
    "URL": "url",
    "Subdomains": lambda doc: ", ".join(doc.get("subdomains", [])),
}

VERSION_COLUMNS: Columns = {"Version": "version"}

AUTO_VERSIONS = ("package-json", "git-describe")


def _command(*argv: str, profile: Optional[str]) -> str:
    """A pltr command line, quoted, with the profile in use."""
    line = " ".join(shlex.quote(arg) for arg in argv)
    return f"{line} --profile {shlex.quote(profile)}" if profile else line


def _rollback(
    version: str, application: str, profile: Optional[str], *, yes: bool = True
) -> str:
    """The `pltr site rollback` command that deploys an uploaded version."""
    argv = ["pltr", "site", "rollback", version, "--application", application]
    return _command(*argv, *(["--yes"] if yes else []), profile=profile)


#: Deploy errors after which the uploaded version can never go live.
UNDEPLOYABLE = ("SiteAssetHasVulnerabilities", "ScanningErrored")


def _deploy_failed(
    exc: BaseException,
    version: str,
    application: str,
    rollback: str,
    profile: Optional[str],
) -> str:
    """What to do after the deploy of an uploaded version failed."""
    from foundry_sdk import _errors as sdk

    if not isinstance(exc, sdk.PalantirRPCException):
        # No error answer from Foundry (a network error, an answer pltr can't
        # read): the deploy may have gone through.
        website = _command(
            "pltr",
            "api",
            "third-party-applications",
            "third-party-application",
            "website",
            "get",
            application,
            profile=profile,
        )
        return (
            f"Uploaded version {version}, and it may have been deployed (pltr "
            f"couldn't read Foundry's answer): check with '{website}', and if "
            f"deployedVersion isn't {version}, deploy it with '{rollback}'"
        )
    if foundry_error_name(exc) in UNDEPLOYABLE:
        return (
            f"Uploaded version {version}, but Foundry won't deploy it: fix what "
            "the Website hosting page of Developer Console reports, then build "
            "and upload a new version"
        )
    return (
        f"Uploaded version {version}, but deploying it failed; once fixed, "
        f"deploy it with '{rollback}'"
    )


def _version(version: Optional[str], auto_version: Optional[str], folder: Path) -> str:
    """The version to upload: --version, or what --auto-version finds."""
    if version is not None and auto_version is not None:
        raise typer.BadParameter(
            "Pass --version or --auto-version, not both.", param_hint="'--version'"
        )
    if version is not None:
        return bundle.check_version(version)
    if auto_version == "package-json":
        found, path = bundle.version_from_package_json(folder)
        info(f"Version {found} (from {path})")
        return found
    if auto_version == "git-describe":
        found, described = bundle.version_from_git_describe(folder)
        info(f"Version {found} (git describe: {described})")
        return found
    raise typer.BadParameter(
        "Pass the version to upload: --version x.y.z, or --auto-version "
        "package-json|git-describe (pltr doesn't make one up).",
        param_hint="'--version'",
    )


def _deployed(application: str, version: str, website: Any) -> Dict[str, Any]:
    """The document a deploy prints, from the ``Website`` the API returned."""
    document: Dict[str, Any] = {
        "thirdPartyApplicationRid": application,
        "version": version,
        "deployed": True,
    }
    if website.deployed_version is not None:
        document["deployedVersion"] = website.deployed_version
    if website.deployed_version != version:
        warn(
            f"Foundry reports version {website.deployed_version} as deployed, "
            f"not {version}: check the Website hosting page of Developer Console."
        )
    document["subdomains"] = list(website.subdomains)
    urls = [bundle.site_url(subdomain) for subdomain in website.subdomains]
    if not website.subdomains:
        warn(
            "The website has no subdomain yet, so it has no URL: request one "
            "under Website hosting in Developer Console, and wait until it is "
            "approved."
        )
    elif urls[0] is None:
        warn(
            f"The API gave the subdomain {website.subdomains[0]!r} without its "
            "domain, so pltr can't build the site's URL: find it under Website "
            "hosting in Developer Console."
        )
    else:
        document["url"] = urls[0]
    return document


def _report_deploy(document: Dict[str, Any]) -> None:
    url = document.get("url")
    success(f"Deployed version {document['version']}" + (f": {url}" if url else ""))
    if url:
        info(
            "First deploy? Visitors need the domain on Control Panel's network "
            "ingress allowlist (else an ingress 403), and sign-in needs "
            f"{url}/auth/callback registered as a redirect URL of the application."
        )


@app.command("deploy")
@pltr_command(
    sdk=(
        "third_party_applications.ThirdPartyApplication.Website.Version.get",
        "third_party_applications.ThirdPartyApplication.Website.Version.upload",
        "third_party_applications.ThirdPartyApplication.Website.deploy",
    ),
    destructive=True,
)
def deploy_site(
    dist_dir: Annotated[
        Path,
        typer.Argument(
            help=(
                "The site's build output folder (Vite: dist), with index.html at "
                "its root. pltr zips its contents."
            ),
            show_default=False,
        ),
    ],
    application: ApplicationOption,
    version: Annotated[
        Optional[str],
        typer.Option(
            "--version",
            help=(
                "Version to upload: MAJOR.MINOR.PATCH, such as 0.1.0. Each "
                "version can be uploaded once."
            ),
            show_default=False,
        ),
    ] = None,
    auto_version: Annotated[
        Optional[str],
        typer.Option(
            "--auto-version",
            click_type=click.Choice(AUTO_VERSIONS),
            help=(
                "Take the version from the nearest package.json at or above the "
                "folder's parent, or from `git describe --tags` there: tag v1.2.0 "
                "gives 1.2.0, and commits after it a pre-release such as "
                "1.2.0-2-g<sha>. Refused when tracked files have uncommitted "
                "changes."
            ),
            show_default=False,
        ),
    ] = None,
    upload_only: Annotated[
        bool,
        typer.Option(
            "--upload-only",
            help=(
                "Upload the version without deploying it: the live site doesn't "
                "change, and nothing asks for confirmation."
            ),
        ),
    ] = False,
    timeout: TimeoutOption = 300,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Zip a built site, upload it as a new website version and deploy it.

    Deploying replaces the live version, so it asks first (--yes skips the
    question); --upload-only doesn't. The version must not exist yet. Prints
    thirdPartyApplicationRid, version, deployed, and after a deploy the
    website's deployedVersion and subdomains, plus url (https:// and the
    first subdomain) when the API gives a full hostname. Website hosting must
    be turned on for the application, with an approved subdomain: see `pltr
    site --help`.
    """
    application = bundle.check_application_rid(application)
    folder = bundle.check_site_folder(dist_dir)
    version = _version(version, auto_version, folder)
    body, count = bundle.zip_site(folder)
    info(f"Zipped {count} files from {folder} ({len(body):,} bytes)")
    rollback = _rollback(version, application, profile)
    service = ThirdPartyApplicationsService(profile=profile)
    # A read: an existing version is reported before anyone is asked to approve.
    with spinner(f"Checking that version {version} is new..."):
        exists = service.website_version_exists(application, version)
    if exists:
        raise PltrError(
            f"Version {version} of the website already exists, and an uploaded "
            "version can't be replaced.",
            error_type="conflict",
            exit_code=ExitCode.API,
            hint=(
                "Upload a new version (bump it in package.json, tag a new commit, "
                "or pass another --version). To deploy the version already "
                f"uploaded, run `{_rollback(version, application, profile, yes=False)}`."
            ),
            suggested_command=_command(
                "pltr",
                "site",
                "versions",
                "--application",
                application,
                profile=profile,
            ),
            parameters={"thirdPartyApplicationRid": application, "version": version},
        )
    if not upload_only:
        confirm_destructive(
            f"Deploy version {version} of {folder} to application {application}? "
            "It replaces the live version.",
            yes=yes,
        )
    try:
        with spinner(f"Uploading version {version}..."):
            service.upload_website_version(application, body, version)
    except Exception as exc:
        if foundry_error_name(exc) == "VersionLimitExceeded":
            # Keeps the SDK error's type; adds what to do about it.
            raise RuntimeError(
                "The website has as many versions as it may: delete one that "
                "isn't deployed with 'pltr api third-party-applications "
                f"third-party-application website version delete {application} "
                "<old-version>' (pltr site versions lists them), then deploy again"
            ) from exc
        raise
    cache_rid(application)
    if upload_only:
        success(f"Uploaded version {version}; deploy it with: {rollback}")
        emit(
            {
                "thirdPartyApplicationRid": application,
                "version": version,
                "deployed": False,
            },
            format=format,
            output=output,
            columns=SITE_COLUMNS,
            title="Site",
        )
        return
    try:
        with spinner(f"Deploying version {version}..."):
            website = service.deploy_website(
                application, version, timeout=timeout, resume=rollback
            )
    except PltrError:
        raise
    except Exception as exc:
        # The version is uploaded, so running this command again would be a
        # conflict: say what to do instead (the SDK error keeps its type).
        raise RuntimeError(
            _deploy_failed(exc, version, application, rollback, profile)
        ) from exc
    document = _deployed(application, version, website)
    _report_deploy(document)
    emit(document, format=format, output=output, columns=SITE_COLUMNS, title="Site")


@app.command("versions")
@pltr_command(
    sdk="third_party_applications.ThirdPartyApplication.Website.Version.list",
    paged=True,
)
def list_site_versions(
    application: ApplicationOption,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the uploaded versions of an application's website (paged).

    The deployed one is the deployedVersion of `pltr api
    third-party-applications third-party-application website get`.
    """
    application = bundle.check_application_rid(application)
    service = ThirdPartyApplicationsService(profile=profile)
    with spinner("Listing website versions..."):
        page = collect_pages(
            lambda token: service.list_website_versions(
                application, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(application)
    emit(page, format=format, output=output, columns=VERSION_COLUMNS)


@app.command("rollback")
@pltr_command(
    sdk="third_party_applications.ThirdPartyApplication.Website.deploy",
    destructive=True,
)
def rollback_site(
    version: Annotated[
        str,
        typer.Argument(
            help="An uploaded version (`pltr site versions` lists them).",
            show_default=False,
        ),
    ],
    application: ApplicationOption,
    timeout: TimeoutOption = 300,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Deploy a version that was already uploaded (roll back, or go live with
    an --upload-only version).

    Replaces the live version, so it asks first; --yes skips the question.
    Prints the same document as `pltr site deploy`.
    """
    application = bundle.check_application_rid(application)
    version = bundle.check_version(version, param_hint="'VERSION'")
    confirm_destructive(
        f"Deploy version {version} to application {application}? It replaces "
        "the live version.",
        yes=yes,
    )
    with spinner(f"Deploying version {version}..."):
        website = ThirdPartyApplicationsService(profile=profile).deploy_website(
            application,
            version,
            timeout=timeout,
            resume=_rollback(version, application, profile),
        )
    cache_rid(application)
    document = _deployed(application, version, website)
    _report_deploy(document)
    emit(document, format=format, output=output, columns=SITE_COLUMNS, title="Site")
