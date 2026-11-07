"""
Admin commands (Foundry admin API): users, groups, roles, organizations and
markings.

Users and groups are identified by ID (a UUID), organizations by RID
(ri.multipass..organization.<id>), and markings and roles by ID.
"""

import re
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

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
    PageSizeOption,
    PageTokenOption,
    ProfileOption,
    YesOption,
    collect_pages,
    confirm_destructive,
    emit,
    pltr_command,
    spinner,
    success,
    warn,
)
from ..services.admin import MAX_BATCH_SIZE, AdminService
from ..utils.completion import cache_rid, complete_rid

if TYPE_CHECKING:
    from foundry_sdk.v2.admin.models import MarkingRole

app = typer.Typer(
    name="admin", help="Manage users, groups, roles, organizations and markings"
)
user_app = typer.Typer(
    name="user",
    short_help="Manage users (by user ID, a UUID).",
    help=(
        "Manage users. A user is identified by its ID, a UUID: find it with "
        "'pltr admin user search <name>' ('pltr admin user current' for yourself)."
    ),
)
group_app = typer.Typer(
    name="group",
    short_help="Manage groups (by group ID, a UUID).",
    help=(
        "Manage groups. A group is identified by its ID, a UUID: find it with "
        "'pltr admin group search <name>'."
    ),
)
role_app = typer.Typer(
    name="role",
    short_help="Look up roles by ID.",
    help=(
        "Look up roles by ID (beta endpoints). List the roles of an "
        "organization with 'pltr admin org available-roles <organization RID>'."
    ),
)
org_app = typer.Typer(
    name="org",
    short_help="Manage organizations (by organization RID).",
    help=(
        "Manage organizations. An organization is identified by its RID "
        "(ri.multipass..organization.<id>); 'pltr admin user get <user ID>' "
        "shows a user's organization."
    ),
)
marking_app = typer.Typer(
    name="marking",
    short_help="Manage markings (by marking ID).",
    help=(
        "Manage markings. A marking is identified by its ID: find it with "
        "'pltr admin marking list'."
    ),
)

app.add_typer(user_app, name="user")
app.add_typer(group_app, name="group")
app.add_typer(role_app, name="role")
app.add_typer(org_app, name="org")
app.add_typer(marking_app, name="marking")


# ------------------------------------------------------------------ columns

#: Table/CSV columns for a ``User`` model.
USER_COLUMNS: Columns = {
    "ID": "id",
    "Username": "username",
    "Given Name": "given_name",
    "Family Name": "family_name",
    "Email": "email",
    "Organization": "organization",
    "Realm": "realm",
    "Status": "status",
    "Attributes": "attributes",
}

#: Table/CSV columns for lists of users (one row per ``User``).
USER_LIST_COLUMNS: Columns = {
    "ID": "id",
    "Username": "username",
    "Given Name": "given_name",
    "Family Name": "family_name",
    "Email": "email",
    "Status": "status",
}

#: Table/CSV columns for ``user markings`` (one row per marking ID).
USER_MARKING_COLUMNS: Columns = {"Marking ID": lambda marking_id: marking_id}

#: Table/CSV columns for a ``Group`` model.
GROUP_COLUMNS: Columns = {
    "ID": "id",
    "Name": "name",
    "Description": "description",
    "Organizations": lambda group: ", ".join(group.organizations),
    "Realm": "realm",
    "Attributes": "attributes",
}

#: Table/CSV columns for lists of groups (one row per ``Group``).
GROUP_LIST_COLUMNS: Columns = {
    "ID": "id",
    "Name": "name",
    "Description": "description",
    "Organizations": lambda group: ", ".join(group.organizations),
}

#: Table/CSV columns for an admin ``Role`` model.
ROLE_COLUMNS: Columns = {
    "ID": "id",
    "Display Name": "display_name",
    "Description": "description",
    "Operations": lambda role: ", ".join(role.operations),
    "Inherited Roles": lambda role: ", ".join(role.can_assigns),
}

#: Table/CSV columns for ``role batch-get`` (one row per ``Role``).
ROLE_LIST_COLUMNS: Columns = {
    "ID": "id",
    "Display Name": "display_name",
    "Description": "description",
}

#: Table/CSV columns for an ``Organization`` model.
ORGANIZATION_COLUMNS: Columns = {
    "RID": "rid",
    "Name": "name",
    "Description": "description",
    "Host": "host",
    "Marking ID": "marking_id",
}

#: Table/CSV columns for ``org available-roles`` (one row per core ``Role``).
AVAILABLE_ROLE_COLUMNS: Columns = {
    "ID": "id",
    "Name": "name",
    "Role Set": "role_set_id",
    "Default": "is_default",
    "Description": "description",
}

#: Table/CSV columns for a ``Marking`` model.
MARKING_COLUMNS: Columns = {
    "ID": "id",
    "Name": "name",
    "Description": "description",
    "Category ID": "category_id",
    "Organization": "organization",
    "Priority": "priority",
    "Prominence": "prominence",
    "Deleted": "deleted",
    "Created": "created_time",
    "Created By": "created_by",
}

#: Table/CSV columns for lists of markings (one row per ``Marking``).
MARKING_LIST_COLUMNS: Columns = {
    "ID": "id",
    "Name": "name",
    "Category ID": "category_id",
    "Deleted": "deleted",
    "Created": "created_time",
}


# ---------------------------------------------------- argument validation

# User and group IDs (principal IDs) are UUIDs; the SDK rejects anything else.
_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_USER_HINT = "find one with 'pltr admin user search <name>'"
_GROUP_HINT = "find one with 'pltr admin group search <name>'"
_PRINCIPAL_HINT = (
    "find users with 'pltr admin user search <name>' and groups with "
    "'pltr admin group search <name>'"
)


def _callback_result(param: click.Parameter, value: Any) -> Any:
    """The value a Typer callback returns for ``param``.

    Typer hands callbacks of list parameters ``None`` when nothing was
    passed, then converts the callback's return value again, which fails on
    ``None``: return an empty list instead (Typer turns it back into None).
    """
    if value is None and (param.multiple or param.nargs == -1):
        return []
    return value


def _principal_id_callback(kind: str, hint: str) -> Callable[..., Any]:
    """Typer callback: every value must be a user/group ID (a UUID)."""

    def check(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
        for item in value if isinstance(value, (list, tuple)) else [value]:
            if item is not None and not _UUID.fullmatch(item):
                raise typer.BadParameter(
                    f"{item!r} is not a {kind} ID: {kind} IDs are UUIDs "
                    f"such as 9b6e1c2d-3f4a-4b5c-8d6e-7f8091a2b3c4 ({hint})."
                )
        return _callback_result(param, value)

    return check


def _check_batch_size(ids: List[str], param_hint: str) -> None:
    if len(ids) > MAX_BATCH_SIZE:
        raise typer.BadParameter(
            f"at most {MAX_BATCH_SIZE} IDs per request, got {len(ids)}",
            param_hint=param_hint,
        )


def _deprecated_alias_callback(flag: str, replacement: str) -> Callable[..., Any]:
    """Warn when a hidden, renamed option is used (it still works)."""

    def callback(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
        if value and not ctx.resilient_parsing:
            warn(
                f"{flag} is deprecated and will be removed in a future release; "
                f"use {replacement}."
            )
        return _callback_result(param, value)

    return callback


def _no_effect_callback(flag: str, reason: str) -> Callable[..., Any]:
    """Warn when a hidden option that no longer does anything is used."""

    def callback(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
        if value is not None and not ctx.resilient_parsing:
            warn(
                f"{flag} is deprecated and has no effect: {reason} "
                "It will be removed in a future release."
            )
        return value

    return callback


def _parse_attributes(values: List[str]) -> Dict[str, List[str]]:
    """``["team=ds", "team=ml", "site=ldn"]`` -> ``{"team": ["ds", "ml"], ...}``."""
    attributes: Dict[str, List[str]] = {}
    for value in values:
        name, sep, item = value.partition("=")
        if not sep or not name.strip():
            raise typer.BadParameter(
                f"expected NAME=VALUE, got {value!r}", param_hint="'--attribute'"
            )
        attributes.setdefault(name.strip(), []).append(item)
    return attributes


_MARKING_ROLES: Dict[str, "MarkingRole"] = {
    "ADMINISTER": "ADMINISTER",
    "DECLASSIFY": "DECLASSIFY",
    "USE": "USE",
}


def _parse_marking_roles(values: List[str]) -> List[Tuple["MarkingRole", str]]:
    """``["ADMINISTER:<id>", "use:<id>"]`` -> ``[("ADMINISTER", "<id>"), ...]``."""
    assignments: List[Tuple["MarkingRole", str]] = []
    for value in values:
        role_name, sep, principal_id = value.partition(":")
        role = _MARKING_ROLES.get(role_name.strip().upper())
        if not sep or role is None:
            raise typer.BadParameter(
                f"expected ROLE:PRINCIPAL_ID with ROLE one of ADMINISTER, "
                f"DECLASSIFY or USE, got {value!r}",
                param_hint="'--role'",
            )
        principal_id = principal_id.strip()
        if not _UUID.fullmatch(principal_id):
            raise typer.BadParameter(
                f"{principal_id!r} is not a user or group ID: they are UUIDs "
                f"({_PRINCIPAL_HINT})",
                param_hint="'--role'",
            )
        assignments.append((role, principal_id))
    if not any(role == "ADMINISTER" for role, _ in assignments):
        raise typer.BadParameter(
            "at least one ADMINISTER role is required, e.g. "
            "--role ADMINISTER:<your user ID> (see 'pltr admin user current')",
            param_hint="'--role'",
        )
    return assignments


# ------------------------------------------------------------- arguments

UserIdArg = Annotated[
    str,
    typer.Argument(
        help=f"User ID (a UUID; {_USER_HINT}).",
        callback=_principal_id_callback("user", _USER_HINT),
        show_default=False,
    ),
]
UserIdsArg = Annotated[
    List[str],
    typer.Argument(
        help=f"User IDs (UUIDs), separated by spaces (at most {MAX_BATCH_SIZE}).",
        callback=_principal_id_callback("user", _USER_HINT),
        show_default=False,
    ),
]
GroupIdArg = Annotated[
    str,
    typer.Argument(
        help=f"Group ID (a UUID; {_GROUP_HINT}).",
        callback=_principal_id_callback("group", _GROUP_HINT),
        show_default=False,
    ),
]
GroupIdsArg = Annotated[
    List[str],
    typer.Argument(
        help=f"Group IDs (UUIDs), separated by spaces (at most {MAX_BATCH_SIZE}).",
        callback=_principal_id_callback("group", _GROUP_HINT),
        show_default=False,
    ),
]
OrganizationRidArg = Annotated[
    str,
    typer.Argument(
        help=(
            "Organization RID (ri.multipass..organization.<id>); "
            "'pltr admin user get <user ID>' shows a user's organization."
        ),
        autocompletion=complete_rid,
        show_default=False,
    ),
]
MarkingIdArg = Annotated[
    str,
    typer.Argument(
        help="Marking ID (find it with 'pltr admin marking list').",
        show_default=False,
    ),
]
MarkingIdsArg = Annotated[
    List[str],
    typer.Argument(
        help=f"Marking IDs, separated by spaces (at most {MAX_BATCH_SIZE}).",
        show_default=False,
    ),
]
RoleIdArg = Annotated[
    str,
    typer.Argument(
        help="Role ID (as listed by 'pltr admin org available-roles').",
        show_default=False,
    ),
]
RoleIdsArg = Annotated[
    List[str],
    typer.Argument(
        help=f"Role IDs, separated by spaces (at most {MAX_BATCH_SIZE}).",
        show_default=False,
    ),
]
DescriptionOption = Annotated[
    Optional[str],
    typer.Option("--description", help="Description.", show_default=False),
]


# -------------------------------------------------------------------- users


@user_app.command("list")
@pltr_command(sdk="admin.User.list", paged=True)
def list_users(
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List users.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = AdminService(profile=profile)
    with spinner("Listing users..."):
        page = collect_pages(
            lambda token: service.list_users(page_size=page_size, page_token=token),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    emit(page, format=format, output=output, columns=USER_LIST_COLUMNS)


@user_app.command("get")
@pltr_command(sdk="admin.User.get")
def get_user(
    user_id: UserIdArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a user."""
    with spinner(f"Fetching user {user_id}..."):
        user = AdminService(profile=profile).get_user(user_id)
    emit(user, format=format, output=output, columns=USER_COLUMNS, title="User")


@user_app.command("current")
@pltr_command(sdk="admin.User.get_current")
def get_current_user(
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get the user you are authenticated as."""
    with spinner("Fetching the current user..."):
        user = AdminService(profile=profile).current_user()
    emit(user, format=format, output=output, columns=USER_COLUMNS, title="User")


@user_app.command("search")
@pltr_command(sdk="admin.User.search", paged=True)
def search_users(
    query: Annotated[
        str,
        typer.Argument(
            help="Start of a username, given name or family name (any case).",
            show_default=False,
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """Search active users by name.

    Matches the start of usernames, given names and family names, ignoring
    case; deleted users aren't included. Fetches one page by default; use
    --all for every page, or --page-token with the nextPageToken of an
    earlier response to continue.
    """
    service = AdminService(profile=profile)
    with spinner(f"Searching users for '{query}'..."):
        page = collect_pages(
            lambda token: service.search_users(
                query, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    emit(page, format=format, output=output, columns=USER_LIST_COLUMNS)


@user_app.command("markings")
@pltr_command(sdk="admin.User.get_markings")
def get_user_markings(
    user_id: UserIdArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """List the IDs of the markings a user can access.

    Includes the markings of organizations the user is a guest member of.
    JSON output is the API's response: {"view": ["<marking ID>", ...]}. Look a
    marking up with 'pltr admin marking get <marking ID>'.
    """
    with spinner(f"Fetching markings of user {user_id}..."):
        response = AdminService(profile=profile).get_user_markings(user_id)
    emit(
        response,
        format=format,
        output=output,
        columns=USER_MARKING_COLUMNS,
        rows=lambda markings: markings.view,
    )


@user_app.command("revoke-tokens")
@pltr_command(sdk="admin.User.revoke_all_tokens", destructive=True)
def revoke_user_tokens(
    user_id: UserIdArg,
    yes: YesOption = False,
    confirm: ConfirmAliasOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Invalidate all of a user's tokens and browser sessions.

    The user's API tokens stop working and they must sign in again; this can
    take a couple of minutes to take effect.
    """
    confirm_destructive(
        f"Revoke all tokens and browser sessions of user {user_id}?", yes=yes
    )
    with spinner(f"Revoking the tokens of user {user_id}..."):
        AdminService(profile=profile).revoke_user_tokens(user_id)
    success(f"Revoked all tokens of user {user_id}")
    emit(None, format=format)


@user_app.command("delete")
@pltr_command(sdk="admin.User.delete", destructive=True)
def delete_user(
    user_id: UserIdArg,
    yes: YesOption = False,
    confirm: ConfirmAliasOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Delete a user."""
    confirm_destructive(f"Delete user {user_id}?", yes=yes)
    with spinner(f"Deleting user {user_id}..."):
        AdminService(profile=profile).delete_user(user_id)
    success(f"Deleted user {user_id}")
    emit(None, format=format)


@user_app.command("batch-get")
@pltr_command(sdk="admin.User.get_batch")
def batch_get_users(
    user_ids: UserIdsArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get several users in one request.

    JSON output is the API's response: {"data": {"<user ID>": {...}}}.
    """
    _check_batch_size(user_ids, "USER_IDS")
    with spinner(f"Fetching {len(user_ids)} users..."):
        response = AdminService(profile=profile).get_batch_users(user_ids)
    emit(
        response,
        format=format,
        output=output,
        columns=USER_LIST_COLUMNS,
        rows=lambda batch: list(batch.data.values()),
    )


# ------------------------------------------------------------------- groups


@group_app.command("list")
@pltr_command(sdk="admin.Group.list", paged=True)
def list_groups(
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List groups.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = AdminService(profile=profile)
    with spinner("Listing groups..."):
        page = collect_pages(
            lambda token: service.list_groups(page_size=page_size, page_token=token),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    emit(page, format=format, output=output, columns=GROUP_LIST_COLUMNS)


@group_app.command("get")
@pltr_command(sdk="admin.Group.get")
def get_group(
    group_id: GroupIdArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a group."""
    with spinner(f"Fetching group {group_id}..."):
        group = AdminService(profile=profile).get_group(group_id)
    emit(group, format=format, output=output, columns=GROUP_COLUMNS, title="Group")


@group_app.command("search")
@pltr_command(sdk="admin.Group.search", paged=True)
def search_groups(
    query: Annotated[
        str,
        typer.Argument(help="Start of a group name (any case).", show_default=False),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """Search groups by name.

    Matches the start of group names, ignoring case. Fetches one page by
    default; use --all for every page, or --page-token with the
    nextPageToken of an earlier response to continue.
    """
    service = AdminService(profile=profile)
    with spinner(f"Searching groups for '{query}'..."):
        page = collect_pages(
            lambda token: service.search_groups(
                query, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    emit(page, format=format, output=output, columns=GROUP_LIST_COLUMNS)


@group_app.command("create")
@pltr_command(sdk="admin.Group.create")
def create_group(
    name: Annotated[
        str, typer.Argument(help="Name of the new group.", show_default=False)
    ],
    organizations: Annotated[
        Optional[List[str]],
        typer.Option(
            "--organization",
            help=(
                "RID of an organization whose members can see the group "
                "(required; repeat for several)."
            ),
            autocompletion=complete_rid,
            show_default=False,
        ),
    ] = None,
    attributes: Annotated[
        Optional[List[str]],
        typer.Option(
            "--attribute",
            metavar="NAME=VALUE",
            help=(
                "Group attribute (repeat for several attributes, or for several "
                "values of one). Names starting with 'multipass:' are reserved."
            ),
            show_default=False,
        ),
    ] = None,
    description: DescriptionOption = None,
    org_rid: Annotated[
        Optional[List[str]],
        typer.Option(
            "--org-rid",
            hidden=True,
            help="Deprecated alias for --organization.",
            callback=_deprecated_alias_callback("--org-rid", "--organization"),
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create a group.

    Members of the organizations you pass with --organization (at least one)
    can see the group. Add members with
    'pltr api admin group group-member add'. Example:

    \b
        pltr admin group create "Data Science" \\
            --organization ri.multipass..organization.<id> \\
            --description "ML team" --attribute team=ds
    """
    organization_rids = list(organizations or []) + list(org_rid or [])
    if not organization_rids:
        raise typer.BadParameter(
            "pass at least one --organization (an organization RID)",
            param_hint="'--organization'",
        )
    group_attributes = _parse_attributes(list(attributes or []))
    with spinner(f"Creating group '{name}'..."):
        group = AdminService(profile=profile).create_group(
            name=name,
            organizations=organization_rids,
            attributes=group_attributes,
            description=description,
        )
    success(f"Created group '{group.name}' ({group.id})")
    emit(group, format=format, output=output, columns=GROUP_COLUMNS, title="Group")


@group_app.command("delete")
@pltr_command(sdk="admin.Group.delete", destructive=True)
def delete_group(
    group_id: GroupIdArg,
    yes: YesOption = False,
    confirm: ConfirmAliasOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Delete a group."""
    confirm_destructive(f"Delete group {group_id}?", yes=yes)
    with spinner(f"Deleting group {group_id}..."):
        AdminService(profile=profile).delete_group(group_id)
    success(f"Deleted group {group_id}")
    emit(None, format=format)


@group_app.command("batch-get")
@pltr_command(sdk="admin.Group.get_batch")
def batch_get_groups(
    group_ids: GroupIdsArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get several groups in one request.

    JSON output is the API's response: {"data": {"<group ID>": {...}}}.
    """
    _check_batch_size(group_ids, "GROUP_IDS")
    with spinner(f"Fetching {len(group_ids)} groups..."):
        response = AdminService(profile=profile).get_batch_groups(group_ids)
    emit(
        response,
        format=format,
        output=output,
        columns=GROUP_LIST_COLUMNS,
        rows=lambda batch: list(batch.data.values()),
    )


# -------------------------------------------------------------------- roles


@role_app.command("get")
@pltr_command(sdk="admin.Role.get", beta=True)
def get_role(
    role_id: RoleIdArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a role: its permissions (operations) and the roles it inherits."""
    with spinner(f"Fetching role {role_id}..."):
        role = AdminService(profile=profile).get_role(role_id)
    emit(role, format=format, output=output, columns=ROLE_COLUMNS, title="Role")


@role_app.command("batch-get")
@pltr_command(sdk="admin.Role.get_batch", beta=True)
def batch_get_roles(
    role_ids: RoleIdsArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get several roles in one request.

    JSON output is the API's response: {"data": {"<role ID>": {...}}}.
    """
    _check_batch_size(role_ids, "ROLE_IDS")
    with spinner(f"Fetching {len(role_ids)} roles..."):
        response = AdminService(profile=profile).get_batch_roles(role_ids)
    emit(
        response,
        format=format,
        output=output,
        columns=ROLE_LIST_COLUMNS,
        rows=lambda batch: list(batch.data.values()),
    )


# ------------------------------------------------------------ organizations


@org_app.command("get")
@pltr_command(sdk="admin.Organization.get")
def get_organization(
    organization_rid: OrganizationRidArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get an organization."""
    with spinner(f"Fetching organization {organization_rid}..."):
        organization = AdminService(profile=profile).get_organization(organization_rid)
    cache_rid(organization_rid)
    emit(
        organization,
        format=format,
        output=output,
        columns=ORGANIZATION_COLUMNS,
        title="Organization",
    )


@org_app.command("create")
@pltr_command(sdk="admin.Organization.create", beta=True)
def create_organization(
    name: Annotated[
        str, typer.Argument(help="Name of the new organization.", show_default=False)
    ],
    enrollment_rid: Annotated[
        str,
        typer.Option(
            "--enrollment-rid",
            help="RID of the enrollment the organization belongs to.",
            autocompletion=complete_rid,
            show_default=False,
        ),
    ],
    admin_ids: Annotated[
        List[str],
        typer.Option(
            "--admin-id",
            help=(
                "ID (a UUID) of a user or group that administers the "
                "organization (required; repeat for several)."
            ),
            callback=_principal_id_callback("user or group", _PRINCIPAL_HINT),
            show_default=False,
        ),
    ],
    description: DescriptionOption = None,
    host: Annotated[
        Optional[str],
        typer.Option(
            "--host",
            help="Primary host name of the organization, used in its users' URLs.",
            show_default=False,
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create an organization.

    Pass at least one --admin-id, and include yourself or a group you belong
    to (see 'pltr admin user current') to keep administering it. Example:

    \b
        pltr admin org create "Research" \\
            --enrollment-rid ri.control-plane.main.enrollment.<id> \\
            --admin-id <your user ID>
    """
    with spinner(f"Creating organization '{name}'..."):
        organization = AdminService(profile=profile).create_organization(
            name=name,
            enrollment_rid=enrollment_rid,
            administrators=admin_ids,
            description=description,
            host=host,
        )
    cache_rid(organization.rid)
    success(f"Created organization '{organization.name}' ({organization.rid})")
    emit(
        organization,
        format=format,
        output=output,
        columns=ORGANIZATION_COLUMNS,
        title="Organization",
    )


@org_app.command("replace")
@pltr_command(
    sdk=("admin.Organization.get", "admin.Organization.replace"), destructive=True
)
def replace_organization(
    organization_rid: OrganizationRidArg,
    name: Annotated[
        str,
        typer.Argument(help="New name of the organization.", show_default=False),
    ],
    description: Annotated[
        Optional[str],
        typer.Option(
            "--description",
            help="New description (default: keep the current one).",
            show_default=False,
        ),
    ] = None,
    host: Annotated[
        Optional[str],
        typer.Option(
            "--host",
            help="New primary host name (default: keep the current one).",
            show_default=False,
        ),
    ] = None,
    yes: YesOption = False,
    confirm: ConfirmAliasOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Rename an organization, and change its description or host.

    The description and host keep their current values unless you pass
    --description or --host (pltr reads the organization first).
    """
    confirm_destructive(
        f"Replace organization {organization_rid} (new name: '{name}')?", yes=yes
    )
    with spinner(f"Replacing organization {organization_rid}..."):
        organization = AdminService(profile=profile).replace_organization(
            organization_rid, name=name, description=description, host=host
        )
    cache_rid(organization_rid)
    success(f"Replaced organization {organization_rid}")
    emit(
        organization,
        format=format,
        output=output,
        columns=ORGANIZATION_COLUMNS,
        title="Organization",
    )


@org_app.command("available-roles")
@pltr_command(sdk="admin.Organization.list_available_roles")
def list_available_roles(
    organization_rid: OrganizationRidArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: Annotated[
        Optional[int],
        typer.Option(
            "--page-size",
            hidden=True,
            help="Deprecated; has no effect.",
            callback=_no_effect_callback(
                "--page-size", "the API returns every role in one response."
            ),
        ),
    ] = None,
    page_token: Annotated[
        Optional[str],
        typer.Option(
            "--page-token",
            hidden=True,
            help="Deprecated; has no effect.",
            callback=_no_effect_callback(
                "--page-token", "the API returns every role in one response."
            ),
        ),
    ] = None,
):
    """List the roles that can be assigned in an organization.

    The API returns every role in one response. JSON output is that
    response: {"data": [...]}.
    """
    with spinner(f"Fetching the roles of organization {organization_rid}..."):
        response = AdminService(profile=profile).list_available_roles(organization_rid)
    cache_rid(organization_rid)
    emit(
        response,
        format=format,
        output=output,
        columns=AVAILABLE_ROLE_COLUMNS,
        rows=lambda roles: roles.data,
    )


# ----------------------------------------------------------------- markings


@marking_app.command("list")
@pltr_command(sdk="admin.Marking.list", paged=True)
def list_markings(
    include_deleted: Annotated[
        Optional[bool],
        typer.Option(
            "--include-deleted/--exclude-deleted",
            help="Include or leave out deleted markings (default: the API includes them).",
            show_default=False,
        ),
    ] = None,
    marking_type: Annotated[
        Optional[str],
        typer.Option(
            "--marking-type",
            click_type=click.Choice(["MANDATORY", "CBAC"], case_sensitive=False),
            help="Only list markings of this type (default: every type).",
            show_default=False,
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List markings.

    Fetches one page by default (the API returns at most 100 markings per
    page); use --all for every page, or --page-token with the nextPageToken
    of an earlier response to continue.
    """
    service = AdminService(profile=profile)
    with spinner("Listing markings..."):
        page = collect_pages(
            lambda token: service.list_markings(
                include_deleted=include_deleted,
                marking_type=marking_type,
                page_size=page_size,
                page_token=token,
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    emit(page, format=format, output=output, columns=MARKING_LIST_COLUMNS)


@marking_app.command("get")
@pltr_command(sdk="admin.Marking.get")
def get_marking(
    marking_id: MarkingIdArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a marking."""
    with spinner(f"Fetching marking {marking_id}..."):
        marking = AdminService(profile=profile).get_marking(marking_id)
    emit(
        marking, format=format, output=output, columns=MARKING_COLUMNS, title="Marking"
    )


@marking_app.command("batch-get")
@pltr_command(sdk="admin.Marking.get_batch")
def batch_get_markings(
    marking_ids: MarkingIdsArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get several markings in one request.

    JSON output is the API's response: {"data": {"<marking ID>": {...}}}.
    """
    _check_batch_size(marking_ids, "MARKING_IDS")
    with spinner(f"Fetching {len(marking_ids)} markings..."):
        response = AdminService(profile=profile).get_batch_markings(marking_ids)
    emit(
        response,
        format=format,
        output=output,
        columns=MARKING_LIST_COLUMNS,
        rows=lambda batch: list(batch.data.values()),
    )


@marking_app.command("create")
@pltr_command(sdk="admin.Marking.create")
def create_marking(
    name: Annotated[
        str,
        typer.Argument(
            help="Name of the new marking (unique within its category).",
            show_default=False,
        ),
    ],
    category_id: Annotated[
        str,
        typer.Option(
            "--category-id",
            help="ID of the marking category to create the marking in.",
            show_default=False,
        ),
    ],
    roles: Annotated[
        List[str],
        typer.Option(
            "--role",
            metavar="ROLE:PRINCIPAL_ID",
            help=(
                "Give a user or group (by ID, a UUID) a role on the marking: "
                "ADMINISTER, DECLASSIFY or USE. Repeat for several; at least "
                "one ADMINISTER is required."
            ),
            show_default=False,
        ),
    ],
    members: Annotated[
        Optional[List[str]],
        typer.Option(
            "--member",
            help=(
                "ID (a UUID) of a user or group that can view resources "
                "protected by the marking (repeat for several)."
            ),
            callback=_principal_id_callback("user or group", _PRINCIPAL_HINT),
            show_default=False,
        ),
    ] = None,
    description: DescriptionOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create a marking.

    Give at least one user or group the ADMINISTER role, and include yourself
    or a group you belong to (see 'pltr admin user current'): otherwise
    nobody you know can administer the marking. --member lists who can view
    resources protected by it. Change roles and members later with
    'pltr api admin marking marking-role-assignment' and
    'pltr api admin marking marking-member'. Example:

    \b
        pltr admin marking create "Project X" --category-id <category ID> \\
            --role ADMINISTER:<your user ID> --member <group ID>
    """
    role_assignments = _parse_marking_roles(roles)
    with spinner(f"Creating marking '{name}'..."):
        marking = AdminService(profile=profile).create_marking(
            name=name,
            category_id=category_id,
            initial_members=list(members or []),
            initial_role_assignments=role_assignments,
            description=description,
        )
    success(f"Created marking '{marking.name}' ({marking.id})")
    emit(
        marking, format=format, output=output, columns=MARKING_COLUMNS, title="Marking"
    )


@marking_app.command("replace")
@pltr_command(sdk=("admin.Marking.get", "admin.Marking.replace"), destructive=True)
def replace_marking(
    marking_id: MarkingIdArg,
    name: Annotated[
        str, typer.Argument(help="New name of the marking.", show_default=False)
    ],
    description: Annotated[
        Optional[str],
        typer.Option(
            "--description",
            help="New description (default: keep the current one).",
            show_default=False,
        ),
    ] = None,
    yes: YesOption = False,
    confirm: ConfirmAliasOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Rename a marking, and change its description.

    The description keeps its current value unless you pass --description
    (pltr reads the marking first).
    """
    confirm_destructive(f"Replace marking {marking_id} (new name: '{name}')?", yes=yes)
    with spinner(f"Replacing marking {marking_id}..."):
        marking = AdminService(profile=profile).replace_marking(
            marking_id, name=name, description=description
        )
    success(f"Replaced marking {marking_id}")
    emit(
        marking, format=format, output=output, columns=MARKING_COLUMNS, title="Marking"
    )
