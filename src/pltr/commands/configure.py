"""
Profile commands: create, list, select and delete authentication profiles.

These commands touch only local state (``profiles.json`` in the configuration
directory and the system keyring, which holds each profile's credentials);
they make no Foundry API call. They follow the shared contract: messages and
prompts on stderr, ``--format json`` output on stdout, structured errors and
the documented exit codes. Nothing is prompted when stdin is not a terminal.
"""

from typing import Any, Dict, List, Optional

import click
import typer
from typing_extensions import Annotated

from ..auth.base import ProfileNotFoundError
from ..auth.storage import CredentialStorage
from ..config.profiles import ProfileManager
from ..contract import (
    Columns,
    ExitCode,
    ForceAliasOption,
    FormatOption,
    OutputOption,
    PltrError,
    YesOption,
    confirm_destructive,
    emit,
    info,
    pltr_command,
    stdin_is_interactive,
    success,
    warn,
)
from ..utils.completion import complete_profile

app = typer.Typer()

AUTH_TYPES = ("token", "oauth")

#: Table/CSV columns for ``list-profiles`` (one row per profile).
PROFILE_COLUMNS: Columns = {"Profile": "name", "Default": "default"}

ProfileName = Annotated[
    str,
    typer.Argument(
        help="Profile name (see 'pltr configure list-profiles').",
        autocompletion=complete_profile,
    ),
]


def _profile_not_found(profile: str, manager: ProfileManager) -> PltrError:
    names = manager.list_profiles()
    known = (
        f" Configured profiles: {', '.join(names)}."
        if names
        else " None is configured."
    )
    return PltrError(
        f"Profile '{profile}' not found.{known}",
        error_type="not_found",
        exit_code=ExitCode.NOT_FOUND,
        hint="Create it with 'pltr configure configure --profile NAME'.",
    )


def _prompt(label: str, *, password: bool = False, choices: Any = None) -> str:
    """Ask for a value on stderr (never stdout) until one is given."""
    from rich.console import Console
    from rich.prompt import Prompt

    console = Console(stderr=True)
    while True:
        value = Prompt.ask(
            label,
            console=console,
            password=password,
            choices=list(choices) if choices else None,
        )
        if value and value.strip():
            return value.strip()
        console.print("A value is required.", style="red")


def _infer_auth_type(
    token: Optional[str], client_id: Optional[str], client_secret: Optional[str]
) -> Optional[str]:
    """The auth type the given credential options imply, if unambiguous."""
    if token and not (client_id or client_secret):
        return "token"
    if (client_id or client_secret) and not token:
        return "oauth"
    return None


@app.command()
@pltr_command(destructive=True)
def configure(
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Name of the profile to create or replace.",
            autocompletion=complete_profile,
        ),
    ] = "default",
    auth_type: Annotated[
        Optional[str],
        typer.Option(
            "--auth-type",
            click_type=click.Choice(AUTH_TYPES),
            help=(
                "Authentication type: token or oauth (default: implied by --token "
                "or --client-id/--client-secret)."
            ),
            show_default=False,
        ),
    ] = None,
    host: Annotated[
        Optional[str],
        typer.Option(
            "--host",
            help="Foundry host, e.g. https://your-stack.palantirfoundry.com.",
            show_default=False,
        ),
    ] = None,
    token: Annotated[
        Optional[str],
        typer.Option("--token", help="Bearer token (token auth).", show_default=False),
    ] = None,
    client_id: Annotated[
        Optional[str],
        typer.Option(
            "--client-id", help="OAuth client ID (oauth auth).", show_default=False
        ),
    ] = None,
    client_secret: Annotated[
        Optional[str],
        typer.Option(
            "--client-secret",
            help="OAuth client secret (oauth auth).",
            show_default=False,
        ),
    ] = None,
    yes: YesOption = False,
    format: FormatOption = "table",
):
    """Create a profile, or replace an existing one (asks first; --yes skips).

    The credentials are stored in the system keyring. Values you don't pass
    as options are prompted for. When stdin is not a terminal nothing is
    prompted: pass --host and the credentials (--token, or --client-id and
    --client-secret) as options, and --yes to replace an existing profile.
    Where no keyring is available (CI, containers, agents), skip profiles and
    set FOUNDRY_HOST and FOUNDRY_TOKEN instead.
    """
    profile = profile or "default"
    interactive = stdin_is_interactive()

    auth_type = auth_type or _infer_auth_type(token, client_id, client_secret)
    if auth_type == "token" and (client_id or client_secret):
        raise typer.BadParameter(
            "--client-id and --client-secret are for --auth-type oauth",
            param_hint="'--auth-type'",
        )
    if auth_type == "oauth" and token:
        raise typer.BadParameter(
            "--token is for --auth-type token", param_hint="'--auth-type'"
        )
    if not interactive:
        missing = ["--host"] if not host else []
        if auth_type is None:
            missing.append("--token (or --client-id and --client-secret)")
        elif auth_type == "token" and not token:
            missing.append("--token")
        elif auth_type == "oauth":
            missing += [
                flag
                for flag, value in (
                    ("--client-id", client_id),
                    ("--client-secret", client_secret),
                )
                if not value
            ]
        if missing:
            raise typer.BadParameter(
                f"missing {', '.join(missing)}. Values that aren't passed as "
                "options are prompted for, but stdin is not a terminal."
            )

    storage = CredentialStorage()
    # Checked before any prompt: also fails fast when there is no usable keyring.
    if storage.profile_exists(profile):
        confirm_destructive(
            f"Profile '{profile}' already exists. Replace its credentials?", yes=yes
        )

    if auth_type is None:
        auth_type = _prompt("Authentication type", choices=AUTH_TYPES)
    if not host:
        host = _prompt("Foundry host (e.g. https://your-stack.palantirfoundry.com)")
    credentials: Dict[str, Any] = {"auth_type": auth_type, "host": host}
    if auth_type == "token":
        credentials["token"] = token or _prompt("Bearer token", password=True)
    else:
        credentials["client_id"] = client_id or _prompt("OAuth client ID")
        credentials["client_secret"] = client_secret or _prompt(
            "OAuth client secret", password=True
        )

    storage.save_profile(profile, credentials)
    manager = ProfileManager()
    manager.add_profile(profile)
    if manager.get_default() is None or len(manager.list_profiles()) == 1:
        manager.set_default(profile)
        success(f"Profile '{profile}' configured and set as the default")
    else:
        success(f"Profile '{profile}' configured")
    emit(None, format=format)


@app.command("list-profiles")
@pltr_command()
def list_profiles(
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """List the configured profiles and which one is the default.

    Reads only the local profile list; credentials stay in the keyring.
    """
    manager = ProfileManager()
    default = manager.get_default()
    profiles: List[Dict[str, Any]] = [
        {"name": name, "default": name == default} for name in manager.list_profiles()
    ]
    emit(profiles, format=format, output=output, columns=PROFILE_COLUMNS)
    if not profiles:
        info(
            "No profiles configured. Run 'pltr configure configure' to create one, "
            "or set FOUNDRY_HOST and FOUNDRY_TOKEN to use pltr without a profile."
        )


@app.command("set-default")
@pltr_command()
def set_default(
    profile: ProfileName,
    format: FormatOption = "table",
):
    """Make a profile the default for commands run without --profile."""
    manager = ProfileManager()
    if profile not in manager.list_profiles():
        raise _profile_not_found(profile, manager)
    manager.set_default(profile)
    success(f"Profile '{profile}' is now the default")
    emit(None, format=format)


@app.command()
@pltr_command(destructive=True)
def delete(
    profile: ProfileName,
    yes: YesOption = False,
    force: ForceAliasOption = False,
    format: FormatOption = "table",
):
    """Delete a profile and its stored credentials (asks first; --yes skips)."""
    manager = ProfileManager()
    if profile not in manager.list_profiles():
        raise _profile_not_found(profile, manager)
    confirm_destructive(f"Delete profile '{profile}' and its credentials?", yes=yes)

    try:
        CredentialStorage().delete_profile(profile)
    except ProfileNotFoundError:
        warn(f"The keyring held no credentials for profile '{profile}'.")
    was_default = manager.get_default() == profile
    manager.remove_profile(profile)
    success(f"Deleted profile '{profile}'")
    if was_default:
        new_default = manager.get_default()
        info(
            f"The default profile is now '{new_default}'."
            if new_default
            else "No default profile is set now."
        )
    emit(None, format=format)
