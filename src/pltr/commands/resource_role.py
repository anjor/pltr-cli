"""
Resource role commands (Foundry filesystem API): who has which role on a resource.
"""

import uuid
from typing import Any, Optional

import click
import typer
from typing_extensions import Annotated

from ..contract import (
    AllPagesOption,
    Columns,
    ConfirmAliasOption,
    FormatOption,
    MaxPagesOption,
    OutputOption,
    Page,
    PageSizeOption,
    PageTokenOption,
    ProfileOption,
    YesOption,
    collect_pages,
    confirm_destructive,
    emit,
    pltr_command,
    profile_option,
    spinner,
    success,
    warn,
)
from ..services.resource_role import ResourceRoleService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()


def principal_type(role: Any) -> str:
    """USER, GROUP or EVERYONE for a ``ResourceRole`` (table/CSV only)."""
    from foundry_sdk.v2.filesystem.models import Everyone, PrincipalWithId

    principal = role.resource_role_principal
    if isinstance(principal, PrincipalWithId):
        return principal.principal_type
    if isinstance(principal, Everyone):
        return "EVERYONE"
    return principal.type  # a principal kind this pltr version doesn't know


def principal_id(role: Any) -> Optional[str]:
    """The user or group ID of a ``ResourceRole`` (none for everyone)."""
    from foundry_sdk.v2.filesystem.models import PrincipalWithId

    principal = role.resource_role_principal
    if isinstance(principal, PrincipalWithId):
        return principal.principal_id
    return None


#: Table/CSV columns for a ``ResourceRole``.
ROLE_COLUMNS: Columns = {
    "Principal Type": principal_type,
    "Principal ID": principal_id,
    "Role ID": "role_id",
}

ResourceRid = Annotated[
    str,
    typer.Argument(
        help=(
            "RID of the resource: a project, folder, dataset or any other "
            "filesystem resource (ri.<service>.<instance>.<type>.<id>)."
        ),
        autocompletion=complete_rid,
    ),
]
RoleOption = Annotated[
    str,
    typer.Option(
        "--role",
        "-r",
        help=(
            "Role ID, from the role set of the resource's space (for example "
            "compass:manage for Owner in the default role set). 'pltr "
            "resource-role list' shows the role IDs in use on a resource."
        ),
    ),
]
PrincipalIdOption = Annotated[
    Optional[str],
    typer.Option(
        "--principal-id",
        "-p",
        help=(
            "ID of the user or group (a UUID; usernames and group names are "
            "not accepted). Find IDs with the 'pltr admin' user and group "
            "commands."
        ),
        show_default=False,
    ),
]
EveryoneOption = Annotated[
    bool,
    typer.Option("--everyone", help="Use the Everyone principal instead of an ID."),
]
#: Hidden: add/remove take only the principal's ID, so the type is ignored.
PrincipalTypeAliasOption = Annotated[
    Optional[str],
    typer.Option(
        "--principal-type",
        "-t",
        hidden=True,
        help="Deprecated and ignored: the principal ID is enough.",
    ),
]
# -p is --principal-id on grant/revoke, so --profile has no short flag there.
ProfileNoShortOption = Annotated[Optional[str], profile_option(short=False)]


def _principal(principal_id: Optional[str], everyone: bool) -> Optional[str]:
    """Validate the principal options; returns the ID, or None for everyone."""
    if everyone:
        if principal_id is not None:
            raise typer.BadParameter(
                "pass either --principal-id or --everyone, not both",
                param_hint="'--principal-id'",
            )
        return None
    if not principal_id:
        raise typer.BadParameter(
            "pass the user or group ID with --principal-id (or use --everyone)",
            param_hint="'--principal-id'",
        )
    try:
        return str(uuid.UUID(principal_id))
    except ValueError:
        raise typer.BadParameter(
            f"{principal_id!r} is not a user or group ID. IDs are UUIDs such as "
            "6f2a1b3c-0000-4000-8000-000000000001; usernames and group names "
            "are not accepted.",
            param_hint="'--principal-id'",
        ) from None


def _describe(principal: Optional[str]) -> str:
    return "everyone" if principal is None else f"principal {principal}"


def _warn_principal_type(value: Optional[str]) -> None:
    if value is not None:
        warn(
            "--principal-type is deprecated and ignored: granting or revoking a "
            "role only needs the principal ID. It will be removed in a future "
            "release."
        )


@app.command("grant")
@pltr_command(sdk="filesystem.Resource.Role.add")
def grant_role(
    resource_rid: ResourceRid,
    role_id: RoleOption,
    principal_id: PrincipalIdOption = None,
    everyone: EveryoneOption = False,
    principal_type_alias: PrincipalTypeAliasOption = None,
    profile: ProfileNoShortOption = None,
    format: FormatOption = "table",
):
    """Grant a role on a resource to a user, a group or everyone.

    Prints nothing on stdout (JSON: null); the API returns no body.
    """
    principal = _principal(principal_id, everyone)
    _warn_principal_type(principal_type_alias)
    with spinner(f"Granting role '{role_id}' on {resource_rid}..."):
        ResourceRoleService(profile=profile).grant_role(
            resource_rid, role_id, principal_id=principal
        )
    cache_rid(resource_rid)
    success(f"Granted role '{role_id}' to {_describe(principal)} on {resource_rid}")
    emit(None, format=format)


@app.command("revoke")
@pltr_command(sdk="filesystem.Resource.Role.remove", destructive=True)
def revoke_role(
    resource_rid: ResourceRid,
    role_id: RoleOption,
    principal_id: PrincipalIdOption = None,
    everyone: EveryoneOption = False,
    principal_type_alias: PrincipalTypeAliasOption = None,
    yes: YesOption = False,
    confirm: ConfirmAliasOption = False,
    profile: ProfileNoShortOption = None,
    format: FormatOption = "table",
):
    """Revoke a role on a resource from a user, a group or everyone.

    Asks for confirmation; --yes skips it. Prints nothing on stdout (JSON:
    null).
    """
    principal = _principal(principal_id, everyone)
    _warn_principal_type(principal_type_alias)
    confirm_destructive(
        f"Revoke role '{role_id}' from {_describe(principal)} on {resource_rid}?",
        yes=yes,
    )
    with spinner(f"Revoking role '{role_id}' on {resource_rid}..."):
        ResourceRoleService(profile=profile).revoke_role(
            resource_rid, role_id, principal_id=principal
        )
    success(f"Revoked role '{role_id}' from {_describe(principal)} on {resource_rid}")
    emit(None, format=format)


@app.command("list")
@pltr_command(sdk="filesystem.Resource.Role.list", paged=True)
def list_roles(
    resource_rid: ResourceRid,
    principal_type_filter: Annotated[
        Optional[str],
        typer.Option(
            "--principal-type",
            "-t",
            click_type=click.Choice(
                ["USER", "GROUP", "EVERYONE"], case_sensitive=False
            ),
            help=(
                "Only show grants to users, groups or everyone. Filtered "
                "locally on the fetched pages (the API has no such filter)."
            ),
            show_default=False,
        ),
    ] = None,
    include_inherited: Annotated[
        bool,
        typer.Option(
            "--include-inherited",
            help="Also list the roles the resource inherits from its parents.",
        ),
    ] = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the role grants on a resource.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = ResourceRoleService(profile=profile)
    with spinner(f"Listing roles on {resource_rid}..."):
        page = collect_pages(
            lambda token: service.list_roles(
                resource_rid,
                include_inherited=True if include_inherited else None,
                page_size=page_size,
                page_token=token,
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(resource_rid)
    if principal_type_filter:
        wanted = principal_type_filter.upper()
        page = Page(
            data=[role for role in page.data if principal_type(role) == wanted],
            next_page_token=page.next_page_token,
        )
    emit(page, format=format, output=output, columns=ROLE_COLUMNS)


@app.callback()
def main():
    """
    Resource role operations using foundry-platform-sdk.

    Grant, revoke and list the roles users and groups have on a filesystem
    resource (a project, folder, dataset, ...). Resources are addressed by
    RID; principals by their user or group ID (a UUID), never by name. Role
    IDs come from the role set of the resource's space.

    Examples:

    \b
        # List the role grants on a dataset
        pltr resource-role list ri.foundry.main.dataset.xyz123
    \b
        # Include inherited roles, as JSON
        pltr resource-role list ri.foundry.main.dataset.xyz123 \\
            --include-inherited --format json
    \b
        # Grant a role to a user or group (by ID)
        pltr resource-role grant ri.compass.main.folder.abc456 \\
            --principal-id 6f2a1b3c-0000-4000-8000-000000000001 --role compass:manage
    \b
        # Revoke it (asks for confirmation; --yes skips it)
        pltr resource-role revoke ri.compass.main.folder.abc456 \\
            --principal-id 6f2a1b3c-0000-4000-8000-000000000001 --role compass:manage
    """
