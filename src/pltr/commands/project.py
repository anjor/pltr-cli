"""
Project commands (Foundry filesystem API).
"""

import uuid
from typing import Dict, List, Optional

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
    output_option,
    pltr_command,
    resource_argument,
    spinner,
    success,
)
from ..services.project import OWNER_ROLE_ID, PrincipalType, ProjectService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()

#: Table/CSV columns for a ``Project`` model.
PROJECT_COLUMNS: Columns = {
    "RID": "rid",
    "Display Name": "display_name",
    "Description": "description",
    "Path": "path",
    "Space": "space_rid",
    "Trash Status": "trash_status",
    "Resource-Level Role Grants": "resource_level_role_grants_allowed",
    "Created": "created_time",
    "Created By": "created_by",
    "Updated": "updated_time",
    "Updated By": "updated_by",
}

#: Table/CSV columns for ``project list`` (one row per project ``Resource``).
PROJECT_LIST_COLUMNS: Columns = {
    "Display Name": "display_name",
    "RID": "rid",
    "Space": "space_rid",
    "Trash Status": "trash_status",
    "Created": "created_time",
    "Created By": "created_by",
}

#: ``Project.organizations`` returns organization RIDs (strings).
ORGANIZATION_COLUMNS: Columns = {"Organization RID": lambda rid: rid}

ProjectRid = Annotated[
    str,
    resource_argument(
        "project",
        help="Project RID (ri.compass.main.folder.<id>; find it with 'pltr project list').",
        autocompletion=complete_rid,
    ),
]
OrganizationsOption = Annotated[
    List[str],
    typer.Option(
        "--org",
        "-o",
        help="Organization RID (repeat for several).",
    ),
]
DefaultRolesOption = Annotated[
    Optional[List[str]],
    typer.Option(
        "--default-role",
        help=(
            "Role ID for the project's default roles (repeat for several); it "
            "must be in the role set of the space."
        ),
        show_default=False,
    ),
]
DescriptionOption = Annotated[
    Optional[str],
    typer.Option("--description", "-d", help="Project description."),
]


def _user_or_group_id(value: str, param_hint: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise typer.BadParameter(
            f"{value!r} is not a user or group ID. IDs are UUIDs such as "
            "6f2a1b3c-0000-4000-8000-000000000001; usernames and group names "
            "are not accepted.",
            param_hint=param_hint,
        ) from None


def _parse_variables(values: Optional[List[str]]) -> Dict[str, str]:
    variables: Dict[str, str] = {}
    for value in values or []:
        name, sep, text = value.partition("=")
        if not sep or not name.strip():
            raise typer.BadParameter(
                f"expected name=value, got {value!r}", param_hint="'--var'"
            )
        variables[name.strip()] = text
    return variables


@app.command("create")
@pltr_command(sdk=("filesystem.Project.create", "admin.User.get_current"))
def create_project(
    name: Annotated[
        str,
        typer.Argument(
            help="Display name of the new project (unique in the space; no '/')."
        ),
    ],
    space_rid: Annotated[
        str,
        typer.Option(
            "--space-rid",
            "-s",
            help="RID of the space to create the project in (see 'pltr space list').",
            autocompletion=complete_rid,
        ),
    ],
    description: DescriptionOption = None,
    organization_rids: Annotated[
        Optional[List[str]],
        typer.Option(
            "--organization-rid",
            "-org",
            help=(
                "Organization RID to apply to the project (repeat for several); "
                "it must also be on the space."
            ),
            show_default=False,
        ),
    ] = None,
    owner_id: Annotated[
        Optional[str],
        typer.Option(
            "--owner-id",
            help="User or group ID (a UUID) that owns the project (default: you).",
            show_default=False,
        ),
    ] = None,
    owner_type: Annotated[
        Optional[str],
        typer.Option(
            "--owner-type",
            click_type=click.Choice(["USER", "GROUP"], case_sensitive=False),
            help="Whether --owner-id is a user or a group (default: USER).",
            show_default=False,
        ),
    ] = None,
    owner_role: Annotated[
        str,
        typer.Option(
            "--owner-role",
            help=(
                "Role ID granted to the owner. The API requires an owner-like "
                "role; change it for spaces with a custom role set."
            ),
        ),
    ] = OWNER_ROLE_ID,
    default_roles: DefaultRolesOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create a project in a space.

    The API requires an owner: by default you get the compass:manage role
    (Owner in Foundry's default role set). --owner-id and --owner-type make a
    user or group the owner instead.
    """
    if owner_type is not None and owner_id is None:
        raise typer.BadParameter(
            "--owner-type needs --owner-id", param_hint="'--owner-type'"
        )
    owner = _user_or_group_id(owner_id, "'--owner-id'") if owner_id else None
    principal_type: PrincipalType = (
        "GROUP" if (owner_type or "").upper() == "GROUP" else "USER"
    )
    with spinner(f"Creating project '{name}'..."):
        project = ProjectService(profile=profile).create_project(
            display_name=name,
            space_rid=space_rid,
            owner_id=owner,
            owner_type=principal_type,
            owner_role=owner_role,
            description=description,
            organization_rids=organization_rids,
            default_roles=default_roles,
        )
    cache_rid(project.rid)
    success(f"Created project '{project.display_name}' ({project.rid})")
    emit(
        project, format=format, output=output, columns=PROJECT_COLUMNS, title="Project"
    )


@app.command("get")
@pltr_command(sdk="filesystem.Project.get")
def get_project(
    project_rid: ProjectRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a project's metadata."""
    with spinner(f"Fetching project {project_rid}..."):
        project = ProjectService(profile=profile).get_project(project_rid)
    cache_rid(project_rid)
    emit(
        project, format=format, output=output, columns=PROJECT_COLUMNS, title="Project"
    )


@app.command("list")
@pltr_command(sdk=("filesystem.Space.list", "filesystem.Folder.children"), paged=True)
def list_projects(
    space_rid: Annotated[
        Optional[str],
        typer.Option(
            "--space-rid",
            "-s",
            help="RID of the space to list (default: every space you can see).",
            autocompletion=complete_rid,
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
    """List the projects in a space, or in every space you can see.

    With --space-rid, fetches one page of the space's projects by default;
    use --all for every page, or --page-token with the nextPageToken of an
    earlier response to continue. Without it, pltr reads every page of
    every space (at least one request per space), so --page-token and
    --max-pages don't apply. Items are the projects' Resource metadata.
    """
    service = ProjectService(profile=profile)
    if space_rid:
        with spinner(f"Listing projects in space {space_rid}..."):
            page = collect_pages(
                lambda token: service.list_projects(
                    space_rid, page_size=page_size, page_token=token
                ),
                page_token=page_token,
                max_pages=max_pages,
                all_pages=all_pages,
            )
        cache_rid(space_rid)
        emit(page, format=format, output=output, columns=PROJECT_LIST_COLUMNS)
        return
    if page_token is not None or max_pages != 1:
        raise typer.BadParameter(
            "--page-token and --max-pages need --space-rid: without it, pltr "
            "lists every project of every space",
            param_hint="'--space-rid'",
        )
    with spinner("Listing the projects of every space..."):
        projects = service.list_all_projects(page_size=page_size)
    emit(projects, format=format, output=output, columns=PROJECT_LIST_COLUMNS)


@app.command("update")
@pltr_command(sdk=("filesystem.Project.get", "filesystem.Project.replace"), beta=True)
def update_project(
    project_rid: ProjectRid,
    name: Annotated[
        Optional[str], typer.Option("--name", "-n", help="New display name.")
    ] = None,
    description: Annotated[
        Optional[str], typer.Option("--description", "-d", help="New description.")
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Change a project's display name or description.

    The field you don't pass keeps its current value.
    """
    if name is None and description is None:
        raise typer.BadParameter("pass --name, --description or both")
    with spinner(f"Updating project {project_rid}..."):
        project = ProjectService(profile=profile).update_project(
            project_rid, display_name=name, description=description
        )
    success(f"Updated project {project_rid}")
    emit(
        project, format=format, output=output, columns=PROJECT_COLUMNS, title="Project"
    )


@app.command("delete")
@pltr_command(
    sdk=("filesystem.Project.get", "filesystem.Resource.delete"), destructive=True
)
def delete_project(
    project_rid: ProjectRid,
    yes: YesOption = False,
    confirm: ConfirmAliasOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Move a project, and everything in it, to the trash.

    The SDK has no project-specific delete: pltr checks that the RID is a
    project and moves it to the trash like any other resource. Restore it
    with 'pltr resource restore', or delete it for good with 'pltr resource
    permanently-delete'. Asks for confirmation; --yes skips it. Prints
    nothing on stdout (JSON: null).
    """
    confirm_destructive(
        f"Move project {project_rid}, and everything in it, to the trash?", yes=yes
    )
    with spinner(f"Moving project {project_rid} to the trash..."):
        project = ProjectService(profile=profile).delete_project(project_rid)
    success(
        f"Moved project '{project.display_name}' ({project_rid}) to the trash; "
        f"restore it with 'pltr resource restore {project_rid}'"
    )
    emit(None, format=format)


# ==================== Organization Operations ====================


@app.command("add-orgs")
@pltr_command(sdk="filesystem.Project.add_organizations")
def add_organizations(
    project_rid: ProjectRid,
    organization_rids: OrganizationsOption,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Apply organizations to a project; they must also be on its space.

    Prints nothing on stdout (JSON: null).
    """
    with spinner(f"Adding organizations to project {project_rid}..."):
        ProjectService(profile=profile).add_organizations(
            project_rid, organization_rids
        )
    success(f"Added {len(organization_rids)} organization(s) to project {project_rid}")
    emit(None, format=format)


@app.command("remove-orgs")
@pltr_command(sdk="filesystem.Project.remove_organizations", destructive=True)
def remove_organizations(
    project_rid: ProjectRid,
    organization_rids: OrganizationsOption,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Remove organizations from a project.

    Asks for confirmation; --yes skips it. Prints nothing on stdout (JSON:
    null).
    """
    confirm_destructive(
        f"Remove organization(s) {', '.join(organization_rids)} from project "
        f"{project_rid}?",
        yes=yes,
    )
    with spinner(f"Removing organizations from project {project_rid}..."):
        ProjectService(profile=profile).remove_organizations(
            project_rid, organization_rids
        )
    success(
        f"Removed {len(organization_rids)} organization(s) from project {project_rid}"
    )
    emit(None, format=format)


@app.command("list-orgs")
@pltr_command(sdk="filesystem.Project.organizations", paged=True)
def list_organizations(
    project_rid: ProjectRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the RIDs of the organizations applied directly to a project.

    Fetches one page by default; use --all for every page.
    """
    service = ProjectService(profile=profile)
    with spinner(f"Listing organizations of project {project_rid}..."):
        page = collect_pages(
            lambda token: service.list_organizations(
                project_rid, page_size=page_size, page_token=token
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    cache_rid(project_rid)
    emit(page, format=format, output=output, columns=ORGANIZATION_COLUMNS)


# ==================== Template Operations ====================


@app.command("create-from-template")
@pltr_command(sdk="filesystem.Project.create_from_template")
def create_from_template(
    template_rid: Annotated[
        str,
        typer.Option(
            "--template-rid",
            "-t",
            help="RID of the project template.",
            autocompletion=complete_rid,
        ),
    ],
    variables: Annotated[
        Optional[List[str]],
        typer.Option(
            "--var",
            "-v",
            help="Template variable as name=value (repeat for several).",
            show_default=False,
        ),
    ] = None,
    description: DescriptionOption = None,
    organization_rids: Annotated[
        Optional[List[str]],
        typer.Option(
            "--org",
            "-o",
            help="Organization RID to apply to the project (repeat for several).",
            show_default=False,
        ),
    ] = None,
    default_roles: DefaultRolesOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    # -o is --org here, so --output has no short flag.
    output: Annotated[Optional[str], output_option(short=False)] = None,
):
    """Create a project from a project template."""
    variable_values = _parse_variables(variables)
    with spinner(f"Creating project from template {template_rid}..."):
        project = ProjectService(profile=profile).create_project_from_template(
            template_rid=template_rid,
            variable_values=variable_values,
            default_roles=default_roles,
            organization_rids=organization_rids,
            project_description=description,
        )
    cache_rid(project.rid)
    success(f"Created project '{project.display_name}' ({project.rid})")
    emit(
        project, format=format, output=output, columns=PROJECT_COLUMNS, title="Project"
    )


@app.callback()
def main():
    """
    Project operations using foundry-platform-sdk.

    Projects live in spaces and are addressed by RID
    (ri.compass.main.folder.<id>, like folders). Find a space with
    'pltr space list' and its projects with 'pltr project list --space-rid'.
    Updating a project uses a beta Foundry endpoint (labeled [beta]).

    Examples:

    \b
        # Create a project in a space (you become its owner)
        pltr project create "My Project" --space-rid ri.compass.main.folder.space123
    \b
        # List the projects in a space, or in every space
        pltr project list --space-rid ri.compass.main.folder.space123
        pltr project list --format json
    \b
        # Get, rename, and move a project to the trash
        pltr project get ri.compass.main.folder.proj456
        pltr project update ri.compass.main.folder.proj456 --name "New Name"
        pltr project delete ri.compass.main.folder.proj456
    \b
        # Organizations
        pltr project add-orgs ri.compass.main.folder.proj456 -o <ORGANIZATION_RID>
        pltr project list-orgs ri.compass.main.folder.proj456
    \b
        # Create a project from a template
        pltr project create-from-template -t <TEMPLATE_RID> -v "name=My Project"
    """
