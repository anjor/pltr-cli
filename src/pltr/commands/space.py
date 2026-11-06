"""
Space commands (Foundry filesystem API).
"""

from typing import List, Optional

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
)
from ..services.space import SpaceService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()

#: Table/CSV columns for a ``Space`` model.
SPACE_COLUMNS: Columns = {
    "RID": "rid",
    "Display Name": "display_name",
    "Description": "description",
    "Path": "path",
    "Organizations": lambda space: ", ".join(space.organizations),
    "Deletion Policy Organizations": lambda space: ", ".join(
        space.deletion_policy_organizations
    ),
    "Default Role Set": "default_role_set_id",
    "Usage Account": "usage_account_rid",
    "File System": "file_system_id",
}

#: Table/CSV columns for ``space list`` (one row per ``Space``).
SPACE_LIST_COLUMNS: Columns = {
    "Display Name": "display_name",
    "RID": "rid",
    "Path": "path",
    "Organizations": lambda space: ", ".join(space.organizations),
}

SpaceRid = Annotated[
    str,
    typer.Argument(
        help="Space RID (find it with 'pltr space list').",
        autocompletion=complete_rid,
    ),
]
DefaultRoleSetOption = Annotated[
    Optional[str],
    typer.Option(
        "--default-role-set-id",
        help="Default role set for projects in the space (default: Foundry's).",
    ),
]
UsageAccountOption = Annotated[
    Optional[str],
    typer.Option(
        "--usage-account-rid",
        help="Usage account RID that the space's resource usage accrues to.",
    ),
]


@app.command("create")
@pltr_command(sdk="filesystem.Space.create", beta=True)
def create_space(
    name: Annotated[str, typer.Argument(help="Display name of the new space.")],
    enrollment_rid: Annotated[
        str,
        typer.Option(
            "--enrollment-rid",
            "-e",
            help="RID of the enrollment the space belongs to.",
            autocompletion=complete_rid,
        ),
    ],
    organizations: Annotated[
        List[str],
        typer.Option(
            "--organization",
            "-org",
            help=(
                "Organization RID whose members get access to the space "
                "(repeat for several)."
            ),
        ),
    ],
    deletion_policy_organizations: Annotated[
        List[str],
        typer.Option(
            "--deletion-policy-org",
            "-dpo",
            help=(
                "Organization RID for the deletion policy: the space is deleted "
                "when the last of these organizations is (repeat for several)."
            ),
        ),
    ],
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="Description of the space."),
    ] = None,
    default_role_set_id: DefaultRoleSetOption = None,
    file_system_id: Annotated[
        Optional[str],
        typer.Option(
            "--file-system-id",
            help="Filesystem that stores the space's contents (default: Foundry's).",
        ),
    ] = None,
    usage_account_rid: UsageAccountOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create a space."""
    with spinner(f"Creating space '{name}'..."):
        space = SpaceService(profile=profile).create_space(
            display_name=name,
            enrollment_rid=enrollment_rid,
            organizations=organizations,
            deletion_policy_organizations=deletion_policy_organizations,
            description=description,
            default_role_set_id=default_role_set_id,
            file_system_id=file_system_id,
            usage_account_rid=usage_account_rid,
        )
    cache_rid(space.rid)
    success(f"Created space '{space.display_name}' ({space.rid})")
    emit(space, format=format, output=output, columns=SPACE_COLUMNS, title="Space")


@app.command("get")
@pltr_command(sdk="filesystem.Space.get", beta=True)
def get_space(
    space_rid: SpaceRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a space's metadata."""
    with spinner(f"Fetching space {space_rid}..."):
        space = SpaceService(profile=profile).get_space(space_rid)
    cache_rid(space_rid)
    emit(space, format=format, output=output, columns=SPACE_COLUMNS, title="Space")


@app.command("list")
@pltr_command(sdk="filesystem.Space.list", paged=True)
def list_spaces(
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
    organization_rid: Annotated[
        Optional[str],
        typer.Option(
            "--organization-rid",
            "-org",
            hidden=True,
            help="Removed: the API can't filter spaces by organization.",
        ),
    ] = None,
):
    """List the spaces you can see.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    if organization_rid is not None:
        raise typer.BadParameter(
            "the Foundry API can't filter spaces by organization, so this option "
            "was removed. List spaces and filter on their 'organizations' field "
            "instead, e.g. pltr space list --all --format json | jq "
            "'.data[] | select(.organizations | index(\"<org RID>\"))'",
            param_hint="'--organization-rid'",
        )
    service = SpaceService(profile=profile)
    with spinner("Listing spaces..."):
        page = collect_pages(
            lambda token: service.list_spaces(page_size=page_size, page_token=token),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    emit(page, format=format, output=output, columns=SPACE_LIST_COLUMNS)


@app.command("update")
@pltr_command(sdk=("filesystem.Space.get", "filesystem.Space.replace"), beta=True)
def update_space(
    space_rid: SpaceRid,
    name: Annotated[
        Optional[str], typer.Option("--name", "-n", help="New display name.")
    ] = None,
    description: Annotated[
        Optional[str], typer.Option("--description", "-d", help="New description.")
    ] = None,
    default_role_set_id: DefaultRoleSetOption = None,
    usage_account_rid: UsageAccountOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Change a space's name, description, default role set or usage account.

    Fields you don't pass keep their current values.
    """
    if all(
        value is None
        for value in (name, description, default_role_set_id, usage_account_rid)
    ):
        raise typer.BadParameter(
            "pass at least one of --name, --description, --default-role-set-id "
            "or --usage-account-rid"
        )
    with spinner(f"Updating space {space_rid}..."):
        space = SpaceService(profile=profile).update_space(
            space_rid,
            display_name=name,
            description=description,
            default_role_set_id=default_role_set_id,
            usage_account_rid=usage_account_rid,
        )
    success(f"Updated space {space_rid}")
    emit(space, format=format, output=output, columns=SPACE_COLUMNS, title="Space")


@app.command("delete")
@pltr_command(sdk="filesystem.Space.delete", beta=True, destructive=True)
def delete_space(
    space_rid: SpaceRid,
    yes: YesOption = False,
    confirm: ConfirmAliasOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Delete an empty space (delete its projects and resources first)."""
    confirm_destructive(f"Delete space {space_rid}?", yes=yes)
    with spinner(f"Deleting space {space_rid}..."):
        SpaceService(profile=profile).delete_space(space_rid)
    success(f"Deleted space {space_rid}")
    emit(None, format=format)


@app.callback()
def main():
    """
    Space operations using foundry-platform-sdk.

    Spaces are addressed by RID. Creating, reading, updating and deleting a
    space uses beta Foundry endpoints (labeled [beta]); listing is GA.

    Examples:
        # Create a space
        pltr space create "My Space" \\
            --enrollment-rid <ENROLLMENT_RID> \\
            --organization <ORGANIZATION_RID> \\
            --deletion-policy-org <ORGANIZATION_RID>

        # List spaces (one page; --all for every page)
        pltr space list

        # Get space information as JSON
        pltr space get <SPACE_RID> --format json

        # Update the description
        pltr space update <SPACE_RID> --description "New text"

        # Delete an empty space (asks for confirmation; --yes skips it)
        pltr space delete <SPACE_RID>
    """
