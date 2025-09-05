"""
Resource Role management commands for Foundry filesystem.
"""

import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table

from ..services.resource_role import ResourceRoleService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..auth.base import ProfileNotFoundError, MissingCredentialsError
from ..utils.completion import (
    complete_rid,
    complete_profile,
    complete_output_format,
    cache_rid,
)

app = typer.Typer()
console = Console()
formatter = OutputFormatter(console)


@app.command("grant")
def grant_role(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
    ),
    principal_id: str = typer.Option(
        ..., "--principal-id", "-p", help="Principal (user/group) identifier"
    ),
    principal_type: str = typer.Option(
        ...,
        "--principal-type",
        "-t",
        help="Principal type (User or Group)",
    ),
    role_name: str = typer.Option(..., "--role", "-r", help="Role name to grant"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
):
    """Grant a role to a principal on a resource."""
    try:
        service = ResourceRoleService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Granting role '{role_name}' to {principal_type} '{principal_id}' on {resource_rid}..."
        ):
            role_grant = service.grant_role(
                resource_rid=resource_rid,
                principal_id=principal_id,
                principal_type=principal_type.title(),
                role_name=role_name,
            )

        formatter.print_success(
            f"Successfully granted role '{role_name}' to {principal_type} '{principal_id}'"
        )

        # Format output
        if format == "json":
            formatter.format_dict(role_grant)
        elif format == "csv":
            formatter.format_list([role_grant])
        else:
            _format_role_grant_table(role_grant)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to grant role: {e}")
        raise typer.Exit(1)


@app.command("revoke")
def revoke_role(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
    ),
    principal_id: str = typer.Option(
        ..., "--principal-id", "-p", help="Principal (user/group) identifier"
    ),
    principal_type: str = typer.Option(
        ...,
        "--principal-type",
        "-t",
        help="Principal type (User or Group)",
    ),
    role_name: str = typer.Option(..., "--role", "-r", help="Role name to revoke"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
):
    """Revoke a role from a principal on a resource."""
    try:
        if not confirm:
            confirm_revoke = typer.confirm(
                f"Are you sure you want to revoke role '{role_name}' from {principal_type} '{principal_id}' on resource {resource_rid}?"
            )
            if not confirm_revoke:
                formatter.print_info("Role revocation cancelled.")
                return

        service = ResourceRoleService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Revoking role '{role_name}' from {principal_type} '{principal_id}' on {resource_rid}..."
        ):
            service.revoke_role(
                resource_rid=resource_rid,
                principal_id=principal_id,
                principal_type=principal_type.title(),
                role_name=role_name,
            )

        formatter.print_success(
            f"Successfully revoked role '{role_name}' from {principal_type} '{principal_id}'"
        )

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to revoke role: {e}")
        raise typer.Exit(1)


@app.command("list")
def list_resource_roles(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
    ),
    principal_type: Optional[str] = typer.Option(
        None,
        "--principal-type",
        "-t",
        help="Filter by principal type (User or Group)",
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of items per page"
    ),
):
    """List all roles granted on a resource."""
    try:
        # Cache the RID for future completions
        cache_rid(resource_rid)

        service = ResourceRoleService(profile=profile)

        filter_desc = f" for {principal_type}s" if principal_type else ""
        with SpinnerProgressTracker().track_spinner(
            f"Listing roles on {resource_rid}{filter_desc}..."
        ):
            role_grants = service.list_resource_roles(
                resource_rid=resource_rid,
                principal_type=principal_type.title() if principal_type else None,
                page_size=page_size,
            )

        if not role_grants:
            formatter.print_info(f"No roles found on resource {resource_rid}.")
            return

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(role_grants, output, "json")
            else:
                formatter.format_list(role_grants)
        elif format == "csv":
            if output:
                formatter.save_to_file(role_grants, output, "csv")
            else:
                formatter.format_list(role_grants)
        else:
            _format_role_grants_table(role_grants)

        if output:
            formatter.print_success(f"Role grants saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to list resource roles: {e}")
        raise typer.Exit(1)


@app.command("get-principal-roles")
def get_principal_roles(
    principal_id: str = typer.Option(
        ..., "--principal-id", "-p", help="Principal (user/group) identifier"
    ),
    principal_type: str = typer.Option(
        ...,
        "--principal-type",
        "-t",
        help="Principal type (User or Group)",
    ),
    resource_rid: Optional[str] = typer.Option(
        None,
        "--resource-rid",
        "-r",
        help="Filter by resource RID",
        autocompletion=complete_rid,
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    page_size: Optional[int] = typer.Option(
        None, "--page-size", help="Number of items per page"
    ),
):
    """Get all roles granted to a principal, optionally filtered by resource."""
    try:
        service = ResourceRoleService(profile=profile)

        filter_desc = f" on resource {resource_rid}" if resource_rid else ""
        with SpinnerProgressTracker().track_spinner(
            f"Getting roles for {principal_type} '{principal_id}'{filter_desc}..."
        ):
            role_grants = service.get_principal_roles(
                principal_id=principal_id,
                principal_type=principal_type.title(),
                resource_rid=resource_rid,
                page_size=page_size,
            )

        if not role_grants:
            formatter.print_info(
                f"No roles found for {principal_type} '{principal_id}'."
            )
            return

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(role_grants, output, "json")
            else:
                formatter.format_list(role_grants)
        elif format == "csv":
            if output:
                formatter.save_to_file(role_grants, output, "csv")
            else:
                formatter.format_list(role_grants)
        else:
            _format_role_grants_table(role_grants)

        if output:
            formatter.print_success(f"Role grants saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get principal roles: {e}")
        raise typer.Exit(1)


@app.command("get-available-roles")
def get_available_roles(
    resource_rid: str = typer.Argument(
        ..., help="Resource Identifier", autocompletion=complete_rid
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Profile name", autocompletion=complete_profile
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Get all available roles for a resource type."""
    try:
        service = ResourceRoleService(profile=profile)

        with SpinnerProgressTracker().track_spinner(
            f"Getting available roles for {resource_rid}..."
        ):
            roles = service.get_available_roles(resource_rid)

        if not roles:
            formatter.print_info(
                f"No available roles found for resource {resource_rid}."
            )
            return

        # Format output
        if format == "json":
            if output:
                formatter.save_to_file(roles, output, "json")
            else:
                formatter.format_list(roles)
        elif format == "csv":
            if output:
                formatter.save_to_file(roles, output, "csv")
            else:
                formatter.format_list(roles)
        else:
            _format_available_roles_table(roles)

        if output:
            formatter.print_success(f"Available roles saved to {output}")

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to get available roles: {e}")
        raise typer.Exit(1)


def _format_role_grant_table(role_grant: dict):
    """Format role grant information as a table."""
    table = Table(
        title="Role Grant Information", show_header=True, header_style="bold cyan"
    )
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Resource RID", role_grant.get("resource_rid", "N/A"))
    table.add_row("Principal ID", role_grant.get("principal_id", "N/A"))
    table.add_row("Principal Type", role_grant.get("principal_type", "N/A"))
    table.add_row("Role Name", role_grant.get("role_name", "N/A"))
    table.add_row("Granted By", role_grant.get("granted_by", "N/A"))
    table.add_row("Granted Time", role_grant.get("granted_time", "N/A"))
    table.add_row("Expires At", role_grant.get("expires_at", "N/A"))

    console.print(table)


def _format_role_grants_table(role_grants: List[dict]):
    """Format multiple role grants as a table."""
    table = Table(title="Role Grants", show_header=True, header_style="bold cyan")
    table.add_column("Principal Type")
    table.add_column("Principal ID")
    table.add_column("Role Name")
    table.add_column("Granted By")
    table.add_column("Granted Time")

    for grant in role_grants:
        table.add_row(
            grant.get("principal_type", "N/A"),
            grant.get("principal_id", "N/A"),
            grant.get("role_name", "N/A"),
            grant.get("granted_by", "N/A"),
            grant.get("granted_time", "N/A"),
        )

    console.print(table)
    console.print(f"\nTotal: {len(role_grants)} role grants")


def _format_available_roles_table(roles: List[dict]):
    """Format available roles as a table."""
    table = Table(title="Available Roles", show_header=True, header_style="bold cyan")
    table.add_column("Name")
    table.add_column("Display Name")
    table.add_column("Description")
    table.add_column("Owner-like")

    for role in roles:
        table.add_row(
            role.get("name", "N/A"),
            role.get("display_name", "N/A"),
            role.get("description", "N/A"),
            "Yes" if role.get("is_owner_like", False) else "No",
        )

    console.print(table)
    console.print(f"\nTotal: {len(roles)} available roles")


@app.callback()
def main():
    """
    Resource Role operations using foundry-platform-sdk.

    Manage permissions and access control for resources in the Foundry filesystem.
    Grant and revoke roles for users and groups on specific resources.

    Examples:
        # Grant a role to a user
        pltr resource-role grant ri.compass.main.dataset.xyz123 \\
            --principal-id user123 --principal-type User --role viewer

        # Grant a role to a group
        pltr resource-role grant ri.compass.main.project.abc456 \\
            --principal-id group789 --principal-type Group --role editor

        # List all roles on a resource
        pltr resource-role list ri.compass.main.dataset.xyz123

        # List only user roles on a resource
        pltr resource-role list ri.compass.main.dataset.xyz123 --principal-type User

        # Get all roles for a specific user
        pltr resource-role get-principal-roles \\
            --principal-id user123 --principal-type User

        # Get roles for a user on a specific resource
        pltr resource-role get-principal-roles \\
            --principal-id user123 --principal-type User \\
            --resource-rid ri.compass.main.dataset.xyz123

        # See what roles are available for a resource
        pltr resource-role get-available-roles ri.compass.main.dataset.xyz123

        # Revoke a role from a user
        pltr resource-role revoke ri.compass.main.dataset.xyz123 \\
            --principal-id user123 --principal-type User --role viewer
    """
    pass
